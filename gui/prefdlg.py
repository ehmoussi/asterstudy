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
Preferences dialog
------------------

This module implements `Preferences` dialog for AsterGui standalone
application.

"""

from __future__ import unicode_literals

from PyQt5 import Qt as Q

from common import connect, load_icon, translate
from . behavior import behavior
from . widgets import CatalogsView, Dialog, FontWidget
from . prefmanager import ignore_user_values

__all__ = ["PrefDlg"]

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class PrefDlg(Dialog):
    """Preferences dialog."""

    last_tab = 0

    def __init__(self, astergui):
        """
        Create dialog.

        Arguments:
            astergui (AsterGui): Parent AsterGui instance.
        """
        # pragma pylint: disable=too-many-statements

        Dialog.__init__(self, astergui.mainWindow())
        self.setObjectName("Preferences")

        self.astergui = astergui
        self.widgets = {}
        self.changes = []

        self.setWindowTitle(translate("PrefDlg", "Preferences"))

        items = []
        values = []
        icons = []

        def _add_item(_text, _value=None, _icon=None, _clear=False):
            if _clear:
                items[:] = []
                values[:] = []
                icons[:] = []
            items.append(_text)
            if _value is not None:
                values.append(_value)
            if _icon is not None:
                icons.append(_icon)

        # 'General' tab
        title = translate("PrefDlg", "General")
        tab = self.addTab(title)
        tab.setObjectName("Preferences_General")

        # Language
        title = translate("PrefDlg", "Language")
        _add_item("English", "en", "as_lang_en.png", _clear=True)
        _add_item("Français", "fr", "as_lang_fr.png")
        self._addSelectorItem(tab, title, "language", items, icons, values)
        self.widgets["language"].need_restart = True

        # Add spacing
        self._addSpacing(tab, 10)

        # code_aster version
        title = translate("PrefDlg", "Version of code_aster")
        _add_item(translate("PrefDlg", "Use default"), "default", _clear=True)
        _add_item(translate("PrefDlg", "Ask"), "ask")
        self._addSelectorItem(tab, title, "code_aster_version",
                              items, icons, values)

        # Add spacing
        self._addSpacing(tab, 10)

        # Toolbar buttons style
        title = translate("PrefDlg", "Toolbar button style")
        _add_item(translate("PrefDlg", "Only display icon"),
                  "icon_only", _clear=True)
        _add_item(translate("PrefDlg", "Only display text"),
                  "text_only")
        _add_item(translate("PrefDlg", "Text appears beside icon"),
                  "text_beside_icon")
        _add_item(translate("PrefDlg", "Text appears under icon"),
                  "text_under_icon")
        _add_item(translate("PrefDlg", "Follow style"),
                  "follow_style")
        self._addSelectorItem(tab, title, "toolbar_button_style",
                              items, icons, values)

        # Workspace tabs position
        title = translate("PrefDlg", "Workspace tab pages position")
        _add_item(translate("PrefDlg", "North"), "north", _clear=True)
        _add_item(translate("PrefDlg", "South"), "south")
        _add_item(translate("PrefDlg", "West"), "west")
        _add_item(translate("PrefDlg", "East"), "east")
        self._addSelectorItem(tab, title, "workspace_tab_position",
                              items, icons, values)

        # Add spacing
        self._addSpacing(tab, 10)

        # Strict import mode
        title = translate("PrefDlg", "Strict import mode")
        self._addSwitchItem(tab, title, "strict_import_mode")

        title = translate("PrefDlg",
                          "Limit of number of lines for graphical mode")
        self._addIntegerItem(tab, title, "nblines_limit", 1, 100000)

        # Add spacing
        self._addSpacing(tab, 10)

        # Switch on/off Undo/Redo feature
        title = translate("PrefDlg", "Disable Undo/Redo feature")
        self._addSwitchItem(tab, title, "disable_undo_redo")

        self._addSpacing(tab, 10)

        # Use CodeAster native naming
        # (switch off business-oriented translation)
        title = translate("PrefDlg", "Use business-oriented translations")
        self._addSwitchItem(tab, title, "use_business_translations")
        if behavior().forced_native_names:
            force = behavior().force_native_names
            self.widgets["use_business_translations"].setChecked(not force)
            self.widgets["use_business_translations"].setDisabled(True)
            self.widgets["use_business_translations"].ignore = True

        self._addSpacing(tab, 10)

        # Documentation url
        title = translate("PrefDlg", "Documentation website")
        self._addStringItem(tab, title, "doc_base_url")

        # Add stretch
        self._addSpacing(tab, 0, True)

        # --- end of 'General' tab

        # 'Interface' tab
        title = translate("PrefDlg", "Interface")
        tab = self.addTab(title)
        tab.setObjectName("Preferences_Interface")

        # *** Data Settings

        # Show catalogue name in Data Settings panel
        title = translate("PrefDlg",
                          "Show catalogue name in Data Settings panel")
        self._addSwitchItem(tab, title, "show_catalogue_name")

        # Show comments in Data Settings panel
        title = translate("PrefDlg", "Show comments in Data Settings panel")
        self._addSwitchItem(tab, title, "show_comments")

        # Enable auto-hide feature for search tool in Data Settings panel
        title = translate("PrefDlg", "Auto-hide search panel")
        self._addSwitchItem(tab, title, "auto_hide_search")

        # Add spacing
        self._addSpacing(tab, 10)

        # *** Data Files

        # Sort stages in Data Files panel
        title = translate("PrefDlg", "Sort stages in Data Files panel")
        self._addSwitchItem(tab, title, "sort_stages")

        # Show related concepts in Data Files panel
        title = translate("PrefDlg",
                          "Show related concepts in Data Files panel")
        self._addSwitchItem(tab, title, "show_related_concepts")

        # Join similar files in Data Files panel
        title = translate("PrefDlg",
                          "Join similar data files in Data Files panel")
        self._addSwitchItem(tab, title, "join_similar_files")

        # Add spacing
        self._addSpacing(tab, 10)

        # *** Operations

        # Auto-edit command
        title = translate("PrefDlg", "Automatically activate command edition")
        self._addSwitchItem(tab, title, "auto_edit")

        # Add spacing
        self._addSpacing(tab, 10)

        # *** Windows

        # Show read-only banner
        title = translate("PrefDlg", "Show read-only banner")
        self._addSwitchItem(tab, title, "show_readonly_banner")

        # Add spacing
        self._addSpacing(tab, 10)

        # *** Parameter panel

        # Content label mode
        title = translate("PrefDlg", "Parameter content display mode")
        _add_item(translate("PrefDlg", "None"), "none", _clear=True)
        _add_item(translate("PrefDlg", "Parameters"), "parameters")
        _add_item(translate("PrefDlg", "Keywords"), "keywords")
        _add_item(translate("PrefDlg", "Values"), "values")
        self._addSelectorItem(tab, title, "content_mode",
                              items, icons, values)

        # Show tooltip for 'into' items
        title = translate("PrefDlg", "Show identifier for selector items")
        self._addSwitchItem(tab, title, "show_selector_value")

        # Sort selector items in Parameters panel
        title = translate("PrefDlg", "Sort selector items")
        self._addSwitchItem(tab, title, "sort_selector_values")

        # Show catalogue name for command selector items
        title = translate("PrefDlg",
                          "Show catalogue name in command selector items")
        self._addSwitchItem(tab, title, "show_catalogue_name_in_selectors")

        # External list
        title = translate("PrefDlg", "Edit list-like keywords in sub-panel")
        self._addSwitchItem(tab, title, "external_list")

        # Add spacing
        self._addSpacing(tab, 10)

        # *** Other features

        # Allow delete case used by other case(s)
        title = translate("PrefDlg",
                          "Allow deleting cases used by other case(s)")
        self._addSwitchItem(tab, title, "allow_delete_cases")

        # Add stretch
        self._addSpacing(tab, 0, True)

        # --- end of 'Interface' tab

        # 'Editor' tab
        title = translate("PrefDlg", "Editor")
        tab = self.addTab(title)
        tab.setObjectName("Preferences_Editor")

        # - External editor
        title = translate("PrefDlg", "External editor")
        self._addFileItem(tab, title, "external_editor", self._browseEditor)

        # Add spacing
        self._addSpacing(tab, 10)

        # Use external editor for text stage
        title = translate("PrefDlg",
                          "Use external editor for text stage edition")
        self._addSwitchItem(tab, title, "use_external_editor_stage")

        # Use external editor for data files edition
        title = translate("PrefDlg",
                          "Use external editor for data files edition")
        self._addSwitchItem(tab, title, "use_external_editor_data_file")

        # Use external editor for message files viewing
        title = translate("PrefDlg",
                          "Use external editor for message files viewing")
        self._addSwitchItem(tab, title, "use_external_editor_msg_file")

        # Add spacing
        self._addSpacing(tab, 10)

        # Warn for file's size limit
        title = translate("PrefDlg", "Warn when viewing file larger than")
        self._addIntegerItem(tab, title, "file_size_limit", 1, 100000, " KB")

        try:
            import PyEditorPy
            if hasattr(PyEditorPy, "PyEditor_Widget"):
                # Add spacing
                self._addSpacing(tab, 10)

                # Python editor group
                title = translate("PrefDlg", "Python editor")
                grp = self._addGroupBox(tab, title, obj_name="python_editor")

                # - Font
                title = translate("PrefDlg", "Font")
                self._addFontItem(grp, title, "PyEditor/font")

                # - Enable current line highlight
                title = translate("PrefDlg", "Enable current line highlight")
                self._addSwitchItem(grp, title,
                                    "PyEditor/highlightcurrentline")

                # - Enable text wrapping
                title = translate("PrefDlg", "Enable text wrapping")
                self._addSwitchItem(grp, title, "PyEditor/textwrapping")

                # - Center cursor on scroll
                title = translate("PrefDlg", "Center cursor on scroll")
                self._addSwitchItem(grp, title,
                                    "PyEditor/centercursoronscroll")

                # - Display line numbers area
                title = translate("PrefDlg", "Display line numbers area")
                self._addSwitchItem(grp, title, "PyEditor/linenumberarea")

                # Add spacing
                self._addSpacing(grp, 10)

                # - Completion mode
                title = translate("PrefDlg", "Completion mode")
                _add_item(translate("PrefDlg", "None"), "none", _clear=True)
                _add_item(translate("PrefDlg", "Auto"), "auto")
                _add_item(translate("PrefDlg", "Manual"), "manual")
                _add_item(translate("PrefDlg", "Always"), "always")
                self._addSelectorItem(grp, title, "PyEditor/completionpolicy",
                                      items, icons, values)

                # Add spacing
                self._addSpacing(grp, 10)

                # - Display tab delimiters
                title = translate("PrefDlg", "Display tab delimiters")
                self._addSwitchItem(grp, title, "PyEditor/tabspacevisible")

                # - Tab size
                title = "\t" + translate("PrefDlg", "Tab size")
                self._addIntegerItem(grp, title, "PyEditor/tabsize", 1, 99)

                # Add spacing
                self._addSpacing(grp, 10)

                # - Display vertical edge
                title = translate("PrefDlg", "Display vertical edge")
                self._addSwitchItem(grp, title, "PyEditor/verticaledge")
                connect(self.widgets["PyEditor/verticaledge"].stateChanged,
                        self._updateState)

                # - Number of columns
                title = "\t" + translate("PrefDlg", "Number of columns")
                self._addIntegerItem(grp, title, "PyEditor/numbercolumns",
                                     1, 200)

        except ImportError:
            pass

        # Add stretch
        self._addSpacing(tab, 0, True)

        # --- end of 'Editor' tab

        # 'Confirmations' tab
        title = translate("PrefDlg", "Confirmations")
        tab = self.addTab(title)
        tab.setObjectName("Preferences_Confirmations")

        # - Delete object
        title = translate("PrefDlg", "Delete object")
        self._addSwitchItem(tab, title, "msgbox_delete")

        # - Undefined files
        title = translate("PrefDlg", "Undefined files")
        self._addSwitchItem(tab, title, "msgbox_undefined_files")

        # - Break operation
        title = translate("PrefDlg", "Break current operation")
        self._addSwitchItem(tab, title, "msgbox_break")

        # - Delete case used by other case(s)
        title = translate("PrefDlg", "Delete case used by other case(s)")
        self._addSwitchItem(tab, title, "msgbox_delete_case")

        # - Delete child stages
        title = translate("PrefDlg", "Delete child stages")
        self._addSwitchItem(tab, title, "msgbox_delete_stages")

        # - Convert invalid graphical stage
        title = translate("PrefDlg", "Convert invalid graphical stage")
        self._addSwitchItem(tab, title, "msgbox_convert_invalid_graphic_stage")

        # - Close the parameter panel
        title = translate("PrefDlg",
                          "Close parameter panel with modifications")
        self._addSwitchItem(tab, title, "msgbox_parampanel_close")

        # - Abort the parameter panel
        title = translate("PrefDlg", "Abort command edition")
        self._addSwitchItem(tab, title, "msgbox_parampanel_abort")

        # Add stretch
        self._addSpacing(tab, 0, True)

        # --- end of 'Confirmations' tab

        # 'Catalogs' tab
        title = translate("PrefDlg", "Catalogs")
        tab = self.addTab(title)
        tab.setObjectName("Preferences_Catalogs")

        # User's catalogs
        title = translate("PrefDlg", "User's catalogs")
        grp = self._addGroupBox(tab, title, obj_name="user_catalogs")
        self._addDirItem(grp, "user_catalogs")

        # --- end of 'Catalogs' tab

        title = translate("PrefDlg", "Defaults")
        def_btn = self.addButton(title)
        def_btn.setObjectName("Dialog_defaults")
        connect(def_btn.clicked, self._fromResources)

        self.okButton().setObjectName("Dialog_ok")
        self.cancelButton().setObjectName("Dialog_cancel")

        self._fromResources(False)

        self.tabWidget().setCurrentIndex(PrefDlg.last_tab)

    @staticmethod
    def execute(astergui):
        """
        Show *Preferences* dialog.

        Arguments:
            astergui (AsterGui): Parent AsterGui instance.

        Returns:
            list[str]: List of settings changed by the user.
        """
        changes = []
        dlg = PrefDlg(astergui)
        if dlg.exec_():
            changes = dlg.changes
        return changes

    @Q.pyqtSlot()
    def accept(self):
        """Accept changes, store preferences and close dialog box."""
        need_restart = False
        pref_mgr = self.astergui.preferencesMgr()
        for setting, widget in self.widgets.items():
            ignore = getattr(widget, "ignore", False)
            if ignore:
                continue
            value = None
            item_changed = False
            if isinstance(widget, Q.QComboBox):
                value = widget.currentData() if widget.currentData() \
                    else widget.currentText()
                item_changed = value != pref_mgr.str_value(setting)
            elif isinstance(widget, Q.QSpinBox):
                value = widget.value()
                item_changed = value != pref_mgr.int_value(setting)
            elif isinstance(widget, Q.QLineEdit):
                value = widget.text()
                item_changed = value != pref_mgr.str_value(setting)
            elif isinstance(widget, Q.QCheckBox):
                value = widget.isChecked()
                item_changed = value != pref_mgr.bool_value(setting)
            elif isinstance(widget, Q.QGroupBox):
                value = widget.isChecked()
                item_changed = value != pref_mgr.bool_value(setting)
            elif isinstance(widget, FontWidget):
                value = widget.value()
                item_changed = value != pref_mgr.font_value(setting)
            elif isinstance(widget, CatalogsView):
                widget.store()
            item_need_restart = getattr(widget, "need_restart", False)
            need_restart = need_restart or (item_changed and item_need_restart)
            if item_changed:
                self.changes.append(setting)
                pref_mgr.setValue(setting, value)
        if need_restart:
            Q.QMessageBox.information(self,
                                      "AsterStudy",
                                      translate("PrefDlg",
                                                "Some changes will take effect"
                                                " after application restart."))
        PrefDlg.last_tab = self.tabWidget().currentIndex()
        Dialog.accept(self)

    @Q.pyqtSlot()
    def _browseEditor(self):
        """Open dialog to browse editor executable."""
        btn = self.sender()
        title = translate("PrefDlg", "Choose editor program")
        filename, _ = Q.QFileDialog.getOpenFileName(self, title,
                                                    btn.editor.text())
        if filename:
            btn.editor.setText(filename)

    def _layout(self, widget=None):
        """
        Get layout for given widget; create it if necessary.

        Arguments:
            widget (Optional[QWidget]): Widget. Defaults to *None*; in
                this case top-level frame layout of dialog is used.

        Returns:
            QGridLayout: Widget's layout.
        """
        if widget is None:
            widget = self.frame()
        layout = widget.layout()
        if layout is None:
            layout = Q.QGridLayout(widget)
            layout.setContentsMargins(0, 0, 0, 0)
        return layout

    def _addFileItem(self, parent, title, setting, slot):
        """
        Add file selection item.

        Arguments:
            parent (QWidget): Parent widget.
            title (str): Text label.
            setting (str): Preference item's identifier.
            slot (method): Slot to connect `Browse` button to.
        """
        label = Q.QLabel(title, parent)
        _setObjName(label, "label", setting)
        editor = Q.QLineEdit(parent)
        _setObjName(editor, "edit", setting)
        btn = Q.QPushButton(translate("AsterStudy", "Browse..."), parent)
        _setObjName(btn, "btn", setting)
        hblayout = Q.QHBoxLayout()
        hblayout.addWidget(editor)
        hblayout.addWidget(btn)
        row = self._layout(parent).rowCount()
        self._layout(parent).addWidget(label, row, 0)
        self._layout(parent).addLayout(hblayout, row, 1)
        btn.editor = editor
        connect(btn.clicked, slot)
        self.widgets[setting] = editor

    def _addStringItem(self, parent, title, setting):
        """
        Add line edit item.

        Arguments:
            parent (QWidget): Parent widget.
            title (str): Text label.
            setting (str): Preference item's identifier.
        """
        label = Q.QLabel(title, parent)
        _setObjName(label, "label", setting)
        editor = Q.QLineEdit(parent)
        _setObjName(editor, "edit", setting)
        row = self._layout(parent).rowCount()
        self._layout(parent).addWidget(label, row, 0)
        self._layout(parent).addWidget(editor, row, 1)
        self.widgets[setting] = editor

    def _addSelectorItem(self, parent, title, setting, items, icons, ids):
        """
        Add combo box item.

        Arguments:
            parent (QWidget): Parent widget.
            title (str): Text label.
            setting (str): Preference item's identifier.
            items (list[str]): Selector items (choices).
            icons (list[str]): Names of icons for the selector items.
            ids (list[str]): Identifiers of the selector items (to
                identify choices in the preferences file).
        """
        label = Q.QLabel(title, parent)
        _setObjName(label, "label", setting)
        editor = Q.QComboBox(parent)
        _setObjName(editor, "combo", setting)
        for index, item in enumerate(items):
            editor.addItem(item)
            if index < len(icons) and icons[index]:
                editor.setItemIcon(index, load_icon(icons[index]))
            if index < len(ids) and ids[index]:
                editor.setItemData(index, ids[index])
        row = self._layout(parent).rowCount()
        self._layout(parent).addWidget(label, row, 0)
        self._layout(parent).addWidget(editor, row, 1)
        self.widgets[setting] = editor

    def _addSwitchItem(self, parent, title, setting):
        """
        Add check box item.

        Arguments:
            parent (QWidget): Parent widget.
            title (str): Text label.
            setting (str): Preference item's identifier.
        """
        editor = Q.QCheckBox(title, parent)
        _setObjName(editor, "check", setting)
        row = self._layout(parent).rowCount()
        self._layout(parent).addWidget(editor, row, 0, 1, 2)
        self.widgets[setting] = editor

    def _addFontItem(self, parent, title, setting):
        """
        Add check box item.

        Arguments:
            parent (QWidget): Parent widget.
            title (str): Text label.
            setting (str): Preference item's identifier.
        """
        label = Q.QLabel(title, parent)
        _setObjName(label, "label", setting)
        editor = FontWidget(parent)
        _setObjName(editor, "font", setting)
        row = self._layout(parent).rowCount()
        self._layout(parent).addWidget(label, row, 0)
        self._layout(parent).addWidget(editor, row, 1)
        self.widgets[setting] = editor

    def _addIntegerItem(self, parent, title, setting, min_val=0, max_val=99,
                        suffix=None):
        """
        Add integer spin box item.

        Arguments:
            parent (QWidget): Parent widget.
            title (str): Text label.
            setting (str): Preference item's identifier.
            min_val (Optional[int]): Minimal allowed value.
                Defaults to 0.
            max_val (Optional[int]): Maximal allowed value.
                Defaults to 99.
        """
        label = Q.QLabel(title, parent)
        _setObjName(label, "label", setting)
        editor = Q.QSpinBox(parent)
        _setObjName(editor, "spinbox", setting)
        editor.setRange(min_val, max_val)
        if suffix:
            editor.setSuffix(suffix)
        row = self._layout(parent).rowCount()
        self._layout(parent).addWidget(label, row, 0)
        self._layout(parent).addWidget(editor, row, 1)
        self.widgets[setting] = editor

    def _addDirItem(self, parent, setting):
        """
        Add user catalogs configuration widget.

        Arguments:
            parent (QWidget): Parent widget.
            setting (str): Preference item's identifier.
        """
        editor = CatalogsView(parent)
        _setObjName(editor, "dirs", setting)
        row = self._layout(parent).rowCount()
        self._layout(parent).addWidget(editor, row, 0, 1, 2)
        self.widgets[setting] = editor

    def _addGroupBox(self, parent, title, setting=None, obj_name=None):
        """
        Add a group box item.

        Note:
            To add checkable group box (enabled / disabled by the user),
            specify *setting* parameter.

        Arguments:
            parent (QWidget): Parent widget.
            title (str): Group title.
            setting (str): Preference item's identifier.

        Returns:
            QGroupBox: A group box item.
        """
        grp = Q.QGroupBox(title, parent)
        _setObjName(grp, "group", setting or obj_name or title)
        grp.setLayout(Q.QGridLayout())
        if setting:
            grp.setCheckable(True)
            self.widgets[setting] = grp
        row = self._layout(parent).rowCount()
        self._layout(parent).addWidget(grp, row, 0, 1, 2)
        return grp

    def _addSpacing(self, parent, size=0, stretch=False):
        """
        Add vertical stretchable spacing.

        Arguments:
            parent (QWidget): Parent widget.
        """
        row = self._layout(parent).rowCount()
        self._layout(parent).setRowMinimumHeight(row, size)
        if stretch:
            self._layout(parent).setRowStretch(row, 10)

    @Q.pyqtSlot()
    def _updateState(self):
        """
        Update controls.
        """
        if "PyEditor/verticaledge" in self.widgets:
            value = self.widgets["PyEditor/verticaledge"].isChecked()
            self.widgets["PyEditor/numbercolumns"].setEnabled(value)

    @Q.pyqtSlot()
    def _fromResources(self, ignore_user=True):
        """
        Set-up widgets from preferences.

        Arguments:
            ignore_user (Optional[bool]): Says if user options should be
                ignored (used when 'Defaults' button is clicked).
                Defaults to *True*.
        """
        if ignore_user:
            question = translate("PrefDlg",
                                 "Do you want to restore default preferences?")
            ask = Q.QMessageBox.question(self, "AsterStudy", question,
                                         Q.QMessageBox.Yes | Q.QMessageBox.No,
                                         Q.QMessageBox.Yes)
            if ask == Q.QMessageBox.No:
                return

        with ignore_user_values(self.astergui.preferencesMgr(), ignore_user) \
                as pref_mgr:

            for option, widget in self.widgets.iteritems():
                ignore = getattr(widget, "ignore", False)
                if ignore:
                    continue
                if isinstance(widget, Q.QComboBox):
                    value = pref_mgr.str_value(option)
                    for index in range(widget.count()):
                        text = widget.itemText(index)
                        data = widget.itemData(index)
                        if data is not None and data == value or text == value:
                            widget.setCurrentIndex(index)
                elif isinstance(widget, Q.QSpinBox):
                    widget.setValue(pref_mgr.int_value(option))
                elif isinstance(widget, Q.QLineEdit):
                    widget.setText(pref_mgr.str_value(option))
                elif isinstance(widget, Q.QCheckBox):
                    widget.setChecked(pref_mgr.bool_value(option))
                elif isinstance(widget, Q.QGroupBox):
                    widget.setChecked(pref_mgr.bool_value(option))
                elif isinstance(widget, FontWidget):
                    widget.setValue(pref_mgr.font_value(option))
                elif isinstance(widget, CatalogsView):
                    widget.restore()

        self._updateState()


def _setObjName(widget, prefix, suffix=None):
    """
    Set object name to sub-widget.

    Arguments:
        widget (QWidget): Sub-widget.
        prefix (str): Name's prefix.
        suffix (Optional[str]): Name's suffix. Defaults to *None*.
    """
    if suffix:
        suffix = suffix.replace('/', '_')
    name = "Preferences_{}_{}".format(prefix, suffix if suffix else "unknown")
    widget.setObjectName(name)
