# Traceability 2.0

Application de traçabilité pour Raspberry Pi 3 (écran tactile 5" 800×480, **paysage**) :

- 📷 **Scan ticket** : détection auto d'étiquettes blanches sur fond contrasté, capture automatique.
- 🌡 **Relevés de température** : saisie tactile quotidienne par appareil (frigo/congélateur) avec alerte hors seuils. Capteurs **BLE** (Brifit WS07) et **WiFi Tuya** (lecture via le cloud Smart Life — nécessite des clés API sur iot.tuya.com ; ⚠ le plan gratuit « Trial » expire tous les 6 mois, à renouveler sur iot.tuya.com si les lectures WiFi tombent en erreur d'autorisation).
- 📦 **Réception** : relevé de température des produits livrés par fournisseur, via thermomètre Bluetooth (pistolet IR HoldPeak HP-985C-APP) ou saisie manuelle.
- 📊 **Historique** mensuel consultable et modifiable (tickets, températures, réceptions).
  Une réception oubliée se rattrape depuis **Historique ▸ Réceptions ▸ + Ajouter**
  (fournisseur, jour du mois affiché, température) ; chaque ligne est aussi
  modifiable et supprimable. Les jours à venir ne sont pas sélectionnables.
- 📄 **Export PDF** par mois sur clé USB (températures + réceptions).
- 🗑 **Purge auto** des photos > 6 mois.
- 🔒 **Contrôle à distance** : verrou + réglages via `remote_control.json` (voir plus bas).

## Contrôle à distance (verrou + réglages)

Chaque Pi lit périodiquement (≈20 s) **son propre fichier** `devices/<nom-du-pi>.json`
(le nom d'hôte du Pi), qu'on édite directement sur GitHub (téléphone ou PC). Un fichier
par client → pour en bloquer un, on ouvre juste son fichier. Gabarit :
[`devices/_modele.json`](devices/_modele.json).

`devices/raspstpriest.json` :
```json
{
  "locked": true,
  "message": "Application suspendue.\nContactez votre fournisseur.",
  "config": { "COLOR_PRIMARY": "#e11d48", "SCAN_INACTIVITY_S": 120 }
}
```

Nouveau client : copier `_modele.json` en `<hostname>.json` (voir `hostname` sur le Pi).

- **Bloquer** : `locked: true` + un `message`. Un overlay plein écran non fermable
  s'affiche. Le blocage est mémorisé localement → il **survit au redémarrage** de
  l'appli et du Pi, et à une coupure internet. Débloquer : remettre `locked: false`.
- **Régler à distance** (`config`) : liste blanche = `COLOR_*` (format `#rrggbb`),
  `SCAN_INACTIVITY_S`, `SCREEN_OFF_S`, `RECT_STABLE_FRAMES`, `PHOTO_RETENTION_DAYS`,
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
├── tools/                    # diagnostic (ble_e2e.py, focus_probe.py)
│                             # + déploiement (prepare_master.sh, set_client.sh)
├── requirements.txt
├── install.sh
└── traceability.service
```

## Installation sur le Raspberry Pi

1. Copier le dossier `traceability/` sur le Pi (clé USB, SCP, git clone...).
2. `cd traceability && bash install.sh`
3. Redémarrer : l'appli se lance automatiquement.

## Essayer l'application sur un PC

```bash
python tools/run_pc.py
```

Ouvre l'appli dans une fenêtre 800×480 (la taille de l'écran du Pi). Pratique
pour essayer une modification sans toucher à un Pi en production.

- Données isolées dans `_local/` : aucune configuration réelle n'est touchée.
- **Contrôle à distance, mise à jour automatique et signe de vie désactivés** —
  un essai sur PC ne peut ni verrouiller ni mettre à jour quoi que ce soit.
- La caméra utilise la webcam du PC : l'autofocus et la calibration ne sont pas
  représentatifs du module du Pi.
- `Échap` bascule le plein écran. Pour repartir de zéro : supprimer `_local/`.

Prérequis (une seule fois) : `pip install opencv-python-headless pillow reportlab bleak tinytuya`

## Tests automatiques

```bash
python tests/run_all.py
```

11 tests qui pilotent réellement l'application (interface comprise) et vérifient
les points qui ont posé problème en production : dialogues enchaînés qui figeaient
l'appli, contact sur écran en veille qui ne doit déclencher aucun bouton, une seule
photo par ticket, recadrage sur l'étiquette, calibration du focus, mise à jour
annulée si le code ne démarre pas, signe de vie, effacement des données client,
rattrapage d'une réception.

Chaque test s'exécute isolé (dossier temporaire, aucun réseau) : ni la config d'un
Pi ni celle du PC ne sont touchées. Certains ouvrent brièvement une fenêtre, c'est
normal. **À lancer avant chaque fabrication de carte SD.**

## Signe de vie Telegram (parc à distance)

Chaque Pi annonce sur Telegram qu'il est en ligne et quelle version il exécute :
un message **immédiat** à l'installation et à chaque mise à jour, puis un message
**quotidien** à partir de `HEARTBEAT_HOUR` (8 h par défaut, réglable à distance).
Un Pi qui ne donne plus signe de vie est hors ligne — c'est à l'exploitant de le
remarquer, rien ne surveille à sa place.

Configuration, **une seule fois sur le Pi modèle** (les identifiants partent dans
l'image et sont conservés par `prepare_master.sh`) :

1. Dans Telegram, écrire à **@BotFather** → `/newbot` → il donne un **jeton**.
2. Écrire un message quelconque à ce nouveau bot (sinon il ne peut pas répondre).
3. Sur le Pi :

```bash
python3 ~/traceability-app/tools/set_telegram.py --chat-id <jeton>   # trouve le chat_id
python3 ~/traceability-app/tools/set_telegram.py <jeton> <chat_id>   # enregistre
python3 ~/traceability-app/tools/set_telegram.py --test              # message d'essai
```

Seuls le **nom du magasin** et la **version** sont transmis — aucune donnée client.
Le jeton étant présent dans l'image, il se retrouve sur chaque Pi installé : en cas
de fuite, le régénérer via @BotFather suffit à tout invalider.

## Veille de l'écran

Après `SCREEN_OFF_S` secondes sans contact (600 par défaut, `0` = jamais),
l'application éteint l'écran : rétroéclairage coupé **et** voile noir plein écran.

Ce voile est le point important : il **absorbe le contact qui réveille
l'appareil**. Avec la veille du système, ce contact est transmis à l'application
et déclenche le bouton situé sous le doigt — l'opérateur se retrouve alors dans
un menu au hasard. Ici, le premier contact ne fait que rallumer.

L'appli désactive donc la veille du système au démarrage (`xset`) pour en garder
la maîtrise. Le délai est réglable à distance (`SCREEN_OFF_S` dans `config`).

## Mise à jour automatique du code

Chaque Pi compare toutes les 15 min le code déployé à la branche `master` du
dépôt. Si elle a avancé, il récupère la nouvelle version, **vérifie qu'elle
démarre**, puis redémarre l'application. Il suffit donc de pousser sur GitHub
pour mettre à jour tout le parc.

Garde-fous — une mauvaise version ne doit pas paralyser les magasins :

- mise à jour **uniquement quand l'appli est au repos** (menu principal), jamais
  pendant un scan ou une mesure ;
- en mode `auto`, **seulement entre 2 h et 5 h** — sauf si la mise à jour attend
  depuis plus de 24 h (Pi éteint la nuit) ;
- le nouveau code est **chargé en test avant d'être adopté** ; s'il ne démarre
  pas, **retour automatique à la version précédente** (journalisé dans
  `~/traceability/logs/update.log`) ;
- un commit qui ne touche **que** `devices/*.json` (verrou, réglages, mode de
  mise à jour) est enregistré sans redémarrer l'application — éditer le fichier
  de contrôle n'interrompt donc jamais un magasin ;
- pilotage par appareil dans `devices/<hostname>.json` :

```json
{ "update": "auto" }
```
`auto` (défaut) · `now` (dès que possible, pour un correctif urgent) ·
`off` (fige la version de ce client).

La version déployée et le nom du Pi sont affichés en bas de l'écran
**Paramètres** (utile pour le support à distance).

⚠ Le Pi exécute le code du dépôt : garder la **2FA** active sur le compte
GitHub, et tester avant de pousser.

## Déployer sur plusieurs Pi (clonage de carte SD)

Le clonage emporte tous les réglages système déjà faits sur le Pi maître
(rotation de l'écran, `dtoverlay=ov5647,vcm`, Bluetooth, démarrage auto) —
c'est ce qui rend la méthode rapide. Matériel identique requis.

**1. Préparer l'image modèle** (sur le Pi maître, une seule fois) :

```bash
bash tools/prepare_master.sh        # --garder-wifi pour conserver le WiFi
sudo poweroff                       # ÉTEINDRE, surtout ne pas redémarrer
```

Efface les données du client (relevés, appareils, fournisseurs, capteurs,
calibration caméra), les identifiants uniques (clés SSH, machine-id) et les
WiFi mémorisés. **Conserve les clés cloud Tuya** (compte développeur commun).

**2. Copier la carte SD** dans une image, sur le PC (Raspberry Pi Imager →
« Lire », ou Win32DiskImager → *Read*).

**3. Flasher chaque nouveau Pi** avec cette image via Raspberry Pi Imager, en
renseignant dans les **réglages avancés** (roue crantée) :
- un **nom d'hôte unique** = le nom du client (`boucherie-durand`) — c'est
  l'identifiant du [contrôle à distance](#contrôle-à-distance-verrou--réglages) ;
- le **WiFi du magasin**.

Si le nom n'a pas été défini au flashage : `bash tools/set_client.sh boucherie-durand`.

**4. Sur place**, au premier démarrage :
1. Assistant : créer les appareils (frigos/congélateurs) avec leurs seuils.
2. **Réception → ⚙ Fournisseurs** : fournisseurs + MAC du pistolet BLE.
3. **Paramètres → 📡 Capteurs temp.** : **📡 Ajouter BLE** (détection des
   capteurs à proximité, ou ⌨ pour saisir l'adresse) et **🌐 Ajouter WiFi**
   (liste du cloud Tuya), puis **Assigner** chaque capteur à un appareil.
4. **Paramètres → 📷 Test caméra → 🎯 Calibrer** (propre à chaque montage).
5. Sur GitHub, créer `devices/<nom-du-client>.json` (copie de `_modele.json`)
   pour pouvoir verrouiller ce Pi à distance. Sans fichier, il fonctionne
   normalement.

## Stockage

- **Carte SD** (`~/traceability/`) : base SQLite (config + relevés), photos en attente si USB absente, logs.
- **Clé USB** (`/media/pi/<VOLUME>/traceability/`) : photos (`photos/YYYY-MM/…jpg`), exports PDF (`exports/`).

Si l'USB est absente au moment d'une photo, elle est stockée localement puis synchronisée automatiquement dès la reconnexion.

## Mise au point de la caméra (module autofocus)

Sur les modules AF clones (OV5647-AF…), l'autofocus continu n'est pas fiable :
le pilote expose bien le moteur, mais la lentille peut rester où elle était —
d'où une image nette un jour et floue après un redémarrage.

Comme la caméra est montée à distance fixe, on **calibre une fois** :

1. Placer un ticket à la distance de travail définitive (support en place).
2. **Paramètres → 📷 Test caméra → 🎯 Calibrer** (~10 s) : l'appli balaye toutes
   les positions de lentille, mesure la netteté à chacune (passe large puis
   fine) et **fige la meilleure**, enregistrée en base (`camera_lens_position`).
3. La mise au point est alors identique à chaque démarrage, sans autofocus.

**↺ Auto** efface la calibration et revient à l'autofocus automatique.
Prérequis : `dtoverlay=ov5647,vcm` dans `/boot/firmware/config.txt`
(+ `camera_auto_detect=0`) pour que le moteur de mise au point soit piloté.

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
