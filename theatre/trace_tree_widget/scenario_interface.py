# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import contextlib
from typing import Any, Tuple, Callable

import scenario
from scenario import State, Event, Action

from theatre.trace_tree_widget.structs import StateNodeOutput
from theatre.logger import logger as theatre_logger

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


def close_event(event: Event, state: State):
    """Attempt to autofill missing event metadata."""
    try:
        if event._is_workload_event:
            if event.container:
                return event
            return event.replace(
                container=state.get_container(event.name[: -len("-pebble-ready")])
            )

        if event._is_relation_event:
            if event.relation:
                return event

            # actually kind of hard.
            raise NotImplementedError()

    except Exception:
        logger.error(exc_info=True)
        logger.warning(
            f"failure closing {event}: expect scenario inconsistency errors."
            f"Please fill the missing metadata manually."
        )


def run_scenario(context: scenario.Context, state: State, event: Event):
    with capture_output() as stdout:
        if event._is_action_event:
            # todo: use the action from the event instead as soon as the event dialog supports attaching them
            action = Action(event.name[: -len("_action")])
            action_out = context.run_action(state=state, action=action)
            state_out = action_out.state
        else:
            closed_event = close_event(event, state)
            state_out = context.run(state=state, event=closed_event)
    return StateNodeOutput(state_out, context.juju_log, stdout)
