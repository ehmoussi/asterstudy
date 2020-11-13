#
# Automatically-generated file. Do not edit!
#
#

from code_aster.Cata.Syntax import *
from code_aster.Cata.DataStructure import *
from code_aster.Cata.Commons import *


def C_MFRONT_OFFICIAL():
    keywords = {

        'Iwan' : FACT(statut='f',
            YoungModulus = SIMP(statut='o', typ='R'),
            PoissonRatio = SIMP(statut='o', typ='R'),
            GammaRef = SIMP(statut='o', typ='R'),
            n = SIMP(statut='o', typ='R'),
        ),
        'Iwan_FO' : FACT(statut='f',
            YoungModulus = SIMP(statut='o', typ=fonction_sdaster),
            PoissonRatio = SIMP(statut='o', typ=fonction_sdaster),
            GammaRef = SIMP(statut='o', typ=fonction_sdaster),
            n = SIMP(statut='o', typ=fonction_sdaster),
        ),
        'MetaAcierEPIL_PT' : FACT(statut='f',
            YoungModulus = SIMP(statut='o', typ='R'),
            PoissonRatio = SIMP(statut='o', typ='R'),
            SYY_0 = SIMP(statut='o', typ='R'),
            SYY_1 = SIMP(statut='o', typ='R'),
            SYY_2 = SIMP(statut='o', typ='R'),
            SYY_3 = SIMP(statut='o', typ='R'),
            SYY_4 = SIMP(statut='o', typ='R'),
            ETT_0 = SIMP(statut='o', typ='R'),
            ETT_1 = SIMP(statut='o', typ='R'),
            ETT_2 = SIMP(statut='o', typ='R'),
            ETT_3 = SIMP(statut='o', typ='R'),
            ETT_4 = SIMP(statut='o', typ='R'),
            FK_0 = SIMP(statut='o', typ='R'),
            FK_1 = SIMP(statut='o', typ='R'),
            FK_2 = SIMP(statut='o', typ='R'),
            FK_3 = SIMP(statut='o', typ='R'),
            metaF1 = SIMP(statut='o', typ='R'),
            metaFDF_0 = SIMP(statut='o', typ='R'),
            metaFDF_1 = SIMP(statut='o', typ='R'),
            metaFDF_2 = SIMP(statut='o', typ='R'),
            metaFDF_3 = SIMP(statut='o', typ='R'),
        ),
        'MetaAcierEPIL_PT_FO' : FACT(statut='f',
            YoungModulus = SIMP(statut='o', typ=fonction_sdaster),
            PoissonRatio = SIMP(statut='o', typ=fonction_sdaster),
            SYY_0 = SIMP(statut='o', typ=fonction_sdaster),
            SYY_1 = SIMP(statut='o', typ=fonction_sdaster),
            SYY_2 = SIMP(statut='o', typ=fonction_sdaster),
            SYY_3 = SIMP(statut='o', typ=fonction_sdaster),
            SYY_4 = SIMP(statut='o', typ=fonction_sdaster),
            ETT_0 = SIMP(statut='o', typ=fonction_sdaster),
            ETT_1 = SIMP(statut='o', typ=fonction_sdaster),
            ETT_2 = SIMP(statut='o', typ=fonction_sdaster),
            ETT_3 = SIMP(statut='o', typ=fonction_sdaster),
            ETT_4 = SIMP(statut='o', typ=fonction_sdaster),
            FK_0 = SIMP(statut='o', typ=fonction_sdaster),
            FK_1 = SIMP(statut='o', typ=fonction_sdaster),
            FK_2 = SIMP(statut='o', typ=fonction_sdaster),
            FK_3 = SIMP(statut='o', typ=fonction_sdaster),
            metaF1 = SIMP(statut='o', typ=fonction_sdaster),
            metaFDF_0 = SIMP(statut='o', typ=fonction_sdaster),
            metaFDF_1 = SIMP(statut='o', typ=fonction_sdaster),
            metaFDF_2 = SIMP(statut='o', typ=fonction_sdaster),
            metaFDF_3 = SIMP(statut='o', typ=fonction_sdaster),
        ),
    }
    return keywords
