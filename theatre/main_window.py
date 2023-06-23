import os
import sys
import typing

import ops
from nodeeditor.node_editor_window import NodeEditorWindow
from nodeeditor.utils import dumpException
from nodeeditor.utils import loadStylesheets
from qtpy.QtCore import QSettings
from qtpy.QtCore import Qt, QSignalMapper
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import QApplication
from qtpy.QtWidgets import (
    QMdiArea,
    QWidget,
    QDockWidget,
    QAction,
    QMessageBox,
    QFileDialog,
)

from logger import logger
from theatre.helpers import get_icon, toggle_visible
from theatre.trace_inspector import TraceInspectorWidget
from theatre.trace_tree_widget.drag_listbox import QDMDragListbox
from theatre.trace_tree_widget.trace_tree_editor_widget import NodeEditorWidget

if typing.TYPE_CHECKING:
    from nodeeditor.node_editor_widget import NodeEditorWidget


# os.environ["QT_QPA_PLATFORM"] = "offscreen"

# TODO: disable edgeIntersect functionality


class TheatreMainWindow(NodeEditorWindow):
    SHOW_MAXIMIZED = False
    RESTORE_ON_OPEN = True
    FILE_DIALOG_TYPE = "Graph (*.json);;All files (*)"

    def __init__(self):
        # todo figure out import from file/project
        class DummyCharm(ops.CharmBase):
            def __init__(self, framework: ops.Framework):
                super().__init__(framework)
                for event in self.on.events().values():
                    framework.observe(event, self._on_event)

            def _on_event(self, _):
                opts = [
                    ops.ActiveStatus(""),
                    ops.BlockedStatus("whoops"),
                    ops.WaitingStatus("..."),
                ]
                import random

                self.unit.status = random.choice(opts)

        self.charm_type: typing.Optional[typing.Type[ops.CharmBase]] = DummyCharm

        super().__init__()

    def initUI(self):
        self.name_company = "Canonical"
        self.name_product = "Theatre"

        self.stylesheet_filename = os.path.join(
            os.path.dirname(__file__), "qss/nodeeditor.qss"
        )
        loadStylesheets(
            os.path.join(os.path.dirname(__file__), "qss/nodeeditor-dark.qss"),
            self.stylesheet_filename,
        )

        self.empty_icon = get_icon("code_blocks")

        self.mdiArea = QMdiArea(self)
        self.mdiArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.mdiArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.mdiArea.setViewMode(QMdiArea.TabbedView)
        self.mdiArea.setDocumentMode(True)
        self.mdiArea.setTabsClosable(True)
        self.mdiArea.setTabsMovable(True)
        self.setCentralWidget(self.mdiArea)

        self.mdiArea.subWindowActivated.connect(self.update_menus)
        self.windowMapper = QSignalMapper(self)
        self.windowMapper.mapped[QWidget].connect(self.set_active_subwindow)

        self._states = states = QDMDragListbox(self)
        self._states_dock = states_dock = QDockWidget("Library")
        states_dock.setWidget(states)
        states_dock.setFloating(False)
        self.addDockWidget(Qt.RightDockWidgetArea, states_dock)

        self._trace_inspector = trace_inspector = TraceInspectorWidget(self)
        self._trace_inspector_dock = trace_inspector_dock = QDockWidget(
            "Trace Inspector"
        )
        trace_inspector_dock.setWidget(trace_inspector)
        trace_inspector_dock.setFloating(False)
        self.addDockWidget(Qt.RightDockWidgetArea, trace_inspector_dock)

        self.createActions()
        self.createMenus()
        self.create_toolbars()
        self.create_status_bar()
        self.update_menus()

        self.readSettings()

        if not self.current_node_editor:
            # open a clean graph

            # FIXME: this horrible workaround
            new_0: NodeEditorWidget = self.onFileNew()
            self.onFileNew()  # creating another one somehow activates the menus.
            new_0.close()  # remove the first one and we're left with a functioning window.
            # WTF

            if not self.current_node_editor:
                # we just activated it but it's not active.
                # this means all the menus are disabled while they should be enabled.
                logger.debug("buggity-bug! This should not happen.")

        self.setTitle()

    def closeEvent(self, event):
        self.mdiArea.closeAllSubWindows()
        if self.mdiArea.currentSubWindow():
            event.ignore()
        else:
            self.writeSettings()
            event.accept()
            # hacky fix for PyQt 5.14.x
            import sys

            sys.exit(0)

    def createActions(self):
        super().createActions()

        self.actClose = QAction(
            "Cl&ose",
            self,
            statusTip="Close the active window",
            triggered=self.mdiArea.closeActiveSubWindow,
        )
        self.actCloseAll = QAction(
            "Close &All",
            self,
            statusTip="Close all the windows",
            triggered=self.mdiArea.closeAllSubWindows,
        )
        self.actTile = QAction(
            "&Tile",
            self,
            statusTip="Tile the windows",
            triggered=self.mdiArea.tileSubWindows,
        )
        self.actCascade = QAction(
            "&Cascade",
            self,
            statusTip="Cascade the windows",
            triggered=self.mdiArea.cascadeSubWindows,
        )
        self.actNext = QAction(
            "Ne&xt",
            self,
            shortcut=QKeySequence.NextChild,
            statusTip="Move the focus to the next window",
            triggered=self.mdiArea.activateNextSubWindow,
        )
        self.actPrevious = QAction(
            "Pre&vious",
            self,
            shortcut=QKeySequence.PreviousChild,
            statusTip="Move the focus to the previous window",
            triggered=self.mdiArea.activatePreviousSubWindow,
        )

        self.actAbout = QAction(
            "&About",
            self,
            statusTip="Show the application's About box",
            triggered=self.about,
        )

        self.actToggleStatesView = QAction(
            "Show Trace Lib",
            self,
            statusTip="Toggle the visibility of the trace library.",
            triggered = self.toggle_states,
            checkable=True,
        )

        self.actToggleScenarioLogs = QAction(
            "Show scenario logs",
            self,
            statusTip="Toggle the visibility of scenario logs in trace inspector/logs.",
            triggered = self._trace_inspector.node_view.logs_view.scenario_logs_view.toggle,
            checkable=True,
        )

        self.actToggleTraceInspector = QAction(
            "Show Trace Inspector",
            self,
            statusTip="Toggle the visibility of the trace inspector widget.",
            triggered = self._trace_inspector.toggle,
            checkable=True,
        )

    def getCurrentNodeEditorWidget(self) -> typing.Optional["NodeEditorWidget"]:
        active_subwindow = self.mdiArea.activeSubWindow()
        if active_subwindow:
            return typing.cast("NodeEditorWidget", active_subwindow.widget())
        return None

    @property
    def current_node_editor(self):
        return self.getCurrentNodeEditorWidget()

    def getFileDialogDirectory(self):
        return ""

    def onFileSaveAs(self):
        editor = self.current_node_editor

        if editor is not None:
            fname, _ = QFileDialog.getSaveFileName(
                self,
                "Save graph to file",
                self.getFileDialogDirectory(),
                self.FILE_DIALOG_TYPE,
            )
            print(f"selected: {fname!r}")
            if not fname:
                return False

            self.onBeforeSaveAs(editor, fname)
            editor.fileSave(fname)
            self.statusBar().showMessage(
                "Successfully saved as %s" % editor.filename, 5000
            )

            # support for MDI app
            if hasattr(editor, "setTitle"):
                editor.setTitle()

            else:
                self.setTitle()
            return True

    def get_title(self):
        """Generate window title."""
        title = f"Theatre[{self.charm_type.__name__}]: Trace Tree Editor"
        current_trace_tree = self.mdiArea.currentSubWindow()
        if current_trace_tree:
            title += f" - {current_trace_tree.widget().getUserFriendlyFilename()}"

    def setTitle(self):
        """Update window title."""
        self.setWindowTitle(self.get_title())

    def onFileNew(self):
        """Hande File New operation"""
        if self.maybeSave():
            editor = self.current_node_editor
            if not editor:
                new_graph = self.create_new_graph()
                self.setTitle()
                return new_graph
            self.setTitle()

    def create_new_graph(self):
        try:
            return self.create_new_trace_tree_tab()
        except Exception as e:
            logger.error(e, exc_info=True)

    def open_if_not_already_open(self, fname: str):
        existing = self.find_mdi_child(fname)
        if existing:
            self.mdiArea.setActiveSubWindow(existing)
        else:
            # we need to create new subWindow and open the file
            editor_widget = NodeEditorWidget(self.charm_type, self.mdiArea)
            if editor_widget.fileLoad(fname):
                self.statusBar().showMessage("File %s loaded" % fname, 5000)
                self.create_new_trace_tree_tab(editor_widget)
            else:
                editor_widget.close()

    def onFileOpen(self):
        fnames, _ = QFileDialog.getOpenFileNames(
            self,
            "Open graph from file",
            self.getFileDialogDirectory(),
            self.getFileDialogFilter(),
        )

        try:
            for fname in filter(None, fnames):
                self.open_if_not_already_open(fname)

        except Exception as e:
            dumpException(e)

    def about(self):
        QMessageBox.about(
            self,
            "This is awesome!",
        )

    def createMenus(self):
        super().createMenus()

        self.windowMenu = self.menuBar().addMenu("&Window")
        self.update_window_menu()
        self.windowMenu.aboutToShow.connect(self.update_window_menu)

        self.menuBar().addSeparator()

        self.helpMenu = self.menuBar().addMenu("&Help")
        self.helpMenu.addAction(self.actAbout)

        self.editMenu.aboutToShow.connect(self.update_edit_menu)

    def update_menus(self):
        active = self.current_node_editor

        hasMdiChild = active is not None

        self.actSave.setEnabled(hasMdiChild)
        self.actSaveAs.setEnabled(hasMdiChild)
        self.actClose.setEnabled(hasMdiChild)
        self.actCloseAll.setEnabled(hasMdiChild)
        self.actTile.setEnabled(hasMdiChild)
        self.actCascade.setEnabled(hasMdiChild)
        self.actNext.setEnabled(hasMdiChild)
        self.actPrevious.setEnabled(hasMdiChild)

        self.update_edit_menu()

    def update_edit_menu(self):
        try:
            # print("update Edit Menu")
            active = self.current_node_editor
            hasMdiChild = active is not None

            self.actPaste.setEnabled(hasMdiChild)

            self.actCut.setEnabled(hasMdiChild and active.hasSelectedItems())
            self.actCopy.setEnabled(hasMdiChild and active.hasSelectedItems())
            self.actDelete.setEnabled(hasMdiChild and active.hasSelectedItems())

            self.actUndo.setEnabled(hasMdiChild and active.canUndo())
            self.actRedo.setEnabled(hasMdiChild and active.canRedo())
        except Exception as e:
            dumpException(e)

    def update_window_menu(self):
        menu = self.windowMenu
        menu.clear()

        menu.addAction(self.actToggleStatesView)
        self.actToggleStatesView.setChecked(self._states_dock.isVisible())

        menu.addAction(self.actToggleTraceInspector)
        self.actToggleTraceInspector.setChecked(self._trace_inspector_dock.isVisible())

        menu.addAction(self.actToggleScenarioLogs)
        self.actToggleScenarioLogs.setChecked(
            self._trace_inspector.node_view.logs_view.scenario_logs_view.isVisible()
        )

        menu.addSeparator()

        menu.addAction(self.actClose)
        menu.addAction(self.actCloseAll)
        menu.addSeparator()
        menu.addAction(self.actTile)
        menu.addAction(self.actCascade)
        menu.addSeparator()
        menu.addAction(self.actNext)
        menu.addAction(self.actPrevious)

        windows = self.mdiArea.subWindowList()
        if windows:
            menu.addSeparator()

        for i, window in enumerate(windows):
            child = window.widget()

            text = "%d %s" % (i + 1, child.getUserFriendlyFilename())
            if i < 9:
                text = "&" + text

            action = menu.addAction(text)
            action.setCheckable(True)
            action.setChecked(child is self.current_node_editor)
            action.triggered.connect(self.windowMapper.map)
            self.windowMapper.setMapping(action, window)

    def toggle_states(self):
        # we don't subclass the states dock yet.
        toggle_visible(self._states_dock)

    def create_toolbars(self):
        pass

    def create_status_bar(self):
        self.statusBar().showMessage("Ready")

    def create_new_trace_tree_tab(self, widget: NodeEditorWidget = None):
        trace_tree_editor = widget or NodeEditorWidget(
            self.charm_type, self.mdiArea
        )
        subwnd = self.mdiArea.addSubWindow(trace_tree_editor)
        subwnd.setWindowIcon(self.empty_icon)
        self.mdiArea.setActiveSubWindow(subwnd)  # this doesn't always work

        # FIXME: horrible
        trace_tree_editor.scene.charm_type = self.charm_type
        # state reevaluated --> (re)display in trace inspector
        trace_tree_editor.state_node_changed.connect(
            self._trace_inspector.on_node_changed
        )
        # click on trace tree editor --> display in trace inspector
        trace_tree_editor.state_node_clicked.connect(self._trace_inspector.display)

        trace_tree_editor.scene.history.addHistoryModifiedListener(
            self.update_edit_menu
        )
        trace_tree_editor.add_close_event_listener(self.on_sub_window_close)

        subwnd.widget().fileNew()
        subwnd.showMaximized()
        return subwnd

    def on_sub_window_close(self, widget, event):
        existing = self.find_mdi_child(widget.filename)
        self.mdiArea.setActiveSubWindow(existing)

        if self.maybeSave():
            event.accept()
        else:
            event.ignore()

    def find_mdi_child(self, filename):
        for window in self.mdiArea.subWindowList():
            if window.widget().filename == filename:
                return window
        return None

    def set_active_subwindow(self, window):
        if window:
            self.mdiArea.setActiveSubWindow(window)

    def readSettings(self):
        """Read the permanent profile settings for this app"""
        super().readSettings()

        if self.RESTORE_ON_OPEN:
            settings = QSettings(self.name_company, self.name_product)
            previous_open = settings.value("open", []) or []
            for fname in previous_open:
                self.open_if_not_already_open(fname)

    def writeSettings(self):
        """Write the permanent profile settings for this app"""
        super().writeSettings()

        settings = QSettings(self.name_company, self.name_product)
        previous_open = [tab.filename for tab in self.mdiArea.subWindowList()]
        settings.setValue("open", previous_open)


def show_main_window():
    app = QApplication([])
    app.setStyle("Fusion")

    window = TheatreMainWindow()
    if window.SHOW_MAXIMIZED:
        window.showMaximized()
    else:
        window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    show_main_window()
