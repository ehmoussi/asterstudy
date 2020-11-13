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
Comm2Study
----------

Implementation of the features to import code_aster syntax into the data model.

"""

from __future__ import unicode_literals

import sys
import os
import copy
import traceback
from collections import OrderedDict

from common import (ConversionError, debug_message, debug_mode, format_code,
                    old_complex, split_text, to_unicode)
from .general import ConversionLevel
from .abstract_data_model import add_parent
from .catalogs import CATA
from .aster_parser import MARK, change_text
from .aster_syntax import is_unit_valid
from .command import CO as _CO, Variable
from .command.mixing import Factor


class CommandBuilder(object):
    """Builder of objects of AsterStudy data model.

    Use the current version of the code_aster commands catalog.

    Args:
        stage (Stage): The :obj:`datamodel.stage.Stage` object
            to fill.
        strict (ConversionLevel): Tells how strict the conversion must be.
                Default is not to fail.

    Attributes:
        _stg (Stage): The :obj:`datamodel.stage.Stage` object to fill.
        _strict (ConversionLevel): The level of conversion required.
        _cmd_results (dict): Stores the result returned by a command.
        _results_cmd (dict): Stores the command that returns a result.
        _saved (dict): Used to store temporary objects.
        _exec_ctxt (dict): Context of the command file.
        _vars (dict): Used to store value of Python variables.
        _reuse (dict): Store command reused by another.
        _del (dict): Store deleted commands.
        _unfinish (Command): Command currently added.
    """

    def __init__(self, stage, strict=ConversionLevel.NoFail):
        if not stage.is_graphical_mode():
            raise TypeError("The stage must be in graphical mode.")
        self._stg = stage
        self._unfinish = None
        self._strict = strict
        self._cmd_results = {}
        self._results_cmd = {}
        self._saved = {}
        self._exec_ctxt = {}
        self._vars = {}
        self._reuse = {}
        self._del = OrderedDict()
        CATA.command.register_call_callback(self._exec_command)
        CATA.baseds.register_deepcopy_callback(self._deepcopy_ds)

    @staticmethod
    def reset_callbacks():
        """Reset callbacks."""
        CATA.command.register_call_callback(None)
        CATA.baseds.register_deepcopy_callback(None)

    def _exec_command(self, ascommand, **kwargs):
        """Execution of the *ascommand*."""
        debug_message("executing aster command", ascommand.name)
        parents = []
        if len(self._stg) > 0:
            last = self._stg.dataset.get_last_command()
            if last.title == "_CONVERT_COMMENT":
                if ascommand.name == "_CONVERT_COMMENT":
                    # append the text of the comment to the previous comment
                    debug_message("append to last comment", kwargs)
                    last["EXPR"] = last["EXPR"].value + "\n" + kwargs["EXPR"]
                    return
                # add a dependency to the previous comment
                parents.append(last)

        kwargs = add_reuse_badcommands(ascommand, kwargs)
        kwargs = add_unit_default_value(ascommand, kwargs)
        result = ascommand.call_default(__strict__=self._strict, **kwargs)
        debug_message("creating Command for", ascommand.name)
        command = self.add_command(ascommand.name, **kwargs)
        # store the result produced by the Command.
        if result is not None:
            self._cmd_results[command] = result
            self._results_cmd[result] = command
            debug_message("result stored for", command.title, result)

        # DETRUIRE
        if command.title == "DETRUIRE":
            concept = command["CONCEPT"]
            if isinstance(concept, Factor):
                concept = [concept, ]
            for fact in concept:
                names = fact["NOM"].value
                if not isinstance(names, (list, tuple)):
                    names = [names, ]
                for cmd in names:
                    self._del[cmd] = command

        # if a macro-command produces additional results
        for hidden in command.hidden:
            hidden.check(safe=False)
            self._exec_ctxt[hidden.name] = hidden

        # In case of "reuse", a command result may be reset by the current
        # command, that's why we must name it now and not wait
        # for `_post_conversion()`.
        # Name previously created objects
        _locals = self._exec_ctxt
        for name, item in _locals.viewitems():
            if not isinstance(item, CATA.baseds):
                continue

            cmd = self._results_cmd[item]
            cmd.name = name
            debug_message("name updated", name, "for", cmd.title, item)

        for i in parents:
            debug_message("adding parent of", command.title, ":", i.uid)
            add_parent(command, i)

        return result

    def _deepcopy_ds(self, datastructure, memodict=None):
        # pragma pylint: disable=unused-argument
        """Overrides the original *__deepcopy__* hook of *DataStructure*."""
        return self._results_cmd[datastructure]

    def add_command(self, title, **kwargs):
        """Add the new *Command* in the *Stage*."""
        cmd = self._stg.add_command(title, '_')
        self._unfinish = cmd
        ikwargs = copy.deepcopy(kwargs)
        if 'reuse' in ikwargs:
            self._reuse[cmd] = ikwargs['reuse']
            del ikwargs['reuse']
        ikwargs = convert_value(ikwargs)
        cmd.init(ikwargs)
        self._unfinish = None
        return cmd

    def _setup(self):
        """Build and setup the context to evaluate the commands file.

        Returns:
            dict: Context to execute the commands file.
        """
        context = {}

        # Update context with commands from preceding stages
        for stage in self._stg.preceding_stages:
            for command in stage:
                if command.name in ['', '_']:
                    continue

                # Create an instance of the result type
                result_type = command.gettype(self._strict)

                if isinstance(result_type, basestring):
                    result = result_type
                else:
                    result = result_type()

                try:
                    self._results_cmd[result] = command
                except TypeError: # pragma: no cover
                    # ignore list, dict results
                    pass
                context[command.name] = result

        # add code_aster command dictionary
        context.update(CATA.iteritems())

        # support of CO object
        context['CO'] = _CO

        # add basic mathematical functions
        context.update(Variable.initial_context())

        # We could generate the function name to avoid possible conflict
        context["_post_conversion"] = self._post_conversion
        # change output streams
        if not debug_mode():
            self._saved['sys.stdout'] = sys.stdout
            sys.stdout = open(os.devnull, "wb")
            self._saved['sys.stderr'] = sys.stderr
            sys.stderr = open(os.devnull, "wb")

        return context

    def _teardown(self):
        """Restore initial state."""
        if not debug_mode():
            sys.stdout = self._saved['sys.stdout']
            sys.stderr = self._saved['sys.stderr']

    def _post_conversion(self):
        """Post-conversion function to name the results in *Command* objects.

        Arguments:
            _locals (dict): Context of the comm file.
        """
        _locals = self._exec_ctxt
        _unauthorized = [i for i in CATA]
        # store the name of code_aster datastructures
        result_names = {}
        for name, result in _locals.viewitems():
            if isinstance(result, CATA.baseds):
                if name in _unauthorized:
                    raise ValueError("Unauthorized name: {0!r}".format(name))
                result_names[result] = name
                debug_message("naming result", result, "as", name)
        # store results names in Command objects and evaluate user variables
        results = result_names.keys()
        # it is important to loop on commands by creation order for DETRUIRE
        deleters = OrderedDict()
        for cmd in self._stg:
            if cmd in self._del:
                deleters[cmd] = self._del[cmd]
            _check_deleters(cmd, deleters)

            result = self._cmd_results.get(cmd)
            if result is None:
                continue

            if result in results:
                cmd.name = result_names[result]
                debug_message("naming result of", cmd.title, ":", cmd.name)
            elif cmd in self._reuse:
                # because of tolerated syntax "cmd(reuse='xx', ...)"
                cmd.name = self._reuse[cmd].name
                debug_message("reuse name for", cmd.title, ":", cmd.name)
            if self._strict & ConversionLevel.Naming and \
                    cmd.name in ('', '_'):
                raise NotImplementedError("can not name command: {0}"
                                          .format(cmd))

    def convert(self, intext):
        """Fill the stage from a commands file (given as text).

        Arguments:
            intext (str): Content of the commands file.
        """
        init_size = len(self._stg)
        intext = to_unicode(intext)
        try:
            eoi, text = change_text(intext, self._strict)
        except Exception as exc: # pragma pylint: disable=broad-except
            details = traceback.format_exc()
            raise ConversionError(exc, details, '?', '?')
        text = "{0}\n_post_conversion() # {1}\n".format(text, MARK)
        self._exec_ctxt = self._setup()
        try:
            exec text in self._exec_ctxt # pragma pylint: disable=exec-used
        except Exception as exc: # pragma pylint: disable=broad-except
            self._teardown()
            details = traceback.format_exc()
            eoprev, lineno, line = _locate_error(exc, eoi, text)
            if self._strict & ConversionLevel.Partial:
                debug_message("Conversion failed, split after line", eoprev)
                # remove the unfinished command
                if self._unfinish:
                    del self._stg[self._unfinish]
                # _post_conversion was not called
                try:
                    self._post_conversion()
                except Exception: # pragma pylint: disable=broad-except
                    # some commands have not be named...
                    pass
                part1, astext = split_text(intext, eoprev, remove=MARK)
                # debug_message("+" * 50)
                # debug_message(part1)
                # debug_message("-" * 50)
                # debug_message(astext)
                # debug_message("=" * 50)
                # in case of SyntaxError, nothing has been added
                if isinstance(exc, SyntaxError):
                    debug_message("SyntaxError: convert first part separately")
                    comm2study(part1, self._stg, self._strict)
                if astext:
                    self.add_text_stage(astext)
            else:
                # revert the input stage as it was
                while len(self._stg) > init_size:
                    del self._stg[-1]
                raise ConversionError(exc, details, lineno, line)
        finally:
            self._teardown()

    def add_text_stage(self, text):
        """Add a text stage for the text that can not be converted.

        Arguments:
            text (str): The text that can not be converted.
        """
        debug_message("add a text stage containing:\n", text)
        stg = self._stg
        case = self._stg.parent_case
        if stg.number != case.nb_stages:
            # a text stage was already inserted: concatenate
            stg = case[case.nb_stages - 1]
            text = stg.get_text(pretty=False) + os.linesep + text
        elif len(stg) != 0:
            # some commands have been added, create a new text stage
            newname = "{0}_{1}".format(stg.name, case.nb_stages)
            stg = case.create_stage(newname)

        try:
            text = format_code(text)
        except SyntaxError:
            pass
        stg.use_text_mode()
        stg.set_text(text)


def _locate_error(exc, eoi, text):
    """Return the line number and the line where the exception occurred.

    Returns:
        int: Line number of the end of the previous (successfull) instruction.
        int: Line number of the error.
        line: Line content where the error occurred.
    """
    if isinstance(exc, SyntaxError):
        lineno = exc.args[1][1]
        line = exc.args[1][3].strip()
    else:
        # 0: here, 1: executed text
        ltb = traceback.extract_tb(sys.exc_info()[-1], limit=3)
        try:
            tbck = ltb[1]
            lineno = tbck[1]
        except IndexError: # pragma: no cover
            lineno = -1

    debug_message("Error at line", lineno, "end of instr", eoi)
    lines = text.splitlines()
    upto = []
    offset = 0
    for i in eoi:
        if i >= lineno:
            break
        orig = i - offset
        if lines[i - 1].startswith("raise NotImplementedError"):
            offset += 1
        else:
            upto.append(orig)

    eoprev = upto.pop(-1) if upto else 0
    debug_message("Previous instr at line", eoprev, "(original text)")

    if not isinstance(exc, SyntaxError):
        line = lines[lineno - 1] if len(lines) > lineno - 2 else "?"

    return eoprev, lineno, line


def _check_deleters(command, deleters):
    """Check if a Command reuse a name of a previously deleted result.
    In this case, the Command must depend on the deleter.

    Arguments:
        command (Command): Command currently checked.
        deleters (dict): Dict `{deleted: deleter}`.
    """
    delnames = [i.name for i in deleters.keys()]
    name = command.name
    if name in ('', '_'):
        return

    if name in delnames:
        # add a dependency to DETRUIRE of the previous 'name'
        delcmds = [(i, val) for i, val in deleters.iteritems() \
                       if i.name == name and i != command]
        if not delcmds:
            return
        key, deleter = delcmds[0]
        del deleters[key]
        debug_message("add deps {0.title}<{0.uid}> vers {1.title}<{1.uid}>"
                      .format(command, deleter))
        add_parent(command, deleter)


class SetKeywordValue(object):
    """Visitor of a catalog of command to set value of some keywords.

    Attributes:
        _checker (function): Predicate used to select filter keywords.
        _setter (function): Function that returns the new value for a simple
            keyword.
        _values (dict): Dict of user keywords.
        _parent (str): Name of the current factor keyword or None at the top
            level.
        _current (str): Name of the keyword currently analysed.
    """

    def __init__(self, checker, setter, userdict):
        self._checker = checker
        self._setter = setter
        self._values = userdict
        self._parent = None
        self._current = None

    def _visit_composite(self, compo, _):
        """Visit a composite object (command, factor keywords...)"""
        for key, kwd in compo.definition.iterItemsByType():
            self._current = key
            kwd.accept(self)
            self._current = None

    def visit_simple(self, simple, _):
        """Visit a simple keyword."""
        if self._checker(simple):
            store = self._values
            if self._parent is not None:
                values = self._values
                store = values[self._parent] = values.get(self._parent, {})

            value = self._setter(simple)
            if isinstance(store, dict):
                store = [store, ]
            for occ in store:
                self._set(occ, value)

    def _set(self, store, value):
        """Set the value in dict"""
        if not store.has_key(self._current):
            debug_message("Add default value: {0}={1!r}".format(
                self._current, value))
            store[self._current] = value

    def visit_factor(self, factor, _):
        """Visit a factor keyword."""
        if not self._values.has_key(self._current):
            return
        self._parent = self._current
        self._visit_composite(factor, _)
        self._parent = None

    def visit_bloc(self, bloc, _):
        """Visit a block: does nothing because condition is not evaluated."""

    visitCommand = _visit_composite
    visitFactorKeyword = visit_factor
    visitSimpleKeyword = visit_simple
    visitBloc = visit_bloc


def add_unit_default_value(command, kwargs):
    """Set the value of UNITE keywords that have no value to default."""
    def _predicate(simple):
        if simple.definition.get('defaut') is None:
            return False
        if not is_unit_valid(simple.definition['defaut']):
            return False
        typ = simple.definition['typ']
        try:
            return issubclass(typ, CATA.package("DataStructure").UnitBaseType)
        except TypeError:
            pass
        return False

    def _setter(simple):
        return simple.definition.get('defaut')

    visitor = SetKeywordValue(_predicate, _setter, kwargs)
    command.accept(visitor)
    return kwargs


def add_reuse_badcommands(ascommand, kwargs):
    """Set the value of keywords to handle properly reuse property for
    uncorrect command."""
    # MECA_STATIQUE
    if ascommand.name == "MECA_STATIQUE":
        if 'reuse' in kwargs and 'RESULTAT' not in kwargs:
            kwargs["RESULTAT"] = kwargs['reuse']
    # MACR_ELEM_STAT
    elif ascommand.name == "MACR_ELEM_STAT":
        if 'reuse' in kwargs and 'MACR_ELEM' not in kwargs:
            kwargs["MACR_ELEM"] = kwargs['reuse']
    # MACRO_ELAS_MULT
    elif ascommand.name == "MACRO_ELAS_MULT":
        if 'reuse' in kwargs and 'RESULTAT' not in kwargs:
            kwargs["RESULTAT"] = kwargs['reuse']
    # DEFI_DOMAINE_REDUIT
    elif ascommand.name == "DEFI_DOMAINE_REDUIT":
        if 'reuse' in kwargs and 'MAILLAGE' not in kwargs:
            kwargs["MAILLAGE"] = kwargs['reuse']
    # CREA_RESU
    elif ascommand.name == "CREA_RESU":
        if 'reuse' in kwargs and kwargs.get("OPERATION") == "AFFE":
            kwargs["RESULTAT"] = kwargs['reuse']
    return kwargs


def convert_value(obj):
    """Convert old-style values"""
    # pragma pylint: disable=redefined-variable-type,no-member
    obj = old_complex(obj)
    if isinstance(obj, dict):
        for key, value in obj.iteritems():
            obj[key] = convert_value(value)
    elif isinstance(obj, list):
        for i, j in enumerate(obj):
            obj[i] = convert_value(j)
    elif isinstance(obj, tuple):
        obj = tuple([convert_value(i) for i in obj])
    return obj


def comm2study(content, stage, strict=ConversionLevel.NoFail):
    """Import a text of code_aster commands into the *Stage* object.

    Arguments:
        content (str): Text of code_aster commands to import.
        stage (Stage): *Stage* in which the *Command* objects are added.
        strict (ConversionLevel): Tells how strict the conversion must be.
            See `general.ConversionLevel` for more details.
            Default is not to fail.
    """
    nbs = stage.parent_case.nb_stages
    debug_message("starting new conversion of stage", stage.number, "/", nbs)
    assert not strict & ConversionLevel.Partial or stage.number == nbs
    builder = CommandBuilder(stage, strict)

    try:
        builder.convert(content)
        stage.reorder()
    finally:
        builder.reset_callbacks()
