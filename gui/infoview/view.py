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
Information view
----------------

The module implements *Information* view for AsterStudy GUI.
See `InfoView` class for more details.

"""

from __future__ import unicode_literals

from StringIO import StringIO

from PyQt5 import Qt as Q

from common import bold, change_cursor, italic, translate
from datamodel.study2comm import ExportToCommVisitor
from gui import NodeType, get_node_type

__all__ = ["InfoView"]

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class InfoView(Q.QWidget):
    """
    Information view.
    """

    def __init__(self, astergui, parent=None):
        """
        Create view.

        Arguments:
            astergui (AsterGui): *AsterGui* instance.
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
        """
        super(InfoView, self).__init__(parent)
        self.astergui = astergui
        self._objs = []

        self.setLayout(Q.QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)

        label = Q.QLabel(translate("InfoView", "Information"))
        self.layout().addWidget(label)

        self.view = Q.QTextEdit(self)
        self.layout().addWidget(self.view)

        self.view.setObjectName("information_view")
        self.view.setReadOnly(True)

    def setSelection(self, objs):
        """
        Update information when selection is changed.
        """
        self._objs = objs
        self.update()

    def update(self):
        """
        Update the current information.
        """
        selected = self._objs
        if len(selected) > 1:
            text = translate("InfoView", "{} items selected")
            self.setText(text.format(len(selected)))
        elif len(selected) > 0:
            node = self.astergui.study().node(selected[0]) \
                if self.astergui.study() is not None else None
            self.setText(info(node))
        else:
            self.clear()

    def setText(self, text):
        """
        Set text to view.

        Arguments:
            text (str): Text data.
        """
        self.view.setText(text)
        debug_widget = getattr(self.astergui, 'debug_widget', None)
        if debug_widget is not None:
            debug_widget.setText(text)

    def text(self):
        """
        Get text from view.

        Note:
            Contents of view is returned as plain text, all HTML tags
            are lost.

        Returns:
            str: Text data.
        """
        return self.view.toPlainText()

    def clear(self):
        """Clear contents of view."""
        self.view.clear()


# pragma pylint: disable=no-self-use

class Visitor(ExportToCommVisitor):
    """Custom visitor introducing pretty decoration of command.

    Output is limited to the first occurrences.
    """

    Indent = '&nbsp;&nbsp;'

    def __init__(self, *args):
        """Create visitor."""
        super(Visitor, self).__init__(*args, limit=20)
        self._level = 0
        self._something = []

    def decorate_name(self, text):
        """Redefined from *ExportToCommVisitor*."""
        return italic(text)

    def decorate_title(self, text):
        """Redefined from *ExportToCommVisitor*."""
        return bold(text)

    def decorate_keyword(self, text):
        """Redefined from *ExportToCommVisitor*."""
        self._something[-1] = True
        return '<br>' + Visitor.Indent * self._level + bold(text)

    def decorate_comment(self, text):
        """Redefined from *ExportToCommVisitor*."""
        return italic(text)

    def decorate_special(self, text):
        """Redefined from *ExportToCommVisitor*."""
        return bold(text)

    @staticmethod
    @change_cursor
    def dump(node):
        """Dump command to pretty string representation."""
        ostream = StringIO()
        visitor = Visitor(ostream)
        node.accept(visitor)
        visitor.end()
        value = ostream.getvalue().strip()
        value = visitor.clean(value)
        return value

    def _print_left_brace(self):
        """Redefined from *ExportToCommVisitor*."""
        super(Visitor, self)._print_left_brace()
        self._begin_block()

    def _print_right_brace(self):
        """Redefined from *ExportToCommVisitor*."""
        self._end_block()
        super(Visitor, self)._print_right_brace()

    def _begin_block(self):
        """Begin block."""
        self._level = self._level + 1
        self._something.append(False)

    def _end_block(self):
        """End block."""
        self._level = self._level - 1
        something = self._something.pop()
        if something:
            self._write('<br>' + Visitor.Indent * self._level)


def info(node):
    """
    Get pretty formatted preview information on the data model node.

    Arguments:
    node (Node): Data model object.

    Returns:
    str: Object's description.
    """
    node_type = get_node_type(node)
    return Visitor.dump(node) \
        if node_type in (NodeType.Command, NodeType.Variable) else ""
