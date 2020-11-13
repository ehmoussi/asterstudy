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

"""Implementation of data model for AsterStudy application."""

from __future__ import unicode_literals

from datamodel.abstract_data_model import AbstractDataModel, Node
from datamodel.aster_syntax import IDS, get_cata_typeid, is_unit_valid
from datamodel.catalogs import CATA
from datamodel.command import CO, KeysMixing
from datamodel.comm2study import comm2study
from datamodel.file_descriptors import Info
from datamodel.general import FileAttr, Validity, ConversionLevel
from datamodel.general import UIDMixing, no_new_attributes
from datamodel.history import History
from datamodel.study2comm import study2comm
from datamodel.study2code import study2code
from datamodel.sync import synchronize
from datamodel.undo_redo import UndoRedo
