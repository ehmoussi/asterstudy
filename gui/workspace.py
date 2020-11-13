# -*- coding: utf-8 -*-

# Copyright 2016 EDF R&D
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, you may download a copy of license
# from https://www.gnu.org/licenses/gpl-3.0.

"""
Workspace
---------

The module implements Workspace for AsterStudy GUI.
See `Workspace` class for mode details.

"""
from __future__ import unicode_literals


from PyQt5 import Qt as Q

from common import connect, font, is_child, load_icon, translate, wrap_html
from . import Entity, Context, Panel, WorkingMode
from . behavior import behavior
from . editionpanel import EditionPanel
from . widgets import TabWidget
from . datafiles import DataFiles
from . dashboard import Dashboard
from . casesview import CasesView
from . datasettings import DataSettings
from . infoview import InfoView

def views():
    """
    Get all views managed by Worspace.

    Returns:
        list[int]: Views supported by workspace (see `Context`).
    """
    return [Context.DataSettings, Context.DataFiles,
            Context.Information, Context.Cases]


def view_title(context):
    """
    Get view's title.

    Arguments:
        context (int): Selection context (see `Context`).

    Returns:
        str: View title.
    """
    title = ""
    if context == Context.DataSettings:
        title = translate("Workspace", "Data Settings")
    elif context == Context.DataFiles:
        title = translate("Workspace", "Data Files")
    elif context == Context.Information:
        title = translate("Workspace", "Information")
    elif context == Context.Cases:
        title = translate("Workspace", "Cases")
    return title


# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class Workspace(Q.QWidget):
    """
    `Workspace` is a class that manages main GUI elements of the
    AsterStudy application.

    To access main GUI elements like *Data Settings* or *Edition*
    views, use `view()` method.
    """

    modeChanged = Q.pyqtSignal(int)
    """
    Signal: emitted when workspace is switched between `History` and
    `Case` working modes.

    Arguments:
        mode (int): Working mode (see `WorkingMode`).
    """

    viewChanged = Q.pyqtSignal(int)
    """
    Signal: emitted when view is switched between `DataSettings` and
    `DataFiles`.

    Arguments:
        context (int): Active view (see `Context`).
    """

    selectionChanged = Q.pyqtSignal(int)
    """
    Signal: emitted when selection is changed.

    Arguments:
        context (int): Selection context (see `Context`).
    """

    popupMenuRequest = Q.pyqtSignal(int, "QPoint")
    """
    Signal: emitted when context popup menu is requested.

    Arguments:
        context (int): Event context (see `Context`).
        point (QPoint): Mouse cursor position.
    """

    itemChanged = Q.pyqtSignal(Entity, str, int)
    """
    Signal: emitted when data item is changed.

    Arguments:
        entity (Entity): Selection entity.
        value (str): New item's value.
        context (int): Selection context (see `Context`).
    """

    itemActivated = Q.pyqtSignal(Entity, int)
    """
    Signal: emitted when data item is activated.

    Arguments:
        entity (Entity): Selection entity.
        context (int): Selection context (see `Context`).
    """

    editModeActivated = Q.pyqtSignal()
    """
    Signal: emitted when application switches from View to Edit mode.
    """

    def __init__(self, astergui, parent=None, tab_position=Q.QTabWidget.West):
        """
        Create workspace.

        Arguments:
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
            tab_position (Optional[QTabWidget.TabPosition]): Position
                of tab pages. Defaults to QTabWidget.West (left,
                vertical).
        """
        Q.QWidget.__init__(self, parent)

        self.astergui = astergui
        self.pages = {}
        self.panels = {}
        self.views = {}

        # Set-up main area as tab widget with two pages
        self.main = Q.QTabWidget(self)
        self.main.setSizePolicy(Q.QSizePolicy.Expanding,
                                Q.QSizePolicy.Expanding)
        self.main.setTabPosition(tab_position)
        v_layout = Q.QVBoxLayout(self)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.addWidget(self.main)

        # - Add "History View" page
        self.pages[WorkingMode.HistoryMode] = Q.QWidget(self.main)
        self.main.addTab(self.pages[WorkingMode.HistoryMode],
                         load_icon("as_pic_historypanel.png"),
                         translate("Workspace", "History View"))
        # - Add "Case View" page
        self.pages[WorkingMode.CaseMode] = Q.QWidget(self.main)
        self.main.addTab(self.pages[WorkingMode.CaseMode],
                         load_icon("as_pic_casepanel.png"),
                         translate("Workspace", "Case View"))

        # Set-up "History View" page.
        self.history_hsplitter = \
            Q.QSplitter(Q.Qt.Horizontal, self.pages[WorkingMode.HistoryMode])
        self.history_hsplitter.setChildrenCollapsible(False)
        v_layout = Q.QVBoxLayout(self.pages[WorkingMode.HistoryMode])
        v_layout.addWidget(self.history_hsplitter)
        # - Add "Dashboard" view
        self.views[Context.Dashboard] = Dashboard(astergui,
                                                  self.history_hsplitter)
        # - Add "Cases" view
        self.views[Context.Cases] = CasesView(astergui,
                                              self.history_hsplitter)
        self.history_hsplitter.addWidget(self.views[Context.Cases])
        self.history_hsplitter.addWidget(self.views[Context.Dashboard])
        self.history_hsplitter.\
            setStretchFactor(self.history_hsplitter.count()-1, 1)

        # Set-up "Case View" page.
        v_layout = Q.QVBoxLayout(self.pages[WorkingMode.CaseMode])

        self.banner = Q.QLabel(self.pages[WorkingMode.CaseMode])
        self.banner.setObjectName("read_only_banner")
        self.banner.setFrameStyle(Q.QLabel.Box | Q.QLabel.Sunken)
        self.banner.setBackgroundRole(Q.QPalette.ToolTipBase)
        self.banner.setAutoFillBackground(True)
        self.banner.setAlignment(Q.Qt.AlignCenter)
        self.banner.linkActivated.connect(self.editModeActivated)
        v_layout.addWidget(self.banner)

        self.case_hsplitter = \
            Q.QSplitter(Q.Qt.Horizontal, self.pages[WorkingMode.CaseMode])
        self.case_hsplitter.setChildrenCollapsible(False)
        v_layout.addWidget(self.case_hsplitter, 10)

        self.case_vsplitter = Q.QSplitter(Q.Qt.Vertical, self.case_hsplitter)
        self.case_vsplitter.setChildrenCollapsible(False)
        self.case_hsplitter.addWidget(self.case_vsplitter)

        # - Set-up data panel
        self.panels[Panel.Data] = TabWidget(self.case_vsplitter)
        self.panels[Panel.Data].setSizePolicy(Q.QSizePolicy.Expanding,
                                              Q.QSizePolicy.Expanding)
        self.case_vsplitter.addWidget(self.panels[Panel.Data])

        # -- Add "Data Settings" view
        self.views[Context.DataSettings] = \
            DataSettings(astergui, self.panels[Panel.Data])
        self.panels[Panel.Data].addTab(self.views[Context.DataSettings],
                                       load_icon("as_pic_datasettingview.png"),
                                       view_title(Context.DataSettings))

        # -- Add "Data Files" view
        self.views[Context.DataFiles] = DataFiles(astergui,
                                                  self.panels[Panel.Data])
        self.panels[Panel.Data].addTab(self.views[Context.DataFiles],
                                       load_icon("as_pic_datafilesview.png"),
                                       view_title(Context.DataFiles))

        # -- Add "Information" view
        self.views[Context.Information] = InfoView(astergui,
                                                   self.case_vsplitter)
        self.case_vsplitter.addWidget(self.views[Context.Information])

        # - Set-up "View" panel
        self.panels[Panel.View] = astergui.createMeshView(self.case_hsplitter)
        self.case_hsplitter.addWidget(self.panels[Panel.View])
        self.case_hsplitter.setStretchFactor(self.case_hsplitter.count()-1, 1)

        # - Set-up "Edition" panel
        self.panels[Panel.Edit] = EditionPanel(self.case_hsplitter)
        self.case_hsplitter.addWidget(self.panels[Panel.Edit])

        connect(self.main.currentChanged, self.modeChanged)
        connect(self.main.currentChanged, self._updateBanner)
        connect(self.main.currentChanged, self._selectActiveCase)
        connect(self.panels[Panel.Data].currentChanged, self._viewChanged)

        for view in self.views.itervalues():
            view.setContextMenuPolicy(Q.Qt.CustomContextMenu)
            connect(view.customContextMenuRequested, self._popupMenuRequest)
            if hasattr(view, "itemSelectionChanged"):
                connect(view.itemSelectionChanged, self._selectionChanged)
            if hasattr(view, "itemDoubleClicked"):
                connect(view.itemDoubleClicked, self._itemActivated)
            if hasattr(view, "itemChanged"):
                connect(view.itemChanged, self._itemChanged)
            if hasattr(view, "entityChanged"):
                connect(view.entityChanged, self.itemChanged)

        for win in self._windows():
            win.installEventFilter(self)

        self.setFocusPolicy(Q.Qt.StrongFocus)
        self.activate(False)


    def activate(self, enable):
        """
        Activate/deactivate workspace.

        Arguments:
            enable (bool): *True* to activate, *False* to deactivate.
        """
        self.main.setVisible(enable)

    def workingMode(self):
        """
        Get current working mode.

        Returns:
            int: Working mode (see `WorkingMode`).
        """
        return self.main.currentIndex()

    def setWorkingMode(self, mode):
        """
        Set current working mode.

        Arguments:
            mode (int): Working mode (see `WorkingMode`).
        """
        self.main.setCurrentIndex(mode)

    def setTabPosition(self, tab_position):
        """
        Set tab pages position.

        Arguments:
            tab_position (QTabWidget.TabPosition): Tab pages position.
        """
        self.main.setTabPosition(tab_position)

    def view(self, context):
        """
        Get view window.

        Arguments:
            context (int): View type (see `Context`).

        Returns:
            QWidget: View window.
        """
        return self.views.get(context)

    def activeView(self):
        """
        Get currently active view in given panel.

        Arguments:
            panel (int): Panel type (see `Panel`).

        Returns:
            Context: View being active (*None* if there's no active view).
        """
        view = None
        if self.workingMode() == WorkingMode.HistoryMode:
            focus = self.focusWidget()
            if focus is not None:
                for ctx in self.views:
                    wid = self.views[ctx]
                    if is_child(focus, wid):
                        view = ctx
                        break
            if view is None:
                if self.isViewVisible(Context.Cases):
                    view = Context.Cases
                elif self.isViewVisible(Context.Dashboard):
                    view = Context.Dashboard
        else:
            data_view = self.panels[Panel.Data].currentWidget()
            if data_view == self.views[Context.DataSettings] and \
                    self.isViewVisible(Context.DataSettings):
                view = Context.DataSettings
            elif data_view == self.views[Context.DataFiles] and \
                    self.isViewVisible(Context.DataFiles):
                view = Context.DataFiles
        return view

    def isViewAvailable(self, context):
        """
        Check if given view is available in current working mode.

        Arguments:
            context (int): View type (see `Context`).

        Returns:
            bool: *True* if view is available in current working mode;
            *False* otherwise.
        """
        panels = {
            WorkingMode.HistoryMode: [Context.Cases, Context.Dashboard],
            WorkingMode.CaseMode: [Context.DataSettings, Context.DataFiles,
                                   Context.Information],
            }
        return context in panels[self.workingMode()]

    def isViewVisible(self, context):
        """
        Check if given view is shown.

        Arguments:
            context (int): View type (see `Context`).

        Returns:
            bool: *True* if view is shown; *False* otherwise.
        """
        view = self.views.get(context)
        visible = False
        if view is not None:
            if context in [Context.DataSettings, Context.DataFiles]:
                visible = self.panels[Panel.Data].isTabVisible(view)
            else:
                visible = view.isVisible()
        return visible

    def setViewVisible(self, context, is_visible):
        """
        Show/hide view.

        Arguments:
            context (int): View type (see `Context`).
            is_visible (bool): *True* to show view; *False* to hide it.
        """
        view = self.views.get(context)
        if view is not None:
            if context in [Context.DataSettings, Context.DataFiles]:
                self.panels[Panel.Data].setTabVisible(view, is_visible)
            else:
                view.setVisible(is_visible)

    def panel(self, panel):
        """
        Get panel.

        Arguments:
            panel (int): Panel type (see `Panel`).

        Returns:
            QWidget: Panel.
        """
        return self.panels.get(panel)

    def saveState(self):
        """
        Save state of workspace's layout.

        Returns:
            str: String representation of layout state, suitable for storage in
            preference file.
        """
        history_hdata = Q.QByteArray.\
            toBase64(self.history_hsplitter.saveState())
        case_hdata = Q.QByteArray.toBase64(self.case_hsplitter.saveState())
        case_vdata = Q.QByteArray.toBase64(self.case_vsplitter.saveState())
        data = []
        data.append("{}={}".format("history_hdata", history_hdata))
        data.append("{}={}".format("case_hdata", case_hdata))
        data.append("{}={}".format("case_vdata", case_vdata))
        return Q.QByteArray(str(";".join(data)))

    def restoreState(self, state):
        """
        Restore state of workspace's layout.

        Arguments:
            state (str): String representation of layout state.
        """
        if not state:
            return
        state = state.split(";")
        data = {}
        for item in state:
            value = item.split("=")
            if len(value) > 1:
                data[str(value[0])] = value[1]
        if "history_hdata" in data:
            state = Q.QByteArray(data["history_hdata"])
            self.history_hsplitter.restoreState(state)
        if "case_hdata" in data:
            state = Q.QByteArray(data["case_hdata"])
            self.case_hsplitter.restoreState(state)
        if "case_vdata" in data:
            state = Q.QByteArray(data["case_vdata"])
            self.case_vsplitter.restoreState(state)

    def ensureVisible(self, context, entity, select=False):
        """
        Make the entity visible in the given widget.

        Arguments:
            context (int): Selection context (see `Context`).
            entity (Entity): Selection entity.
            select (Optional[bool]): Flag pointing that item should be
                also selected. Defaults to *False*.
        """
        view = self.view(context)
        if view is None:
            return
        if context in (Context.Cases, Context.Dashboard):
            self.main.setCurrentIndex(WorkingMode.HistoryMode)
        else:
            self.main.setCurrentIndex(WorkingMode.CaseMode)
            if context in (Context.DataSettings, Context.DataFiles):
                self.panels[Panel.Data].setCurrentWidget(view)
        view.setFocus()
        if context == Context.DataSettings:
            view.ensureVisible(entity, select)
        elif context == Context.Cases:
            view.ensureVisible(entity, select)
        elif context == Context.Dashboard:
            view.ensureVisible(entity, select)

    def selected(self, context):
        """
        Get current selection.

        Arguments:
            context (int): Selection context (see `Context`).

        Returns:
            list[Entity]: Selected items.
        """
        result = []
        view = self.view(context)
        if context == Context.DataSettings:
            result = view.selection()
        elif context == Context.Dashboard:
            result = view.selection()
        elif context == Context.DataFiles:
            result = view.selection()
        elif context == Context.Information:
            pass
        elif context == Context.Cases:
            result = view.selection()
        return result

    def setSelected(self, context, sellist):
        """
        Sets current selection.

        Arguments:
            context (int): Selection context (see `Context`).
            sellist (list[Entity]): Selected items.
        """
        view = self.view(context)
        if context == Context.DataSettings:
            view.setSelection(sellist)
        elif context == Context.Dashboard:
            view.setSelection(sellist)
        elif context == Context.DataFiles:
            pass
        elif context == Context.Information:
            view.setSelection(sellist)
        elif context == Context.Cases:
            view.setSelection(sellist)

    def edit(self, context, entity):
        """
        Enter edition mode for given *entity*.

        Arguments:
            context (int): Selection context (see `Context`).
            entity (Entity): Selection entity.
        """
        if context == Context.Dashboard:
            context = Context.Cases
        view = self.view(context)
        if context in (Context.DataSettings, Context.Cases):
            self.ensureVisible(context, entity, True)
            view.edit(entity)

    def updateViews(self):
        """Update views."""
        if self.astergui.study() is not None:
            # Update Read-only banner
            self._updateBanner()

            # Show/hide "Read-only" banner
            show_banner = behavior().show_readonly_banner
            cc_active = self.astergui.study().isCurrentCase()
            self.banner.setVisible(show_banner and not cc_active)

            # Update "Data Settings" view
            datasettings = self.view(Context.DataSettings)
            if datasettings is not None:
                datasettings.update()

            # Update "Data Files" view
            file_model = self.astergui.study().dataFilesModel()
            if file_model is not None:
                file_model.update()

            # Update "Dashboard" view
            dashboard = self.view(Context.Dashboard)
            if dashboard is not None:
                dashboard.update()

            # Update "Cases" view
            casesview = self.view(Context.Cases)
            if casesview is not None:
                casesview.update()

            # Update "Information" view
            infoview = self.view(Context.Information)
            if infoview is not None:
                infoview.update()

    # pragma pylint: disable=unused-argument
    def eventFilter(self, obj, event):
        """
        Detect the view and panels hiding event.
        """
        if event.type() == Q.QEvent.Hide or \
                event.type() == Q.QEvent.HideToParent or \
                event.type() == Q.QEvent.Show or \
                event.type() == Q.QEvent.ShowToParent:
            self._transferFocus()
        return False

    @Q.pyqtSlot("QPoint")
    def _popupMenuRequest(self, pos):
        """
        Called when child widget requests context popup menu.

        Emit `popupMenuRequest(Entity, QPoint)` signal.

        Arguments:
            pos (QPoint): Mouse cursor position.
        """
        sender = self.sender()
        sender.setFocus()
        self.popupMenuRequest.emit(self._context(sender), pos)

    @Q.pyqtSlot(Entity, str)
    def _itemChanged(self, entity, text):
        """
        Called when data item is changed.

        Emit `itemChanged(Entity, str)` signal.

        Arguments:
            item (QTreeWidgetItem): Widget item.
            column (int): Item's column.
        """
        sender = self.sender()
        self.itemChanged.emit(entity, text, self._context(sender))

    @Q.pyqtSlot(Entity)
    def _itemActivated(self, entity):
        """
        Called when data item is activated.

        Emit `itemActivated(Entity)` signal.

        Arguments:
            entity (Entity): Data item being activated.
        """
        sender = self.sender()
        self.itemActivated.emit(entity, self._context(sender))

    @Q.pyqtSlot()
    def _selectionChanged(self):
        """
        Called when selection is changed in a child widget.

        Emits `selectionChanged(int)` signal.
        """
        sender = self.sender()
        self.selectionChanged.emit(self._context(sender))

    @Q.pyqtSlot(int)
    def _viewChanged(self):
        """
        Called when active view is switched.

        Emits `viewChanged(int)` signal.
        """
        self.viewChanged.emit(self.activeView())

    @Q.pyqtSlot(int)
    def _selectActiveCase(self, mode):
        """
        Is called when Working mode is changed.
        Selects current case item if nothing was selected before.
        """
        context = None
        if mode == WorkingMode.CaseMode:
            context = Context.DataSettings
        elif mode == WorkingMode.HistoryMode:
            context = Context.Cases

        if context is not None and not self.selected(context):
            self.ensureVisible(context, self.astergui.study().activeCase,
                               True)

    def _windows(self):
        """Returns all views and panels."""
        return [p[1] for p in self.views.items() + self.panels.items()]

    def _transferFocus(self):
        """Move the focus to one of the visible windows."""
        focuswin = None
        curfocus = self.focusWidget()
        win_list = self._windows()
        if curfocus is not None:
            for win in win_list:
                if is_child(curfocus, win):
                    focuswin = win
                    break
            if focuswin is not None and not focuswin.isVisible():
                focuswin = None

        if focuswin is None:
            for win in win_list:
                if win.isVisible():
                    focuswin = win
                    break

            if focuswin is not None:
                focuswin.setFocus()

    def _context(self, widget):
        """
        Get context from widget.

        Arguments:
            widget (QWidget): Workspace's child widget.

        Returns:
            int: Widget's context (see `Context`).
        """
        for context, view in self.views.iteritems():
            if view is widget:
                return context
        return Context.Unknown

    @Q.pyqtSlot(int)
    def _updateBanner(self):
        """
        Update Read-only banner
        """
        txt = translate("AsterStudy",
                        "Read-only (click here to switch back to edit {})")
        case_name = self.astergui.study().history.current_case.name \
            if self.astergui.study() is not None else "<none>"
        txt = txt.format(case_name)
        txt = font(txt, color="red")
        txt = wrap_html(txt, "b")
        txt = wrap_html(txt, "a", href="to_edit_mode")
        txt = wrap_html(txt, "pre")
        self.banner.setText(txt)
