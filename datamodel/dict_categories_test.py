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

# pragma pylint: skip-file
# to disable 'duplicate-code' with dict_categories.py

"""
Old categories only used for unittests.
"""

from __future__ import unicode_literals

from collections import OrderedDict


__all__ = ["CATEGORIES_DEFINITION"]


CATEGORIES_DEFINITION = OrderedDict()

CATEGORIES_DEFINITION["Mesh"] = [
    "LIRE_MAILLAGE",
    "MODI_MAILLAGE",
    "CREA_MAILLAGE",
    "ASSE_MAILLAGE",
    ]

CATEGORIES_DEFINITION["Finite Element"] = [
    "AFFE_MODELE",
    "AFFE_CARA_ELEM",
    "MODI_MODELE",
    ]

CATEGORIES_DEFINITION["Material"] = [
    "DEFI_MATERIAU",
    "DEFI_COMPOSITE",
    "AFFE_MATERIAU",
    ]

CATEGORIES_DEFINITION["Functions and Lists"] = [
    "DEFI_FONCTION",
    "DEFI_CONSTANTE",
    "DEFI_NAPPE",
    "FORMULE",
    "CALC_FONCTION",
    "CALC_FONC_INTERP",
    "DEFI_LIST_REEL",
    "DEFI_LIST_INST",
    ]

CATEGORIES_DEFINITION["BC and Load"] = [
    "AFFE_CHAR_CINE",
    "AFFE_CHAR_CINE_F",
    "AFFE_CHAR_MECA",
    "AFFE_CHAR_MECA_F",
    "AFFE_CHAR_THER",
    "AFFE_CHAR_THER_F",
    "DEFI_CONTACT",
    ]

CATEGORIES_DEFINITION["Pre Processing"] = [
    "GENE_ACCE_SEISME",
    "MODE_STATIQUE",
    "MODE_NON_LINE",
    "CALC_MODES",
    ]

CATEGORIES_DEFINITION["Analysis"] = [
    "MECA_STATIQUE",
    "STAT_NON_LINE",
    "DYNA_NON_LINE",
    "DYNA_ISS_VARI",
    "DYNA_VIBRA",
    "THER_LINEAIRE",
    "CALC_EUROPLEXUS",
    "CALC_MISS",
    "SIMU_POINT_MAT",
    ]

CATEGORIES_DEFINITION["Post Processing"] = [
    "POST_CHAMP",
    "POST_ELEM",
    "POST_RELEVE_T",
    "CALC_CHAMP",
    "CALC_ERREUR",
    "CREA_CHAMP",
    "MACR_LIGN_COUPE",
    "MACR_ADAP_MAIL",
    "RECU_FONCTION",
    ]

CATEGORIES_DEFINITION["Fracture and Fatigue"] = [
    "CALC_FATIGUE",
    "CALC_G",
    "CALC_GP",
    "DEFI_FISS_XFEM",
    "DEFI_FOND_FISS",
    "MODI_MODELE_XFEM",
    "POST_CHAM_XFEM",
    "POST_CZM_FISS",
    "POST_FATIGUE",
    "POST_K1_K2_K3",
    "POST_K_BETA",
    "POST_K_TRANS",
    "POST_MAIL_XFEM",
    "POST_RCCM",
    "POST_RUPTURE",
    "PROPA_FISS",
    "RAFF_GP",
    "RAFF_XFEM",
    "RECA_WEIBULL",
    ]

CATEGORIES_DEFINITION["Output"] = [
    "IMPR_RESU",
    "IMPR_RESU_SP",
    "IMPR_FONCTION",
    "IMPR_TABLE",
    ]
