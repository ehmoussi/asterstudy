# -*- coding: utf-8 -*-

# Copyright 2016 EDF R&D i
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
Command Helpers
---------------

Helper functionality for Command implementation.

"""

from __future__ import unicode_literals

from ..abstract_data_model import add_parent, remove_parent
from ..visit_study import FilterVisitor, UnitVisitor
from ..general import ConversionLevel, FileAttr
from ..catalogs import CATA

def register_cos(stage, command, pool_co=None):
    """Properly register all CO command args via producing corresponding
    hiddens.

    Arguments:
        stage (Stage): The stage that the command belongs to.
        command (Command): Command object.
        pool_co (dict, optional): CO objects that existed before unregistering.

    Returns:
        dict: Pool of CO objetcs that have not been reused.
    """
    for path, value in command.get_list_co():
        exist = pool_co and pool_co.get(path)
        if not exist:
            hidden = stage.add_command("_RESULT_OF_MACRO", value.name)
            hidden.init(dict(DECL=value, PARENT=command, PATH=path))
        else:
            del pool_co[path]
            exist.name = value.name
            add_parent(exist, command)

def unregister_cos(command, delete=True):
    """Unregister all registered command COs via removing corresponding hiddens.

    .. note:: If the caller does not need the CO objects, it must delete them.

    Arguments:
        command (Command): Command object that have to forget CO objects.
        delete (bool): If *True*, CO objects that belongs to the command are
            deleted. Otherwise, the command is only removed from their parents
            list.

    Returns:
        dict: Pool of CO objetcs that have not been forgotten.
    """
    pool_co = {}
    for child in command.hidden:
        if child.parent_id == command.uid:
            # command is the creator of the CO
            if delete:
                child.delete()
            else:
                pool_co[child.storage['PATH']] = child
                # The Hidden must be removed if not re-registered.
                remove_parent(child, command)
        else:
            remove_parent(child, command)
    return pool_co

def unregister_parent(command, value):
    "Unregister all value items from the command instance"
    from .basic import Command

    if isinstance(value, Command):
        remove_parent(command, value)
    elif isinstance(value, list):
        for item in value:
            unregister_parent(command, item)
    elif isinstance(value, dict):
        for item in value.itervalues():
            unregister_parent(command, item)

def update_dependence_up(value):
    "Update 'up' dependencies on value cloning"
    from .basic import Command

    if isinstance(value, list):
        for item in value:
            update_dependence_up(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, Command) and item.clone is not None:
                value[key] = item.clone
            else:
                update_dependence_up(item)

def update_dependence_down(command):
    "Update 'down' dependencies on value cloning"
    iterator = (i for i in command.child_commands       \
                if i.stage is not command.stage         \
                    and command.clone is not None       \
                    and command.clone.stage.parent_case \
                        is not i.stage.parent_case)
    for child in iterator:
        _update_dependence_helper(child, command)

def _update_dependence_helper(command, parent):
    def _predicate(simple):
        return simple.value is parent

    visitor = FilterVisitor(_predicate)
    command.accept(visitor)

    for keyword in visitor.keywords:
        keyword.value = parent.clone

def register_parent(command, value):
    "Register value items in the command instance"
    from .basic import Command

    if isinstance(value, Command):
        if value.name == '_' and value.gettype() is not None:
            value.name = "_%d" % value.uid
        add_parent(command, value)
    elif isinstance(value, (list, tuple)):
        for item in value:
            register_parent(command, item)
    elif isinstance(value, dict):
        for item in value.itervalues():
            register_parent(command, item)


def clean_undefined(value):
    "Removes all 'keys' of None 'values'"
    if isinstance(value, (list, tuple)):
        for item in value:
            clean_undefined(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if item is None:
                del value[key]
            else:
                clean_undefined(item)


def unregister_unit(command, clear=True):
    "Unregister all units assigned to the command"
    visitor = UnitVisitor()
    command.accept(visitor)

    if not visitor.keywords:
        return

    for keyword in visitor.keywords:
        value = keyword.value
        if not isinstance(value, int):
            continue

        stage = command.stage
        info = stage.handle2info[value]

        if command not in info:
            continue

        del info[command]

        if clear and not len(info):
            del stage.handle2info[value]


def register_unit(command):
    "Find out and register all units assigned to the command"
    visitor = UnitVisitor()
    command.accept(visitor)

    stage = command.stage
    for keyword in visitor.keywords:
        value = keyword.value
        if isinstance(value, int):
            info = stage.handle2info[value]
            val = keyword.cata.definition['inout']
            attr = FileAttr.str2value(val)
            info[command] = attr
            continue

        if value is None or len(value) != 1:
            keyword.value = None
            continue

        filename = value.values()[0]
        unit = value.keys()[0]

        if unit is None:
            keyword.value = None
            continue

        info = stage.handle2info[unit]
        info.filename = filename if len(filename) > 0 else None

        val = keyword.cata.definition['inout']
        attr = FileAttr.str2value(val)

        info[command] = attr

        keyword.value = unit

def avail_meshes(storage):
    """Mesh concepts of whom the commands in storage depend."""
    from .basic import Command
    res = []
    for val in storage.viewvalues():
        if isinstance(val, dict):
            res += avail_meshes(val)
        elif isinstance(val, (list, tuple)):
            for elem in val:
                if isinstance(elem, dict):
                    res += avail_meshes(elem)
                elif isinstance(elem, Command):
                    res += avail_meshes_in_cmd(elem)
        elif isinstance(val, Command):
            res += avail_meshes_in_cmd(val)

    # eliminate duplicates in list
    return list(set(res))

def avail_meshes_in_cmd(command):
    """Mesh concepts of whom the command depends."""
    from .basic import Command
    res = []
    # `command` may be None if the user did not specify any command
    if command is None:
        return res
    typ = command.gettype(ConversionLevel.NoFail)
    if typ is CATA.package("DataStructure").maillage_sdaster:
        res.append(command)
    parents = [cmd for cmd in command.parent_nodes \
                           if isinstance(cmd, Command)]
    for par in parents:
        res += avail_meshes_in_cmd(par)
    return res

def deleted_by(command):
    """Return the list of results deleted by a DETRUIRE Command.

    Arguments:
        command (Command): Command to analyze.

    Returns:
        list[Command]: List of Command
    """
    from .mixing import Sequence
    if command.title != "DETRUIRE":
        return []

    deleted = []
    lfact = command["CONCEPT"]
    is_seq = isinstance(lfact, Sequence)
    if not is_seq:
        lfact = [lfact]
    for fact in lfact:
        obj = fact["NOM"].value
        obj = obj if isinstance(obj, (list, tuple)) else [obj]
        deleted.extend(obj)
    # cleanup else CONCEPT is set
    if is_seq and lfact.undefined(): # pragma pylint: disable=no-member
        del command._engine["CONCEPT"] # pragma pylint: disable=protected-access

    return deleted
