# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from pathlib import Path

from PyQt5.QtWidgets import QFileDialog
from qtpy import QtGui
from qtpy.QtWidgets import QPushButton
from scenario import State, Context

from theatre.config import PYTHON_SOURCE_TYPE
from theatre.dialogs.file_backed_edit_dialog import FileBackedEditDialog, TEMPLATES_DIR
from theatre.helpers import load_module
from theatre.helpers import show_error_dialog
from theatre.logger import logger

LOADER_TEMPLATE = TEMPLATES_DIR / "loader_template.py"


class CharmCtxLoaderDialog(FileBackedEditDialog):

    def __init__(self, parent=None):
        super().__init__(
            parent,
            "Select or create a context loader file."
        )

        self._open_existing_button = existing = QPushButton("Select existing")
        existing.setToolTip("Select an existing loader.")
        self._button_box.addButton(existing, self._button_box.ActionRole)
        existing.clicked.connect(self._on_existing_loader_click)

        self._new_from_template = new_from_template = QPushButton("New from template")
        new_from_template.setToolTip(
            "Create a new loader file from template. "
            "Save the template file to your charm repository root and edit it.")
        self._button_box.addButton(new_from_template, self._button_box.ActionRole)
        new_from_template.clicked.connect(self._on_new_from_template_click)

    def _on_new_from_template_click(self):
        # let the user create a file.
        fname, _ = QFileDialog.getSaveFileName(
            self,
            "Choose a file to save the loader to",
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
        self._set_source(path)

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        super().closeEvent(a0)

    def _on_existing_loader_click(self):
        fname, _ = QFileDialog.getOpenFileName(
            self,
            "Select a loader file",
            "",
            PYTHON_SOURCE_TYPE,
            PYTHON_SOURCE_TYPE,
        )
        path = Path(fname)
        self._set_source(path)

    def get_output(self) -> Context:
        if not self._source:
            raise RuntimeError("no source selected")

        ctx = load_charm_context(self._source)
        try:
            ctx.run("start", State())
        except Exception as e:
            raise RuntimeError(
                "should be able to run the context on `start` and an empty State."
            ) from e
        return ctx


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
