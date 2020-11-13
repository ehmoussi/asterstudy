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
Parameters Panel Editors and Factory
------------------------------------

Implementation of the parameters editors for Parameters panel.

TODO:
    It is not clear how to create editor in case of heterogeneous types.
    See `ParameterMeshSelectionEditorFactoryCreator.createEditor`.
"""

from __future__ import unicode_literals

import os

from PyQt5.Qt import (Qt, QCheckBox, QComboBox, QDoubleValidator, QHBoxLayout,
                      QIntValidator, QLineEdit, QPushButton, QRegExp, QWidget,
                      QMessageBox, QStyle, QLabel, QFrame, QToolButton, QMenu,
                      QSizePolicy, QStackedWidget, QRegExpValidator, QToolBar,
                      QSize, QEvent, QValidator, QFocusEvent, QApplication,
                      pyqtSignal, pyqtSlot)

from common import (CFG, common_filters, get_cmd_mesh, get_file_name,
                    get_medfile_meshes, italic, image, is_medfile,
                    is_subclass, is_reference, load_icon,
                    to_type, translate, wrap_html)
from datamodel import CATA, IDS, get_cata_typeid
from datamodel.command import Command, Variable, CO
from datamodel.command.helper import avail_meshes_in_cmd
from gui import Role, Panel
from gui.behavior import behavior
from gui.variablepanel import VariablePanel

from .basic import EditorLink, KeywordType, Options, parameterPanel
from .path import ParameterPath
from .widgets import ParameterButton

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name,too-many-lines

class ParameterEditorFactory(object):
    """Class for editor creators."""

    def __init__(self):
        """
        Constructor for empty editor factory.
        """
        super(ParameterEditorFactory, self).__init__()
        self._creators = []

    def registerCreator(self, creator):
        """
        Append editor creator into the factory.

        Arguments:
            creator (ParameterEditorCreator): Editor creator.
        """
        if creator is not None and creator not in self._creators:
            self._creators.append(creator)

    def unregisterCreator(self, creator):
        """
        Remove editor creator into the factory.

        Arguments:
            creator (ParameterEditorCreator): Editor creator.
        """
        if creator is not None:
            self._creators.remove(creator)

    def createEditor(self, path, parent):
        """
        Create editor.

        Arguments:
            path: Parameter keyword catalog path.
            parent (QWidget): parent widget

        Returns:
            [QWidget]: list of available editors.
        """
        editors = []
        for creator in self._creators:
            editor = creator.createEditor(path, parent)
            if editor is not None:
                editors.append(editor)
                if editor.icon() is None:
                    break

        editor = None
        if len(editors) > 1:
            editor = ParameterEditorStack(editors, parent)
        elif len(editors) > 0:
            editor = editors[0]

        return editor


class ParameterEditorFactoryCreator(object):
    """Class for editor creation."""

    # pragma pylint: disable=no-self-use,unused-argument
    def createEditor(self, path, parent):
        """
        Create editor.

        Arguments:
            path: Parameter keyword catalog path.
            parent (QWidget): parent widget

        Returns:
            QWidget: Editor.
        """
        return None


def parameter_editor_factory():
    """
    Get the parameter editor factory.

    Creates the factory if it does not exist.

    Returns:
        ParameterEditorFactory: Parameter editor factory.
    """

    if not hasattr(parameter_editor_factory, "factory"):
        # Create and register the default editor creators
        factory = ParameterEditorFactory()

        # Subpanel editors depend on keyword name
#        factory.registerCreator(ParameterMeshGroupSelectionEditor.Creator())
        factory.registerCreator(ParameterSubEditor.MeshGroupCreator())
        factory.registerCreator(ParameterSubEditor.TableCreator())

        # Ordinary editors depend on keyword name
        factory.registerCreator(ParameterMEDSelectEditor.Creator())
        factory.registerCreator(ParameterFilePathEditor.Creator())

        # Embedded list editor
        factory.registerCreator(ParameterSequenceEditor.Creator())

        # Standard list editor
        factory.registerCreator(ParameterSubEditor.ListCreator())

        # Ordinary editors depend on keyword type
        factory.registerCreator(ParameterMeshSelectionEditor.Creator())
        factory.registerCreator(ParameterCommandSelectEditor.Creator())

        # Standard subpanel editor
        factory.registerCreator(ParameterSubEditor.FactCreator())

        # Standard simple editors
        factory.registerCreator(ParameterBoolEditor.Creator())
        factory.registerCreator(ParameterComboEditor.Creator())
        factory.registerCreator(ParameterLineEditor.Creator())

        # Additional alternative editors
        factory.registerCreator(ParameterVariableSelectEditor.Creator())
        factory.registerCreator(ParameterMacroEditor.Creator())

        parameter_editor_factory.factory = factory
    return parameter_editor_factory.factory


class ParameterEditor(QWidget):
    """Base class for editor widgets."""

    class EditType(object):
        """Enumerator for type id."""

        Unknown = 0 # Unknown type
        Int = 1 # Integer type
        Real = 2 # Real type
        Text = 3 # Text type
        Object = 4 # Object type
        Complex = 5 # Complex number

    class EditContext(object):
        """Enumerator for specifing edition context changing."""

        Variables = 'VARIABLES'


    valueChanged = pyqtSignal()
    """Signal: emitted when value is changed in the editor."""

    linkActivated = pyqtSignal(str)
    """Signal: emitted when sub-editor is activated."""

    def __init__(self, path, parent=None):
        """
        Create editor.

        Arguments:
            parent (Optional[QWidget]): Parent widget.
        """
        super(ParameterEditor, self).__init__(parent)
        self._path = path

        if parent is not None and hasattr(parent, 'editContextChanged'):
            parent.editContextChanged.connect(self._onEditContextChanged)

    # pragma pylint: disable=no-self-use
    def value(self):
        """
        Get value stored in the editor.

        This method must be implemented in sub-classes.
        Default implementation returns None.

        Returns:
            any: int, float, str or any other appropriate value.
        """
        return None

    def setValue(self, value):
        """
        Set the value into editor.

        This method must be implemented in sub-classes.
        Default implementation does nothing.

        Arguments:
            value (any): Parameter's value.
        """
        pass

    # pragma pylint: disable=no-self-use
    def icon(self):
        """
        Get icon associated with the editor.

        This method must be implemented in sub-classes.
        Default implementation returns None.

        Returns:
            str: icon file name.
        """
        return None

    # pragma pylint: disable=no-self-use
    def description(self):
        """
        Get description associated with the editor.

        This method must be implemented in sub-classes.
        Default implementation returns None.

        Returns:
            str: description string.
        """
        return ''

    def path(self):
        """
        Get the parameter's path.

        Returns:
            ParameterPath: Parameter path.
        """
        return self._path

    def name(self):
        """
        Get the parameter's name.

        Returns:
            str: Parameter name.
        """
        return self.path().name() if self.path() is not None else ''

    def command(self):
        """
        Get the parameter's parent command.

        Returns:
            Command: Parent Command.
        """
        return self.path().command()

    def keyword(self):
        """
        Get the parameter's catalogue keyword.

        Returns:
            PartOfSyntax: Parameter's keyword.
        """
        return self.path().keyword() if self.path() is not None else None

    def keywordDefinition(self):
        """
        Get the parameter's catalogue keyword definition.

        Returns:
            PartOfSyntax: Parameter's keyword description.
        """
        return self.keyword().definition \
            if self.keyword() is not None else None

    def dependValue(self, path, value):
        """
        Invoked when value of keyword which this depends from is changed.
        Default implementation does nothing.
        Must be reimplemented in subclasses.

        Arguments:
            path (ParameterPath): Path of keyword which was changed
            value: Changed value
        """
        pass

    def parameterType(self, paramkey=None):
        """
        Get editor type for the parameter.

        Arguments:
            param_def (PartOfSyntax): Description of parameter.

        Returns:
            int: EditType of the parameter's editor.
        """
        param_def = self.keyword() if paramkey is None else paramkey

        typ = self.EditType.Unknown
        if param_def is not None:
            defin = param_def.definition
            if get_cata_typeid(param_def) == IDS.simp:
                if defin.get('typ') == 'I':
                    typ = self.EditType.Int
                elif defin.get('typ') == 'R':
                    typ = self.EditType.Real
                elif defin.get('typ') == 'C':
                    typ = self.EditType.Complex
                elif defin.get('typ') == 'TXM':
                    typ = self.EditType.Text
                else:
                    typ = self.EditType.Object
        return typ

    def forceNoDefault(self):
        """
        This method can be redefined in successors to ignore 'default'
        attribute of keyword.

        Default implementation returns *False*.

        Returns:
            bool: *True* if 'default' attribute should be ignored;
            *False* otherwise.
        """
        return False

    def meshview(self):
        """
        Returns central view
        """
        return parameterPanel(self).meshview()

    def updateTranslations(self):
        """
        Update translations in GUI elements.
        Can be redefined in subclasses.
        """
        pass

    def updateEditContext(self, context):
        """
        Update the data in GUI elements.
        Can be redefined in subclasses.
        """
        pass

    def changeEditContext(self, context):
        """
        Invoked the notification about edit context changing.
        """
        obj = None
        top = self.parent()
        while obj is None and top is not None:
            if hasattr(top, 'editContextChanged'):
                obj = top
            top = top.parent()

        if obj:
            obj.editContextChanged.emit(context)

    def _onEditContextChanged(self, context):
        self.updateEditContext(context)


class ParameterEditorStack(ParameterEditor):
    """Stack for editor widgets."""

    def __init__(self, edits, parent=None):
        """
        Create editor stack.

        Arguments:
            parent (Optional[QWidget]): Parent widget.
        """
        super(ParameterEditorStack, self).\
            __init__(edits[0].path() if edits is not None and len(edits) \
                         else ParameterPath(None), parent)

        base = QHBoxLayout(self)
        base.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget(self)
        base.addWidget(self._stack, 1)

        self._switch = QStackedWidget(self)
        self._switch.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        base.addWidget(self._switch)

        tips = []
        menu = QMenu(self)
        for e in edits:
            icon = load_icon(e.icon())
            menu.addAction(icon, "").\
                setObjectName(str(self._stack.count()))

            self._stack.addWidget(e)

            tbar = QToolBar(self._switch)
            tbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
            btn = QToolButton(tbar)
            tbar.addWidget(btn)
            btn.setObjectName(self.path().name() + "-%s" % e.icon())
            btn.setIcon(icon)
            btn.setMenu(menu)
            self._switch.addWidget(tbar)

            tips.append(image(CFG.rcfile(e.icon())) +
                        wrap_html(" " + italic(e.description()), "span"))

            btn.clicked.connect(self._onSwitchClicked)
            e.valueChanged.connect(self._onValueChanged)
            e.linkActivated.connect(self._onLinkActivated)

        if len(tips) > 0:
            self._switch.setToolTip("<br>".join(tips))

        margin = menu.style().pixelMetric(QStyle.PM_MenuHMargin)
        menu.setFixedWidth(self._switch.sizeHint().width() + 2 * margin)
        menu.triggered.connect(self._onMenuTriggered)

        self._switchEditor(0)

    def currentEditor(self):
        """
        Gets the current editor.

        Returns:
            QWidget: current editor widget
        """
        return self._stack.currentWidget()

    # pragma pylint: disable=no-self-use
    def value(self):
        """
        Get value stored in the editor.

        This method must be implemented in sub-classes.
        Default implementation returns None.

        Returns:
            any: int, float, str or any other appropriate value.
        """
        return self.currentEditor().value() \
            if self.currentEditor() is not None else None

    def setValue(self, value):
        """
        Set the value into editor.

        This method must be implemented in sub-classes.
        Default implementation does nothing.

        Arguments:
            value (any): Parameter's value.
        """
        index = -1
        for i in xrange(self._stack.count()):
            try:
                self._stack.widget(i).setValue(value)
                index = i
                break
            except ValueError:
                pass

        self._switchEditor(index)

    # pragma pylint: disable=no-self-use
    def icon(self):
        """
        Get icon associated with the editor.

        This method must be implemented in sub-classes.
        Default implementation returns None.

        Returns:
            str: icon file name.
        """
        return self.currentEditor().icon() \
            if self.currentEditor() is not None else None

    # pragma pylint: disable=no-self-use
    def description(self):
        """
        Get description associated with the editor.

        This method must be implemented in sub-classes.
        Default implementation returns None.

        Returns:
            str: description string.
        """
        return self.currentEditor().description() \
            if self.currentEditor() is not None else None

    def dependValue(self, path, value):
        """
        Invoked when value of keyword which this depends from is changed.
        Default implementation does nothing.
        Must be reimplemented in subclasses.

        Arguments:
            path (ParameterPath): Path of keyword which was changed
            value: Changed value
        """
        for i in xrange(self._stack.count()):
            self._stack.widget(i).dependValue(path, value)

    def forceNoDefault(self):
        """
        This method can be redefined in successors to ignore 'default'
        attribute of keyword.

        Default implementation returns *False*.

        Returns:
            bool: *True* if 'default' attribute should be ignored;
            *False* otherwise.
        """
        return self.currentEditor().forceNoDefault() \
            if self.currentEditor() is not None else False

    def updateTranslations(self):
        """
        Update translations in GUI elements.
        Can be redefined in subclasses.
        """
        for i in xrange(self._stack.count()):
            self._stack.widget(i).updateTranslations()

    def _onSwitchClicked(self):
        index = self._switch.indexOf(self.sender().parent()) + 1
        if index >= self._stack.count():
            index = 0
        self._switchEditor(index)

    def _onMenuTriggered(self, action):
        index = int(action.objectName())
        self._switchEditor(index)

    def _onValueChanged(self):
        if self.sender() == self.currentEditor():
            self.valueChanged.emit()

    def _onLinkActivated(self, link):
        if self.sender() == self.currentEditor():
            self.linkActivated.emit(link)

    def _switchEditor(self, index):
        if index >= 0 and index < self._stack.count() \
                and self._stack.currentIndex() != index:
            self._stack.setCurrentIndex(index)
            self._switch.setCurrentIndex(index)
            self._onValueChanged()

class ComplexValidator(QValidator):
    """Validator for complex editor"""

    def __init__(self, lineedit):
        super(ComplexValidator, self).__init__(lineedit)

    @staticmethod
    def validate(text, pos):
        """
        Validate the inputted text. Allow to enter the any item text only.

        Arguments:
            text (str): Validated text
            pos (int): Current position in editor

        Returns:
            (QValidator.State): Validation result state
        """
        if to_type(text, complex) is not None:
            state = QValidator.Acceptable
        else:
            state = QValidator.Intermediate
        return state, text, pos


class ParameterLineEditor(ParameterEditor):
    """Simple editor based on line edit widget."""

    class Creator(ParameterEditorFactoryCreator):
        """Class for line editor creation."""

        # pragma pylint: disable=no-self-use
        def createEditor(self, path, parent):
            """
            Create editor.

            Arguments:
                path: Parameter keyword catalog path.
                parent (QWidget): parent widget
            """
            editor = None
            kw_def = path.keyword()
            if path.keywordType() == KeywordType.Standard and \
                    kw_def is not None:
                defin = kw_def.definition
                if 'into' not in defin:
                    typeid = get_cata_typeid(kw_def)
                    if typeid == IDS.simp:
                        typ_attr = defin.get('typ')
                        if isinstance(typ_attr, (tuple, list)) and typ_attr:
                            typ_attr = typ_attr[0]
                        if typ_attr in ('I', 'R', 'C', 'TXM', 'Fichier'):
                            editor = ParameterLineEditor(path, parent)
            return editor

    def __init__(self, path, parent=None):
        """
        Create editor.

        Arguments:
            parent (Optional[QWidget]): Parent widget.
        """
        super(ParameterLineEditor, self).__init__(path, parent)

        self.edit = QLineEdit(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit)

        validator = None
        kword = self.keyword()
        typ = self.parameterType()
        if typ == self.EditType.Int:
            validator = QIntValidator(self.edit)
        elif typ == self.EditType.Real:
            validator = QDoubleValidator(self.edit)
        elif typ == self.EditType.Complex:
            validator = ComplexValidator(self.edit)

        if validator is not None:
            defin = kword.definition
            if 'val_min' in defin:
                validator.setBottom(defin.get('val_min'))
            if 'val_max' in defin:
                validator.setTop(defin.get('val_max'))

        self.edit.setValidator(validator)
        self.edit.setObjectName(self.name())
        self.edit.textChanged.connect(self.valueChanged)

    def value(self):
        """
        Get value stored in the editor.

        Result's type depends on the parameter's description.

        Returns:
            int, float or str: Value stored in the editor.
        """
        txt = self.edit.text()
        if len(txt) == 0:
            txt = None
        typ = self.parameterType()
        if typ == self.EditType.Int:
            return to_type(txt, int)
        elif typ == self.EditType.Real:
            return to_type(txt, float)
        elif typ == self.EditType.Complex:
            return to_type(txt, complex)
        else:
            return txt

    def setValue(self, value):
        """
        Set the value into editor.

        Arguments:
            value (int, float, complex or str): Parameter's value.
        """
        if value is not None and \
                not isinstance(value, (basestring, int, float, complex)):
            raise ValueError("Not supported value type")

        txt = str(value) if value is not None else ""
        self.edit.setText(txt)

    # pragma pylint: disable=no-self-use
    def icon(self):
        """
        Get icon associated with the editor.

        This method must be implemented in sub-classes.
        Default implementation returns None.

        Returns:
            str: icon file name.
        """
        return "as_ico_value.png"

    # pragma pylint: disable=no-self-use
    def description(self):
        """
        Get description associated with the editor.

        This method must be implemented in sub-classes.
        Default implementation returns None.

        Returns:
            str: description string.
        """
        return translate("ParameterPanel", "Enter value")


class ParameterBoolEditor(ParameterEditor):
    """Editor for boolean-like parameter, based on check box widget."""

    class Creator(ParameterEditorFactoryCreator):
        """Class for check box editor creation."""

        # pragma pylint: disable=no-self-use
        def createEditor(self, path, parent):
            """
            Create editor.

            Arguments:
                path: Parameter keyword catalog path.
                parent (QWidget): parent widget
            """
            editor = None
            kw_def = path.keyword()
            if kw_def is not None:
                defin = kw_def.definition
                if 'into' in defin and \
                        sorted(defin.get('into')) == ["NON", "OUI"]:
                    editor = ParameterBoolEditor(path, parent)
            return editor


    def __init__(self, path, parent=None):
        """
        Create editor.

        Arguments:
            parent (Optional[QWidget]): Parent widget.
        """
        super(ParameterBoolEditor, self).__init__(path, parent)
        self.edit = QCheckBox(self)
        self.edit.stateChanged.connect(self.valueChanged)
        self.edit.stateChanged.connect(self._stateChanged)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit)
        layout.addStretch(1)

        self.edit.setObjectName(self.name() + '-value')
        self._stateChanged()

    def value(self):
        """
        Get value stored in the editor.

        Returns:
            str: "OUI" if check box is ON; "NON" otherwise.
        """
        return "OUI" if self.edit.isChecked() else "NON"

    def setValue(self, value):
        """
        Set the value into editor.

        Arguments:
            value (str): Parameter's value: "OUI" for ON, "NON" for OFF.
        """
        if value is not None and not isinstance(value, basestring):
            raise ValueError("Not supported value type")

        self.edit.setChecked(value == "OUI")

    # pragma pylint: disable=no-self-use
    def icon(self):
        """
        Get icon associated with the editor.

        This method must be implemented in sub-classes.
        Default implementation returns None.

        Returns:
            str: icon file name.
        """
        return "as_ico_value.png"

    def description(self):
        """
        Get description associated with the editor.

        This method must be implemented in sub-classes.
        Default implementation returns None.

        Returns:
            str: description string.
        """
        return translate("ParameterPanel", "Switch on/off")

    def updateTranslations(self):
        """
        Update translation.
        """
        self._stateChanged()

    @pyqtSlot(int)
    def _stateChanged(self):
        """
        Called when check box is switched ON/OFF. Updates check-box's
        title.
        """
        self.edit.setText(Options.translate_command(self.command().title,
                                                    self.name(),
                                                    self.value()))


class ParameterComboEditor(ParameterEditor):
    """Editor for selector type parameter, based on combo-box widget."""

    class Creator(ParameterEditorFactoryCreator):
        """Class for combobox editor creation."""

        # pragma pylint: disable=no-self-use
        def createEditor(self, path, parent):
            """
            Create editor.

            Arguments:
                path: Parameter keyword catalog path.
                parent (QWidget): parent widget
            """
            editor = None
            kw_def = path.keyword()
            if path.keywordType() == KeywordType.Standard and \
                    kw_def is not None:
                defin = kw_def.definition
                if 'into' in defin:
                    if sorted(defin.get('into')) != ["NON", "OUI"]:
                        editor = ParameterComboEditor(path, parent)
            return editor

    class ComboBox(QComboBox):
        """Combo box with additional validation after focus out"""

        def __init__(self, parent=None):
            super(ParameterComboEditor.ComboBox, self).__init__(parent)

        def showPopup(self):
            """Reimplemented for internal reasons"""
            QApplication.sendEvent(self, QFocusEvent(QEvent.FocusOut))
            super(ParameterComboEditor.ComboBox, self).showPopup()

        def focusOutEvent(self, event):
            """Reimplemented for internal reasons"""
            super(ParameterComboEditor.ComboBox, self).focusOutEvent(event)
            if self.isEditable():
                self.setEditText(self.itemText(self.currentIndex()))


    class Validator(QValidator):
        """Validator for editable combobox input field"""

        def __init__(self, combobox):
            super(ParameterComboEditor.Validator, self).__init__(combobox)

        def validate(self, text, pos):
            """
            Validate the inputted text. Allow to enter the any item text only.

            Arguments:
                text (str): Validated text
                pos (int): Current position in editor

            Returns:
                (QValidator.State): Validation result state
            """
            state = QValidator.Invalid
            if len(text) == 0:
                state = QValidator.Intermediate
            else:
                idx = self.parent().findText(text, Qt.MatchStartsWith)
                if idx >= 0 and self.parent().itemText(idx).startswith(text):
                    state = QValidator.Acceptable
            return state, text, pos


    def __init__(self, path, parent=None):
        """
        Create editor.

        Arguments:
            parent (Optional[QWidget]): Parent widget.
        """
        super(ParameterComboEditor, self).__init__(path, parent)
        self.edit = ParameterComboEditor.ComboBox(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit)

        self.edit.setEditable(True)
        self.edit.setInsertPolicy(QComboBox.NoInsert)
        self.edit.lineEdit().\
            setValidator(ParameterComboEditor.Validator(self.edit))

        self._updateList()

        self.edit.setObjectName(self.name())
        self.edit.currentIndexChanged.connect(self.valueChanged)

        if self.edit.count() == 1:
            self.edit.setCurrentIndex(0)

    def value(self):
        """
        Get value stored in the editor.

        Returns:
            str: Value chosen by the user.
        """

        data = self.edit.itemData(self.edit.currentIndex())
        val = self.edit.itemText(self.edit.currentIndex())
        typ = self.parameterType()
        if typ == self.EditType.Int:
            return to_type(val, int)
        elif typ == self.EditType.Real:
            return to_type(val, float)
        elif typ == self.EditType.Complex:
            return to_type(val, complex)
        else:
            return data if data is not None else val

    def setValue(self, value):
        """
        Set the value into editor.

        Arguments:
            value (int, float, complex or str): Parameter's value.
        """

        if value is not None and \
                not isinstance(value, (basestring, int, float, complex)):
            raise ValueError("Not supported value type")

        if isinstance(value, basestring):
            index = self.edit.findData(value)
            if index < 0:
                index = self.edit.findText(value)
        else:
            index = self.edit.findText(str(value))
        self.edit.setCurrentIndex(index)

    # pragma pylint: disable=no-self-use
    def icon(self):
        """
        Get icon associated with the editor.

        This method must be implemented in sub-classes.
        Default implementation returns None.

        Returns:
            str: icon file name.
        """
        return "as_ico_value.png"

    def description(self):
        """
        Get description associated with the editor.

        This method must be implemented in sub-classes.
        Default implementation returns None.

        Returns:
            str: description string.
        """
        return translate("ParameterPanel", "Select value")

    def updateTranslations(self):
        """
        Update translation.
        """
        self._updateList()

    def _updateList(self):
        """
        Updates the list in the combobox
        """
        lst = None
        kw_def = self.keywordDefinition()
        if kw_def is not None:
            lst = kw_def.get('into')

        show_ident = behavior().show_selector_value
        sort_lists = behavior().sort_selector_values

        if lst is not None:
            if sort_lists:
                lst = sorted(lst)
            current = self.edit.currentIndex()
            self.edit.clear()
            for value in lst:
                if isinstance(value, basestring):
                    title = Options.translate_command(self.command().title,
                                                      self.name(), value)
                    if title != value and show_ident:
                        title = "{0} ({1})".format(title, value)
                    self.edit.addItem(title, value)
                else:
                    self.edit.addItem(str(value))
            self.edit.setCurrentIndex(current)


class ParameterMEDSelectEditor(ParameterComboEditor):
    """Editor for NOM_MED, based on combo-box widget."""

    class Creator(ParameterEditorFactoryCreator):
        """Class for MED mesh selection creation."""

        # pragma pylint: disable=no-self-use
        def createEditor(self, path, parent):
            """
            Create editor.

            Arguments:
                path: Parameter keyword catalog path.
                parent (QWidget): parent widget
            """
            editor = None
            if path.keywordType() == KeywordType.MeshName:
                editor = ParameterMEDSelectEditor(path, parent)
            return editor

    updateMeshView = pyqtSignal(str, str, float, bool)
    """Signal: emitted when sub-editor is activated."""

    def __init__(self, path, parent=None):
        """
        Create editor.

        Arguments:
            parent (Optional[QWidget]): Parent widget.
        """
        self._file = None
        super(ParameterMEDSelectEditor, self).__init__(path, parent)
        self.edit.setEditable(False)
        self.edit.currentTextChanged.connect(self.meshNameToChange)
        self.updateMeshView.connect(self.meshview().displayMEDFileName)

    def description(self):
        """
        Get description associated with the editor.

        This method must be implemented in sub-classes.
        Default implementation returns None.

        Returns:
            str: description string.
        """
        return translate("ParameterPanel", "Select mesh")

    def dependValue(self, path, value):
        """
        Invoked when value of keyword which this depends from is changed.

        Arguments:
            path (ParameterPath): Path of keyword which was changed
            value: Changed value
        """
        if path.keywordType() == KeywordType.FileName:
            self._file = value.values()[0]

            curvalue = self.value()
            self._updateList()
            self.setValue(curvalue)

            if curvalue != self.value():
                self.valueChanged.emit()

    def _updateList(self):
        """
        Updates the list in the combobox
        """
        items = []
        if self._file:
            items = get_medfile_meshes(self._file)
        self.edit.clear()
        self.edit.addItems(items)

    @pyqtSlot(str)
    def meshNameToChange(self, meshname):
        """
        Emits `updateMeshView` signal whenever value in combo box is changed
        """
        if self.edit.isEnabled():
            self.updateMeshView.emit(self._file, meshname, 1.0, False)

class ParameterCommandSelectEditor(ParameterComboEditor):
    """Editor for selector type parameter, based on combo-box widget."""

    updateMeshView = pyqtSignal(str, str, float, bool)
    """Signal: emitted when sub-editor is activated."""

    class Creator(ParameterEditorFactoryCreator):
        """Class for factor editor creation."""

        # pragma pylint: disable=no-self-use
        def createEditor(self, path, parent):
            """
            Create editor.

            Arguments:
                path: Parameter keyword catalog path.
                parent (QWidget): parent widget
            """
            editor = None
            kw_def = path.keyword().definition
            typ = kw_def.get('typ')
            if isinstance(typ, (tuple, list)):
                if len(typ) > 0:
                    # TODO: it is not clear how to create editor
                    # in case of heterogeneous types
                    typ = typ[0]
                else:
                    typ = None

            if is_subclass(typ, CATA.package('DataStructure').ASSD) and \
                    typ is not CATA.package('DataStructure').CO:
                editor = ParameterCommandSelectEditor(path, parent)
            return editor

    def __init__(self, path, parent=None):
        """
        Create editor.

        Arguments:
            parent (Optional[QWidget]): Parent widget.
        """
        self.cmdlist = []
        super(ParameterCommandSelectEditor, self).__init__(path, parent)
        self.edit.setEditable(False)

        if self.edit.count() == 2:
            self.edit.setCurrentIndex(1)

        self.edit.currentIndexChanged.connect(self.conceptChanged)
        self.edit.activated.connect(self.conceptChanged)
        self.updateMeshView.connect(self.meshview().displayMEDFileName)

    # pragma pylint: disable=no-self-use
    def icon(self):
        """
        Get icon associated with the editor.

        This method must be implemented in sub-classes.
        Default implementation returns None.

        Returns:
            str: icon file name.
        """
        return "as_ico_command.png"

    def description(self):
        """
        Get description associated with the editor.

        This method must be implemented in sub-classes.
        Default implementation returns None.

        Returns:
            str: description string.
        """
        return translate("ParameterPanel", "Select existing result")

    def _updateList(self):
        """
        Updates the list in the combobox
        """
        self.cmdlist = []
        kw_def = self.keywordDefinition()
        if self.path() is not None:
            self.cmdlist = self.path().command().groupby(kw_def.get('typ'))

        self.cmdlist = self._reorderList(self.cmdlist)

        current = self.edit.currentIndex()

        self.edit.clear()
        show_title = behavior().show_catalogue_name_in_selectors
        title_mask = '{n} ({t})' if show_title else '{n}'
        vartit = translate("ParameterPanel", "Variable")
        for cmd in self.cmdlist:
            ctitle = vartit if cmd.title == "_CONVERT_VARIABLE" else cmd.title
            title = title_mask.format(n=cmd.name, t=ctitle)
            self.edit.addItem(title, cmd.uid)

        specials = self._specialItems()
        specials.reverse()
        for j in xrange(len(specials)):
            pair = specials[j]
            self.edit.insertItem(0, pair[0], pair[1])

        if current < 0:
            current = 0
        self.edit.setCurrentIndex(current)

    # pragma pylint: disable=no-self-use
    def _specialItems(self):
        """
        Gets the special selector items.

        Returns:
            [(str, int)]: list of pairs name and id.
        """
        noobj = translate("ParameterPanel",
                          "<no object selected>")
        return [(noobj, 0)]

    # pragma pylint: disable=no-self-use
    def _reorderList(self, lst):
        """
        Reorder the list.

        Arguments:
            lst ([Command]): List of commands
        Returns:
            [Command]: Reordered command list.
        """
        lst.reverse()
        return lst

    def value(self):
        """
        Get value stored in the editor.

        Returns:
            str: Value chosen by the user.
        """
        cmd = None
        idx = self.edit.currentIndex()
        data = self.edit.itemData(idx)
        for c in self.cmdlist:
            if c.uid == data:
                cmd = c
                break
        return cmd

    def setValue(self, value):
        """
        Set the value into editor.

        Arguments:
            value (str): Parameter's value.
        """
        if value is not None and \
                not isinstance(value, Command):
            raise ValueError("Not supported value type")

        index = 0
        if value is not None:
            index = self.edit.findData(value.uid)
            if index < 0:
                index = 0
        self.edit.setCurrentIndex(index)

    def meshlist(self):
        """
        Meshes available from `cmdlist` that can be displayed.
        """
        meshlist = []
        for cmd in self.cmdlist:
            meshes = avail_meshes_in_cmd(cmd)
            for mesh in meshes:
                filename, _ = get_cmd_mesh(mesh)
                if filename:
                    meshlist.append(mesh)
        return meshlist

    @pyqtSlot(int)
    def conceptChanged(self, _):
        """
        Called when the value in combo box is changed.
        Updates central view with the new available meshes.

        Arguments:
            idx (int): new index in the combo box.
        """
        meshes = avail_meshes_in_cmd(self.value())

        if self.meshlist():
            for mesh in meshes:
                filename, meshname = get_cmd_mesh(mesh)
                if self.edit.isEnabled() and filename:
                    self.updateMeshView.emit(filename, meshname, 1.0, False)


class ParameterFilePathEditor(ParameterEditor):
    """Unit parameter's editor."""

    class Creator(ParameterEditorFactoryCreator):
        """Class for custom editor creation."""

        # pragma pylint: disable=no-self-use
        def createEditor(self, path, parent):
            """
            Create editor.

            Arguments:
                path: Parameter keyword catalog path.
                parent (QWidget): parent widget
            """
            editor = None
            if path.keywordType() == KeywordType.FileName:
                editor = ParameterFilePathEditor(path, parent)
            return editor

    meshFileChanged = pyqtSignal(str, str, float, bool)
    """Signal: emitted when sub-editor is activated."""

    def __init__(self, path, parent=None):
        """
        Create editor.

        Arguments:
            parent (Optional[QWidget]): Parent widget.
        """
        super(ParameterFilePathEditor, self).__init__(path, parent)
        self._parent = parent
        self.storage = None
        self._prev_index = None
        self.edit = QComboBox(self)

        model = parameterPanel(self).unitModel()

        self.edit.setModel(model)
        self.edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.edit.setObjectName(self.name())
        self.edit.currentIndexChanged.connect(self.valueChanged)
        btn_text = "..."
        self.browse = QPushButton(btn_text, self)
        self.browse.clicked.connect(self.browseFile)
        self.browse.setMaximumWidth(self.browse.height())
        self.browse.setObjectName(self.name())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit)
        layout.addWidget(self.browse)

        kw_def = path.keyword().definition
        self.udefault = kw_def.get('defaut')
        self.umin = kw_def.get('val_min')
        self.umax = kw_def.get('val_max')

        model.rowsAboutToBeInserted.connect(self._beforeUpdate)
        model.rowsInserted.connect(self._afterUpdate)
        model.rowsAboutToBeRemoved.connect(self._beforeUpdate)
        model.rowsRemoved.connect(self._afterUpdate)
        self.valueChanged.connect(self.updateMeshView)
        self.meshFileChanged.connect(self.meshview().displayMEDFileName)

        # Set the initial combobox state as undefined
        self.edit.setCurrentIndex(-1)

    def currentFilename(self):
        """
        Gets the file name of currently selected item in combobox.
        """
        index = self.edit.currentIndex()
        return self.edit.itemData(index, Role.CustomRole) \
            if index >= 0 else None

    def setCurrentFilename(self, filename):
        """
        Sets the given file name as current item in the combobox.

        Arguments:
            filename (str): File path.
        """
        if filename:
            index = self.edit.findData(filename, Role.CustomRole)
            if index == -1:
                if self.edit.model().basename_conflict(filename):
                    # Set "UnitPanel" as context to avoid duplicate translation
                    #     with `UnitPanel.setCurrentFilename`.
                    # If you change the message text below,
                    #     change it there as well.
                    msg = translate("UnitPanel",
                                    "There is already a file in this stage"
                                    " whose basename is '{0}'.\n"
                                    "Please rename the file before you add it "
                                    "to the study.")
                    QMessageBox.critical(self, "AsterStudy",
                                         msg.format(os.path.basename(filename)))
                    return
                try:
                    unit = self.edit.model().addItem(filename,
                                                     self.udefault,
                                                     self.umin,
                                                     self.umax)
                except ValueError:
                    msg = translate("ParameterPanel",
                                    "Could not find available file"
                                    " descriptors in the range [%d, %d]."
                                    "\nThe given file would not be set.")
                    QMessageBox.critical(self, "AsterStudy",
                                         msg % (self.umin, self.umax))
                else:
                    self.edit.setCurrentIndex(self.edit.findData(unit,
                                                                 Role.IdRole))
            else:
                self.edit.setCurrentIndex(index)
        else:
            self.edit.setCurrentIndex(0)
        self.valueChanged.emit()

    def currentUnit(self):
        """
        Gets the unit of currently selected item in combobox.
        """
        index = self.edit.currentIndex()
        if index < 0:
            return None
        unit = self.edit.itemData(index, Role.IdRole)
        if unit < -1:
            unit = self.edit.model().file2unit(self.currentFilename(),
                                               self.udefault,
                                               self.umin,
                                               self.umax)
        return unit

    def setCurrentUnit(self, unit):
        """
        Sets the given file with given unit as current item in the combobox.

        Arguments:
            unit (int): File unit.
        """
        index = self.edit.findData(unit, Role.IdRole)
        if index == -1 and unit is not None:
            try:
                newunit = self.edit.model().addItem(None, unit,
                                                    self.umin, self.umax)
                index = self.edit.findData(newunit, Role.IdRole)
            except ValueError:
                msg = translate("ParameterPanel",
                                "Could not find available file"
                                " descriptors in the range [%d, %d]."
                                "\nThe given file would not be set.")
                QMessageBox.critical(self, "AsterStudy",
                                     msg % (self.umin, self.umax))
        self.edit.setCurrentIndex(index)
        self.valueChanged.emit()

    @pyqtSlot()
    def browseFile(self):
        """
        Called when '...' button is clicked to browse file or define file name.

        Allows selection of existent file or a new file name definition.
        """
        mode = 0
        param_def = self.path().keyword()
        if param_def is not None and hasattr(param_def, "definition"):
            defin = param_def.definition
            if defin.get('inout') in ('in', 'inout'):
                mode = 1

        typed_name = self.edit.currentText()
        title = translate("ParameterPanel", "Select file")
        filename = get_file_name(mode=mode, parent=self.edit, title=title,
                                 url=typed_name, filters=common_filters())
        if filename:
            self.setCurrentFilename(filename)

    def value(self):
        """
        Get value stored in the editor.

        Returns:
            str: Value chosen by the user.
        """
        unit = self.currentUnit()
        fname = self.currentFilename()
        return {unit: fname if fname is not None else ''}

    def setValue(self, value):
        """
        Set the value into editor.

        Arguments:
            value (str): Parameter's value.
        """
        if value and isinstance(value, dict):
            value = value.keys()[0]

        if value is not None and \
                not isinstance(value, int):
            raise ValueError("Not supported value type")

        self.setCurrentUnit(value)

    def forceNoDefault(self):
        """
        This method is used to ignore 'default' attribute of *Unit*
        keyword.

        Returns
            bool: *True*.
        """
        return True

    @pyqtSlot()
    def updateMeshView(self):
        """Updates mesh view when value is changed."""
        filename = self.edit.currentData(Role.CustomRole)
        if is_medfile(filename) or is_reference(filename):
            meshname = get_medfile_meshes(filename)[0]
            self.meshFileChanged.emit(filename, meshname, 1.0, False)

    # pragma pylint: disable=unused-argument
    @pyqtSlot("QModelIndex", int, int)
    def _beforeUpdate(self, index, start, end):
        """
        Called when rows are about to be inserted to model or removed from it.
        """
        self._prev_index = self.edit.currentData(Role.IdRole)

    # pragma pylint: disable=unused-argument
    @pyqtSlot("QModelIndex", int, int)
    def _afterUpdate(self, index, start, end):
        """Called when rows are inserted to model or removed from it."""
        self.edit.setCurrentIndex(self.edit.findData(self._prev_index,
                                                     Role.IdRole))


class ParameterVariableSelectEditor(ParameterCommandSelectEditor):
    """Editor for python variable selector, based on combo-box widget."""

    class Creator(ParameterEditorFactoryCreator):
        """Class for factor editor creation."""

        # pragma pylint: disable=no-self-use
        def createEditor(self, path, parent):
            """
            Create editor.

            Arguments:
                path: Parameter keyword catalog path.
                parent (QWidget): parent widget
            """
            editor = None
            kw_def = path.keyword()
            if kw_def is not None:
                defin = kw_def.definition
                if 'into' not in defin:
                    typeid = get_cata_typeid(kw_def)
                    if typeid == IDS.simp:
                        typ_attr = defin.get('typ')
                        if isinstance(typ_attr, (tuple, list)) and typ_attr:
                            typ_attr = typ_attr[0]
                        if typ_attr in ('I', 'R', 'TXM'):
                            editor = ParameterVariableSelectEditor(path,
                                                                   parent)
            return editor

    def __init__(self, path, parent=None):
        """
        Create editor.

        Arguments:
            parent (Optional[QWidget]): Parent widget.
        """
        super(ParameterVariableSelectEditor, self).__init__(path, parent)

        self.edit.activated.connect(self._onAddVariable)


    # pragma pylint: disable=no-self-use
    def icon(self):
        """
        Get icon associated with the editor.

        Returns:
            str: icon file name.
        """
        return "as_ico_variable.png"

    def description(self):
        """
        Get description associated with the editor.

        This method must be implemented in sub-classes.
        Default implementation returns None.

        Returns:
            str: description string.
        """
        return translate("ParameterPanel", "Select python variable")

    def setValue(self, value):
        """
        Set the value into editor.

        Arguments:
            value (str): Parameter's value.
        """
        if value is not None and \
                not isinstance(value, Variable):
            raise ValueError("Not supported value type")

        super(ParameterVariableSelectEditor, self).setValue(value)

    def updateEditContext(self, context):
        """
        Invoked when edit context changed.
        """
        if context == self.EditContext.Variables:
            self._updateList()

    def _specialItems(self):
        """
        Gets the special selector items.

        Returns:
            [(str, int)]: list of pairs name and id.
        """
        specs = super(ParameterVariableSelectEditor, self)._specialItems()
        addvar = translate("ParameterPanel", "<Add Variable...>")
        specs.append((addvar, -1))
        return specs

    # pragma pylint: disable=no-self-use
    def _reorderList(self, lst):
        """
        Reorder the list.

        Arguments:
            lst ([Command]): List of commands
        Returns:
            [Command]: Reordered command list.
        """
        return lst

    def _onAddVariable(self, index):
        """
        Invoke 'Add Variable' operation. Calling when user select
        '<Add Variable>' item in combobox.
        """
        if self.edit.itemData(index) >= 0:
            return

        parampanel = parameterPanel(self)
        astergui = parampanel.astergui()
        varpanel = VariablePanel(astergui, owner=parampanel)
        varpanel.stage = self.path().command().stage
        varpanel.destroyed.connect(self._onAddVariableFinished)
        astergui.workSpace().panel(Panel.Edit).setEditor(varpanel)

    def _onAddVariableFinished(self):
        """
        Invoked when 'Add Variable' operation was finished.
        """
        oldset = {}
        for v in self.cmdlist:
            oldset[v.uid] = 0

        self.changeEditContext(self.EditContext.Variables)

        newvar = None
        for i in self.cmdlist:
            if i.uid not in oldset:
                newvar = i
                break

        self.setValue(newvar)


class ParameterMacroEditor(ParameterLineEditor):
    """Macro editor based on line edit widget."""

    class Creator(ParameterEditorFactoryCreator):
        """Class for line editor creation."""

        # pragma pylint: disable=no-self-use
        def createEditor(self, path, parent):
            """
            Create editor.

            Arguments:
                path: Parameter keyword catalog path.
                parent (QWidget): parent widget
            """
            editor = None
            kw_def = path.keyword()
            if kw_def is not None:
                defin = kw_def.definition
                if 'into' not in defin:
                    typeid = get_cata_typeid(kw_def)
                    if typeid == IDS.simp:
                        typ_attr = defin.get('typ')
                        if typ_attr is not None and \
                                not isinstance(typ_attr, (tuple, list)):
                            typ_attr = [typ_attr]
                        is_macro = False
                        for i in typ_attr:
                            if is_subclass(i,
                                           CATA.package('DataStructure').CO):
                                is_macro = True
                                break
                        if is_macro:
                            editor = ParameterMacroEditor(path, parent)
            return editor

    def __init__(self, path, parent=None):
        """
        Create editor.

        Arguments:
            parent (Optional[QWidget]): Parent widget.
        """
        super(ParameterMacroEditor, self).__init__(path, parent)

        validator = QRegExpValidator(QRegExp("[A-Za-z]{1}\\w{0,7}$"))
        self.edit.setValidator(validator)

    # pragma pylint: disable=no-self-use
    def icon(self):
        """
        Get icon associated with the editor.

        This method must be implemented in sub-classes.
        Default implementation returns None.

        Returns:
            str: icon file name.
        """
        return "as_ico_macro.png"

    def description(self):
        """
        Get description associated with the editor.

        This method must be implemented in sub-classes.
        Default implementation returns None.

        Returns:
            str: description string.
        """
        return translate("ParameterPanel", "Enter new result name")

    def value(self):
        """
        Get value stored in the editor.

        Result's type depends on the parameter's description.

        Returns:
            *CO*: *CO* object created using the name stored in the editor.
        """
        return CO(self.edit.text())

    def setValue(self, value):
        """
        Set the value into editor.

        Arguments:
            value (int, float or str): Parameter's value.
        """
        if value is not None and \
                not isinstance(value, CO):
            raise ValueError("Not supported value type")
        txt = value.name if value is not None else ""
        self.edit.setText(txt)


class ParameterSequenceEditor(ParameterEditor):
    """Sequence (embeded list) parameter's editor."""

    class Creator(ParameterEditorFactoryCreator):
        """Class for sequence editor creation."""

        # pragma pylint: disable=no-self-use
        def createEditor(self, path, parent):
            """
            Create editor.

            Arguments:
                path: Parameter keyword catalog path.
                parent (QWidget): parent widget
            """
            editor = None
            if not behavior().external_list and \
                    path.isKeywordSequence() and not path.isInSequence():
                editor = ParameterSequenceEditor(path, parent)
            return editor

    def __init__(self, path, parent=None):
        """
        Create editor.

        Arguments:
            path (ParameterPath): parameter keyword path in catalogue
            parent (Optional[QWidget]): Parent widget.
        """
        super(ParameterSequenceEditor, self).__init__(path, parent)

        base = QHBoxLayout(self)
        base.setContentsMargins(0, 0, 0, 0)

        main = QFrame(self)
        main.setFrameStyle(QFrame.Panel | QFrame.Raised)
        base.addWidget(main)

        layout = QHBoxLayout(main)
        layout.setContentsMargins(0, 0, 0, 0)

        tbar = QToolBar(main)
        tbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        layout.addWidget(tbar)

        self._expand = QToolButton(tbar)
        self._expand.setObjectName(path.name() + "_expand")
        self._expand.setArrowType(Qt.RightArrow)

        self._info = QLabel(tbar)
        self._info.setObjectName(path.name() + "_info")
        self._info.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        self._add = QToolButton(tbar)
        self._add.setIcon(load_icon("as_pic_add_row.png", size=16))
        self._add.setObjectName(path.name() + "_add")

        tbar.addWidget(self._expand)
        sp1 = QWidget(tbar)
        sp1.setFixedWidth(5)
        tbar.addWidget(sp1)
        tbar.addWidget(self._info)
        sp2 = QWidget(tbar)
        sp2.setFixedWidth(5)
        tbar.addWidget(sp2)
        tbar.addWidget(self._add)

        tbar.setIconSize(QSize(16, 16))

        self._add.clicked.connect(self._addClicked)
        self._expand.clicked.connect(self._expandClicked)

        from . views import ParameterView
        self._panel = ParameterView(parameterPanel(self),
                                    item_path=path, parent_item=None,
                                    parent=parent)
        self._panel.setFrameStyle(QFrame.Box | QFrame.Sunken)
#        self._panel.setFrameStyle(QFrame.Panel | QFrame.Plain)

        self._panel.appendEnabled.connect(self._add.setEnabled)
        self._panel.checkConstraints.connect(self._updatePanelState)

        self._info.installEventFilter(self)

        self._updatePanelState()

    def sequencePanel(self):
        """
        Gets the sequence panel widget

        Returns:
            (QWidget): Panel with sequence items
        """
        return self._panel

    def value(self):
        """
        Get value stored in the editor.
        """
        return self._panel.itemValue() if self._panel is not None else None

    def setValue(self, value):
        """
        Set the value into editor.
        """
        if self._panel is not None:
            self._panel.setItemValue(value)

    def expand(self):
        """
        Expand the panel
        """
        self.setExpanded(True)

    def collaps(self):
        """
        Expand the panel
        """
        self.setExpanded(False)

    def isExpanded(self):
        """
        Gets the expand state of panel

        Returns:
            (bool): True if the panel is expanded.
        """
        return self._expand.arrowType() == Qt.DownArrow

    def setExpanded(self, expand):
        """
        Expand or collaps the panel
        """
        self._expand.setArrowType(Qt.DownArrow if expand else Qt.RightArrow)
        self._updatePanelVisibility()

    def updateTranslations(self):
        """
        Update translations in GUI elements.
        """
        num = len(self._panel.childItems()) if self._panel is not None else 0
        txt = str(num) + " " + (translate("ParameterPanel", "item") \
                                    if num == 1 else \
                                    translate("ParameterPanel", "items"))
        self._info.setText(txt)

    def setEnabled(self, on):
        """
        Enabled/disable the panel with it.
        """
        super(ParameterSequenceEditor, self).setEnabled(on)

        if self._panel is not None:
            self._panel.setEnabled(on)

    def eventFilter(self, obj, event):
        """
        Translate click from label to expand/collapse button
        """
        if obj == self._info and event.type() == QEvent.MouseButtonPress:
            self._expand.click()
            return True
        return False

    def showEvent(self, event):
        """
        Reimplemented for internal reasons
        """
        super(ParameterSequenceEditor, self).showEvent(event)
        self._updatePanelVisibility()

    def hideEvent(self, event):
        """
        Reimplemented for internal reasons
        """
        super(ParameterSequenceEditor, self).hideEvent(event)
        self._updatePanelVisibility()

    def _updatePanelVisibility(self):
        if self._panel is None:
            return

        vis = self.isExpanded() and self.isVisibleTo(self.parentWidget()) \
            and len(self._panel.childItems()) > 0
        self._panel.setVisible(vis)

    def _expandClicked(self):
        """
        Invoked when 'Expand' button is clicked.
        """
        self.setExpanded(not self.isExpanded())

    def _addClicked(self):
        """
        Invoked when 'Add' button is clicked.
        """
        if self._panel is not None:
            self._panel.createItem()
            self.expand()

    def _updatePanelState(self):
        self.updateTranslations()
        self._updatePanelVisibility()
        empty = self._panel is None or len(self._panel.childItems()) == 0
        self._expand.setEnabled(not empty)


class ParameterSubEditor(ParameterEditor):
    """`FACT` parameter's editor."""

    class ListCreator(ParameterEditorFactoryCreator):
        """Class for list editor creation."""

        # pragma pylint: disable=no-self-use
        def createEditor(self, path, parent):
            """
            Create editor.

            Arguments:
                path: Parameter keyword catalog path.
                parent (QWidget): parent widget
            """
            editor = None
            if path.isKeywordSequence() and not path.isInSequence():
                editor = ParameterSubEditor(EditorLink.List, path, parent)
            return editor

    class FactCreator(ParameterEditorFactoryCreator):
        """Class for factor editor creation."""

        # pragma pylint: disable=no-self-use
        def createEditor(self, path, parent):
            """
            Create editor.

            Arguments:
                path: Parameter keyword catalog path.
                parent (QWidget): parent widget
            """
            editor = None
            kw_def = path.keyword()
            if kw_def is not None:
                if get_cata_typeid(kw_def) == IDS.fact:
                    editor = ParameterSubEditor(EditorLink.Fact,
                                                path, parent)
            return editor

    class TableCreator(ParameterEditorFactoryCreator):
        """Class for table editor creation."""

        # pragma pylint: disable=no-self-use
        def createEditor(self, path, parent):
            """
            Create editor.

            Arguments:
                path: Parameter keyword catalog path.
                parent (QWidget): parent widget
            """
            editor = None
            if path.keywordType() == KeywordType.Function:
                editor = ParameterSubEditor(EditorLink.Table, path, parent)
            return editor


    class MeshGroupCreator(ParameterEditorFactoryCreator):
        """Class for list editor creation."""

        # pragma pylint: disable=no-self-use
        def createEditor(self, path, parent):
            """
            Create editor.

            Arguments:
                path: Parameter keyword catalog path.
                parent (QWidget): parent widget
            """
            editor = None
            if path.keywordType() == KeywordType.MeshGroup:
                editor = ParameterSubEditor(EditorLink.GrMa, path, parent)
            return editor

    def __init__(self, link, path, parent=None):
        """
        Create editor.

        Arguments:
            parent (Optional[QWidget]): Parent widget.
        """
        super(ParameterSubEditor, self).__init__(path, parent)
        self.link = link
        self.storage = None

        base = QHBoxLayout(self)
        base.setContentsMargins(0, 0, 0, 0)

        main = QFrame(self)
        main.setFrameStyle(QFrame.Panel | QFrame.Raised)
        base.addWidget(main)

        layout = QHBoxLayout(main)
        layout.setContentsMargins(0, 0, 0, 0)

        txt = translate("ParameterPanel", "Edit...")
        self.edit = ParameterButton(path, txt, main)
        self.edit.setObjectName(self.name())
        self.edit.clicked.connect(self._editClicked)

        layout.addWidget(self.edit)

    def value(self):
        """
        Get value stored in the editor.
        """
        return self.storage

    def setValue(self, value):
        """
        Set the value into editor.
        """
        self.storage = value
        self.updateTranslations()

    def updateTranslations(self):
        """
        Update translations.
        """
        value = self.value()
        extlist = behavior().external_list
        mode = behavior().content_mode
        if not self.path().isInSequence() or extlist:
            value = None
        self.edit.setContents(value, mode)

    def _editClicked(self):
        """
        Invoked when push button 'Edit' is clicked.
        """
        self.linkActivated.emit(self.link)


class ParameterMeshGroupSelectionEditor(ParameterSubEditor):
    """Mesh group selection parameter's editor."""

    class Creator(ParameterEditorFactoryCreator):
        """Class for list editor creation."""

        # pragma pylint: disable=no-self-use
        def createEditor(self, path, parent):
            """
            Create editor.

            Arguments:
                path: Parameter keyword catalog path.
                parent (QWidget): parent widget
            """
            editor = None
            if path.keywordType() == KeywordType.MeshGroup:
                editor = ParameterMeshGroupSelectionEditor(EditorLink.GrMa,
                                                           path, parent)
            return editor

    def __init__(self, link, path, parent=None):
        """
        Create editor.

        Arguments:
            parent (Optional[QWidget]): Parent widget.
        """
        super(ParameterMeshGroupSelectionEditor, self).\
            __init__(link, path, parent)

    def updateTranslations(self):
        """
        Update translations.
        """
        extlist = behavior().external_list
        value = self.value() if not extlist else None
        mode = behavior().content_mode
        self.edit.setContents(value, mode)


class ParameterMeshSelectionEditor(ParameterLineEditor):
    """Mesh group selection based on line edit widget."""

    class Creator(ParameterEditorFactoryCreator):
        """Class for factor editor creation."""

        # pragma pylint: disable=no-self-use
        def createEditor(self, path, parent):
            """
            Create editor.

            Arguments:
                path: Parameter keyword catalog path.
                parent (QWidget): parent widget
            """
            editor = None
            kw_def = path.keyword().definition
            typ = kw_def.get('typ')
            if isinstance(typ, (tuple, list)):
                if len(typ) > 0:
                    # TODO: it is not clear how to create editor
                    # in case of heterogeneous types
                    typ = typ[0]
                else:
                    typ = None
            if is_subclass(typ, CATA.package('DataStructure').GEOM):
                editor = ParameterMeshSelectionEditor(path, parent)
            return editor

    def __init__(self, path, parent=None):
        """
        Create editor.

        Arguments:
            parent (Optional[QWidget]): Parent widget.
        """
        super(ParameterMeshSelectionEditor, self).__init__(path, parent)
