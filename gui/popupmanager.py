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
Popup menu management
---------------------

Implementation of context menu management for AsterStudy application.

"""

from __future__ import unicode_literals

from PyQt5.Qt import QMenu

from gui import ActionType, Context, NodeType

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class ContextMenuMgr(object):
    """Context menu manager."""

    def __init__(self, astergui, context):
        """
        Create menu manager.

        Arguments:
            astergui (AsterGui): Parent AsterGui instance.
            context (int): Context requesting menu (see `Context`).
        """
        self._astergui = astergui
        self._context = context

    def showContextMenu(self, widget, pos):
        """
        Show context menu.

        Arguments:
            widget (QWidget): Widget displaying popup menu.
            pos (QPoint): Mouse cursor position.
        """
        menu = QMenu(self._astergui.mainWindow())
        self._add_actions(menu, self._context)
        if len(menu.actions()) > 0:
            menu.exec_(widget.mapToGlobal(pos))

    def _addDataSettingsActions(self, menu, selected):
        """
        Fill in the menu with the actions for DataSettings context.

        Arguments:
            menu (QMenu): Popup menu.
            selected (list<Entity>): List of selected entities.
        """
        if len(selected) == 1:
            selected = selected[0]
            node = self._astergui.study().node(selected)
            curcase = self._astergui.study().history.current_case
            if selected.type == NodeType.Command:
                self._add(menu, self._astergui.action(ActionType.Edit), True)
                self._add(menu, self._astergui.action(ActionType.View), True)
                self._add(menu, self._astergui.action(ActionType.Rename))
                self._add(menu, self._astergui.action(ActionType.Delete))
                self._add(menu, None)
                self._add(menu, self._astergui.action(ActionType.Copy))
                self._add(menu, self._astergui.action(ActionType.Cut))
                self._add(menu, self._astergui.action(ActionType.Paste))
                self._add(menu, None)
                self._add(menu, self._astergui.action(ActionType.Duplicate))
                self._add(menu, None)
                self._add(menu, self._astergui.action(ActionType.EditComment))
                self._add(menu, None)
                self._add(menu, self._astergui.action(ActionType.LinkToDoc))
            elif selected.type == NodeType.Variable:
                self._add(menu, self._astergui.action(ActionType.Edit), True)
                self._add(menu, self._astergui.action(ActionType.View), True)
                self._add(menu, self._astergui.action(ActionType.Rename))
                self._add(menu, self._astergui.action(ActionType.Delete))
                self._add(menu, None)
                self._add(menu, self._astergui.action(ActionType.Copy))
                self._add(menu, self._astergui.action(ActionType.Cut))
                self._add(menu, self._astergui.action(ActionType.Paste))
                self._add(menu, None)
                self._add(menu, self._astergui.action(ActionType.Duplicate))
                self._add(menu, None)
                self._add(menu, self._astergui.action(ActionType.EditComment))
            elif selected.type == NodeType.Comment:
                self._add(menu, self._astergui.action(ActionType.Edit), True)
                self._add(menu, self._astergui.action(ActionType.Delete))
                self._add(menu, None)
                self._add(menu, self._astergui.action(ActionType.Copy))
                self._add(menu, self._astergui.action(ActionType.Cut))
                self._add(menu, self._astergui.action(ActionType.Paste))
                self._add(menu, None)
                self._add(menu, self._astergui.action(ActionType.Duplicate))
            elif selected.type == NodeType.Macro:
                self._add(menu, self._astergui.action(ActionType.Paste))
            elif selected.type == NodeType.Category:
                self._add(menu, self._astergui.action(ActionType.Delete))
                self._add(menu, None)
                self._add(menu, self._astergui.action(ActionType.Paste))
            elif selected.type == NodeType.Stage:
                self._add(menu, self._astergui.action(ActionType.Edit), True)
                self._add(menu, self._astergui.action(ActionType.View), True)
                self._add(menu, self._astergui.action(ActionType.Rename))
                self._add(menu, self._astergui.action(ActionType.Delete))
                self._add(menu, None)
                self._add(menu, self._astergui.action(ActionType.
                                                      StageToGraphical))
                self._add(menu, self._astergui.action(ActionType.StageToText))
                self._add(menu, self._astergui.action(ActionType.ExportStage))
                self._add(menu, None)
                self._add(menu, self._astergui.action(ActionType.Paste))
                self._add(menu, None)
                self._add(menu, self._astergui.action(ActionType.AddVariable))
                self._add(menu, None)
                if node.is_graphical_mode():
                    self._add(menu, self._astergui.action(ActionType.ShowAll))
                    for action in self._astergui.cmd_actions.values():
                        self._add(menu, action)
            elif selected.type == NodeType.Case:
                self._add(menu, self._astergui.action(ActionType.AddStage),
                          True)
                self._add(menu, self._astergui.action(ActionType.ImportStage))
                self._add(menu,
                          self._astergui.action(ActionType.ImportTextStage))
                self._add(menu, None)
                self._add(menu,
                          self._astergui.action(ActionType.ExportCaseTest))
                if selected.uid == curcase.uid:
                    self._add(menu, self._astergui.action(ActionType.BackUp))
                    self._add(menu, None)
                    action = self._astergui.action(ActionType.SetupDirs)
                    self._add(menu, action)
                self._add(menu,
                          self._astergui.action(ActionType.EditDescription))
                self._add(menu, None)
                self._add(menu, self._astergui.action(ActionType.ReRun))
        else:
            self._add(menu, self._astergui.action(ActionType.Delete))
            self._add(menu, None)
            self._add(menu, self._astergui.action(ActionType.Copy))
            self._add(menu, self._astergui.action(ActionType.Cut))
            self._add(menu, None)
            self._add(menu, self._astergui.action(ActionType.Duplicate))
        self._add(menu, None)
        self._add(menu, self._astergui.action(ActionType.Find))

    def _addDashboardActions(self, menu, selected):
        """
        Fill in the menu with the actions for Dashboard and Cases contexts.

        Arguments:
            menu (QMenu): Popup menu.
            selected (list<Entity>): List of selected entities.
        """
        curcase = self._astergui.study().history.current_case
        if len(selected) == 1:
            selected = selected[0]
            if selected.type == NodeType.Case:
                self._add(menu,
                          self._astergui.action(ActionType.ActivateCase), True)
                self._add(menu, None)
                self._add(menu,
                          self._astergui.action(ActionType.Rename))
                self._add(menu,
                          self._astergui.action(ActionType.Delete))
                self._add(menu,
                          self._astergui.action(ActionType.DeleteResults))
                self._add(menu,
                          self._astergui.action(ActionType.EditDescription))
                self._add(menu, None)
                self._add(menu,
                          self._astergui.action(ActionType.ExportCaseTest))
                if selected.uid == curcase.uid:
                    self._add(menu,
                              self._astergui.action(ActionType.BackUp))
                    self._add(menu, None)
                    self._add(menu,
                              self._astergui.action(ActionType.SetupDirs))
                self._add(menu,
                          self._astergui.action(ActionType.CopyAsCurrent))
        else:
            is_supported = True
            for s in selected:
                if s.type != NodeType.Case or \
                        curcase == self._astergui.study().node(s):
                    is_supported = False
                    break
            if is_supported:
                self._add(menu, self._astergui.action(ActionType.Delete))

    def _addDataFilesActions(self, menu, selected):
        """
        Fill in the menu with the actions for DataFiles contexts.

        Arguments:
            menu (QMenu): Popup menu.
            selected (list<QModelIndex>): List of selected indices.
        """
        if len(selected) == 1:
            selected = selected[0]
            if selected.type == NodeType.Case:
                self._add(menu, self._astergui.action(ActionType.SetupDirs))
            if selected.type == NodeType.Dir:
                self._add(menu, self._astergui.action(ActionType.Edit), True)
                self._add(menu, self._astergui.action(ActionType.Delete))
                self._add(menu, None)
                self._add(menu, self._astergui.action(ActionType.Browse))
                self._add(menu, None)
                self._add(menu, self._astergui.action(ActionType.Remove))
            if selected.type == NodeType.Stage:
                self._add(menu, self._astergui.action(ActionType.AddFile),
                          True)
            elif selected.type == NodeType.Unit:
                self._add(menu, self._astergui.action(ActionType.Edit), True)
                self._add(menu, self._astergui.action(ActionType.View), True)
                self._add(menu, self._astergui.action(ActionType.Delete))
                self._add(menu, None)
                self._add(menu, self._astergui.action(ActionType.EmbedFile))
                self._add(menu, None)
                self._add(menu, self._astergui.action(ActionType.Browse))
                self._add(menu, None)
                self._add(menu, self._astergui.action(ActionType.OpenInEditor))
                self._add(menu,
                          self._astergui.action(ActionType.OpenInParaVis))
            elif selected.type == NodeType.Command:
                self._add(menu, self._astergui.action(ActionType.GoTo), True)

    def _add_actions(self, menu, context):
        """
        Fill in the menu with the actions for given context.

        Arguments:
            menu (QMenu): Popup menu.
            context (int): Menu context (see `Context`).
        """
        if context in (Context.DataSettings,):
            selected = self._astergui.selected(context)
            self._addDataSettingsActions(menu, selected)

        elif context in (Context.Dashboard, Context.Cases):
            selected = self._astergui.selected(context)
            self._addDashboardActions(menu, selected)

        elif context in (Context.DataFiles,):
            selected = self._astergui.selected(context)
            self._addDataFilesActions(menu, selected)

    # pragma pylint: disable=no-self-use
    def _add(self, menu, action, set_default=False):
        """
        Add action to menu.

        Parameters:
            menu (QMenu): Popup menu.
            action (QAction): Action (pass *None* to add separator).
            set_default (bool): Pass *True* to make action a default one.
        """
        if action and action.isEnabled():
            menu.addAction(action)
            if set_default:
                menu.setDefaultAction(action)
        elif action is None:
            menu.addSeparator()
