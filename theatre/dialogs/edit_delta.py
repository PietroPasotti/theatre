# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import inspect
import typing
from pathlib import Path

from theatre.dialogs.file_backed_edit_dialog import FileBackedEditDialog, TEMPLATES_DIR
from theatre.helpers import load_module
from theatre.logger import logger

DELTA_TEMPLATE = TEMPLATES_DIR / "delta_template.py"

if typing.TYPE_CHECKING:
    from theatre.trace_tree_widget.delta import Delta


class EditDeltaDialog(FileBackedEditDialog):
    OFFER_LIBRARY_OPTION = True

    def __init__(self, parent=None):
        super().__init__(parent, title="Edit Deltas", from_tempfile=DELTA_TEMPLATE.read_text())

    def get_output(self) -> typing.List["Delta"]:
        module = load_module(Path(self._source.name))
        collected = []

        for obj in inspect.getmembers(module):
            if not inspect.isfunction(obj):
                logger.info(f"ignored {obj} as it is not a function")
                continue

            # todo check signature?
            collected.append(Delta(obj, obj.__name__))

        if not collected:
            logger.warning(f"no deltas collected from {self._source}")
        return collected
