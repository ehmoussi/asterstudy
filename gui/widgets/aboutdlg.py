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
About dialog
------------

The module implements *About* dialog for AsterStudy application.

For more details refer to *AboutDlg* class.

"""

from __future__ import unicode_literals

import os

from PyQt5 import Qt as Q

from common import CFG, italic, load_pixmap, translate, version, wrap_html

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class AboutDlg(Q.QDialog):
    """About dialog box of AsterStudy application."""

    def __init__(self, parent=None):
        """
        Create dialog.

        Arguments:
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
        """
        super(AboutDlg, self).__init__(parent)
        self.setModal(True)
        text = translate("AboutDlg", "About {}").format("AsterStudy")
        self.setWindowTitle(text)

        icon_lbl = Q.QLabel(self)
        title_lbl = Q.QLabel(self)
        version_lbl = Q.QLabel(self)
        description_lbl = Q.QLabel(self)
        license_lbl = Q.QLabel(self)
        credits_lbl = Q.QLabel(self)
        copyright_lbl = Q.QLabel(self)
        self.info_te = Q.QTextEdit(self)
        ok_btn = Q.QPushButton(self)

        main_wg = Q.QWidget(self)
        info_wg = Q.QWidget(self)

        hlayout = Q.QHBoxLayout()
        hlayout.addWidget(license_lbl)
        hlayout.addWidget(credits_lbl)

        glayout = Q.QGridLayout(main_wg)
        glayout.setContentsMargins(0, 0, 0, 0)
        glayout.addWidget(icon_lbl, 1, 1, 5, 1)
        glayout.addWidget(title_lbl, 1, 2)
        glayout.addWidget(version_lbl, 2, 2)
        glayout.addWidget(description_lbl, 4, 2)
        glayout.addLayout(hlayout, 6, 1, 1, 2)
        glayout.addWidget(copyright_lbl, 7, 0, 1, 4)
        glayout.setRowMinimumHeight(0, 10)
        glayout.setRowMinimumHeight(3, 10)
        glayout.setRowMinimumHeight(5, 20)
        glayout.setRowStretch(5, 10)
        glayout.setRowMinimumHeight(7, 40)
        glayout.setColumnMinimumWidth(0, 10)
        glayout.setColumnMinimumWidth(3, 10)

        hlayout = Q.QHBoxLayout()
        hlayout.addStretch()
        hlayout.addWidget(ok_btn)
        hlayout.addStretch()

        vlayout = Q.QVBoxLayout(info_wg)
        vlayout.addWidget(self.info_te)
        vlayout.addLayout(hlayout)

        slayout = Q.QStackedLayout()
        slayout.addWidget(main_wg)
        slayout.addWidget(info_wg)

        self.setLayout(slayout)

        pixmap = load_pixmap("asterstudy.png")
        icon_lbl.setPixmap(pixmap)
        icon_lbl.setFixedSize(pixmap.size()*1.2)
        icon_lbl.setAlignment(Q.Qt.AlignCenter)
        title_lbl.setText(wrap_html("AsterStudy", "h1"))
        text = translate("AboutDlg", "Version: {}").format(version())
        version_lbl.setText(wrap_html(text, "h4"))
        text = translate("AboutDlg", "GUI framework for {code_aster}")
        text = text.format(code_aster=wrap_html("code_aster", "a",
                                                href="code_aster"))
        description_lbl.setText(wrap_html(text, "h3"))
        description_lbl.setTextInteractionFlags(Q.Qt.LinksAccessibleByMouse)
        description_lbl.linkActivated.connect(self._browseCodeAster)
        text = translate("AboutDlg", "License Information")
        license_lbl.setText(wrap_html(text, "a", href="license"))
        license_lbl.setAlignment(Q.Qt.AlignCenter)
        license_lbl.setTextInteractionFlags(Q.Qt.LinksAccessibleByMouse)
        license_lbl.linkActivated.connect(self._showLicense)
        text = translate("AboutDlg", "Credits")
        credits_lbl.setText(wrap_html(text, "a", href="credits"))
        credits_lbl.setAlignment(Q.Qt.AlignCenter)
        credits_lbl.setTextInteractionFlags(Q.Qt.LinksAccessibleByMouse)
        credits_lbl.linkActivated.connect(self._showCredits)
        text = "Copyright 2016 EDF R&D"
        copyright_lbl.setText(italic(text))
        copyright_lbl.setAlignment(Q.Qt.AlignCenter)
        self.info_te.setReadOnly(True)
        self.info_te.setMinimumWidth(450)
        ok_btn.setText(translate("AsterStudy", "&OK"))
        ok_btn.clicked.connect(self._showMain)

        palette = self.palette()
        palette.setColor(Q.QPalette.Window, Q.QColor("#f7f7f7"))
        self.setPalette(palette)
        palette.setColor(Q.QPalette.Window, Q.QColor("#ebebeb"))
        copyright_lbl.setPalette(palette)
        copyright_lbl.setAutoFillBackground(True)

        self.resize(self.minimumSizeHint())

    def _showLicense(self):
        """
        Called when *License Information* link is activated.
        Shows license info.
        """
        self._showFile(os.path.join(CFG.docdir, "COPYING"))

    def _showCredits(self):
        """
        Called when *Credits* link is activated.
        Shows credits info.
        """
        self._showFile(os.path.join(CFG.docdir, "AUTHORS"))

    def _browseCodeAster(self): # pragma pylint: disable=no-self-use
        """
        Called when *code_aster* link is activated.
        Opens web browser at *code_aster* page.
        """
        Q.QDesktopServices.openUrl(Q.QUrl("http://www.code-aster.org"))

    def _showMain(self):
        """
        Called when *OK* button is pressed.
        Shows base information.
        """
        self.layout().setCurrentIndex(0)

    def _showFile(self, file_name):
        """
        Display a information sub-window listing the content of
        specified file.

        Arguments:
            file_name (str): Path to the file.
        """
        info_file = Q.QFile(file_name)
        if not info_file.open(Q.QFile.ReadOnly):
            return
        stream = Q.QTextStream(info_file)
        info = stream.readAll()
        info_file.close()
        self.info_te.setText(info)
        self.layout().setCurrentIndex(1)
