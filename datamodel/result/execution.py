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
Execution objects
-----------------

Implementation of objects that give access to execution results.

"""

from __future__ import unicode_literals

from common import to_list, to_str, translate

from ..general import no_new_attributes

from .utils import StateOptions


class Result(object):
    """Implementation of the result."""

    _state = _stage = _job = _has_remote = _messages = None
    __setattr__ = no_new_attributes(object.__setattr__)

    def __init__(self, stage):
        """
        Create Result object.

        Arguments:
            stage (Stage): Parent Stage.
            name (Optional[str]): Name of Result. Defaults to *None*.
        """
        self._stage = stage
        self._state = StateOptions.Waiting
        self._job = Job()
        self._has_remote = False
        self._messages = []

    @property
    def stage(self):
        """Stage: Attribute that holds Result's parent stage."""
        return self._stage

    @stage.setter
    def stage(self, value):
        """Set Result's parent stage."""
        self._stage = value

    @property
    def state(self):
        """int: Attribute that holds Result's status (*StateOptions*)."""
        return self._state

    @state.setter
    def state(self, value):
        """Set Result's status.

        Arguments:
            value (StateOptions): new state of the Result (an intermediate
                state stays intermediate).
        """
        if self.is_intermediate():
            self._state = value | StateOptions.Intermediate
        else:
            preceding_stages = [i for i in self._stage.preceding_stages]
            for stg in reversed(preceding_stages):
                if not stg.is_intermediate():
                    break
                stg.state = value
            self._state = value

    def is_intermediate(self):
        """Tell if the stage is an intermediate one
        (means executed grouped with the following).
        """
        return bool(self._state & StateOptions.Intermediate)

    @property
    def folder(self):
        """Return the folder containing the result files.

        Returns:
            str: Path to results directory.
        """
        stage = self._stage
        if self.is_intermediate():
            stage = stage.parent_case.get_stage_by_num(stage.number + 1)
        return stage.folder

    @property
    def job(self):
        """int: Attribute that holds Result's job identifier."""
        return self._job

    @property
    def used_in_cases(self):
        """list[Case]: Attribute that holds list of Cases where this
        Result is used."""
        return self._stage.cases

    @property
    def has_remote(self):
        """bool: if result databases are kept on remote execution server."""
        return self._has_remote

    @has_remote.setter
    def has_remote(self, value):
        """To set the keep-on-remote property for result databases."""
        self._has_remote = value

    def clear(self):
        """Clear result."""
        self._state = StateOptions.Waiting

    def __str__(self):
        """Get Result's representation as string."""
        return to_str('Result-' + self._stage.name)

    def __repr__(self):
        """Get stringified representation of the result."""
        return to_str("{0} <{1}>".format(str(self),
                                         StateOptions.name(self.state)))

    def __mul__(self, other):
        """Support native Python '*' operator protocol."""
        assert self.state == other.state \
            and self._stage.name == other.stage.name

    @property
    def messages(self):
        """Get the list of messages of this execution.

        Messages are returned in the order of creation that is supposed to be
        the raising order.
        """
        return self._messages

    def add_messages(self, msglist):
        """Add messages to the list of messages of this execution."""
        existing = [msg.checksum for msg in self._messages]
        for msg in to_list(msglist):
            if msg.checksum not in existing:
                self._messages.append(msg)


class Job(object):
    """Implementation of the job informations.

    It stores informations required to refresh a job even after a save/reload
    and parameters enter the *Run dialog*.
    """
    # pragma pylint: disable=too-many-instance-attributes
    # !!! keep consistency with asterstudy.proto for serialization !!!
    Null = 0x00
    Batch = 0x01
    Interactive = 0x02
    BatchText = translate("Dashboard", "Batch")
    InteractiveText = translate("Dashboard", "Interactive")

    _jobid = _name = _server = _mode = _descr = _start = _end = None
    # Names of execution parameters
    ExecParameters = ('memory', 'time', 'version', 'mpicpu', 'nodes', 'threads',
                      'folder')
    _memory = _time = _version = _mpicpu = _nodes = _threads = _folder = None
    __setattr__ = no_new_attributes(object.__setattr__)

    def __init__(self):
        self._jobid = ''
        self._name = ''
        self._server = ''
        self._mode = Job.Null
        self._start = ''
        self._end = ''
        self._descr = ''
        self._memory = None
        self._time = None
        self._version = None
        self._mpicpu = None
        self._nodes = None
        self._threads = None
        self._folder = None

    # Properties that are externally set
    @property
    def jobid(self):
        """str: Attribute that holds the job's identifier."""
        return self._jobid

    @jobid.setter
    def jobid(self, value):
        """Assign the job identifier."""
        self._jobid = value

    @property
    def jobid_int(self):
        """int: Return the job's identifier as int (for runners that expect
        an integer)."""
        return int(self._jobid or 0)

    @property
    def name(self):
        """str: Attribute that holds the job's name."""
        return self._name

    @name.setter
    def name(self, value):
        """Assign the jobs's name."""
        self._name = value

    @property
    def server(self):
        """str: Attribute that holds the server on which the job was
        submitted."""
        return self._server

    @server.setter
    def server(self, value):
        """Assign the submission server."""
        self._server = value

    @property
    def mode(self):
        """int: Attribute that holds the running mode."""
        return self._mode

    def _set_mode(self, value):
        """Assign the running mode."""
        if not isinstance(value, int):
            value = Job.text_to_mode(value)
        self._mode = value

    @mode.setter
    def mode(self, value):
        """Assign the running mode."""
        self._set_mode(value)

    @property
    def description(self):
        """str: Attribute that holds the job's description."""
        return self._descr

    @description.setter
    def description(self, value):
        """Assign the job description."""
        self._descr = value

    @property
    def start_time(self):
        """str: Attribute that holds the time when the job was submitted."""
        return self._start

    @start_time.setter
    def start_time(self, value):
        """Set the start time."""
        self._start = value

    @property
    def end_time(self):
        """str: Attribute that holds the time when the job was submitted."""
        return self._end

    @end_time.setter
    def end_time(self, value):
        """Set the end time."""
        self._end = value

    @property
    def full_description(self):
        """str: The job's description that is the description entered by the
        user and a summary of job's execution parameters."""
        return translate("AsterStudy",
                         "{0._descr}\n\n"
                         "Start time: {0._start}\n"
                         "End time: {0._end}\n"
                         "Server name: {0._server}\n"
                         "Version: {0._version}\n"
                         "Submission parameters:\n"
                         "    Memory limit: {0._memory} MB\n"
                         "    Time limit: {0._time}\n"
                         "Parallel parameters:\n"
                         "    Number of nodes: {0._nodes}\n"
                         "    Number of processors: {0._mpicpu}\n"
                         "    Number of threads: {0._threads}\n"
                        ).format(self)

    @staticmethod
    def text_to_mode(text):
        """Return the text for a given mode."""
        return {
            Job.BatchText: Job.Batch,
            Job.InteractiveText: Job.Interactive,
        }[text]

    @staticmethod
    def mode_to_text(mode):
        """Return the mode for a given text label."""
        return {
            Job.Batch: Job.BatchText,
            Job.Interactive: Job.InteractiveText,
        }[mode]

    def set_parameters_from(self, parameters):
        """Set the value of parameters from a dict."""
        for key in Job.ExecParameters:
            if key not in parameters.keys():
                continue
            self.set(key, parameters[key])

    def copy_parameters_from(self, other):
        """Copy the value of parameters from another Job object."""
        self.server = other.server
        self.mode = other.mode
        self.description = other.description
        for key in Job.ExecParameters:
            self.set(key, other.get(key))

    def asdict(self):
        """Return parameters as a dict."""
        params = {}
        if self.jobid:
            params['jobid'] = self.jobid
        if self.name:
            params['name'] = self.name
        if self.server:
            params['server'] = self.server
        if self.mode:
            params['mode'] = self.mode_to_text(self.mode)
        if self.description:
            params['description'] = self.description
        for key in Job.ExecParameters:
            if self.get(key):
                params[key] = self.get(key)
        return params

    def set(self, parameter, value):
        """Set the value of a parameter."""
        setter = getattr(self, "_set_" + parameter, None)
        if not setter:
            setattr(self, "_" + parameter, value)
        else:
            setter(value)

    def get(self, parameter, default=None):
        """Return a property value by name or *default* if it is not set."""
        value = getattr(self, "_" + parameter)
        return default if value is None else value
