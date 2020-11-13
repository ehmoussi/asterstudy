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
code_aster engine
-----------------

Implementation of classes code_aster executions.

"""

from __future__ import unicode_literals

import os
import re

from common import RunnerError, translate


class Engine(object):
    """Enumerator for the different types of engine."""
    Simulator = 0x01
    AsRun = 0x02
    Salome = 0x04

    # If revert to AsRun by default, see changeset 2e851e61bfe3 to restore
    # a relevant message about the job output
    Default = Simulator if os.getenv('ASTERSTUDY_SIMULATOR') else Salome

    @staticmethod
    def name(engine):
        """Return a name of an Engine."""
        return {
            Engine.Simulator: "Simulator",
            Engine.AsRun: "AsRun",
            Engine.Salome: "Salome",
        }[engine]

def _select_engine(engine):
    """Select the proper engine type."""
    if engine & Engine.Simulator:
        from .simulator import Simulator, SimulatorInfos
        return Simulator, SimulatorInfos, NAJobsList

    elif engine & Engine.AsRun:
        from .asrun_runner import AsRun, AsRunInfos
        return AsRun, AsRunInfos, NAJobsList

    elif engine & Engine.Salome:
        from .salome_runner import Salome, SalomeInfos, SalomeJobsList
        return Salome, SalomeInfos, SalomeJobsList

    raise TypeError(translate('Runner',
                              "Unknown engine type: {0}").format(engine))

def runner_factory(engine=Engine.Default, **kwargs):
    """Return the proper runner instance."""
    class_ = _select_engine(engine)[0]
    return class_(**kwargs)


def serverinfos_factory(engine=Engine.Default, **kwargs):
    """Return the proper server informations instance."""
    class_ = _select_engine(engine)[1]
    return class_(**kwargs)

def jobslist_factory(engine=Engine.Default, **kwargs):
    """Return the proper instance that register jobs list."""
    class_ = _select_engine(engine)[2]
    return class_(**kwargs)


class NAJobsList(object):
    """Not Available JobsList object."""

    @staticmethod
    def load_jobs(string):
        """Load the list of jobs.

        Arguments:
            string (str): Jobs list to load.
        """

    @staticmethod
    def save_jobs():
        """Store the list of jobs.

        Returns:
            str: Jobs list as string.
        """
        return ''

def version_ismpi(version):
    """Tell if the version is a MPI version (currently by name convention).

    Arguments:
        version (str): Version name.

    Returns:
        bool: *True* if the version supports MPI, *False* otherwise.
    """
    return re.search('_mpi', version, flags=re.I) is not None
