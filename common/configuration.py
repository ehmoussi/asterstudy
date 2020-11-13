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
Configuration
-------------

This module gives access to the application configuration.

"""

from __future__ import unicode_literals

import os
import os.path as osp
from ConfigParser import SafeConfigParser
# pragma pylint: disable=unused-import
#: Exception raised by the underlying ConfigParser object
from ConfigParser import Error as ConfigurationError

from .base_utils import get_absolute_dirname, get_absolute_path


__all__ = ["CFG", "Configuration", "ConfigurationError"]


RCFILE = "AsterStudy.conf"
RCCFG = "AsterStudyConfig"

__ASTER_OLDSTABLE__ = "" or "@" "ASTER_OLDSTABLE_DIR" "@"
__ASTER_STABLE__ = "" or "@" "ASTER_STABLE_DIR" "@"
__ASTER_TESTING__ = "" or "@" "ASTER_TESTING_DIR" "@"
__FORCE_SALOMEMECA__ = "Yes" or "No"
__DEFAULT_WCKEY__ = "P10WB:ASTER" or None
__VERSION_LABEL__ = "2017.0.2" or ""

URL_TRANSLATOR = "http://code-aster.org/spip.php?article1015"


class Configuration(object):
    """Object to manage the configuration.

    Note:
        The installation parameters are available as attributes and through the
        DEFAULT section.
        This allows to use magic interpolation feature (see `SafeConfigParser`
        object). For example::

            [Versions]
            stable = %(installdir)/stable
    """

    __slots__ = (
        # internal attribute
        '_cfg', '_defaults',
        # automatically set from the installation
        'installdir', 'rcdir', 'docdir', 'htmldoc',
        'apprc', 'userrc', 'is_installed',
        # change by the application during execution time
        'default_version',
    )

    def __init__(self, user_only=False):
        #: directory name containing the packages: datamodel/gui...
        self.installdir = get_absolute_dirname(get_absolute_dirname(__file__))
        path = osp.join(self.installdir, "resources")
        #: boolean flag: signals that application is properly installed
        self.is_installed = False
        #: directory containing the resources files
        if not osp.exists(path):
            root = osp.join(*([self.installdir] + 4*[os.pardir]))
            path = osp.join(root, "share", "salome", "resources", "asterstudy")
            self.is_installed = True
        self.rcdir = get_absolute_path(path)
        #: documentation
        path = osp.join(self.installdir, "docs", "_build", "html",
                        "index.html")
        if not osp.exists(path):
            root = osp.join(*([self.installdir] + 4*[os.pardir]))
            path = osp.join(root, "share", "doc", "asterstudy", "html",
                            "index.html")
        self.htmldoc = get_absolute_path(path)
        # dir with extra docs
        if osp.exists(osp.join(self.installdir, "COPYING")):
            self.docdir = get_absolute_path(self.installdir)
        else:
            root = osp.join(*([self.installdir] + 4*[os.pardir]))
            path = osp.join(root, "share", "doc", "asterstudy")
            self.docdir = get_absolute_path(path)
        #: resource file of the application
        self.apprc = osp.join(self.rcdir, RCFILE)
        #: user resource file
        path = osp.join(os.environ.get("HOME", "/"), ".config", "salome")
        self.userrc = osp.join(path, RCFILE)
        try:
            os.makedirs(path)
        except OSError:
            pass
        self._defaults = {
            'installdir': self.installdir,
            'rcdir': self.rcdir,
            'docdir' : self.docdir,
            'htmldoc': self.htmldoc,
            'apprc': self.apprc,
            'userrc': self.userrc,
            'default_version': 'stable',
        }
        # storage of the configuration parameters
        self._cfg = SafeConfigParser()
        self._load(user_only)
        #: store default code_aster version
        try:
            self.default_version = self.get("General", "default_version")
        except KeyError:
            self.default_version = None

    def get(self, section, option, raw=False):
        """Get option's value. This is a wrapper on SafeConfigParser's
        method."""
        try:
            return self._cfg.get(section, option, raw, self._defaults)
        except ConfigurationError as exc:
            raise KeyError(str(exc))

    def __getattr__(self, attrname):
        """Wrapper on SafeConfigParser object"""
        # unknown Configuration attributes are supposed to be attributes of
        # SafeConfigParser
        return getattr(self._cfg, attrname)

    def _load(self, user_only=False):
        """Load the content of resources files"""
        files = []
        if not user_only:
            files.append(self.apprc)
            paths = os.getenv(RCCFG, '').split(os.pathsep)
            for path in reversed([i for i in paths if i]):
                cfg_file = osp.join(path, RCFILE)
                if osp.exists(cfg_file):
                    files.append(cfg_file)
        if osp.isfile(self.userrc):
            files.append(self.userrc)

        self._cfg.read(files)

        if not user_only:
            # custom initialization from SalomeMeca
            self._force_salomemeca_versions()

    def rcfile(self, filename, must_exist=True):
        """Return the full path to the given resource file.

        Arguments:
            filename (str): Basename of an existing file in the resource
                directory.

        Returns:
            str: Full path to the file or *None* if the file does not exist
                and `must_exist` is *False*.
        """
        path = osp.join(self.rcdir, filename)
        return path if osp.exists(path) or not must_exist else None

    def _force_salomemeca_versions(self):
        """Initialize code_aster versions from SalomeMeca."""
        salomemeca_versions = ["OLDSTABLE", "STABLE", "TESTING", "DEV"]
        for version in salomemeca_versions:
            var_name = "__ASTER_{0}__".format(version)
            var_defval = ("@" "ASTER_{0}_DIR" "@").format(version)
            var_value = globals().get(var_name, var_defval)
            if var_value != var_defval:
                version_root = var_value
            elif __FORCE_SALOMEMECA__.lower() == "yes":
                version_root = os.getenv("ASTER_{0}".format(version))
            else:
                version_root = None
            if os.getenv('DEBUG'):
                print "AsterStudy: config: version: {0}, path : {1}" \
                      .format(version, version_root)
            if version_root:
                version_path = osp.join(version_root, "lib", "aster")
                if osp.isdir(osp.join(version_path, "code_aster")):
                    self.set("Versions", version.lower(), version_path)
                    if os.getenv('DEBUG'):
                        print "AsterStudy: add version: {0}, path : {1}" \
                              .format(version.lower(), version_path)

    @staticmethod
    def get_wckey():
        """Return the Workload Characterization Key.

        It uses the SLURM_WCKEY environment variable if defined.
        Otherwise, it takes the value set during installation in this file.

        Returns:
            str: Key to be used for SALOME jobs.
        """
        # see `salome_runner` for usages
        defval = ("@" "DEFAULT_WCKEY" "@")
        value = __DEFAULT_WCKEY__ if __DEFAULT_WCKEY__ != defval else None
        value = os.getenv("SLURM_WCKEY") or value
        return value

    @staticmethod
    def business_translation_url():
        """Return the url of the business-oriented language translator."""
        return URL_TRANSLATOR

    @staticmethod
    def version_label():
        """Return the version label shown to the user.

        Returns:
            str: The "user" version or "" if it is not defined.
        """
        return __VERSION_LABEL__


#: singleton instance of Configuration
CFG = Configuration()
