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
**AsRun runner**

This module defines a runner using ``as_run`` for code_aster executions.

"""

from __future__ import unicode_literals

from common import (current_time, debug_mode, debug_message2,
                    ping, translate, valid_filename,
                    LogFiles, RunnerError, Singleton)
from ..result import extract_messages, Job, StateOptions as SO
from .abstract_runner import Runner, ServerInfos
from .engine_utils import (convert_asrun_state, create_profil_for_current,
                           need_asrun, text_to_asrun)


class AsRun(Runner):
    """Runner that use asrun backend.

    Arguments:
        case, params, logger: see
            :obj:`datamodel.engine.abstract_runner.Runner`.
        unittest (bool): Enable unittest mode.

    Attributes:
        _run (object): AsterRun instance.
        _infos (object): AsRunInfos instance.
        _hdlr (object): AsterCalcHandler instance.
    """

    def __init__(self, **kwargs):
        super(AsRun, self).__init__(**kwargs)
        self._unittest = kwargs.get('unittest', False)
        self._run = AsRunInfos.asrun_instance(**kwargs)
        self._infos = AsRunInfos()
        self._infos.set_log_callback(self._logger)
        self._hdlr = None
        self._nbline = 10000

    @property
    def hdlr(self):
        """Return or build a handler on a asrun calculation."""
        if not self._hdlr:
            self._hdlr = self._build_new_hanfler(self.current)
        return self._hdlr

    def new_handler(self):
        """Create a new handler for a new calculation.

        This will create a fresh AsterProfil object for the next calculation.
        """
        self._hdlr = None

    def _build_new_hanfler(self, result):
        """Create a handler to manage a result."""
        from asrun import create_calcul_handler

        job = result.job
        server = self._params.get('server') or job.server
        if server not in self._infos.available_servers:
            raise RunnerError(translate('Runner', 'Unknown server: {0!r}')
                              .format(server))
        prof = self._infos.init_profil(server)
        if job.jobid:
            prof['jobid'] = job.jobid
            prof['nomjob'] = job.name
            prof['mode'] = text_to_asrun(Job.mode_to_text(job.mode))
        debug_message2("Create handler with:\n", prof)
        return create_calcul_handler(prof)

    def refresh(self):
        """Refresh state of currently processed (calculated) result."""
        if self.is_finished() or not self.is_started():
            return
        res = self.hdlr.tail(nbline=self._nbline)
        self.current.state = convert_asrun_state(res.state, res.diag)
        debug_message2('Job status is', res, ':', self.current.state)
        if self.current.state & SO.Finished:
            self.current.job.end_time = current_time()
            self.hdlr.get_results()
            self._update_result()
            # refresh next if any
            self.refresh()
        else:
            self.console("\nLast {0} lines at {1}..."
                         .format(self._nbline, current_time()))
            self.console(res.output)
            # on partial output
            self.current.add_messages(extract_messages(res.output))

    def start_current(self):
        """Activate calculation simulation for next result."""
        stage = self.current_stage
        stages = self.stages_stack + [stage]
        stagename = self._name(stage)
        name = valid_filename(stagename)
        params = self._params
        self.log(translate('Runner', 'Starting "{0}"...').format(stagename))
        try:
            self.new_handler()
            create_profil_for_current(self.hdlr.prof, self._case,
                                      stages, name, params, None)
            jret, out = self.hdlr.start()
            if jret != 0:
                msg = translate('Runner',
                                'Error during submission of "{0}"'
                                .format(stagename))
                self.log(msg)
                self.log(out)
                raise RunnerError(msg, out)

        except RunnerError as exc:
            self.log("ERROR: {0}".format(exc.msg))
            self.stop()
            raise

        else:
            self.current.state = SO.Pending
            job = self.current.job
            job.jobid = self.hdlr.jobid
            job.server = params['server']
            job.name = name
            job.mode = params['mode']
            job.set_parameters_from(params)
            job.start_time = current_time()
            job.description = params.get('description', '')
            self.log(translate('Runner',
                               'Stage "{0}" start calculation (jobid={1}, '
                               'queue={2})')
                     .format(stagename, self.hdlr.jobid, self.hdlr.queue))

    def stop_current(self):
        """Stop the current calculation process."""
        if not self.current or self.current.state & SO.Finished:
            return False
        # self.hdlr.kill()
        return True

    def cleanup(self):
        """Cleanup function, called when a RunCase is removed."""
        # Warning: it should be "when a RunCase is deleted"
        # Currently "removed" means "not follow by the dashboard", no?
        # That's why it is currently limited to unittests.
        debug_message2("cleanup execution")
        if self._unittest:
            for result in self._results:
                if not result.job.jobid:
                    continue
                hdlr = self._build_new_hanfler(result)
                hdlr.kill()

    def _update_result(self):
        """
        Assign calculation state to the first result and remove
        it from list. In successfull case begin simulation for next
        result or interrupt simulation otherwise.
        """
        stagename = self._name(self.current_stage)
        if self.current.state & SO.Error:
            self.log(translate('Runner',
                               'Stage "{0}" calculation failed. Interruption')
                     .format(stagename))
            self.cancel_next()
        else:
            self.log(translate('Runner',
                               'Stage "{0}" calculation succeeded')
                     .format(stagename))
            self._queue.pop(0)
            self.start_next()


class AsRunInfos(ServerInfos):
    """Proxy object to request asrun informations."""
    __metaclass__ = Singleton
    _singleton_id = 'asrun_runner.AsRunInfos'
    _cache_run = _stream = None

    def __init__(self, **kwargs):
        super(AsRunInfos, self).__init__(**kwargs)
        self._run = AsRunInfos.asrun_instance(**kwargs)

        from asrun import create_client
        self._client = create_client(self._run.rcdir)
        self._client.init_server_config()

    @classmethod
    @need_asrun
    def asrun_instance(cls, **kwargs):
        """Return a singleton instance of the main AsterRun object."""
        if not cls._cache_run:
            from asrun import create_run_instance
            cls._stream = Stream2Func()
            opts = {'log_progress': cls._stream}
            opts['debug_stderr'] = debug_mode() > 1
            if debug_mode() <= 1:
                opts['stderr'] = LogFiles.filename(name='asrun')
            opts.update(kwargs)
            cls._cache_run = create_run_instance(**opts)
        return cls._cache_run

    @classmethod
    def set_log_callback(cls, callback):
        """Set the function in charge of logging."""
        cls._stream.set_function(callback)

    @property
    def available_servers(self):
        """Return the list of available servers."""
        return self._client.get_server_list()

    def server_username(self, server):
        """Return the username to be used on a server.

        Returns:
            str: Username.
        """
        return self.server_config(server).get('login')

    def server_hostname(self, server):
        """Return the hostname of a server.

        Returns:
            str: Name/IP of the server, None if it is not found.
        """
        return self.server_config(server).get('nom_complet')

    def server_versions(self, server):
        """Give the list of available versions on `server`.

        Returns:
            list(str): List of names of versions.
        """
        return self.server_config(server).get('vers', '').split()

    def server_modes(self, server):
        """Give the modes supported by `server`.

        Returns:
            list(str): List of modes (as text).
        """
        modes = []
        cfg = self.server_config(server)
        for name, text in [('batch', Job.BatchText),
                           ('interactif', Job.InteractiveText)]:
            if cfg.get(name, '') in ('oui', 'yes'):
                modes.append(text)
        return modes

    def server_config(self, server):
        """Returns a dict with server configuration."""
        return self._client.get_server_config(server)

    def init_profil(self, server):
        """Build a *template* profil for the server"""
        return self._client.init_profil(server)

    def refresh_one(self, server):
        """Refresh the informations of a server.

        Arguments:
            server (str): Server name.

        Returns:
            bool: *True* if it succeeded, *False* otherwise.
        """
        # switch all servers on
        servcfg = self.server_config(server)
        if ping(self.server_hostname(server)):
            servcfg["etat"] = "on"
        self._client.refresh_server_config([server])
        return True


class Stream2Func(object):
    """Proxy for the asrun logger object."""

    def __init__(self):
        self._func = None

    def set_function(self, function):
        """Use the function as stream."""
        self._func = function

    def write(self, string):
        """Write/send a string"""
        # covered by test_engine_asrun.py but needs --nologcapture option
        if self._func: # pragma: no cover
            self._func(string.strip())

    def flush(self):
        """Does nothing."""
