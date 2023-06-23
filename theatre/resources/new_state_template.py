#!/usr/bin/env python3
from ops import UnknownStatus
from scenario import *

# Fill in your state.
# Alternatively, you can set STATE to a jsonified State object.

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
