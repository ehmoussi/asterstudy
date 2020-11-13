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
File Descriptors Model
----------------------

Custom QAbstractItemModel for Unit management functionality.

"""

from __future__ import unicode_literals

import os

from PyQt5 import Qt as Q

from common import external_file, is_subpath, translate
from datamodel import FileAttr
from gui import NodeType, Role, get_icon
from gui.behavior import behavior
from gui.datasettings import get_object_name, get_object_info
from . objects import Directory, File

__all__ = ["create_model"]

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name
# pragma pylint: disable=redefined-variable-type


class FileData(object):
    """
    Enumerator for 'Data files' view's column.

    Attributes:
        file: Filename.
        unit: Unit.
        inout: 'In/out' attribute.
        exists: 'Exists' attribute.
        embedded: 'Embedded' attribute.
    """
    file = 0
    unit = 1
    inout = 2
    exists = 3
    embedded = 4

    @staticmethod
    def value2str(value):
        """
        Get title for given file attribute.

        Arguments:
            value (int): File attribute (*FileData*).

        Returns:
            str: File attribute's title.
        """
        text = '?'
        if value == FileData.file:
            text = translate("DataFiles", "Filename")
        elif value == FileData.unit:
            text = translate("DataFiles", "Unit")
        elif value == FileData.inout:
            text = translate("DataFiles", "Mode")
        elif value == FileData.exists:
            text = translate("DataFiles", "Exists")
        elif value == FileData.embedded:
            text = translate("DataFiles", "Embedded")
        return text


class TreeItem(object):
    """
    Basic class to represent file descriptors model's internal
    structure.
    """

    Type = NodeType.Unknown

    def __init__(self, data, parent=None):
        """
        Create item.

        Arguments:
            data (any): Item's internal data.
            parent (Optional[TreeItem]): Parent item. Defaults to
                *None*.
        """
        self._parent = parent
        self._data = data
        self._children = []
        if parent is not None:
            parent.appendChild(self)

    def itemData(self):
        """
        Get internal data associated with item.

        Returns:
            any: Item's internal data.
        """
        return self._data

    def appendChild(self, child):
        """
        Append given item to the list of children.

        Arguments:
            child (TreeItem): Child item.
        """
        if child not in self._children:
            child.setParent(self)
            self._children.append(child)

    def child(self, row):
        """
        Get child item by given index.

        Arguments:
            row (int): Child item's index.
        """
        return self._children[row] if (0 <= row < len(self._children)) \
            else None

    def indexOf(self, child):
        """
        Get index of child item.

        Arguments:
            child (TreeItem): Child item.

        Returns:
            int: Item's index; -1 if *child* is not in item's children
            list.
        """
        return self._children.index(child) if child in self._children else -1

    def childCount(self):
        """
        Get number of child items.

        Returns:
            int: Number of child items.
        """
        return len(self._children)

    def parent(self):
        """
        Get parent item.

        Returns:
            TreeItem: Parent item (*None* for top-level item).
        """
        return self._parent

    def setParent(self, parent):
        """
        Set parent item.

        Arguments:
            parent (TreeItem): Parent item.
        """
        self._parent = parent

    def root(self):
        """
        Get root item.

        Returns:
            TreeItem: Root item.
        """
        root = self
        while root.parent() is not None:
            root = root.parent()
        return root

    def row(self):
        """
        Get index of item in the parent's list of children.

        Returns:
            int: Item's row index.
        """
        return self.parent().indexOf(self) if self.parent() is not None else -1

    @property
    def uid(self): # pragma pylint: disable=no-self-use
        """
        Get UID of the item.

        Returns:
            int: Item's UID.
        """
        return -1

    @property
    def type(self):
        """
        Get item type.

        Returns:
            int: Item's type (*NodeType*).
        """
        return self.Type

    @property
    def visible(self): # pragma pylint: disable=no-self-use
        """
        Get visibility status.

        Returns:
            bool: *True* if item is visible; *False* otherwise.
        """
        return True

    @property
    def valid(self): # pragma pylint: disable=no-self-use
        """
        Get validity status.

        Returns:
            bool: *True* if item is valid; *False* otherwise.
        """
        return True

    def data(self, column, role):
        """
        Get item's model data.

        Arguments:
            column: Model's column.
            role: Data role.

        Returns:
            any: Item's data.
        """
        res = None
        if column >= 0:
            if role in (Role.TypeRole,):
                res = self.type
            elif role in (Role.IdRole,):
                res = self.uid
            elif role in (Role.ValidityRole,):
                res = self.valid
            elif role in (Role.VisibilityRole,):
                res = self.visible
            elif role in (Role.CustomRole,):
                res = self.itemData()
        return res


class ModelItem(TreeItem):
    """
    Represents root item in the model.

    Item's data stores a reference to the view model.
    """

    @property
    def model(self):
        """
        Get reference to the model.

        Returns:
            Model: View model.
        """
        return self.itemData()

    @property
    def case(self):
        """
        Get case being managed by the model.

        Returns:
            Case: Case object.
        """
        return self.itemData().case


class CaseItem(TreeItem):
    """
    Represents case item in the model.

    Item's data stores a case being managed.
    """

    Type = NodeType.Case

    @property
    def case(self):
        """
        Get case.

        Returns:
            Case: Case object.
        """
        return self.itemData()

    @property
    def uid(self):
        """Redefined from TreeItem."""
        return self.case.uid

    def data(self, column, role):
        """Redefined from TreeItem."""
        res = super(CaseItem, self).data(column, role)
        if role in (Q.Qt.UserRole,):
            res = self.case
        elif role in (Role.SortRole,) and Model.sort_stages():
            res = 0
        elif column == FileData.file:
            if role in (Q.Qt.DisplayRole,):
                res = self.case.name
            elif role in (Q.Qt.ToolTipRole,):
                res = get_object_info(self.case)
            elif role in (Q.Qt.DecorationRole,):
                return get_icon(self.case)
        return res


class DirItem(TreeItem):
    """
    Represents input and output directory items.

    Item's data stores *Directory* object.
    """

    Type = NodeType.Dir

    @property
    def dirType(self):
        """
        Get directory type.

        Returns:
            int: 0 for input directory; 1 for output directory.
        """
        return self.itemData().dir_type

    @property
    def case(self):
        """
        Get case.

        Returns:
            Case: Case object.
        """
        return self.itemData().case

    @property
    def dir(self):
        """
        Get directory path.

        Returns:
            str: Directory path.
        """
        return self.itemData().directory

    @property
    def title(self):
        """
        Get directory title.

        Returns:
            str: Directory title.
        """
        val = '?'
        if self.dirType == Directory.InDir:
            val = translate("DataFiles", "Input directory")
        elif self.dirType == Directory.OutDir:
            val = translate("DataFiles", "Output directory")
        return val

    @property
    def uid(self):
        """Redefined from TreeItem."""
        return self.dirType

    @property
    def visible(self):
        """Redefined from TreeItem."""
        return self.dir is not None

    @property
    def valid(self):
        """Redefined from TreeItem."""
        return self.dirType == Directory.OutDir or \
            self.dirType == Directory.InDir and self.dir is not None and \
            os.path.exists(self.dir)

    def data(self, column, role):
        """Redefined from TreeItem."""
        res = super(DirItem, self).data(column, role)
        if role in (Q.Qt.UserRole,):
            res = self.dir
        elif role in (Role.SortRole,) and Model.sort_stages():
            res = self.dirType
        elif column == FileData.file:
            if role in (Q.Qt.DisplayRole,):
                res = self.title
            elif role in (Q.Qt.ToolTipRole,):
                res = self.title + ": {}".format(self.dir)
            elif role in (Q.Qt.DecorationRole,):
                return get_icon("Dir")
        return res


class StageItem(TreeItem):
    """
    Represents stage item in the model.

    Item's data stores a stage being managed.
    """

    Type = NodeType.Stage

    @property
    def stage(self):
        """
        Get stage.

        Returns:
            Stage: Stage object.
        """
        return self.itemData()

    @property
    def uid(self):
        """Redefined from TreeItem."""
        return self.stage.uid

    def data(self, column, role):
        """Redefined from TreeItem."""
        res = super(StageItem, self).data(column, role)
        if role in (Q.Qt.UserRole,):
            res = self.stage
        elif column == FileData.file:
            if role in (Q.Qt.DisplayRole,):
                res = self.stage.name
            elif role in (Q.Qt.ToolTipRole,):
                res = get_object_info(self.stage)
            elif role in (Role.SortRole,) and Model.sort_stages():
                res = self.stage.number
            elif role in (Q.Qt.DecorationRole,):
                return get_icon(self.stage)
        elif column == FileData.unit:
            if role in (Role.SortRole,) and Model.sort_stages():
                res = self.stage.number
        return res


class HandleItem(TreeItem):
    """
    Represents file descriptor item in the model.

    Item's data stores *FileData* object.
    """

    Type = NodeType.Unit

    @property
    def stage(self):
        """
        Get parent stage.

        Returns:
            Stage: Stage owning the file descriptor.
        """
        return self.itemData().stage

    @property
    def unit(self):
        """
        Get file descriptor's unit value.

        Returns:
            int: File descriptor's unit.
        """
        return self.itemData().unit

    @property
    def filename(self):
        """
        Get filename of the desriptor.

        Returns:
            str: Filename.
        """
        return self.itemData().filename

    @property
    def attr(self):
        """
        Get descriptor's in/out attribute.

        Returns:
            int: Descriptors cumulative in/out attribute.
        """
        return self.itemData().attr

    @property
    def is_forced_attr(self):
        """Check if 'attr' is forced (by input/output directory)."""
        return self.itemData().is_forced_attr

    @property
    def exists(self):
        """
        Get descriptor's 'exists' attribute.

        Returns:
            bool: *True* if file exists; *False* otherwise.
        """
        return self.itemData().exists

    @property
    def embedded(self):
        """
        Get descriptor's 'embedded' attribute.

        Returns:
            bool: *True* if file is embedded; *False* otherwise.
        """
        return self.itemData().embedded

    @property
    def is_reference(self):
        """
        Get descriptor's 'isreference' attribute.

        Returns:
            bool: *True* if file is a reference to SALOME study object;
            *False* otherwise.
        """
        return self.itemData().is_reference

    @property
    def uid(self):
        """Redefined from TreeItem."""
        return self.itemData().uid

    @property
    def visible(self):
        """Redefined from TreeItem."""
        root = self.root()
        hidden = False
        if root is not None:
            case = root.case # pragma pylint: disable=no-member
            in_dir = case.in_dir
            out_dir = case.out_dir
            hidden = isinstance(self.parent(), StageItem) and \
                is_subpath(self.filename, (in_dir, out_dir))
        return not hidden

    @property
    def valid(self):
        """Redefined from TreeItem."""
        return self.itemData().valid

    # pragma pylint: disable=too-many-branches
    def data(self, column, role):
        """Redefined from TreeItem."""
        # pragma pylint: disable=redefined-variable-type
        res = super(HandleItem, self).data(column, role)
        if role in (Role.ReferenceRole,):
            res = self.is_reference
        elif role in (Q.Qt.BackgroundRole,):
            if self.itemData().is_repeated:
                return Q.QBrush(Q.QColor(Q.Qt.yellow))
            else:
                return Q.QBrush(Q.QColor(Q.Qt.white))
        elif column == FileData.file:
            if role in (Q.Qt.DisplayRole, Q.Qt.ToolTipRole, Role.SortRole):
                res = self._text(role != Q.Qt.ToolTipRole)
            elif role in (Q.Qt.UserRole,):
                return self.filename
            elif role in (Q.Qt.DecorationRole,):
                return get_icon("Unit")
        elif column == FileData.unit:
            if role in (Q.Qt.DisplayRole, Q.Qt.ToolTipRole,):
                res = '?' if self.unit is None else self.unit
            elif role in (Q.Qt.UserRole, Role.SortRole):
                res = self.unit
        elif column == FileData.inout:
            if role in (Q.Qt.DisplayRole, Q.Qt.ToolTipRole, Role.SortRole):
                res = FileAttr.value2str(self.attr)
            elif role in (Q.Qt.UserRole,):
                res = self.attr
            elif role in (Q.Qt.FontRole,):
                res = Q.QFont()
                res.setBold(self.is_forced_attr)
        elif column == FileData.exists:
            if role in (Q.Qt.DisplayRole, Q.Qt.ToolTipRole, Role.SortRole):
                res = bool2str(self.exists)
            elif role in (Q.Qt.UserRole,):
                res = self.exists
        elif column == FileData.embedded:
            if role in (Q.Qt.DisplayRole, Q.Qt.ToolTipRole, Role.SortRole):
                res = bool2str(self.embedded)
            elif role in (Q.Qt.UserRole,):
                res = self.embedded
            elif role in (Q.Qt.FontRole,):
                res = Q.QFont()
                res.setBold(self.is_forced_attr)
        return res

    def _text(self, short=False):
        """
        Get internal representation of the item's filename.

        Arguments:
            short (Optional[bool]): Says long or short reprsentation to
                get.

        Returns:
            str: String representation of filename.
        """
        prefix = NodeType.value2str(NodeType.Unit) + ": " if not short else ''
        if self.filename:
            if self.is_reference:
                res = external_file(self.filename)
                if res is None:
                    res = "<{}>".format(translate("DataFiles", "undefined"))
                res = res if short else res + " ({})".format(self.filename)
            else:
                res = os.path.basename(self.filename) if short \
                    else self.filename
        else:
            res = "<{}>".format(translate("DataFiles", "undefined"))
        if self.embedded and not self.is_reference:
            res += ' ({})'.format(translate("DataFiles", "embedded"))
        return prefix + res


class CommandItem(TreeItem):
    """
    Represents command item in the model.

    Item's data stores *Command* object.
    """

    Type = NodeType.Command

    @property
    def stage(self):
        """
        Get stage owning the command.

        Returns:
            Stage: Stage owning the command.
        """
        return self.command.stage

    @property
    def command(self):
        """
        Get command referenced by item.

        Returns:
            Command: Command object.
        """
        return self.itemData()

    @property
    def uid(self):
        """Redefined from TreeItem."""
        return self.command.uid

    def data(self, column, role):
        """Redefined from TreeItem."""
        # pragma pylint: disable=redefined-variable-type
        res = super(CommandItem, self).data(column, role)
        if role in (Q.Qt.UserRole,):
            res = self.command
        elif column == FileData.file:
            if role in (Q.Qt.DisplayRole, Role.SortRole):
                res = get_object_name(self.command)
            elif role in (Q.Qt.ToolTipRole,):
                res = get_object_info(self.command, with_parent_stage=True)
            elif role in (Q.Qt.DecorationRole,):
                res = get_icon(self.command)
        elif column == FileData.unit:
            if role in (Role.SortRole,):
                res = self.command.uid
        return res


class Model(Q.QAbstractItemModel):
    """File Descriptors model."""

    FORCE_RESORT = False

    def __init__(self, case_proxy):
        """
        Create model.

        Arguments:
            case_proxy (CaseProxy): Case proxy object.
            args
        """
        super(Model, self).__init__()
        self._case_proxy = case_proxy
        self._setup(self._case_proxy())

    def _setup(self, case):
        """Build initial tree of items."""
        self.rootItem = ModelItem(self)

        # top-level 'Case' item
        case_item = CaseItem(case)
        self.rootItem.appendChild(case_item)

        # 'InDir' and 'OutDir' items - children of 'Case' item
        indir_item = DirItem(Directory(case, Directory.InDir))
        case_item.appendChild(indir_item)
        outdir_item = DirItem(Directory(case, Directory.OutDir))
        case_item.appendChild(outdir_item)

        # top-level 'Stage' items
        for stage in case:
            stage_item = StageItem(stage, self.rootItem)

            for handle in stage.handle2info:
                file_item, ref_item = _add_file_item(stage, handle, stage_item,
                                                     indir_item, outdir_item)
                if behavior().show_related_concepts:
                    for command in stage.handle2info[handle].commands:
                        file_item.appendChild(CommandItem(command))
                        if ref_item is not None:
                            ref_item.appendChild(CommandItem(command))

    @property
    def case(self):
        """Get case being managed by the model."""
        return self._case_proxy()

    def object(self, entity):
        """
        Get Data object identified by given *entity*.

        Arguments:
            entity (Entity): Selection entity.

        Return:
            any: Data model object.
        """
        index = self._findIndex(entity.uid, entity.type)
        return index.data(Role.CustomRole) if index.isValid() is not None \
            else None

    def update(self):
        """Inform model that it should be reset."""
        self.beginResetModel()
        self._setup(self._case_proxy())
        self.endResetModel()

    @staticmethod
    def sort_stages():
        """
        Get 'sort stages' option.

        Returns:
            bool: *True* if stages should be sorted.
        """
        return Model.FORCE_RESORT or behavior().sort_stages

    def rowCount(self, parent):
        """
        Gets the number of rows.

        Arguments:
            parent (Optional[QModelIndex]): Parent index. Defaults to
                *None*.

        Returns:
            int: Rows count.
        """
        if parent.isValid():
            item = parent.internalPointer()
        else:
            item = self.rootItem
        return item.childCount()

    def columnCount(self, parent): # pragma pylint: disable=unused-argument, no-self-use
        """
        Gets the number of columns.

        Arguments:
            parent (QModelIndex): Parent index.

        Returns:
            int: Number of columns.
        """
        return 5

    def index(self, row, column, parent):
        """
        Gets the index of the item in the given row and column.

        Arguments:
            row (int): Row id.
            column (int): Column id.
            parent (Optional[QModelIndex]): Parent index. Defaults to
                *None*.

        Returns:
            QModelIndex: Index of (row, column) item.
        """
        if not self.hasIndex(row, column, parent):
            return Q.QModelIndex()

        if parent.isValid():
            item = parent.internalPointer()
        else:
            item = self.rootItem

        child_item = item.child(row)
        return self.createIndex(row, column, child_item)

    def parent(self, index):
        """
        Gets parent index by the given index of child.

        Arguments:
            index (QModelIndex): Model index.

        Returns:
            QModelIndex: Parent model index.
        """
        child_item = index.internalPointer()
        parent_item = child_item.parent()

        if parent_item == self.rootItem:
            return Q.QModelIndex()

        return self.createIndex(parent_item.row(), 0, parent_item)

    def data(self, index, role=Q.Qt.DisplayRole): # pragma pylint: disable=no-self-use
        """
        Gets the data stored under the given role for the item
        referred to by the index.

        Arguments:
            index (QModelIndex): Index of the data.
            role (Optional[int]): Data role. Defaults to
                *Qt.DisplayRole*.

        Returns:
            QVariant: Data of item by the given index
        """
        item = index.internalPointer()
        return item.data(index.column(), role) if item is not None else None


    def headerData(self, section, orientation, role=Q.Qt.DisplayRole):
        """
        Gets the header data.

        Arguments:
            section (int): Header's section index.
            orientation (Qt.Orientation): Headers's orientation.
            role (Optional[int]): Data role. Defaults to
                *Qt.DisplayRole*.

        Returns:
            QVariant: Header data.
        """
        if orientation == Q.Qt.Horizontal and role in (Q.Qt.DisplayRole,):
            return FileData.value2str(section)
        return super(Model, self).headerData(section, orientation, role)

    def _findIndex(self, uid, typeid, parent_index=Q.QModelIndex()):
        """Find an index for given *uid* and *typeid*."""
        for row in range(self.rowCount(parent_index)):
            index = self.index(row, 0, parent_index)
            if index.data(Role.IdRole) == uid and \
                    index.data(Role.TypeRole) == typeid:
                return index
            elif self.hasChildren(index):
                index = self._findIndex(uid, typeid, index)
                if index.isValid():
                    return index
        return Q.QModelIndex()


class ProxyModel(Q.QSortFilterProxyModel):
    """
    Proxy model for Model class.
    Supports sorting / filtering of items.
    """

    def __init__(self, parent=None):
        """
        Create model.

        Arguments:
            parent (Optional[QObject]): Parent object. Defaults to
                *None*.
        """
        super(ProxyModel, self).__init__(parent)
        self.setSortRole(Role.SortRole)

    def filterAcceptsRow(self, source_row, source_parent):
        """Redefined from QSortFilterProxyModel."""
        index = self.sourceModel().index(source_row, 0, source_parent)
        return index.data(Role.VisibilityRole)

    def update(self):
        """Update model."""
        self.sourceModel().update()

    def object(self, entity):
        """See `Model.object()`."""
        return self.sourceModel().object(entity)


def bool2str(value):
    """
    Convert boolean value to string representation.

    Returns:
        str: 'Yes' for *True*; 'No' for *False* and empty string for
        *None*.
    """
    if value is None:
        return ''
    return translate("DataFiles", "Yes") if value \
        else translate("DataFiles", "No")


def create_model(case_proxy):
    """
    Create files descriptors model.

    Arguments:
        case_proxy (CaseProxy): Case proxy object.

    Returns:
        Model: New file descriptors model.
    """
    model = Model(case_proxy)
    proxy_model = ProxyModel()
    proxy_model.setSourceModel(model)
    return proxy_model


class force_resort(object):
    """Context manager for *Data Files* view correct resorting."""

    def __enter__(self):
        Model.FORCE_RESORT = True

    def __exit__(self, exc_type, exc_value, traceback):
        Model.FORCE_RESORT = False


def _add_file_item(stage, unit, stage_item, indir_item, outdir_item):
    """Add file item to the view model."""

    filename = stage.handle2file(unit)

    file_item = HandleItem(File(stage, unit))
    stage_item.appendChild(file_item)

    ref_item = None
    for dir_item in indir_item, outdir_item:
        directory = dir_item.dir
        if is_subpath(filename, directory):
            if behavior().join_similar_files:
                for i in range(dir_item.childCount()):
                    item = dir_item.child(i)
                    if item.filename == filename and item.unit == unit:
                        ref_item = item
                        break
            if ref_item is not None:
                ref_item.itemData().add_entry(stage, unit)
            else:
                file_unit = File(stage, unit)
                file_unit.forced_attr = FileAttr.In \
                    if dir_item is indir_item else FileAttr.Out
                ref_item = HandleItem(file_unit)
                dir_item.appendChild(ref_item)
            break

    return file_item, ref_item
