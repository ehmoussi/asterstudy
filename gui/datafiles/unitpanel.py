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
Data file editor
----------------

Implements Data file unit editor.

"""

from __future__ import unicode_literals

import os

from PyQt5 import Qt as Q

from common import (common_filters, connect, external_file, get_file_name,
                    load_pixmap, translate)
from datamodel import FileAttr, is_unit_valid
from gui import NodeType, Role, get_node_type
from gui.controller import WidgetController
from gui.editionwidget import EditionWidget
from gui.unit_model import UnitModel
from gui.widgets import MessageBox
from . objects import File

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class UnitPanel(EditionWidget, WidgetController):
    """Unit edition panel."""

    CreateMode = 0
    EditMode = 1

    def __init__(self, node, astergui, parent=None): # pragma pylint: disable=too-many-locals
        """
        Create editor panel.

        Arguments:
            node (Stage, Unit): Object to manage.
            astergui (AsterGui): *AsterGui* instance.
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
        """
        #----------------------------------------------------------------------
        super(UnitPanel, self).__init__(parent=parent,
                                        name="",
                                        astergui=astergui)

        #----------------------------------------------------------------------
        self.node = node
        self.prev_unit = None
        self.unit = None

        #----------------------------------------------------------------------
        # set title
        title = translate("UnitPanel", "Edit data file") \
            if self.mode == UnitPanel.EditMode \
            else translate("UnitPanel", "Add data file")
        self._controllername = title
        self.setWindowTitle(title)
        # set icon
        pixmap = load_pixmap("as_pic_edit_file.png") \
            if self.mode == UnitPanel.EditMode \
            else load_pixmap("as_pic_new_file.png")
        self.setPixmap(pixmap)

        #----------------------------------------------------------------------
        # top-level layout
        v_layout = Q.QVBoxLayout(self)
        v_layout.setContentsMargins(0, 0, 0, 0)

        #----------------------------------------------------------------------
        # top level widget to easily manage read-only mode
        self.frame = Q.QWidget(self)
        v_layout.addWidget(self.frame)

        #----------------------------------------------------------------------
        # main layout
        glayout = Q.QGridLayout(self.frame)
        glayout.setContentsMargins(0, 0, 0, 0)

        #----------------------------------------------------------------------
        # 'Mode' controls
        label = Q.QLabel(translate("DataFiles", "Mode"), self.frame)
        glayout.addWidget(label, 0, 0)

        self.attr_combo = Q.QComboBox(self.frame)
        self.attr_combo.setObjectName("Mode")
        attr_list = [FileAttr.In, FileAttr.Out, FileAttr.InOut]
        for attr in attr_list:
            self.attr_combo.addItem(FileAttr.value2str(attr), attr)
        self.attr_combo.setCurrentIndex(-1)
        glayout.addWidget(self.attr_combo, 0, 1)

        #----------------------------------------------------------------------
        label = Q.QLabel(translate("DataFiles", "Filename"), self.frame)
        glayout.addWidget(label, 1, 0)

        self.file_combo = Q.QComboBox(self.frame)
        self.file_combo.setObjectName("Filename")
        glayout.addWidget(self.file_combo, 1, 1, 1, 2)

        self.file_btn = Q.QToolButton(self.frame)
        self.file_btn.setText("...")
        self.file_btn.setObjectName("Filename")
        glayout.addWidget(self.file_btn, 1, 3)

        #----------------------------------------------------------------------
        # 'Unit' controls
        label = Q.QLabel(translate("DataFiles", "Unit"), self.frame)
        glayout.addWidget(label, 2, 0)

        self.unit_edit = Q.QLineEdit(self.frame)
        self.unit_edit.setObjectName("Unit")
        self.unit_edit.setValidator(Q.QIntValidator(2, 99, self.unit_edit))
        glayout.addWidget(self.unit_edit, 2, 1)

        #----------------------------------------------------------------------
        # 'Exists' controls
        label = Q.QLabel(translate("DataFiles", "Exists"), self.frame)
        glayout.addWidget(label, 3, 0)

        self.exists_check = Q.QCheckBox(self.frame)
        self.exists_check.setObjectName("Exists")
        self.exists_check.setEnabled(False)
        glayout.addWidget(self.exists_check, 3, 1)

        #----------------------------------------------------------------------
        # 'Embedded' controls
        label = Q.QLabel(translate("DataFiles", "Embedded"), self.frame)
        glayout.addWidget(label, 4, 0)

        self.embedded_check = Q.QCheckBox(self.frame)
        self.embedded_check.setObjectName("Embedded")
        glayout.addWidget(self.embedded_check, 4, 1)

        #----------------------------------------------------------------------
        # tune layout
        glayout.setColumnStretch(1, 2)
        glayout.setColumnStretch(2, 2)
        glayout.setRowStretch(glayout.rowCount(), 10)

        #----------------------------------------------------------------------
        # initialize unit model
        file_model = UnitModel(self.stage)
        self.file_combo.setModel(file_model)
        self.file_combo.setCurrentIndex(-1)

        #----------------------------------------------------------------------
        # initialize controls from data model object
        if self.mode == UnitPanel.EditMode:
            self.setEditData(node)

        #----------------------------------------------------------------------
        # connections
        connect(self.file_combo.currentIndexChanged, self.updateControls)
        connect(self.file_combo.currentIndexChanged, self.updateButtonStatus)
        connect(self.file_btn.clicked, self.browseFile)
        connect(self.unit_edit.textChanged, self.updateButtonStatus)
        connect(self.attr_combo.currentIndexChanged, self.updateButtonStatus)
        connect(self.embedded_check.toggled, self.embeddedChanged)
        connect(file_model.rowsAboutToBeInserted, self.beforeUpdate)
        connect(file_model.rowsInserted, self.afterUpdate)
        connect(file_model.rowsAboutToBeRemoved, self.beforeUpdate)
        connect(file_model.rowsRemoved, self.afterUpdate)

        #----------------------------------------------------------------------
        # update status
        self.updateControls()

    def setReadOnly(self, on):
        """Redefined from EditionWidget."""
        super(UnitPanel, self).setReadOnly(on)
        self.frame.setDisabled(on)

    @property
    def mode(self):
        """
        Get current working mode of panel.

        Returns:
            int: Working mode: *UnitPanel.CreateMode* (0) for adding new
            file, *UnitPanel.EditMode* (1) for editing file.
        """
        node_type = get_node_type(self.node)
        return UnitPanel.EditMode if node_type == NodeType.Unit \
            else UnitPanel.CreateMode

    @property
    def stage(self):
        """
        Get stage being managed by the panel.

        Returns:
            Stage: Stage being managed.
        """
        node_type = get_node_type(self.node)
        return self.node if node_type == NodeType.Stage else self.node.stage

    def setEditData(self, node):
        """
        Fill in controls from file object.

        Arguments:
            node (File): *File* object.
        """
        stages = node.stages
        has_graphical_stage = any([i.is_graphical_mode() for i in stages])

        attr = node.attr
        if attr == FileAttr.No:
            self.attr_combo.setCurrentIndex(-1)
        else:
            self.attr_combo.setCurrentText(FileAttr.value2str(attr))
        is_enabled = not has_graphical_stage and not node.is_forced_attr
        self.attr_combo.setEnabled(is_enabled)

        self.unit = node.unit
        self.unit_edit.setText(str(self.unit))
        is_enabled = attr == FileAttr.No or not has_graphical_stage
        self.unit_edit.setEnabled(is_enabled)

        exists = node.exists
        self.exists_check.setChecked(exists)

        embedded = node.embedded is not None and node.embedded
        self._checkEmbeddedSilently(embedded)

        self.setCurrentFilename(self.unit)

    @Q.pyqtSlot(int)
    def updateControls(self):
        """
        Called when current index of filename combobox is changed.

        Updates state of 'exists' and 'embedded' controls.
        """
        exists = isvalid = isreference = isforced = False
        combo_index = self.file_combo.currentIndex()
        index = self.file_combo.model().index(combo_index, 0)
        if index.isValid():
            filename = index.data(Role.CustomRole)
            isvalid = index.data(Role.ValidityRole)
            isreference = index.data(Role.ReferenceRole)
            if isreference:
                exists = external_file(filename) is not None
            else:
                exists = isvalid and os.path.isfile(filename)
            isforced = get_node_type(self.node) in (NodeType.Unit,) \
                and self.node.is_forced_attr
        self.exists_check.setChecked(exists)
        # undefined file can not be embedded
        self.embedded_check.setDisabled(isreference or not isvalid or isforced)

    @Q.pyqtSlot(bool)
    def embeddedChanged(self, is_checked):
        """
        Called when embedded checkbox is toggled.

        Arguments:
            is_checked (bool): Toggle flag (*True* or *False*).
        """
        ok = False
        if is_checked:
            # check study saving
            study = self.astergui().study()
            path = study.url()
            if path:
                path = os.path.splitext(path)[0] + '_Files'
                if not os.path.isdir(path):
                    os.mkdir(path)
                study.history.folder = path
                # check selected file
                combo_index = self.file_combo.currentIndex()
                if combo_index >= 0:
                    index = self.file_combo.model().index(combo_index, 0)
                    if index.isValid():
                        extpath = index.model().data(index, Role.CustomRole)
                        embpath = self.file_combo.model().ext2emb(extpath)
                        if embpath != extpath:
                            self.setCurrentFilename(embpath)
                        ok = True
            else:
                msg = translate("UnitPanel", "You should save the "
                                "study before embedding the file")
                MessageBox.warning(self.astergui().mainWindow(),
                                   "AsterStudy", msg)
        else:
            try:
                if self.browseExternalFile():
                    ok = True
            except ValueError as exc:
                MessageBox.critical(self.astergui().mainWindow(),
                                    "AsterStudy", exc.message)

        # check result
        if not ok:
            self._checkEmbeddedSilently(not is_checked)

    @Q.pyqtSlot()
    def browseFile(self):
        """
        Called when '...' button is clicked.

        Opens standard file selection dialog to browse existing file
        or input a file name for non-existing file (depending on unit
        mode).
        """
        cur_attr = self.attr_combo.currentText()
        attr_list = [FileAttr.In, FileAttr.InOut, FileAttr.Out]
        if cur_attr not in [FileAttr.value2str(attr) for attr in attr_list]:
            msg = translate("UnitPanel", "Please select a value "
                            "for the `Mode` property above "
                            "before browsing for the file path.")
            MessageBox.warning(self.astergui().mainWindow(),
                               "AsterStudy", msg)
            return
        out_attr = FileAttr.value2str(FileAttr.Out)
        mode = 0 if cur_attr == out_attr else 1
        self._browseFileTemplate(mode)

    def browseExternalFile(self):
        """
        Called when embedded file becomes external.

        Allows selecting existing file or entering a new file name
        (depending on unit mode).
        """
        # line edit has to be present anyway to unembed files
        return self._browseFileTemplate(0, self.file_combo.model().emb2ext)

    def _checkEmbeddedSilently(self, is_checked):
        """
        Modify 'embedded' check box's state silently.

        Arguments:
            is_checked (bool): Check box's state.
        """
        blocked = self.embedded_check.blockSignals(True)
        self.embedded_check.setChecked(is_checked)
        self.embedded_check.blockSignals(blocked)

    def _browseFileTemplate(self, mode, operation=lambda *_: None):
        """
        Template for managing 'Browse file' operation.

        Arguments:
            mode (int): 0 has line edit, 1 has not.
            operation (func) : Operation to perform, typically
                moving a file from a `source` to a `dest`.
                Defaults to noop.
        """
        combo_index = self.file_combo.currentIndex()
        index = self.file_combo.model().index(combo_index, 0)
        oldfile = index.model().data(index, Role.CustomRole) \
            if index.isValid() else ""

        filters = common_filters()
        title = translate("UnitPanel", "Select file")

        # mode = 1 for "in" or "inout", 0 for "out"
        # 0 is intended for save and has line edit,
        # 1 is intended for open and has not
        filename = get_file_name(mode,
                                 parent=self.file_combo, title=title,
                                 url=oldfile, filters=filters)
        if filename:
            if not operation(oldfile, filename) \
                and self.embedded_check.isChecked():
                # remove old embedded file and uncheck Embedded checkbox,
                # when another file was browsed
                self.file_combo.model().emb2ext(oldfile, "")
                if os.path.exists(oldfile):
                    os.remove(oldfile)
                self._checkEmbeddedSilently(False)
            self.setCurrentFilename(filename)
        return filename

    def setCurrentFilename(self, filename):
        """
        Set given file name as current item in the combobox.

        Arguments:
            filename (str or int): File path or unit value.

        Note:
            Data model is not modified.
        """

        # The following invokes the `data` method of the Qt model
        #     associated with the *QComboBox*.
        # That model is a *UnitModel* instance.
        # So, look at `UnitModel.data` to understand what this does.
        index = self.file_combo.findData(filename, Role.IdRole) \
            if isinstance(filename, int) else \
            self.file_combo.findData(filename, Role.CustomRole)

        if index < 0 and not isinstance(filename, int):
            if self.file_combo.model().basename_conflict(filename):
                msg = translate("UnitPanel",
                                "There is already a file in this stage"
                                " whose basename is '{0}'.\n"
                                "Please rename the file before you add it "
                                "to the study.")
                MessageBox.critical(self.astergui().mainWindow(),
                                    "AsterStudy",
                                    msg.format(os.path.basename(filename)))
                return
            unit = self.file_combo.model().addItem(filename)
            if not self.unit_edit.text():
                self.unit = unit
                self.unit_edit.setText(str(unit))
            index = self.file_combo.findData(unit, Role.IdRole)

        self.file_combo.setCurrentIndex(index)

    @Q.pyqtSlot("QModelIndex", int, int)
    def beforeUpdate(self): # pragma pylint: disable=unused-argument
        """
        Called when rows are about to be inserted to model or removed
        from it.
        """
        self.prev_unit = self.file_combo.currentData(Role.IdRole)

    @Q.pyqtSlot("QModelIndex", int, int)
    def afterUpdate(self, parent, start, end): # pragma pylint: disable=unused-argument
        """
        Called after rows are just inserted to model or removed from it.
        """
        data = self.file_combo.findData(self.prev_unit, Role.IdRole)
        self.file_combo.setCurrentIndex(data)

    @Q.pyqtSlot(Q.QPushButton)
    def isButtonEnabled(self, button):
        """Redefined from *EditionWidget*."""
        is_valid = True
        if button in [Q.QDialogButtonBox.Ok]:
            combo_index = self.file_combo.currentIndex()
            model = self.file_combo.model()
            model_index = model.index(combo_index, 0)
            file_unit = model.data(model_index, Role.IdRole)
            is_valid = model_index.isValid() and \
                model_index.data(Role.ValidityRole)
            is_file_valid = file_unit != -1 and is_valid

            unit_text = self.unit_edit.text()
            is_valid = is_unit_valid(unit_text)

            if is_valid:
                unit = int(unit_text)
                fname = model.data(model_index, Role.CustomRole)
                fname_value = self._file_name(self.unit)
                if unit != self.unit:
                    data = self.file_combo.findData(unit, Role.IdRole)
                    is_valid = data < 0
                    is_valid = is_valid or \
                               self._check_file_conflicts(unit, fname)[1]
                    is_valid = is_valid and \
                               self._check_unit_conflicts(unit, file_unit)
                if fname_value not in (None, fname):
                    is_valid = is_valid and \
                               self._check_file_conflicts(unit, fname)[0] \
                               and self._check_unit_conflicts(unit, file_unit)

            color = Q.Qt.black if is_valid else Q.Qt.red
            pal = self.unit_edit.palette()
            pal.setColor(self.unit_edit.foregroundRole(), color)
            self.unit_edit.setPalette(pal)

            is_attr_valid = self.attr_combo.currentIndex() >= 0

            pal = self.attr_combo.palette()
            pal.setColor(self.attr_combo.foregroundRole(), color)
            self.attr_combo.setPalette(pal)

            is_valid = is_file_valid and is_valid and is_attr_valid

        return is_valid

    def _file_name(self, unit):
        """
        Get filename associated with the unit in the current state.

        Arguments:
            unit (int): logical unit.
        """
        model = self.file_combo.model()
        index = self.file_combo.findData(unit, Role.IdRole)
        if index < 0:
            return None
        model_index = model.index(index, 0)
        return model.data(model_index, Role.CustomRole)

    def _check_file_conflicts(self, unit, fname):
        """
        Checks for file conflicts: same file, two different units.
        """
        model = self.file_combo.model()
        return model.file_conflict(unit, fname)

    def _check_unit_conflicts(self, unit, file_unit):
        """
        Checks for unit conflicts: same unit, two different files.

        Arguments:
           unit (int): unit freshly entered by the user.
           file_unit(int): unit corresponding to the file in the combo.
        """
        model = self.file_combo.model()
        fname = self._file_name(file_unit)
        return model.unit_conflict(unit, fname)

    def requiredButtons(self): # pragma pylint: disable=no-self-use
        """Redefined from *EditionWidget*."""
        return Q.QDialogButtonBox.Ok | Q.QDialogButtonBox.Cancel

    def applyChanges(self):
        """Redefined from *EditionWidget*."""

        # file name
        combo_index = self.file_combo.currentIndex()
        index = self.file_combo.model().index(combo_index, 0)
        filename = index.model().data(index, Role.CustomRole)

        # unit
        unit = int(self.unit_edit.text())

        # inout
        attr = self.attr_combo.currentData()

        # embedded
        embedded = self.embedded_check.isChecked()

        # transfer file
        self.file_combo.model().transferFile(filename)

        # modify data model
        if self.mode == UnitPanel.CreateMode:
            node = File(self.node, -1)
        else:
            node = self.node
        node.unit = unit
        node.filename = filename
        if not node.is_forced_attr:
            node.attr = attr
            node.embedded = embedded

        # commit changes
        self.astergui().study().commit(self.controllerName())

        # update GUI
        self.astergui().update()
