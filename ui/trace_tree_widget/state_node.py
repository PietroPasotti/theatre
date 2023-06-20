import typing
from itertools import count

import scenario
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_graphics_node import QDMGraphicsNode
from nodeeditor.node_node import Node
from nodeeditor.node_socket import LEFT_CENTER, RIGHT_CENTER, Socket as _Socket, QDMGraphicsSocket
from nodeeditor.utils import dumpException
from qtpy.QtCore import QRectF
from qtpy.QtCore import Qt
from qtpy.QtGui import QImage
from qtpy.QtWidgets import QLineEdit

from ui.trace_tree_widget.event_dialog import EventPicker
from ui.trace_tree_widget.event_edge import EventEdge

if typing.TYPE_CHECKING:
    from ui.main_window import Scene


class StateGraphicsNode(QDMGraphicsNode):
    def initSizes(self):
        super().initSizes()
        self.width = 160
        self.height = 74
        self.edge_roundness = 6
        self.edge_padding = 0
        self.title_horizontal_padding = 8
        self.title_vertical_padding = 10
        self.title_height = 24

    def initAssets(self):
        super().initAssets()
        self.icons = QImage("icons/status_icons.png")

    def paint(self, painter, QStyleOptionGraphicsItem, widget=None):
        super().paint(painter, QStyleOptionGraphicsItem, widget)

        offset = 24.0
        if self.node.isDirty():
            offset = 0.0
        if self.node.isInvalid():
            offset = 48.0

        painter.drawImage(
            QRectF(-10, -10, 24.0, 24.0), self.icons, QRectF(offset, 0, 24.0, 24.0)
        )


NEWSTATECTR = count()


class StateContent(QDMNodeContentWidget):
    def initUI(self):
        self.edit = QLineEdit(f"new state {next(NEWSTATECTR)}", self)
        self.edit.setAlignment(Qt.AlignLeft)
        self.edit.setObjectName(self.node.content_label_objname)

    def serialize(self):
        res = super().serialize()
        res['value'] = self.edit.text()
        return res

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)
        try:
            value = data['value']
            self.edit.setText(value)
            return True & res
        except Exception as e:
            dumpException(e)
        return res


class GraphicsSocket(QDMGraphicsSocket):

    def __init__(self, socket: 'Socket'):
        super().__init__(socket)
        self.radius = 6
        self.outline_width = 1


class Socket(_Socket):
    Socket_GR_Class = GraphicsSocket


class StateNode(Node):
    icon = ""
    content_label = ""
    content_label_objname = "state_node_bg"

    GraphicsNode_class = StateGraphicsNode
    NodeContent_class = StateContent
    Socket_class = Socket

    def __init__(self, scene: "Scene", name="State", inputs=[2], outputs=[1]):
        super().__init__(scene, name, inputs, outputs)
        self.name = name
        self.value = None
        self.scene = typing.cast("Scene", self.scene)
        self._is_dirty = True

        self.grNode.title_item.setParent(self.content)

    def initInnerClasses(self):
        self.content = StateContent(self)
        self.grNode = StateGraphicsNode(self)
        self.content.edit.textChanged.connect(self.on_description_changed)

    def initSettings(self):
        super().initSettings()
        self.input_socket_position = LEFT_CENTER
        self.output_socket_position = RIGHT_CENTER

    def recompute_state(self) -> scenario.State:
        """Compute the state in this node, based on previous node=state and edge=event"""
        try:
            edge_in: EventEdge = self.inputs[0].edges[0]
            parent: StateNode = edge_in.start_socket.node
        except IndexError:
            edge_in = None
            parent = None

        if not edge_in:
            title = 'Null State'
            state = scenario.State()
            print(f"no edge in: {self} inited as null state (root)")

        else:  # parent and edge in
            event_spec = edge_in.event_spec
            title = 'State'
            state = scenario.trigger(
                state=parent.eval(),
                event=event_spec.event,
                charm_type=self.scene.charm_type,
            )
            print(f"{self} recomputed state to {state}")

        self.content.wdg_label.setText(title)
        self.markDescendantsDirty()
        self.evalChildren()
        self.markInvalid(False)
        self.value = state

        # self.grNode.setToolTip("Connect all inputs")
        return state

    def eval(self):
        if not self.isDirty() and not self.isInvalid():
            print(
                " _> returning cached %s value:" % self.__class__.__name__, self.value
            )
            return self.value

        try:

            val = self.recompute_state()
            return val
        except ValueError as e:
            self.markInvalid()
            self.grNode.setToolTip(str(e))
            self.markDescendantsDirty()
        except Exception as e:
            self.markInvalid()
            self.grNode.setToolTip(str(e))
            dumpException(e)

    def on_description_changed(self, socket=None):
        print("%s::on_description_changed" % self.__class__.__name__)

    def serialize(self):
        res = super().serialize()
        res["name"] = self.name
        res['value'] = self.content.edit.text()
        return res

    def deserialize(self, data, hashmap={}, restore_id=True):
        res = super().deserialize(data, hashmap, restore_id)
        self.name = data['name']
        try:
            value = data['value']
            self.content.edit.setText(value)
            return True & res
        except Exception as e:
            dumpException(e)
        return res

    def fire_event(self):
        event_picker = EventPicker()
        event_picker.exec()

        if event_picker.confirmed:
            event = event_picker.get_event()
