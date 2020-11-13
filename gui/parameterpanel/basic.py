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
Parameter panel basic data
--------------------------

Basic data types and functions for Parameter panel.
"""

from __future__ import unicode_literals

import re
from inspect import getmro

from common import is_subclass, is_contains_word

from datamodel import CATA
from datamodel.command import Command

from gui import translate_command

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class EditorLink(object):
    """Enumerator for composite editor and sub operations link."""

    List = 'LIST'
    Fact = 'FACT'
    GrMa = 'GRMA'
    Table = 'TABLE'
    Variable = 'VARIABLE'


class KeywordType(object):
    """Enumerator for custom keyword types."""

    FileName = 'FileName'
    Function = 'Function'
    MeshName = 'MeshName'
    MeshGroup = 'MeshGroup'
    Standard = 'Standard'


class Options(object):
    """Specific properties of the *Parameters* panel."""

    use_translations = True

    @staticmethod
    def translate_command(command, keyword=None, item=None):
        """
        Redirect all catalogs translations and force
        'use business oriented translations' option explicitly
        set in *Parameters* panel.

        Note:
            All items of *Parameters* panel should use this
            method instead of function implemented at package level.

        See also:
            `gui.translate_command()`
        """
        return translate_command(command, keyword, item,
                                 force_translations=Options.use_translations)


class CataInfo(object):
    """
    Class with some inquire methods into Aster catalogue.
    """

    @classmethod
    def keyword_type(cls, path):
        """
        Get the parameter keyword type.

        Arguments:
            path (ParameterPath): Parameter's path.

        Returns:
            str: Parameter keyword type.
        """
        kwtype = KeywordType.Standard
        if cls._is_meshname(path):
            kwtype = KeywordType.MeshName
        elif cls._is_meshgroup(path):
            kwtype = KeywordType.MeshGroup
        elif cls._is_function(path):
            kwtype = KeywordType.Function
        elif cls._is_filename(path):
            kwtype = KeywordType.FileName
        return kwtype

    @classmethod
    def keyword_dependancies(cls):
        """
        Get the parameter keyword dependancy table.

        Returns:
            dict: Parameter keyword dependancy table.
        """
        if not hasattr(cls, "_keyword_dependancies"):
            # Create and register the depends table
            table = {}
            table['.LIRE_MAILLAGE.UNITE'] = \
                ['.LIRE_MAILLAGE.b_format_med.NOM_MED']
            cls._keyword_dependancies = table
        return cls._keyword_dependancies

    @classmethod
    def _is_meshname(cls, path):
        return path.command().title == "LIRE_MAILLAGE" and \
            path.name() == "NOM_MED"

    @classmethod
    def _is_meshgroup(cls, path):
        ismeshkw = is_contains_word(path.name(),
                                    ["GROUP_MA", "GROUP_NO"])
        if ismeshkw:
            kw_def = path.keyword().definition
            typ = kw_def.get('typ')
            if isinstance(typ, (tuple, list)):
                if len(typ) > 0:
                    typ = typ[0]
                else:
                    typ = None
            ismeshkw = is_subclass(typ, CATA.package('DataStructure').GEOM)
        return ismeshkw

    @classmethod
    def _is_function(cls, path):
        """
        Check if `path` is a 'DEFI_FONCTION' keyword with one of parameters:
        'VALE',
        'VALE_C',
        'VALE_PARA', 'VALE_FONC',
        'NOEUD_PARA', 'VALE_Y',
        'ABSCISSE', 'ORDONNEE'.

        Arguments:
            path (ParameterPath): Parameter's path.

        Returns:
            bool: *True* if `path` is a function's 'values' parameter;
        *False* otherwise.
        """
        valid = re.compile("^[.]?DEFI_FONCTION[.]("
                           "VALE"
                           "|VALE_C"
                           "|(.*\\.)?VALE_Y"
                           "|ABSCISSE|(.*\\.)?ORDONNEE"
                           ")$")
        is_func_values = (valid.match(path.path()) is not None)
        return is_func_values

    @classmethod
    def _is_filename(cls, path):
        """
        Check if `path` is a unit keyword.

        Arguments:
            path (ParameterPath): Parameter's path.

        Returns:
            bool: *True* if `path` is a unit parameter; *False* otherwise.
        """
        is_file = is_contains_word(path.name(), 'UNITE')
        param_def = path.keyword()
        if is_file and param_def is not None and \
                hasattr(param_def, "definition"):
            defin = param_def.definition
            objtype = defin.get('typ')
            if not is_subclass(objtype,
                               CATA.package('DataStructure').UnitBaseType):
                is_file = False
        return is_file


class ContentData(object):
    """
    Class for formatting contents presentation.
    """
    def __init__(self):
        super(ContentData, self).__init__()

        self._contmode = ""
        self._contdepth = 2
        self._contvalue = None
        self._use_bo = Options.use_translations

    def contentsValue(self):
        """
        Gets the contents

        Returns:
            (any): Contents value
        """
        return self._contvalue

    def setContentsValue(self, val):
        """
        Sets the contents value

        Arguments:
            val (any): Contents value
        """
        if self._contvalue != val or self._use_bo != Options.use_translations:
            self._contvalue = val
            self._updateContents()
            self._use_bo = Options.use_translations

    def contentsMode(self):
        """
        Gets the contents mode

        Returns:
            (str): Contents mode string
        """
        return self._contmode

    def setContentsMode(self, mode):
        """
        Sets the contents mode

        Arguments:
            mode (str): Contents mode string
        """
        if self._contmode != mode or self._use_bo != Options.use_translations:
            self._contmode = mode
            self._updateContents()
            self._use_bo = Options.use_translations

    def contentsDepth(self):
        """
        Gets the contents depth

        Returns:
            (int): Contents parsing depth
        """
        return self._contdepth

    def setContentsDepth(self, depth):
        """
        Sets the contents depth

        Arguments:
            depth (int): Contents mode depth
        """
        if self._contdepth != depth or \
                self._use_bo != Options.use_translations:
            self._contdepth = depth
            self._updateContents()
            self._use_bo = Options.use_translations

    def setContents(self, val, mode, depth=None):
        """
        Sets the contents

        Arguments:
            val (any): Contents value
            mode (str): Contents mode string
            depth (int): Contents mode depth
        """
        changed = self._contvalue != val or self._contmode != mode
        self._contvalue = val
        self._contmode = mode

        if depth is not None:
            changed = changed or self._contdepth != depth
            self._contdepth = depth

        if changed or self._use_bo != Options.use_translations:
            self._updateContents()
            self._use_bo = Options.use_translations

    def _updateContents(self):
        """
        Updates the contents string. Default implementation does nothing.
        Should be reimplemented in subclasses.
        """
        pass

    def _contentsText(self, path, value=None, mode=None, depth=None):
        """
        Gets the formatted contents string.

        Arguments:
            path (ParameterPath): Current keyword catalogue path.

        Returns:
            (str): Formatted contents string
        """
        val = self.contentsValue() if value is None else value
        mod = self.contentsMode() if mode is None else mode
        dep = self.contentsDepth() if depth is None else depth
        return ContentData.formatContents(path, val, mod, dep)

    @classmethod
    def formatContents(cls, path, value, mode, depth=1, is_top=True):
        """
        Convert content into string according to given mode.

        Arguments:
            value (list, dict): Content value
            mode (str): Content mode string

        Returns:
            (str): Content string
        """
        contdict = {}
        islist = isinstance(value, (list, tuple))
        if islist:
            for i in xrange(len(value)):
                contdict[i+1] = value[i]
        elif isinstance(value, dict):
            contdict = value
        else:
            islist = True
            contdict[0] = value

        command = path.command()

        reslist = []
        if depth > 0:
            for key in contdict:
                if key is None:
                    continue
                txt = ""
                if not islist and (mode == "parameters" or mode == "keywords"):
                    txt += Options.translate_command(command.title, "%s" % key)

                if not islist and mode == "parameters":
                    txt += "="

                if mode == "parameters" or mode == "values":
                    val = contdict[key]
                    if val is None:
                        txt += "{}"
                    elif isinstance(val, (list, tuple, dict)):
                        txt += cls.formatContents(path, val,
                                                  mode, depth - 1, False)
                    elif isinstance(val, Command):
                        txt += val.name
                    elif isinstance(val, basestring):
                        txt += "'%s'" % \
                            Options.translate_command(command.title,
                                                      str(key), val)
                    else:
                        txt += str(val)

                reslist.append(txt)

        res = ", ".join(reslist) if len(reslist) > 0 else ""

        if isinstance(value, list):
            res = "[%s]" % res
        elif isinstance(value, tuple):
            res = "(%s)" % res
        elif isinstance(value, dict) and not is_top:
            res = "{%s}" % res

        return res


def parameterPanel(widget):
    """
    Searches ParameterPanel in parents of `widget`.

    Returns:
        ParameterPanel: root parent of the widget.
    """
    panel = widget
    while panel is not None and 'ParameterPanel' not in \
            [i.__name__ for i in getmro(panel.__class__)]:
        panel = panel.parentWidget()
    return panel
