# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import inspect
from dataclasses import dataclass
from pathlib import Path

from theatre.dialogs.file_backed_edit_dialog import TEMPLATES_DIR, FileBackedEditDialog
from theatre.helpers import load_module
from theatre.logger import logger

from theatre.trace_tree_widget.delta import Delta


DELTA_TEMPLATE = TEMPLATES_DIR / "delta_template.py"


@dataclass
class DeltaDialogOutput:
    deltas: ["Delta"]
    source: str


class EditDeltaDialog(FileBackedEditDialog):
    OFFER_LIBRARY_OPTION = False

    def __init__(self, parent=None, source: str | None = None):
        super().__init__(
            parent, title="Edit Deltas", template=source or DELTA_TEMPLATE.read_text()
        )

    def get_output(self) -> DeltaDialogOutput:
        source = Path(self._source)
        module = load_module(source)
        collected = []

        for name, value in inspect.getmembers(module):
            if not inspect.isfunction(value):
                logger.info(f"ignored {name}:{value} as it is not a function")
                continue

            if name.startswith("_"):
                logger.info(f"ignored {name}: private function")
                continue

            if inspect.getmodule(value).__name__ != source.name.split(".")[0]:
                logger.info(
                    f"ignored {name}:{value} as it is imported from an external module"
                )
                continue

            # todo check signature?
            collected.append(Delta(value, name))

        if not collected:
            logger.warning(f"no deltas collected from {self._source}")
        return DeltaDialogOutput(collected, source.read_text())
