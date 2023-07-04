# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import typing
from dataclasses import asdict
from itertools import count
from pathlib import Path

import scenario
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_node import Node
from nodeeditor.node_socket import (
    LEFT_CENTER,
    RIGHT_CENTER,
)
from nodeeditor.utils import dumpException
from qtpy.QtCore import QEvent
from qtpy.QtCore import QPoint
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QLineEdit
from qtpy.QtWidgets import QVBoxLayout, QWidget
from scenario.state import State

from theatre.helpers import get_icon
from theatre.logger import logger
from theatre.scenario_json import parse_state
from theatre.dialogs import new_state, edit_delta
from theatre.trace_tree_widget.delta import DeltaSocket, Delta, DeltaNode
from theatre.trace_tree_widget.event_edge import EventEdge
from theatre.trace_tree_widget.scenario_interface import run_scenario
from theatre.trace_tree_widget.state_bases import StateGraphicsNode, Socket
from theatre.trace_tree_widget.structs import StateNodeOutput

if typing.TYPE_CHECKING:
    from theatre.theatre_scene import TheatreScene
    from theatre.trace_tree_widget.node_editor_widget import GraphicsView

ALLOW_INPUTS_ON_CUSTOM_NODES = False
"""Allow custom nodes to have inputs; i.e. if you add an incoming edge, the custom node 
will be reset and lost."""

GREEDY_NODE_EVALUATION = True
"""Greedily, automatically evaluate newly created or newly connected nodes."""

NEWSTATECTR = count()


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


class ParentEvaluationFailed(RuntimeError):
    """Raised by StateNode._evaluate if the parent node's evaluation fails."""


class SocketType:
    INPUT = 1
    OUTPUT = 2
    DELTA_OUTPUT = 3


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
            icon: QIcon = None,
    ):
        self._is_null = False

        # python file where the deltas are defined
        self._deltas_source: Path | None = None

        # deltas parsed from the source.
        self.deltas: typing.List[Delta] = [
            # Delta(lambda x: x, f"identity {next(NEWDELTACTR)}"),
            # Delta(lambda x: x.replace(leader=True), f"leadermaker {next(NEWDELTACTR)}"),
            # Delta(lambda x: x.replace(leader=False), f"leaderunmaker {next(NEWDELTACTR)}")
        ]

        self._is_custom = False
        super().__init__(scene, name, [SocketType.INPUT], [SocketType.OUTPUT])
        self.icon: QIcon = icon or self._get_icon()
        self.value: typing.Optional[StateNodeOutput] = None
        self.scene = typing.cast("TheatreScene", self.scene)
        self.markDirty()
        self.grNode.title_item.setParent(self.content)
        self._update_title()

    @property
    def input_socket(self) -> Socket:
        return self.inputs[0]

    @property
    def output_socket(self) -> Socket:
        return self.outputs[0]

    def initSockets(self, inputs: list, outputs: list, reset: bool = True):
        super().initSockets(inputs, outputs, reset)
        self._init_delta_sockets()

    def getSocketPosition(self, index: int, position: int, num_out_of: int = 1) -> '(x, y)':
        if index == 0:
            return super().getSocketPosition(index, position, num_out_of)
        return self._get_delta_socket_position(index)

    def _get_delta_socket_position(self, idx: int):
        x = self.grNode.width
        dbox_h = self.grNode.deltabox_height
        node_height = self.grNode.height
        dbox_padding = self.grNode.deltabox_vertical_padding
        y = node_height + dbox_padding + dbox_h / 2 + (dbox_h + dbox_padding) * (idx-1)
        return [x, y]

    def _init_delta_sockets(self):
        # clear existing
        new_outputs = []
        for socket in self.outputs:
            if isinstance(socket, DeltaSocket):
                socket.delete()
            else:
                new_outputs.append(socket)

        for i, delta in enumerate(self.deltas):
            socket = DeltaSocket(
                node=DeltaNode(self, delta), index=i + 1, position=self.output_socket_position,
                socket_type=SocketType.DELTA_OUTPUT, multi_edges=self.output_multi_edged,
                count_on_this_node_side=i + 1, is_input=False
            )
            new_outputs.append(socket)

        self.outputs.clear()
        self.outputs.extend(new_outputs)

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
        self.content = StateContent(self, title=self.title)
        self.content.clicked.connect(self._on_content_clicked)
        self.grNode = StateGraphicsNode(self)
        self.grNode.setToolTip("Click to evaluate.")
        self.content.edit.textChanged.connect(self.on_description_changed)

    def _on_content_clicked(self):
        self.scene.state_node_clicked.emit(self)

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
        except IndexError:
            return None

    @property
    def edge_out(self) -> typing.Optional[EventEdge]:
        """The EventEdge that, combined with the parent state, gave this state."""
        try:
            return self.outputs[0].edges[0]
        except IndexError:
            return None

    def get_title(self):
        title = []
        if self._is_custom:
            title.append("Custom")
        if self._is_null:
            title.append("Null")
        title.append("State")
        if self.is_root:
            title.append("(root)")
        return " ".join(title)

    def _update_title(self):
        self.grNode.title = self.get_title()

    def _get_input_state(self) -> StateNodeOutput:
        """Get the output of the previous node."""
        edge_in = self.edge_in
        parent = edge_in.start_node

        state_in = parent.eval()

        if not isinstance(state_in, StateNodeOutput):
            raise RuntimeError(
                f"parent {parent} evaluation yielded something bad: {state_in}"
            )
        if not state_in.state:
            raise ParentEvaluationFailed(
                "Cannot evaluate this node. Fix the parents first."
            )
        return state_in

    def _evaluate(self) -> StateNodeOutput:
        """Compute the state in this node, based on previous node=state and edge=event"""
        logger.info(f'{"re" if self.value else ""}evaluating {self}')
        self._is_null = False

        if self.is_root:
            logger.info(f"no edge in: {self} inited as null state (root)")
            self._is_null = True
            return StateNodeOutput(scenario.State(), [], "")

        state_in = self._get_input_state()
        event_spec = self.edge_in.event_spec

        logger.info(f"{'re' if self.value else ''}computing state on {self}")
        return run_scenario(self.scene.context, state_in.state, event_spec.event)

    def onInputChanged(self, socket: "Socket"):
        super().onInputChanged(socket)
        if GREEDY_NODE_EVALUATION:
            self.eval()

    def open_edit_dialog(self, parent: QWidget = None):
        dialog = new_state.NewStateDialog(parent, mode=new_state.Mode.edit, base=self)
        dialog.exec()

        if not dialog.confirmed:
            logger.info("new state dialog aborted")
            return

        intent = dialog.finalize()
        self.set_custom_value(intent.output)

    def open_edit_deltas_dialog(self, parent: QWidget = None):
        dialog = edit_delta.EditDeltaDialog(parent, self._deltas_source)
        dialog.exec()

        if not dialog.confirmed:
            logger.info("new state dialog aborted")
            return

        intent = dialog.finalize()
        output = intent.output

        self.deltas = output.deltas
        self._deltas_source = output.source
        self._init_delta_sockets()
        self.grNode.init_delta_labels()

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
        self._update_title()
        self.grNode.update()
        if self.input_socket and self.input_socket.edges:
            self.input_socket.edges[0]._update_icon()

    def eval(self) -> StateNodeOutput:
        if self._is_custom:
            logger.info("Skipping eval of custom node.")
            self.markInvalid(False)
            self.markDirty(False)
            return self.value

        if not self.isDirty() and not self.isInvalid():
            logger.info("Returning cached value.")
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


