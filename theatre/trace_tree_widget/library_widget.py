# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import typing
from dataclasses import dataclass

from nodeeditor.utils import dumpException
from qtpy.QtCore import QSize, Qt, QByteArray, QDataStream, QMimeData, QIODevice, QPoint
from qtpy.QtGui import QDrag
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QListWidget, QAbstractItemView, QListWidgetItem
from scenario import State

from theatre.helpers import get_icon
from theatre.trace_tree_widget.new_state_dialog import StateIntent

STATE_SPEC_LIBRARY_ENTRY_MIMETYPE = "application/x-item"


@dataclass
class StateSpec:  # todo unify with StateIntent
    """Library entry."""

    state: State
    icon: QIcon = None
    name: str = "Anonymous State"


# Library database
CATALOGUE = [
    StateSpec(State(), get_icon("data_object"), "Null State"),
    StateSpec(State(leader=True), get_icon("data_object"), "Leader State"),
]


def get_sorted_state_specs() -> typing.List[StateSpec]:
    return sorted(CATALOGUE, key=lambda spec: spec.name)


def get_spec(name: str) -> StateSpec:
    return next(filter(lambda spec: spec.name == name, CATALOGUE))


class Library(QListWidget):
    _icon_size = 32

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        # init
        self.setIconSize(QSize(self._icon_size, self._icon_size))
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)

        self._add_state_templates()

    def on_node_created(self, state_intent: StateIntent):
        if state_intent.add_to_library:
            self._add_state(
                StateSpec(
                    state=state_intent.state,
                    icon=state_intent.icon,
                    name=state_intent.name
                )
            )

    def _add_state_templates(self):
        for state in get_sorted_state_specs():
            self._add_state(state)

    def _add_state(self, state_spec: StateSpec):
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
            state_spec: StateSpec = item.data(Qt.UserRole)
            name = state_spec.name
            icon = state_spec.icon
            pixmap = icon.pixmap(self._icon_size, self._icon_size)

            itemData = QByteArray()
            dataStream = QDataStream(itemData, QIODevice.WriteOnly)
            dataStream << pixmap
            dataStream.writeQString(name)

            mimeData = QMimeData()
            mimeData.setData("application/x-item", itemData)

            drag = QDrag(self)
            drag.setMimeData(mimeData)
            drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
            drag.setPixmap(pixmap)

            drag.exec_(Qt.MoveAction)

        except Exception as e:
            dumpException(e)
