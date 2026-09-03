"""Simule le balayage de calibration : objectif dont l'optimum reel est connu.
Verifie que la calibration le retrouve, l'enregistre et la relit."""
import sys
import types
import pathlib

# --- mocks config / database / cv2-libres ---
fake_config = types.ModuleType("config")
fake_config.LOG_DIR = pathlib.Path(".")
fake_config.FOCUS_DISTANCE_CM = 0
fake_config.COLOR_WARNING = "#f59e0b"
fake_config.COLOR_SUCCESS = "#22c55e"
fake_config.COLOR_DANGER = "#ef4444"
_meta = {}
fake_db = types.ModuleType("database")
fake_db.get_meta = lambda k, d=None: _meta.get(k, d)
fake_db.set_meta = lambda k, v: _meta.__setitem__(k, v)

pkg = types.ModuleType("src")
pkg.__path__ = ["src"]
sys.modules.update({"src": pkg, "src.config": fake_config, "src.database": fake_db})
pkg.config = fake_config
pkg.database = fake_db
from _harness import setup, cleanup  # noqa: E402
sandbox = setup("focus_")
fake_config.LOG_DIR = sandbox

from src import camera_scan as cs

TRUE_BEST = 7.3  # position optimale reelle de l'objectif simule
LENS_MIN, LENS_MAX = 0.0, 15.0


class Fake:
    """Reprend les methodes reelles de calibration, sans Tk ni camera."""
    _cal = None
    _cal_done_at = 0.0
    _stop = False
    _sharp_max = 0.0

    def __init__(self):
        self.lens = 0.0
        self.visited = []
        self.status = types.SimpleNamespace(config=lambda **kw: None)

    # --- ce que le materiel fournirait ---
    def _lens_range(self):
        return LENS_MIN, LENS_MAX

    def _set_lens(self, pos):
        self.lens = max(LENS_MIN, min(LENS_MAX, float(pos)))
        self.visited.append(round(self.lens, 3))
        return True

    def read_fn(self):
        return "frame"

    def _sharpness(self, frame):
        # nettete en cloche autour de TRUE_BEST (+ bruit deterministe leger)
        d = self.lens - TRUE_BEST
        return 1000.0 / (1.0 + d * d) + (hash(round(self.lens, 2)) % 7)

    def after(self, ms, fn):
        fn()

    # --- methodes testees (les vraies) ---
    _calibrated_lens = cs.CameraScanScreen._calibrated_lens
    _start_calibration = cs.CameraScanScreen._start_calibration
    _cal_next = cs.CameraScanScreen._cal_next
    _cal_measure = cs.CameraScanScreen._cal_measure
    _finish_calibration = cs.CameraScanScreen._finish_calibration
    _clear_calibration = cs.CameraScanScreen._clear_calibration
    _focus_is_fixed = cs.CameraScanScreen._focus_is_fixed


cs.HAS_PICAMERA = True
f = Fake()
print("calibration memorisee au depart :", f._calibrated_lens())
print("focus fige au depart :", f._focus_is_fixed())

f._start_calibration()

found = float(_meta["camera_lens_position"])
print("positions balayees :", len(f.visited))
print("optimum reel : %.2f  |  trouve : %.3f  |  ecart : %.3f"
      % (TRUE_BEST, found, abs(found - TRUE_BEST)))
print("lentille laissee sur :", round(f.lens, 3))
print("relecture apres redemarrage :", f._calibrated_lens())
print("focus fige apres calibration :", f._focus_is_fixed())

assert abs(found - TRUE_BEST) < 0.35, "optimum manque"
assert abs(f.lens - found) < 1e-6, "lentille non positionnee sur l'optimum"
assert f._cal is None, "etat de calibration non liberee"

# bouton Auto : oubli de la calibration
f.picam = types.SimpleNamespace(set_controls=lambda c: None)
f._clear_calibration()
print("apres 'Auto' -> calibration :", f._calibrated_lens(),
      "| focus fige :", f._focus_is_fixed())
assert f._calibrated_lens() is None

print("\nTOUS LES TESTS OK")

cleanup(sandbox)
