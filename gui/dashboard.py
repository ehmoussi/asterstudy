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
Dashboard
---------

The module implements Dashboard for AsterStudy GUI.
See `Dashboard` class for mode details.

"""

from __future__ import unicode_literals

from glob import glob
from math import sqrt
import os.path as osp

from PyQt5 import Qt as Q

from common import (AsterStudyError, auto_dupl_on, debug_mode, load_icon,
                    load_pixmap, translate, wait_cursor)
from datamodel.stage import Stage
from datamodel.case import Case
from datamodel.result import RunOptions, StateOptions
from datamodel.engine import (Engine, runner_factory, serverinfos_factory,
                              version_ismpi)
from . import (Context, Entity, NodeType, check_selection, get_node_type)
from . controller import Controller
from . widgets import ElidedLabel, SearchWidget, MessageBox

__all__ = ["Dashboard"]

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name

# pragma pylint: disable=too-many-lines


class Options(object):
    """Dashboard options."""

    LinkArc = 0
    LinkLine = 1
    LinkOrtho = 2
    LinkRounded = 3
    LinkMidRounded = 4
    LinkMidArc = 5

    def __init__(self):
        """Set initial values of options."""
        # height of case item's title
        self.title_height = 50
        # margin size
        self.margin = 20
        # spacing between stage items
        self.spacing = 30
        # size of stage item
        self.stage_size = 50
        # link mode
        self.link_mode = Options.LinkMidArc
        # refresh interval
        self.refresh = (1 if Engine.Default == Engine.Simulator else 5) * 1000


class Dashboard(Q.QSplitter):
    """
    Class for dashboard presentation.
    """
    itemSelectionChanged = Q.pyqtSignal()

    _options = Options()

    class InfoType(object):
        """Enumerator for information window type."""
        Console = 0
        Log = 1

    def __init__(self, astergui, parent=None):
        """
        Constructor.
        """
        super(Dashboard, self).__init__(Q.Qt.Vertical, parent)

        self.setChildrenCollapsible(False)

        self._astergui = astergui
        self._scene = None

        self._runner = DashboardRunner(self)
        self._runner.logMessage.connect(self._logMessage)
        self._runner.logConsole.connect(self._logConsole)

        self._monitor = DashboardMonitor(self)
        self._monitor.stageChanged.connect(self._stageChanged)
        self._monitor.started.connect(self._updateState)
        self._monitor.stopped.connect(self._updateState)
        self._monitor.finished.connect(self._runFinished)
        self._monitor.completed.connect(self._caseCompleted)
        self._monitor.setWatcher(self._runner)

        top = Q.QWidget(self)
        self.addWidget(top)
        top.setSizePolicy(Q.QSizePolicy.Preferred, Q.QSizePolicy.Expanding)

        self._exec = DashboardExec(self, top)
        self._exec.setObjectName("DashboardExec")
        self._scene = DashboardScene(self, top)
        self._view = DashboardView(self._scene, top)
        self._view.setObjectName("DashboardView")

        self._exec.setDashboardView(self._view)

        base = Q.QHBoxLayout(top)
        base.setContentsMargins(0, 0, 0, 0)
        base.addWidget(self._exec)
        base.addWidget(self._view)

        if debug_mode():
            self._states = DashboardRunCasesTable(self)
            self.addWidget(self._states)

        self._info = DashboardInfo(self)
        self.addWidget(self._info)

        self._view.contextMenu.connect(self._contextMenu)
        self._exec.runClicked.connect(self._runClicked)
        self._info.stopClicked.connect(self._stopClicked)
        self._info.pauseClicked.connect(self._pauseClicked)
        self._info.resumeClicked.connect(self._resumeClicked)
        self._info.refreshClicked.connect(self._refreshClicked)
        self._info.showMsgFileClicked.connect(self._showMessageFile)

        # Note: itemSelectionChanged must be connected before _updateState in
        # order to synchronize RunCase selection in DashboardScene and
        # CasesView before update of DashboardExec availability.
        self._scene.selectionChanged.connect(self.itemSelectionChanged)
        self._scene.selectionChanged.connect(self._updateState)

        self._updateState()

    @staticmethod
    def opts():
        """Get Dashboard options."""
        return Dashboard._options

    def update(self):
        """
        Updates the dashboard contents.
        """
        history = self._astergui.study().history
        self._exec.setCase(history.current_case)
        self._scene.updateScene(history)
        if debug_mode():
            self._states.updateTable(history)

    def selected_objects(self):
        """
        Gets the currently selected objects in scene.

        Returns:
            list: List of selected objects: cases, stages.
        """
        return self._scene.selection() if self._scene is not None else []

    def selection(self):
        """
        Gets the currently selected objects.

        Returns:
            list: List of selected objects: cases, stages.
        """
        return [Entity(i.uid, get_node_type(i)) \
                    for i in self.selected_objects()]

    def setSelection(self, objs):
        """
        Sets the selection, i.e. select given objects.
        Other objects will be unselected.

        Arguments:
            objs (list): List of objects that should be selected.
        """
        self._scene.setSelection(objs)
        self._updateState()

    def clearSelection(self):
        """
        Clear the selection.
        """
        self._scene.clearSelection()
        self._updateState()

    def ensureVisible(self, obj):
        """
        Make graphics item for specified object is visible.
        """
        item = self._scene.findItem(obj)
        if item is not None:
            self._view.ensureVisible(item)

    def isRunning(self):
        """
        Gets the running state.

        Returns:
            bool: Running state.
        """
        selection = self.selected_objects()
        return self._monitor.isRunning(selection[0] \
                                           if len(selection) > 0 else None)

    def isPausing(self):
        """
        Gets the pausing state.

        Returns:
            bool: Pausing state.
        """
        selection = self.selected_objects()
        return self._monitor.isPausing(selection[0] \
                                           if len(selection) > 0 else None)

    def stageState(self, stage, case):
        """
        Gets the current state of stage.

        Arguments:
            stage (Stage): Stage being checked.
            case (Case): Reference case.

        Returns:
            int: State value.
        """
        return self._scene.stageState(stage, case) \
            if self._scene is not None else None

    def isActiveCase(self, case):
        """
        Checks the active state of given case.

        Arguments:
            Case: Case object.

        Returns:
            bool: Active state of case.
        """
        return self._astergui.study().isActiveCase(case) \
            if self._astergui.study() is not None else False

    def reRun(self):
        """
        Executes the Case with the previous parameters.
        """
        return self._exec.reRun()

    def _contextMenu(self, pos):
        """
        Emit signal to display context menu of dashboard graphics view
        at specified position.
        """
        self.customContextMenuRequested.emit(self.mapFromGlobal(pos))

    def _runClicked(self, forced=False):
        """
        Performed when 'Run' button clicked.

        Arguments:
            forced(bool): Flag to run execution without interruption for
                            execution parameters (previous ones will be used).
                            Default state is False.

        """
        result = Controller.execute('', None, self._astergui)
        if not result:
            return

        study = self._astergui.study()

        path = study.url()
        if not path:
            msg = translate("Dashboard", "You should save the "
                            "study before calculation running")
            MessageBox.warning(self._astergui.mainWindow(), "AsterStudy", msg)
            return

        path = osp.splitext(path)[0] + '_Files'
        study.history.folder = path

        dlg = DashboardRunDialog(self)
        dlg.setFolder(study.history.folder)
        last = self._lastStage()
        if last is not None:
            previous = last.result.job.asdict()
            previous_version = previous.get('version')
            if previous_version:
                dlg.setCodeAsterVersion(previous_version)

        dlg.initRunParameters()
        dlg.setFolderEnabled(study.history.folder is None or \
                                 len(study.history.folder) == 0)
        dlg.setRemoteFolderEnabled((study.history.remote_folder is None or \
                                    len(study.history.remote_folder) == 0) \
                                    and not dlg.isLocal()                  \
                                   )
        dlg.setHistoryVersion(study.history.version)

        if not forced and dlg.exec_() == Q.QDialog.Rejected:
            return

        run_params = dlg.runParameters()
        DashboardRunDialog.setCachedParams(run_params)
        if debug_mode():
            run_params['forced_states'] = self._exec.results()

        run_case = self._createRunCase()
        if run_case is not None:
            self._exec.saveSelectorStates()

            run_case.make_run_dir()
            study.history.folder = run_params['folder']
            study.commit(translate("Dashboard", "Create Run case"))

            self._astergui.autosave()


            self._monitor.appendCase(run_case)
            self._monitor.start()

            self._runner.start(run_case, run_params)

            self.update()
            self._scene.setStateProxy(self._monitor)
            self._astergui.update(autoSelect=run_case, context=Context.Cases)
        else:
            study.revert()
            self._astergui.update(autoSelect=self._astergui.study().activeCase,
                                  context=Context.Cases)

    def _stopClicked(self):
        """
        Performed when 'Stop' button clicked.
        """
        selection = self.selected_objects()
        wait_cursor(True)
        self._runner.stop(selection[0] \
                              if len(selection) > 0 else None)
        self._info.updateState()
        wait_cursor(False)

    def _pauseClicked(self):
        """
        Performed when 'Pause' button clicked.
        """
        selection = self.selected_objects()
        self._runner.pause(selection[0] \
                               if len(selection) > 0 else None)
        self._monitor.refresh()
        self._info.updateState()

    def _resumeClicked(self):
        """
        Performed when 'Resume' button clicked.
        """
        selection = self.selected_objects()
        self._runner.resume(selection[0] \
                                if len(selection) > 0 else None)
        self._monitor.refresh()
        self._info.updateState()

    def _refreshClicked(self):
        """
        Performed when 'Refresh' button clicked.
        """
        self._info.updateState()
        self._monitor.refresh()

    def _showMessageFile(self, action):
        """
        Performed when 'Show message file' button clicked.
        """
        msg_path = action.data()
        self._astergui.openFileInEditor(msg_path, "msg_file", read_only=True,
                                        popup=True)

    def _stageChanged(self, stage):
        """
        Invoked when stage state was changed
        """
        item = self._scene.findItem(stage)
        if item is not None:
            item.update()

        self._exec.updateState()
        if debug_mode() and self._astergui.study() is not None:
            self._states.updateTable(self._astergui.study().history)

    def _runFinished(self):
        self._scene.setStateProxy(None)
        self._updateState()

    def _caseCompleted(self, case):
        if self._runner.is_finished(case):
            study = self._astergui.study()
            if study is not None:
                study.commit(translate("Dashboard", "Accept Run results"))
                self._astergui.update()
        self._runner.remove(case)
        self._updateState()

    def _updateState(self):
        self._exec.updateState()
        self._info.updateState()
        if debug_mode() and self._astergui.study() is not None:
            self._states.updateTable(self._astergui.study().history)
        self._info.setVisible(len(self.selection()))
        selected = self._astergui.selected(Context.Cases)
        is_current_selected = \
            check_selection(selected, size=1, typeid=NodeType.Case) and \
            self._astergui.study().node(selected[0]) is \
            self._astergui.study().history.current_case
        self._exec.setEnabled(is_current_selected)

    def _log(self, ident, text, reset):
        if reset:
            self._info.setInformation(ident, text)
        else:
            self._info.appendInformation(ident, text)

    def _logMessage(self, logtext, reset=False):
        self._log(Dashboard.InfoType.Log, logtext, reset)

    def _logConsole(self, logtext, reset=False):
        self._log(Dashboard.InfoType.Console, logtext, reset)

    def _lastStage(self):
        stage = None
        study = self._astergui.study()
        if study is not None:
            history = study.history
            if history is not None:
                stage_range = self._exec.stageRange(RunOptions.Execute)
                stage = history.current_case[stage_range[1]]
        return stage

    def _createRunCase(self):
        run_case = None
        study = self._astergui.study()
        if study is not None:
            history = study.history
            if history is not None:
                stage_range = self._exec.stageRange(RunOptions.Execute)
                if stage_range is not None:
                    to_keep = self._exec.reusableStages()
                    run_case = history.create_run_case(stage_range,
                                                       reusable_stages=to_keep)
        return run_case

class DashboardMonitor(Q.QObject):
    """
    Class that monitor the executed case calculations
    """
    started = Q.pyqtSignal()
    stopped = Q.pyqtSignal()
    finished = Q.pyqtSignal()
    completed = Q.pyqtSignal(Case)
    stageChanged = Q.pyqtSignal(Stage)

    def __init__(self, parent=None):
        super(DashboardMonitor, self).__init__(parent)
        self._cases = []
        self._datas = {}
        self._timer = None
        self._watch = None

    def cases(self):
        """
        Gets the monitored cases list.

        Returns:
            list: List of Cases objects
        """
        return self._cases

    def setCases(self, cases):
        """
        Sets the monitored cases list.

        Arguments:
            cases (list): List of Cases objects
        """
        self._cases = cases

    def appendCase(self, case):
        """
        Append the case to monitored cases list.

        Arguments:
            case (Case): Case object.
        """
        if case is not None:
            self._cases.append(case)
            self._datas[case] = True

    def removeCase(self, case):
        """
        Remove the case from monitored cases list.

        Arguments:
            case (Case): Case object.
        """
        if case in self._cases:
            with auto_dupl_on(case):
                for stage in case.stages:
                    if stage in self._datas:
                        del self._datas[stage]
                if case in self._datas:
                    del self._datas[case]
                self._cases.remove(case)

    def isRunning(self, case=None):
        """
        Gets the running state.

        Returns:
            bool: Running state.
        """
        state = self._timer is not None
        if case is not None:
            caseStates = self._caseStates(case, False)
            state = caseStates.get(StateOptions.Running, 0) > 0 or \
                caseStates.get(StateOptions.Pausing, 0) > 0
        return state

    def isPausing(self, case=None):
        """
        Gets the pausing state.

        Returns:
            bool: Pausing state.
        """
        state = False
        if self.isRunning():
            caselist = [case] if case is not None else self._cases
            state = True
            runned = 0
            paused = 0
            for c in caselist:
                caseStates = self._caseStates(c, False)
                if caseStates.get(StateOptions.Running, 0) > 0:
                    runned += 1
                elif caseStates.get(StateOptions.Pausing, 0) > 0:
                    paused += 1
            state = paused > 0
        return state

    def start(self):
        """
        Start the monitor.
        """
        opts = Dashboard.opts()
        if not self.isRunning():
            self._timer = Q.QTimer(self)
            self._timer.setInterval(opts.refresh)
            self._timer.setSingleShot(False)
            self._timer.timeout.connect(self._checkState)
            self._timer.start()
            self._datas = {}
            for case in self._cases:
                self._datas[case] = True
            self.started.emit()

    def stop(self):
        """
        Stop the monitor.
        """
        if self.isRunning():
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None
            self.stopped.emit()

    def refresh(self):
        """
        Force check the calculation states.
        """
        self._checkState()

    def stageState(self, stage, case):
        """
        Gets the current state of stage (internal cached value).

        Returns:
            int: State value.
        """
        proxy_stage = _proxyStage(stage, case)
        if proxy_stage is not None:
            state = self._datas.get(proxy_stage)
            if state is not None:
                state = state | StateOptions.Intermediate
            return state
        return self._datas.get(stage)

    def watcher(self):
        """
        Gets the result state watcher.
        """
        return self._watch

    def setWatcher(self, watch):
        """
        Sets the result state watcher.
        """
        self._watch = watch

    def _checkState(self):
        """
        Main monitor function.
        """
        runcases = 0
        delcases = []
        for case in self._cases:
            caseStates = self._caseStates(case)
            caseexec = caseStates.get(StateOptions.Running, 0) > 0 or \
                caseStates.get(StateOptions.Pausing, 0) > 0
            if caseexec:
                runcases += 1
            else:
                if case in self._datas and self._datas[case]:
                    self.completed.emit(case)
                    delcases.append(case)
            self._datas[case] = caseexec

        for d in delcases:
            self.removeCase(d)

        if runcases == 0:
            self.finished.emit()
            self.stop()

    def _caseStates(self, case, emit=True):
        caseStates = {}
        stage_list = case.stages
        for stage in stage_list:
            state = self._checkResult(stage, stage.result, case, emit)
            if state not in caseStates:
                caseStates[state] = 0
            caseStates[state] += 1
        return caseStates

    def _checkResult(self, stage, result, case, emit):
        """
        Check the state of the given result.

        Arguments:
             result (Result): Result object for state checking

        Returns:
            int: Current state of result execution
        """
        state = StateOptions.Waiting
        if stage is not None and result is not None:
            resstate = None
            if self.watcher() is not None:
                resstate = self.watcher().stageState(stage, case)
                if resstate is not None:
                    state = resstate
                else:
                    proxy_stage = _proxyStage(stage, case)
                    state = proxy_stage.state | StateOptions.Intermediate \
                        if proxy_stage is not None else result.state
        changed = stage not in self._datas or self._datas[stage] != state
        self._datas[stage] = state
        if changed and emit:
            self.stageChanged.emit(stage)
        return state

class DashboardRunner(Q.QObject):
    """
    Class that process calculation run and simulates the execution process.
    """
    logMessage = Q.pyqtSignal(str)
    logConsole = Q.pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super(DashboardRunner, self).__init__(parent)
        self._caserun = {}

    def log(self, *args):
        """Log a message."""
        self.logMessage.emit(*args)

    def console(self, text, reset=False):
        """Log a message to the console."""
        self.logConsole.emit(text, reset)

    def start(self, case, params):
        """
        Starts the case calculation process for given case.

        Arguments:
            case (Case): Calculated run case.
            params (dict): Parameters for calculation running.
        """
        self._caserun[case] = runner_factory(case=case, logger=self.log,
                                             console=self.console)
        wait_cursor(True)
        try:
            self._caserun[case].start(params)
        except AsterStudyError as exc:
            # do not wait next refresh to mark job as stopped
            self._caserun[case].stop()
            MessageBox.critical(parent=None, **exc.for_messagebox())
        except Exception as exc: # pragma pylint: disable=broad-except
            import traceback
            import sys
            sys.stderr.write("ERROR during submission - traceback:\n")
            traceback.print_exc()
            raise
        finally:
            wait_cursor(False)

    def stop(self, case=None):
        """
        Stops the case calculation process.
        """
        cases = self._cases(case)
        for c in cases:
            caserun = self._caserun.get(c)
            if caserun is not None:
                caserun.stop()

    def pause(self, case=None):
        """
        Pause running
        """
        cases = self._cases(case)
        for c in cases:
            caserun = self._caserun.get(c)
            if caserun is not None:
                caserun.pause()

    def resume(self, case=None):
        """
        Resume running
        """
        cases = self._cases(case)
        for c in cases:
            caserun = self._caserun.get(c)
            if caserun is not None:
                caserun.resume()

    def remove(self, case):
        """
        Remove case from runner.

        Arguments:
            case (Case): Case object.
        """
        if case in self._caserun:
            self._caserun[case].cleanup()
            del self._caserun[case]

    def is_finished(self, case):
        """Tell if the case is finished."""
        if case in self._caserun:
            return self._caserun[case].is_finished()
        return True

    def stageState(self, stage, case):
        """
        Gets the current state of result
        """
        state = None
        proxy_state = 0
        if stage is not None:
            proxy_stage = _proxyStage(stage, case)
            if proxy_stage is not None:
                proxy_state = StateOptions.Intermediate
                stage = proxy_stage
            case = stage.parent_case
            caserun = self._caserun.get(case)
            if caserun is not None:
                state = caserun.result_state(stage.result) | proxy_state
        return state

    def _cases(self, case=None):
        return [i for i in self._caserun] if case is None else [case]


class DashboardExec(Q.QWidget):
    """
    Class represents panel for execution stage selection
    """
    runClicked = Q.pyqtSignal(bool)

    class CaseLabel(ElidedLabel):
        """
        Label control for current case title
        """
        def __init__(self, parent=None):
            super(DashboardExec.CaseLabel, self).__init__('', parent)
            self._view = None

        def dashboardView(self):
            """
            Gets the dashboard graphics view assigned to label.

            Returns:
                DashboardView: Assigned dashboard view.
            """
            return self._view

        def setDashboardView(self, view):
            """
            Sets the dashboard graphics view assigned to label.

            Arguments:
                view (DashboardView): Assigned dashboard view.
            """
            self._view = view

        def sizeHint(self):
            """
            Returns size hint increased for case titile height in
            dashboard graphics view.

            Returns:
                QSize: size hint.
            """
            sz = super(DashboardExec.CaseLabel, self).sizeHint()
            if self._view is not None:
                sz.setHeight(self._view.caseTitleHeight())
            return sz

        def minimumSizeHint(self):
            """
            Returns minimum size hint increased for case titile height in
            dashboard graphics view.

            Returns:
                QSize: size hint.
            """
            sz = super(DashboardExec.CaseLabel, self).minimumSizeHint()
            if self._view is not None:
                sz.setHeight(self._view.caseTitleHeight())
            return sz

    class StageLabel(ElidedLabel):
        """
        Elided label for stage name in selector with limited width
        """
        def __init__(self, text, parent=None):
            super(DashboardExec.StageLabel, self).__init__(text, parent)

        def sizeHint(self):
            """
            Returns size hint with width limited by 150 px.

            Returns:
                QSize: size hint.
            """
            sz = super(DashboardExec.StageLabel, self).sizeHint().\
                boundedTo(Q.QSize(150, self.maximumHeight()))
            return sz

        def minimumSizeHint(self):
            """
            Returns minimum size hint with width limited by 150 px.

            Returns:
                QSize: size hint.
            """
            sz = super(DashboardExec.StageLabel, self).minimumSizeHint().\
                boundedTo(Q.QSize(150, self.maximumHeight()))
            return sz


    class Selector(Q.QWidget):
        """
        Labeled control that allow to select one of the three state
        """
        stateChanged = Q.pyqtSignal(int)
        reusableChecked = Q.pyqtSignal()

        def __init__(self, stage, parent=None):
            """
            Constructor.
            """
            super(DashboardExec.Selector, self).__init__(parent)
            self._stage = stage
            self._state = RunOptions.Skip
            self._reuse = True
            self._view = None

            base = Q.QHBoxLayout(self)
            base.setContentsMargins(0, 0, 0, 0)
            self._button = Q.QToolButton(self)
            base.addWidget(self._button)
            self._label = DashboardExec.StageLabel(stage.name, self)
            self._label.setToolTip(stage.name)
            base.addWidget(self._label, 1)

            self._reusable = Q.QCheckBox(translate("Dashboard", "Reusable"),
                                         self)
            self._reusable.setObjectName('reusable_' + stage.name)
            self._reusable.stateChanged.connect(self.reusableChecked)
            base.addWidget(self._reusable)

            self._result = Q.QCheckBox(self) if debug_mode() else None
            if self._result is not None:
                self._result.setObjectName('expected_result')
                self._result.setChecked(True)
                base.addWidget(self._result)

            self._button.clicked.connect(self._clicked)
            self._updateButton()

        def setDashboardView(self, view):
            """
            Sets the dashboard graphics view assigned to control.

            Arguments:
                view (DashboardView): Assigned dashboard view.
            """
            self._view = view

        def sizeHint(self):
            """
            Returns size hint increased for stage height in
            dashboard graphics view.

            Returns:
                QSize: size hint.
            """
            sz = super(DashboardExec.Selector, self).sizeHint()
            if self._view is not None:
                sz.setHeight(self._view.stageHeight())
            return sz

        def minimumSizeHint(self):
            """
            Returns minimum size hint increased for stage height in
            dashboard graphics view.

            Returns:
                QSize: size hint.
            """
            sz = super(DashboardExec.Selector, self).minimumSizeHint()
            if self._view is not None:
                sz.setHeight(self._view.stageHeight())
            return sz

        def stage(self):
            """
            Gets the stage object associated with selector.

            Returns:
                Stage: stage object.
            """
            return self._stage

        def setStage(self, stage):
            """
            Sets the stage object associated with selector.

            Arguments:
                stage (Stage): Stage object.
            """
            self._stage = stage

        def state(self):
            """
            Gets the current state.

            Returns:
                int: Stage run state.
            """
            return self._state

        def setState(self, state):
            """
            Sets the current stage run state.

            Arguments:
                state (int): Stage run state.
            """
            if self._state != state:
                self._state = state
                self._updateButton()
                self.stateChanged.emit(state)

        def isReusable(self):
            """
            Get 'reusable' state.

            Returns:
                bool: *True* if stage is configured to keep results;
                *False* otherwise.
            """
            return self.state() == RunOptions.Execute and \
                self._reusable.isChecked()

        def setReusable(self, on):
            """
            Set 'reusable' state.

            Arguments:
                on (bool): 'reusable' flag state.
            """
            self._reusable.setChecked(on)

        def incrementState(self):
            """
            Switch the current run state to the next possible value.
            """
            self._changeState(1)

        def decrementState(self):
            """
            Switch the current run state to the previous possible value.
            """
            self._changeState(-1)

        def isReuseEnabled(self):
            """
            Gets the possibility of 'Reuse' state using

            Returns:
                bool: The enable state.
            """
            return self._reuse

        def setReuseEnabled(self, on):
            """
            Sets the possibility of 'Reuse' state using

            Arguments:
                on (bool): The enable state.
            """
            self._reuse = on
            if not self._reuse and \
                    self.state() == RunOptions.Reuse:
                self.setState(RunOptions.Execute)

        def result(self):
            """
            Gets the required result state.

            Returns:
                bool: Result state.
            """
            return self._result.isChecked() \
                if self._result is not None else False

        def setResult(self, on):
            """
            Sets the required result state.

            Returns:
                on (bool): Result state.
            """
            if self._result is not None:
                self._result.setChecked(on)

        def update(self):
            """
            Updates the stage name.
            """
            super(DashboardExec.Selector, self).update()
            self._label.setText(self.stage().name)
            self._label.setToolTip(self.stage().name)
            self._updateButton()

        def _clicked(self):
            """
            Invoked when state tool button clicked.
            Switch the current stage run state to next value.
            """
            self._changeState(1)

        def _changeState(self, delta):
            """
            Switch the current stage run state to next or previous value.

            Arguments:
                delta (int): Positive or negative delta for state changing.
            """
            state = self.state() + delta
            if not self.isReuseEnabled() and \
                    state == RunOptions.Reuse:
                state = state + delta
            if state > RunOptions.Execute:
                state = RunOptions.Skip
            if state != self.state():
                self.setState(state)

        def _updateButton(self):
            """
            Updates the tool button icon according
            to the current stage run state.
            """
            state = self.state()
            ico = None
            if state == RunOptions.Skip:
                ico = load_icon("as_pic_run_skip.png")
            elif state == RunOptions.Execute:
                ico = load_icon("as_pic_run_execute.png")
            elif state == RunOptions.Reuse:
                ico = load_icon("as_pic_run_reuse.png")
            self._button.setIcon(ico)
            self._button.setObjectName(self.stage().name + ':' + str(state))
            self._reusable.setEnabled(state == RunOptions.Execute)
            self._reusable.setObjectName('reusable_' + self.stage().name)


    class Spacer(Q.QWidget):
        """
        Used for spacing in layout.
        """
        def __init__(self, view, parent=None):
            super(DashboardExec.Spacer, self).__init__(parent)
            self._view = view

        def sizeHint(self):
            """
            Returns size hint increased for stage space height in
            dashboard graphics view.

            Returns:
                QSize: size hint.
            """
            sz = super(DashboardExec.Spacer, self).sizeHint()
            if self._view is not None:
                sz.setHeight(self._view.spacerHeight())
            return sz

        def minimumSizeHint(self):
            """
            Returns minimum size hint increased for stage space height in
            dashboard graphics view.

            Returns:
                QSize: size hint.
            """
            sz = super(DashboardExec.Spacer, self).minimumSizeHint()
            if self._view is not None:
                sz.setHeight(self._view.spacerHeight())
            return sz


    class ScrollArea(Q.QScrollArea):
        """
        Scroll area with size hints wrappped contained widget.
        """
        def __init__(self, parent=None):
            super(DashboardExec.ScrollArea, self).__init__(parent)
            self.setFrameStyle(self.Panel | self.Sunken)

        def sizeHint(self):
            """
            Reimplemented for wrapping size hint of scrolled widget.

            Returns:
                QSize: Size object with minimum size hint.
            """
            sz = super(DashboardExec.ScrollArea, self).sizeHint()
            if self.widget():
                sz.setWidth(self.widget().sizeHint().width() + \
                                self.contentsMargins().left() + \
                                self.contentsMargins().right() + \
                                (self.verticalScrollBar().sizeHint().width() \
                                     if self.verticalScrollBar().\
                                     isVisibleTo(self) else 0))
            return sz

        def minimumSizeHint(self):
            """
            Reimplemented for wrapping minimum size hint of scrolled widget.

            Returns:
                QSize: Size object with minimum size hint.
            """
            sz = super(DashboardExec.ScrollArea, self).minimumSizeHint()
            if self.widget():
                sz.setWidth(self.widget().minimumSizeHint().width() + \
                                self.contentsMargins().left() + \
                                self.contentsMargins().right() + \
                                (self.verticalScrollBar().\
                                     minimumSizeHint().width() \
                                     if self.verticalScrollBar().\
                                     isVisibleTo(self) else 0))
            return sz

        def setVisible(self, vis):
            """
            Reimplemented for internal reason.
            Schedule the first step of delayed layout update.
            """
            super(DashboardExec.ScrollArea, self).setVisible(vis)
            if vis:
                Q.QApplication.postEvent(self, Q.QEvent(Q.QEvent.User))

        def customEvent(self, event):
            """
            Reimplemented for internal reason.
            Schedule the second step of delayed layout update.
            """
            super(DashboardExec.ScrollArea, self).customEvent(event)
            Q.QTimer.singleShot(0, self._onTimeout)

        def _onTimeout(self):
            """
            Performs the delayed layout update.
            """
            self.widget().updateGeometry()
            self.updateGeometry()


    def __init__(self, dashboard, parent=None):
        super(DashboardExec, self).__init__(parent)
        self._dashboard = dashboard
        self._caseObject = None
        self._selectors = []
        self._lastRunStates = {}
        self._base = Q.QVBoxLayout(Q.QWidget(self))
        self._base.setSpacing(0)
        self._base.setContentsMargins(5, 0, 5, 0)

        self._case = DashboardExec.CaseLabel(self)
        self._case.setAlignment(Q.Qt.AlignCenter)

        self._scroll = DashboardExec.ScrollArea(self)
        self._scroll.setHorizontalScrollBarPolicy(Q.Qt.ScrollBarAlwaysOff)
        self._scroll.setWidgetResizable(True)
        self._scroll.setSizePolicy(Q.QSizePolicy.Minimum,
                                   Q.QSizePolicy.Expanding)
        self._scroll.setWidget(self._base.parentWidget())

        layout = Q.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._run = Q.QPushButton(translate("Dashboard", "Run"), self)
        self._run.setIcon(load_icon("as_pic_run.png"))
        self._run.setObjectName("Run")

        self._run.clicked.connect(self.runClicked)

        layout.addSpacing(4)
        layout.addWidget(self._case)
        layout.addWidget(self._scroll)
        layout.addSpacing(5)
        layout.addWidget(self._run, 0, Q.Qt.AlignCenter)

        self.updateState()

    def saveSelectorStates(self):
        """
        Saves selectors state.
        """
        self._lastRunStates = []
        for sel in self._selectors:
            self._lastRunStates.append((sel.state(), sel.isReusable()))

    def restoreSelectorStates(self):
        """
        Restores selectors state.
        """
        res = len(self._lastRunStates) == len(self._selectors)
        for i, sel in enumerate(self._selectors):
            if i < len(self._lastRunStates):
                state, reusable = self._lastRunStates[i]
                if state == RunOptions.Reuse:
                    if not self._canReUse(sel.stage()):
                        res = False
                        break # keep Skip state
                block = sel.signalsBlocked()
                sel.blockSignals(True)
                sel.setState(state)
                sel.setReusable(reusable)
                sel.blockSignals(block)
            else:
                res = False
        return res

    def minimumSizeHint(self):
        """
        Reimplemented for expanding minimum size hint.

        Returns:
            QSize: Size object with minimum size hint.
        """
        sz = super(DashboardExec, self).minimumSizeHint()
        return sz.expandedTo(Q.QSize(100, 0)) + \
            Q.QSize(self._scroll.verticalScrollBar().sizeHint().width(), 0)

    def dashboard(self):
        """
        Gets the Dashboard parent object.

        Returns:
            Dashboard: Dashboard object.
        """
        dshbrd = None
        parent = self.parentWidget()
        while parent is not None and dshbrd is None:
            if isinstance(parent, Dashboard):
                dshbrd = parent
            parent = parent.parentWidget()
        return dshbrd

    def setDashboardView(self, view):
        """
        Sets the dashboard graphics view assigned to exec controls.

        Arguments:
        view (DashboardView): Assigned dashboard view.
        """
        self._case.setDashboardView(view)
        for i in self._selectors:
            i.setDashboardView(view)

    def caseName(self):
        """
        Gets the current case name.

        Returns:
            str: Case name.
        """
        return self._case.text()

    def setCaseName(self, name):
        """
        Sets the current case name.

        Arguments:
            name (str): Case name.
        """
        return self._case.setText(name)

    def stages(self, runtype=None):
        """
        Gets the stage list with given running type.

        Arguments:
            runtype (int): Stage run type. If it parameter is ommited (None)
                           then all stages will be returned.

        Returns:
            list: Returns the list of the Stage objects.
        """
        reslist = []
        for i in self._selectors:
            if runtype is None or i.state() == runtype:
                reslist.append(i.stage())
        return reslist

    def stageRange(self, runtype=None):
        """
        Gets the list with two indexes 'from' and 'to' for stages sub list
        with given running type.

        Arguments:
            runtype (int): Stage run type. If it parameter is ommited (None)
                           then all stages will be returned.

        Returns:
            list: Returns the list with two indexes.
        """
        index = -1
        length = 0
        for idx in xrange(len(self._selectors)):
            selector = self._selectors[idx]
            if runtype is None or selector.state() == runtype:
                if index < 0:
                    index = idx
                else:
                    length += 1
            elif index >= 0:
                break

        return [index, index + length] if index >= 0 else None

    def reusableStages(self):
        """
        Get stages which are marked as reusable for execution.

        Returns:
            list[int]: Indices of stages for which results should be
            kept.
        """
        return [idx for idx, selector in enumerate(self._selectors)\
                if selector.isReusable()]

    def results(self):
        """
        Gets the required results for stages.

        Returns:
            dict: Dictionary with stage as keys and bool result state as value.
        """
        res = {}
        for i in self._selectors:
            res[i.stage()] = i.result()
        return res

    def setCase(self, case):
        """
        Sets the stages list into the panel

        Arguments:
            stages (list): List with objects of the Stage class.
        """
        self._caseObject = case
        self.setCaseName(case.name)
        stages = case.stages
        selectors = {}
        # Remove all entries in layout
        while self._base.count() > 0:
            wid = self._base.itemAt(0).widget()
            if wid is not None:
                if hasattr(wid, 'stage'):
                    selectors[wid.stage().uid] = wid
                else:
                    wid.deleteLater()
            self._base.removeItem(self._base.itemAt(0))

        self._selectors = []
        # Create new widgets and place them into layout
        hasnew = False
        view = self._case.dashboardView()
        for i in xrange(len(stages)):
            stage = stages[i]
            entry = None
            if stage.uid in selectors:
                entry = selectors[stage.uid]
                selectors[stage.uid] = None
                entry.setStage(stage)
                entry.update()
            else:
                hasnew = True
                entry = DashboardExec.Selector(stage, self)
                entry.setDashboardView(view)
                entry.stateChanged.connect(self._stateChanged)
                entry.reusableChecked.connect(self.updateRunButton)
            self._base.addWidget(entry)
            if i < len(stages) - 1:
                self._base.addWidget(DashboardExec.Spacer(view, self))
            self._selectors.append(entry)

        for s in selectors:
            if selectors[s] is not None:
                selectors[s].deleteLater()

        if hasnew:
            for i in self._selectors:
                i.setState(RunOptions.Skip)

        self._base.addStretch(1)
        self._scroll.updateGeometry()
        self.updateState()

    def updateRunButton(self):
        """
        Updates state of Run button.
        """
        self._run.setEnabled(self._canBeRan())

    def updateState(self):
        """
        Updates the state of controls.
        """
        last_executed = None
        for selector in self._selectors:
            stage = selector.stage()
            canreuse = self._canReUse(stage)
            selector.setReuseEnabled(canreuse)
            selector.setReusable(False)
            if selector.state() == RunOptions.Execute:
                last_executed = selector
        if last_executed is not None:
            last_executed.setReusable(True)

        self.updateRunButton()

    def reRun(self):
        """
        Restores previous parameters of executor and run the case.
        """
        res = self.restoreSelectorStates()
        runnable = self._canBeRan()
        if res and runnable:
            self.runClicked.emit(False)
        else:
            self._run.setEnabled(runnable)

    def _selector(self, stage):
        """Get selector for given *stage*."""
        for selector in self._selectors:
            if selector.stage() is stage:
                return selector
        return None

    def _canBeRan(self):
        """Tells whether current case can be ran."""
        if len(self.stages(RunOptions.Execute)) > 0:
            if len(self.reusableStages()) > 0:
                exec_stages = self.stageRange(RunOptions.Execute)
                if exec_stages:
                    last_exec_stage_idx = exec_stages[-1]
                    if self._selectors[last_exec_stage_idx].isReusable():
                        return True
        return False

    # pragma pylint: disable=no-self-use
    def _canReUse(self, stage):
        """
        Returns result reuse possibility for specified stage.

        Arguments:
            stage (Stage): Stage object.
        """
        proxy_stage = _proxyStage(stage, self._caseObject)
        if proxy_stage is not None:
            stage = proxy_stage
        return stage.parent_case.can_reuse(stage)

    def _stateChanged(self, state):
        """
        Invoked when stage state is changed.
        """
        entry = self.sender()
        if entry in self._selectors:
            index = self._selectors.index(entry)
            if state in (RunOptions.Execute, RunOptions.Reuse):
                for i in xrange(index):
                    if state == RunOptions.Reuse:
                        self._selectors[i].setState(state)
                    elif self._selectors[i].state() == RunOptions.Skip:
                        self._selectors[i].incrementState()
                proxy_stage = _proxyStage(entry.stage(), self._caseObject)
                for i in xrange(index + 1, len(self._selectors)):
                    if state == RunOptions.Reuse and proxy_stage is not None:
                        self._selectors[i].setState(state)
                        if self._selectors[i].stage() is proxy_stage:
                            break

            if state == RunOptions.Execute:
                for i in xrange(index + 1, len(self._selectors)):
                    if self._selectors[i].state() != RunOptions.Skip:
                        self._selectors[i].setState(state)

            if state == RunOptions.Skip:
                for i in xrange(index + 1, len(self._selectors)):
                    self._selectors[i].setState(state)
        self.updateState()


class DashboardRunDialog(Q.QDialog):
    """
    Dialog with run parameters.
    """
    class PathEdit(Q.QWidget):
        """
        Class that represents the input path field with browse button.
        """
        pathChanged = Q.pyqtSignal(str)

        def __init__(self, parent=None):
            super(DashboardRunDialog.PathEdit, self).__init__(parent)
            self._path = Q.QLineEdit(self)
            self._path.setObjectName('DashboardRunDialog.path')
            self._path.setCompleter(Q.QCompleter(Q.QDirModel(self._path),
                                                 self._path))
            self._path.textChanged.connect(self.pathChanged)

            self._browse = Q.QToolButton(self)
            self._browse.setText("...")
            self._browse.clicked.connect(self._browseClicked)

            base = Q.QHBoxLayout(self)
            base.setContentsMargins(0, 0, 0, 0)
            base.addWidget(self._path)
            base.addWidget(self._browse)

        def path(self):
            """
            Gets the current path

            Returns:
                str: Path string
            """
            return self._path.text()

        def setPath(self, value):
            """
            Sets the current path

            Arguments:
                value (str): Path string
            """
            self._path.setText(value)

        def _browseClicked(self):
            """
            Invoked when 'Browse' button clicked.
            """
            path = self.path()
            caption = translate("Dashboard", "Directory")
            sel_path = Q.QFileDialog.getExistingDirectory(self, caption, path)
            if sel_path:
                self.setPath(sel_path)

    class RemotePathEdit(PathEdit):
        """
        Input path field with browse button and checkbox.
        """
        remoteStateChanged = Q.pyqtSignal(bool)

        def __init__(self, parent=None):
            """
            Calls parent initializer and inserts the checkbox.
            """
            super(DashboardRunDialog.RemotePathEdit, self).__init__(parent)

            self._checkbox = Q.QCheckBox(self)
            self._checkbox.stateChanged.connect(self._checkboxStateChanged)

            base = self.layout()
            base.insertWidget(0, self._checkbox)

            # Waiting for a portable option to browse remote files,
            # Hide the browse button
            base.removeWidget(self._browse)
            self._browse.hide()

            self._checkbox.stateChanged.emit(self._checkbox.checkState())

        def state(self):
            """
            State of the checkbox.
            """
            return True if self._checkbox.checkState() == Q.Qt.Checked \
                   else False

        def _checkboxStateChanged(self, state):
            """
            Called when checkbox is ticked or unticked.

            Note:
                Ticking enables text edit and browsing.
                Wrapper that emits `remoteStateChanged`.
            """
            bool_state = True if state == Q.Qt.Checked else False

            self._path.setEnabled(bool_state)

            self.remoteStateChanged.emit(bool_state)

    # keep in memory last parameters used per session
    # stored at runParameters getter call
    _last_seq_params = {'memory': 1024, 'time': '00:15:00',
                        'version': 'stable',
                        'server': 'localhost',
                        'mpicpu' : 1, 'threads': 0, 'nodes': 1,
                        'description': ''}
    _last_mpi_params = _last_seq_params.copy()

    @classmethod
    def getCachedParams(cls, instance):
        """Return the dict used for this kind of version.

        Arguments:
            instance (*DashboardRunDialog*): Current instance.

        Return:
            dict: Dict that store the last parameters used.
        """
        ismpi = version_ismpi(instance.codeAsterVersion())
        return cls._last_mpi_params if ismpi else cls._last_seq_params

    @classmethod
    def setCachedParams(cls, params):
        """Register the dict used for this kind of version.

        Arguments:
            params (dict): Dict of the last parameters used.
        """
        if version_ismpi(params.get('version', '')):
            cls._last_mpi_params = params
        else:
            cls._last_seq_params = params

    def __init__(self, parent=None):
        super(DashboardRunDialog, self).__init__(parent)

        base = Q.QVBoxLayout(self)
        base.setContentsMargins(5, 5, 5, 5)

        tab_widget = Q.QTabWidget(self)
        base.addWidget(tab_widget)

        basic_tab = Q.QWidget(self)
        basic_grid = Q.QGridLayout(basic_tab)
        advan_tab = Q.QWidget(self)
        advan_grid = Q.QGridLayout(advan_tab)

        # interface to server informations
        self._infos = serverinfos_factory()

        # Memory
        self._memory = Q.QLineEdit(self)
        self._memory.setValidator(Q.QIntValidator(self._memory))
        self._memory.validator().setBottom(0)
        self._addWidget(basic_grid,
                        translate("Dashboard", "Memory"), self._memory)

        # Time
        self._time = Q.QTimeEdit(self)
        self._time.setDisplayFormat('hh:mm:ss')
        self._addWidget(basic_grid,
                        translate("Dashboard", "Time"), self._time)

        # Server
        self._server = Q.QComboBox(self)
        self._server.addItems(self._infos.available_servers)
        self._addWidget(basic_grid,
                        translate("Dashboard", "Run servers"), self._server)

        # code_aster version
        self._history_version = None
        self._version = Q.QComboBox(self)
        self._addWidget(advan_grid,
                        translate("Dashboard",
                                  "Version of code_aster"), self._version)

        # Run mode
        self._mode = Q.QComboBox(self)
        self._addWidget(advan_grid,
                        translate("Dashboard", "Run mode"), self._mode)

        # MPI CPU
        self._mpicpu = Q.QLineEdit(self)
        self._mpicpu.setValidator(Q.QIntValidator(1, 8192, self._mpicpu))
        self._addWidget(advan_grid,
                        translate("Dashboard",
                                  "Number of MPI CPU"), self._mpicpu)

        # Number of nodes
        self._nodes = Q.QLineEdit(self)
        self._nodes.setValidator(Q.QIntValidator(1, 8192, self._nodes))
        self._addWidget(advan_grid,
                        translate("Dashboard",
                                  "Number of MPI nodes"), self._nodes)

        # Number of threads
        self._threads = Q.QLineEdit(self)
        self._threads.setValidator(Q.QIntValidator(0, 8192, self._threads))
        self._addWidget(advan_grid,
                        translate("Dashboard",
                                  "Number of threads"), self._threads)

        # User description
        self._descr = Q.QTextEdit(self)
        self._addWidget(basic_grid,
                        translate("Dashboard",
                                  "User description"), self._descr)

        # History folder
        self._folder = DashboardRunDialog.PathEdit(self)
        self._addWidget(basic_grid,
                        translate("Dashboard",
                                  "History folder"), self._folder)
        self._folder.pathChanged.connect(self._updateState)

        # Remote folder (where to store result databases)
        self._remote_folder = DashboardRunDialog.RemotePathEdit(self)
        self._addWidget(basic_grid,
                        translate("Dashboard",
                                  "Remote databases"), self._remote_folder)
        self._remote_folder.remoteStateChanged.connect(self._updateState)
        self._remote_folder.pathChanged.connect(self._updateState)

        #---------------------------------------------------------------------
        tab_widget.addTab(basic_tab, translate("Dashboard", "Basic"))
        tab_widget.addTab(advan_tab, translate("Dashboard", "Advanced"))

        #---------------------------------------------------------------------
        self._btnbox = Q.QDialogButtonBox(Q.QDialogButtonBox.Ok |
                                          Q.QDialogButtonBox.Cancel,
                                          Q.Qt.Horizontal, self)
        self._btnbox.button(Q.QDialogButtonBox.Ok).\
            setText(translate("Dashboard", "Run"))
        self._btnbox.button(Q.QDialogButtonBox.Ok).\
            setObjectName('DashboardRunDialog.run')
        self._btnbox.accepted.connect(self.accept)
        self._btnbox.rejected.connect(self.reject)
        base.addWidget(self._btnbox)

        basic_grid.setRowStretch(basic_grid.rowCount(), 1)
        advan_grid.setRowStretch(advan_grid.rowCount(), 1)

        #---------------------------------------------------------------------
        self._server.activated.connect(self._serverActivated)
        self._version.activated.connect(self._versionActivated)
        self._mpicpu.textEdited.connect(self._mpicpuEdited)
        self._nodes.textEdited.connect(self._nodesEdited)

        self._serverActivated()
        self._versionActivated()
        self._updateState()

        self.setModal(True)
        self.setWindowTitle(translate("Dashboard", "Run..."))

    def memory(self):
        """
        Gets the memory quantity.

        Returns:
            int: Memory quantity.
        """
        val = self._memory.text()
        return int(val) if len(val) > 0 else 0

    def setMemory(self, mem):
        """
        Sets the memory quantity.

        Arguments:
            mem (int): Memory quantity.
        """
        self._memory.setText(str(mem))

    def time(self):
        """
        Gets the running time.

        Returns:
            str: Running time.
        """
        return self._time.time().toString('hh:mm:ss')

    def setTime(self, timeval):
        """
        Sets the running time.

        Arguments:
            timeval (str): Running time.
        """
        self._time.setTime(Q.QTime.fromString(timeval, 'hh:mm:ss'))

    def server(self):
        """
        Gets the currently selected run server.

        Returns:
            str: Run server name.
        """
        return self._server.currentText()

    def setServer(self, serv):
        """
        Sets the current run server.

        Arguments:
            serv (str): Run server name.
        """
        self._server.setCurrentIndex(self._server.findText(serv))
        self._serverActivated()

    def codeAsterVersion(self):
        """
        Gets the current code_aster version.

        Returns:
            str: code_aster version.
        """
        return self._version.currentText()

    def setCodeAsterVersion(self, ver):
        """
        Sets the current code_aster version.

        Arguments:
            ver (str): code_aster version.
        """
        idx = self._version.findText(ver)
        if idx >= 0:
            self._version.setCurrentIndex(idx)
        self._versionActivated()

    def mode(self):
        """
        Gets the running mode.

        Returns:
            int: Running mode.
        """
        return self._mode.currentText()

    def setMode(self, mode):
        """
        Sets the running mode.

        Arguments:
            mode (int): Running mode.
        """
        self._mode.setCurrentIndex(self._mode.findText(mode))

    def mpiCpu(self):
        """
        Gets the number of MPI CPU's.

        Returns:
            int: number of MPI CPU's.
        """
        val = self._mpicpu.text()
        return int(val) if len(val) > 0 else 0

    def setMpiCpu(self, cpu):
        """
        Sets the number of MPI CPU's.

        Arguments:
            cpu (int): Number of MPI CPU's.
        """
        self._mpicpu.setText(str(cpu))

    def threads(self):
        """
        Gets the number of threads.

        Returns:
            int: number of threads.
        """
        val = self._threads.text()
        return int(val) if len(val) > 0 else 0

    def setThreads(self, num):
        """
        Sets the number of threads.

        Arguments:
            num (int): Number of threads.
        """
        self._threads.setText(str(num))

    def nodes(self):
        """
        Gets the number of nodes.

        Returns:
            int: number of nodes.
        """
        val = self._nodes.text()
        return int(val) if len(val) > 0 else 0

    def setNodes(self, num):
        """
        Sets the number of nodes.

        Arguments:
            num (int): Number of nodes.
        """
        self._nodes.setText(str(num))

    def userDescription(self):
        """
        Gets the user description.

        Returns:
            str: User description text.
        """
        return self._descr.toPlainText()

    def setUserDescription(self, txt):
        """
        Sets the user description.

        Arguments:
            txt (str): User description text.
        """
        self._descr.setPlainText(txt)

    def folder(self):
        """
        Gets the history folder.

        Returns:
            str: Folder path string
        """
        return self._folder.path()

    def setFolder(self, path):
        """
        Sets the history folder.

        Arguments:
            path (str): Folder path string
        """
        self._folder.setPath(path)

    def remoteFolder(self):
        """
        Gets the history folder.

        Returns:
            str: Folder path string
        """
        return self._remote_folder.path()

    def setRemoteFolder(self, path):
        """
        Sets the history folder.

        Arguments:
            path (str): Folder path string
        """
        self._remote_folder.setPath(path)

    def isFolderEnabled(self):
        """
        Gets the history folder enabled state.

        Returns:
            bool: Enabled state
        """
        return self._folder.isEnabled()

    def setFolderEnabled(self, on):
        """
        Sets the history folder enabled state.

        Arguments:
            on (bool): Enabled state
        """
        return self._folder.setEnabled(on)

    def setRemoteFolderEnabled(self, on):
        """
        Sets the history folder enabled state.

        Arguments:
            on (bool): Enabled state
        """
        return self._remote_folder.setEnabled(on)

    def setHistoryVersion(self, version):
        """Sets the version name used in history."""
        self._history_version = version

    def runParameters(self):
        """
        Gets all run dialog parameters.
        Do not export MPI parameters for a sequential version.

        Returns:
            dict: Dictionary with all parameters.
        """
        params = {'memory': self.memory(), 'time': self.time(),
                  'server': self.server(), 'version': self.codeAsterVersion(),
                  'mode': self.mode(), 'threads': self.threads(),
                  'description': self.userDescription(),
                  'folder': self.folder(),
                  'remote_folder':self.remoteFolder()}
        if version_ismpi(self.codeAsterVersion()):
            params.update({'mpicpu' : self.mpiCpu(), 'nodes': self.nodes()})
        return params

    def initRunParameters(self):
        """
        Sets default run dialog parameters.

        Arguments:
            params (dict): Dictionary with run parameters.
        """
        params = DashboardRunDialog.getCachedParams(self)

        if 'memory' in params:
            self.setMemory(params['memory'])
        if 'time' in params:
            self.setTime(params['time'])
        if 'server' in params:
            self.setServer(params['server'])
        if 'version' in params:
            self.setCodeAsterVersion(params['version'])
        if 'mode' in params:
            self.setMode(params['mode'])
        if 'mpicpu' in params:
            self.setMpiCpu(params['mpicpu'])
        if 'threads' in params:
            self.setThreads(params['threads'])
        if 'nodes' in params:
            self.setNodes(params['nodes'])
        if 'description' in params:
            self.setUserDescription(params['description'])
        if 'folder' in params:
            self.setFolder(params['folder'])
        if 'remote_folder' in params:
            self.setRemoteFolder(params['remote_folder'])

    def isLocal(self):
        """
        Returns *True* if the selected server is the local machine.
        """
        return self.server() == "localhost"

    def _serverActivated(self):
        """
        Updates the code aster versions list dependant from current server.
        """
        wait_cursor(True)
        self._infos.refresh_once(self.server())
        wait_cursor(False)
        self._version.clear()
        versions = self._infos.server_versions(self.server())
        self._version.addItems(versions)
        if self._history_version in versions:
            self.setCodeAsterVersion(self._history_version)
        self._mode.clear()
        self._mode.addItems(self._infos.server_modes(self.server()))
        self.setRemoteFolderEnabled(not self.isLocal())
        # update buttons
        self._updateState()

    def _versionActivated(self):
        """
        Enables/disables the MPI input fields dependant from current
        code_aster version (fields are enabled when version tagged by '_mpi').
        """
        ismpi = version_ismpi(self.codeAsterVersion())
        self._nodes.setEnabled(ismpi)
        self._mpicpu.setEnabled(ismpi)
        params = DashboardRunDialog.getCachedParams(self)
        self.setNodes(params.get('nodes', 1))
        self.setMpiCpu(params.get('mpicpu', 1))

    def _mpicpuEdited(self):
        """Store current as value in cache for future usage."""
        params = DashboardRunDialog.getCachedParams(self)
        params['mpicpu'] = self.mpiCpu()

    def _nodesEdited(self):
        """Store current as value in cache for future usage."""
        params = DashboardRunDialog.getCachedParams(self)
        params['nodes'] = self.nodes()

    def _addWidget(self, grid, label, edit):
        """
        Added labeled control into the last grid row.
        """
        row = grid.rowCount()
        grid.addWidget(Q.QLabel(label, self), row, 0)
        grid.addWidget(edit, row, 1)

    def _updateState(self):
        """
        Updates the buttons state.
        """
        hasfolder = self.folder() is not None and len(self.folder()) > 0
        hasrfolder = self.remoteFolder() is not None \
                     and len(self.remoteFolder()) > 0
        needsremote = self._remote_folder.state()
        isvalid = hasfolder and (hasrfolder or not needsremote)
        # ensure a version is selected (in case of error when refeshing server)
        isvalid = isvalid and self.codeAsterVersion() != ''
        self._btnbox.button(Q.QDialogButtonBox.Ok).setEnabled(isvalid)


class DashboardInfo(Q.QWidget):
    """
    Class that represent the bottom part of Dashboard with
    control buttons and log, info windows
    """
    stopClicked = Q.pyqtSignal()
    pauseClicked = Q.pyqtSignal()
    resumeClicked = Q.pyqtSignal()
    refreshClicked = Q.pyqtSignal()
    showMsgFileClicked = Q.pyqtSignal(Q.QAction)

    class TextEdit(Q.QTextBrowser):
        """
        Class text edit with support show/hide lines.
        """
        def __init__(self, parent=None):
            super(DashboardInfo.TextEdit, self).__init__(parent)
            self.setReadOnly(True)

        def lineCount(self):
            """
            Gets the number of lines.

            Returns:
                int: Lines number
            """
            return self.document().blockCount()

        def lineText(self, num):
            """
            Gets the line text.

            Arguments:
                num (int): Line number

            Returns:
                str: Line text
            """
            block = self.document().findBlockByNumber(num)
            return block.text() if block is not None else ''

        def isLineVisible(self, num):
            """
            Gets the line visibility state.

            Arguments:
                num (int): Line number

            Returns:
                bool: Line visibility state
            """
            block = self.document().findBlockByNumber(num)
            return block.isVisible() if block is not None else False

        def setLineVisible(self, num, on):
            """
            Sets the line visibility state.

            Arguments:
                num (int): Line number
                on (bool): Line visibility state
            """
            block = self.document().findBlockByNumber(num)
            if block is not None and block.isVisible() != on:
                block.setVisible(on)
                event = Q.QResizeEvent(self.size(),
                                       self.size() + Q.QSize(1, 1))
                Q.QApplication.sendEvent(self.viewport(), event)

        def filter(self, pattern):
            """
            Shows edit lines according specified pattern.

            Arguments:
                pattern (str): Filter pattern
            """
            changed = False
            regex = Q.QRegExp(pattern, Q.Qt.CaseInsensitive)
            for i in xrange(self.lineCount()):
                block = self.document().findBlockByNumber(i)
                if block is not None:
                    ison = len(pattern) == 0 or \
                        regex.indexIn(block.text()) != -1
                    changed = changed or block.isVisible() != ison
                    block.setVisible(ison)

            if changed:
                event = Q.QResizeEvent(self.size(),
                                       self.size() + Q.QSize(1, 1))
                Q.QApplication.sendEvent(self.viewport(), event)


    class Searcher(Q.QWidget):
        """Search widget."""

        def __init__(self, parent):
            super(DashboardInfo.Searcher, self).__init__(parent)
            self.setLayout(Q.QHBoxLayout())
            self.layout().setContentsMargins(0, 0, 0, 0)

            self.search = SearchWidget(self)

            self.prev_btn = Q.QToolButton(self)
            self.prev_btn.setIcon(load_icon("as_pic_find_prev.png"))
            self.prev_btn.setObjectName("find_prev")

            self.next_btn = Q.QToolButton(self)
            self.next_btn.setIcon(load_icon("as_pic_find_next.png"))
            self.next_btn.setObjectName("find_next")

            self.layout().addWidget(self.search)
            self.layout().addWidget(self.prev_btn)
            self.layout().addWidget(self.next_btn)

        def clear(self):
            """Clear search text."""
            self.search.clear()

    def __init__(self, parent=None):
        """
        Constructor
        """
        super(DashboardInfo, self).__init__(parent)

        base = Q.QVBoxLayout(self)
        base.setContentsMargins(0, 0, 0, 0)

        tools = Q.QWidget(self)
        base.addWidget(tools)
        tools.setSizePolicy(Q.QSizePolicy.Preferred, Q.QSizePolicy.Maximum)

        row = Q.QHBoxLayout(tools)
        row.setContentsMargins(0, 0, 0, 0)
        self._combo = Q.QComboBox(tools)
        row.addWidget(self._combo)

        self._stop = Q.QPushButton(translate("Dashboard", "Stop"), tools)
        # TODO Replace by "Send USR1 signal"
        # self._pause = Q.QPushButton(translate("Dashboard", "Pause"), tools)
        self._resume = Q.QPushButton(translate("Dashboard", "Resume"), tools)
        self._refresh = Q.QPushButton(translate("Dashboard", "Refresh"), tools)
        self._view_file = Q.QPushButton(translate("Dashboard",
                                                  "Show message file"), tools)
        self._view_file.setMenu(Q.QMenu(self))
        row.addWidget(self._stop)
        # row.addWidget(self._pause)
        row.addWidget(self._resume)
        row.addWidget(self._refresh)
        row.addWidget(self._view_file)
        row.addStretch(1)

        self._search = DashboardInfo.Searcher(tools)
        row.addWidget(self._search)

        self._stack = Q.QStackedWidget(self)
        base.addWidget(self._stack, 1)

        self._stop.clicked.connect(self.stopClicked)
        # self._pause.clicked.connect(self.pauseClicked)
        self._resume.clicked.connect(self.resumeClicked)
        self._refresh.clicked.connect(self.refreshClicked)
        self._combo.activated.connect(self._infoActivated)
        self._view_file.menu().triggered.connect(self.showMsgFileClicked)

        self._createInfoWindow(self.TextEdit(self._stack),
                               translate("Dashboard", "Log"),
                               Dashboard.InfoType.Log)
        self._createInfoWindow(self.TextEdit(self._stack),
                               translate("Dashboard", "Console"),
                               Dashboard.InfoType.Console)

        self._search.search.filterChanged.connect(self._find)
        self._search.search.confirmed.connect(self._findNext)
        self._search.prev_btn.clicked.connect(self._findPrevious)
        self._search.next_btn.clicked.connect(self._findNext)
        self.updateState()

    def dashboard(self):
        """
        Gets the Dashboard parent object.

        Returns:
            Dashboard: Dashboard object.
        """
        dshbrd = None
        parent = self.parentWidget()
        while parent is not None and dshbrd is None:
            if isinstance(parent, Dashboard):
                dshbrd = parent
            parent = parent.parentWidget()
        return dshbrd

    def information(self, ident):
        """
        Gets the information text from window with given identifier.

        Arguments:
            ident (int): Information window identifier.

        Returns:
            str: Information window text.
        """
        win = self._infoWindow(ident)
        return '' if win is None else win.toPlainText()

    def setInformation(self, ident, text):
        """
        Sets the information text to window with given identifier.

        Arguments:
            ident (int): Information window identifier.
            text (str): Information text.
        """
        win = self._infoWindow(ident)
        if win is not None:
            win.setText(text)

    def appendInformation(self, ident, text):
        """
        Appends the information text to window with given identifier.

        Arguments:
            ident (int): Information window identifier.
            text (str): Information text.
        """
        win = self._infoWindow(ident)
        if win is not None:
            win.append(text)
            win.moveCursor(Q.QTextCursor.End)

    def updateState(self):
        """
        Update the button states according to running state.
        """
        dshbrd = self.dashboard()
        is_running = dshbrd is not None and dshbrd.isRunning()
        self._stop.setEnabled(is_running)
        # self._pause.setEnabled(is_running)
        self._resume.setEnabled(is_running)
        ispause = dshbrd is not None and dshbrd.isPausing()
        self._resume.setVisible(ispause)
        # self._pause.setVisible(not ispause)

        if not is_running:
            files = [(translate("Dashboard", "'message'"), "message"),
                     (translate("Dashboard", "'export'"), "export"),
                     (translate("Dashboard", "'log'"),
                      osp.join("logs", "command_*.log"))]

            selection = dshbrd.selected_objects()
            if selection and len(selection) == 1:
                stages_menu = self._view_file.menu()
                stages_menu.clear()
                actions = []
                runcase = selection[0]
                seen = set()
                for st in runcase.stages:
                    for label, pattern in files:
                        found = glob(osp.join(st.folder, pattern))
                        if found and found[0] not in seen:
                            act = Q.QAction(st.name + " " + label, stages_menu)
                            act.setData(found[0])
                            actions.append(act)
                            seen.add(found[0])
                stages_menu.addActions(actions)

        self._view_file.setEnabled(not is_running and
                                   not self._view_file.menu().isEmpty())
        self._updateInfoWindow(dshbrd)

    def _updateInfoWindow(self, dshbrd=None):
        """
        Updates the information window if RunCase in selection.

        Arguments:
            dshbrd (Dashboard): Dashboard to get scene of Run cases.
        """
        infotype = Dashboard.InfoType.Console
        if self._activeInfoType() == infotype:
            if dshbrd is None:
                dshbrd = self.dashboard()
            selection = dshbrd.selected_objects()
            if selection:
                self.setInformation(infotype, selection[0].show_message())

    def _infoWindow(self, ident):
        """
        Gets the information window with given identifier

        Arguments:
            ident (int): Identifier of information window.

        Returns:
            QWidget: Information window object.
        """
        return self._stack.widget(self._combo.findData(ident))

    def _createInfoWindow(self, widget, name, ident):
        """
        Create the information window with given identifier

        Arguments:
            widget (QWidget): Information window object.
            name (str): Information window title.
            ident (int): Identifier of information window.
        """
        self._combo.addItem(name)
        self._combo.setItemData(self._combo.count() - 1, ident)
        widget.setCurrentFont(Q.QFont("Monospace"))
        self._stack.addWidget(widget)

    def _infoActivated(self, index):
        self._stack.setCurrentIndex(index)
        self._search.clear()
        self._updateInfoWindow()
        self._gotoStart()

    def _filter(self, pattern):
        """
        Filter the lines in the current information window.
        """
        wid = self._stack.currentWidget()
        if wid is not None and hasattr(wid, 'filter'):
            wid.filter(pattern)

    def _gotoStart(self):
        wid = self._stack.currentWidget()
        if wid is not None:
            wid.moveCursor(Q.QTextCursor.Start)

    def _find(self, text):
        wid = self._stack.currentWidget()
        if wid is not None:
            cursor = wid.textCursor()
            position = min(cursor.position(), cursor.anchor())
            cursor.setPosition(position)
            wid.setTextCursor(cursor)
            if not wid.find(text):
                wid.moveCursor(Q.QTextCursor.Start)
                wid.find(text)

    def _findPrevious(self):
        text = self._search.search.filter()
        wid = self._stack.currentWidget()
        if wid is not None:
            if not wid.find(text, Q.QTextDocument.FindBackward):
                wid.moveCursor(Q.QTextCursor.End)
                wid.find(text, Q.QTextDocument.FindBackward)

    def _findNext(self):
        text = self._search.search.filter()
        wid = self._stack.currentWidget()
        if wid is not None:
            if not wid.find(text):
                wid.moveCursor(Q.QTextCursor.Start)
                wid.find(text)

    def _activeInfoType(self):
        """
        Get type of the active Info window from combobox.

        Returns:
            Dashboard.InfoType: Information window type.
        """
        return self._combo.currentData()


class DashboardScene(Q.QGraphicsScene):
    """
    Class represents graphics scene in dashboard
    """
    def __init__(self, dashboard, parent=None):
        """
        Constructor
        """
        super(DashboardScene, self).__init__(parent)
        self._stateproxy = None
        self._dashboard = dashboard

    def updateScene(self, history):
        """
        Refulfill the all case and stages in scene
        """
        selected = self.selection()
        block = self.signalsBlocked()
        self.blockSignals(True)

        for i in self.items():
            i.setVisible(False)
        self.clear()

        cases = []
        if history is not None:
            cases = history.run_cases
        for case in reversed(cases):
            item = DashboardCaseItem(case)
            self.addItem(item)
            item.updatePosition()

        for case in reversed(cases):
            prev = None
            for stage in case.stages:
                ref_stage = prev
                if ref_stage is not None:
                    result = ref_stage.result
                    if result is not None and result.stage is not None:
                        ref_stage = result.stage
                if ref_stage is not None:
                    link = self._createLink(ref_stage, stage)
                    if link is not None:
                        self.addItem(link)
                        link.updatePosition()
                prev = stage

        self.setSelection(selected)

        for view in self.views():
            view.setResizeAnchor(view.AnchorViewCenter)
            view.update()

        self.blockSignals(block)
        old = set([i.uid for i in selected])
        cur = set([i.uid for i in self.selection()])
        if old != cur:
            self.selectionChanged.emit()

    def selection(self):
        """
        Gets the currently selected objects.

        Returns:
            list: List of selected objects: cases, stages.
        """
        objs = []
        for i in self.selectedItems():
            obj = i.itemObject() if hasattr(i, 'itemObject') else None
            if obj is not None:
                objs.append(obj)
        return objs

    def setSelection(self, objs):
        """
        Sets the selection, i.e. select given objects.
        Other objects will be unselected.

        Arguments:
            objs (list): List of objects that should be selected.
        """
        block = self.signalsBlocked()
        self.blockSignals(True)
        self.clearSelection()
        for i in objs:
            item = self.findItem(i)
            if item is not None:
                item.setSelected(True)
        self.blockSignals(block)

    def stageState(self, stage, case):
        """
        Gets the current state of stage.

        Returns:
            int: State value.
        """
        state = None
        if self.stateProxy() is not None:
            state = self.stateProxy().stageState(stage, case)
        if state is None:
            proxy_stage = _proxyStage(stage, case)
            if proxy_stage is not None:
                state = proxy_stage.state | StateOptions.Intermediate
            elif stage is not None:
                state = stage.state
            else:
                state = StateOptions.Waiting
        return state

    def stateProxy(self):
        """
        Gets the state proxy.
        """
        return self._stateproxy

    def setStateProxy(self, proxy):
        """
        Sets the state proxy.
        """
        if self._stateproxy != proxy:
            self._stateproxy = proxy
            self.update()

    def isActiveCase(self, case):
        """
        Gets the active state of specified case.

        Arguments:
            case (Case): Case object.

        Returns:
            bool: Case activity state.
        """
        return self._dashboard.isActiveCase(case) \
            if self._dashboard is not None else False

    def findItem(self, obj):
        """
        Find the graphics item which contains specified object.

        Arguments:
            obj: Stage or Case object.

        Returns:
            QGraphicsItem: found graphics item.
        """
        item = None
        for i in self.items():
            item = self._findItem(i, obj)
            if item is not None:
                break
        return item

    def _findItem(self, item, obj):
        """
        Find the child graphics item of given item which contains
        specified object.

        Arguments:
            item: Parent graphics item.
            obj: Stage or Case object.

        Returns:
            QGraphicsItem: found graphics item.
        """
        res = None
        if item is not None and hasattr(item, 'itemObject'):
            iobj = item.itemObject()
            if (isinstance(obj, Entity) and obj.uid == iobj.uid) \
                    or iobj == obj:
                res = item

        if res is None:
            for i in item.childItems():
                res = self._findItem(i, obj)
                if res is not None:
                    break
        return res

    def _createLink(self, src, trg):
        """
        Create the link item.
        """
        if src is None or trg is None:
            return None

        srcItem = self.findItem(src)
        trgItem = self.findItem(trg)
        if srcItem is None or trgItem is None:
            return None

        return DashboardLinkItem(srcItem, trgItem)

class DashboardView(Q.QGraphicsView):
    """
    Class represents graphics view in dashboard
    """
    contextMenu = Q.pyqtSignal(Q.QPoint)

    def __init__(self, scene, parent=None):
        """
        Constructor
        """
        super(DashboardView, self).__init__(scene, parent)
        self.setResizeAnchor(self.AnchorViewCenter)
        self.setTransformationAnchor(self.NoAnchor)
        self.setAlignment(Q.Qt.AlignLeft | Q.Qt.AlignTop)
        self.setViewportUpdateMode(self.BoundingRectViewportUpdate)
        self.setDragMode(Q.QGraphicsView.RubberBandDrag)
        self.setMouseTracking(True)
        self._pos = None

    def caseTitleHeight(self):
        """
        Gets the case title height in graphics view.

        Returns:
            int: Case title height
        """
        opts = Dashboard.opts()
        top = self.mapFromScene(Q.QPointF(0, 0))
        pnt = self.mapFromScene(Q.QPointF(0, opts.title_height))
        return pnt.y() - top.y()

    def stageHeight(self):
        """
        Gets the stage height in graphics view.

        Returns:
            int: Stage height
        """
        opts = Dashboard.opts()
        top = self.mapFromScene(Q.QPointF(0, 0))
        pnt = self.mapFromScene(Q.QPointF(0, opts.stage_size))
        return pnt.y() - top.y()

    def spacerHeight(self):
        """
        Gets the stage space height in graphics view.

        Returns:
            int: Stage space height
        """
        opts = Dashboard.opts()
        top = self.mapFromScene(Q.QPointF(0, 0))
        pnt = self.mapFromScene(Q.QPointF(0, opts.spacing + 6))
        return pnt.y() - top.y()

    def viewHeight(self):
        """
        Gets the total graphics view height with 4 stages.

        Returns:
            int: View height
        """
        opts = Dashboard.opts()
        top = self.mapFromScene(Q.QPointF(0, 0))
        y = opts.title_height + \
            4 * (opts.stage_size + 6 + opts.spacing) + 15
        pnt = self.mapFromScene(Q.QPointF(0, y))
        return pnt.y() - top.y()

    def sizeHint(self):
        """
        Reimplemented for wrapping size hint of graphics view.

        Returns:
            QSize: Size object with size hint.
        """
        sz = super(DashboardView, self).sizeHint()
        sz.setHeight(self.viewHeight())
        return sz

    def contextMenuEvent(self, event):
        """
        Reimplemented for context menu handling.
        """
        self.contextMenu.emit(event.globalPos())

    def wheelEvent(self, event):
        """
        Reimplemented for scaling view by mouse wheel.
        """
        delta = event.angleDelta()
        if not delta.isNull():
            step = 1.15
            if delta.x() + delta.y() < 0:
                step = 1.0 / step
            self.scale(step, step)
            event.accept()

    def mousePressEvent(self, event):
        """
        Reimplemented for translating view by mouse move with
        holded right mouse button.
        """
        if event.button() == Q.Qt.MidButton:
            self._pos = event.pos()
        # Prevent deselection by right button click
        elif event.button() != Q.Qt.RightButton:
            super(DashboardView, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """
        Reimplemented for translating view by mouse move with
        holded right mouse button.
        """
        if event.button() == Q.Qt.MidButton:
            self._pos = None
        else:
            super(DashboardView, self).mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        """
        Reimplemented for translating view by mouse move with
        holded right mouse button.
        """
        if self._pos is not None:
            delta = event.pos() - self._pos
            self._pos = event.pos()
            self.setResizeAnchor(self.NoAnchor)
            self.translate(delta.x(), delta.y())
            self.update()
        super(DashboardView, self).mouseMoveEvent(event)


class DashboardItem(Q.QGraphicsItem):
    """
    Class represents graphics item in dashboard graphics view.
    """
    def __init__(self, obj, parent=None):
        """
        Constructor
        """
        super(DashboardItem, self).__init__(parent)
        self.setZValue(0)
        self._object = obj

    def itemObject(self):
        """
        Gets the object associated with item.

        Returns:
            Node: Node object from data model.
        """
        return self._object

    def itemName(self):
        """
        Gets the object name.

        Returns:
            str: Name of object.
        """
        txt = ""
        if self.itemObject() is not None:
            txt = self.itemObject().name
        return txt

    def updatePosition(self):
        """
        Updates position of item and all child items.
        """
        for i in self.childItems():
            if hasattr(i, 'updatePosition'):
                i.updatePosition()


class DashboardCaseItem(DashboardItem):
    """
    Class represents graphics item in dashboard graphics view.
    """
    def __init__(self, case):
        """
        Constructor
        """
        super(DashboardCaseItem, self).__init__(case)
        self.setFlags(self.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self._createStages()
        self._hover = False

    def _checkHover(self, event):
        hover = False
        if event.widget() is not None:
            view = event.widget().parentWidget()
            if view is not None and hasattr(view, 'itemAt'):
                hover = view.itemAt(view.mapFromGlobal(event.screenPos())) \
                    == self
        if self._hover != hover:
            self._hover = hover
            self.update()

    def index(self):
        """
        Gets the index of case in history case list

        Returns:
            int: Case index
        """
        idx = -1
        case = self.itemObject()
        if case is not None:
            hist = case.model
            if hist is not None:
                case_list = [i for i in reversed(hist.run_cases)]
                if case in case_list:
                    idx = case_list.index(case)
        return idx

    # pragma pylint: disable=unused-argument,no-self-use
    def paint(self, painter, option, widget=None):
        """
        Case item painting.
        """
        opts = Dashboard.opts()
        rect = self.boundingRect()

        painter.save()
        painter.setRenderHint(Q.QPainter.Antialiasing, True)
        painter.setRenderHint(Q.QPainter.TextAntialiasing, True)

        if self.scene() is not None and \
                self.scene().isActiveCase(self.itemObject()):
            font = painter.font()
            font.setBold(True)
            font.setItalic(True)
            font.setUnderline(True)
            painter.setFont(font)
        fm = Q.QFontMetrics(self.scene().font())
        mg = opts.margin
        mg2 = opts.margin / 2
        mg4 = opts.margin / 4
        title_rect = Q.QRectF(mg2, mg2, rect.width() - mg, fm.height() + mg)
        title_rect = title_rect.adjusted(mg4, mg4, -mg4, -mg4)
        title_color = Q.QColor(100, 100, 100, 70)
        title_area = Q.QPainterPath()
        title_area.addRoundedRect(title_rect, 3, 3)
        painter.fillPath(title_area, title_color)
        painter.drawText(title_rect,
                         fm.elidedText(self.itemName(), Q.Qt.ElideRight,
                                       title_rect.toRect().width()),
                         Q.QTextOption(Q.Qt.AlignCenter))

        if option.state & (Q.QStyle.State_Selected | Q.QStyle.State_MouseOver):
            color = Q.Qt.blue if (option.state & Q.QStyle.State_Selected) \
                else Q.Qt.cyan
            pen = Q.QPen(color)
            pen.setWidth(2)
            painter.setPen(pen)
            bnd_rect = rect.adjusted(mg2, mg2, -mg2, -mg2)
            painter.drawRoundedRect(bnd_rect, 5, 5)

        painter.restore()

    def shape(self):
        """
        Gets the shape of item bound contour.

        Returns:
            QPainterPath: Countor.
        """
        opts = Dashboard.opts()
        rect = self.boundingRect()
        path = Q.QPainterPath()
        mg2 = opts.margin / 2
        path.addRect(rect.adjusted(mg2, mg2, -mg2, -mg2))
        return path

    def boundingRect(self):
        """
        Gets the case item bound rectangle.

        Returns:
            QRectF: Bound rectangle.
        """
        opts = Dashboard.opts()
        name = self.itemName()
        width = 0
        height = opts.title_height
        if self.scene() is not None:
            font_metrics = Q.QFontMetrics(self.scene().font())
            width = min(font_metrics.width(name), 150)

        bottom = 0
        if len(self.childItems()) > 0:
            for i in self.childItems():
                rect = i.boundingRect()
                width = max(width, rect.width())
                spacing = rect.height() + opts.spacing
                bottom = max(bottom, rect.height() + i.index() * spacing)
        height += bottom

        width += 2 * opts.margin
        height += 2 * opts.margin

        return Q.QRectF(Q.QPointF(0, 0), Q.QSizeF(width, height))

    def updatePosition(self):
        """
        Updates position of item and all child items.
        """
        opts = Dashboard.opts()
        ref = None
        case = self.itemObject()
        if case is not None:
            hist = case.model
            if hist is not None:
                case_list = [i for i in reversed(hist.run_cases)]
                if case in case_list and case_list.index(case) > 0:
                    ref = case_list[case_list.index(case) - 1]
        xpos = 0
        if ref is not None:
            refItem = self.scene().findItem(ref)
            if refItem is not None:
                rect = refItem.boundingRect()
                xpos = refItem.x() + rect.width() + opts.spacing
        self.setPos(xpos, 0)
        super(DashboardCaseItem, self).updatePosition()

    def _createStages(self):
        """
        Create graphics stage items from case
        """
        stages = []
        case = self.itemObject()
        if self.itemObject() is not None:
            stages = case.stages

        descr = ""
        for stage in stages:
            if case == stage.parent_case:
                DashboardStageItem(stage, case, self)
                descr = stage.result.job.full_description
        if descr:
            self.setToolTip(descr)


class DashboardStageItem(DashboardItem):
    """
    Class represents graphics item in dashboard graphics view.
    """

    class HourGlassItem(Q.QGraphicsPixmapItem):
        """
        Class represents hour glass graphics item in dashboard graphics view.
        """
        def __init__(self, parent):
            super(DashboardStageItem.HourGlassItem, self).\
                __init__(load_pixmap("as_pic_wait.png"), parent)
            self.setTransformOriginPoint(self.boundingRect().center())
            self._anim = False
            self._time = Q.QTimeLine(1000)
            self._time.setLoopCount(0)
            self._time.setFrameRange(0, 360)
            self._time.frameChanged.connect(self.setRotation)

        def isAnimation(self):
            """
            Gets the animation state.

            Returns:
                bool: Animation state.
            """
            return self._anim

        def setAnimation(self, on):
            """
            Sets the animation state.

            Arguments:
                on (bool): Animation state.
            """
            if self._anim != on:
                self._anim = on
                self.itemChange(self.ItemVisibleChange, self.isVisible())

        def updatePosition(self):
            """
            Updates position of item and all child items.
            """
            self.setPos(self.parentItem().boundingRect().center() -
                        self.boundingRect().center())

        def itemChange(self, change, value):
            """
            Notification about changes in the item.
            """
            if change == self.ItemVisibleChange:
                anim = self.isAnimation() and value
                if anim:
                    if self._time.state() != Q.QTimeLine.Running:
                        self._time.start()
                else:
                    if self._time.state() == Q.QTimeLine.Running:
                        self._time.stop()
                    self.setRotation(0)
            return super(DashboardStageItem.HourGlassItem,
                         self).itemChange(change, value)

    def __init__(self, stage, case, parent=None):
        """
        Constructor
        """
        super(DashboardStageItem, self).__init__(stage, parent)
        self._case = case

        wait = DashboardStageItem.HourGlassItem(self)
        wait.setVisible(False)

    def index(self):
        """
        Gets the index of stage in run case stages list

        Returns:
            int: Stage index
        """
        idx = -1
        stage = self.itemObject()
        if stage is not None:
            case = stage.parent_case
            if case is not None:
                if stage in case.stages:
                    idx = case.stages.index(stage)
        return idx

    def updatePosition(self):
        """
        Updates position of item and all child items.
        """
        opts = Dashboard.opts()
        xpos = opts.margin
        rect = self.boundingRect()
        if self.parentItem() is not None:
            prect = self.parentItem().boundingRect()
            xpos = (prect.center() - rect.center()).x()
        spacing = rect.height() + opts.spacing
        self.setPos(xpos, opts.title_height + self.index() * spacing)
        super(DashboardStageItem, self).updatePosition()

    # pragma pylint: disable=unused-argument,no-self-use
    def paint(self, painter, option, widget=None):
        """
        Stage item painting.
        """
        opts = Dashboard.opts()
        state = self.stageState()

        painter.save()
        painter.setRenderHint(Q.QPainter.Antialiasing, True)

        path = Q.QPainterPath()
        path.addEllipse(0, 0, opts.stage_size, opts.stage_size)
        path.translate(3, 3)
        if state & StateOptions.Success:
            bg_color = Q.QColor(Q.Qt.green)
        elif state & StateOptions.Error:
            bg_color = Q.QColor(Q.Qt.red)
        elif state & StateOptions.Interrupted:
            # orange
            bg_color = Q.QColor(255, 175, 0)
        else:
            bg_color = Q.QColor(Q.Qt.white)
        if state & StateOptions.Intermediate:
            bg_color = bg_color.lighter()
        painter.fillPath(path, bg_color)

        pen = Q.QPen(Q.Qt.black)
        pen.setWidth(2)

        if state & (StateOptions.Running | StateOptions.Pausing):
            pen.setStyle(Q.Qt.DotLine)
            self._setWait(True, state & StateOptions.Running)
        else:
            self._setWait(False, False)

        if option.state & Q.QStyle.State_MouseOver:
            pen.setColor(Q.Qt.cyan)
        elif option.state & Q.QStyle.State_Selected:
            pen.setColor(Q.Qt.blue)

        painter.setPen(pen)
        painter.drawPath(path)
        painter.restore()

    def boundingRect(self):
        """
        Gets the stage item bound rectangle.

        Returns:
            QRectF: Bound rectangle.
        """
        opts = Dashboard.opts()
        rect = Q.QRectF(0, 0, opts.stage_size + 6,
                        opts.stage_size + 6)
        return rect

    def shape(self):
        """
        Gets the shape of item bound contour.

        Returns:
            QPainterPath: Countor.
        """
        opts = Dashboard.opts()
        path = Q.QPainterPath()
        path.addEllipse(0, 0, opts.stage_size, opts.stage_size)
        path.translate(3, 3)
        return path

    def stageState(self):
        """
        Gets the current state of stage.

        Returns:
            int: State value.
        """
        return self.scene().stageState(self.itemObject(), self._case) \
            if self.scene() is not None else StateOptions.Waiting

    def _setWait(self, on, isrun):
        """
        Show/hide waiting hour glass symbol
        """
        for symb in self.childItems():
            symb.setVisible(on)
            symb.setAnimation(isrun)

class DashboardLinkItem(Q.QGraphicsItem):
    """
    Class represents graphics link between two stages in dashboard
    graphics view.
    """
    def __init__(self, from_node, to_node, parent=None):
        """
        Constructor
        """
        super(DashboardLinkItem, self).__init__(parent)
        self._from = from_node
        self._to = to_node
        self.setZValue(5)

    def updatePosition(self):
        """
        Updates position of item and all child items.
        """
        self.setPos(self._path().boundingRect().topLeft())

    def shape(self):
        """
        Gets the shape of item bound contour.

        Returns:
            QPainterPath: Countor.
        """
        path = self._path()
        return path.translated(-path.boundingRect().topLeft())

    def boundingRect(self):
        """
        Gets the link item bound rectangle.

        Returns:
            QRectF: Bound rectangle.
        """
        return self.shape().boundingRect()

    # pragma pylint: disable=unused-argument,no-self-use
    def paint(self, painter, option, widget=None):
        """
        Link item painting.
        """
        painter.drawPath(self.shape())

    def _path(self):
        opts = Dashboard.opts()
        path = Q.QPainterPath()
        if self._from is not None and self._to is not None:
            beg = self._center(self._from)
            end = self._center(self._to)
            delta = end - beg
            if abs(delta.x()) < 0.00001 or abs(delta.y()) < 0.00001 \
                    or opts.link_mode == Options.LinkLine:
                path.moveTo(self._offsetPoint(beg, end,
                                              self._radius(self._from)))
                path.lineTo(self._offsetPoint(end, beg,
                                              self._radius(self._to)))
            else:
                if opts.link_mode in(Options.LinkMidRounded,
                                     Options.LinkMidArc):
                    dirpnt = Q.QPointF(beg.x() + (end.x() - beg.x()) / \
                                           abs(end.x() - beg.x()),
                                       beg.y() + (end.y() - beg.y()) / \
                                           abs(end.y() - beg.y()))
                    start = self._offsetPoint(beg, dirpnt,
                                              self._radius(self._from))
                else:
                    start = self._offsetPoint(beg, Q.QPointF(end.x(), beg.y()),
                                              self._radius(self._from))
                finish = self._offsetPoint(end, Q.QPointF(end.x(), beg.y()),
                                           self._radius(self._to))

                xcoeff = (finish.x() - start.x()) / abs(finish.x() - start.x())
                ycoeff = (finish.y() - start.y()) / abs(finish.y() - start.y())

                path.moveTo(start)
                if opts.link_mode == Options.LinkOrtho:
                    path.lineTo(finish.x(), start.y())
                    path.lineTo(finish)
                elif opts.link_mode == Options.LinkMidRounded:
                    mid = (beg.y() + end.y()) / 2
                    arcradius = abs(finish.y() - mid)

                    path.arcTo(Q.QRectF(Q.QPointF(start.x() +
                                                  2 * xcoeff * arcradius,
                                                  mid -
                                                  2 * ycoeff * arcradius),
                                        Q.QPointF(start.x(), mid)),
                               ycoeff * 0, xcoeff * 90)
                    path.lineTo(finish.x() - xcoeff * arcradius, mid)
                    path.arcTo(Q.QRectF(Q.QPointF(finish.x(), mid),
                                        Q.QPointF(finish.x() -
                                                  2 * xcoeff * arcradius,
                                                  mid +
                                                  2 * ycoeff * arcradius)),
                               ycoeff * 90, xcoeff * -90)
                    path.lineTo(finish)
                elif opts.link_mode == Options.LinkRounded:
                    arcradius = 20
                    path.lineTo(finish.x() - xcoeff * arcradius, start.y())
                    path.arcTo(Q.QRectF(Q.QPointF(finish.x(), start.y()),
                                        Q.QPointF(finish.x() -
                                                  2 * xcoeff * arcradius,
                                                  start.y() +
                                                  2 * ycoeff * arcradius)),
                               ycoeff * 90, xcoeff * -90)
                    path.lineTo(finish)
                elif opts.link_mode == Options.LinkArc:
                    path.arcTo(Q.QRectF(Q.QPointF(finish.x(), start.y()),
                                        Q.QPointF(finish.x() - 2 * xcoeff *
                                                  abs(finish.x() -
                                                      start.x()),
                                                  start.y() + 2 * ycoeff *
                                                  abs(finish.y() -
                                                      start.y()))),
                               ycoeff * 90, xcoeff * -90)
                elif opts.link_mode == Options.LinkMidArc:
                    mid = beg.y() + self._radius(self._from) + 5
                    arcradius = abs(start.y() - mid)

                    path.arcTo(Q.QRectF(Q.QPointF(start.x() +
                                                  2 * xcoeff * arcradius,
                                                  mid -
                                                  2 * ycoeff * arcradius),
                                        Q.QPointF(start.x(), mid)),
                               ycoeff * 0, xcoeff * 90)
                    path.arcTo(Q.QRectF(Q.QPointF(finish.x(), mid),
                                        Q.QPointF(finish.x() - 2 * xcoeff *
                                                  abs(finish.x() - start.x() -
                                                      2 * xcoeff * arcradius),
                                                  mid + 2 * ycoeff *
                                                  abs(finish.y() - mid))),
                               ycoeff * 90, xcoeff * -90)

        return path

    def _line(self):
        path = Q.QPainterPath()
        if self._from is not None and self._to is not None:
            beg = self._center(self._from)
            end = self._center(self._to)
            path.moveTo(self._offsetPoint(beg, end, self._radius(self._from)))
            path.lineTo(self._offsetPoint(end, beg, self._radius(self._to)))
        return path

    def _offsetPoint(self, beg, end, dist):
        delta = beg - end
        length = sqrt(delta.x() * delta.x() + delta.y() * delta.y())
        if length < 0.000001:
            return beg

        return Q.QPointF(beg.x() + dist * (end.x() - beg.x()) / length,
                         beg.y() + dist * (end.y() - beg.y()) / length)

    def _radius(self, node):
        return node.boundingRect().width() / 2 if node is not None else 0

    def _center(self, node):
        if node is None:
            return Q.QPointF()

        center = Q.QRectF(node.pos(), node.boundingRect().size()).center()
        if node.parentItem() is not None:
            center = node.parentItem().mapToScene(center)
        if self.parentItem() is not None:
            center = self.parentItem().mapFromScene(center)
        return center


class DashboardRunCasesTable(Q.QTableWidget):
    """
    Debug class with stage states representation in table view.
    Used for testing in Squish test.
    """
    def __init__(self, parent=None):
        super(DashboardRunCasesTable, self).__init__(parent)

    def dashboard(self):
        """
        Gets the Dashboard parent object.

        Returns:
            Dashboard: Dashboard object.
        """
        dshbrd = None
        parent = self.parentWidget()
        while parent is not None and dshbrd is None:
            if isinstance(parent, Dashboard):
                dshbrd = parent
            parent = parent.parentWidget()
        return dshbrd

    def updateTable(self, history):
        """
        Updates the status in the table.
        """
        self.clear()

        cases = [c for c in reversed(history.run_cases)] \
            if history is not None else []

        dsbrd = self.dashboard()

        self.setRowCount(0)
        self.setColumnCount(len(cases))
        self.setHorizontalHeaderLabels([c.name for c in cases])

        for case_idx, case in enumerate(cases):
            stages = case.stages
            self.setRowCount(max(self.rowCount(), len(stages)))
            for stage_idx, stage in enumerate(stages):
                result = stage.result
                if result is not None and stage == result.stage:
                    state = dsbrd.stageState(stage, case)
                    if state is None:
                        state = result.state
                    if state is not None:
                        self.setItem(stage_idx, case_idx,
                                     Q.QTableWidgetItem(str(state)))

        for r in xrange(self.rowCount()):
            self.setRowHeight(r, 20)

def _proxyStage(stage, case):
    """
    Get stage that actually stores results for given *stage* if this
    *stage* has *Intermediate* state (i.e. result was not kept at
    previous run).

    Arguments:
        stage (Stage): Source stage.
        case (Case): Reference case.

    Returns:
        Stage: Proxy stage if there's any; *None* elsewise.
    """
    if stage is not None and (stage.state & StateOptions.Intermediate) and \
            case is not None and stage in case.stages:
        index = case.stages.index(stage)
        child_stages = case.stages[index:]
        for child in child_stages:
            if not child.state & StateOptions.Intermediate:
                return child
    return None
