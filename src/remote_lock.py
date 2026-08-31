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
import logging
import socket
import time
import urllib.error
import urllib.request

from . import config, database

logger = logging.getLogger(__name__)
if not logger.handlers:
    _h = logging.FileHandler(config.LOG_DIR / "remote.log")
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)


# --- Reglages surchargeables a distance : nom -> validation/conversion ---

def _color(v):
    v = str(v).strip()
    if v.startswith("#") and len(v) in (4, 7):
        int(v[1:], 16)  # leve ValueError si pas hexadecimal
        return v
    raise ValueError(f"couleur invalide : {v}")


def _posint(v):
    n = int(v)
    if n < 0:
        raise ValueError("entier negatif")
    return n


CONFIG_WHITELIST = {
    "COLOR_BG": _color, "COLOR_FG": _color, "COLOR_PRIMARY": _color,
    "COLOR_SUCCESS": _color, "COLOR_DANGER": _color, "COLOR_WARNING": _color,
    "COLOR_CARD": _color, "COLOR_MUTED": _color,
    "SCAN_INACTIVITY_S": _posint, "RECT_STABLE_FRAMES": _posint,
    "SCREEN_OFF_S": _posint,
    "PHOTO_RETENTION_DAYS": _posint, "FOCUS_DISTANCE_CM": _posint,
    "CAMERA_ROTATION": _posint,
}


def device_id():
    return (config.DEVICE_ID or socket.gethostname() or "inconnu").strip()


def apply_config(cfg):
    """Applique les reglages surcharges (liste blanche) au module config.
    Un reglage inconnu ou invalide est ignore (jamais de plantage)."""
    if not isinstance(cfg, dict):
        return
    for key, raw in cfg.items():
        conv = CONFIG_WHITELIST.get(key)
        if conv is None:
            logger.warning("reglage non autorise ignore : %s", key)
            continue
        try:
            setattr(config, key, conv(raw))
        except Exception as e:
            logger.warning("reglage %s invalide (%s) : %s", key, raw, e)


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
        logger.info("verification a distance (HTTP %s)", e.code)
        return None
    except Exception as e:
        logger.info("verification a distance impossible : %s", e)
        return None
    if not isinstance(entry, dict):
        return dict(_AUTHORIZED)
    return {
        "locked": bool(entry.get("locked", False)),
        "message": str(entry.get("message", "")),
        "config": entry.get("config") or {},
        "update": str(entry.get("update", "auto")),
    }


def refresh():
    """Verifie l'etat a distance, met a jour le cache local + applique la
    config. Retourne (locked, message). En cas d'echec reseau, conserve et
    renvoie le dernier etat connu."""
    entry = _fetch()
    if entry is None:
        locked, message, cfg = cached_state()
        apply_config(cfg)
        return locked, message
    database.set_meta("remote_locked", "1" if entry["locked"] else "0")
    database.set_meta("remote_lock_msg", entry["message"])
    database.set_meta("remote_config", json.dumps(entry["config"]))
    database.set_meta("remote_update", entry["update"])
    apply_config(entry["config"])
    logger.info("etat distant : locked=%s update=%s config=%s",
                entry["locked"], entry["update"], entry["config"])
    return entry["locked"], entry["message"]
