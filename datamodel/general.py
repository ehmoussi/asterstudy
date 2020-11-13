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
Base services
-------------

Implementation of base classes and enumerators.

"""

from __future__ import unicode_literals

from common.utilities import translate

def no_new_attributes(wrapped_setattr):
    """ Raise an error on attempts to add a new attribute, while
        allowing existing attributes to be set to new values.

        Taken from ?
        'Python Cookbook' by Alex Martelli, Anna Ravenscroft, David Ascher,
        ?6.3. 'Restricting Attribute Setting'
    """
    def __setattr__(self, name, value):
        if hasattr(self, name): # not a new attribute, allow setting
            wrapped_setattr(self, name, value)
        else:
            message = "Can't add attribute %r to %s" % (name, self)
            raise AttributeError(message)

    return __setattr__


class UIDMixing(object):
    """Sub class for UID based classes.

    Arguments:
        uid (int): Object's id.
    """

    _id = None
    __setattr__ = no_new_attributes(object.__setattr__)

    def __init__(self, uid):
        self._id = uid

    @property
    def uid(self):
        """Attribute that holds unique *id*"""
        return self._id


class CataMixing(object):
    """Sub class for classes based on a catalog.

    Attributes:
        _cata (PartOfSyntax): The catalog on which the object is based.
    """

    _cata = None
    __setattr__ = no_new_attributes(object.__setattr__)

    def __init__(self, cata):
        self._cata = cata

    @property
    def cata(self):
        """Attribute that holds unique *cata*"""
        return self._cata

    @cata.setter
    def cata(self, value):
        "Declares setter for so named property"
        self._cata = value


class Validity(object):
    """
    Enumerator for validity statuses.

    Attributes:
        Nothing: Empty (valid object).
        Syntaxic: Object is syntaxically invalid.
        Dependency: Object is invalid in terms of dependencies.
        Naming: Object is invalid in terms of naming.
        Complete: Object is invalid in all aspects.
        Valid: Same as `Nothing`.
        Any: Same as `Complete`.
    """
    Nothing = 0x00
    Ok = Valid = Nothing
    Syntaxic = 0x01
    Dependency = 0x02
    Naming = 0x04
    Complete = Syntaxic | Dependency | Naming
    Any = Complete

    @staticmethod
    def value2str(value):
        "Maps enumerator to string representation."
        result = []

        if value & Validity.Syntaxic:
            result.append(translate("AsterStudy", "Syntax problem"))
        if value & Validity.Dependency:
            result.append(translate("AsterStudy", "Broken dependencies"))
        if value & Validity.Naming:
            result.append(translate("AsterStudy", "Naming conflict"))

        return ", ".join(result)


class FileAttr(object):
    """
    Enumerator for *UnitType* status.

    Attributes:
        No: Unknown status.
        In: Used only as input.
        Out: Used only as output.
        InOut: Used as both input and output.
    """
    No = 0x00
    In = 0x01
    Out = 0x02
    InOut = In | Out

    @staticmethod
    def str2value(value):
        "Maps string representation to enumerator."
        result = FileAttr.No

        if value == 'in':
            result = FileAttr.In
        elif value == 'out':
            result = FileAttr.Out
        elif value == 'inout':
            result = FileAttr.InOut

        return result

    @staticmethod
    def value2str(value):
        "Maps enumerator to string representation."
        result = '?'

        if value == FileAttr.In:
            result = 'in'
        elif value == FileAttr.Out:
            result = 'out'
        elif value == FileAttr.InOut:
            result = 'inout'

        return result


# Must stay identical to `code_aster.Cata.SyntaxObjects.ConversionLevel`
class ConversionLevel(object):
    """
    Enumerator for the level of conversion requirements.

    Attributes:
        NoFail: Do not fail, not *strict*.
        Naming: Requires that all command results are explicitly named.
        Type: Requires a valid type definition.
        Keyword: Requires that all keywords are valid.
        Syntaxic: Requires a valid syntax of all the commands.
        Restore: Requires a conversion without error during restore.
        Any: All conversion must pass.
        Partial: Allows to make a partial conversion (to be used with
            another level).
        NoGraphical: Force to load all stages in text mode.
    """
    NoFail = 0x00
    Naming = 0x01
    Type = 0x02
    Keyword = 0x04
    Syntaxic = Naming | Type | Keyword
    Restore = 0x08
    Any = Syntaxic | Restore
    Partial = 0x10
    NoGraphical = 0x20


class DuplicationContext(object):
    """
    Defines the context in an object is duplicated.

    Attributes:
        Nothing: not specified
        AutoDupl: automatic duplication, when the user edits
            a child object referenced by several parents.
        CopyFrom: copy as current operation.
        CreateRun: create run case operation.
        User: explicit user's copy and paste operation.
    """
    Nothing = 0x00
    AutoDupl = 0x01
    CopyFrom = 0x02
    CreateRun = 0x04
    User = 0x08
