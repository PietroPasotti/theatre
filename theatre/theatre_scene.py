# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import json
import os
import typing

import ops
from nodeeditor.node_scene import Scene as _Scene, InvalidFile
from nodeeditor.node_scene_clipboard import SceneClipboard as _SceneClipboard
from qtpy.QtCore import QObject
from qtpy.QtCore import QPoint
from qtpy.QtCore import Signal
from qtpy.QtGui import QDragMoveEvent
from qtpy.QtWidgets import QGraphicsItem
from qtpy.QtWidgets import QGraphicsProxyWidget

from theatre.logger import logger
from theatre.trace_tree_widget.event_edge import EventEdge
from theatre.trace_tree_widget.library_widget import (
    STATE_SPEC_MIMETYPE,
    SUBTREE_SPEC_MIMETYPE,
)
from theatre.trace_tree_widget.state_node import (
    StateNode,
    GraphicsSocket,
    StateContent,
)
if typing.TYPE_CHECKING:
    from scenario.state import _CharmSpec

SerializedScene = dict  # TODO

class SceneClipboard(_SceneClipboard):
    def deserializeFromClipboard(self, data: SerializedScene, *args, **kwargs):
        """
        Deserializes data from Clipboard.

        :param data: ``dict`` data for deserialization to the :class:`nodeeditor.node_scene.Scene`.
        :type data: ``dict``
        """

        hashmap = {}

        # calculate mouse pointer - scene position
        view = self.scene.getView()
        mouse_scene_pos = view.last_scene_mouse_position

        # calculate selected objects bbox and center
        minx, maxx, miny, maxy = 10000000, -10000000, 10000000, -10000000
        for node_data in data["nodes"]:
            x, y = node_data["pos_x"], node_data["pos_y"]
            if x < minx:
                minx = x
            if x > maxx:
                maxx = x
            if y < miny:
                miny = y
            if y > maxy:
                maxy = y

        # add width and height of a node
        maxx -= 180
        maxy += 100

        # calculate the offset of the newly creating nodes
        mousex, mousey = mouse_scene_pos.x(), mouse_scene_pos.y()

        # create each node
        created_nodes = []

        self.scene.setSilentSelectionEvents()

        self.scene.doDeselectItems()

        for node_data in data["nodes"]:
            new_node = StateNode(self.scene)
            new_node.deserialize(node_data, hashmap, restore_id=False, *args, **kwargs)
            created_nodes.append(new_node)

            # readjust the new nodeeditor's position

            # new node's current position
            posx, posy = new_node.pos.x(), new_node.pos.y()
            newx, newy = mousex + posx - minx, mousey + posy - miny

            new_node.setPos(newx, newy)

            new_node.doSelect()

        if "edges" in data:
            for edge_data in data["edges"]:
                new_edge = EventEdge(self.scene)
                new_edge.deserialize(
                    edge_data, hashmap, restore_id=False, *args, **kwargs
                )

        self.scene.setSilentSelectionEvents(False)

        # store history
        self.scene.history.storeHistory("Pasted elements in scene", setModified=True)

        return created_nodes


class TheatreScene(QObject, _Scene):
    """TheatreScene class."""

    state_node_changed = Signal(StateNode)
    state_node_clicked = Signal(StateNode)

    def __init__(self):
        super().__init__()
        # FIXME: Dynamically set by MainWindow
        self._charm_spec: "_CharmSpec" | None = None
        self.clipboard = SceneClipboard(self)

    def set_charm_spec(self, spec: "_CharmSpec"):
        self._charm_spec = spec

    @property
    def charm_spec(self):
        return self._charm_spec

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

    def deserialize(self, data: dict, hashmap: dict = {},
                    restore_id: bool = True, *args, **kwargs) -> bool:
        hashmap = {}

        if restore_id: self.id = data['id']

        # -- deserialize NODES

        # Instead of recreating all the nodes, reuse existing ones...
        # get list of all current nodes:
        all_nodes = self.nodes.copy()

        # go through deserialized nodes:
        for node_data in data['nodes']:
            # can we find this node in the scene?
            found: StateNode | typing.Literal[False] = False
            for node in all_nodes:
                if node.id == node_data['id']:
                    found = node
                    break

            if not found:
                try:
                    new_node = StateNode(self)
                    new_node.deserialize(node_data, hashmap, restore_id, *args, **kwargs)
                    new_node.onDeserialized(node_data)
                except Exception as e:
                    logger.error(e, exc_info=True)
            else:
                try:
                    found.deserialize(node_data, hashmap, restore_id, *args, **kwargs)
                    found.onDeserialized(node_data)
                    all_nodes.remove(found)
                    # print("Reused", node_data['title'])
                except Exception as e:
                    logger.error(e, exc_info=True)

        while all_nodes != []:
            node = all_nodes.pop()
            node.remove()

        # Instead of recreating all the edges, reuse existing ones...
        # get list of all current edges:
        all_edges = self.edges.copy()

        # go through deserialized edges:
        for edge_data in data['edges']:
            # can we find this node in the scene?
            found: EventEdge | typing.Literal[False] = False
            for edge in all_edges:
                if edge.id == edge_data['id']:
                    found = edge
                    break

            if not found:
                new_edge = EventEdge(self)
                new_edge.deserialize(edge_data, hashmap, restore_id, *args, **kwargs)
            else:
                found.deserialize(edge_data, hashmap, restore_id, *args, **kwargs)
                all_edges.remove(found)

        # remove nodes which are left in the scene and were NOT in the serialized data!
        # that means they were not in the graph before...
        while all_edges != []:
            edge = all_edges.pop()
            edge.remove()

        return True

    def get_node_at(self, pos: QPoint) -> StateNode | None:
        nearest = self.find_nearest_parent_at(pos, (GraphicsSocket, StateContent))
        if nearest is None:
            return None
        if isinstance(nearest, GraphicsSocket):
            return nearest.socket.node
        elif isinstance(nearest, StateContent):
            return nearest.node
        else:
            raise TypeError(nearest)

    def find_nearest_parent_at(self, pos: QPoint,
                                types: typing.Tuple[type, ...]
                                ) -> QGraphicsItem | None:
        """Climb up the widget hierarchy until we find a parent of one of the desired types."""
        item = self.getItemAt(pos)

        if not item:
            return None

        if type(item) == QGraphicsProxyWidget:
            item = item.widget()

        while item:
            if isinstance(item, types):
                return item

            # happens on edges
            if not hasattr(item, "parent"):
                logger.warn(f'encountered unexpected item type while climbing up parents: {item}')
                return None

            item = item.parent()
        return item
