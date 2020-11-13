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
ASTERSTUDY module: SALOME wrapping for AsterStudy application.

SALOME GUI
----------

Implementation of ASTERSTUDY SALOME GUI - a wrapper for AsterStudy
application.

"""

from __future__ import unicode_literals

import os

import PyQt5.Qt as Q

from common import (FilesSupplier, MeshGroupType, MeshElemType,
                    debug_message, enable_except_hook,
                    external_files_callback, get_base_name, to_str, translate)
from gui import Context, NodeType, Panel, WorkingMode, check_selection, str2font
from gui.astergui import AsterGui
from gui.behavior import behavior
from gui.meshview import MeshBaseView, MeshView
from gui.study import Study, study_extension
from gui.prefmanager import tab_position

def get_salome_pyqt():
    """
    Get access to SALOME PyQt interface.

    Returns:
        SalomePyQt: SALOME PyQt interface
    """
    # pragma pylint: disable=no-member
    import SalomePyQt
    return SalomePyQt.SalomePyQt()


def get_aster_view_type():
    """
    Get Aster workspace view type name.

    Returns:
        string: AsterStudy workspace's type name
    """
    return str("AsterWorkspace")


class MeshObjects(FilesSupplier):
    """Provides access to SMESH Mesh data."""
    # pragma pylint: disable=no-member

    def files(self, file_format=None):
        """
        Redefined from FilesSupplier.
        Get list of SMESH Mesh objects.
        """
        # pragma pylint: disable=import-error,protected-access
        files = []
        if file_format is None or file_format in ("MED",):
            try:
                import salome
                import SMESH
                if salome.myStudy is not None:
                    smesh = salome.myStudy.FindComponent(str('SMESH'))
                    if smesh:
                        iterator = salome.myStudy.NewChildIterator(smesh)
                        while iterator.More():
                            sobj = iterator.Value()
                            obj = sobj.GetObject()
                            uid = sobj.GetID()
                            if isinstance(obj, SMESH._objref_SMESH_Mesh):
                                files.append(uid)
                            iterator.Next()
            except ImportError:
                pass
        return files

    def filename(self, uid):
        """
        Redefined from FilesSupplier.
        Get name of SMESH Mesh object by entry specified with *uid*.
        """
        # pragma pylint: disable=import-error
        try:
            import salome
            sobj = salome.myStudy.FindObjectID(str(uid))
            if sobj and sobj.GetAllAttributes():
                return sobj.GetName()
        except (ImportError, AttributeError):
            pass
        return None

    def groups(self, uid, group_type):
        """
        Redefined from FilesSupplier.
        Get names of groups for given SMESH Mesh object.
        """
        # pragma pylint: disable=import-error,protected-access
        groups = []
        try:
            import salome
            import SMESH
            smesh_types = {
                MeshGroupType.GNode: (SMESH.NODE,),
                MeshGroupType.GElement: (SMESH.EDGE, SMESH.FACE, SMESH.VOLUME,
                                         SMESH.ELEM0D, SMESH.BALL,)
                }
            sobj = salome.myStudy.FindObjectID(str(uid))
            if group_type in smesh_types and sobj and sobj.GetAllAttributes():
                mesh = sobj.GetObject()
                if mesh and isinstance(mesh, SMESH._objref_SMESH_Mesh):
                    groups = [i.GetName() for i in mesh.GetGroups() \
                                  if i.GetType() in smesh_types[group_type]]
        except (ImportError, AttributeError):
            pass
        return groups

    def groups_by_type(self, uid, elem_type, with_size=False):
        """
        Redefined from FilesSupplier.
        Get names of groups for given SMESH Mesh object.
        """
        # pragma pylint: disable=import-error,protected-access
        groups = []
        try:
            import salome
            import SMESH
            smesh_types = {
                MeshElemType.ENode: (SMESH.NODE,),
                MeshElemType.E0D: (SMESH.ELEM0D, SMESH.BALL,),
                MeshElemType.E1D: (SMESH.EDGE, ),
                MeshElemType.E2D: (SMESH.FACE, ),
                MeshElemType.E3D: (SMESH.VOLUME,),
                }
            sobj = salome.myStudy.FindObjectID(str(uid))
            if elem_type in smesh_types and sobj and sobj.GetAllAttributes():
                mesh = sobj.GetObject()
                if mesh and isinstance(mesh, SMESH._objref_SMESH_Mesh):
                    all_groups = mesh.GetGroups()
                    for group in all_groups:
                        if group.GetType() in smesh_types[elem_type]:
                            if with_size:
                                groups.append((group.GetName().rstrip(),
                                               group.Size()))
                            else:
                                groups.append(group.GetName().rstrip())
        except (ImportError, AttributeError):
            pass
        return groups

    def export_to_med(self, uid, filepath):
        """
        Export the MESH object with entry `uid` to `filepath`.

        Arguments:
            uid (str): entry of the object
            filepath (str): path where to export it as a file
        """
        # pragma pylint: disable=import-error,no-name-in-module,protected-access
        try:
            import salome
            from salome.smesh import smeshBuilder
            sobj = salome.myStudy.FindObjectID(str(uid))
            smesh = smeshBuilder.New(salome.myStudy)
            import SMESH
            corba_obj = sobj.GetObject()
            assert isinstance(corba_obj, SMESH._objref_SMESH_Mesh)
            mesh_obj = smesh.Mesh(corba_obj, sobj.GetName())
            mesh_obj.ExportMED(to_str(filepath), 0)
        except (ImportError, AttributeError):
            pass

external_files_callback(MeshObjects(), True)


def enable_salome_actions(enable):
    """
    Show / hide unnecessary SALOME actions

    Note:
        This is a workaround until SALOME GUI is not improved to provide
        better way to do this.
    """
    import SalomePyQt
    menu = get_salome_pyqt().getPopupMenu(SalomePyQt.Edit)
    for action in menu.actions():
        action.setVisible(enable)

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class SalomePreferencesMgr(object):
    """A wrapper for preference management in SALOME."""

    def __init__(self):
        """
        Create preferences manager.
        """
        pass

    # pragma pylint: disable=no-self-use
    def value(self, key, default=None):
        """
        Get preference option's value.

        Arguments:
            key (str): Option's name.
            default (Optional[str]). Default value for the option.
                Defaults to *None*.

        Returns:
            str: Option's value.
        """
        section, parameter = self._splitKey(key)
        value = get_salome_pyqt().stringSetting(section, parameter,
                                                str(default), True)
        if value.startswith("@ByteArray"):
            try:
                value = get_salome_pyqt().byteArraySetting(section, parameter)
            except AttributeError:
                print "WARNING: can not yet restore setting {0}.".format(key)
        return value

    # pragma pylint: disable=no-self-use
    def int_value(self, key, default=0):
        """
        Get preference option's value as an integer.

        Arguments:
            key (str): Option's name.
            default (Optional[int]). Default value for the option.
                Defaults to 0.

        Returns:
            int: Option's value.
        """
        section, parameter = self._splitKey(key)
        return get_salome_pyqt().integerSetting(section, parameter, default)

    # pragma pylint: disable=no-self-use
    def float_value(self, key, default=.0):
        """
        Get preference option's value as a float.

        Arguments:
            key (str): Option's name.
            default (Optional[float]). Default value for the option.
                Defaults to 0.0.

        Returns:
            float: Option's value.
        """
        section, parameter = self._splitKey(key)
        return get_salome_pyqt().doubleSetting(section, parameter, default)

    # pragma pylint: disable=no-self-use
    def bool_value(self, key, default=False):
        """
        Get preference option's value as a boolean.

        Arguments:
            key (str): Option's name.
            default (Optional[bool]). Default value for the option.
                Defaults to *False*.

        Returns:
            bool: Option's value.
        """
        section, parameter = self._splitKey(key)
        return get_salome_pyqt().boolSetting(section, parameter, default)

    # pragma pylint: disable=no-self-use
    def str_value(self, key, default="", subst=True):
        """
        Get preference option's value as a string.

        Arguments:
            key (str): Option's name.
            default (Optional[str]). Default value for the option.
                Defaults to empty string.
            subst (Optional[bool]). Flag specifying if it's necessary to
                perform auto-substitution of variables. Defaults to
                *True*.

        Returns:
            str: Option's value.
        """
        section, parameter = self._splitKey(key)
        return get_salome_pyqt().stringSetting(section, parameter, default,
                                               subst)

    # pragma pylint: disable=no-self-use
    def font_value(self, key, default=Q.QFont()):
        """
        Get preference option's value as *QFont*.

        Arguments:
            key (str): Option's name.
            default (Optional[int]). Default value for the option.
                Defaults to null font.

        Returns:
            QFont: Option's value.
        """
        section, parameter = self._splitKey(key)
        try:
            return get_salome_pyqt().fontSetting(section, parameter, default)
        except AttributeError:
            text = get_salome_pyqt().stringSetting(section, parameter,
                                                   default.toString(), True)
            return str2font(text)

    # pragma pylint: disable=no-self-use
    def setValue(self, key, value):
        """
        Set preference option's value.

        Arguments:
            key (str): Option's name.
            value (any). Option's value.
        """
        section, parameter = self._splitKey(key)
        get_salome_pyqt().addSetting(section, parameter, value)

    # pragma pylint: disable=no-self-use
    def contains(self, key):
        """
        Check if option is known by preference manager.

        Arguments:
            key (str): Option's name.

        Returns:
            bool: *True* if this is a known option; *False* otherwise.
        """
        section, parameter = self._splitKey(key)
        return get_salome_pyqt().hasSetting(section, parameter)

    def _splitKey(self, key):
        """
        Split option to section and key components.

        For example, _splitKey('aaa/bbb') will return ('aaa', 'bbb').

        If section is not given, it defaults to name of the module.

        Arguments:
            key (str): Option's name.

        Returns:
            (str, str): Section and key components of option.
        """
        separator = '/'
        section, parameter = '', key
        if separator in key:
            index = key.index(separator)
            section, parameter = key[:index], key[index+1:]
        return section if section else AsterSalomeGui.NAME, parameter


class AsterSalomeGui(AsterGui):
    """ASTERSTUDY SALOME module GUI."""

    NAME = 'ASTERSTUDY'
    _prefMgr = None
    _VTKViewer = -1

    def __init__(self):
        """Create GUI instance."""
        AsterGui.__init__(self)

    # pragma pylint: disable=no-self-use
    def createMenu(self, text, parent=-1, group=-1):
        """
        Create menu item in the main menu of application.

        Menu item is specified by its label. If there is already a menu
        with given text, its identifier is returned.

        Parent menu is specified via the identifier; -1 means top-level
        menu.

        Menu items are combined into groups; -1 means most bottom (last)
        group.

        Arguments:
            text (str): Text label of menu item.
            parent (Optional[int]): Parent menu item. Defaults to -1.
            group (Optional[int]): Menu group. Defaults to -1.

        Returns:
            int: Menu item's unique identifier.

        Raises:
            RuntimeError: If parent menu was not found.

        See also:
            `addMenuAction()`
        """
        return get_salome_pyqt().createMenu(text, parent, -1, group)

    # pragma pylint: disable=no-self-use
    def addMenuAction(self, action, parent, group=-1):
        """
        Add action to the menu.

        Similarly to menu items, actions are combined into groups;
        see `createMenu()` for more details.

        Arguments:
            action (QAction): Menu action.
            parent (int): Parent menu item.
            group (Optional[int]): Menu group. Defaults to -1.

        Raises:
            RuntimeError: If parent menu was not found.

        See also:
            `createMenu()`
        """
        if action is None:
            action = get_salome_pyqt().createSeparator()
        get_salome_pyqt().createMenu(action, parent, -1, group)

    # pragma pylint: disable=no-self-use
    def createToolbar(self, text, name):
        """
        Create toolbar.

        Toolbar is specified by its label and name.
        Label normally is specified as a text translated to the current
        application's language, while name should not be translated - it
        is used to properly save and restore positions of toolbars.

        Arguments:
            text (str): Text label of toolbar.
            name (str): Unique name of toolbar.

        Returns:
            int: Toolbar's unique identifier.

        See also:
            `addToolbarAction()`
        """
        return get_salome_pyqt().createTool(text, name)

    # pragma pylint: disable=no-self-use
    def addToolbarAction(self, action, parent):
        """
        Add action to the toolbar.

        Arguments:
            action (QAction): Toolbar action.
            parent (int): Parent toolbar.

        Raises:
            RuntimeError: If parent toolbar was not found.

        See also:
            `createToolbar()`
        """
        if action is None:
            action = get_salome_pyqt().createSeparator()
        get_salome_pyqt().createTool(action, parent)

    @classmethod
    def preferencesMgr(cls):
        """
        Get preferences manager.

        Returns:
            object: Application's Preferences manager.
        """
        if cls._prefMgr is None:
            cls._prefMgr = SalomePreferencesMgr()
        return cls._prefMgr

    def createPreferences(self):
        """Export preferences to common Preferences dialog."""
        # pragma pylint: disable=too-many-statements

        import SalomePyQt
        def _addSpacing(_title, _gid):
            spacer = get_salome_pyqt().addPreference(_title, _gid,
                                                     SalomePyQt.PT_Space)
            get_salome_pyqt().setPreferenceProperty(spacer, "hsize", 0)
            get_salome_pyqt().setPreferenceProperty(spacer, "vsize", 10)
            get_salome_pyqt().setPreferenceProperty(spacer, "hstretch", 0)
            get_salome_pyqt().setPreferenceProperty(spacer, "vstretch", 0)

        # 'General' page
        title = translate("PrefDlg", "General")
        gid = get_salome_pyqt().addPreference(title)

        # code_aster version
        title = translate("PrefDlg", "Version of code_aster")
        item = get_salome_pyqt().addPreference(title,
                                               gid,
                                               SalomePyQt.PT_Selector,
                                               AsterSalomeGui.NAME,
                                               "code_aster_version")
        values = []
        values.append(translate("PrefDlg", "Use default"))
        values.append(translate("PrefDlg", "Ask"))
        get_salome_pyqt().setPreferenceProperty(item, "strings", values)
        values = ["default", "ask"]
        get_salome_pyqt().setPreferenceProperty(item, "ids", values)

        # Add spacing
        _addSpacing("1", gid)

        # Workspace tab pages position
        title = translate("PrefDlg", "Workspace tab pages position")
        item = get_salome_pyqt().addPreference(title,
                                               gid,
                                               SalomePyQt.PT_Selector,
                                               AsterSalomeGui.NAME,
                                               "workspace_tab_position")
        values = []
        values.append(translate("PrefDlg", "North"))
        values.append(translate("PrefDlg", "South"))
        values.append(translate("PrefDlg", "West"))
        values.append(translate("PrefDlg", "East"))
        get_salome_pyqt().setPreferenceProperty(item, "strings", values)
        values = ["north", "south", "west", "east"]
        get_salome_pyqt().setPreferenceProperty(item, "ids", values)

        # Add spacing
        _addSpacing("2", gid)

        # Strict import mode
        title = translate("PrefDlg", "Strict import mode")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "strict_import_mode")

        # Warn for number of lines
        title = translate("PrefDlg",
                          "Limit of number of lines for graphical mode")
        item = get_salome_pyqt().addPreference(title, gid,
                                               SalomePyQt.PT_IntSpin,
                                               AsterSalomeGui.NAME,
                                               "nblines_limit")
        get_salome_pyqt().setPreferenceProperty(item, "min", 1)
        get_salome_pyqt().setPreferenceProperty(item, "max", 100000)

        # Add spacing
        _addSpacing("3", gid)

        # Switch on/off Undo/Redo feature
        title = translate("PrefDlg", "Disable Undo/Redo feature")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "disable_undo_redo")

        _addSpacing("3a", gid)

        # Use CodeAster native naming
        # (switch off business-oriented translation)
        title = translate("PrefDlg",
                          "Use business-oriented translations")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "use_business_translations")

        _addSpacing("3b", gid)

        # Documentation url
        title = translate("PrefDlg", "Documentation website")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_String,
                                        AsterSalomeGui.NAME,
                                        "doc_base_url")

        # --- end of 'General' page

        # 'Interface' page
        title = translate("PrefDlg", "Interface")
        gid = get_salome_pyqt().addPreference(title)

        # *** Data Settings

        # Show catalogue name in Data Settings panel
        title = translate("PrefDlg",
                          "Show catalogue name in Data Settings panel")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "show_catalogue_name")

        # Show comments in Data Settings panel
        title = translate("PrefDlg",
                          "Show comments in Data Settings panel")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "show_comments")

        # Enable auto-hide feature for search tool in Data Settings panel
        title = translate("PrefDlg", "Auto-hide search panel")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "auto_hide_search")

        # Add spacing
        _addSpacing("4", gid)

        # *** Data Files

        # Sort stages in Data Files panel
        title = translate("PrefDlg",
                          "Sort stages in Data Files panel")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "sort_stages")

        # Show related concepts in Data Files panel
        title = translate("PrefDlg",
                          "Show related concepts in Data Files panel")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "show_related_concepts")

        # Join similar files in Data Files panel
        title = translate("PrefDlg",
                          "Join similar data files in Data Files panel")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "join_similar_files")

        # Add spacing
        _addSpacing("5", gid)

        # *** Operations

        # Auto-edit command
        title = translate("PrefDlg", "Automatically activate command edition")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "auto_edit")

        # Add spacing
        _addSpacing("6", gid)

        # *** Windows

        # Show read-only banner
        title = translate("PrefDlg", "Show read-only banner")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "show_readonly_banner")

        # Add spacing
        _addSpacing("7", gid)

        # *** Parameter panel

        # Content label mode
        title = translate("PrefDlg", "Parameter content display mode")
        item = get_salome_pyqt().addPreference(title,
                                               gid,
                                               SalomePyQt.PT_Selector,
                                               AsterSalomeGui.NAME,
                                               "content_mode")
        values = []
        values.append(translate("PrefDlg", "None"))
        values.append(translate("PrefDlg", "Parameters"))
        values.append(translate("PrefDlg", "Keywords"))
        values.append(translate("PrefDlg", "Values"))
        get_salome_pyqt().setPreferenceProperty(item, "strings", values)
        values = ["none", "parameters", "keywords", "values"]
        get_salome_pyqt().setPreferenceProperty(item, "ids", values)

        # Show tooltip for 'into' items
        title = translate("PrefDlg", "Show identifier for selector items")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "show_selector_value")

        # Sort selector items in Parameters panel
        title = translate("PrefDlg", "Sort selector items")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "sort_selector_values")

        # Show catalogue name for command selector items
        title = translate("PrefDlg",
                          "Show catalogue name in command selector items")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "show_catalogue_name_in_selectors")

        # External list
        title = translate("PrefDlg", "Edit list-like keywords in sub-panel")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "external_list")

        # Add spacing
        _addSpacing("8", gid)

        # *** Other features

        # Allow delete case used by other case(s)
        title = translate("PrefDlg",
                          "Allow deleting cases used by other case(s)")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "allow_delete_cases")

        # --- end of 'Interface' page

        # 'Editor' page
        title = translate("PrefDlg", "Editor")
        gid = get_salome_pyqt().addPreference(title)

        # - External editor
        title = translate("PrefDlg", "External editor")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_File,
                                        AsterSalomeGui.NAME,
                                        "external_editor")

        # Add spacing
        _addSpacing("9", gid)

        # Use external editor for text stage
        title = translate("PrefDlg",
                          "Use external editor for text stage edition")
        get_salome_pyqt().addPreference(title, gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "use_external_editor_stage")

        # Use external editor for data files edition
        title = translate("PrefDlg",
                          "Use external editor for data files edition")
        get_salome_pyqt().addPreference(title, gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "use_external_editor_data_file")

        # Use external editor for message files viewing
        title = translate("PrefDlg",
                          "Use external editor for message files viewing")
        get_salome_pyqt().addPreference(title, gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "use_external_editor_msg_file")

        # Add spacing
        _addSpacing("10", gid)

        # Warn for file's size limit
        title = translate("PrefDlg", "Warn when viewing file larger than")
        item = get_salome_pyqt().addPreference(title, gid,
                                               SalomePyQt.PT_IntSpin,
                                               AsterSalomeGui.NAME,
                                               "file_size_limit")
        get_salome_pyqt().setPreferenceProperty(item, "min", 1)
        get_salome_pyqt().setPreferenceProperty(item, "max", 100000)
        get_salome_pyqt().setPreferenceProperty(item, "suffix", str(" KB"))

        # --- end of 'Editor' page

        # 'Confirmations' page
        title = translate("PrefDlg", "Confirmations")
        gid = get_salome_pyqt().addPreference(title)

        # - Delete object
        title = translate("PrefDlg", "Delete object")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "msgbox_delete")

        # - Undefined files
        title = translate("PrefDlg", "Undefined files")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "msgbox_undefined_files")

        # - Break operation
        title = translate("PrefDlg", "Break current operation")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "msgbox_break")

        # - Delete case used by other case(s)
        title = translate("PrefDlg", "Delete case used by other case(s)")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "msgbox_delete_case")

        # - Delete child stages
        title = translate("PrefDlg", "Delete child stages")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "msgbox_delete_stages")

        # - Convert invalid graphical stage
        title = translate("PrefDlg", "Convert invalid graphical stage")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "msgbox_convert_invalid_graphic_stage")

        # - Close the parameter panel
        title = translate("PrefDlg", "Close parameter panel "
                          "with modifications")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "msgbox_parampanel_close")

        # - Abort the parameter panel
        title = translate("PrefDlg", "Abort command edition")
        get_salome_pyqt().addPreference(title,
                                        gid,
                                        SalomePyQt.PT_Bool,
                                        AsterSalomeGui.NAME,
                                        "msgbox_parampanel_abort")

        # --- end of 'Confirmations' page

        if hasattr(SalomePyQt, 'UserDefinedContent'):
            from gui.widgets.dirwidget import DirWidget

            # 'Catalogs' page
            title = translate("PrefDlg", "Catalogs")
            gid = get_salome_pyqt().addPreference(title)

            # User's catalogs
            title = translate("PrefDlg", "User's catalogs")
            sgid = get_salome_pyqt().addPreference(title, gid)
            item = get_salome_pyqt().addPreference('',
                                                   sgid,
                                                   SalomePyQt.PT_UserDefined,
                                                   AsterSalomeGui.NAME,
                                                   "user_catalogs")
            widget = DirWidget.instance()
            get_salome_pyqt().setPreferencePropertyWg(item, "content", widget)

            # --- end of 'Catalogs' page

    def preferenceChanged(self, section, name):
        """
        Called when preferences item is changed in Preferences dialog.

        Arguments:
            section (str): Resource section's name.
            name (str): Resource parameter's name.
        """
        has_changes = False

        if section == AsterSalomeGui.NAME:
            has_changes = True
            self.from_preferences() # re-initialize behavior from preferences
            if name == "workspace_tab_position":
                if self.work_space is not None:
                    tbposition = behavior().workspace_tab_position
                    self.work_space.setTabPosition(tab_position(tbposition))
            elif name in ("use_business_translations", "content_mode"):
                self.updateTranslations()
            elif name == "sort_stages":
                self.workSpace().view(Context.DataFiles).resort()
            elif name in ("show_related_concepts", "join_similar_files"):
                self.workSpace().view(Context.DataFiles).update()
            elif name in ("show_catalogue_name", "show_comments"):
                self.workSpace().view(Context.DataSettings).update()
            elif name == "auto_hide_search":
                view = self.workSpace().view(Context.DataSettings)
                view.setAutoHideSearch(behavior().auto_hide_search)
            elif name == "show_readonly_banner":
                self._updateWindows()

        elif section == "PyEditor":
            has_changes = True

        if has_changes:
            self.preferencesChanged.emit(self.preferencesMgr())

    def activate(self):
        """Activate AsterStudy GUI."""
        if int(os.getenv("ASTER_NO_EXCEPTHANDLER", 0)) == 0:
            enable_except_hook(True)
        enable_salome_actions(False)
        view = get_salome_pyqt().findViews(get_aster_view_type())
        if view:
            get_salome_pyqt().setViewVisible(view[0], True)
        else:
            self.work_space = self._createWorkspace(self.main_window)
            view = get_salome_pyqt().createView(get_aster_view_type(),
                                                self.work_space)
            get_salome_pyqt().setViewClosable(view, False)
            get_salome_pyqt().setViewTitle(view, translate("AsterStudy",
                                                           "Aster workspace"))

        reactivate = False
        if self.study() is None:
            chosen_version = self.chooseVersion()
            if not chosen_version:
                return False
            self._setStudy(Study(self, version=chosen_version))
            reactivate = True

        self._connectWorkspace()

        self.work_space.activate(True)
        if hasattr(get_salome_pyqt(), "createRoot"):
            get_salome_pyqt().createRoot()
        else:
            children = get_salome_pyqt().getChildren()
            if not children:
                get_salome_pyqt().createObject()
        self.update()

        # activate mesh view last
        self.work_space.panels[Panel.View].activate()
        if reactivate:
            self.workSpace().setWorkingMode(WorkingMode.CaseMode)

        return True

    def deactivate(self):
        """Deactivate AsterStudy GUI."""
        if self.work_space:
            self.work_space.activate(False)
        view = get_salome_pyqt().findViews(get_aster_view_type())
        if view:
            get_salome_pyqt().setViewVisible(view[0], False)
        if int(os.getenv("ASTER_NO_EXCEPTHANDLER", 0)) == 0:
            enable_except_hook(False)
        enable_salome_actions(True)

    def save(self, directory, url):
        """
        Save module data to files; returns file names.

        The function saves the module data to the files in a temporary
        directory specified as a parameter and returns names if files in
        which module data is saved.

        Arguments:
            directory (str): A directory to store data files. Note: this
                can be not a final study destination folder but a
                temporary directly, depending on used save mode
                (single-file or multi-file).

            url (str): Actual study URL (the final study destination).
                Note: this parameter is provided for information
                purposes only! Depending on version of SALOME being used
                this parameter may be empty!

        Returns:
            list[str]: names of files in which data is saved
        """
        try:
            study_name = get_salome_pyqt().getStudyName() + "_"
        except AttributeError:
            study_name = get_base_name(url, False) + "_" if url else ""
        ajs = "{}asterstudy.{}".format(study_name, study_extension())
        path = os.path.join(directory, ajs)
        debug_message("salomegui.save(): ajs: {0}, url: {1}".format(ajs, url))
        self.study().set_url(url)
        try:
            self.study().saveAs(path)
        except IOError:
            ajs = ""
        self._updateActions()
        files = [to_str(ajs)]
        files.extend(self.study().history.save_embedded_files(directory))
        return files

    def load(self, files, url):
        """
        Load data from the files; return result status.

        The function restores module data from the files specified as a
        parameter; returns *True* in case of success or *False*
        otherwise.

        Arguments:
            files (list[str]): Data files in which module data is
                stored. Note: first element of this list is a directory
                name. File names are normally specified as relative to
                this directory.

            url (str): Actual study URL (the original study file path).
                Note: this parameter is provided for information
                purposes only! Depending on version of SALOME being used
                this parameter may be empty!

        Returns:
            bool: *True* in case of success; *False* otherwise
        """
        debug_message("salomegui.load(): url: {0}, files: {1}"
                      .format(url, files))
        # do nothing if url is empty
        if not url:
            return False
        try:
            ajs = os.path.join(files[0], files[1])
            self._setStudy(Study.load(self, ajs, url))
            self.study().set_url(url)
            self.study().loadEmbeddedFilesWrapper(files[0], files[2:])
            return True
        except IOError:
            pass
        return False

    def close(self):
        """Clean-up data model to handle study closure."""

        # delete directory with embedded files
        if self.study():
            self.study().history.clean_embedded_files()

        self._setStudy(None)
        if self.work_space:
            workspace_state = self.work_space.saveState()
            try:
                self.preferencesMgr().setValue("workspace_state",
                                               workspace_state)
            except TypeError:
                pass
        self.work_space = None

    def hasParavis(self):
        """Reimplemented from AsterGui."""
        try:
            import salome
            return salome.sg.getComponentUserName(str('PARAVIS')) is not None
        except (ImportError, AttributeError):
            pass
        return False

    def openInParavis(self):
        """Reimplemented from AsterGui."""
        selected = self.selected(Context.DataFiles)
        if check_selection(selected, size=1, typeid=NodeType.Unit):
            node = self.study().node(selected[0])

            if node.filename is None:
                return

            if not os.path.exists(node.filename):
                message = translate("AsterStudy", "File '{}' does not exist.")
                message = message.format(node.filename)
                Q.QMessageBox.critical(self.mainWindow(), "AsterStudy",
                                       message)
                return

            # activate PARAVIS module
            import salome
            paravis = salome.sg.getComponentUserName(str('PARAVIS'))
            get_salome_pyqt().activateModule(str(paravis))

            # import MED file with MEDReader, create and show presentation
            from pvsimple import MEDReader, GetActiveViewOrCreate, Show
            proxy = MEDReader(FileName=node.filename)
            view = GetActiveViewOrCreate('RenderView')
            Show(proxy, view)
            view.ResetCamera()

    def createMeshView(self, parent=None):
        """Reimplemented from AsterGui."""
        no_mesh_view = behavior().no_mesh_view
        return MeshView(parent) if not no_mesh_view and \
            hasattr(get_salome_pyqt(), 'getViewWidget') \
            else MeshBaseView(parent)

    def _createMainWindow(self):
        """Initialize main window of application."""
        self.main_window = get_salome_pyqt().getDesktop()

    def _updateActions(self):
        """Update state of actions, menus, toolbars, etc."""
        AsterGui._updateActions(self)

        has_study = self.study() is not None
        is_modified = has_study and self.study().isModified()
        get_salome_pyqt().setModified(is_modified)

    def autosave(self):
        """Calls SALOME save mechanism"""

        # disable pylint, `salome` module only known within salome python shell
        import salome # pragma pylint: disable=import-error
        salome.salome_init() # necessary or not?
        salome.myStudyManager.Save(salome.myStudy, False)
