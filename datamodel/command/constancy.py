# -*- coding: utf-8 -*-

# Copyright 2016 EDF R&D i
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
Constancy Guards
----------------

Implementation of Stage constancy guardence.

"""

from __future__ import unicode_literals

from functools import wraps

def trace_back(method):
    """
    Decorator that retains the calling object in the result
    """

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        """Wrapper"""
        from .basic import Command

        res = method(self, *args, **kwargs)
        if res is not None:
            res.calling_obj = self
            return res

        engine = self._engine # pragma pylint: disable=protected-access
        if isinstance(engine, Command):
            self.calling_obj = engine
        else:
            engine.calling_obj = self

    return wrapper

class ConstContext(object):
    """
    Context manager to not duplicate upon load
    """
    def __init__(self, value):
        """Value tells to what to reset"""
        self.value = value

    def __enter__(self):
        """Actions when entering the context"""
        NonConstStage.DECORATED_CALLER = True

    def __exit__(self, *args):
        """Actions when leaving the context"""
        NonConstStage.DECORATED_CALLER = self.value

class NonConstStage(object):
    """
    Decorator indicating a method modifying self.

    Note:
        Stages are duplicated.
        Only that stage contained by the calling case is modified.
        If there is no calling case, only that stage contained
        by parent stage is modified.
    """

    DECORATED_CALLER = False

    def __init__(self, decorate):
        """
        Initialize decorator

        Note:
            The method is not passed as an arg
                so that decorator arguments can be added later
        """

        self.decorate = decorate

    def __call__(self, method):
        """
        Implementation of the decorator
        """

        @wraps(method)
        def wrapper(this, *args, **kwargs):
            """Wrapper"""

            if type(self).DECORATED_CALLER:
                return method(this, *args, **kwargs)

            if not self.decorate:
                with ConstContext(type(self).DECORATED_CALLER):
                    return method(this, *args, **kwargs)

            # if the auto_dupl is not on, just call method
            if not this.model.auto_dupl:
                return method(this, *args, **kwargs)

            with ConstContext(False):
                this.split()
                return method(this, *args, **kwargs)

        return wrapper

class NonConst(object):
    """
    Decorator to auto-duplicate on an operation that modifies
    a Command instance
    """

    def __init__(self):
        """Initializer"""

        pass

    def __call__(self, method):
        """Implementation of the decorator"""

        @wraps(method)
        def wrapper(this, *args, **kwargs):
            """Wrapper"""

            from .basic import Command
            if NonConstStage.DECORATED_CALLER:
                return method(this, *args, **kwargs)

            with ConstContext(False):
                if isinstance(this, Command):
                    if this.model.auto_dupl:
                        this.split()
                        return method(this, *args, **kwargs)

                    # else
                    return method(this, *args, **kwargs)

                # retrieve the command
                cmd = this
                while not isinstance(cmd, Command):
                    cmd = cmd.calling_obj

                if not cmd.model.auto_dupl:
                    return method(this, *args, **kwargs)

                # split it
                cmd.split()

                # apply the method on that object
                return method(this, *args, **kwargs)

        return wrapper
