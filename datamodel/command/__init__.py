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
Command
-------

Declaration of the Command related entities.

"""

from __future__ import unicode_literals

from .constancy import NonConst, NonConstStage
from .mixing import KeysMixing, CO, Unit
from .basic import Command
from .variable import Variable
from .comment import Comment
from .hidden import Hidden
