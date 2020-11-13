# -*- coding: utf-8 -*-

# Copyright 2017 EDF R&D
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
Variable panel
--------------

This module implements `Edit Variable` panel that allows the user
adding/editing variables within AsterStudy application.

"""

from __future__ import unicode_literals

import inspect

from PyQt5 import Qt as Q

from common import (auto_dupl_on, CyclicDependencyError, connect,
                    disconnect, load_pixmap, translate)
from datamodel.command import Variable

from . import Context, NodeType, get_node_type
from . editionwidget import EditionWidget
from . controller import WidgetController

# note: the following pragma is added to prevent pylint complaining
#       about functions that follow Qt naming conventions;
#       it should go after all global functions
# pragma pylint: disable=invalid-name


class VariablePanel(EditionWidget, WidgetController):
    """Variable panel."""

    class Completer(Q.QCompleter):
        """Completer for variable names."""
        def __init__(self, parent=None):
            """
            Create completer.

            Arguments:
                parent (Optional[QWidget]): Parent widget. Defaults to
                    *None*.
            """
            super(VariablePanel.Completer, self).__init__(parent)
            self.setWidget(parent)
            connect(parent.textChanged, self._onTextChanged)
            connect(self.activated, self._onActivated)

        def uncomplete(self):
            """
            Hide the completer's popup menu.
            """
            if self.popup() is not None:
                self.popup().hide()

        def _completionRange(self):
            """
            Get position of completion prefix in editor.

            Returns:
                (int, int): Start, end indices of completion prefix
                within editor.
            """
            txt = self.widget().text()

            beg = 0
            end = self.widget().cursorPosition()

            rx = Q.QRegExp(VariablePanel.namePattern())
            pos = rx.indexIn(txt[beg:end])
            if pos >= 0:
                beg = pos

            return beg, end

        def _completionText(self):
            """
            Get the current completion prefix from editor.

            Returns:
                str: Completion prefix.
            """
            txt = self.widget().text()
            if txt:
                beg, end = self._completionRange()
                txt = txt[beg:end]
            return txt

        def _onTextChanged(self):
            """
            Process completion when text is changed in editor.
            """
            prefix = self._completionText()
            self.setCompletionPrefix(prefix)

            if self.completionPrefix() and self.completionCount():
                self.complete()
            else:
                self.uncomplete()

        def _onActivated(self, text):
            """
            Insert selected completion into editor.

            Arguments:
                text (str): Selected completion.
            """
            rng = self._completionRange()
            self.widget().setSelection(rng[0], rng[1] - rng[0])
            self.widget().insert(text)
            self.uncomplete()


    def __init__(self, astergui, parent=None, **kwargs):
        """
        Create variable edition panel.

        Arguments:
            astergui (AsterGui): Parent *AsterGui* instance.
            parent (Optional[QWidget]): Parent widget. Defaults to
                *None*.
            kwargs: Keyword arguments.
        """
        super(VariablePanel, self).__init__(parent=parent,
                                            name=translate("VariablePanel",
                                                           "Create variable"),
                                            astergui=astergui, **kwargs)
        self._stage = None
        self._variable = None

        grid = Q.QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)

        grid.addWidget(Q.QLabel(translate("VariablePanel", "Name"),
                                self), 0, 0)
        self._vname = Q.QLineEdit(self)
        self._vname.setObjectName("Name")
        validator = Q.QRegExpValidator(Q.QRegExp(VariablePanel.namePattern()),
                                       self._vname)
        self._vname.setValidator(validator)
        grid.addWidget(self._vname, 0, 1, 1, 2)

        grid.addWidget(Q.QLabel(translate("VariablePanel", "Expression"),
                                self), 1, 0)
        self._vexpr = Q.QLineEdit(self)
        self._vexpr.setObjectName("Expression")
        grid.addWidget(self._vexpr, 1, 1)

        self._vcomp = VariablePanel.Completer(self._vexpr)

        self._vins = Q.QToolButton(self)
        self._vins.setArrowType(Q.Qt.DownArrow)
        self._vins.setPopupMode(Q.QToolButton.InstantPopup)
        self._vins.setMenu(Q.QMenu(self._vins))
        grid.addWidget(self._vins, 1, 2)

        label = Q.QLabel(translate("VariablePanel", "Value"), self)
        grid.addWidget(label, 2, 0)
        self._veval = Q.QLineEdit(self)
        self._veval.setReadOnly(True)
        self._veval.setFrame(False)
        self._veval.setObjectName("Value")

        fnt = self._veval.font()
        fnt.setBold(True)
        fnt.setItalic(True)
        self._veval.setFont(fnt)

        pal = self._veval.palette()
        pal.setColor(self._veval.backgroundRole(),
                     label.palette().color(label.backgroundRole()))
        self._veval.setPalette(pal)

        grid.addWidget(self._veval, 2, 1, 1, 2)

        grid.addWidget(Q.QLabel(translate("VariablePanel", "Comment"),
                                self), 3, 0)
        self._vcomment = Q.QPlainTextEdit(self)
        self._vcomment.setObjectName("Comment")
        grid.addWidget(self._vcomment, 3, 1, 1, 2)
        grid.setRowStretch(4, 1)

        self.setFocusProxy(self._vname)

        connect(self._vname.textChanged, self._onNameChanged)
        connect(self._vexpr.textChanged, self._onExpressionChanged)
        connect(self._vcomment.textChanged, self.updateButtonStatus)
        connect(self._vins.menu().triggered, self._onMenuTriggered)

        self._reconnect()
        self._updateState()
        self._onExpressionChanged()

    @staticmethod
    def namePattern():
        """
        Get variable name regexp pattern.

        Returns:
            str: Regexp pattern for Python variable name.
        """
        return '[A-Za-z]{1}\\w*$'

    @property
    def variable(self):
        """
        Get variable being edited.

        Returns:
            Variable: Variable being edited (*None* in creation mode).
        """
        return self._variable

    @variable.setter
    def variable(self, variable):
        """
        Set variable to be edited.

        Arguments:
            variable (Variable): Variable to be edited.
        """
        if self._variable is variable:
            return

        self._variable = variable

        if variable is not None:
            self._setVariableName(variable.name)
            self._setVariableExpression(variable.expression)
            comment = variable.comment.content \
                    if variable.comment is not None else ''
            self._setVariableComment(comment)

        self._reconnect()
        self._updateState()
        self._onExpressionChanged()

    @property
    def stage(self):
        """
        Get stage.

        Returns:
            Stage: Stage being used.
        """
        # pragma pylint: disable=no-member
        stage = self._stage
        if self.variable is not None:
            stage = self.variable.stage
        if stage is None:
            selected = self.astergui().selected(Context.DataSettings)
            if selected:
                obj = self.astergui().study().node(selected[0])
                obj_type = get_node_type(obj)
                if obj_type in (NodeType.Stage,):
                    stage = obj
                elif obj_type in (NodeType.Category, NodeType.Command,
                                  NodeType.Variable, NodeType.Macro,
                                  NodeType.Comment):
                    stage = obj.stage
        return stage

    @stage.setter
    def stage(self, stage):
        """
        Set stage.

        Arguments:
            stage (Stage): Stage to be used.
        """
        self._stage = stage
        self._reconnect()
        self._updateState()

    def isButtonEnabled(self, button):
        """
        Redefined from *EditionWidget* class.
        """
        # pragma pylint: disable=no-member
        result = True
        if button in [Q.QDialogButtonBox.Ok, Q.QDialogButtonBox.Apply]:
            result = self._isValidName(self._variableName()) and \
                len(self._veval.text()) and self.stage is not None
            if self.variable is not None:
                name_changed = self.variable.name != self._variableName()
                expr_changed = self.variable.expression != \
                    self._variableExpression()
                comment = self.variable.comment.content \
                    if self.variable.comment is not None else ''
                comment_changed = comment != self._variableComment()
                result = result and (name_changed or expr_changed or \
                                         comment_changed)
        return result

    def applyChanges(self):
        """
        Redefined from *EditionWidget* class.
        """
        # pragma pylint: disable=no-member
        result = False

        var = self.variable
        edit = var is not None

        name = self._variableName()
        expr = self._variableExpression()
        comment = self._variableComment()

        if edit:
            try:
                with auto_dupl_on(self.stage.model.current_case):
                    var.update(expr, name)
                    if comment:
                        var.comment = comment
                    elif var.comment is not None:
                        var.comment.delete()
                    result = True
            except CyclicDependencyError:
                message = translate("AsterStudy", "Cyclic dependency detected")
                Q.QMessageBox.critical(self, "AsterStudy", message)
                result = False
        else:
            try:
                with auto_dupl_on(self.stage.model.current_case):
                    if self.stage is not None:
                        var = self.stage.add_variable(name, expr)
                        if comment:
                            var.comment = comment
            except StandardError:
                var = None

            result = var is not None

        if self.controllerOwner() is None:
            if result:
                if edit:
                    op_name = translate("VariablePanel", "Edit variable")
                else:
                    op_name = translate("VariablePanel", "Create variable")
                self.astergui().study().commit(op_name)
                self.astergui().update(autoSelect=var,
                                       context=Context.DataSettings)
            else:
                self.astergui().study().revert()

        self._updateState()

    def _updateState(self):
        """
        Update panel's state.
        """
        if self.variable is None:
            op_name = translate("VariablePanel", "Create variable")
            op_pixmap = load_pixmap("as_pic_new_variable.png")
        else:
            op_name = translate("VariablePanel", "Edit variable")
            op_pixmap = load_pixmap("as_pic_edit_variable.png")
        self._controllername = op_name
        self.setWindowTitle(op_name)
        self.setPixmap(op_pixmap)

        self._vins.menu().clear()

        vnames = sorted(self._variableNames())
        fnames = sorted([i + '()' for i in self._functionNames()])

        for i in vnames:
            self._vins.menu().addAction(i)

        if vnames and fnames:
            self._vins.menu().addSeparator()

        for f in fnames:
            a = self._vins.menu().addAction(f)
            f = a.font()
            f.setItalic(True)
            a.setFont(f)

        self._vins.menu().setEnabled(not self._vins.menu().isEmpty())
        self._vcomp.setModel(Q.QStringListModel(vnames + fnames, self._vcomp))

        self.updateButtonStatus()

    def _variableName(self):
        """
        Gets the current variable name

        Returns:
            str: current variable name string
        """
        return self._vname.text()

    def _setVariableName(self, name):
        """
        Sets the current variable name

        Arguments:
            name (str): variable name string
        """
        self._vname.setText(name)

    def _variableExpression(self):
        """
        Gets the current variable expression

        Returns:
            str: current variable expression string
        """
        return self._vexpr.text()

    def _setVariableExpression(self, val):
        """
        Sets the current variable expression

        Arguments:
            val (str): variable expression string
        """
        self._vexpr.setText(val)

    def _variableComment(self):
        """
        Gets the current variable comment

        Returns:
            str: current variable comment string
        """
        return self._vcomment.toPlainText()

    def _setVariableComment(self, val):
        """
        Sets the current variable comment

        Arguments:
            val (str): variable comment string
        """
        self._vcomment.setPlainText(val)

    def _variableNames(self, full=False):
        """
        Get names of variables available in current context.

        Arguments:
            full (Optional[bool]): Get full context when *True*; else
                get partial context. See `_getContext()`.

        Returns:
            list[str]: Names of variables.

        See also:
            `_getContext()`
        """
        names = []
        ctx = self._getContext(full)
        for name in ctx:
            if not inspect.isbuiltin(ctx[name]) and \
                    not inspect.isfunction(ctx[name]):
                names.append(name)
        return names

    def _functionNames(self):
        """
        Get names of functions available in current context.

        Returns:
            list[str]: Names of functions.
        """
        names = []
        ctx = self._getContext(True)
        for name in ctx:
            if inspect.isbuiltin(ctx[name]) or \
                    inspect.isfunction(ctx[name]):
                names.append(name)
        return names

    def _getContext(self, full=False):
        """
        Get evaluation context.

        If *full* is *True*, method return complete existing context,
        i.e. all known variables and functions; otherwise, only valid
        context if returned - in particular, variables that have been
        added after one currently being edited are not returned; this
        is needed to avoid cyclic dependencies.

        Arguments:
            full (Optional[bool]): Get full context when *True*; else
                get partial context.

        Returns:
            dict: Context dictionary, where key is a object's name and
            value is object itself; variable or function.
        """
        context = {}
        if self.stage is not None and self.stage.is_graphical_mode(): # pragma pylint: disable=no-member
            constraint = self.variable if not full else None
            context = Variable.context(self.stage, constraint)
        return context

    # pragma pylint: disable=no-self-use
    def _isValidName(self, name):
        """
        Check variable name's validity.

        Arguments:
            name (str): Name being checked.

        Returns:
            bool: *True* if name is valid; *False* otherwise.
        """
        return len(name) > 0 and name not in self._variableNames()

    # pragma pylint: disable=eval-used
    def _evalExpression(self, expr, ctx=None):
        """
        Evaluate specified expression with the given context.

        Arguments:
            expr (str): Expression being evaluated.
            ctx (Optional[dict]): Evaluation context. Defaults to
                *None* (in that case current context is used).

        Returns:
            str: Result of evalution or *None* if an expression
            cannot be evaluated.
        """
        val = None
        context = ctx or self._getContext()
        try:
            val = eval(expr, {}, context)
        except StandardError:
            val = None
        return val

    def _onMenuTriggered(self, action):
        """
        Invoked when an item is activated in "add variable" button's
        context menu.

        Arguments:
            action (QAction): Action activated from menu.
        """
        var = action.text()
        self._vexpr.insert(var)
        pos = self._vexpr.cursorPosition()
        self._vexpr.setFocus()
        self._vexpr.setCursorPosition(pos)
        self._vcomp.uncomplete()

    def _onNameChanged(self):
        """
        Invoked when name of variable is being edited.
        """
        self.updateButtonStatus()

    def _onExpressionChanged(self):
        """
        Invoked when variable expression is being edited.
        """
        val = self._evalExpression(self._variableExpression())
        if val is None:
            self._veval.setText('')
        elif isinstance(val, basestring):
            self._veval.setText("'{0}'".format(val))
        else:
            self._veval.setText("{0}".format(val))

        pal = self._vexpr.palette()
        color = Q.Qt.black if val is not None else Q.Qt.red
        pal.setColor(self._vexpr.foregroundRole(), color)
        self._vexpr.setPalette(pal)

        self.updateButtonStatus()

    def _reconnect(self):
        """
        Reconnect selection change event from AsterGui.
        """
        disconnect(self.astergui().selectionChanged, self._updateState)
        if self._variable is None and self._stage is None:
            connect(self.astergui().selectionChanged, self._updateState)
