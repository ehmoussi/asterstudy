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
**Runner - base classes**

Implementation of the common classes for code_aster runners.

"""

from __future__ import unicode_literals

from common import RunnerError, translate, debug_message, debug_message2
from ..case import Case
from ..stage import Stage
from ..result import StateOptions as SO


class Runner(object):
    """
    Abstract class to define a runner.

    Args:
        case (Case): Case object to run.
        logger (optional[function]): Callback function used to send
            information messages.

    Attributes:
        _case (Case): Case object to run.
        _params (dict): Parameters for calculation running.
        _results (list[Result]): Memory of the results that must be processed
            for this RunCase.
        _queue (list[Result]): List of results that are waiting, running
            or pausing to be processed.
        _interm (list[Result]): Stack of intermediate results to calculate.
        _logger (function): Callback for logging of server commands.
        _console (function): Callback for the console (jobs output).
    """

    def __init__(self, case, **kwargs):
        self._case = case
        self._params = {}
        self._results = []
        self._queue = []
        self._interm = []
        self._logger = kwargs.get('logger', debug_message)
        self._console = kwargs.get('console', debug_message)

        for result in self._case.results():
            if result.state & (SO.NotFinished | SO.Intermediate):
                self._results.append(result)
        self._queue = self._results[:]

    @property
    def current(self):
        """Holds the current processed result."""
        return self._queue[0] if self._queue else None

    @property
    def current_stage(self):
        """Holds the current processed stage."""
        return self._case.result_stage(self.current)

    @property
    def stages_stack(self):
        """Holds the stack of intermediate stages."""
        return [self._case.result_stage(res) for res in self._interm]

    def is_started(self):
        """Tell if at least one result has been submitted."""
        return self._queue[0].state & SO.Waiting == 0 \
            if self._queue else True

    def is_finished(self):
        """Tell if all results have been processed."""
        return len(self._queue) == 0

    def cancel_next(self):
        """Mark all stages following `current` as cancelled and
        empty the queue."""
        for i in self._queue[1:]:
            i.state = SO.Waiting
        self._queue = []

    def log(self, *args):
        """Log a message about the commands on server."""
        self._logger(*args)

    def console(self, *args, **kwargs):
        """Log a message to the console about the calculation."""
        self._console(*args, **kwargs)

    def cleanup(self):
        """Cleanup function, called when a RunCase is removed."""

    def check_parameters(self, params):
        """Check parameters before starting."""
        self._params = params
        required = set(['server', 'version', 'mode', 'memory', 'time'])
        missing = required.difference(params.keys())
        if missing:
            raise RunnerError(translate('Runner', 'Missing parameters: {}')
                              .format(missing))
        debug_message2("Parameters:", params)

    def start(self, params):
        """Start the case calculation process.

        Arguments:
            params (dict): Parameters for calculation running.
        """
        self.check_parameters(params)
        self.log(translate('Runner',
                           'Run case "{0}" calculations process started')
                 .format(self._name(self._case)))
        self.start_next()

    def start_next(self):
        """Start calculation for next result."""
        if self.is_finished():
            self.log(translate('Runner',
                               'Run case "{0}" calculations process finished')
                     .format(self._name(self._case)))
        elif not self.intermediate_stage():
            self.start_current()
            self._interm = []

    def start_current(self):
        """Activate calculation simulation for next result."""
        raise NotImplementedError("must be sub-classed")

    def intermediate_stage(self):
        """Treat intermediate stage.

        Returns:
            bool: True if the current stage is an intermediate stage.
        """
        if self.current_stage.is_intermediate():
            stage = self.current_stage
            stagename = self._name(stage)
            self.log('Stage "{0}" is an intermediate stage and will be '
                     'executed with the next one.'.format(stagename))
            self._interm.append(self._queue.pop(0))
            self.start_next()
            return True
        return False

    def refresh(self):
        """Refresh state of all *not finished* results."""
        raise NotImplementedError("must be sub-classed")

    def stop_current(self):
        """Implementation of the core of 'stop' action.

        Returns:
            bool: The current calculation has been stopped successfully.
        """
        raise NotImplementedError("must be sub-classed")

    def stop(self):
        """Stop the case calculation process."""
        self.refresh()
        current = self.current
        if self.stop_current():
            current.state = SO.Error
            self.cancel_next()
            self.log(translate('Runner',
                               'Run case "{0}" calculations process stopped')
                     .format(self._name(self._case)))
        else:
            self.log(translate('Runner',
                               'Run case "{0}" is already stopped.')
                     .format(self._name(self._case)))

    def pause(self):
        """Pause the execution (optional)."""

    def resume(self):
        """Resume a paused process (optional)."""

    def result_state(self, result):
        """Gets a result state.

        Returns:
            StateOptions: Current state of `result`.
        """
        state = result.state
        if state & SO.Finished:
            return state
        self.refresh()
        state = result.state
        debug_message2("State of", result, ":", SO.name(state))
        return state

    def _name(self, obj):
        """Convenient function to print the name of an object."""
        names = []
        if isinstance(obj, Stage):
            name = self._name(obj.parent_case)
            if len(name) > 0:
                names.append(name)
            names.append(obj.name)
        elif isinstance(obj, Case):
            names.append(obj.name)

        return ':'.join(names)


class ServerInfos(object):
    """Abstract class that provides informations of the servers."""

    def __init__(self, **dummy):
        self._servers = []
        self._refreshed = set()

    @property
    def available_servers(self):
        """Return the list of available servers."""
        return self._servers

    def server_username(self, server):
        """Return the username to be used on a server.

        Returns:
            str: Username.
        """
        raise NotImplementedError("must be sub-classed")

    def server_hostname(self, server):
        """Return the hostname of a server.

        Returns:
            str: Name/IP of the server, None if it is not found.
        """
        raise NotImplementedError("must be sub-classed")

    def server_by_host(self, hostname):
        """Return the server name as label that matches the hostname.

        Returns:
            str: Server name if found, None otherwise.
        """
        found = None
        for server in self.available_servers:
            if self.server_hostname(server) == hostname:
                found = server
                break
        return found

    def server_versions(self, server):
        """Give the list of available versions on `server`.

        Returns:
            list(str): List of names of versions.
        """
        raise NotImplementedError("must be sub-classed")

    def server_modes(self, server):
        """Give the modes supported by `server`.

        Returns:
            list(str): List of modes (as text).
        """
        raise NotImplementedError("must be sub-classed")

    def refresh_once(self, server):
        """Refresh the informations of a server, only once per session."""
        if server not in self._refreshed:
            if self.refresh_one(server):
                self._refreshed.add(server)

    def refresh_one(self, server): # pragma: pylint disable=unused-argument
        """Refresh the informations of a server.

        Arguments:
            server (str): Server name.

        Returns:
            bool: *True* if it succeeded, *False* otherwise.
        """
        # does nothing by default
