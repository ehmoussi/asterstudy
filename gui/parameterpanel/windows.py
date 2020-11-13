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
Parameters Panel Windows
------------------------

Implementation of the Parameters panel windows for different views.

"""

from __future__ import unicode_literals

import re

from PyQt5.Qt import Qt, QPushButton, pyqtSignal, QSplitter, QToolBar, QAction

from common import load_icon, translate, get_cmd_mesh, is_medfile, is_reference

from gui.widgets import FilterPanel

from .views import ParameterView, ParameterTableView, ParameterMeshGroupView
from .path import ParameterPath
from .widgets import PlotWidget

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name

class ParameterWindow(FilterPanel):
    """Base widget for Command or Parameter editing."""

    gotoParameter = pyqtSignal(ParameterPath, str)

    # pragma pylint: disable=unused-argument
    def __init__(self, path, panel, parent):
        """
        Create widget.

        Arguments:
            obj (Command, Parameter): Command or Parameter being edited.
            parent (Optional[QWidget]): Parent widget.
        """
        FilterPanel.__init__(self, parent)
        self._view = None
        self._panel = panel

    def path(self):
        """
        Returns the item path of the view.

        Returns:
            ParameterPath: Root item path.
        """
        return self.view().itemPath()

    def panel(self):
        """
        Gets the parameter panel.

        Returns:
            (ParameterPanel): Parameter panel object.
        """
        return self._panel

    def setUnusedVisibile(self, state):
        """
        Sets the visibility of unsed items in the view.

        Arguments:
            state (bool): visibility state for unsed items.
        """
        self.view().setUnusedVisibile(state)

    def view(self):
        """
        Gets the parameter view placed in window.

        Returns:
            ParameterView: parameter view.
        """
        return self._view

    def updateTranslations(self):
        """
        Update translations in GUI elements.
        """
        if self.view() is not None:
            self.view().updateTranslations()
            self.applyFilter()

    def _setView(self, view):
        """
        Sets the parameter view into window.

        Arguments:
            view (ParameterView): parameter view.
        """
        if self._view != view:
            self._view = view
            self._view.gotoParameter.connect(self.gotoParameter)
            self._view.ensureVisible.connect(self._ensureVisible)

    def _ensureVisible(self, rect):
        """
        Ensure visible the specified rectangle in the scrolled area.

        Arguments:
            rect (QRect): rectangle that should be visible.
        """
        pos = rect.center()
        xmargin = rect.width() / 2
        ymargin = rect.height() / 2
        self._scroll.ensureVisible(pos.x(), pos.y(), xmargin, ymargin)


class ParameterFactWindow(ParameterWindow):
    """Edition widget for Command or complex parameter (Fact)."""

    def __init__(self, path, panel, parent):
        """
        Create widget.

        Arguments:
            obj (Command, Parameter): Command or Parameter being edited.
            parent (Optional[QWidget]): Parent widget.
        """
        super(ParameterFactWindow, self).__init__(path, panel, parent)
        view = ParameterView(panel, item_path=path,
                             parent_item=None, parent=self)
        self._setView(view)
        self.addWidget(view)


class ParameterListWindow(ParameterWindow):
    """Edition widget for list or Parameters."""

    def __init__(self, path, panel, parent):
        """
        Create widget.

        Arguments:
            obj (Command, Parameter): Command or Parameter being edited.
            parent (Optional[QWidget]): Parent widget.
        """
        super(ParameterListWindow, self).__init__(path, panel, parent)
        view = ParameterView(panel, item_path=path,
                             parent_item=None, parent=self)
        self._setView(view)
        self._search.setVisible(False)
        self.add = QPushButton(translate("ParameterPanel", "Add item"))
        self.add.setIcon(load_icon("as_pic_add_row.png"))
        self.add.clicked.connect(self._addListItem)
        self.add.setObjectName(self.add.text())
        self.addControlWidget(self.add)
        self.addWidget(view)

        view.appendEnabled.connect(self.add.setEnabled)

    def _addListItem(self):
        """
        Called when 'Add' button is clicked in list parameter view.
        """
        self.view().createItem()


class ParameterTableWindow(ParameterWindow):
    """Edition widget for table in function definition."""

    AppendRow = 0       # Action: append row
    InsertRow = 1       # Action: insert row
    RemoveRow = 2       # Action: remove rows
    MoveRowUp = 3       # Action: move rows up
    MoveRowDown = 4     # Action: move rows down
    FunctionPlot = 5    # Action: plot function
    Import = 6          # Action: import table

    def __init__(self, path, panel, parent):
        """
        Create widget.

        Arguments:
            obj (Command, Parameter): Command or Parameter being edited.
            parent (Optional[QWidget]): Parent widget.
        """
        super(ParameterTableWindow, self).__init__(path, panel, parent)
        view = ParameterTableView(panel, item_path=path,
                                  parent_item=None, parent=self)
        self._actions = {}
        self._setView(view)
        self._search.setVisible(False)
        self._plot = None

        if re.match("^.*[.]VALE$", path.path()) or \
            re.match("^.*[.](ABSCISSE|ORDONNEE)$", path.path()):
            self._plot = PlotWidget(view, self)
            self._plot.hide()

            splitter = QSplitter(self)
            splitter.setOrientation(Qt.Vertical)
            splitter.addWidget(view)
            splitter.addWidget(self._plot)
            self._scroll.setWidget(splitter)
        else:
            self._scroll.setWidget(view)

        view.selectionChanged.connect(self._updateState)

        tbar = QToolBar(self)
        tbar.setToolButtonStyle(Qt.ToolButtonIconOnly)

        tbar.addAction(\
            self._createAction(ParameterTableWindow.AppendRow,
                               load_icon("as_pic_add_row.png"),
                               translate("ParameterPanel", "Append row"),
                               translate("ParameterPanel",
                                         "Append row to the end of table"),
                               view.appendRow))

        tbar.addAction(\
            self._createAction(ParameterTableWindow.InsertRow,
                               load_icon("as_pic_insert_row.png"),
                               translate("ParameterPanel", "Insert row"),
                               translate("ParameterPanel",
                                         "Insert row at current position"),
                               view.insertRow))

        tbar.addAction(\
            self._createAction(ParameterTableWindow.RemoveRow,
                               load_icon("as_pic_remove_row.png"),
                               translate("ParameterPanel", "Remove rows"),
                               translate("ParameterPanel",
                                         "Remove selected rows"),
                               view.removeRows))

        tbar.addSeparator()

        tbar.addAction(\
            self._createAction(ParameterTableWindow.MoveRowUp,
                               load_icon("as_pic_move_up.png"),
                               translate("ParameterPanel", "Move up"),
                               translate("ParameterPanel",
                                         "Move selected rows up"),
                               view.moveRowsUp))

        tbar.addAction(\
            self._createAction(ParameterTableWindow.MoveRowDown,
                               load_icon("as_pic_move_down.png"),
                               translate("ParameterPanel", "Move down"),
                               translate("ParameterPanel",
                                         "Move selected rows down"),
                               view.moveRowsDown))

        tbar.addSeparator()

        if self._plot is not None:
            tbar.addAction(\
                self._createAction(ParameterTableWindow.FunctionPlot,
                                   load_icon("as_pic_show_plot.png"),
                                   translate("ParameterPanel",
                                             "Plot function"),
                                   translate("ParameterPanel",
                                             "Show/hide plot view"),
                                   self._plot.setVisible, True))
            tbar.addSeparator()

        tbar.addAction(\
            self._createAction(ParameterTableWindow.Import,
                               load_icon("as_pic_import_table.png"),
                               translate("ParameterPanel", "Import table"),
                               translate("ParameterPanel",
                                         "Import function data from file"),
                               view.importFile))

        self.addControlWidget(tbar)

        self._updateState()

    def _action(self, actionid):
        """
        Gets the internal action by given identifier.
        """
        return self._actions.get(actionid)

    def _createAction(self, actionid, icon, text,
                      tooltip, slot, toggled=False):
        """
        Creates the new internal action with given identifier.
        """
        action = QAction(icon, text, self)
        action.setToolTip(text)
        action.setStatusTip(tooltip)
        action.setCheckable(toggled)
        if slot is not None:
            if action.isCheckable():
                action.toggled.connect(slot)
            else:
                action.triggered.connect(slot)
        self._actions[actionid] = action
        return action

    def _updateState(self):
        """
        Updates the actions according current selection
        """
        hassel = len(self.view().selectedRows()) > 0
        self._action(ParameterTableWindow.InsertRow).setEnabled(hassel)
        self._action(ParameterTableWindow.RemoveRow).setEnabled(hassel)
        self._action(ParameterTableWindow.MoveRowUp).setEnabled(hassel)
        self._action(ParameterTableWindow.MoveRowDown).setEnabled(hassel)


class ParameterMeshGroupWindow(ParameterWindow):
    """Edition widget for mesh group selection."""

    def __init__(self, path, panel, parent):
        """
        Create widget.

        Arguments:
            obj (Command, Parameter): Command or Parameter being edited.
            parent (Optional[QWidget]): Parent widget.
        """
        super(ParameterMeshGroupWindow, self).__init__(path, panel, parent)
        self._view = ParameterMeshGroupView(panel, item_path=path,
                                            parent_item=None, parent=self)
        self._view.meshChanged.connect(self.applyFilter)
        mesh = self._view.mesh()
        if mesh is not None:
            file_name, nom_med = get_cmd_mesh(mesh)
            if is_medfile(file_name) or is_reference(file_name):
                self._view.meshFileChanged.emit(file_name, nom_med, 0.1, False)
        self._setView(self._view)
        self.addWidget(self._view)


    def hideEvent(self, args):
        """
        Hide widget and reload Mesh view with opacity 1.
        """
        super(ParameterMeshGroupWindow, self).hideEvent(args)
        mesh = self._view.mesh()
        if mesh is not None:
            file_name, nom_med = get_cmd_mesh(mesh)
            if is_medfile(file_name) or is_reference(file_name):
                self._view.meshFileChanged.emit(file_name, nom_med, 1, True)
