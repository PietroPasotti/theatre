# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import os
import subprocess
import sys
import typing
from pathlib import Path

from PyQt5.QtWidgets import QFileDialog
from qtpy import QtGui
from qtpy.QtWidgets import QLabel, QPushButton
from qtpy.QtWidgets import (
    QVBoxLayout,
    QDialog,
    QDialogButtonBox,
)
from scenario import State, Context

from theatre.config import RESOURCES_DIR, PYTHON_SOURCE_TYPE
from theatre.helpers import load_module
from theatre.helpers import show_error_dialog, get_icon
from theatre.logger import logger

if typing.TYPE_CHECKING:
    pass

LOADER_TEMPLATE = RESOURCES_DIR / "templates" / "loader_template.py"


class ValidationError(RuntimeError):
    pass


class CharmCtxLoaderDialog(QDialog):
    def __init__(self, parent=None, title: str = "Select a charm context."):
        super().__init__(parent)
        self.setWindowTitle(title)
        self._button_box = QDialogButtonBox()

        self._explanation = QLabel()

        self._explanation.setText(
            f"""Please select a context loader file, or create a templated one."""
        )

        init_from_template = QPushButton("Save template")
        init_from_template.setToolTip(
            "Create a new loader file from template. "
            "Save the template file to your charm repository root and edit it.")

        existing_loader = QPushButton("Existing loader")
        existing_loader.setToolTip("Select an existing loader.")

        self._source: Path = None

        self._check = check = QPushButton("Check")
        check.setToolTip("Validate the loader file.")
        check.setIcon(get_icon("flaky"))

        button_box = self._button_box
        button_box.clear()

        button_box.addButton(init_from_template, QDialogButtonBox.ActionRole)
        button_box.addButton(existing_loader, QDialogButtonBox.ActionRole + 1)
        button_box.addButton(check, QDialogButtonBox.ApplyRole)
        self._abort = button_box.addButton("Abort", QDialogButtonBox.NoRole)
        self._confirm = button_box.addButton("Confirm", QDialogButtonBox.YesRole)

        check.clicked.connect(self._check_valid)
        init_from_template.clicked.connect(self._on_init_from_template_click)
        existing_loader.clicked.connect(self._on_existing_loader_click)
        button_box.accepted.connect(self._on_confirm)
        button_box.rejected.connect(self._on_abort)

        self._layout = QVBoxLayout()
        self._layout.addWidget(self._explanation)
        self._layout.addWidget(button_box)

        self.setLayout(self._layout)
        self.confirmed = False

    def _on_init_from_template_click(self):
        fname, _ = QFileDialog.getSaveFileName(
            self,
            "Save template to file",
            "my_theatre_loader.py",
            PYTHON_SOURCE_TYPE,
            PYTHON_SOURCE_TYPE,
        )
        try:
            path = Path(fname)
            path.write_text(LOADER_TEMPLATE.read_text())
        except Exception as e:
            msg = f"error encountered while attempting to save template to {fname}: {e}"
            logger.error(msg, exc_info=True)
            show_error_dialog(self, msg)
            return
        self._source = path
        self._try_open_source()

    def _on_existing_loader_click(self):
        fname, _ = QFileDialog.getOpenFileName(
            self,
            "Select a loader file",
            "",
            PYTHON_SOURCE_TYPE,
            PYTHON_SOURCE_TYPE,
        )
        path = Path(fname)
        self._source = path
        self._try_open_source()

    def _try_open_source(self):
        if not self._source:
            show_error_dialog("no source selected")
            return
        if sys.platform == "linux":
            subprocess.call(["xdg-open", self._source.name])
        elif sys.platform == "win32":
            os.startfile(self._source.name)
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
        self._check_valid()
        if not self._is_valid:
            show_error_dialog(self, 'cannot confirm while invalid')
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
            self._get_ctx()
        except Exception as e:
            logger.error(f"error validating", exc_info=True)
            show_error_dialog(
                self,
                f"an exception occurred while attempting to validate: {e}. "
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

    def _get_ctx(self) -> Context:
        if not self._source:
            raise RuntimeError("no source selected")

        ctx = load_charm_context(self._source)
        try:
            ctx.run("start", State())
        except Exception as e:
            raise ValidationError(
                "should be able to run the context on `start` and an empty State."
            ) from e
        return ctx

    def finalize(self) -> Context:
        return self._get_ctx()


class InvalidLoader(RuntimeError):
    pass


def load_charm_context(path: Path) -> Context:
    logger.info(f"Loading charm context from {path}.")
    module = load_module(path)

    logger.info(f"imported module {module}.")
    context_getter = getattr(module, "charm_context", None)

    if not context_getter:
        raise InvalidLoader("missing charm_context function definition")

    if not callable(context_getter):
        raise InvalidLoader(f"{path}::context_getter should be of type Callable[[], Context]")

    try:
        ctx = context_getter()
    except Exception as e:
        raise InvalidLoader(f"{path}::context_getter() raised an exception") from e

    if not isinstance(ctx, Context):
        raise InvalidLoader(f"{path}::context_getter() returned {type(ctx)}: "
                            f"instead of scenario.Context")

    logger.info(f"Successfully loaded charm {ctx.charm_spec.charm_type} context from {path}.")
    return ctx
