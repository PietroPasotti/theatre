# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import contextlib

import scenario
from scenario import State, Event

from theatre.trace_tree_widget.structs import StateNodeOutput


def run_scenario(context: scenario.Context, state: State, event: Event):
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
        state_out = context.run(state=state, event=event)

    # whatever Scenario outputted is in 'scenario_stdout_buffer' now.

    return StateNodeOutput(state_out, context.juju_log, scenario_stdout_buffer)
