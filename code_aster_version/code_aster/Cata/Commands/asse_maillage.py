# coding=utf-8
# --------------------------------------------------------------------
# Copyright (C) 1991 - 2017 - EDF R&D - www.code-aster.org
# This file is part of code_aster.
#
# code_aster is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# code_aster is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with code_aster.  If not, see <http://www.gnu.org/licenses/>.
# --------------------------------------------------------------------

# person_in_charge: jacques.pellet at edf.fr
from code_aster.Cata.Syntax import *
from code_aster.Cata.DataStructure import *
from code_aster.Cata.Commons import *


ASSE_MAILLAGE=OPER(nom="ASSE_MAILLAGE",op= 105,sd_prod=maillage_sdaster,
                   fr=tr("Assembler deux maillages pour en former un nouveau"),
                   reentrant='n',
         MAILLAGE_1 =  SIMP(statut='o',typ=maillage_sdaster,),
         MAILLAGE_2 =  SIMP(statut='o',typ=maillage_sdaster,),
         OPERATION  =  SIMP(statut='o',typ='TXM',into=("SOUS_STR","SUPERPOSE","COLLAGE"),),
         b_collage  =  BLOC(condition = """equal_to("OPERATION", 'COLLAGE')""",
           COLLAGE  =  FACT(statut='o',
              GROUP_MA_1     =SIMP(statut='o',typ=grma),
              GROUP_MA_2     =SIMP(statut='o',typ=grma),
                             ),
                           ),
)  ;
