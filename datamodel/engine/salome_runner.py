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
**Salome runner**

This module defines a runner using SALOME for code_aster executions.

See documentation of *SalomeLauncher*
http://docs.salome-platform.org/latest/tui/KERNEL/interfaceEngines_1_1SalomeLauncher.html
"""

from __future__ import unicode_literals

import getpass
from glob import glob
import os
import os.path as osp
import shutil
import socket
import tempfile

from common import (CFG, current_time, debug_message2, RunnerError, Singleton,
                    to_str, to_unicode, translate, valid_filename)
from common.utilities import timestamp
from ..general import FileAttr
from ..result import extract_messages, Job, StateOptions as SO
from .abstract_runner import Runner, ServerInfos
from .engine_utils import (convert_launcher_state, convert_state_from_message,
                           create_profil_for_current, parse_server_config,
                           remote_exec, remote_file_copy, remote_tail)

try:
    import salome
    salome.salome_init()
    HAS_SALOME = True
except (ImportError, RuntimeError): # pragma: no cover
    HAS_SALOME = False


def has_salome():
    """Tell if SalomeLauncher is available"""
    return HAS_SALOME


class Salome(Runner):
    """Runner that use SALOME backend.

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
        super(Salome, self).__init__(**kwargs)
        self._unittest = kwargs.get('unittest', False)
        self._infos = SalomeInfos()
        # ensure that the resource definition are read
        _ = self._infos.available_servers
        self._hdlr = None
        self._nbline = 10000
        self.xmlfile = osp.join(self._case.model.folder, 'joblist.xml')

    @property
    def hdlr(self):
        """Return or build a handler on a SALOME launcher."""
        if not self._hdlr:
            self._hdlr = salome.naming_service.Resolve(str('/SalomeLauncher'))
        return self._hdlr

    def refresh(self):
        """Refresh state of currently processed (calculated) result."""
        if self.is_finished() or not self.is_started():
            return
        job = self.current.job
        res = self.hdlr.getJobState(job.jobid_int)
        self.current.state = convert_launcher_state(res)
        debug_message2('Job {0}: status is {1}: {2}'
                       .format(job.jobid, res, SO.name(self.current.state)))
        if self.current.state & SO.Finished:
            job.end_time = current_time()
            self.get_job_results(job)
            # parse message file if it exists
            stage = self.current_stage
            output = glob(osp.join(stage.folder, "logs", "command_*.log"))
            if output:
                self.current.state = convert_state_from_message(res, output[0])
                with open(output[0], 'rb') as fileout:
                    text = to_unicode(fileout.read())
                    self.current.add_messages(extract_messages(text))

            self.save_jobs()
            self._update_result()
            # refresh next if any
            self.refresh()
        else:
            self.console("\nLast {0} lines at {1}..."
                         .format(self._nbline, current_time()))
            salome_job = self.hdlr.getJobParameters(job.jobid_int)
            text = remote_tail(self._infos.server_username(job.server),
                               self._infos.server_hostname(job.server),
                               osp.join(salome_job.work_directory,
                                        "logs", "command_*.log"),
                               self._nbline)
            self.current.add_messages(extract_messages(text))
            self.console(text)

    def start_current(self):
        """Activate calculation simulation for next result."""
        stage = self.current_stage
        stages = self.stages_stack + [stage]
        stagename = self._name(stage)
        name = valid_filename(stagename)
        params = self._params
        self.log(translate('Runner', 'Starting "{0}"...').format(stagename))
        try:
            server = params['server']
            servcfg = self._infos.server_config(server)
            stage.set_remote(params.get('remote_folder'))
            if not servcfg:
                raise RunnerError(translate("Runner",
                                            "Server {0!r} is not available.")
                                  .format(server))
            prof = create_profil_for_current(None, self._case,
                                             stages, name, params, servcfg)
            dbtype, _ = prof.get_base('D')
            remote_in_files = [i.path for i in prof.get_data() \
                                      if i.host and i.type == dbtype]
            salome_job = create_command_job(servcfg, params, prof, stage)
            jobid = self.hdlr.createJob(salome_job)
            try:
                self._infos.export_remote_input_files(server,
                                                      remote_in_files,
                                                      salome_job.work_directory)
                self.hdlr.launchJob(jobid)
                self.save_jobs()
            except Exception as exc:
                msg = translate('Runner',
                                'Error during submission of "{0}"'
                                .format(stagename))
                self.log(msg)
                self.log(str(exc))
                raise RunnerError(msg, str(exc))

        except RunnerError as exc:
            self.log("ERROR: {0}".format(exc.msg))
            self.stop()
            raise

        else:
            self.current.state = SO.Pending
            # Store job informations
            job = self.current.job
            job.jobid = str(jobid)
            job.server = server
            job.name = name
            job.mode = params['mode']
            job.set_parameters_from(params)
            job.start_time = current_time()
            job.description = params.get('description', '')
            self.log(translate('Runner',
                               'Stage "{0}" start calculation (jobid={1})')
                     .format(stagename, jobid))

    def stop_current(self):
        """Stop the current calculation process."""
        if not self.current or self.current.state & SO.Finished:
            return False
        self.current.state = SO.Error
        job = self.current.job
        if not job.jobid_int:
            return True
        self.hdlr.stopJob(job.jobid_int)
        self.get_job_results(job)
        self.save_jobs()
        debug_message2('Job {0} stopped'.format(job.jobid))
        return True

    def cleanup(self):
        """Cleanup function, called when a RunCase is removed."""
        # Warning: it should be "when a RunCase is deleted"
        # Currently "removed" means "not follow by the dashboard", no?
        # That's why it is currently limited to unittests.
        debug_message2("cleanup execution")

    def _update_result(self):
        """
        Assign calculation state to the first result and remove
        it from list. In successfull case begin simulation for next
        result or interrupt simulation otherwise.
        """
        stagename = self._name(self.current_stage)
        current = self.current
        if current.state & SO.Success:
            copy_error = self._copy_results()
            if copy_error:
                current.state = SO.Error
                self.log(translate('Runner',
                                   "{0} result file(s) has(have) not been "
                                   "copied to their destination. "
                                   "Following stages will probably fail.")
                         .format(copy_error))
            else:
                self.log(translate('Runner',
                                   'Stage "{0}" calculation succeeded '
                                   'with state {1} ({2})')
                         .format(stagename, SO.name(current.state),
                                 current.state))
                self._queue.pop(0)
                self.start_next()

        if not current.state & SO.Success:
            self.log(translate('Runner',
                               'Stage "{0}" calculation failed. Interruption')
                     .format(stagename))
            self.cancel_next()

    def _copy_results(self):
        """Copy/move results files to their final destination.

        Note:
            Results are put in the stage directory by the profile,
                they are copied to the path specified by the user
                in this function. This does not include result databases.
        """
        error = 0
        stage = self.current_stage
        stagedir = stage.folder
        for fileinfo in stage.handle2info.values():
            src = osp.join(stagedir, osp.basename(fileinfo.filename))
            if fileinfo.attr & FileAttr.Out:
                try:
                    self.log(translate('Runner',
                                       "Copying result {0!r}")
                             .format(fileinfo.filename))
                    parent = osp.dirname(fileinfo.filename)
                    if not osp.isdir(parent):
                        os.makedirs(parent)
                    dest = fileinfo.filename if not osp.isdir(src) else parent
                    shutil.move(src, dest)
                except (IOError, OSError) as exc:
                    self.log(translate('Runner',
                                       'ERROR: Copy failed: {0}').format(exc))
                    error += 1
        return error

    def get_job_results(self, job):
        """Wrapper for retrieving job results, to handle remote res database.

        Arguments:
            job (Job): Asterstudy's job object.
        """
        if self.current.has_remote: # pragma: no cover
            # Checked by test_engine_salome_remote.py
            # SALOME Launcher's job object
            salome_job = self.hdlr.getJobParameters(job.jobid_int)

            # the remote database is found in out_files
            # thanks to its name
            dbpath = self.current_stage.database_path

            # `out_files` has Salome encoding (utf-8)
            for outfile in salome_job.out_files:
                if outfile == to_str(osp.basename(dbpath)):
                    remote_file_copy(self._infos.server_username(job.server),
                                     self._infos.server_hostname(job.server),
                                     osp.join(to_str(salome_job.work_directory),
                                              to_str(outfile)),
                                     osp.dirname(dbpath), True)
                else:
                    self.hdlr.getJobWorkFile(job.jobid_int,
                                             to_str(outfile),
                                             to_str(""))
        else:
            self.hdlr.getJobResults(job.jobid_int, str(""))

    def save_jobs(self):
        """Store the list of jobs."""
        self._case.model.jobs_list = SalomeJobsList.save_jobs()


class SalomeJobsList(object):
    """Manage the list of jobs in SALOME."""
    _hdlr = None

    @classmethod
    def hdlr(cls):
        """Return or build a handler on a SALOME launcher."""
        if not cls._hdlr:
            cls._hdlr = salome.naming_service.Resolve(str('/SalomeLauncher'))
        return cls._hdlr

    @classmethod
    def load_jobs(cls, string):
        """Load the list of jobs.

        Arguments:
            string (str): Jobs list to load.
        """
        if not string:
            return
        tmp = tempfile.mkstemp()[1]
        try:
            with open(tmp, 'wb') as xmlfile:
                xmlfile.write(to_str(string))
            cls.hdlr().loadJobs(to_str(tmp))
        except Exception: # pragma pylint: disable=broad-except
            pass # fresh development, must not fail!
        finally:
            os.remove(tmp)

    @classmethod
    def save_jobs(cls):
        """Store the list of jobs.

        Returns:
            str: Jobs list as string.
        """
        tmp = tempfile.mkstemp()[1]
        try:
            cls.hdlr().saveJobs(to_str(tmp))
            with open(tmp, 'rb') as xmlfile:
                string = xmlfile.read()
        except Exception: # pragma pylint: disable=broad-except
            string = "" # fresh development, must not fail!
        finally:
            os.remove(tmp)
        return string


class SalomeInfos(ServerInfos):
    """Proxy object to request informations about servers in SALOME."""
    __metaclass__ = Singleton
    _singleton_id = 'salome_runner.SalomeInfos'
    _cache_run = _stream = None

    def __init__(self, **kwargs):
        super(SalomeInfos, self).__init__(**kwargs)
        self._cfg = {}

    @property
    def available_servers(self):
        """Return the list of available servers."""
        # If it is already filled, return
        if self._servers:
            return self._servers
        # Ask for SALOME the known resources
        param = salome.ResourceParameters()
        param.can_launch_batch_jobs = True
        rc_manager = salome.lcc.getResourcesManager()
        self._servers = rc_manager.GetFittingResources(param)
        # Put localhost at first position to ensure a quick refresh
        # at the first opening of Run dialog
        if 'localhost' in self._servers:
            self._servers.remove('localhost')
            self._servers.insert(0, 'localhost')
        for server in self._servers:
            self._set_rcdef(server)
        return self._servers

    def _set_rcdef(self, server):
        """Ask Salome Resources Manager for the `rc_definition` of a server.

        Arguments:
            server (str): Name of the server as declared in JobManager.

        Returns:
            *ResourceDefinition*: Resources definition of the server.
        """
        if server not in self._servers:
            return None
        rc_manager = salome.lcc.getResourcesManager()
        rcdef = rc_manager.GetResourceDefinition(to_str(server))
        # Quick and dirty correction, if empty, default `working_directory`
        # is set to that of `localhost` preceded by $HOME
        if not rcdef.working_directory:
            rcloc = rc_manager.GetResourceDefinition(to_str('localhost'))
            bname = osp.basename(osp.normpath(rcloc.working_directory))
            rcdef.working_directory = osp.join(os.getenv(str("HOME")),
                                               str("Batch"),
                                               str(bname))
        cfg = self.server_config(server)
        cfg['rc_definition'] = rcdef
        return rcdef

    def server_username(self, server):
        """Return the username to be used on a server.

        Returns:
            str: Username.
        """
        rcdef = self.server_config(server).get('rc_definition')
        return getattr(rcdef, 'username', None)

    def server_hostname(self, server):
        """Return the hostname of a server.

        Returns:
            str: Name/IP of the server, None if it is not found.
        """
        rcdef = self.server_config(server).get('rc_definition')
        return getattr(rcdef, 'hostname', None)

    def server_config(self, server):
        """Returns a dict with server configuration."""
        # ensure the servers informations have been read
        if not self._servers:
            _ = self.available_servers
        # initialize it if it does not yet exist
        self._cfg[server] = self._cfg.get(server, {})
        return self._cfg[server]

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

    def refresh_one(self, server):
        """Refresh the informations of a server.

        *To check error recovery in unittests, *server* can take a special
        value *"unittest"*, that simulates an *OSError* exception.*

        Arguments:
            server (str): Server name.

        Returns:
            bool: *True* if it succeeded, *False* otherwise.
        """
        _unittest = server == 'unittest'
        server = 'localhost' if _unittest else server
        rcdef = self._set_rcdef(server)
        if not rcdef:
            raise ValueError(translate("Runner",
                                       "Server {0!r} is not available.")
                             .format(server))
        try:
            hostname = 'localhost' if server == 'localhost' else rcdef.hostname
            if _unittest:
                raise OSError
            output = remote_exec(rcdef.username, hostname,
                                 "{} shell -- as_run --info"
                                 .format(osp.join(rcdef.applipath, 'salome')))
        except OSError:
            return False

        cfg = self.server_config(server)
        cfg.update(parse_server_config(output))
        debug_message2("Server configuration for {0!r}: {1}"
                       .format(server, cfg))
        return True

    def export_remote_input_files(self, server, flist, workdir):
        """Method to manually copy already remote input files to work dir.

        Arguments:
            server (str): name of the SALOME resource.
            flist (list): list of remote files to copy.
            workdir (str): path to execution directory.

        Note:
            For `flist` and `workdir`, paths are related to the resource,
                they are not preceded by [<user>@<host>:].
            This is a dirty workaround, waiting for SALOME Launcher to
                provide a proper implementation of this feature.
        """
        # see the example at
        # http://python-for-system-administrators.readthedocs.io/en/latest/ssh.html
        user = self.server_username(server)
        host = self.server_hostname(server)
        for myfile in flist:
            return remote_file_copy(user, host, myfile, workdir, True)


def create_command_job(servcfg, params, prof, stage):
    """Create the SalomeLauncher job."""
    stagedir = stage.folder
    export = osp.join(stagedir, "export")
    fname = osp.join(stagedir, "launcher_script")
    rcdef = servcfg['rc_definition']
    with open(fname, "wb") as fobj:
        fobj.write(os.linesep.join([
            "#!/bin/bash",
            "{} shell -- as_run export",
            ""]).format(osp.join(rcdef.applipath, 'salome')))
    os.chmod(fname, 0755)

    salome_job = salome.JobParameters()
    salome_job.job_name = to_str(prof["nomjob"][0])
    salome_job.job_type = str("command")
    salome_job.wckey = to_str(CFG.get_wckey() or '')
    salome_job.job_file = to_str(fname)
    salome_job.result_directory = to_str(stagedir)
    salome_job.work_directory = str(new_directory(servcfg))
    salome_job.maximum_duration = str(params['time'])

    # In files, do not take distant input databases
    dbtype, _ = prof.get_base('D')
    local_in_files = [i.path for i in prof.get_data() \
                             if not (i.host and i.type == dbtype)]
    local_in_files.append(export)
    salome_job.in_files = [to_str(i) for i in local_in_files]
    out_files = [osp.basename(i.path) for i in prof.get_result()]
    salome_job.out_files = [to_str(i).split(str(":"))[-1] for i in out_files]
    salome_job.resource_required = resource_parameters(params)

    # Now, profil methods from asrun are called (see profil.py)

    # Deepcopy of the profil object
    exported = prof.copy()

    # Loop study files
    for entry in exported.get_collection():
        entry.host, entry.user, entry.passwd = '', '', ''
        entry.path = osp.basename(entry.path)

        # Warning: despite of the method's name, the entry
        #    (i.e. asrun obj referencing a file)
        #    is updated in place and not added,
        #    because the entry object is already referenced
        #    by the profil (see implementation in asrun/profil.py).
        # Updating the entry is required to update the export content
        exported.add(entry)
    exported.WriteExportTo(export)
    return salome_job


def resource_parameters(params):
    """Create ResourceParameters from the job parameters"""
    debug_message2("ResourceParameters from:", params)
    use_batch = params.get('mode') == Job.BatchText
    res = salome.ResourceParameters()
    res.name = to_str(params['server'])
    res.can_launch_batch_jobs = use_batch
    # setting mem_mb raises: ulimit: error setting limit (Invalid argument)
    res.mem_mb = int(params['memory'])
    res.nb_proc = params.get('mpicpu', 1)
    res.nb_node = params.get('nodes', 1)
    return res

def new_directory(servcfg):
    """Return a new directory that should be unique, even on a remote server.

    Arguments:
        servcfg (dict): server configuration as stored by `SalomeInfos`.

    Returns:
        str: Path to a temporary directory on the remote server.
    """
    return osp.join(
        getattr(servcfg.get('rc_definition', None), \
                "working_directory", False) \
        or servcfg['proxy_dir'],
        "{0}-{1}-{2}".format(getpass.getuser(),
                             socket.gethostname(),
                             timestamp(as_path=True)))
