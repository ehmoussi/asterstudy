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
File Model's objects
--------------------

Specific data objects maintained by 'Data Files' panel.

"""

from __future__ import unicode_literals
import os
import shutil

from common import (auto_dupl_on, external_file, get_extension, is_reference,
                    is_subpath)
from datamodel import Info

__all__ = ["Directory", "File"]


class Directory(object):
    """Represents directory object."""

    InDir = 0
    OutDir = 1

    DirType = None

    def __init__(self, case, dir_type):
        """
        Create directory object.

        Arguments:
            case (Case): Parent case.
            dir_type (int): Directory type: Directory.InDir (0) for
                input directory or Directory.OutDir (1) for output
                directory.
        """
        self.case = case
        self.dir_type = dir_type

    @property
    def directory(self):
        """
        Get directory path.

        Returns:
            str: Directory path.
        """
        return self.case.in_dir if self.dir_type == Directory.InDir \
            else self.case.out_dir

    @directory.setter
    def directory(self, directory):
        """Setter for 'directory' property."""
        with auto_dupl_on(self.case):
            if self.dir_type == Directory.InDir:
                self.case.in_dir = directory
            else:
                self.case.out_dir = directory

    @property
    def deletable(self):
        """
        Check if directory can be deleted.

        Returns:
            bool: *True* if directory can be deleted; *False* otherwise.
        """
        return True

    def delete(self, delete_files=False):
        """
        Remove directory from study.

        Arguments:
            delete_files (Optional[bool]): Forces removal of related
                data files from study. Defaults to *False*.
        """
        directory = self.directory
        if directory is None:
            return
        with auto_dupl_on(self.case):
            if self.dir_type == Directory.InDir:
                self.case.in_dir = None
            else:
                self.case.out_dir = None
            if delete_files:
                for stage in self.case.stages:
                    if stage.is_graphical_mode():
                        continue
                    units = stage.handle2info.keys()
                    for unit in units:
                        file_obj = File(stage, unit)
                        if is_subpath(file_obj.filename, directory):
                            file_obj.delete()

    @property
    def removable(self):
        """
        Check if directory can be removed from disk.

        Returns:
            bool: *True* if directory can be removed; *False* otherwise.
        """
        return self.dir_type == Directory.OutDir

    def remove(self, keep_in_study=True):
        """
        Remove directory with all contents from disk.

        Arguments:
            keep_in_study[bool]): Forces keeping of related data files
                in the study. Defaults to *True*.
        """
        directory = self.directory
        if directory is None:
            return
        if not os.path.isdir(directory):
            return
        if not keep_in_study:
            self.delete(delete_files=True)
        shutil.rmtree(directory)


class FileEntry(object):
    """
    Single data entry within *File* object, to store *stage*/*unit*
    couple.
    """

    def __init__(self, stage, unit):
        """Create record for given *stage* and *unit*."""
        self.stage = stage
        self.unit = unit

    @property
    def filename(self):
        """Attribute that stores entry's filename."""
        return self.stage.handle2file(self.unit)

    @property
    def exists(self):
        """Attribute that stores entry's filename."""
        return self.stage.handle2info[self.unit].exists


class File(object):
    """Represents Data file object."""

    UID = -1

    def __init__(self, stage=None, unit=-1):
        """
        Create file object.

        If *stage* and *unit* parameters are specified, the object
        contains single data entry; otherwise object is created with
        empty list of entries.

        Entries should store the same unit for all stages.

        Arguments:
            stage (Optional[Stage]): Stage object. Defaults to *None*.
            unit (Optional[int]): Data file's UID. Defaults to -1.
        """
        self.entries = []
        self.uid = File.UID
        File.UID = File.UID - 1
        if stage is not None and unit is not None:
            self.add_entry(stage, unit)
        self.forced_attr = None

    def add_entry(self, stage, unit):
        """Add file unit entry for given *stage* and *unit*."""
        for entry in self.entries:
            if entry.stage == stage and entry.unit == unit:
                return # don't re-add the same entry
            assert entry.unit == unit # error: different units
        self.entries.append(FileEntry(stage, unit))

    @property
    def deletable(self):
        """
        Check if file object can be removed.

        Returns:
            bool: *True* if file can be removed; *False* otherwise.
        """
        can_delete = True
        for entry in self.entries:
            can_delete = can_delete and entry.stage.is_text_mode()
        return can_delete

    def delete(self):
        """Remove data file from study."""
        unit = self.unit
        if unit is None:
            return
        for entry in self.entries:
            handle2info = entry.stage.handle2info
            if handle2info is not None and unit in handle2info:
                del handle2info[unit]

    @property
    def stage(self):
        """
        Get stage owning file entry.

        Returns:
            Stage: Parent stage; *None* if 0 or more than one entries
            are referenced by the object.
        """
        return self.entries[0].stage if len(self.entries) > 0 else None

    @property
    def stages(self):
        """
        Get stage which refer to this file entry.

        Returns:
            list[Stage]: Parent stages
        """
        return [i.stage for i in self.entries]

    @property
    def unit(self):
        """
        Get file entry's unit.

        Returns:
            int: File's unit; *None* if there are no entries stored.
        """
        return self.entries[0].unit if len(self.entries) > 0 else None

    @unit.setter
    def unit(self, unit):
        """Setter for 'unit' property."""
        assert len(self.entries) > 0
        for entry in self.entries:
            stage = entry.stage
            with auto_dupl_on(stage.parent_case):
                info = None
                if entry.unit in stage.handle2info:
                    info = stage.handle2info.pop(entry.unit)
                else:
                    info = Info(stage)
                stage.handle2info[unit] = info
                entry.unit = unit

    @property
    def filename(self):
        """
        Get file entry's filename.

        Returns:
            str: File's path; *None* if there are no entries stored.
        """
        return self.entries[0].filename if len(self.entries) > 0 else None

    @filename.setter
    def filename(self, filename):
        """Setter for 'filename' property."""
        assert len(self.entries) > 0
        for entry in self.entries:
            stage = entry.stage
            with auto_dupl_on(stage.parent_case):
                info = stage.handle2info[self.unit]
                info.filename = filename

    @property
    def attr(self):
        """
        Get file object's in/out attribute.

        Returns:
            int: Cumulative in/out attribute; *None* if 0 or more
            than one entries are referenced by the object.
        """
        if self.is_forced_attr:
            return self.forced_attr
        return self.entries[0].stage.handle2info[self.unit].attr \
            if len(self.entries) == 1 else None

    @property
    def is_repeated(self):
        """Returns *True* when the file is reapeated in another stage."""
        mystage = self.entries[0].stage
        return mystage.handle2info[self.unit].is_repeated(mystage)

    @property
    def is_forced_attr(self):
        """Check if 'attr' is forced (by input/output directory)."""
        return self.forced_attr is not None

    @attr.setter
    def attr(self, attr):
        """Setter for 'attr' property."""
        assert len(self.entries) > 0
        for entry in self.entries:
            stage = entry.stage
            with auto_dupl_on(stage.parent_case):
                info = stage.handle2info[self.unit]
                info.attr = attr

    @property
    def exists(self):
        """
        Get file object's 'exists' attribute.

        Returns:
            bool: *True* if file exists; *False* otherwise.
        """
        return self.entries[0].exists if len(self.entries) > 0 else None

    @property
    def embedded(self):
        """
        Get file descriptor's 'embedded' attribute.

        Returns:
            bool: *True* if file is embedded; *False* otherwise.
        """
        if self.is_forced_attr:
            return None
        return self.entries[0].stage.handle2info[self.unit].embedded \
            if len(self.entries) == 1 else None

    @embedded.setter
    def embedded(self, embedded):
        """Setter for 'embedded' property."""
        assert len(self.entries) > 0
        for entry in self.entries:
            stage = entry.stage
            with auto_dupl_on(stage.parent_case):
                info = stage.handle2info[self.unit]
                info.embedded = embedded

    @property
    def is_reference(self):
        """
        Get file descriptor's 'isreference' attribute.

        Returns:
            bool: *True* if file is a reference to SALOME study object;
            *False* otherwise.
        """
        return is_reference(self.filename)

    @property
    def valid(self):
        """
        Check if file object is valid.

        Returns:
            bool: *True* if file is valid; *False* otherwise.
        """
        return external_file(self.filename) is not None if self.is_reference \
            else self.filename is not None

    @property
    def for_editor(self):
        """Check if file object can be viewed in an editor."""
        return self.valid and not self.is_reference and self.exists \
            and get_extension(self.filename) not in ("med", "rmed", "mmed")

    @property
    def for_paravis(self):
        """Check if file object can be viewed in an editor."""
        return self.valid and not self.is_reference and self.exists \
            and get_extension(self.filename) in ("med", "rmed", "mmed")
