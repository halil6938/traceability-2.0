"""Lecture BLE des capteurs Brifit WS07 (ThermoBeacon).

Protocole decode : manufacturer_data[0x0010], bytes[10:12] little-endian
int16 SIGNE / 16.0 = degres C (le signe est necessaire pour les congelateurs ;
identique a un decodage non signe pour les temperatures positives).
"""
import asyncio
import struct
import logging

logger = logging.getLogger(__name__)

MANUFACTURER_ID = 16   # 0x0010
SCAN_TIMEOUT = 25.0    # secondes max d'ecoute

# Plage de mesure du capteur : hors de la, la trame est aberrante et ignoree.
# Large a dessein — les seuils par appareil (frigo, congelateur) sont geres
# ailleurs ; restreindre ici ferait disparaitre les releves de congelateur.
TEMP_MIN = -40.0
TEMP_MAX = 80.0

try:
    from bleak import BleakScanner
    HAS_BLEAK = True
except ImportError:
    HAS_BLEAK = False


async def _scan_async(targets: set, temp_min: float = TEMP_MIN,
                      temp_max: float = TEMP_MAX, cancel=None) -> dict:
    results = {}

    def callback(device, adv):
        if device.address.lower() not in targets:
            return
        data = adv.manufacturer_data.get(MANUFACTURER_ID)
        if not data or len(data) < 12:
            return
        temp = struct.unpack_from('<h', data, 10)[0] / 16.0
        if not (temp_min <= temp <= temp_max):
            logger.warning("BLE trame aberrante ignoree : %s -> %.2f C", device.address, temp)
            return
        results[device.address.lower()] = round(temp, 2)
        logger.info("BLE capte : %s -> %.2f C", device.address, temp)

    scanner = BleakScanner(detection_callback=callback)
    await scanner.start()
    elapsed = 0.0
    while elapsed < SCAN_TIMEOUT:
        if cancel is not None and cancel.is_set():
            break
        await asyncio.sleep(0.3)
        elapsed += 0.3
        if targets <= results.keys():   # tous les capteurs trouves -> arret anticipe
            break
    await scanner.stop()
    return results


def read_temperatures(macs: list, temp_min: float = TEMP_MIN,
                      temp_max: float = TEMP_MAX, cancel=None) -> dict:
    """Scan BLE synchrone. Retourne {mac_lower: temp_celsius}.
    cancel : threading.Event optionnel — stoppe le scan en moins de 0.5 s
    en renvoyant ce qui a deja ete capte.
    Leve RuntimeError si bleak est absent."""
    if not HAS_BLEAK:
        raise RuntimeError("bleak non installe (pip install bleak)")
    targets = {m.lower() for m in macs}
    return asyncio.run(_scan_async(targets, temp_min, temp_max, cancel))


async def _discover_async(timeout: float, cancel=None) -> list:
    found = {}

    def callback(device, adv):
        data = adv.manufacturer_data.get(MANUFACTURER_ID)
        if not data or len(data) < 12:
            return
        temp = struct.unpack_from('<h', data, 10)[0] / 16.0
        if not (TEMP_MIN <= temp <= TEMP_MAX):
            return
        mac = device.address.lower()
        seen = found.get(mac)
        if seen is None or adv.rssi > seen["rssi"]:
            found[mac] = {"mac": mac, "name": device.name or "",
                          "temp": round(temp, 1), "rssi": adv.rssi}

    scanner = BleakScanner(detection_callback=callback)
    await scanner.start()
    elapsed = 0.0
    while elapsed < timeout:
        if cancel is not None and cancel.is_set():
            break
        await asyncio.sleep(0.3)
        elapsed += 0.3
    await scanner.stop()
    return sorted(found.values(), key=lambda d: -d["rssi"])


def discover(timeout: float = 12.0, cancel=None) -> list:
    """Cherche les capteurs de temperature BLE a proximite (ThermoBeacon /
    Brifit WS07). Retourne [{mac, name, temp, rssi}], le plus proche d'abord.
    Leve RuntimeError si bleak est absent."""
    if not HAS_BLEAK:
        raise RuntimeError("bleak non installe (pip install bleak)")
    return asyncio.run(_discover_async(timeout, cancel))
