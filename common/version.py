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
Versioning
----------

This module provides versioning utilities for AsterStudy application.

Attributes:
    VERSION_MAJOR (int): Application major version number.
    VERSION_MINOR (int): Application minor version number.
    VERSION_PATCH (int): Application release version number.
    VERSION_STR (str): String representation of the application version.

"""


from __future__ import unicode_literals

from .configuration import CFG

VERSION_MAJOR = 0
VERSION_MINOR = 9
VERSION_PATCH = 1

VERSION_STR = "%d.%d" % (VERSION_MAJOR, VERSION_MINOR)
if VERSION_PATCH > 0:
    VERSION_STR += ".%d" % VERSION_PATCH


def version():
    """
    Get the version of the application shown to the user.

    If one needs the version of the *core*, use constant ``VERSION_STR``.

    Returns:
       str: Version of the application.
    """
    return CFG.version_label() if CFG.version_label() else VERSION_STR
