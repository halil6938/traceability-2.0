# Traceability 2.0

Application de traçabilité pour Raspberry Pi 3 (écran tactile 5" 800×480, **paysage**) :

- 📷 **Scan ticket** : détection auto d'étiquettes blanches sur fond contrasté, capture automatique.
- 🌡 **Relevés de température** : saisie tactile quotidienne par appareil (frigo/congélateur) avec alerte hors seuils. Capteurs **BLE** (Brifit WS07) et **WiFi Tuya** (lecture via le cloud Smart Life — nécessite des clés API sur iot.tuya.com ; ⚠ le plan gratuit « Trial » expire tous les 6 mois, à renouveler sur iot.tuya.com si les lectures WiFi tombent en erreur d'autorisation).
- 📦 **Réception** : relevé de température des produits livrés par fournisseur, via thermomètre Bluetooth (pistolet IR HoldPeak HP-985C-APP) ou saisie manuelle.
- 📊 **Historique** mensuel consultable et modifiable (tickets, températures, réceptions).
- 📄 **Export PDF** par mois sur clé USB (températures + réceptions).
- 🗑 **Purge auto** des photos > 6 mois.
- 🔒 **Contrôle à distance** : verrou + réglages via `remote_control.json` (voir plus bas).

## Contrôle à distance (verrou + réglages)

Chaque Pi lit périodiquement (≈1 min) le fichier [`remote_control.json`](remote_control.json)
de ce dépôt, à la ligne correspondant à **son nom d'hôte**. On l'édite directement
sur GitHub (téléphone ou PC).

```json
"raspstpriest": {
  "locked": true,
  "message": "Application suspendue.\nContactez votre fournisseur.",
  "config": { "COLOR_PRIMARY": "#e11d48", "SCAN_INACTIVITY_S": 120 }
}
```

- **Bloquer** : `locked: true` + un `message`. Un overlay plein écran non fermable
  s'affiche. Le blocage est mémorisé localement → il **survit au redémarrage** de
  l'appli et du Pi, et à une coupure internet. Débloquer : remettre `locked: false`.
- **Régler à distance** (`config`) : liste blanche = `COLOR_*` (format `#rrggbb`),
  `SCAN_INACTIVITY_S`, `RECT_STABLE_FRAMES`, `PHOTO_RETENTION_DAYS`,
  `FOCUS_DISTANCE_CM`, `CAMERA_ROTATION`. Une valeur inconnue/invalide est ignorée.
  Les changements de couleur s'appliquent au retour au menu (ou au redémarrage).
- Une coupure réseau **conserve le dernier état connu** (jamais de blocage accidentel).
  Un Pi non listé est considéré comme autorisé.
- ⚠ Blocage **dissuasif** (soft) : un accès physique + technique peut le contourner.
  Activer la **2FA** sur le compte GitHub (le Pi exécute ce que dit le dépôt).

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
│   ├── ble_reader.py         # capteurs frigo BLE (Brifit WS07)
│   ├── tuya_reader.py        # capteurs frigo WiFi Tuya (cloud Smart Life)
│   ├── sensor_reader.py      # lecture combinee BLE + WiFi
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
