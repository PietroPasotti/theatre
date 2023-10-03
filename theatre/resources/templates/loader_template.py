"""Theatre loader for this charm repository.

This file should expose a ``charm_context`` callable that returns a ``scenario.Context``.

A barebone example for your typical charm repo will look like:

>>> from scenario import Context
>>> from charm import MyCharm
>>>
>>> def charm_context():
>>>     return Context(charm_type=MyCharm)

If you need to mock, patch, etc... to make your charm runnable by Scenario, this is where
you can do so.
The context you return from ``charm_context`` should be runnable as_is.

>>> from scenario import Context
>>> from charm import MyCharm
>>>
>>> def charm_context():
>>>     MyCharm._make_call_to_kubernetes_api = lambda: "42"
>>>     return Context(charm_type=MyCharm)
"""

import ops
from scenario import Context


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
