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
Utilities
---------

Auxiliary utilities for AsterStudy application.

"""

from __future__ import unicode_literals

import sys
import math
import os
import os.path as osp
import re
import tempfile
import time
import traceback
import getpass
from collections import OrderedDict
from functools import partial, wraps
from contextlib import contextmanager

from PyQt5 import Qt as Q

from . base_utils import to_unicode, to_str
from . configuration import CFG


def debug_mode(raw=False):
    """
    Check if application is running in debug mode.

    By default (*raw* is *False*), function returns 0 if DEBUG <= 0,
    that means debug mode is switched OFF (not visible), or the DEBUG
    flag's value if it's positive.
    If *raw* is *True*, function returns actual value of DEBUG flag;
    this feature is used by `debug_message()` function.

    Arguments:
        raw (Optional[bool]): If *True*, return actual value of DEBUG
            flag; else return its normalized value. Defaults to *False*.

    Returns:
        int: Value of DEBUG flag.

    See also:
        `debug_message()`
    """
    # debug_mode.DEBUG attribute is only used for unittest
    debug = getattr(debug_mode, "DEBUG", 0)
    try:
        debug = int(os.getenv("DEBUG", debug))
    except ValueError:
        pass
    if not raw:
        debug = max(0, debug)
    return debug


def translate(context, source_text, disambiguation=None, num=-1):
    """
    Get translation text for source text.

    Arguments:
        context (str): Context name.
        source_text (str): Text being translated.
        disambiguation (Opional[str]): String identifying text role
            within the same context. Defaults to *None*.
        num (Optional[int]): Number used to support plural forms of
            translation. Defaults to -1 (that means no number feature).

    Returns:
        str: Translation text.
    """
    return Q.QApplication.translate(context, source_text, disambiguation, num)


def timestamp(as_path=False):
    """Return a timestamp with milliseconds.

    Arguments:
        as_path (bool): If True, ensure that the string is a valid path.
    """
    _now = time.time()
    _msec = (_now - long(_now)) * 1000
    fmt = '%a-%d-%H%M%S' if as_path else '%a-%d-%H:%M:%S'
    return time.strftime(fmt) + '.{:03d}'.format(int(_msec))

def debug_message(*args, **kwargs):
    """
    Print debug message.

    While this function is mainly dedicated for printing textual
    message, you may pass any printable object(s) as parameter.

    The behavior of function depends on the value of DEBUG flag
    (see `debug_mode()` function), as follows:

    - DEBUG = 0: no debug information;
    - DEBUG > 0: print debug informations to stdout;
    - DEBUG < 0: write debug informations to a file
      (``/tmp/asterstudy-main-"username".log``).

    Example:
        >>> from common.utilities import debug_message, debug_mode
        >>> previous = debug_mode()
        >>> debug_mode.DEBUG = 1
        >>> debug_message.timestamp = False
        >>> debug_message("Start operation:", "Compute", "[args]", 100)
        AsterStudy: Start operation: Compute [args] 100
        >>> debug_message("Operation finished:", "Compute")
        AsterStudy: Operation finished: Compute
        >>> debug_mode.DEBUG = previous

    Note:
        - Message is only printed if application is running in debug
          mode. See `debug_mode()`.
        - `debug_message.timestamp` only exists for doctest.

    Arguments:
        *args: Variable length argument list.
        **kwargs: Keyword arguments.

    The following named parameters can be passed via `**kwargs`:

    - *level* (int): Indentation level.

    See also:
        `debug_mode()`
    """
    level = kwargs.get('level', 0)
    mode = debug_mode(raw=True)
    if mode != 0 and len(args) > 0:
        stream = sys.stdout
        if mode < 0:
            stream = LogFiles.file(name="main")
        text = []
        stamp = "AsterStudy:"
        if getattr(debug_message, 'timestamp', True):
            stamp += " " + timestamp()
        text.append(stamp + ("." * abs(level) if level else ""))
        for i in args:
            if not isinstance(i, (str, unicode)):
                i = str(i)
            text.append(to_unicode(i))
        line = " ".join(text)
        stream.write(to_str(line))
        stream.write("\n")
        stream.flush()


debug_message2 = partial(debug_message, level=1) # pragma pylint: disable=invalid-name


def load_pixmap(*args, **kwargs):
    """
    Load pixmap from resource files. Default pixmap can be provided via
    the *default* keyword argument.

    Note:
        Pixmap files are searched in the application's resource
        directory.

    Arguments:
        *args: Pixmap file names.
        **kwargs: Keyword arguments.

    Returns:
        QPixmap: Pixmap object.

    The following named parameters can be passed via `**kwargs`:

    - *default* (QPixmap): Default pixmap.

    See also:
        `load_icon()`, `load_icon_set()`
    """
    if Q.QApplication.instance() is None:
        return kwargs.get('default', None)
    pixmap = Q.QPixmap()
    for name in args:
        pixmap = Q.QPixmap(CFG.rcfile(name))
        if not pixmap.isNull():
            break
    if pixmap.isNull() and 'default' in kwargs:
        pixmap = kwargs['default']
    elif 'size' in kwargs:
        size = kwargs['size']
        width = size if size else pixmap.width()
        height = size if size else pixmap.height()
        if isinstance(size, (tuple, list)):
            width = size[0] if len(size) > 0 else width
            height = size[1] if len(size) > 1 else width
        if (width, height) != (pixmap.width(), pixmap.height()):
            img = pixmap.toImage()
            img = img.scaled(width, height,
                             Q.Qt.IgnoreAspectRatio,
                             Q.Qt.SmoothTransformation)
            pixmap = Q.QPixmap.fromImage(img)
    return pixmap


def load_icon(*args, **kwargs):
    """
    Load icon from resource files. Default pixmap can be provided via
    the *default* keyword argument.

    Note:
        Icon files are searched in the application's resource directory.

    Arguments:
        *args: Icon file names.
        **kwargs: Keyword arguments.

    Returns:
        QIcon: Icon object.

    The following named parameters can be passed via `**kwargs`:

    - *default* (QIcon): Default pixmap.

    See also:
        `load_pixmap()`, `load_icon_set()`
    """
    if Q.QApplication.instance() is None:
        return kwargs.get('default', None)
    return Q.QIcon(load_pixmap(*args, **kwargs))


def load_icon_set(*args):
    """
    Load icon set from resource files.

    With this function separate pixmaps can be assigned to different
    icon states. Different pixmaps for icon should be stored in separate
    files. The function searches pixmaps by appending suffix(es) to the
    base file name:

    Format for pixmaps file names is:
        <filename>[<mode>][<state>].<extension>

    Here,

    - *filename* is a base file name specified via `names`
      parameter;
    - *mode* is an optional icon's mode: "normal", "disabled",
      "active", "selected";
    - *state* is an optional icon's state: "off", "on";
    - *extension* is an original extension specified with `names`
      parameter.

    Note:
        Icon files are searched in the application's resource directory.

    Arguments:
        *args: Icon file names.

    Returns:
        QIcon: Icon object.

    See also:
        `load_pixmap()`, `load_icon()`
    """
    if Q.QApplication.instance() is None:
        return None
    icon = Q.QIcon()

    modes = ("normal", "disabled", "active", "selected")
    states = ("on", "off")

    def _str2mode(_mode):
        _map = {
            "normal" : Q.QIcon.Normal,
            "disabled" : Q.QIcon.Disabled,
            "active" : Q.QIcon.Active,
            "selected" : Q.QIcon.Selected,
            }
        return _map.get(_mode, Q.QIcon.Normal)

    def _str2state(_state):
        _map = {
            "on" : Q.QIcon.On,
            "off" : Q.QIcon.Off,
            }
        return _map.get(_state, Q.QIcon.Off)

    from itertools import product

    # first try mode,state combination
    for mode, state in product(modes, states):
        files = ["{0[0]}_{1}_{2}{0[1]}".format(osp.splitext(name), mode,
                                               state) for name in args]
        pixmap = load_pixmap(*files)
        if not pixmap.isNull():
            icon.addPixmap(pixmap, _str2mode(mode), _str2state(state))

    # then try only mode
    if icon.isNull():
        for mode in modes:
            files = ["{0[0]}_{1}{0[1]}".format(osp.splitext(name), mode)
                     for name in args]
            pixmap = load_pixmap(*files)
            if not pixmap.isNull():
                icon.addPixmap(pixmap, _str2mode(mode), _str2state(""))

    # then try only state
    if icon.isNull():
        for state in states:
            files = ["{0[0]}_{1}{0[1]}".format(osp.splitext(name), state)
                     for name in args]
            pixmap = load_pixmap(*files)
            if not pixmap.isNull():
                icon.addPixmap(pixmap, _str2mode(""), _str2state(state))

    # finally try no mode and no state
    if icon.isNull():
        icon = load_icon(*args)
    return icon


def clean_text(text):
    """
    Clean action, menu or toolbar title by removing special symbols.

    Example:
        >>> from common.utilities import clean_text
        >>> clean_text("&File")
        u'File'
        >>> clean_text("&OK")
        u'OK'

    Arguments:
        text (str): Text to clean up.

    Returns:
        str: Resulting text.
    """
    return text.replace("&", "")


def valid_filename(name):
    """
    Make a valid file name from the given string.

    The function returns a modified version of input string by applying
    the following changes:

    - Spaces are replaced by underscores;
    - Leading and tralinng underscores are truncated.

    Arguments:
        name (str): Initial name.

    Returns:
        str: Corrected name.
    """
    name = re.sub(r'[\s\W]+', '_', name)
    name = re.sub('(^_+|_+$)', '', name)
    return name


def format_code(text):
    """
    Format the given Python code.

    Arguments:
        text (str): Source code block.

    Returns:
        str: Formatted code block.
    """
    from yapf.yapflib.yapf_api import FormatCode
    return FormatCode(text, style_config='facebook')[0]


def format_expr(text):
    """
    Format the given Python expression.

    Arguments:
        text (str): Source code block.

    Returns:
        str: Formatted code block.
    """
    try:
        return format_code(text)[:-1]
    except SyntaxError:
        return text


def wait_cursor(value, **kwargs):
    """
    Set / clear "wait" override cursor for the application.

    The function can be called recursively: each request to set "wait"
    cursor must eventually be followed by a corresponding request to
    restore cursor.

    To unconditionally remove "wait" cursor, specify *True* value as the
    *force* keyword argument.

    Arguments:
        value (bool): *True* to set "wait" cursor; *False* to clear it.
        **kwargs: Keyword arguments.

    The following named parameters can be passed via `**kwargs`:

    - *force* (bool): Forces complete clearing of "wait" cursor;
      applicable only when *value* is *False*.
    """
    if value:
        Q.QApplication.setOverrideCursor(Q.QCursor(Q.Qt.WaitCursor))
    else:
        if Q.QApplication.overrideCursor() is not None:
            Q.QApplication.restoreOverrideCursor()
        if kwargs.get("force", False):
            while Q.QApplication.overrideCursor() is not None:
                Q.QApplication.restoreOverrideCursor()


def change_cursor(func):
    """Decorator for long functions to be wrapped with
    `wait_cursor(True/False)`.

    Arguments:
        func (callable): Function to be wrapped.
    """
    @wraps(func)
    def wrapper(*args, **kargs):
        """wrapper"""
        wait_cursor(True)
        try:
            retcode = func(*args, **kargs)
        finally:
            wait_cursor(False, force=True)
        return retcode
    return wrapper


def show_exception(exception, **kwargs):
    """
    Process unhandled exception.

    If there's a main window (i.e. GUI has been started), the error
    message box showing details about the exception is displayed.
    Additionally, in debug mode, traceback is shown in the details area
    of the message box.

    If there is no main window, error is printed to the terminal.

    The following keyword arguments are accepted:

    - message (str): Custom error message text.
    - traceback (traceback): Traceback object.

    Arguments:
        exception (Exception): Exception object.
        **kwargs: Arbitrary keyword arguments.
    """
    message = kwargs.get("message")
    trace = kwargs.get("traceback")

    message_title = message if message \
        else translate("AsterStudy", "Unexpected error")
    message_type = translate("AsterStudy", "Type:")
    message_value = translate("AsterStudy", "Value:")
    message_traceback = translate("AsterStudy", "Traceback:")

    exc_type = type(exception).__name__
    exc_value = exception.args
    exc_traceback = message_traceback + "\n" + \
        "\n".join(traceback.format_tb(trace)) if trace else \
        traceback.format_exc(exception)

    windows = [i for i in Q.QApplication.topLevelWidgets() \
                   if isinstance(i, Q.QMainWindow)]
    window = windows[0] if windows else None

    if window is None:
        print message_title
        print message_type, exc_type
        print message_value, exc_value
        print exc_traceback
    else:
        wait_cursor(False, force=True)
        msg_box = Q.QMessageBox(Q.QMessageBox.Critical,  # icon
                                "AsterStudy",            # title
                                message_title,           # text
                                Q.QMessageBox.Ok,        # buttons
                                window)                  # parent
        informative = "{tlab} {tval}<br>{vlab} {vval}".format(
            tlab=bold(message_type),
            tval=exc_type,
            vlab=bold(message_value),
            vval=exc_value)
        msg_box.setInformativeText(informative)
        if debug_mode():
            msg_box.setDetailedText(exc_traceback)
            textbox = msg_box.findChild(Q.QTextEdit)
            if textbox:
                textbox.setMinimumWidth(400)
        msg_box.setEscapeButton(msg_box.button(Q.QMessageBox.Ok))
        msg_box.show()


def wrap_html(text, tag, **kwargs):
    """
    Format text with specific html tag.

    Example:
        >>> from common.utilities import wrap_html
        >>> wrap_html("text", "b")
        u'<b>text</b>'
        >>> wrap_html("link", "a", href="http://www.code-aster.org")
        u'<a href="http://www.code-aster.org">link</a>'

    Arguments:
        text (str): Source text.
        tag (str): HTML tag.
        **kwargs: Arbitrary tag attributes.

    Returns:
        str: Formatted text.
    """
    args = ["{}=\"{}\"".format(i, j) for i, j in kwargs.iteritems()]
    args = " ".join(args)
    sep = " " if args else ""
    return "<{tag}{sep}{args}>{text}</{tag}>".format(tag=tag, text=text,
                                                     sep=sep, args=args)

def bold(text):
    """
    Format text as bold.

    This is the shortcut to `wrap_html(text, "b")`.

    Example:
        >>> from common.utilities import bold
        >>> bold("text")
        u'<b>text</b>'

    Arguments:
        text (str): Source text.

    Returns:
        str: Formatted text.
    """
    return wrap_html(text, "b")


def italic(text):
    """
    Format text as italic.

    This is the shortcut to `wrap_html(text, "i")`.

    Example:
        >>> from common.utilities import italic
        >>> italic("text")
        u'<i>text</i>'

    Arguments:
        text (str): Source text.

    Returns:
        str: Formatted text.
    """
    return wrap_html(text, "i")


def underline(text):
    """
    Format text as underlined.

    This is the shortcut to `wrap_html(text, "u")`.

    Example:
        >>> from common.utilities import underline
        >>> underline("text")
        u'<u>text</u>'

    Arguments:
        text (str): Source text.

    Returns:
        str: Formatted text.
    """
    return wrap_html(text, "u")


def preformat(text):
    """
    Format text as preformatted.

    This is the shortcut to `wrap_html(text, "pre")`.

    Example:
        >>> from common.utilities import preformat
        >>> preformat("text")
        u'<pre>text</pre>'

    Arguments:
        text (str): Source text.

    Returns:
        str: Formatted text.
    """
    return wrap_html(text, "pre")


def font(text, **kwargs):
    """
    Format text with specific font attributes.

    This is the shortcut to `wrap_html(text, "font", ...)`.

    Example:
        >>> from common.utilities import font
        >>> font("text", color="#0000ff")
        u'<font color="#0000ff">text</font>'

    Arguments:
        text (str): Source text.
        **kwargs: Arbitrary tag attributes.

    Returns:
        str: Formatted text.
    """
    return wrap_html(text, "font", **kwargs)


def image(src, **kwargs):
    """
    Return html code to insert an image.

    Example:
        >>> from common.utilities import image
        >>> image("filename.png", height="15")
        u'<img src="filename.png" alt="filename.png" height="15"></img>'

    Arguments:
        src (str): Image filename.
        **kwargs: Arbitrary tag attributes.

    Returns:
        str: Formatted text.
    """
    args = kwargs.copy()
    args["alt"] = kwargs.get("alt", osp.basename(src))
    return wrap_html("", "img", src=src, **args)


def href(text, url, **kwargs):
    """
    Return html code to add a hyperlink.

    Example:
        >>> from common.utilities import href
        >>> href("text", "http://code-aster.org", target="_blank")
        u'<a href="http://code-aster.org" target="_blank">text</a>'

    Arguments:
        text (str): Link's text.
        url (str): Link's URL.
        **kwargs: Arbitrary tag attributes.

    Returns:
        str: Formatted text.
    """
    return wrap_html(text, "a", href=url, **kwargs)


def div(name):
    """
    Return html code to insert an id.

    Example:
        >>> from common.utilities import div
        >>> div("anchor")
        u'<div id="anchor"></div>'

    Arguments:
        name (str): Div's text.

    Returns:
        str: Formatted text.
    """
    return wrap_html("", "div", id=name)


def is_child(child, parent):
    """
    Check if the specified *child* object belongs to given *parent*
    object.

    Arguments:
        child (QObject): Child object.
        parent (QObject): Parent object.

    Returns:
        bool: *True* if *child* is a child of *parent*; *False*
        otherwise.
    """
    res = False
    obj = child
    while obj is not None and not res:
        res = obj == parent
        obj = obj.parent()
    return res


def is_subclass(typ, pattern):
    """
    Check the `typ` is subclass of `pattern`.

    Arguments:
        typ (class): Class being checked.
        pattern (class): Parent class.

    Returns:
        bool: *True* if `typ` is subclass of `pattern`; *False* otherwise.
    """
    res = False
    try:
        if typ is not None:
            res = issubclass(typ, pattern)
    except StandardError:
        res = False
    return res


def is_contains_word(text, word):
    """
    Check if the string contains word.

    Arguments:
        text (str): Source string.
        word (str): word substring.

    Returns:
        bool: *True* if `word` is contained in `text`; *False* otherwise.
    """
    words = None
    if isinstance(word, (tuple, list)):
        words = list(word)
    else:
        words = [word]

    result = False
    if words is not None:
        for wrd in words:
            regexp = re.compile("^(.*_)?" + wrd + "(_.*)?$")
            result = regexp.match(text) is not None
            if result:
                break
    return result


def get_file_name(mode, parent, title, url, filters, suffix=None,
                  dflt_filter=None):
    """
    Show standard file dialog, to select a file to open or save.

    Arguments:
        mode (int): File mode: 0 for Save; 1 for Open.
        parent (QWidget): Parent widget.
        title (str): Dialog's title.
        url (str): Initial file path.
        filters (list[str] or str): File patterns by list or
            one pattern by string.
        suffix (Optional[str]): Default extension to be automatically
            appended to the file name. Defaults to *None*.
        dflt_filter (Optional[str]): File pattern that will be set as
            current file filter. Defaults to *None*: first pattern.

    Returns:
    str: Selected file or *None* if operation is cancelled.
    """
    dlg = Q.QFileDialog(parent)
    urls = []
    urls.append(Q.QDir.homePath())
    urls.append(osp.dirname(Q.QApplication.arguments()[0]))
    dlg.setSidebarUrls([Q.QUrl.fromLocalFile(i) for i in urls])
    acc_mode = Q.QFileDialog.AcceptOpen if mode else Q.QFileDialog.AcceptSave
    fmode = Q.QFileDialog.ExistingFile if mode else Q.QFileDialog.AnyFile
    dlg.setAcceptMode(acc_mode)
    dlg.setFileMode(fmode)
    # Uncomment below to disable using the system dialog
    # That would make ExistingFile mode effective
    #option = Q.QFileDialog.DontUseNativeDialog
    #dlg.setOption(option)
    dlg.setWindowTitle(title)
    dlg.setNameFilters(to_list(filters))
    if dflt_filter is None:
        dflt_filter = common_filters()[-1]
    dlg.selectNameFilter(dflt_filter)
    if suffix:
        dlg.setDefaultSuffix(suffix)
    dlg.selectFile(url)
    return dlg.selectedFiles()[0] if dlg.exec_() else None


def get_directory(parent, path, is_in_dir):
    """
    Show standard directory selection dialog.

    Arguments:
        parent (QWidget): Parent widget.
        path (str): Initial path.
        is_in_dir (bool): *True* for input directory, *False* for output
            directory.
    """
    title = translate("DirsPanel", "Choose input directory") if is_in_dir \
        else translate("DirsPanel", "Choose output directory")
    return Q.QFileDialog.getExistingDirectory(parent, title, path)


def connect(signal, slot, connection_type=Q.Qt.UniqueConnection):
    """
    Shortcut function for signal / slot connection.

    Arguments:
        signal (pyqtSignal): Signal object.
        slot (function): Slot function.
        connection_type (Optional[Qt.ConnectionType]): Connection type.
            Defaults to *Qt.UniqueConnection*.
    """
    if signal is not None and slot is not None:
        signal.connect(slot, connection_type)


def disconnect(signal, slot=None):
    """
    Shortcut function for signal / slot disconnection.

    If *slot* is *None*, removes all connections from *signal*.

    Arguments:
        signal (pyqtSignal): Signal object.
        slot (Optional[function]): Slot function. Defaults to *None*.
    """
    if signal is not None:
        try:
            signal.disconnect(slot)
        except TypeError: # prevent exception when there's no connection
            pass


def not_implemented(parent):
    """
    Show 'not implemented yet' message.

    Arguments:
        parent (QWidget): Parent widget.
    """
    msg = translate("AsterStudy", "Not implemented yet")
    Q.QMessageBox.information(parent, "AsterStudy", msg)


def to_words(text):
    """
    Split text to words; each word is started either from beginning of
    the text or from capital letter; words can be separated by spaces.

    Example:
        >>> from common.utilities import to_words
        >>> to_words("abc")
        ['abc']
        >>> to_words("abcDef")
        ['abc', 'Def']
        >>> to_words("Abc Def Ghi")
        ['Abc', 'Def', 'Ghi']

    Arguments:
        text (str): Text string.

    Returns:
        list[str]: List of words.

    See also:
        `from_words()`
    """
    result = []
    if re.search(r'\s', text):
        words = text.split()
        for word in words:
            result += to_words(word)
        return result
    prev = 0
    for i, letter in enumerate(text):
        if letter.isupper():
            substr = text[prev:i]
            if substr:
                result.append(substr)
                prev = i
    if prev < len(text):
        result.append(text[prev:])
    return result


def from_words(text):
    """
    Split text to words and convert back to the string where words are
    separated by spaces."

    Example:
        >>> from common.utilities import from_words
        >>> from_words("abc")
        u'abc'
        >>> from_words("abcDef")
        u'abc Def'
        >>> from_words("AbcDefGhi")
        u'Abc Def Ghi'

    Arguments:
        text (str): Text string.

    Returns:
        str: Converted string.

    See also:
        `to_words()`
    """
    return " ".join(to_words(text))


def simplify_separators(toolbar):
    """
    Hide unnecessary separators in a toolbar.

    Arguments:
        toolbar (QToolBar): Toolbar to manage.
    """
    actions = toolbar.actions()
    if actions:
        vis_action = False
        for act in actions:
            if act.isSeparator():
                act.setVisible(vis_action)
                vis_action = False
            elif act.isVisible():
                vis_action = True

        actions.reverse()

        vis_action = False
        for act in actions:
            if act.isSeparator():
                act.setVisible(vis_action)
                vis_action = False
            elif act.isVisible():
                vis_action = True


def update_visibility(widget):
    """
    Update visibility of menu or toolbar dependending on its content.

    Arguments:
        widget (QMenu, QToolBar): Menu or toolbar.
    """
    if widget is None or not hasattr(widget, "actions"):
        return

    visible = False
    for action in widget.actions():
        if not action.isSeparator() and action.isVisible():
            visible = True
            break
    if isinstance(widget, Q.QToolBar):
        simplify_separators(widget)
        widget.setVisible(visible)
        widget.toggleViewAction().setVisible(visible)
    elif isinstance(widget, Q.QMenu):
        widget.menuAction().setVisible(visible)


def hms2s(vtime):
    """
    Convert a time given in the 'H:M:S' format into seconds.

    Arguments:
        vtime (str): Time in 'H:M:S' format.

    Returns:
        int: Number of seconds.

    Raises:
        ValueError: If *vtime* is given in wrong format.
    """
    secs = 0
    stps = vtime.split(':')
    multiplier = 1
    if len(stps) > 3:
        raise ValueError(u"invalid time value : '%s'" % vtime)
    while len(stps) > 0:
        secs += int(stps.pop()) * multiplier
        multiplier = multiplier * 60
    return secs


@contextmanager
def auto_dupl_on(case, changed=True):
    """
    Context manager enabling automatic duplication.

    Arguments:
        case (Case) : Case object.
        changed (Optional[bool]): Tell if data model can be changed
            during the operation. Defaults to *True*.
    """
    if changed:
        # all contained stages are set with case as calling_case
        for stage in case.stages:
            stage.calling_case = case
        if case.model:
            case.model.auto_dupl = True
    yield
    if changed and case.model:
        case.model.auto_dupl = False


def recursive_items(dictionary):
    """
    Recursively loop on items of *dictionary* and its nested *dict* items.

    Arguments:
        dictionary (dict): Input dictionary.

    Returns:
        generator object suitable for iterating.
    """
    stack = [dictionary.items()]
    while stack:
        first = stack.pop(0)
        for key, value in first:
            if isinstance(value, dict):
                stack.append([((key, 0, ikey), ival) \
                              for ikey, ival in value.items()])
            elif isinstance(value, (list, tuple)):
                j = -1
                for i in value:
                    if isinstance(i, dict):
                        j += 1
                        stack.append([((key, j, ikey), ival) \
                                      for ikey, ival in i.items()])
            else:
                yield (key, value)


def common_filters():
    """
    Get common file filters to be used in file browsing dialogs.

    Return:
       str: Set of common file filters.
    """
    filters = []
    def _get_mask(_typs):
        _mask = " ".join(["*.%s" % i for i in _typs])
        return " (%s)" % _mask
    filters.append(translate("AsterStudy", "Med files") + \
                       _get_mask(["med", "rmed", "mmed"]))
    filters.append(translate("AsterStudy", "Other mesh files") + \
                       _get_mask(["msh", "mgib", "unv", "msup"]))
    filters.append(translate("AsterStudy", "Text files") + \
                       _get_mask(["txt", "csv", "dat"]))

    # !!! ADD NEW FILTER HERE !!!

    filters.append(translate("AsterStudy", "All files") + \
                       " (*)")
    return filters


def to_list(*args):
    """
    Return input value(s) as a list.

    Each input argument is treated as follows:

    - Tuple or list is converted to list;
    - For dict, its keys are added to result;
    - Simple value is converted to a list with a single item;
    - *None* values are ignored.

    Note:
        Treating of complex values from arguments list is not done: i.e.
        tuple of lists will not be converted to single plain list of
        items from all lists enclosed to tuple.

    Arguments:
        *args: Variable length argument list of input values.

    Returns:
        list: List created from input value(s).
    """
    result = []
    for value in args:
        if isinstance(value, (list, tuple, dict)):
            result.extend(value)
        elif value is not None:
            result.append(value)
    return [i for i in result if i is not None]


# same function exist in SyntaxUtils
def old_complex(value):
    """Convert an old-style complex."""
    if isinstance(value, (list, tuple)) and len(value) == 3:
        if value[0] == 'RI':
            value = complex(value[1], value[2])
        elif value[0] == 'MP':
            value = complex(value[1] * math.cos(value[2]),
                            value[1] * math.sin(value[2]))
    return value


def to_type(txt, typ, default=None):
    """
    Convert text to specific type.

    Example:
        >>> from common.utilities import to_type
        >>> to_type("1", float)
        1.0
        >>> to_type("1e", float) is None
        True
        >>> to_type("1e", float, 100)
        100
        >>> to_type("'1.+2j'", complex)
        (1+2j)

    Arguments:
        txt (str): Text to convert.
        typ (type): Expected result type.
        default (Optional[any]): Default value to be returned if
            conversion fails. Defaults to *None*.

    Returns:
        typ: Result of conversion (*default* if conversion fails).
    """
    value = default
    try:
        if typ is complex:
            txt = old_complex(eval(txt)) # pragma pylint: disable=eval-used
        value = typ(txt)
    except Exception: # pragma pylint: disable=broad-except
        pass
    return value


class CachedValues(object):
    """Stores some (key, value) pairs in a cache."""

    def __init__(self, size=5):
        self._size = size
        self.clear()

    def get(self, key, default=None):
        """Return a cached value or *default*."""
        return self._cache.get(key, default)

    def discard(self, key):
        """Forget the value for *key*."""
        try:
            self._cache.pop(key)
        except KeyError:
            pass

    def set(self, key, value):
        """Store a value in the cache."""
        self.discard(key)
        # limit size of cache
        if len(self._cache) > self._size:
            self._cache.popitem(last=False)
        self._cache[key] = value

    def clear(self):
        """Empty the cache."""
        self._cache = OrderedDict()


class LogFiles(object):
    """Helper class to deal with global log files.

    Attributes:
        cache (dict): Dict of file objects.
    """
    cache = {}
    _user = getpass.getuser()

    @classmethod
    def file(cls, name="main", nocache=False):
        """Returns the log file to use."""
        if not nocache and cls.cache.get(name) is not None:
            return cls.cache[name]
        logfile = osp.join(tempfile.gettempdir(),
                           'asterstudy-{0}-{1}.log'.format(name, cls._user))
        if osp.isfile(logfile) and not os.access(logfile, os.W_OK):
            prefix = 'asterstudy-{0}-'.format(name)
            logfile = unicode(tempfile.mkstemp(prefix=prefix,
                                               suffix='.log')[1])
        # force reset
        fileobj = open(logfile, 'wb')
        cls.cache[name] = fileobj
        return fileobj

    @classmethod
    def filename(cls, name="main", nocache=False):
        """Returns the name of a log file to use."""
        fileobj = cls.file(name, nocache)
        return fileobj.name
