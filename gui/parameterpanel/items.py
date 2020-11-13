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
Parameters Items for Parameters Panel
-------------------------------------

Implementation of the Parameters panel items.

"""

from __future__ import unicode_literals

from PyQt5.Qt import (Qt, QRadioButton, QLabel, QRect, QToolButton, QObject,
                      QCheckBox, QMouseEvent, QEvent, QTimer, QApplication,
                      QSpacerItem, QFrame, pyqtSignal)

from common import is_child, load_icon, translate, bold, italic

from datamodel import IDS, KeysMixing, get_cata_typeid
from datamodel.command import Variable

from gui import translate_rule
from gui.behavior import behavior

from .basic import KeywordType
from .editors import parameter_editor_factory
from .widgets import ParameterLabel, SpinWidget
from .path import ParameterPath

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name

# pragma pylint: disable=too-many-public-methods,too-many-lines

class ParameterItem(object):
    """Base class for parameter edition."""

    class ItemFlags(object):
        """Enumerator for item flags."""
        Filtered = 1 # Filtered - item was hidden by filtering
        Excluded = 2 # Excluded - item was hidden by block conditions
        Disabled = 4 # Disabled - item was disabled by some rule
        Mandatory = 8 # Mandatory - item temporary become mandatory by rule
        HideUnused = 16 # Hide unused - item was hidden by 'Hide unused' btn
        CantRemove = 32 # Can't remove - item remove button is disabled

    class ColumnId(object):
        """Enumerator for column id."""

        Check = 0 # Check box column
        Label = 1 # Keyword label column
        Mandatory = 2 # Mandatory asterix column
        Editor = 3 # Keyword editor column
        Default = 4 # Default button column
        Move = 5 # Move up button column
        Remove = 6 # Remove button column

    def __init__(self, item_path, parent_item, **kwargs):
        """
        Create item.

        Arguments:
            obj (Parameter): Command's parameter.
            parent_item (ParameterItem): Parent item.
            **kwargs: Arbitrary keyword arguments.
        """
        super(ParameterItem, self).__init__(**kwargs)

        self._path = item_path

        self._flags = 0
        self._rules = []
        self._timer = None
        self.storage = None

        self._slave = None
        self._master = None

        self._depend_items = []

        self._parent_item = None
        self._child_items = []
        self.setParentItem(parent_item)

    def flags(self):
        """
        Returns the item state flags

        Returns:
            int: Flags combination
        """
        return self._flags

    def setFlags(self, flags):
        """
        Assign the specified flags to item state flags

        Arguments:
            flags (int): Combination of setted flags
        """
        if self._flags != flags:
            aflags = flags & ~self._flags
            dflags = self._flags & ~flags
            self._flags = flags
            if aflags != 0:
                self.flagsChanged(aflags)
            if dflags != 0:
                self.flagsChanged(dflags)

    def testFlags(self, flags):
        """
        Test the existance of specified flags in item state flags

        Arguments:
            int: Combination of tested flags

        Returns:
            bool: Flags combination existance state
        """
        return self._flags & flags != 0

    def modifyFlags(self, flags, state):
        """
        Set/reset the specified flags to item state flags

        Arguments:
            flags (int): Combination of setted flags
            on (bool): Required action: True - set, False - reset
        """
        if state:
            self.setFlags(self.flags() | flags)
        else:
            self.setFlags(self.flags() & ~flags)

    def flagsChanged(self, flags):
        """
        Invoked when item flags was changed
        """
        pass

    def masterItem(self):
        """
        Master parameter item e.g. bottom level item in another
        tree which is describe the same keyword like and this item

        Returns:
            ParameterItem: Master item.
        """
        return self._master

    def setMasterItem(self, item):
        """
        Set master parameter item.

        Arguments:
            item (ParameterItem): Master item.
        """
        self._master = item

    def slaveItem(self):
        """
        Slave parameter item e.g. toplevel item in another tree which
        is describe the same keyword like and this item

        Returns:
            ParameterItem: Slave item.
        """
        return self._slave

    def setSlaveItem(self, item):
        """
        Set slave parameter item.

        Arguments:
            item (ParameterItem): Slave item.
        """
        self._slave = item

    def cleanup(self):
        """
        Remove internal structures
        """
        if self._timer is not None:
            self._timer.deleteLater()
            self._timer = None

    def grid(self):
        """
        Get the grid layout got from parent item.

        Returns:
            QGridLayout: Grid layout.
        """
        return self.parentItem().grid() \
            if self.parentItem() is not None else None

    def command(self):
        """
        Get the command got from parent item.

        Returns:
            Command: Command object.
        """
        return self.itemPath().command()

    def itemName(self):
        """
        Get item's name, i.e. name of the item's object.

        Returns:
            str: Item's name.
        """
        return self.itemPath().name()

    def itemPath(self):
        """
        Get item's path, i.e. item name concatenated with names
        of the item's parents by dots.

        Returns:
            str: Item's path.
        """
        return self._path

    def rootItem(self):
        """
        Get root item.

        Returns:
            ParameterItem: Root item.
        """
        item = self
        while item.parentItem() is not None:
            item = item.parentItem()
        return item

    def parentItem(self):
        """
        Get parent item.

        Returns:
            ParameterItem: Parent item (None for top-level item).
        """
        return self._parent_item

    def setParentItem(self, parent_item):
        """
        Set parent item.

        Arguments:
            parent_item (ParameterItem): Parent item.
        """
        if self._parent_item != parent_item:
            if self._parent_item is not None:
                self._parent_item.removeChildItem(self)
            self._parent_item = parent_item
            if self._parent_item is not None:
                self._parent_item.appendChildItem(self)

    def childItems(self, **kwargs):
        """
        Get child items.

        Returns:
            list[ParameterItem]: Child items.
        """
        items = []
        rec = kwargs.get("all")
        if rec is not None and rec:
            for item in self._child_items:
                items.append(item)
                items = items + item.childItems(**kwargs)
        else:
            items = self._child_items
        return items

    def appendChildItem(self, child):
        """
        Append item to the child list.

        Arguments:
            child (ParameterItem): Child item.
        """
        if not self._child_items.__contains__(child):
            self._child_items.append(child)
            child.setParentItem(self)

    def removeChildItem(self, child):
        """
        Remove item from the child list.

        Arguments:
            child (ParameterItem): Child item.
        """
        if child in self._child_items:
            self._child_items.remove(child)
            child.setParentItem(None)

    def moveChildItem(self, child, offset):
        """
        Move item in the child list.

        Arguments:
            child (ParameterItem): Child item.
            offset (int): Child item position offset.
        """
        if child in self._child_items:
            curpos = self._child_items.index(child)
            newpos = min(max(curpos + offset, 0), len(self._child_items) - 1)
            if newpos != curpos:
                self._child_items.remove(child)
                self._child_items.insert(newpos, child)

    def dependChanged(self, item):
        """
        Invoked when value of item which this item depends from is changed.
        Default implementation does nothing.
        Must be reimplemented in subclasess.

        Arguments:
            item (ParameterItem): dependent item
        """
        pass

    def dependItems(self):
        """
        List of dependant items

        Returns:
            (list): List of dependant ParameterItem objects
        """
        return self._depend_items

    def appendDependItem(self, item):
        """
        Append dependant item.

        Arguments:
            item (ParameterItem): Dependant item.
        """
        if not self._depend_items.__contains__(item):
            self._depend_items.append(item)

    def removeDependItem(self, item):
        """
        Remove dependant item.

        Arguments:
            item (ParameterItem): Dependant item.
        """
        if self._depend_items.__contains__(item):
            self._depend_items.remove(item)

    def appendTo(self):
        """
        Append item to the parameter grid layout.

        Method should be implemented in sub-classes.
        Default implementation does nothing.
        """
        pass

    def isAppended(self):
        """
        Item append to the parameter grid layout state.

        Method should be implemented in sub-classes.
        Default implementation return False.
        """
        pass

    def removeFrom(self):
        """
        Remove item from the parameter grid layout.

        Method should be implemented in sub-classes.
        Default implementation does nothing.
        """
        tbl = self.grid()
        last = -1
        for row in xrange(tbl.rowCount() - 1, -1, -1):
            for col in xrange(tbl.columnCount()):
                if tbl.itemAtPosition(row, col) is not None:
                    last = row
                    break
            if last != -1:
                break

    def itemRect(self):
        """
        Get item rectangle in grid layout.

        Method should be implemented in sub-classes.
        Default implementation returns invalid rect.
        """
        pass

    def itemAt(self, pos):
        """
        Gets the child parameter item contained specified point.

        Arguments:
            pos (QPoint): Position point

        Returns:
            (ParameterItem): Child item contained position.
        """
        item = None
        for i in self.childItems(all=True):
            if i.isAppended():
                rect = i.itemRect()
                if rect is not None and rect.contains(pos):
                    item = i
                    break
        return item

    def keyword(self):
        """
        Get the parameter keyword definition of item.

        Returns:
            PartOfSyntax: catalog keyword definition object.
        """
        return self.itemPath().keyword()

    def cataTypeId(self):
        """
        Return catalog type id of keyword

        Returns:
           IDS: catalog type identifier
        """
        return get_cata_typeid(self.keyword())

    def isItemList(self):
        """
        Returns 'true' if the item parameter keyword is sequence.

        Returns:
            bool: Sequence flag.
        """
        return self.itemPath().isKeywordSequence() and \
            not self.itemPath().isInSequence() and \
            self.itemPath().keywordType() == KeywordType.Standard

    def findItemByPath(self, path):
        """
        Get child item with specified path.

        Arguments:
            path: Item path.

        Returns:
            ParameterItem: Child item.
        """
        res_item = None
        sub_path = path.path() \
            if isinstance(path, ParameterPath) else path
        if sub_path.startswith(ParameterPath.separator):
            my_path = self.itemPath().path() + ParameterPath.separator
            if sub_path.startswith(my_path):
                sub_path = sub_path[len(my_path):len(sub_path)]
            else:
                sub_path = ""

        if len(sub_path) > 0:
            sub_list = sub_path.split(ParameterPath.separator)
            found_item = self.findItemByName(sub_list.pop(0))
            if found_item is not None:
                if len(sub_list) > 0:
                    res_item = found_item.findItemByPath(\
                        ParameterPath.separator.join(sub_list))
                else:
                    res_item = found_item

        return res_item

    def findItemByName(self, name):
        """
        Get child item with specified name.

        Arguments:
            name (str): Item's name.

        Returns:
            ParameterItem: Child item.
        """
        res_item = None
        for item in self.childItems():
            if item.itemName() == name:
                res_item = item
                break
        return res_item

    def findItemsByName(self, name):
        """
        Get child items with specified name.

        Arguments:
            name (str): Item's name.

        Returns:
            list: List of child ParameterItem.
        """
        res_list = []
        for item in self.childItems():
            if item.itemName() == name:
                res_list.append(item)
            res_list = res_list + item.findItemsByName(name)
        return res_list

    # pragma pylint: disable=no-self-use
    def isUsed(self):
        """
        Check if the editor item is used (chosen by the user).

        This method must be implemented in sub-classes.
        Default implementation returns False.

        Returns:
            True if the item is used (checked); False otherwise.
        """
        return False

    # pragma pylint: disable=no-self-use
    def setIsUsed(self, state):
        """
        Set the editor item is should be used (chosen by the user).

        This method must be implemented in sub-classes.
        Default implementation does nothing.
        """
        pass

    # pragma pylint: disable=no-self-use
    def value(self):
        """
        Get value stored in the item.

        This method must be implemented in sub-classes.
        Default implementation returns None.

        Returns:
            any: int, float, str or any other appropriate value.
        """
        return None

    def setValue(self, value):
        """
        Set the item's value.

        This method must be implemented in sub-classes.
        Default implementation does nothing.

        Arguments:
            value (any): Parameter's value.
        """
        pass

    def globalStorage(self, with_default=False):
        """
        Total context container (dict) with values of all keyword items.

        Returns:
            dict: Dictionary with all child item values.
        """
        item = self.rootItem()
        while item.masterItem() is not None:
            item = item.masterItem().rootItem()
        return item.itemValue(glob=True, default=with_default)

    def conditionStorage(self, with_default=False):
        """
        Total one level context container (dict) with
        values of all keyword items.

        Returns:
            dict: Dictionary with all child item values.
        """
        item = self.rootItem()
        context = item.itemValue(default=with_default)
        while item.masterItem() is not None:
            item = item.masterItem().rootItem()
            topctx = item.itemValue(default=with_default)
            if isinstance(topctx, dict):
                if isinstance(context, dict):
                    topctx.update(context)
                context = topctx
        return context

    def itemValue(self, **kwargs):
        """
        Get values of child items.

        Returns:
            dict: Dictionary with all child item values::

                {
                    name (str): value (any)
                }
        """
        glob = kwargs['glob'] if 'glob' in kwargs else False
        default = kwargs['default'] if 'default' in kwargs else False
        childvalue = self.storage
        typeid = self.cataTypeId()
        if typeid in (IDS.fact, IDS.bloc, IDS.command) \
                and len(self.childItems()) > 0:
            childvalue = {}
            for item in self.childItems():
                if item.isUsed() or (default and item.hasDefaultValue()):
                    if item.isUsed():
                        val = item.slaveItem().itemValue(**kwargs) \
                            if glob and item.slaveItem() is not None else \
                            item.itemValue(**kwargs)
                    elif not self.testFlags(self.ItemFlags.Excluded):
                        val = item.defaultValue()
                    if val is not None and item.cataTypeId() == IDS.bloc \
                            and isinstance(val, dict):
                        for key, value in val.iteritems():
                            childvalue[key] = value
                    else:
                        childvalue[item.itemName()] = val
        self.storage = childvalue
        return childvalue

    def setItemValue(self, values):
        """
        Set values of child items.

        Arguments:
            values: Dictionary with item values (see `childValues()`).
        """
        self.storage = values
        typeid = self.cataTypeId()
        if typeid in (IDS.fact, IDS.bloc, IDS.command) \
                and isinstance(values, dict):
            for item in self.childItems():
                if item.itemName() in values:
                    item.setItemValue(values[item.itemName()])
                    if not item.isUsed():
                        item.setIsUsed(True)
                        for rule in item.attachedItemRules():
                            rule.stateChanged(item)
                elif item.cataTypeId() == IDS.bloc:
                    item.updateCondition()
                    item.updateConditions()
                    if item.isUsed():
                        item.setItemValue(values)
        self.valueChanged()

    def filterItem(self, text):
        """
        Filter out the item.

        This method must be implemented in sub-classes.
        Default implementation does nothing.

        Arguments:
            text (str): Regular expression.
        """
        pass

    def isKeywordMandatory(self):
        """
        Check if Parameter is mandatory.

        Returns:
            True if the parameter is mandatory; False otherwise.
        """
        res = False
        param_def = self.keyword()
        if param_def is not None:
            res = param_def.isMandatory()
        return res

    def hasDefaultValue(self):
        """
        Gets the keyword default value state.
        """
        param_def = self.keyword()
        islist = self.itemPath().isKeywordSequence() and \
            not self.itemPath().isInSequence()
        state = hasattr(param_def, 'hasDefaultValue') and \
            param_def.hasDefaultValue() and not islist

        return state

    def defaultValue(self):
        """
        Gets the keyword default value.
        """
        return self.keyword().defaultValue()

    def itemRules(self, rec=False):
        """
        Rules list of the items

        Returns:
           list: List of the ParameterRuleItem object from item.
        """
        rulelist = self._rules
        if rec:
            for item in self.childItems():
                rulelist = rulelist + item.itemRules(rec)
        return rulelist

    def attachedItemRules(self):
        """
        Returns the list of parameter rules which contains this item.

        Returns:
            list: List of ParameterRuleItem objects
        """
        ruleslist = []
        if self.parentItem() is not None:
            ruleslist = self.parentItem().itemRules()
        reslist = []
        for rule in ruleslist:
            if rule.containsItem(self):
                reslist.append(rule)
        return reslist

    def attachedItemRuleNames(self):
        """
        Returns the list of name for parameter rules which contains this item.

        Returns:
            list: List of unique strings with attached rule names
        """
        nameslist = []
        ruleslist = self.attachedItemRules()
        uniq = {}
        for rule in ruleslist:
            rulename = rule.itemName()
            if rulename not in uniq:
                nameslist.append(rulename)
                uniq[rulename] = 0
        return nameslist

    # pragma pylint: disable=no-self-use
    def validate(self):
        """
        Perform value validation.

        This method must be implemented in sub-classes.
        Default implementation does nothing and returns True.

        Returns:
           bool: Validation status: True if value is valid; False
           otherwise.
        """
        return True

    def updateItem(self, force=False):
        """
        Schedule item's components state update.
        """
        if force:
            self._updateItem()
        else:
            if self._timer is None:
                self._timer = QTimer()
                self._timer.setInterval(0)
                self._timer.setSingleShot(True)
                self._timer.timeout.connect(self._onUpdateTimeout)

            if self._timer.isActive():
                self._timer.stop()
            self._timer.start()

    def updateCondition(self):
        """
        Perform item updation according to the condition.
        This method must be implemented in sub-classes.
        Default implementation does nothing.
        """
        pass

    def updateConditions(self):
        """
        Perform child items updation according to the condition.
        """
        for item in self.childItems():
            item.updateCondition()

        for i in self.childItems():
            i.updateConditions()

    def updateRules(self, item):
        """
        Update rules after parameter value's changing.
        """
        rules = self.itemRules()
        for rule in rules:
            if rule.containsItem(item):
                rule.stateChanged(item)

        for item in self.childItems():
            item.updateRules(item)

    def valueChanged(self):
        """
        Called when item's value is changed.
        """
        for item in self.dependItems():
            item.dependChanged(self)
        if self.parentItem() is not None:
            self.parentItem().valueChanged()

    def checkChanged(self, item):
        """Called when item's check state is changed."""
        if self.parentItem() is not None:
            self.parentItem().checkChanged(item)

    def itemStateChanged(self, item):
        """
        Called when item state is changed.

        Arguments:
            path (ParameterPath): Parameter path.
        """
        if self.parentItem() is not None:
            self.parentItem().itemStateChanged(item)

    def parameterActivated(self, path, link=''):
        """
        Called when item's sub-editor is activated.

        Arguments:
            path (ParameterPath): Parameter path.
        """
        if self.parentItem() is not None:
            self.parentItem().parameterActivated(path, link)

    def updateTranslations(self):
        """
        Update translations in GUI elements.
        Can be redefined in subclasses.
        """
        for item in self.childItems():
            item.updateTranslations()

    def itemClicked(self, event):
        """
        Invoked when mouse pressed inside item rect.
        Default implementation does nothing.
        Should be reimplemented in subclassed.
        """
        pass

    def _onUpdateTimeout(self):
        """
        Invoked when update timer timeout activated,
        """
        self._updateItem()

    def _updateItem(self):
        """
        Update the item components state.
        """
        if self._timer is not None and self._timer.isActive():
            self._timer.stop()


class ParameterEditItem(ParameterItem):
    """Simple parameter edition item."""

    def __init__(self, **kwargs):
        """
        Create item.

        Arguments:
            **kwargs: Arbitrary keyword arguments.
        """
        super(ParameterEditItem, self).__init__(**kwargs)

        tbl = self.grid()

        param_mandatory = self.isKeywordMandatory()
        rules = self.attachedItemRules()

        self.check = None
        self.mandatory = None
        self.label = None
        self.notsupp = None
        if not param_mandatory:
            exclusive = False
            for arule in rules:
                if arule.isExclusive():
                    exclusive = True
                    break
            if exclusive:
                self.check = QRadioButton()
            else:
                self.check = QCheckBox()
            self.check.setAutoExclusive(False)
            self.check.setObjectName(self.itemName())
            self.check.clicked.connect(self._checkClicked)
            self.check.toggled.connect(self._checkToggled)
        self.mandatory = QLabel("*" if param_mandatory else "")
        pal = self.mandatory.palette()
        pal.setColor(self.mandatory.foregroundRole(), Qt.red)
        self.mandatory.setPalette(pal)

        self.label = ParameterLabel(self.itemPath(), rules)
        self.label.clicked.connect(self._labelClicked)

        factory = parameter_editor_factory()
        self.editor = factory.createEditor(self.itemPath(), tbl.parentWidget())

        if self.editor is None:
            label = translate("ParameterPanel", "Not Supported")
            self.notsupp = QLabel(italic(bold(label)), tbl.parentWidget())
            self.notsupp.setFrameStyle(QFrame.Sunken|QFrame.Panel)
            self.notsupp.setAlignment(Qt.AlignCenter)

        self.default = None
        if self.hasDefaultValue():
            self.default = QToolButton()
            self.default.setIcon(load_icon("as_pic_undo.png"))
            self.default.clicked.connect(self._resetToDefault)
            self.default.setToolTip(translate("ParameterPanel",
                                              "Reset to default"))

        self.resetValue()

        if self.editor:
            self.editor.valueChanged.connect(self._valueChanged)
            self.editor.linkActivated.connect(self._linkActivated)

    def cleanup(self):
        """
        Remove internal structures
        """
        super(ParameterEditItem, self).cleanup()

        if self.check is not None:
            self.check.deleteLater()
            self.check = None
        if self.label is not None:
            self.label.deleteLater()
            self.label = None
        if self.mandatory is not None:
            self.mandatory.deleteLater()
            self.mandatory = None
        if self.editor is not None:
            self.editor.deleteLater()
            self.editor = None
        if self.default is not None:
            self.default.deleteLater()
            self.default = None
        if self.notsupp is not None:
            self.notsupp.deleteLater()
            self.notsupp = None

    def appendTo(self):
        """
        Append item to the parameter grid layout.
        """
        super(ParameterEditItem, self).appendTo()

        tbl = self.grid()
        added = self.isAppended()

        if not added:
            index = tbl.actualRowCount()
            if self.check is not None:
                tbl.addWidget(self.check, index, self.ColumnId.Check)

            if self.label is not None:
                tbl.addWidget(self.label, index, self.ColumnId.Label)

            if self.mandatory is not None:
                tbl.addWidget(self.mandatory, index, self.ColumnId.Mandatory)

            if self.editor is not None:
                tbl.addWidget(self.editor, index, self.ColumnId.Editor)
            elif self.notsupp is not None:
                tbl.addWidget(self.notsupp, index, self.ColumnId.Editor)

            if self.default is not None:
                tbl.addWidget(self.default, index, self.ColumnId.Default)

            self.updateItem()

    def isAppended(self):
        """
        Item append to the parameter grid layout state.
        """
        tbl = self.grid()
        return tbl.indexOf(self.label) >= 0 or \
            (self.editor is not None and tbl.indexOf(self.editor) >= 0)

    def removeFrom(self):
        """Remove item from the parameter grid layout."""
        tbl = self.grid()
        added = self.isAppended()

        if added:
            if self.check is not None:
                tbl.removeWidget(self.check)
            if self.label is not None:
                tbl.removeWidget(self.label)
            if self.mandatory is not None:
                tbl.removeWidget(self.mandatory)
            if self.editor is not None:
                tbl.removeWidget(self.editor)
            if self.notsupp is not None:
                tbl.removeWidget(self.notsupp)
            if self.default is not None:
                tbl.removeWidget(self.default)

        super(ParameterEditItem, self).removeFrom()

    def dependChanged(self, item):
        """
        Invoked when value of item which this item depends from is changed.
        Default implementation does nothing.
        Must be reimplemented in subclasess.

        Arguments:
            item (ParameterItem): dependent item
        """
        if self.editor is not None:
            self.editor.dependValue(item.itemPath(), item.itemValue())

    def itemWidgets(self):
        """
        Gets the item widgets.

        Returns:
            [QWidget]: List of widgets contained by item.
        """
        return [self.check, self.label, self.mandatory,
                self.editor, self.notsupp, self.default]

    def itemRect(self):
        """
        Get item rectangle in grid layout.
        """
        tbl = self.grid()
        widgets = self.itemWidgets()
        begrow = endrow = begcol = endcol = -1
        for wid in widgets:
            if wid is not None:
                idx = tbl.indexOf(wid)
                if idx >= 0:
                    pos = tbl.getItemPosition(idx)
                    begrow = pos[0] if begrow < 0 else min(begrow, pos[0])
                    endrow = pos[0] + pos[2] - 1 \
                        if endrow < 0 else max(endrow, pos[0] + pos[2] - 1)
                    begcol = pos[1] if begcol < 0 else min(begcol, pos[1])
                    endcol = pos[1] + pos[3] - 1 \
                        if endcol < 0 else max(endcol, pos[1] + pos[3] - 1)

        if begrow < 0 or endrow < 0 or begcol < 0 or endcol < 0:
            return QRect()

        start = tbl.cellRect(begrow, begcol)
        finish = tbl.cellRect(endrow, endcol)

        rect = QRect(start.topLeft(), finish.bottomRight())
        return rect


    def isUsed(self):
        """
        Check if the editor item is used (chosen by the user).

        Returns:
            True if the item is used (checked); False otherwise.
        """
        return (self.isKeywordMandatory() or \
                    self.testFlags(self.ItemFlags.Mandatory) or \
                    self.isChecked() or self.parentItem().isItemList()) and \
                    not self.testFlags(self.ItemFlags.Disabled)

    def setIsUsed(self, state):
        """
        Set the editor item is should be used (chosen by the user).
        """
        self.setChecked(state)

    def isChecked(self):
        """
        Check if item is chosen by the user.

        Returns:
            True if item is used (checked); False otherwise.
        """
        state = False
        if self.check is not None:
            state = self.check.isChecked()
        return state

    def setChecked(self, value):
        """
        Change parameter's usage status.

        Arguments:
            value (bool): True if item is set as used; False otherwise.
        """
        if self.check is not None:
            self.check.setChecked(value)

    def value(self):
        """
        Get value stored in the item.

        Returns:
            any: int, float, str or any other appropriate value.
        """
        val = None
        if self.editor is not None:
            val = self.editor.value()
        return val

    def setValue(self, val):
        """
        Set the item's value.

        Arguments:
            value (any): Parameter's value.
        """
        if self.editor is not None:
            try:
                self.editor.setValue(val)
            except ValueError:
                pass

    def resetValue(self):
        """Reset item to parameter's default value (if specified)."""
        if self.hasDefaultValue():
            self.setValue(self.defaultValue())

    def hasDefaultValue(self):
        """
        Gets the keyword default value state.
        """
        state = super(ParameterEditItem, self).hasDefaultValue()
        if self.editor is not None:
            state = state and not self.editor.forceNoDefault()
        return state

    def itemValue(self, **kwargs):
        """
        Get values of item and child items.
        """
        childvalue = self.storage
        typeid = self.cataTypeId()
        if (typeid == IDS.simp and not self.isItemList()) or \
                (self.isItemList() and not len(self.childItems())):
            if self.editor is not None:
                childvalue = self.editor.value()
        else:
            childvalue = super(ParameterEditItem, self).itemValue(**kwargs)
        return childvalue

    def setItemValue(self, values):
        """
        Set values of child items.
        """
        self.storage = values
        if self.editor is not None:
            self.editor.setValue(values)
            self.valueChanged()

        if self.isItemList():
            super(ParameterEditItem, self).setItemValue(values)

    def filterItem(self, text):
        """
        Filter out the item.

        Arguments:
            text (str): Regular expression.
        """
        hidden = text != "" and not self.label.match(text)
        self.modifyFlags(self.ItemFlags.Filtered, hidden)

    def setVisible(self, value):
        """
        Set item's visibility.

        Arguments:
            value (bool): True to show item; False to hide it.
        """
        if self.check is not None:
            state = value and not self.testFlags(self.ItemFlags.Disabled) \
                and not self.testFlags(self.ItemFlags.Mandatory)
            self.check.setVisible(state)
        if self.label is not None:
            self.label.setVisible(value)
        if self.mandatory is not None:
            self.mandatory.setVisible(value)
        if self.editor is not None:
            self.editor.setVisible(value)
        if self.notsupp is not None:
            self.notsupp.setVisible(value)
        if self.default is not None:
            self.default.setVisible(value and self.hasDefaultValue())

    def flagsChanged(self, flags):
        """
        Invoked when item flags was changed
        """
        super(ParameterEditItem, self).flagsChanged(flags)
        self.updateItem()

    def updateTranslations(self):
        """
        Update translations in GUI elements.
        """
        super(ParameterEditItem, self).updateTranslations()

        self._updateContents()
        if self.label is not None:
            self.label.updateTranslations()
        if self.editor is not None:
            self.editor.updateTranslations()

    def itemClicked(self, event):
        """
        Invoked when mouse pressed inside item rect.
        """
        if self.isUsed():
            return

        wid = QApplication.widgetAt(event.globalPos())

        if wid is None or wid == self.check:
            return

        if self.check is not None and \
                self.check.isVisibleTo(self.check.parentWidget()) and \
                self.check.isEnabled():
            self.check.setChecked(True)
            if self.isUsed():
                self._checkClicked()
                self._checkToggled()
                self.updateItem(True)
                if not is_child(wid, self.label) and wid.isEnabled():
                    QApplication.processEvents()
                    evn = QMouseEvent(event.type(),
                                      wid.mapFromGlobal(event.globalPos()),
                                      event.button(), event.buttons(),
                                      event.modifiers())
                    QApplication.postEvent(wid, evn)

    def valueChanged(self):
        """Called when item's value is changed."""
        super(ParameterEditItem, self).valueChanged()
        self._updateContents()

    def _resetToDefault(self):
        """Called when `Reset` button is clicked."""
        self.resetValue()

    def _checkClicked(self):
        """Called when enable/disable check box is clicked."""
        self.checkChanged(self)
        self.valueChanged()

    def _checkToggled(self):
        """Called when enable/disable check box is toggled."""
        self.updateItem()

    def _linkActivated(self, link):
        """Called when sub-editor is activated."""
        self.parameterActivated(self.itemPath(), link)

    def _valueChanged(self):
        """Called when editor value is changed."""
        self.valueChanged()
        self.updateItem()

    def _labelClicked(self):
        """Called when label clicked"""
        if self.check is not None and \
                self.check.isVisibleTo(self.check.parentWidget()) and \
                self.check.isEnabled():
            self.check.setChecked(not self.check.isChecked())
            self._checkClicked()
            self._checkToggled()

    def _updateItem(self):
        """
        Update item components state.
        """
        super(ParameterEditItem, self)._updateItem()

        enabled = self.testFlags(self.ItemFlags.Mandatory) or \
            self.isKeywordMandatory() or self.isChecked() \
            or (self.parentItem() is not None \
                    and self.parentItem().isItemList())
        blocked = self.testFlags(self.ItemFlags.Disabled)

        if self.check:
            self.check.setEnabled(not blocked)
        if self.label is not None:
            self.label.setEnabled(enabled and not blocked)
        if self.editor is not None:
            self.editor.setEnabled(enabled and not blocked)
        if self.notsupp is not None:
            self.notsupp.setEnabled(enabled and not blocked)
        if self.default is not None:
            self.default.setEnabled(enabled and not blocked)
        if self.mandatory:
            mflag = self.testFlags(self.ItemFlags.Mandatory) or \
                self.isKeywordMandatory()
            self.mandatory.setText("*" if mflag else "")
        if self.default is not None:
            self.default.setEnabled(self.defaultValue() != self.value())

        hidden = self.testFlags(self.ItemFlags.Filtered) or \
            self.testFlags(self.ItemFlags.Excluded) or \
            (self.testFlags(self.ItemFlags.HideUnused) and not self.isUsed())
        self.setVisible(not hidden)

    def _updateContents(self):
        """
        Updates the content info label.
        """
        if self.label is None:
            return

        mode = "none"
        content = None
        if self.cataTypeId() != IDS.simp or \
                self.itemPath().keywordType() != KeywordType.Standard:
            extlist = behavior().external_list
            if extlist or \
                    (not extlist and \
                         (not self.itemPath().isKeywordSequence() or \
                              self.itemPath().keywordType() != \
                              KeywordType.Standard)):
                mode = behavior().content_mode
                if mode is not None and mode != "none":
                    content = self.itemValue()
        self.label.setContents(content, mode)


class ParameterListItem(ParameterEditItem):
    """Simple parameter edition item contained by list."""

    def __init__(self, **kwargs):
        """
        Create item.

        Arguments:
            **kwargs: Arbitrary keyword arguments.
        """
        super(ParameterListItem, self).__init__(**kwargs)

        if self.check is not None:
            self.check.deleteLater()
            self.check = None

        self.spin = SpinWidget()
        self.spin.clicked.connect(self._move)
        self.spin.setToolTip(translate("ParameterPanel",
                                       "Change item position in list"))

        self.remove = QToolButton()
        self.remove.setIcon(load_icon("as_pic_delete.png"))
        self.remove.clicked.connect(self._remove)
        self.remove.setObjectName("Remove_Item")
        self.remove.setToolTip(translate("ParameterPanel", "Remove item"))

    def cleanup(self):
        """
        Remove internal structures
        """
        super(ParameterListItem, self).cleanup()

        if self.spin is not None:
            self.spin.deleteLater()
            self.spin = None

        if self.remove is not None:
            self.remove.deleteLater()
            self.remove = None

    def appendTo(self):
        """
        Append item to the parameter grid layout.
        """
        if not self.isAppended():
            tbl = self.grid()
            index = tbl.actualRowCount()

            super(ParameterListItem, self).appendTo()

            if self.spin is not None:
                tbl.addWidget(self.spin, index, self.ColumnId.Move)
            if self.remove is not None:
                tbl.addWidget(self.remove, index, self.ColumnId.Remove)

    def removeFrom(self):
        """
        Remove item from the parameter grid layout.
        """
        if self.isAppended():
            tbl = self.grid()
            if self.spin is not None:
                tbl.removeWidget(self.spin)
            if self.remove is not None:
                tbl.removeWidget(self.remove)

        super(ParameterListItem, self).removeFrom()

    def itemWidgets(self):
        """
        Gets the item widgets.

        Returns:
            [QWidget]: List of widgets contained by item.
        """
        lst = super(ParameterListItem, self).itemWidgets()
        lst.append(self.spin)
        lst.append(self.remove)
        return lst

    def setVisible(self, value):
        """
        Set item's visibility.

        Arguments:
            value (bool): True to show item; False to hide it.
        """
        super(ParameterListItem, self).setVisible(value)

        if self.spin is not None:
            self.spin.setVisible(value)
        if self.remove is not None:
            self.remove.setVisible(value)

    def _updateItem(self):
        """
        Update item's widgets.
        """
        super(ParameterListItem, self)._updateItem()

        noremove = self.testFlags(self.ItemFlags.CantRemove)
        first = False
        last = False

        if self.parentItem() is not None:
            itemlist = self.parentItem().childItems()
            if self in itemlist:
                index = itemlist.index(self)
                first = index == 0
                last = index == (len(itemlist) - 1)

        if self.spin is not None:
            self.spin.setSpinEnabled(SpinWidget.SpinType.Up, not first)
            self.spin.setSpinEnabled(SpinWidget.SpinType.Down, not last)

        if self.remove is not None:
            self.remove.setEnabled(not noremove)

    # pragma pylint: disable=no-member
    def _remove(self):
        """
        Called when 'Remove' button is clicked in list parameter view.
        """
        root = self.rootItem()
        if hasattr(root, "deleteItem"):
            root.deleteItem(self)

    # pragma pylint: disable=no-member
    def _move(self, spintype):
        """
        Called when 'Up' or 'Down' button is clicked in list parameter view.
        """
        root = self.rootItem()
        if hasattr(root, "moveItem"):
            if spintype == SpinWidget.SpinType.Up:
                root.moveItem(self, -1)
            elif spintype == SpinWidget.SpinType.Down:
                root.moveItem(self, 1)


class ParameterBlockItem(ParameterItem):
    """List of items item."""

    def __init__(self, **kwargs):
        """
        Create item.

        Arguments:
            **kwargs: Arbitrary keyword arguments.
        """
        super(ParameterBlockItem, self).__init__(**kwargs)

        self._createRules()

        param_def = self.keyword()

        if self.isItemList():
            nb_min = 0
            if 'min' in param_def.definition:
                nb_min = param_def.definition['min']

            for i in range(nb_min):
                ParameterListItem(item_path=self.itemPath().
                                  absolutePath(str(i)),
                                  parent_item=self)
            self.itemStateChanged(self)
        else:
            used_kws = {}
            block_params = []
            for i in param_def.keywords:
                block_params.append(i)
                used_kws[i] = 0

            for i in param_def.entites:
                if i not in used_kws:
                    block_params.append(i)
                    used_kws[i] = 0

            extlist = behavior().external_list

            for param in block_params:
                paramkw = param_def.getKeyword(param, None)
                if paramkw is not None and not paramkw.isHidden():
                    param_path = self.itemPath().absolutePath(param)
                    typeid = get_cata_typeid(paramkw)
                    if param_path.isKeywordSequence() and \
                            not param_path.isInSequence() and \
                            param_path.keywordType() == \
                            KeywordType.Standard and not extlist:
                        ParameterSequenceItem(item_path=param_path,
                                              parent_item=self)
                    elif typeid in (IDS.simp, IDS.fact):
                        ParameterEditItem(item_path=param_path,
                                          parent_item=self)
                    else:
                        ParameterBlockItem(item_path=param_path,
                                           parent_item=self)

    # pragma pylint: disable=no-self-use
    def reorder(self, items):
        """
        Reorder items.

        This method can be overridden in sub-classes.
        Default implementation does nothing.

        Arguments:
            items (list[ParameterItem]): Child items.

        Returns:
            list[ParameterItem]: Reordered child items.
        """
        return items

    def appendTo(self):
        """
        Append item to the parameter grid layout.
        """
        super(ParameterBlockItem, self).appendTo()

        item_list = self.reorder(self._allBlocChildItems(self))
        for pitem in item_list:
            pitem.appendTo()

    def isAppended(self):
        """
        Item append to the parameter grid layout state.
        """
        added = False
        item_list = self._allBlocChildItems(self)
        for pitem in item_list:
            added = pitem.isAppended()
            if added:
                break
        return added

    def removeFrom(self):
        """Remove item from the parameter grid layout."""
        for pitem in self.childItems():
            pitem.removeFrom()

        super(ParameterBlockItem, self).removeFrom()

    # pragma pylint: disable=redefined-variable-type
    def itemValue(self, **kwargs):
        """
        Get values of child items.

        Returns:
            dict: Dictionary with all child item values::

                {
                    name (str): value (any)
                }
        """
        glob = kwargs['glob'] if 'glob' in kwargs else False
        childvalue = self.storage
        if len(self.childItems()) > 0 and self.isItemList():
            childvalue = tuple([item.slaveItem().itemValue(**kwargs) \
                                    if glob and item.slaveItem() is not None \
                                    else item.itemValue(**kwargs)
                                for item in self.childItems()])
            # if there is only one Variable of type tuple, just take it
            if len(childvalue) == 1 and isinstance(childvalue[0], Variable):
                if isinstance(childvalue[0].evaluation, (list, tuple)):
                    childvalue = childvalue[0]
            self.storage = childvalue
        else:
            childvalue = super(ParameterBlockItem, self).itemValue(**kwargs)
        return childvalue

    def setItemValue(self, values):
        """
        Set values of child items.

        Arguments:
            values: Dictionary with item values (see `childValues()`).
        """
        if self.isItemList() and values is not None:
            val_list = []
            if isinstance(values, tuple):
                val_list = list(values)
            else:
                val_list.append(values)
            list_len = len(val_list)
            child_len = len(self.childItems())
            if list_len > child_len:
                for i in xrange(list_len - child_len):
                    apath = self.itemPath().absolutePath(str(child_len + i))
                    nitem = ParameterListItem(item_path=apath,
                                              parent_item=self)
                    nitem.appendTo()
            if list_len < child_len:
                for i in xrange(child_len - list_len):
                    citem = self.childItems()[list_len]
                    citem.removeFrom()
                    self.removeChildItem(citem)
            for i in xrange(list_len):
                item = self.childItems()[i]
                item.setItemValue(val_list[i])
            self.itemStateChanged(self)
            self.valueChanged()
        else:
            super(ParameterBlockItem, self).setItemValue(values)

    def isUsed(self):
        """
        Check if the editor item is used (chosen by the user).
        This method must be implemented in sub-classes.

        Returns:
            True if the item is used; False otherwise.
        """
        return not self.testFlags(self.ItemFlags.Excluded)

    def filterItem(self, text):
        """
        Filter out the item.

        Arguments:
            text (str): Regular expression.
        """
        for pitem in self.childItems():
            pitem.filterItem(text)

    def validate(self):
        """
        Perform value validation.

        Returns:
           bool: Validation status: True if value is valid; False
           otherwise.
        """
        state = True
        for pitem in self.childItems():
            state = state and pitem.validate()
            if not state:
                break
        return state

    def checkChanged(self, item):
        """Called when item's check state is changed."""
        self.updateRules(item)
        super(ParameterBlockItem, self).checkChanged(item)

    def valueChanged(self):
        """Called when item's value is changed."""
        self.updateCondition()
        self.updateConditions()
        super(ParameterBlockItem, self).valueChanged()

    def updateCondition(self):
        """
        Perform item updation according to the condition.
        Default implementation does nothing.

        Arguments:
           storage (dict): Current values context
        """
        kwdef = self.keyword()
        if kwdef is not None and hasattr(kwdef, "getCondition"):
            if kwdef.getCondition():
                storage = self.conditionStorage(True)
                state = KeysMixing.is_item_enabled(kwdef, storage)
                if state and self.parentItem() is not None and \
                        self.parentItem().testFlags(self.ItemFlags.Excluded):
                    state = False
                self.modifyFlags(self.ItemFlags.Excluded, not state)

        super(ParameterBlockItem, self).updateCondition()

    def flagsChanged(self, flags):
        """
        Invoked when item flags was changed
        """
        super(ParameterBlockItem, self).flagsChanged(flags)
        for pitem in self.childItems():
            pitem.modifyFlags(flags, self.testFlags(flags))

    def _createRules(self):
        """
        Create parameter item rules according to rule objects
        from catalog keyword definition
        """
        if not self.isItemList():
            kword = self.itemPath().keyword()
            if kword is not None:
                rulelist = kword.rules
                for rule in rulelist:
                    self._rules.append(ParameterRuleItem(self, rule))

    def _allBlocChildItems(self, item):
        """
        Get the all bloc child items recursivelly
        """
        reslist = []
        if item is not None:
            itemlist = item.childItems()
            for i in itemlist:
                if i.cataTypeId() == IDS.bloc:
                    reslist = reslist + self._allBlocChildItems(i)
                else:
                    reslist.append(i)
        return reslist


class ParameterSequenceItem(ParameterEditItem):
    """Simple parameter edition item."""

    def __init__(self, **kwargs):
        """
        Create item.

        Arguments:
            **kwargs: Arbitrary keyword arguments.
        """
        super(ParameterSequenceItem, self).__init__(**kwargs)

        if self.panel() is not None:
            self.panel().gotoParameter.connect(self.parameterActivated)

    def panel(self):
        """
        Gets the sequence panel widget

        Returns:
            (QWidget): Panel with sequence items.
        """
        return self.editor.sequencePanel() \
            if (self.editor is not None and \
                    hasattr(self.editor, 'sequencePanel')) \
                    else None

    def appendTo(self):
        """
        Append item to the parameter grid layout.
        """
        if self.isAppended():
            return

        super(ParameterSequenceItem, self).appendTo()

        tbl = self.grid()
        index = tbl.actualRowCount()
        if self.panel() is not None:
            tbl.addWidget(self.panel(), index, self.ColumnId.Label,
                          1, self.ColumnId.Editor - self.ColumnId.Label + 1)

        self.updateItem()

    def removeFrom(self):
        """
        Remove item from the parameter grid layout.
        """
        if not self.isAppended():
            return

        super(ParameterSequenceItem, self).removeFrom()

        tbl = self.grid()
        if self.panel() is not None:
            tbl.removeWidget(self.panel())

    def findItemByName(self, name):
        """
        Get child item with specified name.

        Arguments:
            name (str): Item's name.

        Returns:
            ParameterItem: Child item.
        """
        return self.panel().findItemByName(name) \
            if self.panel() is not None else None

    def updateTranslations(self):
        """
        Update translations in GUI elements.
        """
        super(ParameterSequenceItem, self).updateTranslations()

        if self.panel() is not None:
            self.panel().updateTranslations()


class ParameterRuleItem(ParameterItem):
    """
    Base class for parameter rule operation.
    """

    class Watcher(QObject):
        """
        Class which monitors the show/hide event of rule items widgets.
        """
        visibilityChanged = pyqtSignal()

        def __init__(self):
            """
            Constructor
            """
            super(ParameterRuleItem.Watcher, self).__init__()
            self._widgets = []

        def eventFilter(self, obj, event):
            """
            Event filer that process show/hide events
            """
            if event.type() == QEvent.Show or \
                    event.type() == QEvent.Hide:
                self.visibilityChanged.emit()
            return super(ParameterRuleItem.Watcher, self).\
                eventFilter(obj, event)

        def setContent(self, widgets):
            """
            Sets the list of widgets which has been monitored
            """
            for wid in self._widgets:
                wid.removeEventFilter(self)

            self._widgets = []
            for wid in widgets:
                self._widgets.append(wid)
                wid.installEventFilter(self)


    def __init__(self, param_item, rule_obj):
        """
        Constructor

        Arguments:
            param_item (ParameterItem): Parameter item which rule belong to
            rule_obj (PartOfSyntax): Keyword rule object from catalog
        """
        super(ParameterRuleItem, self).\
            __init__(item_path=param_item.itemPath().
                     absolutePath(type(rule_obj).__name__),
                     parent_item=None)
        self._parent_item = param_item
        self._rule = rule_obj
        self._frame = None
        self._begitem = None
        self._enditem = None
        self._viswatcher = None

    def rule(self):
        """
        Returns the rule object

        Returns:
            PartOfSyntax: Rule catalog object
        """
        return self._rule

    def ruleKeywords(self):
        """
        Returns the rule object

        Returns:
            PartOfSyntax: Rule catalog object
        """
        return self.rule().ruleArgs if self.rule() is not None else None

    def ruleItems(self):
        """
        Returns the items which contained by rule in
        order defined by rule keywords.
        """
        items = []
        if self.parentItem():
            for kword in self.ruleKeywords():
                items = items + self.parentItem().findItemsByName(kword)
        return self._removeExcluded(items)

    def childItems(self, **kwargs):
        """
        Returns the items which contained by rule in
        order defined by catalog.

        Returns:
            item_list (list): List of items
        """
        itemlist = []
        owner = self.parentItem()
        kwlist = self.ruleKeywords()
        if owner is not None and kwlist is not None:
            kwdict = {}
            for kword in kwlist:
                kwdict[kword] = 0
            for item in owner.childItems(rec=True):
                if item.itemName() in kwdict:
                    itemlist.append(item)
        return self._removeExcluded(itemlist)

    def containsKeyword(self, kword):
        """
        Check the existance the specified keyword in rule

        Returns:
            bool: True if the keyword exist in rule or False otherwise
        """
        kwlist = self.ruleKeywords()
        return kword in kwlist if kwlist is not None else False

    def containsItem(self, item):
        """
        Check the existance the specified item in rule

        Returns:
            bool: True if the item exist in rule or False otherwise
        """
        return self.containsKeyword(item.itemName()) \
            if item is not None and item.parentItem() == self.parentItem() \
            else False

    def isExclusive(self):
        """
        Get the exclusive flag.

        Returns:
            bool: True if the rule allow only excusive content
        """
        return self.itemName() == "ExactlyOne"

    def isGrouped(self):
        """
        Get the grouping flag.

        Returns:
            bool: True if the rule allow to group items
        """
        return self.itemName() == "ExactlyOne" or \
            self.itemName() == "AtLeastOne"

    def appendTo(self):
        """
        Append item to the parameter grid layout.
        """
        super(ParameterRuleItem, self).appendTo()

        tbl = self.grid()
        added = self.isAppended()

        if self.isGrouped() and not added:
            items = []
            for pitem in self.childItems():
                if not pitem.isAppended():
                    items.append(pitem)

            if len(items) > 0:
                index = tbl.actualRowCount()
                if self._begitem is None:
                    self._begitem = QSpacerItem(0, self._groupOffset())
                tbl.addItem(self._begitem, index, self.ColumnId.Check, 1,
                            self.ColumnId.Default - self.ColumnId.Check + 1)

                for pitem in items:
                    pitem.appendTo()

                idx = tbl.actualRowCount()
                if self._enditem is None:
                    self._enditem = QSpacerItem(0, self._groupOffset())
                tbl.addItem(self._enditem, idx, self.ColumnId.Check, 1,
                            self.ColumnId.Default - self.ColumnId.Check + 1)

                self._installVisibilityWatcher()

                self._frame = QRect(self.ColumnId.Check, index + 1,
                                    self.ColumnId.Default - \
                                        self.ColumnId.Check + 1,
                                    idx - index - 1)
                # translate rule
                self._frame.title = translate_rule(self.itemName())
                if hasattr(self.rootItem(), "appendFrame"):
                    self.rootItem().appendFrame(self._frame) # pragma pylint: disable=no-member

                # Update offset vertical size because offset which dependant
                # from grid margins can be changed after first frame addition.
                self._begitem.changeSize(0, self._groupOffset())
                self._enditem.changeSize(0, self._groupOffset())


    def isAppended(self):
        """
        Item append to the parameter grid layout state.
        """
        return self._begitem is not None and self._enditem is not None \
            and self._indexOfSpacer(self._begitem) >= 0 \
            and self._indexOfSpacer(self._enditem) >= 0

    def removeFrom(self):
        """Remove item from the parameter grid layout."""
        tbl = self.grid()
        added = self.isAppended()

        if self.isGrouped() and added:
            if self._begitem is not None:
                tbl.removeItem(self._begitem)

            for pitem in self.childItems():
                pitem.removeFrom()

            if self._enditem is not None:
                tbl.removeItem(self._enditem)

            self._removeVisibilityWatcher()

            if hasattr(self.rootItem(), "removeFrame"):
                self.rootItem().removeFrame(self._frame) # pragma pylint: disable=no-member

        super(ParameterRuleItem, self).removeFrom()

    def stateChanged(self, item):
        """
        Update rule items state.
        Invoked when one of the child items in owner change state.

        Arguments:
            item (ParameterItem): Changed parameter item.
        """
        self.processRule(item, None)

    def processRule(self, item, check_dict):
        """
        Process rule items state dependant from state specified item.

        Arguments:
            item (ParameterItem): Changed parameter item.
        """
        if self.itemName() == "ExactlyOne":
            self._processExactlyOne(item, check_dict)
        if self.itemName() == "AtMostOne":
            self._processAtMostOne(item, check_dict)
#       Dynamic control disabled according to Bug #982
#       if self.itemName() == "AtLeastOne":
#           self._processAtLeastOne(item, check_dict)
        if self.itemName() == "AllTogether":
            self._processAllTogether(item, check_dict)
        if self.itemName() == "IfFirstAllPresent":
            self._processIfFirstAllPresent(item, check_dict)
        if self.itemName() == "OnlyFirstPresent":
            self._processOnlyFirstPresent(item, check_dict)

    def _processExactlyOne(self, item, check_dict):
        self._processAtLeastOne(item, check_dict)
        self._processAtMostOne(item, check_dict)

    def _processAtMostOne(self, item, check_dict):
        modified = []
        if item.isUsed():
            items = self.ruleItems()
            for i in items:
                if i != item:
                    prev = i.isUsed()
                    i.setIsUsed(False)
                    if prev != i.isUsed():
                        modified.append(i)
        self._processDependency(modified, check_dict)

    def _processAtLeastOne(self, item, check_dict):
        if not item.isUsed() and check_dict is None:
            exist = False
            for i in self.ruleItems():
                if i.isUsed():
                    exist = True
                    break
            if not exist:
                item.setIsUsed(True)

    def _processAllTogether(self, item, check_dict):
        modified = []
        items = self.ruleItems()
        for i in items:
            if i != item:
                prev = i.isUsed()
                i.setIsUsed(item.isUsed())
                if prev != i.isUsed():
                    modified.append(i)
        self._processDependency(modified, check_dict)


    def _processIfFirstAllPresent(self, item, check_dict):
        modified = []
        items = self.ruleItems()
        if item == items[0]:
            for i in items:
                if i != item:
                    allrules = i.attachedItemRules()
                    mandatory = False
                    for rule in allrules:
                        if self.itemName() == rule.itemName():
                            ritems = rule.ruleItems()
                            if ritems and len(ritems) > 0 and ritems[0] != i \
                                    and ritems[0].isUsed():
                                mandatory = True
                                break
                    prev = i.isUsed()
                    i.modifyFlags(self.ItemFlags.Mandatory, mandatory)
                    if prev != i.isUsed():
                        modified.append(i)
        self._processDependency(modified, check_dict)

    def _processOnlyFirstPresent(self, item, check_dict):
        modified = []
        items = self.ruleItems()
        if item == items[0]:
            for i in items:
                if i != item:
                    allrules = i.attachedItemRules()
                    disabled = False
                    for rule in allrules:
                        if self.itemName() == rule.itemName():
                            ritems = rule.ruleItems()
                            if ritems and len(ritems) > 0 and ritems[0] != i \
                                    and ritems[0].isUsed():
                                disabled = True
                                break
                    prev = i.isUsed()
                    i.modifyFlags(self.ItemFlags.Disabled, disabled)
                    if prev != i.isUsed():
                        modified.append(i)
        self._processDependency(modified, check_dict)

    def _processDependency(self, items, check_dict):
        check = check_dict if check_dict is not None else {}
        if self in check or len(items) == 0:
            return

        check[self] = 0
        for item in items:
            rules = item.attachedItemRules()
            for rule in rules:
                if rule not in check:
                    rule.processRule(item, check)
        check.pop(self)

    def _installVisibilityWatcher(self):
        """
        Install monitoring for item widgets in rule group
        """
        tbl = self.grid()
        beg = self._indexOfSpacer(self._begitem) \
            if self._begitem is not None else -1
        end = self._indexOfSpacer(self._enditem) \
            if self._begitem is not None else -1
        if beg >= 0 and end >= 0:
            if self._viswatcher is None:
                self._viswatcher = ParameterRuleItem.Watcher()
                self._viswatcher.visibilityChanged.\
                    connect(self._visibilityChanged)
            widgets = []
            for i in range(beg + 1, end):
                layitem = tbl.itemAt(i)
                if layitem is not None and layitem.widget() is not None:
                    widgets.append(layitem.widget())
            self._viswatcher.setContent(widgets)
            QTimer.singleShot(0, self._visibilityChanged)

    def _removeVisibilityWatcher(self):
        """
        Remove monitoring of item widgets in rule group
        """
        if self._viswatcher is not None:
            self._viswatcher.setContent([])

    def _visibilityChanged(self):
        """
        Invoked when visibility state of some widgets in rule group
        was changed.
        """
        if self.isAppended():
            tbl = self.grid()
            beg = self._indexOfSpacer(self._begitem) \
                if self._begitem is not None else -1
            end = self._indexOfSpacer(self._enditem) \
                if self._begitem is not None else -1

            vis = False
            for i in range(beg + 1, end):
                layitem = tbl.itemAt(i)
                laywidget = layitem.widget() if layitem is not None else None
                if laywidget is not None and \
                        laywidget.isVisibleTo(laywidget.parentWidget()):
                    vis = True
                    break

            offset = self._groupOffset()
            self._begitem.changeSize(0, offset if vis else 0)
            self._enditem.changeSize(0, offset if vis else 0)

    def _groupOffset(self):
        """
        Returns the offset between rule groups
        """
        return self.grid().contentsMargins().left() / 2

    def _indexOfSpacer(self, spacer):
        """
        Index of layout item in layout.
        """
        idx = -1
        tbl = self.grid()
        for i in xrange(tbl.count()):
            if tbl.itemAt(i) == spacer:
                idx = i
                break
        return idx

    def _removeExcluded(self, items):
        """
        Remove excluded items from given list.
        """
        filtered = []
        for i in items:
            if not i.testFlags(self.ItemFlags.Excluded):
                filtered.append(i)
        return filtered
