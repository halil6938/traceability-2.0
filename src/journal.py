"""Journaux de l'appli : un fichier par module, de taille plafonnee.

Sans plafond, un journal ecrit toutes les 20 secondes grossit d'environ
130 Mo par an sur la carte SD. Ici chaque fichier est limite a TAILLE_MAX ;
au-dela, il est renomme en .1 (puis .2) et un nouveau fichier commence.
"""
import logging
from logging.handlers import RotatingFileHandler

from . import config

TAILLE_MAX = 512 * 1024   # octets par fichier
COPIES = 2                # anciennes versions gardees : fichier.log.1, .2


def journal(nom, fichier):
    """Logger ecrivant dans logs/<fichier>, avec rotation."""
    logger = logging.getLogger(nom)
    if not logger.handlers:
        h = RotatingFileHandler(config.LOG_DIR / fichier, maxBytes=TAILLE_MAX,
                                backupCount=COPIES, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
    return logger
