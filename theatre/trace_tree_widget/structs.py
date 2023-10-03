# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import inspect
import typing
from dataclasses import dataclass

import scenario
from scenario.state import JujuLogLine


@dataclass
class StateNodeOutput:
    state: typing.Optional[scenario.State] = None
    charm_logs: typing.Optional[typing.List[JujuLogLine]] = None
    scenario_logs: typing.Optional[str] = None
    exception: typing.Optional[Exception] = None

    @property
    def traceback(self) -> typing.Optional[inspect.Traceback]:
        if self.exception:
            return self.exception.__traceback__
        return None
