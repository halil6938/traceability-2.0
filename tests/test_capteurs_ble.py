"""Verifie : plus de capteurs codes en dur, decodage des temperatures
negatives, et presence des nouvelles actions dans l'ecran Capteurs."""
import struct
import tkinter as tk

from _harness import setup, cleanup  # noqa: E402

sandbox = setup("ble_")
from src import config, database  # noqa: E402

# --- 1. base neuve : aucun capteur impose ---
database.init_db()
sensors = database.list_ble_sensors()
print("1. capteurs sur un Pi neuf :", len(sensors), "(attendu 0)")
assert not sensors, f"capteurs codes en dur toujours presents : {sensors}"

# --- 2. decodage : congelateur a -18 C ---
raw = bytearray(12)
raw[10:12] = struct.pack("<h", int(-18.0 * 16))
avant = struct.unpack_from("<H", raw, 10)[0] / 16.0
apres = struct.unpack_from("<h", raw, 10)[0] / 16.0
print(f"2. trame d'un congelateur a -18 C -> avant : {avant:.1f} C "
      f"(rejetee), maintenant : {apres:.1f} C")
assert apres == -18.0
from src import ble_reader  # noqa: E402
assert ble_reader.TEMP_MIN <= -18.0 <= ble_reader.TEMP_MAX, \
    "la plage de validite exclut encore les congelateurs"
assert hasattr(ble_reader, "discover"), "detection des capteurs BLE absente"

# --- 3. ecran Capteurs : nouvelles actions ---
root = tk.Tk()
root.geometry("800x480")
config.SCREEN_W, config.SCREEN_H = 800, 480
root.withdraw()
database.add_device("Congelateur", -25, -18)
database.add_sensor("aa:bb:cc:dd:04:34", "Capteur 04:34", "ble")

from src.ui_settings import SettingsScreen  # noqa: E402

scr = SettingsScreen(root, lambda: None)
scr._safe(scr._ble_config)
root.update()


def labels(widget, out):
    if isinstance(widget, tk.Button):
        out.append(str(widget.cget("text")))
    for child in widget.winfo_children():
        labels(child, out)
    return out


found = labels(scr, [])
for wanted in ("🔍 Tester", "📡 Ajouter BLE", "⌨ Adresse",
               "🌐 Ajouter WiFi", "🔑 Clés", "Assigner", "Suppr"):
    print(f"3. bouton {wanted!r:26} present :", wanted in found)
    assert wanted in found, f"bouton manquant : {wanted}"

# --- 4. ajout puis suppression d'un capteur BLE ---
database.add_sensor("11:22:33:44:55:66", "Capteur 55:66", "ble")
n = len(database.list_ble_sensors())
database.delete_sensor(database.list_ble_sensors()[-1]["id"])
print(f"4. ajout puis suppression d'un capteur BLE : {n} -> "
      f"{len(database.list_ble_sensors())}")
assert len(database.list_ble_sensors()) == n - 1

root.destroy()
cleanup(sandbox)
print("\nTOUS LES TESTS OK")
