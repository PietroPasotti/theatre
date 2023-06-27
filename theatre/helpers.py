# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import typing

from qtpy.QtCore import QObject
from qtpy.QtCore import Qt
from qtpy.QtGui import QPainter, QPixmap
from qtpy.QtGui import QPalette, QColor, QIcon
from qtpy.QtSvg import QSvgRenderer
from qtpy.QtWidgets import QWidget, QMessageBox

from theatre.config import RESOURCES_DIR

ColorType = typing.Union[str, typing.Tuple[int, int, int]]
DEFAULT_ICON_PIXMAP_RESOLUTION = 100

CUSTOM_COLORS = {
    "pastel red": (245, 96, 86),
    # event edge colors
    "relation event": "#D474AF",
    "secret event": "#A9FAC8",
    "storage event": "#EABE8C",
    "workload event": "#87F6D3",
    "builtin event": "#96A1F6",
    "leader event": "#C6D474",
    "generic event": "#D6CA51",
}


def get_color(color: ColorType):
    if isinstance(color, tuple):
        mapped_color = color
    else:
        mapped_color = CUSTOM_COLORS.get(color, color)
    return (
        QColor(*mapped_color)
        if isinstance(mapped_color, tuple)
        else QColor(mapped_color)
    )


class Color(QWidget):
    def __init__(self, color):
        super(Color, self).__init__()
        self.setAutoFillBackground(True)

        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(color))
        self.setPalette(palette)


def show_error_dialog(
        parent, message: str, title="Whoopsiedaisies!", choices=QMessageBox.Ok
):
    return QMessageBox.critical(parent, title, message, choices)


def colorized_pixmap(
        svg_filename: str, color: QColor, res: int = DEFAULT_ICON_PIXMAP_RESOLUTION
) -> QPixmap:
    renderer = QSvgRenderer(svg_filename)
    pixmap = QPixmap(res, res)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)  # this is the destination, and only its alpha is used!
    painter.setCompositionMode(painter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), color)
    painter.end()
    return pixmap


def get_icon(name: str, color: str = None) -> QIcon:
    path = RESOURCES_DIR / "icons" / name
    filename = path.with_suffix(".svg")
    if not filename.exists():
        raise ValueError(name)

    abspath_str = str(filename.absolute())

    if color:
        pixmap = colorized_pixmap(svg_filename=abspath_str, color=get_color(color))
        return QIcon(pixmap)

    return QIcon(abspath_str)


def toggle_visible(obj: QObject):
    obj.setVisible(not obj.isVisible())
