"""Edit this file to define any number of deltas on top of a given state.

Deltas are variations of a state.
This file includes two example delta definitions.

Any function defined in this file will be collected and called on the base state.
The state returned by it will be used in any state transitions from the delta.

Private functions (starting with "_") will not be gathered.

This module will be executed from the charm's (virtual) root, so you can freely
import from /src and /lib, like a charm.
"""

from scenario import *  # noqa


def with_leadership(state: State) -> State:  # noqa
    """Same as the base state, but charm unit has leadership."""
    return state.replace(leader=True)


def with_foo_relation(state: State) -> State:  # noqa
    """Same as the base state, but adds a relation on 'foo' with some remote app data."""
    return state.replace(
        relations=[Relation("foo", remote_app_data={"1": "2"})]  # noqa
    )
