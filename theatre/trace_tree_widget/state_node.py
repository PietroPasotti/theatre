import contextlib
import inspect
import typing
from dataclasses import dataclass
from itertools import count

import scenario
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_graphics_node import QDMGraphicsNode
from nodeeditor.node_node import Node
from nodeeditor.node_socket import (
    LEFT_CENTER,
    RIGHT_CENTER,
    Socket as _Socket,
    QDMGraphicsSocket,
)
from nodeeditor.utils import dumpException
from qtpy.QtCore import QEvent
from qtpy.QtCore import QPoint
from qtpy.QtCore import QRectF
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QLineEdit
from qtpy.QtWidgets import QVBoxLayout, QWidget

from logger import logger
from theatre.helpers import get_icon
from theatre.trace_tree_widget.event_edge import EventEdge

if typing.TYPE_CHECKING:
    from theatre.theatre_scene import TheatreScene
    from theatre.trace_tree_widget.trace_tree_editor_widget import GraphicsView

GREEDY_NODE_EVALUATION = True
"""Greedily, automatically evaluate newly created or newly connected nodes."""


class StateGraphicsNode(QDMGraphicsNode):
    def initSizes(self):
        super().initSizes()
        self.width = 160
        self.height = 84
        self.edge_roundness = 6
        self.edge_padding = 0
        self.title_horizontal_padding = 8
        self.title_vertical_padding = 10
        self.title_height = 24

    def initAssets(self):
        super().initAssets()
        self.icon_ok = get_icon('stars')
        self.icon_dirty = get_icon('flaky')
        self.icon_invalid = get_icon('error')

    def paint(self, painter, QStyleOptionGraphicsItem, widget=None):
        super().paint(painter, QStyleOptionGraphicsItem, widget)

        if self.node.isDirty():
            icon = self.icon_dirty
        elif self.node.isInvalid():
            icon = self.icon_invalid
        else:
            icon = self.icon_ok

        rect = QRectF(-10, -10, 24.0, 24.0)
        pxmp = icon.pixmap(34, 34)
        painter.drawImage(
            rect, pxmp.toImage()
        )


NEWSTATECTR = count()


class StateContent(QDMNodeContentWidget):
    clicked = Signal()

    def __init__(self, node: "Node", parent: QWidget = None, title: str = ""):
        self._title = title
        super().__init__(node, parent)

    def initUI(self):
        """Sets up layouts and widgets to be rendered in :py:class:`~nodeeditor.node_graphics_node.QDMGraphicsNode` class."""
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(self.layout)

        self.edit = edit = QLineEdit(f"new state {next(NEWSTATECTR)}", self)
        self.edit.setAlignment(Qt.AlignLeft)
        self.layout.addWidget(edit)
        self.edit.setObjectName(self.node.content_label_objname)

    def serialize(self):
        res = super().serialize()
        res["value"] = self.edit.text()
        return res

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)
        try:
            value = data["value"]
            self.edit.setText(value)
            return True & res
        except Exception as e:
            dumpException(e)
        return res

    def mousePressEvent(self, e: QEvent):
        self.clicked.emit()
        e.accept()


class GraphicsSocket(QDMGraphicsSocket):
    def __init__(self, socket: "Socket"):
        super().__init__(socket)
        self.radius = 6
        self.outline_width = 1


class Socket(_Socket):
    Socket_GR_Class = GraphicsSocket


@dataclass
class StateNodeOutput:
    state: scenario.State = None
    logs: str = None
    traceback: inspect.Traceback = None


class StateNode(Node):
    content_label = ""
    content_label_objname = "state_node_bg"

    GraphicsNode_class = StateGraphicsNode
    NodeContent_class = StateContent
    Socket_class = Socket

    def __repr__(self):
        return f"<StateNode {self.title, self.content.edit.text()}>"

    __str__ = __repr__

    def __init__(
            self,
            scene: "TheatreScene",
            name="State",
            inputs=[2],
            outputs=[1],
            on_value_changed: typing.Callable[["StateNode"], None] = None,
            on_clicked: typing.Callable[["StateNode"], None] = None,
            icon: QIcon = None,
    ):
        self._on_value_changed = on_value_changed  # signals!
        self._on_clicked = on_clicked  # signals!

        super().__init__(scene, name, inputs, outputs)

        self.icon: QIcon = icon or self._get_icon()
        self.value: typing.Optional[StateNodeOutput] = None
        self.scene = typing.cast("TheatreScene", self.scene)
        self._is_dirty = True

        self.grNode.title_item.setParent(self.content)
        self._update_title()

        self.input_socket: Socket = self.inputs[0]
        self.output_socket: Socket = self.outputs[0]

    @property
    def description(self) -> str:
        """User-editable description for this state."""
        return self.content.edit.text()

    def _get_icon(self) -> QIcon:
        name = self.title
        # todo icons per different types
        if name == "start":
            return get_icon("stars")
        return get_icon("data_object")

    def initInnerClasses(self):
        self.content = StateContent(self, title=self.title)
        self.content.clicked.connect(self._on_content_clicked)
        self.grNode = StateGraphicsNode(self)
        self.content.edit.textChanged.connect(self.on_description_changed)

    def _on_content_clicked(self):
        self._on_clicked.emit(self)

    def initSettings(self):
        super().initSettings()
        self.input_socket_position = LEFT_CENTER
        self.output_socket_position = RIGHT_CENTER

    @property
    def is_root(self) -> bool:
        """Is this a root node?"""
        return not self.inputs[0].edges

    @property
    def edge_in(self) -> EventEdge:
        """The EventEdge that, combined with the parent state, gave this state."""
        try:
            return self.inputs[0].edges[0]
        except IndexError as e:
            raise RuntimeError("root node has no edge_in.") from e

    def get_title(self):
        if self.is_root:
            return "Null State (root)"
        else:
            return "State"

    def _update_title(self):
        self.grNode.title = self.get_title()

    def _evaluate(self) -> scenario.State:
        """Compute the state in this node, based on previous node=state and edge=event"""
        logger.info(f'{"re" if self.value else ""}evaluating {self}')

        if self.is_root:
            logger.info(f"no edge in: {self} inited as null state (root)")
            return scenario.State()

        edge_in = self.edge_in
        parent = edge_in.start_node

        event_spec = edge_in.event_spec
        state_in = parent.eval()

        if not isinstance(state_in, StateNodeOutput):
            raise RuntimeError(
                f'parent {parent} evaluation yielded something bad: {state_in}'
            )

        scenario_stdout_buffer = ''
        class StreamWrapper:
            def write(self, msg):
                if msg and not msg.isspace():
                    nonlocal scenario_stdout_buffer
                    scenario_stdout_buffer += msg

            def flush(self): pass

        with contextlib.redirect_stdout(StreamWrapper()):
            # todo switch to Scenario 4.0 when released
            state = scenario.trigger(
                state=state_in.state,
                event=event_spec.event,
                charm_type=self.scene.charm_type,
                meta={'name': 'dummy'}
            )

        # whatever Scenario outputted is in 'scenario_stdout_buffer' now.
        # TODO: show it somewhere.

        logger.info(f"{'re' if self.value else ''}computed state on {self}")

        return state

    def onInputChanged(self, socket: 'Socket'):
        super().onInputChanged(socket)
        if GREEDY_NODE_EVALUATION:
            self.eval()

    def eval(self) -> StateNodeOutput:
        if not self.isDirty() and not self.isInvalid():
            logger.info(f" _> returning cached {self} value")
            return self.value

        self.traceback = None

        try:
            state = self._evaluate()
            # todo attach logs
            value = StateNodeOutput(state=state)
            self.markInvalid(False)
            self.markDirty(False)

            self.grNode.setToolTip(str(state))

            # notify listeners of potential value change
            if self._on_value_changed:
                self._on_value_changed.emit(self)

        except Exception as e:
            self.markInvalid()
            self.markDescendantsDirty()
            self.grNode.setToolTip(str(e))
            self.traceback = tb = e.__traceback__
            logger.error(e)
            value = StateNodeOutput(
                traceback=tb
            )

        self.value = value
        # first set our own value, otherwise evalchildren will try to fetch our eval()
        # and cause recursive nightmares

        # self.evalChildren()
        self.markDescendantsDirty()
        self.grNode.update()

        return self.value

    def on_description_changed(self, socket=None):
        logger.info(f"description changed: {self}")

    def serialize(self):
        res = super().serialize()
        res["name"] = self.title
        res["value"] = self.content.edit.text()
        return res

    def deserialize(self, data, hashmap={}, restore_id=True):
        res = super().deserialize(data, hashmap, restore_id)
        self.title = data["name"]
        try:
            value = data["value"]
            self.content.edit.setText(value)
            return True & res
        except Exception as e:
            dumpException(e)
        return res

    def get_previous(self) -> typing.Optional["StateNode"]:
        """The previous state, if any."""
        return self.getInput()

    def get_next(self) -> typing.Optional["StateNode"]:
        """The next state, if any."""
        outs = self.getOutputs()
        return outs[0] if outs else None


def create_new_state(
        scene: "TheatreScene", view: "GraphicsView", pos: QPoint, name: str = "State"
):
    new_state_node = StateNode(
        scene,
        name=name,
        on_value_changed=scene.state_node_changed,
        on_clicked=scene.state_node_clicked,
    )
    pos = QPoint(pos)
    # translate up by half the node height so the node appears vertically centered
    #  relative to the mouse click
    pos.setY(pos.y() - new_state_node.grNode.height // 2)
    scene_pos = view.mapToScene(pos)
    new_state_node.setPos(scene_pos.x(), scene_pos.y())
    return new_state_node
