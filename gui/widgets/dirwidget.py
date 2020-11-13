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
Directory widget
----------------

The module implements a widget managing code_aster catalogs
in SALOME Preferences dialog.

For more details refer to *DirWidget* class.

"""

from __future__ import unicode_literals

import PyQt5.Qt as Q
import SalomePyQt

from . catalogsview import CatalogsView

class DirWidget(SalomePyQt.UserDefinedContent):
    """Custom preference item for user's catalogs set-up."""

    widget = None

    def __init__(self):
        """Create widget."""
        super(DirWidget, self).__init__()
        self.editor = CatalogsView()
        self.setLayout(Q.QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self.editor)

    def store(self):
        """Store settings."""
        self.editor.store()

    def retrieve(self):
        """Restore settings."""
        self.editor.restore()

    @staticmethod
    def instance():
        """Get singleton widget object."""
        if DirWidget.widget is None:
            DirWidget.widget = DirWidget()
        return DirWidget.widget
