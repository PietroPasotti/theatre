from PySide2.QtCore import Signal
from PySide2.QtWidgets import QWidget, QSplitter, QVBoxLayout, QHBoxLayout, QPushButton
from scenario import State

from ui.helpers import Color, show_error_dialog


class TraceView(QWidget):
    def __init__(self, parent) -> None:
        super().__init__(parent)


class StateViewBottomBar(QWidget):
    event_fired = Signal()

    def __init__(self, parent) -> None:
        super().__init__(parent)
        bottom_bar_layout = QHBoxLayout(self)
        fire_event_button = QPushButton("&Fire event", self)
        fire_event_button.clicked.connect(self.event_fired)
        bottom_bar_layout.addWidget(fire_event_button)
        self.setLayout(bottom_bar_layout)
        self.setFixedHeight(50)


class StateView(QWidget):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self._state = None

        layout = QVBoxLayout(self)
        self.state_tree = state_tree = Color("blue")
        self.bottom_bar = bottom_bar = StateViewBottomBar(self)
        layout.addWidget(state_tree)
        layout.addWidget(bottom_bar)
        self.setLayout(layout)
        self.bottom_bar.event_fired.connect(self._on_fire_event)

    def display(self, state: State):
        self._state = state
        # todo: parse State and display in treeview

    def _on_fire_event(self, _=None):
        if not self._state:
            show_error_dialog(self, "no current state selected")
            return

        # todo: event emission dialog


class TraceInspectorWidget(QSplitter):
    def __init__(self, parent) -> None:
        super().__init__(parent)

        self.trace_view = trace_view = TraceView(self)
        self.state_view = state_view = StateView(self)

        self.addWidget(trace_view)
        self.addWidget(state_view)
        self.setSizes([20, 80])
