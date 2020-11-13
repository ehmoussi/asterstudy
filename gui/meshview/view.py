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
Mesh view
---------

Implementation of mesh view for SALOME ASTERSTUDY module.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

from common import change_cursor, debug_message, is_reference, to_str
from . baseview import MeshBaseView

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


def find_mesh_by_name(meshfile=None, meshname=None):
    """
    Search mesh object in the SALOME study.

    If *meshname* is not given, last published mesh object from
    *meshfile* is returned.

    If *meshfile* is not given, last published in the study with given
    *meshname* is returned.

    If both *meshfile* and *meshname* are not given, last published
    in the study mesh object is returned.

    Arguments:
        meshfile (Optional[str]): Mesh file name. Defaults to *None*.
        meshname (Optional[str]): Name of the mesh. Defaults to *None*.

    Returns:
        SObject: SALOME study object (*None* if mesh is not found).
    """
    import salome
    import SMESH

    meshobjs = []

    if is_reference(meshfile): # 'meshfile' is entry
        return salome.myStudy.FindObjectID(str(meshfile))

    # find SMESH component
    smesh_component = salome.myStudy.FindComponent(str('SMESH'))
    if smesh_component is not None:
        # iterate through all children of SMESH component, i.e. mesh objects
        iterator = salome.myStudy.NewChildIterator(smesh_component)
        while iterator.More():
            sobject = iterator.Value() # SALOME study object (SObject)
            name = sobject.GetName() # study name of the object
            comment = sobject.GetComment() # file name (see register_meshfile)
            tag = sobject.Tag() # tag (row number)

            # name is empty if object is removed from study
            # tag for mesh object is >= SMESH.Tag_FirstMeshRoot
            if name and tag >= SMESH.Tag_FirstMeshRoot:
                if meshfile is None or comment == to_str(meshfile):
                    if meshname is None or name == to_str(meshname):
                        meshobjs.append(sobject)
            iterator.Next()

    # return last found object (study object)
    return meshobjs[-1] if len(meshobjs) > 0 else None


def register_meshfile(meshes, meshfile):
    """
    Register mesh object.

    The method puts a file name as a 'Comment' attribute to all study
    objects created by importing meshes from that file.

    Arguments:
        meshes (list[Mesh]): SMESH Mesh objects.
        meshfile (str): Mesh file name.
    """
    import salome
    for mesh in meshes:
        sobject = salome.ObjectToSObject(mesh.mesh) # pragma pylint: disable=no-member
        if sobject is not None:
            salome_study = sobject.GetStudy()
            builder = salome_study.NewBuilder()
            attr = builder.FindOrCreateAttribute(sobject,
                                                 str('AttributeComment'))
            attr.SetValue(to_str(meshfile))


def find_group_by_name(meshfile, meshname, groupname):
    """
    Search mesh group.

    Arguments:
        meshfile (str): Mesh file name.
        meshname (str): Name of the mesh.
        groupname (str): Name of the group.

    Returns:
        SObject: SALOME study object (*None* if group is not found).
    """
    sobject = find_mesh_by_name(meshfile, meshname)

    group = None
    if sobject is not None:
        salome_study = sobject.GetStudy()
        import SMESH
        # iterate through all types of groups
        for tag in range(SMESH.Tag_FirstGroup, SMESH.Tag_LastGroup+1):
            ok, container = sobject.FindSubObject(tag)
            if not ok or container is None:
                continue
            # iterate through all group of particular type
            iterator = salome_study.NewChildIterator(container)
            while iterator.More() and group is None:
                child = iterator.Value()
                name = child.GetName()
                if name and name == to_str(groupname):
                    group = child
                iterator.Next()
    return group


class MeshView(MeshBaseView):
    """Central view to display mesh and groups."""

    VIEW_TITLE = "VTK Viewer for Asterstudy"

    def __init__(self, parent=None):
        """
        Create panel.

        Arguments:
            parent (Optional[QWidget]): Parent widget. Defaults to None.

        Note:
            The VTK detached view is not created here but later, on purpose.
            For now, the place where a detached view is put shall
            not be visible at the time when it is created.
            Therefore, the detached view is only created once the
            creation of Asterstudy's desktop is complete.
        """
        MeshBaseView.__init__(self, parent)

        # attached VTK viewer
        self._vtk_viewer = -1

        # define dictionnary to collect displayed object
        self._diplayed_entry = dict()
        self._filename2entry = dict()
        self._displayed_mesh = (None, None)

    def activate(self):
        """
        Redefined from *MeshBaseView*.

        Create or activate VTK detached view.

        Note:
            The creation of the VTK detached view is not in the initializer.
            The detached view has to be created only once the
            creation of Asterstudy's desktop is complete.
        """
        from .. salomegui import get_salome_pyqt
        sgPyQt = get_salome_pyqt()

        if self._vtk_viewer < 0:
            self._vtk_viewer = sgPyQt.createView(str('VTKViewer'),
                                                 True, 0, 0, True)
            sgPyQt.setViewTitle(self._vtk_viewer, str(MeshView.VIEW_TITLE))

        # put widget within the layout
        self.layout().addWidget(sgPyQt.getViewWidget(self._vtk_viewer))

    def sizeHint(self):
        """
        Get size hint for the view.

        Returns:
            QSize: Size hint.
        """
        desktop = Q.QApplication.desktop().availableGeometry(self)
        return Q.QSize(desktop.width(), desktop.height())

    def getMeshEntry(self, meshfile, meshname):
        """
        Get the entry of a mesh in the study.

        Arguments:
            meshfile (str): MED file to read.
            meshname (Optional[str]): Name of the mesh to read.
                If empty, use the first mesh. Defaults to *None*.

        Returns:
            str: entry of the mesh.
        """
        # pragma pylint: disable=no-name-in-module,import-error
        # from this, we create an object in SMESH module
        import salome
        from salome.smesh import smeshBuilder
        smesh = smeshBuilder.New(salome.myStudy)

        if is_reference(meshfile): # 'meshfile' is entry
            return meshfile

        # we get the entry of the mesh in SMESH
        entry = None
        if meshfile not in self._filename2entry:
            theMeshes, _ = smesh.CreateMeshesFromMED(to_str(meshfile))
            register_meshfile(theMeshes, meshfile)
            sobject = find_mesh_by_name(meshfile, meshname)
            if sobject is not None:
                entry = sobject.GetID()
                self._filename2entry[meshfile] = {meshname: entry}
        elif meshname not in self._filename2entry[meshfile]:
            sobject = find_mesh_by_name(meshfile, meshname)
            if sobject is not None:
                entry = sobject.GetID()
                self._filename2entry[meshfile][meshname] = entry
        else:
            entry = self._filename2entry[meshfile][meshname]
        return entry

    @Q.pyqtSlot(str, str, float, bool)
    @change_cursor
    def displayMEDFileName(self, meshfile, meshname=None,
                           opacity=1.0, erase=False):
        """Redefined from *MeshBaseView*."""
        debug_message("entering displayMEDFileName...")
        import salome

        entry = self.getMeshEntry(meshfile, meshname)

        # activate Asterstudy's VTK view with help of the SalomePyQt utility of
        # SALOME's GUI module
        from .. salomegui import get_salome_pyqt
        get_salome_pyqt().activateViewManagerAndView(self._vtk_viewer)

        if meshfile == self._displayed_mesh[0] \
            and meshname == self._displayed_mesh[1] \
            and not erase:
            self.setAspect(entry, opacity)
            salome.sg.UpdateView()
            debug_message("displayMEDFileName return #1")
            return

        # display the entry in the active view with help of the `sg` python
        # module of `salome` python package

        for dentry in self._diplayed_entry:
            self._diplayed_entry[dentry] = 0
        salome.sg.EraseAll()
        salome.sg.Display(str(entry))

        self._diplayed_entry[entry] = 1
        self._displayed_mesh = (meshfile, meshname)
        self.setAspect(entry, opacity)

        salome.sg.FitAll()
        salome.sg.UpdateView()
        debug_message("displayMEDFileName return final")

    @Q.pyqtSlot(str, str, str)
    @change_cursor
    def displayMeshGroup(self, meshfile, meshname, group):
        """Redefined from *MeshBaseView*."""
        import salome

        # import MED file and register meshes if needed
        self.getMeshEntry(meshfile, meshname)

        sobject = find_group_by_name(meshfile, meshname, group)
        if sobject is None:
            return

        entry = sobject.GetID()

        # activate Asterstudy's VTK view with help of the SalomePyQt utility of
        # SALOME's GUI module
        from .. salomegui import get_salome_pyqt
        get_salome_pyqt().activateViewManagerAndView(self._vtk_viewer)

        # go for display
        salome.sg.Display(str(entry))
        self._diplayed_entry[entry] = 1

        self.setAspect(entry, opacity=1.0)
        salome.sg.UpdateView()

    @Q.pyqtSlot(str, str, str)
    def undisplayMeshGroup(self, meshfile, meshname, group):
        """Redefined from *MeshBaseView*."""
        import salome

        sobject = find_group_by_name(meshfile, meshname, group)
        if sobject is None:
            return

        entry = sobject.GetID()

        if entry in self._diplayed_entry and \
                self._diplayed_entry[entry] == 1:

            # activate Asterstudy's VTK view with help of the SalomePyQt
            # utility of SALOME's GUI module
            from .. salomegui import get_salome_pyqt
            get_salome_pyqt().activateViewManagerAndView(self._vtk_viewer)

            # go for display
            salome.sg.Erase(str(entry))
            self._diplayed_entry[entry] = 0

            salome.sg.UpdateView()

    def setAspect(self, entry, opacity):
        """Set aspect of an object."""

        # to set up display options
        # let us retrieve an instance of libSMESH_Swig.SMESH_Swig
        import salome

        sm_gui = salome.ImportComponentGUI(str('SMESH'))
        if not hasattr(sm_gui, 'GetActorAspect'):
            # Customizing aspect requires a newer GUI module.
            return

        # pragma pylint: disable=no-member

        # retrieve a structure with presentation parameters for this actor
        pres = sm_gui.GetActorAspect(str(entry), self._vtk_viewer)
        # redefine some of these parameters
        pres.opacity = opacity
        # the following will have to be adapted according to dimension
        # volumeColor  : 3D
        # surfaceColor : 2D
        # edgeColor    : 1D
        # nodeColor    : 0D
        #pres.surfaceColor.r = 0.
        #pres.surfaceColor.g = 1.
        #pres.surfaceColor.b = 0.
        # reinject this for the actor
        sm_gui.SetActorAspect(pres, str(entry), self._vtk_viewer)
