import typing
from dataclasses import asdict

from nodeeditor.node_edge import Edge as _Edge, EDGE_TYPE_DIRECT
from nodeeditor.node_edge_validators import (
    edge_validator_debug,
    edge_cannot_connect_two_outputs_or_two_inputs,
    edge_cannot_connect_input_and_output_of_same_node,
)
from qtpy.QtWidgets import QLabel
from qtpy.QtGui import QIcon

from theatre.helpers import get_icon
from theatre.trace_tree_widget.event_dialog import EventSpec

if typing.TYPE_CHECKING:
    from theatre.theatre_scene import TheatreScene
    from nodeeditor.node_socket import Socket
    from theatre.trace_tree_widget.state_node import StateNode


class EventNameLabel(QLabel):
    """Label representing an event's name."""


class EventEdge(_Edge):
    """Edge representing an Event."""

    def __init__(
        self,
        scene: "TheatreScene",
        start_socket: "Socket" = None,
        end_socket: "Socket" = None,
        edge_type=EDGE_TYPE_DIRECT,
        event_spec: EventSpec = None,
    ):
        super().__init__(scene, start_socket, end_socket, edge_type)
        self._event_spec = event_spec

        # todo: display label and anchor it to the edge
        # self.label = EventNameLabel(event_spec.event.name)
        self.icon = self._get_icon()

    def _get_icon(self) -> QIcon:
        # todo: custom icons per event type
        return get_icon("arrow_circle_right")

    def __repr__(self):
        return f"<{self.start_node} --> {self._event_spec} --> {self.end_node}>"

    @property
    def start_node(self) -> "StateNode":
        return typing.cast("StateNode", self.start_socket.node)

    @property
    def end_node(self) -> "StateNode":
        return typing.cast("StateNode", self.end_socket.node)

    @property
    def event_spec(self) -> EventSpec:
        if not self._event_spec:
            raise RuntimeError(f"event spec unset on {self}")
        return self._event_spec

    def set_event_spec(self, spec: EventSpec):
        self._event_spec = spec
        # self.grEdge.set_label(spec.event.name)

    def serialize(self):
        out = super().serialize()
        out["event_spec"] = asdict(self._event_spec) if self._event_spec else None
        return out

    def deserialize(
        self, data: dict, hashmap: dict = {}, restore_id: bool = True, *args, **kwargs
    ) -> bool:
        evt_spec = data.pop("event_spec")
        if evt_spec:
            self.set_event_spec(EventSpec(evt_spec))
        return super().deserialize(data, hashmap, restore_id, *args, **kwargs)


EventEdge.registerEdgeValidator(edge_validator_debug)
EventEdge.registerEdgeValidator(edge_cannot_connect_two_outputs_or_two_inputs)
EventEdge.registerEdgeValidator(edge_cannot_connect_input_and_output_of_same_node)
