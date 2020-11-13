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
Study2Comm
----------

AsterStudy Stage Converter to code_aster COMM file format.

"""

from __future__ import unicode_literals

from StringIO import StringIO

from common import debug_mode, format_code, to_str, translate
from .command import Command, CO
from .visit_study import obj_start, obj_end


class ExportToCommVisitor(object):
    """Visitor of a DataSet to be exported as a code_aster comm file.

    Args:
        ostream (output stream): File-like object on which write the text.
        sort (bool): By default commands are sorted according to their
            dependencies. For unittests and keep order for commands without
            dependencies, one may use *False*.
        limit (int): Limits the output to the first occurrences of factor
            keywords or in the lists of values. Warning: Using *limit* may
            generate an invalid commands file.
    """
    interrupt_value = '"_interrupt_MARK_value_"'
    interrupt_fact = '_interrupt_MARK_fact_()'

    def __init__(self, ostream, sort=True, limit=0):
        self._sort = sort
        self._limit = limit
        self._limit_reached = False
        if debug_mode():
            self._write = _debug_write(ostream.write) # pragma: no cover
        else:
            self._write = ostream.write

    def visit_stage(self, stage):
        """Visit a Stage."""
        stage.dataset.accept(self)

    def visit_dataset(self, dataset):
        """Visit a DataSet."""
        if self._sort:
            cmds = dataset.sorted_commands
        else:
            cmds = dataset.commands
        for command in cmds:
            command.accept(self)

    def visit_command(self, command):
        """Visit a generic Command."""
        self._print_eol()
        name = command.name
        if name != "_":
            self._write(self.decorate_name(name))
            self._print_equal()
        self._write(self.decorate_title(command.title))
        self._print_left_brace()
        # if limit is set, do not check if reuse is required
        if self._limit <= 0 and command.need_reuse():
            self._write(self.decorate_keyword("reuse"))
            self._print_equal()
            self._write(self.decorate_name(name))
            self._print_delimiter(0, (None, None))
        self._visit_keysmixing_based(command)
        self._print_right_brace()
        self._print_eol()

    def visit_hidden(self, dummy):
        """Visit a Hidden."""
        pass

    def visit_variable(self, var):
        """Visit a Variable."""
        self._print_eol()
        self._write(self.decorate_name(var.name))
        self._print_equal()
        self._write(var['EXPR'].value)
        self._print_eol()

    def visit_comment(self, comment):
        """Visit a Comment."""
        lines = comment['EXPR'].value.splitlines()
        lines.insert(0, "")
        self._write(self.decorate_comment("\n# ".join(lines)))

    def visit_sequence(self, sequence):
        """Visit a Sequence of keywords."""
        self._write(self.decorate_keyword(sequence.name))
        self._print_equal(False)
        if len(sequence) > 1:
            self._print_left_brace()

        for idx, item in enumerate(sequence):
            self._write(self.decorate_special('_F'))
            self._print_left_brace()
            self._visit_keysmixing_based(item)
            self._print_right_brace()
            if self._limited(idx, sequence, self.interrupt_fact):
                break
            self._print_delimiter(idx, sequence)

        if len(sequence) > 1:
            self._print_right_brace()

    def visit_factor(self, factor):
        """Visit a Factor keyword."""
        self._write(self.decorate_keyword(factor.name))
        self._print_equal(False)
        self._write(self.decorate_special('_F'))
        self._print_left_brace()
        self._visit_keysmixing_based(factor)
        self._print_right_brace()

    def visit_simple(self, simple):
        """Visit a Simple keyword."""
        value = simple.value
        self._write(self.decorate_keyword(simple.name))
        self._print_equal(False)
        if isinstance(value, basestring):
            self._write("{0!r}".format(to_str(value)))
        elif isinstance(value, Command):
            self._write(self.decorate_name(value.name))
        elif isinstance(value, CO):
            self._write(self.decorate_special('CO'))
            self._print_left_brace()
            self._write(repr(self.decorate_name(value.name)))
            self._print_right_brace()
        elif isinstance(value, (list, tuple)):
            self._write(obj_start(value))

            for idx, item in enumerate(value):
                if isinstance(item, Command):
                    self._write(self.decorate_name(item.name))
                elif isinstance(item, basestring):
                    self._write("{0!r}".format(to_str(item)))
                else:
                    self._write(repr(item))

                if self._limited(idx, value, self.interrupt_value):
                    break
                self._print_delimiter(idx, value)

            self._write(obj_end(value))
        else:
            self._write("%s" % (value,))

    def _visit_keysmixing_based(self, item):
        """Visit an object based on a KeysMixing."""
        keys = sorted(item.keys())
        for idx, key in enumerate(keys):
            obj = item[key]
            if obj.undefined():
                continue
            obj.accept(self)
            self._print_delimiter(idx, keys)

    def _print_delimiter(self, idx, sequence):
        if idx != len(sequence) - 1:
            self._write(", ")

    def _print_eol(self):
        self._write('\n')

    def _print_equal(self, with_spaces=True):
        if with_spaces:
            self._write(' = ')
        else:
            self._write('=')

    def _print_left_brace(self):
        self._write('(')

    def _print_right_brace(self):
        self._write(')')

    def _limited(self, idx, sequence, string):
        """Tell if the output must be limited."""
        if (self._limit <= 0 or idx < self._limit - 1
                or idx == len(sequence) - 1):
            return False
        self._limit_reached = True
        self._print_delimiter(0, [])
        self._write(string)
        return True

    def end(self):
        """Close the export"""
        if self._limit_reached:
            self._write(self.decorate_comment(
                translate("AsterStudy",
                          "\n# sequences have been limited to the first "
                          "{} occurrences.").format(self._limit)))

    @classmethod
    def clean(cls, text):
        """Clean a text generated by *ExportToCommVisitor*."""
        text = text.replace(cls.interrupt_value, "...")
        text = text.replace(cls.interrupt_fact, "...")
        return text

    def decorate_name(self, text): # pragma pylint: disable=no-self-use
        """Decorate item's name."""
        return to_str(text)

    def decorate_title(self, text): # pragma pylint: disable=no-self-use
        """Decorate catalogue name."""
        return to_str(text)

    def decorate_keyword(self, text): # pragma pylint: disable=no-self-use
        """Decorate keyword's name."""
        return text

    def decorate_comment(self, text): # pragma pylint: disable=no-self-use
        """Decorate comment."""
        return text

    def decorate_special(self, text): # pragma pylint: disable=no-self-use
        """Decorate special word."""
        return text


def study2comm(dataset, pretty=True, **opts):
    """Exports AsterStudy Commands into code_aster COMM file format.

    By default the commands are sorted to respect their dependencies.
    Using ``sort=False`` may be required to keep the order of commands that
    have no dependencies. This is useful to have reproductible results in
    unittests.

    Use ``limit=NN`` to limit the output to the fist ``NN`` occurrences in
    sequences.
    """
    ostream = StringIO()
    export = ExportToCommVisitor(ostream, **opts)

    dataset.accept(export)
    export.end()

    value = ostream.getvalue().strip()

    text = value if not pretty else format_code(value)
    text = export.clean(text)

    return text


def _debug_write(writer): # pragma: no cover
    """Debug helper: also dump text on output"""
    import sys
    def _wrap(text):
        sys.stdout.write(text)
        writer(text)
    return _wrap
