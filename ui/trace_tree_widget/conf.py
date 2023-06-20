from dataclasses import dataclass

from qtpy.QtGui import QIcon
from scenario import State

from ui.helpers import get_icon

LISTBOX_MIMETYPE = "application/x-item"


@dataclass
class StateSpec:
    state: State
    icon: QIcon = None


STATES = {
    "null state": StateSpec(
        State(),
        get_icon('data_object')
    )}


def get_state(name: str) -> StateSpec:
    return STATES.get(name)
