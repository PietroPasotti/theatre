# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import inspect
import typing
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Iterable, Callable

from theatre.dialogs.file_backed_edit_dialog import TEMPLATES_DIR, FileBackedEditDialog
from theatre.helpers import load_module
from theatre.logger import logger

from theatre.trace_tree_widget.delta import Delta

if typing.TYPE_CHECKING:
    from scenario import State

DELTA_TEMPLATE = TEMPLATES_DIR / "delta_template.py"


@dataclass
class DeltaDialogOutput:
    deltas: ["Delta"]
    source: str


_NOT_GIVEN = object()


def _filter_deltas(
    ns: Iterable[Tuple[str, Callable[["State"], "State"]]],
    check_module: Optional[str] = _NOT_GIVEN,
):
    collected = []

    for name, value in ns:
        if not inspect.isfunction(value):
            logger.info(f"ignored {name}:{value} as it is not a function")
            continue

        if name.startswith("_"):
            logger.info(f"ignored {name}: private function")
            continue

        if (
            check_module is not _NOT_GIVEN
            and getattr(inspect.getmodule(value), "__name__", None) != check_module
        ):
            logger.info(
                f"ignored {name}:{value} as it is imported from an external module"
            )
            continue

        # todo check signature?
        collected.append(Delta(value, name))
    return collected


def get_deltas_from_source_code(source: str):
    """Loads deltas from a string containing python code."""
    glob = {}
    exec(source, glob)
    # inspect.getmodule from string sources will give None.
    return _filter_deltas(glob.items(), None)


def get_deltas_from_source_path(source: Path) -> List[Delta]:
    """Loads the Deltas from a python file."""
    module = load_module(source)
    return _filter_deltas(inspect.getmembers(module), source.name.split(".")[0])


class EditDeltaDialog(FileBackedEditDialog):
    OFFER_LIBRARY_OPTION = False

    def __init__(self, parent=None, source: str | None = None):
        super().__init__(
            parent, title="Edit Deltas", template=source or DELTA_TEMPLATE.read_text()
        )

    def get_output(self) -> DeltaDialogOutput:
        source = self._source
        collected = get_deltas_from_source_path(source)
        if not collected:
            logger.warning(f"no deltas collected from {source}")
        return DeltaDialogOutput(collected, source.read_text())
