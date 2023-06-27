# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import typing
from dataclasses import dataclass
from itertools import chain

from scenario.state import ACTION_EVENT_SUFFIX, RELATION_EVENTS_SUFFIX, STORAGE_EVENTS_SUFFIX, \
    PEBBLE_READY_EVENT_SUFFIX
from PyQt5 import QtGui
from PyQt5.QtGui import QFont, QIntValidator
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLayout,
    QLineEdit,
    QLabel,
    QPlainTextEdit,
    QDialog,
    QDialogButtonBox,
    QComboBox, QAction,
)
from scenario import Event

if typing.TYPE_CHECKING:
    from scenario.state import _CharmSpec

LIFECYCLE_EVENTS = (
    "collect-metrics",
    "config-changed",
    "install",
    "leader-elected",
    "leader-settings-changed",
    "post-series-upgrade",
    "pre-series-upgrade",
    "remove",
    "start",
    "stop",
    "update-status",
    "upgrade-charm",
)

# fixme: when scenario 4.0 lands, replace with scenario.state.SECRET_EVENTS
SECRET_EVENTS = (
    "secret-changed",
    "secret-expired",
    "secret-remove",
    "secret-rotate",
)

@dataclass
class EventSpec:
    event: Event
    env: typing.Dict[str, str]


class EventConfig(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setSizeConstraint(QLayout.SetMinimumSize)

        self.inputs = []
        self._main_layout = layout
        self.setLayout(layout)
        self.event_name: str = None
        self._edit: QLineEdit = None

    def add_field(self, widget: "Field"):
        layout = self._main_layout
        layout.addWidget(widget)
        self.inputs.append(widget)

    def clear(self):
        for field in self.inputs:
            self.layout().removeWidget(field)
        self.inputs.clear()

    def specialize(self, event_name: str):
        self.event_name = event_name

        self.clear()
        self.add_field(TextField("override env"))

        if event_name.endswith("relation-changed"):
            self.add_field(IntField("remote unit id", 0))
            self.add_field(StrField("remote application name", "remote"))

    def _set_event_name(self, e):
        self.event_name = self._edit.text()

    def get_output(self) -> typing.Dict[str, typing.Any]:
        return {field.name: field.get_value() for field in self.inputs}


class Field(QWidget):
    name: str

    def get_value(self) -> typing.Any:
        raise NotImplementedError()


class IntField(Field):
    def __init__(self, title, initial_value=None):
        QWidget.__init__(self)
        self.name = title
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.label = QLabel()
        self.label.setText(title)
        self.label.setFont(QFont("Arial", weight=QFont.Bold))
        layout.addWidget(self.label)

        self.lineEdit = QLineEdit(self)
        self.lineEdit.setFixedWidth(40)
        self.lineEdit.setValidator(QIntValidator())

        if initial_value is not None:
            self.lineEdit.setText(str(initial_value))

        layout.addWidget(self.lineEdit)
        layout.addStretch()

    def get_value(self):
        return int(self.lineEdit.text())


class StrField(Field):
    def __init__(self, title, initial_value=None):
        QWidget.__init__(self)
        self.name = title
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.label = QLabel()
        self.label.setText(title)
        self.label.setFixedWidth(100)
        self.label.setFont(QFont("Arial", weight=QFont.Bold))
        layout.addWidget(self.label)

        self.lineEdit = QLineEdit(self)
        self.lineEdit.setFixedWidth(40)
        # self.lineEdit.setValidator(Validator())

        if initial_value is not None:
            self.lineEdit.setText(str(initial_value))

        layout.addWidget(self.lineEdit)
        layout.addStretch()

    def get_value(self) -> str:
        return self.lineEdit.text()


class TextField(Field):
    def __init__(self, title, initial_value=None):
        QWidget.__init__(self)
        self.name = title
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.label = QLabel()
        self.label.setText(title)
        self.label.setFixedWidth(100)
        self.label.setFont(QFont("Arial", weight=QFont.Bold))
        layout.addWidget(self.label)

        self.lineEdit = QPlainTextEdit(self)
        # self.lineEdit.setValidator(Validator())

        if initial_value is not None:
            self.lineEdit.setText(str(initial_value))

        layout.addWidget(self.lineEdit)
        layout.addStretch()

    def get_value(self) -> str:
        return self.lineEdit.toPlainText()


class EventPicker(QDialog):
    def __init__(self, charm_spec: "_CharmSpec", parent=None):
        super().__init__(parent)
        self._charm_spec = charm_spec

        self.setWindowTitle("Let's fire an event!")

        QBtn = QDialogButtonBox.Cancel | QDialogButtonBox.Ok

        self.event_config = EventConfig(self)
        self.button_box = QDialogButtonBox(QBtn)

        self.button_box.rejected.connect(self.on_abort)
        self.button_box.accepted.connect(self.on_confirm)

        self.layout = QVBoxLayout()
        self.event_name = event_name = QComboBox()
        self.event_name.currentTextChanged.connect(self.event_config.specialize)

        self._add_events(event_name)

        self.layout.addWidget(event_name)
        self.layout.addWidget(self.event_config)
        self.layout.addWidget(self.button_box)
        self.setLayout(self.layout)
        self.confirmed = False

    def _add_events(self, dropdown: QComboBox):
        def _add_sep():
            sep = QAction()
            sep.setSeparator(True)
            dropdown.addAction(sep)

        # Lifecycle events
        for name in LIFECYCLE_EVENTS:
            dropdown.addItem(name)
        _add_sep()
        # Lifecycle events
        for name in SECRET_EVENTS:
            dropdown.addItem(name)
        _add_sep()
        # Dynamically defined builtin events

        charm_spec = self._charm_spec
        builtins = []
        for relation_name in chain(
                charm_spec.meta.get("requires", ()),
                charm_spec.meta.get("provides", ()),
                charm_spec.meta.get("peers", ()),
        ):
            relation_name = relation_name.replace("-", "_")
            for relation_evt_suffix in RELATION_EVENTS_SUFFIX:
                builtins.append(relation_name + relation_evt_suffix)

        for storage_name in charm_spec.meta.get("storages", ()):
            storage_name = storage_name.replace("-", "_")
            for storage_evt_suffix in STORAGE_EVENTS_SUFFIX:
                builtins.append(storage_name + storage_evt_suffix)

        for action_name in charm_spec.actions or ():
            action_name = action_name.replace("-", "_")
            builtins.append(action_name + ACTION_EVENT_SUFFIX)

        for container_name in charm_spec.meta.get("containers", ()):
            container_name = container_name.replace("-", "_")
            builtins.append(container_name + PEBBLE_READY_EVENT_SUFFIX)


    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        super().closeEvent(a0)
        self.on_abort()

    def on_abort(self, _=None):
        self.close()

    def on_confirm(self, _=None):
        self.confirmed = True
        self.close()

    def get_event(self) -> EventSpec:
        return EventSpec(
            Event(name=self.event_config.event_name),
            env=self.event_config.get_output()[
                "override env"
            ],  # todo: parse as str:str dict
        )
