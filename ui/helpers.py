import typing
from pathlib import Path

from qtpy.QtGui import QPalette, QColor, QIcon
from qtpy.QtWidgets import QWidget, QMessageBox


CUSTOM_COLORS = {
    'pastel_red': (245, 96, 86)
}

def get_color(color_str_or_tuple: typing.Union[str, typing.Tuple[int,int,int]]):
    if isinstance(color_str_or_tuple, tuple):
        color_tuple = color_str_or_tuple
    else:
        color_tuple = CUSTOM_COLORS.get(color_str_or_tuple)
    return QColor(*color_tuple)


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


def get_icon(name: str):
    path = Path(__file__).parent / "icons" / name
    filename = path.with_suffix(".svg")
    if not filename.exists():
        raise ValueError(name)

    return QIcon(str(filename.absolute()))
