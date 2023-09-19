import logging

import ops
from scenario import Context, State

# TODO from charm import MyCharmType
class DummyCharm(ops.CharmBase):
    # TODO delete this class: use MyCharmType instead.

    META = {"name": "dummy charm", "requires": {"foo": {"interface": "bar"}}}

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        for event in self.on.events().values():
            framework.observe(event, self._on_event)

    def _on_event(self, _):
        opts = [
            ops.ActiveStatus(""),
            ops.BlockedStatus("whoops"),
            ops.WaitingStatus("..."),
        ]
        import random

        self.unit.status = random.choice(opts)


def charm_context() -> Context:
    """This function is expected to return a ready-to-run ``scenario.Context``.
    Edit this function as necessary.
    """
    return Context(charm_type=DummyCharm, meta=DummyCharm.META)  # TODO MyCharmType
