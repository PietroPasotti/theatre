# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import json
import os
import typing
from functools import partial
from pathlib import Path

from nodeeditor.node_edge import EDGE_TYPE_DEFAULT
from nodeeditor.node_edge_dragging import EdgeDragging as _EdgeDragging
from nodeeditor.node_editor_widget import NodeEditorWidget as _NodeEditorWidget
from nodeeditor.node_graphics_edge import QDMGraphicsEdge
from nodeeditor.node_graphics_view import MODE_EDGE_DRAG, QDMGraphicsView
from nodeeditor.node_node import Node
from nodeeditor.utils import dumpException
from PyQt5.QtCore import QMimeData
from qtpy.QtCore import QDataStream, QEvent, QIODevice, QPoint, Qt, Signal
from qtpy.QtGui import QDragMoveEvent, QMouseEvent, QWheelEvent
from qtpy.QtWidgets import QAction, QGraphicsProxyWidget, QMenu, QVBoxLayout
from scenario import Event, Relation, State

from theatre.dialogs.relation_picker import RelationPickerDialog
from theatre.dialogs.event_dialog import LIFECYCLE_EVENTS, EventPicker, EventSpec
from theatre.dialogs.file_backed_edit_dialog import Intent
from theatre.dialogs.new_state import NewStateDialog
from theatre.helpers import get_icon, show_error_dialog
from theatre.logger import logger
from theatre.theatre_scene import SerializedScene, TheatreScene
from theatre.trace_tree_widget.event_edge import EventEdge
from theatre.trace_tree_widget.library_widget import (
    DYNAMIC_STATE_SPEC_MIMETYPE,
    DYNAMIC_SUBTREE_SPEC_MIMETYPE,
    DYNAMIC_SUBTREES_TEMPLATES_DIR,
    STATE_SPEC_MIMETYPE,
    SUBTREE_SPEC_MIMETYPE,
    DynamicStateSpec,
    DynamicSubtreeName,
    DynamicSubtreeSpec,
    StateSpec,
    SubtreeSpec,
    get_sorted_entries,
    get_spec,
)
from theatre.trace_tree_widget.state_bases import GraphicsSocket
from theatre.trace_tree_widget.state_node import (
    StateContent,
    StateNode,
    add_simulated_fs_from_repo,
    create_new_node,
)
from theatre.trace_tree_widget.utils import autolayout

if typing.TYPE_CHECKING:
    from theatre.main_window import TheatreMainWindow

DEBUG = False
DEBUG_CONTEXT = False


def get_new_custom_state(parent=None) -> typing.Optional[Intent[State]]:
    dialog = NewStateDialog(parent)
    dialog.exec()

    if not dialog.confirmed:
        logger.info("new state dialog aborted")
        return

    return dialog.finalize()


class EdgeDragging(_EdgeDragging):
    drag_edge: EventEdge

    def edgeDragEnd(self, item: "GraphicsSocket"):
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

    def dragMoveEvent(self, event: QDragMoveEvent):
        mime_data = event.mimeData()
        scene: TheatreScene = self.parent().scene
        if mime_data.hasFormat(STATE_SPEC_MIMETYPE) or mime_data.hasFormat(
            DYNAMIC_STATE_SPEC_MIMETYPE
        ):
            is_hovering_bg = scene.getItemAt(event.pos()) is None
            event.setAccepted(is_hovering_bg)
        elif mime_data.hasFormat(SUBTREE_SPEC_MIMETYPE) or mime_data.hasFormat(
            DYNAMIC_SUBTREE_SPEC_MIMETYPE
        ):
            is_hovering_node = scene.get_node_at(event.pos())
            event.setAccepted(bool(is_hovering_node))
        else:
            event.setAccepted(False)

    def wheelEvent(self, event: QWheelEvent):
        """overridden Qt's ``wheelEvent``. This handles zooming"""
        if event.modifiers() & Qt.CTRL:
            zoom_out_factor = 1 / self.zoomInFactor
            delta = event.angleDelta().y()
            if delta == 0:  # wheel button being pressed
                event.ignore()
                return

            if delta > 0:
                zoom_factor = self.zoomInFactor
                self.zoom += self.zoomStep
            else:
                zoom_factor = zoom_out_factor
                self.zoom -= self.zoomStep

            clamped = False
            if self.zoom < self.zoomRange[0]:
                self.zoom, clamped = self.zoomRange[0], True
            if self.zoom > self.zoomRange[1]:
                self.zoom, clamped = self.zoomRange[1], True

            # set scene scale
            if not clamped or self.zoomClamp is False:
                self.scale(zoom_factor, zoom_factor)
            event.accept()

        elif event.modifiers() & Qt.SHIFT:
            # pos = self.sceneRect().topRight()
            # new_pos = QPointF(pos.x(), pos.y()+50)
            sb = self.horizontalScrollBar()
            # TODO: support inverted scrolling? --> replace - with +
            sb.setValue(sb.value() - event.angleDelta().y())
            event.accept()

        else:
            sb = self.verticalScrollBar()
            sb.setValue(sb.value() - event.angleDelta().y())
            event.accept()


def open_vfs_in_external_editor(root_vfs_tempdir: Path):
    logger.info(f"opening {root_vfs_tempdir} in external navigator...")
    os.system(f"xdg-open {root_vfs_tempdir}")


class NodeEditorWidget(_NodeEditorWidget):
    view: GraphicsView
    scene: TheatreScene
    state_node_created = Signal(Intent)
    state_node_changed = Signal(StateNode)
    state_node_clicked = Signal(StateNode)

    def __init__(self, main_window: "TheatreMainWindow", parent=None):
        self._main_window = main_window
        super().__init__(parent)
        self.update_title()
        self.chain_on_new_node = True
        self._last_added_node: StateNode | None = None
        self._create_new_state_actions()

        self.scene.addHasBeenModifiedListener(self.update_title)
        self.scene.history.addHistoryRestoredListener(self.on_history_restored)
        self.scene.addDragEnterListener(self.on_drag_enter)
        self.scene.addDropListener(self.on_drop)
        self.scene.setNodeClassSelector(self._get_node_class_from_data)
        self.view.drag_lmb_bg_click.connect(self._create_new_node_at)

        self._close_event_listeners = []

    @property
    def _charm_spec(self):
        return self._main_window.charm_spec

    def initUI(self):
        """Set up this ``NodeEditorWidget`` with its layout.`"""
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

        # crate graphics scene
        self.scene = scene = TheatreScene(self._main_window)
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
            icon=get_icon("edit_square"),
        )

    def _create_new_node_at(self, pos: QPoint):
        """RMB While dragging on bg:

        - pick an event to put on this edge.
        - create a new node where we are.
        - link old node to new node.
        """
        event_spec = self.choose_event()

        if not event_spec:
            # aborted
            return

        scene: "TheatreScene" = self.scene

        new_state_node = create_new_node(scene, self.view, pos)
        dragging: EdgeDragging = self.view.dragging
        target_socket = new_state_node.input_socket

        # create a new edge
        _new_edge = EventEdge(
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

    def choose_event(self) -> typing.Optional[EventSpec]:
        charm_spec = self._main_window.charm_spec
        event_picker = EventPicker(charm_spec=charm_spec, parent=self)
        event_picker.exec()

        if not event_picker.confirmed:
            logger.info("event picker aborted")
            return

        return event_picker.get_event()

    @staticmethod
    def _get_node_class_from_data(data):
        if "name" not in data:
            return Node
        # state = get_state(data['name'])
        return StateNode

    def eval_outputs(self):
        # eval all output nodes
        for node in self.scene.nodes:
            try:
                node.eval()
            except Exception:
                logger.error(f"error evaluating {node}", exc_info=True)

    def on_history_restored(self):
        self.eval_outputs()

    def fileLoad(self, filename):
        if super().fileLoad(filename):
            # self.eval_outputs()
            return True

        return False

    def _create_new_state_actions(self):
        self.state_actions = {}
        for state in get_sorted_entries(StateSpec):
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
        if (
            event.mimeData().hasFormat(STATE_SPEC_MIMETYPE)
            or event.mimeData().hasFormat(SUBTREE_SPEC_MIMETYPE)
            or event.mimeData().hasFormat(DYNAMIC_SUBTREE_SPEC_MIMETYPE)
            or event.mimeData().hasFormat(DYNAMIC_STATE_SPEC_MIMETYPE)
        ):
            event.acceptProposedAction()
        else:
            logger.info(f"denied drag enter evt on {self}")
            event.setAccepted(False)

    def on_drop(self, event: QEvent):
        # if hovering on background: accept STATE SPEC drops
        # if hovering on state: accept SUBTREE SPEC drops
        mime_data: QMimeData = event.mimeData()

        # TODO: if we're dropping something on a Delta...
        #  will require extending theatre_scene.TheatreScene.get_node_at

        for mimetype, drop_handler_method in (
            (STATE_SPEC_MIMETYPE, self._drop_node),
            (DYNAMIC_STATE_SPEC_MIMETYPE, self._drop_dynamic_node),
            (SUBTREE_SPEC_MIMETYPE, self._drop_subtree),
            (DYNAMIC_SUBTREE_SPEC_MIMETYPE, self._drop_dynamic_subtree),
        ):
            if mime_data.hasFormat(mimetype):
                event_data = mime_data.data(mimetype)
                data_stream = QDataStream(event_data, QIODevice.ReadOnly)
                name = data_stream.readQString()
                spec = get_spec(name)
                logger.debug(f"handling {spec} drop with {drop_handler_method}")
                drop_handler_method(spec, event.pos())
                break

            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            event.ignore()

    def _set_state_on_node(self, node: StateNode, state_in: State):
        """Assign a state to a node and inject the simulated fs from the repo."""
        state_with_fs = add_simulated_fs_from_repo(
            state_in, self.scene.repo, root_vfs=node.root_vfs_tempdir
        )
        node.set_custom_value(state_with_fs)

    def _drop_node(self, spec: StateSpec, pos: QPoint):
        node = create_new_node(
            scene=self.scene, view=self.view, pos=pos, name=spec.name, icon=spec.icon
        )
        self._set_state_on_node(node, spec.state)
        self.scene.history.storeHistory("Created node %s" % node.__class__.__name__)

    def _drop_dynamic_node(self, spec: DynamicStateSpec, pos: QPoint):
        node = create_new_node(
            scene=self.scene, view=self.view, pos=pos, name=spec.name, icon=spec.icon
        )
        raw_state = spec.get_state(self._charm_spec)
        self._set_state_on_node(node, raw_state)
        self.scene.history.storeHistory(f"Created dynamic node {spec.name}")

    def _drop_subtree(self, spec: SubtreeSpec, pos: QPoint):
        start = self.scene.get_node_at(pos)
        self._paste_subtree(start, spec.graph)
        self.scene.history.storeHistory(f"Added subtree {spec.name}")

    def _drop_dynamic_subtree(self, spec: DynamicSubtreeSpec, pos: QPoint):
        start = self.scene.get_node_at(pos)
        self._paste_dynamic_subtree(start, spec)
        self.scene.history.storeHistory(f"Added dynamic subtree {spec.name}")

    def contextMenuEvent(self, event):
        try:
            item = self.scene.find_nearest_parent_at(
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

        context_menu = QMenu(self)
        mark_dirty_action = context_menu.addAction(
            get_icon("recycling"), "Mark Dirty", selected.markDirty
        )
        evaluate_action = context_menu.addAction(
            get_icon("start"), "Evaluate", selected.eval
        )
        force_reeval = context_menu.addAction(get_icon("start"), "Force-reevaluate")
        context_menu.addAction(get_icon("delete"), "Delete node", selected.remove)
        edit_action = context_menu.addAction(get_icon("edit"), "Edit")
        inspect_vfs_action = context_menu.addAction(
            get_icon("folder_copy"), "Inspect virtual filesystem"
        )
        context_menu.addAction(
            get_icon("edit_delta"),
            "Deltas",
            lambda: selected.open_edit_deltas_dialog(self),
        )
        branch_submenu = context_menu.addMenu(get_icon("arrow_split"), "Branch")
        branch_actions = []
        subtree: SubtreeSpec
        for subtree in get_sorted_entries((SubtreeSpec, DynamicSubtreeSpec)):
            branch_action = branch_submenu.addAction(
                subtree.icon,
                subtree.name,
                partial(self._on_branch_action, selected, subtree),
            )
            branch_actions.append(branch_action)

        # markDirtyDescendantsAct = context_menu.addAction("Mark Descendant Dirty")
        # markInvalidAct = context_menu.addAction("Mark Invalid")
        # unmarkInvalidAct = context_menu.addAction("Unmark Invalid")
        # evalAct = context_menu.addAction("Eval")
        if selected.value:  # if the node has a value
            evaluate_action.setEnabled(False)
        else:
            mark_dirty_action.setEnabled(False)

        if not selected.is_root:
            edit_action.setEnabled(False)

        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        # dispatch
        if action == force_reeval:
            selected.markDirty()
            selected.eval()
        elif action == inspect_vfs_action:
            open_vfs_in_external_editor(selected.root_vfs_tempdir)

        elif action == edit_action:
            selected.open_edit_dialog(self)
            self.state_node_changed.emit(selected)
        else:
            logger.info(f"chosen action: {action}")
            # other actions should handle themselves

    def _on_edge_context_menu(self, event, edge: "EventEdge"):
        context_menu = QMenu(self)
        change_event_action = context_menu.addAction("Change event")
        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        if action == change_event_action:
            event_spec = self.choose_event()
            edge.set_event_spec(event_spec)  # this will notify the end node

    def _finalize_node(self, new_state_node):
        self.scene.doDeselectItems()
        new_state_node.grNode.doSelect(True)
        new_state_node.grNode.onSelected()

    def _new_node(self, pos: QPoint = None) -> StateNode:
        # fixme: this is the topleft corner, somehow
        pos = pos or self.view.viewport().rect().center()
        new_node = create_new_node(scene=self.scene, view=self.view, pos=pos)
        self.scene.history.storeHistory(f"Created {new_node}")
        self._finalize_node(new_node)
        self._last_added_node = new_node
        return new_node

    def _on_background_context_menu(self, event):
        menu = QMenu(self)
        menu.addAction(self._new_state_action)

        for state in get_sorted_entries():
            if isinstance(state, StateSpec):
                menu.addAction(self.state_actions[state.name])

        pos = event.pos()
        action = menu.exec_(self.mapToGlobal(pos))
        logger.info(f"triggered {action}")

        if action not in [self._new_state_action, None]:
            # only action that will handle itself by calling self.create_new_custom_state
            self._new_node(pos=pos)
        if action is self._new_state_action and self._last_added_node:
            pos = self.view.mapToScene(pos)
            self._last_added_node.setPos(pos.x(), pos.y())

    def create_new_custom_state(self):
        state_intent = get_new_custom_state(self)
        if state_intent is None:
            logger.info("new state creation aborted")
            return

        logger.info(f"created new state! {state_intent}")
        node = self._new_node()
        # TODO should we allow overriding virtual fs?

        raw_state = state_intent.output
        self._set_state_on_node(node, raw_state)
        self.state_node_created.emit(state_intent)

    def _on_branch_action(
        self, start: StateNode, data: DynamicSubtreeSpec | SubtreeSpec
    ):
        if isinstance(data, SubtreeSpec):
            return self._paste_subtree(start, data.graph)
        return self._paste_dynamic_subtree(start, data)

    def _paste_dynamic_subtree(self, start: StateNode, subtree: DynamicSubtreeSpec):
        if subtree.name == DynamicSubtreeName.FAN_OUT:
            return self._fan_out(start)
        elif subtree.name == DynamicSubtreeName.RELATION_LIFECYCLE:
            return self._extend_with_relation_lifecycle(start)
        else:
            logger.error(f"unknown subtree: {subtree.name}")

    def _fan_out(self, start: StateNode):
        """Experimental action to branch out in all possible directions from a start."""

        for event in LIFECYCLE_EVENTS:
            # todo avoid generating inconsistent paths.
            new_node = self._new_node()

            EventEdge(
                self.scene,
                start.output_socket,
                new_node.input_socket,
                event_spec=EventSpec(Event(event), {}),
            )

        autolayout(start, align="center")

    def _choose_relation(self, node: StateNode) -> typing.Optional[Relation]:
        relations = {
            f"{r.endpoint}:{r.relation_id}": r for r in node.value.state.relations
        }
        logger.info(f"opening relation picker; choices: {relations.keys()}")
        picker = RelationPickerDialog(self, options=relations)
        picker.exec()
        out = picker.finalize()
        if not out:
            logger.info("relation picker not confirmed or aborted")
            return None
        return relations[out]

    def _extend_with_relation_lifecycle(self, start: StateNode):
        """Generate a subtree for a standard relation lifecycle."""
        if not start.value:
            logger.info(
                "selected start node not evaluated yet; force-evaluating it now..."
            )
            try:
                start.eval()
            except Exception:
                logger.error(
                    f"failed to evaluate start node {start}: "
                    f"aborting relation lifecycle subtree creation.",
                    exc_info=True,
                )
                return

        if not start.value.state:
            logger.error(
                "start node has no state even after evaluating it. "
                "Something went wrong, but either way we can't proceed."
            )
            show_error_dialog(
                self, "Parent node evaluation failed. Fix it before proceeding."
            )
            return

        if not start.value.state.relations:
            msg = "start node has no relations. Relation lifecycle macro requires some relation to be present."
            logger.error(msg)
            show_error_dialog(self, msg)
            return

        if len(start.value.state.relations) == 1:
            logger.info(
                "start node has exactly one relation: expanding lifecycle on that one."
            )
            relation = start.value.state.relations[0]
        else:
            relation = self._choose_relation(start)

        if not relation:
            logger.error("no relation name chosen; aborting")
            return

        filename = DYNAMIC_SUBTREES_TEMPLATES_DIR / "relation_lifecycle.theatre"
        text = filename.read_text().replace("{relation_name}", relation.endpoint)
        obj = json.loads(text)
        self._paste_subtree(start, obj)

    def _paste_subtree(
        self, start: StateNode, data: SerializedScene
    ) -> typing.List[StateNode]:
        created_nodes = self.scene.clipboard.deserializeFromClipboard(data)
        roots: typing.List[StateNode] = list(
            filter(lambda node: node.is_root, created_nodes)
        )

        if len(roots) == 1:
            root = roots[0]
        else:
            raise RuntimeError(f"expected a single root: got {len(roots)}")

        # swap out loaded root for selected node
        edge = root.edge_out
        next_node = edge.end_node

        root.remove()
        created_nodes.remove(root)

        EventEdge(
            edge.scene,
            start.output_socket,
            next_node.input_socket,
            edge.edge_type,
            event_spec=edge.event_spec,
        )

        autolayout(start)
        return created_nodes
