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
DataSet
-------

Implementation of dataset within a stage.

There are two specializations of *datasets*: *GraphicalDataSet* and
*TextDataSet*.

"""

from __future__ import unicode_literals

import itertools

from common import debug_message
from .abstract_data_model import Node, add_parent, remove_parent
from .general import no_new_attributes
from .command import Command, Comment, Variable
from .command.helper import deleted_by
from .catalogs import CATA


class DataSet(Node):
    """Implementation of the base class for datasets."""

    _mode = None
    graphicalMode = 0
    textMode = 1

    __setattr__ = no_new_attributes(object.__setattr__)

    @staticmethod
    def factory(mode):
        """Create a dataset object of the provided type.

        Arguments:
            mode (int): Type of the dataset; one of
                *DataSet.graphicalMode*, *DataSet.textMode*.

        Returns:
            DataSet: New dataset.
        """
        if mode == DataSet.graphicalMode:
            cls = GraphicalDataSet
        elif mode == DataSet.textMode:
            cls = TextDataSet
        else:
            raise NotImplementedError("unknown mode: {0!r}".format(mode))
        return cls()

    def __init__(self):
        """Create dataset."""
        Node.__init__(self, "DataSet")
        self.delete_children = Command

    # public interface
    @property
    def stage(self):
        """Stage: Attribute that holds a parent *Stage* of dataset."""
        return self.parent_nodes[0] if self.has_parents() else None

    @property
    def mode(self):
        """int: Attribute that holds a type of dataset.

        Result is one of *DataSet.graphicalMode*, *DataSet.textMode*.
        """
        return self._mode

    def is_graphical_mode(self):
        """Tell if the dataset is a graphical one.

        Returns:
            bool: *True* if this is a graphical dataset; *False*
            otherwise.
        """
        return self.mode == DataSet.graphicalMode

    def is_text_mode(self):
        """Tell if the dataset is a text one.

        Returns:
            bool: *True* if this is a text dataset; *False* otherwise.
        """
        return self.mode == DataSet.textMode

    def accept(self, visitor):
        """Walk along the objects tree using the visitor pattern.

        Arguments:
            visitor (any): Visitor object.
        """
        visitor.visit_dataset(self)

    @property
    def preceding_stages(self):
        """list[Stage]: Attribute that provides access to the preceding
        stages for this dataset."""
        return self.stage.parent_case[:self.stage]

    def reorder(self, command=None):
        """Reorder commands in a DataSet."""
        raise NotImplementedError('Must be defined in a subclass.')

    @property
    def commands(self):
        """
        list[Command]: Attribute that holds list of *commands*
        associated with the dataset (sorted by dependency).
        """
        return self.subnodes(lambda node: isinstance(node, Command))


STARTER = 0x01
DELETED_NAMES = 0x02
DELETERS = 0x3


class GraphicalDataSet(DataSet):
    """Implementation of the graphical dataset.

    Contains a set of Command objects.

    Attributes:
        _ids (list<int>): List of Command ids that defines the order.
        _cache (dict): Cached informations.
    """

    _mode = DataSet.graphicalMode
    _ids = _cache = None
    __setattr__ = no_new_attributes(object.__setattr__)

    def __init__(self):
        """Create dataset."""
        DataSet.__init__(self)
        self._ids = []
        self._reset_cache()

    def add_command(self, command_type, name=None):
        """Add a command into the dataset.

        Arguments:
            command_type (str): Type of the command (in a catalogue).
            name (Optional[str]): Name of the command. Defaults to
                *None*; in this case name is automatically generated for
                the command.

        Returns:
            Command: Command just added.
        """
        cata = CATA.get_catalog(command_type)
        syntax_checker = CATA.package('Syntax').SyntaxCheckerVisitor
        command = Command.factory(name, command_type, cata, syntax_checker)

        if not name:
            name = self.stage.parent_case.generate_name(command)
            command.name = name

        last_command = self.get_last_command()

        self._model.add(command, self)

        if isinstance(last_command, Comment):
            if last_command.nb_children == 0:
                if not isinstance(command, Comment):
                    add_parent(command, last_command)

        self._set_position(command)

        return command

    def add_variable(self, var_name, var_expr):
        """Add a Variable instance into the dataset.

        Arguments:
            var_name (str): Name of the variable.
            var_expr (str): Right side variable expression.

        Returns:
            Variable: Variable just added.
        """
        if var_name in Variable.context(self.stage):
            raise NameError("name {0!r} is already in use".format(var_name))

        engine = self.add_command(Variable.specific_name)

        engine.update(var_expr, var_name)

        return engine

    def add_comment(self, content, concatenate=True):
        """Add a Comment instance into the dataset.

        Arguments:
            content (str): content of the (optionaly multiline) Comment.

        Returns:
            Comment: Comment just added.
        """
        engine = self.get_last_command() if concatenate else None

        if isinstance(engine, Comment):
            engine /= content
        else:
            engine = self.add_command(Comment.specific_name)
            engine.content = content

        return engine

    def get_cmd(self, uid):
        """Shortcut to get a command from the model."""
        return self.model.get_node(uid)

    def _reset_cache(self):
        """Reinitialize the informations about the commands ordering."""
        self._cache = dict()
        self._cache[DELETED_NAMES] = {}
        self._cache[DELETERS] = {}

    def get_ids(self, but=None):
        """Ensure that `_ids` contains all the child commands excepting
        those of `but`.

        Returns:
            list[int]: Current list of commands ids.
        """
        but = but or []
        children = [i.uid for i in self.child_nodes if isinstance(i, Command)]
        if set(self._ids).union(but).symmetric_difference(children):
            self._ids = children
            self.reorder()
        return self._ids

    def _set_position(self, command):
        """Insert a command at the right position."""
        self._before_insert(command)
        self._insert_id(command)
        self._after_insert(command)

    def _discard_position(self, command):
        """Remove an element from the list if it is a member."""
        try:
            self._ids.remove(command.uid)
        except ValueError:
            pass

    def reorder(self, command=None):
        """Ask reordering of one or all commands."""
        if command is None:
            self._reset_cache()
            for uid in self._ids[:]:
                self._set_position(self.get_cmd(uid))
        else:
            self._set_position(command)

    def __contains__(self, given):
        """
        Support native Python "in" operator protocol.

        Arguments:
            given (Command or str): Command being checked.

        Returns:
            bool: *True* if Command is contained in the Stage; *False*
            otherwise.
        """
        if isinstance(given, Command):
            return next((True for command in self if command is given), False)

        return next((True for command in self if command.name == given), False)

    def __getitem__(self, given):
        """
        Support native Python ``[]`` operator protocol.

        Get particular command(s) from the Stage or DataSet:

        - ``stage[N]`` returns the ``N-1``-th command of the stage.

        - ``stage[name]`` returns the last command of the stage and its
          preceding stages that matches this ``name``.

        - ``stage[name:N]`` returns the ``N-1``-th command of the stage and its
          preceding stages that matches this ``name``.

        - ``stage[name:command]`` returns the last command of the stage and its
          preceding stages that matches this ``name`` and **does not** depend
          on ``command``.

        Note:
            *First*, *last*, or *N-1-th command* means that commands
            are sorted by dependency.

        Arguments:
            given (str, int, slice): Command's name, index or indices
                range.

        Returns:
            Command or list[Command]: Command or commands specifying
            search criterion.
        """
        # self[i] case
        if isinstance(given, int):
            return self.commands[given]

        # self[command:] case
        if isinstance(given, slice) and isinstance(given.start, Command):
            return itertools.dropwhile(lambda x: x is not given.start, self)

        commands = []
        stages = self.preceding_stages
        for stage in stages:
            commands.extend(stage.dataset.commands)

        commands.extend(self.commands)

        rcommands = reversed(commands)
        # self['name'] case
        if not isinstance(given, slice):
            return next(cmd for cmd in rcommands if cmd.name == given)

        # self[:i] case
        if isinstance(given.stop, int):
            excommands = [cmd for cmd in rcommands if cmd.name == given.start]
            return excommands[given.stop]

        # self['name':command] case
        def _predicate(item):
            return item.depends_on(given.stop)

        excommands = list(itertools.dropwhile(_predicate, rcommands))

        return next(cmd for cmd in excommands if cmd.name == given.start)

    def on_remove_command(self, command):
        """Remove the command from the dataset."""
        self._clear_artificial_deps(command)
        self._discard_position(command)

    @property
    def sorted_commands(self):
        """Return the pre-sorted list of commands.

        The commands are grouped by category and then sorted by dependency
        and uid.

        Returns:
            list: Pre-sorted list of commands.
        """
        return [self.get_cmd(uid) for uid in self.get_ids()]

    def get_last_command(self):
        """Return the last created command.

        Returns:
            Command: Last created command (with the highest uid).
        """
        if len(self) == 0:
            return None

        last_uid = self.children[-1]
        return self._model.get_node(last_uid)

    def before_remove(self):
        """Prepares to remove the dataset from the model.

        Removes commands that have been added.
        """
        self.clear()

        return Node.before_remove(self)

    def clear(self):
        """Remove all commands."""
        for command in reversed(self.commands):
            if not command.is_valid():
                continue
            command.delete()

    def __len__(self):
        """Get the dataset length.

        Returns:
            int: Length of dataset which is equal to the number of
            commands stored in the dataset."""
        return len(self.commands)

    def __iter__(self):
        """Iterate over the commands stored in the dataset."""
        return iter(self.commands)

    def init_duplicated(self):
        """
        Callback function: called when this dataset is duplicated.

        Bare duplication: Create new empty dataset of the corresponding type.

        Returns:
            DataSet: New empty dataset.
        """
        return self.__class__()

    def update_duplicated(self, orig, **kwargs): # pragma pylint: disable=unused-argument
        """Sets all clones to *None*.

        Arguments:
            orig (DataSet): Original DataSet object freshly replicated.
        """
        for cmd in self.commands + orig.commands:
            cmd.clone = None

    def _insert_id(self, command):
        """Insert a command at the right position."""
        self._discard_position(command)
        idx = 0

        ids = self._ids
        cmdid = command.uid
        for i, uid in enumerate(ids):
            # if command is a child of cmd_i
            if self._model.has_path(uid, cmdid):
                pass
            # elif cmd_i is a child of command:
            elif self._model.has_path(cmdid, uid):
                break
            # no direct dependencies
            else:
                # if command depends on a command that follows,
                # do not use other criteria
                deps = False
                for idj in ids[i + 1:]:
                    # if command is a child of cmd_idj:
                    if self._model.has_path(idj, cmdid):
                        deps = True
                        break
                if deps:
                    idx += 1
                    continue
                cmd_i = self.get_cmd(uid)
                if command.categ < cmd_i.categ:
                    # debug_message("criteria: category", level=2)
                    break
                elif command.categ == cmd_i.categ:
                    if command.uid < uid:
                        # debug_message("criteria: creation order", level=2)
                        break
            idx += 1

        debug_message("insert at", idx, ':', command.title, repr(command))
        ids.insert(idx, command.uid)

    def _before_insert(self, current):
        """Checkings run before inserting a command.

        Arguments:
            current (Command): Command that is inserting.
        """
        if self._cache.get(STARTER):
            # all the commands except comments and variables
            # depend on the starter
            if not isinstance(current, (Comment, Variable)):
                add_parent(current, self._cache[STARTER])
        elif current.title in ("DEBUT", "POURSUITE"):
            self._cache[STARTER] = current

        # has an object with the same name been deleted?
        deleters = self._cache[DELETED_NAMES].get(current.name, [])
        found = False
        for delcmd in deleters:
            # is it 'current'?
            found = current in self._cache[DELETERS][delcmd.uid]
            if found:
                break
        # if 'current' has not been deleted, it must depend on all the deleters
        if not found:
            for delcmd in deleters:
                if not delcmd.depends_on(current):
                    add_parent(current, delcmd)

    def _clear_artificial_deps(self, command):
        """Clear "artifical" dependencies related to the deletion
        of a command."""
        uids = self._cache[STARTER].uid if self._cache.get(STARTER) else -1
        # remove relationship with DEBUT
        if command.uid == uids:
            for child in command.child_nodes:
                remove_parent(child, command)
            del self._cache[STARTER]

    def _after_insert(self, _):
        """Additional tasks executed after inserting a command.

        Arguments:
            current (Command): Command that is inserting.

        Returns:
            list<Command>: List of Command objects changed.
        """
        # Cached info:
        # - dict('result_name': [DETRUIRE Commands])
        # - dict(DETRUIRE Command: [deleted Commands])
        deleters = self._cache[DELETED_NAMES] = {}
        names = self._cache[DELETERS] = {}
        for uid in self._ids:
            command = self.get_cmd(uid)
            deleted = deleted_by(command)
            if deleted:
                names[command.uid] = deleted
                for rmcmd in deleted:
                    deleters[rmcmd.name] = deleters.get(rmcmd.name, [])
                    deleters[rmcmd.name].append(command)
        return []


class TextDataSet(DataSet):
    """Implementation of the text dataset.

    Contains only the text of a code_aster commands file.
    """

    _mode = DataSet.textMode

    _text = None
    __setattr__ = no_new_attributes(object.__setattr__)

    def __init__(self):
        """Create dataset."""
        DataSet.__init__(self)
        self._text = ""

    @property
    def text(self):
        """str: Attribute that holds *text* of the TextDataSet."""
        return self._text

    @text.setter
    def text(self, text):
        self._text = text

    def append_text(self, text):
        """Append text to the content.

        Arguments:
            text (str): Text being added.
        """
        self._text += text

    def __len__(self):
        """Get the dataset length.

        Returns:
            int: Length of dataset which is equal to the number of
            text lines stored in the dataset."""
        return len(self._text.strip().split('\n')) - 1

    def __mul__(self, other):
        """Support native Python '*' operator protocol."""
        assert self.text == other.text

    def init_duplicated(self):
        """Text is copied into content"""

        res = self.__class__()
        res.text = self.text
        return res

    def reorder(self, _=None):
        """Does nothing for a TextDataSet."""
