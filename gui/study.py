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
Study
-----

Implementation of study document within AsterStudy application.

"""

from __future__ import unicode_literals

import re
import os
import os.path as osp
import traceback

from functools import wraps

from PyQt5 import Qt as Q

from common import (AsterStudyError, AsterStudyInterrupt, CatalogError, CFG,
                    ConversionError, ExistingSwapError,
                    auto_dupl_on, debug_message, get_base_name, get_file_name,
                    show_exception, to_list, translate,
                    wait_cursor)
from datamodel import History, UndoRedo, Validity
from datamodel.general import ConversionLevel
from datamodel.engine import jobslist_factory
from . import Entity, HistoryProxy, NodeType, get_node_type
from . behavior import behavior
from . datafiles import create_data_files_model
from . datasettings import create_data_settings_model
from . widgets import MessageBox, TestnameDialog
from . controller import Controller


def study_extension():
    """
    Get extension for study files.

    Returns:
        str: Extension for study files.
    """
    return behavior().study_extension


def command_extension():
    """
    Get extension for command files.

    Returns:
        str: Extension for command files.
    """
    return behavior().comm_extension


def export_extension():
    """
    Get extension for export files.

    Returns:
        str: Extension for export files.
    """
    return behavior().export_extension


def command_mask():
    """
    Get mask for extension of command files.

    Returns:
        str: Mask for command files extension.
    """
    return behavior().comm_file_mask


def undo_redo_disabled():
    """Tell if the Undo/Redo feature is disabled.

    Returns:
        bool: *True* if the feature is disabled, *False* otherwise.
    """
    return behavior().disable_undo_redo


def manage_dm_access(operation_name, default=False, changed=True):
    """
    Manage data modification access to data model.

    This is a decoration function to manage data modification access to
    the data model. It can be used for the methods of the class Study
    only.

    Decorated function may return boolean result; in that case *True*
    means success and *False* means failure.

    Alternatively function may produce a data model object and return it
    as result. In that case, operation is considered as finished
    successfully if result is not *None*.

    Decorated function may or may not modify data model. Parameter
    *changed* controls if decorator has to call `commit()` / `revert()`
    functions; this is needed to properly maintain data model integrity.

    The decorator catches the following exceptions:

    - RuntimeError: In this case it shows a message box with the caught
      exception's message.

    - Exception: All other exceptions are treated in general way. In
      this case the general error message string informing about
      unexpected error occurred is appeared in the message box. It is
      composed from the operation name and exception's message.

    In case if general exception handling algorithm is enough it is not
    necessary to do special actions. However if a special treament is
    required, it is necessary to raise RuntimeError with the translated
    string. It is shown in the message box as it is.

    Example of usage:
    @manage_dm_access(translate("AsterStudy", "New stage"))

    Arguments:
        operation_name (str): The name of an operation to be decorated.
            Operation name should be translated.
        changed (Optional[bool]): Specify if data model can be changed
            within the operation. Defaults to *True*.

    Returns:
        function: Decorator function.
        """
    def decorator(function):
        """
        Decorate function call.

        Returns the function that manages call of decorated function,
        i.e. calls it within try-except block and calls `commit()` in
        case if successfull data model modification or `revert`
        otherwise.

        Arguments:
            function (function): Decorated function.

        Returns:
            function: `try_call_except` function.
        """
        # To keep the original function name an documentation.
        @wraps(function)
        def try_call_except(self, *args, **kwargs):
            """
            Decorates the call of the function.

            Arguments:
                *args: Positional arguments.
                **kwargs: Keyword arguments.

            Returns:
                bool, object: Result of the decorated function.
            """
            with auto_dupl_on(self.activeCase, changed):
                result = default
                try:
                    ctrl = Controller(operation_name, self.astergui())
                    if ctrl.controllerStart():
                        result = function(self, *args, **kwargs)
                    else:
                        ctrl.controllerAbort()
                except RuntimeError as detail:
                    ctrl.controllerAbort()
                    wait_cursor(False, force=True)
                    Q.QMessageBox.critical(self.astergui().mainWindow(),
                                           "AsterStudy", detail.args[0])
                except Exception as detail: # pragma pylint: disable=broad-except
                    ctrl.controllerAbort()
                    message = translate("AsterStudy",
                                        "Unexpected error during operation "
                                        "{0!r}:").format(operation_name)
                    show_exception(detail, message=message)

                if ctrl.isActive():
                    ctrl.controllerCommit()
                    if changed:
                        wait_cursor(True)
                        is_ok = result if isinstance(result, bool) else \
                            result is not None
                        if is_ok:
                            self.commit(operation_name)
                        else:
                            self.revert()
                        wait_cursor(False)
                return result
        return try_call_except
    return decorator


# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class Study2History(HistoryProxy):
    """Wraps History instance for Data Settings model."""

    def __init__(self, study):
        """
        Create adaptor.

        Arguments:
            study: Parent study.
        """
        self._study = study

    @property
    def root(self):
        """Redefined from *HistoryProxy*."""
        return self.case

    @property
    def case(self):
        """Redefined from *HistoryProxy*"""
        return self._study.activeCase

    @property
    def history(self):
        """
        Get history being managed.

        Returns:
            History: Actual history instance.
        """
        return self._study.history


class CaseProxy(object):
    """Wraps current Case instance for Data Files model."""

    def __init__(self, study):
        """
        Create adaptor.

        Arguments:
            study: Owning study.
        """
        self._study = study

    def __call__(self):
        """This method is called when a current Case instance is required."""
        return self._study.case


class Study(object):
    """
    Representation of the document within the AsterStudy application.
    """

    def __init__(self, astergui, **kwargs):
        """
        Create Study object.

        Study can be constructed in two ways:

        - By specifying *code_aster version*: via *version* keyword
          argument. In this case, new empty study is created.
        - By specifying a study *file name*: via *file_name* keyword
          argument. In this case, study is loaded from the file.

        Arguments:
            astergui (AsterGui): Parent AsterGui instance.
            **kwargs: Keyword arguments.

        Raises:
            RuntimeError: If study cannot be created.
        """
        self._astergui = astergui
        self._ajs_file = None
        self._hdf_file = None
        self._active_case = None

        history = None
        if "file_name" in kwargs and kwargs["file_name"]:
            file_name = kwargs["file_name"]

            perm_file = kwargs["url"] if "url" in kwargs and kwargs["url"] \
                                      else file_name
            try:
                history = self._load_wrapper(file_name, perm_file, level=-1)
            except Exception as exc:
                debug_message("Loading error:", traceback.format_exc())
                message = translate("AsterStudy",
                                    "Your study file can not be reloaded.\n\n"
                                    "A new empty study will be created.")
                MessageBox.critical(self.astergui().mainWindow(),
                                    "AsterStudy", message,
                                    detailedText=str(exc))
                raise RuntimeError(str(exc))
            self._ajs_file = file_name
        else:
            version = kwargs.get("version", CFG.default_version)
            try:
                history = History(version)
            except CatalogError:
                msg = translate("AsterStudy",
                                "Cannot import catalog of version "
                                "{0!r}.").format(version)
                raise RuntimeError(msg)
            except Exception as exc:
                msg = translate("AsterStudy",
                                "Cannot create history for code_aster "
                                "version {0!r}\n"
                                "Reason: {1}").format(version, exc)
                raise RuntimeError(msg)

        if history is None:
            raise RuntimeError("Bad history")

        self._undo_redo = UndoRedo(history, disable_cbck=undo_redo_disabled)

        study2history = Study2History(self)
        self._category_model = create_data_settings_model(study2history)

        case_proxy = CaseProxy(study2history)
        self._data_files_model = create_data_files_model(case_proxy)

        self._state = self._undo_redo.current_state

        jobslist_factory().load_jobs(history.jobs_list)

    def _load_wrapper(self, file_name, perm_file, level=0):
        """
        Wrapper of load with additional checks on the study directory.

        Arguments:
            file_name (str): file from where to load Asterstudy's data model.
            perm_file (str): non-temporary persistence file,
                HDF in Salome, `file_name` in standalone.
            level (int): checking operation to perform
                0=plain warning, 1=detailed warning, 2=clean study and dir.
        """
        operations = [History.warn, History.full_warn, History.clean]
        # load ajs file
        history = self._load_ajs(file_name)

        # set expected study directory
        if perm_file:
            path = osp.splitext(perm_file)[0] + '_Files'
            history.folder = path
        # check directory
        debug_message("checking '_Files' directory ({})...".format(level))
        try:
            history.check_dir(operations[level])
            return history
        except AsterStudyError as exc:
            if level == 2:
                raise
            ask = MessageBox.warning(parent=self.astergui().mainWindow(),
                                     buttons=MessageBox.Ok | MessageBox.Cancel,
                                     defaultButton=MessageBox.Cancel,
                                     **exc.for_messagebox())
            if isinstance(exc, AsterStudyInterrupt):
                raise
            if ask == MessageBox.Ok:
                return self._load_wrapper(file_name, perm_file, level+1)
            raise RuntimeError("Loading operation cancelled.")

    def _load_ajs(self, file_name, **args):
        """Wrapper of ajs loader to propose several choices to the user."""
        try:
            history = History.load(file_name, **args)
        except KeyError as exc:
            if "aster_version" in exc.args[0]:
                defvers = CFG.default_version
                trbk = os.linesep.join([exc.__class__.__name__ + str(exc.args),
                                        "", traceback.format_exc(exc)])
                message = translate("AsterStudy",
                                    "It seems that your study used a version "
                                    "that is not available anymore.\n\n"
                                    "Do you want to try using the default "
                                    "version ({0!s})?\n\n"
                                    "The stages may be imported in text mode "
                                    "in case of syntaxic incompatibility."
                                   ).format(defvers)
                ask = MessageBox.critical(
                    self.astergui().mainWindow(),
                    "AsterStudy", message,
                    buttons=MessageBox.Yes | MessageBox.No,
                    defaultButton=MessageBox.Yes,
                    detailedText=trbk)
                if ask == MessageBox.No:
                    raise
                # try loading with the default version
                args['aster_version'] = defvers
                history = self._load_ajs(file_name, **args)
            else:
                raise

        except ValueError as exc:
            if "study was created using" in exc.args[0]:
                trbk = os.linesep.join([exc.__class__.__name__ + str(exc.args),
                                        "", traceback.format_exc(exc)])
                message = translate("AsterStudy",
                                    exc.args[0] + "\n\n"
                                    "Do you want to continue anyway?\n\n")
                ask = MessageBox.critical(
                    self.astergui().mainWindow(),
                    "AsterStudy", message,
                    buttons=MessageBox.Yes | MessageBox.No,
                    defaultButton=MessageBox.Yes,
                    detailedText=trbk)
                if ask == MessageBox.No:
                    raise
                # try without the Restore flag
                args['strict'] = ConversionLevel.Syntaxic
                history = self._load_ajs(file_name, **args)
            else:
                raise

        except ConversionError as exc:
            trbk = os.linesep.join([exc.msg, "", exc.details])
            message = translate("AsterStudy",
                                "At least one stage that was in graphical "
                                "mode can not be re-imported.\n\n"
                                "Do you want to create a stage with "
                                "the first commands and a second with "
                                "the last part in text mode?\n\n"
                                "See the details for the unsupported "
                                "features.")
            ask = MessageBox.critical(
                self.astergui().mainWindow(),
                "AsterStudy", message,
                buttons=MessageBox.Yes | MessageBox.No,
                defaultButton=MessageBox.Yes,
                detailedText=trbk)
            if ask == MessageBox.No:
                raise
            # try loading with partial conversion
            args['strict'] = ConversionLevel.Partial
            history = self._load_ajs(file_name, **args)

        except Exception as exc: # pragma pylint: disable=broad-except
            trbk = os.linesep.join([exc.__class__.__name__ + str(exc.args),
                                    "", traceback.format_exc(exc)])
            message = translate("AsterStudy",
                                "Sorry it failed again!\n\n"
                                "The study will be loaded in failsafe mode "
                                "(all stages in text mode).\n\n"
                                "See the details for the unsupported "
                                "features.")
            ask = MessageBox.critical(
                self.astergui().mainWindow(),
                "AsterStudy", message,
                buttons=MessageBox.Ok,
                defaultButton=MessageBox.Ok,
                detailedText=trbk)
            args['strict'] = ConversionLevel.NoGraphical
            history = self._load_ajs(file_name, **args)

        return history

    @property
    def history(self):
        """
        Get study history.

        Returns:
            History: Associated History object.
        """
        return self._undo_redo.model

    @property
    def activeCase(self):
        """
        Get currently active Case.

        Returns:
            Case: Currently active Case.
        """
        case = self.node(Entity(self._active_case, NodeType.Case)) \
            if self._active_case is not None else None
        return case if case is not None else self.history.current_case

    @activeCase.setter
    def activeCase(self, case):
        """
        Set active Case.

        Arguments:
            Case: Case to activate.
        """
        self._active_case = case.uid if case is not None else None

    def isActiveCase(self, case):
        """
        Check if specified Case is a currently active one.

        Arguments:
            case (Case): Case to check.

        Returns:
            bool: *True* if Case is currently active; *False* otherwise.
        """
        # pragma pylint: disable=no-member
        return self.activeCase.uid == case.uid \
            if self.activeCase is not None and case is not None else False

    def isCurrentCase(self):
        """
        Check if History's Current Case is an active one.

        Returns:
            bool: *True* if Current Case is currently active;
            *False* otherwise.
        """
        # pragma pylint: disable=no-member
        return self.activeCase.uid == self.history.current_case.uid \
            if self.activeCase is not None else False

    def name(self):
        """
        Get study name.

        Returns:
            str: Study name.

        See also:
            `url()`
        """
        return get_base_name(self._ajs_file, False) \
            if self._ajs_file else "Noname"

    def url(self):
        """
        Get file name associated with study.

        It is the full pathname to the hdf file in Salome or
        the ajs file in the standalone mode

        Returns:
            str: File name (*None* if not set).

        See also:
            `name()`
        """
        return self._hdf_file or self._ajs_file

    def set_url(self, path):
        """
        Set the path of the hdf filename.

        Arguments:
            path (str): Absolute path of the hdf file in Salome.
        """
        self._hdf_file = path

    def astergui(self):
        """
        Get aster gui.

        Returns:
            AsterGui: Associated aster gui object.
        """
        return self._astergui

    def categoryModel(self):
        """
        Get category model.

        Returns:
            datasettings.Model: Category model of the study.
        """
        return self._category_model

    def dataFilesModel(self):
        """
        Get data files model.

        Returns:
            datafiles.Model: Data Files model of the study.
        """
        return self._data_files_model

    def node(self, entity):
        """
        Get data object from the model.

        Arguments:
            entity (Entity): Selection entity.

        Returns:
            Node: Data model object (*None* if object is not found).
        """
        node = None
        if entity.type in (NodeType.Category,):
            node = self.categoryModel().category(entity.uid)
        elif entity.type in (NodeType.Dir, NodeType.Unit):
            node = self.dataFilesModel().object(entity)
        elif entity.type not in (NodeType.Unknown,):
            node = self.history.get_node(entity.uid)
        return node

    @staticmethod
    def load(astergui, file_name, url=''):
        """
        Load study from specified file.

        Arguments:
            astergui (AsterGui): Parent AsterGui instance.
            file_name (str): Path to the file.
            url (str): Path to the original HDF file (in Salome).

        Raises:
            RuntimeError: If `file_name` is *None* or empty.

        See also:
            `save()`, `saveAs()`
        """
        return Study(astergui, file_name=file_name, url=url)

    def save(self):
        """
        Save study to associated file.

        Raises:
            RuntimeError: If there is no file name associated with the
                study.
            IOError: If file could not be written.

        See also:
            `load()`, `saveAs()`
        """
        History.save(self._undo_redo.last, self._ajs_file)

        self._state = self._undo_redo.current_state

    def saveAs(self, filename):
        """
        Save study to specified file.

        Arguments:
            filename (str): Path to the file.

        Raises:
            RuntimeError: If *filename* is *None* or empty.
            IOError: If file could not be written.

        See also:
            `save()`, `load()`
        """
        History.save(self._undo_redo.last, filename)

        self._ajs_file = filename
        self._state = self._undo_redo.current_state

    @manage_dm_access(translate("AsterStudy", "Duplicate"), None)
    def duplicate(self, node): # pragma pylint: disable=no-self-use
        """
        Duplicate object.

        Arguments:
            node (Node): Data model object to duplicate.

        Returns:
            Node: New node which is a copy of source one in case of
            success; *None* otherwise.
        """
        if node is None:
            return None

        try:
            wait_cursor(True)
            content = str(node)
            stage = node.stage
            return stage.paste(content)
        except Exception:
            message = translate("AsterStudy", "Cannot duplicate node")
            raise RuntimeError(message)
        finally:
            wait_cursor(False)

    def copy(self, nodes): # pragma pylint: disable=no-self-use
        """
        Copy object.

        Arguments:
            nodes [Node]: Data model objects to copy: command or variable.

        Returns:
            (str): Text representation of specified objects.
        """
        result = ''
        if nodes is not None:
            try:
                wait_cursor(True)

                node_list = to_list(nodes)
                result = "\n".join([str(i) for i in node_list])

                wait_cursor(False)
            except StandardError:
                result = ''
        return result

    @manage_dm_access(translate("AsterStudy", "Cut"), None)
    def cut(self, nodes): # pragma pylint: disable=no-self-use
        """
        Cut object.

        Arguments:
            nodes [Node]: Data model objects to cut: commands or variables.

        Returns:
            (str): Text representation of specified objects.
        """
        result = None
        if nodes is not None:
            try:
                wait_cursor(True)

                node_list = to_list(nodes)
                result = "\n".join([str(i) for i in node_list])
                for i in node_list:
                    i.delete()

                wait_cursor(False)
            except Exception:
                message = translate("AsterStudy", "Cannot cut node(s)")
                raise RuntimeError(message)
        return result

    @manage_dm_access(translate("AsterStudy", "Paste"), None)
    def paste(self, stage, content): # pragma pylint: disable=no-self-use
        """
        Paste objects.

        Arguments:
            stage (Stage): Stage for pasting objects.
            content (str): Text representation of pasted objects

        Returns:
            [Node]: List of pasted objects if stage in graphics mode or
            list with Stage object otherwise.
        """
        if stage is None:
            return None

        if content is None:
            return None

        try:
            wait_cursor(True)
            return stage.paste(content)
        except Exception:
            message = translate("AsterStudy", "Cannot paste node(s)")
            raise RuntimeError(message)
        finally:
            wait_cursor(False)

    @manage_dm_access(translate("AsterStudy", "Delete"))
    def delete(self, nodes):
        """
        Delete objects.

        Arguments:
            nodes (list[Node]): Data model objects to delete.

        Returns:
            bool: *True* if at least one node was removed; *False*
            otherwise.
        """
        # pragma pylint: disable=too-many-locals
        deleted = 0
        extra_kw = {}

        is_case_deleted = False
        cases = [node for node in nodes if \
                     get_node_type(node) == NodeType.Case]
        for case in cases:
            other_cases = [i for i in case.used_by_others() if i not in nodes]
            if other_cases:
                is_case_deleted = True
                break

        stages = [node for node in nodes if \
                      get_node_type(node) == NodeType.Stage]
        are_child_stages_deleted = False
        for stage in stages:
            if stage.parent_case in nodes:
                continue
            child_stages = [i for i in stage.child_stages if i not in nodes]
            if child_stages:
                are_child_stages_deleted = True
                break

        dirs = [node for node in nodes if \
                    get_node_type(node) == NodeType.Dir]
        is_dir_deleted = len(dirs) > 0

        # 1. General question: confirm delete
        pref_mgr = self.astergui().preferencesMgr()
        msg = translate("AsterStudy",
                        "Selected objects will be deleted. Are you sure?")
        noshow = "delete"
        ask = MessageBox.question(self._astergui.mainWindow(),
                                  translate("AsterStudy", "Delete"), msg,
                                  MessageBox.Yes | MessageBox.No,
                                  MessageBox.Yes, noshow=noshow,
                                  prefmgr=pref_mgr)

        # 2. If case is deleted, confirm deleting of case(s) used by others
        if ask == MessageBox.Yes and is_case_deleted:
            if not behavior().allow_delete_cases:
                msg = translate("AsterStudy",
                                "Cannot remove case used by other case(s).")
                MessageBox.critical(self._astergui.mainWindow(),
                                    "AsterStudy", msg)
                return False
            msg = translate("AsterStudy",
                            "Do you want to remove case "
                            "used by other case(s)?")
            noshow = "delete_case"
            ask = MessageBox.question(self._astergui.mainWindow(),
                                      translate("AsterStudy", "Delete"), msg,
                                      MessageBox.Yes | MessageBox.No,
                                      MessageBox.Yes, noshow=noshow,
                                      prefmgr=pref_mgr)

        # 3. If stage is deleted, confirm deleting of child stage(s)
        if ask == MessageBox.Yes and are_child_stages_deleted:
            msg = translate("AsterStudy",
                            "This operation will remove selected stage(s) "
                            "and all subsequent ones.\n"
                            "Continue?")
            noshow = "delete_stages"
            ask = MessageBox.question(self._astergui.mainWindow(),
                                      translate("AsterStudy", "Delete"), msg,
                                      MessageBox.Yes | MessageBox.No,
                                      MessageBox.Yes, noshow=noshow,
                                      prefmgr=pref_mgr)

        # 4. If directory is deleted, confirm deleting of child file(s)
        if ask == MessageBox.Yes and is_dir_deleted:
            msg = translate("AsterStudy", "You are removing one or more "
                            "directories from study. Remove also all related "
                            "data files?")
            informative = translate("AsterStudy", "Warning: Files belonging "
                                    "to graphical stages will not be removed!")
            ret = MessageBox.question(self._astergui.mainWindow(),
                                      translate("AsterStudy", "Delete"), msg,
                                      MessageBox.Yes | MessageBox.No | \
                                          MessageBox.Cancel,
                                      MessageBox.Yes,
                                      informativeText=informative)
            if ret == MessageBox.Cancel:
                return False
            extra_kw["delete_files"] = ret == MessageBox.Yes

        if ask == MessageBox.Yes:
            wait_cursor(True)
            for node in nodes:
                if get_node_type(node) == NodeType.Case and self.url() and \
                   node.model is not None:
                    node.model.folder = osp.splitext(self.url())[0] + '_Files'
                if not hasattr(node, 'model') or node.model is not None:
                    node.delete(**extra_kw)
                deleted = deleted + 1
            wait_cursor(False)
        return deleted > 0

    @manage_dm_access(translate("AsterStudy", "New case"), None)
    def newCase(self):
        """
        Create new case.

        Returns:
            Case: New Case in case of success; *None* in case of
            failure.
        """
        result = None
        case = self.history.current_case
        if case is not None and case.nb_stages > 0:
            msg = translate("AsterStudy",
                            "Current case is not empty. "
                            "All changes will be discarded.")
            ask = Q.QMessageBox.question(self._astergui.mainWindow(),
                                         "AsterStudy", msg,
                                         MessageBox.Ok | MessageBox.Cancel,
                                         MessageBox.Ok)
            if ask == MessageBox.Cancel:
                return None
        wait_cursor(True)
        result = self.history.create_case(replace=True)
        wait_cursor(False)
        return result

    @manage_dm_access(translate("AsterStudy", "Import case"), None)
    def importCase(self):
        """
        Create new case from an export file.

        Returns:
            Case: New Case in case of success; *None* in case of
            failure.
        """
        result = None
        case = self.history.current_case
        if case is not None and case.nb_stages > 0:
            msg = translate("AsterStudy",
                            "Current case is not empty. "
                            "All changes will be discarded.")
            ask = Q.QMessageBox.question(self._astergui.mainWindow(),
                                         "AsterStudy", msg,
                                         MessageBox.Ok | MessageBox.Cancel,
                                         MessageBox.Ok)
            if ask == MessageBox.Cancel:
                return None
        title = translate("AsterStudy", "Import an export file from ASTK")
        file_filter = [
            translate("AsterStudy", "Export files") + " (*.export)",
            translate("AsterStudy", "Astk files") + " (*.astk)",
            translate("AsterStudy", "From flasheur directory") + " (*.p[0-9]*)"
        ]

        file_name = get_file_name(1, self._astergui.mainWindow(),
                                  title, "", file_filter)
        if file_name:
            try:
                wait_cursor(True)
                result = self.history.import_case(file_name, replace=True)
                wait_cursor(False)
            except Exception as exc:
                message = translate("AsterStudy", "Cannot import case")
                raise RuntimeError(message + '\n' + str(exc))
        return result

    @manage_dm_access(translate("AsterStudy", "Import a testcase"),
                      None)
    def importCaseTest(self):
        """
        Create new case from a testcase.

        Returns:
            Case: New Case in case of success; *None* in case of
            failure.
        """
        result = None
        case = self.history.current_case
        if case is not None and case.nb_stages > 0:
            msg = translate("AsterStudy",
                            "Current case is not empty. "
                            "All changes will be discarded.")
            ask = Q.QMessageBox.question(self._astergui.mainWindow(),
                                         "AsterStudy", msg,
                                         MessageBox.Ok | MessageBox.Cancel,
                                         MessageBox.Ok)
            if ask == MessageBox.Cancel:
                return None

        file_name = TestnameDialog.execute(self._astergui,
                                           translate("AsterStudy",
                                                     "Enter a testcase name"),
                                           translate("AsterStudy",
                                                     "Testcase name"))
        if file_name:
            try:
                wait_cursor(True)
                export = osp.join(self.history.tests_path,
                                  file_name + "." + export_extension())
                debug_message("Importing {0}...".format(export))
                result = self.history.import_case(export, replace=True)
                wait_cursor(False)
            except Exception as exc:
                message = translate("AsterStudy", "Cannot import the testcase")
                raise RuntimeError(message + '\n' + str(exc))
        return result

    @manage_dm_access(translate("AsterStudy", "Export Case for a testcase"),
                      False, False)
    def exportCaseTest(self, case):
        """
        Export a case for a testcase.

        Arguments:
            case (Case): Case to export.

        Returns:
            bool: *True* in case of success; *False* otherwise.
        """
        if case is None:
            return False

        title = translate("AsterStudy", "Choose new export file name")
        file_filter = translate("AsterStudy", "Export files") + " (*.export)"

        file_name = get_file_name(0, self._astergui.mainWindow(),
                                  title, case.name + "." + export_extension(),
                                  file_filter,
                                  export_extension())
        if not file_name:
            return False

        wait_cursor(True)
        case.export(file_name)
        wait_cursor(False)

        return True


    @manage_dm_access(translate("AsterStudy", "Add stage"), None)
    def newStage(self):
        """
        Add a new stage.

        Returns:
            Stage: New Stage in case of success; *None* in case of
            failure.
        """
        result = None
        case = self.history.current_case
        if case is None:
            Q.QMessageBox.critical(self._astergui.mainWindow(),
                                   "AsterStudy",
                                   translate("AsterStudy", "Null case"))
        else:
            wait_cursor(True)
            result = case.create_stage()
            wait_cursor(False)
        return result

    @manage_dm_access(translate("AsterStudy", "Add Stage from File"), None)
    def importStage(self, force_text=False):
        """
        Add a new stage from a file.

        Returns:
            Stage: New Stage in case of success; *None* in case of
            failure.
        """
        result = None
        case = self.history.current_case
        if case is None:
            Q.QMessageBox.critical(self._astergui.mainWindow(),
                                   "AsterStudy",
                                   translate("AsterStudy", "Null case"))
        else:
            title = translate("AsterStudy", "Import File")
            file_filter = translate("AsterStudy", "Command files")
            file_filter = file_filter + " (*.%s)" % command_mask()

            file_name = get_file_name(1, self._astergui.mainWindow(),
                                      title, "", file_filter,
                                      command_extension())
            if file_name:
                try:
                    nblines = len(open(file_name, 'rb').readlines())
                    if not force_text and nblines > behavior().nblines_limit:
                        msg = translate("AsterStudy",
                                        "The selected file is {0} lines "
                                        "long.\n\n"
                                        "Importing it in graphical mode may "
                                        "take a while.\nLater modifications "
                                        "may be very long too.\n\n"
                                        "Do you want to import it in text "
                                        "mode?")
                        mbox = Q.QMessageBox(MessageBox.Warning,
                                             "AsterStudy",
                                             msg.format(nblines),
                                             MessageBox.Yes | MessageBox.No,
                                             self._astergui.mainWindow())
                        mbox.setDefaultButton(MessageBox.Yes)
                        ask = mbox.exec_()
                        if ask == MessageBox.Yes:
                            force_text = True

                    strict_mode = ConversionLevel.NoFail
                    if behavior().strict_import_mode:
                        strict_mode = ConversionLevel.Syntaxic
                    wait_cursor(True)
                    result = case.import_stage(file_name, strict_mode,
                                               force_text)
                    wait_cursor(False)
                    if not force_text and result.can_use_graphical_mode() \
                        and result.is_text_mode():
                        msg = translate("AsterStudy",
                                        "The stage cannot be converted to "
                                        "graphical mode.\n\n"
                                        "Do you want to create a stage with "
                                        "the first commands and a second with "
                                        "the last part in text mode?\n\n"
                                        "See the details for the unsupported "
                                        "features.")
                        mbox = Q.QMessageBox(MessageBox.Warning,
                                             "AsterStudy",
                                             msg,
                                             MessageBox.Yes | MessageBox.No,
                                             self._astergui.mainWindow())
                        mbox.setDefaultButton(MessageBox.Yes)
                        mbox.setDetailedText(result.conversion_report)
                        ask = mbox.exec_()
                        if ask == MessageBox.Yes:
                            # TODO use 'revert()' but?!
                            del case[-1]
                            partial = strict_mode | ConversionLevel.Partial
                            wait_cursor(True)
                            result = case.import_stage(file_name, partial)
                            wait_cursor(False)
                        else:
                            result = None
                except Exception:
                    message = translate("AsterStudy", "Cannot import stage")
                    raise RuntimeError(message)

        if result is not None:
            self._checkDataFiles(result)

        return result

    @manage_dm_access(translate("AsterStudy", "Export Command File"),
                      False, False)
    def exportStage(self, stage):
        """
        Export stage to a COMM file.

        Arguments:
            stage (Stage): Stage to export.

        Returns:
            bool: *True* in case of success; *False* otherwise.
        """
        if stage is None:
            return False

        title = translate("AsterStudy", "Export File")
        file_filter = translate("AsterStudy", "Command files")
        file_filter = file_filter + " (*.%s)" % command_mask()

        file_name = get_file_name(0, self._astergui.mainWindow(),
                                  title, stage.name + "." + command_extension(),
                                  file_filter,
                                  command_extension())
        if not file_name:
            return False

        wait_cursor(True)
        stage.export(file_name)
        wait_cursor(False)

        return True

    def hasStages(self):
        """
        Check if there are stages in the model.

        Returns:
            bool: *True* if current case has stages; *False* otherwise.
        """
        case = self.history.current_case
        return case is not None and case.nb_stages > 0

    @manage_dm_access(translate("AsterStudy", "Rename"))
    def rename(self, node, value):
        """
        Rename item.

        Arguments:
            node (Node): Data model object to rename.
            value (str): New name.

        Returns:
            bool: *True* in case of success; *False* otherwise.
        """
        result = False
        if node is not None and hasattr(node, "rename"):
            match = re.search("^[_]*[a-zA-Z]+\\w*$", value)
            if match is None:
                message = translate("AsterStudy", \
                    "The name is not valid. The old name is restored.")
                Q.QMessageBox.warning(self._astergui.mainWindow(),
                                      "AsterStudy", message)
            elif get_node_type(node) == NodeType.Variable and \
                    value in node.current_context:
                message = translate("AsterStudy",
                                    "Name '{}' is already in use")
                Q.QMessageBox.critical(self._astergui.mainWindow(),
                                       "AsterStudy", message.format(value))
            else:
                node.rename(value)
                result = True
        return result

    @manage_dm_access(translate("AsterStudy", "Add command"), None)
    def addCommand(self, stage, command_type):
        """
        Add a command to the study.

        Arguments:
            stage (Stage): Parent Stage.
            command_type (str): Type of the Command being added.

        Returns:
            Command: New command in case of success; *None* otherwise.
        """
        # pragma pylint: disable=no-self-use
        result = None
        if stage is not None:
            try:
                result = stage.add_command(command_type)
            except Exception:
                message = translate("AsterStudy", "Cannot add command")
                raise RuntimeError(message)
        return result

    @manage_dm_access(translate("AsterStudy", "Switch to graphical mode"))
    def setStageGraphicalMode(self, stage):
        """
        Switch the stage in the graphical mode.

        Arguments:
            stage (Stage): Stage being converted.

        Returns:
            bool: *True* if the stage has been switched to the graphical
            mode; *False* otherwise.
        """
        result = False
        if stage is not None:
            if stage.can_use_graphical_mode():
                text = stage.get_text(pretty_text=False, enclosed=False)
                lines_before = [i for i in text.splitlines() if i.strip()]
                text = re.sub("^ *#.*", "", text)
                lines = [i for i in text.splitlines() if i.strip()]
                if lines_before and not lines:
                    message = translate("AsterStudy",
                                        "The commands file contains only "
                                        "comments.\nThey will be lost in "
                                        "graphical mode.\n\n"
                                        "Do you want to continue?")
                    ask = MessageBox.question(self.astergui().mainWindow(),
                                              "AsterStudy", message)
                    if ask == MessageBox.No:
                        return False
                try:
                    stage.use_graphical_mode(behavior().strict_import_mode)
                    result = True
                except Exception: # pragma pylint: disable=broad-except
                    message = translate("AsterStudy", \
                            "Cannot convert the stage to graphic mode")
                    mbox = Q.QMessageBox(MessageBox.Warning,
                                         "AsterStudy",
                                         message,
                                         MessageBox.Ok,
                                         self._astergui.mainWindow())
                    mbox.setDetailedText(stage.conversion_report)
                    mbox.setEscapeButton(mbox.button(MessageBox.Ok))
                    mbox.show()
            else:
                message = translate("AsterStudy",
                                    "Cannot switch to graphical mode")
                Q.QMessageBox.critical(self._astergui.mainWindow(),
                                       "AsterStudy", message)

        if result:
            self._checkDataFiles(stage)

        return result

    @manage_dm_access(translate("AsterStudy", "Switch to text mode"))
    def setStageTextMode(self, stage):
        """
        Switch the stage in the text mode.

        Arguments:
            stage (Stage): Stage being converted.

        Returns:
            bool: *True* if the stage has been switched to the text
            mode; *False* otherwise.
        """
        result = False
        if stage is not None:
            is_valid = stage.check() == Validity.Nothing
            if not is_valid:
                pref_mgr = self.astergui().preferencesMgr()
                msg = translate("AsterStudy",
                                "The stage is syntactically invalid.\n"
                                "Come back to graphical mode may be not "
                                "completely possible.\n\n"
                                "Do you want to continue?")
                noshow = "convert_invalid_graphic_stage"
                ask = MessageBox.question(self._astergui.mainWindow(),
                                          "AsterStudy", msg,
                                          MessageBox.Yes | MessageBox.No,
                                          MessageBox.Yes, noshow=noshow,
                                          prefmgr=pref_mgr)
                if ask != MessageBox.Yes:
                    return False
            if stage.can_use_text_mode(False):
                wait_cursor(True)
                try:
                    stage.use_text_mode()
                    result = True
                except Exception:
                    message = translate("AsterStudy", \
                            "Cannot convert the stage to text mode")
                    raise RuntimeError(message)
                finally:
                    wait_cursor(False)
            else:
                message = translate("AsterStudy", "Cannot switch to text mode")
                Q.QMessageBox.critical(self._astergui.mainWindow(),
                                       "AsterStudy", message)
        return result

    @manage_dm_access(translate("AsterStudy", "Edit stage"))
    def editStage(self, stage, new_text):
        """
        Assign new text to the Stage.

        Arguments:
            stage (Stage): Stage to be modified.
            new_text (str): New text of the stage.

        Returns:
            bool: *True* if the stage has been modified; *False*
            otherwise.
        """
        result = False
        if get_node_type(stage) == NodeType.Stage:
            if stage.is_text_mode():
                stage.set_text(new_text)
                result = True
            else:
                message = translate("AsterStudy", "Stage is not in text mode")
                Q.QMessageBox.critical(self._astergui.mainWindow(),
                                       "AsterStudy", message)
        else:
            message = translate("AsterStudy", "The item is not a stage")
            Q.QMessageBox.critical(self._astergui.mainWindow(),
                                   "AsterStudy", message)
        return result

    @manage_dm_access(translate("AsterStudy", "Back up"))
    def backUp(self):
        """
        Make backup copy of current case.

        Returns:
            Case: Backup case in case of success; *None* otherwise.
        """
        wait_cursor(True)
        backup_case = self.history.create_backup_case()
        wait_cursor(False)
        return backup_case

    @manage_dm_access(translate("AsterStudy", "Copy as current"))
    def copyAsCurrent(self, node):
        """
        Copy the specified case content into the Current case object.

        Arguments:
            node (Case): Case object to copy.

        Returns:
            bool: *True* if at case copied successful; *False* otherwise.
        """
        state = False
        curcase = self.history.current_case
        if curcase is not None and curcase != node:
            wait_cursor(True)
            curcase.copy_from(node)
            state = True
            wait_cursor(False)
        return state

    # Current behavior of Directory.remove() operation is to keep
    # directory and related files in the study; see Directory class in
    # gui/datafiles/objects.py.
    # If behavior changes, and files are removed from study, this
    # operation should become undoable, so the following decorator
    # should be uncommented.
    # @manage_dm_access(translate("AsterStudy", "Remove directory"))
    def removeDir(self, directory): # pragma pylint: disable=no-self-use
        """
        Remove directory from disk.

        Arguments:
            directory (Directory): Directory to remove.

        Returns:
            bool: *True* if directory was successfully removed; *False*
            otherwise.
        """
        if directory is None:
            return None

        result = False
        try:
            wait_cursor(True)
            directory.remove()
            result = True
        except Exception:
            message = translate("AsterStudy", "Cannot remove directory")
            raise RuntimeError(message)
        finally:
            wait_cursor(False)
        return result

    def isModified(self):
        """
        Check if study has been modified.

        Returns:
            bool: *True* if study has been modified; *False* otherwise.
        """
        return self._state != self._undo_redo.current_state

    def hasUndo(self):
        """
        Check if study has undo actions.

        Returns:
            bool: *True* if there are operations to undo; *False*
            otherwise.
        """
        return self._undo_redo.nb_undo > 0

    def hasRedo(self):
        """
        Check if study has redo actions.

        Returns:
            bool: *True* if there are operations to redo; *False*
            otherwise.
        """
        return self._undo_redo.nb_redo > 0

    def undoMessages(self):
        """
        Get available undo actions.

        Returns:
            list[str]: Operations available for undo.

        See also:
            `undo()`, `hasUndo()`, `redoMessages()`
        """
        return self._undo_redo.undo_messages

    def redoMessages(self):
        """
        Get available rendo actions.

        Returns:
            list[str]: Operations available for redo.

        See also:
            `redo()`, `hasRedo()`, `undoMessages()`
        """
        return self._undo_redo.redo_messages

    def undo(self, count=1):
        """
        Undo last operations.

        Arguments:
            count (Optional[int]): Number of operations to undo.
                Defaults to 1.

        See also:
            `redo()`, `undoMessages()`, `hasUndo()`, `commit()`
        """
        self._undo_redo.undo(count)

    def redo(self, count=1):
        """
        Redo last undone operations.

        Arguments:
            count (Optional[int]): Number of operations to redo.
                Defaults to 1.

        See also:
            `undo()`, `redoMessages()`, `hasRedo()`, `commit()`
        """
        self._undo_redo.redo(count)

    def commit(self, message):
        """
        Commit changes into the data model.

        Note:
            Commit message must be non-empty.

        Arguments:
            message (str): Commit message.

        Raises:
            RuntimeError: If commit message is empty.
        """
        if not message:
            raise RuntimeError("Empty commit message")
        self._undo_redo.commit(message)

    def revert(self):
        """
        Revert changes in the data model.
        """
        self._undo_redo.revert()

    def _checkDataFiles(self, stage):
        """
        Checks the data files. Remove unused and warn about undefined.
        """
        num = 0
        empty = []
        for unit in stage.handle2info.keys():
            info = stage.handle2info[unit]
            if not len(info):
                empty.append(unit)
            elif info.filename is None:
                num += 1

        for i in empty:
            del stage.handle2info[i]

        if num > 0:
            msg = translate("AsterStudy",
                            "There are data files with undefined file name.")
            MessageBox.warning(self._astergui.mainWindow(),
                               translate("AsterStudy", "Undefined files"),
                               msg, MessageBox.Ok,
                               noshow="undefined_files",
                               prefmgr=self.astergui().preferencesMgr())



    def loadEmbeddedFilesWrapper(self, directory, files):
        """
        Wrapper with message boxes to load embedded files.
        """
        try:
            self.history.load_embedded_files(directory, files, check=True)
        except ExistingSwapError as exc:
            ask = MessageBox.warning(parent=self.astergui().mainWindow(),
                                     buttons=MessageBox.Ok | MessageBox.Cancel,
                                     defaultButton=MessageBox.Cancel,
                                     **exc.for_messagebox())
            if ask == MessageBox.Ok:
                self.history.load_embedded_files(directory, files, check=False)
            elif ask == MessageBox.Cancel:
                raise RuntimeError("Loading operation cancelled.")
