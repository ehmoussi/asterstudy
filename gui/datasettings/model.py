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
Category model
--------------

Implementation of the category model for *Data Settings* view.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

from common import bold, font, italic, preformat, translate, to_list
from datamodel import (CATA, History, Validity, synchronize,
                       ConversionLevel)
from gui import (HistoryProxy, NodeType, Role,
                 get_node_type, get_icon, root_node_type,
                 translate_category, translate_command)
from gui.behavior import behavior
from . category import Category

def get_id(tree_item):
    """
    Get id from the tree widget item.

    Arguments:
        tree_item (QTreeWidgetItem): Tree widget item.

    Returns:
        int: Item's identifier (UID).
    """
    return tree_item.data(0, Role.IdRole)


def get_type(tree_item):
    """
    Get the node type from the tree widget item.

    Arguments:
        tree_item (QTreeWidgetItem): Tree widget item.

    Returns:
        int: Item's type name (*NodeType*).
    """
    return tree_item.data(0, Role.TypeRole)


def update_validity_role(obj, tree_item):
    """
    Update validity role of the tree widget item.

    Arguments:
        obj (Command, Category, Stage or Case): Source data object.
        tree_item (QTreeWidgetItem): Tree widget item.
    """
    validity = obj.check() == Validity.Nothing
    tree_item.setData(0, Role.ValidityRole, validity)


def get_object_name(obj):
    """
    Get object name to be displayed in data view.

    Arguments:
        obj (Node): Data model node.

    Returns:
        str: Object's name.
    """
    node_type = get_node_type(obj)
    if node_type == NodeType.History:
        return translate("AsterStudy", "History")
    elif node_type == NodeType.Command:
        if obj.gettype(ConversionLevel.NoFail) is not None:
            return obj.name
        if behavior().show_catalogue_name:
            return translate("AsterStudy", "[noname]")
        else:
            return translate_command(obj.title)
    elif node_type == NodeType.Comment:
        return obj.content.split("\n")[0]

    return obj.name


def get_object_type(obj):
    """
    Get object catalogue name to be displayed in data view.

    Arguments:
        obj (Node): Data model node.

    Returns:
        str: Object's catalogue name.
    """
    name = ""
    node_type = get_node_type(obj)
    if node_type == NodeType.Command:
        name = translate_command(obj.title)
    return name


def get_object_info(obj, **kwargs):
    """
    Get object info to be displayed in tooltip.

    Arguments:
        obj (Node): Data model node.
        **kwargs: Arbitrary keyword arguments:

    Returns:
        str: Object's info.
    """
    node_type = get_node_type(obj)
    info = NodeType.value2str(node_type)
    if node_type == NodeType.Command:
        info += ": "
        if obj.type is None:
            name = translate("AsterStudy", "[noname]")
        else:
            name = obj.name
        info += bold(name)
        cata = obj.title
        title = translate_command(cata)
        tip = " ({title} / {name})" if title != cata else " ({name})"
        info += tip.format(title=italic(title), name=cata)
        if kwargs.get('with_parent_stage', False):
            info += "<br>"
            st_name = bold(obj.stage.name)
            info += translate("AsterStudy", "From stage: {}").format(st_name)
    elif node_type == NodeType.Comment:
        info += ":<br>"
        content = obj.content.split("\n")
        content = ["  # " + i for i in content]
        info += italic("\n".join(content))
    elif node_type == NodeType.Variable:
        info += ": "
        info += bold(obj.name)
        info += " ({})".format(italic(obj.expression))
    elif node_type == NodeType.Case:
        info += ": "
        info += bold(obj.name)
        if obj.description:
            info += "\n\n"
            info += obj.description
    elif node_type != NodeType.History:
        info += ": "
        info += bold(obj.name)
    if node_type in [NodeType.Case, NodeType.Stage, NodeType.Category,
                     NodeType.Command]:
        validity = Validity.value2str(obj.check())
        if validity:
            info += "<br>"
            info += font("Invalid:", color="#ff0000")
            info += ", ".join([bold(i.strip()) for i in validity.split(",")])
    info = preformat(info)
    return info


def update_font(tree_item, is_italic):
    """
    Update font of tree widget item.

    Italicizes the font if *is_italic* is *True* or makes it normal
    otherwise.

    Arguments:
        tree_item (QTreeWidgetItem): Tree widget item.
        is_italic (bool): *True* if the font should be italic; *False*
            for normal font.
    """
    item_font = tree_item.font(0)
    if item_font.italic() != is_italic:
        item_font.setItalic(is_italic)
        tree_item.setFont(0, item_font)


def match_string(text, pattern, case_sensitive=False):
    """
    Check if string matches given pattern.
    Used within search functionality of 'Data Settings' panel.

    Arguments:
        text (str): String to check.
        pattern (str): Match pattern.
        case_sensitive (Optional[bool]): Make case sensitive search.
            Defaults to *False*.

    Returns:
        bool: *True* if string matches pattern; *False* otherwise.
    """
    if case_sensitive:
        return pattern in text
    else:
        return pattern.lower() in text.lower()


class CategoryTreeData(object):
    """
    Tree data for category model synchronization.

    The class is used to synchronize data model (*History*) with the GUI
    widget (*QTreeWidget*).

    Methods related to synchronization purposes take one or two
    arguments:

    - *obj*: Source item which is either an actual data mode object
      (*Node*) or an instance of helper class (*Model*, *Category*);
    - *tree_item*: Destination item which is a tree widget item
      (*QTreeWidgetItem*).
    """

    def __init__(self, category_model):
        """
        Create object.

        Arguments:
            category_model (Model): Category model.
        """
        self.category_model = category_model
        self._selected_ids = []

    def init_selection(self, tree_item):
        """
        Store current selection in tree widget.

        Arguments:
            tree_item (QTreeWidgetItem): Tree widget item.
        """
        if tree_item is not None:
            if tree_item.isSelected():
                self._selected_ids.append(get_id(tree_item))
            for i in xrange(0, tree_item.childCount()):
                self.init_selection(tree_item.child(i))

    def is_equal(self, obj, tree_item): # pragma pylint: disable=no-self-use
        """
        Check if two items are equivalent.

        Note:
            See class description for more details about argument types.

        Arguments:
            obj (object): Source data object.
            tree_item (TreeWidgetItem): Tree widget item.

        Returns:
            bool: *True* if items correspond to each other; *False*
            otherwise.
        """
        if tree_item is None:
            return obj is None
        elif isinstance(obj, History):
            return tree_item.text(0) == "History"
        else:
            return get_id(tree_item) == obj.uid

    def update_item(self, obj, tree_item): # pragma pylint: disable=no-self-use
        """
        Update destination item from source data item.

        Note:
            See class description for more details about argument types.

        Arguments:
            obj (object): Source data object.
            tree_item (QTreeWidgetItem): Tree widget item.
        """
        node_type = get_node_type(obj)
        if node_type in (NodeType.Command, NodeType.Category,
                         NodeType.Stage, NodeType.Case, NodeType.Variable):
            update_validity_role(obj, tree_item)
            if node_type == NodeType.Command:
                update_font(tree_item, obj.type is None)
        # !!! Validity update must be before data set
        tree_item.setText(0, get_object_name(obj))
        tree_item.setText(1, get_object_type(obj))
        tree_item.setData(0, Q.Qt.ToolTipRole, get_object_info(obj))
        tree_item.setData(0, Role.ExpandedRole, tree_item.isExpanded())
        icon = get_icon(obj)
        if icon is not None:
            tree_item.setIcon(0, icon)

    def get_src_children(self, obj):
        """
        Get children items for a source item.

        Note:
            See class description for more details about argument and
            return type.

        Arguments:
            obj (object): Source data object.

        Returns:
            list[object]: Child items.
        """
        children = []
        node_type = get_node_type(obj)
        if isinstance(obj, Model):
            children = [obj.root]
        elif node_type == NodeType.History:
            children = [self.category_model.case]
        elif node_type == NodeType.Case:
            children = obj.child_nodes
        elif node_type == NodeType.Stage:
            children = self.category_model.get_stage_children(obj)
        elif node_type & NodeType.NoChildrenItems:
            children = [] # it is confirmed that command has no
            # children in the categories representation
        else:
            children = obj.child_nodes
        return children

    def get_dst_children(self, tree_item): # pragma pylint: disable=no-self-use
        """
        Get children items for a destination item.

        Note:
            See class description for more details about argument and
            return type.

        Arguments:
            tree_item (TreeWidgetItem): Tree widget item.

        Returns:
            list[TreeWidgetItem]: Child items.
        """
        children = []
        for i in xrange(0, tree_item.childCount()):
            children.append(tree_item.child(i))
        return children

    def create_item(self, obj):
        """
        Create a destination item for given source item.

        Note:
            See class description for more details about argument and
            return type.

        Arguments:
            obj (object): Source data object.

        Returns:
            TreeWidgetItem: Tree widget item.
        """
        is_current_case = self.category_model.case == \
            self.category_model.history.current_case
        node_type = get_node_type(obj)

        tree_item = Q.QTreeWidgetItem()

        # first column: name, icon
        tree_item.setText(0, get_object_name(obj))
        icon = get_icon(obj)
        if icon is not None:
            tree_item.setIcon(0, icon)
        tree_item.setData(0, Q.Qt.ToolTipRole, get_object_info(obj))
        tree_item.setData(0, Role.TypeRole, node_type)
        if isinstance(obj, History):
            node_id = root_node_type()
        else:
            node_id = obj.uid
        tree_item.setData(0, Role.IdRole, node_id)

        # second column: catalogue name (Command only)
        tree_item.setText(1, get_object_type(obj))

        # third column (debug mode only): object id
        tree_item.setText(2, str(node_id))

        # item flags
        if node_type & NodeType.ValidityItems:
            update_validity_role(obj, tree_item)
            if node_type == NodeType.Stage:
                flags = tree_item.flags()
                if is_current_case:
                    flags = flags | Q.Qt.ItemIsEditable
                tree_item.setFlags(flags)
            elif node_type in (NodeType.Command, NodeType.Variable):
                update_font(tree_item, obj.type is None)
                flags = tree_item.flags()
                if obj.type is not None and is_current_case:
                    flags = flags | Q.Qt.ItemIsEditable
                tree_item.setFlags(flags)
        self.category_model.register_item(tree_item)
        return tree_item

    def replace_dst_children(self, tree_item, children):
        """
        Replace children in the destination item.

        Note:
            See class description for more details about argument types.

        Arguments:
            tree_item (TreeWidgetItem): Tree widget item.
            children (list[TreeWidgetItem]): Child items.
        """
        for _ in xrange(0, tree_item.childCount()):
            child_item = tree_item.takeChild(0)
            if child_item not in children:
                self.category_model.unregister_item(child_item)
        for child in children:
            tree_item.addChild(child)

    def update_expanded_status(self, tree_item):
        """
        Update `expanded` status of given tree item and its children
        recursively.

        Arguments:
            tree_item (TreeWidgetItem): Tree widget item.
        """
        is_expanded = tree_item.data(0, Role.ExpandedRole)
        if is_expanded is not None:
            tree_item.setExpanded(is_expanded)
        for i in xrange(0, tree_item.childCount()):
            self.update_expanded_status(tree_item.child(i))

    def update_selection(self, tree_item):
        """
        Update selection under tree widget item.

        Arguments:
            tree_item (TreeWidgetItem): Tree widget item.
        """
        if tree_item is not None:
            if get_id(tree_item) in self._selected_ids:
                tree_item.setSelected(True)
        for i in xrange(0, tree_item.childCount()):
            self.update_selection(tree_item.child(i))


class Model(object):
    """Category model."""

    class Context(object):
        """Enumerator for search context."""
        Name = 'Name'
        Concept = 'Concept'
        Keyword = 'Keyword'
        Group = 'Group'

    def __init__(self, history_proxy):
        """
        Create model.

        Arguments:
            history_proxy (HistoryProxy): History proxy object.

        Raises:
            RuntimeError: If `history_proxy` is not of *HistoryProxy*
                class or if proxy refers to the invalid root.
        """
        if not isinstance(history_proxy, HistoryProxy):
            raise RuntimeError("Category model should be created only "
                               "on the HistoryProxy object")
        elif history_proxy.root is None:
            raise RuntimeError\
                ("Null root node not allowed for Category model construction")
        self._name = ''
        self._categories = []
        self._stage_children = {}
        self._history_proxy = history_proxy
        self._id_tree_item = {}

    @property
    def history(self):
        """
        Get study history.

        Returns:
            History: Associated *History* object.
        """
        node = self._history_proxy.root
        return node if isinstance(node, History) else node.model

    @property
    def root(self):
        """
        Get the root node of the tree to be created.

        Returns:
            Node: Root node of the tree to be created.
        """
        return self._history_proxy.root

    @property
    def case(self):
        """
        Get case to be displayed.

        Returns:
            Case: Case to be displayed.
        """
        return self._history_proxy.case

    @property
    def uid(self):
        """int: Attribute that holds identifier (UID) of the model."""
        return root_node_type()

    @property
    def name(self):
        """str: Attribute that holds name of the model."""
        return self._name

    def category(self, uid):
        """
        Get category with given *uid*.

        Arguments:
            uid (int): Category UID.

        Returns:
            Category: Category node (*None* if *uid* is invalid).
        """
        category = None
        if uid < 0 and -uid <= len(self._categories):
            category = self._categories[-uid - 1]
        return category

    def get_stage_children(self, stage):
        """
        Get children of the stage.

        Arguments:
            stage (Stage): Stage object.

        Returns:
            list[Category]: Child categories of the stage.
        """
        return self._stage_children.get(stage, [])

    def register_item(self, tree_item):
        """
        Register newly created item in the category model.

        Arguments:
            tree_item (QTreeWidgetItem): tree widget item.
        """
        item_id = get_id(tree_item)
        if item_id is not None:
            self._id_tree_item[item_id] = tree_item

    def unregister_item(self, tree_item):
        """
        Unregister removed item in the category model.

        Arguments:
            tree_item (QTreeWidgetItem): tree widget item.
        """
        node_id = get_id(tree_item)
        if node_id in self._id_tree_item.keys():
            # unregister children
            for i in xrange(0, tree_item.childCount()):
                self.unregister_item(tree_item.child(i))
            del self._id_tree_item[node_id]

    def find_items(self, pattern, context):
        """
        Gets the list of items according to given crteria.

        Arguments:
            pattern (str): Search pattern string
            context (str): Search context string

        Returns:
            [QTreeWidgetItem]: List of found items
        """
        res = []
        for i in self._id_tree_item:
            item = self._id_tree_item[i]
            if self._is_matched(item, pattern, context):
                res.append(item)
        return res

    def get_item_by_id(self, node_id):
        """
        Get the registered tree widget item by its UID.

        Arguments:
            node_id (int): node UID.

        Returns:
            QTreeWidgetItem: Tree widget item.
        """
        result = None
        if node_id in self._id_tree_item.keys():
            result = self._id_tree_item[node_id]
        return result

    def update(self):
        """Update model."""
        stages = []
        if self.case is None:
            if get_node_type(self.root) == NodeType.Stage:
                stages.append(self.root)
        else:
            self._stage_children = {}
            self._categories = []
            stages = self.case.stages
        for stage in stages:
            if stage.is_graphical_mode():
                # not be necessary if command.check was called before update
                stage.reorder()
                commands = stage.sorted_commands
                categories = []
                withnext = []
                for command in commands:
                    if command.title == "_CONVERT_COMMENT":
                        if behavior().show_comments:
                            withnext.append(command)
                        continue
                    category = CATA.get_command_category(command.title)
                    category = translate_category(category)
                    if not categories or categories[-1].name != category:
                        uid = len(self._categories) + 1
                        new_category = Category(-uid, category, stage.uid,
                                                self._history_proxy)
                        self._categories.append(new_category)
                        categories.append(new_category)
                    for i in withnext:
                        categories[-1].add_child(i)
                    categories[-1].add_child(command)
                    withnext = []
                # purge the buffer
                if categories: # only comments => ignored!
                    for i in withnext:
                        categories[-1].add_child(i)
                self._stage_children[stage] = categories
            else:
                self._stage_children[stage] = []

    def synchronize(self, root_tree_item=None):
        """
        Synchronize model with tree widget.

        Arguments:
            root_tree_item (Optional[QTreeWidgetItem]): Tree widget.
                 item. Defaults to *None* that means root item.

        Returns:
            QTreeWidgetItem: Updated tree widget item.
        """
        category_tree_data = CategoryTreeData(self)
        category_tree_data.init_selection(root_tree_item)
        if root_tree_item is None:
            self._id_tree_item = {}
        new_root = synchronize(self, root_tree_item, category_tree_data)
        category_tree_data.update_expanded_status(new_root)
        category_tree_data.update_selection(new_root)
        return new_root

    def update_all(self, root_tree_item=None):
        """
        Update and synchronize the model with tree widget.

        Arguments:
            root_tree_item (Optional[QTreeWidgetItem]): Tree widget.
                item. Defaults to *None* that means root item.

        Returns:
            QTreeWidgetItem: Updated tree widget item.
        """
        self.update()
        return self.synchronize(root_tree_item)

    def get_node(self, tree_item, node_type=None):
        """
        Find appopriate node from tree item.

        Arguments:
            tree_item (QTreeWidgetItem): Tree widget item.
            node_type (Optional[str, Node, Category]): Requested node
                type or typename.

        Returns:
            Node: Data model node (*None* if not found).
        """
        node = None
        type_id = get_type(tree_item)
        needed_type_id = get_node_type(node_type) if node_type else type_id
        if type_id > needed_type_id:
            # search among parents
            node = self.get_node(tree_item.parent(), node_type)
        elif type_id == needed_type_id:
            node_id = get_id(tree_item)
            if type_id == NodeType.History:
                node = self.history
            elif type_id == NodeType.Category:
                node = self._categories[node_id]
            elif node_id:
                node = self.history.get_node(node_id)
        return node

    def _is_matched(self, item, pattern, context):
        """
        Check if the specified item matched given criteries

        Arguments:
            item (QTreeWidgetItem): Checked item
            pattern (str): Search pattern string
            context (str): Search context string

        Returns:
            bool: Check state. 'True' if the item is matched otherwise 'False'
        """
        res = False

        if item is not None and context is not None and len(context):
            res = len(pattern) == 0
            if not res:
                uid = get_id(item)
                typ = get_type(item)
                obj = self.category(uid) if uid < 0 else \
                    self.history.get_node(uid)

                if context == Model.Context.Name:
                    res = typ in (NodeType.Command, NodeType.Variable) and \
                        (match_string(obj.title, pattern) or \
                             match_string(translate_command(obj.title),
                                          pattern))
                elif context == Model.Context.Concept:
                    res = typ in (NodeType.Command, NodeType.Variable) and \
                        match_string(obj.name, pattern)
                elif context == Model.Context.Keyword:
                    res = typ == NodeType.Command and \
                        self._is_exist_keyword(obj.title, obj.storage, pattern)
                elif context == Model.Context.Group:
                    res = typ == NodeType.Command and \
                        self._is_exist_keyword(obj.title, obj.storage,
                                               'GROUP', pattern)
        return res

    def _is_exist_keyword(self, command, storage, keyword, value=None):
        """
        Checks existance the parameters in storage. Parameter should
        has keyword which starts with specified 'keyword' and
        has value which starts with specified 'value' if it's not None

        Arguments:
            storage (dict): Command storage.
            keyword (str): Search keyword pattern string
            value (str): Search value pattern string

        Returns:
            bool: Check state. 'True' if the storage contains parameter
            according given patterns
        """
        res = False
        if isinstance(storage, dict):
            for key in storage.keys():
                res = match_string(key, keyword) or \
                    match_string(translate_command(command, key), keyword)
                res = res and (value is None or len(value) == 0 or \
                                   self._check_value(command, key,
                                                     storage[key], value))
                if not res:
                    childstorage = storage[key]
                    if isinstance(childstorage, dict):
                        res = self._is_exist_keyword(command, childstorage,
                                                     keyword, value)
                    else:
                        for param in to_list(childstorage):
                            res = self._is_exist_keyword(command, param,
                                                         keyword, value)
                            if res:
                                break

                if res:
                    break
        return res

    # pragma pylint: disable=no-self-use
    def _check_value(self, command, keyword, value, pattern):
        """
        Checks existance of the pattern in value.

        Arguments:
            command (str): Command title.
            keyword (str): Parameter keyword.
            value (str|list): Parameter value.
            pattern (str): Value pattern string.

        Returns:
            bool: Check state. 'True' if the value contains given pattern.
        """
        res = False
        if value is not None:
            values = to_list(value)
            for item in values:
                val = str(item)
                res = match_string(val, pattern) or \
                    match_string(translate_command(command, keyword, val),
                                 pattern)
                if res:
                    break
        return res


def create_model(history_proxy):
    """
    Create category model.

    Arguments:
        history_proxy (HistoryProxy): History proxy object.

    Returns:
        Model: New category model.
    """
    model = Model(history_proxy)
    return model
