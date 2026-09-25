"""Verrou et configuration a distance via un fichier JSON sur GitHub.

Chaque Pi interroge periodiquement remote_control.json (que tu edites sur
GitHub). Ce fichier, indexe par machine (nom d'hote), porte pour chaque Pi :
  - locked / message : bloque l'appareil avec un message plein ecran
  - config           : surcharge de reglages autorises (couleurs, seuils...)

Le dernier etat recu est memorise en base : un blocage persiste hors ligne
et apres redemarrage ; une coupure reseau garde simplement le dernier etat
connu (jamais de blocage/deblocage accidentel sur simple perte de reseau).
"""
import json
import socket
import time
import urllib.error
import urllib.request

from . import config, database
from .journal import journal

logger = journal(__name__, "remote.log")


# --- Reglages surchargeables a distance : nom -> validation/conversion ---

def _color(v):
    v = str(v).strip()
    if v.startswith("#") and len(v) in (4, 7):
        int(v[1:], 16)  # leve ValueError si pas hexadecimal
        return v
    raise ValueError(f"couleur invalide : {v}")


def _style(v):
    v = str(v).strip().lower()
    if v not in ("classic", "rounded"):
        raise ValueError(f"style inconnu : {v}")
    return v


def _posint(v):
    n = int(v)
    if n < 0:
        raise ValueError("entier negatif")
    return n


def _texte(v):
    v = str(v).strip()
    if len(v) > 60:
        raise ValueError("texte trop long (60 caracteres max)")
    return v


CONFIG_WHITELIST = {
    "COLOR_BG": _color, "COLOR_FG": _color, "COLOR_PRIMARY": _color,
    "COLOR_SUCCESS": _color, "COLOR_DANGER": _color, "COLOR_WARNING": _color,
    "COLOR_CARD": _color, "COLOR_MUTED": _color,
    "SCAN_INACTIVITY_S": _posint, "RECT_STABLE_FRAMES": _posint,
    "HISTORY_INACTIVITY_S": _posint, "SETTINGS_INACTIVITY_S": _posint,
    "STYLE": _style,
    "SCREEN_OFF_S": _posint, "HEARTBEAT_HOUR": _posint,
    "PHOTO_RETENTION_DAYS": _posint, "FOCUS_DISTANCE_CM": _posint,
    "CAMERA_ROTATION": _posint,
    "NOM_MAGASIN": _texte, "NUIT_INACTIVITE_S": _posint,
}


def device_id():
    return (config.DEVICE_ID or socket.gethostname() or "inconnu").strip()


# Reglages surcharges a distance : leur valeur d'origine, pour la remettre si
# la ligne est retiree du fichier (sinon le reglage resterait en place
# jusqu'au prochain redemarrage).
_origines = {}
_dernier_cfg = None
_change = False


def apply_config(cfg):
    """Applique les reglages surcharges (liste blanche) au module config, et
    remet leur valeur d'origine a ceux qui ont ete retires. Un reglage inconnu
    ou invalide est ignore (jamais de plantage)."""
    global _dernier_cfg, _change
    if not isinstance(cfg, dict):
        cfg = {}
    signature = json.dumps(cfg, sort_keys=True, default=str)
    if signature == _dernier_cfg:
        return                          # rien de neuf : rien a faire, rien a ecrire
    _dernier_cfg = signature
    voulu = {}
    for key, raw in cfg.items():
        conv = CONFIG_WHITELIST.get(key)
        if conv is None:
            logger.warning("reglage non autorise ignore : %s", key)
            continue
        try:
            voulu[key] = conv(raw)
        except Exception as e:
            logger.warning("reglage %s invalide (%s) : %s", key, raw, e)
    for key in list(_origines):
        if key not in voulu:
            setattr(config, key, _origines.pop(key))
    for key, valeur in voulu.items():
        _origines.setdefault(key, getattr(config, key))
        setattr(config, key, valeur)
    _change = True


def config_changee():
    """Vrai (une seule fois) si des reglages ont change depuis le dernier
    appel : l'ecran principal se redessine alors pour les montrer."""
    global _change
    changee, _change = _change, False
    return changee


def cached_state():
    """Etat memorise localement (pour l'affichage immediat au demarrage,
    sans attendre le reseau)."""
    locked = database.get_meta("remote_locked", "0") == "1"
    message = database.get_meta("remote_lock_msg", "") or ""
    try:
        cfg = json.loads(database.get_meta("remote_config", "") or "{}")
    except Exception:
        cfg = {}
    return locked, message, cfg


_AUTHORIZED = {"locked": False, "message": "", "config": {}, "update": "auto"}


def _fetch():
    """Telecharge le fichier de CE Pi (<base>/<device_id>.json) et retourne
    son contenu normalise. Fichier absent (404) = appareil autorise. None en
    cas d'echec reseau ou JSON invalide (l'appelant garde le dernier etat)."""
    base = config.REMOTE_CONTROL_BASE
    if not base:
        return None
    url = f"{base.rstrip('/')}/{device_id()}.json"
    sep = "&" if "?" in url else "?"          # anti-cache CDN GitHub
    full = f"{url}{sep}t={int(time.time())}"
    try:
        req = urllib.request.Request(full, headers={"User-Agent": "traceability"})
        with urllib.request.urlopen(req, timeout=10) as r:
            entry = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return dict(_AUTHORIZED)  # pas de fichier pour ce Pi = autorise
        _signaler_echec(f"HTTP {e.code}")
        return None
    except Exception as e:
        _signaler_echec(str(e))
        return None
    _signaler_echec(None)
    if not isinstance(entry, dict):
        return dict(_AUTHORIZED)
    return {
        "locked": bool(entry.get("locked", False)),
        "message": str(entry.get("message", "")),
        "config": entry.get("config") or {},
        "update": str(entry.get("update", "auto")),
    }


_dernier_echec = None


def _signaler_echec(message):
    """Journalise une coupure une seule fois (et le retour), pas toutes les
    20 secondes pendant toute la duree de la coupure."""
    global _dernier_echec
    if message != _dernier_echec:
        if message:
            logger.info("verification a distance impossible : %s", message)
        elif _dernier_echec:
            logger.info("verification a distance retablie")
        _dernier_echec = message


def refresh():
    """Verifie l'etat a distance, met a jour le cache local + applique la
    config. Retourne (locked, message). En cas d'echec reseau, conserve et
    renvoie le dernier etat connu."""
    entry = _fetch()
    if entry is None:
        locked, message, cfg = cached_state()
        apply_config(cfg)
        return locked, message
    avant = (database.get_meta("remote_locked", "0"),
             database.get_meta("remote_lock_msg", "") or "",
             database.get_meta("remote_config", "") or "{}",
             database.get_meta("remote_update", "") or "")
    apres = ("1" if entry["locked"] else "0", entry["message"],
             json.dumps(entry["config"]), entry["update"])
    if apres != avant:
        # ecriture (carte SD) et journal uniquement quand quelque chose change
        for cle, valeur in zip(("remote_locked", "remote_lock_msg",
                                "remote_config", "remote_update"), apres):
            database.set_meta(cle, valeur)
        logger.info("etat distant : locked=%s update=%s config=%s",
                    entry["locked"], entry["update"], entry["config"])
    apply_config(entry["config"])
    return entry["locked"], entry["message"]
