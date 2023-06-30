# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import typing

from qtpy.QtCore import QRectF, Qt
from qtpy.QtGui import QBrush, QFont, QPainter, QPainterPath
from qtpy.QtWidgets import QGraphicsTextItem
from nodeeditor.node_graphics_node import QDMGraphicsNode
from nodeeditor.node_graphics_socket import QDMGraphicsSocket
from nodeeditor.node_socket import Socket as _Socket

from theatre.helpers import get_icon, get_color

if typing.TYPE_CHECKING:
    from theatre.trace_tree_widget.state_node import StateNode


class StateGraphicsNode(QDMGraphicsNode):
    node: "StateNode"

    def initSizes(self):
        super().initSizes()
        self.width = 160
        self.height = 84
        self.edge_roundness = 6
        self.edge_padding = 0
        self.title_horizontal_padding = 8
        self.title_vertical_padding = 10
        self.title_height = 24
        self.deltabox_height = 24
        self.deltabox_vertical_padding = 5

    def initAssets(self):
        super().initAssets()
        # FIXME: colors don't quite work as intended here, somehow...?
        self._icon_ok = get_icon("stars")
        self._icon_dirty = get_icon("flaky")
        self._icon_invalid = get_icon("error")
        self._color_ok = get_color("pastel green")
        self._color_dirty = get_color("pastel orange")
        self._color_invalid = get_color("pastel red")
        self._brush_delta = QBrush(get_color("lavender"))
        self._delta_label_color = get_color("black")
        self._delta_label_font = QFont("Ubuntu", 9)

    def boundingRect(self) -> QRectF:
        """Defining Qt' bounding rectangle"""
        n_deltas = len(self.node.deltas)
        return QRectF(
            0,
            0,
            self.width,
            self.height + self.deltabox_height * n_deltas + self.deltabox_vertical_padding * n_deltas
        ).normalized()

    def initUI(self):
        super().initUI()
        self.init_delta_labels()

    def _delta_topleft_corners(self):
        dbox_vpadding = self.deltabox_vertical_padding
        h = self.height
        dbox_h = self.deltabox_height

        for i, delta in enumerate(self.node.deltas):
            topleft_y = h + ((dbox_h + dbox_vpadding) * i) + dbox_vpadding
            yield topleft_y

    def init_delta_labels(self):
        self.delta_gr_items = delta_gr_items = []
        for y, delta in zip(self._delta_topleft_corners(), self.node.deltas):
            gritem = QGraphicsTextItem(self)
            gritem.node = self.node
            gritem.setPlainText(delta.name)
            gritem.setDefaultTextColor(self._delta_label_color)
            gritem.setFont(self._delta_label_font)
            gritem.setPos(self.title_horizontal_padding, y)
            gritem.setTextWidth(
                self.width
                - 2 * self.title_horizontal_padding
            )
            delta_gr_items.append(gritem)

    def paint(self, painter: QPainter, QStyleOptionGraphicsItem, widget=None):
        super().paint(painter, QStyleOptionGraphicsItem, widget)

        if self.node.isInvalid():
            icon = self._icon_invalid
            color = self._color_invalid
        elif self.node.isDirty():
            icon = self._icon_dirty
            color = self._color_dirty
        else:
            icon = self._icon_ok
            color = self._color_ok

        rect = QRectF(160 - 24, 0, 24.0, 24.0)
        painter.setPen(color)
        painter.drawEllipse(rect)
        pxmp = icon.pixmap(34, 34)
        painter.drawImage(rect, pxmp.toImage())

        dbox_h = self.deltabox_height

        for y, delta in zip(self._delta_topleft_corners(), self.node.deltas):
            # draw a box for the deltas
            path_title = QPainterPath()
            path_title.setFillRule(Qt.WindingFill)

            path_title.addRoundedRect(0, y, self.width, dbox_h, self.edge_roundness, self.edge_roundness)
            painter.setPen(Qt.NoPen)
            painter.setBrush(self._brush_delta)
            painter.drawPath(path_title.simplified())

            path_outline = QPainterPath()
            path_outline.addRoundedRect(0, y, self.width, dbox_h, self.edge_roundness, self.edge_roundness)
            painter.setBrush(Qt.NoBrush)
            if self.hovered:
                painter.setPen(self._pen_hovered)
                painter.drawPath(path_outline.simplified())
                painter.setPen(self._pen_default)
                painter.drawPath(path_outline.simplified())
            else:
                painter.setPen(self._pen_default if not self.isSelected() else self._pen_selected)
                painter.drawPath(path_outline.simplified())

    def hoverEnterEvent(self, event) -> None:
        super().hoverEnterEvent(event)
        self.setCursor(Qt.OpenHandCursor)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self.setCursor(Qt.ClosedHandCursor)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        # assuming we're still hovering it:
        if self.hovered:
            self.setCursor(Qt.OpenHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def hoverLeaveEvent(self, event) -> None:
        super().hoverLeaveEvent(event)
        self.setCursor(Qt.ArrowCursor)


class GraphicsSocket(QDMGraphicsSocket):
    def __init__(self, socket: "Socket"):
        super().__init__(socket)
        self.radius = 6
        self.outline_width = 1


class Socket(_Socket):
    Socket_GR_Class = GraphicsSocket
