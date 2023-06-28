# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import contextlib
import inspect
import typing
from dataclasses import dataclass, asdict
from itertools import count

import scenario
from PyQt5 import QtCore
from PyQt5.QtCore import QSize
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QPushButton, QListView, QListWidgetItem, QListWidget
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
from scenario.state import JujuLogLine, State

from theatre.helpers import get_icon, get_color
from theatre.logger import logger
from theatre.scenario_json import parse_state
from theatre.trace_tree_widget import new_state_dialog
from theatre.trace_tree_widget.event_edge import EventEdge

if typing.TYPE_CHECKING:
    from theatre.theatre_scene import TheatreScene
    from theatre.trace_tree_widget.node_editor_widget import GraphicsView

ALLOW_INPUTS_ON_CUSTOM_NODES = False
"""Allow custom nodes to have inputs; i.e. if you add an incoming edge, the custom node 
will be reset and lost."""

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
        # FIXME: colors don't quite work as intended here, somehow...?
        self._icon_ok = get_icon("stars")
        self._icon_dirty = get_icon("flaky")
        self._icon_invalid = get_icon("error")
        self._color_ok = get_color("pastel green")
        self._color_dirty = get_color("pastel orange")
        self._color_invalid = get_color("pastel red")

    def paint(self, painter: QPainter, QStyleOptionGraphicsItem, widget=None):
        super().paint(painter, QStyleOptionGraphicsItem, widget)

        if self.node.isInvalid():
            icon = self._icon_invalid
            color = self._color_invalid
        elif self.node.isDirty():
            icon = self._icon_dirty
            color = self._color_dirty
        else:
            icon = self._icon_ok
            color = self._color_ok

        rect = QRectF(160 - 24, 0, 24.0, 24.0)
        painter.setPen(color)
        painter.drawEllipse(rect)
        pxmp = icon.pixmap(34, 34)
        painter.drawImage(rect, pxmp.toImage())


NEWSTATECTR = count()


class DeltaList(QWidget):
    delta_added = Signal()
    delta_removed = Signal()

    def __init__(self, node: "StateNode", parent=None) -> None:
        super().__init__(parent)
        self._node = node
        self._delta_list = delta_list = QListWidget(self)
        self._add_delta_button = delta_butt = QPushButton(get_icon("difference"), "add delta", self)

        delta_butt.clicked.connect(self._add_delta)

        self._layout = layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(delta_list)
        layout.addWidget(delta_butt)

    def _add_delta(self):
        # todo: add row including 'remove' and 'edit' buttons
        name = "modified"
        item = QListWidgetItem(name, self._delta_list)  # can be (icon, text, parent, <int>type)
        item.setIcon(get_icon("difference"))
        item.setSizeHint(QSize(32, 32))

        item.setFlags(Qt.ItemIsEnabled)
        item.setData(Qt.UserRole, Delta(lambda x: x, "identity"))


class StateContent(QDMNodeContentWidget):
    clicked = Signal()

    def __init__(self, node: "StateNode", parent: QWidget = None, title: str = ""):
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
    state: typing.Optional[scenario.State] = None
    charm_logs: typing.Optional[typing.List[JujuLogLine]] = None
    scenario_logs: typing.Optional[str] = None
    traceback: typing.Optional[inspect.Traceback] = None


class ParentEvaluationFailed(RuntimeError):
    """Raised by StateNode._evaluate if the parent node's evaluation fails."""


@dataclass
class Delta:
    get: typing.Callable[[State], State]
    name: str


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
            icon: QIcon = None,
    ):
        super().__init__(scene, name, inputs, outputs)

        self.icon: QIcon = icon or self._get_icon()
        self.value: typing.Optional[StateNodeOutput] = None
        self._deltas = []
        self.scene = typing.cast("TheatreScene", self.scene)
        self._is_dirty = True
        self._is_custom = False
        self.grNode.title_item.setParent(self.content)
        self._update_title()

    @property
    def input_socket(self) -> Socket:
        return self.inputs[0]

    @property
    def output_socket(self) -> Socket:
        return self.outputs[0]

    def set_custom_value(self, state: State):
        """Overrides any value with this state and configures this as a custom node."""
        self._is_custom = True
        self.value = StateNodeOutput(state=state)

        if not ALLOW_INPUTS_ON_CUSTOM_NODES:
            old_socket = self.inputs.pop()
            self.scene.grScene.removeItem(old_socket.grSocket)

        self.eval()

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
        # todo: render delta list as tail of nodes beneath this one.
        self.delta_list = DeltaList(self)
        self.content = StateContent(self, title=self.title)
        self.content.clicked.connect(self._on_content_clicked)
        self.delta_list.delta_added.connect(self._on_add_delta)
        self.delta_list.delta_removed.connect(self._on_remove_delta)
        self.grNode = StateGraphicsNode(self)
        self.grNode.setToolTip("Click to evaluate.")
        self.content.edit.textChanged.connect(self.on_description_changed)

    def _on_content_clicked(self):
        self.scene.state_node_clicked.emit(self)

    def _on_add_delta(self, delta: Delta):
        self._deltas.append(delta)
        # todo add socket

    def _on_remove_delta(self, index: int = 0):
        self._deltas.pop(index)
        # todo remove socket

    def initSettings(self):
        super().initSettings()
        self.input_socket_position = LEFT_CENTER
        self.output_socket_position = RIGHT_CENTER

    @property
    def is_root(self) -> bool:
        """Is this a root node?"""
        return not self.inputs or not self.inputs[0].edges

    @property
    def edge_in(self) -> typing.Optional[EventEdge]:
        """The EventEdge that, combined with the parent state, gave this state."""
        try:
            return self.inputs[0].edges[0]
        except IndexError as e:
            return None

    @property
    def edge_out(self) -> typing.Optional[EventEdge]:
        """The EventEdge that, combined with the parent state, gave this state."""
        try:
            return self.outputs[0].edges[0]
        except IndexError as e:
            return None

    def get_title(self):
        title = []
        if self._is_custom:
            title.append("Custom")
        title.append("State")
        if self.is_root:
            title.append("(root)")
        return " ".join(title)

    def _update_title(self):
        self.grNode.title = self.get_title()

    def _evaluate(self) -> StateNodeOutput:
        """Compute the state in this node, based on previous node=state and edge=event"""
        logger.info(f'{"re" if self.value else ""}evaluating {self}')

        if self.is_root:
            logger.info(f"no edge in: {self} inited as null state (root)")
            return StateNodeOutput(scenario.State(), [], "")

        edge_in = self.edge_in
        parent = edge_in.start_node

        event_spec = edge_in.event_spec
        state_in = parent.eval()

        if not isinstance(state_in, StateNodeOutput):
            raise RuntimeError(
                f"parent {parent} evaluation yielded something bad: {state_in}"
            )
        if not state_in.state:
            raise ParentEvaluationFailed(
                "Cannot evaluate this node. Fix the parents first."
            )

        scenario_stdout_buffer = ""

        class StreamWrapper:
            def write(self, msg):
                if msg and not msg.isspace():
                    nonlocal scenario_stdout_buffer
                    scenario_stdout_buffer += msg

            def flush(self):
                pass

        with contextlib.redirect_stdout(StreamWrapper()):
            ctx = scenario.Context(
                charm_type=self.scene.charm_spec.charm_type, meta={"name": "dummy"}
            )
            state_out = ctx.run(state=state_in.state, event=event_spec.event)

        # whatever Scenario outputted is in 'scenario_stdout_buffer' now.
        logger.info(f"{'re' if self.value else ''}computed state on {self}")

        return StateNodeOutput(state_out, ctx.juju_log, scenario_stdout_buffer)

    def onInputChanged(self, socket: "Socket"):
        super().onInputChanged(socket)
        if GREEDY_NODE_EVALUATION:
            self.eval()

    def open_edit_dialog(self, parent: QWidget = None):
        dialog = new_state_dialog.NewStateDialog(parent, mode=new_state_dialog.Mode.edit, base=self)
        dialog.exec()

        if not dialog.confirmed:
            logger.info("new state dialog aborted")
            return

        intent = dialog.finalize()
        self.set_custom_value(intent.state)

    def update_value(self, new_value: StateNodeOutput) -> StateNodeOutput:
        # todo: also update library, name and icon
        self.markInvalid(False)
        self.markDirty(False)

        self.value = new_value

        # todo find better tooltip
        self.grNode.setToolTip(str(new_value.state))

        # notify listeners of potential value change
        self.scene.state_node_changed.emit(self)

        self.markDescendantsDirty()
        self._update_graphics()
        return new_value

    def _set_error_value(self, e: Exception):
        self.grNode.setToolTip(str(e))
        tb = e.__traceback__
        logger.error(e)
        value = StateNodeOutput(traceback=tb)

        self.value = value
        # first set our own value, otherwise evalchildren will try to fetch our eval()
        # and cause recursive nightmares
        # self.evalChildren()
        self.markInvalid(True)
        self.markDirty(True)
        self.markDescendantsDirty(True)
        self._update_graphics()
        return value

    def _update_graphics(self):
        self.grNode.update()
        if self.input_socket and self.input_socket.edges:
            self.input_socket.edges[0]._update_icon()

    def eval(self) -> StateNodeOutput:
        if self._is_custom:
            logger.info(f"Skipping eval of custom node.")
            self.markInvalid(False)
            self.markDirty(False)
            return self.value

        if not self.isDirty() and not self.isInvalid():
            logger.info(f"Returning cached value.")
            return self.value

        try:
            return self.update_value(self._evaluate())
        except Exception as e:
            return self._set_error_value(e)

    def getChildrenNodes(self) -> typing.List["StateNode"]:
        """
        Retrieve all first-level children connected to this `Node` `Outputs`

        :return: list of `Nodes` connected to this `Node` from all `Outputs`
        :rtype: List[:class:`~nodeeditor.node_node.Node`]
        """

        if not self.outputs:
            return []

        children = []
        for socket in self.outputs:
            edge: EventEdge
            for edge in socket.edges:
                # if the edge is the one generated by Dragging, there might be no end node (yet).
                if edge.end_socket:
                    children.append(edge.end_socket.node)
        return children

    def on_description_changed(self, socket=None):
        logger.info(f"description changed: {self}")

    def serialize(self):
        res = super().serialize()
        res["name"] = self.title
        res["value"] = self.content.edit.text()
        if self._is_custom:
            res["custom-state"] = asdict(self.value.state)
        return res

    def deserialize(self, data, hashmap={}, restore_id=True):
        res = super().deserialize(data, hashmap, restore_id)
        self.title = data["name"]
        try:
            value = data["value"]
            self.content.edit.setText(value)
            if custom_state := data.get('custom-state'):
                self.set_custom_value(parse_state(custom_state))
            return True & res
        except Exception as e:
            dumpException(e)
        return res

    def get_previous(self) -> typing.Optional["StateNode"]:
        """The previous state, if any."""
        return self.getInput() if self.inputs else None  # skip traceback

    def get_next(self) -> typing.Optional["StateNode"]:
        """The next state, if any."""
        outs = self.getOutputs()
        return outs[0] if outs else None


def create_new_node(
        scene: "TheatreScene", view: "GraphicsView", pos: QPoint, name: str = "State",
        icon: QIcon = None
):
    new_state_node = StateNode(
        scene,
        name=name,
        icon=icon
    )
    pos = QPoint(pos)
    # translate up by half the node height so the node appears vertically centered
    #  relative to the mouse click
    pos.setY(pos.y() - new_state_node.grNode.height // 2)
    scene_pos = view.mapToScene(pos)
    new_state_node.setPos(scene_pos.x(), scene_pos.y())
    return new_state_node


def autolayout(node: StateNode,
               align: typing.Literal['top', 'bottom', 'center'] = 'top'):
    pos = node.pos
    children: typing.Iterable[StateNode] = node.getOutputs()
    xpos = pos.x() + node.grNode.width * 1.5
    ypos = pos.y()
    vspacing = node.grNode.height * 1.5

    if align == 'top':
        baseline = ypos
    elif align == "center":
        baseline = ypos - vspacing * len(children) / 2
    else:
        baseline = ypos - vspacing * len(children)

    for i, child in enumerate(children):
        child.setPos(xpos, baseline + vspacing * i)
        child.updateConnectedEdges()
        autolayout(child)
