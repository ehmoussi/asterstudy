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
Stage text editor
-----------------

The module implements an editor for text stage.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

from common import auto_dupl_on, load_pixmap, translate
from datamodel import CATA

from . controller import WidgetController
from . editionwidget import EditionWidget
from . widgets import TextEditor

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class StageTextEditor(EditionWidget, WidgetController):
    """Stage text editor widget."""

    def __init__(self, stage, astergui, parent=None, **kwargs):
        """
        Create editor.

        Arguments:
            stage (Stage): Stage to edit.
            astergui (AsterGui): AsterGui instance.
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
            **kwargs: Keyword arguments.
        """
        super(StageTextEditor, self).__init__(parent=parent,
                                              name=translate("StageTextEditor",
                                                             "Edit stage"),
                                              astergui=astergui, **kwargs)

        self.stage = stage
        self.prev_state = stage.get_text()

        title = translate("StageTextEditor", "Edit stage '{}'")
        self.setWindowTitle(title.format(stage.name))
        self.setPixmap(load_pixmap("as_pic_edit_stage.png"))

        self.editor = TextEditor(self)
        v_layout = Q.QVBoxLayout(self)
        v_layout.addWidget(self.editor)
        commands = [j for i in [CATA.get_category(i) \
                                    for i in CATA.get_categories()] for j in i]
        self.editor.setKeywords(commands, 0, Q.QColor("#ff0000"))
        self.editor.setText(self.prev_state)
        self.editor.textChanged.connect(self.updateButtonStatus)
        self.setFocusProxy(self.editor)
        astergui.preferencesChanged.connect(self.editor.updateSettings)
        self.editor.updateSettings(self.astergui().preferencesMgr())

    def isButtonEnabled(self, button):
        """
        Redefined from *EditionWidget* class.
        """
        result = True
        if button in [Q.QDialogButtonBox.Ok, Q.QDialogButtonBox.Apply]:
            result = self.stage is not None and \
                self.editor.text() != self.prev_state
        return result

    def applyChanges(self):
        """
        Redefined from *EditionWidget* class.
        """
        with auto_dupl_on(self.astergui().study().activeCase):
            self.prev_state = self.editor.text()
            self.stage.set_text(self.prev_state)
            msg = translate("StageTextEditor", "Edit stage")
            self.astergui().study().commit(msg)
            self.astergui().update()
