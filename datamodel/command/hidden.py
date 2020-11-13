# -*- coding: utf-8 -*-

# Copyright 2016 EDF R&D i
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
Hidden Command
--------------

Implementation of the Hidden as a specfic Command sub class.

"""

from __future__ import unicode_literals

from ..general import no_new_attributes
from .basic import Command


class Hidden(Command):
    """Special command to store a result of a macro-command.

    Macro-commands can create results that are not direct results of the
    operator (on the left of the equal sign).
    This syntax is not Python compliant but must be supported to work with
    the current versions of code_aster.

    *Hidden* allows to manage the creation of these additional results
    with a valid Python syntax.

    This looks like::

        # code_aster syntax
        res1 = MACRO_COMMAND(RESULT2=CO('res2'), <other keywords...>)
        ANOTHER(USE=res2)

        # asterstudy objects (symbolic)
        macro = Command(RESULT2=CO('res2'), ...)
        hidden = Hidden(DECL=<CO object>, PARENT=macro)

        # asterstudy objects (API)
        macro = stage('MACRO_COMMAND', 'res1')
        macro['RESULT2'] = 'res2'
        hidden = stage['res2']

    The *Hidden* is automatically created when a keyword with type 'CO'
    is assigned in the parent *Command*.

    """
    specific_name = '_RESULT_OF_MACRO'
    _parent_id = None
    __setattr__ = no_new_attributes(object.__setattr__)

    @property
    def parent_id(self):
        """Attribute that holds the uid of the parent *Command*."""
        # store id no to add cyclic reference
        return self._parent_id

    def init(self, storage, duplication=None):
        """Initializes its context from an outside dictionary"""
        self._parent_id = storage['PARENT'].uid
        super(Hidden, self).init(storage)

    def accept(self, visitor):
        """Walks along the objects tree using the visitor pattern."""
        visitor.visit_hidden(self)

    def _register_cos(self, _):
        """Overrides corresponding 'Command._register_cos' method with dummy."""

    def init_duplicated(self):
        """Create empty duplicate."""
        return Hidden(self.name, self.title, self.cata, self._syntax_checker)

    def update_duplicated(self, orig, **kwargs):
        """
        Callback function: attune data model additionally after a Hidden
        has been duplicated.

        Updates parent id.

        Arguments:
            orig (Hidden): Original Hidden object freshly replicated.
            duplicated_nodes (dict): Links `node: duplicated_node`.
        """
        super(Hidden, self).update_duplicated(orig, **kwargs)

        dups = kwargs['duplicated_nodes']
        new_parent = dups[self._model.get_node(orig.parent_id)]
        self._parent_id = new_parent.uid
