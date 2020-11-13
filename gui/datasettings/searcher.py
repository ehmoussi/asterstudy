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
Quick searcher
--------------

The module implements quick searcher for *Data Settings* view in
AsterStudy GUI.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

from common import translate, load_icon
from gui.widgets import SearchWidget
from . model import Model

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class Searcher(Q.QWidget):
    """
    Class for search view panel.
    """

    def __init__(self, astergui, view):
        """
        Create searcher.

        Arguments:
            astergui (AsterGui): *AsterGui* instance.
            view (QWidget): Parent view.
        """
        super(Searcher, self).__init__(view)
        self._astergui = astergui
        self._view = view
        self._items = []
        self._auto_hide = True

        self._filter = SearchWidget(self)
        self._filter.setToolTip(translate("Searcher", "Search criteria"))

        base = Q.QGridLayout(self)
        base.setContentsMargins(5, 0, 5, 5)

        self._context = Q.QComboBox(self)
        self._context.addItem(translate("Searcher", "Command"),
                              Model.Context.Name)
        self._context.addItem(translate("Searcher", "Concept"),
                              Model.Context.Concept)
        self._context.addItem(translate("Searcher", "Keyword"),
                              Model.Context.Keyword)
        self._context.addItem(translate("Searcher", "Group"),
                              Model.Context.Group)
        self._context.setToolTip(translate("Searcher", "Type of search"))

        self._prev = Q.QToolButton(self)
        self._prev.setToolTip(translate("Searcher", "Find previous item"))
        self._prev.setIcon(load_icon("as_pic_find_prev.png"))
        self._prev.setObjectName("find_prev")

        self._next = Q.QToolButton(self)
        self._next.setToolTip(translate("Searcher", "Find next item"))
        self._next.setIcon(load_icon("as_pic_find_next.png"))
        self._next.setObjectName("find_next")

        close = Q.QToolButton(self)
        close.setToolTip(translate("Searcher", "Close search panel"))
        close.setIcon(load_icon("as_pic_find_close.png"))
        close.setObjectName("close_searcher")

        base.addWidget(self._filter, 0, 0, 1, 4)
        base.addWidget(self._context, 1, 0)
        base.addWidget(self._prev, 1, 1)
        base.addWidget(self._next, 1, 2)
        base.addWidget(close, 1, 3)

        self._timer = Q.QTimer(self)
        self._timer.setInterval(10000)
        self._timer.setSingleShot(True)

        close.clicked.connect(self._onTimeout)
        self._timer.timeout.connect(self._onTimeout)
        self._context.activated.connect(self._onContextActivated)
        self._filter.filterChanged.connect(self._onFilterChanged)

        self._prev.clicked.connect(self._onFindPrev)
        self._next.clicked.connect(self._onFindNext)

        self.setFocusProxy(self._filter)

        self.hide()

    def setAutoHide(self, value):
        """
        Enable / disable auto-hide feature.

        Arguments:
            value (bool): Auto-hide flag.
        """
        self._auto_hide = value
        self._restartTimer()

    def filter(self):
        """
        Gets the current search filter.

        Returns:
            (str): Search filter string
        """
        return self._filter.filter()

    def context(self):
        """
        Gets the current search context.

        Returns:
            (str): Search context constant
        """
        return self._context.itemData(self._context.currentIndex())

    def keyPressEvent(self, event):
        """
        Reimplemented for close the searcher when 'Escape' key pressing.
        """
        if event.key() == Q.Qt.Key_Escape:
            if self.isVisibleTo(self.parentWidget()):
                if self.hasFocus():
                    self._view.setFocus()
                self.hide()
                event.accept()
            else:
                event.ignore()
        elif event.key() == Q.Qt.Key_Return or \
                event.key() == Q.Qt.Key_Enter:
            self._onFindNext()
        elif event.key() == Q.Qt.Key_F3:
            if event.modifiers() == Q.Qt.ShiftModifier:
                self._onFindPrev()
            elif event.modifiers() == Q.Qt.NoModifier:
                self._onFindNext()
        else:
            super(Searcher, self).keyPressEvent(event)

    def setVisible(self, val):
        """
        Reimplemented to clear search filter when searcher hides.
        """
        super(Searcher, self).setVisible(val)
        if not val:
            self._filter.clear()
            if self._timer.isActive():
                self._timer.stop()
        else:
            self.setFocus()
            self._restartTimer()

    def _restartTimer(self):
        """
        Restarts the internal hiding timer.
        """
        if self._timer.isActive():
            self._timer.stop()
        if self._auto_hide:
            self._timer.start()

    def _onTimeout(self):
        """
        Invoked when hide time delay is over. Hides the searcher.
        """
        if self.hasFocus():
            self._view.setFocus()
        self.hide()

    def _onContextActivated(self):
        """
        Invoked when search context was changed. Performs search.
        """
        self._performSearch()

    def _onFilterChanged(self):
        """
        Invoked when search string was changed. Performs search.
        """
        self._performSearch()

    def _onFindNext(self):
        """
        Invoked when find next button clicked.
        """
        self._findNext(self._items)

    def _onFindPrev(self):
        """
        Invoked when find next button clicked.
        """
        self._findPrev(self._items)

    def _performSearch(self):
        """
        Performs search. Obtain list of matched items and set the current
        the first from current position in view
        """
        self._items = self._matched(self.filter(), self.context())
        self._highlight(self._items)
        self._restartTimer()
        if not self._checkCurrent(self._items):
            self._findNext(self._items)
        self._updateState()

    def _matched(self, pattern, context):
        """
        Gets the list of items which matched to given pattern or context
        """
        items = []
        if pattern is not None and context is not None \
                and len(pattern) and len(context):
            if self._astergui.study() is not None:
                model = self._astergui.study().categoryModel()
                if model is not None:
                    items = model.find_items(pattern, context)
        return items

    def _highlight(self, items):
        """
        Highlight the specified items.
        """
        self._view.highlight(items)
        self._view.showChildIems(items)

    def _findNext(self, items):
        """
        Sets the current next searched item.
        """
        self._view.updateCurrent(items, True)
        self._restartTimer()

    def _findPrev(self, items):
        """
        Sets the current next searched item.
        """
        self._view.updateCurrent(items, False)
        self._restartTimer()

    def _checkCurrent(self, items):
        """
        Checks the found items list contains the current item.
        """
        cur = self._view.currentItem()
        return cur is not None and cur in items

    def _updateState(self):
        """
        Updates the seracher contorols state.
        """
        self._filter.setValidState(len(self.filter()) == 0 or \
                                       len(self._items))
        self._prev.setEnabled(len(self._items))
        self._next.setEnabled(len(self._items))
