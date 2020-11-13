# -*- coding: utf-8 -*-

# Copyright 2017 EDF R&D
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
Comment panel
-------------

This module implements `Edit Comment` panel that allows the user
editing textual properties of the data objects within AsterStudy
application, like:

- Comment for command or variable;
- Case's description,
- Etc.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

from common import auto_dupl_on, load_pixmap, translate

from . import NodeType, get_node_type
from . editionwidget import EditionWidget
from . controller import WidgetController

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class CommentPanel(EditionWidget, WidgetController):
    """Comment panel."""

    def __init__(self, astergui, parent=None, **kwargs):
        """
        Create comment edition panel.

        Arguments:
            astergui (AsterGui): Parent *AsterGui* instance.
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
            **kwargs: Keyword arguments.
        """
        super(CommentPanel, self).__init__(parent=parent,
                                           name=translate("AsterStudy",
                                                          "Edit comment"),
                                           astergui=astergui, **kwargs)
        self._prev_state = None
        self._node = None

        self.setWindowTitle(self.controllerName())
        self.setPixmap(load_pixmap("as_pic_edit_comment.png"))

        self.editor = Q.QPlainTextEdit(self)
        self.editor.setObjectName("text_editor")
        v_layout = Q.QVBoxLayout(self)
        v_layout.addWidget(self.editor)
        self.editor.textChanged.connect(self.updateButtonStatus)

    @property
    def node(self):
        """
        Get object being edited.

        Returns:
            Node: Object being edited (*Command*, *Comment* or *Case*
            object).
        """
        return self._node

    @node.setter
    def node(self, node):
        """
        Set object to be edited.

        Arguments:
            node (Node): Object to be edited (*Command*, *Comment* or
                *Case* object).
        """
        if self._node is node:
            return

        self._node = node

        if node is not None:
            cname = ''
            pixmap = Q.QPixmap()
            node_type = get_node_type(node)
            if node_type in (NodeType.Command, NodeType.Variable):
                self._prev_state = node.comment.content \
                    if node.comment is not None else ''
                cname = translate("AsterStudy", "Edit comment")
                pixmap = load_pixmap("as_pic_edit_comment.png")
            elif node_type in (NodeType.Comment,):
                self._prev_state = node.content
                cname = translate("AsterStudy", "Edit comment")
                pixmap = load_pixmap("as_pic_edit_comment.png")
            elif node_type in (NodeType.Case,):
                self._prev_state = node.description
                cname = translate("AsterStudy", "Edit description")
                pixmap = load_pixmap("as_pic_edit_comment.png")
            if self._prev_state is not None:
                self.editor.setPlainText(self._prev_state)
            self._controllername = cname
            self.setWindowTitle(self.controllerName())
            self.setPixmap(pixmap)

    def requiredButtons(self):
        """
        Redefined from *EditionWidget* class.
        """
        buttons = super(CommentPanel, self).requiredButtons()
        if self.controllerOwner() is not None:
            buttons = Q.QDialogButtonBox.Ok | Q.QDialogButtonBox.Cancel
        return buttons

    def isButtonEnabled(self, button):
        """
        Redefined from *EditionWidget* class.
        """
        result = True
        if button in [Q.QDialogButtonBox.Ok, Q.QDialogButtonBox.Apply]:
            result = self.node is not None and \
                self._prev_state is not None and \
                self.editor.toPlainText() != self._prev_state
        return result

    def applyChanges(self):
        """
        Redefined from *EditionWidget* class.
        """
        with auto_dupl_on(self.astergui().study().activeCase):
            self._prev_state = self.editor.toPlainText()
            if self.node is not None:
                node_type = get_node_type(self.node)
                if node_type in (NodeType.Command, NodeType.Variable):
                    if not self._prev_state:
                        self.node.comment.delete()
                    else:
                        self.node.comment = self._prev_state
                elif node_type in (NodeType.Comment,):
                    self.node.content = self._prev_state
                elif node_type in (NodeType.Case,):
                    self.node.description = self._prev_state
            if self.controllerOwner() is None:
                self.astergui().study().commit(self.controllerName())
                self.astergui().update()
