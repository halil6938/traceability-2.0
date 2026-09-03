"""Verifie que le recadrage sur l'etiquette reste juste apres l'optimisation
(detection sur image reduite, coordonnees remises a l'echelle) et mesure le gain."""
import sys
import time
import types
import pathlib

import numpy as np
import cv2

fake_config = types.ModuleType("config")
fake_config.LOG_DIR = pathlib.Path(".")
fake_config.CROP_TO_LABEL = True
fake_config.RECT_MIN_AREA_RATIO = 0.08
fake_db = types.ModuleType("database")
fake_db.get_meta = lambda k, d=None: d
fake_db.set_meta = lambda k, v: None
fake_usb = types.ModuleType("usb_manager")
pkg = types.ModuleType("src")
pkg.__path__ = ["src"]
sys.modules.update({"src": pkg, "src.config": fake_config,
                    "src.database": fake_db, "src.usb_manager": fake_usb})
pkg.config, pkg.database, pkg.usb_manager = fake_config, fake_db, fake_usb
from _harness import setup, cleanup  # noqa: E402
sandbox = setup("crop_")
fake_config.LOG_DIR = sandbox
from src import camera_scan as cs  # noqa: E402


class Fake:
    _detect_rectangle = cs.CameraScanScreen._detect_rectangle
    _crop_to_label = cs.CameraScanScreen._crop_to_label


# Photo 5 Mpx : fond sombre + etiquette blanche avec du "texte"
H, W = 1944, 2592
X0, Y0, X1, Y1 = 600, 400, 1800, 1250
img = np.full((H, W, 3), 40, np.uint8)
img[Y0:Y1, X0:X1] = 245
for i in range(12):                      # lignes de texte
    y = Y0 + 60 + i * 60
    cv2.line(img, (X0 + 60, y), (X1 - 80, y), (20, 20, 20), 6)

f = Fake()
t0 = time.perf_counter()
crop = f._crop_to_label(img)
dt_fast = time.perf_counter() - t0

t0 = time.perf_counter()
rect_full = f._detect_rectangle(img)     # ancienne methode : pleine resolution
dt_slow = time.perf_counter() - t0

label_w, label_h = X1 - X0, Y1 - Y0
exp_w = label_w + 2 * int(label_w * 0.10)
exp_h = label_h + 2 * int(label_h * 0.10)
print(f"etiquette          : {label_w} x {label_h} px en ({X0},{Y0})")
print(f"recadrage obtenu   : {crop.shape[1]} x {crop.shape[0]} px "
      f"(attendu ~{exp_w} x {exp_h} avec la marge de 10%)")
print(f"photo entiere      : {W} x {H} px")
print()
print(f"detection reduite  : {dt_fast * 1000:6.0f} ms  (nouvelle methode)")
print(f"detection 5 Mpx    : {dt_slow * 1000:6.0f} ms  (ancienne)")
print(f"gain               : x{dt_slow / dt_fast:.1f}")

assert crop.shape[1] < W and crop.shape[0] < H, "aucun recadrage !"
assert abs(crop.shape[1] - exp_w) < 60, "largeur du recadrage incorrecte"
assert abs(crop.shape[0] - exp_h) < 60, "hauteur du recadrage incorrecte"
# le recadrage doit bien contenir l'etiquette (centre tres clair)
c = crop[crop.shape[0] // 2, crop.shape[1] // 2]
assert c.mean() > 200, f"le recadrage ne tombe pas sur l'etiquette ({c})"
print("\nTOUS LES TESTS OK")

cleanup(sandbox)
