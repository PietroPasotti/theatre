# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import typing
from dataclasses import dataclass
from itertools import count

from scenario import State

from theatre.logger import logger
from theatre.trace_tree_widget.scenario_interface import run_scenario
from theatre.trace_tree_widget.structs import StateNodeOutput
from theatre.trace_tree_widget.state_bases import Socket

if typing.TYPE_CHECKING:
    from theatre.trace_tree_widget.state_node import (
        StateNode,
        add_simulated_fs_from_repo,
    )

NEWDELTACTR = count()


class DeltaSocket(Socket):
    pass


@dataclass
class Delta:
    get: typing.Callable[[State], State]
    name: str


class DeltaNode:
    def __init__(self, node: "StateNode", delta: Delta):
        self._base_node = node
        self._delta = delta
        self._cached_value = None

    def __repr__(self):
        return f"<DeltaNode {self._delta.name}>"

    def __getattr__(self, item):
        # proxy all node calls
        return getattr(self._base_node, item)

    def _get_parent_output(self) -> StateNodeOutput:
        """Get the output of the previous node."""
        # todo: cache input
        base_node_output = self._base_node.eval()
        deltaed_state = self._delta.get(base_node_output.state)

        if not isinstance(deltaed_state, State):
            raise RuntimeError(
                f"Applying {self.delta} to {base_node_output.state} "
                f"yielded {type(deltaed_state)} "
                f"instead of scenario.State."
            )

        return StateNodeOutput(state=deltaed_state)

    def eval(self) -> StateNodeOutput:
        parent_output = self._get_parent_output()
        edge_in = self.edge_in
        if not edge_in:
            # root node! return unmodified state
            return parent_output

        logger.info(f"{'re' if self.value else ''}computing state on {self}")
        # the parent node is deltae'd
        return run_scenario(
            self.scene.context, parent_output.state, self.edge_in.event_spec.event
        )
