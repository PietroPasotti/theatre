# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import typing
from dataclasses import asdict

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QPainter, QPainterPath
from PyQt5.QtWidgets import QGraphicsPixmapItem, QWidget
from nodeeditor.node_edge import Edge as _Edge, EDGE_TYPE_DIRECT, EDGE_TYPE_DEFAULT
from nodeeditor.node_edge_validators import (
    edge_validator_debug,
    edge_cannot_connect_two_outputs_or_two_inputs,
    edge_cannot_connect_input_and_output_of_same_node,
)
from nodeeditor.node_graphics_edge import QDMGraphicsEdge
from qtpy.QtWidgets import QLabel
from qtpy.QtGui import QIcon

from theatre.helpers import get_icon, get_color
from theatre.logger import logger
from theatre.scenario_json import parse_event
from theatre.trace_tree_widget.event_dialog import EventSpec

if typing.TYPE_CHECKING:
    from theatre.theatre_scene import TheatreScene
    from nodeeditor.node_socket import Socket
    from theatre.trace_tree_widget.state_node import StateNode


class GraphicsEdge(QDMGraphicsEdge):
    edge: "EventEdge"

    def __init__(self, edge: 'EventEdge', parent: QWidget = None):
        super().__init__(edge, parent)
        self._label_color = get_color('cyan1')

    def paint(self, painter: QPainter, QStyleOptionGraphicsItem, widget=None):
        super().paint(painter, QStyleOptionGraphicsItem, widget)
        try:
            spec = self.edge.event_spec
        except RuntimeError:
            return

        # sx, sy = self.posSource
        # dx, dy = self.posDestination
        # midpoint = QPointF(((sx+dx)/2), ((sy+dy)/2))

        path: QPainterPath = self.path()
        midpoint = path.pointAtPercent(.5)

        # align to center
        midpoint.setX(midpoint.x() - 16)
        midpoint.setY(midpoint.y() - 16)
        painter.setPen(self._label_color)
        painter.drawText(midpoint, spec.event.name)

        # painter.drawPixmap(midpoint, self.edge.icon.pixmap(32, 32))


class SpecUnsetError(RuntimeError):
    pass


class EventEdge(_Edge):
    """Edge representing an Event."""

    def __init__(
            self,
            scene: "TheatreScene",
            start_socket: "Socket" = None,
            end_socket: "Socket" = None,
            edge_type=EDGE_TYPE_DIRECT,
            event_spec: typing.Optional[EventSpec] = None,
    ):
        super().__init__(scene, start_socket, end_socket, edge_type)
        self._event_spec: typing.Optional[EventSpec] = None

        # todo: display label and anchor it to the edge
        # self.label = EventNameLabel(event_spec.event.name)
        self.icon = None
        self._update_icon()

        if event_spec:
            self.set_event_spec(event_spec)
        else:
            self._notify_end_node()

    def _update_icon(self):
        self.icon = self._get_icon()

    def createEdgeClassInstance(self):
        """
        Create instance of grEdge class
        :return: Instance of `grEdge` class representing the Graphics Edge in the grScene
        """
        self.grEdge = GraphicsEdge(self)
        self.scene.grScene.addItem(self.grEdge)
        if self.start_socket is not None:
            self.updatePositions()
        return self.grEdge

    def _notify_end_node(self):
        """notify end node, if present, that it has a new input"""
        end_socket = self.end_socket
        if end_socket:
            end_socket.node.onInputChanged(end_socket)

    def _get_icon(self) -> QIcon:
        if not self._event_spec:
            # edge being dragged
            return get_icon("pending")

        if self.end_socket and self.end_socket.node.value is None:
            # end node not evaluated yet
            return get_icon("flaky")

        if self.end_socket and self.end_socket.node.value.traceback:
            # end node evaluated and errored
            return get_icon("offline_bolt")

        # all good:
        return get_icon("arrow_circle_right")

    def __repr__(self):
        return f"<{self.start_node if self.start_socket else '?'} --> " \
               f"{self._event_spec} --> " \
               f"{self.end_node if self.end_socket else '?'}>"

    @property
    def start_node(self) -> "StateNode":
        if not self.start_socket:
            raise RuntimeError("no start node: is this edge still being dragged?")
        return typing.cast("StateNode", self.start_socket.node)

    @property
    def end_node(self) -> "StateNode":
        if not self.end_socket:
            raise RuntimeError("no end node: is this edge still being dragged?")
        return typing.cast("StateNode", self.end_socket.node)

    @property
    def event_spec(self) -> EventSpec:
        if not self._event_spec:
            raise SpecUnsetError(self)
        return self._event_spec

    def _get_color(self):
        event = self._event_spec.event
        if event.name == 'update-status':
            return get_color("update-status")
        if event._is_relation_event:
            return get_color("relation event")
        elif event._is_secret_event:
            return get_color("secret event")
        elif event._is_storage_event:
            return get_color("storage event")
        elif event._is_workload_event:
            return get_color("workload event")
        elif event.name.startswith("leader"):  # _is_leader_event...
            return get_color("leader event")
        elif event._is_builtin_event:
            return get_color("builtin event")
        else:
            return get_color("generic event")

    def set_event_spec(self, spec: EventSpec):
        self._event_spec = spec
        self.grEdge.changeColor(self._get_color())
        self._notify_end_node()
        self.grEdge.setToolTip(spec.event.name)
        self._update_icon()
        # self.grEdge.set_label(spec.event.name)

    def serialize(self):
        if not self.end_socket or not self.start_socket:
            raise RuntimeError(f'cannot serialize {self}! missing socket')
        if not self._event_spec:
            logger.warning('should not quite serialize: event edge '
                           'underspecified, missing event spec')

        out = super().serialize()
        out["event_spec"] = asdict(self._event_spec) if self._event_spec else None
        return out

    def deserialize(
            self, data: dict, hashmap: dict = {}, restore_id: bool = True, *args, **kwargs
    ) -> bool:
        evt_spec = data.get("event_spec", None)
        if evt_spec:
            # TODO: Relation Events and the like will need a reference to
            #  the Relation object which is stored in the parent state!
            event = parse_event(evt_spec['event'])
            self.set_event_spec(EventSpec(event, evt_spec['env']))
        return super().deserialize(data, hashmap, restore_id, *args, **kwargs)


EventEdge.registerEdgeValidator(edge_validator_debug)
EventEdge.registerEdgeValidator(edge_cannot_connect_two_outputs_or_two_inputs)
EventEdge.registerEdgeValidator(edge_cannot_connect_input_and_output_of_same_node)
