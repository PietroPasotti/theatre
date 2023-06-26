# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import importlib
import json
import os
import subprocess
import sys
import tempfile
import types
import typing
from dataclasses import dataclass, asdict
from enum import Enum
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

from logger import logger
from theatre.helpers import show_error_dialog, get_icon

if typing.TYPE_CHECKING:
    from theatre.trace_tree_widget.state_node import StateNode

TEMPLATES_DIR = Path(__file__).parent.parent / "resources"
NEW_STATE_TEMPLATE = "new_state_template.py"
EDIT_STATE_TEMPLATE = "edit_state_template.py"
DEFAULT_TEMPLATE = NEW_STATE_TEMPLATE


def read_template(name=DEFAULT_TEMPLATE, dir=TEMPLATES_DIR):
    return (Path(dir) / name).read_text()


@dataclass
class StateIntent:
    state: State
    add_to_library: bool
    name: str = ""
    icon: QIcon = None


class Mode(Enum):
    new = 'new'
    edit = 'edit'


class NewStateDialog(QDialog):
    def __init__(self, parent=None, mode: Mode=Mode.new, base: "StateNode" = None):
        super().__init__(parent)
        if mode is Mode.new:
            title = "Create a new Root State."
            template_text = read_template(NEW_STATE_TEMPLATE)
            lib_name = "Custom State"
        else:
            title = f"Edit {base}."
            state_repr = json.dumps(asdict(base.value.state))
            template_text = read_template(EDIT_STATE_TEMPLATE).format(state_repr)
            lib_name = base.title

        self.setWindowTitle(title)

        self._state_tempfile = state_tempfile = tempfile.NamedTemporaryFile(
            dir="/tmp", prefix="edit_state", suffix=".py"
        )
        Path(state_tempfile.name).write_text(template_text)

        self._button_box = QDialogButtonBox()
        button_box = self._button_box
        button_box.clear()

        self._explanation = QLabel()
        self._library_name_input = QLineEdit(lib_name)

        self._add_to_library = QCheckBox()
        self._add_to_library.setText("Add to library")

        self._explanation.setText(
            f"""Edit {state_tempfile.name} and don't forget to save!"""
        )
        #
        #     statusTip=f"Open {state_tempfile.name} in your favourite editor.",
        #
        #     statusTip="Validate the file.",
        #
        #     statusTip="Abort and close the dialog.",
        #
        #     statusTip="Confirm and create the state.",
        #
        # )

        edit = QPushButton("Edit")
        self._check = check = QPushButton("Check")
        check.setIcon(get_icon("flaky"))

        button_box.addButton(edit, QDialogButtonBox.ActionRole)
        button_box.addButton(check, QDialogButtonBox.ApplyRole)
        self._abort = button_box.addButton("Abort", QDialogButtonBox.NoRole)
        self._confirm = button_box.addButton("Confirm", QDialogButtonBox.YesRole)

        check.clicked.connect(self._check_valid)
        edit.clicked.connect(self._try_open_state_tempfile)
        button_box.accepted.connect(self._on_confirm)
        button_box.rejected.connect(self._on_abort)

        self._layout = QVBoxLayout()
        self._layout.addWidget(self._explanation)
        self._layout.addWidget(self._add_to_library)
        self._layout.addWidget(self._library_name_input)
        self._layout.addWidget(button_box)

        self.setLayout(self._layout)
        self.confirmed = False

    def _try_open_state_tempfile(self):
        if sys.platform == "linux":
            subprocess.call(["xdg-open", self._state_tempfile.name])
        elif sys.platform == "win32":
            os.startfile(self._state_tempfile.name)
        else:
            show_error_dialog(
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
        self._confirm.setEnabled(valid)
        self._check.setIcon(get_icon("stars") if valid else get_icon("error"))

    @property
    def _is_valid(self) -> bool:
        try:
            self._get_state()
        except Exception as e:
            logger.error(f"error getting state", exc_info=True)
            show_error_dialog(
                self,
                f"an exception occurred while attempting to retrieve the state: {e}. "
                f"See the logs for more details.",
            )
            return False

        return True

    @property
    def _should_add_to_library(self) -> bool:
        if not self.confirmed:
            raise RuntimeError("not confirmed")
        return self._add_to_library.checkState()

    @property
    def _library_name(self) -> str:
        if not self.confirmed:
            raise RuntimeError("not confirmed")
        return self._library_name_input.text()

    def _get_state(self) -> State:
        module = load_module(Path(self._state_tempfile.name))
        state = getattr(module, "STATE")
        if not isinstance(state, State):
            raise TypeError(type(state))
        return state

    def finalize(self) -> StateIntent:
        return StateIntent(
            self._get_state(),
            self._should_add_to_library,
            self._library_name,
            # todo: add icon selection
        )


def load_module(path: Path) -> types.ModuleType:
    """Import the file at path as a python module."""

    # so we can import without tricks
    sys.path.append(str(path.parent))
    # strip .py
    module_name = str(path.with_suffix("").name)

    # if a previous call to load_module has loaded a
    # module with the same name, this will conflict.
    # besides, we don't really want this to be importable from anywhere else.
    if module_name in sys.modules:
        del sys.modules[module_name]

    try:
        module = importlib.import_module(module_name)
    except ImportError:
        raise
    finally:
        # cleanup
        sys.path.remove(str(path.parent))

    return module
