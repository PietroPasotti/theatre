# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import contextlib

import scenario
from scenario import State, Event
from scenario.state import _CharmSpec

from theatre.trace_tree_widget.structs import StateNodeOutput


def run_scenario(state: State, charm_spec: "_CharmSpec", event: Event):
    scenario_stdout_buffer = ""
    # fixme: logging redirect not quite working

    class StreamWrapper:
        def write(self, msg):
            if msg and not msg.isspace():
                nonlocal scenario_stdout_buffer
                scenario_stdout_buffer += msg

        def flush(self):
            pass

    with contextlib.redirect_stdout(StreamWrapper()):
        ctx = scenario.Context(
            charm_type=charm_spec.charm_type, meta={"name": "dummy"}
        )
        state_out = ctx.run(state=state, event=event)

    # whatever Scenario outputted is in 'scenario_stdout_buffer' now.

    return StateNodeOutput(state_out, ctx.juju_log, scenario_stdout_buffer)
