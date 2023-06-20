import typing
from dataclasses import asdict

from PyQt5.QtWidgets import QLabel
from nodeeditor.node_edge import Edge as _Edge, EDGE_TYPE_DIRECT
from nodeeditor.node_edge_validators import (
    edge_validator_debug,
    edge_cannot_connect_two_outputs_or_two_inputs,
    edge_cannot_connect_input_and_output_of_same_node,
)

from ui.trace_tree_widget.event_dialog import EventSpec

if typing.TYPE_CHECKING:
    from ui.main_window import Scene
    from nodeeditor.node_socket import Socket


class EventEdge(_Edge):
    """Edge representing an Event."""

    def __init__(
            self, scene: 'Scene', start_socket: 'Socket' = None, end_socket: 'Socket' = None,
            edge_type=EDGE_TYPE_DIRECT, event_spec: EventSpec = None, *, label: "EventNameLabel"):
        super().__init__(scene, start_socket, end_socket, edge_type)
        self._event_spec = event_spec

        # todo: display label and anchor it to the edge
        self.label = label

    def set_event_spec(self, spec: EventSpec):
        self._event_spec = spec
        self.grEdge.set_label(spec.event.name)

    def serialize(self):
        out = super().serialize()
        out['event_spec'] = asdict(self._event_spec) if self._event_spec else None
        return out

    def deserialize(self, data: dict, hashmap: dict = {}, restore_id: bool = True, *args, **kwargs) -> bool:
        evt_spec = data.pop('event_spec')
        if evt_spec:
            self.set_event_spec(EventSpec(evt_spec))
        return super().deserialize(data, hashmap, restore_id, *args, **kwargs)


class EventNameLabel(QLabel):
    pass


EventEdge.registerEdgeValidator(edge_validator_debug)
EventEdge.registerEdgeValidator(edge_cannot_connect_two_outputs_or_two_inputs)
EventEdge.registerEdgeValidator(edge_cannot_connect_input_and_output_of_same_node)
