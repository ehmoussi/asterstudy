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
Elided button
-------------

The module implements button that shows elided text.

For more details refer to *ElidedButton* class.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class ElidedButton(Q.QPushButton):
    """Button with possibility to display long text elided."""

    def __init__(self, text, parent=None):
        """Constructor."""
        super(ElidedButton, self).__init__(text, parent)
        self.setForegroundRole(Q.QPalette.ButtonText)
        self.setFlat(True)

    def minimumSizeHint(self):
        """Not allow to great increase button size with long text."""
        sz = super(ElidedButton, self).minimumSizeHint()
        sz.setWidth(min(sz.width(), 50))
        return sz

    def sizeHint(self):
        """Not allow to great increase button size with long text."""
        sz = super(ElidedButton, self).sizeHint()
        sz.setWidth(min(sz.width(), 100))
        return sz

    # pragma pylint: disable=unused-argument
    def paintEvent(self, event):
        """Displayed long text as elided."""
        p = Q.QStylePainter(self)
        option = Q.QStyleOptionButton()
        self.initStyleOption(option)
        width = self.style().subElementRect(Q.QStyle.SE_PushButtonContents,
                                            option, self).width()
        option.text = self.fontMetrics().\
            elidedText(self.text(), Q.Qt.ElideRight, width)
        p.drawControl(Q.QStyle.CE_PushButton, option)
