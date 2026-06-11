"""Lecture du pistolet infrarouge Bluetooth HoldPeak HP-985C-APP.

Protocole retro-ingenierie sur le materiel reel (module BLE nomme 'SWAN') :
le pistolet notifie sur la characteristic 0xFFB2 des trames de 8 octets :

    bc 05 00 5f TL TH SS CK
      - bc 05 00 5f : en-tete fixe
      - TL TH       : temperature x10, int16 little-endian
      - SS          : statut (octet variable, non utilise)
      - CK          : checksum = (0x64 + TL + TH + SS) & 0xFF

Plusieurs trames peuvent arriver concatenees dans une seule notification.
Chaque trame brute est loggee dans logs/ble_thermo.log.
"""
import asyncio
import logging
import re
import struct

from . import config

# Plage de mesure du HP-985C : -50 a +800 C
TEMP_MIN = -50.0
TEMP_MAX = 800.0

CONNECT_TIMEOUT = 20.0
FRAME_HEADER = b"\xbc\x05\x00\x5f"
FRAME_LEN = 8
CHECKSUM_BASE = 0x64

# Characteristics : mesures notifiees sur FFB2, commandes ecrites sur FFB1
CHAR_MEAS = "0000ffb2-0000-1000-8000-00805f9b34fb"
CHAR_CMD = "0000ffb1-0000-1000-8000-00805f9b34fb"
# Commandes retro-ingenierees depuis l'appli officielle (sur FFB1, sans reponse).
# Sequence observee : CMD_UNLOCK une fois, puis CMD_START en boucle -> le flux
# de mesures (FFB2) ne demarre QU'APRES CMD_UNLOCK.
CMD_UNLOCK = bytes.fromhex("acfffe150100cce0")  # deverrouille le flux
CMD_START = bytes.fromhex("bc20000222")         # demande/relance les mesures
CMD_STOP = bytes.fromhex("bc21000021")          # arrete le flux

# Detection : nom GATT/advertising, ou service vendeur annonce
NAME_HINTS = ("985", "holdpeak", "hp-9", "swan")
SERVICE_HINTS = ("0000ffb0", "0000d618")

try:
    from bleak import BleakClient, BleakScanner
    HAS_BLEAK = True
except ImportError:
    HAS_BLEAK = False

logger = logging.getLogger(__name__)
if not logger.handlers:
    _h = logging.FileHandler(config.LOG_DIR / "ble_thermo.log")
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)


def _plausible(v: float) -> bool:
    return TEMP_MIN <= v <= TEMP_MAX


def parse_frame(data: bytes):
    """Extrait une temperature d'une notification.
    Retourne (valeur, methode) ou None si aucune trame valide."""
    if not data:
        return None

    # 1) Trame HP-985C : en-tete + checksum verifie
    idx = data.find(FRAME_HEADER)
    while idx != -1:
        frame = data[idx:idx + FRAME_LEN]
        if len(frame) == FRAME_LEN:
            expected = (CHECKSUM_BASE + frame[4] + frame[5] + frame[6]) & 0xFF
            if frame[7] == expected:
                v = struct.unpack_from("<h", frame, 4)[0] / 10.0
                if _plausible(v):
                    return round(v, 1), f"hp985c@{idx}"
                logger.warning("trame HP-985C hors plage : %.1f", v)
        idx = data.find(FRAME_HEADER, idx + 1)

    # 2) Secours : trame ASCII (autre modele de thermometre)
    text = data.decode("ascii", errors="ignore")
    m = re.search(r"-?\d{1,4}(?:\.\d+)?", text)
    if m:
        try:
            v = float(m.group())
        except ValueError:
            return None
        if _plausible(v):
            return round(v, 1), f"ascii:{text.strip()!r}"

    return None


async def _resolve_device(mac: str, deadline: float):
    """Attend que le pistolet apparaisse et retourne DES LA PREMIERE detection
    (le pistolet ne reste joignable qu'un court instant apres la gachette, il
    faut donc se connecter au plus vite). Retourne un BLEDevice, ou None."""
    target = mac.lower()
    found = asyncio.Event()
    box = {}

    def cb(device, adv):
        if device.address.lower() == target and not found.is_set():
            box["dev"] = device
            found.set()

    scanner = BleakScanner(detection_callback=cb)
    await scanner.start()
    try:
        await asyncio.wait_for(found.wait(), deadline)
    except asyncio.TimeoutError:
        return None
    finally:
        await scanner.stop()
    return box.get("dev")


async def _read_async(mac: str, timeout: float):
    got = asyncio.Event()
    result = {}

    def handler(char, data):
        raw = bytes(data)
        parsed = parse_frame(raw)
        logger.info("notify %s : %s -> %s", char.uuid, raw.hex(" "), parsed)
        if parsed is not None and not got.is_set():
            result["temp"] = parsed[0]
            got.set()

    # Phase 1 : attendre que l'operateur reveille le pistolet (gachette)
    target = await _resolve_device(mac, deadline=timeout)
    if target is None:
        logger.info("pistolet introuvable apres %.0fs de scan", timeout)
        return None
    async with BleakClient(target, timeout=CONNECT_TIMEOUT) as client:
        # S'abonner aux mesures (FFB2) ; fallback : toutes les notify connues
        subscribed = []
        meas_char = client.services.get_characteristic(CHAR_MEAS)
        targets = [meas_char] if meas_char else [
            ch for s in client.services for ch in s.characteristics
            if "notify" in ch.properties or "indicate" in ch.properties
        ]
        for char in targets:
            try:
                await client.start_notify(char, handler)
                subscribed.append(char)
            except Exception as e:
                logger.warning("start_notify %s : %s", char.uuid, e)
        if not subscribed:
            raise RuntimeError("Aucune characteristic notify sur ce peripherique")

        # Demarrer le flux : l'appli officielle deverrouille avec CMD_UNLOCK
        # puis relance CMD_START en boucle. Sans CMD_UNLOCK, le pistolet reste
        # muet. On reproduit cette sequence tant qu'aucune mesure n'arrive.
        async def pump_start():
            try:
                await client.write_gatt_char(CHAR_CMD, CMD_UNLOCK, response=False)
            except Exception as e:
                logger.warning("ecriture CMD_UNLOCK : %s", e)
                return
            while not got.is_set():
                try:
                    await client.write_gatt_char(CHAR_CMD, CMD_START, response=False)
                except Exception as e:
                    logger.warning("ecriture CMD_START : %s", e)
                    return
                await asyncio.sleep(0.8)

        logger.info("connecte a %s, %d notify, envoi CMD_UNLOCK + CMD_START",
                    mac, len(subscribed))
        pumper = asyncio.create_task(pump_start())
        try:
            await asyncio.wait_for(got.wait(), timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            pumper.cancel()
            try:
                await client.write_gatt_char(CHAR_CMD, CMD_STOP, response=False)
            except Exception:
                pass
            for char in subscribed:
                try:
                    await client.stop_notify(char)
                except Exception:
                    pass
    return result.get("temp")


def read_temperature(mac: str, timeout: float = 30.0):
    """Connexion GATT au pistolet et attente d'une mesure (gachette).
    Retourne la temperature en C, ou None si rien recu avant timeout.
    Leve RuntimeError si bleak absent, BleakError si connexion impossible."""
    if not HAS_BLEAK:
        raise RuntimeError("bleak non installe (pip install bleak)")
    return asyncio.run(_read_async(mac, timeout))


async def _find_async(timeout: float):
    found = await BleakScanner.discover(timeout=timeout, return_adv=True)
    best = None  # (rssi, mac, label)
    for mac, (dev, adv) in found.items():
        name = (dev.name or "").lower()
        if name and any(h in name for h in NAME_HINTS):
            logger.info("pistolet detecte par nom : %s (%s)", dev.name, mac)
            return mac, dev.name
        # Le HP-985C n'annonce pas de nom mais annonce ses services vendeur :
        # on garde le candidat au signal le plus fort (= le plus proche)
        if any(u.lower().startswith(p) for u in adv.service_uuids
               for p in SERVICE_HINTS):
            if best is None or adv.rssi > best[0]:
                best = (adv.rssi, mac, dev.name or "Pistolet IR (SWAN)")
    if best:
        logger.info("pistolet detecte par service : %s rssi=%d", best[1], best[0])
        return best[1], best[2]
    logger.info("scan termine, pistolet non trouve (%d peripheriques vus)",
                len(found))
    return None


def find_thermometer(timeout: float = 15.0):
    """Scan BLE par nom. Retourne (mac, nom) ou None si non trouve."""
    if not HAS_BLEAK:
        raise RuntimeError("bleak non installe (pip install bleak)")
    return asyncio.run(_find_async(timeout))
