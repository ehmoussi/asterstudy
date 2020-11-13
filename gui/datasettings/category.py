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
Category
--------

Implementation of pseudo-node representing category entity in the GUI
model.

"""

from __future__ import unicode_literals

from datamodel import (AbstractDataModel, History, UIDMixing, Validity,
                       no_new_attributes)

class Category(UIDMixing):
    """Category node."""

    _name = _children = _stage = _model = None
    __setattr__ = no_new_attributes(object.__setattr__)

    def __init__(self, uid, name, stage, model):
        """
        Create category node.

        Arguments:
            uid (int): Category UID.
            name (str): Category name.
            stage (int): Parent stage's UID.
            model (AbstractDataModel): Reference data model.
        """
        UIDMixing.__init__(self, uid)
        self._name = name
        self._children = []
        self._stage = stage
        self._model = model

    @property
    def name(self):
        """str: Attribute that holds *name* of the category."""
        return self._name

    @property
    def stage(self):
        """
        Stage: Attribute that holds parent Stage of the category.
        """
        return self.model.get_node(self._stage) if self.model is not None and \
            self._stage is not None else None

    @property
    def model(self):
        """
        AbstractDataModel: Attribute that holds *data model* of the category.
        """
        model = self._model
        if model is not None and not isinstance(self._model,
                                                AbstractDataModel):
            model = model.root
            if model is not None and not isinstance(model, History):
                model = model.model
        return model

    @property
    def children(self):
        """
        list[int]: Attribute that holds uids of category's *children*.
        """
        return self._children

    @property
    def child_nodes(self):
        """
        list[Node]: Attribute that provides access to the child nodes.
        """
        children = []
        if self.model is not None:
            for i in self._children:
                node = self.model.get_node(i)
                if node is not None:
                    children.append(node)
        return children

    def add_child(self, node):
        """
        Add child node to the category.

        Arguments:
            node (Node): Node object.
        """
        self._children.append(node.uid)

    def check(self, mode=Validity.Complete):
        """
        Check validity status of Category.

        Arguments:
            mode (Optional[int]): Validity to check. Defaults to
                Validity.Complete.

        Returns:
            int: Validity status (see `Validity` enumerator).
        """
        result = Validity.Nothing

        for command in self.child_nodes:
            result |= command.check(mode)

        return result

    def delete(self):
        """Remove all items belonging to the category."""
        _children = self.child_nodes
        self._children = []
        for child in _children:
            child.delete()
