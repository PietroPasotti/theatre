from pathlib import Path

from qtpy.QtGui import QPalette, QColor, QIcon
from qtpy.QtWidgets import QWidget, QMessageBox


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
    path = Path(__file__).parent / 'icons' / name
    filename = path.with_suffix('.svg')
    if not filename.exists():
        raise ValueError(name)

    return QIcon(str(filename.absolute()))
