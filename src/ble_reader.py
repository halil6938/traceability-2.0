"""Lecture BLE des capteurs Brifit WS07 (ThermoBeacon).

Protocole decode : manufacturer_data[0x0010], bytes[10:12] little-endian uint16 / 16.0 = degres C
"""
import asyncio
import struct
import logging

logger = logging.getLogger(__name__)

MANUFACTURER_ID = 16   # 0x0010
SCAN_TIMEOUT = 25.0    # secondes max d'ecoute

TEMP_MIN = 0.0    # valeurs hors plage = trame aberrante ignoree
TEMP_MAX = 25.0

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
        temp = struct.unpack_from('<H', data, 10)[0] / 16.0
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
