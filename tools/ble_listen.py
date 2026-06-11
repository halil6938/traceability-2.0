"""Diagnostic : affiche TOUTES les trames brutes du pistolet (2 min d'ecoute).
Appuyez sur la gachette plusieurs fois pendant l'ecoute !"""
import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.ble_thermo import parse_frame  # noqa: E402
from bleak import BleakClient, BleakScanner  # noqa: E402

MAC = "07:b4:ec:14:67:5a"


def safe_ascii(raw: bytes) -> str:
    return "".join(chr(b) if 32 <= b < 127 else "." for b in raw)


async def wait_for_gun(deadline: float = 60.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < deadline:
        dev = await BleakScanner.find_device_by_address(MAC, timeout=5.0)
        if dev:
            return dev
        print("  pistolet pas encore visible...")
    return None


async def main():
    print(f"Recherche du pistolet {MAC}...")
    dev = await wait_for_gun()
    if dev is None:
        print("ECHEC : pistolet introuvable.")
        return
    print("Trouve ! Connexion...")
    async with BleakClient(dev, timeout=15.0) as client:
        def handler(char, data):
            raw = bytes(data)
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"{ts}  {char.uuid[4:8]}  {raw.hex(' ')}  |{safe_ascii(raw)}|"
                  f"  parse={parse_frame(raw)}")

        n = 0
        for service in client.services:
            for char in service.characteristics:
                if "notify" in char.properties or "indicate" in char.properties:
                    try:
                        await client.start_notify(char, handler)
                        n += 1
                        print(f"abonne a {char.uuid}")
                    except Exception as e:
                        print(f"echec abonnement {char.uuid}: {e}")
        print(f"{n} characteristics ecoutees. GACHETTE ! (120 s)")
        await asyncio.sleep(120)
        print("Fin d'ecoute.")

asyncio.run(main())
