"""Sauvegarde quotidienne de la base sur la cle USB.

Tout l'historique sanitaire (releves, receptions, appareils, fournisseurs) tient
dans un seul fichier sur la carte SD : si la carte meurt, il serait perdu. Une
copie est donc faite chaque nuit sur la cle, dans traceability/sauvegardes/.

  - copie COHERENTE meme si l'appli ecrit au meme moment (API de sauvegarde
    de SQLite, et non simple copie du fichier) ;
  - ecrite sous un nom provisoire puis renommee : une coupure de courant ou une
    cle retiree pendant la copie ne laisse jamais une sauvegarde abimee ;
  - SANS les identifiants (jeton Telegram, cles Tuya) : la cle reste chez le
    client, ils ne doivent pas s'y trouver ;
  - les JOURS_GARDES dernieres copies sont conservees.

Restauration : copier la sauvegarde voulue a la place de
~/traceability/config.db (appli arretee), puis redemarrer. Les identifiants
se remettent ensuite avec tools/finaliser.py.
"""
import os
import sqlite3
from datetime import date

from . import config, usb_manager
from .journal import journal

JOURS_GARDES = 14
# Jamais sur la cle USB, qui reste chez le client
CLES_SECRETES = ("telegram_token", "telegram_chat_id",
                 "tuya_access_id", "tuya_access_secret")

logger = journal(__name__, "sauvegarde.log")


def sauvegarder(jour=None):
    """Copie la base sur la cle. Retourne le chemin de la sauvegarde, ou None
    si aucune cle n'est branchee."""
    base = usb_manager.usb_base_dir()
    if base is None:
        return None
    jour = jour or date.today()
    dossier = base / "sauvegardes"
    dossier.mkdir(parents=True, exist_ok=True)
    dest = dossier / f"config_{jour.isoformat()}.db"
    provisoire = dossier / "en_cours.tmp"

    source = sqlite3.connect(config.DB_PATH)
    copie = sqlite3.connect(provisoire)
    try:
        source.backup(copie)
        # secure_delete : les identifiants sont reellement effaces du fichier,
        # pas seulement marques comme supprimes
        copie.execute("PRAGMA secure_delete = ON")
        copie.execute("DELETE FROM meta WHERE key IN (%s)"
                      % ",".join("?" * len(CLES_SECRETES)), CLES_SECRETES)
        copie.commit()
    finally:
        copie.close()
        source.close()
    os.replace(provisoire, dest)

    anciennes = sorted(dossier.glob("config_*.db"))
    for vieille in anciennes[:-JOURS_GARDES]:
        try:
            vieille.unlink()
        except OSError:
            pass
    logger.info("sauvegarde ecrite : %s", dest.name)
    return dest
