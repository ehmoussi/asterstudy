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
Abstract Data Model
-------------------

Implementation of the abstract data model that stores set of nodes and
their connections.

"""

from __future__ import unicode_literals

import numpy as NP

from common import to_str
from .general import UIDMixing, no_new_attributes


def add_parent(node, parent):
    """
    Add a parent to the node.

    Arguments:
        node (Node): Child data model node.
        parent (Node): Parent data model node.
    """
    if node.add_parent(parent):
        parent.add_child(node)


def remove_parent(node, parent):
    """
    Remove a parent from the node.

    Arguments:
        node (Node): Child data model node.
        parent (Node): Parent data model node.
    """
    if node.remove_parent(parent):
        parent.remove_child(node)


def compare_deps(node1, node2):
    """
    Compare the dependencies between two nodes.

    ``a < b`` means ``a`` is an ancestor of ``b``.

    Arguments:
        node1 (Node): First node.
        node2 (Node): Second node.

    Returns:
        int: 0 if nodes are equal, -1 if first node is "<" of second one
            and 1 if first node is ">" of second one.
    """
    if node1.uid == node2.uid:
        return 0

    if node2.depends_on(node1):
        return -1
    if node1.depends_on(node2):
        return 1

    return 0


class Node(UIDMixing):
    """A node of the abstract data model.

    .. note::
        Be care to notify the model by calling
        :meth:`.AbstractDataModel.reset_paths` each time the dependencies are
        changed.

    Attributes:
        _name (str): Object's name.
        _model (DataModel): The model to which the Node belongs.
        _parents (list[Node]): List of parent nodes.
        _children (list[int]): List of children nodes uids.
        shallow_copy (Optional[type or tuple[types]]): Class or tuple of
            classes on which to make only a shallow copy.
        ignore_copy (Optional[type or tuple[types]]): Class or tuple of
            classes on which copying should not be done.
        delete_children: when deleting object, recursively delete children?
    """

    _name = _model = _parents = _children = None
    shallow_copy = ignore_copy = delete_children = None
    __setattr__ = no_new_attributes(object.__setattr__)

    def __init__(self, name='', model=None):
        """
        Create a node.

        Arguments:
            name (Optional[str]): Object's name.
            model (Optional[AbstractDataModel]): Data model.
                Defaults to *None*.
        """
        super(Node, self).__init__(uid=-1)
        self._name = name
        self._model = model
        self._parents = []
        self._children = []
        self.shallow_copy = None
        self.ignore_copy = None
        self.delete_children = None

    @property
    def name(self):
        """str: Attribute that holds *name* of the node."""
        return self._name

    @name.setter
    def name(self, name):
        """Declares setter for so named property."""
        if self._name != name:
            self._name = name
            self._after_rename()

    @property
    def model(self):
        """
        AbstractDataModel: Attribute that holds *model* owning the node.
        """
        return self._model

    def detach_model(self):
        """Detach the node from its model.
        """
        self._model = None

    def is_valid(self):
        """Checks whether Node instance is valid or not."""
        return self._model is not None

    @property
    def parent_nodes(self):
        """list[Node]: Attribute that holds parent nodes of the node."""
        return self._parents

    def subnodes(self, criteria=lambda child: True):
        """list[Node]: Returns child nodes according to the given criteria"""
        children = (self._model.get_node(i) for i in self._children)
        return [child for child in children if criteria(child)]

    @property
    def child_nodes(self):
        """list[Node]: Attribute that holds child nodes of the node."""
        return [self._model.get_node(i) for i in self._children] \
            if self._model is not None else []

    @property
    def children(self):
        """list[int]: Attribute that holds uids of node's *children*."""
        return self._children

    @property
    def nb_parents(self):
        """int: Attribute that holds number of parent nodes."""
        return len(self._parents)

    @property
    def nb_children(self):
        """int: Attribute that holds number of child nodes."""
        return len(self._children)

    def dup(self, node, duplicated_nodes, only_children=False):
        """
        Duplicate parent/child relations of the node in the model.

        Arguments:
            node (Node): New node which is a duplicate of this one.
            duplicated_nodes (dict): Map of duplicated nodes,
                for recursive calls; contains mapping of duplicated
                nodes to their clones. Defaults to *None*.
            only_children (Optional[bool]): When *True* only child
                relations are duplicated; otherwise parent relations are
                also duplicated. Defaults to *False*.
        """
        # dealing with parents
        if not only_children:
            for parent in self._parents:
                new_parent = duplicated_nodes.get(parent, parent)
                add_parent(node, new_parent)

        # dealing with children
        for uid in self._children:
            child = self._model.get_node(uid)

            # if ignore copy: skip
            if self.ignore_copy and isinstance(child, self.ignore_copy):
                continue

            # if shallow copy: reference the same child object
            if self.shallow_copy and isinstance(child, self.shallow_copy):
                add_parent(child, node)

            # if deep copy: recursively duplicate children
            else:
                self._model.duplicate(child, duplicated_nodes)

    def __contains__(self, given):
        """Support native Python "in" operator protocol."""
        if isinstance(given, int):
            return next((True for item in self if item.uid == given), False)

        return next((True for item in self if item is given), False)

    def __iter__(self):
        """Support native Python "iter" operator protocol."""
        return iter(self.child_nodes)

    def __eq__(self, other):
        """
        Check nodes equality.

        Arguments:
            other (Node): Node which is being compared with this one.

        Returns:
            bool: *True* if nodes are equal, *False* otherwise.
        """
        if other is None:
            return False

        if not isinstance(other, Node):
            return False

        if other.uid != self._id:
            return False

        if other.name != self._name:
            return False

        if other.model != self._model:
            return False

        parents_this = set(self.parent_nodes)
        parents_that = set(other.parent_nodes)

        if len(parents_this) != len(parents_that):
            return False

        if parents_this - parents_that != set():
            return False

        children_this = set(self._children)
        children_that = set(other.children)

        if len(children_this) != len(children_that):
            return False

        if children_that - children_this != set():
            return False

        return True

    def __ne__(self, other):
        """
        Check nodes non-equality.

        Arguments:
            other (Node): Node which is being compared with this one.

        Returns:
            bool: *True* if nodes are non equal, *False* otherwise.
        """
        return not self.__eq__(other)

    def __lt__(self, other):
        """Tells if `other` depends on the current node."""
        return compare_deps(self, other) < 0

    def __le__(self, other):
        """See `__eq__()` and `__lt__()`."""
        return compare_deps(self, other) <= 0

    def __gt__(self, other):
        """Tells if the current node depends on `other`."""
        return compare_deps(self, other) > 0

    def __ge__(self, other):
        """See `__eq__()` and `__gt__()`."""
        return compare_deps(self, other) >= 0

    def __len__(self):
        """
        Get node size in the terms of children.

        Returns:
            int: Node's size that is equal to the number of children.
        """
        return len(self._children)

    def shortrepr(self):
        """
        Get a short representation of the node.

        Returns:
            str: Short node's representation.
        """
        return to_str("{0._name} <{0._id}:{0.__class__.__name__}"
                      ">").format(self)

    def __repr__(self):
        """
        Get stringified representation of the node.

        Returns:
            str: Node's representation.
        """
        children = self._children
        if self._model:
            children = [self._model.get_node(i).shortrepr() for i in children]
        parent = [i.shortrepr() for i in self.parent_nodes]
        fmt = "{0._name} <{0._id}:{0.__class__.__name__} child={1} parent={2}>"
        return to_str(fmt.format(self, children, parent))

    def __mul__(self, other):
        """
        Support of native Python '*' operator protocol.

        Compares nodes recursively "by value"; here "by value" means
        arbitrary semantics defined in the successor classes.

        Arguments:
            other (Node): Another node.

        Returns:
            bool: *True* of nodes are equal "by value"; *False*
            otherwise.
        """
        assert self.name == other.name

        lchildren = self.child_nodes
        rchildren = other.child_nodes

        assert len(lchildren) == len(rchildren)

        for uid, lchild in enumerate(lchildren):
            rchild = rchildren[uid]
            assert lchild * rchild is None

    def depends_on(self, other):
        """
        Check if the node depends on another node.

        Arguments:
            other (Node): Another model node.

        Returns:
            bool: *True* if node depends on argument (the argument in an
                ancestor of the current node), *False* otherwise.
        """
        return self._model.has_path(other.uid, self._id) \
            if self._model is not None else False

    def add_parent(self, parent):
        """
        Add a parent to the node.

        Arguments:
            parent (Node): Parent node.

        Returns:
            bool: *True* if parent was added, *False* otherwise.
        """
        if parent is None or parent in self._parents or self is parent:
            return False
        self._parents.append(parent)
        if self._model:
            self._model.deps_update_parent(self, parent)
        return True

    def delete(self):
        """Remove the node from the model."""
        args = self.before_remove()

        if self._model:
            self._model.remove_node(self)

        self.after_remove(*args)

    def _after_rename(self): # pragma pylint: disable=no-self-use
        """Hook that is called after the node renaming is finished."""
        pass

    def before_remove(self): # pragma pylint: disable=no-self-use
        """Hook that is called before a basic node removing starts."""
        return ()

    def after_remove(self, *args): # pragma pylint: disable=no-self-use
        """Hook that is called after the node removing is finished."""
        pass

    def add_child(self, child):
        """
        Add a child to the node.

        Arguments:
            child (Node): Child node.

        Returns:
            bool: *True* if child was added, *False* otherwise.
        """
        if child.uid in self._children:
            return False
        self._children.append(child.uid)
        if self._model:
            self._model.deps_update_child(self, child)
        return True

    def remove_parent(self, parent):
        """
        Remove the parent from the node's parents.

        Arguments:
            parent (Node): Parent node.

        Returns:
            bool: *True* if parent was removed, *False* otherwise.
        """
        if parent is None or parent not in self._parents:
            return False
        self._parents.remove(parent)
        if self._model:
            self._model.deps_remove_parent(self, parent)
        return True

    def remove_child(self, child):
        """
        Remove a child from the node.

        Arguments:
            child (Node): Child node.

        Returns:
            bool: *True* if child was removed, *False* otherwise.
        """
        if child.uid not in self._children:
            return False
        self._children.remove(child.uid)
        if self._model:
            self._model.deps_remove_child(self, child)
        return True

    def has_parents(self):
        """
        Check if the node has parents.

        Returns:
            bool: *True* if node has at least one parent
        """
        return self.nb_parents > 0

    def move_parent(self, parent, index=None):
        """
        Change parent's position in the list of parents.

        Arguments:
            parent (Node): Parent node.
            index (Optinal[int]): New parent index. Defaults to *None*
                (move to the end of list).
        """
        if parent is not None and parent in self._parents:
            if index is None:
                index = len(self._parents)-1
            self._parents.remove(parent)
            self._parents.insert(index, parent)

    def sort_children(self, typ, attr):
        """
        Reorders children of the given type according to the value of their
        attribute `attr`.

        Arguments:
            typ (type): Type of the children to consider.
            attr (str): Attribute name whose value is used as an order.
        """
        def _key(uid):
            mynode = self._model.get_node(uid)
            if isinstance(mynode, typ):
                return getattr(mynode, attr)
            else:
                # TODO: not a good value, order of other objects will change
                return None

        self._children.sort(key=_key)


class AbstractDataModel(object):
    """Abstract data model implementation."""

    _nodes = _next_id = _name = _deps = shallow_copy = None
    __setattr__ = no_new_attributes(object.__setattr__)

    def __init__(self):
        """Create model."""
        self._nodes = {}
        self._next_id = 1
        self._name = ''
        self.shallow_copy = None
        self._deps = NP.zeros((0, 0), NP.int_)

    def __contains__(self, node):
        """
        Support of native Python 'in' operator protocol.

        Arguments:
            node (Node, int): Node or its uid.

        Returns:
            bool: *True* if node is a child of the model; *False*
            otherwise.
        """
        if not isinstance(node, int):
            node = node.uid

        return node in self.uids

    @property
    def uids(self):
        """
        list[int]: Attribute that holds uids of all registered nodes.
        """
        return self._nodes.keys()

    def add(self, node, parent=None):
        """
        Add a node into the model.

        Arguments:
            node (Node): Node being added.
            parent (Optional[Node]): Parent node. Defaults to *None*.

        Returns:
            Node: node that has been just added.
        """
        # already in model, do not increment id
        if node.model is self:
            return node
        # pragma pylint: disable=protected-access
        node_id = self._next_id
        node._id = node_id
        node._model = self

        self._init_deps(node)
        add_parent(node, parent)

        self._nodes[node_id] = node
        self._next_id = self._next_id + 1

        return node

    @staticmethod
    def remove(node):
        """
        Removes the node from the model in a proper way

        Arguments:
            node (Node): Node being removed.

        Note:
            Removes child nodes according to node's type
        """
        node.delete()

    def remove_node(self, node):
        """
        Executes a common code for removing the node from the model.

        Arguments:
            node (Node): Node being removed.

        Note:
            Removes child nodes according to node's type
        """
        # Remove node from the list of children from its parents.
        node_id = node.uid
        if node_id in self._nodes:
            # use a copy of the parents list
            for parent in node.parent_nodes[:]:
                remove_parent(node, parent)

            # no more parent: assert not node.has_parents()
            del self._nodes[node_id]

            # if delete_children remove child nodes recursively
            if node.delete_children:
                for child in node.child_nodes:
                    if isinstance(child, node.delete_children):
                        self.remove_node(child)

            # remove node reference to its model
            node.detach_model()
            self._remove_deps(node)

    def duplicate(self, node, duplicated_nodes=None, only_children=False,
                  **kwargs):
        """
        Duplicate the node in the model.

        Arguments:
            node (Node): Node being duplicated.
            duplicated_nodes (Optional[dict]): Map of duplicated nodes,
                for recursive calls; contains mapping of duplicated
                nodes to their clones. Defaults to *None*.
            only_children (Optional[bool]): When *True* only child
                relations are duplicated; otherwise parent relations are
                also duplicated. Defaults to *False*.
            **kwargs: Arbitrary keyword arguments.

        Note:
            Node class must implements `init_duplicated()` method to create a
            new node with no parent nor child.

        Note:
            Extra keyword arguments specified to this function are
            passed to `update_duplicated()` method of the `Node`.

        Returns:
            Node: New node (a clone of argument).
        """
        # keep memory of the copy of nodes not to duplicate them twice
        # or to assign the parent of a copied node the copy of its parent.
        if duplicated_nodes is None:
            duplicated_nodes = {}

        # already duplicated?
        new_node = duplicated_nodes.get(node)
        if not new_node:
            new_node = node.init_duplicated()
            # registering the new node to the abstract data model
            self.add(new_node, None)
            duplicated_nodes[node] = new_node

        # customize some part of the work via node subclasses
        node.dup(new_node, duplicated_nodes, only_children=only_children)

        # specific adjustments
        if hasattr(new_node, "update_duplicated"):
            kwargs['duplicated_nodes'] = duplicated_nodes
            new_node.update_duplicated(node, **kwargs)

        # recompute deps
        self.deps_compute()
        return new_node

    def get_node(self, node_id):
        """
        Get node by its identifier.

        Arguments:
            node_id (int): Identifier of the node.

        Returns:
            Node: Data model node (*None* if not found).
        """
        return self._nodes.get(node_id)

    def child_nodes(self, parent=None):
        """
        Get child nodes of the given object.

        If argument is a Node, its children are returned.
        If argument is *None* (default), then all nodes which do not
        have parent (in other words, top-level nodes, i.e nodes which
        belong to data model itself) are returned.

        Arguments:
            parent (Optional[Node]): Parent node. Defaults to *None*.

        Returns:
            list[Node]: Child nodes.
        """
        if parent is None:
            children = []
            for node in self._nodes.itervalues():
                if not node.has_parents():
                    children.append(node)
            return children
        else:
            return parent.child_nodes

    def has_path(self, node_id1, node_id2):
        """
        Check if there is a dependency path between nodes.

        Arguments:
            node_id1 (int): Identifier of the first node.
            node_id2 (int): Identifier of the second node.

        Returns:
            bool: *True* if there is a path from `node1` to `node2` (if `node1`
            is an ancestor of `node2`); *False* otherwise.
        """
        return self._deps[node_id1 - 1, node_id2 - 1] == 1

    def _init_deps(self, node):
        """Resize the dependencies array."""
        node_id = node.uid
        prev = self._deps
        dim = prev.shape[0]
        self._deps = NP.zeros((node_id, node_id), NP.int_)
        self._deps[:dim, :dim] = prev
        self._deps[node_id - 1, node_id - 1] = 1

    def _remove_deps(self, node):
        """Remove a node in deps array."""
        node_id = node.uid
        self._deps[node_id - 1] = 0
        self._deps[:, node_id - 1] = 0

    def deps_update_parent(self, node, parent):
        """Add a parent to a node."""
        self._deps[parent.uid - 1, node.uid - 1] = 1
        for ancestor in parent.parent_nodes:
            self.deps_update_parent(node, ancestor)

    def deps_remove_parent(self, node, parent):
        """Remove a parent of a node."""
        # if not a direct descendant
        if node.uid not in parent.children:
            self._deps[parent.uid - 1, node.uid - 1] = 0
        for ancestor in parent.parent_nodes:
            self.deps_remove_parent(node, ancestor)

    def deps_update_child(self, node, child):
        """Add a child to a node."""
        uid = node.uid
        self._deps[uid - 1, child.uid - 1] = 1

    def deps_remove_child(self, node, child):
        """Remove a child of a node."""
        self._deps[node.uid - 1, child.uid - 1] = 0

    def deps_compute(self):
        """Compute all dependencies.

        It should not be necessary but needed after duplication.
        """
        deps = self._deps
        dim = deps.shape[0]
        for i in range(dim):
            for j in range(dim):
                if deps[i, j] == 1:
                    deps[i] = NP.amax([deps[i], deps[j]], axis=0)

    @staticmethod
    def save(model, file_name, serializer=None):
        """
        Save model to a file.

        If `serializer` is not given, default on (pickle-based) is used.

        Arguments:
            model (AbstractDataModel): Model object.
            file_name (str): Path to the file.
            serializer (Optinal[any]): Serializer object.
                Defaults to *None*.
        """
        if serializer is None:
            serializer = PickleSerializer()
        serializer.save(model, file_name)

    @staticmethod
    def load(file_name, serializer=None, **kwargs):
        """
        Load model from a file.

        If `serializer` is not given, default on (pickle-based) is used.

        Arguments:
            file_name (str): Path to the file.
            serializer (Optional[any]): Serializer object.
                Defaults to *None*.
            kwargs (Optional): Keywords arguments passed to the serializer.

        Returns:
            AbstractDataModel: Model object.
        """
        if serializer is None:
            serializer = PickleSerializer()
        model = serializer.load(file_name, **kwargs)
        return model


class PickleSerializer(object):
    """
    Simple serializer object based on Python `pickle` functionality.
    """

    def save(self, model, file_name): # pragma pylint: disable=no-self-use
        """
        Save model.

        Arguments:
            model (AbstractDataModel): Model object.
            file_name (str): Path to the file.
        """
        import pickle
        pickle.dump(model, open(file_name, 'w'))

    def load(self, file_name, **_): # pragma pylint: disable=no-self-use
        """
        Load model.

        Arguments:
            file_name (str): Path to the file.

            *PickleSerializer* does not support additional keywords arguments.

        Returns:
            AbstractDataModel: Model object.
        """
        import pickle
        return pickle.load(open(file_name))
