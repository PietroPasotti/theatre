# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import typing
from dataclasses import dataclass

from qtpy.QtGui import QIcon
from qtpy import QtGui
from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QLabel,
    QVBoxLayout,
)

from theatre.helpers import get_icon, show_error_dialog
from theatre.logger import logger


class RelationPickerDialog(QDialog):
    def __init__(
        self,
        parent=None,
        title: str = "Relation picker",
        instructions: str = "Select a relation.",
        options: typing.Iterable[str] = (),
    ):
        super().__init__(parent)

        self.setWindowTitle(title)

        self._button_box = QDialogButtonBox()
        button_box = self._button_box
        button_box.clear()
        self.confirmed = False

        self._explanation = QLabel()
        self._explanation.setText(instructions)
        self._picker = picker = QComboBox(self)

        for option in options:
            picker.addItem(option)

        self._abort_button = button_box.addButton("Abort", QDialogButtonBox.NoRole)
        self._confirm_button = button_box.addButton("Confirm", QDialogButtonBox.YesRole)

        button_box.accepted.connect(self._on_confirm)
        button_box.rejected.connect(self._on_abort)

        self._layout = QVBoxLayout()
        self._layout.addWidget(self._explanation)

        self._layout.addWidget(button_box)

        self.setLayout(self._layout)

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        super().closeEvent(a0)
        self._on_abort()

    def _on_abort(self):
        self.close()

    def _on_confirm(self):
        self.confirmed = True
        self.close()

    def get_output(self) -> str:
        return self._picker.currentText()

    def finalize(self) -> typing.Optional[str]:
        if not self.confirmed:
            return None
        return self.get_output()
