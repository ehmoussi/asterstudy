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
Basic Command
-------------

Implementation of the basic Command.

"""

from __future__ import unicode_literals

import copy
from cStringIO import StringIO

from common import recursive_items, to_str
from ..general import (CataMixing, Validity, ConversionLevel,
                       DuplicationContext as Ctx, no_new_attributes)
from ..abstract_data_model import Node, remove_parent, add_parent
from ..catalogs import CATA
from ..visit_study import BooleanVisitor, FilterVisitor

from .helper import unregister_unit, register_unit, clean_undefined
from .helper import unregister_parent, register_parent
from .helper import unregister_cos, register_cos
from .helper import update_dependence_up

from .mixing import KeysMixing, ResultMixing, CO

from .constancy import trace_back, NonConst

class Command(Node, CataMixing, ResultMixing):
    """Implementation of the command"""
    name_length = 8
    subclass_dict_cache = None
    specific_name = None
    is_co = False
    _cache_type = None
    _validity = _check_validity = None
    _engine = _storage = _syntax_checker = _title = None
    clone = None
    __setattr__ = no_new_attributes(object.__setattr__)

    @staticmethod
    def factory(name, title, cata, syntax_checker):
        """Create a generic or specific Command object."""
        if not Command.subclass_dict_cache:
            dict_sub = {}
            for cls in Command.__subclasses__(): # pragma pylint: disable=no-member
                if cls.specific_name:
                    dict_sub[cls.specific_name] = cls
            Command.subclass_dict_cache = dict_sub

        cls = Command.subclass_dict_cache.get(title, Command)

        return cls(name, title, cata, syntax_checker)

    def __init__(self, name, title, cata, syntax_checker):
        """Constructor"""
        Node.__init__(self, name)
        CataMixing.__init__(self, cata)
        self._engine = None
        self._storage = {}
        self.cata = cata
        self._syntax_checker = syntax_checker
        self._title = title
        self.ignore_copy = Command

        self._validity = Validity.Nothing
        self._check_validity = True
        self.clone = None
        self.reset_cache_type()

    def __deepcopy__(self, memodict):
        # pragma pylint: disable=unused-argument
        """Supports native Python 'deepcopy' function protocol"""
        return self

    @property
    def storage(self):
        """Attribute that holds parameter's internal representation"""
        return copy.deepcopy(self._storage)

    @CataMixing.cata.setter # pragma pylint: disable=no-member
    def cata(self, value):
        "Declares setter for so named property"
        keywords = value.definition
        CataMixing.cata.fset(self, value) # pragma pylint: disable=no-member
        self._engine = KeysMixing(value, keywords, self._storage, self)

    def rkeys(self):
        """Returns definition *keys* in the composite structure"""
        return self._engine.rkeys()

    def keys(self):
        """Returns actual *keys* in the composite structure"""
        return self._engine.keys()

    @trace_back
    def __getitem__(self, name):
        """Returns composite structure item for the given *key*"""
        # TODO getitem is a read-only action, not? why reset_validity?
        self.reset_validity()
        return self._engine[name]

    @NonConst()
    @trace_back
    def __setitem__(self, name, value):
        """Assigns a value for the given *key*"""
        self.reset_validity()
        self._engine[name] = value

    def gettype(self, strict=ConversionLevel.Type):
        """Returns code_aster type for the given command"""
        if strict & ConversionLevel.Type:
            return self.unsafe_type()
        return self.safe_type()

    def unsafe_type(self):
        """Calculates code_aster type; raises exception in case"""
        if self._cache_type:
            return self._cache_type
        typ = self.cata.get_type_sd_prod(**self._storage)
        # if the function returns None but it should not, return `baseds`
        if CATA.expects_result(self.cata) and (not typ or typ == type(None)):
            raise TypeError
        self._cache_type = typ
        return typ

    def safe_type(self):
        """Returns code_aster type for the given command in a safe way"""
        try:
            return self.unsafe_type()
        except: # pragma pylint: disable=bare-except
            return CATA.baseds

    @property
    def type(self):
        """Returns code_aster type for the given command"""
        return self._cata.definition.get('sd_prod')

    def submit(self):
        """Submits the command changes into the Study"""
        self.reset_validity()

    def get_list_co(self):
        """Return the list of *CO* found in a storage dict with their path
        in the storage dict."""
        cos = []
        for key, node in recursive_items(self._storage):
            if isinstance(node, CO):
                cos.append((key, node))
        return cos

    @property
    def list_co(self):
        """Return the list of *CO* passed as argument."""
        return [i[1] for i in self.get_list_co()]

    @property
    def hidden(self):
        """Return the list of produced *Hidden* commands."""
        hidden = []
        from .hidden import Hidden
        for node  in self.child_nodes:
            if isinstance(node, Hidden):
                hidden.append(node)
        return hidden

    def _register_cos(self, pool_co):
        """
        Properly register all CO command args via producing corresponding
        hiddens
        """
        register_cos(self.stage, self, pool_co)

    @NonConst()
    def init(self, storage, duplication=False):
        """Initializes its context from an outside dictionary.

        During the duplication process, do not create Hidden objects from CO
        because they will be created by duplication of the previously existing
        ones.
        """
        pool_co = unregister_cos(self, delete=False)
        unregister_unit(self)
        unregister_parent(self, self._storage)

        self._storage.clear()
        self._engine.clear_cache()

        clean_undefined(storage)
        update_dependence_up(storage)

        self._storage.update(storage)

        register_parent(self, self._storage)
        # in case of duplication, do not create new COs
        if not duplication:
            self._register_cos(pool_co)
        for hid in pool_co.itervalues():
            hid.delete()

        register_unit(self)
        self.submit()

    def __call__(self, storage):
        """Initializes its context from an outside dictionary"""
        self.init(storage)
        return self

    def __mul__(self, other):
        """Supports native Python '*' operator protocol."""
        assert str(self) == str(other)

    def __eq__(self, other):
        """Supports native Python '==' operator protocol."""
        return self is other

    def __nonzero__(self):
        """Implements truth value testing '*if command*'"""
        # else __len__ would be used
        return True

    def short_repr(self):
        """Returns a short textual representation."""
        return to_str("{0.name} <from {0._title}>".format(self))

    def node_repr(self):
        """Native node representation that shows dependencies."""
        return Node.__repr__(self)

    def __str__(self):
        """Stringifies a command: returns is code_aster syntax"""
        ostream = StringIO()

        from ..study2comm import ExportToCommVisitor
        export = ExportToCommVisitor(ostream)

        comment = self.comment # Print corresponding comment first
        if comment is not None:
            comment.accept(export) # pragma pylint: disable=no-member

        self.accept(export)

        value = ostream.getvalue()

        return to_str(value[1:])

    def __repr__(self):
        """Raw representation"""
        return self.node_repr()

    @property
    def stage(self):
        """Returns corresponding parent *Stage* instance"""
        return next(node.parent_nodes[0] for node in self.parent_nodes \
                    if not isinstance(node, Command))

    @staticmethod
    def filterby(stage, astype, command=None):
        """Collects all commands in the Aster-Study Case with given *astype*"""
        commands = []
        stages = stage.preceding_stages
        for item in stages:
            commands.extend(item.commands)

        commands.extend(stage.commands)

        if command is not None:
            def _predicate(item):
                return item.depends_on(command)

            from itertools import ifilterfalse
            excommands = list(ifilterfalse(_predicate, commands))
        else:
            rcommands = reversed(commands)
            excommands = list(rcommands)

        filtered = []
        for item in excommands:
            typ = item.gettype(strict=ConversionLevel.NoFail)

            if typ is None:
                continue

            if isinstance(astype, basestring) \
                    and isinstance(typ, basestring):
                if typ in ['R', 'I'] and astype in ['R', 'I']:
                    filtered.append(item)
                elif typ == astype:
                    filtered.append(item)
            elif not isinstance(astype, basestring) \
                    and not isinstance(typ, basestring) \
                    and issubclass(typ, astype):
                filtered.append(item)

        return filtered

    def groupby(self, astype):
        """Collects all commands in the Aster-Study Case with given *astype*"""
        return Command.filterby(self.stage, astype, self)

    @property
    def title(self):
        """Attribute that holds unique *title*"""
        return self._title

    def need_reuse(self):
        """Tell if the command needs the 'reuse' argument.
        It is required if it the same name of an input keyword is used as the
        result name."""
        def _same_name(simple):
            if not isinstance(simple.value, Command):
                return False
            return simple.value.name == self.name

        visitor = BooleanVisitor(_same_name)
        try:
            self.accept(visitor)
        except StopIteration:
            pass
        return visitor.checked()

    def can_reuse(self):
        """Tell if the command can reuse the result name."""
        return self._cata.can_reuse()

    def keywords_equal_to(self, value):
        """Return the keywords that are equal to *value*."""
        def _predicate(simple):
            return simple.value == value

        visitor = FilterVisitor(_predicate)
        self.accept(visitor)
        return visitor.keywords

    def accept(self, visitor):
        """Walks along the objects tree using the visitor pattern."""
        visitor.visit_command(self)

    def init_duplicated(self):
        """Creates a copy with no connections"""
        return Command.factory(self._name, self._title,
                               self._cata, self._syntax_checker)

    @NonConst()
    def rename(self, name):
        """Renames the result of the command."""
        self.name = name

    @NonConst()
    def duplicate(self):
        """Create and return duplicated Command node."""
        return self._model.duplicate(self, context=Ctx.User)

    def update_duplicated(self, orig, **kwargs):
        """
        Callback function: attune data model additionally after a Command
        has been duplicated.

        Updates storage of the newly created Command.

        Arguments:
            orig (Command): Original Command object freshly replicated.
            context (Ctx): Context of duplication.
        """
        context = kwargs.get('context', Ctx.Nothing)
        # clear parent commands
        for parent in self.parent_nodes:
            if isinstance(parent, type(self)):
                remove_parent(self, parent)

        # tag clones
        if not context & Ctx.User:
            orig.clone = self

        if orig is not None:
            self.init(orig.storage, duplication=True)

        # update dependence downwards
        if not context & Ctx.User:
            from .helper import update_dependence_down
            update_dependence_down(orig)

    def split(self):
        """Calls parent stage's split method"""
        self.stage.split()

    @property
    def comment(self):
        "Returns related Comment Command instance"
        from .comment import Comment
        for command in self.parent_nodes:
            if isinstance(command, Comment):
                return command

        return None

    @comment.setter
    def comment(self, content):
        "Adds or updates Comment instance for the given command"
        if content is None:
            return

        comment = self.comment
        if comment is None:
            stage = self.stage
            comment = stage.add_comment(content, concatenate=False)
            add_parent(self, comment)
            comment.reorder()
        else:
            comment.content = content

    @NonConst()
    def before_remove(self):
        """Prepares to remove the command from the model.

        Removes child hidden commands that have been automatically added.
        """
        unregister_cos(self)

        comment = self.comment
        if comment is not None:
            comment.delete() # pragma pylint: disable=no-member

        try:
            unregister_unit(self)
        except KeyError:
            # the command is probably invalid
            pass

        self.stage.on_remove_command(self)

        self.reset_validity()

        self.reset_cache_type()

        return Node.before_remove(self)

    def reset_validity(self):
        """Recursively resets cachable validity flag"""
        for child in self.child_nodes:
            child.reset_validity()

        self._check_validity = True

    def reset_cache_type(self):
        """Recursively resets cachable type flag"""
        for child in self.child_nodes:
            child.reset_cache_type()

        self._cache_type = None

    def check(self, mode=Validity.Complete, safe=True):
        """Checks given validity aspect and returns corresponding status

        Arguments:
            mode (Validity): Defines the level of checking (see
                general.Validity for levels definition).
            safe (bool): If `safe` is False, an error is raised in case of
                Syntaxic error.

        Returns:
            Validity: Status of the validation.
        """
        check_all = mode == Validity.Complete
        if not self._check_validity and check_all:
            return self._validity

        # check the command position in the list, do not skip
        self.reorder()

        result = Validity.Nothing

        if mode & (Validity.Naming | Validity.Dependency):
            if not self._check_naming():
                result |= Validity.Naming

        if mode & Validity.Dependency:
            result |= self._check_dependencies()

        if mode & Validity.Syntaxic:
            result |= self._check_syntax(check_all, safe)

        if check_all:
            self._validity = result
            self._check_validity = False

        return result

    def reorder(self):
        """Check the command position in the dataset."""
        self.stage.reorder(self)

    def _check_naming(self):
        """Check the validity of the command result name."""
        if self._name == "_":
            return True

        if len(self._name) > self.name_length:
            return False

        # is it a valid python variable?
        try:
            exec self._name + " = 0" # pragma pylint: disable=exec-used
        except SyntaxError:
            return False

        return True

    def _check_dependencies(self):
        """Checks dependencies."""
        result = Validity.Nothing

        for parent in self.parent_nodes:
            if parent not in self._model:
                result |= Validity.Dependency
            elif isinstance(parent, Command):
                result |= parent.check()

        return result

    def _check_syntax(self, check_all, safe):
        """Checks syntax of the command."""
        result = Validity.Nothing

        checker = self._syntax_checker()
        if not safe:
            self._cata.accept(checker, self.storage)
            if check_all:
                self._check_validity = False
            return result

        try:
            self._cata.accept(checker, self.storage)
        except Exception: # pragma pylint: disable=broad-except
            result |= Validity.Syntaxic

        return result

    def repair(self, previous_commands):
        """Try to repair the stage in case of dependency error.

        - Search for broken dependencies: commands that are not in the model.

        - Try to fix these broken dependencies by using results with the same
          name and type.

        Returns:
            bool: True if a replacement has be done (but that does not ensure
                that the Case is valid).
        """
        def _search_compatible_commands(lost):
            for command in previous_commands:
                if command.name != lost.name:
                    continue
                if command.gettype() == lost.gettype():
                    return command
            return None

        valid = self.check(mode=Validity.Dependency)
        if valid & Validity.Dependency:
            # search for keywords with broken dependencies
            def _predicate(simple):
                cmd = simple.value
                if not isinstance(cmd, Command):
                    return False
                return cmd not in self._model

            visitor = FilterVisitor(_predicate)
            self.accept(visitor)

            # replace broken deps
            for kwd in visitor.keywords:
                replaceby = _search_compatible_commands(kwd.value)
                if replaceby is not None:
                    kwd.value = replaceby

    @property
    def categ(self):
        """[int]: Category index of the command in the data tree."""
        if self._title in ("DEBUT", "POURSUITE"):
            return -999
        elif self._title in ("FIN",):
            return 999
        elif self._title in ("_CONVERT_VARIABLE",):
            return -1000
        if self._title in ("_CONVERT_COMMENT",):
            children = [i for i in self.child_nodes if isinstance(i, Command)]
            if children:
                return children[0].categ
        return CATA.get_category_index(self._title)

    def _after_rename(self):
        """Called when command is renamed."""
        self.reset_validity()

    @property
    def child_commands(self):
        """Commands that depend upon this one"""
        return [i for i in self.child_nodes if isinstance(i, type(self))]
