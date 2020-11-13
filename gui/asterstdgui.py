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
Standalone GUI
--------------

Implementation of GUI for standalone AsterStudy application.

"""

from __future__ import unicode_literals

import uuid

from PyQt5 import Qt as Q

from common import (CFG, clean_text, debug_mode, get_file_name, load_icon,
                    translate, version)
from . import ActionType, Context, MenuGroup
from . astergui import AsterGui
from . behavior import behavior
from . controller import Controller
from . guitest import DebugWidget
from . prefdlg import PrefDlg
from . prefmanager import PreferencesMgr, toolbar_style, tab_position
from . study import Study, study_extension
from . widgets import AboutDlg, MainWindow

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class AsterStdGui(AsterGui):
    """GUI for standalone AsterStudy application."""

    _prefMgr = None
    gui = None

    def __init__(self):
        """Create GUI wrapper for standalone AsterStudy application."""
        super(AsterStdGui, self).__init__()
        self.menus = {}
        self.toolbars = {}
        self.console = None
        AsterStdGui.gui = self

    @Q.pyqtSlot(bool)
    def newStudy(self):
        """[File | New] action's slot."""
        chosen_version = self.chooseVersion()
        if not chosen_version:
            return

        if not self.closeStudy():
            return

        self._setStudy(Study(self, version=chosen_version))

        self._connectWorkspace()
        self.workSpace().activate(True)

        self.update(autoSelect=self.study().activeCase, context=Context.Cases)

    @Q.pyqtSlot(bool)
    def openStudy(self):
        """[File | Open] action's slot."""
        can_close = False
        if self.study():
            can_close = self._canClose()
            if not can_close:
                return

        title = translate("AsterStudy", "Open File")
        file_filter = translate("AsterStudy", "Study files")
        file_filter = file_filter + " (*.%s)" % study_extension()

        file_name = get_file_name(1, self.mainWindow(),
                                  title, "", file_filter,
                                  study_extension())
        if file_name:
            if can_close:
                self._close()
            if not self.load(file_name):
                message = translate("AsterStudy", "Cannot load study.")
                Q.QMessageBox.critical(self.mainWindow(),
                                       "AsterStudy",
                                       message)

    @Q.pyqtSlot(bool)
    def saveStudy(self):
        """
        [File | Save] action's slot.

        Returns:
            bool: *True* if study is successfully saved; *False*
            otherwise.
        """
        null_study_msg = translate("AsterStudy", "Cannot save null study.")
        if self.isNullStudy(null_study_msg):
            return False
        if not self.study().isModified():
            msg = translate("AsterStudy", "Cannot save not modified study.")
            Q.QMessageBox.critical(self.mainWindow(), "AsterStudy", msg)
            return False

        if not self.study().url():
            return self.saveStudyAs()

        self.study().save()
        self._updateActions()

        return True

    @Q.pyqtSlot(bool)
    def saveStudyAs(self):
        """
        [File | Save As] action's slot.

        Returns:
            bool: *True* if study is successfully saved; *False*
            otherwise.
        """
        null_study_msg = translate("AsterStudy", "Cannot save null study.")
        if self.isNullStudy(null_study_msg):
            return False
        title = translate("AsterStudy", "Save File")
        file_filter = translate("AsterStudy", "Study files")
        file_filter = file_filter + " (*.%s)" % study_extension()
        url = self.study().url() if self.study().url() \
            else self.study().name()

        file_name = get_file_name(0, self.mainWindow(),
                                  title, url, file_filter,
                                  study_extension())
        if not file_name:
            return False

        self.study().saveAs(file_name)
        self._updateActions()

        return True

    @Q.pyqtSlot(bool)
    def closeStudy(self):
        """
        [File | Close] action's slot.

        Returns:
            bool: *True* if study is successfully closed; *False*
            otherwise.
        """
        if not self.study():
            return True
        result = self._canClose()
        if result:
            self._close()
        return result

    @Q.pyqtSlot(bool)
    def exit(self):
        """
        [File | Exit] action's slot.

        Quit application.
        """
        self.mainWindow().close()

    @Q.pyqtSlot(bool)
    def preferences(self):
        """
        [Edit | Preferences] action's slot.

        Show Preferences dialog.
        """
        changes = PrefDlg.execute(self)
        self.from_preferences() # re-initialize behavior from preferences

        if "toolbar_button_style" in changes:
            tbstyle = behavior().toolbar_button_style
            self.main_window.setToolButtonStyle(toolbar_style(tbstyle))

        if "workspace_tab_position" in changes:
            tbposition = behavior().workspace_tab_position
            self.workSpace().setTabPosition(tab_position(tbposition))

        if "use_business_translations" in changes or "content_mode" in changes:
            self.updateTranslations()

        if "sort_stages" in changes:
            self.workSpace().view(Context.DataFiles).resort()

        if "show_related_concepts" in changes \
                or "join_similar_files" in changes:
            self.workSpace().view(Context.DataFiles).update()

        if "show_catalogue_name" in changes or "show_comments" in changes:
            self.workSpace().view(Context.DataSettings).update()

        if "auto_hide_search" in changes:
            view = self.workSpace().view(Context.DataSettings)
            view.setAutoHideSearch(behavior().auto_hide_search)

        if "show_readonly_banner" in changes:
            self._updateWindows()

        if changes:
            self.preferencesChanged.emit(self.preferencesMgr())

    @Q.pyqtSlot(bool)
    def help(self): # pragma pylint: disable=no-self-use
        """[Help | User's Guide] action's slot."""
        Q.QDesktopServices.openUrl(Q.QUrl.fromLocalFile(CFG.htmldoc))

    @Q.pyqtSlot(bool)
    def about(self):
        """[Help | About] action's slot."""
        AboutDlg(self.mainWindow()).exec_()

    def load(self, file_name):
        """
        Load study from the file.

        Arguments:
            file_name (str): Path to the study file.

        Returns:
            bool: *True* in case of success; *False* otherwise.
        """
        result = False
        try:
            self._setStudy(Study.load(self, file_name))

            self._connectWorkspace()
            self.workSpace().activate(True)

            self.update(autoSelect=self.study().activeCase,
                        context=Context.Cases)

            result = True
        except IOError:
            pass
        return result

    @Q.pyqtSlot(bool)
    def showConsole(self):
        """[Show / hide console] action's slot."""
        action = self.sender()
        if self.console is not None:
            self.console.setVisible(action.isChecked())

    @Q.pyqtSlot(bool)
    def execute(self):
        """[Load script] action's slot."""
        if self.console is not None:
            title = translate("AsterStudy", "Load script")
            file_filter = translate("AsterStudy", "Python scripts")
            file_filter = file_filter + " (*.py)"

            file_name = get_file_name(1, self.mainWindow(),
                                      title, "", file_filter,
                                      "py")
            if file_name:
                cmd = "execfile(r\'{}\')".format(file_name)
                method = getattr(self.console, "exec")
                method(cmd)

    def createMenu(self, text, parent=-1, group=-1):
        """
        Create menu item in the main menu of application.

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
            RuntimeError: If parent menu was not found.

        See also:
            `addMenuAction()`
        """
        # Get parent menu.
        parent_menu = self.mainWindow().menuBar() if parent == -1 \
            else self.menus.get(parent)
        if parent_menu is None:
            raise RuntimeError("Parent menu is not found")

        # Check if menu is already present in parent menu.
        actions = parent_menu.actions()
        menus = [i for i in actions if i.menu() is not None and \
                     clean_text(i.text()) == clean_text(text)]
        if menus:
            # If menu is present, return it.
            menu = menus[0].menu()
            if "_ident" not in menu.dynamicPropertyNames():
                ident = uuid.uuid1()
                menu.setProperty("_ident", ident)
                self.menus[ident] = menu
            else:
                ident = menu.property("_ident")
        else:
            # If menu is not present, create it.
            menu = Q.QMenu(text)
            ident = uuid.uuid1()
            menu.setProperty("_ident", ident)
            self.menus[ident] = menu
            menu.menuAction().setProperty("_menu_group", group)
            if group < 0:
                before = None
            else:
                groups = [i.property("_menu_group")
                          if "_menu_group" in i.dynamicPropertyNames()
                          else -2 for i in actions]
                groups = [i == -1 or i > group for i in groups]
                before = actions[groups.index(True)] if True in groups \
                    else None
            parent_menu.insertMenu(before, menu)
        return ident

    def addMenuAction(self, action, parent, group=-1):
        """
        Add action to the menu.

        Similarly to menu items, actions are combined into groups;
        see `createMenu()` for more details.

        Arguments:
            action (QAction): Menu action.
            parent (int): Parent menu item.
            group (Optional[int]): Menu group. Defaults to -1.

        Raises:
            RuntimeError: If parent menu was not found.

        See also:
            `createMenu()`
        """
        # Get parent menu
        parent_menu = self.mainWindow().menuBar() if parent == -1 \
            else self.menus.get(parent)
        if parent_menu is None:
            raise RuntimeError("Parent menu is not found")

        actions = parent_menu.actions()
        if group < 0:
            before = None
        else:
            groups = [i.property("_menu_group")
                      if "_menu_group" in i.dynamicPropertyNames()
                      else -2 for i in actions]
            groups = [i == -1 or i > group for i in groups]
            before = actions[groups.index(True)] if True in groups \
                else None
        if action is None:
            action = parent_menu.insertSeparator(before)
        else:
            parent_menu.insertAction(before, action)
        action.setProperty("_menu_group", group)

    def createToolbar(self, text, name):
        """
        Create toolbar.

        Toolbar is specified by its label and name.
        Label normally is specified as a text translated to the current
        application's language, while name should not be translated - it
        is used to properly save and restore positions of toolbars.

        Arguments:
            text (str): Text label of toolbar.
            name (str): Unique name of toolbar.

        Returns:
            int: Toolbar's unique identifier.

        See also:
            `addToolbarAction()`
        """
        # Check if toolbar is already present.
        toolbars = [i for i in self.toolbars if \
                        clean_text(self.toolbars[i].windowTitle()) ==
                    clean_text(text)]
        if toolbars:
            # If toolbar is present, return it.
            return toolbars[0]
        else:
            # If toolbar is not present, create it.
            toolbar = self.mainWindow().addToolBar(text)
            toolbar.setObjectName(name)
            ident = uuid.uuid1()
            toolbar.setProperty("_ident", ident)
            self.toolbars[ident] = toolbar
        return ident

    def addToolbarAction(self, action, parent):
        """
        Add action to the toolbar.

        Arguments:
            action (QAction): Toolbar action.
            parent (int): Parent toolbar.

        Raises:
            RuntimeError: If parent toolbar was not found.

        See also:
            `createToolbar()`
        """
        # Get parent toolbar.
        parent_toolbar = self.toolbars.get(parent)
        if parent_toolbar is None:
            raise RuntimeError("Parent toolbar is not found")
        if action is None:
            parent_toolbar.addSeparator()
        else:
            parent_toolbar.addAction(action)

    def updateToolbarsMenu(self):
        """Update View/Toolbars menu content."""
        menu = self.sender()
        menu.clear()
        for i in self.toolbars:
            menu.addAction(self.toolbars[i].toggleViewAction())

    @classmethod
    def preferencesMgr(cls):
        """
        Get preferences manager.

        Returns:
            object: Application's Preferences manager.
        """
        if cls._prefMgr is None:
            cls._prefMgr = PreferencesMgr()
        return cls._prefMgr

    def _createMainWindow(self):
        """
        Initialize main window of application.

        This function is called as a part of GUI initialization procedure.
        """
        self.main_window = MainWindow(self)
        self.main_window.setWindowTitle("AsterStudy v%s" % version())
        self.main_window.setWindowIcon(load_icon("asterstudy.png"))
        tbstyle = behavior().toolbar_button_style
        self.main_window.setToolButtonStyle(toolbar_style(tbstyle))

        status_bar = self.main_window.statusBar()
        status_bar.setSizeGripEnabled(True)
        status_bar.showMessage(translate("AsterStudy", "Ready"))

        # Set-up Workspace
        mainframe = Q.QSplitter(Q.Qt.Vertical, self.main_window)
        self.main_window.setCentralWidget(mainframe)
        self.work_space = self._createWorkspace(mainframe)
        mainframe.addWidget(self.work_space)

        # Set-up Python console
        if debug_mode():
            try:
                from PyConsolePy import PyConsole_Console
                self.console = PyConsole_Console(mainframe)
                mainframe.addWidget(self.console)
                self.console.setVisible(False)
            except ImportError:
                pass

        self.main_window.closing.connect(self._closeMainWindow)

        # For debug mode, here we add "helper" widget to status bar
        if debug_mode():
            debug_widget = DebugWidget(self)
            status_bar.addPermanentWidget(debug_widget)
            setattr(self, 'debug_widget', debug_widget)

    def _createActions(self):
        """
        Create actions.

        This function is called as a part of GUI initialization procedure.
        """
        AsterGui._createActions(self)

        self.createAction(translate("AsterStudy", "&New"),
                          translate("AsterStudy", "New study"),
                          translate("AsterStudy", "Create new study"),
                          load_icon("as_pic_new.png"),
                          translate("AsterStudy", "Ctrl+N"),
                          self.newStudy,
                          ActionType.NewStudy,
                          self)

        self.createAction(translate("AsterStudy", "&Open..."),
                          translate("AsterStudy", "Open study"),
                          translate("AsterStudy",
                                    "Open study from the the file on a disk"),
                          load_icon("as_pic_open.png"),
                          translate("AsterStudy", "Ctrl+O"),
                          self.openStudy,
                          ActionType.OpenStudy,
                          self)

        self.createAction(translate("AsterStudy", "&Save"),
                          translate("AsterStudy", "Save study"),
                          translate("AsterStudy",
                                    "Save study to the file on a disk"),
                          load_icon("as_pic_save.png"),
                          translate("AsterStudy", "Ctrl+S"),
                          self.saveStudy,
                          ActionType.SaveStudy,
                          self)

        self.createAction(translate("AsterStudy", "Save &As..."),
                          translate("AsterStudy", "Save study with new name"),
                          translate("AsterStudy",
                                    "Save study to the alternative "
                                    "location on a disk"),
                          load_icon("as_pic_save_as.png"),
                          translate("AsterStudy", "Ctrl+Shift+S"),
                          self.saveStudyAs,
                          ActionType.SaveStudyAs,
                          self)

        self.createAction(translate("AsterStudy", "&Close"),
                          translate("AsterStudy", "Close study"),
                          translate("AsterStudy", "Close study"),
                          load_icon("as_pic_close.png"),
                          translate("AsterStudy", "Ctrl+W"),
                          self.closeStudy,
                          ActionType.CloseStudy,
                          self)

        self.createAction(translate("AsterStudy", "E&xit"),
                          translate("AsterStudy", "Exit"),
                          translate("AsterStudy", "Quit application"),
                          None,
                          translate("AsterStudy", "Ctrl+Q"),
                          self.exit,
                          ActionType.Exit,
                          self)

        self.createAction(translate("AsterStudy", "&Preferences..."),
                          translate("AsterStudy", "Preferences"),
                          translate("AsterStudy",
                                    "Edit application's preferences"),
                          None,
                          translate("AsterStudy", "Ctrl+P"),
                          self.preferences,
                          ActionType.Options,
                          self)

        # in standalone GUI we redefine LinkToDoc's shortcut
        # to avoid ambiguity with global Help
        shortcut = translate("AsterStudy", "Ctrl+Shift+F1")
        self.action(ActionType.LinkToDoc).setShortcut(shortcut)
        self.createAction(translate("AsterStudy", "&User's Guide"),
                          translate("AsterStudy", "User's Guide"),
                          translate("AsterStudy", "Show user's manual"),
                          load_icon("as_pic_help.png"),
                          translate("AsterStudy", "F1"),
                          self.help,
                          ActionType.UserGuide,
                          self)

        self.createAction(translate("AsterStudy", "&About..."),
                          translate("AsterStudy", "About application"),
                          translate("AsterStudy",
                                    "Display information "
                                    "about this application"),
                          load_icon("as_pic_help.png"),
                          None,
                          self.about,
                          ActionType.AboutApp,
                          self)

        status_tip = translate("AsterStudy", "Show/hide '{}' view")
        status_tip = status_tip.format(translate("AsterStudy",
                                                 "Python console"))
        action = self.createAction(translate("AsterStudy", "&Console"),
                                   translate("AsterStudy", "Python console"),
                                   status_tip,
                                   None,
                                   None,
                                   self.showConsole,
                                   ActionType.ShowConsole,
                                   self)
        action.setCheckable(True)

        self.createAction(translate("AsterStudy", "&Load Script..."),
                          translate("AsterStudy", "Load script"),
                          translate("AsterStudy",
                                    "Execute script in the embedded "
                                    "Python console"),
                          None,
                          translate("AsterStudy", "Ctrl+L"),
                          self.execute,
                          ActionType.ExecScript,
                          self)

    def _createMenus(self):
        """
        Initialize menus.

        This function is called as a part of GUI initialization procedure.
        """
        AsterGui._createMenus(self)

        # "File" menu
        menu_file = self.createMenu(translate("AsterStudy", "&File"),
                                    -1, MenuGroup.File)
        self.addMenuAction(self.action(ActionType.NewStudy), menu_file)
        self.addMenuAction(self.action(ActionType.OpenStudy), menu_file)
        self.addMenuAction(None, menu_file)
        self.addMenuAction(self.action(ActionType.SaveStudy), menu_file)
        self.addMenuAction(self.action(ActionType.SaveStudyAs), menu_file)
        self.addMenuAction(self.action(ActionType.CloseStudy), menu_file)
        if self.console is not None:
            self.addMenuAction(None, menu_file)
            self.addMenuAction(self.action(ActionType.ExecScript), menu_file)
        self.addMenuAction(None, menu_file)
        self.addMenuAction(self.action(ActionType.Options), menu_file)
        self.addMenuAction(None, menu_file)
        self.addMenuAction(self.action(ActionType.Exit), menu_file)

        # "View" menu
        menu_view = self.createMenu(translate("AsterStudy", "&View"),
                                    -1, MenuGroup.View)
        menu_toolbars = self.createMenu(translate("AsterStudy", "&Toolbars"),
                                        menu_view, 0)
        self.menus[menu_toolbars].aboutToShow.connect(self.updateToolbarsMenu)
        self.addMenuAction(None, menu_view, 1)
        if self.console is not None:
            self.addMenuAction(self.action(ActionType.ShowConsole),
                               menu_view, 1)

        # "Help" menu
        menu_help = self.createMenu(translate("AsterStudy", "&Help"),
                                    -1, MenuGroup.Help)
        self.addMenuAction(self.action(ActionType.UserGuide), menu_help)
        self.addMenuAction(None, menu_help)
        self.addMenuAction(self.action(ActionType.AboutApp), menu_help)

    def _createToolbars(self):
        """
        Initialize toolbars.

        This function is called as a part of GUI initialization procedure.
        """
        # "Standard" toolbar
        toolbar_std = self.createToolbar(translate("AsterStudy", "Standard"),
                                         "StandardToolbar")
        self.addToolbarAction(self.action(ActionType.NewStudy), toolbar_std)
        self.addToolbarAction(self.action(ActionType.OpenStudy), toolbar_std)
        self.addToolbarAction(self.action(ActionType.SaveStudy), toolbar_std)
        self.addToolbarAction(self.action(ActionType.SaveStudyAs), toolbar_std)
        self.addToolbarAction(None, toolbar_std)
        self.addToolbarAction(self.action(ActionType.CloseStudy), toolbar_std)

        AsterGui._createToolbars(self)

    def _updateActions(self):
        """Update state of actions, menus, toolbars, etc."""
        AsterGui._updateActions(self)

        has_study = self.study() is not None
        is_modified = has_study and self.study().isModified()
        self.action(ActionType.SaveStudy).setEnabled(is_modified)
        self.action(ActionType.SaveStudyAs).setEnabled(has_study)
        self.action(ActionType.CloseStudy).setEnabled(has_study)

        title = "AsterStudy v%s" % version()
        if has_study:
            title = "%s - %s" % (self.study().name(), title)
        self.main_window.setWindowTitle(title)

    def _canClose(self):
        """
        Check if currently open study can be closed.

        Returns:
            bool: *True* if study can be closed; *False* otherwise.
        """
        result = Controller.execute('', None, self)
        if result and self.study() is not None and self.study().isModified():
            text = translate("AsterStudy",
                             "Do you want to save changes to %s?")
            text = text % self.study().name()
            buttons = (Q.QMessageBox.Save | Q.QMessageBox.Discard | \
                           Q.QMessageBox.Cancel)
            answer = Q.QMessageBox.question(self.mainWindow(),
                                            "AsterStudy", text,
                                            buttons, Q.QMessageBox.Save)
            if answer == Q.QMessageBox.Cancel:
                result = False
            elif answer == Q.QMessageBox.Save:
                result = self.saveStudy()
        return result

    def _close(self):
        """Close study."""
        if self.study():
            self.study().history.clean_embedded_files()
        if self.workSpace():
            workspace_state = self.workSpace().saveState()
            self.preferencesMgr().setValue("workspace_state", workspace_state)
            self.workSpace().activate(False)
        self._setStudy(None)
        self.update()

    def _closeMainWindow(self, event):
        """
        Process main window close event.

        Arguments:
            event (QCloseEvent): Close event.
        """
        if not self.closeStudy():
            event.ignore()

    def autosave(self):
        """
        What to do when automatically saving upon run?
        """
        self.saveStudy()
