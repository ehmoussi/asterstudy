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
Test utilities for GUI
----------------------

Auxiliary functions and classes used for testing of AsterStudy
application.

"""

from __future__ import unicode_literals

from PyQt5.Qt import Qt, QAction, QLineEdit, QMenu, pyqtSlot

from common import get_file_name
from datamodel import Validity
from gui import Context, NodeType, check_selection


# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class GuiTester(object):
    """Test actions for GUI."""

    DefaultStudy = 1
    DumpStudy = 2

    def __init__(self, asterstudy):
        """Constructor. Create test actions."""
        self._asterstudy = asterstudy
        self._actions = {}
        #
        action = QAction("Create sample study", asterstudy)
        action.setStatusTip("Create a sample study for testing")
        action.triggered.connect(self._create_sample_study)
        self._actions[self.DefaultStudy] = action
        #
        action = QAction("Dump study", asterstudy)
        action.setStatusTip("Dump study contents to the file")
        action.triggered.connect(self._dump_study)
        self._actions[self.DumpStudy] = action
        self._dump_file_name = None

    def actions(self):
        """Get test actions."""
        return self._actions.values()

    def updateActions(self):
        """Update actions state."""
        has_study = self._asterstudy.study() is not None
        if has_study:
            case = self._asterstudy.study().history.current_case
            self._actions[self.DefaultStudy].setEnabled(case.nb_stages == 0)
        self._actions[self.DumpStudy].setEnabled(has_study)

    def _create_sample_study(self):
        """Create sample study."""
        if self._asterstudy.study() is None:
            self._asterstudy.newStudy()
        case = self._asterstudy.study().history.current_case
        if case.nb_stages > 0:
            return
        stage_1 = case.create_stage()
        stage_1.add_command('DEFI_MATERIAU', 'material_1')
        stage_1.add_command('DEFI_MATERIAU', 'material_2')
        stage_1.add_command('AFFE_MODELE', 'model')
        stage_1.add_command('DEFI_MATERIAU', 'material_3')
        case.create_stage()
        self._asterstudy.study().commit("Sample study creation")
        self._asterstudy.update()

    def _dump_study(self):
        if self._asterstudy.study() is None:
            return
        if self._dump_file_name is None:
            file_name = get_file_name(0, self._asterstudy.mainWindow(),
                                      "Dump Study", "", "*.txt")
            if file_name:
                self._dump_file_name = file_name
        if self._dump_file_name is not None:
            try:
                dump_file = open(self._dump_file_name, "w")
                dump_file.write(self._get_repr())
                dump_file.close()
            except IOError:
                pass

    def _get_repr(self):
        """
        Dump model to a string representation.

        Returns:
            str: String representation of whole data model.
        """
        result = []

        history = self._asterstudy.study().history
        nodes = (history.get_node(uid) for uid in history.uids)
        for node in nodes:
            result.append(repr(node))

        return '\n'.join(result) + "\n"

class DebugWidget(QLineEdit):
    """
    Helper widget for advanced testing with Squish.

    To use it:

    #. Call `setText(property)`: specify property to check for currently
       selected object.
    #. Call `text()` to get value of the property.
    """

    def __init__(self, astergui):
        """
        Create widget.

        Arguments:
            astergui (AsterGui): Parent AsterGui instance.
        """
        QLineEdit.__init__(self, astergui.mainWindow())
        self.setObjectName("DebugWidget")
        self.astergui = astergui
        self.setReadOnly(True)
        self.textChanged.connect(self.process)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._contextMenu)

        self.props = {
            "validity" : self._validity,
            "edit mode" : self._editMode
            }

    def process(self, text):
        """
        Called when `setText()` is called (programmatically).

        Arguments:
            text (str): Property being checked.
        """
        self.blockSignals(True)
        func = self.props.get(text)
        if func:
            func()
        self.blockSignals(False)

    def _validity(self):
        selected = self.astergui.selected(Context.DataSettings)
        if check_selection(selected, size=1):
            node = self.astergui.study().node(selected[0])
            validity = node.check()
            text = "valid"
            if validity != Validity.Nothing:
                text = "invalid: "
                what = []
                if validity & Validity.Syntaxic:
                    what.append("syntaxic")
                if validity & Validity.Dependency:
                    what.append("dependency")
                if validity & Validity.Naming:
                    what.append("naming")
                text += ", ".join(what)
            self.setText(text)

    def _editMode(self):
        selected = self.astergui.selected(Context.DataSettings)
        if check_selection(selected, size=1, typeid=NodeType.Stage):
            stage = self.astergui.study().node(selected[0])
            self.setText("graphical" if stage.is_graphical_mode() else "text")

    @pyqtSlot("QPoint")
    def _contextMenu(self, pos):
        menu = QMenu(self)
        for prop in self.props:
            menu.addAction(prop)
        action = menu.exec_(self.mapToGlobal(pos))
        if action is not None:
            self.setText(action.text())
