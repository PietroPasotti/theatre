# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import json
import os
import typing

import ops
from qtpy.QtCore import QObject, Signal
from nodeeditor.node_scene import Scene as _Scene, InvalidFile

from logger import logger
from theatre.trace_tree_widget.event_edge import EventEdge
from theatre.trace_tree_widget.state_node import StateNode


class TheatreScene(QObject, _Scene):
    """TheatreScene class."""

    state_node_changed = Signal(StateNode)
    state_node_clicked = Signal(StateNode)

    def __init__(self):
        super().__init__()
        # FIXME: Dynamically set by MainWindow
        self.charm_type: typing.Optional[typing.Type[ops.CharmBase]] = None

    def loadFromFile(self, filename: str):
        with open(filename, "r") as file:
            raw_data = file.read()
            try:
                data = json.loads(raw_data)
                self.filename = filename
                self.deserialize(data)
                self.has_been_modified = False
            except json.JSONDecodeError:
                raise InvalidFile(f"{os.path.basename(filename)} is not a valid JSON file")
            except Exception as e:
                logger.error(e, exc_info=True)


    def getEdgeClass(self):
        return EventEdge
