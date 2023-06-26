# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import typing

import ops
from PyQt5.QtWidgets import QGraphicsItem
from nodeeditor.node_edge import EDGE_TYPE_DEFAULT
from nodeeditor.node_edge_dragging import EdgeDragging as _EdgeDragging
from nodeeditor.node_editor_widget import NodeEditorWidget as _NodeEditorWidget
from nodeeditor.node_graphics_edge import QDMGraphicsEdge
from nodeeditor.node_graphics_socket import QDMGraphicsSocket
from nodeeditor.node_graphics_view import MODE_EDGE_DRAG, QDMGraphicsView
from nodeeditor.node_node import Node
from nodeeditor.utils import dumpException
from qtpy.QtCore import QDataStream, QIODevice, Qt
from qtpy.QtCore import QPoint
from qtpy.QtCore import Signal
from qtpy.QtGui import QMouseEvent
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import QAction, QGraphicsProxyWidget, QMenu
from qtpy.QtWidgets import QVBoxLayout

from logger import logger
from theatre.helpers import get_icon
from theatre.theatre_scene import TheatreScene
from theatre.trace_tree_widget.event_dialog import EventPicker, EventSpec
from theatre.trace_tree_widget.event_edge import EventEdge
from theatre.trace_tree_widget.library_widget import (
    STATE_SPEC_LIBRARY_ENTRY_MIMETYPE,
    get_sorted_state_specs, get_spec,
)
from theatre.trace_tree_widget.new_state_dialog import NewStateDialog, StateIntent
from theatre.trace_tree_widget.state_node import (
    StateNode,
    GraphicsSocket,
    StateContent,
    create_new_node,
)

DEBUG = False
DEBUG_CONTEXT = False


def choose_event(parent=None) -> typing.Optional[EventSpec]:
    event_picker = EventPicker(parent)
    event_picker.exec()

    if not event_picker.confirmed:
        logger.info("event picker aborted")
        return

    return event_picker.get_event()


def get_new_custom_state(parent=None) -> typing.Optional[StateIntent]:
    dialog = NewStateDialog(parent)
    dialog.exec()

    if not dialog.confirmed:
        logger.info("new state dialog aborted")
        return

    return dialog.finalize()


class EdgeDragging(_EdgeDragging):
    drag_edge: EventEdge

    def edgeDragEnd(self, item: 'GraphicsSocket'):
        # preserve the spec as edgeDragEnd removes the old edge and creates a new one.
        spec = self.drag_edge.event_spec
        super().edgeDragEnd(item)
        self.drag_edge.set_event_spec(spec)


class GraphicsView(QDMGraphicsView):
    drag_lmb_bg_click = Signal(QPoint)

    def leftMouseButtonPress(self, event: QMouseEvent):
        item_clicked = self.getItemAtClick(event)
        if self.mode is MODE_EDGE_DRAG and not item_clicked:
            # RMB when dragging an edge; didn't click on anything specific:
            self.drag_lmb_bg_click.emit(event.pos())
            event.accept()
        else:
            event.ignore()
            super().leftMouseButtonPress(event)



class NodeEditorWidget(_NodeEditorWidget):
    view: GraphicsView
    scene: TheatreScene
    state_node_created = Signal(StateIntent)
    state_node_changed = Signal(StateNode)
    state_node_clicked = Signal(StateNode)

    def __init__(self, charm_type: typing.Type[ops.CharmBase], parent=None):
        super().__init__(parent)

        self.update_title()
        self.chain_on_new_node = True
        self.charm_type = charm_type

        self._create_new_state_actions()

        self.scene.addHasBeenModifiedListener(self.update_title)
        self.scene.history.addHistoryRestoredListener(self.on_history_restored)
        self.scene.addDragEnterListener(self.on_drag_enter)
        self.scene.addDropListener(self.on_drop)
        self.scene.setNodeClassSelector(self._get_node_class_from_data)
        self.view.drag_lmb_bg_click.connect(self._create_new_node_at)

        self._close_event_listeners = []

    def initUI(self):
        """Set up this ``NodeEditorWidget`` with its layout.`"""
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

        # crate graphics scene
        self.scene = scene = TheatreScene()
        scene.state_node_changed.connect(self.state_node_changed)
        scene.state_node_clicked.connect(self.state_node_clicked)

        # create graphics view
        self.view = GraphicsView(self.scene.grScene, self)

        self.layout.addWidget(self.view)
        self._init_actions()

    def _init_actions(self):
        self._new_state_action = QAction(
            "New State",
            self,
            statusTip="Create a new custom state.",
            triggered=self.create_new_custom_state,
            icon=get_icon("edit_square")
        )

    def _create_new_node_at(self, pos: QPoint):
        """RMB While dragging on bg:

        - pick an event to put on this edge.
        - create a new node where we are.
        - link old node to new node.
        """
        event_spec = choose_event()
        scene: "TheatreScene" = self.scene

        new_state_node = create_new_node(scene, self.view, pos)
        dragging: EdgeDragging = self.view.dragging
        target_socket = new_state_node.input_socket

        # create a new edge
        EventEdge(
            scene,
            dragging.drag_start_socket,
            target_socket,
            edge_type=EDGE_TYPE_DEFAULT,
            event_spec=event_spec,
        )

        if self.chain_on_new_node:
            new_origin = new_state_node.output_socket
            x, y = new_state_node.getSocketScenePosition(new_origin)
            dragging.drag_start_socket = new_origin
            dragging.drag_edge.grEdge.setSource(x, y)
            dragging.drag_edge.grEdge.update()
            new_state_node._update_title()

        else:
            dragging.edgeDragEnd(None)

    @staticmethod
    def _get_node_class_from_data(data):
        if "name" not in data:
            return Node
        # state = get_state(data['name'])
        return StateNode

    def eval_outputs(self):
        # eval all output nodes
        for node in self.scene.nodes:
            if node.__class__.__name__ == "CalcNode_Output":
                node.eval()

    def on_history_restored(self):
        self.eval_outputs()

    def fileLoad(self, filename):
        if super().fileLoad(filename):
            self.eval_outputs()
            return True

        return False

    def _create_new_state_actions(self):
        self.state_actions = {}
        for state in get_sorted_state_specs():
            self.state_actions[state.name] = QAction(state.icon, state.name)
            self.state_actions[state.name].setData(state.name)

    def update_title(self):
        self.setWindowTitle(self.getUserFriendlyFilename())

    def add_close_event_listener(self, callback):
        self._close_event_listeners.append(callback)

    def closeEvent(self, event):
        for callback in self._close_event_listeners:
            callback(self, event)

    def on_drag_enter(self, event):
        if event.mimeData().hasFormat(STATE_SPEC_LIBRARY_ENTRY_MIMETYPE):
            event.acceptProposedAction()
        else:
            logger.info(f"denied drag enter evt on {self}")
            event.setAccepted(False)

    def on_drop(self, event):
        if event.mimeData().hasFormat(STATE_SPEC_LIBRARY_ENTRY_MIMETYPE):
            event_data = event.mimeData().data(STATE_SPEC_LIBRARY_ENTRY_MIMETYPE)
            data_stream = QDataStream(event_data, QIODevice.ReadOnly)
            pixmap = QPixmap()
            data_stream >> pixmap
            name = data_stream.readQString()
            spec = get_spec(name)

            try:
                node = create_new_node(
                    scene=self.scene, view=self.view,
                    pos=event.pos(),
                    name=name, icon=spec.icon
                )
                node.set_custom_value(spec.state)
                self.scene.history.storeHistory(
                    "Created node %s" % node.__class__.__name__
                )
            except Exception as e:
                dumpException(e)

            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            # print(" ... drop ignored, not requested format '%s'" % STATE_SPEC_LIBRARY_ENTRY_MIMETYPE)
            event.ignore()

    def find_nearest_parent_at(self, pos: QPoint, types: typing.Tuple[type]):
        """Climb up the widget hierarchy until we find a parent of one of the desired types."""
        item = self.scene.getItemAt(pos)
        if type(item) == QGraphicsProxyWidget:
            item = item.widget()

        while item:
            if isinstance(item, types):
                return item

            if not hasattr(item, "parent"):  # FIXME
                raise TypeError(f"what kind of item is this? {item}")

            item = item.parent()
        return item

    def contextMenuEvent(self, event):
        try:
            item = self.find_nearest_parent_at(
                event.pos(), (GraphicsSocket, StateContent, QDMGraphicsEdge)
            )
            if isinstance(item, (GraphicsSocket, StateContent)):
                self._on_state_context_menu(event)
            elif isinstance(item, QDMGraphicsEdge):
                if self.view.mode != MODE_EDGE_DRAG:
                    # if you're not dragging an edge and RMB on it:
                    self._on_edge_context_menu(event, item.edge)
            else:  # click on background
                if self.view.mode == MODE_EDGE_DRAG:
                    # If you were dragging, stop dragging
                    dragging: EdgeDragging = self.view.dragging
                    dragging.edgeDragEnd(None)
                else:
                    self._on_background_context_menu(event)

            return super().contextMenuEvent(event)
        except Exception as e:
            dumpException(e)

    def _on_state_context_menu(self, event):
        context_menu = QMenu(self)
        mark_dirty_action = context_menu.addAction(get_icon("recycling"), "Mark Dirty")
        evaluate_action = context_menu.addAction(get_icon("start"), "Evaluate")
        edit_action = context_menu.addAction(get_icon("edit"), "Edit")
        # markDirtyDescendantsAct = context_menu.addAction("Mark Descendant Dirty")
        # markInvalidAct = context_menu.addAction("Mark Invalid")
        # unmarkInvalidAct = context_menu.addAction("Unmark Invalid")
        # evalAct = context_menu.addAction("Eval")
        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        item = self.scene.getItemAt(event.pos())
        if isinstance(item, QGraphicsProxyWidget):
            item = item.widget()

        selected: StateNode
        if hasattr(item, "node"):
            selected = item.node
        elif hasattr(item, "socket"):
            selected = item.socket.node
        else:
            logger.error(f"invalid clicked item: {item}")
            return

        # dispatch
        if action == mark_dirty_action:
            selected.markDirty()
        elif action == evaluate_action:
            selected.eval()
        elif action == edit_action:
            selected.open_edit_dialog(self)
            self.state_node_changed.emit(selected)
        else:
            logger.error(f"unhandled action: {action}")

    def _on_edge_context_menu(self, event, edge: "EventEdge"):
        context_menu = QMenu(self)
        change_event_action = context_menu.addAction("Change event")
        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        if action == change_event_action:
            event_spec = choose_event()
            edge.set_event_spec(event_spec)  # this will notify the end node

        # bezierAct = context_menu.addAction("Bezier Edge")
        # directAct = context_menu.addAction("Direct Edge")
        # squareAct = context_menu.addAction("Square Edge")
        # action = context_menu.exec_(self.mapToGlobal(event.pos()))
        #
        # selected = None
        # item = self.scene.getItemAt(event.pos())
        # if hasattr(item, "edge"):
        #     selected = item.edge
        #
        # if selected and action == bezierAct:
        #     selected.edge_type = EDGE_TYPE_BEZIER
        # if selected and action == directAct:
        #     selected.edge_type = EDGE_TYPE_DIRECT
        # if selected and action == squareAct:
        #     selected.edge_type = EDGE_TYPE_SQUARE

    def _finalize_node(self, new_state_node):
        self.scene.doDeselectItems()
        new_state_node.grNode.doSelect(True)
        new_state_node.grNode.onSelected()

    def _new_node(self, pos: QPoint = None) -> StateNode:
        # todo: check this out
        pos = pos or self.view.scene().sceneRect().center().toPoint()
        return create_new_node(scene=self.scene,
                               view=self.view,
                               pos=pos)

    def _on_background_context_menu(self, event):
        menu = QMenu(self)
        menu.addAction(self._new_state_action)

        for state in get_sorted_state_specs():
            menu.addAction(self.state_actions[state.name])

        action = menu.exec_(self.mapToGlobal(event.pos()))
        logger.info(f'triggered {action}')

        if action is not None:
            node = self._new_node(pos=event.pos())
            self.scene.history.storeHistory("Created %s" % node.__class__.__name__)

    def create_new_custom_state(self):
        state_intent = get_new_custom_state(self)
        if state_intent is None:
            logger.info("new state creation aborted")
            return

        logger.info(f"created new state! {state_intent}")
        node = self._new_node()
        node.set_custom_value(state_intent.state)
        self.state_node_created.emit(state_intent)
