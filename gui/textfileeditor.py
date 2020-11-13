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
File text editor
-----------------

The module implements an editor for text file.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

from common import (get_base_name, read_file, load_pixmap, to_unicode,
                    translate, write_file)

from . behavior import behavior
from . controller import WidgetController
from . editionwidget import EditionWidget
from . widgets import Dialog

__all__ = ["TextFileEditor", "TextFileDialog"]

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class TextFileEditor(EditionWidget, WidgetController):
    """Text file editor widget."""

    def __init__(self, file_name, astergui, parent=None, **kwargs):
        """
        Create editor.

        Arguments:
            file_name (str): File path.
            astergui (AsterGui): AsterGui instance.
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
            **kwargs: Keyword arguments.
        """
        super(TextFileEditor, self).__init__(parent=parent,
                                             name=translate("AsterStudy",
                                                            "Edit file"),
                                             astergui=astergui, **kwargs)
        self.file_name = file_name
        self.prev_state = _text2unicode(read_file(file_name))

        title = translate("AsterStudy", "Edit file") + " '{}'"
        self.setWindowTitle(title.format(get_base_name(file_name)))
        self.setPixmap(load_pixmap("as_pic_edit_file.png"))

        self.editor = Q.QTextEdit(self)
        self.editor.setLineWrapMode(Q.QTextEdit.NoWrap)
        self.setLayout(Q.QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self.editor)

        self.editor.setPlainText(self.prev_state)
        self.editor.textChanged.connect(self.updateButtonStatus)

    def isButtonEnabled(self, button):
        """
        Redefined from *EditionWidget* class.
        """
        result = True
        if button in [Q.QDialogButtonBox.Ok, Q.QDialogButtonBox.Apply]:
            result = self.file_name is not None and \
                _text2unicode(self.editor.toPlainText()) != self.prev_state
        return result

    def applyChanges(self):
        """
        Redefined from *EditionWidget* class.
        """
        self.prev_state = _text2unicode(self.editor.toPlainText())
        try:
            write_file(self.file_name, self.prev_state)
        except IOError:
            message = translate("AsterStudy", "Cannot write file.")
            Q.QMessageBox.critical(self, "AsterStudy", message)

    def setReadOnly(self, on):
        """Redefined from EditionWidget."""
        super(TextFileEditor, self).setReadOnly(on)
        self.editor.setReadOnly(on)


class TextFileDialog(Dialog):
    """Text file edition dialog."""

    def __init__(self, file_name, read_only=False, parent=None):
        """
        Create dialog.

        Arguments:
            file_name (str): File path.
            read_only (Optional[bool]): Read-only mode. Defaults to
                *False*.
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
        """
        super(TextFileDialog, self).__init__(parent)

        self.file_name = file_name
        self.prev_state = _text2unicode(read_file(file_name))

        title = translate("TextFileDialog", "View file") if read_only \
            else translate("TextFileDialog", "Edit file")
        self.setWindowTitle(title)
        self.setObjectName("text_file_dlg")

        self.editor = Q.QTextEdit(self.frame())
        self.editor.setLineWrapMode(Q.QTextEdit.NoWrap)
        self.editor.setObjectName("text_file_dlg_editor")
        self.frame().layout().addWidget(self.editor)

        if read_only:
            self.setStandardButtons(Q.QDialogButtonBox.Close)
            button = self.button(Q.QDialogButtonBox.Close)
            button.clicked.connect(self.reject)

        self.editor.setPlainText(self.prev_state)
        self.editor.textChanged.connect(self.updateButtonStatus)

        self.editor.setFocus()
        self.editor.setReadOnly(read_only)

        self.updateButtonStatus()
        self.resize(500, 500)

    def updateButtonStatus(self):
        """Enable / disable control buttons."""
        if self.okButton() is not None:
            enabled = self.file_name is not None and \
                _text2unicode(self.editor.toPlainText()) != self.prev_state
            self.okButton().setEnabled(enabled)

    def accept(self):
        """
        Redefined from *Dialog* class.
        """
        text = _text2unicode(self.editor.toPlainText())
        try:
            write_file(self.file_name, text)
        except IOError:
            message = translate("AsterStudy", "Cannot write file.")
            Q.QMessageBox.critical(self, "AsterStudy", message)
        super(TextFileDialog, self).accept()


def _text2unicode(text):
    """Conditionally convert text to unicode."""
    if behavior().editor_use_unicode:
        return to_unicode(text)
    else:
        return text
