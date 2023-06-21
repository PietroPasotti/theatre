from nodeeditor.utils import dumpException
from qtpy.QtCore import QSize, Qt, QByteArray, QDataStream, QMimeData, QIODevice, QPoint
from qtpy.QtGui import QDrag
from qtpy.QtWidgets import QListWidget, QAbstractItemView, QListWidgetItem

from theatre.helpers import get_icon
from theatre.trace_tree_widget.conf import STATES


class QDMDragListbox(QListWidget):
    _icon_size = 32

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        # init
        self.setIconSize(QSize(self._icon_size, self._icon_size))
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)

        self._add_state_templates()

    def _add_state_templates(self):
        keys = list(STATES.keys())
        keys.sort()
        for key in keys:
            state = STATES[key]
            self._add_state(key, state.icon)

    def _add_state(self, name, icon=None):
        item = QListWidgetItem(name, self)  # can be (icon, text, parent, <int>type)
        if icon:
            item.setIcon(icon)
        item.setSizeHint(QSize(32, 32))

        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)

        # setup data
        item.setData(Qt.UserRole, icon or get_icon("help"))
        item.setData(Qt.UserRole + 1, name)

    def startDrag(self, *args, **kwargs):
        try:
            item = self.currentItem()
            name = item.data(Qt.UserRole + 1)

            pixmap = item.data(Qt.UserRole).pixmap(self._icon_size, self._icon_size)

            itemData = QByteArray()
            dataStream = QDataStream(itemData, QIODevice.WriteOnly)
            dataStream << pixmap
            dataStream.writeQString(name)
            dataStream.writeQString(item.text())

            mimeData = QMimeData()
            mimeData.setData("application/x-item", itemData)

            drag = QDrag(self)
            drag.setMimeData(mimeData)
            drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
            drag.setPixmap(pixmap)

            drag.exec_(Qt.MoveAction)

        except Exception as e:
            dumpException(e)
