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
Show All panel
--------------

This module implements `Show All` panel that allows the user adding the
command from the catalogue to the study.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

from common import (CFG, auto_dupl_on, bold, connect, href, image, italic,
                    load_pixmap, preformat, translate)
from datamodel import CATA
from . import (Context, NodeType, get_node_type, translate_category,
               translate_command)
from . behavior import behavior
from . widgets import CategoryView, FilterPanel
from . editionwidget import EditionWidget
from . controller import WidgetController

__all__ = ["ShowAllPanel"]

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class ShowAllPanel(EditionWidget, WidgetController):
    """`Show All` panel."""

    def __init__(self, astergui, parent=None):
        """
        Create `Show all` edition panel.

        Arguments:
            astergui (AsterGui): Parent AsterGui instance.
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
        """
        super(ShowAllPanel, self).__init__(parent=parent,
                                           name=translate("ShowAllPanel",
                                                          "Show all commands"),
                                           astergui=astergui)
        self.setWindowTitle(translate("ShowAllPanel", "Add command"))
        self.setPixmap(load_pixmap("as_pic_new_command.png"))
        v_layout = Q.QVBoxLayout(self)
        v_layout.setContentsMargins(0, 0, 0, 0)
        self.panel = Panel(self)
        description = Q.QGroupBox(self)
        description.setTitle(translate("ShowAllPanel", "Command description"))
        desc_layout = Q.QVBoxLayout(description)
        self.info = Q.QLabel(description)
        self.info.setWordWrap(True)
        self.info.setOpenExternalLinks(True)
        desc_layout.addWidget(self.info)
        for category in CATA.get_categories("showall"):
            # get commands from category
            items = CATA.get_category(category)
            if not items:
                continue
            # get translation for category's title
            view = CategoryView(translate_category(category),
                                parent=self.panel)
            view.category = category
            for item in items:
                # get translation for command
                title = translate_command(item)
                if title != item:
                    title = title + " ({})".format(item)
                view.addItem(title, item)
            self.panel.addWidget(view)
            connect(view.selected, self._selectionChanged)
            connect(view.doubleClicked, self._doubleClicked)
        v_layout.addWidget(self.panel)
        v_layout.addWidget(description)
        connect(self.astergui().selectionChanged, self.updateButtonStatus)
        self.panel.installEventFilter(self)
        self.setFocusProxy(self.panel)

    def defaultButton(self):
        """
        Get button to be used for default action.

        Default implementation returns *None*.
        """
        return Q.QDialogButtonBox.Ok

    def isButtonEnabled(self, button):
        """
        Redefined from *EditionWidget* class.
        """
        result = True
        if button in [Q.QDialogButtonBox.Ok, Q.QDialogButtonBox.Apply]:
            result = False
            if self.astergui().canAddCommand():
                result = self._selected() is not None
        return result

    def applyChanges(self):
        """
        Redefined from *EditionWidget* class.
        """
        command = self._selected()
        if command:
            cmdobj = None
            selected = self.astergui().selected(Context.DataSettings)
            stage = self.astergui().study().node(selected[0])
            if get_node_type(stage) not in (NodeType.Stage,):
                stage = stage.stage
            if stage is not None:
                try:
                    cmdobj = stage.add_command(command)
                except Exception: # pragma pylint: disable=broad-except
                    cmdobj = None
            if cmdobj is not None:
                with auto_dupl_on(self.astergui().study().activeCase):
                    self.astergui().study().commit(translate("AsterStudy",
                                                             "Add command"))
                    self.astergui().update(autoSelect=cmdobj,
                                           context=Context.DataSettings)
                    msg = translate("AsterStudy",
                                    "Command with type '{}' "
                                    "successfully added")
                    msg = msg.format(command)
                    self.astergui().showMessage(msg)
            else:
                self.astergui().study().revert()

    def postClose(self, button):
        """
        Redefined from *EditionWidget* class.

        Activates automatic edition of the just added command if *OK*
        button is clicked.
        """
        if button in (Q.QDialogButtonBox.Ok,):
            if behavior().auto_edit:
                self.astergui().edit()

    @Q.pyqtSlot()
    def expandAll(self):
        """Expand all categories."""
        for view in self.panel.widgets():
            view.expand()

    @Q.pyqtSlot()
    def collapseAll(self):
        """Collapse all categories."""
        for view in self.panel.widgets():
            view.collapse()

    def updateTranslations(self):
        """
        Update translations in GUI elements.
        """
        views = self.panel.widgets()
        for view in views:
            items = CATA.get_category(view.category)
            view.clear()
            for item in items:
                title = translate_command(item)
                if title != item:
                    title = title + " ({})".format(item)
                view.addItem(title, item)
        self.panel.applyFilter()

    def eventFilter(self, obj, event):
        """
        Filter events if this object has been installed as an event
        filter for the watched object.

        Shows dedicated context menu for categories panel.

        Arguments:
            obj (QObject): Watched object.
            event (QEvent): Event being processed.

        Returns:
            bool: *True* if event should be filtered out (i.e. if
            further processing should be stopped); *False* otherwise.
        """
        if obj == self.panel and event.type() == Q.QEvent.ContextMenu:
            menu = Q.QMenu()
            menu.addAction(translate("ShowAllPanel", "Expand all"),
                           self.expandAll)
            menu.addAction(translate("ShowAllPanel", "Collapse all"),
                           self.collapseAll)
            event.accept()
            menu.exec_(self.mapToGlobal(event.pos()))
        # pragma pylint: disable=no-member
        return False

    @Q.pyqtSlot(str)
    def _selectionChanged(self, command):
        """
        Called when a command is selected in any category.

        Arguments:
            command (str): Command name.
        """
        sender_view = self.sender()
        for view in self.panel.widgets():
            if view != sender_view:
                view.clearSelection()
        if command:
            translation = translate_command(command)
            description = CATA.get_command_docstring(command)
            url = self.astergui().doc_url(command)
            if translation != command:
                text = italic(translation) + " ({})".format(bold(command))
            else:
                text = bold(command)
            # add doc url
            if url:
                doc = href(image(CFG.rcfile("as_pic_help.png"),
                                 width=20, height=20), url)
                text += "&nbsp;" + doc
            text = preformat(text)
            if description:
                text = text + "<br/>" + description
            self.info.setText(text)
        else:
            self.info.setText("")
        self.updateButtonStatus()

    @Q.pyqtSlot(str)
    def _doubleClicked(self):
        """
        Called when a command is double-clicked in any category.

        Arguments:
            command (str): Command name.
        """
        if self.isButtonEnabled(Q.QDialogButtonBox.Ok):
            self.perform(Q.QDialogButtonBox.Ok)

    def _selected(self):
        """
        Get selected command (*None* if there is no selection).

        Returns:
            str: Selected command.
        """
        for view in self.panel.widgets():
            if view.selection():
                return view.selection()
        return None


class Panel(FilterPanel):
    """
    Custom filter panel to automatically select first item that
    satisfies search criterion.
    """

    @Q.pyqtSlot(str)
    def filter(self, text):
        """Redefined from *FilterPanel* class."""
        super(Panel, self).filter(text)
        for widget in self.widgets():
            if not isinstance(widget, CategoryView):
                continue
            if widget.visibleCount() > 0:
                widget.expand()
                widget.select(0)
                break
