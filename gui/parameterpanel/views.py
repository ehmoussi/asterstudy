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
Parameters Panel Views
----------------------

Implementation of the Parameters panel views for different cases.

"""

from __future__ import unicode_literals

import re
import numpy

from PyQt5.Qt import (Qt, QComboBox, QGridLayout, QLabel, QLineEdit, QPainter,
                      QTreeWidget, QTreeWidgetItem, QMessageBox, QFontMetrics,
                      QRegExp, QRect, QHeaderView, qDrawShadeRect, pyqtSignal,
                      QApplication, QEvent, QStyledItemDelegate, QTableWidget,
                      QAbstractItemView, QDoubleValidator, QTableWidgetItem,
                      QSizePolicy, pyqtSlot)

from common import (debug_mode, get_cmd_groups, translate, is_child,
                    common_filters, get_cmd_mesh, get_file_name, is_medfile,
                    is_reference, is_contains_word,
                    MeshGroupType, MeshElemType)

from datamodel import CATA
from datamodel.command.helper import avail_meshes

from gui.behavior import behavior
from gui.widgets import FilterWidget, MessageBox

from .basic import CataInfo, Options, parameterPanel
from .items import ParameterBlockItem, ParameterListItem
from .widgets import ParameterItemHilighter
from .path import ParameterPath


# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name

class ParameterView(FilterWidget, ParameterBlockItem):
    """Top-level parameters editor item."""

    ensureVisible = pyqtSignal(QRect)
    """
    Signal: emitted when item rect should be visible.

    Arguments:
        rect (QRect): Item's rect.
    """

    checkConstraints = pyqtSignal(ParameterPath)
    """
    Signal: emitted when constrants of current list should be checked.

    Arguments:
        bool: Enable state.
    """

    appendEnabled = pyqtSignal(bool)
    """
    Signal: emitted when append enabled/disabled for current list.

    Arguments:
        bool: Enable state.
    """

    editContextChanged = pyqtSignal(str)
    """
    Signal: emitted when edit context was changed.

    Arguments:
        str: Context type.
    """

    gotoParameter = pyqtSignal(ParameterPath, str)
    """
    Signal: emitted when parameter's sub-editor is activated.

    Arguments:
        uid (int): Parameter's UID.
    """

    class GridLayout(QGridLayout):
        """
        Extended grid layout.
        """
        def __init__(self, parent=None):
            """Constructor"""
            super(ParameterView.GridLayout, self).__init__(parent)
            self._rows = None
            self._cols = None

        def actualRowCount(self):
            """Gets the actual row count in grid"""
            if self._rows is None:
                last = -1
                for row in xrange(self.rowCount() - 1, -1, -1):
                    for col in xrange(self.columnCount()):
                        if self.itemAtPosition(row, col) is not None:
                            last = row
                            break
                    if last != -1:
                        break
                self._rows = last + 1
            return self._rows

        def actualColumnCount(self):
            """Gets the actual column count in grid"""
            if self._cols is None:
                last = -1
                for col in xrange(self.columnCount() - 1, -1, -1):
                    for row in xrange(self.rowCount()):
                        if self.itemAtPosition(row, col) is not None:
                            last = col
                            break
                    if last != -1:
                        break
                self._cols = last + 1
            return self._cols

        def invalidate(self):
            """Reimplemented for internal reason"""
            super(ParameterView.GridLayout, self).invalidate()
            self._rows = None
            self._cols = None


    def __init__(self, panel, **kwargs):
        """
        Create view.

        Arguments:
            **kwargs: Arbitrary keyword arguments.
        """
        self._frames = []
        self._cache = None
        self._panel = panel

        super(ParameterView, self).__init__(**kwargs)

        self._initDependancies()
        self.appendTo()

        self.checkConstraints.connect(self._checkConstraints)

        self.itemStateChanged(self)

    def grid(self):
        """
        Create and return top-level grid layout to arrange child items.

        Returns:
            QGridLayout: Layout for widgets.
        """
        if self.layout() is None:
            grid = self.GridLayout()
            grid.setSpacing(10)
            extlist = behavior().external_list
            if self.isItemList() and not extlist:
                grid.setColumnStretch(self.ColumnId.Label, 0)
                grid.setColumnStretch(self.ColumnId.Editor, 1)
            else:
                grid.setColumnStretch(self.ColumnId.Label, 1)
                grid.setColumnStretch(self.ColumnId.Editor, 0)
            self.setLayout(grid)
            self._updateGrid()
        return self.layout()

    def panel(self):
        """
        Gets the panel which view belongs to.

        Returns:
            (ParameterPanel): Parent panel object
        """
        return self._panel

    def reorder(self, items):
        """
        Reorder items.

        Arguments:
            items (list[ParameterItem]): Child items.

        Returns:
            list[ParameterItem]: Reordered child items.
        """
        r_dict = {}
        r_items = []
        for rule in self.itemRules(True):
            if rule.isGrouped():
                r_items.append(rule)
                r_dict[rule] = 0
                for i in rule.childItems():
                    r_dict[i] = 0

        m_items = []
        o_items = []
        for item in items:
            if item not in r_dict:
                if item.isKeywordMandatory():
                    m_items.append(item)
                else:
                    o_items.append(item)

        return r_items + m_items + o_items

    def filter(self, text):
        """
        Apply filter.

        Arguments:
            text (str): Regular expression.
        """
        self.filterItem(text)

    def setItemValue(self, values):
        """
        Set values of child items.

        Arguments:
            values: Dictionary with item values (see `childValues()`).
        """
        super(ParameterView, self).setItemValue(values)

        self.updateCondition()
        self.updateConditions()
        self.itemStateChanged(self)
        self._cache = self.itemValue()

    def hasModifications(self):
        """
        Returns 'True' if view has modifications.
        """
        return self._cache != self.itemValue()

    def validate(self):
        """
        Perform value validation.

        Returns:
           bool: Validation status: True if value is valid; False
           otherwise.
        """
        state = True
        checker = CATA.package('Syntax').SyntaxCheckerVisitor()
        cond_context = self.conditionStorage(with_default=True)
        # conditionStorage returns values for simple keyword
        if isinstance(cond_context, dict):
            checker.set_parent_context(cond_context)

        exc_message = []
        try:
            self.keyword().accept(checker, self.itemValue())
        except Exception as exc: # pragma pylint: disable=broad-except
            from traceback import format_exc
            exc_message.append("Raw output message:\n{}\n".format(exc.args[0]))
            if debug_mode():
                exc_message.append("\n" + format_exc(exc))
            state = False

        if state:
            return True

        rule = None
        stack = checker.stack
        if len(stack) > 0 and not isinstance(stack[-1], basestring):
            rule = stack.pop()

        item = self
        while len(stack) > 0:
            items = item.findItemsByName(stack.pop(0))
            for i in items:
                if not i.testFlags(self.ItemFlags.Filtered) and \
                        not i.testFlags(self.ItemFlags.Excluded):
                    item = i
                    break

#        pos = self.contentsRect().center()
        msgInfo = []
        hiframe = None
        if item is not None and item != self:
            rect = item.itemRect()
            space = self.grid().spacing() / 2
            rect.adjust(-space, -space, space, space)
            self.ensureVisible.emit(rect)
#            pos = rect.center()

            hiframe = ParameterItemHilighter(rect, self)
            hiframe.show()
            kwtext = Options.translate_command(item.command().title,
                                               item.itemName())
            msgInfo.append(translate("ParameterPanel",
                                     "Invalid input in {0}.").format(kwtext))
        else:
            msgInfo.append(translate("ParameterPanel", "Invalid input."))

        if rule is not None:
            rulemsg = translate("ParameterPanel", "Not respected the rule: {0}"
                                                  " with keywords: {1}.")
            msgInfo.append(rulemsg.format(type(rule).__name__,
                                          ", ".join(rule.ruleArgs)))

        msgInfo.append(translate("ParameterPanel",
                                 "Do you want to save the changes any way?"))

#        balloon = ParameterBaloon(self)
#        balloon.setTitle(translate("ParameterPanel", "Error"))
#        balloon.setMessage("<br>".join(msg))
#        balloon.setPositon(self.mapToGlobal(pos))
#        balloon.show()

        details = " ".join(exc_message)
        answer = MessageBox.question(self,
                                     translate("ParameterPanel", "Error"),
                                     "\n".join(msgInfo),
                                     QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.Yes, detailedText=details)

        if hiframe is not None:
            hiframe.hide()

        return answer == QMessageBox.Yes

    def setUnusedVisibile(self, state):
        """
        Sets the visibility of unsed items in the view.

        Arguments:
            state (bool): visibility state for unsed items.
        """
        items = self.childItems(all=True)
        for item in items:
            item.modifyFlags(self.ItemFlags.HideUnused, not state)

    def createItem(self):
        """
        Create, append to list and show item.
        """
        nb_child = len(self.childItems())
        new_num = 0
        if nb_child > 0:
            last = self.childItems()[nb_child - 1]
            new_num = int(last.itemName()) + 1
        item = ParameterListItem(item_path=self.itemPath().
                                 absolutePath(str(new_num)),
                                 parent_item=self)
        item.appendTo()

        for i in self.childItems():
            i.updateItem()

        self.updateTranslations()
        self.itemStateChanged(self)

    def deleteItem(self, item):
        """
        Delete the specified item.

        Arguments:
            item (ParameterItem): Moved item
        """
        item.removeFrom()
        self.removeChildItem(item)
        item.cleanup()

        items = self.childItems()
        for idx in xrange(len(items)):
            curitem = items[idx]
            curitem.itemPath().rename(str(idx))
            curitem.updateTranslations()

        for i in items:
            i.updateItem()

        self.updateTranslations()
        self.itemStateChanged(self)

    def moveItem(self, item, step):
        """
        Move the specified item by the given step.

        Arguments:
            item (ParameterItem): Moved item
            step (int): Move offset
        """
        self.removeFrom()
        self.moveChildItem(item, step)
        items = self.childItems()
        for idx in xrange(len(items)):
            curitem = items[idx]
            curitem.itemPath().rename(str(idx))
            curitem.updateTranslations()
        self.appendTo()


    def appendFrame(self, frame):
        """
        Append the specified frame into view.

        Arguments:
            frame (QRect): Frame geometry
        """
        if not self._frames.__contains__(frame):
            self._frames.append(frame)
            self._updateGrid()
            self.update()

    def removeFrame(self, frame):
        """
        Remove the specified frame from view.

        Arguments:
            frame (QRect): Frame geometry
        """
        if self._frames.__contains__(frame):
            self._frames.remove(frame)
            self._updateGrid()
            self.update()

    def parameterActivated(self, path, link=''):
        """
        Called when item's sub-editor is activated.

        Arguments:
            obj (Parameter): Command's parameter.
        """
        self.gotoParameter.emit(path, link)

    def itemStateChanged(self, item):
        """
        Called when item state is changed.

        Arguments:
            item (ParameterItem): changed item.
        """
        self.checkConstraints.emit(item.itemPath())

    def setVisible(self, visible):
        """
        Reimplemented for setting focus on view during showing process
        """
        if visible:
            for item in self.childItems(all=True):
                item.updateItem(True)

        super(ParameterView, self).setVisible(visible)
        self.setFocus(Qt.OtherFocusReason)

    def eventFilter(self, obj, event):
        """
        Follow the mouse press events on it's child widget with disabled state.
        """
        if event.type() != QEvent.MouseButtonPress:
            return False

        if hasattr(obj, "isEnabled") and not obj.isEnabled():
            if is_child(obj, self):
                if obj != self:
                    item = self.itemAt(self.mapFromGlobal(event.globalPos()))
                    if item is not None:
                        item.itemClicked(event)
                        return True
        return False

    def showEvent(self, event):
        """
        Show event handler.
        Reimplemented for install global event filter.
        """
        super(ParameterView, self).showEvent(event)
        QApplication.instance().installEventFilter(self)

    def hideEvent(self, event):
        """
        Hide event handler.
        Reimplemented for remove global event filter.
        """
        super(ParameterView, self).hideEvent(event)
        QApplication.instance().removeEventFilter(self)

    def paintEvent(self, pevent):
        """
        Paint event handler.
        Reimplemented for drawing rule group frames.
        """
        super(ParameterView, self).paintEvent(pevent)

        grid = self.grid()
        offset = grid.contentsMargins().left() / 2
        for frame in self._frames:
            start_cell = grid.cellRect(frame.top(), frame.left())
            finish_cell = QRect()
            for col in xrange(frame.right(), frame.left() - 1, -1):
                for row in xrange(frame.bottom(), frame.top() - 1, -1):
                    finish_cell = grid.cellRect(row, col)
                    if finish_cell.isValid():
                        break
                if finish_cell.isValid():
                    break

            rect = QRect(start_cell.topLeft(), finish_cell.bottomRight())
            if rect.isValid():
                rect.adjust(-offset, -offset, offset, offset)
                self._paintGroupBox(rect, frame.title \
                                        if hasattr(frame, "title") else "")

    # pragma pylint: disable=unused-argument
    def _checkConstraints(self, path):
        """
        Called when `Add` or 'Delete' button is clicked in Edition panel
        during tuple parameter modification.
        """
        addstate = False
        if self.isItemList():
            defin = self.keyword().definition
            items = self.childItems()

            # check lower bound: min
            nb_min = defin.get('min', 0)
            for item in items:
                item.modifyFlags(self.ItemFlags.CantRemove,
                                 len(items) <= nb_min)

            # check upper bound: max
            nb_max = defin.get('max')
            addstate = nb_max is None or nb_max == "**" or len(items) < nb_max
        self.appendEnabled.emit(addstate)

    def _paintGroupBox(self, rect, title):
        painter = QPainter(self)
        qDrawShadeRect(painter, rect, self.palette(), True)

        if len(title) > 0:
            fnt = self.font()
            fnt.setPointSize(fnt.pointSize() - 1)
            offset = 5
            asterix = ' *'
            twidth = QFontMetrics(fnt).width(title)
            awidth = QFontMetrics(fnt).width(asterix)
            width = twidth + awidth + 2 * offset
            height = QFontMetrics(fnt).height()
            rect = QRect(rect.left() + 2 * offset,
                         rect.top() - height / 2 + 1, width, height)
            painter.fillRect(rect,
                             self.palette().color(self.backgroundRole()))
            painter.setFont(fnt)
            painter.drawText(QRect(rect.left() + offset, rect.top(),
                                   twidth, rect.height()), Qt.AlignLeft, title)
            painter.setPen(Qt.red)
            painter.drawText(QRect(rect.left() + offset + twidth, rect.top(),
                                   awidth, rect.height()), Qt.AlignRight,
                             asterix)

    def _updateGrid(self):
        """
        Updates the grid layout margins
        """
        self.grid().setContentsMargins(20 if self._frames else 5, 5,
                                       20 if self._frames else 5, 5)

    def _initDependancies(self):
        """
        Set the dependancies beetwin child items
        """
        table = CataInfo.keyword_dependancies()
        for key, value in table.items():
            item = self.findItemByPath(key)
            if item is not None:
                deps = value if isinstance(value, list) else [value]
                for dep in deps:
                    depitem = self.findItemByPath(dep)
                    if depitem is not None:
                        item.appendDependItem(depitem)

    def meshview(self):
        """
        Returns central view where mesh and groups should be displayed
        """
        return parameterPanel(self).meshview()


class ParameterTableView(ParameterView):
    """Top-level table editor item."""

    class Delegate(QStyledItemDelegate):
        """Table view delegate to validate input data."""

        def createEditor(self, parent, option, index):
            """
            Set double validator to default editor.
            """
            editor = QStyledItemDelegate.createEditor(self, parent, option,
                                                      index)
            validator = QDoubleValidator(editor)
            editor.setValidator(validator)
            return editor

    class FunctionTable(QTableWidget):
        """Reimplemented QTableWidget."""

        in_foc_as = False

        def moveCursor(self, cursor_action, modifiers):
            """
            Reimplemented in order to create a new row by <Tab> if last cell.

            Returns:
                index (QModelIndex): index to move cursor.
            """
            if not self.in_foc_as and \
                cursor_action == QAbstractItemView.MoveNext and \
                self.currentRow() == self.rowCount() - 1 and \
                self.currentColumn() == self.columnCount() - 1:
                self.insertRow(self.rowCount())
                for j in xrange(self.columnCount()):
                    newitem = QTableWidgetItem("")
                    self.setItem(self.rowCount() - 1, j, newitem)
                index = self.indexFromItem(self.item(self.rowCount() - 1, 0))
            else:
                index = QTableWidget.moveCursor(self, cursor_action, modifiers)
            return index

        def focusInEvent(self, *args, **kwargs):
            """
            Reimplemented in order to set flag if cursor was moved by focus.
            """
            self.in_foc_as = True
            QTableWidget.focusInEvent(self, *args, **kwargs)
            self.in_foc_as = False


    functionChanged = pyqtSignal()
    """Signal: emitted when table is changed."""

    selectionChanged = pyqtSignal()
    """Signal: emitted when table selection is changed."""

    def __init__(self, panel, **kwargs):
        """
        Create view.

        Arguments:
            **kwargs: Arbitrary keyword arguments.
        """
        super(ParameterTableView, self).__init__(panel, **kwargs)

        nb_rows = self.tableDefRowCount()
        nb_cols = self.tableDefColumnCount()

        self.table = self.FunctionTable(nb_rows, nb_cols)
        for i in xrange(nb_rows):
            for j in xrange(nb_cols):
                newitem = QTableWidgetItem("")
                self.table.setItem(i, j, newitem)
        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(True)
        self.table.setItemDelegate(self.Delegate())
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.table.itemChanged.connect(self.valueChanged)
        self.table.itemSelectionChanged.connect(self.selectionChanged)

        tbl = self.grid()
        tbl.setContentsMargins(0, 0, 0, 0)
        tbl.addWidget(self.table, 0, 0, tbl.rowCount(), tbl.columnCount())

    def validate(self):
        """
        Perform table validation.

        Returns:
           bool: Validation status: True if all cells were filled in; False
           otherwise.
        """
        state = True
        empty_cells = self.table.findItems("", Qt.MatchFixedString)
        if len(empty_cells) > 0:
            self.table.setCurrentItem(empty_cells[0])
            self.table.setFocus()
            state = False
        return state

    def selectedRows(self):
        """
        Gets the selected rows.
        """
        return list(set([i.row() for i in self.table.selectedItems()]))

    def selectedColumns(self):
        """
        Gets the selected rows.
        """
        return list(set([i.column() for i in self.table.selectedItems()]))

    def headerLabels(self):
        """
        Gets horizontal header names from 'NOM_PARA' and 'NOM_RESU' parameters.
        """
        param_name = translate("ParameterPanel", "Parameter")
        func_name = translate("ParameterPanel", "Function")

        item = self.rootItem()
        master = item.masterItem()
        if master is not None:
            parent_item = master.parentItem()
            if parent_item is not None:
                for item in parent_item.childItems():
                    if not item.isUsed():
                        continue
                    if item.itemName() == 'NOM_PARA':
                        param_name = \
                            Options.translate_command(self.command().title,
                                                      self.itemName(),
                                                      item.itemValue())
                    elif item.itemName() == 'NOM_RESU':
                        func_name = item.itemValue()
        labels = list()
        labels.append(param_name)
        path = self.itemPath().path()
        if re.match("^.*[.]VALE$", path):
            labels.append(func_name)
        elif re.match("^.*[.]VALE_C$", path):
            labels.append(translate("ParameterPanel", "Real"))
            labels.append(translate("ParameterPanel", "Imaginary"))
        return labels

    def updateTranslations(self):
        """
        Update translations.
        """
        self._updateHeaders()
        self.functionChanged.emit()

    def setData(self, data):
        """
        Insert values from array to the table widget.

        Arguments:
            array: numpy.ndarray with table values
        """
        if data.size == 0:
            return

        to_import = True
        file_cols = data.ndim
        nb_cols = self.tableDefColumnCount()
        if file_cols != nb_cols:
            msg = translate("ParameterPanel",
                            "Number of columns in the file does not correspond"
                            " to the table dimension."
                            "\nDo you want to read this file anyway?")
            to_import = QMessageBox.question(self.table, "AsterStudy", msg) \
                            == QMessageBox.Yes

        if to_import:
            self.table.blockSignals(True)
            self.table.setRowCount(len(data))
            for i in xrange(len(data)):
                for j in xrange(nb_cols):
                    text = str("")
                    if file_cols > 1:
                        if j < file_cols:
                            text = str(data[i, j])
                    else:
                        text = str(data[i])
                    newitem = QTableWidgetItem(text)
                    self.table.setItem(i, j, newitem)
            self.table.blockSignals(False)
            self.valueChanged()
        else:
            self.importFile()

    def itemValue(self, **kwargs):
        """
        Get table values.

        Returns:
            list: List with all table values
        """
        childvalue = self.storage
        glob = kwargs['glob'] if 'glob' in kwargs else False
        if glob and self.slaveItem() is not None:
            childvalue = self.slaveItem().itemValue(**kwargs)
        else:
            values = list()
            for i in xrange(self.table.rowCount()):
                for j in xrange(self.table.columnCount()):
                    item = self.table.item(i, j)
                    val = None
                    if item is not None and len(item.text()) > 0:
                        val = float(item.text())
                    values.append(val)
            if values:
                childvalue = tuple(values)
                self.storage = childvalue
        return childvalue

    def setItemValue(self, values):
        """
        Set values of child items.

        Arguments:
            values: Dictionary with item values (see `childValues()`).
        """
        self._updateHeaders()
        nb_cols = self.tableDefColumnCount()
        if values is not None:
            self.table.blockSignals(True)
            nb_rows = len(values) / nb_cols
            self.table.setRowCount(nb_rows)
            self.table.setColumnCount(nb_cols)
            ind = 0
            for i in xrange(nb_rows):
                for j in xrange(nb_cols):
                    val = values[ind]
                    newitem = QTableWidgetItem(str(val) \
                                                   if val is not None else "")
                    self.table.setItem(i, j, newitem)
                    ind += 1
            self.table.blockSignals(False)
            self.valueChanged()
        self.storage = values
        self._cache = self.itemValue()

    def valueChanged(self):
        """
        Called when item's value is changed.
        """
        super(ParameterTableView, self).valueChanged()
        self.functionChanged.emit()

    def tableDefColumnCount(self):
        """
        Returns columns number according to parameter type.

        Result:
            (int): number of columns.
        """
        nb_cols = 0
        path = self.itemPath().path()
        if re.match("^.*[.]VALE$", path):
            nb_cols = 2
        elif re.match("^.*[.]VALE_C$", path):
            nb_cols = 3
        elif re.match("^.*[.](VALE_PARA|VALE_FONC)$", path):
            nb_cols = 1
        elif re.match("^.*[.](NOEUD_PARA|VALE_Y)$", path):
            nb_cols = 1
        elif re.match("^.*[.](ABSCISSE|ORDONNEE)$", path):
            nb_cols = 1
        return nb_cols

    def tableDefRowCount(self):
        """
        Returns rows number according to parameter type and 'min' constraint.

        Result:
            (nb_rows, nb_cols)(tuple): number of rows and columns.
        """
        nb_rows = 1
        param_def = self.keyword()
        if param_def and 'min' in param_def.definition:
            nb_min = param_def.definition['min']
            nb_cols = self.tableDefColumnCount()
            if nb_min > nb_cols:
                nb_rows = nb_min / nb_cols
        return nb_rows

    @pyqtSlot()
    def importFile(self):
        """
        Called when 'Import from file' button is clicked.

        Allows to select file and fills in a table if any file was given.
        """
        data = None
        title = translate("ParameterPanel", "Import table")
        filters = common_filters()
        filename = get_file_name(mode=1, parent=self.table, title=title,
                                 url="", filters=filters,
                                 dflt_filter=filters[2]) # "Text files"
        if filename:
            try:
                data = numpy.loadtxt(filename, delimiter=',')
            except BaseException as exc:
                QMessageBox.critical(self.table, "AsterStudy", exc.message)
            else:
                self.setData(data)

    @pyqtSlot()
    def appendRow(self):
        """
        Adds empty row to the end of table.
        """
        self._insertRow(self.table.rowCount())

    @pyqtSlot()
    def insertRow(self):
        """
        Inserts empty row before selected one.
        """
        selected = [i.row() for i in self.table.selectedIndexes()]
        self._insertRow(min(selected) if selected else self.table.rowCount())

    @pyqtSlot()
    def removeRows(self):
        """
        Remove selected rows.
        """
        # get selected rows
        selected = [i.row() for i in self.table.selectedIndexes()]
        selected = sorted(set(selected), reverse=True)
        if not selected:
            return
        # remove selected rows
        for row in selected:
            self.table.removeRow(row)
        # set selection
        if self.table.rowCount() > 0:
            row_to_select = min([selected[0], self.table.rowCount() - 1])
            self.table.setCurrentCell(row_to_select, 0)
        self.table.setFocus()
        self.valueChanged()

    @pyqtSlot()
    def moveRowsUp(self):
        """
        Move selected rows up by one position.
        """
        self.moveRows(-1)

    @pyqtSlot()
    def moveRowsDown(self):
        """
        Move selected rows down by one position.
        """
        self.moveRows(1)

    def moveRows(self, offset):
        """
        Move selected rows by specified offset.
        """
        selrows = self.selectedRows()
        if not len(selrows) or not offset:
            return

        selitems = self.table.selectedItems()

        if offset > 0:
            selrows.reverse()

        moved = []

        chaged = False
        nb_rows = self.table.rowCount()
        nb_cols = self.table.columnCount()
        for row in selrows:
            pos = max(0, min(row + offset, nb_rows - 1))
            if pos != row and pos not in moved:
                trg = pos if offset < 0 else pos + 1
                src = row if offset > 0 else row + 1
                self.table.insertRow(trg)
                for col in xrange(nb_cols):
                    self.table.setItem(trg, col, self.table.takeItem(src, col))
                self.table.removeRow(src)
                chaged = True
            else:
                pos = row
            moved.append(pos)

        self.table.clearSelection()
        for item in selitems:
            item.setSelected(True)

        if chaged:
            self.valueChanged()

    def _insertRow(self, row):
        """Insert row at given position."""
        nb_cols = self.tableDefColumnCount()
        self.table.insertRow(row)
        for col in xrange(nb_cols):
            newitem = QTableWidgetItem("")
            self.table.setItem(row, col, newitem)
        item = self.table.item(row, 0)
        self.table.scrollTo(self.table.indexFromItem(item))
        self.table.setCurrentCell(row, 0)
        self.table.setFocus()

    def _updateHeaders(self):
        """
        Update table headers.
        """
        self.table.setHorizontalHeaderLabels(self.headerLabels())


class ParameterMeshGroupView(ParameterView):
    """Top-level table editor item."""

    meshFileChanged = pyqtSignal(str, str, float, bool)
    meshGroupCheck = pyqtSignal(str, str, str)
    meshGroupUnCheck = pyqtSignal(str, str, str)
    meshChanged = pyqtSignal()
    """Signal: emitted when mesh is changed in the combo box."""

    def __init__(self, panel, **kwargs):
        """
        Create view.

        Arguments:
            **kwargs: Arbitrary keyword arguments.
        """
        super(ParameterMeshGroupView, self).__init__(panel, **kwargs)

        self.setStretchable(True)

        self._mesh = QComboBox(self)
        self._mesh.setObjectName("MESH")
        self._msg = QLabel(self)
        self._list = QTreeWidget(self)
        self._list.setAllColumnsShowFocus(True)
        self._list.setSelectionMode(QTreeWidget.SingleSelection)
        self._list.setColumnCount(2)
        titles = []
        titles.append(translate("AsterStudy", "Name"))
        titles.append(translate("AsterStudy", "Size"))
        self._list.setHeaderLabels(titles)
        self._list.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._list.header().setStretchLastSection(True)

        manlabel = QLabel(translate("ParameterPanel", "Manual selection"),
                          self)
        manlabel.setToolTip(translate("ParameterPanel",
                                      "Enter manually the wanted groups if "
                                      "not present in the list"))
        self._manual = QLineEdit(self)
        self._manual.setObjectName("MANUAL_INPUT")

        base = self.grid()
        base.addWidget(self._mesh, 0, 0, 1, -1)
        base.addWidget(self._msg, 1, 0, 1, -1)
        base.addWidget(self._list, 2, 0, 1, -1)
        base.addWidget(manlabel, 3, 0, 1, -1)
        base.addWidget(self._manual, 4, 0, 1, -1)

        self._mesh.activated[int].connect(self._meshActivated)
        self._updateMeshList()

        self.meshFileChanged.connect(self.meshview().displayMEDFileName)
        self.meshGroupCheck.connect(self.meshview().displayMeshGroup)
        self.meshGroupUnCheck.connect(self.meshview().undisplayMeshGroup)
        self._list.itemChanged.connect(self.meshGroupToChange)

    def meshList(self):
        """
        Gets the mesh commands list

        Returns:
            list (Command): List of commands with meshes.
        """
        mlist = []
        for i in xrange(self._mesh.count()):
            mlist.append(self._mesh.itemData(i).name)
        return mlist

    def setMeshList(self, meshlist):
        """
        Sets the mesh commands list

        Arguments:
            meshlist: List of commands with meshes.
        """
        self._mesh.clear()
        show_title = behavior().show_catalogue_name_in_selectors
        title_mask = '{n} ({t})' if show_title else '{n}'
        for meshcmd in meshlist:
            title = title_mask.format(n=meshcmd.name, t=meshcmd.title)
            self._mesh.addItem(title, meshcmd)

    def mesh(self):
        """
        Gets the currently selected mesh command object or None in error case.

        Returns:
            Command: Current mesh command object.
        """
        idx = self._mesh.currentIndex()
        return self._mesh.itemData(idx) if idx >= 0 else None

    def setMesh(self, mesh):
        """
        Sets the current mesh command object if it exists in the list.

        Arguments:
            mesh: Current mesh command object.
        """
        self._mesh.setCurrentIndex(self._mesh.findData(mesh))

    def message(self):
        """
        Gets the info message text.

        Returns:
            str: info message text.
        """
        return self._msg.text()

    def setMessage(self, msg):
        """
        Sets the info message text.

        Arguments:
            msg (str): info message text.
        """
        self._msg.setText(msg)
        self._msg.setVisible(len(msg) > 0)

    def setMeshGroups(self, groups):
        """
        Sets the mesh group list

        Arguments:
            groups (dict[int, list[tuple[str, int]]]): Mesh groups info.
        """
        self._list.clear()
        grp_types = sorted(groups.keys())
        for typ in grp_types:
            names = groups[typ]
            if not names:
                continue
            title = MeshElemType.value2str(typ)
            item = QTreeWidgetItem(self._list, [title])
            for name, size in names:
                sub_item = QTreeWidgetItem(item, [name, str(size)])
                sub_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                sub_item.setCheckState(0, Qt.Unchecked)
                sub_item.setTextAlignment(1, Qt.AlignRight)
        self._list.expandAll()

    def inputMeshGroups(self):
        """
        Gets the mesh group names list entered manually

        Returns:
            list (str): List of group names.
        """
        text = self._manual.text().strip()
        return [i.strip() for i in text.split(",")] if len(text) > 0 else []

    def setInputMeshGroups(self, groups):
        """
        Sets the mesh group list entered manually

        Arguments:
            groups: List of mesh group names.
        """
        self._manual.setText(",".join(groups))

    def selectedMeshGroups(self):
        """
        Gets the names of selected (checked) mesh groups.

        Returns:
            list (str): List of selected group names.
        """
        groups = []
        for i in range(self._list.topLevelItemCount()):
            item = self._list.topLevelItem(i)
            for j in xrange(item.childCount()):
                sub_item = item.child(j)
                if sub_item.checkState(0) == Qt.Checked:
                    groups.append(sub_item.text(0))
        return list(set(groups))

    def setSelectedMeshGroups(self, groups):
        """
        Sets the specified group names are selected (checked)
        and unchecked all other.

        Arguments:
            groups: List of selected mesh group names.
        """
        for i in range(self._list.topLevelItemCount()):
            item = self._list.topLevelItem(i)
            for j in xrange(item.childCount()):
                sub_item = item.child(j)
                state = Qt.Checked if sub_item.text(0) in groups \
                    else Qt.Unchecked
                sub_item.setCheckState(0, state)

    @pyqtSlot(QTreeWidgetItem, int)
    def meshGroupToChange(self, item, column):
        """
        Emits display signal whenever the user clicks a check box
        """
        meshcmd = self._meshcmd(self._mesh.currentIndex())
        if meshcmd is not None:
            file_name, nom_med = get_cmd_mesh(meshcmd)
            if file_name is not None and nom_med is not None:
                if item.checkState(column) == Qt.Checked:
                    self.meshGroupCheck.emit(file_name, nom_med,
                                             item.text(0))
                else:
                    self.meshGroupUnCheck.emit(file_name, nom_med,
                                               item.text(0))

    def _meshcmd(self, index):
        """
        Returns the *Command* instance associated with the panel
        """
        meshcmd = None
        if 0 <= index < self._mesh.count():
            meshcmd = self._mesh.itemData(index)
        return meshcmd

    def itemValue(self, **kwargs):
        """
        Get selected values.

        Returns:
            tuple: List with all selected mesh groups
        """
        res = tuple(self.selectedMeshGroups() + self.inputMeshGroups())
        return res if len(res) > 0 else None

    def setItemValue(self, values):
        """
        Set values of child items.

        Arguments:
            values: Tuple with item values (see `childValues()`).
        """
        grplist = []
        if values is not None:
            if isinstance(values, (tuple, list)):
                grplist = list(values)
            else:
                grplist = [values]
        self.setSelectedMeshGroups(grplist)
        check = dict.fromkeys(self.selectedMeshGroups())
        grplist = [grp for grp in grplist if grp not in check]
        self.setInputMeshGroups(grplist)
        self._cache = self.itemValue()

    def filterItem(self, text):
        """
        Filter out the item.

        Arguments:
            text (str): Regular expression.
        """
        regex = QRegExp(text, Qt.CaseInsensitive)
        for i in range(self._list.topLevelItemCount()):
            item = self._list.topLevelItem(i)
            cnt_visible = 0
            for j in xrange(item.childCount()):
                sub_item = item.child(j)
                item_text = sub_item.text(0)
                hidden = text != "" and regex.indexIn(item_text) == -1
                sub_item.setHidden(hidden)
                if not hidden:
                    cnt_visible += 1
            item.setHidden(cnt_visible == 0)

    def _updateMeshList(self):
        """
        Updates the mesh list in the combobox
        """
        meshlist = avail_meshes(parameterPanel(self).pendingStorage())
        meshlist.reverse()
        self.setMeshList(meshlist)
        msg = ""
        if len(meshlist) > 1:
            msg = translate("ParameterPanel", "More than one mesh found")
        elif len(meshlist) == 0:
            msg = translate("ParameterPanel", "No mesh found")
        self.setMessage(msg)
        self._meshActivated(self._mesh.currentIndex())

    def _meshActivated(self, index):
        """
        Updates the mesh groups in checkable list.
        Invoked after mesh changing in mesh combobox.
        """
        meshcmd = None
        if 0 <= index < self._mesh.count():
            meshcmd = self._mesh.itemData(index)

        groups = {}
        if meshcmd is not None:
            group_type = self._meshGroupType()
            file_name, nom_med = get_cmd_mesh(meshcmd)
            if is_medfile(file_name) or is_reference(file_name):
                self.meshFileChanged.emit(file_name, nom_med, 0.1, False)
            try:
                groups = get_cmd_groups(meshcmd, group_type, with_size=True)
            except TypeError:
                pass
        self.setMeshGroups(groups)
        self.meshChanged.emit()

    def _meshGroupType(self):
        """
        Get the type of the mesh group

        Returns:
            str: Mesh group type (see `MeshGroupType`).
        """
        mgtype = -1
        name = self.itemName()
        if name.endswith("_MA") or is_contains_word(name, "MA"):
            mgtype = MeshGroupType.GElement
        elif name.endswith("_NO") or is_contains_word(name, "NO"):
            mgtype = MeshGroupType.GNode
        return mgtype
