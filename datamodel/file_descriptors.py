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
File Descriptors
----------------

Implementation of the file descriptors management functionality.
"""

from __future__ import unicode_literals

import os.path as osp
import copy_reg
import types

from collections import defaultdict

from common import copy_file, is_reference, external_file
from .general import no_new_attributes
from .general import FileAttr
from .command import Command
from .command import NonConstStage as NonConst

def _pickle_method(method):
    """So that instance methods can support pickle."""

    # Uncomment below to extend to class methods
    #if method.im_self is None:
    #    return getattr, (method.im_class, method.im_func.func_name)
    #else:
    return getattr, (method.im_self, method.im_func.func_name)

# register a pickle method for methods
copy_reg.pickle(types.MethodType, _pickle_method)

def _unit_generate_helper(ulist, udefault, umin, umax):
    """
    Helper to file2unit, generates new unit.

    Arguments:
       ulist (list): list of taken units, cannot be reused.
       udefault (int): default logical unit.
       umin (int): lower bound for the generated unit.
       umax (int): upper bound for the generated unit.
    """
    unit = None

    if udefault is not None and \
        udefault not in ulist:
        unit = udefault
    elif umin is not None:
        unit = umin
    else:
        unit = 1

    while unit in ulist or unit in [0, 1, 6, 8, 9]:
        unit += 1
    if umax is not None and unit > umax:
        raise ValueError, "No available file descriptors."

    return unit

def _recursion(pars, chs, func, res, skip, *args):
    """
    Helper function to perform operation `func` recursively,
    on parent and children stages.

    Arguments:
        pars (list): parent *Stage* to explore.
        chs (list): list of children *Stage* to explore.
        func (function): operation to perform.
        res (list): *list* to populate recusively with results.
            For file search operations, may also be an *int*.
        skip (bool): discard results from the first iteration.
            Used to explore parent and child, but not the stage itself.
        args (list): any arguments to pass to `func`.
    """
    npars, nchs = [], []
    if skip:
        save = res[:] if isinstance(res, list) else res
    for par in pars:
        res = func(par, res, *args)
        if par.parent_stage is not None:
            npars = [par.parent_stage]
    for child in chs:
        res = func(child, res, *args)
        if child.child_stages:
            nchs += child.child_stages
    if skip:
        res = save
    if npars or nchs:
        res = _recursion(npars, nchs, func, res, False, *args)
    return res


class Info(object):
    "Keeps all Handle related information"

    _filename = _command2attrs = _imposed_attr = _embedded = None
    calling = None
    __setattr__ = no_new_attributes(object.__setattr__)

    def __init__(self, stage):
        self._filename = None
        self._command2attrs = defaultdict(set)
        self._imposed_attr = FileAttr.No
        self._embedded = False
        self.calling = stage

    def __mul__(self, other):
        """Support native Python '*' operator protocol."""
        assert self.filename == other.filename

        assert self.attr == other.attr

        assert self.embedded == other.embedded

    def copy_from(self, other):
        """Copy values from another object."""
        self._filename = other.filename
        # keep values of _command2attrs?
        self._imposed_attr = other.attr
        self._embedded = other.embedded

    @property
    def model(self):
        """History object to which this one is related"""
        return self.calling.model

    def split(self):
        """Splits associated stage"""
        return self.calling.split()

    @property
    def filename(self):
        "Returns file name for the given handle."
        return self._filename

    @filename.setter
    @NonConst(True)
    def filename(self, filename):
        "Sets file name for the given handle."
        self._filename = filename

    @property
    def attr(self):
        "Returns cumulative FileAttr value for the given handle."
        if not len(self._command2attrs):
            return self._imposed_attr

        result = FileAttr.No
        for attrs in self._command2attrs.viewvalues():
            for attr in attrs:
                result |= attr

        return result

    @attr.setter
    @NonConst(True)
    def attr(self, value):
        """Sets user's FileAttr value for the given handle."""
        self._imposed_attr = value

    @property
    def embedded(self):
        """Returns embedded state of the file."""
        return self._embedded

    @embedded.setter
    @NonConst(True)
    def embedded(self, value):
        """Sets embedded status for the file"""
        self._embedded = value

    @property
    def isreference(self):
        """
        Returns *True* if file is a reference to SALOME study object.
        """
        return is_reference(self.filename)

    @property
    def exists(self):
        """Returns file name presence in file system."""
        exists = False
        if self.filename:
            if self.isreference:
                sobj_name = external_file(self.filename)
                exists = sobj_name is not None
            else:
                exists = osp.isfile(self.filename)
        return exists

    @property
    def commands(self):
        """Get commands which refer to the file"""
        return sorted(self._command2attrs.keys())

    def clear(self):
        """
        Clear the info: removes all resgistered commands.
        """
        self._command2attrs.clear()

    def __contains__(self, given):
        """
        Support native Python "in" operator protocol.
        Checks the presence of command in command2attrs dict.

        Arguments:
            given (Command): Command being checked.

        Returns:
            bool: *True* if Command is contained in the dict;
            *False* otherwise.
        """
        return given in self._command2attrs

    def __getitem__(self, cmd):
        """
        Support native Python '[]' operator protocol.

        Arguments:
            cmd (Command): Key command object.

        Returns:
            attr for given command.
        """
        if isinstance(cmd, Command):
            return list(self._command2attrs[cmd])
        else:
            raise TypeError, "Invalid argument type."

    @NonConst(True)
    def __setitem__(self, cmd, attr):
        """
        Support native Python '[]' operator protocol.

        Arguments:
            cmd (Command): Key command object.
            attr (int): File attribute.
        """
        if isinstance(cmd, Command):
            self._command2attrs[cmd].add(attr)
            self._imposed_attr = self.attr
        else:
            raise TypeError, "Invalid argument type."

    @NonConst(True)
    def __delitem__(self, cmd):
        """
        Support native Python '[]' operator protocol.

        Arguments:
            cmd (Command): Key command object.
        """
        if isinstance(cmd, Command):
            del self._command2attrs[cmd]
        else:
            raise TypeError, "Invalid argument type."

    def __len__(self):
        """
        Support native Python 'len' operator protocol.

        Returns:
            int: Number of registered commands in info.
        """
        return len(self._command2attrs)

    def is_repeated(self, stage):
        """
        Test wether the file appears in another stage.

        Arguments:
            stage (Mixing) : stage the info objects belongs to.
        """
        return stage.other_unit_search(self.filename) is not None


class Mixing(object):
    """Encapsulates file descriptors management functionality"""

    _handle2info = None
    __setattr__ = no_new_attributes(object.__setattr__)

    def __init__(self):
        """
        Create Case.

        Arguments:
            name (str): Name of the Case.
        """
        self._handle2info = defaultdict(self.fact_info)

    def fact_info(self):
        """Workaround to have a pickable object."""

        return Info(self)

    def __mul__(self, other):
        """Support native Python '*' operator protocol."""
        lhandle2info = self.handle2info
        rhandle2info = other.handle2info

        assert set(lhandle2info) ^ set(rhandle2info) == set()

        for handle, linfo in lhandle2info.viewitems():
            rinfo = rhandle2info[handle]
            assert linfo * rinfo is None

    @property
    def handle2info(self):
        """dict[int, Info]: returns `unite` to `keyword` mapping."""
        return self._handle2info

    def handle2file(self, unit):
        """
        Returns file name for the given unit.

        Arguments:
            unit (int): Unit identifier.

        Returns:
            str: File name.
        """
        if unit not in self._handle2info:
            return None

        return self._handle2info[unit].filename

    def file2unit(self, filename, udefault=None, umin=None, umax=None):
        """
        Generates unique unite for the given filename.

        Arguments:
            filename (str): File name.
            add (bool): If True and 'filename' is not in the dictionary,
                then new record will be added.

        Returns:
            int: Unique (for this case) unit identifier.

        Note:
            To avoid conflicts between stages, files
            for parent and child stages are checked.
        """
        unit = self.unit_search(filename)
        if unit is not None:
            return unit
        unit = self.unit_generate(udefault, umin, umax)
        return unit

    def unit_search(self, filename):
        """
        Recursive search for a logical unit, in the current stage,
        its parents and children.

        Arguments:
            filename (str): full path of the file.

        Returns:
            int: logical unit of the file if found, *None* otherwise.
        """
        return _recursion([self],
                          [self],
                          Mixing.stage_unit_search,
                          None,
                          False,
                          filename)

    def other_unit_search(self, filename):
        """
        Recursive search for a file in parent and child stages,
        but not the stage itself.

        Arguments:
            filename (str): full path of the file.

        Returns:
            int: logical unit of the file if found, *None* otherwise.
        """
        return _recursion([self],
                          [self],
                          Mixing.stage_unit_search,
                          None,
                          True,
                          filename)

    def unit_conflict(self, unit, filename):
        """
        Recursive search for a unit conflict,
        i.e. two files sharing the same unit.

        Arguments:
            unit (int): logical unit to test.
            filename (str): full file path to test.

        Returns:
            bool: *True* if there is no conflict, *False* otherwise.
        """
        blist = _recursion([self],
                           [self],
                           Mixing._unit_conflict,
                           [], True,
                           unit, filename)
        return all(blist)

    def file_conflict(self, unit, filename):
        """
        Recursive search for a file conflict,
        i.e. two units sharing the same file.

        Arguments:
            unit (int): logical unit to test.
            filename (str): full file path to test.

        Returns:
            bool: *True* if there is no conflict, *False* otherwise.
        """
        res = self.other_unit_search(filename)
        return (res in (None, unit), res in (unit,))

    def unit_generate(self, udefault, umin, umax):
        """
        Recursive generation of a logical unit.

        Note:
            Gets all taken units in parent and child stages
            to avoid conflicts.
        """
        ulist = _recursion([self], [self], Mixing._taken_units, [], False)
        return _unit_generate_helper(ulist, udefault, umin, umax)

    def stage_unit_search(self, unit, filename):
        """
        Search for a file name among existing entries.

        Arguments:
            unit (int): value to return if `filename` is not found.
            filename (str): file name to search for.
        """
        for handle, info in self._handle2info.viewitems():
            if info.filename == filename:
                unit = handle
                break
        return unit

    def _taken_units(self, ulist):
        """
        Appends the logical units used in the current stage to `ulist`.
        """
        return list(set(ulist + self._handle2info.keys()))

    def _unit_conflict(self, blist, unit, fname):
        """
        Looks for a unit conflict in the current stage,
        i.e. two different files sharing the same unit.

        Arguments:
            blist (list<bool>): list where to append the result.
            unit (int): logical unit to test.
            fname (str): full path of the file to test.
        """
        blist.append(self.handle2file(unit) in (fname, None))
        return blist

    def ext2emb(self, filepath):
        """
        Generate a name for the embedded file.

        Arguments:
            filepath (str): file path when it used to be external.

        Returns:
            str: generated embedded file path.

        Note:
            Does not modify the data model.
        """
        return osp.join(self.model.tmpdir, osp.basename(filepath)) # pragma pylint: disable=no-member


    def parent_info(self, info):
        """
        Returns nearest similar file entry in parent stages, if any.

        Arguments:
            info (Info): file entry (Info object) to look for.

        Returns:
            Info: nearest *Info* object in parent stages with the same id.

        Note:
            Two *Info* objects are considered similar when they have
            the same `filename` (if external) or the same basename
            (if embedded).
        """
        res = None
        case = self.parent_case # pragma pylint: disable=no-member
        stlist = case[:self] # pragma pylint: disable=invalid-slice-index
        for stage in stlist:
            for _, inf in stage.handle2info.iteritems():
                if not info.embedded and not inf.embedded:
                    if inf.filename == info.filename:
                        res = inf
                        break
                if info.embedded and inf.embedded:
                    if osp.basename(inf.filename) == \
                       osp.basename(info.filename):
                        res = inf
                        break
        return res

    def copy2tmpdir(self):
        """
        When a stage is automatically duplicated
        copies the embedded files to the temp dir.
        """
        for info in self.handle2info.viewvalues():
            if info.embedded:
                source = info.filename
                bname = osp.basename(info.filename)
                dest = osp.join(self.model.tmpdir, bname) # pragma pylint: disable=no-member
                if source != dest:
                    copy_file(source, dest)
                info.filename = dest

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
        for info in self.handle2info.viewvalues():
            if filename and info.filename and \
               osp.basename(info.filename) == osp.basename(filename):
                return True
        return False
