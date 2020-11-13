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
Data Files view
---------------

The module implements *Data Files* view for AsterStudy application.
See `DataFiles` class for more details.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

from common import connect, load_icon, translate
from gui import Entity, NodeType, Role
from gui.widgets import TreeDelegate
from . model import force_resort

__all__ = ["DataFiles"]

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class FilesView(Q.QTreeView):
    "Tree view widget to display file descriptors."

    def __init__(self, parent=None):
        """
        Create tree view.

        Arguments:
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
        """
        super(FilesView, self).__init__(parent)

        self.setItemDelegate(TreeDelegate(-1, self))

        self.header().setSectionResizeMode(Q.QHeaderView.ResizeToContents)
        self.setSortingEnabled(True)
        self.sortByColumn(0, Q.Qt.AscendingOrder)

        self.setEditTriggers(Q.QAbstractItemView.AllEditTriggers)
        self.setSelectionBehavior(Q.QAbstractItemView.SelectRows)
        self.setSelectionMode(Q.QAbstractItemView.SingleSelection)

    def selected(self):
        """
        Get selected rows.

        Returns:
            QModelIndexList: List of selected rows.
        """
        return self.selectionModel().selectedRows()

    def mouseDoubleClickEvent(self, event):
        """
        Process mouse double click event.

        Redefined from *QTreeView* class; this is needed to prevent
        non-necessary item expanding in some cases.

        Arguments:
            event (QMouseEvent): Mouse event.
        """
        index = self.indexAt(event.pos())
        if index.isValid():
            typ = index.data(Role.TypeRole)
            if typ in (NodeType.Unit, NodeType.Stage, NodeType.Dir):
                self.doubleClicked.emit(index)
                return
        super(FilesView, self).mouseDoubleClickEvent(event)


class DataFiles(Q.QWidget):
    """Data Files view."""

    itemSelectionChanged = Q.pyqtSignal()
    """
    Signal: emitted when selection is changed in the view.
    """

    itemDoubleClicked = Q.pyqtSignal(Entity)
    """
    Signal: emitted when item is activated in the view.

    Arguments:
        entity (Entity): Data item being activated.
    """

    Add = 0
    Edit = 1
    View = 2
    Remove = 3
    GoTo = 4

    def __init__(self, astergui, parent=None):
        """
        Create view.

        Arguments:
            astergui (AsterGui): *AsterGui* instance.
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
        """
        super(DataFiles, self).__init__(parent)
        self.astergui = astergui
        self.setObjectName("DataFilesBase")
        self.ops = {}

        # Files tree
        self.view = FilesView(self)
        self.view.setObjectName('DataFilesView')
        connect(self.view.clicked, self.updateButtonsState)
        connect(self.view.doubleClicked, self._doubleClicked)

        # Toolbar
        self.toolbar = Q.QToolBar(self)
        self.toolbar.setToolButtonStyle(Q.Qt.ToolButtonIconOnly)
        self.toolbar.setObjectName("DataFilesToolbar")

        # - add file
        action = Q.QAction(translate("AsterStudy", "&Add File"), self)
        action.setToolTip(translate("AsterStudy", "Add file"))
        action.setStatusTip(translate("AsterStudy",
                                      "Add a data file to the stage"))
        action.setIcon(load_icon("as_pic_new_file.png"))
        connect(action.triggered, self.add)
        self.ops[DataFiles.Add] = action

        # - edit file
        action = Q.QAction(translate("AsterStudy", "&Edit File"), self)
        action.setToolTip(translate("AsterStudy", "Edit file"))
        action.setStatusTip(translate("AsterStudy",
                                      "Edit properties of selected data file"))
        action.setIcon(load_icon("as_pic_edit_file.png"))
        connect(action.triggered, self.edit)
        self.ops[DataFiles.Edit] = action

        # - view file
        action = Q.QAction(translate("AsterStudy", "&View File"), self)
        action.setToolTip(translate("AsterStudy", "View file"))
        action.setStatusTip(translate("AsterStudy",
                                      "View properties of selected data file"))
        action.setIcon(load_icon("as_pic_view_file.png"))
        connect(action.triggered, self.edit)
        self.ops[DataFiles.View] = action

        # - remove file
        action = Q.QAction(translate("AsterStudy", "&Remove File"), self)
        action.setToolTip(translate("AsterStudy", "Remove file"))
        action.setStatusTip(translate("AsterStudy",
                                      "Remove selected data file "
                                      "from the stage"))
        action.setIcon(load_icon("as_pic_remove_file.png"))
        connect(action.triggered, self.remove)
        self.ops[DataFiles.Remove] = action

        # - go to
        action = Q.QAction(translate("AsterStudy", "&Go To"), self)
        action.setToolTip(translate("AsterStudy", "Go to"))
        action.setStatusTip(translate("AsterStudy",
                                      "Go to the selected command"))
        action.setIcon(load_icon("as_pic_goto.png"))
        connect(action.triggered, self.goto)
        self.ops[DataFiles.GoTo] = action

        # - fill in toolbar
        self.toolbar.addAction(self.ops[DataFiles.Add])
        self.toolbar.addAction(self.ops[DataFiles.Edit])
        self.toolbar.addAction(self.ops[DataFiles.View])
        self.toolbar.addAction(self.ops[DataFiles.Remove])
        self.toolbar.addAction(self.ops[DataFiles.GoTo])

        # Layout widgets
        vbox_layout = Q.QVBoxLayout(self)
        vbox_layout.setContentsMargins(5, 5, 5, 5)
        vbox_layout.addWidget(self.view)
        vbox_layout.addWidget(self.toolbar)

    def setModel(self, model):
        """
        Set model to the view.

        Arguments:
            model (QAbstractItemModel): Data model.
        """
        if self.view.model() is model:
            return
        self.view.setModel(model)
        if model is not None:
            connect(model.modelReset, self.view.expandAll)
            connect(model.modelReset, self.updateButtonsState)
            connect(self.view.selectionModel().currentChanged,
                    self.updateButtonsState)
            connect(self.view.selectionModel().selectionChanged,
                    self.itemSelectionChanged)

    def update(self):
        """Update view."""
        super(DataFiles, self).update()
        if self.view.model() is not None:
            self.view.model().update()

    def selection(self):
        """
        Get currently selected objects.

        Returns:
            list: List of selected objects.
        """
        result = []
        indices = self.view.selected()
        for index in indices:
            entity = index2entity(index)
            if entity is not None:
                result.append(entity)
        return result

    def resort(self):
        """Re-sort items in the view."""
        with force_resort():
            self.view.sortByColumn(0, Q.Qt.AscendingOrder)
        self.view.sortByColumn(0, Q.Qt.AscendingOrder)

    @Q.pyqtSlot()
    @Q.pyqtSlot(Q.QModelIndex)
    def updateButtonsState(self):
        """
        Update buttons according to the current selection.
        """
        can_add = False
        can_edit = False
        can_remove = False
        can_view = False
        can_goto = False

        selected = self.view.selected()
        is_read_only = self._isReadOnly()
        if len(selected) == 1:
            typ = selected[0].data(Role.TypeRole)
            obj = selected[0].data(Role.CustomRole)
            if typ == NodeType.Stage:
                is_text_stage = obj.is_text_mode()
                can_add = is_text_stage and not is_read_only
            elif typ == NodeType.Unit:
                can_remove = obj.deletable
                can_edit = not is_read_only
                can_view = is_read_only
            elif typ == NodeType.Command:
                can_goto = True

        self.ops[DataFiles.Add].setEnabled(can_add)
        self.ops[DataFiles.Edit].setVisible(not is_read_only)
        self.ops[DataFiles.Edit].setEnabled(can_edit)
        self.ops[DataFiles.View].setVisible(is_read_only)
        self.ops[DataFiles.View].setEnabled(can_view)
        self.ops[DataFiles.Remove].setEnabled(can_remove)
        self.ops[DataFiles.GoTo].setEnabled(can_goto)

    @Q.pyqtSlot()
    def add(self):
        """Called when 'Add' button is clicked."""
        self.astergui.addFile()

    @Q.pyqtSlot()
    def edit(self):
        """Called when 'Edit' button is clicked or item is activated."""
        self.astergui.edit()

    @Q.pyqtSlot()
    def remove(self):
        """Called when 'Remove' button is clicked."""
        self.astergui.delete()

    @Q.pyqtSlot()
    def goto(self):
        """Called when 'Go to' button is clicked."""
        self.astergui.goToCommand()

    @Q.pyqtSlot(Q.QModelIndex)
    def _doubleClicked(self, index):
        """
        Called when item is double clicked in the view.

        Emits `itemDoubleClicked(entity)` signal.

        Arguments:
            index (QModelIndex): Model index being activated.
        """
        entity = index2entity(index)
        if entity is not None:
            if entity.type in (NodeType.Stage,):
                is_ok = self.astergui.study().node(entity).is_text_mode() and \
                    not self._isReadOnly()
            elif entity.type in (NodeType.Dir,):
                is_ok = not self._isReadOnly()
            else:
                is_ok = True
            if is_ok:
                self.itemDoubleClicked.emit(entity)

    def _isReadOnly(self):
        """
        Check if view is in Read-only mode.

        Returns:
            bool: *True* if view works in Read-only mode; *False*
            otherwise.
        """
        is_read_only = True
        model = self.view.model()
        if model is not None:
            model = model.sourceModel()
            case = model.case
            is_read_only = case is not case.model.current_case
        return is_read_only


def index2entity(index):
    """
    Create selection entity from model index.

    Arguments:
        index (QModelIndex): Model index.

    Returns:
        Entity: Selection entity.
    """
    return Entity(index.data(Role.IdRole), typeid=index.data(Role.TypeRole),
                  flags=index.flags()) if index.isValid() else None
