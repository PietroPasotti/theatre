from PyQt5.QtCore import QEvent
from nodeeditor.node_edge import EDGE_TYPE_DIRECT, EDGE_TYPE_BEZIER, EDGE_TYPE_SQUARE, EDGE_TYPE_DEFAULT
from nodeeditor.node_edge_dragging import EdgeDragging
from nodeeditor.node_editor_widget import NodeEditorWidget
from nodeeditor.node_graphics_edge import QDMGraphicsEdge
from nodeeditor.node_graphics_view import MODE_EDGE_DRAG
from nodeeditor.node_node import Node
from nodeeditor.utils import dumpException
from qtpy.QtCore import QDataStream, QIODevice, Qt
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import QAction, QGraphicsProxyWidget, QMenu

from logger import logger
from ui.trace_tree_widget.event_edge import EventEdge
from ui.trace_tree_widget.conf import STATES, LISTBOX_MIMETYPE
from ui.trace_tree_widget.event_dialog import EventPicker
from ui.trace_tree_widget.state_node import StateNode, GraphicsSocket

DEBUG = False
DEBUG_CONTEXT = False


class TraceTreeEditor(NodeEditorWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.update_title()
        self.chain_on_new_node = True

        self._create_new_state_actions()

        self.scene.addHasBeenModifiedListener(self.update_title)
        self.scene.history.addHistoryRestoredListener(self.on_history_restored)
        self.scene.addDragEnterListener(self.on_drag_enter)
        self.scene.addDropListener(self.on_drop)
        self.scene.setNodeClassSelector(self._get_node_class_from_data)

        self._close_event_listeners = []

    def _get_node_class_from_data(self, data):
        if "name" not in data:
            return Node
        # state = get_state(data['name'])
        return StateNode

    def doEvalOutputs(self):
        # eval all output nodes
        for node in self.scene.nodes:
            if node.__class__.__name__ == "CalcNode_Output":
                node.eval()

    def on_history_restored(self):
        self.doEvalOutputs()

    def fileLoad(self, filename):
        if super().fileLoad(filename):
            self.doEvalOutputs()
            return True

        return False

    def _create_new_state_actions(self):
        self.state_actions = {}
        keys = list(STATES.keys())
        keys.sort()
        for key in keys:
            node_spec = STATES[key]
            self.state_actions[key] = QAction(node_spec.icon, key)
            self.state_actions[key].setData(key)

    def update_title(self):
        self.setWindowTitle(self.getUserFriendlyFilename())

    def addCloseEventListener(self, callback):
        self._close_event_listeners.append(callback)

    def closeEvent(self, event):
        for callback in self._close_event_listeners:
            callback(self, event)

    def on_drag_enter(self, event):
        if event.mimeData().hasFormat(LISTBOX_MIMETYPE):
            event.acceptProposedAction()
        else:
            # print(" ... denied drag enter event")
            event.setAccepted(False)

    def on_drop(self, event):
        if event.mimeData().hasFormat(LISTBOX_MIMETYPE):
            eventData = event.mimeData().data(LISTBOX_MIMETYPE)
            dataStream = QDataStream(eventData, QIODevice.ReadOnly)
            pixmap = QPixmap()
            dataStream >> pixmap
            name = dataStream.readQString()
            text = dataStream.readQString()

            mouse_position = event.pos()
            scene_position = self.scene.grScene.views()[0].mapToScene(mouse_position)

            if DEBUG:
                print(
                    "GOT DROP: [%d] '%s'" % (name, text),
                    "mouse:",
                    mouse_position,
                    "scene:",
                    scene_position,
                )

            try:
                node = StateNode(self.scene, name)
                node.setPos(scene_position.x(), scene_position.y())
                self.scene.history.storeHistory(
                    "Created node %s" % node.__class__.__name__
                )
            except Exception as e:
                dumpException(e)

            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            # print(" ... drop ignored, not requested format '%s'" % LISTBOX_MIMETYPE)
            event.ignore()

    def contextMenuEvent(self, event):
        try:
            item = self.scene.getItemAt(event.pos())
            if DEBUG_CONTEXT:
                print(item)

            if type(item) == QGraphicsProxyWidget:
                item = item.widget()

            print(item)

            if isinstance(item, GraphicsSocket):
                self._on_state_context_menu(event)
            if isinstance(item, StateNode):
                self._on_state_context_menu(event)
            elif isinstance(item, QDMGraphicsEdge):
                self._on_edge_context_menu(event)
            else:  # click on background
                self._on_background_context_menu(event)

            return super().contextMenuEvent(event)
        except Exception as e:
            dumpException(e)

    def _on_state_context_menu(self, event):
        context_menu = QMenu(self)
        # markDirtyAct = context_menu.addAction("Mark Dirty")
        # markDirtyDescendantsAct = context_menu.addAction("Mark Descendant Dirty")
        # markInvalidAct = context_menu.addAction("Mark Invalid")
        # unmarkInvalidAct = context_menu.addAction("Unmark Invalid")
        # evalAct = context_menu.addAction("Eval")
        fire_event = context_menu.addAction("Event")
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
            logger.error(f'invalid clicked item: {item}')
            return

        if selected and action == fire_event:
            selected.fire_event()

    def _on_edge_context_menu(self, event):
        context_menu = QMenu(self)
        bezierAct = context_menu.addAction("Bezier Edge")
        directAct = context_menu.addAction("Direct Edge")
        squareAct = context_menu.addAction("Square Edge")
        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        selected = None
        item = self.scene.getItemAt(event.pos())
        if hasattr(item, "edge"):
            selected = item.edge

        if selected and action == bezierAct:
            selected.edge_type = EDGE_TYPE_BEZIER
        if selected and action == directAct:
            selected.edge_type = EDGE_TYPE_DIRECT
        if selected and action == squareAct:
            selected.edge_type = EDGE_TYPE_SQUARE

    # helper functions
    def determine_target_socket_of_node(self, was_dragged_flag, new_state_node):
        target_socket = None
        if was_dragged_flag:
            if len(new_state_node.inputs) > 0:
                target_socket = new_state_node.inputs[0]
        else:
            if len(new_state_node.outputs) > 0:
                target_socket = new_state_node.outputs[0]
        return target_socket

    def _finalize_node(self, new_state_node):
        self.scene.doDeselectItems()
        new_state_node.grNode.doSelect(True)
        new_state_node.grNode.onSelected()

    def _on_edge_drag_context_menu(self, event: QEvent):
        # if we were dragging an edge...
        # target_socket = self.determine_target_socket_of_node(
        #     self.scene.getView().dragging.drag_start_socket.is_output,
        #     new_state_node,
        # )
        # if target_socket is not None:
        #     self.scene.getView().dragging.edgeDragEnd(target_socket.grSocket)
        #     self._finalize_node(new_state_node)
        event_picker = EventPicker()
        event_picker.exec()

        if not event_picker.confirmed:
            logger.info('event picker aborted')
            return event.ignore()

        _evt = event_picker.get_event()
        new_state_node = self._new_state_at(event.pos())

        dragging: EdgeDragging = self.scene.getView().dragging
        target_socket = self.determine_target_socket_of_node(
            dragging.drag_start_socket.is_output,
            new_state_node,
        )

        new_event_edge = EventEdge(
            self.scene,
            dragging.drag_start_socket,
            target_socket,
            edge_type=EDGE_TYPE_DEFAULT,
            label=_evt.event.name  # todo: replace with label`
        )
        dragging.edgeDragEnd(None)

        if self.chain_on_new_node or event.modifiers() & Qt.CTRL:
            # RMB+ctrl -> chain another edge
            dragging.edgeDragStart(new_state_node.outputs[0].grSocket)
            event.accept()

    def _on_background_context_menu(self, event):
        if self.scene.getView().mode == MODE_EDGE_DRAG:
            return self._on_edge_drag_context_menu(event)

        context_menu = QMenu(self)
        keys = list(STATES.keys())
        keys.sort()
        for key in keys:
            context_menu.addAction(self.state_actions[key])

        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        if action is not None:
            new_state_node = StateNode(self.scene)
            scene_pos = self.scene.getView().mapToScene(event.pos())
            new_state_node.setPos(scene_pos.x(), scene_pos.y())
            self.scene.history.storeHistory(
                "Created %s" % new_state_node.__class__.__name__
            )

    def _new_state_at(self, pos):
        new_state_node = StateNode(self.scene)
        scene_pos = self.scene.getView().mapToScene(pos)
        new_state_node.setPos(scene_pos.x(), scene_pos.y())
        return new_state_node
