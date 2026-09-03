"""Pilote la VRAIE boucle de scan image par image pour verifier qu'une
etiquette laissee devant l'objectif n'est photographiee qu'UNE fois, et que
l'appareil ne se rearme qu'apres son retrait."""
import sys
import types
import pathlib

import numpy as np

fake_config = types.ModuleType("config")
fake_config.LOG_DIR = pathlib.Path(".")
fake_config.RECT_STABLE_FRAMES = 5
fake_config.RECT_ABSENT_FRAMES = 8
fake_config.SCAN_INACTIVITY_S = 180
fake_config.COLOR_SUCCESS = "#22c55e"
fake_config.COLOR_WARNING = "#f59e0b"
fake_config.SCREEN_W, fake_config.SCREEN_H = 800, 480
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
sandbox = setup("scan_")
fake_config.LOG_DIR = sandbox
from src import camera_scan as cs  # noqa: E402

FRAME = np.zeros((120, 160, 3), np.uint8)
RECT = np.array([[[10, 10]], [[150, 10]], [[150, 110]], [[10, 110]]], np.int32)


class Fake:
    """Instance minimale : seule la logique de la boucle est reelle."""
    test_mode = False
    _stop = False

    def __init__(self):
        self.label_present = False
        self.captures = 0
        self._stable_count = 0
        self._last_capture = 0
        self._capturing = False
        self._last_activity = 1e12      # jamais d'expiration pendant le test
        self._capture_msgs = []
        self._await_removal = False
        self._absent_count = 0
        self.status = types.SimpleNamespace(config=lambda **kw: None)

    _loop = cs.CameraScanScreen._loop

    def read_fn(self):
        return FRAME.copy()

    def _detect_rectangle(self, frame):
        return RECT if self.label_present else None

    def _show_frame(self, frame):
        pass

    def _show_capturing(self):
        pass

    def _do_capture(self):
        self.captures += 1
        self._last_capture = 0          # capture instantanee
        self._stable_count = 0
        self._capturing = False

    def after(self, ms, fn):
        pass                            # la boucle est pilotee a la main


def frames(f, n, present):
    f.label_present = present
    for _ in range(n):
        f._loop()


f = Fake()

frames(f, 10, True)
print("1. ticket present 10 images                -> %d photo(s)" % f.captures)
assert f.captures == 1, "il faut exactement une photo"

frames(f, 40, True)
print("2. ticket TOUJOURS la, 40 images de plus   -> %d photo(s) (doit rester 1)"
      % f.captures)
assert f.captures == 1, "l'appareil rephotographie le meme ticket !"

frames(f, 4, False)
print("3. ticket retire depuis 4 images (<8)      -> rearme :", not f._await_removal,
      "(doit etre False)")
assert f._await_removal, "rearme trop tot"

frames(f, 6, False)
print("4. ticket retire depuis 10 images (>8)     -> rearme :", not f._await_removal,
      "(doit etre True)")
assert not f._await_removal, "ne se rearme pas"

frames(f, 10, True)
print("5. nouveau ticket presente                 -> %d photo(s) au total" % f.captures)
assert f.captures == 2, "le ticket suivant n'est pas photographie"

# un clignotement bref de la detection ne doit pas rearmer
f2 = Fake()
frames(f2, 10, True)
for _ in range(3):                       # 3 images sans detection, puis retour
    frames(f2, 1, False)
    frames(f2, 1, True)
frames(f2, 20, True)
print("6. detection qui clignote pendant que le ticket reste -> %d photo(s)"
      % f2.captures)
assert f2.captures == 1, "un clignotement provoque une seconde photo"

print("\nTOUS LES TESTS OK")

cleanup(sandbox)
