"""Signe de vie Telegram : chaque Pi annonce qu'il est en ligne et sa version.

Trois messages :
  - immediat quand la version change (installation, mise a jour) ;
  - immediat quand le verrou change : c'est la confirmation que l'ordre de
    verrouillage donne sur GitHub a bien ete recu par l'appareil ;
  - quotidien a partir de HEARTBEAT_HOUR (« en ligne » ou « VERROUILLE »).

L'absence du message quotidien signale un Pi hors ligne : c'est a l'exploitant
de le remarquer, rien ne surveille a sa place.

Jeton du bot et identifiant de conversation : stockes en base locale (donc
presents dans l'image SD, communs a tous les Pi). A configurer une fois avec
    python3 tools/set_telegram.py <jeton> <chat_id>
Seuls le nom du magasin et la version sont transmis — aucune donnee client.
"""
import json
import logging
import urllib.parse
import urllib.request
from datetime import date, datetime

from . import config, database

API = "https://api.telegram.org/bot{token}/sendMessage"

logger = logging.getLogger(__name__)
if not logger.handlers:
    _h = logging.FileHandler(config.LOG_DIR / "heartbeat.log")
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)


def get_creds():
    """(jeton, chat_id) ou None si le signe de vie n'est pas configure."""
    token = database.get_meta("telegram_token", "") or ""
    chat = database.get_meta("telegram_chat_id", "") or ""
    return (token, chat) if token and chat else None


def set_creds(token, chat_id):
    database.set_meta("telegram_token", str(token).strip())
    database.set_meta("telegram_chat_id", str(chat_id).strip())


def send(text):
    """Envoie un message. Retourne True si Telegram l'a accepte.
    Le jeton n'est jamais journalise."""
    creds = get_creds()
    if creds is None:
        return False
    token, chat = creds
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    try:
        req = urllib.request.Request(API.format(token=token), data=data)
        with urllib.request.urlopen(req, timeout=15) as r:
            ok = bool(json.loads(r.read().decode("utf-8")).get("ok"))
    except Exception as e:
        logger.info("envoi impossible : %s", e)
        return False
    logger.info("message envoye : %s" if ok else "message refuse : %s", text)
    return ok


def _label():
    """Nom du magasin, version deployee et etat du verrou."""
    from . import remote_lock, updater
    version = (updater.current_version() or "")[:7] or "inconnue"
    locked = database.get_meta("remote_locked", "0") == "1"
    return remote_lock.device_id(), version, locked


def tick():
    """A appeler regulierement : envoie ce qui doit l'etre, ou rien."""
    if get_creds() is None:
        return
    device, version, locked = _label()
    etat = "VERROUILLE" if locked else "en ligne"

    # 1) La version a change (installation ou mise a jour) : message immediat.
    known = database.get_meta("heartbeat_version", "") or ""
    if known != version:
        quoi = "mis a jour" if known else "installe"
        if send(f"{device} — {quoi}, version {version}"):
            database.set_meta("heartbeat_version", version)
            database.set_meta("heartbeat_locked", "1" if locked else "0")
            database.set_meta("heartbeat_date", date.today().isoformat())
        return

    # 2) Le verrou a change : confirmation immediate que l'appareil a bien
    #    recu l'ordre donne sur GitHub (sinon rien ne le confirmerait).
    known_lock = database.get_meta("heartbeat_locked", "")
    if known_lock != ("1" if locked else "0"):
        quoi = "VERROUILLE" if locked else "deverrouille"
        if send(f"{device} — {quoi}, version {version}"):
            database.set_meta("heartbeat_locked", "1" if locked else "0")
            database.set_meta("heartbeat_date", date.today().isoformat())
        return

    # 3) Message quotidien, a partir de l'heure convenue.
    today = date.today().isoformat()
    heure = max(0, min(23, config.HEARTBEAT_HOUR))
    if (database.get_meta("heartbeat_date", "") != today
            and datetime.now().hour >= heure):
        if send(f"{device} — {etat}, version {version}"):
            database.set_meta("heartbeat_date", today)
