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
Data Settings view
------------------

The module implements *Data Settings* view for AsterStudy GUI.
See `DataSettings` class for more details.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

from common import connect, debug_mode, to_list
from gui import Entity, Role, root_node_type
from gui.behavior import behavior
from gui.widgets import TreeWidget
from . searcher import Searcher

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name

class DataSettings(Q.QWidget):
    """
    Class for categories tree presentation.
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
        entity (Entity): Data item being activated.
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
        super(DataSettings, self).__init__(parent)
        self._astergui = astergui

        base = Q.QVBoxLayout(self)
        base.setContentsMargins(0, 0, 0, 0)

        self._view = TreeWidget(self)
        self._view.itemDelegate().setEditColumns(0)
        self._view.setColumnCount(2)
        if debug_mode():
            self._view.setColumnCount(3)
        self._view.setSelectionMode(Q.QTreeWidget.ExtendedSelection)
        header = self._view.header()
        header.hide()
        header.setSectionResizeMode(Q.QHeaderView.ResizeToContents)
        header.setMaximumSectionSize(250)
        header.setStretchLastSection(True)
        root = self._view.invisibleRootItem()
        root.setData(0, Role.IdRole, root_node_type())
        base.addWidget(self._view)

        self._finder = Searcher(astergui, self)
        self._finder.setAutoHide(behavior().auto_hide_search)
        base.addWidget(self._finder)

        connect(self._view.itemSelectionChanged, self.itemSelectionChanged)
        connect(self._view.itemDoubleClicked, self._itemDoubleClicked)
        connect(self._view.itemChanged, self._itemChanged)

        self.update()

    def sizeHint(self):
        """
        Returns the desired size.
        """
        return super(DataSettings, self).sizeHint().\
            expandedTo(Q.QSize(300, 0)).\
            boundedTo(Q.QSize(400, self.maximumHeight()))

    def setAutoHideSearch(self, value):
        """
        Enable / disable search tool's auto-hide feature.

        Arguments:
            value (bool): Auto-hide flag.
        """
        self._finder.setAutoHide(value)

    def find(self):
        """
        Activate search tool.
        """
        self._finder.show()

    def update(self):
        """
        Update tree view contents.
        """
        super(DataSettings, self).update()

        self._view.setColumnHidden(1, not behavior().show_catalogue_name)

        view = self._view
        study = self._astergui.study()
        if study  is not None:
            block = view.signalsBlocked()
            view.blockSignals(True)
            category_model = study.categoryModel()
            if category_model is not None:
                category_model.update_all(view.invisibleRootItem())
            else:
                view.clear()
            view.blockSignals(block)

    def ensureVisible(self, entity, select=False):
        """
        Make the entity visible in the given widget.

        Arguments:
            entity (Entity): Selection entity.
            select (Optional[bool]): Flag pointing that item should be
                also selected. Defaults to *False*.
        """
        view = self._view
        view.setFocus()
        items = view.findData(entity.uid, Role.IdRole)
        if items:
            view.scrollToItem(items[0])
            if select:
                view.clearSelection()
                view.setCurrentItem(items[0])

    def selection(self):
        """
        Get currently selected objects.

        Returns:
            list[Entity]: List of selected objects.
        """
        result = []
        view = self._view
        items = view.selectedItems()
        result = [Entity(item.data(0, Role.IdRole),
                         typeid=item.data(0, Role.TypeRole),
                         flags=item.flags())
                  for item in items]
        return result

    def setSelection(self, objs):
        """
        Set selection, i.e. select given objects.

        Note:
            Current selection is cleared before selecting new items.

        Arguments:
            objs (list[Entity]): Objects to be selected.
        """
        block = self.signalsBlocked()
        self.blockSignals(True)

        view = self._view
        viewitems = []
        for entity in objs:
            items = view.findData(entity.uid, Role.IdRole)
            viewitems = viewitems + items

        view.selectionModel().clearSelection()
        for i in viewitems:
            i.setSelected(True)

        self.blockSignals(block)

    def clearSelection(self):
        """
        Clear selection.
        """
        self._view.selectionModel().clearSelection()

    def edit(self, entity):
        """
        Enter edition mode for given *entity*.

        Arguments:
            entity (Entity): Selection entity.
        """
        view = self._view
        items = view.findData(entity.uid, Role.IdRole)
        if items:
            view.editItem(items[0], 0)

    def highlight(self, items):
        """
        Sets the highlighting for specified tree items.

        Arguments:
            items [list (QTreeWidgetItem)]: List of highlited items
        """
        itemset = {}
        if items is not None:
            for i in to_list(items):
                itemset[i] = True

        if self._view is not None:
            treeitems = self._view.findItems('*', Q.Qt.MatchWildcard | \
                                                 Q.Qt.MatchRecursive)
            root = self._view.invisibleRootItem()
            block = self.signalsBlocked()
            self.blockSignals(True)
            for item in treeitems:
                hlt = itemset.get(item, False)
                for c in xrange(self._view.columnCount()):
                    item.setData(c, Role.HighlightRole, hlt)
                    item.setBackground(c, Q.Qt.yellow \
                                           if hlt else root.background(c))
            self.blockSignals(block)

    def showChildIems(self, items):
        """
        Provide visibility of specified items by expanding their parent items.

        Arguments:
            items ([QTreeWidgetItem]): List with items to show.
        """
        if items is None:
            return

        for i in to_list(items):
            pitem = i.parent()
            while pitem is not None:
                if not pitem.isExpanded():
                    self._view.expandItem(pitem)
                pitem = pitem.parent()

    def currentItem(self):
        """
        Gets the current item from view.

        Returns:
            QTreeWidgetItem: Current view item.
        """
        return self._view.currentItem()

    def updateCurrent(self, items, tonext, wrap=True):
        """
        Sets the current the item after current by first item
        from specified list.

        Arguments:
            items (QTreeWidgetItem|[QTreeWidgetItem]): List with items to show.
            tonext (bool): Next or prevoius item flags.
        """
        if items is None or not len(items):
            return

        itemset = {}
        if items is not None:
            for i in to_list(items):
                itemset[i] = True

        cur = self._view.currentItem()

        step = 1 if tonext else -1

        treeitems = self._view.findItems('*', Q.Qt.MatchWildcard | \
                                             Q.Qt.MatchRecursive)
        index = treeitems.index(cur) if cur in treeitems else -1
        index += step

        cur = None
        start = -1
        while cur is None and index < len(treeitems) and \
                index >= 0 and index != start:
            if itemset.get(treeitems[index], False):
                cur = treeitems[index]
            if start < 0:
                start = index
            index += step
            if wrap and index >= len(treeitems):
                index = 0
            if wrap and index < 0:
                index = len(treeitems) - 1

        if cur is not None:
            self._view.setCurrentItem(cur)
            self._view.scrollToItem(cur)

    @Q.pyqtSlot("QTreeWidgetItem*", int)
    def _itemDoubleClicked(self, item):
        """
        Called when item is double clicked in the view.

        Emits `itemDoubleClicked(entity)` signal.

        Arguments:
            item (QTreeWidgetItem): Tree widget item being activated.
        """
        entity = Entity(item.data(0, Role.IdRole),
                        typeid=item.data(0, Role.TypeRole),
                        flags=item.flags())
        self.itemDoubleClicked.emit(entity)

    @Q.pyqtSlot("QTreeWidgetItem*", int)
    def _itemChanged(self, item, column):
        """
        Called when editable item is changed by the user.

        Emits `itemChanged(entity, text)` signal.

        Arguments:
            item (QTreeWidgetItem): Tree widget item being changed.
            column (int): Tree widget column.
        """
        entity = Entity(item.data(0, Role.IdRole),
                        typeid=item.data(0, Role.TypeRole),
                        flags=item.flags())
        text = item.text(column)
        self.itemChanged.emit(entity, text)
