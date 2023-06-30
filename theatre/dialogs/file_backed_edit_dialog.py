# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import os
import subprocess
import sys
import tempfile
import typing
from dataclasses import dataclass
from pathlib import Path

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QLineEdit
from qtpy import QtGui
from qtpy.QtWidgets import QLabel, QPushButton, QCheckBox
from qtpy.QtWidgets import (
    QVBoxLayout,
    QDialog,
    QDialogButtonBox,
)
from scenario import State

from theatre.config import RESOURCES_DIR
from theatre.helpers import show_error_dialog, get_icon
from theatre.logger import logger

TEMPLATES_DIR = RESOURCES_DIR / "templates"


def read_template(name, dir=TEMPLATES_DIR):
    return (Path(dir) / name).read_text()


T = typing.TypeVar("T")


@dataclass
class Intent(typing.Generic[T]):
    output: [T]
    add_to_library: bool
    name: str = ""
    icon: QIcon = None


class FileBackedEditDialog(QDialog):
    OFFER_LIBRARY_OPTION = False
    EDIT_BUTTON_TEXT = "Edit"

    def __init__(self, parent=None, title: str = "", from_tempfile: str = "",
                 instructions: str = "Edit the source file."):
        super().__init__(parent)

        self.setWindowTitle(title)

        self._button_box = QDialogButtonBox()
        button_box = self._button_box
        button_box.clear()

        self._explanation = QLabel()

        if from_tempfile:
            tf = tempfile.NamedTemporaryFile(
                dir="/tmp", prefix="edit_state", suffix=".py"
            )
            Path(tf.name).write_text(from_tempfile)
            self._tempfile = tf
            self._set_source(Path(tf.name))

        self._explanation.setText(instructions)
        self._edit_button = edit = QPushButton(self.EDIT_BUTTON_TEXT)
        self._check_button = check = QPushButton("Check")
        check.setIcon(get_icon("flaky"))

        button_box.addButton(edit, QDialogButtonBox.ActionRole)
        button_box.addButton(check, QDialogButtonBox.ApplyRole)
        self._abort_button = button_box.addButton("Abort", QDialogButtonBox.NoRole)
        self._confirm_button = button_box.addButton("Confirm", QDialogButtonBox.YesRole)

        check.clicked.connect(self._check_valid)
        edit.clicked.connect(self._on_edit_click)
        button_box.accepted.connect(self._on_confirm)
        button_box.rejected.connect(self._on_abort)

        self._layout = QVBoxLayout()
        self._layout.addWidget(self._explanation)

        if self.OFFER_LIBRARY_OPTION:
            self._library_name_input = QLineEdit(title)
            self._add_to_library = QCheckBox()
            self._add_to_library.setText("Add to library")
            self._layout.addWidget(self._add_to_library)
            self._layout.addWidget(self._library_name_input)

        self._layout.addWidget(button_box)

        self.setLayout(self._layout)
        self.confirmed = False
        self._source: Path
        self._set_source(None, _check_valid=False)  # type:ignore

    def _set_source(self, file: Path, _check_valid: bool = True):
        self._source = file
        self._explanation.setText(
            f"Edit the source file: {file}. When ready, confirm." if file else "Select or create a source file."
        )
        logger.info(f"source set to {file}")
        if _check_valid:
            self._check_valid()

    def _on_edit_click(self):
        if not self._check_source_set():
            return
        self._open_source_in_system_editor()

    def _open_source_in_system_editor(self):
        """Attempt to open source file in system editor."""
        if sys.platform == "linux":
            subprocess.call(["xdg-open", self._source.name])
        elif sys.platform == "win32":
            os.startfile(self._source.name)
        else:
            show_error_dialog(
                self,
                f"unsupported platform: {sys.platform}; "
                f"edit the file manually and click check/confirm when ready."
            )

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        super().closeEvent(a0)
        self._on_abort()

    def _on_abort(self):
        self.close()

    def _on_confirm(self):
        if not self._is_valid:
            logger.error("confirmed dialog while invalid")
            self.close()
            return

        self.confirmed = True
        self.close()

    def _check_valid(self):
        valid = self._is_valid
        self._confirm_button.setEnabled(valid)
        self._check_button.setIcon(get_icon("stars") if valid else get_icon("error"))

    def close(self) -> bool:
        print('closing')
        return super().close()

    def _check_source_set(self) -> bool:
        if not self._source:
            show_error_dialog(self,
                              'no source file selected')
            return False
        return True

    @property
    def _is_valid(self) -> bool:
        if not self._check_source_set():
            return False

        try:
            self.get_output()
        except Exception as e:
            logger.error(f"error getting state", exc_info=True)
            show_error_dialog(
                self,
                f"Selected source ({self._source}) is invalid: {e}. "
                f"See the logs for more details.",
                title="Invalid."
            )
            return False

        return True

    @property
    def _should_add_to_library(self) -> bool:
        if not self.self.OFFER_LIBRARY_OPTION:
            return False
        if not self.confirmed:
            raise RuntimeError("not confirmed")
        return self._add_to_library.isChecked()

    @property
    def _library_name(self) -> str | None:
        if not self.self.OFFER_LIBRARY_OPTION:
            return None
        if not self.confirmed:
            raise RuntimeError("not confirmed")
        return self._library_name_input.text()

    def get_output(self) -> T:
        raise NotImplementedError("override get_output")

    def finalize(self) -> Intent[State]:
        return Intent(
            self.get_output(),
            self._should_add_to_library,
            self._library_name,
            # todo: add icon selection
        )
