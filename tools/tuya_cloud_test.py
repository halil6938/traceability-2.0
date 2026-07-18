"""Test de lecture d'un capteur Tuya WiFi via le cloud (tinytuya).

Liste les appareils lies au projet Tuya IoT, puis affiche l'etat (DPS)
de chacun — permet d'identifier le Device ID et le code de la temperature.

Usage :
    python tools/tuya_cloud_test.py <ACCESS_ID> <ACCESS_SECRET> [region]

region : eu (defaut), us, cn, in
Les cles ne sont jamais stockees : uniquement passees en argument.
"""
import json
import sys

import tinytuya


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    access_id, secret = sys.argv[1], sys.argv[2]
    region = sys.argv[3] if len(sys.argv) > 3 else "eu"

    cloud = tinytuya.Cloud(apiRegion=region, apiKey=access_id, apiSecret=secret)
    devices = cloud.getdevices()
    if not isinstance(devices, list):
        print("ERREUR getdevices() :")
        print(json.dumps(devices, indent=2, ensure_ascii=False))
        sys.exit(2)

    print(f"{len(devices)} appareil(s) lie(s) au projet :\n")
    for d in devices:
        print(f"- Nom        : {d.get('name')}")
        print(f"  Device ID  : {d.get('id')}")
        print(f"  Produit    : {d.get('product_name')}  (category={d.get('category')})")
        print(f"  En ligne   : {d.get('online')}")
        status = cloud.getstatus(d.get("id"))
        print("  Etat (DPS) :")
        print("    " + json.dumps(status, indent=4, ensure_ascii=False).replace("\n", "\n    "))
        print()


if __name__ == "__main__":
    main()
