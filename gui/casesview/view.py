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
Cases view
----------

The module implements *Cases* view for AsterStudy GUI.
See `CasesView` class for more details.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

from common import connect
from gui import Entity, get_node_type
from . model import Model

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class CasesView(Q.QWidget):
    """
    Class for Cases view presentation.
    """

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

    itemChanged = Q.pyqtSignal(Entity, str)
    """
    Signal: emitted when editable item is changed by the user.

    Arguments:
        entity (Entity): Data item being changed.
        text (str): New text.
    """

    def __init__(self, astergui, parent=None):
        """
        Create view.

        Arguments:
            astergui (AsterGui): *AsterGui* instance.
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
        """
        super(CasesView, self).__init__(parent)
        self._astergui = astergui

        base = Q.QVBoxLayout(self)
        base.setContentsMargins(0, 0, 0, 0)

        self._view = Q.QTreeView(self)
        self._view.setObjectName("CasesTreeView")
        self._view.setEditTriggers(Q.QTreeView.NoEditTriggers)
        self._view.setSelectionMode(Q.QTreeView.ExtendedSelection)
        self._view.setHeaderHidden(True)
        base.addWidget(self._view)

        self._view.setModel(Model(self))

        connect(self._view.model().indexChanged, self._indexChanged)
        connect(self._view.model().indexExpanded, self._view.expand)
        connect(self._view.model().internalUpdate, self._view.update)
        connect(self._view.doubleClicked, self._doubleClicked)
        connect(self._view.selectionModel().selectionChanged,
                self._selectionChanged)

        self.update()

    def update(self):
        """
        Update cases view contents.
        """
        history = self._astergui.study().history \
            if self._astergui.study() is not None else None
        self._view.model().history = history

    def edit(self, entity):
        """
        Activate edition mode for given entity.

        Arguments:
            entity (Entity): Data entity being edited.
        """
        index = self._modelIndex(self._astergui.study().node(entity))
        if index.isValid():
            self._view.setCurrentIndex(index)
            self._view.edit(index)

    def selection(self):
        """
        Get currently selected objects.

        Returns:
            list[Entity]: List of selected entities.
        """
        selection = []
        for index in self._view.selectionModel().selectedIndexes():
            obj = self._modelObject(index)
            if obj is not None:
                selection.append(Entity(obj.uid, get_node_type(obj)))
        return selection

    def setSelection(self, objs):
        """
        Set selection (select given objects).

        Current selection is cleared.

        Arguments:
            objs (list): Objects to be selected.
        """
        block_flag = self.signalsBlocked()
        self.blockSignals(True)

        indexes = []
        for o in objs:
            index = self._modelIndex(o.uid if isinstance(o, Entity) else o)
            if index.isValid():
                indexes.append(index)

        selmodel = self._view.selectionModel()
        if len(indexes) > 0:
            selmodel.select(indexes[0], Q.QItemSelectionModel.NoUpdate|
                            Q.QItemSelectionModel.ClearAndSelect)
            for idx in indexes:
                selmodel.select(idx, Q.QItemSelectionModel.NoUpdate|
                                Q.QItemSelectionModel.Select)
            selmodel.select(indexes[len(indexes) - 1],
                            Q.QItemSelectionModel.Select)
        else:
            selmodel.clearSelection()

        self.blockSignals(block_flag)

    def clearSelection(self):
        """
        Clear selection.
        """
        self._view.selectionModel().clearSelection()

    def ensureVisible(self, obj, select=False):
        """
        Ensure that given object is visible in the view.

        Expand and scroll view if necessary.
        If *select* is *True*, the item is also selected.

        Arguments:
            obj (list): Object to manage.
            select (Optional[bool]): If *True*, the object is selected
                additionally.
        """
        index = self._modelIndex(obj.uid if isinstance(obj, Entity) else obj)
        if index.isValid():
            self._view.scrollTo(index)
            if select:
                self.setSelection([obj])
                self.itemSelectionChanged.emit()

    def isActiveCase(self, case):
        """
        Get active state of specified case.

        Arguments:
            case (Case): Case object.

        Returns:
            bool: Case activity state.
        """
        return self._astergui.study().isActiveCase(case) \
            if self._astergui.study() is not None else False

    def _modelIndex(self, case):
        """
        Get model index for given case.

        Arguments:
            case (Case): Case object.

        Returns:
            QModelIndex: Model index corresponding to case.
        """
        return self._view.model().modelIndex(case)

    def _modelObject(self, index):
        """
        Get case for given model index.

        Arguments:
            index (QModelIndex): Model index.

        Returns:
            Case: Case object corresponding to the model index.
        """
        return self._view.model().modelObject(index)

    @Q.pyqtSlot(Q.QModelIndex, str)
    def _indexChanged(self, index, value):
        """
        Called when editable item is changed by the user.

        Emits `itemChanged(entity, text)` signal.

        Arguments:
            index (QModelIndex): Model index being changed.
            value (str): New value of model index.
        """
        obj = self._modelObject(index)
        if obj is not None:
            entity = Entity(obj.uid, get_node_type(obj))
            self.itemChanged.emit(entity, value)

    @Q.pyqtSlot(Q.QModelIndex)
    def _doubleClicked(self, index):
        """
        Called when item is double clicked in the view.

        Emits `itemDoubleClicked(entity)` signal.

        Arguments:
            index (QModelIndex): Model index being activated.
        """
        obj = self._modelObject(index)
        if obj is not None:
            entity = Entity(obj.uid, get_node_type(obj))
            self.itemDoubleClicked.emit(entity)

    @Q.pyqtSlot()
    def _selectionChanged(self):
        """
        Called when selection changed in the view.
        """
        self.itemSelectionChanged.emit()
