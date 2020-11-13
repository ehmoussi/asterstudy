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
Tab widget
----------

The module implements improved version of tab widget.

For more details refer to *TabWidget* class.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class TabWidget(Q.QTabWidget):
    """Tab widget class that is able to show / hide child pages."""

    def __init__(self, parent=None):
        """
        Create widget.

        Arguments:
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
        """
        super(TabWidget, self).__init__(parent)
        self.widgets = []
        self.in_show_hide = False

    def tabInserted(self, index):
        """
        Called just after new page is inserted.

        Arguments:
            index (int): Index of just inserted page.
        """
        if self.in_show_hide:
            return
        self.widgets.insert(index, self.widget(index))
        self.widgets[index].icon = self.tabIcon(index)
        self.widgets[index].title = self.tabText(index)

    def tabRemoved(self, index):
        """
        Called just after new page is removed.

        Arguments:
            index (int): Index of just removed page.
        """
        if self.in_show_hide:
            return
        self.widgets.pop(index)

    def setTabVisible(self, widget, visible):
        """
        Show / hide page.

        Arguments:
            widget (QWidget): Widget inserted into the tab widget as a
            page.
            visible (bool): *True* to show page, *False* to hide it.
        """
        if widget is None or widget not in self.widgets:
            return
        if visible:
            if self.indexOf(widget) != -1:
                return # already shown
            index = 0
            for wdg in self.widgets:
                if wdg == widget:
                    break
                elif self.indexOf(wdg) != -1:
                    index = index + 1
            self.in_show_hide = True
            self.insertTab(index, widget, widget.icon, widget.title)
            self.in_show_hide = False
            if self.count():
                self.setVisible(True)
        else:
            index = self.indexOf(widget)
            if index == -1:
                return # already hidden
            self.in_show_hide = True
            self.removeTab(index)
            self.in_show_hide = False
            if not self.count():
                self.setVisible(False)
        widget.setVisible(visible)

    def isTabVisible(self, widget):
        """
        Check if page is shown.

        Arguments:
            widget (QWidget): Widget inserted into the tab widget as a
            page.

        Returns:
            bool: *True* if page is shown; *False* otherwise.
        """
        return self.indexOf(widget) != -1
