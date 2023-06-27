# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import json
import typing
from dataclasses import dataclass
from pathlib import Path

from nodeeditor.utils import dumpException
from qtpy.QtCore import QSize, Qt, QByteArray, QDataStream, QMimeData, QIODevice, QPoint
from qtpy.QtGui import QDrag
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QListWidget, QAbstractItemView, QListWidgetItem
from scenario import State

from theatre.config import RESOURCES_DIR
from theatre.helpers import get_icon

if typing.TYPE_CHECKING:
    from theatre.theatre_scene import SerializedScene
    from theatre.trace_tree_widget.new_state_dialog import StateIntent

STATE_SPEC_MIMETYPE = "application/x-state"
SUBTREE_SPEC_MIMETYPE = "application/x-subtree"
SUBTREES_DIR = RESOURCES_DIR / 'subtrees'
STATES_DIR = RESOURCES_DIR / 'states'


@dataclass
class StateSpec:  # todo unify with StateIntent
    """Library entry defining a single (root) state.

    Allows adding predefined nodes.
    """

    state: State
    icon: QIcon = None
    name: str = "Anonymous State"


@dataclass
class SubtreeSpec:
    """Library entry defining a sequence of events.

    Allows adding predefined subtrees.
    """

    graph: "SerializedScene"
    icon: QIcon = None
    name: str = "Anonymous Subtree"


def load_subtree_from_file(filename: Path) -> "SerializedScene":
    if not filename.exists():
        raise FileNotFoundError(filename)
    obj = json.load(filename.open())
    return obj


# Library database
CATALOGUE: [StateSpec | SubtreeSpec] = [
    StateSpec(State(), get_icon("data_object"), "Null State"),
    StateSpec(State(leader=True), get_icon("data_object"), "Leader State"),
]


def _load_all_builtin_subtrees():
    for filename in SUBTREES_DIR.glob('*.theatre'):
        CATALOGUE.append(
            SubtreeSpec(
                graph=load_subtree_from_file(filename),
                icon=get_icon("arrow_split"),
                name=filename.name.split('.')[0].replace('_', ' ').title()
            )
        )


def get_sorted_entries(type_: type | typing.Tuple[type, ...] = None) -> [StateSpec | SubtreeSpec]:
    entries = filter(lambda x: isinstance(x, type_), CATALOGUE) if type_ else CATALOGUE
    return sorted(entries, key=lambda spec: spec.name)


def get_spec(name: str) -> StateSpec | SubtreeSpec:
    return next(filter(lambda spec: spec.name == name, CATALOGUE))


class Library(QListWidget):
    _icon_size = 32

    def __init__(self, parent=None):
        super().__init__(parent)
        _load_all_builtin_subtrees()
        self.initUI()

    def initUI(self):
        # init
        self.setIconSize(QSize(self._icon_size, self._icon_size))
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)

        self._add_entries()

    def on_node_created(self, state_intent: "StateIntent"):
        if state_intent.add_to_library:
            self._add_state(
                StateSpec(
                    state=state_intent.state,
                    icon=state_intent.icon,
                    name=state_intent.name
                )
            )

    def _add_entries(self):
        for entry in get_sorted_entries():
            self._add_entry(entry)

    def _add_entry(self, state_spec: StateSpec):
        name = state_spec.name
        item = QListWidgetItem(name, self)  # can be (icon, text, parent, <int>type)
        icon = state_spec.icon
        if icon:
            item.setIcon(icon)
        item.setSizeHint(QSize(32, 32))

        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
        item.setData(Qt.UserRole, state_spec)

    def startDrag(self, *args, **kwargs):
        try:
            item = self.currentItem()
            state_spec: StateSpec | SubtreeSpec = item.data(Qt.UserRole)
            name = state_spec.name
            icon = state_spec.icon
            pixmap = icon.pixmap(self._icon_size, self._icon_size)

            item_data = QByteArray()
            data_stream = QDataStream(item_data, QIODevice.WriteOnly)
            data_stream << pixmap
            data_stream.writeQString(name)

            mime_data = QMimeData()
            mimetype = STATE_SPEC_MIMETYPE if isinstance(state_spec, StateSpec) else SUBTREE_SPEC_MIMETYPE
            mime_data.setData(mimetype, item_data)

            drag = QDrag(self)
            drag.setMimeData(mime_data)
            drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
            drag.setPixmap(pixmap)

            drag.exec_(Qt.MoveAction)

        except Exception as e:
            dumpException(e)
