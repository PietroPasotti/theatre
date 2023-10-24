# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import contextlib
from typing import Any, Callable, Tuple

import scenario
from scenario import Action, Event, State
from scenario.state import BindFailedError

from theatre.logger import logger as theatre_logger
from theatre.trace_tree_widget.structs import StateNodeOutput

logger = theatre_logger.getChild("scenario_interface")


@contextlib.contextmanager
def capture_output() -> Tuple[Any, str]:
    stdout_buffer = ""

    # fixme: logging redirect not quite working

    class StreamWrapper:
        def write(self, msg):
            if msg and not msg.isspace():
                nonlocal stdout_buffer
                stdout_buffer += msg

        def flush(self):
            pass

    # todo: if the event is a relation event, patch in
    #  the relation object from state that we're referring to.

    with contextlib.redirect_stdout(StreamWrapper()):
        # whatever this call output is in 'stdout_buffer' now.
        yield stdout_buffer


def run_scenario(context: scenario.Context, state: State, event: Event):
    with capture_output() as stdout:
        if event._is_action_event:
            # todo: use the action from the event instead as soon as the event dialog supports attaching them
            action = Action(event.name[: -len("_action")])
            action_out = context.run_action(state=state, action=action)
            state_out = action_out.state
        else:
            try:
                closed_event = event.bind(state)
            except BindFailedError:
                logger.debug("bind failed: might get an inconsistent scenario error")
                closed_event = event
            state_out = context.run(state=state, event=closed_event)
    return StateNodeOutput(state_out, context.juju_log, stdout)
