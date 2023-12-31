# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import typing
from enum import Enum

from scenario import State

from theatre.dialogs.file_backed_edit_dialog import TEMPLATES_DIR, FileBackedEditDialog
from theatre.helpers import load_module
from theatre.logger import logger

if typing.TYPE_CHECKING:
    from theatre.trace_tree_widget.state_node import StateNode

NEW_STATE_TEMPLATE = TEMPLATES_DIR / "new_state_template.py"
EDIT_STATE_TEMPLATE = TEMPLATES_DIR / "edit_state_template.py"
DEFAULT_TEMPLATE = NEW_STATE_TEMPLATE


class Mode(Enum):
    new = "new"
    edit = "edit"


class NewStateDialog(FileBackedEditDialog):
    OFFER_LIBRARY_OPTION = True

    def __init__(self, parent=None, mode: Mode = Mode.new, base: "StateNode" = None):
        logger.info(f"opening state dialog in mode {mode}")
        if mode is Mode.new:
            title = "New Root State."
            template_text = NEW_STATE_TEMPLATE.read_text()
        else:
            if not base:
                raise ValueError(
                    f"'base' is required when using {type(self)} in mode {mode}"
                )
            title = f"Edit {base}."
            state_repr = repr(base.value.state)
            # fixme: scenario's repr is broken on UnknownStatus.
            #  cfr: https://github.com/canonical/ops-scenario/issues/42
            state_repr = state_repr.replace("UnknownStatus('')", "UnknownStatus()")

            # todo: format with black
            template_text = EDIT_STATE_TEMPLATE.read_text().format(state_repr)

        super().__init__(parent, title, template_text)

    def get_output(self) -> State:
        module = load_module(self._source)
        state = getattr(module, "STATE")
        if not isinstance(state, State):
            raise TypeError(type(state))
        return state
