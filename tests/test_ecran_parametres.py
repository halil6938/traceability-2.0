"""Construit reellement l'ecran Parametres puis l'ecran Capteurs, avec une
base remplie, pour verifier qu'ils se montent sans erreur ni blocage."""
import tkinter as tk

from _harness import setup, cleanup  # noqa: E402

sandbox = setup("param_")
from src import config, database  # noqa: E402

database.init_db()
database.add_device("Frigo volailles", 0, 4)
database.add_device("Congelateur", -25, -18)
database.add_sensor("bfc9dabac61c75135am53q", "T & H Sensor with external pro", "wifi")
sensors = database.list_ble_sensors()
database.update_ble_sensor(sensors[0]["id"], sensors[0]["label"],
                           database.list_devices()[0]["id"])
print("base : %d appareils, %d capteurs"
      % (len(database.list_devices()), len(database.list_ble_sensors())))

root = tk.Tk()
root.geometry("800x480")
config.SCREEN_W, config.SCREEN_H = 800, 480
root.withdraw()

from src.ui_settings import SettingsScreen  # noqa: E402

scr = SettingsScreen(root, lambda: None)
root.update()
print("ecran Parametres construit :", scr.winfo_exists() == 1)
print("ligne de version           :", scr._version_line())

before = len(scr.winfo_children())
scr._safe(scr._ble_config)          # <- l'action qui figeait l'appli
root.update()
after = len(scr.winfo_children())
print("ecran Capteurs ajoute      :", after > before)

# le cadre capteurs doit exister et contenir la liste
frames = [w for w in scr.winfo_children() if isinstance(w, tk.Frame)]
assert after > before, "l'ecran capteurs n'a pas ete cree"

log = (config.LOG_DIR / "ui.log")
etapes = log.read_text(encoding="utf-8").strip().splitlines() if log.exists() else []
print("\netapes journalisees :")
for line in etapes:
    print("   ", line.split(" INFO ")[-1])
assert any("pret" in e for e in etapes), "l'ecran capteurs n'est pas alle au bout"

# assignation d'un capteur : l'autre popup converti
from src.ui_settings import _pick_device  # noqa: E402
top = frames[-1]
_pick_device(top, database.list_ble_sensors()[0], database.list_devices(),
             lambda: None)
root.update()
print("\npopup d'assignation cree   :", len(top.winfo_children()) > 0)

root.destroy()
cleanup(sandbox)
print("\nTOUS LES TESTS OK")
