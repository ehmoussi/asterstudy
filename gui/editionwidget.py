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
Edition Widget
--------------

Base class for editor widget used in the *Edition Panel*
of AsterStudy application.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class EditionWidget(Q.QWidget):
    """
    *EditionWidget* is the base class that provides common functionality
    for the editing operations performed within the *Edition Panel*. All
    editor widgets must inherit this class.

    By default, the editor shows 3 standard buttons: *Ok*, *Apply* and
    *Close*, all of them are always enabled. The widget can be closed by
    the buttons *Close* or *Cancel*. There are no special actions for
    other buttons.

    To customize the behavior of the editor, it is necessary to create
    new class inheriting from *EditionWidget* and override the
    following methods:

    - `requiredButtons()`: Set-up buttons to be shown for the editor.
      The buttons can be changed at any time.
    - `isButtonEnabled()`: Enable/disable particular button depending
      on certain condition.
    - `updateButtonStatus()`: Normally it is not necessary to override
      this method. This method can be called at any time when it is
      necessary to show/hide or enable/disable buttons.
    - `perform()`: Perform corresponding action when a particular button
      is clicked. Instead of overriding this method, `applyChanges()`
      method may be customized.
    - `applyChanges()`: Apply user's input. Called when *Apply* or *OK*
      button is pressed.
    - `canClose()`: Check if the editor can be closed.

    Please refer to the documentation of each particular methods for
    more details.
    """

    buttonStatusChanged = Q.pyqtSignal()
    """
    Signal: emitted when configuration of buttons or their status is
    changed.
    """

    pixmapChanged = Q.pyqtSignal()
    """
    Signal: emitted when editor's pixmap is changed.
    """

    validated = Q.pyqtSignal()
    """
    Signal: emitted when user validates input.
    """

    def __init__(self, parent=None, **kwargs):
        """
        Create widget.

        Arguments:
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
        """
        Q.QWidget.__init__(self, parent, **kwargs)
        self._readonly = False
        self._pixmap = Q.QPixmap()

    def isReadOnly(self):
        """
        Get the *Read only* state of editor widget.

        Returns:
            bool: *Read only* state.
        """
        return self._readonly

    def setReadOnly(self, on):
        """
        Change the *Read only* state of editor widget.

        Arguments:
            on (bool): *Read only* state.
        """
        self._readonly = on

    def pixmap(self):
        """
        Get editor's pixmap.

        Returns:
            QPixmap: Editor's pixmap (null pixmap by default).
        """
        return self._pixmap

    def setPixmap(self, pixmap):
        """
        Set editor's pixmap.

        Emits `pixmapChanged()` signal.

        Arguments:
            QPixmap: Editor's pixmap.
        """
        self._pixmap = pixmap
        self.pixmapChanged.emit()

    # pragma pylint: disable=no-self-use
    def requiredButtons(self):
        """
        Get the combination of standard buttons required for editor
        widget.

        The return value is a combination of the flags from
        *QDialogButtonBox.StandardButton* enumeration. This combination
        is used by *Edition Panel* to show / hide required buttons.

        This method is called each time the combination of buttons is
        changed, for instance, when editor's state changes. To signal
        about such change, the method `updateButtonStatus()` can be
        called.

        Default value corresponds to *OK*, *Apply* and *Close* buttons.

        Returns:
            int: Buttons set (combination of
            *QDialogButtonBox.StandardButton* enumerators).
        """
        return Q.QDialogButtonBox.Ok | \
            Q.QDialogButtonBox.Apply | \
            Q.QDialogButtonBox.Close

    def defaultButton(self):
        """
        Get button to be used for default action.

        Default implementation returns *None*.
        """
        return None

    # pragma pylint: disable=unused-argument, no-self-use
    def isButtonEnabled(self, button):
        """
        Check if specified *button* is enabled.

        This method is called by *Edition Panel* to check if the
        particular button should be enabled or disabled. By default,
        this method always returns *True*.

        Arguments:
            button (QDialogButtonBox.StandardButton): Button being
                checked.

        Returns:
            bool: *True* if button should be enabled; *False* otherwise.
        """
        return True

    @Q.pyqtSlot()
    def updateButtonStatus(self):
        """
        Inform that buttons combination or status is changed.

        Emits `buttonStatusChanged()` signal.
        """
        self.buttonStatusChanged.emit()

    def accept(self):
        """
        Check input.

        This method is called before applying changes to data model.
        If it returns *False*, the operation is not performed.

        Default implementation returns *True*.

        Returns:
            bool: *True* if user's input is valid and can be accepted.
        """
        return True

    def perform(self, button):
        """
        Perform action for corresponding *button*.

        This method is called when the corresponding button in the
        *Edition Panel* is clicked. By default, it does nothing for all
        buttons except *Cancel* and *Close*. For these two buttons the
        method calls `canClose()` to check if the editor can be closed
        and, if yes, closes it.

        The default behavior can be redefined in successors.

        Arguments:
            button (QDialogButtonBox.StandardButton): Button being
                clicked.
        """
        if button in [Q.QDialogButtonBox.Ok, Q.QDialogButtonBox.Apply]:
            if not self.accept():
                return
            self.applyChanges()

        if button in [Q.QDialogButtonBox.Ok, Q.QDialogButtonBox.Cancel,
                      Q.QDialogButtonBox.Close]:
            if self.canClose():
                self.close()
                self.postClose(button)
        else:
            self.updateButtonStatus()

    # pragma pylint: disable=no-self-use
    def applyChanges(self):
        """
        Apply the user's input.

        This method is by default called from `perform()` when *Apply*
        or *OK* button is pressed. Instead of overriding `perform()`
        method, for most cases it is enough to override this method in
        order to perform corresponding actions.

        Default implementation of this method does nothing.
        """
        pass

    # pragma pylint: disable=no-self-use
    def canClose(self):
        """
        Check if editor can be closed.

        This method should return *True* if the editor widget can be
        closed or *False* otherwise. It can be redefined in successor
        classes. Default implementation always returns *True*.

        Returns:
            bool: *True* if editor can be closed; *False* otherwise.
        """
        return True

    def setVisible(self, visible):
        """
        Reimplemented from base class, in order to automatically set
        input focus to editor widget when it is shown.

        Arguments:
            visible (bool): *True* when widget is being shown; *False*
                when it is being *hidden*.
        """
        super(EditionWidget, self).setVisible(visible)
        if visible:
            self.setFocus(Q.Qt.OtherFocusReason)

    def postClose(self, button):
        """
        Perform particular action after the editor is closed.

        This method can be redefined in successors. Default
        implementation does nothing.

        Arguments:
            button (QDialogButtonBox.StandardButton): Button being
                clicked.
        """
        pass

    @Q.pyqtSlot()
    def validate(self):
        """
        Validate user's input.

        Emits `validated()` signal.
        """
        self.validated.emit()
