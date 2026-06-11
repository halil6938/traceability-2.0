"""Scan BLE de diagnostic : liste tout ce qui est visible pendant 12 s."""
import asyncio
from bleak import BleakScanner


async def main():
    print("Scan BLE 12 s... allumez le pistolet en mode Bluetooth.")
    devices = await BleakScanner.discover(timeout=12.0, return_adv=True)
    if not devices:
        print("Aucun peripherique BLE vu.")
        return
    for addr, (dev, adv) in sorted(devices.items()):
        print(f"{addr}  rssi={adv.rssi:4}  name={dev.name!r}  "
              f"mfr_data={ {k: v.hex() for k, v in adv.manufacturer_data.items()} }  "
              f"services={list(adv.service_uuids)}")

asyncio.run(main())
