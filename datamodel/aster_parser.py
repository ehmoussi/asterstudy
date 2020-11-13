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
Parser of COMM files
--------------------

Implementation of a mini parser to improve import of code_aster commands files.

"""

from __future__ import unicode_literals

import ast
import re
from StringIO import StringIO
import tokenize
import token

from common import AsterStudyError, translate, debug_message, debug_mode
from common.utilities import format_expr
from .general import ConversionLevel
from .catalogs import CATA

# mark used to identify added lines
MARK = "ASTERSTUDY_IMPORT:"


def clean_expression(text):
    """Clean expression before evaluation.

    Arguments:
        text (str): expression to clean.

    Returns:
        str: cleaned expression without trailing semi-colon.
    """
    if not hasattr(clean_expression, "re_expr"):
        clean_expression.re_expr = re.compile("[; ]*$")
    return clean_expression.re_expr.sub("", text)


def _change_text(text):
    """Pre-processing of the input text.

    - Wrap constant parameters:

      ``a = 1`` is converted as ``a = _CONVERT_VARIABLE(EXPR="1")``

    - Wrap comments:

      ``# line of comment.`` is converted as
      ``_CONVERT_COMMENT(EXPR="# line of comment.")``

    Returns:
        list[int]: list of line numbers of end of instruction.
        str: changed text.
    """
    generator = tokenize.generate_tokens(StringIO(text).readline)
    result = []
    buff = []
    eoi = []
    started = False
    for ret in generator:
        num, val = ret[:2]
        started = started or num == token.NAME
        # _debug_parse(num, val, ret[4])
        if num == token.NEWLINE:
            eoi.append(ret[2][0])
        buff.append((num, val))
        if num in (token.NEWLINE, token.ENDMARKER):
            buff = _replace_variable(buff)
            started = False
        elif num == tokenize.COMMENT and len(buff) == 1:
            # ignore inline comment
            buff = _replace_comment(buff)
            started = False
        if not started:
            result.extend(buff)
            # _debug_parse(tokenize.COMMENT, "> > > new buffer > > >", "???")
            buff = []
    changed = tokenize.untokenize(result)
    debug_message("Pre-processed text:\n", changed)
    return eoi, changed


def change_text(text, strict):
    """Check for unsupported features and change text."""
    # _inc = re.compile(r"^ *INCLUDE *\(", re.M)
    replace = strict & ConversionLevel.Partial != 0
    for expr, msg in [
            (r"^ *(if|for|import|from|try|def)\b",
             translate("AsterStudy",
                       "Python statements can not be edited in graphical mode."
                       "\nYou can only edit this commands file in text mode.")),
            (r"^(.*?\[ *None *\])",
             translate("AsterStudy",
                       "List of code_aster results is not supported.")),
            (r"^ *[^#]*DEFI_FICHIER",
             translate("AsterStudy",
                       "Command DEFI_FICHIER is not supported in "
                       "graphical mode.")),
            (r"^ *[^#]*INCLUDE",
             translate("AsterStudy",
                       "Command INCLUDE is not supported in "
                       "graphical mode, please add a stage instead.")),
        ]:
        err = _check_unsupported(text, expr, msg, replace)
        if err:
            text = err
            break
    return _change_text(text)


def _check_unsupported(text, expr, message, replace):
    """Check if the text contains an unsupported feature.

    In this case, it returns a text that will raise an exception,
    else it returns None.
    """
    _expr = re.compile(expr, re.M)
    mat = _expr.search(text)
    if mat:
        fmt = "raise NotImplementedError({0!r})"
        error = fmt.format(MARK + " " + message)
        if replace:
            error = _expr.sub(error + "\n" + mat.group(1), text)
        return error


def _replace_variable(buff):
    """Replacement for user variable."""
    opsep = (token.OP, ';')
    try:
        idx = buff.index(opsep)
    except ValueError:
        idx = -1
    if idx > 0 and idx != len(buff) - 1:
        return (_replace_variable(buff[:idx] + [opsep]) +
                _replace_variable(buff[idx + 1:]))

    num = [i[0] for i in buff[:3]]
    val = [i[1] for i in buff[:3]]
    if num[:2] == [token.NAME, token.OP] and val[1] == "=":
        commands = [name for name in CATA]
        if num[2] == token.NAME and val[2] in ("CO",):
            # insert an error: raise NotImplementedError
            buff = [
                (token.NAME, "raise"),
                (token.NAME, "NotImplementedError"),
                (token.OP, "("),
                (token.STRING, '"can not assign a \'CO()\' in a Python '
                               'variable"'),
                (token.OP, ")"),
                buff[-1],
            ] + buff # pragma: no cover
        elif num[2] != token.NAME or val[2] not in commands:
            rvalue = ' '.join(i[1] for i in buff[2:-1])
            expr = format_expr(rvalue)
            buff = [
                (token.NAME, val[0]),
                (token.OP, "="),
                (token.NAME, "_CONVERT_VARIABLE"),
                (token.OP, "("),
                (token.NAME, "EXPR"),
                (token.OP, "="),
                (token.STRING, repr(expr)),
                (token.OP, ")"),
                buff[-1],
            ]
    return buff


def _replace_comment(buff):
    """Replacement for comment."""
    # remove comment mark
    text = buff[0][1]
    text = re.sub("^ *# ?", "", text)
    wrap = [
        (token.NAME, "_CONVERT_COMMENT"),
        (token.OP, "("),
        (token.NAME, "EXPR"),
        (token.OP, "="),
        (token.STRING, repr(text)),
        (token.OP, ")")
    ]
    return wrap


def is_empty_comment(comment):
    """Tells if the comment contains no text"""
    null = re.escape(r" -+=*#/_$%:,.!§\\")
    return re.search('^ *#[{0}]*$'.format(null), comment.strip()) is not None


def _debug_parse(num, val, line): # pragma: no cover
    """Debug helper"""
    if debug_mode():
        if num == token.NEWLINE:
            snum = "*" * 12
        elif num == tokenize.NL:
            snum = "+" * 12
        elif num == tokenize.COMMENT:
            snum = "#" * 12
        else:
            snum = token.tok_name[num]
        fmt = "{0:<12} {1!r:<20}: {2!r}"
        debug_message(fmt.format(snum, val, line))

def is_cmd_called(text, title):
    """
    If valid python syntax, looks for a call of a callable named 'title'

    Returns:
        *True*: if syntactically correct and callable called
        *False*: if syntactically correct and callable not called

    Raises:
        SyntaxError: if not correct python syntax
    """
    try:
        asttree = ast.parse(text)
    except SyntaxError as err:
        errmsg = translate("AsterStudy",
                           "Syntax error when looking for the command '{0}' "
                           "in a python file.".format(title))
        raise AsterStudyError(errmsg, str(err))
    for node in ast.walk(asttree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == title:
                return True
    return False

def add_debut_fin(text, start):
    """Add DEBUT and FIN commands to text if necessary.

    Arguments:
        text (str): Input text of a commands file.
        start (bool): *True* if it starts the case.

    Returns:
        str: Text of the commands file enclosed by DEBUT/FIN.
    """
    first_cmd = 'DEBUT' if start else 'POURSUITE'
    try:
        if not is_cmd_called(text, first_cmd):
            text = first_cmd + str('()\n\n') + text
        if not is_cmd_called(text, str("FIN")):
            text += str('\nFIN()')
    except AsterStudyError:
        # text unchanged
        pass
    return text
