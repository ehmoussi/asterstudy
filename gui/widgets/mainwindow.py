# -*- coding: utf-8 -*-

# Copyright 2016-2017 EDF R&D
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
Main Window
-----------

The module implements main window of the AsterStudy application.

For more details refer to *MainWindow* class.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

from common import update_visibility

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class MainWindow(Q.QMainWindow):
    """Main window that handles close events."""

    closing = Q.pyqtSignal("QCloseEvent")
    """
    Signal: emitted when main window is closing.

    Arguments:
        event (QCloseEvent): Close event.
    """

    def __init__(self, astergui):
        """
        Create window.

        Arguments:
            astergui (AsterGui): Parent *AsterGui* instance.
        """
        super(MainWindow, self).__init__()
        self._astergui = astergui
        self.readSettings()
        self._initial = True

    def closeEvent(self, event):
        """
        Handle window closing event.

        Emits `closing()` signal.

        Arguments:
            event (QCloseEvent): Close event.
        """
        self.closing.emit(event)
        if event.isAccepted():
            self.writeSettings()

    def readSettings(self):
        """
        Restore window settings from preferences.
        """
        pref_mgr = self._astergui.preferencesMgr()
        size = pref_mgr.value("MainWindow/size", None)
        position = pref_mgr.value("MainWindow/position", None)
        state = pref_mgr.value("MainWindow/state", None)

        if size is None or position is None:
            desktop = Q.QApplication.desktop().availableGeometry(self)
            size = Q.QSize(desktop.width() * 0.7, desktop.height() * 0.7)
            position = Q.QPoint(desktop.width() * 0.15,
                                desktop.height() * 0.15)

        self.resize(size)
        self.move(position)
        if state is not None:
            self.setWindowState(Q.Qt.WindowState(state))

    def showEvent(self, event):
        """
        Show/hide window.

        Restores dock windows and toolbars position at first display.

        Arguments:
            event (QShowEvent): Show event.
        """
        if self._initial:
            pref_mgr = self._astergui.preferencesMgr()
            windows = pref_mgr.value("MainWindow/windows", None)
            if windows is not None:
                self.restoreState(windows)
            toolbars = self.findChildren(Q.QToolBar)
            for toolbar in toolbars:
                if toolbar.parentWidget() == self:
                    update_visibility(toolbar)
            self._initial = False
        super(MainWindow, self).showEvent(event)

    def writeSettings(self):
        """
        Store window settings to preferences.
        """
        pref_mgr = self._astergui.preferencesMgr()
        pref_mgr.setValue("MainWindow/size", self.size())
        pref_mgr.setValue("MainWindow/position", self.pos())
        state = self.windowState() & ~Q.Qt.WindowMinimized
        pref_mgr.setValue("MainWindow/state", state)
        pref_mgr.setValue("MainWindow/windows", self.saveState())
