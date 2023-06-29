import ops
from scenario import Context


class DummyCharm(ops.CharmBase):
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


# should be of type Callable[[], Context]
def charm_context() -> Context:
    return Context(
        charm_type=DummyCharm,
        meta={'name': 'dummy charm',
              'requires': {'foo': {'interface': 'bar'}}}
    )
