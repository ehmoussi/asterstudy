#!/usr/bin/env python
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
Persistence
-----------

AsterStudy related serialization functionality

"""

from __future__ import unicode_literals

import tempfile

from common import debug_message, debug_mode
from .general import ConversionLevel


STRICT_DEFAULT = ConversionLevel.Any

def factory(file_name, serializer=None, strict=None):
    "Returns a proper serializer instance"
    import os
    extension = os.path.splitext(file_name)[1][1:]
    if extension == 'ast':
        return serializer

    strict = STRICT_DEFAULT if strict is None else strict
    return JSONSerializer(strict)


class JSONSerializer(object):
    """
    Simple serializer object based on Python `pickle` functionality.

    Args:
        strict (ConversionLevel): If False, loading does not fail if graphical
            stages can not be reloaded, use text dataset instead.
            Defaults to *STRICT_DEFAULT*.
    """

    def __init__(self, strict=STRICT_DEFAULT):
        self._strict = strict

    def save(self, history, file_name): # pragma pylint: disable=no-self-use
        """
        Save model.

        Arguments:
            model (AbstractDataModel): Model object.
            file_name (str): Path to the file.
        """
        js_text = history2json(history)
        debug_ajs(js_text)

        with open(file_name, "wt") as handle:
            handle.write(js_text)
            handle.flush()

    def load(self, file_name, **kwargs):
        """
        Load model.

        Arguments:
            file_name (str): Path to the file.
            kwargs (Optional): Keywords arguments passed to create the History.

        Returns:
            AbstractDataModel: Model object.
        """
        with open(file_name, "rt") as handle:
            js_text = handle.read()
            debug_ajs(js_text)

            history = json2history(js_text, strict=self._strict, **kwargs)

        return history

def history2document(history): # pragma pylint: disable=too-many-locals
    "Converts History instance to AsterStudy ProtoBuffer message"
    from . import asterstudy_pb2
    from .result import Job
    from .backup import BackupHistory
    bdocument = asterstudy_pb2.BDocument()

    from common.version import VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH
    bdocument.major = VERSION_MAJOR
    bdocument.minor = VERSION_MINOR
    bdocument.patch = VERSION_PATCH

    backup = BackupHistory()
    bhistory = bdocument.history # pragma pylint: disable=no-member
    bhistory.aster = history.version
    bhistory.versionMajor, bhistory.versionMinor, bhistory.versionPatch = \
        history.version_number
    bhistory.jobs_list = history.jobs_list

    suids = set()
    stage2uid = {}
    for case in history:
        bcase = bhistory.cases.add()
        bcase.name = case.name
        bcase.base_folder = case.base_folder
        bcase.description = case.description
        bcase.is_backup = case.is_backup
        bcase.in_dir = case.in_dir if case.in_dir else ''
        bcase.out_dir = case.out_dir if case.out_dir else ''
        for stage in case:
            if stage not in stage2uid:
                bstage = bhistory.stages.add()
                bstage.name = stage.name
                bstage.mode = stage.dataset.mode
                text = stage.get_text(sort=True, pretty=False,
                                      pretty_text=False, enclosed=False)
                bstage.text = text
                backup.save_stage(stage, text)
                bstage.base_folder = stage.base_folder

                for handle, info in stage.handle2info.viewitems():
                    binfo = bstage.files.add()
                    binfo.handle = handle

                    binfo.attr = info.attr
                    binfo.embedded = info.embedded

                    filename = info.filename
                    if filename is None:
                        continue

                    binfo.filename = filename
                    backup.add_file(filename, handle, info.attr)

                bresult = bstage.result
                bresult.resstate = stage.result.state
                job = stage.result.job
                bjob = bresult.job
                bjob.jobid = job.jobid
                bjob.name = job.name
                bjob.server = job.server
                bjob.mode = job.mode
                bjob.start_time = job.start_time
                bjob.end_time = job.end_time
                bjob.description = job.description
                for key in Job.ExecParameters:
                    value = job.get(key)
                    if value is None:
                        continue
                    setattr(bjob, key, value)

                suids.add(stage.uid)
                uid = len(suids)
                bstage.uid = uid
                stage2uid[stage] = uid
            bcase.stages.append(stage2uid[stage])
    backup.end()

    return bdocument

def document2history(bdocument, strict=STRICT_DEFAULT, aster_version=None): # pragma pylint: disable=too-many-locals
    """Converts AsterStudy ProtoBuffer message to History instance

    Arguments:
        bdocument (BDocument): AsterStudy ProtoBuffer document.
        strict (Optional[ConversionLevel]): Tells how strict the conversion
            must be.
        aster_version (Optional[str]): code_aster version used instead of those
            stored in the document.
    """
    from .history import History
    from common import ConversionError
    from .dataset import DataSet
    from .result import Job

    bhistory = bdocument.history
    history = History(bhistory.aster if aster_version is None \
                      else aster_version)
    bvers = bhistory.versionMajor, bhistory.versionMinor, bhistory.versionPatch
    if bvers != history.version_number:
        sbvers = ".".join([str(i) for i in bvers])
        snumb = ".".join([str(i) for i in history.version_number])
        msgerr = ("The study was created using the '{0}' version as {1} "
                  "but the available '{0}' version is {2}").format(
                      history.version, sbvers, snumb)
        if strict & ConversionLevel.Restore:
            raise ValueError(msgerr)
        else:
            debug_message(msgerr)
    history.jobs_list = bhistory.jobs_list

    uid2stage = {}
    for idx, bcase in enumerate(bhistory.cases):
        name = bcase.name
        if idx == 0:
            case = history.current_case
            case.name = name
        else:
            case = history.create_case(name)

        debug_message("loading case {0!r}...".format(name))
        case.base_folder = bcase.base_folder

        case.description = bcase.description
        case.is_backup = bcase.is_backup
        if bcase.in_dir:
            case.in_dir = bcase.in_dir
        if bcase.out_dir:
            case.out_dir = bcase.out_dir

        debug_message("loading stages...")
        for stageid in bcase.stages:
            if stageid in uid2stage:
                case.add_stage(uid2stage[stageid])
            else:
                bstage = bhistory.stages[stageid-1]

                debug_message("loading stage {0.uid}-{0.name}..."
                              .format(bstage))
                stage = case.create_stage(bstage.name)
                text = bstage.text
                stage.use_text_mode()
                stage.set_text(text)
                stage.base_folder = bstage.base_folder

                mode = bstage.mode
                if strict & ConversionLevel.NoGraphical:
                    mode = DataSet.textMode
                if mode == DataSet.graphicalMode:
                    try:
                        stage.use_graphical_mode(strict)
                    except (TypeError, ConversionError):
                        if strict & ConversionLevel.Syntaxic:
                            raise
                        stage.use_text_mode()
                        stage.set_text(stage.get_text(pretty_text=True,
                                                      enclosed=False))
                else:
                    stage.use_text_mode()

                for binfo in bstage.files:
                    info = stage.handle2info[binfo.handle]

                    info.attr = binfo.attr
                    info.embedded = binfo.embedded

                    filename = binfo.filename
                    if filename == '':
                        continue

                    info.filename = filename

                bresult = bstage.result
                # backward compatibility: resstate[int] replaces state[enum]
                if not bresult.resstate and bresult.state:
                    bresult.resstate = bresult.state
                stage.result.state = bresult.resstate
                job = stage.result.job
                bjob = bresult.job
                job.jobid = bjob.jobid
                job.name = bjob.name
                job.server = bjob.server
                job.mode = bjob.mode
                job.start_time = bjob.start_time
                job.end_time = bjob.end_time
                job.description = bjob.description
                for key in Job.ExecParameters:
                    job.set(key, getattr(bjob, key))

                uid2stage[stageid] = stage

        debug_message("case {0!r} loaded".format(name))

    return history

def document2json(bdocument):
    "Converts AsterStudy ProtoBuffer message to JSON text representation"
    from google.protobuf import json_format
    js_text = json_format.MessageToJson(bdocument)

    return js_text

def json2document(js_text):
    "Converts JSON text representation to AsterStudy ProtoBuffer message"
    from . import asterstudy_pb2
    bdocument = asterstudy_pb2.BDocument()

    from google.protobuf import json_format
    json_format.Parse(js_text, bdocument)

    return bdocument

def history2json(history):
    "Converts History instance to JSON text representation"
    bdocument = history2document(history)
    js_text = document2json(bdocument)

    return js_text

def json2history(js_text, strict=STRICT_DEFAULT, **kwargs):
    """Converts JSON text representation to AsterStudy History instance.

    Arguments:
        js_text (str): Content of JSON document.
        strict (Optional[ConversionLevel]): Tells how strict the conversion
            must be.
        kwargs (Optional): Keywords arguments passed to create the History.
    """
    bdocument = json2document(js_text)
    history = document2history(bdocument, strict, **kwargs)

    return history

def debug_ajs(js_text): # pragma: no cover
    """For debugging, use one file name per session"""
    if not debug_mode():
        return
    if not hasattr(debug_ajs, "cache"):
        debug_ajs.cache = tempfile.mkstemp(prefix='astdy-', suffix='.ajs')[1]

    with open(debug_ajs.cache, "w") as js_file:
        js_file.write(js_text)
    debug_message("File saved:", debug_ajs.cache)
