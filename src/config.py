"""Configuration globale de l'application Traceability."""
import threading
from pathlib import Path

# Verrou global : une seule operation Bluetooth a la fois dans toute l'appli
# (deux scans simultanes peuvent bloquer BlueZ sur le Pi)
BLE_LOCK = threading.Lock()

# Dossiers sur la carte SD du Pi (config permanente)
APP_DIR = Path.home() / "traceability"
DB_PATH = APP_DIR / "config.db"
PENDING_DIR = APP_DIR / "pending_photos"  # photos en attente si pas d'USB
LOG_DIR = APP_DIR / "logs"

USB_SUBDIR = "traceability"  # sous-dossier créé sur la clé

# Parametres ecran — PAYSAGE 800x480
SCREEN_W = 800
SCREEN_H = 480

# Camera
CAMERA_RESOLUTION = (1640, 1232)  # capture haute qualite (ratio 4:3 natif Pi Camera v2)
PREVIEW_RESOLUTION = (640, 480)   # taille livree au preview (reduite par l'ISP
                                  # materiel du Pi : leger pour le CPU)
PREVIEW_SENSOR_MODE = (1296, 972) # mode capteur force pour le preview : le mode
                                  # 4:3 binne 2x2, bien plus net que le mode
                                  # capteur 640x480
CAMERA_ROTATION = 180             # rotation si camera montee de cote : 0, 90, 180 ou 270
FOCUS_DISTANCE_CM = 0             # 0 = autofocus reel avant chaque photo
                                  # (recommande : les modules AF generiques ne
                                  # sont pas calibres). >0 = focus fige a cette
                                  # distance en cm (necessite objectif calibre).
CROP_TO_LABEL = True              # recadre la photo sur l'etiquette detectee
                                  # (objectif grand angle : sans cela beaucoup
                                  # de decor inutile autour du ticket)
RECT_STABLE_FRAMES = 5            # frames consecutifs avec rectangle detecte avant capture
RECT_MIN_AREA_RATIO = 0.08        # aire min du rectangle / aire frame
RECT_ABSENT_FRAMES = 8            # apres une photo, frames consecutifs SANS
                                  # etiquette avant de réarmer (laisse le
                                  # temps de retirer le ticket)
SCAN_INACTIVITY_S = 180           # retour auto au menu si aucune etiquette
                                  # detectee pendant ce delai (mode scan)
SCREEN_OFF_S = 600                # veille de l'ecran apres ce delai sans
                                  # contact (0 = jamais de veille)

# Retention photos (6 mois)
PHOTO_RETENTION_DAYS = 180

# --- Controle a distance (verrou + reglages) ---
# Chaque Pi lit SON fichier : <REMOTE_CONTROL_BASE>/<device_id>.json sur GitHub.
REMOTE_CONTROL_BASE = ("https://raw.githubusercontent.com/"
                       "halil6938/traceability-2.0/master/devices")
REMOTE_POLL_S = 20      # frequence de verification (secondes) : compromis
                        # entre reactivite du verrou et trafic reseau
DEVICE_ID = ""          # identifiant de CE Pi (= nom du fichier) ; vide = nom d'hote

# --- Mise a jour automatique du code (voir src/updater.py) ---
REPO_URL = "https://github.com/halil6938/traceability-2.0.git"
REPO_DIR = Path.home() / "traceability-2.0"  # depot local (clone au besoin)
REPO_BRANCH = "master"
UPDATE_CHECK_S = 900         # verification toutes les 15 min
UPDATE_QUIET_HOURS = (2, 5)  # heures creuses des mises a jour « auto »
UPDATE_MAX_PENDING_H = 24    # au-dela, appliquer meme hors heures creuses
                             # (Pi eteint la nuit)

# Couleurs UI
COLOR_BG = "#1e293b"
COLOR_FG = "#f1f5f9"
COLOR_PRIMARY = "#0ea5e9"
COLOR_SUCCESS = "#22c55e"
COLOR_DANGER = "#ef4444"
COLOR_WARNING = "#f59e0b"
COLOR_CARD = "#334155"
COLOR_MUTED = "#94a3b8"

# Fonts
FONT_TITLE = ("DejaVu Sans", 24, "bold")
FONT_BIG = ("DejaVu Sans", 20, "bold")
FONT_MED = ("DejaVu Sans", 14)
FONT_SMALL = ("DejaVu Sans", 11)

APP_DIR.mkdir(parents=True, exist_ok=True)
PENDING_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
