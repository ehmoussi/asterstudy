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
Unit model
----------

Implementation of the unit model to deal with *UNITE* keywords.

"""

from __future__ import unicode_literals

import os
from collections import OrderedDict

from PyQt5 import Qt as Q

from common import (copy_file, external_files, external_file, move_file,
                    translate)
from . import Role

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class UnitModel(Q.QAbstractItemModel):
    """Unit model."""

    def __init__(self, file_descriptors, file_format=None):
        """
        Create model.

        Arguments:
            file_descriptors: File descriptors proxy object.
            file_format (Optional[str]): File format. Defaults to
                *None*.
        """
        super(UnitModel, self).__init__()
        self._file_descriptors = file_descriptors

        self._units2file = OrderedDict()
        self._units2stat = OrderedDict()
        self._emb2ext = OrderedDict()
        self._ext2emb = OrderedDict()
        self._extfiles = {}

        file_dict = {}
        for handle, info in self._file_descriptors.handle2info.viewitems():
            self._units2file[handle] = info.filename
            self._units2stat[handle] = info.embedded
            file_dict[info.filename] = handle

        unit = -10
        for fileuid in external_files(file_format):
            filename = external_file(fileuid)
            if not filename:
                continue
            self._extfiles[fileuid] = filename
            if fileuid in file_dict:
                continue
            self._units2file[unit] = fileuid
            unit = unit - 1

    def file2unit(self, filename, udefault=None, umin=None, umax=None):
        """Get unit for given file."""
        return self._file_descriptors.file2unit(filename, udefault, umin, umax)

    def addItem(self, filename, udefault=None, umin=None, umax=None):
        """
        Add item to model and units dictionary.

        Arguments:
            filename (str): File name.
            udefault (Optional[int]): Default file descriptor value.
                Defaults to *None*.
            umin (Optional[int]): Minimum file descriptor value.
                Defaults to *None*.
            umax (Optional[int]): Maximum file descriptor value.
                Defaults to *None*.

        Returns:
            int: File descriptor.

        Raises:
            ValueError: if unit can not be registered in [min, max]
            range.

        Note:
            For now, items are always added as external files.
        """
        self.beginInsertRows(Q.QModelIndex(), 0, 0)

        unit = self.file2unit(filename, udefault, umin, umax)

        self._units2file[unit] = filename

        self.endInsertRows()
        return unit

    def rowCount(self, parent=Q.QModelIndex()):
        """
        Get number of rows.

        Arguments:
            parent (Optional[QModelIndex]): Parent model index. Defaults
                to invalid model index.

        Returns:
            int: Rows count.
        """
        if parent.isValid():
            return 0

        return len(self._units2file)

    # pragma pylint: disable=unused-argument, no-self-use
    def columnCount(self, parent=Q.QModelIndex()):
        """
        Get number of columns.

        Arguments:
            parent (Optional[QModelIndex]): Parent model index. Defaults
                to invalid model index.

        Returns:
            int: Columns count.
        """
        return 1

    def index(self, row, column, parent=Q.QModelIndex()):
        """
        Get model index for given *row* *column* and *parent*.

        Arguments:
            row (int): Row index.
            column (int): Column index.
            parent (Optional[QModelIndex]): Parent model index. Defaults
                to invalid model index.

        Returns:
            QModelIndex: Corresponding model index.
        """
        return self.createIndex(row, column) if \
            self.hasIndex(row, column, parent) else Q.QModelIndex()

    def data(self, index, role=Q.Qt.DisplayRole):
        """
        Get data stored by model index for given role.

        Arguments:
            index (QModelIndex): Model index.
            role (Optional[int]): Role of the data. Defaults to
                *Qt.DisplayRole*.

        Returns:
            any: Data stored by model index.
        """
        # pragma pylint: disable=too-many-branches
        value = None
        if index.isValid():
            unit = self._units2file.keys()[index.row()]
            filename = None if unit == -1 else self._units2file[unit]

            if role in (Role.IdRole,):
                value = unit

            elif role in (Role.ValidityRole,):
                if unit == -1:
                    value = False
                else:
                    if filename in self._extfiles:
                        value = self._extfiles.get(filename) is not None
                    else:
                        value = filename is not None

            elif role in (Role.ReferenceRole,):
                if unit == -1:
                    value = False
                else:
                    value = filename in self._extfiles

            elif role in (Q.Qt.DisplayRole, Q.Qt.EditRole, Q.Qt.ToolTipRole,
                          Role.CustomRole):
                undefstr = translate("DataFiles", "undefined")
                embedstr = translate("DataFiles", "embedded")

                if unit == -1:
                    value = "<{}>".format(undefstr) # pragma pylint: disable=redefined-variable-type

                else:
                    if filename in self._extfiles:
                        # for external files 'filename' is its UID
                        if role in (Q.Qt.DisplayRole, Q.Qt.EditRole):
                            value = self._extfiles.get(filename)
                        elif role in (Q.Qt.ToolTipRole,):
                            value = self._extfiles.get(filename) + \
                                " ({})".format(filename)
                        else: # Role.CustomRole
                            value = filename
                    else:
                        if role in (Q.Qt.DisplayRole, Q.Qt.EditRole):
                            if filename is not None:
                                state = self._units2stat.get(unit, False)
                                value = os.path.basename(filename)
                                if state:
                                    value = value + " ({})".format(embedstr)
                            else:
                                value = undefstr
                                if unit is not None:
                                    value = "{} ".format(unit) + value
                                value = "<{}>".format(value)
                        else: # Qt.ToolTipRole, Role.CustomRole
                            value = filename
        return value

    # pragma pylint: disable=unused-argument, no-self-use
    def parent(self, index):
        """
        Get parent model index for the given one.

        Arguments:
            index (QModelIndex): Model index.

        Returns:
            QModelIndex: Parent model index.
        """
        return Q.QModelIndex()

    def emb2ext(self, embname, extname):
        """
        Unembed file from the study.

        Arguments:
            embname (str): Source path for embedded data file.
            extname (str): Destination path to put the file to.

        Returns:
            str: New file path (external).

        Raises:
            ValueError: If external file name is already in use (except
                when it is a back conversion).
        """
        return self._conversionTemplate(embname,
                                        lambda _: extname,
                                        self._ext2emb,
                                        self._emb2ext,
                                        False)

    def ext2emb(self, extname):
        """
        Embed file to the study.

        Arguments:
            extname (str): Source path of the data file.

        Returns:
            str: New file path (embedded).

        Raises:
            ValueError: If internal file name is already in use (except
                when it is a  back conversion).
        """
        return self._conversionTemplate(extname,
                                        self._file_descriptors.ext2emb,
                                        self._emb2ext,
                                        self._ext2emb,
                                        True)

    def _conversionTemplate(self,
                            oldname,
                            gen_newname,
                            register,
                            unregister,
                            newstate):
        """
        Template for converting file from embedded to external and back.

        Arguments:
            oldname (str): Source file path.
            gen_newname (function): Used to generate new file path.
            register (dict): Dictionary where to register the resulting
                conversion.
            unregister (dict): Dictionary where to unregister a previous
                conversion.
            newstate (bool): New embedded state flag.

        Returns:
            str: New file path.

        Raises:
            ValueError: If new file path is already in use under another
                entry.
        """
        [unit] = [k for k, v in self._units2file.iteritems() if v == oldname]

        oldstate = self._units2stat.get(unit, False)
        if oldstate == newstate:
            return oldname

        newname = gen_newname(oldname)

        # if not a back conversion
        if oldname not in unregister:
            # error if the name already exists
            if newname in self._units2file.viewvalues():
                errmsg = translate("DataFiles",
                                   "File {0} is already in use elsewhere in "
                                   "the study. It cannot be reused under a "
                                   "different file entry.").format(newname)
                raise ValueError(errmsg)

            # register
            register[newname] = oldname

        # unregister if a back conversion
        if oldname in unregister:
            unregister.pop(oldname)

        # replace the old name by the new one in the dictionary
        self._units2file[unit] = newname
        self._units2stat[unit] = newstate
        self.modelReset.emit()

        return newname

    def transferFile(self, filename):
        """
        Called at register time when an external file is embedded
        / unembedded.

        Argument:
            filename (str): File path in its new status.

        Note:
            - From external to embedded, the file is copied.
            - From embedded to external, the file is moved.
        """
        if filename in self._ext2emb:
            assert filename not in self._emb2ext
            move_file(self._ext2emb[filename], filename)
            return

        if filename in self._emb2ext:
            assert filename not in self._ext2emb
            copy_file(self._emb2ext[filename], filename)

    def other_unit_search(self, filename):
        """
        Looks for `filename` among child and parent stages,
        but not the current stage.

        Arguments:
            filename (str): full path of the file.

        Returns:
            int: logical unit of the file if found, else *None*.
        """
        return self._file_descriptors.other_unit_search(filename)

    def unit_conflict(self, unit, filename):
        """
        Looks for a unit conflict in parent and child stages,
        i.e. two files sharing the same unit.

        Arguments:
            unit (int): logical unit to test.
            filename (str): full file path to test.

        Returns:
            bool: *True* if there is no conflict, *False* otherwise.
        """
        return self._file_descriptors.unit_conflict(unit, filename)

    def file_conflict(self, unit, filename):
        """
        Looks for a file conflict in parent and child stages,
        i.e. two different units sharing the same file.

        Arguments:
            unit (int): logical unit to test.
            filename (str): full file path to test.

        Returns:
            bool: *True* if there is no conflict, *False* otherwise.
        """
        return self._file_descriptors.file_conflict(unit, filename)

    def basename_conflict(self, filename):
        """
        Looks for a basename conflict, i.e. a file with the same
        basename in the current stage.

        Arguments:
            filename (str): file path.

        Note:
            Due to Salome launcher not supporting two files with
            the same basename, we have to forbide it for two files
            of the same stage.
        """
        return self._file_descriptors.basename_conflict(filename)
