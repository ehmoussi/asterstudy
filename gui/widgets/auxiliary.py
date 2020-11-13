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
Auxiliary widgets
-----------------

The module implements different auxiliary widgets.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class HLine(Q.QFrame):
    """Helper class to create horizontal line frame widget."""

    def __init__(self, parent=None):
        """
        Create line widget.

        Arguments:
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
        """
        super(HLine, self).__init__(parent)
        self.setFrameStyle(Q.QFrame.HLine | Q.QFrame.Sunken)
