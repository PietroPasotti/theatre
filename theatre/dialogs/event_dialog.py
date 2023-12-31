# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import typing
from dataclasses import dataclass

from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QMenu
from qtpy import QtGui
from qtpy.QtCore import Signal
from qtpy.QtGui import QFont, QIntValidator
from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from scenario import Event
from scenario.state import (
    ACTION_EVENT_SUFFIX,
    PEBBLE_READY_EVENT_SUFFIX,
    RELATION_EVENTS_SUFFIX,
    STORAGE_EVENTS_SUFFIX,
    SECRET_EVENTS,
)

from theatre.helpers import get_icon, get_event_icon, show_error_dialog
from theatre.logger import logger as theatre_logger

logger = theatre_logger.getChild(__file__)

if typing.TYPE_CHECKING:
    from scenario.state import _CharmSpec

LIFECYCLE_EVENTS = (
    # "collect-metrics",
    "config_changed",
    "install",
    "leader_elected",
    "leader_settings_changed",
    "post_series_upgrade",
    "pre_series_upgrade",
    "remove",
    "start",
    "stop",
    "update_status",
    "upgrade_charm",
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

        evt = Event(event_name)
        if evt._is_relation_event:
            self.add_field(IntField("remote unit id", 0))
            self.add_field(StrField("remote application name", "remote"))

        if evt._is_action_event:
            # TODO
            logger.warning("cannot configure action events yet")

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
        self.label.setFont(QFont("Arial", weight=QFont.Bold))
        layout.addWidget(self.label)

        self.lineEdit = QLineEdit(self)

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


class EventMenu(QMenu):
    def __init__(
        self, parent: typing.Optional["QWidget"], charm_spec: "_CharmSpec"
    ) -> None:
        super().__init__(parent)
        lifecycle = self.addMenu(get_icon("cycle"), "lifecycle")
        secret = self.addMenu(get_icon("lock"), "secret")
        # self._ops = ops = self.addMenu("ops")

        for evt in LIFECYCLE_EVENTS:
            lifecycle.addAction(get_event_icon(evt), evt)

        for evt in SECRET_EVENTS:
            secret.addAction(get_event_icon(evt), evt)

        # Dynamically defined builtin events
        _relations_menu = None
        for rel_type, icon_name in [
            ("requires", "arrow_back"),
            ("provides", "arrow_forward"),
            ("peers", "compare_arrows"),
        ]:
            relations = charm_spec.meta.get(rel_type, ())
            submenu_icon = get_icon(icon_name)
            if relations:
                relation_menu = _relations_menu or self.addMenu(
                    get_icon("compare_arrows"), "relation"
                )
                _relations_menu = relation_menu

                for relation_name in relations:
                    relation_submenu = relation_menu.addMenu(
                        submenu_icon, relation_name
                    )
                    relation_name = relation_name.replace("-", "_")
                    for relation_evt_suffix in RELATION_EVENTS_SUFFIX:
                        evt = relation_name + relation_evt_suffix
                        relation_submenu.addAction(get_event_icon(evt), evt)

        storages = charm_spec.meta.get("storages")
        if storages:
            storage_menu = self.addMenu(get_icon("hard_drive"), "storage")
            for storage_name in storages:
                storage_submenu = storage_menu.addMenu(storage_name)
                storage_name = storage_name.replace("-", "_")
                for storage_evt_suffix in STORAGE_EVENTS_SUFFIX:
                    evt = storage_name + storage_evt_suffix
                    storage_submenu.addAction(get_event_icon(evt), evt)

        actions = charm_spec.actions
        if actions:
            actions_menu = self.addMenu(get_icon("handyman"), "actions")
            for action_name in actions:
                action_name = action_name.replace("-", "_")
                evt = action_name + ACTION_EVENT_SUFFIX
                actions_menu.addAction(get_event_icon(evt), evt)

        workloads = charm_spec.meta.get("containers")
        if workloads:
            workload_menu = self.addMenu(get_icon("cloud_circle"), "workload")
            for container_name in workloads:
                container_name = container_name.replace("-", "_")
                evt = container_name + PEBBLE_READY_EVENT_SUFFIX
                workload_menu.addAction(get_event_icon(evt), evt)


class EventSelector(QWidget):
    event_selected = Signal(str)

    def __init__(self, parent, charm_spec: "_CharmSpec"):
        super().__init__(parent)
        self._charm_spec = charm_spec

        self.line_edit = te = QLineEdit(self)
        self.select_button = sb = QPushButton(self)
        sb.setIcon(get_icon("edit"))

        self._layout = layout = QHBoxLayout(self)
        layout.addWidget(te)
        layout.addWidget(sb)

        te.textChanged.connect(self._on_text_edit_changed)
        sb.clicked.connect(self._on_select_button_clicked)

    def _on_text_edit_changed(self):
        self.event_selected.emit(self.line_edit.text())

    def _on_select_button_clicked(self):
        em = EventMenu(self, self._charm_spec)
        selected = em.exec(QCursor.pos())
        if selected:
            name = selected.text()
            self.line_edit.setText(name)
            self.event_selected.emit(name)


class EventPicker(QDialog):
    """Dialog to select and configure an event for an EventEdge."""

    DEFAULT_TITLE = "Select and configure an event."

    def __init__(self, charm_spec: "_CharmSpec", parent=None, title: str = None):
        super().__init__(parent)
        self._charm_spec = charm_spec

        self.setWindowTitle(title or self.DEFAULT_TITLE)

        QBtn = QDialogButtonBox.Cancel | QDialogButtonBox.Ok

        self.event_config = EventConfig(self)
        self.button_box = QDialogButtonBox(QBtn)

        self.button_box.rejected.connect(self.on_abort)
        self.button_box.accepted.connect(self.on_confirm)

        self.layout = QVBoxLayout()
        self.event_name = event_name = EventSelector(self, charm_spec)
        self.event_name.event_selected.connect(self.event_config.specialize)

        self.layout.addWidget(event_name)
        self.layout.addWidget(self.event_config)
        self.layout.addWidget(self.button_box)
        self.setLayout(self.layout)
        self.confirmed = False

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        super().closeEvent(a0)
        self.on_abort()

    def on_abort(self, _=None):
        self.close()

    def on_confirm(self, _=None):
        if not self.event_config.event_name:
            show_error_dialog(self, "Event name empty.")
            return

        self.confirmed = True
        self.close()

    def get_event(self) -> EventSpec:
        if not self.confirmed:
            raise RuntimeError("unconfirmed dialog.")

        return EventSpec(
            Event(self.event_config.event_name),
            env=self.event_config.get_output()[
                "override env"
            ],  # todo: parse as str:str dict
        )
