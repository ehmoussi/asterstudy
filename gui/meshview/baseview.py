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
Mesh base view
--------------

Implementation of dummy mesh view for standalone AsterStudy application.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class MeshBaseView(Q.QFrame):
    """Base widget to display mesh data."""

    def __init__(self, parent=None):
        """
        Create view.

        Arguments:
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
        """
        Q.QFrame.__init__(self, parent)
        self.setLayout(Q.QVBoxLayout())
        self.layout().setContentsMargins(5, 5, 5, 5)

    def activate(self):
        """
        Activate mesh view.

        Default implementation does nothing.
        """
        pass

    @Q.pyqtSlot(str, str, float, bool)
    def displayMEDFileName(self, meshfile, meshname=None,
                           opacity=1.0, erase=False):
        """
        Display the mesh in `meshfile` with name `meshname`.

        Default implementation does nothing.

        Arguments:
            meshfile (str): MED file name.
            meshname (Optional[str]): Mesh name. If empty, first mesh
                is used. Defaults to *None*.
            opacity (Optional[float]): Opacity of mesh presentation.
                Defaults to 1.0.
            erase (Optional[bool]): Erase all presentation in a view
                before displaying mesh presentation.
                Defaults to *False*.
        """
        pass

    @Q.pyqtSlot(str, str, str)
    def displayMeshGroup(self, meshfile, meshname, group):
        """
        Display mesh group.

        Default implementation does nothing.

        Arguments:
            meshfile (str): MED file name.
            meshname (str): Mesh name.
            group (str): Mesh group name.
        """
        pass

    @Q.pyqtSlot(str, str, str)
    def undisplayMeshGroup(self, meshfile, meshname, group):
        """
        Erase mesh group.

        Default implementation does nothing.

        Arguments:
            meshfile (str): MED file name.
            meshname (str): Mesh name.
            group (str): Mesh group name.
        """
        pass
