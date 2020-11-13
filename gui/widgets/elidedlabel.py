# -*- coding: utf-8 -*-

# Copyright 2016-2017 EDF R&D
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
Elided label
------------

The module implements label that shows elided text.

For more details refer to *ElidedLabel* class.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

__all__ = ["ElidedLabel"]

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class WrapStyle(Q.QStyle):
    """Override given style behaviour."""

    def __init__(self, style):
        """
        Create style wrapper.

        Arguments:
            style (QStyle): Style being wrapped.
        """
        super(WrapStyle, self).__init__()
        self._base_style = style

    def drawComplexControl(self, control, option, painter, widget=None):
        """See Qt5 documentation for `QStyle` class."""
        if self._base_style is not None:
            self._base_style.drawComplexControl(control, option,
                                                painter, widget)
        else:
            super(WrapStyle, self).\
                drawComplexControl(control, option, painter, widget)

    def drawControl(self, element, option, painter, widget=None):
        """See Qt5 documentation for `QStyle` class."""
        if self._base_style is not None:
            self._base_style.drawControl(element, option, painter, widget)
        else:
            super(WrapStyle, self).\
                drawControl(element, option, painter, widget)

    def drawItemText(self, painter, rect, flags, pal, enabled,
                     text, textRole=Q.QPalette.NoRole):
        """See Qt5 documentation for `QStyle` class."""
        if self._base_style is not None:
            self._base_style.drawItemText(painter, rect, flags, pal,
                                          enabled, text, textRole)
        else:
            super(WrapStyle, self).\
                drawItemText(painter, rect, flags, pal,
                             enabled, text, textRole)

    def drawItemPixmap(self, painter, rectangle, alignment, pixmap):
        """See Qt5 documentation for `QStyle` class."""
        if self._base_style is not None:
            self._base_style.drawItemPixmap(painter, rectangle,
                                            alignment, pixmap)
        else:
            super(WrapStyle, self).\
                drawItemPixmap(painter, rectangle, alignment, pixmap)

    def drawPrimitive(self, element, option, painter, widget=None):
        """See Qt5 documentation for `QStyle` class."""
        if self._base_style is not None:
            self._base_style.drawPrimitive(element, option, painter, widget)
        else:
            super(WrapStyle, self).\
                drawPrimitive(element, option, painter, widget)

    def generatedIconPixmap(self, iconMode, pixmap, option):
        """See Qt5 documentation for `QStyle` class."""
        res = None
        if self._base_style is not None:
            res = self._base_style.generatedIconPixmap(iconMode,
                                                       pixmap, option)
        else:
            res = super(WrapStyle, self).\
                generatedIconPixmap(iconMode, pixmap, option)
        return res

    def hitTestComplexControl(self, control, option, position, widget=None):
        """See Qt5 documentation for `QStyle` class."""
        res = None
        if self._base_style is not None:
            res = self._base_style.hitTestComplexControl(control, option,
                                                         position, widget)
        else:
            res = super(WrapStyle, self).\
                hitTestComplexControl(control, option, position, widget)
        return res

    def itemPixmapRect(self, rectangle, alignment, pixmap):
        """See Qt5 documentation for `QStyle` class."""
        res = None
        if self._base_style is not None:
            res = self._base_style.itemPixmapRect(rectangle, alignment, pixmap)
        else:
            res = super(WrapStyle, self).\
                itemPixmapRect(rectangle, alignment, pixmap)
        return res

    def itemTextRect(self, metrics, rectangle, alignment, enabled, text):
        """See Qt5 documentation for `QStyle` class."""
        res = None
        if self._base_style is not None:
            res = self._base_style.itemTextRect(metrics, rectangle,
                                                alignment, enabled, text)
        else:
            res = super(WrapStyle, self).\
                itemTextRect(metrics, rectangle, alignment, enabled, text)
        return res

    def layoutSpacing(self, control1, control2,
                      orientation, option=None, widget=None):
        """See Qt5 documentation for `QStyle` class."""
        res = None
        if self._base_style is not None:
            res = self._base_style.layoutSpacing(control1, control2,
                                                 orientation, option, widget)
        else:
            res = super(WrapStyle, self).\
                layoutSpacing(control1, control2, orientation, option, widget)
        return res

    def pixelMetric(self, metric, option=None, widget=None):
        """See Qt5 documentation for `QStyle` class."""
        res = None
        if self._base_style is not None:
            res = self._base_style.pixelMetric(metric, option, widget)
        else:
            res = super(WrapStyle, self).\
                pixelMetric(metric, option, widget)
        return res

    def sizeFromContents(self, ctype, option, contentsSize, widget=None):
        """See Qt5 documentation for `QStyle` class."""
        res = None
        if self._base_style is not None:
            res = self._base_style.sizeFromContents(ctype, option,
                                                    contentsSize, widget)
        else:
            res = super(WrapStyle, self).\
                sizeFromContents(ctype, option, contentsSize, widget)
        return res

    def standardIcon(self, standardIcon, option=None, widget=None):
        """See Qt5 documentation for `QStyle` class."""
        res = None
        if self._base_style is not None:
            res = self._base_style.standardIcon(standardIcon, option, widget)
        else:
            res = super(WrapStyle, self).\
                standardIcon(standardIcon, option, widget)
        return res

    def standardPalette(self):
        """See Qt5 documentation for `QStyle` class."""
        res = None
        if self._base_style is not None:
            res = self._base_style.standardPalette()
        else:
            res = super(WrapStyle, self).standardPalette()
        return res

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        """See Qt5 documentation for `QStyle` class."""
        res = None
        if self._base_style is not None:
            res = self._base_style.styleHint(hint, option, widget, returnData)
        else:
            res = super(WrapStyle, self).\
                styleHint(hint, option, widget, returnData)
        return res

    def subControlRect(self, control, option, subControl, widget=None):
        """See Qt5 documentation for `QStyle` class."""
        res = None
        if self._base_style is not None:
            res = self._base_style.subControlRect(control, option,
                                                  subControl, widget)
        else:
            res = super(WrapStyle, self).\
                subControlRect(control, option, subControl, widget)
        return res

    def subElementRect(self, element, option, widget=None):
        """See Qt5 documentation for `QStyle` class."""
        res = None
        if self._base_style is not None:
            res = self._base_style.subElementRect(element, option, widget)
        else:
            res = super(WrapStyle, self).\
                subElementRect(element, option, widget)
        return res

    def polish(self, obj):
        """See Qt5 documentation for `QStyle` class."""
        if self._base_style is not None:
            self._base_style.polish(obj)
        else:
            super(WrapStyle, self).polish(obj)

    def unpolish(self, obj):
        """See Qt5 documentation for `QStyle` class."""
        if self._base_style is not None:
            self._base_style.unpolish(obj)
        else:
            super(WrapStyle, self).unpolish(obj)


class Style(WrapStyle):
    """Override drawItemText() behaviour."""

    def drawItemText(self, painter, rect, flags, pal, enabled,
                     text, textRole=Q.QPalette.NoRole):
        """Redefined from QStyle."""
        astr = Q.QFontMetrics(painter.font()).\
            elidedText(text, Q.Qt.ElideRight, rect.width())
        super(Style, self).drawItemText(painter, rect, flags,
                                        pal, enabled, astr,
                                        textRole)


class ElidedLabel(Q.QLabel):
    """Label with possibility to display long text elided."""

    def __init__(self, text, parent=None):
        """
        Create label.

        Arguments:
            text (str): Label's text.
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
        """
        super(ElidedLabel, self).__init__(parent)
        self.setTextFormat(Q.Qt.PlainText)
        clrflags = Q.Qt.TextSelectableByMouse | Q.Qt.TextSelectableByKeyboard
        self.setTextInteractionFlags(self.textInteractionFlags() & ~clrflags)
        self.setStyle(Style(self.style()))
        self.setText(text)
