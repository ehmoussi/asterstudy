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
Visitors
--------

This modules defines classes to visit content of *Command* objects (but can be
used on *DataSet* or *Stage*) and apply generic tasks, such as check values or
extract some keywords values.

"""


from __future__ import unicode_literals

from datamodel.aster_syntax import get_cata_typeid, IDS


class AbstractVisitor(object):
    """Abstract visitor of a DataSet or Command."""

    def __init__(self, *args, **kwargs):
        pass

    @classmethod
    def _does_nothing(cls, dummy):
        pass

    def _visit_keysmixing_based(self, item):
        """Visit an object based on a KeysMixing."""
        keys = sorted(item.keys())
        for key in keys:
            obj = item[key]
            if obj.undefined():
                continue
            obj.accept(self)

    def visit_command(self, command):
        """Visit a command"""
        self._visit_keysmixing_based(command)

    def visit_hidden(self, dummy):
        """Visit a Hidden command"""
        self._does_nothing(dummy)

    def visit_variable(self, var):
        """Visit a Variable"""
        self.visit_command(var)

    def visit_comment(self, dummy):
        """Visit a Comment"""
        self._does_nothing(dummy)

    def visit_factor(self, factor):
        """Visit a Factor keyword"""
        self._visit_keysmixing_based(factor)

    def visit_sequence(self, sequence):
        """Visit a Sequence of keywords."""
        for item in sequence:
            self._visit_keysmixing_based(item)

    def visit_simple(self, simple):
        """Visit a Simple keyword."""
        raise NotImplementedError


class BooleanVisitor(AbstractVisitor):
    """Visitor of a Command to check if a keyword is passing a given checker.

    The walk along the keywords tree is interrupted (by raising *StopIteration*
    exception) as soon as the checker is validated.

    Args:
        checker (function): Function that takes a SimpleKeyword as unique
            argument and returns a boolean.
    """

    def __init__(self, checker):
        super(BooleanVisitor, self).__init__()
        self._checker = checker
        self._found = False

    def checked(self):
        """Returns *True* if the checker has been validated,
        *False* otherwise."""
        return self._found

    def visit_simple(self, simple):
        """Visit a Simple keyword."""
        if self._checker(simple):
            self._found = True
            raise StopIteration


class FilterVisitor(AbstractVisitor):
    """Visitor of Command that filter the value of simple keywords.

    The keywords for which the values are matching the *checker* function are
    available using the *keywords* property as a list.

    Args:
        checker (function): Function that takes a SimpleKeyword as unique
            argument and returns a boolean.
    """

    def __init__(self, checker):
        super(FilterVisitor, self).__init__()
        self._checker = checker
        self._keywords = []

    @property
    def keywords(self):
        """Returns the list of filtered keywords."""
        return self._keywords

    def visit_simple(self, simple):
        """Visit a Simple keyword."""
        if self._checker(simple):
            self._keywords.append(simple)


class UnitVisitor(FilterVisitor):
    """Visitor of Command that return the UNITE keywords.

    It is a specialization of *FilterVisitor* with a pre-treatment to skip
    commands or factor keyworsd that have no such keywords.
    """

    def __init__(self):
        def _predicate_name(name):
            return name.startswith('UNITE')
        self._checker_name = _predicate_name

        def _predicate(simple):
            return _predicate_name(simple.name)

        super(UnitVisitor, self).__init__(_predicate)

    def _visit_keysmixing_based(self, item):
        """Visit an object based on a KeysMixing."""
        # interrupt as soon as possible for performance reasons
        found = _check_cata(item.cata, self._checker_name)
        if not found:
            return

        super(UnitVisitor, self)._visit_keysmixing_based(item)


def _check_cata(cata, checker):
    """Recursively check a catalog definition (*Command* or *FactorKeyword*)"""
    found = False
    for name, kwd in cata.definition.iterItemsByType():
        if get_cata_typeid(kwd) == IDS.simp:
            if checker(name):
                found = True
        else:
            found = _check_cata(kwd, checker)
        if found:
            break
    return found


def obj_start(obj):
    """Helper function to represent an object."""
    txt = ""
    if isinstance(obj, list):
        txt += "["
    if isinstance(obj, tuple):
        txt += "("
    return txt


def obj_end(obj):
    """Helper function to represent an object."""
    txt = ""
    if isinstance(obj, list):
        txt += "]"
    if isinstance(obj, tuple):
        if len(obj) == 1:
            txt += ", "
        txt += ")"
    return txt
