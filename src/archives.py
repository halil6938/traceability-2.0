"""Archives mensuelles sur la cle USB.

Le 1er de chaque mois (a partir de 2 h), les tableaux du mois ecoule sont
enregistres en PDF, un dossier par element, un fichier par mois :

    traceability/temperatures/temperatures_2026-09.pdf
    traceability/receptions/receptions_2026-09.pdf
    traceability/nettoyage/nettoyage_2026-09.pdf

Si la cle est absente ou le Pi eteint le 1er, l'archive est faite des que
possible ensuite, et les mois manques sont rattrapes (12 au plus). La
premiere fois, tous les mois depuis la premiere donnee du Pi sont enregistres
(12 derniers au plus).
"""
from datetime import date

from . import database, pdf_export, usb_manager
from .journal import journal

MAX_RATTRAPAGE = 12

logger = journal(__name__, "sauvegarde.log")


def _precedent(annee, mois):
    return (annee - 1, 12) if mois == 1 else (annee, mois - 1)


def mois_a_archiver(aujourd_hui=None):
    """Mois termines pas encore archives, du plus ancien au plus recent."""
    aujourd_hui = aujourd_hui or date.today()
    dernier = _precedent(aujourd_hui.year, aujourd_hui.month)
    fait = database.get_meta("archive_mois", "") or ""
    try:
        a, m = (int(x) for x in fait.split("-"))
        deja = (a, m)
    except ValueError:
        # premiere fois : tout l'historique, depuis la premiere donnee du Pi
        premiere = database.premiere_donnee()
        deja = (_precedent(premiere.year, premiere.month) if premiere
                else _precedent(*dernier))
    mois = []
    courant = dernier
    while courant > deja and len(mois) < MAX_RATTRAPAGE:
        mois.append(courant)
        courant = _precedent(*courant)
    return list(reversed(mois))


def dossiers(base):
    """Un dossier par element sur la cle : {element: dossier}."""
    return {nom: base / nom for nom in ("temperatures", "receptions", "nettoyage")}


def archiver(annee, mois):
    """Ecrit les 3 tableaux du mois sur la cle. Retourne la liste des
    fichiers, ou None si aucune cle n'est branchee."""
    base = usb_manager.usb_base_dir()
    if base is None:
        return None
    d = dossiers(base)
    for dossier in d.values():
        dossier.mkdir(parents=True, exist_ok=True)
    fichiers = [
        pdf_export.export_month_pdf(annee, mois, dossier=d["temperatures"],
                                    avec_receptions=False),
        pdf_export.export_receptions_pdf(annee, mois, dossier=d["receptions"]),
        pdf_export.export_nettoyage_pdf(annee, mois, dossier=d["nettoyage"]),
    ]
    logger.info("archive mensuelle %d-%02d enregistree", annee, mois)
    return fichiers


def archiver_en_attente(aujourd_hui=None):
    """Archive les mois en attente. Retourne la liste des fichiers ecrits."""
    faits = []
    for annee, mois in mois_a_archiver(aujourd_hui):
        fichiers = archiver(annee, mois)
        if fichiers is None:
            break                          # cle retiree : on reessaiera
        database.set_meta("archive_mois", f"{annee}-{mois:02d}")
        faits += fichiers
    return faits
