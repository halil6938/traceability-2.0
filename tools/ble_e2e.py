"""Diagnostic verbeux bout-en-bout : detection -> connexion -> unlock -> mesures.
Affiche chaque etape avec horodatage pour localiser une eventuelle panne."""
import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.ble_thermo import (parse_frame, CMD_UNLOCK, CMD_START, CMD_STOP,
                            CHAR_CMD, CHAR_MEAS)  # noqa: E402
from bleak import BleakClient, BleakScanner  # noqa: E402

MAC = "07:b4:ec:14:67:5a"


def ts():
    return datetime.now().strftime("%H:%M:%S")


async def main():
    print(f"{ts()} Scan continu — APPUYEZ SUR LA GACHETTE (90 s)...")
    found = asyncio.Event()
    box = {}

    def cb(d, adv):
        if d.address.lower() == MAC:
            if not found.is_set():
                print(f"{ts()} >>> PISTOLET DETECTE (rssi={adv.rssi})")
                box["d"] = d
                found.set()

    scanner = BleakScanner(detection_callback=cb)
    await scanner.start()
    try:
        await asyncio.wait_for(found.wait(), 90)
    except asyncio.TimeoutError:
        print(f"{ts()} ECHEC : jamais detecte en 90 s")
        await scanner.stop()
        return
    await scanner.stop()

    print(f"{ts()} Connexion...")
    try:
        async with BleakClient(box["d"], timeout=20.0) as client:
            print(f"{ts()} CONNECTE")
            got = asyncio.Event()

            def handler(char, data):
                p = parse_frame(bytes(data))
                if p:
                    print(f"{ts()} *** MESURE {p[0]} C ***")
                    got.set()

            await client.start_notify(CHAR_MEAS, handler)
            print(f"{ts()} abonne FFB2")
            await client.write_gatt_char(CHAR_CMD, CMD_UNLOCK, response=False)
            print(f"{ts()} CMD_UNLOCK envoye")
            for i in range(40):
                await client.write_gatt_char(CHAR_CMD, CMD_START, response=False)
                await asyncio.sleep(0.8)
                if got.is_set():
                    break
            try:
                await client.write_gatt_char(CHAR_CMD, CMD_STOP, response=False)
            except Exception:
                pass
            print(f"{ts()} Fin ({'mesure recue' if got.is_set() else 'aucune mesure'})")
    except Exception as e:
        print(f"{ts()} ERREUR connexion : {e!r}")

asyncio.run(main())
