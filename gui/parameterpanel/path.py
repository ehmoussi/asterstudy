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
Parameters Path
---------------

Implementation of the Parameters path entity. This entity specify location
of parameter keyword in Aster Catalog hierarchy tree and used in Parameter
panel for parameter identification.

"""

from __future__ import unicode_literals

from .basic import CataInfo

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name

class ParameterPath(object):
    """Class for parameter keyword path."""

    separator = "."

    def __init__(self, cmd, **kwargs):
        """ Constructor """
        super(ParameterPath, self).__init__()

        self._keyword = None
        self._keywordtype = None

        self._command = cmd
        apath = kwargs.get("path")
        if apath is None:
            aname = kwargs.get("name")
            if aname is None:
                aname = cmd.cata.name
            apath = self.separator + aname
        self._path = apath

        self._initialize_keyword()

    def command(self):
        """
        Return command object.

        Returns:
              Command: Command object.
        """
        return self._command

    def path(self):
        """
        Return path string, i.e. keywords separated by dots.

        Returns:
              str: Object's path.
        """
        return self._path

    def name(self):
        """
        Return name of the node.

        Returns:
              str: Object's name.
        """
        return self.path().split(self.separator).pop()

    def names(self):
        """
        Return path names as string list.

        Returns:
              list[str]: Path names array.
        """
        path = self.path()
        if self.isAbsolute():
            path = path[1:len(path)]
        return path.split(self.separator)

    def rename(self, name):
        """
        Replace the current item name in path by specified name.

        Arguments:
            name (str): New item name
        """
        names = self._path.split(self.separator)
        names.pop()
        names.append(name)
        self._path = self.separator.join(names)
        self._initialize_keyword()

    def isEqual(self, other):
        """
        Check if this path is equal to another one.

        Arguments:
            other (ParameterPath): Other path.

        Returns:
            bool: *True* if the path is equal to other path; *False*
            otherwise.
        """
        return self.command() == other.command() and \
            self.path() == other.path()

    def isAbsolute(self):
        """
        Check if path is an absolute one.

        Returns:
            bool: *True* if the path is absolute; *False* otherwise.
        """
        my_path = self.path()
        return my_path.startswith(self.separator)

    def isRelative(self):
        """
        Check if path is a relative one.

        Returns:
            bool: *True* if the path is relative; *False* otherwise.
        """
        return not self.path().startswith(self.separator)

    def isRelativeTo(self, root_path):
        """
        Check if path is a relative agains the specified one.

        Arguments:
            rel_path (str): Root path.

        Returns:
            bool: *True* if the path is relative to `root_path`; *False*
            otherwise.
        """
        rpath = root_path.path() \
            if isinstance(root_path, ParameterPath) else root_path
        return self.path().startswith(rpath)

    def relativePath(self, root_path):
        """
        Get part of path which is relative to the specified root path.

        Arguments:
            root_path (ParameterPath): Root path.

        Returns:
            ParameterPath: Relative path.
        """
        rel_path = ""
        path = self.path()
        rpath = root_path.path() \
            if isinstance(root_path, ParameterPath) else root_path
        if path.startswith(rpath):
            rel_path = path[len(rpath) + 1:len(path)]
        return ParameterPath(self.command(), path=rel_path)

    def absolutePath(self, rel_path):
        """
        Return new path which is an absolute one and consists of
        internal path and specified relative path.

        Arguments:
            rel_path (ParameterPath): Relative sub path.

        Returns:
            ParameterPath: Absolute path.
        """
        abs_path = ""
        path = self.path()
        rpath = ""
        if isinstance(rel_path, ParameterPath):
            rpath = rel_path.path()
        elif isinstance(rel_path, list):
            rpath = self.separator.join(rel_path)
        else:
            rpath = rel_path
        if not rpath.startswith(self.separator):
            abs_path = path + self.separator + rpath
        return ParameterPath(self.command(), path=abs_path)

    def parentPath(self):
        """
        Get parent path.

        Returns:
            ParameterPath: Parent path.
        """
        path_list = self.path().split(self.separator)
        path_list.pop()
        parent_path = None
        if len(path_list) > 0:
            new_path = self.separator.join(path_list)
            if len(new_path) > 0:
                parent_path = ParameterPath(self.command(), path=new_path)
        return parent_path

    def keyword(self):
        """
        Get the keyword stored within this path object.

        Returns:
            PartOfSyntax: Catalog keyword definition object.
        """
        return self._keyword

    def keywordType(self):
        """
        Get the parameter keyword type.

        Returns:
            str: Parameter keyword type.
        """
        return self._keywordtype

    def isKeywordSequence(self):
        """
        Check if stored keyword is a sequence.

        Returns:
            bool: *True* if the keyword is a sequence; *False*
            otherwise.
        """
        is_list = False
        param_def = self.keyword()
        if param_def is not None and hasattr(param_def, "definition"):
            defin = param_def.definition
            min_limit = defin['min'] if 'min' in defin else None
            max_limit = defin['max'] if 'max' in defin else None
            if max_limit is None and min_limit is not None:
                max_limit = max(1, min_limit)
            if max_limit is not None or min_limit is not None:
                degenerate = max_limit == 1
                is_list = not degenerate
        return is_list

    def isInSequence(self):
        """
        Check if path refers to an item in a sequence.

        Returns:
            bool: *True* if the path stores item of a sequence; *False*
            otherwise.
        """
        inseq = False
        parent_path = self.parentPath()
        if parent_path is not None:
            parent_kw = parent_path.keyword()
            if hasattr(parent_kw, 'definition'):
                parent_kw = parent_kw.definition
            if self.name() not in parent_kw:
                inseq = True
        return inseq

    def _initialize_keyword(self):
        """
        Define internal keyword parameters.
        """
        self._keyword = None
        names = self.names()
        if self._command is not None:
            kwords = self._command.cata
            names.pop(0)
            while kwords is not None and len(names) > 0:
                name = names.pop(0)
                if name in kwords.entites:
                    kwords = kwords.getKeyword(name, None)
            self._keyword = kwords
        self._keywordtype = CataInfo.keyword_type(self)
