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
Operation controller
--------------------

Implementation of Aster Study operations management.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

from common import translate
from . widgets import MessageBox

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class Controller(object):
    """
    Base class for AsterStudy operation.
    """

    _active = []

    def __init__(self, name, astergui, owner=None, **kwargs):
        """
        Create controller.

        Arguments:
            name (str): Operation name.
            astergui (AsterGui): Parent *AsterGui* instance.
            owner (Optional[Controller]): Controller's owner. Defaults
                to *None*.
            kwargs: Keyword arguments.
        """
        super(Controller, self).__init__(**kwargs)

        self._controllername = name
        self._astergui = astergui
        self._owner = owner

    def astergui(self):
        """
        Get reference to AsterGui instance.

        Returns:
            AsterGui: AsterGui instance.
        """
        return self._astergui

    def controllerName(self):
        """
        Get operation name.

        Returns:
            str: Operation's name.
        """
        return self._controllername

    def controllerOwner(self):
        """
        Get controller's owner.

        Returns:
            Controller: Controller that owns this one.
        """
        return self._owner

    @classmethod
    def active(cls):
        """
        Get active controller.

        Returns:
            Controller: Active controller.
        """
        return Controller._active[len(Controller._active) - 1] \
            if len(Controller._active) else None

    @classmethod
    def activate(cls, ctrl):
        """
        Set active controller.

        Arguments:
            ctrl (Controller): Controller being activated.
        """
        cond = (None, ctrl, ctrl.controllerOwner())
        while Controller.active() not in cond:
            Controller.deactivate(Controller.active())

        if Controller.active() != ctrl:
            Controller._active.append(ctrl)

    @classmethod
    def deactivate(cls, ctrl):
        """
        Deactivate specified controller (and all its children).

        Arguments:
            ctrl (Controller): Controller being deactivated.
        """
        if ctrl not in Controller._active:
            return

        index = Controller._active.index(ctrl)
        while len(Controller._active) > index:
            last = Controller._active.pop()
            last.controllerAbort()

    def isActive(self):
        """
        Check if this controller is active one.

        Returns:
            bool: *True* if this controller is active one: *False*
            otherwise.
        """
        return Controller.active() == self

    def controllerStart(self):
        """
        Start operation.

        Checks possibility to start operation; starts it if possible and
        returns the status.

        Returns:
            bool: *True* if operation is successfully started; *False*
            otherhwise.
        """
        current = Controller.active()
        if current == self:
            return True

        check = True
        if current is not None and current != self.controllerOwner():
            title = translate("Controller", "Operation performed")
            text = translate("Controller",
                             "There is executed operation. "
                             "Do you want to break it and lose all "
                             "input data?")
#            text = text.format(current.controllerName())
            key = MessageBox.question(Q.QApplication.activeWindow(),
                                      title, text,
                                      Q.QMessageBox.Yes | Q.QMessageBox.No,
                                      Q.QMessageBox.Yes, noshow="break",
                                      prefmgr=self._astergui.preferencesMgr())
            check = key == Q.QMessageBox.Yes

        if check:
            Controller.activate(self)
        else:
            self.controllerAbort()
        return check

    def controllerCommit(self):
        """
        Commit changes and finish operation.
        """
        self.controllerStop()

    def controllerAbort(self):
        """
        Abort changes and abort operation.
        """
        self.controllerStop()

    def controllerStop(self):
        """
        Stop operation and deactivate it.
        """
        Controller.deactivate(self)

    @classmethod
    def execute(cls, opname, function, astergui, **kwargs):
        """
        Execute specified function as an operation.

        Arguments:
            opname (str): Operation's  name.
            function (function): Function to execute.
            astergui (AsterGui): *AsterGui* instance.
            kwargs: Arguments to be passed to the function.
        """
        state = True
        ctrl = Controller(opname, astergui)
        state = ctrl.controllerStart()
        if state:
            try:
                if function is not None:
                    function(**kwargs)
            except StandardError:
                state = False
            if state:
                ctrl.controllerCommit()
            else:
                ctrl.controllerAbort()
        return state


class WidgetController(Controller):
    """
    Base class for AsterStudy operations implemented via the widgets.
    """

    class Filter(Q.QObject):
        """Helper class to manage show/hide events for editor widgets."""

        def __init__(self, parent):
            """Create helper."""
            super(WidgetController.Filter, self).__init__(parent)
            parent.installEventFilter(self)

        def eventFilter(self, obj, event):
            """Process events from parent widget."""
            if obj is self.parent():
                if event.type() == Q.QEvent.Show:
                    self.parent().handleShow()
                elif event.type() == Q.QEvent.HideToParent:
                    self.parent().handleHide()
            return False

    def __init__(self, **kwargs):
        """
        Create controller.

        Arguments:
            kwargs: Keyword arguments. See `Controller` class.
        """
        super(WidgetController, self).__init__(**kwargs)
        self.destroyed.connect(self._destroyed) # pragma pylint: disable=no-member
        self.filter = self.Filter(self)

    def handleShow(self):
        """
        Start operation when widget is being shown.
        """
        if not self.isActive():
            self.controllerStart()

    def handleHide(self):
        """
        Stop operation when widget is being hidden to parent.
        """
        if self.isActive():
            self.controllerCommit()

    def controllerAbort(self):
        """
        Abort operation and close widget.
        """
        super(WidgetController, self).controllerAbort()
        self.close() # pragma pylint: disable=no-member

    def _destroyed(self, _):
        """
        Called when widget is being deleted; automatically stops
        operation.
        """
        self.controllerStop()
