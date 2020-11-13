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
Convenient utilities
--------------------

Some basic utilities.

"""

from __future__ import unicode_literals

from glob import glob
import os
import os.path as osp
import re
import shutil
import time
import tempfile


def get_absolute_path(path):
    """
    Return the absolute path of *path*, eventually by following the
    symbolic links.

    Arguments:
        path (str): File or directory path.

    Returns:
        str: The absolute path of *path*.
    """
    if osp.islink(path):
        path = osp.realpath(path)
    res = osp.normpath(osp.abspath(path))
    return res


def get_absolute_dirname(path):
    """
    Return the absolute directory name of *path*, eventually by following
    the symbolic links.


    Arguments:
        path (str): File or directory path.

    Returns:
        str: The absolute path of the directory containing *path*.
    """
    res = osp.normpath(osp.join(get_absolute_path(path), os.pardir))
    return res


def get_base_name(path, with_ext=True):
    """
    Extract base name from path.

    Arguments:
        path (str): File path.
        with_ext (Optional[bool]): True to extract base name with
            extension; False to get base name without extension.
            Defaults to True.

    Returns:
        str: File's base name.
    """
    basename = osp.basename(path)
    if not with_ext:
        basename = osp.splitext(basename)[0]
    return basename


def get_extension(path, full=False):
    """
    Extract file extension from path.

    Arguments:
        path (str): File path.
        full (Optional[bool]): *True* to extract full extension; *False*
            to get only last part of extension. Defaults to *False*.

    Returns:
        str: File's extension.
    """
    basename = osp.basename(path)
    parts = basename.split(osp.extsep)
    extension = ''
    if len(parts) > 1:
        parts.pop(0)
        extension = osp.extsep.join(parts) if full else parts[-1]
    return extension


def add_extension(path, ext, mask=None):
    """
    Add the extension to the file name.

    If `mask` is specified, it is used to match given file name;
    otherwise `ext` is used for this purpose.

    Arguments:
        path (str): File name or path.
        ext (str): File extension.
        mask (Optional[str]): Match string for extension.

    Returns:
        str: File path with the extension added.
    """
    if not ext.startswith(osp.extsep):
        ext = osp.extsep + ext
    if mask is None:
        mask = ext
    if not mask.startswith(osp.extsep):
        mask = osp.extsep + mask
    mask = "*{}".format(mask)
    from fnmatch import fnmatch
    if not fnmatch(path, mask):
        path += ext
    return path


def same_path(left, right):
    """
    Check if two paths (which may be non-existent) are equivalent.

    Arguments:
        left (str): First path to compare.
        right (str): Second path to compare.

    Returns:
        bool: *True* if paths are equivalent; *False* otherwise.
    """
    return osp.realpath(left) == osp.realpath(right)


def is_subpath(url, dirs):
    """
    Check if *url* is a subpath of any directory in given *dirs*.

    Arguments:
        url (str): Path to check.
        dirs (str, list[str]). Directories to be checked.

    Returns:
         bool: *True* if *url* is contained in any of *dirs*;
         *False* otherwise.
    """
    from . utilities import to_list
    dirs = to_list(dirs)
    if url is not None:
        url = osp.realpath(url)
        for path in dirs:
            path = osp.realpath(path)
            if not path.endswith(osp.sep):
                path = path + osp.sep # properly manage root dir
            if url.startswith(path):
                return True
    return False


def read_file(file_name):
    """
    Read the content of file.

    Arguments:
        file_name (str): File path.

    Returns:
        str: Content of the file.
    """
    file_text = ""
    with open(file_name, 'r') as op_f:
        file_text = op_f.read()
    return file_text


def write_file(file_name, text, safe=True):
    """
    Write data to the file.

    Arguments:
        file_name (str): File path.
        text (str): New file contents.
    """
    if safe:
        tmp_name = None
        with tempfile.NamedTemporaryFile(delete=False) as op_f:
            op_f.write(text.encode('utf-8', 'ignore'))
            tmp_name = op_f.name
        if tmp_name:
            shutil.copyfile(tmp_name, file_name)
            os.unlink(tmp_name)
    else:
        with open(file_name, 'w') as op_f:
            op_f.write(text.encode('utf-8', 'ignore'))


def move_file(source, dest):
    """
    Moves the file if it exists.

    Arguments:
        source (str): Source file path.
        dest (str): Destination path.

    Returns:
        bool: *True* if the copy was done, *False* otherwise.
    """
    if osp.isfile(source):
        shutil.move(source, dest)
        return True
    return False


def copy_file(source, dest):
    """
    Copies the file if it exists.

    Arguments:
        source (str): Source file path.
        dest (str): Destination path.

    Returns:
        bool: *True* if the copy was done, *False* otherwise.
    """
    if osp.isfile(source):
        shutil.copyfile(source, dest)
        return True
    return False


def tail_file(filename, nbline):
    """Read the last *nbline* lines of a file.

    Arguments:
        filename (str): Path of the file.
        nbline (int): Number of lines to return (at most).

    Returns:
        str: Last lines or "" if the file does not exist.
    """
    if not osp.isfile(filename):
        return ""
    with open(filename, 'rb') as fobj:
        lines = fobj.readlines()[-nbline:]
    # remove trailing empty lines
    while lines and not lines[-1].strip():
        lines.pop()
    return ''.join(lines).strip()


def current_time():
    """Return the current time."""
    return time.strftime("%c").decode('utf-8')


def to_unicode(string):
    """Try to convert string into a unicode string."""
    if isinstance(string, unicode):
        return string
    if not isinstance(string, str):
        return unicode(string)
    for encoding in ('utf-8', 'iso-8859-15', 'cp1252'):
        try:
            return string.decode(encoding)
        except UnicodeDecodeError:
            pass
    return string.decode('utf-8', 'replace')

def to_str(ustr):
    """Convert a unicode string into a utf-8 encoded string."""
    # ensure it's a unicode string
    ustr = to_unicode(ustr)
    return ustr.encode('utf-8', 'replace')


def split_text(text, lineno, remove="ASTERSTUDY:"):
    """Split the text at line *lineno* and returns the both parts.

    Arguments:
        text (str): Text to split.
        lineno (int): Line number of the last to include in the first part.
        remove (bool): If *True*, lines with 'ASTERSTUDY:' marker are removed.

    Returns:
        str, str: The both parts of the text.
    """
    lines = text.splitlines()
    join = os.linesep.join
    part1 = join(i for i in lines[:lineno] if remove and remove not in i)
    part2 = join(i for i in lines[lineno:] if remove and remove not in i)
    return part1.strip(), part2.strip()

def ping(hostname, timeout=2):
    """Tell if a remote host is online.

    Returns:
        bool: True if the host responds before the timeout, False otherwise.
    """
    from subprocess import call, PIPE
    return hostname and call(['ping', '-c', '1', '-W', str(timeout), hostname],
                             stdout=PIPE, stderr=PIPE) == 0


class Singleton(type):
    """Singleton implementation in python (Metaclass)."""
    # add _singleton_id attribute to the subclasses to be independant of import
    # path used
    __inst = {}

    def __call__(cls, *args, **kws):
        cls_id = getattr(cls, '_singleton_id', cls)
        if cls_id not in cls.__inst:
            cls.__inst[cls_id] = super(Singleton, cls).__call__(*args, **kws)
        return cls.__inst[cls_id]


def rotate_path(prefix, count):
    """Similar to logrotate, keep `count` versions of `prefix`.

    Arguments:
        prefix (str): Pathname to rotate.
        count (int): Number of times the file is rotated.
    """
    exists = glob('{}.[0-9]*'.format(prefix))
    expr = re.compile(r'{}\.([0-9]+)'.format(re.escape(prefix)))
    # list of (number, path)
    ids = [(int(expr.search(i).group(1)), i) for i in exists]
    ids.sort()

    todelete = ids[count:]
    tokeep = ids[:count]
    if len(tokeep) >= count:
        if tokeep:
            todelete.insert(0, tokeep[-1])
    else:
        np1 = len(ids) + 1
        tokeep.append((np1, '{0}.{1}'.format(prefix, np1)))

    if todelete and tokeep and not osp.exists(prefix):
        todelete.pop()
    for _, path in todelete:
        if osp.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

    if not osp.exists(prefix):
        return
    while len(tokeep) >= 2:
        _, path_1 = tokeep.pop()
        _, path_0 = tokeep[-1]
        os.rename(path_0, path_1)

    _, path_1 = tokeep.pop()
    assert len(tokeep) == 0
    os.rename(prefix, path_1)
