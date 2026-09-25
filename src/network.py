"""Etat de la connexion internet et de l'horloge (en-tete du menu principal).

Les tests tournent en tache de fond, au plus une fois par minute : l'ecran lit
le dernier resultat connu sans jamais attendre le reseau.
"""
import os
import socket
import subprocess
import threading
import time

# GitHub d'abord : c'est lui que l'appli interroge pour les mises a jour et le
# controle a distance. Repli sur une adresse IP pour distinguer « pas
# d'internet » de « GitHub injoignable ». Simple ouverture de connexion : rien
# n'est envoye.
_CIBLES = (("raw.githubusercontent.com", 443), ("1.1.1.1", 53))
INTERVALLE_S = 60

_etat = {"en_ligne": None, "heure_ok": None, "quand": 0.0, "en_cours": False}


def is_online(timeout=2.0):
    if os.environ.get("TRACEABILITY_TEST"):
        return True                     # les tests n'ouvrent aucune connexion
    for hote, port in _CIBLES:
        try:
            with socket.create_connection((hote, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def heure_synchronisee():
    """True si l'horloge a ete mise a l'heure par internet, False sinon, None
    si on ne peut pas le savoir (PC de test). Le Pi 3 n'a pas d'horloge
    interne : demarre sans internet, il peut etre a la mauvaise heure, et les
    releves, receptions et photos seraient alors mal dates."""
    if os.environ.get("TRACEABILITY_TEST"):
        return True
    try:
        r = subprocess.run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    valeur = r.stdout.strip().lower()
    return True if valeur == "yes" else False if valeur == "no" else None


def _tester():
    try:
        _etat["en_ligne"] = is_online()
        _etat["heure_ok"] = heure_synchronisee()
    finally:
        _etat["quand"] = time.time()
        _etat["en_cours"] = False


def actualiser_si_besoin():
    """Relance les tests en tache de fond si le dernier date d'une minute ou
    plus. Un seul test a la fois : en cas de coupure, un test peut durer
    plusieurs secondes, ils ne doivent pas s'empiler."""
    if _etat["en_cours"] or time.time() - _etat["quand"] < INTERVALLE_S:
        return
    _etat["en_cours"] = True
    threading.Thread(target=_tester, daemon=True).start()


def etat():
    """(en_ligne, heure_ok) : derniers resultats connus, None = pas encore su."""
    return _etat["en_ligne"], _etat["heure_ok"]
