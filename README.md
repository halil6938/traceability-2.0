# Traceability 2.0

Application de traçabilité pour Raspberry Pi 3 (écran tactile 5" 800×480, **paysage**) :

- 📷 **Scan ticket** : détection auto d'étiquettes blanches sur fond contrasté, capture automatique.
- 🌡 **Relevés de température** : saisie tactile quotidienne par appareil (frigo/congélateur) avec alerte hors seuils.
- 📦 **Réception** : relevé de température des produits livrés par fournisseur, via thermomètre Bluetooth (pistolet IR HoldPeak HP-985C-APP) ou saisie manuelle.
- 📊 **Historique** mensuel consultable et modifiable (tickets, températures, réceptions).
- 📄 **Export PDF** par mois sur clé USB (températures + réceptions).
- 🗑 **Purge auto** des photos > 6 mois.

## Architecture

```
traceability/
├── main.py                   # point d'entrée
├── src/
│   ├── config.py             # chemins, couleurs, polices
│   ├── database.py           # SQLite : appareils, relevés, pending
│   ├── usb_manager.py        # détection USB + sync
│   ├── purge.py              # suppression > 6 mois
│   ├── pdf_export.py         # export mensuel PDF
│   ├── camera_scan.py        # preview + détection rectangle + capture
│   ├── ui_common.py          # widgets + clavier tactile
│   ├── ui_setup.py           # wizard premier lancement
│   ├── ble_thermo.py         # pistolet IR HoldPeak HP-985C-APP (BLE)
│   ├── ui_main.py            # menu principal + routeur
│   ├── ui_temperature.py     # saisie du jour
│   ├── ui_reception.py       # réception fournisseurs + lecture pistolet
│   ├── ui_history.py         # tableau mensuel + export
│   └── ui_settings.py        # gestion appareils
├── tools/                    # outils de diagnostic BLE (ble_e2e.py, ...)
├── requirements.txt
├── install.sh
└── traceability.service
```

## Installation sur le Raspberry Pi

1. Copier le dossier `traceability/` sur le Pi (clé USB, SCP, git clone...).
2. `cd traceability && bash install.sh`
3. Redémarrer : l'appli se lance automatiquement.

## Stockage

- **Carte SD** (`~/traceability/`) : base SQLite (config + relevés), photos en attente si USB absente, logs.
- **Clé USB** (`/media/pi/<VOLUME>/traceability/`) : photos (`photos/YYYY-MM/…jpg`), exports PDF (`exports/`).

Si l'USB est absente au moment d'une photo, elle est stockée localement puis synchronisée automatiquement dès la reconnexion.

## Premier lancement

Un assistant demande d'ajouter au moins un appareil (nom, seuil min/max). Modifiable ensuite dans Paramètres.

## Sortir du plein écran / quitter

- `Échap` : basculer plein écran (pour debug).
- Quitter l'appli : bouton dans Paramètres.

## Raccourcis utiles

```bash
sudo systemctl status traceability    # état du service
sudo systemctl restart traceability   # redémarrer
journalctl -u traceability -f         # suivre les logs
```
