#!/usr/bin/env python3
from ops import UnknownStatus
from scenario import Model, State  # noqa
from scenario import *  # noqa

# Fill in your state.

STATE = State(
    config={},
    relations=[],
    networks=[],
    containers=[],
    unit_status=UnknownStatus(),
    leader=False,
    model=Model(),
    secrets=[],
    unit_id=0,
    deferred=[],
    stored_state=[],
)
