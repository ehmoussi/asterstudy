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
Execution messages
------------------

Implementation of objects that give access to the execution messages.

"""

from __future__ import unicode_literals

import hashlib

from common import to_list, translate

from ..general import no_new_attributes
from .utils import MsgLevel, MsgType


class Message(object):
    """This object contains informations about execution messages.

    Arguments:
        level (*MsgLevel*): Message level.
        text (str): Text of the message
        source (*MsgType*): Type of the origin of the message.
        identifier (int): Identify the origin (index in a list, object id...).
        line (int): Line number if the origin is *Stage*: a stage in text mode.

    Attributes:
        _level (*MsgLevel*): Message level.
        _text (str): Text of the message
        _source (*MsgType*): Type of the origin of the message.
        _id (int): Identify the origin (index in a list, object id...).
        _line (int): Line number if the origin is *Stage*: a stage in text mode.
        _topo (dict): Lists of names of topological entities for 'grel' (groups
            of elements), 'grno' (groups of nodes), 'el' (list of elements),
            'no' (list of nodes).
        _unknown (list[str]): List of unknowns.
    """
    _level = _source = _id = _line = _text = None
    _topo = _unknown = None
    __setattr__ = no_new_attributes(object.__setattr__)

    def __init__(self, level, text, source, identifier, line=None):
        self.level = level
        self._text = text
        self._source = source
        self._id = identifier
        self._line = line
        self._topo = {}
        self._unknown = []

    @property
    def level(self):
        """Get the message level."""
        return self._level

    @level.setter
    def level(self, value):
        """Set the message level."""
        assert value in (MsgLevel.Debug, MsgLevel.Info, MsgLevel.Warn,
                         MsgLevel.Error), "unexpected value {!r}".format(value)
        self._level = value

    @property
    def text(self):
        """Get the text of the message."""
        return self._text

    @property
    def source(self):
        """*MsgType*: Type of the creator."""
        return self._source

    @property
    def identifier(self):
        """int: The identifier of the source. A step for 'runner', stage number
        for 'stage', DataModel id for 'command'."""
        return self._id

    @property
    def line(self):
        """int: Line number in a text stage for 'stage'."""
        return self._line

    def source_repr(self, model):
        """Representation of the source of the message.

        Arguments:
            model (*History*): History that contains the referenced source.

        Returns:
            str: String reprensenting the source of the message.
        """
        loc = MsgType.to_str(self.source)
        msgid = self.identifier
        if self.source == MsgType.Runner:
            if msgid == 0:
                loc += translate("Message", " during initialization")
            else:
                loc += translate("Message", " after run #{0}").format(msgid)
        elif self.source == MsgType.Stage:
            loc += translate("Message", " at line {0}").format(self.line)
        else:
            cmd = model.get_node(msgid)
            if cmd and hasattr(cmd, 'title'):
                loc += " in {}".format(cmd.title)
        return loc

    @property
    def checksum(self):
        """Return a checksum of the message."""
        sha = hashlib.sha1()
        sha.update(MsgLevel.to_str(self._level))
        sha.update(MsgType.to_str(self._source))
        sha.update(str(self._id))
        sha.update(str(self._line or ''))
        sha.update(self._text)
        return sha.digest()

    def add_topo(self, typ, names):
        """Add one or several topological entities of type *typ*.

        Arguments:
            typ (str): One of 'grel', 'grno', 'el' or 'no'.
            names (str or list[str]): One or more names of entity.
        """
        self._topo[typ] = self._topo.get(typ, []) + to_list(names)

    def add_unknown(self, names):
        """Add one or several unknowns.

        Arguments:
            typ (str): One of 'grel', 'grno', 'el' or 'no'.
            names (str or list[str]): One or more names of entity.
        """
        self._unknown.extend(to_list(names))

    def get_topo(self, typ):
        """Return the list of topological entities of type *typ*."""
        return self._topo.get(typ, [])

    def get_unknown(self):
        """Return the list of unknowns used in the message."""
        return self._unknown


def extract_messages(text):
    """Extract the messages from a text.

    Arguments:
        text (str): Output of an execution.

    Returns:
        list[*Message*]: List of Message objects.
    """
    msglist = []
    # for unittest and simulator runner
    if text == 'random':
        msglist = _random_messages()
    return msglist


def _random_messages():
    from random import choice, randint, randrange
    msglist = []
    lsrc = set()
    uid = -1
    while len(lsrc) != 3 or len(msglist) < 10:
        level = choice([MsgLevel.Debug, MsgLevel.Info,
                        MsgLevel.Warn, MsgLevel.Error])
        source = choice([MsgType.Runner, MsgType.Stage, MsgType.Command])
        lsrc.add(source)
        uid += 1
        line = randrange(500) if source == MsgType.Stage else ''
        text = 'Sample text for message of level {0}'.format(
            MsgLevel.to_str(level))
        msg = Message(level, text, source, uid, line)
        if source == MsgType.Command:
            for j in range(randint(0, 2)):
                msg.add_topo('grel', 'group{}'.format(j))
            for j in range(randint(0, 2)):
                msg.add_unknown('dof{}'.format(j))
        msglist.append(msg)
    return msglist
