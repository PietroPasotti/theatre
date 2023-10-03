# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import dataclasses
import typing
import traceback

import scenario
import yaml
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QTabWidget, QTextEdit
from qtpy.QtCore import Signal, QItemSelection
from qtpy.QtGui import QBrush
from qtpy.QtGui import QStandardItemModel, QStandardItem
from qtpy.QtWidgets import QListView
from qtpy.QtWidgets import QSplitter
from qtpy.QtWidgets import QTreeView

from theatre.logger import logger
from theatre.helpers import get_icon, get_color, toggle_visible
from theatre.trace_tree_widget.state_node import StateNode, ParentEvaluationFailed
from theatre.trace_tree_widget.structs import StateNodeOutput

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
    _invalid_state_color = "pastel red"

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self._trace: _Trace = None
        self._state_node: StateNode = None
        self.setModel(QStandardItemModel())
        self.setSelectionMode(self.SingleSelection)

    def is_displayed(self, state: typing.Optional[StateNode]):
        return self._state_node is state

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


class StateNodeUnsetError(RuntimeError):
    pass


class NoStateError(RuntimeError):
    pass


class TextView(QTextEdit):
    TOOLTIP = ""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._state_node: StateNode = None
        self.setReadOnly(True)
        self.setToolTip(self.TOOLTIP)

    def display(self, state_node: StateNode):
        self._state_node = state_node
        self.update_contents()

    def generate_contents(self) -> str:
        """Return a string or raise NoContents"""
        raise NotImplementedError("abstract method")

    def update_contents(self):
        try:
            contents = self.generate_contents()
        except NoStateError:
            contents = "Nothing to display. State evaluation failed."
        self.setText(contents)

    @property
    def node_output(self) -> StateNodeOutput:
        if self._state_node is None:
            raise StateNodeUnsetError()
        out = self._state_node.eval()
        return out

    def toggle(self):
        return toggle_visible(self)


def _format_error_message(exception: typing.Optional[Exception]):
    if not exception:
        return "<no logs>"
    if isinstance(exception, ParentEvaluationFailed):
        return (
            "<no logs>: state evaluation failed because some parent node is broken. "
            f"Fix the parents of this node and try again.\n ({type(exception).__name__})"
        )
    return f"<no logs>: state evaluation failed with error\n {type(exception).__name__}"


class ScenarioLogsView(TextView):
    TOOLTIP = "scenario.Context.run() logging output"

    def generate_contents(self):
        out = self.node_output
        scenario_logs = out.scenario_logs
        if scenario_logs:
            return scenario_logs
        return _format_error_message(out.exception)


class CharmLogsView(TextView):
    TOOLTIP = "charm execution juju-log output"

    def generate_contents(self):
        out = self.node_output
        juju_log = out.charm_logs
        if juju_log:
            return "\n".join(" ".join(line) for line in juju_log)
        return _format_error_message(out.exception)


class LogsView(QSplitter):
    def __init__(self, *__args):
        super().__init__(*__args)
        self.setOrientation(Qt.Vertical)

        self.charm_logs_view = clogsview = CharmLogsView(self)
        self.scenario_logs_view = slogsview = ScenarioLogsView(self)

        self.addWidget(clogsview)
        self.addWidget(slogsview)
        self.setSizes([80, 20])

    def show_scenario_logs(self, show: bool = True):
        self.scenario_logs_view.setVisible(show)

    def update_contents(self):
        self.charm_logs_view.update_contents()
        self.scenario_logs_view.update_contents()

    def display(self, state_node: StateNode):
        self.charm_logs_view.display(state_node)
        self.scenario_logs_view.display(state_node)


class RawStateView(TextView):
    def generate_contents(self):
        if not self.node_output.state:
            raise NoStateError()
        state_dict = dataclasses.asdict(self.node_output.state)

        # yaml doesn't like paths nor pebble layers
        for container in state_dict.get("containers", {}):
            for mount in container.get("mounts", {}).values():
                mount["src"] = str(mount["src"])
                mount["location"] = str(mount["location"])
            container["layers"] = {
                name: str(value) for name, value in container["layers"].items()
            }
            container["service_status"] = {
                name: str(value) for name, value in container["service_status"].items()
            }

        return yaml.safe_dump(state_dict)


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
            status_item = QStandardItem(get_icon("error"), "state evaluation failed")
            model.appendRow(status_item)
            return

        # status
        state: scenario.State = state_node.value.state
        status_name_to_icon = {
            "active": "stars",
            "blocked": "error",
        }
        unit_status = state.unit_status
        status_icon = status_name_to_icon.get(unit_status.name, "warning")
        status_text = f"{unit_status.name}: {unit_status.message}"
        status_item = QStandardItem(get_icon(status_icon), status_text)

        model.appendRow(status_item)


class NodeView(QTabWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._displayed: None | StateNode = None

        self.setToolTip("Select a state in the inspector to view it.")
        self.state_view = sw = StateView(self)
        self.logs_view = tv = LogsView(self)
        self.raw_state_view = rsv = RawStateView(self)
        self.addTab(sw, "state")
        self.addTab(tv, "logs")
        self.addTab(rsv, "raw")

    def is_displayed(self, state_node: StateNode | None):
        return self._displayed is state_node

    def update_contents(self):
        """Update contents of all tabs"""
        self.state_view.update_contents()
        self.logs_view.update_contents()
        self.raw_state_view.update_contents()

    def display(self, state_node: StateNode):
        if self.is_displayed(state_node):
            logger.info(f"ignored display: state node {state_node} already in NodeView")
            return

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

        self.setToolTip("Select a state node to inspect the trace leading to it.")
        self.addWidget(trace_view)
        self.addWidget(node_view)
        self.setSizes([20, 80])

    def toggle(self):
        toggle_visible(self)

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
        if self.trace_view.is_displayed(None):
            return self.display(state_node)

        if self.node_view.is_displayed(state_node):
            self.node_view.update_contents()
