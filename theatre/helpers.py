# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import importlib
import sys
import types
import typing
from pathlib import Path

from PyQt5.QtGui import QImage
from qtpy.QtCore import QObject
from qtpy.QtGui import QPainter, QPixmap
from qtpy.QtGui import QPalette, QColor, QIcon
from qtpy.QtSvg import QSvgRenderer
from qtpy.QtWidgets import QWidget, QMessageBox

from theatre.config import RESOURCES_DIR
from theatre.logger import logger
from theatre.resources.x11_colors import X11_COLORS

ColorType = typing.Union[str, typing.Tuple[int, int, int]]
DEFAULT_ICON_PIXMAP_RESOLUTION = 100
CUSTOM_COLORS = {
    # state node icon
    "pastel green": (138, 255, 153),
    "pastel orange": (255, 185, 64),
    "pastel red": (245, 96, 86),

    # event edge colors
    "relation event": "#D474AF",
    "secret event": "#A9FAC8",
    "storage event": "#EABE8C",
    "workload event": "#87F6D3",
    "builtin event": "#96A1F6",
    "leader event": "#C6D474",
    "generic event": "#D6CA51",
    "update-status": "#4a708b",  # x11's skyblue4
}


def get_color(color: ColorType):
    if isinstance(color, QColor):
        return color
    elif isinstance(color, tuple):
        return QColor(*color)
    elif isinstance(color, str):
        for db in (CUSTOM_COLORS, X11_COLORS):
            if mapped_color := db.get(color, None):
                return QColor(mapped_color) if isinstance(mapped_color, str) else QColor(*mapped_color)
    raise RuntimeError(f'invalid input: unable to map {color} to QColor.')


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


def colorized(name: str, color: QColor, res: int = 500):
    path = RESOURCES_DIR / "icons" / name
    filename = path.with_suffix(".svg")
    renderer = QSvgRenderer(str(filename.absolute()))
    orig_svg = QImage(res, res, QImage.Format_ARGB32)
    painter = QPainter(orig_svg)

    renderer.render(painter)
    img_copy = orig_svg.copy()
    painter.end()

    painter.begin(img_copy)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(img_copy.rect(), color)
    painter.end()
    pxmp = QPixmap.fromImage(img_copy)
    return QIcon(pxmp)


def get_icon(name: str, color: ColorType | None = None) -> QIcon:
    if color:
        return colorized(name, get_color(color))

    path = RESOURCES_DIR / "icons" / name
    filename = path.with_suffix(".svg")
    if not filename.exists():
        raise ValueError(name)

    abspath_str = str(filename.absolute())
    return QIcon(abspath_str)


def toggle_visible(obj: QObject):
    obj.setVisible(not obj.isVisible())


def load_module(path: Path) -> types.ModuleType:
    """Import the file at path as a python module."""

    # so we can import without tricks
    sys.path.append(str(path.parent))
    # strip .py
    module_name = str(path.with_suffix("").name)

    # if a previous call to load_module has loaded a
    # module with the same name, this will conflict.
    # besides, we don't really want this to be importable from anywhere else.
    if module_name in sys.modules:
        del sys.modules[module_name]

    try:
        module = importlib.import_module(module_name)
    except ImportError:
        logger.error(f"cannot import {path} as a python module")
        raise
    finally:
        # cleanup
        sys.path.remove(str(path.parent))

    return module
