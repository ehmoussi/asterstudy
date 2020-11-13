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
Catalogs
--------

Implementation of the catalogs container.

"""

from __future__ import unicode_literals

from collections import OrderedDict
import os
import os.path as osp
import traceback

from common import CatalogError, CFG, debug_message, AsterStudySession
from .dict_categories import CATEGORIES_DEFINITION, DEPRECATED
from .aster_syntax import IDS, get_cata_typeid, import_aster
from .global_dict import GLOBAL_DICT


class Catalogs(object):
    """Class for the catalogs access"""

    def __init__(self):
        """Create catalogs object."""
        self._version = None
        self._pkgs = {}
        self._catalogs = {}
        self._categories = OrderedDict()
        self._command_to_category = {}
        self._dockeys = {}
        self.read_catalogs()

    def reset(self):
        """Reset catalogs when version is changing."""
        self._pkgs.clear()
        self._catalogs.clear()
        self._categories.clear()
        self._command_to_category.clear()
        self._version = None

    def package(self, pkg_name):
        """
        Get the package of *code_aster.Cata* by its name.

        Returnds:
            package: Package being requested.
        """
        return self._pkgs[pkg_name]

    @staticmethod
    def version_path(version):
        """Return the path to a version.

        Arguments:
            version (str): Version label.

        Returns:
            str: Path to the version.
        """
        try:
            version_path = CFG.get("Versions", version)
        except KeyError:
            version_path = version
        return version_path

    def tests_path(self, version):
        """Return the path where to find the testcases associated to a catalog.

        Arguments:
            version (str): Version label.

        Returns:
            str: Path to the testcases directory.
        """
        base = self.version_path(version)
        return osp.normpath(osp.join(base, os.pardir, os.pardir,
                                     "share", "aster", "tests"))

    def read_catalogs(self, version=None):
        """
        Read all catalogs.

        Arguments:
            version (str): Version of code_aster catalogs.
        """
        if version and version == self._version:
            debug_message("Catalog for {0!r}: already loaded".format(version))
            return

        self.reset()
        if not version:
            version = CFG.default_version
        debug_message("Loading catalog for {0!r}".format(version))
        version_path = self.version_path(version)
        debug_message("from path {0!r}".format(version_path))

        # Enable marker
        AsterStudySession.set_cata()
        try:
            self._pkgs = import_aster(version_path)
            commands = self._pkgs["Commands"].__dict__
        except ImportError as exc:
            debug_message("Can not import version {0!r}\nReason: {1}"
                          .format(version_path, exc))
            commands = {}

        if commands:
            self._add_conversion_commands()
        for key, value in commands.iteritems():
            if get_cata_typeid(value) == IDS.command:
                self._catalogs[key] = value

        self._fill_categories()
        self._version = version
        self._read_dockeys()

    @property
    def version(self):
        """str: Attribute that holds current catalog's version."""
        return self._version

    @property
    def version_number(self):
        """str: Attribute that holds current catalog's version number."""
        try:
            vers = self.package("aster_version")
        except KeyError as exc:
            details = traceback.format_exc()
            raise CatalogError(exc, details)
        return vers.VERSION_MAJOR, vers.VERSION_MINOR, vers.VERSION_PATCH

    def _add_conversion_commands(self):
        """Add fake commands."""
        stx = self.package("Syntax")
        oper = stx.OPER
        simp = stx.SIMP
        variable = oper(nom="_CONVERT_VARIABLE",
                        sd_prod=stx.DS.PythonVariable,
                        fr="Definition of a user variable",
                        EXPR=simp(statut='o', typ='TXM'))
        comment = oper(nom="_CONVERT_COMMENT",
                       fr="A line of comment",
                       EXPR=simp(statut='o', typ='TXM'))

        hidden = oper(nom="_RESULT_OF_MACRO",
                      sd_prod=_hidden_prod,
                      fr="A hidden command",
                      DECL=simp(statut='o'),
                      PARENT=simp(statut='o'),
                      PATH=simp(statut='o'))

        fake = {'_CONVERT_VARIABLE': variable,
                '_CONVERT_COMMENT': comment,
                '_RESULT_OF_MACRO': hidden}

        self._catalogs.update(fake)

    # TODO Add a category for special "commands": _CONVERT_*
    def _fill_categories(self):
        """Fill categories map."""
        not_found_msg = "Command {0} is not found in catalogue"

        # 0. First of all add special category for variables
        self._command_to_category['_CONVERT_VARIABLE'] = 'Variables'
        self._categories['Variables'] = []

        # 1. Fill in categories in proper order
        for category in CATEGORIES_DEFINITION:
            self._categories[category] = []
            for name in CATEGORIES_DEFINITION[category]:
                command = self._catalogs.get(name)
                if not command:
                    debug_message(not_found_msg.format(name))
                else:
                    self._categories[category].append(name)
                    self._command_to_category[name] = category

        # Finally, add a category for deprecated commands
        self._categories['Other'] = []
        self._categories['Deprecated'] = []
        self._categories['Hidden'] = []
        for name in DEPRECATED:
            self._categories['Deprecated'].append(name)
            self._command_to_category[name] = 'Deprecated'

        # 2. Put remaining commands to the 'Other' category
        for name in self._catalogs:
            if self._command_to_category.get(name):
                continue
            # fake commands starts with "_": hidden
            if name.startswith("_"):
                category = 'Hidden'
            else:
                category = 'Other'
            self._categories[category].append(name)
            self._command_to_category[name] = category
        self._categories['Other'].sort()

    def is_co(self, astype):
        """Tell if the given code_aster type is CO (result of
        macro-command).

        Arguments:
            astype (type): Type being checked.

        Returns:
            bool: Check status.
        """
        if isinstance(astype, (tuple, list)):
            return self.package("DataStructure").CO in astype

        return astype is self.package("DataStructure").CO

    @property
    def baseds(self):
        """Get the type on which all datastructures are based.

        Returns:
            type: Base data structure type.
        """
        return self.package("DataStructure").DataStructure

    @property
    def command(self):
        """Get the Command type.

        Returns:
            type: Command type.
        """
        return self.package("SyntaxObjects").Command

    def expects_result(self, command):
        """Tell if the given command must return a result (is an *Operator*).

        *Procedures* create no results, *Macros* may create 0 or 1 result.

        Arguments:
            command (object): Command to check.

        Returns:
            bool: *True* if the command must return a result, *False* otherwise.
        """
        return isinstance(command, (self.package("Syntax").Operator,
                                    self.package("Syntax").Formule))

    def get_categories(self, usage=None):
        """Get all categories.

        Argument:
            usage (str): By default, returns all categories. "toolbar" returns
                the categories for the toolbar, "showall" for the "Show All"
                dialog.

        Returns:
            list[str]: Names of all categories.
        """
        categ = self._categories.keys()
        if usage:
            categ.remove("Hidden")
        if usage in ("showall", "toolbar"):
            categ.remove("Variables")
        if usage == "toolbar":
            categ.remove("Other")
            categ.remove("Deprecated")
        return categ

    def get_category(self, category):
        """Get all commands in given category.

        Arguments:
            category (str): Name of the category.

        Returns:
            list[str]: Names of all commands in given category.
        """
        return self._categories.get(category, [])

    def get_command_category(self, command):
        """Get category owning the command.

        Arguments:
            command (str): Name of the command.

        Returns:
            str: Name of the category.
        """
        return self._command_to_category.get(command)

    def get_category_index(self, command):
        """Get index of category owning the command.

        Arguments:
            command (str): Name of the command.

        Returns:
            int: Index of the category in the catalogs.
        """
        category = self.get_command_category(command)
        return self.get_categories().index(category) if category else -1

    def get_catalog(self, command):
        """Get the catalog of a command.

        Arguments:
            command (str): Name of the command.

        Returns:
            PartOfSyntax: Command's catalog class.
        """
        return self._catalogs.get(str(command))

    def iteritems(self):
        """Return an iterator over the pairs (*command name*, *catalog*).
        """
        for key, value in self._catalogs.iteritems():
            yield key, value

    def __iter__(self):
        """Iterator over command names."""
        for key in self._catalogs:
            yield key

    def get_translation(self, command, keyword=None, item=None):
        """Return the translation for a command or keyword name, or for
        keyword's value (to manage *into* attribute).

        The translation is provided by the catalog or a global dictionary.
        """
        key = item if item is not None else \
            keyword if keyword is not None else command
        cata = self.get_catalog(command)
        if cata is not None:
            dtr = cata.definition.get("translation", {})
            trans = dtr.get(key)
            if trans is not None:
                return unicode(trans, 'utf-8')
        return GLOBAL_DICT.get(key, key)

    def _read_dockeys(self):
        """Read the file containing the documentation keys."""
        template = "clefs_docu_{0}"
        self._dockeys = {}
        for name in (self.version, "stable"):
            filename = CFG.rcfile(template.format(name))
            if filename:
                for line in open(filename, "rb"):
                    cmd, url = line.split(":", 1)
                    self._dockeys[cmd] = url.strip()
                break

    def get_command_url(self, command, base_url):
        """Return the url of the documentation for a command name.

        Arguments:
            command (str): Command name.

        Returns:
            str: Url of the documentation or *None*.
        """
        vers = self.package("aster_version")
        info = dict(branch=vers.BRANCH, lang="fr",
                    base_url=base_url.rstrip("/"))
        base = "{base_url}/{branch}/{lang}/".format(**info)
        failover = "index.php?man=commande"
        return base + self._dockeys.get(command, failover)

    def get_command_docstring(self, command):
        """Return the docstring for given command.

        Arguments:
            command (str): Command name.

        Returns:
            str: Command's docstring.
        """
        return self.get_catalog(command).udocstring


def _hidden_prod(**kwargs):
    return kwargs["DECL"].gettype()

CATA = Catalogs()
