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
Result Mixings
--------------

Implementation of Mixing classes used for Result definition.

"""

from __future__ import unicode_literals

import cgi
import os
import os.path as osp
import shutil
import warnings

from common import (ExistingSwapError, StudyDirectoryError,
                    MissingStudyDirError,
                    bold, copy_file, div, href, preformat, to_str, translate)
from ..general import no_new_attributes, FileAttr
from ..abstract_data_model import add_parent, remove_parent

from .utils import RunOptions, StateOptions
from .execution import Result


class CaseMixing(object):
    """Result related CaseMixing."""

    _folder = _description = _is_backup = None
    __setattr__ = no_new_attributes(object.__setattr__)

    def __init__(self):
        """Initializer"""
        self._folder = ""
        self._description = ""
        self._is_backup = False

    def __mul__(self, other):
        """Support native Python '*' operator protocol."""
        assert self.description == other.description

        assert self.is_backup == other.is_backup

    @property
    def description(self):
        """str: Attribute that holds the Case's description."""
        return self._description

    @description.setter
    def description(self, value):
        """Assign the Case description."""
        self._description = value

    @property
    def is_backup(self):
        """Returns the purpose of this case."""
        return self._is_backup

    @is_backup.setter
    def is_backup(self, value):
        """Defines the purpose of this case."""
        self._is_backup = value

    def run_options(self, stage):
        """
        Get available options for run.

        Arguments:
            stage (Stage, int): Stage being checked.

        Returns:
            int: Available run options (*RunOptions*).

        Raises:
            IndexError: If `stage` does not belong to this Case.
        """
        if isinstance(stage, int):
            stage = self[stage] # pragma pylint: disable=unsubscriptable-object
        if stage not in self.stages: # pragma pylint: disable=no-member
            raise IndexError("stage does not belong to case")
        value = RunOptions.Skip | RunOptions.Execute
        if self.can_reuse(stage):
            value = value | RunOptions.Reuse
        return value

    def can_reuse(self, stage):
        """
        Check if Stage's result can be re-used.

        Arguments:
            stage (Stage, int): Stage being checked.

        Returns:
            bool: *True* if result can be re-used; *False* otherwise.

        Raises:
            IndexError: If `stage` does not belong to this Case.
        """
        res = False
        if isinstance(stage, int):
            stage = self[stage] # pragma pylint: disable=unsubscriptable-object
        if stage not in self.stages: # pragma pylint: disable=no-member
            raise IndexError("stage does not belong to case")
        next_idx = self.stages.index(stage) + 1 # pragma pylint: disable=no-member
        if stage.state & StateOptions.Success:
            case_path = stage.parent_case.folder
            # case_path is empty if study folder was not specified
            res = os.path.isdir(case_path) if case_path else True
        elif stage.is_intermediate() and next_idx < len(self.stages): # pragma pylint: disable=no-member
            res = self.can_reuse(next_idx)
        return res

    def copy_from(self, other):
        """
        Copy content of given case to this one.

        Arguments:
            other (Case): Other case.
        """
        if self.nb_stages > 0: # pragma pylint: disable=no-member
            self.remove_stage(self.stages[0]) # pragma pylint: disable=no-member
        for stage in other.stages:
            self.add_stage(stage) # pragma pylint: disable=no-member

        # clean directory
        if self.model.tmpdir: # pragma pylint: disable=no-member
            rootdir, _, files = next(os.walk(self.model.tmpdir)) # pragma pylint: disable=no-member
            for myfile in files:
                os.remove(osp.join(rootdir, myfile))

    def run(self, state=StateOptions.Success):
        """
        Run case in dummy mode.

        TODO:
            This function is used for test purposes only; it should be
            removed as soon as correct run mechanism is implemented.
        """
        for stage in self.stages: # pragma pylint: disable=no-member
            if not stage.is_intermediate():
                if not stage.state & state:
                    stage.state = state
                if state == StateOptions.Error:
                    break
        return self

    def modify(self, stage):
        """
        Mark Stage as modified.

        TODO:
            This function is used for test purposes only; it will be
            removed as soon as correct edit mechanism is implemented.

        Arguments:
            stage (Stage): Stage being modified.

        Raises:
            RuntimeError: If stage cannot be modified.
        """
        if stage in self.stages: # pragma pylint: disable=no-member
            history = self.model # pragma pylint: disable=no-member

            if self != history.current_case:
                err_msg = "cannot modify case which is not a current case"
                raise RuntimeError(err_msg)

            # pragma pylint: disable=unsubscriptable-object
            stages_to_add = [i.copy() for i in self[stage:]]
            self.remove_stage(stage) # pragma pylint: disable=no-member
            for new_stage in stages_to_add:
                self.add_stage(new_stage) # pragma pylint: disable=no-member

    def before_remove(self):
        """Hook that is called before a Case removing starts."""
        model = self.model # pragma pylint: disable=no-member
        if model is not None and model.current_case is not None:
            if model.current_case is self:
                raise RuntimeError("current case cannot be removed")

            for stage in self.stages: # pragma pylint: disable=no-member
                if stage in model.current_case.stages:
                    if stage.parent_case is self:
                        stage.result.clear()

        if self.stages: # pragma pylint: disable=no-member
            self.remove_stage(self.stages[0]) # pragma pylint: disable=no-member

    def results(self):
        """Gets the chain of calculated results in case."""
        res_list = []
        for stage in self.stages: # pragma pylint: disable=no-member
            result = stage.result
            if result is not None:
                if result.stage == stage:
                    res_list.append(result)
        return res_list

    def result_stage(self, result):
        """Gets the stage in case according to the specified result."""
        res_stage = None
        for stage in self.stages: # pragma pylint: disable=no-member
            if stage.result == result:
                res_stage = stage
                break
        return res_stage

    def show_message(self):
        """Return the messages of each stage of the case.

        Returns:
            str: Rich text of the messages.
        """
        # TODO: it's a job for a dedicated module!
        alltxt = []
        header = [div("summary"), bold(translate("Result", "Summary"))]
        rtxt = []
        for stage in self.stages: # pragma pylint: disable=no-member
            if not stage.state & StateOptions.Finished:
                break
            if stage.parent_case is not self:
                continue
            title = bold(translate("Result",
                                   "Output messages for stage {0}")
                         .format(stage.name))
            # link
            rtxt.append(div(stage.name))
            header.append(href(title, "#" + stage.name))
            if stage.is_intermediate():
                rtxt.append(translate("Result",
                                      "Execution grouped with the following "
                                      "stage."))
                continue
            rtxt.append(title + " - [" \
                        + href(translate("Result", "top"), '#summary') + " / "\
                        + href(translate("Result", "bottom"), "#bottom") + "]")
            # show message file content
            mess = osp.join(stage.folder, 'message')
            if osp.exists(mess):
                with open(mess, 'rb') as fobj:
                    text = fobj.read()
                text = cgi.escape(text.decode('utf-8', 'ignore'))
                rtxt.append(preformat(text))
            else:
                rtxt.append(translate("Result",
                                      "Full job output should be available"
                                      " in the directory {0!r}.")
                            .format(osp.join(stage.folder, 'logs')))

        rtxt.extend([div("bottom") + href(translate("Result", "back to top"),
                                          "#summary")])
        if len(header) > 2:
            alltxt.extend(header)
        else:
            alltxt = [header[0]]
        alltxt.extend(rtxt)
        txt = "\n".join(alltxt).strip()
        return "<br />".join(txt.splitlines())

    @property
    def base_folder(self):
        """Get the basename of the Case folder.
        Should be used only by the serializer."""
        return self._folder

    @base_folder.setter
    def base_folder(self, value):
        """Set the basename of the Case folder.
        Should be used only by the serializer."""
        self._folder = value

    @property
    def folder(self):
        """str: Attribute that holds Case's folder path."""
        return self._folder_template(self.model.folder) # pragma pylint: disable=no-member

    @property
    def remote_folder(self):
        """str: Case's remote folder for database results."""
        return self._folder_template(self.model.remote_folder) # pragma pylint: disable=no-member

    def _folder_template(self, root):
        """
        Helper function to build the case's folder.

        Arguments:
            root (str): folder related to History object.
        """
        if not self._folder:
            self._folder = self.name # pragma pylint: disable=no-member
        return osp.join(root, self._folder) if root else ""

    def make_run_dir(self):
        """
        Handles the embedded files for a run case before it is submitted.
        """
        first = self.stages[self.first_owned_stage_id()] # pragma pylint: disable=no-member
        for stage in self[first:]: # pragma pylint: disable=unsubscriptable-object
            self._make_run_dir_helper(stage)

    def _make_run_dir_helper(self, stage):
        """
        Copies embedded files to `self.folder` and change their paths
        accordingly in `stage`. Called before `stage` is run.

        Arguments:
            stage (Stage): stage whose embedded files are to be moved.
        """
        embfolder = osp.join(self.model.folder, self.name, 'Embedded') # pragma pylint: disable=no-member
        if not osp.isdir(embfolder):
            os.makedirs(embfolder)
        for info in stage.handle2info.viewvalues():
            if info.embedded:
                tmpfile = info.filename
                curfile = osp.join(embfolder, osp.basename(tmpfile))
                infi = stage.parent_info(info)

                # if the file doesn't appear in a preceding stage
                if not infi:
                    source = tmpfile
                    dest = curfile

                # if the file appears in a preceding stage
                if infi:
                    parfile = infi.filename

                    # in file, point to the preceding folder, do not copy again
                    if info.attr == FileAttr.In:
                        dest = source = parfile

                    # out file, point to current folder, do not copy
                    if info.attr == FileAttr.Out:
                        source = dest = curfile

                    # inout file, copy the file from another location
                    if info.attr == FileAttr.InOut:
                        source = parfile
                        dest = curfile

                if dest != source:
                    copy_file(source, dest)
                info.filename = dest

    def delete_dir(self):
        """
        Deletes the directory associated with the case.
        """
        res = False
        casedir = self.folder

        if casedir and osp.isdir(casedir):
            shutil.rmtree(casedir)
            res = True

        return res


class HistoryMixing(object):
    """Result related HistoryMixing."""

    _folder = _remote_folder = _cases = _no_dir_loaded = None
    __setattr__ = no_new_attributes(object.__setattr__)

    def __init__(self):
        """Create object."""
        self._folder = None
        self._no_dir_loaded = False
        self._cases = []

    @staticmethod
    def listdir_exclude_emb(directory):
        """Lists a directory subdirs omitting "Embedded" entries."""
        root, subdirs, _ = next(os.walk(directory))
        assert osp.samefile(root, directory)
        return [s for s in subdirs if s != "Embedded"]

    @property
    def missing_root(self):
        """Returns *True* if the study dir should be considered missing.

        Note:
             This happens when history had no directory at load time
             and there are run cases; or when the path is not defined
             or does not exist."""
        return (not bool(self.folder)) \
            or (not osp.isdir(self.folder)) \
            or (self._no_dir_loaded and self.run_cases)

    @property
    def cases(self):
        """list[Case]: Attribute that holds all Cases."""
        return self._cases

    @property
    def current_case(self):
        """Case: Attribute that holds single *current* Case."""
        return self._cases[-1] if self.cases else None

    @property
    def run_cases(self):
        """list[Case]: Attribute that holds list of *run* Cases."""
        return [case for case in self._cases[:-1] if not case.is_backup]

    @property
    def backup_cases(self):
        """list[Case]: Attribute that holds list of *run* Cases."""
        return [case for case in self._cases[:-1] if case.is_backup]

    @property
    def folder(self):
        """str: Attribute that holds study related root directory."""
        return self._folder

    @property
    def remote_folder(self):
        """str: remote folder on which result databases are kept."""
        return self._remote_folder

    @remote_folder.setter
    def remote_folder(self, value):
        """
        Set remote folder on which remote databases will be kept.

        Note:
            `value` if the raw folder provided by the user.
            The study name is appended to it in the attribute.
        """
        bname = osp.basename(osp.normpath(self.folder))
        self._remote_folder = osp.join(value, bname)

    @folder.setter
    def folder(self, value):
        """
        Set study folder.

        Note:
            If `value` is an existing directory, this creates a
            subdirectory for embedded files for the current case.
        """
        if osp.basename(value) == "_Files":
            warnings.warn("\n    Path {0!r} seems invalid, probably due to "
                          "a known issue in SALOME Save()."
                          "\n    Study base folder is not changed."
                          .format(value), RuntimeWarning)
            return
        self._folder = value
        if (not self._folder) or (not osp.isdir(self._folder)):
            self._no_dir_loaded = True
        if self._folder:
            dirname = osp.join(self._folder, 'Embedded')
            if not osp.isdir(dirname):
                os.makedirs(dirname)

    def _new_case_name(self, cases, prefix):
        """Return a new name for a case.

        Returns:
            str: Name for a case.
        """
        idx = len(cases) + 1
        name = prefix.format(idx)
        exnames = [i.name for i in self.cases]
        while name in exnames or \
                (self.folder and osp.exists(osp.join(self.folder, name))):
            idx += 1
            name = prefix.format(idx)
        return name

    def create_backup_case(self, name=None):
        "Create backup Case"
        ref_case = self.current_case

        if not name:
            name = self._new_case_name(self.backup_cases, "BackupCase_{}")

        case = ref_case.duplicate(name)

        case.is_backup = True

        return case

    def create_run_case(self, exec_stages=None, reusable_stages=None,
                        name=None):
        """
        Create and initialize Run Case.

        The resulting Run case will contain Stages selected from Current
        case in accordance with below described rules.

        The stages to execute are specified via the *exec_stages*
        parameter. It can be:

        - Single integer value: in this case only Stage with specified
          index is executed.
        - List or tuple of two integer values: in this case all Stages
          in given range (inclusively) are executed.
        - List of tuple of one integer value: in this case all Stages
          starting from given one are executed.
        - None (default): all Stages are executed.

        Note:

        - All Stages preceeding first executed Stage are "re-used".
        - All Stages following last executed Stage are omitted.

        Arguments:
            exec_stages (Optional[multiple]): Indexes of stages to execute.
                Defaults to *None*.
            reusable_stages (Optional[multiple]): Indexes of executed stages
                that will be reusable. By default, only the last stage will be
                marked as reusable.
            name (str): Name for Run Case. Defaults to *None* (in this
                case the name is automatically assigned).

        Return:
            Case: New Run Case.

        Raises:
            IndexError: If given range of stages is invalid.
            RuntimeError: If stage aimed to be re-used, cannot be
                reused.
        """
        ref_case = self.current_case

        first_stage = 0
        last_stage = ref_case.nb_stages
        if isinstance(exec_stages, (list, tuple)):
            if len(exec_stages) > 0:
                first_stage = exec_stages[0]
            if len(exec_stages) > 1:
                last_stage = exec_stages[1] + 1
        elif exec_stages is not None:
            first_stage = exec_stages
            last_stage = first_stage + 1

        if first_stage < 0 or first_stage >= ref_case.nb_stages or \
                last_stage < 0 or last_stage > ref_case.nb_stages or \
                last_stage <= first_stage:
            raise IndexError("wrong range of stages")

        if reusable_stages is None:
            reusable_stages = [last_stage - 1]
        elif not isinstance(reusable_stages, (list, tuple)):
            reusable_stages = [reusable_stages]
        if last_stage - 1 not in reusable_stages:
            raise IndexError("Last stage must be reusable to keep its results")

        if not name:
            name = self._new_case_name(self.run_cases, "RunCase_{}")

        # check results available for reuse
        for i in xrange(first_stage):
            ref_stage = ref_case[i]
            if not ref_stage.state & StateOptions.Success:
                raise RuntimeError("Cannot reuse stage '{0.name}'"
                                   .format(ref_stage))

        run_case = ref_case.duplicate(name)

        # reused stages: put current last
        for i in xrange(first_stage):
            plist = ref_case[i].parent_nodes
            plist.append(plist.pop(plist.index(ref_case)))

        # switch stages to be executed, as well as skipped stages
        for i in xrange(first_stage, ref_case.nb_stages):
            ref_stage = ref_case[i]
            if ref_stage.parent_case is ref_case:

                assert ref_stage.cases == [ref_case, run_case]
                # make run_case the new parent (move ref_case at last position)
                ref_stage.move_parent(ref_case)

        run_case.own_stages_from(first_stage + 1)

        # make current point to stages owned by run_case whenever possible
        for i in xrange(first_stage, ref_case.nb_stages):
            run_stage = run_case[i]

            # should be owned by run_case by now, reset folder
            assert run_stage.parent_case is run_case or i >= last_stage
            run_stage.base_folder = ""

            # point current to it
            old_stage = ref_case[i]
            assert old_stage.parent_case is not ref_case or i >= last_stage

            # if not the same, switch
            if old_stage is not run_stage:
                assert old_stage.parent_case is not run_case
                remove_parent(old_stage, ref_case)
                add_parent(run_stage, ref_case)

                # after modifying child relations, don't forget to reorder!
                ref_case.sort_children(type(run_stage), 'number')

            # mark as intermediate stage if needed
            if i not in reusable_stages:
                run_stage.set_intermediate()

        if last_stage < ref_case.nb_stages:
            run_case.detach_stage(run_case[last_stage])

        # clear any result owned by current
        mylist = [st for st in ref_case.stages if st.parent_case is ref_case]
        for stage in mylist:
            stage.result.clear()

        return run_case

    def __mul__(self, other):
        """Support native Python '*' operator protocol."""
        assert self.folder == other.folder

    @classmethod
    def warn(cls, hist):
        """
        Emit dedicated exceptions with quick hints to the user
        if the study directory is missing or incomplete.

        Arguments:
            hist (HistoryMixing): the history to inspect

        Note:
            The `folder` attribute (expected study directory)
            must have been set before to call this method.
        """
        def _missing_root(hist):
            """Task for a missing study directory."""
            if not hist.folder:
                msg = "The study directory is undefined."
                raise MissingStudyDirError(msg)

            msg = ("The study directory '{0}' did not exist "
                   "and had to be created empty.\n\n"
                   "If you moved the HDF study '{1}' from another "
                   "location, please make sure to move "
                   "the study directory as well.\n\n"
                   "Click 'Cancel', move the study directory "
                   "then try again "
                   "or click 'OK' to continue without study directory."
                   "".format(hist.folder, hist.folder.rstrip('_Files')))
            raise MissingStudyDirError(msg)

        def _missing_stage(hist, stage):
            """Task for each *Stage* without subfolder"""
            msg = ("The study directory {0} does not match "
                   "the HDF study {1}.\n"
                   "For instance, subdirectory {2} does not exist.\n\n"
                   "If you moved the HDF study '{1}' from another location, "
                   "please make sure to move the study directory as well.\n\n"
                   "Click 'Cancel', move the study directory and try again "
                   "or click 'OK' to continue without study directory."
                   "".format(hist.folder,
                             hist.folder.rstrip('_Files'),
                             stage.folder))
            raise StudyDirectoryError(msg)

        def _missing_subdir(mydir):
            """Task for each subfolder without *Stage*"""
            msg = ("The study seems incomplete "
                   "with regard to the study directory.\n"
                   "For instance, subdirectory {0} has no corresponding stage."
                   "".format(osp.abspath(mydir)))
            raise StudyDirectoryError(msg)

        hist.check_dir_template(_missing_root, _missing_stage, \
                                               _missing_subdir)

    @classmethod
    def full_warn(cls, hist):
        """
        Emit dedicated exceptions with detailed info to the user
        if the study directory is missing or incomplete.

        Arguments:
            hist (HistoryMixing): the history to inspect

        Note:
            The `folder` attribute (expected study directory)
            must have been set before to call this method.
        """
        def _missing_root(_):
            """Task for a missing study directory."""
            msg = ("Run cases will not be loaded.\n\n"
                   "Continue anyway?")
            raise StudyDirectoryError(msg)

        stnames, dirs = hist.check_dir_template(_missing_root)

        if not stnames and not dirs:
            return

        msg = ""
        if stnames:
            msg += "The following stages will not be loaded ({0}/{1}):\n"\
                   .format(min(len(stnames), 5), len(stnames))
            for i in range(min(len(stnames), 5)):
                msg += "    {}\n".format(stnames[i])
            msg += "\n"

        if dirs:
            msg += "The following subfolders will be deleted ({0}/{1}):\n"\
                   .format(min(len(dirs), 5), len(dirs))
            for i in range(min(len(dirs), 5)):
                msg += "    {}\n".format(dirs[i])
            msg += "\n"

        msg += "Continue anyway?"
        raise StudyDirectoryError(msg)

    @classmethod
    def clean(cls, hist):
        """
        Makes the study directory consistent with the study:
        deletes stages without subfolder and conversely.

        Arguments:
            hist (HistoryMixing): the history to inspect

        Note:
            The `folder` attribute (expected study directory)
            must have been set before to call this method.
        """
        def _missing_root(hist):
            """Task for a missing study directory"""
            hist.current_case.own_stages_from(1)
            for case in hist.run_cases:
                case.delete()

        def _missing_stage(hist, stage):
            """Task for each *Stage* without subfolder"""
            if stage in hist.current_case:
                hist.current_case.own_stages_from(stage.number)
            stage.delete()

        def _missing_subdir(subdir):
            """Task for each subfolder without *Stage*"""
            shutil.rmtree(subdir)

        def _after_clean(hist):
            """Specific operations to do after a `clean`."""

            # delete run cases with no owned stages
            for case in hist.run_cases:
                if case.first_owned_stage_id() == -1:
                    case.delete()

            # remove empty case directories
            casedirs = HistoryMixing.listdir_exclude_emb(hist.folder)
            for casedir in casedirs:
                if not os.listdir(osp.join(hist.folder, casedir)):
                    os.rmdir(osp.join(hist.folder, casedir))

        hist.check_dir_template(_missing_root, _missing_stage, \
                                _missing_subdir, _after_clean)

    def check_dir_template(self,
                           missing_root=lambda _: None,
                           missing_stage=lambda *_: None,
                           missing_subdir=lambda _: None,
                           after_clean=lambda _: None):
        """
        Template for operations checking the study directory.

        Returns:
            tuple(stagedirs, orphandirs): List of paths.

            `stagedirs` is the list of the stage directories.

            `orphandirs` is the list of subdirectories of cases that are not a
            stage folder.
        """
        if self.missing_root:
            return missing_root(self)

        # list stage subdirectories
        dirlist = []
        stlist = []
        casedirs = HistoryMixing.listdir_exclude_emb(self.folder)

        for casedir in casedirs:
            stdirs = HistoryMixing.listdir_exclude_emb(osp.join(self.folder,
                                                                casedir))
            for stdir in stdirs:
                dirlist.insert(0, osp.join(self.folder, casedir, stdir))

        # delete stage with no subdir
        for case in reversed(self.run_cases):
            for stage in reversed(case.stages):
                if not self.folder or not osp.isdir(stage.folder) \
                        and not stage.is_intermediate():
                    stlist.append("{0}/{1}".format(stage.parent_case.name,
                                                   stage.name))
                    missing_stage(self, stage)
                else:
                    try:
                        dirlist.remove(stage.folder)
                    except ValueError:
                        pass

        # delete subdirs with no stage
        for orphandir in dirlist:
            missing_subdir(orphandir)

        after_clean(self)

        # return `dirlist` and `stagelist`
        return (stlist, dirlist)

    @property
    def tmpdir(self):
        """
        Directory where embedded files are put for the current case.
        """
        if not self.folder:
            return None
        return osp.join(self.folder, 'Embedded')

    def clean_embedded_files(self):
        """Removes directory with embedded files."""
        tmpdir = self.tmpdir
        if tmpdir and osp.isdir(tmpdir):
            _, subdirs, _ = next(os.walk(tmpdir))
            assert not subdirs
            shutil.rmtree(tmpdir)

    def save_embedded_files(self, directory):
        """
        Handle embedded files at save time.

        Arguments:
            directory (str): directory where to copy embedded files.

        Returns:
            list<str> : a list with the basenames of emb files.
        """
        tmpdir = self.tmpdir
        if tmpdir and osp.isdir(tmpdir):
            _, _, bnames = next(os.walk(tmpdir))
            for bname in bnames:
                source = osp.join(tmpdir, bname)
                dest = osp.join(directory, bname)
                assert source != dest
                shutil.copyfile(source, dest)
            return [to_str(bname) for bname in bnames]
        return []

    def load_embedded_files(self, directory, files, check=True):
        """
        Handle embedded files at load time.

        Arguments:
            directory (str): directory where files are stored.
            files (list<str>): list of basenames.
            check (bool): if *True*, checks there are no embedded
                files in the study dir at load time.

        Raises:
            ExistingSwapError: if there are files
                in the study directory at load time.
        """
        # test that there are no embbedded files
        tmpdir = self.tmpdir
        if (not tmpdir) or (not osp.isdir(tmpdir)):
            return
        if os.listdir(tmpdir):
            if check:
                errmsg = translate("AsterStudy",
                                   "Existing embedded files have been detected"
                                   " in directory {0}.\n"
                                   "This could be due to Salome stopping "
                                   "unexpectedly.\n"
                                   "Loading will override them.\n"
                                   "Do you wish to continue?").format(tmpdir)
                raise ExistingSwapError(errmsg)

            self.clean_embedded_files()
            os.makedirs(tmpdir)
        for bname in files:
            source = osp.join(directory, bname)
            dest = osp.join(tmpdir, bname)
            assert source != dest
            shutil.copyfile(source, dest)


class StageMixing(object):
    """Result related StageMixing."""

    _result = None
    _folder = ""
    __setattr__ = no_new_attributes(object.__setattr__)

    def __init__(self):
        """Create object."""
        self._result = Result(self)
        self._folder = ""

    @property
    def result(self):
        """Result: Attribute that holds Stage's result."""
        return self._result

    @result.setter
    def result(self, value):
        """Setter for the result."""
        self._result = value

    @property
    def state(self):
        """int: Attribute that holds Stage's Result status
        (*StateOptions*)."""
        return self.result.state

    @state.setter
    def state(self, state):
        """Set Stage's Result status (*StateOptions*)."""
        self.result.state = state

    def is_intermediate(self):
        """Tell if the stage is an intermediate one
        (means executed grouped with the following).
        """
        return self.result.is_intermediate()

    def set_intermediate(self):
        """Mark as an intermediate stage (not reusable)."""
        self.state = self.state | StateOptions.Intermediate

    @property
    def folder(self):
        """str: Attribute that holds Stage's folder path."""
        return self._folder_template(self.parent_case.folder) # pragma pylint: disable=no-member

    @property
    def remote_folder(self):
        """str: Remote folder where Stage's result database are kept."""
        return self._folder_template(self.parent_case.remote_folder) # pragma pylint: disable=no-member

    def _folder_template(self, cfolder):
        """
        Helper method to build the Stage's folder.

        Arguments:
            cfolder (str): the parent Case's folder.
        """
        if not self._folder:
            self._folder = 'Result-' + self.name # pragma pylint: disable=no-member
        return osp.join(cfolder, self._folder)

    def set_remote(self, value):
        """
        Sets the root remote folder if it is not already set,
        checks its consistence otherwise.

        Arguments:
            value (str): root remote folder.
        """
        # None means no remote directory
        if not value:
            return
        existing = self.model.remote_folder # pragma pylint: disable=no-member
        if not existing:
            self.model.remote_folder = value # pragma pylint: disable=no-member
        elif osp.dirname(osp.normpath(existing)) != osp.normpath(value):
            msg = ("The specified remote directory {0} is different "
                   "from the remote directory {1} of previous "
                   "runs".format(existing, value))
            raise StudyDirectoryError(msg)
        self.result.has_remote = True

    @property
    def database_path(self):
        """Return the pathname of the results database of the stage."""
        folder = self.remote_folder if self.result.has_remote else self.folder
        return osp.join(folder, 'base-stage{0}'.format(self.number)) # pragma pylint: disable=no-member

    @property
    def base_folder(self):
        """Get the basename of the Stage folder.
        Should be used only by the serializer."""
        return self._folder

    @base_folder.setter
    def base_folder(self, value):
        """Set the basename of the Stage folder.
        Should be used only by the serializer."""
        self._folder = value

    def __mul__(self, other):
        """Support native Python '*' operator protocol."""
        assert self.result * other.result is None

    def before_remove(self):
        """Prepare deletion."""
        self._result = None
