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
History
-------

Implementation of the history (collection of cases).

"""

from __future__ import unicode_literals

import os.path as osp

from common import AsterStudyError, AsterStudyInterrupt, translate, CFG
from .abstract_data_model import AbstractDataModel
from .case import Case
from .catalogs import CATA
from .result import HistoryMixing as RHistoryMixing
from .general import no_new_attributes
from .engine.engine_utils import add_stages_from_astk
from .serializer import STRICT_DEFAULT, factory as serializer_factory


class History(AbstractDataModel, RHistoryMixing):
    """History: a collection of study Cases.

    There is always a single *current* Case - the only one which is
    modifiable: see `current_case` property.

    Read-only Cases can be accessed via `run_cases` property.
    """

    __version = __version_number = _auto_dupl = _jobs_list = None
    __setattr__ = no_new_attributes(object.__setattr__)

    def __init__(self, version=None):
        """
        Create History.

        Attributes:
            version (Optional[str]): Version of code_aster to use.
                Defaults to *None*; in this case default version is
                used.
        """
        super(History, self).__init__()
        RHistoryMixing.__init__(self)
        if not version:
            version = CFG.default_version
        self.__version = version
        self.create_case()
        CATA.read_catalogs(self.__version)
        self.__version_number = CATA.version_number
        self._auto_dupl = False

    @property
    def nodes(self):
        """list[int]: Attribute that provides access to uids of all
        stored nodes."""
        return sorted(self._nodes.keys())

    @property
    def version(self):
        """str: Attribute that holds code_aster version associated with
        this History object."""
        return self.__version

    @property
    def version_number(self):
        """str: Attribute that holds code_aster version number associated with
        this History object."""
        return self.__version_number

    @property
    def tests_path(self):
        """str: Attribute that holds path of the testcases."""
        return CATA.tests_path(self.__version)

    @property
    def nb_cases(self):
        """int: Attribute that holds number of Cases."""
        return len(self._cases)

    def create_case(self, name=None, replace=False):
        """
        Create a new Case in the history.

        Attributes:
            name (Optional[str]): Name of Case being created. Default to
                *None* (in this case name is auto-assigned to Case).
            replace (Optional[bool]): Specifies if *current* Case should
                be replaced (*True*) or kept (*False*). Defaults to
                *False*.

        Returns:
            Case: New Case.

        Note:
            New Case becomes a *current* one; previous *current* Case is
            added to the list of *run* Cases (if `replace` is *False*) or
            replaced by new one (if `replace` is *True*).
        """
        if not name:
            idx = self.nb_cases if replace else self.nb_cases + 1
            name = "Case_{}".format(idx)
        case = Case(name)
        self.insert_case(case, replace)
        return case

    def add_case(self, case):
        """
        Add Case.

        This function is only used if Case is created outside of the
        `History`.

        Attributes:
            case (Case): Case being added.

        Note:
            - Case is not added if it is already present in the history.
            - Case being added becomes a *current* one; previous
              *current* Case is added to the list of *run* Cases.
        """
        self.insert_case(case)

    def insert_case(self, case, replace=False, index=None):
        """
        Inserts Case into the given position in the list of Cases.

        Attributes:
            case (Case): Case being inserted.
            replace (Optional[bool]): Specifies if existing Case at
                given position should be kept (*False*) or replaced by
                new one (*True*). Defaults to *False*.
            index (int): Position in the cases list. Defaults to *None*
                that means last position in the list (i.e. "current"
                Case).
        """
        if case not in self.cases:
            self.add(case, None)
            if self.cases and replace:
                old_case = self._cases.pop(index if index is not None else -1)
                old_case.delete()
            idx = index if index is not None else len(self._cases)
            self._cases[idx:idx] = [case]

    def import_case(self, filename, replace=False):
        """
        Create a new Case in the history by importing an export file from ASTK.

        Attributes:
            filename (str): Filename of the export file to import.
            replace (Optional[bool]): Specifies if *current* Case should
                be replaced (*True*) or kept (*False*). Defaults to
                *False*.

        Returns:
            Case: New Case.

        Note:
            New Case becomes a *current* one; previous *current* Case is
            added to the list of *run* Cases (if `replace` is *False*) or
            replaced by new one (if `replace` is *True*).
        """
        basename = osp.splitext(osp.basename(filename))[0]
        case = self.create_case(basename, replace=replace)
        add_stages_from_astk(case, filename)
        return case

    def remove_node(self, node):
        """
        Execute a common code for removing the node from the model.

        Arguments:
            node (Node): Node being removed.

        Note:
            Removes child nodes according to node's type.
        """
        super(History, self).remove_node(node)
        if node in self._cases:
            self._cases.remove(node)

    def check_dir(self, task):
        """
        Check study directory after a load.

        Arguments:
            task (func): the checking operation to perform, among:
                `RHistoryMixing.warn`,
                `RHistoryMixing.full_warn`,
                `RHistoryMixing.clean`
        """
        import traceback
        try:
            task(self)
        except AsterStudyError:
            raise
        except Exception as err: # pragma: no cover
            trbk = "Error: {0}\n\n{1}".format(err, traceback.format_exc())
            raise AsterStudyInterrupt(
                translate("AsterStudy", "Errors occurred during checking the "
                                        "study directory"),
                str(trbk))

    def __call__(self, uid):
        """
        Support native Python '()' operator protocol.

        Arguments:
            uid (int): Node's uid.

        Returns:
            Node: Data model node.

        Raises:
            KeyError: If `uid` is invalid.
        """
        return self._nodes[uid]

    def __getitem__(self, given):
        """
        Support native Python '[]' operator protocol.
        """
        cases = self._cases

        if isinstance(given, int):
            return cases[given]

        return next(item for item in cases if item.name == given)

    def __eq__(self, other):
        """Support native Python '==' operator protocol."""
        return self is other

    def __mul__(self, other):
        """Support native Python '*' operator protocol."""
        lcases = self.cases
        rcases = other.cases
        assert len(lcases) == len(rcases)

        for idx, lcase in enumerate(lcases):
            rcase = rcases[idx]
            assert lcase * rcase is None

        RHistoryMixing.__mul__(self, other)

    @staticmethod
    def save(model, file_name, serializer=None):
        """
        Save model to a file.

        If `serializer` is not given, a default one is used.

        Arguments:
            model (AbstractDataModel): Model object.
            file_name (str): Path to the file.
            serializer (Optinal[any]): Serializer object.
                Defaults to *None*.
        """
        serializer = serializer_factory(file_name, serializer)
        AbstractDataModel.save(model, file_name, serializer)

    @staticmethod
    def load(file_name, serializer=None, strict=STRICT_DEFAULT, **kwargs):
        """
        Load model from a file.

        If `serializer` is not given, a default one is used.

        Arguments:
            file_name (str): Path to Asterstudy persistence file.
            serializer (Optinal[any]): Serializer object.
                Defaults to *None*.
            kwargs (Optional): Keywords arguments passed to the serializer.

        Returns:
            AbstractDataModel: Model object.
        """
        serializer = serializer_factory(file_name, serializer, strict)
        return AbstractDataModel.load(file_name, serializer, **kwargs)

    @property
    def auto_dupl(self):
        """Is auto duplication enabled?"""
        return self._auto_dupl

    @auto_dupl.setter
    def auto_dupl(self, value):
        """Set automatic duplication mode."""
        self._auto_dupl = value

    @property
    def jobs_list(self):
        """str: Attribute that holds the list of jobs of this History."""
        return self._jobs_list or ''

    @jobs_list.setter
    def jobs_list(self, value):
        """Register jobs list as string."""
        self._jobs_list = value
