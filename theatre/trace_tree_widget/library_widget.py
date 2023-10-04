# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import json
import typing
from dataclasses import dataclass
from pathlib import Path

from qtpy.QtCore import QByteArray, QDataStream, QIODevice, QMimeData, QPoint, QSize, Qt
from qtpy.QtGui import QDrag, QIcon
from qtpy.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem
from scenario import State
from scenario.state import Container, _CharmSpec

from theatre.config import RESOURCES_DIR
from theatre.dialogs.file_backed_edit_dialog import Intent
from theatre.helpers import get_icon
from theatre.logger import logger as theatre_logger

if typing.TYPE_CHECKING:
    from theatre.theatre_scene import SerializedScene

logger = theatre_logger.getChild("library_widget")


STATE_SPEC_MIMETYPE = "application/x-state"
SUBTREE_SPEC_MIMETYPE = "application/x-subtree"
DYNAMIC_SUBTREE_SPEC_MIMETYPE = "application/x-subtree-dynamic"
DYNAMIC_STATE_SPEC_MIMETYPE = "application/x-state-dynamic"
SUBTREES_DIR = RESOURCES_DIR / "subtrees"
DYNAMIC_SUBTREES_TEMPLATES_DIR = SUBTREES_DIR / "dynamic"
STATES_DIR = RESOURCES_DIR / "states"


@dataclass
class StateSpec:  # todo unify with StateIntent
    """Library entry defining a single (root) state.

    Allows adding predefined nodes.
    """

    state: State
    icon: QIcon = None
    name: str = "Anonymous State"


@dataclass
class LibraryEntry:
    icon: QIcon = None
    name: str = "Anonymous Subtree"


@dataclass
class SubtreeSpec(LibraryEntry):
    """Library entry defining a sequence of events.

    Allows adding predefined subtrees.
    """

    graph: "SerializedScene" = None


@dataclass
class DynamicSubtreeSpec(LibraryEntry):
    """Library entry defining a dynamically generated sequence of events."""

    # the graph is created by the node editor


@dataclass
class DynamicStateSpec(LibraryEntry):
    """Library entry defining a dynamically generated state."""

    # the state is created by the node editor upon selection

    get_state: typing.Callable[["_CharmSpec"], State] = None  # actually required.


def load_subtree_from_file(filename: Path) -> "SerializedScene":
    if not filename.exists():
        raise FileNotFoundError(filename)
    obj = json.load(filename.open())
    return obj


# Library database
CATALOGUE: [LibraryEntry] = []


class DynamicSubtreeName:
    RELATION_LIFECYCLE = "Relation lifecycle"
    FAN_OUT = "Fan out"


class DynamicSpecName:
    NULL_CONTAINERS = "Null with containers"
    NULL_CONTAINERS_READY = "Null with containers (ready)"


def _load_all_builtin_dynamic_subtrees():
    standard_icon = get_icon("arrow_split_magic")
    CATALOGUE.extend(
        [
            DynamicSubtreeSpec(standard_icon, DynamicSubtreeName.RELATION_LIFECYCLE),
            DynamicSubtreeSpec(get_icon("hub"), DynamicSubtreeName.FAN_OUT),
        ]
    )


def _load_all_builtin_specs():
    CATALOGUE.extend(
        [
            StateSpec(State(), get_icon("data_object"), "Null State"),
            StateSpec(
                State(leader=True), get_icon("data_object_badge"), "Leader State"
            ),
        ]
    )


def _null_state_with_all_containers_ready(cs: "_CharmSpec") -> State:
    containers = []
    for container in cs.meta.get("containers", ()):
        containers.append(Container(container, can_connect=True))
    return State(containers=containers)


def _null_state_with_all_containers_not_ready(cs: "_CharmSpec") -> State:
    containers = []
    for container in cs.meta.get("containers", ()):
        containers.append(Container(container))
    return State(containers=containers)


def _load_all_builtin_dynamic_specs():
    CATALOGUE.extend(
        [
            DynamicStateSpec(
                get_icon("data_object_box_dash"),
                DynamicSpecName.NULL_CONTAINERS,
                get_state=_null_state_with_all_containers_not_ready,
            ),
            DynamicStateSpec(
                get_icon("data_object_box"),
                DynamicSpecName.NULL_CONTAINERS_READY,
                get_state=_null_state_with_all_containers_ready,
            ),
        ]
    )


def _load_all_builtin_subtrees():
    standard_icon = get_icon("arrow_split")
    for filename in SUBTREES_DIR.glob("*.theatre"):
        CATALOGUE.append(
            SubtreeSpec(
                graph=load_subtree_from_file(filename),
                icon=standard_icon,
                name=filename.name.split(".")[0].replace("_", " ").title(),
            )
        )


_SPEC_ORDERING = {
    StateSpec: 0,
    DynamicStateSpec: 1,
    SubtreeSpec: 2,
    DynamicSubtreeSpec: 3,
}


def get_sorted_entries(type_: type | typing.Tuple[type, ...] = None) -> [LibraryEntry]:
    """All library entries in the catalogue, sorted by type first, by name second."""
    entries = filter(lambda x: isinstance(x, type_), CATALOGUE) if type_ else CATALOGUE
    return sorted(entries, key=lambda spec: (_SPEC_ORDERING[type(spec)]))


def get_spec(name: str) -> LibraryEntry:
    return next(filter(lambda spec: spec.name == name, CATALOGUE))


def get_mimetype(library_entry: LibraryEntry) -> str:
    if isinstance(library_entry, StateSpec):
        return STATE_SPEC_MIMETYPE
    elif isinstance(library_entry, SubtreeSpec):
        return SUBTREE_SPEC_MIMETYPE
    elif isinstance(library_entry, DynamicSubtreeSpec):
        return DYNAMIC_SUBTREE_SPEC_MIMETYPE
    elif isinstance(library_entry, DynamicStateSpec):
        return DYNAMIC_STATE_SPEC_MIMETYPE
    else:
        raise TypeError(library_entry)


class Library(QListWidget):
    _icon_size = 32

    def __init__(self, parent=None):
        super().__init__(parent)
        _load_all_builtin_specs()
        _load_all_builtin_dynamic_specs()
        _load_all_builtin_subtrees()
        _load_all_builtin_dynamic_subtrees()
        self.initUI()

    def initUI(self):
        # init
        self.setIconSize(QSize(self._icon_size, self._icon_size))
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)

        self._add_entries()

    def on_node_created(self, state_intent: "Intent"):
        if state_intent.add_to_library:
            self._add_entry(
                StateSpec(
                    state=state_intent.output,
                    icon=state_intent.icon,
                    name=state_intent.name,
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
            library_entry: LibraryEntry = item.data(Qt.UserRole)
            name = library_entry.name
            icon = library_entry.icon
            pixmap = icon.pixmap(self._icon_size, self._icon_size)

            item_data = QByteArray()
            data_stream = QDataStream(item_data, QIODevice.WriteOnly)
            data_stream.writeQString(name)

            mime_data = QMimeData()
            mimetype = get_mimetype(library_entry)

            mime_data.setData(mimetype, item_data)

            drag = QDrag(self)
            drag.setMimeData(mime_data)
            drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
            drag.setPixmap(pixmap)

            drag.exec_(Qt.MoveAction)

        except Exception as e:
            logger.error(e, exc_info=True)
