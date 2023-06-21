import dataclasses
import typing

import scenario
import yaml
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTabWidget, QTextEdit
from qtpy.QtCore import Signal, QItemSelection
from qtpy.QtGui import QBrush
from qtpy.QtGui import QStandardItemModel, QStandardItem
from qtpy.QtWidgets import QListView
from qtpy.QtWidgets import QSplitter
from qtpy.QtWidgets import QTreeView

from theatre.helpers import show_error_dialog, get_icon, get_color
from theatre.trace_tree_widget.state_node import StateNode, StateNodeOutput

if typing.TYPE_CHECKING:
    from theatre.trace_tree_widget.event_edge import EventEdge

_Trace = typing.List[StateNode]


def get_trace(state: StateNode) -> _Trace:
    trace = [state]
    while state := state.get_previous():
        trace.insert(0, state)
    return trace


class TraceView(QListView):
    selection_changed = Signal(StateNode)
    _invalid_state_color = 'pastel_red'

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self._trace: _Trace = None
        self._state_node: StateNode = None
        self.setModel(QStandardItemModel())
        self.setSelectionMode(self.SingleSelection)

    def display(self, state: StateNode, trace: _Trace):
        self._state_node = state
        self._trace = trace
        self._display()
        self.setCurrentIndex(self.model().index(-1, 0))

    def selectionChanged(self, selected: QItemSelection, deselected):
        super().selectionChanged(selected, deselected)
        if selected.count() > 0:
            idx = selected.indexes()[0]  # should be only one
            item = self.model().itemFromIndex(idx)
            state = item.data(Qt.ItemDataRole.UserRole + 1)
            self.selection_changed.emit(state)

    def _as_state_item(self, state_node: StateNode) -> QStandardItem:
        text = f"{state_node.title} ({state_node.description})"
        item = QStandardItem(state_node.icon, text)
        if state_node.isInvalid():
            brush = QBrush(get_color(self._invalid_state_color))
            brush.setStyle(Qt.BrushStyle.SolidPattern)
            item.setBackground(brush)
        item.setData(state_node)
        return item

    def _as_event_item(self, event: "EventEdge") -> QStandardItem:
        item = QStandardItem(event.icon, event.event_spec.event.name)
        item.setData(event, Qt.ItemDataRole.UserRole + 1)
        item.setEnabled(False)
        model: QStandardItemModel = self.model()
        return item

    def _display(self):
        trace = self._trace
        model = self.model()
        model.clear()
        root = trace[0]
        model.appendRow(self._as_state_item(root))

        for state in trace[1:]:
            model.appendRow(self._as_event_item(state.edge_in))
            model.appendRow(self._as_state_item(state))


class TextView(QTextEdit):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._state_node = None
        self.setReadOnly(True)

    def display(self, state_node: StateNode):
        self._state_node = state_node
        self.update_contents()

    def generate_contents(self) -> str:
        raise NotImplementedError("abstract method")

    def update_contents(self):
        self.setText(self.generate_contents())

    @property
    def node_output(self) -> StateNodeOutput:
        if self._state_node is None:
            raise RuntimeError('state node is unset')
        out = self._state_node.eval()
        return out


class LogsView(TextView):
    def generate_contents(self):
        return self.node_output.logs


class RawStateView(TextView):
    def generate_contents(self):
        return yaml.safe_dump(dataclasses.asdict(self.node_output.state))


class StateView(QTreeView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._state_node = None
        self.setModel(QStandardItemModel())

    def display(self, state_node: StateNode):
        self._state_node = state_node
        self.update_contents()

    def update_contents(self):
        state_node: StateNode = self._state_node
        model: QStandardItemModel = self.model()
        model.clear()

        if not state_node.value.state:
            # state still unavailable: this means the computation has failed.
            # TODO: find some way to show the traceback
            status_item = QStandardItem(get_icon('error'), "evaluation failed")
            model.appendRow(status_item)
            return

        # status
        state: scenario.State = state_node.value.state
        status_name_to_icon = {
            'active': "stars",
            'blocked': "error",
        }
        unit_status = state.status.unit
        status_icon = status_name_to_icon.get(unit_status.name, "warning")
        status_text = f"{unit_status.name}: {unit_status.message}"
        status_item = QStandardItem(get_icon(status_icon), status_text)

        model.appendRow(status_item)

    def _on_fire_event(self, _=None):
        if not self._state_node:
            show_error_dialog(self, "no current statenode selected")
            return

        # todo: event emission dialog


class NodeView(QTabWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._displayed: typing.Optional[StateNode] = None

        self.state_view = sw = StateView(self)
        self.logs_view = tv = LogsView(self)
        self.raw_state_view = rsv = RawStateView(self)
        self.addTab(sw, 'state')
        self.addTab(tv, 'logs')
        self.addTab(rsv, 'raw')

    def is_displayed(self, state_node: StateNode):
        return self._displayed is state_node

    def update_contents(self):
        """Update contents of all tabs"""
        self.state_view.update_contents()
        self.logs_view.update_contents()
        self.raw_state_view.update_contents()

    def display(self, state_node: StateNode):
        self._displayed = state_node

        self.state_view.display(state_node)
        self.logs_view.display(state_node)
        self.raw_state_view.display(state_node)


class TraceInspectorWidget(QSplitter):
    def __init__(self, parent) -> None:
        super().__init__(parent)

        self.trace_view = trace_view = TraceView(self)
        self.node_view = node_view = NodeView(self)
        self.trace_view.selection_changed.connect(node_view.display)

        self.addWidget(trace_view)
        self.addWidget(node_view)
        self.setSizes([20, 80])

    def display(self, state_node: StateNode):
        trace = get_trace(state_node)
        self._evaluate_all(trace)
        self.trace_view.display(state_node, trace)
        self.node_view.display(state_node)

    def _evaluate_all(self, trace: _Trace):
        """Greedily evaluate all nodes in the trace."""
        for node in trace:
            if not node.eval():
                # interrupt when and if a node fails to evaluate
                break

    def on_node_changed(self, state_node: StateNode):
        """Slot for when a StateNode has changed.

        If we're presently displaying it, we may need to update it in the views.
        """
        if self.node_view.is_displayed(state_node):
            self.node_view.update_contents()
