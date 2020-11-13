# -*- coding: utf-8
# ======================================================================
# COPYRIGHT (C) 1991 - 2017  EDF R&D                  WWW.CODE-ASTER.ORG
# THIS PROGRAM IS FREE SOFTWARE; YOU CAN REDISTRIBUTE IT AND/OR MODIFY
# IT UNDER THE TERMS OF THE GNU GENERAL PUBLIC LICENSE AS PUBLISHED BY
# THE FREE SOFTWARE FOUNDATION; EITHER VERSION 2 OF THE LICENSE, OR
# (AT YOUR OPTION) ANY LATER VERSION.
#
# THIS PROGRAM IS DISTRIBUTED IN THE HOPE THAT IT WILL BE USEFUL, BUT
# WITHOUT ANY WARRANTY; WITHOUT EVEN THE IMPLIED WARRANTY OF
# MERCHANTABILITY OR FITNESS FOR A PARTICULAR PURPOSE. SEE THE GNU
# GENERAL PUBLIC LICENSE FOR MORE DETAILS.
#
# YOU SHOULD HAVE RECEIVED A COPY OF THE GNU GENERAL PUBLIC LICENSE
# ALONG WITH THIS PROGRAM; IF NOT, WRITE TO EDF R&D CODE_ASTER,
#    1 AVENUE DU GENERAL DE GAULLE, 92141 CLAMART CEDEX, FRANCE.
# ======================================================================

"""

This module provides versioning utilities for code_aster.

Attributes:
    VERSION_MAJOR (int): Application major version number.
    VERSION_MINOR (int): Application minor version number.
    VERSION_PATCH (int): Application release version number.
    VERSION_STR (str): String representation of the application version.
    BRANCH (str): Name of the origin branch.
"""

from collections import namedtuple

version_info = namedtuple('aster_version_info', [
'version', 'parentid', 'branch', 'date', 'from_branch', 'changes', 'uncommitted'
])(
*[(13, 4, 0),
 '6232ffb66ef6da8efd8d0114606f492803eedf6a',
 'v13',
 '29/06/2017',
 'v13',
 1,
 []]
)

VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH = version_info.version

VERSION_STR = "%d.%d" % (VERSION_MAJOR, VERSION_MINOR)
if VERSION_PATCH > 0:
    VERSION_STR += ".%d" % VERSION_PATCH

BRANCH = version_info.branch


def version():
    """
    Get version of application.

    Returns:
       str: Version of the application.
    """
    return VERSION_STR
