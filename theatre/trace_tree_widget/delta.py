# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import typing
from dataclasses import dataclass
from itertools import count

from scenario import State

from theatre.logger import logger
from theatre.trace_tree_widget.scenario_interface import run_scenario
from theatre.trace_tree_widget.state_bases import Socket
from theatre.trace_tree_widget.structs import StateNodeOutput

if typing.TYPE_CHECKING:
    from theatre.trace_tree_widget.state_node import StateNode

NEWDELTACTR = count()


class DeltaSocket(Socket):
    def __repr__(self):
        return "<DeltaSocket>"


@dataclass
class Delta:
    get: typing.Callable[[State], State]
    name: str


class DeltaNode:
    def __init__(self, node: "StateNode", delta: Delta):
        self._base_node = node
        self._delta = delta
        self.inputs = []  # needed for compatibility with the Node interface
        self.outputs = []  # needed for compatibility with the Node interface
        self._value_cache: typing.Optional[StateNodeOutput] = None

    def get_socket(
        self,
        index,
        position,
        socket_type,
        multi_edges,
        count_on_this_node_side,
        is_input,
    ) -> DeltaSocket:
        ds = DeltaSocket(
            node=self,
            index=index,
            position=position,
            socket_type=socket_type,
            multi_edges=multi_edges,
            count_on_this_node_side=count_on_this_node_side,
            is_input=is_input,
        )
        if is_input:
            self.inputs.append(ds)
        else:
            self.outputs.append(ds)

        return ds

    @property
    def value(self):
        cache = self._value_cache
        if not cache:
            raise ValueError("not evaluated yet")
        return cache

    @property
    def name(self):
        return self._delta.name

    def __repr__(self):
        return f"<DeltaNode {self._delta.name}>"

    # override this StateNode call since this delta's previous is this delta's base node,
    # not this base node's
    def get_previous(self) -> "StateNode":
        return self._base_node

    def _get_parent_output(self) -> StateNodeOutput:
        """Get the output of the previous node."""
        # todo: cache input
        base_node_output = self._base_node.eval()
        deltaed_state = self._delta.get(base_node_output.state)

        if not isinstance(deltaed_state, State):
            raise RuntimeError(
                f"Applying {self._delta} to {base_node_output.state} "
                f"yielded {type(deltaed_state)} "
                f"instead of scenario.State."
            )

        return StateNodeOutput(state=deltaed_state)

    def eval(self) -> StateNodeOutput:
        if self.isDirty():
            # invalidate our cache too
            self._value_cache = None

        if not self._value_cache:
            value = self._evaluate()
            self._value_cache = value

        return self._value_cache

    def _evaluate(self):
        parent_output = self._get_parent_output()
        edge_in = self.edge_in
        if not edge_in:
            # root node! return unmodified state
            return parent_output

        logger.info(f"{'re' if self._value_cache else ''}computing state on {self}")
        # the parent node is deltae'd
        return run_scenario(
            self.scene.context, parent_output.state, self.edge_in.event_spec.event
        )

    # properties we pass through to parent node
    @property
    def grNode(self):
        return self._base_node.grNode

    def isDirty(self):
        return self._base_node.isDirty()

    @property
    def edge_in(self):
        return self._base_node.edge_in

    @property
    def scene(self):
        return self._base_node.scene

    def getSocketPosition(self, *args, **kwargs):
        return self._base_node.getSocketPosition(*args, **kwargs)
