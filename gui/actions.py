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
Actions
-------

The module implements enhanced action classes (i.e. sub-classes of
`QAction`, `QWidgetAction`, etc.) for AsterStudy application.

"""

from __future__ import unicode_literals

from PyQt5.Qt import (Qt, QAction, QEvent, QFrame, QItemSelection,
                      QItemSelectionModel, QLabel, QListWidget, QMenu,
                      QMenuBar, QSignalMapper, QVBoxLayout, QWidgetAction,
                      pyqtSignal, pyqtSlot)

from common import bold, preformat, translate, update_visibility
from .widgets import ShrinkingComboBox, HLine


__all__ = ["ListAction", "UndoAction"]


# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class Action(QAction):
    """
    Generic action class that automatically updates visibility of
    toolbars and menus where it is inserted.
    """

    def __init__(self, text, parent):
        """
        Create action.

        Arguments:
            text (str): Action's text.
            parent (QObject): Parent object.
        """
        QAction.__init__(self, text, parent)
        self.changed.connect(self._changed)

    @pyqtSlot()
    def _changed(self):
        """
        Called when action is changed.

        Updates related widgets.
        """
        for widget in self.associatedWidgets():
            update_visibility(widget)


class ListAction(QWidgetAction):
    """Action that shows list of child items."""

    triggered = pyqtSignal(str)
    """
    Signal: emitted when child action is triggered.

    Arguments:
        text (str): Child item's text.
    """

    highlighted = pyqtSignal(str)
    """
    Signal: emitted when child action is highlighted.

    Arguments:
        text (str): Child item's text.
    """

    def __init__(self, text, icon=None, parent=None):
        """
        Create list action with given menu `text` and, optionaly,
        `icon`.

        Arguments:
            text (str): Action's menu text.
            icon (Optional[QIcon]): Action's icon. Defaults to None.
            parent (Optional[QObject]): Parent object. Defaults to None.
        """
        QWidgetAction.__init__(self, parent)
        self.setText(text)
        if icon is not None:
            self.setIcon(icon)
        self.setMenu(QMenu())
        self._mapper = QSignalMapper(self)
        self._mapper.mapped[str].connect(self.triggered[str])
        self.changed.connect(self._changed)

    def addItem(self, text, ident=None):
        """
        Add item into the action.

        Arguments:
            text (str): Item's text.
            ident (Optional[str]): Item's identifier.

        Returns:
            QAction: Action that corresponds to just added item.
        """
        action = self.menu().addAction(text)
        action.setData(ident)
        self._mapper.setMapping(action, ident if ident is not None else text)
        action.triggered.connect(self._mapper.map)
        self._changed()
        return action

    def clear(self):
        """
        Clear list action.
        """
        self.menu().clear()
        self._changed()

    def count(self):
        """
        Get number of items in the action.

        Returns:
            int: Number of items.
        """
        return len(self.menu().actions())

    def createWidget(self, parent_widget):
        """
        Create widget for action.

        Arguments:
            parent_widget (QWidget): Parent widget.

        Returns:
            QWidget: Created widget.
        """
        if isinstance(parent_widget, (QMenu, QMenuBar)):
            # For menu: show sub-menu.
            widget = QWidgetAction.createWidget(self, parent_widget)
        else:
            # For toolbar: show drop-down combo box.
            widget = ShrinkingComboBox(parent_widget)
            widget.setFocusPolicy(Qt.NoFocus)
            self._updateWidget(widget)
            widget.activated.connect(self._itemActivated)
            widget.highlighted.connect(self._itemHighlighted)
            widget.setEnabled(self.isEnabled())
            widget.setToolTip(self.toolTip())
            widget.setStatusTip(self.statusTip())
        return widget

    def _updateWidget(self, widget):
        """
        Fill the widget with the list of child items.

        Arguments:
            widget (QComboBox): Associated combo box.
        """
        widget.clear()
        widget.addItem(self.icon(), self.text())
        actions = self.menu().actions()
        for action in actions:
            idx = widget.count()
            widget.addItem(action.text(), action.data())
            widget.setItemData(idx, action.toolTip(), Qt.ToolTipRole)
            widget.setItemData(idx, action.statusTip(), Qt.StatusTipRole)

    @pyqtSlot(int)
    def _itemActivated(self, idx):
        """
        Called when combo box's item is activated.

        Emits `triggered(str)` signal.

        Arguments:
            idx (int): Item's index.
        """
        control = self.sender()
        control.blockSignals(True)
        control.setCurrentIndex(0)
        control.blockSignals(False)
        if idx > 0:
            data = control.itemData(idx)
            text = control.itemText(idx)
            self.triggered.emit(data if data is not None else text)

    @pyqtSlot(int)
    def _itemHighlighted(self, idx):
        """
        Called when combo box's item is highlighted.

        Emits `highlighted(str)` signal.

        Arguments:
            idx (int): Item's index.
        """
        control = self.sender()
        if idx > 0:
            data = control.itemData(idx)
            text = control.itemText(idx)
            self.highlighted.emit(data if data is not None else text)

    @pyqtSlot()
    def _changed(self):
        """
        Called when action is changed.

        Updates related widgets.
        """
        for widget in self.createdWidgets():
            widget.setEnabled(self.isEnabled())
            widget.setItemIcon(0, self.icon())
            widget.setItemText(0, self.text())
            widget.setToolTip(self.toolTip())
            widget.setStatusTip(self.statusTip())
            self._updateWidget(widget)
        for widget in self.associatedWidgets():
            update_visibility(widget)


class UndoMenu(QMenu):
    """
    Popup menu for UndoAction.
    [internal usage]
    """

    triggered = pyqtSignal(int)
    """
    Signal: emitted when 1 or more items is selected in menu.

    Arguments:
        selected (int): Number of selected items.
    """

    def __init__(self, parent=None):
        """
        Create menu object.

        `UndoMenu` class shows list of child items in the plain list,
        suitable for undo / redo operations.

        Items are inserted to menu with `setItems()` method.

        Methods `setMaxWidth()` and `setLength()` allow to limit the
        width (in pixels) and height (as a number of shown items) of
        menu.

        To customize summary label (shown in the bottom area of menu),
        use `setComment()` method.

        Top-most item can be obtained with `lastItem()` method.

        Arguments:
            parent (Optional[QWidget]): Parent widget. Defaults to None.
        """
        QMenu.__init__(self, parent)
        v_layout = QVBoxLayout(self)
        v_layout.setContentsMargins(0, 0, 0, 0)

        frame = QFrame(self)
        frame.setFrameStyle(QFrame.Panel | QFrame.Plain)
        v_layout.addWidget(frame)

        v_layout = QVBoxLayout(frame)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(1)

        self._list = QListWidget(frame)
        self._list.setFrameStyle(QListWidget.NoFrame)
        self._list.setSelectionMode(QListWidget.MultiSelection)
        self._list.setVerticalScrollMode(QListWidget.ScrollPerItem)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list.setResizeMode(QListWidget.Adjust)
        self._list.setFocusPolicy(Qt.NoFocus)
        self._list.viewport().installEventFilter(self)
        self._list.installEventFilter(self)
        self._list.viewport().setMouseTracking(True)

        self._label = QLabel(frame)
        self._label.setAlignment(Qt.AlignCenter)

        v_layout.addWidget(self._list)
        v_layout.addWidget(HLine(frame))
        v_layout.addWidget(self._label)

        self._comment = "%d"
        self._length = 10
        self._max_width = 0

        self._updateComment()

    def setItems(self, items):
        """
        Assign items to the list.

        Arguments:
            items (list[str]): Items to be displayed in menu.
        """
        self.clear()
        for item in items:
            self._list.addItem(item)

    def lastItem(self):
        """
        Get topmost shown menu item.

        Returns:
            str: Topmost menu item's text.
        """
        return self._list.item(0).text() if self._list.count() > 0 else ""

    def clear(self):
        """Clear menu."""
        self._list.clear()

    def setMaxWidth(self, max_width):
        """
        Set maximum width of the menu.

        Default value is 0 that means "auto".

        Arguments:
            max_width (int): Width of the menu.
        """
        self._max_width = max_width

    def setLength(self, length):
        """
        Set maximum height of the menu.

        Default value is 10 items.

        Arguments:
            length (int): Number of items to which menu height should be
                resized.
        """
        self._length = length

    def setComment(self, comment):
        """
        Set format of comment label.

        In the format template "%d" is automatically replaced by number
        of currently selected items.

        By default, format label is "%d".

        Arguments:
            comment (str): Comment label.
        """
        self._comment = comment
        self._updateComment()
        font_metrics = self._label.fontMetrics()
        width_cancel = font_metrics.width(translate("UndoAction", "Cancel"))
        width_selected = font_metrics.width(comment + "0"*3)
        self._label.setMinimumWidth(max(width_cancel, width_selected))

    def sizeHint(self):
        """
        Get size hint for the menu.

        Returns:
            QSize: Widget's size hint.
        """
        hint = QMenu.sizeHint(self)
        if self._max_width > 0:
            hint.setWidth(self._max_width)
        if self._length > 0:
            height = self._length * (self._list.fontMetrics().height() + 2)
            height = height + self._label.sizeHint().height()
            hint.setHeight(height)
        return hint

    def minimumSizeHint(self):
        """
        Get minimal size hint for the combo box.

        Returns:
            QSize: Widget's minimum size hint.
        """
        return self.sizeHint()

    def setVisible(self, visible):
        """
        Called when list widget is shown/hidden.

        Arguments:
            visible (bool): True if widget is being shown,
                False otherwise.
        """
        if visible:
            self._list.setFocus()
            self._list.scrollToItem(self._list.item(0),
                                    QListWidget.PositionAtTop)
            self._setSelected(0)
        QMenu.setVisible(self, visible)

    def keyPressEvent(self, event):
        """
        Handle key press event.

        Arguments:
            event (QKeyEvent): Key press event.
        """
        if event.type() == QEvent.KeyRelease:
            return

        event.accept()

        nb_selected = self._selected()
        nb_lines = self._length if self._length > 0 else 10

        # pragma pylint: disable=too-many-branches
        if event.key() == Qt.Key_Up:
            self._setSelected(max(1, nb_selected - 1))
        elif event.key() == Qt.Key_Down:
            self._setSelected(max(1, nb_selected + 1))
        elif event.key() == Qt.Key_PageUp:
            self._setSelected(max(1, nb_selected - nb_lines))
        elif event.key() == Qt.Key_PageDown:
            self._setSelected(max(1, nb_selected + nb_lines))
        elif event.key() == Qt.Key_Home:
            self._setSelected(1)
        elif event.key() == Qt.Key_End:
            self._setSelected(self._list.count())
        elif event.key() == Qt.Key_Return:
            self._accept()
        elif event.key() == Qt.Key_Escape:
            self.hide()

    def eventFilter(self, obj, event):
        """
        Filter events if this object has been installed as an event
        filter for the watched object.

        Arguments:
            obj (QObject): Watched object.
            event (QEvent): Event being processed.

        Returns:
            bool: True if event should be filtered out (i.e. if further
            processing should be stopped); False otherwise.
        """
        res = True

        if obj == self._list:
            if event.type() == QEvent.Leave:
                self._setSelected(0)
            res = False
        else:
            if event.type() == QEvent.MouseMove:
                if not self._list.viewport().rect().contains(event.pos()):
                    self._setSelected(0)
                elif self._list.itemAt(event.pos()):
                    row = self._list.row(self._list.itemAt(event.pos())) + 1
                    self._setSelected(row)
            elif event.type() == QEvent.MouseButtonRelease:
                self._accept()
            elif event.type() in [QEvent.MouseButtonPress,
                                  QEvent.MouseButtonDblClick]:
                pass
            else:
                res = False
        if res:
            return True
        else:
            return QMenu.eventFilter(self, obj, event)

    def _accept(self):
        """
        Validate user's choice.

        Emits `triggered(int)` signal.
        """
        nb_selected = self._selected()
        self.hide()
        if nb_selected > 0:
            self.triggered.emit(nb_selected)

    def _setSelected(self, count):
        """
        Set selection.

        Arguments:
            count (int): Number of selected items.
        """
        index = min(count, self._list.count())
        selection = QItemSelection()
        selection_model = self._list.selectionModel()
        selection.select(selection_model.model().index(0, 0),
                         selection_model.model().index(index-1, 0))
        selection_model.select(selection, QItemSelectionModel.ClearAndSelect)
        self._list.scrollToItem(self._list.item(index - 1))
        self._list.clearFocus()
        self._updateComment()

    def _selected(self):
        """
        Get number of selected items.

        Returns:
            int: Number of selected items.
        """
        return len(self._list.selectedItems())

    def _updateComment(self):
        """Update comment label."""
        comment = translate("UndoAction", "Cancel")
        nb_selected = self._selected()
        if nb_selected > 0:
            comment = self._comment
            try:
                comment = comment % nb_selected
            except TypeError:
                pass
        self._label.setText(comment)


class UndoAction(QAction):
    """
    Action that shows drop-down list of operations for undo/redo.

    Note:
        This action is not suitable for menu; it can be only used with
        toolbars.
    """

    activated = pyqtSignal(int)
    """
    Signal: emitted when action is triggered.

    Arguments:
        count (int): Number of selected actions.
    """

    def __init__(self, parent=None):
        """
        Create action.

        Arguments:
            parent (Optional[QObject]): Parent object. Defaults to None.
        """
        QAction.__init__(self, parent)
        self.setMenu(UndoMenu())
        self._items = []
        self._message = ""
        self._comment = ""
        self._tooltip = ""
        self._statustip = ""
        self._shortcut_hint = ""
        self.triggered.connect(self._triggered)
        self.menu().triggered.connect(self._triggered)

    def setMessage(self, message):
        """
        Set action's tooltip message.

        In the message, "%s" is automatically substituted by the
        operation name.

        Arguments:
            message (str): Tooltip message.
        """
        if not self._tooltip:
            self._tooltip = self.toolTip()
            self._statustip = self.statusTip()
        self._message = message
        self._update()

    def setComment(self, comment):
        """
        Set action's status message.

        Comment message is shown in the bottom area of popup menu.

        In the message, "%d" is automatically substituted by the
        number of selected operations.

        Arguments:
            comment (str): Comment message.
        """
        self._comment = comment
        self.menu().setComment(comment)
        self._update()

    def setShortcutHint(self, hint):
        """
        Set shortcut hint.

        Note:
            Shortcut is not assigned to the action, in order to avoid
            ambiguity with other actions; the hint is only displayed
            in the tooltip.

        Arguments:
            hint (str): Shortcut hint.
        """
        self._shortcut_hint = hint

    def setItems(self, items):
        """
        Set items to be shown in the drop-down menu.

        Arguments:
            items (list[str]): Operations to show.
        """
        self._items = items
        self.menu().setItems(items)
        self._update()

    @pyqtSlot(bool)
    @pyqtSlot(int)
    def _triggered(self, count):
        """
        Called when action is activated, either directly or
        from submenu.

        Emits `activated(int)` signal.

        Arguments:
            count (int, bool): Number of selected items (when called
                from sub-menu); checked status (when called directly
                from action).
        """
        nb_selected = 0
        if isinstance(count, bool):
            nb_selected = 1
        else:
            nb_selected = count
        if nb_selected > 0:
            self.activated.emit(nb_selected)

    def _update(self):
        """Update action's state - tooltip and statustip."""
        if self.menu().lastItem() and self._message:
            tip = self._message % self.menu().lastItem()
            self.setStatusTip(tip)
            if self._shortcut_hint:
                tip = "{0} ({1})".format(tip, bold(self._shortcut_hint))
                tip = preformat(tip)
            self.setToolTip(tip)
        else:
            if self._tooltip:
                self.setToolTip(self._tooltip)
            if self._statustip:
                self.setStatusTip(self._statustip)
