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
Case
----

Implementation of the study case.

"""

from __future__ import unicode_literals

import os
import os.path as osp
import itertools
from functools import wraps

from common import debug_message, is_subpath, same_path
from .abstract_data_model import Node, add_parent, remove_parent
from .general import (Validity, ConversionLevel, DuplicationContext as Ctx,
                      no_new_attributes)
from .result import CaseMixing as RCaseMixing
from .stage import Stage
from .sd_dict import SD_DICT


def trace_back(method):
    """
    Decorator for methods returning stages,
        to keep the case through which they where accessed
        as an attribute.
    """
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        """Wrapper"""
        stages = method(self, *args, **kwargs)
        if stages is None:
            return stages
        if isinstance(stages, Stage):
            stages.calling_case = self
            return stages

        # copy iterator to use it twice
        original, new = itertools.tee(stages)

        # use a copy of the iterator to modify stages
        for stage in original:
            stage.calling_case = self

        return new
    return wrapper

class Case(Node, RCaseMixing):
    """
    Study case.

    Case consists of Stages each of which, in its turn, represents
    separate code_aster COMM file.

    New empty Stage can be added to the Case by `create_stage()`
    method. Similarly, `import_stage()` method allows importing
    existing code_aster COMM file to the Case as a new Stage.
    """

    basicNaming = 0
    autoNaming = 1
    naming_system = autoNaming

    _generated_names = None
    _in_dir = _out_dir = None
    __setattr__ = no_new_attributes(object.__setattr__)

    def __init__(self, name):
        """
        Create Case.

        Arguments:
            name (str): Name of the Case.
        """
        Node.__init__(self, name)
        RCaseMixing.__init__(self)
        self.delete_children = Stage
        self.shallow_copy = Stage
        self._generated_names = set()
        self._in_dir = self._out_dir = None
        if os.environ.get("ASTERSTUDY_NAMING", None) == "basic":
            self.use_basic_naming()

    def __mul__(self, other):
        """Support native Python '*' operator protocol."""
        Node.__mul__(self, other)

        RCaseMixing.__mul__(self, other)

    def init_duplicated(self):
        """
        Callback function: called when this Case is duplicated.

        Bare duplication: Create new empty Case.

        Returns:
            Case: New empty Case.
        """
        return Case(self.name)

    def duplicate(self, name=None):
        """
        Create a copy of this Case.

        Arguments:
            name (Optional[str]): Name for duplicated Case. Defaults to
                *None* (name is automatically generated).

        Returns:
            Case: A copy of this Case.
        """
        return self.model.duplicate(self, name=name)

    def update_duplicated(self, orig, **kwargs):
        """
        Callback function: attune data model additionally after a Case
        has been duplicated.

        This method is called for the Case which has been just created
        via `duplicate()` method, i.e. for the copy of original Case.

        As result new Case is added to the History:

        - Previous Current Case is moved to the list of Run Cases;
        - New Case becomes the Current Case.

        See `History.add_case()` for more details.

        Arguments:
            orig (Case): Original Case object freshly replicated.
            name (Optional[str]): Name for duplicated Case. Defaults to
                *None*.
        """
        name = kwargs.get('name')
        if name is not None:
            self.name = name
        self._in_dir = orig.in_dir
        self._out_dir = orig.out_dir

        # The new case is not inserted last but second to last
        #     so that the instance that is tagged as `current`
        #     is not changed by a duplicate operation.
        self.model.insert_case(self, index=-1)

    def rename(self, name):
        """
        Renames the case.

        Arguments:
            name (str): New name.
        """
        self.name = name

    def __contains__(self, given):
        """
        Support native Python "in" operator protocol.

        Arguments:
            given (Stage or str): Stage being checked.

        Returns:
            bool: *True* if Stage is contained in the Stage; *False*
            otherwise.
        """
        if isinstance(given, Stage):
            return next((True for item in self if item is given), False)

        return next((True for item in self if item.name == given), False)

    @trace_back
    def __getitem__(self, given):
        """
        Support native Python '[]' operator protocol.

        Arguments:
            given (int, slice, str): Reference argument for operator:

                - int: to access child Stage by index
                - slice: to access range of Stages by slice expression (start
                    index is always 0)
                - str: to access child Stage by its name

        Example:
            >>> from datamodel.history import History
            >>> history = History()
            >>> stage_1 = history.current_case.create_stage("Stage 1")
            >>> stage_2 = history.current_case.create_stage("Stage 2")
            >>> s1 = history.current_case[1]
            >>> s2 = history.current_case["Stage 2"]
            >>> stages = history.current_case[:2]

        Returns:
            Stage, islice: Single Stage or set of Stages for slice
            accessor.
        """
        if isinstance(given, int):
            return self.model.get_node(self._children[given])

        if not isinstance(given, slice):
            return next(stage for stage in self if stage.name == given)

        if isinstance(given.start, Stage):
            return itertools.dropwhile(lambda x: x is not given.start, self)

        if not isinstance(given.stop, Stage):
            return itertools.islice(self, given.stop)

        return itertools.takewhile(lambda x: x is not given.stop, self)

    def __delitem__(self, given):
        """
        Implement deletion of stage `self[key]`.

        See `__getitem__()` for description of arguments (slice not
        supported here).
        """

        stage = self._getitem(given)

        stage.delete()

    @trace_back
    def _getitem(self, given):
        """
        Helper routine for `__delitem__`.

        Returns the stage associated with a key. Slice not supported.
        """

        if isinstance(given, int):
            return self.model.get_node(self._children[given])
        elif isinstance(given, basestring):
            return next(stage for stage in self if stage.name == given)
        elif isinstance(given, Stage):
            return given

    def create_stage(self, name=None):
        """
        Create new Stage in the Case.

        The type of new Stage is the same as of the parent Stage.

        If there is no stages in the case, create a new graphical Stage.

        Arguments:
            name (Optional[str]): Name of new Stage. Defaults to *None*.

        Returns:
            Stage: New Stage.
        """
        if not name:
            name = 'Stage_{}'.format(self.nb_stages + 1)

        # current number is assigned within add_stage() method
        stage = Stage(name)
        self.model.add(stage, None)

        self.add_stage(stage)

        return stage

    def add_stage(self, stage):
        """
        Add Stage in the Case.

        The type of Stage becomes the same as of the previous Stage.

        Arguments:
            stage (Stage): Stage being added.
        """
        if stage not in self.stages:
            nb_stages = self.nb_stages
            stage.number = nb_stages + 1

            # create connections with parent case
            # does nothing if that already exists
            add_parent(stage, self)

            if nb_stages > 0:
                parent_stage = self.get_stage_by_num(nb_stages)
                add_parent(stage, parent_stage)
                stage.result.job.copy_parameters_from(parent_stage.result.job)

                if stage.mode is None or (parent_stage.is_text_mode() and \
                                              stage.is_graphical_mode()):
                    if parent_stage.is_graphical_mode():
                        stage.use_graphical_mode()
                    else:
                        stage.use_text_mode()
            else:
                if stage.mode is None:
                    stage.use_graphical_mode()

    def remove_stage(self, stage):
        """
        Remove Stage from the Case.

        Note:
            All the child Stages are also removed from the Case.

        Arguments:
            stage (Stage): Stage being removed.
        """
        stages_to_remove = []
        for stage in self[stage:]:
            stages_to_remove[0:0] = [stage]
        for stage in stages_to_remove:
            remove_parent(stage, self)
            if stage.parent_case is None:
                prev_stage = self.get_stage_by_num(stage.number-1)
                remove_parent(stage, prev_stage)
                self.model.remove(stage)

    @property
    def stages(self):
        """list[Stage]: Attribute that holds Stages stored in the Case."""
        return [i for i in self.child_nodes if isinstance(i, Stage)]

    @property
    def nb_stages(self):
        """int: Attribute that holds number of Stages in the Case."""
        return len(self.stages)

    @property
    def in_dir(self):
        """str: Attribute that holds *Input* directory of the Case."""
        return self._in_dir

    @in_dir.setter
    def in_dir(self, in_dir):
        if in_dir is not None:
            in_dir = osp.realpath(in_dir)
        if in_dir is not None and self._out_dir is not None:
            if same_path(in_dir, self._out_dir):
                raise ValueError, "input and output dirs can't be the same"
            elif is_subpath(in_dir, self._out_dir):
                raise ValueError, "input dir can't be sub-path of output dir"
            elif is_subpath(self._out_dir, in_dir):
                raise ValueError, "input dir can't be parent of output dir"
        if in_dir is not None and not osp.exists(in_dir):
            raise ValueError, "non-existent directory: '{}'".format(in_dir)
        self._in_dir = in_dir

    @property
    def out_dir(self):
        """str: Attribute that holds *Output* directory of the Case."""
        return self._out_dir

    @out_dir.setter
    def out_dir(self, out_dir):
        if out_dir is not None:
            out_dir = osp.realpath(out_dir)
        if out_dir is not None and self._in_dir is not None:
            if same_path(out_dir, self._in_dir):
                raise ValueError, "input and output dirs can't be the same"
            elif is_subpath(out_dir, self._in_dir):
                raise ValueError, "output dir can't be sub-path of input dir"
            elif is_subpath(self._in_dir, out_dir):
                raise ValueError, "output dir can't be parent of input dir"
        self._out_dir = out_dir

    def __len__(self):
        """
        Support native Python 'len' operator protocol.
        """
        return self.nb_stages

    def __iter__(self):
        """
        This method is called when an iterator is required for a Case.

        Example:
            >>> from datamodel.history import History
            >>> history = History()
            >>> stage_1 = history.current_case.create_stage("Stage 1")
            >>> stage_2 = history.current_case.create_stage("Stage 2")
            >>> for stage in history.current_case:
            ...     print stage.name
            ...
            Stage 1
            Stage 2

        Returns:
            listiterator: Iterator object that allows traversing child
            Stages.
        """
        return iter(self.stages)

    @trace_back
    def get_stage_by_num(self, number):
        """
        Get Stage by number.

        Arguments:
            number (int): Stage's number.

        Returns:
            Stage: Child Stage (None if there's no child Stage with such
            number).

        Raises:
            AssertionError: If there are more than one child Stage with
                given number.
        """
        stages = self.stages
        stages = [stage for stage in stages if stage.number == number]
        if len(stages) > 1:
            err_msg = "Case contains several stages number %d" % (number)
            raise AssertionError(err_msg)
        if len(stages) > 0:
            return stages[0]
        return None

    def text2stage(self, text, name=None, strict=ConversionLevel.NoFail,
                   force_text=False):
        """
        Create a new stage from a COMM text snippet.

        See `import_stage()` for details about *strict* mode.

        Arguments:
            text (str): COMM code snippet.
            name (str): Name of Stage being created.
            strict (ConversionLevel): Tells how strict the conversion
                must be. For more details, see `general.ConversionLevel`.
                Default is not to fail.

        Returns:
            Stage: New Stage.
        """
        stage = self.create_stage(name)
        is_graphical_mode = not force_text and stage.is_graphical_mode()
        stage.use_text_mode()
        stage.set_text(text)

        if is_graphical_mode:
            try:
                stage.use_graphical_mode(strict)
            except Exception as exc: # pragma pylint: disable=broad-except
                debug_message('can not use graphical mode: {0}'.format(exc))

        return stage

    def import_stage(self, file_name, strict=ConversionLevel.NoFail,
                     force_text=False):
        """
        Create new Stage by importing code_aster COMM file.

        New Stage is created in the same edition mode as the parent
        Stage (if there is any).

        If there is no existing Stage, new Stage is created in a
        graphical mode.

        Note:
            If Stage cannot be converted to graphical mode due to any
            reason, the Stage is created in text mode.

        Arguments:
            file_name (str): Path to the COMM file.
            strict (Optional[ConversionLevel]): Tells how strict the conversion
                must be. For more details, see `general.ConversionLevel`.
                Default is not to fail.

        Returns:
            Stage: New Stage.
        """
        text = open(file_name).read()
        name = osp.splitext(osp.basename(file_name))[0]
        return self.text2stage(text, name, strict, force_text)

    def export(self, export_name):
        """Export case for a testcase.

        Arguments:
            export_name (str): Filename of export file. Additional files will
                be added into its parent directory.
        """
        from .engine.engine_utils import export_case_as_testcase
        export_case_as_testcase(self, export_name)

    def check(self, mode=Validity.Complete):
        """
        Get validity status of Case.

        Returns:
            bool: Validity status.
        """
        result = Validity.Nothing

        cmdnames = set()
        for stage in self:
            result |= stage.check(mode, cmdnames)

        return result

    def repair(self):
        """Try to repair the case in case of dependency error.

        - Search for broken dependencies: commands that are not in the model.

        - Try to fix these broken dependencies by using results with the same
          name and type.

        Returns:
            Validity: Status of the validation of the case after repairing.
        """
        commands_store = set()
        for stage in self:
            stage.repair(commands_store)

        return self.check()

    def is_used_by_others(self):
        """Tells whether a Case's descendant Stages are contained in other
        cases"""
        for stage in self.stages:
            if stage.parent_case is not self:
                continue
            cases = [self]
            if self.model:
                cases.append(self.model.current_case)
            cases = [i for i in stage.cases if i not in cases]
            if cases:
                return True
        return False

    def used_by_others(self):
        """Tells what cases contain descendant Stages from this one"""
        result = set()
        if self.is_used_by_others():
            for stage in self.stages:
                if stage.parent_case is not self:
                    continue
                cases = [self]
                if self.model:
                    cases.append(self.model.current_case)
                cases = [i for i in stage.cases if i not in cases]
                for case in cases:
                    if case.is_backup:
                        continue
                    result.add(case)
                    result.union(case.used_by_others())
        return list(result)

    @classmethod
    def use_default_naming(cls):
        """Enable the default naming of command results."""
        cls.naming_system = Case.autoNaming

    @classmethod
    def use_basic_naming(cls):
        """Switch to a basic naming of command results."""
        cls.naming_system = Case.basicNaming

    def generate_name(self, command): # pragma pylint: disable=no-self-use
        """Generate the name for the command.

        Arguments:
            command (Command): A command.

        Returns:
            str: Name for the command.
        """
        typ = command.safe_type()
        if not typ:
            return "_"

        if self.naming_system == Case.basicNaming:
            return command.title

        try:
            key = typ.getType()
            prefix = SD_DICT.get(key.lower(), "unnamed")
        except (TypeError, AttributeError):
            prefix = "unnamed"

        attempts = [""] + range(1000)
        while len(attempts) > 0:
            suffix = str(attempts.pop(0))
            size = 8 - len(suffix)
            name = "{0}{1}".format(prefix[:size], suffix)
            if name not in self._generated_names:
                self._generated_names.add(name)
                return name

        return prefix + "_XXX"

    def before_remove(self):
        """Deletes a case, or more precisely all cases that have common
        descendants with this one.
        """
        referencing_cases = self.used_by_others()

        # check if case can be removed
        RCaseMixing.before_remove(self)

        # delete directory
        self.delete_dir()

        # retrieve cases with common descendants
        return (referencing_cases,)

    def after_remove(self, referencing_cases): # pragma pylint: disable=arguments-differ
        """Hook that is called after the node removing is finished."""
        for case in referencing_cases:
            case.delete()

    def own_stages_from(self, number, context=Ctx.Nothing):
        """
        Recursively duplicate all referenced stages from *number*
        in this case, making them owned instead of referenced.

        Arguments:
            number (int): stage number from where to start.
        """
        # TODO: use id = number - 1 as argument
        first_owned = self.first_owned_stage_id()
        start = first_owned if first_owned >= 0 else self.nb_stages
        iterator = (self[i-1] for i in xrange(start, number - 1, -1))
        for stage in iterator:
            stage.duplicate(self, context)
            # as this is backwards duplication,
            # do not forget to reorder each time
            self.sort_children(Stage, 'number')

    def first_owned_stage_id(self):
        """
        Return the index of the first owned stage.

        Returns:
            int: number of first owned stage if any, else returns -1.
        """
        owned_list = [i for i in range(self.nb_stages) \
                          if self[i].parent_case is self]
        return owned_list[0] if owned_list else -1

    def detach_stage(self, stage):
        """
        Detach stage from case

        Arguments:
            stage: stage to be detached.
                   Can be *int*, *str* or *Stage*, but not a slice.

        Raises:
            ValueError: if *stage* is not referenced
        """
        if stage not in self:
            errmsg = "Stage {0!s} does not belong to ".format(stage) + \
                     "Case {0!s}".format(self)
            raise ValueError(errmsg)

        # if the last one, detach it
        # otherwise, call the function recursively on next stage
        mystage = self._getitem(stage)
        if mystage is not self[-1]:
            self.detach_stage(self[mystage.number])
        self._detach_last_stage()


    def _detach_last_stage(self):
        """Detach the last stage of `self`."""

        last_stage = self[-1]
        other_cases = [c for c in last_stage.cases if c is not self]
        if other_cases:
            # simply a refence to remove
            remove_parent(last_stage, self)
            # no need to reorder, since we removed the last one
        else:
            # delete the object
            del self[last_stage]

    def can_be_ran(self):
        """Tells whether this case is valid for running."""
        return self.nb_stages > 0 and self.check() == Validity.Nothing
