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
Search widget
-------------

The module implements general purpose search widget.

For more details refer to *SearchWidget* class.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

from common import load_pixmap, translate

__all__ = ["SearchWidget"]

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class SearchWidget(Q.QWidget):
    """Search widget."""

    filterChanged = Q.pyqtSignal(str)
    """
    Signal: emitted when filter text is changed.

    Arguments:
        text (str): Regular expression.
    """

    confirmed = Q.pyqtSignal()
    """
    Signal: emitted when user presses <Enter> key and search filter is
    not empty.
    """

    def __init__(self, parent=None):
        """
        Create widget.

        Arguments:
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
        """
        super(SearchWidget, self).__init__(parent)
        h_layout = Q.QHBoxLayout(self)
        h_layout.setContentsMargins(0, 0, 0, 0)
        lab = Q.QLabel(self)
        lab.setPixmap(load_pixmap("as_pic_search.png", size=16))
        self._editor = LineEdit(self)
        self._editor.setObjectName("searcher")
        search_text = translate("SearchWidget",
                                "Search... (press Esc to clear search)")
        self._editor.setPlaceholderText(search_text)
        self._editor.setClearButtonEnabled(True)
        self._editor.textChanged.connect(self.filterChanged)
        self._editor.returnPressed.connect(self._returnPressed)
        h_layout.addWidget(lab)
        h_layout.addWidget(self._editor)
        self.setFocusProxy(self._editor)

    def clear(self):
        """
        Clear editor.
        """
        self._editor.setText("")

    def filter(self):
        """
        Get the current filter string

        Returns:
            str: The current string used for filtering
        """
        return self._editor.text()

    def setValidState(self, state):
        """
        Sets the valid state. If state is True (i.e. valid) then
        foreground color is standard (black) otherwise red.
        """
        pal = self._editor.palette()
        pal.setColor(self._editor.foregroundRole(),
                     Q.Qt.black if state else Q.Qt.red)
        self._editor.setPalette(pal)

    def _returnPressed(self):
        """
        Called when user presses <Enter>.
        """
        if self.filter():
            self.confirmed.emit()


class LineEdit(Q.QLineEdit):
    """
    LineEdit for search string
    """

    def __init__(self, parent=None):
        """
        Create widget.

        Arguments:
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
        """
        super(LineEdit, self).__init__(parent)

    def sizeHint(self):
        """
        Reimplemented for adjust desired width to placeholder text width.
        """
        sz = super(LineEdit, self).sizeHint()
        phwidth = self.fontMetrics().width(self.placeholderText())
        cbwidth = 32 if self.isClearButtonEnabled() else 0
        reqwidth = phwidth + cbwidth + 2 \
            + self.textMargins().left() + self.textMargins().right()
        sz.setWidth(max(sz.width(), reqwidth))
        return sz

    def keyPressEvent(self, event):
        """
        Reimplemented for clear filter string when 'Escape' key pressing.
        """
        if event.key() == Q.Qt.Key_Escape:
            if len(self.text()) > 0:
                self.setText("")
                event.accept()
            else:
                event.ignore()
        else:
            super(LineEdit, self).keyPressEvent(event)
