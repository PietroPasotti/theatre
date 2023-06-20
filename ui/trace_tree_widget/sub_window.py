from logger import logger
from nodeeditor.node_node import Node
from qtpy.QtGui import QIcon, QPixmap
from qtpy.QtCore import QDataStream, QIODevice, Qt
from qtpy.QtWidgets import QAction, QGraphicsProxyWidget, QMenu

from ui.trace_tree_widget.conf import STATES, LISTBOX_MIMETYPE, get_state
from nodeeditor.node_editor_widget import NodeEditorWidget
from nodeeditor.node_edge import EDGE_TYPE_DIRECT, EDGE_TYPE_BEZIER, EDGE_TYPE_SQUARE
from nodeeditor.node_graphics_view import MODE_EDGE_DRAG
from nodeeditor.utils import dumpException
from ui.trace_tree_widget.state_node import StateNode

DEBUG = False
DEBUG_CONTEXT = False


class TraceTreeEditor(NodeEditorWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # self.setAttribute(Qt.WA_DeleteOnClose)

        self.setTitle()

        self._create_new_state_actions()

        self.scene.addHasBeenModifiedListener(self.setTitle)
        self.scene.history.addHistoryRestoredListener(self.onHistoryRestored)
        self.scene.addDragEnterListener(self.onDragEnter)
        self.scene.addDropListener(self.onDrop)
        self.scene.setNodeClassSelector(self._get_node_class_from_data)

        self._close_event_listeners = []

    def _get_node_class_from_data(self, data):
        if "name" not in data:
            return Node
        state = get_state(data['name'])
        return StateNode

    def doEvalOutputs(self):
        # eval all output nodes
        for node in self.scene.nodes:
            if node.__class__.__name__ == "CalcNode_Output":
                node.eval()

    def onHistoryRestored(self):
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

    def _init_states_context_menu(self):
        context_menu = QMenu(self)
        keys = list(STATES.keys())
        keys.sort()
        for key in keys:
            context_menu.addAction(self.state_actions[key])
        return context_menu

    def setTitle(self):
        self.setWindowTitle(self.getUserFriendlyFilename())

    def addCloseEventListener(self, callback):
        self._close_event_listeners.append(callback)

    def closeEvent(self, event):
        for callback in self._close_event_listeners:
            callback(self, event)

    def onDragEnter(self, event):
        if event.mimeData().hasFormat(LISTBOX_MIMETYPE):
            event.acceptProposedAction()
        else:
            # print(" ... denied drag enter event")
            event.setAccepted(False)

    def onDrop(self, event):
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

            if hasattr(item, "node") or hasattr(item, "socket"):
                self._on_state_context_menu(event)
            elif hasattr(item, "edge"):
                self._on_edge_context_menu(event)
            else:
                self._on_new_node_context_menu(event)

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

    def _on_new_node_context_menu(self, event):
        context_menu = self._init_states_context_menu()
        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        if action is not None:
            new_state_node = StateNode(self.scene)
            scene_pos = self.scene.getView().mapToScene(event.pos())
            new_state_node.setPos(scene_pos.x(), scene_pos.y())
            if DEBUG_CONTEXT:
                print("Selected node:", new_state_node)

            if self.scene.getView().mode == MODE_EDGE_DRAG:
                # if we were dragging an edge...
                target_socket = self.determine_target_socket_of_node(
                    self.scene.getView().dragging.drag_start_socket.is_output,
                    new_state_node,
                )
                if target_socket is not None:
                    self.scene.getView().dragging.edgeDragEnd(target_socket.grSocket)
                    self._finalize_node(new_state_node)

            else:
                self.scene.history.storeHistory(
                    "Created %s" % new_state_node.__class__.__name__
                )
