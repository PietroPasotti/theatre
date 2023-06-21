import typing

import ops
from qtpy.QtCore import QObject, Signal
from nodeeditor.node_scene import Scene as _Scene

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

    def getEdgeClass(self):
        return EventEdge
