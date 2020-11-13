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
Parameters Panel
----------------

Implementation of the Parameters panel for AsterStudy application.

"""

from __future__ import unicode_literals

from PyQt5.Qt import (QAction, QLabel, QLineEdit, QRegExp, QStackedWidget,
                      QVBoxLayout, QDialogButtonBox, QWhatsThis, QToolBar,
                      QHBoxLayout, QUrl, QRegExpValidator, QDesktopServices,
                      QEvent, QMessageBox, Qt)

from common import (CFG, auto_dupl_on, bold, connect, get_cmd_mesh,
                    href, image, italic,
                    load_icon, load_pixmap, preformat, translate)
from datamodel import CATA, IDS, get_cata_typeid
from datamodel.general import ConversionLevel
from datamodel.command.helper import avail_meshes_in_cmd

from gui import ActionType, Panel
from gui.behavior import behavior
from gui.editionwidget import EditionWidget
from gui.controller import WidgetController
from gui.unit_model import UnitModel
from gui.widgets import HLine, MessageBox
from gui.commentpanel import CommentPanel

from .windows import (ParameterTableWindow, ParameterListWindow,
                      ParameterMeshGroupWindow, ParameterFactWindow)
from .widgets import ParameterTitle
from .path import ParameterPath
from .basic import EditorLink, Options

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name

class ParameterPanel(EditionWidget, WidgetController):
    """Edition Panel implementation."""

    def __init__(self, astergui, parent=None):
        """
        Create panel.

        Arguments:
            astergui (AsterGui): AsterGui instance.
            parent (Optional[QWidget]): Parent widget.
        """
        super(ParameterPanel, self).__init__(parent=parent,
                                             name=translate("ParameterPanel",
                                                            "Edit command"),
                                             astergui=astergui)
        self.setPixmap(load_pixmap("as_pic_edit_command.png"))

        self._files_model = astergui.study().dataFilesModel()
        self._unit_model = None

        self._command = None
        self.title = ParameterTitle(self)
        self.title.installEventFilter(self)
        self._name = QLineEdit(self)
        self.views = QStackedWidget(self)
        v_layout = QVBoxLayout(self)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(5)
        v_layout.addWidget(self.title)
        v_layout.addWidget(HLine(self))

        n_layout = QHBoxLayout()
        v_layout.addLayout(n_layout)
        n_layout.addWidget(QLabel(translate("ParameterPanel", "Name"), self))
        n_layout.addWidget(self._name)
        # force to be a valid identifier + length <= 8
        self._name.setValidator(QRegExpValidator(QRegExp(r"[a-zA-Z]\w{1,7}")))

        # create toolbar
        tbar = QToolBar(self)
        tbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        # - Edit comment
        edit_comment = QAction(translate("AsterStudy", "Edit &Comment"), self)
        edit_comment.setToolTip(translate("AsterStudy", "Edit comment"))
        edit_comment.setStatusTip(translate("AsterStudy",
                                            "Edit comment for the "
                                            "selected object"))
        edit_comment.setIcon(load_icon("as_pic_edit_comment.png"))
        connect(edit_comment.triggered, self._editComment)
        tbar.addAction(edit_comment)
        # - Switch on/off business-translations
        title = translate("AsterStudy", "Use Business-Oriented Translations")
        self.use_translations = QAction(title, self)
        title = translate("AsterStudy", "Use business-oriented translations")
        self.use_translations.setToolTip(title)
        self.use_translations.setStatusTip(title)
        self.use_translations.setIcon(load_icon("as_pic_use_translations.png"))
        self.use_translations.setCheckable(True)
        if behavior().forced_native_names:
            force = behavior().force_native_names
            self.use_translations.setDisabled(True)
            is_on = not force
        else:
            is_on = behavior().use_business_translations
        Options.use_translations = is_on
        self.use_translations.setChecked(is_on)
        connect(self.use_translations.toggled, self.updateTranslations)
        tbar.addAction(self.use_translations)
        # - Hide unused
        hide_unused = astergui.action(ActionType.HideUnused)
        connect(hide_unused.toggled, self._unusedVisibility)
        tbar.addAction(hide_unused)
        # - What's this
        whats_this = QWhatsThis.createAction(tbar)
        whats_this.setToolTip(translate("AsterStudy", "What's this?"))
        whats_this.setStatusTip(translate("AsterStudy",
                                          "Show element's description"))
        whats_this.setIcon(load_icon("as_pic_whats_this.png"))
        tbar.addAction(whats_this)
        # - Link to doc
        tbar.addAction(astergui.action(ActionType.LinkToDoc))

        n_layout.addWidget(tbar)

        v_layout.addWidget(self.views)
        self._updateState()

    def unitModel(self):
        """
        Method that get unit model.

        Returns:
            UnitModel: Unit model.
        """
        return self._unit_model

    def command(self):
        """
        Get command being edited.

        Returns:
            Command: Command being edited.
        """
        return self._command

    def setCommand(self, command):
        """
        Set command to edit.

        Arguments:
            command (Command): Command to edit.
        """
        self.clear()
        self._command = command
        if self._command is None:
            self._name.setText("")
        else:
            self._name.setText(self._command.name)
            self._unit_model = UnitModel(command.stage)
            pview = self._createParameterView(ParameterPath(self._command), '')
            pview.view().setItemValue(command.storage)
            hide_unused = self.astergui().action(ActionType.HideUnused)
            pview.setUnusedVisibile(not hide_unused.isChecked())
            self.views.setCurrentWidget(pview)
        self._updateState()

    def currentPath(self):
        """
        Get currently edited parameter path.

        Returns:
            str: currently edited parameter path.
        """
        path = ""
        wid = self.currentParameterView()
        if wid is not None:
            path = wid.path()
        return path

    def isCurrentCommand(self):
        """
        Get true if the currently edited view contains command.

        Returns:
            bool: Current edited command flag
        """
        curpath = self.currentPath()
        return ParameterPath(self.command()).isEqual(curpath)

    def currentParameterView(self):
        """
        Get current parameter view.

        Returns:
           ParameterView: current view.
        """
        return self.views.currentWidget()

    def clear(self):
        """Remove all parameter views."""
        while self.views.count() > 0:
            wid = self.views.widget(0)
            if wid is not None:
                self.views.removeWidget(wid)
                wid.deleteLater()

    def store(self):
        """
        Save data from all parameter views.
        """
        cmd = self.command()
        if cmd is not None:
            with auto_dupl_on(self.astergui().study().activeCase):
                cmd.rename(self._name.text())
                wid = self._viewByPath(ParameterPath(cmd))
                if wid is not None:
                    cmd.init(wid.view().itemValue())

    def requiredButtons(self):
        """
        Return the combination of standard button flags required for this
        widget.

        Returns:
            int: button flags for buttons required for this widget
                 (combination of QDialogButtonBox.StandardButton flags).
        """
        if self.isCurrentCommand():
            return QDialogButtonBox.Ok | QDialogButtonBox.Apply | \
                QDialogButtonBox.Close
        else:
            return QDialogButtonBox.Ok | QDialogButtonBox.Cancel | \
                QDialogButtonBox.Abort

    def isButtonEnabled(self, button):
        """
        Return True if a particular button is enabled.

        Arguments:
            button (QDialogButtonBox.StandardButton): button flag.

        Returns:
            True: that means that all buttons should be enabled.
        """
        return True

    def perform(self, button):
        """
        Perform action on button click. Redefined method from the base class.

        Arguments:
            button (QDialogButtonBox.StandardButton): clicked button flag.
        """
        if button == QDialogButtonBox.Ok:
            self.performOk()
        elif button == QDialogButtonBox.Apply:
            self.performApply()
        elif button == QDialogButtonBox.Abort:
            self.performAbort()
        elif button == QDialogButtonBox.Close or \
                button == QDialogButtonBox.Cancel:
            self.performClose()

    def performOk(self):
        """Called when `Ok` button is clicked in Edition panel."""
        self.performChanges(True)

    def performApply(self):
        """Called when `Apply` button is clicked in Edition panel."""
        self.performChanges(False)

    def performAbort(self):
        """Called when `Abort` button is clicked in Edition panel."""
        pref_mgr = self.astergui().preferencesMgr()
        msg = translate("ParameterPanel",
                        "Command edition will be aborted and "
                        "all made changes will be lost. "
                        "Do you want to continue?")
        noshow = "parampanel_abort"
        ask = MessageBox.question(self.astergui().mainWindow(),
                                  translate("ParameterPanel", "Abort"),
                                  msg, QMessageBox.Yes | QMessageBox.No,
                                  QMessageBox.Yes, noshow=noshow,
                                  prefmgr=pref_mgr)
        if ask == QMessageBox.Yes:
            self.close()
            self.astergui().study().revert()

    def performClose(self):
        """Called when `Cancel` button is clicked in Edition panel."""
        has_modif = self._hasModifications()
        if has_modif:
            pref_mgr = self.astergui().preferencesMgr()
            msg = translate("ParameterPanel",
                            "There are some unsaved modifications will be "
                            "lost. Do you want to continue?")
            noshow = "parampanel_close"
            ask = MessageBox.question(self.astergui().mainWindow(),
                                      translate("ParameterPanel", "Close"),
                                      msg, QMessageBox.Yes | QMessageBox.No,
                                      QMessageBox.Yes, noshow=noshow,
                                      prefmgr=pref_mgr)
            has_modif = ask != QMessageBox.Yes

        if not has_modif:
            self.performDissmis(True)

    def performChanges(self, close=True):
        """
        Validate and store the command into data model.
        """
        wid = self.currentParameterView()
        if wid is not None:
            view = wid.view()
            if view.validate():
                cur_path = self.currentPath()
                if self.isCurrentCommand():
                    self.store()
                    self._files_model.update()
                    if self.astergui() is not None:
                        opname = translate("ParameterPanel", "Edit command")
                        self.astergui().study().commit(opname)
                        self.astergui().update()
                    if close:
                        self.performDissmis(False)
                    msg = translate("ParameterPanel",
                                    "Command '{}' successfully stored")
                    msg = msg.format(self._name.text())
                    self.astergui().showMessage(msg)
                else:
                    child_val = view.itemValue()
                    self._removeCurrentView()
                    curview = self.currentParameterView()
                    subitem = curview.view().findItemByPath(cur_path)
                    if subitem is not None:
                        subitem.setItemValue(child_val)
        self._updateState()
        self.updateButtonStatus()

    def performDissmis(self, revert=True):
        """
        Cancel changes and revert the command changes.
        """
        if self.isCurrentCommand():
            self.close()
            if revert:
                self.astergui().study().revert()
        else:
            self._removeCurrentView()
        self._updateState()
        self.updateButtonStatus()

    def showEvent(self, event):
        """
        Reimplemented for internal reason: updates the title
        depending on read only state, etc.
        """
        title = translate("ParameterPanel", "View command") \
            if self.isReadOnly() else \
            translate("ParameterPanel", "Edit command")
        self.setWindowTitle(title)

        hide_unused = self.astergui().action(ActionType.HideUnused)
        hide_unused.setVisible(True)
        hide_unused.setChecked(self.isReadOnly())

        # update meshview
        meshes = avail_meshes_in_cmd(self.command())
        for i, mesh in enumerate(meshes):
            filename, meshname = get_cmd_mesh(mesh)
            if filename:
                if i > 0:
                    self.meshview().displayMEDFileName(filename,
                                                       meshname,
                                                       1.0, False)
                else:
                    self.meshview().displayMEDFileName(filename,
                                                       meshname,
                                                       1.0, True)

        super(ParameterPanel, self).showEvent(event)

    def hideEvent(self, event):
        """
        Reimplemented for internal reason: hides "Hide unused" action.
        """
        hide_unused = self.astergui().action(ActionType.HideUnused)
        hide_unused.setVisible(False)
        super(ParameterPanel, self).hideEvent(event)

    def updateTranslations(self):
        """
        Update translations in GUI elements.
        """
        Options.use_translations = self.use_translations.isChecked()
        self._updateState()
        for i in xrange(self.views.count()):
            view = self.views.widget(i)
            view.updateTranslations()

    def eventFilter(self, receiver, event):
        """
        Event filter; processes clicking ln links in What's This window.
        """
        if receiver == self.title and event.type() == QEvent.WhatsThisClicked:
            QDesktopServices.openUrl(QUrl(event.href()))
        return super(ParameterPanel, self).eventFilter(receiver, event)

    def _hasModifications(self):
        curview = self.currentParameterView().view() \
            if self.currentParameterView() is not None else None
        return curview.hasModifications() \
            if curview is not None else False

    def _updateState(self):
        """Update state and current title label."""
        disabled = self.command() is None
        self.setDisabled(disabled)

        if not disabled:
            disabled = self.command().gettype(ConversionLevel.NoFail) is None
        self._name.setDisabled(disabled)

        txt = []
        pview = self.currentParameterView()
        if pview is not None:
            txt = pview.path().names()

        ppath = None
        txt_list = []
        tooltip = ""
        whats_this = ""
        while len(txt) > 0:
            name = txt.pop(0)
            if ppath is None:
                ppath = ParameterPath(self.command(), name=name)
            else:
                ppath = ppath.absolutePath(name)
            if ppath.isInSequence():
                txt_list.append("[" + name + "]")
            elif get_cata_typeid(ppath.keyword()) in (IDS.simp, IDS.fact):
                # translate keyword
                kwtext = Options.translate_command(ppath.command().title, name)
                txt_list.append(kwtext)
            elif get_cata_typeid(ppath.keyword()) == IDS.command:
                # translate command
                translation = Options.translate_command(name)
                txt_list.append(translation)
                if translation != name:
                    wttext = italic(translation) + " ({})".format(bold(name))
                else:
                    wttext = bold(name)
                tooltip = preformat(wttext)
                url = self.astergui().doc_url(name)
                if url:
                    wttext += "&nbsp;"
                    wttext += href(image(CFG.rcfile("as_pic_help.png"),
                                         width=20, height=20), url)
                wttext = preformat(wttext)
                docs = CATA.get_command_docstring(name)
                if docs:
                    wttext += "<hr>"
                    wttext += docs
                whats_this = wttext

        self.title.setTitle(txt_list)
        self.title.setToolTip(tooltip)
        self.title.setWhatsThis(whats_this)

    def _removeCurrentView(self):
        """
        Remove the parameter view for given object.

        Arguments:
            obj (Parameter): Command's parameter.
        """
        curview = self.currentParameterView()
        if curview is not None:
            master = curview.view().masterItem()
            if master is not None and master.slaveItem() == curview.view():
                master.setSlaveItem(None)
            curview.view().setMasterItem(None)
            view = self._parentView(curview)
            if view is not None:
                self.views.setCurrentWidget(view)
                hide_unused = self.astergui().action(ActionType.HideUnused)
                view.setUnusedVisibile(not hide_unused.isChecked())
            self.views.removeWidget(curview)
            curview.deleteLater()
        self._updateState()

    def _viewByPath(self, path):
        view = None
        for i in xrange(self.views.count()):
            the_view = self.views.widget(i)
            if the_view.path().isEqual(path):
                view = the_view
                break
        return view

    def _parentView(self, curview):
        view = None
        path = curview.path()
        while path is not None and view is None:
            path = path.parentPath()
            view = self._viewByPath(path)
        return view

    def _gotoParameter(self, path, link):
        """
        Activate the parameter view for object with given id.

        Arguments:
            uid (int): Object's UID.
        """
        curview = self.currentParameterView()
        act_item = curview.view().findItemByPath(path)
        child_val = None
        wid = self._createParameterView(path, link)
        if act_item is not None:
            child_val = act_item.itemValue()
            act_item.setSlaveItem(wid.view())
        wid.view().setMasterItem(act_item)
        hide_unused = self.astergui().action(ActionType.HideUnused)
        wid.setUnusedVisibile(not hide_unused.isChecked())
        self.views.setCurrentWidget(wid)
        wid.view().setItemValue(child_val)
        self._updateState()
        self.updateButtonStatus()

    def _createParameterView(self, path, link):
        """
        Create parameter view for given object.

        Arguments:
            path (ParameterPath): Path of parameter to edit.

        Returns:
            ParameterWindow: Parameter view for parameter path.
        """
        # pragma pylint: disable=redefined-variable-type
        pview = None
        if link == EditorLink.Table:
            pview = ParameterTableWindow(path, self, self.views)
        elif link == EditorLink.List:
            pview = ParameterListWindow(path, self, self.views)
        elif link == EditorLink.GrMa:
            pview = ParameterMeshGroupWindow(path, self, self.views)
        else:
            pview = ParameterFactWindow(path, self, self.views)
        connect(pview.gotoParameter, self._gotoParameter)
        self.views.addWidget(pview)
        return pview

    def _unusedVisibility(self, ison):
        """
        Invoked when 'Hide unused' button toggled
        """
        curview = self.currentParameterView()
        curview.setUnusedVisibile(not ison)

    def meshview(self):
        """
        Returns the central *MeshView* object
        """
        return self.astergui().workSpace().panels[Panel.View]

    def _editComment(self):
        """
        Invoked when 'Edit comment' button is clicked
        """
        panel = CommentPanel(self.astergui(), owner=self)
        panel.node = self.command()
        self.astergui().workSpace().panel(Panel.Edit).setEditor(panel)

    def pendingStorage(self):
        """
        Dictionnary being filled as this command is edited.
        """
        wid = self._viewByPath(ParameterPath(self.command()))
        if wid is not None:
            return wid.view().itemValue()
        return None
