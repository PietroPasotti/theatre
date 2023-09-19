# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import contextlib

import scenario
from scenario import State, Event, Action

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

    # todo: if the event is a relation event, patch in
    #  the relation object from state that we're referring to.

    with contextlib.redirect_stdout(StreamWrapper()):
        if event._is_action_event:
            # todo: use the action from the event instead as soon as the event dialog supports attaching them
            action = Action(event.name[: -len("_action")])
            action_out = context.run_action(state=state, action=action)
            state_out = action_out.state
        else:
            state_out = context.run(state=state, event=event)

    # whatever Scenario outputted is in 'scenario_stdout_buffer' now.

    return StateNodeOutput(state_out, context.juju_log, scenario_stdout_buffer)
