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
Stage
-----

Implementation of a stage within the study case.

"""

from __future__ import unicode_literals

from functools import wraps
import re

from common import ConversionError, format_code, to_str
from .file_descriptors import Mixing as FDMixing
from .general import (Validity, DuplicationContext as Ctx, ConversionLevel,
                      no_new_attributes)
from .abstract_data_model import Node, add_parent, remove_parent
from .result import StageMixing as RStageMixing
from .dataset import DataSet
from .command import Command, NonConstStage as NonConst
from .command.helper import deleted_by
from .comm2study import comm2study
from .study2comm import study2comm
from .aster_parser import MARK, add_debut_fin


def only_on(mode):
    """
    Decorator to check that the Stage object is in graphical/text mode.

    Arguments:
        method (method): Object's wrapped method.
        mode (str): Required mode: "graphical" or "text".
    """
    def wrapped_method(method):
        """Decorate the method of *Stage*."""
        @wraps(method)
        def wrapper(self, *args, **kwds):
            """wrapper"""
            if (mode == "graphical" and not self.is_graphical_mode()) or \
                    (mode == "text" and not self.is_text_mode()):
                raise TypeError("Not allowed in {} mode".format(mode))
            return method(self, *args, **kwds)
        return wrapper
    return wrapped_method


class Stage(Node, FDMixing, RStageMixing):
    """Implementation of the stage.

    A Stage has a restricted number of children:

    - one child of type DataSet (GraphicalDataSet or TextDataSet).
    - one child of type Result.
    """
    _number = _dataset = _calling_case = _convmsg = None
    __setattr__ = no_new_attributes(object.__setattr__)

    def __init__(self, name, number=0):
        """
        Create Stage object.

        Arguments:
            name (str): Name of a Stage.
            number (Optional[int]): Ordinal number of Stage within
                parent Case. Defaults to 0.
        """
        RStageMixing.__init__(self)
        Node.__init__(self, name)
        FDMixing.__init__(self)

        self.shallow_copy = type(self)
        self._number = number
        self._dataset = None
        self._calling_case = None
        self._convmsg = None

        self.delete_children = (type(self), DataSet)

    @property
    def number(self):
        """int: Attribute that holds the index number of the Stage
        in the parent Case."""
        return self._number

    @number.setter
    def number(self, number):
        self._number = number

    @property
    def parent_case(self):
        """Case: Attribute that holds the parent Case owning this
        Stage."""
        cases = self.cases
        return cases[0] if cases else None

    @property
    def cases(self):
        """list[Case]: Attribute that holds all cases which contain this
        Stage."""
        from .case import Case
        return [i for i in self.parent_nodes if isinstance(i, Case)]

    @property
    def child_stages(self):
        """list[Stage]: Attribute that holds child Stages of this
        Stage."""
        return [i for i in self.child_nodes if isinstance(i, Stage)]

    @property
    def parent_stage(self):
        """list[Stage]: Attribute that holds child Stages of this
        Stage."""
        if self.number > 1:
            return next(i for i in self.parent_nodes if isinstance(i, Stage))
        else:
            return None

    @property
    def dataset(self):
        """DataSet: Attribute that holds the Stage's DataSet."""
        if self._dataset is not None:
            return self._dataset

        objects = [child for child in self.child_nodes \
                   if isinstance(child, DataSet)]

        # assert objects, "DataSet is not yet initialized!"
        if not objects:
            # the DataSet is not yet initialized!
            return None

        assert len(objects) == 1, "too much DataSet children!"
        self._dataset = objects[0]

        return self._dataset

    @dataset.setter
    def dataset(self, dataset):
        """Assign or replace the dataset object."""
        if self._dataset is not None:
            self._dataset.delete()

        if dataset is not None:
            self._dataset = self._model.add(dataset, self)

    @property
    def mode(self):
        """int: Attribute that holds a type of Stage
        (see *DataSet.mode()*)."""
        return self.dataset.mode if self.dataset is not None else None

    @property
    def calling_case(self):
        """Case the stage was accessed by"""
        return self._calling_case

    @calling_case.setter
    def calling_case(self, value):
        """Setter for the calling case"""
        self._calling_case = value

    @Node.name.setter # pragma pylint: disable=no-member
    @NonConst(True)
    def name(self, name):
        """Redefine name setter in order to decorate it"""
        # I am compelled to copy the content of Node.name.setter here
        if self._name != name:
            self._name = name
            self._after_rename()

    def accept(self, visitor):
        """
        Walk along the objects tree using the visitor pattern.

        Arguments:
            visitor (any): Visitor object.
        """
        visitor.visit_stage(self)

    def use_graphical_mode(self, strict=ConversionLevel.NoFail):
        """
        Convert the child *DataSet* in a graphical one.

        If the current *DataSet* is not initialized, it is created.

        Does nothing if the DataSet is already a graphical one.

        Arguments:
            strict (Optional[ConversionLevel]): Tells how strict the conversion
                must be. For more details, see `general.ConversionLevel`.
                Default is not to fail.

        Raises:
            TypeError: If parent Stage is a text one;
            comm2study.ConversionError: If the import fails.
        """
        self.reset_conv()
        if self.dataset is None:
            self.dataset = DataSet.factory(DataSet.graphicalMode)
            return

        if self.is_graphical_mode():
            return

        if not self.can_use_graphical_mode():
            raise TypeError("Parent stage is in text mode, can not switch"
                            " to graphical mode")

        self._2graphical(strict)

    @NonConst(True)
    def _2graphical(self, strict):
        """
        conversion to graphical, once all checks done
        """
        dataset = self.dataset
        self.dataset = DataSet.factory(DataSet.graphicalMode)

        # let the caller checking if ConversionError is raised
        try:
            comm2study(dataset.text, self, strict=strict)
        except ConversionError as exc:
            self.dataset = dataset
            self._convmsg = exc
            raise

    def paste(self, snippet):
        """Pastes the given text Code-Aster snippet at the tail of the stage"""
        result = []

        current_mode = self.mode
        if current_mode == DataSet.graphicalMode:
            num = len(self)
            last = self[num - 1] if num else None
            self.text_mode_on(check_consecutive_stages=False)

        current_text = self.get_text()
        if current_text.endswith('\n') or snippet.startswith('\n'):
            text = current_text + snippet
        else:
            text = current_text + '\n' + snippet

        self.set_text(text)

        if current_mode != DataSet.graphicalMode:
            result.append(self)
            return result

        try:
            self.use_graphical_mode()
        except Exception as exc:
            self.set_text(current_text)
            self.use_graphical_mode()
            raise exc

        for i in xrange(num, len(self)):
            result.append(self[i])

        if not result:
            new_num = len(self)
            new_last = self[new_num - 1] if new_num else None
            if last is not None and new_last is not None:
                try:
                    last * new_last
                except AssertionError:
                    result.append(new_last)

        return result

    def text_mode_on(self, check_consecutive_stages):
        """
        Convert the child *DataSet* in a text one.

        If the current *DataSet* is not initialized, it is created.

        Does nothing if the DataSet is already a text one.

        Raises:
            TypeError: If parent Stage is a graphical one.
        """
        self.reset_conv()
        if self.dataset is None:
            self.dataset = DataSet.factory(DataSet.textMode)
            return

        if self.is_text_mode():
            return

        self._2text(check_consecutive_stages)

    def use_text_mode(self):
        """
        Convert the child *DataSet* in a text one.

        If the current *DataSet* is not initialized, it is created.

        Does nothing if the DataSet is already a text one.

        Raises:
            TypeError: If parent Stage is a graphical one.
        """
        self.text_mode_on(check_consecutive_stages=True)

    @NonConst(True)
    def _2text(self, check_consecutive_stages):
        """
        Conversion to text, once all checks have been done
        """
        if check_consecutive_stages and not self.can_use_text_mode():
            raise TypeError("Child stage is in graphical mode, can not switch"
                            " to text mode")

        text = study2comm(self.dataset)

        for handle in self.handle2info.values():
            handle.clear()

        self.dataset = DataSet.factory(DataSet.textMode)
        self.dataset.text = text

    def is_graphical_mode(self):
        """
        Tell if the Stage is currently based on a GraphicalDataSet.

        Returns:
            bool: *True* if Stage is graphical one; *False* otherwise.
        """
        return self.dataset is not None and self.dataset.is_graphical_mode()

    def is_text_mode(self):
        """
        Tell if the Stage is currently based on a TextDataSet.

        Returns:
            bool: *True* if Stage is text one; *False* otherwise.
        """
        return self.dataset is not None and self.dataset.is_text_mode()

    def can_use_graphical_mode(self):
        """
        Check if stage can be switched to the graphical mode.

        The stage can be switched to the graphical mode only if there
        are no preceeding text stages in parent case.

        Returns:
            bool: *True* if the stage can be switched to the graphical
            mode; *False* otherwise.
        """
        parent_stage = self.parent_case.get_stage_by_num(self.number - 1)
        return self.is_text_mode() and \
            (parent_stage is None or parent_stage.is_graphical_mode())

    def can_use_text_mode(self, *args):
        """
        Check if stage can be switched to the text mode.

        The stage can be switched to the text mode only if there
        are no subsequent graphical stages in parent case.

        Returns:
            bool: *True* if the stage can be switched to the text
            mode; *False* otherwise.
        """
        return self.is_graphical_mode() \
           and self.recursive_can_use_text(*args)

    def recursive_can_use_text(self, testall=True):
        """Returns *True* if child stages are in text mode.

        Arguments:
            testall (bool): *True* if all child stages should be tested
                            (useful for script operations),
                            *False* if only those from selected case should
                            (useful for GUI operations).
        """
        if testall:
            # no graphical stages among all children
            childlist = self.child_stages
        else:
            # no graphical stages among calling_case's stages
            calling_case = self.calling_case if self.calling_case is not None \
                                             else self.model.current_case # pragma pylint: disable=no-member
            child = calling_case.get_stage_by_num(self.number + 1) # pragma pylint: disable=no-member
            childlist = [child] if child is not None else []


        for stage in childlist:
            if stage.is_graphical_mode() or \
                not stage.recursive_can_use_text(testall):
                return False
        return True

    @NonConst(True)
    def rename(self, name):
        """
        Rename the Stage.

        Arguments:
            name (str): New name.
        """
        self.name = name

    def copy(self):
        """
        Create a copy of this Stage.

        Note:
            Unlike `duplicate()`, this method creates copy of the Stage
            that does not have parents; only child relations are
            duplicated.

        Returns:
            Stage: A copy of this Stage.
        """
        return self._model.duplicate(self, only_children=True)

    @NonConst(False)
    def duplicate(self, parent_case=None, context=Ctx.Nothing):
        """
        Create a copy of this Stage.

        Arguments:
            parent_case (Optional[Case]): Case to which the new Stage
                shall be related. Defaults to *None*.

        Returns:
            Stage: A copy of this Stage.
        """
        return self._model.duplicate(self,
                                     parent_case=parent_case,
                                     context=context)

    def init_duplicated(self):
        """
        Callback function: called when this Stage is duplicated.

        Bare duplication: Create new empty Stage.

        Returns:
            Stage: New empty Stage.
        """
        return Stage(self.name, self.number)


    def update_duplicated(self, orig, **kwargs):
        """
        Callback function: Attune data model additionally after a Stage
        has been duplicated.

        Updates relationship of the newly created stage.

        After duplication this new stage (*self*):

        - has the *parent_case* of *orig*;
        - is a child all the parents of *orig*;
        - is a child of *parent_case* passed to *duplicate()*.

        Useful when modifying a stage.

        Arguments:
            orig (Stage): the original Stage object freshly replicated.
            parent_case (Optional[Case]): Case to which the Stage shall
                be related. Defaults to *None*.
            context (Ctx): Context of duplication.
        """
        parent_case = kwargs.get('parent_case')
        context = kwargs.get('context', Ctx.Nothing)
        # copy datafiles, reassociate commands?
        for handle, info in orig.handle2info.viewitems():
            new = self.handle2info[handle]
            new.copy_from(info)

        # remove all stages as _children attributes
        self._clear_child_stages()

        # remove all parents
        for parent in self.cases:
            remove_parent(self, parent)

        # add relation new case -> new stage
        add_parent(self, parent_case)

        if parent_case is None:
            return

        # remove relationship new case -> old stage
        remove_parent(orig, parent_case)

        # new child Stage
        next_stage = parent_case.get_stage_by_num(orig.number + 1)

        if next_stage is not None:
            add_parent(next_stage, self)

            # clear relation between next stage and orig
            if orig in next_stage.parent_nodes:
                remove_parent(next_stage, orig)

        if context & Ctx.AutoDupl:
            # switch results between orig and self
            self.result, orig.result = orig.result, self.result

            # result contains a ref to the stage, to be switched as well
            self.result.stage, orig.result.stage = \
            orig.result.stage, self.result.stage

            # copy embedded files to the new location
            orig.copy2tmpdir()

    def _clear_child_stages(self):
        """Remove all children of the Stage kind."""
        for child in self.child_stages:
            remove_parent(child, self)

    @NonConst(False)
    def split(self):
        """
        If stage referenced by several cases, creates a duplicate
        for any case except the parent case

        Returns:
            Stage: stage contained by calling case,
                or by parent_case if there is no calling case
        """
        # the calling keeps the instance
        # or the parent if calling is None
        calling_case = self.calling_case if self.calling_case in self.cases \
                                         else self.parent_case
        self._split_algo(calling_case)

    def _split_algo(self, calling_case):
        """
        Algorithm to split a case.
        """
        try:
            case = next(i for i in self.cases if i is not calling_case)
        except StopIteration:
            return
        if self.number is not calling_case.nb_stages:
            late_stage = calling_case[self.number]
            late_stage._split_algo(calling_case) # pragma pylint: disable=protected-access

        self._split_helper(case, calling_case)

    def _split_helper(self, case, calling_case):
        """
        Helper function to duplicate child stages recursively.
        Useful in the automatic duplication context.
        """

        original = []

        if case is self.parent_case:
            assert case is not calling_case
            # make the calling_case the new parent
            for stage in reversed([i for i in case]):
                original.append((stage, stage.parent_case))
                stage.move_parent(calling_case, 0)
                assert stage.parent_case is calling_case \
                    or stage.number > self.number

        case.own_stages_from(self.number, context=Ctx.AutoDupl)

        # return to earlier parentship
        for stage, parent in original:
            stage.move_parent(parent, 0)

        # any other case pointing to `self` or its successor stages
        # should point to the corresponding stages in `case`
        for i in xrange(self.number-1, \
                        min(case.nb_stages, calling_case.nb_stages)):
            stage = calling_case[i]
            clist = [k for k in stage.cases if k is not calling_case]

            for other in clist:
                # other case should point to the stage in case
                remove_parent(stage, other)
                add_parent(case[i], other)

                # don't forget to reorder
                other.sort_children(type(stage), 'number')

    @only_on("graphical")
    def clear(self):
        """Clear stage."""
        self.dataset.clear()

    # shortcuts to GraphicalDataSet methods
    @only_on("graphical")
    @NonConst(True)
    def add_command(self, command_type, name=None):
        """
        Add a command into the dataset.

        Arguments:
            command_type (str): Type of the command (in a catalogue).
            name (Optional[str]): Name of the command. Defaults to
                *None*; in this case name is automatically generated for
                the command.

        Returns:
            Command: New command.

        See `GraphicalDataSet.add_command()`.
        """
        return self.dataset.add_command(command_type, name)

    @only_on("graphical")
    @NonConst(True)
    def add_variable(self, var_name, var_expr=''):
        """Add a variable into the dataset.

        Arguments:
            var_name (str): Name of the variable.
            var_expr (str): Right side variable expression.

        Returns:
            Variable: Variable just added.

        See `GraphicalDataSet.add_variable()`.
        """
        return self.dataset.add_variable(var_name, var_expr)

    @only_on("graphical")
    @NonConst(True)
    def add_comment(self, content, concatenate=True):
        """Add a Comment instance into the dataset.

        Arguments:
            content (str): content of the (optionaly multiline) Comment.

        Returns:
            Comment: Comment just added.

        See `GraphicalDataSet.add_comment()`.
        """
        return self.dataset.add_comment(content, concatenate)

    @only_on("graphical")
    @NonConst(True)
    def __call__(self, command_type, name='_'):
        """
        Add a command into the dataset.

        See `add_command()` for description of arguments.
        """
        return self.dataset.add_command(command_type, name)

    @only_on("graphical")
    @NonConst(True)
    def on_remove_command(self, command):
        """
        Remove the command from the dataset.

        Arguments:
            command (Command): Command being removed.
        """
        self.dataset.on_remove_command(command)

    def __delitem__(self, item):
        """
        Remove the command from the dataset.

        Arguments:
            command (Command, str): Command being removed.

        See `remove_command()` for arguments description.
        """
        if isinstance(item, Command):
            item.delete()
        else:
            self[item].delete()

    @property
    def commands(self):
        """
        Get all commands of the dataset.

        Returns:
            list[Command]: Commands contained in a Stage.
        """
        return self.dataset.commands

    @property
    def sorted_commands(self):
        """
        Get all commands of the dataset.

        Returns:
            list[Command]: Commands contained in a Stage.
        """
        return self.dataset.sorted_commands

    @staticmethod
    def add_dependency(node, parent):
        """
        Add a dependency of *node* to *parent*.

        Just a shortcut to simplify usage of *study2code* API.
        """
        add_parent(node, parent)

    def reorder(self, command=None):
        """Ask reordering.

        If *command* is not provided all the stage is reordered, else only
        the position of *command* is checked.
        It does nothing on a text stage.
        """
        self.dataset.reorder(command)

    @only_on("graphical")
    def copy2str(self, given):
        """
        Returns command at the 'given' position in terms of code_aster syntax

        See `Stage.__getitem__()` and `Command.__str__`.
        """
        return str(self[given])

    @only_on("graphical")
    def __iter__(self):
        """
        This method is called when an iterator is required for a Stage.

        Returns:
            listiterator: Iterator object that allows traversing child
            Commands.
        """
        return iter(self.dataset)

    @only_on("graphical")
    def __contains__(self, given):
        """
        Support native Python "in" operator protocol.

        Arguments:
            given (Command or str): Command being checked.

        Returns:
            bool: *True* if Command is contained in the Stage; *False*
            otherwise.
        """
        return given in self.dataset

    @only_on("graphical")
    def __getitem__(self, given):
        """
        Support native Python '[]' operator protocol.

        See `GraphicalDataSet.__getitem__()`.
        """
        return self.dataset[given]

    def __len__(self):
        """
        Get Stage length which is:

        - A number of Commands if Stage is a graphical one;
        - A number of text lines if Stage is a text one.

        Returns:
            int: Stage's length.
        """
        return len(self.dataset)

    def __mul__(self, other):
        """Support native Python '*' operator protocol."""
        FDMixing.__mul__(self, other)

        RStageMixing.__mul__(self, other)

        ldataset = self.dataset
        rdataset = other.dataset

        assert ldataset.mode == rdataset.mode

        assert ldataset * rdataset is None

    @property
    def preceding_stages(self):
        """list[Stage]: Attribute that gives access to the preceding
        Stages."""
        return self.dataset.preceding_stages

    # shortcuts to TextDataSet methods
    @only_on("text")
    @NonConst(True)
    def set_text(self, text):
        """
        Set the text content of the dataset.

        Arguments:
            text (str): Text being set to the Stage.
        """
        self.dataset.text = text

    @only_on("text")
    @NonConst(True)
    def append_text(self, text):
        """
        Append text to the dataset content.

        Arguments:
            text (str): Text being appended to the Stage.
        """
        self.dataset.append_text(text)

    def get_text(self, sort=True, pretty=True, pretty_text=False,
                 enclosed=False):
        """
        Get text content from the dataset.

        Arguments:
            sort (Optional[bool]): Commands are automatically sorted by
                dependency if *True*.
            pretty (Optional[bool]): Optionaly reformat the text for a
                graphical stage.
            pretty_text (Optional[bool]): Optionaly reformat the text for a
                text stage. Should be used for conversions.
            enclosed (Optional[bool]): If *True*, encloses the text with
                DEBUT/POURSUITE/FIN commands if that isn't already done.

        Returns:
            str: Text assigned to the Stage.
        """
        if self.is_graphical_mode():
            text = study2comm(self, pretty, sort=sort)
        else:
            text = self.dataset.text
            try:
                text = text if not pretty_text else format_code(text)
            except SyntaxError:
                pass
        if enclosed:
            text = add_debut_fin(text, self._number == 1)
        return text

    def export(self, file_name):
        """
        Export Stage to a COMM file.

        Arguments:
            file_name (str): Path to the COMM file.
        """
        from common import to_unicode
        utext = to_unicode(self.get_text(enclosed=True))
        if not utext.endswith('\n'):
            utext += '\n'

        with open(file_name, 'w') as handle:
            handle.write(to_str(utext))
            handle.flush()

    def check(self, mode=Validity.Complete, previous_names=None):
        """
        Get validity status of Stage.

        Returns:
            bool: Validity status.
        """
        if self.is_text_mode():
            return Validity.Nothing

        result = Validity.Nothing

        if previous_names is None:
            previous_names = set()
        # ensure that the commands are well ordered before processing DETRUIRE
        for command in self:
            result |= command.check(mode)

        for command in self:
            if command.title == "DETRUIRE":
                try:
                    deleted = command["CONCEPT"]["NOM"].value
                except IndexError:
                    pass
                else:
                    if not isinstance(deleted, (list, tuple)):
                        deleted = [deleted, ]
                    for rmcmd in deleted:
                        previous_names.discard(rmcmd.name)

            if command.name != "_":
                if command.name in previous_names and not command.can_reuse():
                    result |= Validity.Naming
                previous_names.add(command.name)

        return result

    @NonConst(True)
    def before_remove(self):
        """Prepare for stage removing."""
        RStageMixing.before_remove(self)
        self.dataset = None
        return Node.before_remove(self)

    def repair(self, previous_commands):
        """Try to repair the stage in case of dependency error.

        - Search for broken dependencies: commands that are not in the model.

        - Try to fix these broken dependencies by using results with the same
          name and type.

        Arguments:
            previous_commands (set): List of commands that previously exist.
        """
        if self.is_text_mode():
            return

        for command in self.sorted_commands:
            for rmcmd in deleted_by(command):
                previous_commands.discard(rmcmd)

            command.repair(previous_commands)
            previous_commands.add(command)

    def reset_conv(self):
        """Reset the conversion message."""
        self._convmsg = None

    @property
    def conversion_report(self):
        """Property that holds the last conversion report in a *user friendly*
        format."""
        # pylint: disable=missing-format-attribute
        if not self._convmsg:
            return ""
        exc = self._convmsg.original_exception
        unmark = re.compile(re.escape(MARK) + ' *')
        msg = unmark.sub("", exc.message).strip()
        if isinstance(exc, NotImplementedError):
            text = ("Error near the line {0._lineno}:\n"
                    "{1}").format(self._convmsg, msg)
        else:
            text = ("{2.__class__.__name__}, near the line {0._lineno}:\n"
                    "{1}\n\n"
                    "Line is: {0._line!r}").format(self._convmsg, msg, exc)
        return text
