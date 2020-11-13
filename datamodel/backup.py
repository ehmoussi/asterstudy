# -*- coding: utf-8 -*-

# Copyright 2016 - 2017 EDF R&D
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
**Backup utility**

In case of failure in SALOME, the study content is often lost.
This module backups at least the stages and the list of datafiles for the
current case.

The study is backup each time *Save* feature is called into the directory
``$HOME/.asterstudy/backup``.

*The previous backup is available in* ``$HOME/.asterstudy/backup.1``, *and*
``backup.2``... *up to* ``backup.10``.

A backup can be restored by importing ``backup.export`` through menu
*Operations/Import Case*.

"""
from __future__ import unicode_literals

from functools import wraps
import os
import os.path as osp

from common import is_reference, rotate_path, to_str
from .general import FileAttr


def never_fails(method):
    """Decorator that ensures a method never fails and skipped if *path* is
    not defined."""
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        """Wrapper"""
        if not self.path:
            return
        try:
            return method(self, *args, **kwargs)
        except: # pragma pylint: disable=bare-except
            pass
    return wrapper


class BackupHistory(object):
    """Object to backup an History during serialization."""

    _path = _comm = _files = None

    def __init__(self, root=None, _unittest=False):
        """Initializations"""
        if os.getenv("ASTERSTUDYTST", "") and not _unittest:
            return
        root = root or os.getenv("HOME", "")
        path = osp.join(root, ".asterstudy", "backup")
        if osp.exists(path):
            rotate_path(path, count=10)
        try:
            os.makedirs(path)
        except OSError:
            path = None
        self._path = path
        self._comm = []
        self._files = []

    @property
    def path(self):
        """str: Attribute that holds the path value."""
        return self._path

    @never_fails
    def save_stage(self, stage, text):
        """Save the text representation of a Stage."""
        name = "{0.name}_{0.number}".format(stage)
        filename = name + '.comm'
        self._comm.append(filename)
        with open(osp.join(self.path, filename), 'wb') as fobj:
            fobj.write(to_str(text))

    @never_fails
    def add_file(self, filename, unit, attr):
        """Save usage of a file."""
        if not is_reference(filename):
            self._files.append([filename, unit, attr])

    @never_fails
    def end(self):
        """End of the backup."""
        # write an export file
        lines = []
        fmt = "F comm {0} D 1"
        for name in self._comm:
            lines.append(fmt.format(name))
        fmt = "F libr {0} {2} {1}"
        for infos in self._files:
            attr = infos[2]
            infos[2] = ''
            if attr & FileAttr.In:
                infos[2] += 'D'
            if attr & FileAttr.Out:
                infos[2] += 'R'
            lines.append(fmt.format(*infos))
        lines.append('')
        with open(osp.join(self.path, "backup.export"), 'wb') as fobj:
            fobj.write(os.linesep.join(lines))
