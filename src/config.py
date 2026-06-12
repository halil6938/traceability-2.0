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
RECT_STABLE_FRAMES = 8            # frames consecutifs avec rectangle detecte avant capture
RECT_MIN_AREA_RATIO = 0.08        # aire min du rectangle / aire frame

# Retention photos (6 mois)
PHOTO_RETENTION_DAYS = 180

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
