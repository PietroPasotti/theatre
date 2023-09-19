# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from pathlib import Path

from PyQt5.QtWidgets import QFileDialog
from qtpy.QtWidgets import QPushButton
from scenario import Context

from theatre.charm_repo_tools import (
    CharmRepo,
)
from theatre.dialogs.file_backed_edit_dialog import FileBackedEditDialog
from theatre.helpers import show_error_dialog
from theatre.logger import logger


class CharmCtxLoaderDialog(FileBackedEditDialog):
    def __init__(self, parent=None):
        super().__init__(parent, "Select or create a context loader.")

        self._open_existing_button = existing = QPushButton("Select existing")
        existing.setToolTip("Select an existing loader.")
        self._button_box.addButton(existing, self._button_box.ActionRole)
        existing.clicked.connect(self._on_existing_loader_click)

        self._initialize_new = initialize_new = QPushButton("Initialize new")
        initialize_new.setToolTip("Select a charm repo to initialize.")
        self._button_box.addButton(initialize_new, self._button_box.ActionRole)
        initialize_new.clicked.connect(self._on_initialize_new_click)

    def _on_initialize_new_click(self):
        # let the user select a charm root.
        fname = QFileDialog.getExistingDirectory(
            self,
            "Select a charm repository root.",
        )
        try:
            path = Path(fname)
        except Exception as e:
            msg = f"bad path selected {fname}: {e}"
            logger.error(msg, exc_info=True)
            show_error_dialog(self, msg)
            return
        repo = CharmRepo(path)
        if not repo.is_valid:
            # not a charm root!
            msg = "not a valid charm root! cannot initialize"
            logger.error(msg)
            show_error_dialog(self, msg)
            return

        if repo.is_initialized:
            msg = (
                f"already initialized as theatre dir. If you want to reinitialize, "
                f"delete the {(path / '.theatre').absolute()} manually and retry"
            )
            logger.error(msg)
            show_error_dialog(self, msg)
            return

        repo.initialize()
        self._set_source(path)

    def _on_existing_loader_click(self):
        fname = QFileDialog.getExistingDirectory(
            self, "Select a charm root containing a .theatre directory", ""
        )
        path = Path(fname)
        repo = CharmRepo(path)

        if not repo.has_loader:
            msg = f"expected loader file not found at {repo.loader_path}"
            logger.error(msg)
            show_error_dialog(self, msg)
            return
        self._set_source(path)

    def get_output(self) -> Context:
        charm_root = self._source
        if not charm_root:
            raise RuntimeError("no source selected")

        repo = CharmRepo(charm_root)
        if not repo.has_loader():
            raise FileNotFoundError(repo.loader_path)

        return repo.load_context()
