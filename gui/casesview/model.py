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
Cases model
-----------

The module implements a model for *Cases* view.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

from common import connect, translate
from gui import get_icon

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class Model(Q.QStandardItemModel):
    """
    Cases view model.
    """

    CurrentCaseUid = 0
    RunCasesUid = -1
    BackupCasesUid = -2

    indexChanged = Q.pyqtSignal(Q.QModelIndex, str)
    """
    Signal: emitted when an item is edited by the user.

    Arguments:
        index (QModelIndex): Model index being edited.
        value (str): New value of the model index.
    """

    indexExpanded = Q.pyqtSignal(Q.QModelIndex)
    """
    Signal: emitted when an item has to be forcidly expanded.

    Arguments:
        index (QModelIndex): Model index to be expanded.
    """

    internalUpdate = Q.pyqtSignal(Q.QModelIndex)
    """
    Signal: emitted when an item has to be silently updated in a view.

    Arguments:
        index (QModelIndex): Model index being updated.
    """

    def __init__(self, parent=None):
        """
        Create model.

        Arguments:
            parent (Optional[QObject]): Parent object. Defaults to
                *None*.
        """
        super(Model, self).__init__(parent)
        self._history = None
        connect(self.itemChanged, self._changed)

    @property
    def history(self):
        """
        Get history object.

        Returns:
            History: History object.
        """
        return self._history

    @history.setter
    def history(self, history):
        """
        Set history object.

        Arguments:
            history (History): History object.
        """
        self._history = history
        self.update()

    def update(self):
        """
        Update model contents.
        """
        if self.history is None:
            self.clear()
        else:
            current_case = self.history.current_case # pragma pylint: disable=no-member
            run_cases = self.history.run_cases # pragma pylint: disable=no-member
            backup_cases = self.history.backup_cases # pragma pylint: disable=no-member

            item = self._findItem(Model.CurrentCaseUid, recursive=False)
            if item is None:
                item = Q.QStandardItem()
                self.invisibleRootItem().insertRow(0, item)
            self._updateItem(item, current_case)

            title = translate("CasesView", "Run Cases")
            uid = Model.RunCasesUid
            self._syncList(uid, title, 1, run_cases)

            title = translate("CasesView", "Backup Cases")
            uid = Model.BackupCasesUid
            self._syncList(uid, title, 2, backup_cases)

    def _syncList(self, parent_uid, parent_title, parent_row, cases):
        """
        Synchronize list of items for cases.

        Arguments:
            parent_id (int): Parent item's UID.
            parent_title (str): Parent item's title.
            parent_row (int): Parent item's row index.
            cases (list[Case]): List of cases.
        """
        parent_item = self._findItem(parent_uid, recursive=False)
        if cases:
            needs_expanding = False

            if parent_item is None:
                parent_item = Q.QStandardItem(parent_title)
                parent_item.setData(parent_uid)
                row = min(parent_row, self.invisibleRootItem().rowCount())
                self.invisibleRootItem().insertRow(row, parent_item)
                needs_expanding = True

            cases_uids = [i.uid for i in cases]

            for i, case in enumerate(reversed(cases)):
                item = self._findItem(case.uid, parent_item, recursive=False)
                if item is None:
                    item = Q.QStandardItem()
                    parent_item.insertRow(i, item)
                self._updateItem(item, case)

            for row in reversed(range(parent_item.rowCount())):
                item = parent_item.child(row, 0)
                if item.data() not in cases_uids:
                    parent_item.removeRow(row)

            if needs_expanding:
                self.indexExpanded.emit(self.indexFromItem(parent_item))

        else:
            if parent_item is not None:
                self.invisibleRootItem().removeRow(parent_item.row())

    def modelIndex(self, case):
        """
        Get model index for given case.

        Arguments:
            case (int, Case): Case or its UID.

        Returns:
            QModelIndex: Model index corresponding to the given Case
            (invalid if Case is not found).
        """
        uid = case if isinstance(case, int) else case.uid
        item = self._findItem(uid)
        return self.indexFromItem(item) if item is not None \
            else Q.QModelIndex()

    def modelObject(self, index):
        """
        Get Case for given model index.

        Arguments:
            index (QModelIndex): Model index.

        Returns:
            Case: Case corresponding to the model index; *None* if index
            is incorrect.
        """
        obj = None
        item = self.itemFromIndex(index)
        if item is not None and self.history is not None:
            obj = self.history.get_node(item.data()) # pragma pylint: disable=no-member
        return obj

    def _findItem(self, uid, parent_item=None, recursive=True):
        """
        Find item.

        Arguments:
            uid (int): Item's UID.
            parent_item (Optional[QStandardItem]): Parent item. If not
                given, root item is used. Defaults to *None*.
            recursive (Optional[bool]): When *True*, performs recursive
                search. Defaults to *True*.
        """
        if parent_item is None:
            parent_item = self.invisibleRootItem()
        for row in range(parent_item.rowCount()):
            item = parent_item.child(row, 0)
            if uid == Model.CurrentCaseUid and item.data() > 0:
                return item
            elif item.data() == uid:
                return item
            elif recursive:
                item = self._findItem(uid, item)
                if item is not None:
                    return item
        return None

    def _updateItem(self, item, case):
        """
        Update item from case.

        Arguments:
            item (QStandardItem): Model item.
            case (Case): Case object.
        """
        self.blockSignals(True)
        item.setData(case.uid)
        item.setText(case.name)
        item.setIcon(get_icon(case))
        font = item.font()
        if self.parent() is not None:
            font.setBold(self.parent().isActiveCase(case))
            font.setItalic(self.parent().isActiveCase(case))
            item.setFont(font)
        item.setToolTip(case.description)
        self.blockSignals(False)
        self.internalUpdate.emit(item.index())

    @Q.pyqtSlot("QStandardItem*")
    def _changed(self, item):
        """
        Called when item's data is changed.
        Emits `indexChanged()` signal.
        """
        index = self.indexFromItem(item)
        if item is not None and index.isValid():
            self.indexChanged.emit(index, item.text())
