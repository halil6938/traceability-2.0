"""Efface les donnees du client sur ce Pi (avant clonage de la carte SD).

Conserve les cles cloud Tuya (compte developpeur, communes a tous les clients)
et supprime tout le reste : appareils et seuils, releves, receptions,
fournisseurs, capteurs, MAC du pistolet, calibration camera, verrou distant,
photos en attente et logs.

    python3 tools/reset_client_data.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config, database  # noqa: E402

# Reglages communs a tous les clients, a conserver dans l'image modele
# (cles cloud Tuya et signe de vie Telegram : ils sont a vous, pas au client).
# heartbeat_version / heartbeat_date ne sont PAS conserves : chaque nouveau Pi
# doit annoncer son installation.
KEEP_META = ("tuya_access_id", "tuya_access_secret", "tuya_region",
             "telegram_token", "telegram_chat_id")


def main():
    keep = {}
    if config.DB_PATH.exists():
        for key in KEEP_META:
            value = database.get_meta(key, "")
            if value:
                keep[key] = value
        config.DB_PATH.unlink()
        print(f"Base effacee ({len(keep)} cle(s) Tuya conservee(s))")
    else:
        print("Aucune base a effacer")

    for folder in (config.PENDING_DIR, config.LOG_DIR):
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True, exist_ok=True)
    print("Photos en attente et logs effaces")

    database.init_db()
    for key, value in keep.items():
        database.set_meta(key, value)
    print("Base recreee vierge : l'assistant de premier lancement s'ouvrira.")


if __name__ == "__main__":
    main()
