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

"""Common purpose utilities and services."""

from __future__ import unicode_literals

from .base_utils import (add_extension, copy_file, current_time,
                         get_absolute_dirname, get_absolute_path, get_base_name,
                         get_extension, is_subpath, move_file, ping, read_file,
                         rotate_path, same_path, split_text, tail_file, to_str,
                         to_unicode, write_file, Singleton)
from .configuration import CFG, Configuration, ConfigurationError
from .excepthook import enable_except_hook
from .utilities import (auto_dupl_on, bold, CachedValues, clean_text,
                        change_cursor, common_filters, connect, disconnect,
                        debug_message, debug_message2, debug_mode, div, font,
                        format_code, format_expr, from_words,
                        get_directory, get_file_name, hms2s, href,
                        image, is_child, is_contains_word, is_subclass, italic,
                        load_icon, load_icon_set, load_pixmap, LogFiles,
                        not_implemented, old_complex, preformat,
                        recursive_items, show_exception, simplify_separators,
                        to_list, to_type, to_words, translate, underline,
                        update_visibility, valid_filename, wait_cursor,
                        wrap_html)
from .extfiles import (FilesSupplier, MeshElemType, MeshGroupType,
                       external_file, external_files, external_files_callback,
                       get_cmd_groups, get_cmd_mesh, get_medfile_groups,
                       get_medfile_groups_by_type, get_medfile_meshes,
                       is_medfile, is_reference)
from .exceptions import (AsterStudyError, AsterStudyInterrupt, CatalogError,
                         ConversionError, CyclicDependencyError,
                         ExistingSwapError, MissingStudyDirError, RunnerError,
                         StudyDirectoryError)
from .version import version
from .session import AsterStudySession
