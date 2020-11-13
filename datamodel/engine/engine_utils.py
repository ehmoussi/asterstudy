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
**asrun utilities**

This module allows to manipulate asrun objects.

"""
from __future__ import unicode_literals

from collections import defaultdict
from functools import wraps
from math import log10
import os
import os.path as osp
import platform
import re
import subprocess as SP

from common import (AsterStudyError, RunnerError, copy_file, debug_message,
                    debug_message2, hms2s, to_str, to_unicode, translate,
                    version)
from common.extfiles import (external_file_export_to_med, is_reference,
                             gen_mesh_file_name)
from ..result import StateOptions, Job
from ..general import FileAttr
from ..aster_parser import add_debut_fin
from ..aster_parser import is_cmd_called

HOST_SEP = "@"
PATH_SEP = ":"

def has_asrun():
    """Tell if asrun is available"""
    if getattr(has_asrun, 'cache', None) is not None:
        return has_asrun.cache
    try:
        # pragma pylint: disable=unused-variable
        from asrun import create_run_instance
        has_asrun.cache = True
    except ImportError:
        has_asrun.cache = False
    return has_asrun.cache


def need_asrun(func):
    """Decorator that ensures that asrun is available."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        """wrapper"""
        if not has_asrun(): # pragma: no cover
            raise ImportError("Import of asrun package failed!")
        return func(*args, **kwargs)
    return wrapper


def _convert_asrun_state(job_state):
    """Convert state value from asrun (job state only) to asterstudy.

    Returns:
        state (StateOptions): state of the job or 0 if job is ended.
    """
    state = 0
    if job_state in ('_', 'PEND', 'SUSPENDED'):
        state = StateOptions.Pending
    elif job_state == 'RUN':
        state = StateOptions.Running
    debug_message2("AsRun state {0} => {1}"
                   .format(job_state, StateOptions.name(state)))
    return state

def _convert_launcher_state(job_state, full=False):
    """Convert state value from SalomeLauncher to asterstudy.

    Returns:
        state (StateOptions): state of the job or 0 if job is ended.
    """
    state = 0
    if job_state == 'RUNNING':
        state = StateOptions.Running
    elif job_state == 'PAUSED':
        # Pausing not used with code_aster
        state = StateOptions.Pending
    elif job_state not in ("FINISHED", "FAILED"):
        state = StateOptions.Pending
    elif full:
        if job_state == "FINISHED":
            state = StateOptions.Success
        else:
            state = StateOptions.Error
    debug_message2("Launcher state {0} => {1}"
                   .format(job_state, StateOptions.name(state)))
    return state

def _convert_asrun_diag(diag):
    """Convert diagnostic from asrun to asterstudy."""
    if diag == 'OK' or diag.startswith('<A>'):
        state = StateOptions.Success
        if diag.startswith('<A>'):
            state = state | StateOptions.Warn
    elif '<S>' in diag:
        state = StateOptions.Interrupted
    else:
        state = StateOptions.Error

    # additionnal flags
    if 'NOOK' in diag or 'TEST_RESU' in diag:
        state = state | StateOptions.Nook

    if 'CPU_LIMIT' in diag:
        state = state | StateOptions.CpuLimit
    elif 'MEMORY' in diag:
        state = state | StateOptions.Memory
    elif 'NO_CONVERGENCE' in diag:
        state = state | StateOptions.NoConvergence

    debug_message2("AsRun diag {0} => {1}"
                   .format(diag, StateOptions.name(state)))
    return state

def convert_asrun_state(job_state, job_diag):
    """Convert state/diag values from asrun to asterstudy."""
    state = _convert_asrun_state(job_state)
    if state:
        return state
    state = _convert_asrun_diag(job_diag)
    return state

def convert_launcher_state(job_state, job_diag=None):
    """Convert state/diag values from SalomeLauncher to asterstudy.

    If `job_diag` is ``None``, only `job_state` is used.
    Otherwise, `job_diag` is only used if the job is finished.

    Arguments:
        job_state (str): Job state as returned by SalomeLauncher.
        job_diag (str): Diagnostic as returned by asrun (or None).
    """
    state = _convert_launcher_state(job_state, full=job_diag is None)
    if state:
        return state
    state = _convert_asrun_diag(job_diag)
    return state

def convert_state_from_message(job_state, filename):
    """Shortcut to call `convert_launcher_state` with the message file."""
    return convert_launcher_state(job_state, asrun_diag(filename))

def asrun_diag(filename):
    """Return the asrun diagnostic from an output file."""
    diag = '<F>_SYSTEM'
    if osp.isfile(filename):
        re_status = re.compile(r'\-\-\- DIAGNOSTIC JOB : +(.*?) *$')
        re_cpu = re.compile('cpu *time *limit', re.I)
        with open(filename, "rb") as fobj:
            for line in fobj:
                if re_cpu.search(line):
                    diag = '<F>_CPU_LIMIT'
                mat = re_status.search(line)
                if mat:
                    diag = mat.group(1)
    return diag


def text_to_asrun(mode):
    """Convert a job mode from gui label to a string for asrun."""
    return {
        Job.BatchText: 'batch',
        Job.InteractiveText: 'interactif'
    }[mode]


def counter():
    """Returns a counter of execution to pass a unique id for each run."""
    if not hasattr(counter, "idx"):
        counter.idx = 0
    counter.idx += 1
    return counter.idx


def create_profil_for_current(prof, case, stages, jobname, params, servcfg):
    """Create the AsterProfil object for one or more stages.

    If more than one stage is given, the first ones are supposed to be
    *intermediate* stages and the last one is *reusable*.

    Arguments:
        prof (AsterProfil): Object with the server informations.
        case (Case): Case object which the stage belongs to.
        stages (list[Stage]): Stage objects to be run.
        jobname (str): Job name.
        params (dict): Dict of the job parameters.
        servcfg (dict): Server configuration.

    Returns:
        AsterProfil: The profile itself, changed in place.
    """
    from asrun import create_profil
    prof = prof or create_profil()

    prof['actions'] = 'make_etude'
    prof['nomjob'] = jobname
    prof['origine'] = "AsterStudy {}".format(version())
    prof['mode'] = text_to_asrun(params['mode'])
    prof['version'] = params['version']
    prof['time_limit'] = hms2s(params['time'])
    prof['memory_limit'] = params['memory']
    prof['mpi_nbcpu'] = params.get('mpicpu', 1)
    prof['mpi_nbnoeud'] = params.get('nodes', 1)
    prof['ncpus'] = params.get('threads', 0) or ''

    studyid = "{0}-{1:04d}-{2}".format(os.getpid(), counter(), platform.node())
    prof['studyid'] = studyid

    # first and last stages
    first = stages[0]
    last = stages[-1]

    # export files
    destdir = last.folder
    try:
        os.makedirs(destdir)
    except OSError:
        raise RunnerError("Previous results already exist in {0}"
                          .format(destdir))

    for path in export_comm(stages, jobname, destdir):
        prof.add_entry(path, data=True, type='comm', ul=1)

    # add files of previously executed stages as data
    ancestor = None
    for stgi in case[:first]:
        debug_message2("previous stage:", stgi)
        for unit, fileinfo in stgi.handle2info.items():
            kwargs = asrun_info(unit, fileinfo, stgi.folder)
            kwargs['data'] = True
            kwargs['result'] = False
            prof.add_entry(**kwargs)
        ancestor = stgi

    # data/result files
    seen = set()
    for stgi in stages:
        for unit, fileinfo in stgi.handle2info.items():
            args = asrun_info(unit, fileinfo, destdir,
                              check=stgi.number == first.number)
            key = (args['ul'], args['pathname'])
            if not fileinfo.attr & FileAttr.Out and key in seen:
                continue
            prof.add_entry(**args)
            seen.add(key)

    # add message file as result
    prof.add_entry(pathname=osp.join(destdir, 'message'),
                   result=True,
                   ul=6,
                   type='mess')
    # database
    prof.add_entry(pathname=database_path(last, servcfg),
                   result=True,
                   type='base',
                   compr=True,
                   isrep=True)
    if ancestor is not None:
        prof.add_entry(pathname=database_path(ancestor, servcfg),
                       data=True,
                       type='base',
                       compr=True,
                       isrep=True)

    debug_message2("Profil generated:\n", prof.get_content())
    return prof

def database_path(stage, servcfg):
    """
    Result database path based on stage and server config.

    Arguments:
        stage (Stage): stage the database belongs to.
        servcfg (dict): server configuration.

    Returns:
        str: path of the database.

    Note:
        If the path is remote, it is preceded by `hostname:`.
    """
    # database
    if stage.result.has_remote:
        return make_remote_path(servcfg, stage.database_path)
    else:
        return stage.database_path

def make_remote_path(servcfg, path):
    """
    Add `hostname@user:` to path.

    Arguments:
        servcfg(dict): server configuration.
        path(str): path relative to remote machine.

    Returns:
        str: `path` preceded by `hostname@user:`
    """
    user = servcfg['rc_definition'].username
    host = servcfg['rc_definition'].hostname
    user = user + HOST_SEP if user else ''
    return user + host + PATH_SEP + path


def export_comm(stages, jobname, destdir=None, separated=False):
    """Return a list of comm files to run stages.

    If neither DEBUT/FIN exists, the content of comm files can be concatenated
    else several files are generated.

    Arguments:
        stages (list[Stage]): Stages to run.
        jobname (str): Name of the job.
        destdir (str): Destination directory (default: last stage folder).
        separated (Optional[bool]): If *True* it always separates each stage in
            a different comm file.

    Returns:
        list[str]: List of filenames of the generated comm files.
    """
    def _enclosed(text):
        # in case of error, considers to be run separately
        try:
            res = is_cmd_called(text, "DEBUT") or is_cmd_called(text, "FIN")
        except AsterStudyError:
            res = True
        return res

    init0 = stages[0].number
    def _add_buffer(ltext, buff):
        if not buff:
            return
        start = len(ltext) + init0 == 1
        ltext.append(add_debut_fin(buff, start))

    comm_texts = [i.get_text() for i in stages]
    indic = [_enclosed(i) for i in comm_texts]
    buff = str("")
    texts = []
    for ind, txt in zip(indic, comm_texts):
        if ind or separated:
            _add_buffer(texts, buff)
            _add_buffer(texts, txt)
            buff = str("")
        else:
            buff += str(os.linesep) + txt
    _add_buffer(texts, buff)

    nb_digits = int(log10(max(1, len(texts)))) + 1
    ext = '.com{{0:0{0}}}'.format(nb_digits)

    destdir = destdir or stages[-1].folder
    if not osp.isdir(destdir):
        os.makedirs(destdir)
    root = re.sub(r'\.comm$', '', jobname)
    files = []
    for i, txt in enumerate(texts):
        path = osp.join(destdir, root + (ext.format(i) if i > 0 else '.comm'))
        with open(path, "wb") as comm:
            comm.write(to_str(txt))
        files.append(path)

    return files


def export_case_as_testcase(case, export_name):
    """Export case for a testcase.

    Arguments:
        export_name (str): Filename of export file. Additional files will
            be added into its parent directory.
    """
    from asrun import create_profil
    prof = create_profil()
    # waiting for option in create_profil
    prof._auto_param = False # pragma pylint: disable=protected-access

    # parameters names and default values
    pnames = {'time': ('time_limit', '0:30', hms2s),
              'memory': ('memory_limit', 1024, None),
              'mpicpu': ('mpi_nbcpu', 1, int),
              'nodes': ('mpi_nbnoeud', 1, int),
              'threads': ('ncpus', '', None)}
    job = case[-1].result.job
    for par, arg in pnames.items():
        value = job.get(par, arg[1])
        if arg[2]:
            value = arg[2](value)
        prof[arg[0]] = value

    prof['testlist'] = 'verification sequential'

    destdir, basn = osp.split(export_name)
    name = osp.splitext(basn)[0]

    for path in export_comm(case.stages, name, destdir):
        prof.add_entry(path, data=True, type='comm', ul=1)

    # data files
    seen = set()
    for stgi in case.stages:
        for unit, fileinfo in stgi.handle2info.items():
            if fileinfo.attr & FileAttr.Out:
                continue
            args = asrun_info(unit, fileinfo, destdir)
            path = args['pathname']
            ext = osp.splitext(path)[1]
            basn = name + ext
            i = 0
            while basn in seen:
                i += 1
                basn = "{0}_{1}{2}".format(name, i, ext)
            seen.add(basn)
            args['pathname'] = basn
            prof.add_entry(**args)
            copy_file(path, osp.join(destdir, basn))

    # keep only basenames
    prof.relocate(None, "")
    prof.WriteExportTo(osp.join(destdir, name + ".export"))


def asrun_info(unit, info, folder, check=True):
    """Build informations for an asrun file from a
    :obj:`datamodel.file_descriptors.Info` object."""
    if check and info.attr & FileAttr.In and not info.exists:
        raise RunnerError(translate('Runner',
                                    "no such file: {0!r}")
                          .format(info.filename))
    if not info.filename:
        raise RunnerError(translate('Runner',
                                    "filename not defined for unit {0}")
                          .format(unit))

    filename = osp.join(folder, info.filename)

    if is_reference(info.filename):
        filename = _smesh2med(info.filename, folder)

    kwargs = dict(pathname=filename,
                  data=bool(info.attr & FileAttr.In),
                  result=bool(info.attr & FileAttr.Out),
                  type='libr',
                  ul=unit)
    return kwargs

def _smesh2med(ref, folder):
    """
    Export an SMESH object into a MED file located in `folder`.

    The name of that MED file in generated automatically.

    Arguments:
        ref (str): the entry of the object.
        folder (str): dirname where to create file.

    Returns:
        str: the absolute path of the MED file just created.
    """
    bname = gen_mesh_file_name(ref, "med")
    filepath = osp.join(folder, bname)
    if not osp.isfile(filepath):
        external_file_export_to_med(ref, filepath)
    return filepath

@need_asrun
def add_stages_from_astk(case, filename):
    """Add stages by importing a file from ASTK."""
    # we can also support .astk format later...
    from asrun import create_profil
    filetype = get_filetype(filename)
    if filetype == 'export':
        prof = create_profil(filename)
    elif filetype == 'astk':
        prof = astk2export(filename)
    else:
        raise TypeError("unknown file type.")

    prof.absolutize_filename(filename)
    debug_message2("Export to import:\n", prof.get_content())
    commfiles, others = prof.get_type('comm', with_completion=True)
    commfiles = sort_comm_files(commfiles)

    first = True
    for comm in commfiles:
        text = open(comm.path, 'rb').read()
        stage = case.text2stage(text, name=stagename(comm.path))
        for afile in others:
            if afile.isrep:
                raise TypeError("directories are not yet supported.")
            if afile.compr:
                raise TypeError("compressed data files are not yet supported.")
            info = stage.handle2info[afile.ul]
            info.filename = afile.path
            if afile.data or not first:
                info.attr |= FileAttr.In
            if afile.result:
                info.attr |= FileAttr.Out
        first = False


def sort_comm_files(collection):
    """Sort comm files: comm first, then com[0-9] in alphabetic order,
    keep initial order when extensions are identical.

    Arguments:
        collection (EntryCollection): asrun object containing list of files.

    Return:
        EntryCollection: sorted list.
    """
    getext = lambda x: osp.splitext(x.path)[1]
    extfiles = sorted([(getext(entry), i, entry) \
                           for i, entry in enumerate(collection)])
    result = [entry for ext, i, entry in extfiles if ext == '.comm']
    result.extend([entry for ext, i, entry in extfiles if ext != '.comm'])
    return result


def get_filetype(filename):
    """Return the type of the file to import.

    Arguments:
        filename (str): Path to the file.

    Returns:
        str: One of 'astk', 'export' or '' if the type is unknown.
    """
    filetype = ''
    expr1 = re.compile('^ *[PAFR] +')
    expr2 = re.compile('^etude,fich,[0-9]+,')
    with open(filename, 'rb') as fileobj:
        while not filetype:
            try:
                snippet = fileobj.next()
            except StopIteration:
                break
            if expr1.search(snippet):
                filetype = 'export'
                break
            if expr2.search(snippet):
                filetype = 'astk'
                break
    return filetype


@need_asrun
def astk2export(filename):
    """Create a AsterProfil object from a '.astk' file."""
    from asrun import create_profil
    expr = re.compile('^etude,fich,(?P<idx>[0-9]+),'
                      r'(?P<key>\w+) +(?P<value>.*)$ *', re.M)

    with open(filename, 'rb') as fileobj:
        content = fileobj.read()
    entries = defaultdict(dict)
    for mat in expr.finditer(content):
        line = entries[mat.group('idx')]
        line[mat.group('key')] = mat.group('value')

    prof = create_profil()
    for entry in entries.values():
        prof.add_entry(pathname=entry['nom'],
                       type=entry['type'],
                       ul=int(entry['UL']),
                       data=bool(int(entry['donnee'])),
                       result=bool(int(entry['resultat'])),
                       compr=bool(int(entry['compress'])),
                       isrep=entry['FR'] == 'R')
    return prof


def stagename(filename):
    """Make a stage name from the filename of a comm file."""
    re_com = re.compile(r'\.com([0-9]+)')
    root, ext = osp.splitext(osp.basename(filename))
    mat = re_com.search(ext)
    if mat:
        root += '_{0}'.format(mat.group(1))
    return root


def parse_server_config(content):
    """Parse information write by as_run --info"""
    info = {}
    mat = re.search("@PARAM@(.*)@FINPARAM@", content, re.DOTALL)
    if mat is not None:
        for line in mat.group(1).splitlines():
            try:
                key, val = re.split(' *: *', line)
                info[key] = val
            except ValueError:
                pass
    mat = re.search("@VERSIONS@(.*)@FINVERSIONS@", content, re.DOTALL)
    if mat is not None:
        lvers = []
        for line in mat.group(1).splitlines():
            try:
                key, val = re.split(' *: *', line)
                lvers.append(val)
            except ValueError:
                pass
        lvers = [str(i) for i in lvers]
        info['vers'] = ' '.join(lvers)
    return info


def remote_file_copy(user, host, source, dest, isdir):
    """SSH file copy from a remote location to another remote location.

    Arguments:
        user (str): User name on the remote host.
        host (str): host name to be addressed by SSH.
        source (str): path of the source file, remote.
        dest (str): path of the destination file, remote.
        isdir (bool): *True* if a directory should be copied.
    """
    flags = '-r' if isdir else ''
    command = "mkdir -p {2}; cp {0} {1} {2}".format(flags, source, dest)
    return remote_exec(user, host, command)


def remote_tail(user, host, pattern, nbline):
    """Search for a remote file on *host* that matches *pattern* and return
    its last *nbline* lines.

    Arguments:
        user (str): User name on the remote host.
        host (str): Host name to be addressed by SSH.
        pattern (str): Pattern/filename.

    Returns:
        str: Last *nbline* of the file.
    """
    text = remote_exec(user, host,
                       "tail --lines {0} {1}".format(nbline, pattern),
                       ignore_errors=True)
    text = text or translate("Runner", "Cannot read output file or empty file.")
    return to_unicode(text)

def remote_exec(user, host, command, ignore_errors=False):
    """Execute *command* on a remote server and return the output.

    Raise OSError exception in case of failure.

    Arguments:
        user (str): User name on the remote host.
        host (str): Host name to be addressed by SSH.
        command (str): Command line to remotely execute.
        ignore_errors (bool): Do not stop in case of error.

    Returns:
        str: Output of the command.
    """
    debug_message("Command executed on {0}: {1}".format(host, command))
    cmd = [to_str(command)]
    if host and host != "localhost":
        use_shell = False
        cmd = [str("ssh"), "-n",
               "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
               str(user + "@" if user else "") + host] + cmd
        debug_message("Full command {0}".format(cmd))
    else:
        use_shell = True
    ssh = SP.Popen(cmd, shell=use_shell, stdout=SP.PIPE, stderr=SP.PIPE)
    out, err = ssh.communicate()
    if ssh.returncode != 0 and not ignore_errors:
        raise OSError(to_str(err))
    return out
