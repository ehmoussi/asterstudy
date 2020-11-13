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
Shrinking combo box
-------------------

The module implements combo box that fits to size of its first item.

This widget is used in custom list actions used to represent
categories of commands in the AsterStudy toolbar.

For more details refer to *ShrinkingComboBox* class.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class ShrinkingComboBox(Q.QComboBox):
    """Combo-box which size fits to its first item."""

    def __init__(self, parent=None):
        """
        Create widget.

        Arguments:
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
        """
        super(ShrinkingComboBox, self).__init__(parent)

    def sizeHint(self):
        """
        Get size hint for the combo box.

        Returns:
            QSize: Widget's size hint.
        """
        shint = super(ShrinkingComboBox, self).sizeHint()
        fmetrics = self.fontMetrics()
        itext = self.itemText(0) if self.count() > 0 else ""
        textwidth = fmetrics.boundingRect(itext).width()
        iconwidth = self.iconSize().width() + 4 \
            if self.itemIcon(0) is not None else 0
        shint.setWidth(textwidth + iconwidth)
        opt = Q.QStyleOptionComboBox()
        self.initStyleOption(opt)
        shint = self.style().sizeFromContents(Q.QStyle.CT_ComboBox,
                                              opt, shint, self)
        return shint

    def minimumSizeHint(self):
        """
        Get minimal size hint for the combo box.

        Returns:
            QSize: Widget's minimum size hint.
        """
        return self.sizeHint()
