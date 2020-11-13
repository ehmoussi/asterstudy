# -*- coding: utf-8 -*-

# Copyright 2016-2017 EDF R&D
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
Category view
-------------

The module implements *Category view* used in *Show All* dialog
of AsterStudy application.

For more details refer to *CategoryView* class.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

from common import translate
from gui import Role
from . filterpanel import FilterWidget

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class CategoryView(FilterWidget):
    """
    Category view.

    Category view is a widget that contains a button and list with child
    items. Pressing on a button collapses/expandes the list box showing
    or hiding child items.

    The items are added to the view via the `addItem()` method.
    Each item can have assiciated identifier. If an identifier is
    assigned to an item, it is passed as a parameter of `selected()`
    and `doubleClicked()` signals; otherwise these signals pass item's
    text as parameter. Method `selection()` that returns a selected
    item, behaves similarly.
    """

    selected = Q.pyqtSignal(str)
    """
    Signal: emitted when selection in the list view is changed.

    Arguments:
        text (str): Selected text (empty if selection is cleared).
    """

    doubleClicked = Q.pyqtSignal(str)
    """
    Signal: emitted when item in the list view is double-clicked.

    Arguments:
        text (str): Item being double-clicked.
    """

    def __init__(self, title, **kwargs):
        """
        Create widget.

        Arguments:
            title (str): Category title.
            **kwargs: Arbitrary keyword arguments.
        """
        super(CategoryView, self).__init__(**kwargs)
        self._title = title
        self._expanded = True
        self._button = Q.QToolButton(self)
        self._button.setToolButtonStyle(Q.Qt.ToolButtonTextBesideIcon)
        self._button.setSizePolicy(Q.QSizePolicy.MinimumExpanding,
                                   Q.QSizePolicy.Fixed)
        self._list = Q.QListWidget(self)
        self._list.setTextElideMode(Q.Qt.ElideMiddle)
        self._list.setHorizontalScrollBarPolicy(Q.Qt.ScrollBarAlwaysOff)
        self._list.setVerticalScrollBarPolicy(Q.Qt.ScrollBarAlwaysOff)
        v_layout = Q.QVBoxLayout(self)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(0)
        v_layout.addWidget(self._button)
        v_layout.addWidget(self._list)
        self._button.clicked.connect(self._toggled)
        self._list.itemSelectionChanged.connect(self._selectionChanged)
        self._list.itemDoubleClicked.connect(self._doubleClicked)
        self._adjustSize()
        self._updateState()

    def addItem(self, text, ident=None):
        """
        Add item into the view.

        Arguments:
            text (str): Item's text.
            ident (Optional[str]): Item's identifier.
        """
        item = Q.QListWidgetItem(text)
        if ident is not None:
            item.setData(Role.IdRole, ident)
        self._list.addItem(item)
        self._adjustSize()
        self._updateState()

    def count(self):
        """
        Get number of items in view.

        Returns:
            int: Number of items.
        """
        return self._list.count()


    def clear(self):
        """
        Remove all items.
        """
        self._list.clear()
        self._adjustSize()
        self._updateState()

    def visibleCount(self):
        """
        Get number of visible (unfiltered) items in view.

        Returns:
            int: Number of visible items.
        """
        return len([self._list.item(i) for i in range(self._list.count())
                    if not self._list.item(i).isHidden()])

    def filter(self, text):
        """
        Apply filter.

        Arguments:
            text (str): Regular expression.
        """
        regex = Q.QRegExp(text, Q.Qt.CaseInsensitive)
        visible = 0
        for i in range(self._list.count()):
            item = self._list.item(i)
            hidden = False
            if text:
                item_data = item.data(Role.IdRole)
                item_text = item.text()
                hidden = regex.indexIn(item_text) == -1
                if item_data is not None:
                    hidden = hidden and regex.indexIn(item_data) == -1
            item.setHidden(hidden)
            if not hidden:
                visible = visible + 1
            if item.isSelected() and hidden:
                item.setSelected(False)
        self.setHidden(visible == 0)
        self._adjustSize()
        self._updateState()

    def selection(self):
        """
        Get selected item.

        Returns:
            str: Selected item (*None* if there is no selection).
        """
        items = [self._list.item(i) for i in range(self._list.count())
                 if self._list.item(i).isSelected()]
        result = None
        if len(items) > 0:
            item = items[0]
            data = item.data(Role.IdRole)
            result = data if data is not None else item.text()
        return result

    def clearSelection(self):
        """Clear selection."""
        blocked = self._list.blockSignals(True)
        self._list.clearSelection()
        self._list.blockSignals(blocked)

    def select(self, index):
        """
        Set selection to item with given index.

        Note:
            Only viisible items are taken into account.

        Arguments:
            index (int): Item's index
        """
        visible_items = [self._list.item(i) for i in range(self._list.count())
                         if not self._list.item(i).isHidden()]
        if 0 <= index < len(visible_items):
            visible_items[index].setSelected(True)

    def expand(self):
        """Expand widget."""
        self._expanded = True
        self._updateState()

    def collapse(self):
        """Collapse widget."""
        self._expanded = False
        self._updateState()

    @Q.pyqtSlot()
    def _toggled(self):
        """Called when switch button is pressed."""
        self._expanded = not self._expanded
        self._updateState()

    def _updateState(self):
        """Update widget's state."""
        total = self._list.count()
        visible = self.visibleCount()
        text = translate("CategoryView", "{visible} of {total} items shown") \
            if total != visible else translate("CategoryView", "{total} items")
        text = text.format(**{"total": total, "visible": visible})
        if self._title:
            text = "%s [%s]" % (self._title, text)
        self._button.setText(text)
        self._button.setArrowType(Q.Qt.DownArrow if self._expanded \
                                      else Q.Qt.RightArrow)
        font = self._button.font()
        font.setBold(total != visible)
        self._button.setFont(font)
        self._list.setVisible(self._expanded)

    def _adjustSize(self):
        """Adjust widget's size to its content."""
        delegate = self._list.itemDelegate()
        option = Q.QStyleOptionViewItem()
        size_hint = delegate.sizeHint(option, Q.QModelIndex())
        height = size_hint.height() * self.visibleCount()
        if height:
            height = height + 2
        self._list.setFixedHeight(height)

    @Q.pyqtSlot()
    def _selectionChanged(self):
        """
        Called when selection in a view is changed.

        Emits `selected(str)` signal.
        """
        text = ""
        for i in range(self._list.count()):
            if self._list.item(i).isSelected():
                data = self._list.item(i).data(Role.IdRole)
                text = data if data is not None else self._list.item(i).text()
        self.selected.emit(text)

    @Q.pyqtSlot("QListWidgetItem*")
    def _doubleClicked(self, item):
        """
        Called when item in a view is double-clicked.

        Emits `doubleClicked(str)` signal.

        Arguments:
            item (QListWidgetItem): List item being double-clicked.
        """
        if item:
            data = item.data(Role.IdRole)
            text = data if data is not None else item.text()
            self.doubleClicked.emit(text)
