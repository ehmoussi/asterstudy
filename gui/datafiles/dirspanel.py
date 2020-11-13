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
Directories panel
-----------------

The module implements `Set-up directories` panel that allows the user
specifying the input and output directories of the case.

For more details, refer to *DirsPanel* class.

"""

from __future__ import unicode_literals
import os

from PyQt5 import Qt as Q

from common import (connect, get_directory, is_subpath, load_pixmap, same_path,
                    translate)

from gui.controller import Controller, WidgetController
from gui.editionwidget import EditionWidget
from . objects import Directory

__all__ = ["DirsPanel", "edit_directory"]

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class DirsPanel(EditionWidget, WidgetController):
    """Directories editor."""

    def __init__(self, astergui, parent=None, **kwargs):
        """
        Create editor.

        Arguments:
            astergui (AsterGui): AsterGui instance.
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
            **kwargs: Keyword arguments.
        """
        super(DirsPanel, self).__init__(parent=parent,
                                        name=translate("AsterStudy",
                                                       "Set-up directories"),
                                        astergui=astergui, **kwargs)
        title = translate("AsterStudy", "Set-up directories")
        self.setWindowTitle(title)
        self.setPixmap(load_pixmap("as_pic_setup_dirs.png"))
        self.setObjectName("dirs_panel")

        completer = Q.QCompleter(Q.QDirModel(self), self)

        glayout = Q.QGridLayout(self)
        glayout.setContentsMargins(0, 0, 0, 0)

        label = Q.QLabel(translate("DirsPanel", "Input directory"), self)
        glayout.addWidget(label, 0, 0)

        self.in_dir = Q.QLineEdit(self)
        self.in_dir.setCompleter(completer)
        self.in_dir.setObjectName("dirs_panel_in_dir")
        glayout.addWidget(self.in_dir, 0, 1)

        button = Q.QPushButton(translate("AsterStudy", "Browse..."), self)
        button.mode = Directory.InDir
        button.setObjectName("dirs_panel_in_dir_browse")
        connect(button.clicked, self._browse)
        glayout.addWidget(button, 0, 2)

        label = Q.QLabel(translate("DirsPanel", "Output directory"), self)
        glayout.addWidget(label, 1, 0)

        self.out_dir = Q.QLineEdit(self)
        self.out_dir.setCompleter(completer)
        self.out_dir.setObjectName("dirs_panel_out_dir")
        glayout.addWidget(self.out_dir, 1, 1)

        button = Q.QPushButton(translate("AsterStudy", "Browse..."), self)
        button.mode = Directory.OutDir
        button.setObjectName("dirs_panel_out_dir_browse")
        connect(button.clicked, self._browse)
        glayout.addWidget(button, 1, 2)

        glayout.setRowStretch(2, 5)

        case = astergui.study().history.current_case
        self.in_dir.setText(case.in_dir)
        self.in_dir.home(False)
        self.out_dir.setText(case.out_dir)
        self.out_dir.home(False)
        self.setFocusProxy(self.in_dir)

    def requiredButtons(self):
        """Redefined from *EditionWidget* class."""
        return Q.QDialogButtonBox.Ok | Q.QDialogButtonBox.Cancel


    def accept(self):
        """Redefined from *EditionWidget* class."""
        in_dir = self.in_dir.text().strip()
        out_dir = self.out_dir.text().strip()
        if in_dir and out_dir:
            if same_path(in_dir, out_dir):
                message = translate("DirsPanel", "Input and output "
                                    "directories cannot be the same")
                Q.QMessageBox.critical(self, "AsterStudy", message)
                return False
            if is_subpath(in_dir, out_dir) or is_subpath(out_dir, in_dir):
                message = translate("DirsPanel", "Input and output directories"
                                    " cannot be sub-path of each other")
                Q.QMessageBox.critical(self, "AsterStudy", message)
                return False
            if not os.path.exists(in_dir):
                message = translate("DirsPanel", "Input directory '{}' "
                                    "does not exist").format(in_dir)
                Q.QMessageBox.critical(self, "AsterStudy", message)
                return False
        return True

    def applyChanges(self):
        """Redefined from *EditionWidget* class."""
        try:
            case = self.astergui().study().history.current_case
            # first reset both dirs to None to avoid redundant complaints
            case.in_dir = None
            case.out_dir = None
            # then set user's input to the data model
            in_dir = self.in_dir.text().strip()
            out_dir = self.out_dir.text().strip()
            if in_dir:
                case.in_dir = in_dir
            if out_dir:
                case.out_dir = out_dir
            self.astergui().study().commit(self.controllerName())
            self.astergui().update()
        except ValueError:
            self.astergui().study().revert()
            self.astergui().update()
            raise

    def _browse(self):
        """Show standard directory selection dialog."""
        is_in_dir = self.sender().mode == Directory.InDir
        widget = self.in_dir if is_in_dir else self.out_dir
        directory = get_directory(self, widget.text(), is_in_dir)
        if directory:
            widget.setText(directory)
            widget.home(False)


def edit_directory(astergui, directory):
    """
    Edit Input or Output directory

    Arguments:
        astergui (AsterGui): AsterGui instance.
        directory (Directory): *Directory* object.
    """
    if directory is None:
        return
    try:
        case = directory.case
        dir_type = directory.dir_type
        path = directory.directory
        is_in_dir = dir_type == Directory.InDir
        operation_name = translate("AsterStudy", "Set-up directories")
        ctr = Controller(operation_name, astergui)
        if ctr.controllerStart():
            path = get_directory(astergui.mainWindow(), path, is_in_dir)
            if path:
                if is_in_dir:
                    out_dir = case.out_dir
                    if out_dir is not None and same_path(path, out_dir):
                        message = translate("DirsPanel", "Input and output "
                                            "directories cannot be the same")
                        raise ValueError(message)
                    if is_subpath(path, out_dir) or is_subpath(out_dir, path):
                        message = translate("DirsPanel", "Input and output "
                                            "directories cannot be sub-path "
                                            "of each other")
                        raise ValueError(message)
                    if not os.path.exists(path):
                        message = translate("DirsPanel", "Input directory '{}'"
                                            " does not exist").format(path)
                        raise ValueError(message)
                else:
                    in_dir = case.in_dir
                    if in_dir is not None and same_path(path, in_dir):
                        message = translate("DirsPanel", "Input and output "
                                            "directories cannot be the same")
                        raise ValueError(message)
                    if is_subpath(path, in_dir) or is_subpath(in_dir, path):
                        message = translate("DirsPanel", "Input and output "
                                            "directories cannot be sub-path "
                                            "of each other")
                        raise ValueError(message)
                directory.directory = path
                ctr.controllerCommit()
                astergui.study().commit(operation_name)
                astergui.update()
            else:
                ctr.controllerAbort()
    except Exception as detail: # pragma pylint: disable=broad-except
        ctr.controllerAbort()
        Q.QMessageBox.critical(astergui.mainWindow(), "AsterStudy",
                               detail.args[0])
