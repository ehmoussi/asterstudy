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
Additional specific widgets for Parameters Panel
------------------------------------------------

Implementation of the Parameters panel specific widgets.

"""

from __future__ import unicode_literals

import types

import numpy

from PyQt5.Qt import (Qt, QGridLayout, QLabel, QPainter, QPainterPath, QWidget,
                      QRegExp, QBitmap, QSizePolicy, QRect, QLineEdit, QSize,
                      QVBoxLayout, pyqtSignal, pyqtSlot, QResizeEvent, QIcon,
                      QBoxLayout, QToolButton, QPixmap)

import matplotlib
matplotlib.use("Qt5Agg")
# pragma pylint: disable=wrong-import-position
from matplotlib import pyplot
from matplotlib.backend_bases import key_press_handler
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)

from common import (debug_mode, is_subclass, to_list, translate,
                    font, bold, italic, preformat)

from datamodel import CATA

from gui import translate_rule
from gui.widgets import ElidedLabel, ElidedButton

from .basic import ContentData, Options

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class ParameterLabel(QWidget, ContentData):
    """Helper class to display parameter's name."""

    clicked = pyqtSignal()

    def __init__(self, path, rules, parent=None):
        """
        Create widget.

        Arguments:
            path (ParameterPath): Keyword's path.
            rules (list[ParameterRuleItem]): Keyword's rules.
            parent (Optional[QWidget]): Parent widget.
        """
        super(ParameterLabel, self).__init__(parent)

        self._path = path
        self._rules = rules

        base = QVBoxLayout(self)
        base.setSpacing(0)
        base.setContentsMargins(0, 0, 0, 0)

        self._titlelabel = ElidedLabel("", self)
        self._contentslabel = ElidedLabel("", self)
        base.addWidget(self._titlelabel)
        base.addWidget(self._contentslabel)

        self._titlelabel.setObjectName(path.name() + '_title')
        self._contentslabel.setObjectName(path.name() + '_content')

        self.updateTranslations()
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding,
                                       QSizePolicy.Preferred))

        contfont = self._contentslabel.font()
        contfont.setPixelSize(10)
        self._contentslabel.setFont(contfont)

        contpal = self._contentslabel.palette()
        contpal.setColor(self._contentslabel.foregroundRole(), Qt.darkBlue)
        self._contentslabel.setPalette(contpal)

        self.setContents(None, "none")

    def updateTranslations(self):
        """
        Update translation.
        """
        if not self.isVisible():
            return

        path = self.path()
        name = path.name()
        command = path.command()

        # get business-oriented translation if present and set label's text
        if name.isdigit():
            self._titlelabel.setText("[%s]" % name)
            name = path.parentPath().name()
            translation = Options.translate_command(command.title, name)
        else:
            translation = Options.translate_command(command.title, name)
            self._titlelabel.setText(translation)

        # compute tooltip / what's this base info
        if translation != name:
            wttext = italic(translation) + " ({})".format(bold(name))
        else:
            wttext = bold(name)
        wttext = preformat(wttext)

        # set content
        contstr = ""
        if self.contentsMode() != "none" and \
                self.contentsValue() is not None:
            contstr = self._contentsText(self.path())
        self._contentslabel.setText(contstr)
        self._contentslabel.setVisible(len(self._contentslabel.text()) > 0)

        # set tooltip
        tooltip = wttext
        if debug_mode():
            tooltip += "<br>"
            tooltip += path.path()

        contstr = ""
        if self.contentsValue() is not None:
            contstr = self._contentsText(self.path(), None, "parameters")
        if len(contstr) > 0:
            tooltip += "<hr>" + contstr

        self.setToolTip(tooltip)

        # set what's this
        # - add native doc string if present
        docs = path.keyword().udocstring
        if len(docs):
            wttext = wttext + "<hr>" + docs

        # - add value type and default value information if present
        typeinfo = self._typeInformation()
        if len(typeinfo):
            listinfo = self._listInformation()
            if len(listinfo):
                typeinfo += "<br>" + listinfo
            wttext = wttext + "<hr>" + typeinfo
        definfo = self._defaultInformation()
        if len(definfo):
            wttext = wttext + "<br>" + definfo

        # - add rules description if present
        rules = self.rules()
        if rules is not None and len(rules) > 0:
            rulelines = []
            for rule in rules:
                # translate rule
                line = bold(translate_rule(rule.itemName()))
                kw_list = []
                for kword in rule.ruleKeywords():
                    if name == kword:
                        kw_list.append(font(kword, color="#0000ff"))
                    else:
                        kw_list.append(kword)
                line = line + ": " + ", ".join(kw_list)
                rulelines.append(line)
            wttext = wttext + "<hr>" + "<br>".join(rulelines)

        # - finally assign what's this info
        self.setWhatsThis(wttext)

    def path(self):
        """
        Get path assigned to the label.

        Returns:
            ParameterPath: Parameter path.
        """
        return self._path

    def rules(self):
        """
        Get rules assigned to the label.

        Returns:
            list[ParameterRuleItem]: Parameter rules.
        """
        return self._rules

    def match(self, text):
        """
        Check if label matches search criterion.

        Arguments:
            text (str): Regular expression.

        Returns:
            bool: *True* if label matches search criterion; *False*
            otherwise.
        """
        regex = QRegExp(text, Qt.CaseInsensitive)
        return regex.indexIn(self._titlelabel.text()) != -1 or \
            regex.indexIn(self.path().name()) != -1

    def minimumSizeHint(self):
        """
        Get size hint for the label.

        Returns:
            QSize: Label's size hint.
        """
        size = super(ParameterLabel, self).minimumSizeHint()
        if self.path().name().isdigit():
            size.setWidth(self.fontMetrics().width("[000]"))
        else:
            size.setWidth(100)
        return size

    def sizeHint(self):
        """
        Get size hint for the label.

        Returns:
            QSize: Label's size hint.
        """
        size = super(ParameterLabel, self).sizeHint()
        if self.path().name().isdigit():
            size.setWidth(self.fontMetrics().width("[000]"))
        else:
            size.setWidth(100)
        return size

    # pragma pylint: disable=unused-argument
    def mousePressEvent(self, event):
        """
        Reimplemented event to link the QLabel with the related radiobutton or
        checkbox.
        """
        self.clicked.emit()

    def showEvent(self, e):
        """
        Reimplemented event to update messages when label is shown.
        """
        super(ParameterLabel, self).showEvent(e)
        self.updateTranslations()

    def _typeInformation(self):
        """
        Gets the information text about keyword type.
        """
        inflist = []
        kword = self.path().keyword()
        if kword is not None:
            kwtypelist = []
            kwdef = kword.definition
            enum = kwdef.get('into') is not None
            if enum and sorted(kwdef.get('into')) == ["NON", "OUI"]:
                txt = "'%s'/'%s'" % (bold(translate("ParameterPanel", "Yes")),
                                     bold(translate("ParameterPanel", "No")))
                inflist.append(txt)
            elif kwdef.get('typ') is not None:
                kwtypelist = to_list(kwdef.get('typ'))

            for kwtype in kwtypelist:
                if kwtype is None:
                    continue

                if kwtype == 'I':
                    txt = bold(translate("ParameterPanel", "integer"))
                    lim = self._numberLimitsInfo(kwdef.get('val_min'),
                                                 kwdef.get('val_max'))
                    if len(lim):
                        txt += " " + lim
                elif kwtype == 'R':
                    txt = bold(translate("ParameterPanel", "float"))
                    lim = self._numberLimitsInfo(kwdef.get('val_min'),
                                                 kwdef.get('val_max'))
                    if len(lim):
                        txt += " " + lim
                elif kwtype == 'TXM':
                    txt = bold(translate("ParameterPanel", "string"))
                elif is_subclass(kwtype, CATA.package('DataStructure').CO):
                    txt = bold(translate("ParameterPanel", "macro name"))
                elif isinstance(kwtype, (types.TypeType, types.ClassType)):
                    txt = translate("ParameterPanel", "object with type")
                    txt += bold(" '%s'" % kwtype.__name__)
                else:
                    txt = bold(str(kwtype))

                if len(txt):
                    if enum:
                        txt += " (%s)" % italic(translate("ParameterPanel",
                                                          "enumerated"))
                    inflist.append(txt)
        info = ""
        if len(inflist):
            islist = self.path().isKeywordSequence() and \
                not self.path().isInSequence()
            prefix = translate("ParameterPanel", "List with types") \
                if islist else translate("ParameterPanel", "Value types")
            info = prefix + ": " + ", ".join(inflist)
        return info

    def _listInformation(self):
        """
        Gets the information text about keyword type list limits.
        """
        info = ""
        if self.path().isKeywordSequence() and \
                not self.path().isInSequence():
            kword = self.path().keyword()
            if kword is not None:
                kwdef = kword.definition
                min_limit = kwdef.get('min')
                max_limit = kwdef.get('max') \
                    if kwdef.get('max') != '**' else None
                lim = self._numberLimitsInfo(min_limit, max_limit, True, False)
                if len(lim):
                    info = " "  + translate("ParameterPanel",
                                            "List length should be") + lim
        return info

    # pragma pylint: disable=no-self-use
    def _numberLimitsInfo(self, vmin, vmax, inclusive=True, allowrange=True):
        """
        Format min, max limits information into human readable string.
        """
        txt = ""
        if allowrange and vmin is not None and vmax is not None:
            txt += " " + translate("ParameterPanel", "in range")
            if inclusive:
                txt += " [%s, %s]" % (italic(bold(str(vmin))),
                                      italic(bold(str(vmax))))
            else:
                txt += " (%s, %s)" % (italic(bold(str(vmin))),
                                      italic(bold(str(vmax))))
        else:
            if vmin is not None:
                if inclusive:
                    txt += " " + translate("ParameterPanel", "not less than")
                else:
                    txt += " " + translate("ParameterPanel", "greater than")
                txt += " " + italic(bold(str(vmin)))
            if vmax is not None:
                if len(txt):
                    txt += " " + translate("ParameterPanel", "and")
                if inclusive:
                    txt += " " + translate("ParameterPanel",
                                           "not greater than")
                else:
                    txt += " " + translate("ParameterPanel", "less than")
                txt += " " + italic(bold(str(vmax)))
        return txt

    def _defaultInformation(self):
        info = ""
        if not self.path().isKeywordSequence() or \
                self.path().isInSequence():
            kword = self.path().keyword()
            if kword is not None:
                if hasattr(kword, 'hasDefaultValue') \
                        and kword.hasDefaultValue():
                    info = translate("ParameterPanel", "Default value: ") + \
                        italic(bold(str(kword.defaultValue())))
        return info

    def _updateContents(self):
        """
        Updates the contents string.
        """
        self.updateTranslations()


class ParameterButton(ElidedButton, ContentData):
    """Helper class to display parameter's name."""

    def __init__(self, path, text, parent=None):
        """
        Create widget.

        Arguments:
            path (ParameterPath): Keyword's path.
            text (str): Button text.
            parent (Optional[QWidget]): Parent widget.
        """
        super(ParameterButton, self).__init__(text, parent)
        self._path = path
        self._text = text

    def _updateContents(self):
        """
        Updates the contents string.
        """
        content = False
        self.setToolTip("")
        text = self._text

        mode = self.contentsMode()
        if mode is not None and mode != "none" and \
                self.contentsValue() is not None:
            content = True
            text = self._contentsText(self._path)
        contpal = self.palette()
        contpal.setColor(self.foregroundRole(), Qt.darkBlue \
                             if content else Qt.black)
        self.setPalette(contpal)

        self.setText(text)
        self.setToolTip(text)


class ParameterTitle(QLineEdit):
    """Helper class to show a `path` for currently edited parameter."""

    def __init__(self, parent=None):
        """
        Create widget.

        Arguments:
            parent (Optional[QWidget]): Parent widget.
        """
        QLineEdit.__init__(self, parent)
        self.setReadOnly(True)
        self.setFrame(False)

    def setTitle(self, names):
        """
        Set the path to the widget.

        Arguments:
           names (list[str]): Path components.
        """
        self.setText(" > ".join(names))
        self.end(False)


class ParameterItemHilighter(QWidget):
    """
    Frame that highlight the item in view
    """
    def __init__(self, rect, parent=None):
        super(ParameterItemHilighter, self).__init__(parent)
        self.setGeometry(rect)

    def paintEvent(self, pevent):
        """
        Paint event handler.
        Reimplemented for drawing rule group frames.
        """
        super(ParameterItemHilighter, self).paintEvent(pevent)

        painter = QPainter(self)
        rect = QRect(0, 0, self.width(), self.height())
        rect.adjust(1, 1, -1, -1)
        painter.setPen(Qt.red)
        painter.drawRect(rect)


class ParameterBaloon(QWidget):
    """
    Frame that highlight the item in view
    """
    def __init__(self, parent=None):
        super(ParameterBaloon, self).__init__(parent, Qt.ToolTip)

        layout = QGridLayout(self)
        layout.setSizeConstraint(QGridLayout.SetFixedSize)
        self._title = QLabel(self)
        layout.addWidget(self._title, 0, 0)

        line = QLabel(self)
        line.setFrameStyle(QLabel.Plain | QLabel.HLine)
        layout.addWidget(line, 1, 0)

        self._message = QLabel(self)
        layout.addWidget(self._message, 2, 0)

        self.setContentsMargins(5, 5, 5, 20)

    def title(self):
        """Returns title."""
        return self._title.text()

    def setTitle(self, txt):
        """Sets title."""
        self._title.setText(txt)
        self.updateGeometry()
        self.adjustSize()

    def message(self):
        """Returns message."""
        return self._message.text()

    def setMessage(self, txt):
        """Sets message."""
        self._message.setText(txt)
        self.updateGeometry()
        self.adjustSize()

    def setPositon(self, pos):
        """Sets the position."""
        self.move(pos.x() - self.sizeHint().width() / 2,
                  pos.y() - self.sizeHint().height())

    def resizeEvent(self, event):
        """Updates contour after resize."""
        super(ParameterBaloon, self).resizeEvent(event)
        self._updateCountour()

    def paintEvent(self, event):
        """Paint contour."""
        super(ParameterBaloon, self).paintEvent(event)
        ppath = self._contour()
        painter = QPainter(self)
        painter.fillPath(ppath, Qt.white)
        painter.setPen(Qt.black)
        painter.drawPath(ppath)

    def _updateCountour(self):
        """Update countour."""
        ppath = self._contour()

        bmp = QBitmap(self.size())
        bmp.fill(Qt.color0)
        painter = QPainter(bmp)
        painter.fillPath(ppath, Qt.color1)
        painter.end()
        self.setMask(bmp)

    def _contour(self):
        """Returns contour path."""
        ppath = QPainterPath()
        rect = self.contentsRect()
        margin = 5
        ppath.addRoundedRect(rect.left() - margin, rect.top() - margin,
                             rect.width() + 2 * margin,
                             rect.height() + 2 * margin, 15, 15)

        arrowpath = QPainterPath()
        arrowpath.moveTo(rect.center().x(), self.height())
        arrowpath.lineTo(rect.center().x() - 10, rect.bottom())
        arrowpath.lineTo(rect.center().x() + 10, rect.bottom())
        arrowpath.lineTo(rect.center().x(), self.height())

        ppath = ppath.united(arrowpath)
        return ppath


class SpinWidget(QWidget):
    """Spin buttons for up/down (increase/decrease) actions."""

    class SpinType(object):
        """Enumeration for spin types"""
        Decrease = 0
        Increase = 1
        Up = Decrease
        Down = Increase

    class Button(QToolButton):
        """Internal button class for spin"""
        def __init__(self, parent=None):
            super(SpinWidget.Button, self).__init__(parent)

        def sizeHint(self):
            """Reimplemented for internal reason"""
            sz = super(SpinWidget.Button, self).sizeHint()
            if self.parentWidget().layout().direction() \
                    == QBoxLayout.TopToBottom:
                sz.setHeight(sz.height() / 2)
            return sz

        def minimuSizeHint(self):
            """Reimplemented for internal reason"""
            sz = super(SpinWidget.Button, self).minimuSizeHint()
            if self.parentWidget().layout().direction() \
                    == QBoxLayout.TopToBottom:
                sz.setHeight(sz.height() / 2)
            return sz

    clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super(SpinWidget, self).__init__(parent)

        base = QBoxLayout(QBoxLayout.TopToBottom, self)
        base.setContentsMargins(0, 0, 0, 0)
        base.setSpacing(0)

        self._dec = SpinWidget.Button(self)
        self._dec.clicked.connect(self._onDecreaseClicked)
        self._dec.setObjectName("Decrease")

        self._inc = SpinWidget.Button(self)
        self._inc.clicked.connect(self._onIncreaseClicked)
        self._inc.setObjectName("Increase")

        base.addWidget(self._dec)
        base.addWidget(self._inc)

        self._updateButtons()

    def isSpinEnabled(self, spin):
        """
        Gets the enable/disable state of specified spin button

        Arguments:
            spin (SpinType): Spin button type

        Returns:
            bool: Button enable state
        """
        btn = self._spinButton(spin)
        return btn.isEnabled() if btn is not None else False

    def setSpinEnabled(self, spin, value):
        """
        Sets the enable/disable state of specified spin button

        Arguments:
            spin (SpinType): Spin button type
            value (bool): Button enable state
        """
        btn = self._spinButton(spin)
        if btn is not None:
            btn.setEnabled(value)

    def orientation(self):
        """
        Gets the orientation of spin buttons in control

        Returns:
            Qt.Orientation: Control orientation
        """
        direct = self.layout().direction()
        return Qt.Horizontal if direct == QBoxLayout.LeftToRight \
            else Qt.Vertical

    def setOrientation(self, orient):
        """
        Sets the orientation of spin buttons in control


        Arguments:
            orient (Qt.Orientation): Control orientation
        """
        self.layout().setDirection(QBoxLayout.LeftToRight \
                                       if orient == Qt.Horizontal else \
                                       QBoxLayout.TopToBottom)
        self._updateButtons()

    def _onDecreaseClicked(self):
        """
        Invoked when decrease button clicked.
        """
        self.clicked.emit(self.SpinType.Decrease)

    def _onIncreaseClicked(self):
        """
        Invoked when increase button clicked.
        """
        self.clicked.emit(self.SpinType.Increase)

    def _updateButtons(self):
        """
        Update button icons.
        """
        sz = QSize(32, 32)
        if self.orientation() == Qt.Vertical:
            sz.setHeight(sz.height() / 2)
        pix = QPixmap(sz)
        pix.fill(Qt.transparent)
        pnt = QPainter(pix)
        pnt.setPen(Qt.black)

        path = QPainterPath()
        arrowwidth = pix.width() - 2 * 2
        arrowheight = min(arrowwidth / 2, pix.height() - 2 * 2)
        path.moveTo((pix.width() - arrowwidth) / 2,
                    (pix.height() - arrowheight) / 2)
        path.lineTo((pix.width() + arrowwidth) / 2,
                    (pix.height() - arrowheight) / 2)
        path.lineTo(pix.width() / 2, (pix.height() + arrowheight) / 2)
        path.lineTo((pix.width() - arrowwidth) / 2,
                    (pix.height() - arrowheight) / 2)
        pnt.fillPath(path, Qt.black)
        pnt.end()

        self._inc.setIcon(QIcon(pix))
        self._dec.setIcon(QIcon(QPixmap.fromImage(pix.toImage().mirrored())))

    def _spinButton(self, spin):
        """
        Gets the spin button by specified type.
        """
        btn = None
        if spin == self.SpinType.Decrease:
            btn = self._dec
        elif spin == self.SpinType.Increase:
            btn = self._inc
        return btn


class PlotWidget(QWidget):
    """Plot widget to draw function curve."""

    class PlotCanvas(FigureCanvas):
        """Canvas the figure renders into."""

        def resizeEvent(self, event):
            """Overridden in order to correct negative size in the event."""
            w = event.size().width()
            h = event.size().height()
            FigureCanvas.resizeEvent(self, QResizeEvent(QSize(abs(w), abs(h)),
                                                        event.oldSize()))


    def __init__(self, view, parent=None):
        super(PlotWidget, self).__init__(parent)
        self._view = view
        self.createPlot()
        self._view.functionChanged.connect(self.updatePlot)

    def setVisible(self, vis):
        """Show/hide the plot widget."""
        super(PlotWidget, self).setVisible(vis)
        self.updatePlot()

    @pyqtSlot()
    def updatePlot(self):
        """Is called to update plot with table data."""
        if self.isVisible():
            self.onDraw(self._view)

    def createPlot(self):
        """Creates plot and toolbar widgets"""
        self.fig = pyplot.figure()
        self.axes = self.fig.add_subplot(111)
        pyplot.subplots_adjust(bottom=0.15)

        self.canvas = self.PlotCanvas(self.fig)
        self.canvas.setParent(self)
        self.canvas.setFocusPolicy(Qt.StrongFocus)
        self.canvas.setFocus()

        self.mpl_toolbar = NavigationToolbar(self.canvas, self)

        self.canvas.mpl_connect('key_press_event', self.onKeyPress)

        vbox = QVBoxLayout()
        vbox.addWidget(self.mpl_toolbar)
        vbox.addWidget(self.canvas)  # the matplotlib canvas
        self.setLayout(vbox)

    @staticmethod
    def getData(table_item):
        """Gets table item (x, y) values."""
        values = table_item.itemValue()
        nb_cols = table_item.tableDefColumnCount()
        x = y = None
        if values:
            if nb_cols == 1:
                x = values
            else:
                # convert [x1, y1, x2, y2] => [[x1, x2], [y1, y2]]
                values = numpy.reshape(values, (2, -1), order='F')
                x = values[0]
                y = values[1]
        return x, y

    @pyqtSlot()
    def onDraw(self, table_item):
        """Draws table data on plot."""
        x, y = self.getData(table_item)
        self.axes.cla()
        if y is not None:
            self.axes.plot(x, y, 'ko-')
        else:
            self.axes.plot(x, 'ko-')

        xlabel = ''
        ylabel = ''
        if table_item is not None:
            labels = table_item.headerLabels()
            if len(labels) > 1:
                xlabel = labels.pop(0)
            if len(labels):
                ylabel = labels.pop(0)
        self.axes.set_xlabel(xlabel)
        self.axes.set_ylabel(ylabel)
        self.canvas.draw()

    @pyqtSlot()
    def onKeyPress(self, event):
        """Implements the default mpl key press events described at
            http://matplotlib.org/users/navigation_toolbar.html\
            #navigation-keyboard-shortcuts"""
        key_press_handler(event, self.canvas, self.mpl_toolbar)
