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
AsterStudy GUI
--------------

Implementation of base AsterStudy GUI.

"""

from __future__ import unicode_literals

import os
import tempfile
from subprocess import call
from collections import OrderedDict
from functools import partial

from PyQt5.Qt import (Qt, QInputDialog, QMessageBox, QObject,
                      QDesktopServices, QUrl, QApplication, QClipboard,
                      pyqtSignal, pyqtSlot)

from common import (CFG, bold, clean_text, debug_mode, italic, load_icon,
                    not_implemented, preformat, translate, wait_cursor,
                    debug_message, to_list, load_icon_set, read_file)
from datamodel import CATA
from gui import (ActionType, MenuGroup, Entity, Context, WorkingMode, Panel,
                 NodeType, get_node_type, check_selection, translate_category,
                 translate_command)
from .actions import Action, ListAction, UndoAction
from .behavior import Behavior, behavior
from .commentpanel import CommentPanel
from .controller import Controller
from .datafiles import DirsPanel, UnitPanel, edit_directory
from .guitest import GuiTester
from .meshview import MeshBaseView
from .parameterpanel import ParameterPanel
from .popupmanager import ContextMenuMgr
from .prefmanager import tab_position
from .showallpanel import ShowAllPanel
from .stagetexteditor import StageTextEditor
from .textfileeditor import TextFileDialog, TextFileEditor
from .variablepanel import VariablePanel
from .workspace import Workspace, views, view_title

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name
# pragma pylint: disable=too-many-lines

# pragma pylint: disable=too-many-public-methods

# Flag: treat selection buffer of clipboard in Paste operation
PASTE_TREAT_SELECTION_BUFFER = False

class AsterGui(QObject, Behavior):
    """Base AsterStudy GUI implementation."""

    selectionChanged = pyqtSignal(int)
    """
    Signal: emitted when selection is changed.

    Arguments:
        context (int): Selection context (see `Context`).
    """

    preferencesChanged = pyqtSignal(object)
    """
    Signal: emitted when application's preferences are changed.

    Arguments:
        pref_mgr (object): Application's preferences manager.
    """

    def __init__(self):
        """Create GUI wrapper."""
        super(AsterGui, self).__init__()
        self.main_window = None
        self.work_space = None
        self.actions = {}
        self.views_actions = OrderedDict()
        self.cmd_actions = OrderedDict()
        self.aster_study = None
        self.gui_tester = None

        QApplication.clipboard().changed.connect(self._updateActions)
        QApplication.clipboard().dataChanged.connect(self._updateActions)

    def initialize(self):
        """Initialize GUI."""
        self._createMainWindow()
        self._createActions()
        self._createMenus()
        self._createToolbars()
        self._updateActions()

    def mainWindow(self):
        """
        Get main window.

        Returns:
           QMainWindow: Application's main window.
        """
        return self.main_window

    def workSpace(self):
        """
        Get workspace.

        Returns:
            Workspace: Workspace of AsterStudy GUI.
        """
        return self.work_space

    def workingMode(self):
        """
        Get current working mode.

        Returns:
            int: Current working mode (see `WorkingMode`).
        """
        return self.work_space.workingMode() if self.work_space else None

    def setWorkingMode(self, wmode):
        """
        Set current working mode.

        Arguments:
            wmode (int): Current working mode (see `WorkingMode`).
        """
        if self.workSpace() is not None:
            self.workSpace().setWorkingMode(wmode)

    def selected(self, context):
        """
        Get current selection.

        Arguments:
            context (int): Selection context (see `Context`).

        Returns:
            list[Entity]: Selected items.
        """
        return self.work_space.selected(context) if self.work_space else []

    def view(self, context):
        """
        Get view window.

        Arguments:
            context (int): View type (see `Context`).

        Returns:
            QWidget: View window.
        """
        return self.work_space.view(context) \
            if self.work_space else None

    def study(self):
        """
        Get study.

        Returns:
            Study: Current study.
        """
        return self.aster_study

    def isNullStudy(self, message=None):
        """
        Check if the study is not initialized.

        Arguments:
            message (Optional[str]): Warning message to show. Defaults
                to *None*.

        Returns:
            bool: *True* if current study is *None*; *False* otherwise.
        """
        result = False
        if self.study() is None:
            result = True
            null_message = translate("AsterStudy", "Null study") \
                if message is None else message
            QMessageBox.critical(self.mainWindow(),
                                 "AsterStudy",
                                 null_message)
        return result

    def showMessage(self, msg, timeout=5000):
        """
        Show the message in the status bar with specified timeout.

        Arguments:
            msg (str): Status bar message.
            timeout (Optional[int]): Timeout in milliseconds for
                automatic message clear. Use 0 to show permanent
                message. Defaults to 5000 (5 seconds).
        """
        if self.mainWindow() is not None:
            self.mainWindow().statusBar().showMessage(msg, timeout)

    def clearMessage(self):
        """
        Clear the message in the status bar.
        """
        if self.mainWindow() is not None:
            self.mainWindow().statusBar().clearMessage()

    def createAction(self, text, tooltip, statustip,
                     icon, shortcut, slot, ident, parent, *args):
        """
        Create action.

        Each action is associated with the unique identifier. Action can
        have tooltip, status tip text, icon and shortcut key combination
        and can be connected to the dedicated slot function.

        Arguments:
            text (str): Menu text.
            tooltip (str): Tooltip text.
            statustip (str): Status tip text.
            icon (QIcon): Icon.
            shortcut (str): Shortcut key.
            slot (method): Slot for the action.
            ident (int): Unique identifier (see `ActionType`).
            parent (QObject): Owner of the action.
            *args: Optional list of contexts where action should be
                additionally added.

        Returns:
            QAction: Created action.

        Raises:
            RuntimeError: If action with specified identifier has been
                already added.

        See also:
            `action()`
        """
        if ident and ident in self.actions:
            raise RuntimeError("Action %d already presents in map" % ident)
        action = Action(text, parent)
        if icon and not icon.isNull():
            action.setIcon(icon)
        if shortcut:
            action.setShortcut(shortcut)
            action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
            tooltip = preformat("{0} ({1})".format(tooltip, bold(shortcut)))
        action.setToolTip(tooltip)
        action.setStatusTip(statustip)
        if slot is not None:
            action.triggered.connect(slot)
        if ident:
            self.actions[ident] = action

        if not args:
            parent.mainWindow().addAction(action)
        else:
            for context in args:
                if self.workSpace() is not None:
                    self.workSpace().view(context).addAction(action)

        return action

    def action(self, ident):
        """
        Get action by identifier.

        Arguments:
            ident (int): Action's identifier (see `ActionType`).

        Returns:
           QAction: Action associated with the given identifier.

        See also:
            `createAction()`, `actionId()`
        """
        return self.actions.get(ident)

    def actionId(self, action):
        """
        Get action's identifier.

        Arguments:
            action (QAction): Action.

        Returns:
           int: Action's UID; *None* if action is unknown.

        See also:
            `creatAction()`, `action()`
        """
        uid = None
        for key, value in self.actions.iteritems():
            if value == action:
                uid = key
        return uid

    # pragma pylint: disable=unused-argument,no-self-use
    def createMenu(self, text, parent=-1, group=-1):
        """
        Create menu item in the main menu of application.

        Default implementation raises exception; the method should be
        implemented in successor classes.

        Menu item is specified by its label. If there is already a menu
        with given text, its identifier is returned.

        Parent menu is specified via the identifier; -1 means top-level
        menu.

        Menu items are combined into groups; -1 means most bottom (last)
        group.

        Arguments:
            text (str): Text label of menu item.
            parent (Optional[int]): Parent menu item. Defaults to -1.
            group (Optional[int]): Menu group. Defaults to -1.

        Returns:
            int: Menu item's unique identifier.

        Raises:
            NotImplementedError: The method should be implemented in
                sub-classes.

        See also:
            `addMenuAction()`
        """
        raise NotImplementedError("Method should be implemented in successors")

    def menu(self, *args):
        """
        Get menu by path.

        Menu can be searched by the path which is a string or a list of
        strings.

        Arguments:
            *args: Menu title path: list of strings.

        Returns:
           QMenu: Menu object (None if menu is not found).

        See also:
            `createMenu()`
        """
        path = list(args)
        path.reverse()

        root = self.mainWindow().menuBar()
        menu = None

        while path:
            item = path.pop()
            actions = root.actions()
            found_menu = None
            for action in actions:
                if action.menu() is None:
                    continue
                if clean_text(action.text()) == clean_text(item):
                    found_menu = action.menu()
                    break
            if found_menu is None:
                break
            elif path:
                root = found_menu
            else:
                menu = found_menu
        return menu

    # pragma pylint: disable=unused-argument,no-self-use
    def addMenuAction(self, action, parent, group=-1):
        """
        Add action to the menu.

        Default implementation raises exception; the method should be
        implemented in successor classes.

        Similarly to menu items, actions are combined into groups;
        see `createMenu()` for more details.

        Arguments:
            action (QAction): Menu action.
            parent (int): Parent menu item.
            group (Optional[int]): Menu group. Defaults to -1.

        Raises:
            NotImplementedError: The method should be implemented in
                sub-classes.

        See also:
            `createMenu()`
        """
        raise NotImplementedError("Method should be implemented in successors")

    # pragma pylint: disable=unused-argument,no-self-use
    def createToolbar(self, text, name):
        """
        Create toolbar.

        Default implementation raises exception; the method should be
        implemented in successor classes.

        Toolbar is specified by its label and name.
        Label normally is specified as a text translated to the current
        application's language, while name should not be translated - it
        is used to properly save and restore positions of toolbars.

        Arguments:
            text (str): Text label of toolbar.
            name (str): Unique name of toolbar.

        Returns:
            int: Toolbar's unique identifier.

        Raises:
            NotImplementedError: The method should be implemented in
                sub-classes.

        See also:
            `addToolbarAction()`
        """
        raise NotImplementedError("Method should be implemented in successors")

    # pragma pylint: disable=unused-argument,no-self-use
    def addToolbarAction(self, action, parent):
        """
        Add action to the toolbar.

        Default implementation raises exception; the method should be
        implemented in successor classes.

        Arguments:
            action (QAction): Toolbar action.
            parent (int): Parent toolbar.

        Raises:
            NotImplementedError: The method should be implemented in
                sub-classes.

        See also:
            `createToolbar()`
        """
        raise NotImplementedError("Method should be implemented in successors")

    @pyqtSlot(bool)
    @pyqtSlot(int)
    def undo(self, count):
        """
        [Edit | Undo] action's slot.

        Arguments:
            count (int): Number of operations to undo.
        """
        if self.isNullStudy():
            return

        ctr = Controller(translate("AsterStudy", "Undo"), self)
        if ctr.controllerStart():
            if isinstance(count, bool):
                count = 1
            self.study().undo(count)
            self.update()
            ctr.controllerCommit()

    @pyqtSlot(bool)
    @pyqtSlot(int)
    def redo(self, count):
        """
        [Edit | Redo] action's slot.

        Arguments:
            count (int): Number of operations to redo.
        """
        if self.isNullStudy():
            return

        ctr = Controller(translate("AsterStudy", "Redo"), self)
        if ctr.controllerStart():
            if isinstance(count, bool):
                count = 1
            self.study().redo(count)
            self.update()
            ctr.controllerCommit()

    @pyqtSlot(bool)
    def linktodoc(self):
        """[Edit | LinkToDoc] action's slot."""
        if self.isNullStudy():
            return

        selected = self.selected(Context.DataSettings)
        if check_selection(selected, size=1, typeid=NodeType.Command):
            node = self.study().node(selected[0])
            url = self.doc_url(node.title)
            debug_message("LinkToDoc: opening url", url)
            if url:
                QDesktopServices.openUrl(QUrl(url))

    @pyqtSlot(bool)
    def linktotranslator(self):
        """[Operations | LinkToTranslator] action's slot."""
        QDesktopServices.openUrl(QUrl(CFG.business_translation_url()))

    @pyqtSlot(bool)
    def duplicate(self):
        """[Edit | Duplicate] action's slot."""
        if self.isNullStudy():
            return

        selected = self.selected(Context.DataSettings)
        if check_selection(selected, size=1, typeid=NodeType.CutCopyItems):
            node = self.study().node(selected[0])
            new_nodes = to_list(self.study().duplicate(node))
            if new_nodes:
                self.update(autoSelect=new_nodes[-1],
                            context=Context.DataSettings)

    @pyqtSlot(bool)
    def copy(self):
        """[Edit | Copy] action's slot."""
        if self.isNullStudy():
            return

        selected = self.selected(Context.DataSettings)
        if check_selection(selected, size=1, typeid=NodeType.CutCopyItems):
            node = self.study().node(selected[0])
            cnt = self.study().copy(node)
            if cnt is not None:
                QApplication.clipboard().setText(cnt, QClipboard.Selection)
                QApplication.clipboard().setText(cnt, QClipboard.Clipboard)

    @pyqtSlot(bool)
    def cut(self):
        """[Edit | Cut] action's slot."""
        if self.isNullStudy():
            return

        selected = self.selected(Context.DataSettings)
        if check_selection(selected, size=1, typeid=NodeType.CutCopyItems):
            node = self.study().node(selected[0])
            cnt = self.study().cut(node)
            if cnt is not None:
                QApplication.clipboard().setText(cnt, QClipboard.Selection)
                QApplication.clipboard().setText(cnt, QClipboard.Clipboard)
            self.update()

    @pyqtSlot(bool)
    def paste(self):
        """[Edit | Paste] action's slot."""
        if self.isNullStudy():
            return

        selected = self.selected(Context.DataSettings)
        if check_selection(selected, size=1, typeid=NodeType.PasteItems):
            stage = self.study().node(selected[0])
            if get_node_type(stage) not in (NodeType.Stage,):
                stage = stage.stage

            cnt = self._clipboardText()
            if len(cnt):
                new_nodes = to_list(self.study().paste(stage, cnt))
                if new_nodes:
                    self.update(autoSelect=new_nodes[0],
                                context=Context.DataSettings)

    @pyqtSlot(bool)
    def delete(self):
        """[Edit | Delete] action's slot."""
        if self.isNullStudy():
            return

        active_view = self.workSpace().activeView()
        selected = self.selected(active_view)
        nodes = [self.study().node(i) for i in selected]
        nodes = [i for i in nodes if i is not None]

        is_active_case = False
        for n in nodes:
            if n == self.study().activeCase:
                is_active_case = True
                break

        if nodes and self.study().delete(nodes):
            if is_active_case:
                self._activateCase(self.study().history.current_case)
        self.update()

    @pyqtSlot(bool)
    def remove(self):
        """[Operations | Remove] action's slot."""
        if self.isNullStudy():
            return

        selected = self.selected(Context.DataFiles)
        if check_selection(selected, size=1, typeid=NodeType.Dir):
            directory = self.study().node(selected[0])
            self.study().removeDir(directory)

        self.update()

    @pyqtSlot(bool)
    def find(self):
        """[Edit | Find] action's slot."""
        self.workSpace().view(Context.DataSettings).find()

    @pyqtSlot(bool)
    def newCase(self):
        """[Operations | New case] action's slot."""
        if self.isNullStudy():
            return
        case = self.study().newCase()
        if case is not None:
            self.update(autoSelect=case, context=Context.Cases)

    @pyqtSlot(bool)
    def importCase(self):
        """[Operations | Import case] action's slot."""
        if self.isNullStudy():
            return
        case = self.study().importCase()
        if case is not None:
            self.update(autoSelect=case, context=Context.DataSettings)

    @pyqtSlot(bool)
    def exportCaseTest(self):
        """[Operations | Export case for a testcase] action's slot."""
        if self.isNullStudy():
            return
        active_view = self.workSpace().activeView()
        selected = self.selected(active_view)
        if check_selection(selected, size=1, typeid=NodeType.Case):
            node = self.study().node(selected[0])
            if self.study().exportCaseTest(node):
                self.update()

    @pyqtSlot(bool)
    def importCaseTest(self):
        """[Operations | Import a testcase] action's slot."""
        if self.isNullStudy():
            return
        case = self.study().importCaseTest()
        if case is not None:
            self.update(autoSelect=case, context=Context.DataSettings)

    @pyqtSlot(bool)
    def newStage(self):
        """[Operations | Add stage] action's slot."""
        if self.isNullStudy():
            return
        stage = self.study().newStage()
        if stage is not None:
            self.update(autoSelect=stage, context=Context.DataSettings)

    @pyqtSlot(bool)
    def importStage(self, force_text=False):
        """[Operations | Add stage from file] action's slot."""
        if self.isNullStudy():
            return
        stage = self.study().importStage(force_text)
        if stage is not None:
            self.update(autoSelect=stage, context=Context.DataSettings)

    @pyqtSlot(bool)
    def exportStage(self):
        """[Operations | Add stage from file] action's slot."""
        if self.isNullStudy():
            return
        selected = self.selected(Context.DataSettings)
        if check_selection(selected, size=1, typeid=NodeType.Stage):
            node = self.study().node(selected[0])
            if self.study().exportStage(node):
                self.update()

    @pyqtSlot(bool)
    def reRun(self):
        """[Operations | Re-Run] action's slot."""
        self.setWorkingMode(WorkingMode.HistoryMode)
        self.update(autoSelect=self.study().activeCase, context=Context.Cases)
        dashboard = self.view(Context.Dashboard)
        if dashboard is not None:
            dashboard.reRun()

    @pyqtSlot(bool)
    def showAll(self):
        """[Commands | Show all] action's slot."""
        wait_cursor(True)
        show_all_panel = ShowAllPanel(self)
        self.workSpace().panel(Panel.Edit).setEditor(show_all_panel)
        wait_cursor(False)

    @pyqtSlot(bool)
    def rename(self):
        """[Edit | Rename] action's slot."""
        active_view = self.workSpace().activeView()
        selected = self.selected(active_view)
        if check_selection(selected, size=1, typeid=NodeType.RenameItems):
            self.workSpace().edit(active_view, selected[0])

    @pyqtSlot(bool)
    # pragma pylint: disable=redefined-variable-type,too-many-nested-blocks
    def edit(self):
        """[Edit | Edit] and [Edit | View] actions' slot."""
        is_current = self.study().isCurrentCase()
        active_view = self.workSpace().activeView()
        if active_view in (Context.DataSettings,):
            selected = self.selected(Context.DataSettings)
            if check_selection(selected, size=1, typeid=NodeType.EditItems):
                node = self.study().node(selected[0])
                node_type = get_node_type(node)
                if node_type not in (NodeType.Stage,):
                    wait_cursor(True)
                    editor = None
                    if node_type == NodeType.Command:
                        editor = ParameterPanel(self)
                        editor.setCommand(node)
                    elif node_type == NodeType.Variable:
                        editor = VariablePanel(self)
                        editor.variable = node
                    else:
                        editor = CommentPanel(self)
                        editor.node = node
                    editor.setReadOnly(not is_current)
                    self.workSpace().panel(Panel.Edit).setEditor(editor)
                    wait_cursor(False)
                else:
                    if behavior().use_external_editor_stage:
                        external_editor = behavior().external_editor.strip()
                        if external_editor:
                            cmd = external_editor.split(" ")
                            try:
                                old_text = node.get_text()
                                file_name = self._mkTmpFile(old_text)
                                cmd.append(file_name)
                                if file_name and call(cmd) == 0:
                                    new_text = read_file(file_name)
                                    if is_current and new_text != old_text:
                                        self.study().editStage(node, new_text)
                                        self._updateActions()
                                else:
                                    message = translate("AsterStudy",
                                                        "Text editor error.")
                                    QMessageBox.critical(self.mainWindow(),
                                                         "AsterStudy", message)
                            except IOError:
                                message = translate("AsterStudy",
                                                    "Cannot edit stage.")
                                QMessageBox.critical(self.mainWindow(),
                                                     "AsterStudy", message)
                            try:
                                os.unlink(file_name)
                            except OSError:
                                pass
                        else:
                            message = translate("AsterStudy",
                                                "Text editor is not set.")
                            QMessageBox.critical(self.mainWindow(),
                                                 "AsterStudy",
                                                 message)
                    else:
                        editor = StageTextEditor(node, self)
                        editor.setReadOnly(not is_current)
                        self.workSpace().panel(Panel.Edit).setEditor(editor)
        elif active_view in (Context.DataFiles,):
            selected = self.selected(Context.DataFiles)
            if check_selection(selected, size=1, typeid=NodeType.Dir):
                node = self.study().node(selected[0])
                if is_current:
                    edit_directory(self, node)
            elif check_selection(selected, size=1, typeid=NodeType.Unit):
                node = self.study().node(selected[0])
                editor = UnitPanel(node, self)
                editor.setReadOnly(not is_current)
                self.workSpace().panel(Panel.Edit).setEditor(editor)

    @pyqtSlot(bool)
    def graphicalMode(self):
        """[Operations | Graphical mode] action's slot."""
        selected = self.selected(Context.DataSettings)
        if check_selection(selected, size=1, typeid=NodeType.Stage):
            node = self.study().node(selected[0])
            if self.study().setStageGraphicalMode(node):
                self.update()

    @pyqtSlot(bool)
    def textMode(self):
        """[Operations | Text mode] action's slot."""
        selected = self.selected(Context.DataSettings)
        if check_selection(selected, size=1, typeid=NodeType.Stage):
            node = self.study().node(selected[0])
            if self.study().setStageTextMode(node):
                self.update()

    @pyqtSlot(str)
    def addCommand(self, command_type):
        """
        Add a command to the study.

        Arguments:
            command_type (str): Type of the Command being added.
        """
        if self.isNullStudy():
            return
        selected = self.selected(Context.DataSettings)
        if check_selection(selected, size=1, typeid=NodeType.PasteItems):
            stage = self.study().node(selected[0])
            if get_node_type(stage) not in (NodeType.Stage,):
                stage = stage.stage
            command = self.study().addCommand(stage, command_type)
            if command is not None:
                self.update(autoSelect=command, context=Context.DataSettings)
                msg = translate("AsterStudy",
                                "Command with type '{}' successfully added")
                msg = msg.format(command_type)
                self.showMessage(msg)
                if behavior().auto_edit:
                    self.edit()

    @pyqtSlot(bool)
    def addVariable(self):
        """[Commands | Add variable] action's slot."""
        wait_cursor(True)
        panel = VariablePanel(self)
        self.workSpace().panel(Panel.Edit).setEditor(panel)
        wait_cursor(False)

    @pyqtSlot(bool)
    def editComment(self):
        """[Commands | Edit comment] action's slot."""
        if self.isNullStudy():
            return

        selected = self.selected(Context.DataSettings)
        if check_selection(selected, size=1, typeid=(NodeType.Command,
                                                     NodeType.Variable)):
            node = self.study().node(selected[0])
            wait_cursor(True)
            panel = CommentPanel(self)
            panel.node = node
            self.workSpace().panel(Panel.Edit).setEditor(panel)
            wait_cursor(False)

    @pyqtSlot(bool)
    def backUp(self):
        """[Operations | Back Up] action's slot."""
        if self.isNullStudy():
            return
        case = self.study().backUp()
        if case is not None:
            self.update()

    @pyqtSlot(bool)
    def copyAsCurrent(self):
        """[Operations | Copy as current] action's slot."""
        if self.isNullStudy():
            return

        active_view = self.workSpace().activeView()
        selected = self.selected(active_view)
        if selected is not None and len(selected) == 1:
            if selected[0].type == NodeType.Case:
                node = self.study().node(selected[0])

                if node is not None and self.study().copyAsCurrent(node):
                    self.update()

    @pyqtSlot(bool)
    def editDescription(self):
        """[Operations | Edit description] action's slot."""
        if self.isNullStudy():
            return

        active_view = self.workSpace().activeView()
        if active_view not in (Context.DataSettings, Context.Cases,
                               Context.Dashboard):
            return

        selected = self.selected(active_view)
        if check_selection(selected, size=1, typeid=NodeType.Case):
            wait_cursor(True)
            node = self.study().node(selected[0])
            self.setWorkingMode(WorkingMode.CaseMode)
            panel = CommentPanel(self)
            panel.node = node
            self.workSpace().panel(Panel.Edit).setEditor(panel)
            wait_cursor(False)

    @pyqtSlot(bool)
    def deleteResults(self):
        """[Operations | Delete results] action's slot."""
        if self.isNullStudy():
            return

        active_view = self.workSpace().activeView()
        selected = self.selected(active_view)
        if selected is not None and len(selected) == 1:
            if selected[0].type == NodeType.Case:
                ctr = Controller(translate("AsterStudy", "Delete results"),
                                 self)
                if ctr.controllerStart():
                    wait_cursor(True)
                    node = self.study().node(selected[0])
                    if node is not None and node.delete_dir():
                        self.update()
                    wait_cursor(False)
                    ctr.controllerCommit()

    @pyqtSlot(bool)
    def activateCase(self):
        """[Operations | View case] action's slot."""
        if self.isNullStudy():
            return

        active_view = self.workSpace().activeView()
        selected = self.selected(active_view)
        if selected is not None and len(selected) == 1:
            if selected[0].type == NodeType.Case:
                ctr = Controller(translate("AsterStudy", "Activate case"),
                                 self)
                if ctr.controllerStart():
                    wait_cursor(True)
                    node = self.study().node(selected[0])
                    self._activateCase(node)
                    self.setWorkingMode(WorkingMode.CaseMode)
                    wait_cursor(False)
                    ctr.controllerCommit()

    @pyqtSlot(bool)
    def showView(self):
        """Slot which is called when view is shown/hidden."""
        action = self.sender()
        context = action.data()
        if self.workSpace() is not None:
            self.workSpace().setViewVisible(context, action.isChecked())
            self._updateActions()

    @pyqtSlot(bool)
    def setupDirs(self):
        """[Operations | Set-up directories] action's slot."""
        if self.isNullStudy():
            return
        wait_cursor(True)
        self._activateCase(self.study().history.current_case)
        self.setWorkingMode(WorkingMode.CaseMode)
        editor = DirsPanel(self)
        self.workSpace().panel(Panel.Edit).setEditor(editor)
        wait_cursor(False)

    @pyqtSlot(bool)
    def browse(self):
        """[Operations | Browse] action's slot."""
        if self.isNullStudy():
            return
        selected = self.selected(Context.DataFiles)
        if check_selection(selected, size=1, typeid=NodeType.Dir):
            node = self.study().node(selected[0])
            path = node.directory
            QDesktopServices.openUrl(QUrl(path))
        if check_selection(selected, size=1, typeid=NodeType.Unit):
            node = self.study().node(selected[0])
            if node.filename is not None:
                path = os.path.dirname(node.filename)
                QDesktopServices.openUrl(QUrl(path))

    @pyqtSlot(bool)
    def addFile(self):
        """[Operations | Add file] action's slot."""
        selected = self.selected(Context.DataFiles)
        if check_selection(selected, size=1, typeid=NodeType.Stage):
            node = self.study().node(selected[0])
            editor = UnitPanel(node, self)
            self.workSpace().panel(Panel.Edit).setEditor(editor)

    @pyqtSlot(bool)
    def goToCommand(self):
        """[Operations | Go to] action's slot."""
        selected = self.selected(Context.DataFiles)
        if check_selection(selected, size=1, typeid=NodeType.Command):
            node = self.study().node(selected[0])
            self.update(autoSelect=node, context=Context.DataSettings)

    @pyqtSlot(bool)
    def embedFile(self):
        """[Operations | Embed / unembed file] action's slot."""
        action = self.sender()
        selected = self.selected(Context.DataFiles)
        if check_selection(selected, size=1, typeid=NodeType.Unit):
            node = self.study().node(selected[0])
            is_checked = action.isChecked()
            editor = UnitPanel(node, self)
            editor.embedded_check.setChecked(is_checked)

            if editor.embedded_check.isChecked() == is_checked:
                op_name = translate("AsterStudy", "Embed file") if is_checked \
                    else  translate("AsterStudy", "Unembed file")
                ctr = Controller(op_name, self)
                if ctr.controllerStart():
                    combo_index = editor.file_combo.currentIndex()
                    index = editor.file_combo.model().index(combo_index, 0)
                    filename = index.model().data(index, Qt.ToolTipRole)
                    editor.file_combo.model().transferFile(filename)
                    node.filename = filename
                    node.embedded = is_checked
                    ctr.controllerCommit()
                    self.study().commit(op_name)
                    self.update()

    def openFileInEditor(self, file_name, option_key, read_only=False,
                         popup=False, wait=False):
        """
        Opens the given file path in internal or external editor.
        It depends on preferences.

        Arguments:
            file_name (str): File path to edit.
            option key (str): Preference option's suffix.
            read_only (Optional[bool]). Read-only mode (only
                for internal editor). Defaults to *False*.
            popup (Optional[bool]): If *True*, editor is opened as a;
                standalone modal dialog; else editor is opened in panel.
                Defaults to *False*.
            wait (Optional[bool]). Wait for external editor to finish
                (only for external editor). Defaults to *False*.
        """
        if not os.path.exists(file_name):
            message = translate("AsterStudy", "File '{}' does not exist.")
            message = message.format(file_name)
            QMessageBox.critical(self.mainWindow(), "AsterStudy", message)
            return
        option_key = "use_external_editor_" + option_key
        if getattr(behavior(), option_key):
            external_editor = behavior().external_editor.strip()
            if external_editor:
                cmd = external_editor.split(" ")
                cmd.append(file_name)
                if wait:
                    result = call(cmd)
                else:
                    result = os.system(' '.join(cmd) + '&')
                if result != 0:
                    message = translate("AsterStudy",
                                        "Text editor error.")
                    QMessageBox.critical(self.mainWindow(),
                                         "AsterStudy", message)
            else:
                message = translate("AsterStudy",
                                    "Text editor is not set.")
                QMessageBox.critical(self.mainWindow(),
                                     "AsterStudy",
                                     message)
        else:
            file_size = os.path.getsize(file_name)
            size_limit_kb = behavior().file_size_limit
            if file_size > size_limit_kb * 1024:
                message = translate("AsterStudy",
                                    "File '{}' is quite big ({}).\n\nDo you "
                                    "confirm opening it in a text editor?")
                msize = translate("AsterStudy", "{} bytes").format(file_size)
                message = message.format(file_name, msize)
                ask = QMessageBox.question(self.mainWindow(), "AsterStudy",
                                           message,
                                           QMessageBox.Yes | QMessageBox.No,
                                           QMessageBox.Yes)
                if ask == QMessageBox.No:
                    return
            if popup:
                TextFileDialog(file_name, read_only, self.mainWindow()).exec_()
            else:
                self.setWorkingMode(WorkingMode.CaseMode)
                editor = TextFileEditor(file_name, self)
                editor.setReadOnly(read_only)
                self.workSpace().panel(Panel.Edit).setEditor(editor)

    @pyqtSlot(bool)
    def openInEditor(self):
        """[Operations | Open in editor] action's slot."""
        selected = self.selected(Context.DataFiles)
        if check_selection(selected, size=1, typeid=NodeType.Unit):
            node = self.study().node(selected[0])
            if node.filename is not None:
                self.openFileInEditor(node.filename, "data_file")

    @pyqtSlot(bool)
    def openInParavis(self):
        """[Operations | Open in ParaVis] action's slot."""
        not_implemented(self.mainWindow())

    @classmethod
    def preferencesMgr(cls):
        """
        Get preferences manager.

        Returns:
            object: Application's Preferences manager.

        Raises:
            NotImplementedError: The method should be implemented in
                sub-classes.
        """
        raise NotImplementedError("Method should be implemented in successors")

    def update(self, **kwargs):
        """
        Update application's status: widgets, actions, etc.

        Additional arguments can be passed, to perform specific actions:
            autoSelect: Automatically scroll data browser to given item
                and select it.

        Arguments:
            **kwargs: Keyword arguments.
        """
        self._updateWindows()
        if "autoSelect" in kwargs and "context" in kwargs:
            node = kwargs["autoSelect"]
            context = kwargs["context"]
            entity = Entity(node.uid)
            self.workSpace().ensureVisible(context, entity, True)
        self._updateActions()

    def updateTranslations(self):
        """
        Update translations in GUI elements.

        This function is called when "Use business oriented translations"
        option is switched via the `Preferences` dialog.
        """
        self._updateCommands()
        self.workSpace().view(Context.DataSettings).update()
        self.workSpace().panel(Panel.Edit).updateTranslations()

    @pyqtSlot(int, "QPoint")
    def showContextMenu(self, context, pos):
        """
        Show context menu.

        Arguments:
            context (int): Context requesting menu (see `Context`).
            pos (QPoint): Mouse cursor position.
        """
        self._updateActions()
        view = self.workSpace().view(context)
        if context is not Context.Unknown and view is not None:
            popup_mgr = ContextMenuMgr(self, context)
            popup_mgr.showContextMenu(view, pos)

    def canAddCommand(self):
        """
        Check if the command can be added to the selected stage.

        This method returns *True* if:

        - GUI is in the Case View;
        - Stage, Category or Command is selected;
        - Parent Stage is in the Graphical Mode.

        Returns:
            *True* if a command can be added to the selected stage;
            *False* otherwise.
        """
        result = False
        if self.study() and self.workingMode() == WorkingMode.CaseMode:
            selected = self.selected(Context.DataSettings)
            if check_selection(selected, size=1, typeid=NodeType.PasteItems):
                stage = self.study().node(selected[0])
                if stage is not None and \
                        get_node_type(stage) not in (NodeType.Stage,):
                    stage = stage.stage
                result = stage is not None and stage.is_graphical_mode()
        return result

    def chooseVersion(self):
        """
        Select version of code_aster to use.

        Returns:
            str: code_aster version.
        """
        result = None
        option = behavior().code_aster_version
        default_version = CFG.default_version
        versions = CFG.options("Versions")
        if not debug_mode():
            versions = [i for i in versions if i != "fake"]
        if option == 'default' or len(versions) < 2:
            result = default_version
        else: # 'ask' and there are more than 1 version
            idx = versions.index(default_version) \
                if default_version in versions else -1
            msg = translate("AsterStudy", "Choose code_aster version")
            choice, ok = QInputDialog.getItem(self.mainWindow(), "AsterStudy",
                                              msg, versions, idx, False)
            if ok:
                result = choice
        return result

    def doc_url(self, command):
        """
        Return the address of the documentation website.

        Returns:
            str: url of the code_aster website.
        """
        base_url = self.preferencesMgr().value("doc_base_url")
        return CATA.get_command_url(command, base_url)

    def hasParavis(self):
        """
        Check if SALOME ParaVis module is available.

        Default implementation always returns *False* (no ParaVis in
        standalone AsterStudy application).

        Returns:
            bool: *True* if ParaVis available; *False* otherwise.
        """
        return False

    def createMeshView(self, parent=None):
        """
        Create Mesh View widget to be inserted into central area of
        workspace.

        Default implementation creates dummy widget (no actual MeshView
        in standalone AsterStudy application).

        Arguments:
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
        """
        return MeshBaseView(parent)

    def _createMainWindow(self):
        """
        Initialize main window of application.

        This function is called as a part of GUI initialization procedure.

        Default implementation raises exception; the method should be
        implemented in successor classes.

        Raises:
            NotImplementedError: The method should be implemented in
                sub-classes.
        """
        raise NotImplementedError("Method should be implemented in successors")

    def _createWorkspace(self, parent_widget):
        """
        Create workspace.

        Arguments:
            parent_widget (QWidget): Parent widget.

        Returns:
            Workspace: Workspace object.

        See also:
            `workSpace()`
        """
        tbposition = behavior().workspace_tab_position
        workspace_state = self.preferencesMgr().value("workspace_state")
        work_space = Workspace(self, parent_widget, tab_position(tbposition))
        try:
            work_space.restoreState(workspace_state)
        except TypeError:
            pass
        work_space.modeChanged.connect(self._updateActions)
        work_space.viewChanged.connect(self._updateActions)
        work_space.selectionChanged.connect(self._selectionChanged)
        work_space.popupMenuRequest.connect(self.showContextMenu)
        work_space.itemChanged.connect(self._itemRenamed)
        work_space.itemActivated.connect(self._itemActivated)
        work_space.editModeActivated.connect(self._editMode)

        self._connectWorkspace()

        actionlist = [ActionType.Rename,
                      ActionType.Delete,
                      ActionType.Edit,
                      ActionType.View,
                      ActionType.Copy,
                      ActionType.Cut,
                      ActionType.Paste,
                      ActionType.Duplicate,
                      ActionType.LinkToDoc,
                      ActionType.LinkToTranslator,
                      ActionType.AddStage,
                      ActionType.ImportStage,
                      ActionType.ImportTextStage,
                      ActionType.ExportStage,
                      ActionType.ShowAll,
                      ActionType.AddVariable,
                      ActionType.EditComment,
                      ActionType.EditDescription,
                      ActionType.StageToGraphical,
                      ActionType.StageToText,
                      ActionType.ExportCaseTest,
                      ActionType.ReRun,
                      ActionType.Find,
                      ActionType.SetupDirs]
        for actionId in actionlist:
            action = self.action(actionId)
            view = work_space.view(Context.DataSettings)
            if action is not None:
                view.addAction(action)

        actionlist = [ActionType.Rename,
                      ActionType.Delete,
                      ActionType.AddCase,
                      ActionType.ImportCase,
                      ActionType.ImportCaseTest,
                      ActionType.ExportCaseTest,
                      ActionType.CopyAsCurrent,
                      ActionType.BackUp,
                      ActionType.EditDescription,
                      ActionType.DeleteResults,
                      ActionType.ActivateCase,
                      ActionType.SetupDirs]
        for actionId in actionlist:
            action = self.action(actionId)
            if action is not None:
                for ctx in [Context.Cases, Context.Dashboard]:
                    view = work_space.view(ctx)
                    view.addAction(action)

        actionlist = [ActionType.AddFile,
                      ActionType.Edit,
                      ActionType.View,
                      ActionType.Delete,
                      ActionType.EmbedFile,
                      ActionType.GoTo,
                      ActionType.OpenInEditor,
                      ActionType.OpenInParaVis,
                      ActionType.SetupDirs,
                      ActionType.Remove,
                      ActionType.Browse]
        for actionId in actionlist:
            action = self.action(actionId)
            view = work_space.view(Context.DataFiles)
            if action is not None:
                view.addAction(action)

        return work_space

    def _connectWorkspace(self):
        """Connect workspace to study."""
        if self.workSpace() is None:
            return

        if self.study() is None:
            return

        view = self.workSpace().view(Context.DataFiles)
        view.setModel(self.aster_study.dataFilesModel())

    def _setStudy(self, study):
        """
        Re-set current study.

        Arguments:
            study (Study): Study being set to GUI.
        """
        self.aster_study = study
        self._updateCommands()

    def _createActions(self):
        """
        Create actions.

        This function is called as a part of GUI initialization procedure.
        """
        tooltip = translate("AsterStudy", "Undo")
        shortcut = translate("AsterStudy", "Ctrl+Z")
        self.createAction(translate("AsterStudy", "&Undo"),
                          tooltip,
                          translate("AsterStudy", "Undo last operation"),
                          load_icon("as_pic_undo.png"),
                          shortcut,
                          self.undo,
                          ActionType.Undo,
                          self)

        undo_action = UndoAction(self)
        undo_action.setText(translate("AsterStudy", "Undo"))
        tooltip = preformat("{0} ({1})".format(tooltip, bold(shortcut)))
        undo_action.setToolTip(tooltip)
        undo_action.setShortcutHint(shortcut)
        undo_action.setStatusTip(translate("AsterStudy",
                                           "No operations to undo"))
        undo_action.setIcon(load_icon("as_pic_undo.png"))
        undo_action.setMessage(translate("AsterStudy", "Undo %s"))
        undo_action.setComment(translate("AsterStudy", "Undo %d actions"))
        undo_action.activated.connect(self.undo)
        self.actions[ActionType.UndoList] = undo_action

        tooltip = translate("AsterStudy", "Redo")
        shortcut = translate("AsterStudy", "Ctrl+Y")
        self.createAction(translate("AsterStudy", "&Redo"),
                          tooltip,
                          translate("AsterStudy",
                                    "Redo last undone operation"),
                          load_icon("as_pic_redo.png"),
                          shortcut,
                          self.redo,
                          ActionType.Redo,
                          self)

        redo_action = UndoAction(self)
        redo_action.setText(translate("AsterStudy", "Redo"))
        tooltip = preformat("{0} ({1})".format(tooltip, bold(shortcut)))
        redo_action.setToolTip(tooltip)
        redo_action.setShortcutHint(shortcut)
        redo_action.setStatusTip(translate("AsterStudy",
                                           "No operations to redo"))
        redo_action.setIcon(load_icon("as_pic_redo.png"))
        redo_action.setMessage(translate("AsterStudy", "Redo %s"))
        redo_action.setComment(translate("AsterStudy", "Redo %d actions"))
        redo_action.activated.connect(self.redo)
        self.actions[ActionType.RedoList] = redo_action

        self.createAction(translate("AsterStudy", "Document&ation"),
                          translate("AsterStudy", "Documentation"),
                          translate("AsterStudy",
                                    "Show documentation of selected command"),
                          load_icon("as_pic_help.png"),
                          translate("AsterStudy", "F1"),
                          self.linktodoc,
                          ActionType.LinkToDoc,
                          self,
                          Context.DataSettings)

        label = translate("AsterStudy", "Business-oriented language helper")
        self.createAction(label,
                          label,
                          translate("AsterStudy",
                                    "Open tool to suggest business-oriented "
                                    "translations"),
                          load_icon("as_pic_translate.png"),
                          None,
                          self.linktotranslator,
                          ActionType.LinkToTranslator,
                          self,
                          Context.DataSettings)

        self.createAction(translate("AsterStudy", "Dup&licate"),
                          translate("AsterStudy", "Duplicate"),
                          translate("AsterStudy",
                                    "Create a copy of selected object"),
                          load_icon("as_pic_duplicate.png"),
                          translate("AsterStudy", "Ctrl+D"),
                          self.duplicate,
                          ActionType.Duplicate,
                          self,
                          Context.DataSettings)

        self.createAction(translate("AsterStudy", "&Copy"),
                          translate("AsterStudy", "Copy"),
                          translate("AsterStudy",
                                    "Copy selected objects to the clipboard"),
                          load_icon("as_pic_copy.png"),
                          translate("AsterStudy", "Ctrl+C"),
                          self.copy,
                          ActionType.Copy,
                          self,
                          Context.DataSettings)

        self.createAction(translate("AsterStudy", "Cu&t"),
                          translate("AsterStudy", "Cut"),
                          translate("AsterStudy",
                                    "Cut selected objects to the clipboard"),
                          load_icon("as_pic_cut.png"),
                          translate("AsterStudy", "Ctrl+X"),
                          self.cut,
                          ActionType.Cut,
                          self,
                          Context.DataSettings)

        self.createAction(translate("AsterStudy", "&Paste"),
                          translate("AsterStudy", "Paste"),
                          translate("AsterStudy",
                                    "Paste objects from the clipboard"),
                          load_icon("as_pic_paste.png"),
                          translate("AsterStudy", "Ctrl+V"),
                          self.paste,
                          ActionType.Paste,
                          self,
                          Context.DataSettings)

        self.createAction(translate("AsterStudy", "&Delete"),
                          translate("AsterStudy", "Delete"),
                          translate("AsterStudy", "Remove selected objects"),
                          load_icon("as_pic_delete.png"),
                          translate("AsterStudy", "Del"),
                          self.delete,
                          ActionType.Delete,
                          self,
                          Context.DataSettings,
                          Context.DataFiles,
                          Context.Cases,
                          Context.Dashboard)

        self.createAction(translate("AsterStudy", "&Find"),
                          translate("AsterStudy", "Find"),
                          translate("AsterStudy", "Find objects in the study"),
                          load_icon("as_pic_search.png"),
                          translate("AsterStudy", "Ctrl+F"),
                          self.find,
                          ActionType.Find,
                          self,
                          Context.DataSettings)

        self.createAction(translate("AsterStudy", "&New Case"),
                          translate("AsterStudy", "New case"),
                          translate("AsterStudy",
                                    "Add an empty case to the study"),
                          load_icon("as_pic_new_case.png"),
                          translate("AsterStudy", "Ctrl+Shift+N"),
                          self.newCase,
                          ActionType.AddCase,
                          self,
                          Context.Cases,
                          Context.Dashboard)

        self.createAction(translate("AsterStudy", "&Import Case"),
                          translate("AsterStudy", "Import case"),
                          translate("AsterStudy",
                                    "Add a case by importing an export file"),
                          load_icon("as_pic_import_case.png"),
                          translate("AsterStudy", "Ctrl+Shift+I"),
                          self.importCase,
                          ActionType.ImportCase,
                          self,
                          Context.Cases,
                          Context.Dashboard)

        self.createAction(translate("AsterStudy", "Import a testcase"),
                          translate("AsterStudy", "Import a testcase"),
                          translate("AsterStudy",
                                    "Add a case by importing a testcase"),
                          load_icon("as_pic_import_case.png"),
                          translate("AsterStudy", "Ctrl+Shift+T"),
                          self.importCaseTest,
                          ActionType.ImportCaseTest,
                          self,
                          Context.Cases,
                          Context.Dashboard)

        self.createAction(translate("AsterStudy",
                                    "Export Case for a &testcase"),
                          translate("AsterStudy",
                                    "Export case for a testcase"),
                          translate("AsterStudy",
                                    "Export a case for a testcase"),
                          None,
                          None,
                          self.exportCaseTest,
                          ActionType.ExportCaseTest,
                          self,
                          Context.DataSettings,
                          Context.Cases,
                          Context.Dashboard)

        self.createAction(translate("AsterStudy", "&Add Stage"),
                          translate("AsterStudy", "Add stage"),
                          translate("AsterStudy",
                                    "Add an empty stage to the case"),
                          load_icon("as_pic_new_stage.png"),
                          translate("AsterStudy", "Ctrl+Shift+N"),
                          self.newStage,
                          ActionType.AddStage,
                          self,
                          Context.DataSettings)

        self.createAction(translate("AsterStudy", "&Copy As Current"),
                          translate("AsterStudy", "Copy as current"),
                          translate("AsterStudy",
                                    "Copy content of the selected case "
                                    "into the Current case"),
                          load_icon("as_pic_copy_as_current.png"),
                          None,
                          self.copyAsCurrent,
                          ActionType.CopyAsCurrent,
                          self,
                          Context.Cases,
                          Context.Dashboard)

        self.createAction(translate("AsterStudy", "&Back Up"),
                          translate("AsterStudy", "Back up"),
                          translate("AsterStudy",
                                    "Create backup copy of the Current case"),
                          load_icon("as_pic_back_up.png"),
                          None,
                          self.backUp,
                          ActionType.BackUp,
                          self,
                          Context.Cases,
                          Context.Dashboard)

        self.createAction(translate("AsterStudy", "Edit Desc&ription"),
                          translate("AsterStudy", "Edit description"),
                          translate("AsterStudy",
                                    "Edit description of the selected case"),
                          load_icon("as_pic_edit_description.png"),
                          translate("AsterStudy", "F4"),
                          self.editDescription,
                          ActionType.EditDescription,
                          self,
                          Context.DataSettings,
                          Context.Cases,
                          Context.Dashboard)

        self.createAction(translate("AsterStudy", "&Delete Results"),
                          translate("AsterStudy", "Delete results"),
                          translate("AsterStudy",
                                    "Remove results from the "
                                    "selected Run case"),
                          load_icon("as_pic_delete_results.png"),
                          None,
                          self.deleteResults,
                          ActionType.DeleteResults,
                          self,
                          Context.Cases,
                          Context.Dashboard)

        self.createAction(translate("AsterStudy", "&View Case (read-only)"),
                          translate("AsterStudy", "View case (read-only)"),
                          translate("AsterStudy",
                                    "View selected case (read-only)"),
                          load_icon("as_pic_view_case.png"),
                          None,
                          self.activateCase,
                          ActionType.ActivateCase,
                          self,
                          Context.Cases,
                          Context.Dashboard)

        self.createAction(translate("AsterStudy", "Re-&run"),
                          translate("AsterStudy", "Re-run"),
                          translate("AsterStudy",
                                    "Execute selected case "
                                    "with the previous parameters"),
                          load_icon("as_pic_run.png"),
                          None,
                          self.reRun,
                          ActionType.ReRun,
                          self,
                          Context.DataSettings)

        self.createAction(translate("AsterStudy", "&Add Stage from File"),
                          translate("AsterStudy", "Add stage from file"),
                          translate("AsterStudy",
                                    "Add a stage by importing a command file"),
                          load_icon("as_pic_import_stage.png"),
                          translate("AsterStudy", "Ctrl+Shift+I"),
                          self.importStage,
                          ActionType.ImportStage,
                          self,
                          Context.DataSettings)

        importTextStage = partial(self.importStage, force_text=True)
        self.createAction(translate("AsterStudy",
                                    "&Add Text Stage from File"),
                          translate("AsterStudy",
                                    "Add a text stage from a file"),
                          translate("AsterStudy",
                                    "Add a text stage by importing a "
                                    "command file"),
                          None,
                          None,
                          importTextStage,
                          ActionType.ImportTextStage,
                          self,
                          Context.DataSettings)

        self.createAction(translate("AsterStudy", "&Export Command File"),
                          translate("AsterStudy", "Export command file"),
                          translate("AsterStudy",
                                    "Export stage contents into "
                                    "a command file"),
                          load_icon("as_pic_export_stage.png"),
                          translate("AsterStudy", "Ctrl+Shift+E"),
                          self.exportStage,
                          ActionType.ExportStage,
                          self,
                          Context.DataSettings)

        self.createAction(translate("AsterStudy", "&Show All"),
                          translate("AsterStudy", "Show All"),
                          translate("AsterStudy",
                                    "Add a command from the catalogue"),
                          load_icon("as_pic_new_command.png"),
                          translate("AsterStudy", "Ctrl+Shift+A"),
                          self.showAll,
                          ActionType.ShowAll,
                          self,
                          Context.DataSettings)

        self.createAction(translate("AsterStudy", "Rena&me"),
                          translate("AsterStudy", "Rename"),
                          translate("AsterStudy", "Rename selected object"),
                          load_icon("as_pic_rename.png"),
                          translate("AsterStudy", "F2"),
                          self.rename,
                          ActionType.Rename,
                          self,
                          Context.DataSettings,
                          Context.Cases,
                          Context.Dashboard)

        self.createAction(translate("AsterStudy", "&Edit"),
                          translate("AsterStudy", "Edit"),
                          translate("AsterStudy", "Edit selected object"),
                          load_icon("as_pic_edit.png"),
                          translate("AsterStudy", "F4"),
                          self.edit,
                          ActionType.Edit,
                          self,
                          Context.DataSettings,
                          Context.DataFiles)

        self.createAction(translate("AsterStudy", "&View"),
                          translate("AsterStudy", "View"),
                          translate("AsterStudy", "View selected object"),
                          load_icon("as_pic_view.png"),
                          translate("AsterStudy", "F4"),
                          self.edit,
                          ActionType.View,
                          self,
                          Context.DataSettings,
                          Context.DataFiles)

        self.createAction(translate("AsterStudy", "&Graphical Mode"),
                          translate("AsterStudy", "Graphical mode"),
                          translate("AsterStudy",
                                    "Switch stage to the graphical mode"),
                          load_icon("as_pic_switch_to_graphical.png"),
                          translate("AsterStudy", "Ctrl+Shift+G"),
                          self.graphicalMode,
                          ActionType.StageToGraphical,
                          self,
                          Context.DataSettings)

        self.createAction(translate("AsterStudy", "&Text Mode"),
                          translate("AsterStudy", "Text mode"),
                          translate("AsterStudy",
                                    "Switch stage to the text mode"),
                          load_icon("as_pic_switch_to_text.png"),
                          translate("AsterStudy", "Ctrl+Shift+T"),
                          self.textMode,
                          ActionType.StageToText,
                          self,
                          Context.DataSettings)

        self.createAction(translate("AsterStudy", "Create &Variable"),
                          translate("AsterStudy", "Create Variable"),
                          translate("AsterStudy",
                                    "Create a python variable"),
                          load_icon("as_pic_new_variable.png"),
                          translate("AsterStudy", "Ctrl+Shift+V"),
                          self.addVariable,
                          ActionType.AddVariable,
                          self,
                          Context.DataSettings)

        self.createAction(translate("AsterStudy", "Edit &Comment"),
                          translate("AsterStudy", "Edit comment"),
                          translate("AsterStudy",
                                    "Edit comment for the selected object"),
                          load_icon("as_pic_edit_comment.png"),
                          translate("AsterStudy", "Ctrl+Shift+C"),
                          self.editComment,
                          ActionType.EditComment,
                          self,
                          Context.DataSettings)

        self.createAction(translate("AsterStudy", "Hide Unused"),
                          translate("AsterStudy", "Hide unused"),
                          translate("AsterStudy", "Hide unused keywords"),
                          load_icon_set("as_ico_eye.png"),
                          None,
                          None,
                          ActionType.HideUnused,
                          self)
        self.action(ActionType.HideUnused).setCheckable(True)
        self.action(ActionType.HideUnused).setVisible(False)

        self.createAction(translate("AsterStudy", "&Set-up Directories"),
                          translate("AsterStudy", "Set-up directories"),
                          translate("AsterStudy", "Set-up input and output "
                                    "directories of the case"),
                          load_icon("as_pic_setup_dirs.png"),
                          None,
                          self.setupDirs,
                          ActionType.SetupDirs,
                          self,
                          Context.DataSettings,
                          Context.DataFiles,
                          Context.Cases,
                          Context.Dashboard)

        self.createAction(translate("AsterStudy", "&Remove Directory"),
                          translate("AsterStudy", "Remove directory"),
                          translate("AsterStudy", "Remove directory and all "
                                    "enclosed files from the disk"),
                          load_icon("as_pic_remove.png"),
                          None,
                          self.remove,
                          ActionType.Remove,
                          self,
                          Context.DataFiles)

        self.createAction(translate("AsterStudy", "&Browse"),
                          translate("AsterStudy", "Browse"),
                          translate("AsterStudy",
                                    "Show selected object in the "
                                    "file explorer"),
                          load_icon("as_pic_browse.png"),
                          None,
                          self.browse,
                          ActionType.Browse,
                          self,
                          Context.DataFiles)

        self.createAction(translate("AsterStudy", "&Add File"),
                          translate("AsterStudy", "Add file"),
                          translate("AsterStudy",
                                    "Add a data file to the stage"),
                          load_icon("as_pic_new_file.png"),
                          None,
                          self.addFile,
                          ActionType.AddFile,
                          self,
                          Context.DataFiles)

        self.createAction(translate("AsterStudy", "&Go To"),
                          translate("AsterStudy", "Go to"),
                          translate("AsterStudy",
                                    "Go to the selected command"),
                          load_icon("as_pic_goto.png"),
                          translate("AsterStudy", "F2"),
                          self.goToCommand,
                          ActionType.GoTo,
                          self,
                          Context.DataFiles)

        self.createAction(translate("AsterStudy", "&Embedded"),
                          translate("AsterStudy", "Embedded"),
                          translate("AsterStudy",
                                    "Embed/Unembed selected data file"),
                          load_icon("as_pic_embed_file.png"),
                          None,
                          self.embedFile,
                          ActionType.EmbedFile,
                          self,
                          Context.DataFiles)
        self.action(ActionType.EmbedFile).setCheckable(True)

        self.createAction(translate("AsterStudy", "&Open In Editor"),
                          translate("AsterStudy", "Open in editor"),
                          translate("AsterStudy",
                                    "View selected data file in "
                                    "the text editor"),
                          load_icon("as_pic_open_in_editor.png"),
                          translate("AsterStudy", "F2"),
                          self.openInEditor,
                          ActionType.OpenInEditor,
                          self,
                          Context.DataFiles)

        self.createAction(translate("AsterStudy", "Open In &ParaVis"),
                          translate("AsterStudy", "Open in ParaVis"),
                          translate("AsterStudy",
                                    "View selected file in "
                                    "SALOME ParaVis module"),
                          load_icon("as_pic_open_in_paravis.png"),
                          translate("AsterStudy", "F2"),
                          self.openInParavis,
                          ActionType.OpenInParaVis,
                          self,
                          Context.DataFiles)

        # create action for each panel shown by workspace
        all_views = views()
        for view in all_views:
            title = view_title(view)
            status_tip = translate("AsterStudy", "Show/hide '{}' view")
            status_tip = status_tip.format(title)
            action = self.createAction(title, title, status_tip,
                                       None, None, self.showView, 0, self)
            action.setCheckable(True)
            action.setData(view)
            self.views_actions[view] = action

        # create action for each category of commands
        for category in CATA.get_categories("toolbar"):
            # get translation for category's title
            title = translate_category(category)
            list_action = ListAction(title,
                                     load_icon("as_pic_new_command.png"),
                                     self.mainWindow())
            tool_tip = translate("AsterStudy", "Category: {}")
            tool_tip = preformat(tool_tip.format(bold(title)))
            list_action.setToolTip(tool_tip)
            status_tip = translate("AsterStudy",
                                   "Add command from '{}' category")
            status_tip = status_tip.format(title)
            list_action.setStatusTip(status_tip)
            list_action.triggered.connect(self.addCommand)
            self.cmd_actions[category] = list_action

    def _createMenus(self):
        """
        Create menus.

        This function is called as a part of GUI initialization procedure.
        """

        # "Edit" menu
        menu_edit = self.createMenu(translate("AsterStudy", "&Edit"),
                                    -1, MenuGroup.Edit)
        self.addMenuAction(self.action(ActionType.Undo), menu_edit)
        self.addMenuAction(self.action(ActionType.Redo), menu_edit)
        self.addMenuAction(None, menu_edit)
        self.addMenuAction(self.action(ActionType.Copy), menu_edit)
        self.addMenuAction(self.action(ActionType.Cut), menu_edit)
        self.addMenuAction(self.action(ActionType.Paste), menu_edit)
        self.addMenuAction(None, menu_edit)
        self.addMenuAction(self.action(ActionType.Edit), menu_edit)
        self.addMenuAction(self.action(ActionType.View), menu_edit)
        self.addMenuAction(None, menu_edit)
        self.addMenuAction(self.action(ActionType.Rename), menu_edit)
        self.addMenuAction(self.action(ActionType.Duplicate), menu_edit)
        self.addMenuAction(self.action(ActionType.Delete), menu_edit)
        self.addMenuAction(None, menu_edit)
        self.addMenuAction(self.action(ActionType.Find), menu_edit)
        self.addMenuAction(None, menu_edit)
        self.addMenuAction(self.action(ActionType.LinkToDoc), menu_edit)

        # "View" menu
        menu_view = self.createMenu(translate("AsterStudy", "&View"),
                                    -1, MenuGroup.View)
        menu_panels = self.createMenu(translate("AsterStudy", "&Panels"),
                                      menu_view, 0)
        for action in self.views_actions.values():
            self.addMenuAction(action, menu_panels)
        self.addMenuAction(None, menu_view)
        self.addMenuAction(self.action(ActionType.HideUnused), menu_view)

        # "Operations" menu
        menu_operations = self.createMenu(translate("AsterStudy",
                                                    "&Operations"),
                                          -1, MenuGroup.Operations)
        self.addMenuAction(self.action(ActionType.AddCase), menu_operations)
        self.addMenuAction(self.action(ActionType.ImportCase), menu_operations)
        self.addMenuAction(self.action(ActionType.ImportCaseTest),
                           menu_operations)
        self.addMenuAction(None, menu_operations)
        self.addMenuAction(self.action(ActionType.ActivateCase),
                           menu_operations)
        self.addMenuAction(self.action(ActionType.ReRun),
                           menu_operations)
        self.addMenuAction(None, menu_operations)
        self.addMenuAction(self.action(ActionType.ExportCaseTest),
                           menu_operations)
        self.addMenuAction(self.action(ActionType.BackUp),
                           menu_operations)
        self.addMenuAction(self.action(ActionType.CopyAsCurrent),
                           menu_operations)
        self.addMenuAction(None, menu_operations)
        self.addMenuAction(self.action(ActionType.EditDescription),
                           menu_operations)
        self.addMenuAction(self.action(ActionType.DeleteResults),
                           menu_operations)
        self.addMenuAction(None, menu_operations)
        self.addMenuAction(self.action(ActionType.SetupDirs),
                           menu_operations)
        self.addMenuAction(self.action(ActionType.Remove), menu_operations)
        self.addMenuAction(None, menu_operations)
        self.addMenuAction(self.action(ActionType.AddStage), menu_operations)
        self.addMenuAction(self.action(ActionType.ImportStage),
                           menu_operations)
        self.addMenuAction(self.action(ActionType.ImportTextStage),
                           menu_operations)
        self.addMenuAction(self.action(ActionType.ExportStage),
                           menu_operations)
        self.addMenuAction(self.action(ActionType.StageToGraphical),
                           menu_operations)
        self.addMenuAction(self.action(ActionType.StageToText),
                           menu_operations)
        self.addMenuAction(None, menu_operations)
        self.addMenuAction(None, menu_operations)
        self.addMenuAction(self.action(ActionType.AddFile),
                           menu_operations)
        self.addMenuAction(self.action(ActionType.EmbedFile),
                           menu_operations)
        self.addMenuAction(self.action(ActionType.Browse),
                           menu_operations)
        self.addMenuAction(self.action(ActionType.GoTo),
                           menu_operations)
        self.addMenuAction(None, menu_operations)
        self.addMenuAction(self.action(ActionType.OpenInEditor),
                           menu_operations)
        self.addMenuAction(self.action(ActionType.OpenInParaVis),
                           menu_operations)
        self.addMenuAction(None, menu_operations)
        self.addMenuAction(self.action(ActionType.LinkToTranslator),
                           menu_operations)

        # "Commands" menu
        menu_commands = self.createMenu(translate("AsterStudy", "&Commands"),
                                        -1, MenuGroup.Commands)
        self.addMenuAction(self.action(ActionType.AddVariable), menu_commands)
        self.addMenuAction(None, menu_commands)
        self.addMenuAction(self.action(ActionType.ShowAll), menu_commands)
        self.addMenuAction(None, menu_commands)
        self.addMenuAction(self.action(ActionType.EditComment), menu_commands)
        self.addMenuAction(None, menu_commands)
        for action in self.cmd_actions.values():
            self.addMenuAction(action, menu_commands)

        # "Test" menu
        if debug_mode():
            self.gui_tester = GuiTester(self)
            actions = self.gui_tester.actions()
            if actions:
                menu_test = self.createMenu("&Test", -1, MenuGroup.Test)
                for action in actions:
                    self.addMenuAction(action, menu_test)

    def _createToolbars(self):
        """
        Create toolbars.

        This function is called as a part of GUI initialization procedure.
        """

        # "Operations" toolbar
        toolbar_ops = self.createToolbar(translate("AsterStudy",
                                                   "&Operations"),
                                         "OperationsToolbar")
        self.addToolbarAction(self.action(ActionType.UndoList), toolbar_ops)
        self.addToolbarAction(self.action(ActionType.RedoList), toolbar_ops)
        self.addToolbarAction(None, toolbar_ops)
        self.addToolbarAction(self.action(ActionType.Copy), toolbar_ops)
        self.addToolbarAction(self.action(ActionType.Cut), toolbar_ops)
        self.addToolbarAction(self.action(ActionType.Paste), toolbar_ops)
        self.addToolbarAction(self.action(ActionType.Duplicate), toolbar_ops)
        self.addToolbarAction(None, toolbar_ops)
        self.addToolbarAction(self.action(ActionType.Edit), toolbar_ops)
        self.addToolbarAction(self.action(ActionType.View), toolbar_ops)
        self.addToolbarAction(self.action(ActionType.Delete), toolbar_ops)
        self.addToolbarAction(None, toolbar_ops)
        self.addToolbarAction(self.action(ActionType.HideUnused), toolbar_ops)
        self.addToolbarAction(self.action(ActionType.LinkToDoc), toolbar_ops)
        self.addToolbarAction(self.action(ActionType.LinkToTranslator),
                              toolbar_ops)
        self.addToolbarAction(None, toolbar_ops)
        self.addToolbarAction(self.action(ActionType.AddCase), toolbar_ops)
        self.addToolbarAction(self.action(ActionType.ImportCase), toolbar_ops)
        self.addToolbarAction(self.action(ActionType.AddStage), toolbar_ops)
        self.addToolbarAction(self.action(ActionType.ImportStage), toolbar_ops)
        self.addToolbarAction(self.action(ActionType.ExportStage), toolbar_ops)
        self.addToolbarAction(None, toolbar_ops)
        self.addToolbarAction(self.action(ActionType.StageToGraphical),
                              toolbar_ops)
        self.addToolbarAction(self.action(ActionType.StageToText), toolbar_ops)
        self.addToolbarAction(None, toolbar_ops)
        self.addToolbarAction(self.action(ActionType.ReRun), toolbar_ops)
        self.addToolbarAction(None, toolbar_ops)
        self.addToolbarAction(self.action(ActionType.AddFile), toolbar_ops)
        self.addToolbarAction(self.action(ActionType.GoTo), toolbar_ops)

        # "Commands" toolbar
        toolbar_cmds = self.createToolbar(translate("AsterStudy", "&Commands"),
                                          "CommandsToolbar")
        self.addToolbarAction(self.action(ActionType.AddVariable),
                              toolbar_cmds)
        self.addToolbarAction(self.action(ActionType.ShowAll), toolbar_cmds)
        self.addToolbarAction(None, toolbar_cmds)
        self.addToolbarAction(self.action(ActionType.EditComment),
                              toolbar_cmds)
        self.addToolbarAction(None, toolbar_cmds)
        for action in self.cmd_actions.values():
            self.addToolbarAction(action, toolbar_cmds)

    def _updateWindows(self):
        """Update windows: data browser, etc."""
        if self.workSpace() is not None:
            self.workSpace().updateViews()

    # pragma pylint: disable=too-many-locals, too-many-statements
    def _updateActions(self):
        """Update state of actions, menus, toolbars, etc."""
        has_study = self.study() is not None
        is_current = not has_study or self.study().isCurrentCase()
        is_history_mode = has_study and \
            self.workingMode() == WorkingMode.HistoryMode
        is_case_mode = has_study and \
            self.workingMode() == WorkingMode.CaseMode
        active_view = self.workSpace().activeView() \
            if has_study and self.workSpace() is not None else None
        current_case = self.study().history.current_case if has_study else None
        selected = self.selected(active_view) if has_study else []
        is_single = len(selected) < 2
        sel_obj = selected[0] if len(selected) == 1 else None
        sel_node = self.study().node(sel_obj) \
            if has_study and sel_obj is not None else None
        sel_type = sel_obj.type if sel_obj is not None else NodeType.Unknown
        sel_types = NodeType.Unknown
        for s in selected:
            sel_types = sel_types | s.type
        is_gr_mode = False
        is_txt_mode = False
        is_text_stage = False
        if sel_type == NodeType.Stage:
            is_text_stage = sel_node.is_text_mode()
            is_gr_mode = sel_node.can_use_graphical_mode()
            is_txt_mode = sel_node.can_use_text_mode(False)

        is_current_selected = False
        for s in selected:
            if self.study().node(s) == current_case:
                is_current_selected = True
                break

        is_not_current_selected = False
        for s in selected:
            if s.type == NodeType.Case and \
                    self.study().node(s) != current_case:
                is_not_current_selected = True
                break

        # Undo
        undo_list = self.study().undoMessages() if has_study else []
        self.action(ActionType.UndoList).setItems(undo_list)
        self.action(ActionType.Undo).setEnabled(len(undo_list) > 0)
        self.action(ActionType.UndoList).setEnabled(len(undo_list) > 0)
        self.action(ActionType.Undo).setVisible(has_study)
        self.action(ActionType.UndoList).setVisible(has_study)

        # Redo
        redo_list = self.study().redoMessages() if has_study else []
        self.action(ActionType.RedoList).setItems(redo_list)
        self.action(ActionType.Redo).setEnabled(len(redo_list) > 0)
        self.action(ActionType.RedoList).setEnabled(len(redo_list) > 0)
        self.action(ActionType.Redo).setVisible(has_study)
        self.action(ActionType.RedoList).setVisible(has_study)

        # LinkToDoc
        is_ok = active_view in (Context.DataSettings,) and \
            sel_type in (NodeType.Command,) and is_current
        self.action(ActionType.LinkToDoc).setVisible(is_case_mode)
        self.action(ActionType.LinkToDoc).setEnabled(is_ok)

        # Duplicate
        is_ok = active_view in (Context.DataSettings,) and sel_types and \
            (sel_types & NodeType.CutCopyItems == sel_types) and is_current
        self.action(ActionType.Duplicate).setVisible(is_case_mode)
        self.action(ActionType.Duplicate).setEnabled(is_ok)

        # Copy & Cut
        is_ok = active_view in (Context.DataSettings,) and sel_types and \
            (sel_types & NodeType.CutCopyItems == sel_types) and is_current
        self.action(ActionType.Copy).setVisible(is_case_mode)
        self.action(ActionType.Copy).setEnabled(is_ok)
        self.action(ActionType.Cut).setVisible(is_case_mode)
        self.action(ActionType.Cut).setEnabled(is_ok)

        # Paste
        is_ok = active_view in (Context.DataSettings,) and \
            (sel_type & NodeType.PasteItems) and \
            is_current and len(self._clipboardText())
        self.action(ActionType.Paste).setVisible(is_case_mode)
        self.action(ActionType.Paste).setEnabled(is_ok)

        # Delete
        is_ok1 = active_view in (Context.DataSettings,) and sel_types and \
            (sel_types & NodeType.DeleteItems == sel_types) and is_current
        is_ok2 = active_view in (Context.Cases, Context.Dashboard) and \
            check_selection(selected, typeid=NodeType.Case) and \
            not is_current_selected
        is_ok3 = active_view in (Context.DataFiles,) and \
            is_current and sel_type in (NodeType.Dir, NodeType.Unit) and \
            sel_node.deletable
        self.action(ActionType.Delete).setVisible(has_study)
        self.action(ActionType.Delete).setEnabled(is_ok1 or is_ok2 or is_ok3)

        # Find
        is_ok = active_view in (Context.DataSettings,)
        self.action(ActionType.Find).setVisible(is_case_mode)
        self.action(ActionType.Find).setEnabled(is_ok)

        # Rename
        is_ok1 = active_view in (Context.DataSettings,) and \
            check_selection(selected, size=1, flags=Qt.ItemIsEditable) \
            and is_single and is_current
        is_ok2 = active_view in (Context.Cases, Context.Dashboard) and \
            check_selection(selected, size=1, typeid=NodeType.Case) and \
            not is_current_selected and is_single
        self.action(ActionType.Rename).setVisible(has_study)
        self.action(ActionType.Rename).setEnabled(is_ok1 or is_ok2)

        # Edit / View
        is_ok1 = active_view in (Context.DataSettings, Context.DataFiles)
        is_ok2 = active_view in (Context.DataSettings,) and \
            ((sel_type & NodeType.CutCopyItems) or is_text_stage)
        is_ok3 = active_view in (Context.DataFiles,) and \
            sel_type in (NodeType.Unit, NodeType.Dir)
        is_ok4 = active_view in (Context.DataFiles,) and \
            sel_type in (NodeType.Unit,)
        self.action(ActionType.Edit).setVisible(is_ok1 and is_current)
        self.action(ActionType.View).setVisible(is_ok1 and not is_current)
        self.action(ActionType.Edit).setEnabled((is_ok2 or is_ok3) and \
                                                is_current)
        self.action(ActionType.View).setEnabled((is_ok2 or is_ok4) and \
                                                not is_current)

        # Add new stage, Add stage from file
        is_ok = active_view in (Context.DataSettings,) and is_current
        self.action(ActionType.AddStage).setVisible(is_case_mode)
        self.action(ActionType.AddStage).setEnabled(is_ok)
        self.action(ActionType.ImportStage).setVisible(is_case_mode)
        self.action(ActionType.ImportStage).setEnabled(is_ok)
        self.action(ActionType.ImportTextStage).setVisible(is_case_mode)
        self.action(ActionType.ImportTextStage).setEnabled(is_ok)

        # Export stage
        is_ok = active_view in (Context.DataSettings,) and \
            sel_type in (NodeType.Stage,)
        self.action(ActionType.ExportStage).setVisible(is_case_mode)
        self.action(ActionType.ExportStage).setEnabled(is_ok)

        # Show all
        is_ok = is_case_mode and self.study().hasStages() and is_current
        self.action(ActionType.ShowAll).setVisible(is_case_mode)
        self.action(ActionType.ShowAll).setEnabled(is_ok)

        # Add variable
        is_ok = is_case_mode and self.study().hasStages() and is_current
        self.action(ActionType.AddVariable).setVisible(is_case_mode)
        self.action(ActionType.AddVariable).setEnabled(is_ok)

        # Edit comment
        is_ok = active_view in (Context.DataSettings,) and \
            sel_type in (NodeType.Command, NodeType.Variable) and is_current
        self.action(ActionType.EditComment).setVisible(is_case_mode)
        self.action(ActionType.EditComment).setEnabled(is_ok)

        # Graphical mode
        is_ok = active_view in (Context.DataSettings,) \
            and is_gr_mode and is_single and is_current
        self.action(ActionType.StageToGraphical).setVisible(is_case_mode)
        self.action(ActionType.StageToGraphical).setEnabled(is_ok)

        # Text mode
        is_ok = active_view in (Context.DataSettings,) \
            and is_txt_mode and is_single and is_current
        self.action(ActionType.StageToText).setVisible(is_case_mode)
        self.action(ActionType.StageToText).setEnabled(is_ok)

        # Run case
        is_ok = active_view in (Context.DataSettings,) and \
            is_current_selected and current_case.can_be_ran() and \
            self.study().url() is not None
        self.action(ActionType.ReRun).setVisible(is_case_mode)
        self.action(ActionType.ReRun).setEnabled(is_ok)

        # Add case
        self.action(ActionType.AddCase).setVisible(is_history_mode)
        self.action(ActionType.AddCase).setEnabled(is_history_mode
                                                   and is_current)

        # Import case
        self.action(ActionType.ImportCase).setVisible(is_history_mode)
        self.action(ActionType.ImportCase).setEnabled(is_history_mode
                                                      and is_current)

        # Import case from a testcase
        self.action(ActionType.ImportCaseTest).setVisible(is_history_mode)
        self.action(ActionType.ImportCaseTest).setEnabled(is_history_mode
                                                          and is_current)

        # Back up
        self.action(ActionType.BackUp).setVisible(has_study)

        # Export case for testcase
        self.action(ActionType.ExportCaseTest).setVisible(has_study)
        is_ok = has_study and sel_type in (NodeType.Case,)
        self.action(ActionType.ExportCaseTest).setEnabled(is_ok)

        # Copy as current
        self.action(ActionType.CopyAsCurrent).setVisible(is_history_mode)
        is_ok = is_history_mode and is_not_current_selected
        self.action(ActionType.CopyAsCurrent).setEnabled(is_ok)

        # Edit case's description
        self.action(ActionType.EditDescription).setVisible(has_study)
        is_ok = has_study and is_not_current_selected
        self.action(ActionType.EditDescription).setEnabled(is_ok)

        # Delete results
        is_ok = active_view in (Context.Cases, Context.Dashboard) and \
            check_selection(selected, typeid=NodeType.Case) and \
            not is_current_selected
        if is_ok and self.study() is not None:
            node = self.study().node(selected[0])
            is_ok = node is not None
            if is_ok:
                is_ok = os.path.isdir(node.folder) and \
                        not node.is_used_by_others()
        self.action(ActionType.DeleteResults).setVisible(has_study)
        self.action(ActionType.DeleteResults).setEnabled(is_ok)

        # Activate case
        action = self.action(ActionType.ActivateCase)
        action.setVisible(is_history_mode)
        action.setEnabled(is_history_mode)
        if is_current_selected:
            action.setText(translate("AsterStudy", "&Edit Case"))
            action.setToolTip(translate("AsterStudy", "Edit case"))
            action.setStatusTip(translate("AsterStudy",
                                          "Edit selected Case"))
        else:
            action.setText(translate("AsterStudy", "&View Case (read-only)"))
            action.setToolTip(translate("AsterStudy", "View case (read-only)"))
            action.setStatusTip(translate("AsterStudy",
                                          "View selected case "
                                          "(read-only)"))

        # Set-up input / output directories
        self.action(ActionType.SetupDirs).setVisible(has_study)
        is_ok = has_study and is_current_selected
        self.action(ActionType.SetupDirs).setEnabled(is_ok)

        # Remove directory
        is_ok = active_view in (Context.DataFiles,) and is_current \
            and sel_type in (NodeType.Dir,) and sel_node.removable
        self.action(ActionType.Remove).setVisible(is_case_mode)
        self.action(ActionType.Remove).setEnabled(is_ok)

        # Add file
        is_ok = active_view in (Context.DataFiles,) and is_current \
            and is_text_stage
        self.action(ActionType.AddFile).setVisible(is_case_mode)
        self.action(ActionType.AddFile).setEnabled(is_ok)

        # Embed/Unembed file
        is_ok = active_view in (Context.DataFiles,) and is_current and \
            sel_type in (NodeType.Unit,) and sel_node.valid and \
            not sel_node.is_reference and sel_node.embedded is not None
        is_checked = active_view in (Context.DataFiles,) and \
            sel_type in (NodeType.Unit,) and sel_node.embedded is not None \
            and sel_node.embedded
        self.action(ActionType.EmbedFile).setVisible(is_case_mode)
        self.action(ActionType.EmbedFile).setEnabled(is_ok)
        self.action(ActionType.EmbedFile).setChecked(is_checked)

        # Go To
        is_ok = active_view in (Context.DataFiles,) and \
            sel_type in (NodeType.Command,)
        self.action(ActionType.GoTo).setVisible(is_case_mode)
        self.action(ActionType.GoTo).setEnabled(is_ok)

        # Browse
        is_ok1 = active_view in (Context.DataFiles,) and \
            sel_type in (NodeType.Dir,)
        is_ok2 = active_view in (Context.DataFiles,) and \
            sel_type in (NodeType.Unit,) and sel_node.valid
        self.action(ActionType.Browse).setVisible(is_case_mode)
        self.action(ActionType.Browse).setEnabled(is_ok1 or is_ok2)

        # Open in editor
        is_ok = active_view in (Context.DataFiles,) and \
            sel_type in (NodeType.Unit,) and sel_node.for_editor
        self.action(ActionType.OpenInEditor).setVisible(is_case_mode)
        self.action(ActionType.OpenInEditor).setEnabled(is_ok)

        # Open in Paravis
        is_ok = active_view in (Context.DataFiles,) and \
            sel_type in (NodeType.Unit,) and sel_node.for_paravis \
            and self.hasParavis()
        self.action(ActionType.OpenInParaVis).setVisible(is_case_mode)
        self.action(ActionType.OpenInParaVis).setEnabled(is_ok)

        # Commands
        is_ok = self.canAddCommand() and is_current
        for action in self.cmd_actions.values():
            action.setVisible(is_case_mode and action.count() > 0)
            action.setEnabled(is_ok)

        # Panels menu
        panels_menu = self.menu(translate("AsterStudy", "&View"),
                                translate("AsterStudy", "&Panels"))
        if panels_menu is not None:
            panels_menu.menuAction().setVisible(has_study)

        # Views
        for action in self.views_actions.values():
            context = action.data()
            is_ok = self.workSpace() is not None and \
                self.workSpace().isViewAvailable(context)
            action.setVisible(is_ok)
            is_ok = self.workSpace() is not None and \
                self.workSpace().isViewVisible(context)
            action.blockSignals(True)
            action.setChecked(is_ok)
            action.blockSignals(False)

        # Update debug actions
        if debug_mode():
            self.gui_tester.updateActions()

    def _updateCommands(self):
        """
        Re-fill the categories actions according to the used code_aster
        version.
        """
        for category, action in self.cmd_actions.iteritems():
            # clear action
            action.clear()
            if self.study() is not None:
                # get commands from category
                commands = CATA.get_category(category)
                for item in commands:
                    # get translation for command
                    title = translate_command(item)
                    item_action = action.addItem(title, item)
                    tip = ": {title} ({name})" if title != item else ": {name}"
                    tip = translate("AsterStudy", "Add command") + tip
                    tool_tip = preformat(tip.format(title=italic(title),
                                                    name=bold(item)))
                    item_action.setToolTip(tool_tip)
                    status_tip = tip.format(title=title, name=item)
                    item_action.setStatusTip(status_tip)

    @pyqtSlot(Entity, str)
    def _itemRenamed(self, entity, value):
        """
        Called when object is renamed.

        Arguments:
            entity (Entity): Selection entity.
            value (str): New item's value.
        """
        if self.isNullStudy():
            return

        node = self.study().node(entity)
        self.study().rename(node, value)
        self.update()

    @pyqtSlot(Entity, int)
    def _itemActivated(self, entity, context):
        """
        Called when object is activated (e.g. double-clicked in a view).

        Arguments:
            entity (Entity): Selection entity.
            context (int): Selection context (see `Context`).
        """
        if context in (Context.DataSettings,):
            if self.action(ActionType.Edit).isEnabled():
                self.edit()
        elif context in (Context.DataFiles,):
            selected = self.selected(Context.DataFiles)
            if check_selection(selected, size=1, typeid=NodeType.Dir):
                node = self.study().node(selected[0])
                if self.study().isCurrentCase():
                    edit_directory(self, node)
            elif check_selection(selected, size=1, typeid=(NodeType.Stage,
                                                           NodeType.Unit)):
                node = self.study().node(selected[0])
                editor = UnitPanel(node, self)
                editor.setReadOnly(not self.study().isCurrentCase())
                self.workSpace().panel(Panel.Edit).setEditor(editor)
            elif check_selection(selected, size=1, typeid=NodeType.Command):
                node = self.study().node(selected[0])
                self.update(autoSelect=node,
                            context=Context.DataSettings)
        elif context in (Context.Dashboard, Context.Cases):
            self.activateCase()

    @pyqtSlot()
    def _editMode(self):
        """Activate edit mode."""
        if self.study() is not None:
            case = self.study().history.current_case
            self._activateCase(case)

    def _selectionChanged(self, context):
        """
        Called when selection is changed.

        Emits `selectionChanged(int)` signal.

        Arguments:
            context (int): Selection context (see `Context`).
        """
        self._updateActions()

        target = None
        if context == Context.Dashboard:
            target = Context.Cases
        elif context == Context.Cases:
            target = Context.Dashboard
        elif context == Context.DataSettings:
            target = Context.Information

        if target is not None:
            self.workSpace().setSelected(target,
                                         self.workSpace().selected(context))
        self.selectionChanged.emit(context)

    def _mkTmpFile(self, text):
        """
        Create temporary file with the text.

        Arguments:
            text: text to be stored.

        Returns:
            created file name.
        """
        file_name = ""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_f:
            tmp_f.write(text)
            file_name = tmp_f.name
        return file_name

    def _clipboardText(self):
        """
        Gets the current text from clipboard.

        Returns:
            (str): Clipboard text string
        """
        txt = ''
        cb = QApplication.clipboard()
        if cb.mimeData(QClipboard.Clipboard).hasText():
            txt = cb.mimeData(QClipboard.Clipboard).text()
        elif cb.mimeData(QClipboard.Selection).hasText():
            if PASTE_TREAT_SELECTION_BUFFER:
                txt = cb.mimeData(QClipboard.Selection).text()
        return txt

    def _activateCase(self, case):
        """
        Activate specified case.

        Arguments:
            case (Case): Case to be active.
        """
        if self.isNullStudy() or case is None:
            return

        if self.study().activeCase != case:
            self.study().activeCase = case
            self.update()
