# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import typing
from dataclasses import dataclass
from itertools import count

from scenario import State

from theatre.logger import logger
from theatre.trace_tree_widget.structs import StateNodeOutput
from theatre.trace_tree_widget.state_bases import Socket

if typing.TYPE_CHECKING:
    from theatre.trace_tree_widget.state_node import StateNode

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

    def _get_input_state(self) -> StateNodeOutput:
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

        return StateNodeOutput(
            state=deltaed_state,
            charm_logs=None,
            scenario_logs=None,
            traceback=None, # todo?
        )

    def eval(self) -> StateNodeOutput:
        state_in = self._get_input_state()
        edge_in = self.edge_in
        if not edge_in:
            # root node! return unmodified state
            return state_in

        event_spec = edge_in.event_spec
        logger.info(f"{'re' if self.value else ''}computing state on {self}")
        return _evaluate(state_in.state, self.scene.charm_spec, event_spec.event)
