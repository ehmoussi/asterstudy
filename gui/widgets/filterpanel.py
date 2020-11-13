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
Filter panel
------------

The module implements panel that allows to filter out its contents.

The module provides two classes:

- *FilterWidget* implements abstract class that should be used as base
  for any widget which is aimed to be inserted into the *FilterPanel*;
  in that widget it's necessary to implement *filter()* method to
  show/hide contents depending on the search criterion.
- *FilterPanel* introduces panel with a searcher widget and resizable
  main part containing list of *FilterWidget* items.

For more details refer to *FilterWidget* and *FilterPanel* classes.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

from . searchwidget import SearchWidget

__all__ = ["FilterWidget", "FilterPanel"]

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class FilterWidget(Q.QFrame):
    """Base class for all widgets that can filter own content."""

    def __init__(self, **kwargs):
        """
        Create widget.

        Arguments:
            **kwargs: Arbitrary keyword arguments.
        """
        super(FilterWidget, self).__init__(**kwargs)
        self._stretchable = False

    # pragma pylint: disable=unused-argument,no-self-use
    def filter(self, text):
        """
        Apply filter.

        This method should be implemented in successor classes;
        default implementation raises exception.

        Arguments:
            text (str): Regular expression.

        Raises:
            NotImplementedError: The method should be implemented in
                sub-classes.
        """
        raise NotImplementedError("Method should be implemented in successors")

    def setStretchable(self, stretchable):
        """
        Set widget expandable.

        If widget is expandable, it may occupy all free space in parent
        *FilterPanel*; otherwise, its size is controlled by the size
        hint.

        Arguments:
            stretchable (bool): *True* to make widget expandable;
                *False* otherwise.

        See also:
            `isStretchable()`
        """
        self._stretchable = stretchable

    def isStretchable(self):
        """
        Tells whether this widget is expandable.

        Returns:
            bool: *True* if widget is expandable; *False* otherwise.
        """
        return self._stretchable


class FilterPanel(Q.QWidget):
    """
    Panel that contains set of widgets which can filter out own content.
    """

    def __init__(self, parent=None):
        """
        Create widget.

        Arguments:
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
        """
        super(FilterPanel, self).__init__(parent)
        self._widgets = []
        self._search = SearchWidget(self)
        self._scroll = ScrollArea(self)
        self._scroll.setHorizontalScrollBarPolicy(Q.Qt.ScrollBarAlwaysOff)
        self._scroll.setWidgetResizable(True)
        self._scroll.setSizePolicy(Q.QSizePolicy.Minimum,
                                   Q.QSizePolicy.Expanding)
        self._scroll.setWidget(Q.QWidget())
        self._scroll.widget().setLayout(Q.QVBoxLayout())
        self._scroll.widget().layout().setContentsMargins(0, 0, 0, 0)
        self._scroll.widget().layout().setSpacing(0)
        self._scroll.widget().layout().addStretch(1)
        v_layout = Q.QVBoxLayout(self)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.addWidget(self._search)
        v_layout.addWidget(self._scroll)
        self._search.filterChanged.connect(self.filter)
        self.setFocusProxy(self._search)

    def addWidget(self, widget):
        """
        Add child widget to scrolled area.

        Arguments:
            widget (QWidget): Child widget.
        """
        self._widgets.append(widget)
        v_layout = self._scroll.widget().layout()
        v_layout.insertWidget(v_layout.count() - 1, widget)
        if widget.isStretchable():
            # expandable widget should take available space of layout,
            # but not spacer item
            spacer = v_layout.itemAt(v_layout.count() - 1)
            v_layout.removeItem(spacer)

    def addControlWidget(self, widget):
        """
        Add child widget to 'control' area.

        Arguments:
            widget (QWidget): Child widget.
        """
        v_layout = self.layout()
        v_layout.insertWidget(v_layout.count() - 1, widget)

    @Q.pyqtSlot(str)
    def filter(self, text):
        """
        Apply filter to all child widgets.

        Arguments:
            text (str): Regular expression.
        """
        for widget in self._widgets:
            if isinstance(widget, FilterWidget):
                widget.filter(text)

    def applyFilter(self):
        """
        Re-apply currently selected filter to the child widgets.
        """
        self.filter(self._search.filter())

    def widgets(self):
        """
        Get child widgets.

        Returns:
            list[QWidget]: Child widgets.
        """
        return self._widgets


class ScrollArea(Q.QScrollArea):
    """
    Scroll area with corrected size hint behaviour.
    """

    def __init__(self, parent=None):
        """
        Create widget.

        Arguments:
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
        """
        super(ScrollArea, self).__init__(parent)

    def sizeHint(self):
        """Reimplemented from *QScrollArea*."""
        sz = super(ScrollArea, self).sizeHint()
        vsbar = self.verticalScrollBar()
        if vsbar.isVisibleTo(vsbar.parentWidget()):
            sz.setWidth(sz.width() + vsbar.sizeHint().width())
        return sz

    def minimumSizeHint(self):
        """Reimplemented from *QScrollArea*."""
        sz = super(ScrollArea, self).minimumSizeHint()
        vsbar = self.verticalScrollBar()
        if vsbar.isVisibleTo(vsbar.parentWidget()):
            sz.setWidth(sz.width() + vsbar.minimumSizeHint().width())
        return sz
