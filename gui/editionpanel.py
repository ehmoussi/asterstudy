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
Edition Panel
-------------

Implementation of the *Edition Panel* for AsterStudy application.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

from . widgets import HLine

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class EditionPanel(Q.QFrame):
    """Edition Panel implementation."""

    def __init__(self, parent=None):
        """
        Create panel.

        Arguments:
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
        """
        Q.QFrame.__init__(self, parent)

        self.setFrameStyle(Q.QFrame.Box | Q.QFrame.Sunken)
        self.setSizePolicy(Q.QSizePolicy.Expanding, Q.QSizePolicy.Expanding)

        self._icon = Q.QLabel(self)
        self._icon.setSizePolicy(Q.QSizePolicy.Fixed, Q.QSizePolicy.Fixed)
        self._title = Q.QLabel(self)
        base = Q.QWidget(self)
        self._container = Q.QVBoxLayout(base)
        self._container.setContentsMargins(0, 0, 0, 0)
        self._buttonbox = Q.QDialogButtonBox(Q.Qt.Horizontal, self)
        v_layout = Q.QVBoxLayout(self)
        h_layout = Q.QHBoxLayout()
        h_layout.addWidget(self._icon)
        h_layout.addWidget(self._title)
        v_layout.addLayout(h_layout)
        v_layout.addWidget(HLine(self))
        v_layout.addWidget(base)
        v_layout.addWidget(self._buttonbox)

        self._buttonbox.clicked.connect(self._clicked)
        self.hide()

    def editor(self):
        """
        Get current editor.

        Returns:
            QWidget: Current editor (*None* if editor is not set or hidden).
        """
        editor = None
        for i in xrange(self._container.count()):
            wid = self._container.itemAt(i).widget()
            if wid.isVisibleTo(wid.parentWidget()):
                editor = wid
                break
        return editor

    def setEditor(self, editor):
        """
        Set current editor.

        Arguments:
            editor (QWidget): Editor to be set as current one.
        """
        cur_editor = self.editor()
        if cur_editor == editor:
            if cur_editor is not None:
                cur_editor.setFocus()
        else:
            if editor is not None:
                editor.setParent(self.window())
                editor.move(-editor.width(), -editor.height())
                editor.show()
                if editor.isVisibleTo(editor.parentWidget()):
                    self._appendEditor(editor)
                    # set required buttons
                    editor.buttonStatusChanged.connect(self._buttonsChanged)
                    editor.windowTitleChanged.connect(self._windowTitleChanged)
                    editor.pixmapChanged.connect(self._windowTitleChanged)
                    editor.installEventFilter(self)
                    editor.validated.connect(self._validated)
                    owner = self._editorOwner(editor)
                    if owner is None or owner != cur_editor:
                        self._removeEditor(cur_editor)
                else:
                    editor.deleteLater()
            else:
                self._removeEditor(cur_editor)
            self._windowTitleChanged()
            self.setVisible(self.editor() is not None)
            self._buttonsChanged()

    def updateTranslations(self):
        """
        Update translations in GUI elements.
        """
        for i in xrange(self._container.count()):
            wid = self._container.itemAt(i).widget()
            if hasattr(wid, "updateTranslations"):
                wid.updateTranslations()

    def eventFilter(self, obj, event):
        """
        Event filter to treat close event of the editor.

        Arguments:
            obj (QObject): Watched object.
            event (QEvent): Event being processed.

        Returns:
            bool: *True* to filtered out event; *False* otherwise.
        """
        if obj == self.editor() and isinstance(event, Q.QCloseEvent):
            self.setEditor(None)
        return False

    def keyPressEvent(self, event):
        """
        Process key press events.

        Manages *Escape* key pressing.

        Arguments:
            event (QKeyPressEvent): Key press event.
        """
        if self.editor() is not None:
            if event.key() == Q.Qt.Key_Escape:
                buttonlist = self._buttonbox.buttons()
                buttonlist.reverse()
                for button in buttonlist:
                    button_id = self._buttonbox.standardButton(button)
                    button_role = self._buttonbox.buttonRole(button)
                    if button_role == Q.QDialogButtonBox.RejectRole:
                        self.editor().perform(button_id)
                        event.accept()
                        break
            elif event.key() in (Q.Qt.Key_Enter, Q.Qt.Key_Return):
                self.editor().validate()

    def _appendEditor(self, editor):
        """
        Append editor to the internal stack of editors.
        """
        if editor is None:
            return

        self._container.addWidget(editor)
        editor.setVisible(True)
        for i in xrange(self._container.count()):
            wid = self._container.itemAt(i).widget()
            if wid is not None and wid != editor:
                wid.hide()

    def _removeEditor(self, editor):
        """
        Remove editor.

        Arguments:
            editor (QWidget): Editor being removed.
        """
        if editor is None:
            return

        owner = self._editorOwner(editor)
        editor.hide()
        self._container.removeWidget(editor)

        editor.close()
        editor.deleteLater()

        act_wid = None
        for i in xrange(self._container.count()):
            wid = self._container.itemAt(i).widget()
            if wid == owner:
                act_wid = owner
                break

        if act_wid is None and self._container.count() > 0:
            act_wid = \
                self._container.itemAt(self._container.count() - 1).widget()

        if act_wid is not None:
            act_wid.show()

    @Q.pyqtSlot()
    def _buttonsChanged(self):
        """
        Slot to process button status change signal from
        *Edition Widget*.
        """
        edit = self.editor()
        if edit is not None:
            button_ids = edit.requiredButtons()
            def_btn = edit.defaultButton()
            if edit.isReadOnly():
                # Remove buttons 'Ok' and 'Apply'
                # Replace button 'Cancel' by 'Close'
                button_ids = button_ids & ~Q.QDialogButtonBox.Ok
                button_ids = button_ids & ~Q.QDialogButtonBox.Apply
                if button_ids & Q.QDialogButtonBox.Cancel:
                    button_ids = button_ids & ~Q.QDialogButtonBox.Cancel
                    button_ids = button_ids | Q.QDialogButtonBox.Close
            self._buttonbox.setStandardButtons(button_ids)
            if def_btn is not None and def_btn & button_ids:
                self._buttonbox.button(def_btn).setDefault(True)
            for button in self._buttonbox.buttons():
                button_id = self._buttonbox.standardButton(button)
                button.setEnabled(edit.isButtonEnabled(button_id))

    @Q.pyqtSlot("QAbstractButton*")
    def _clicked(self, button):
        """
        Transfer button click event to the editor.

        Arguments:
            button (QAbstractButton): Button being clicked.
        """
        edit = self.editor()
        if edit is not None:
            button_id = self._buttonbox.standardButton(button)
            edit.perform(button_id)

    def _windowTitleChanged(self):
        """
        Called when editor's title or pixmal is changed.
        """
        edit = self.editor()
        self._title.setText('' if edit is None else edit.windowTitle())
        self._icon.setPixmap(Q.QPixmap() if edit is None else edit.pixmap())
        self._icon.setVisible(not self._icon.pixmap().isNull())

    # pragma pylint: disable=no-self-use
    def _editorOwner(self, editor):
        """
        Get editor's owner.

        Arguments:
            editor (QWidget): Editor.

        Returns:
            any: Editor's owner.
        """
        owner = None
        if editor is not None and hasattr(editor, "controllerOwner"):
            owner = editor.controllerOwner()
        return owner

    def _validated(self):
        """Called when user validates input."""
        editor = self.sender()
        if editor != self.editor():
            return
        def_btn = editor.defaultButton()
        if def_btn is None:
            return
        if def_btn & self._buttonbox.standardButtons():
            self._buttonbox.button(def_btn).click()
