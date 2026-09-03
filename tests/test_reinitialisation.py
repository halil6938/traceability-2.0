"""Teste reset_client_data.py dans un bac a sable : une base remplie comme
chez un client, puis effacement, puis verification de ce qui reste."""
import os
import subprocess
import sys

from _harness import REPO, setup, cleanup  # noqa: E402

sandbox = setup("reset_")
env = dict(os.environ, HOME=str(sandbox), USERPROFILE=str(sandbox))

# --- remplir une base "client" ---
fill = f'''
import sys; sys.path.insert(0, r"{REPO}")
from datetime import date
from src import database, config
database.init_db()
database.add_device("Frigo volailles", 0, 4)
did = database.list_devices()[0]["id"]
database.save_reading(did, date.today(), 3.2)
database.add_supplier("Bigard")
sid = database.list_suppliers()[0]["id"]
database.save_reception(sid, 4.1)
database.add_sensor("aa:bb:cc:dd:ee:ff", "Capteur salle", "wifi")
database.set_meta("setup_done", "1")
database.set_meta("tuya_access_id", "MON_ID_TUYA")
database.set_meta("tuya_access_secret", "MON_SECRET_TUYA")
database.set_meta("tuya_region", "eu")
database.set_meta("reception_thermo_mac", "07:b4:ec:14:67:5a")
database.set_meta("camera_lens_position", "6.250")
database.set_meta("remote_locked", "1")
(config.PENDING_DIR / "photo_test.jpg").write_bytes(b"x" * 100)
(config.LOG_DIR / "ble_thermo.log").write_text("trace de test")
print("AVANT  : %d appareil(s), %d fournisseur(s), %d capteur(s)" % (
    len(database.list_devices()), len(database.list_suppliers()),
    len(database.list_ble_sensors())))
print("         photos en attente :", len(list(config.PENDING_DIR.iterdir())))
'''
r = subprocess.run([sys.executable, "-c", fill], env=env, capture_output=True, text=True)
print(r.stdout.strip() or r.stderr.strip())
assert r.returncode == 0, r.stderr

# --- effacement ---
print("\n--- reset_client_data.py ---")
r = subprocess.run([sys.executable, str(REPO / "tools" / "reset_client_data.py")],
                   env=env, cwd=str(REPO), capture_output=True, text=True)
print(r.stdout.strip() or r.stderr.strip())
assert r.returncode == 0, r.stderr

# --- verification ---
check = f'''
import sys; sys.path.insert(0, r"{REPO}")
from src import database, config
devs = database.list_devices(); sups = database.list_suppliers()
wifi = [s for s in database.list_ble_sensors() if s.get("kind") == "wifi"]
print("APRES  : %d appareil(s), %d fournisseur(s), %d capteur(s) wifi" % (
    len(devs), len(sups), len(wifi)))
print("         photos en attente :", len(list(config.PENDING_DIR.iterdir())))
print("         logs              :", len(list(config.LOG_DIR.iterdir())))
print("EFFACE  setup_done        :", repr(database.get_meta("setup_done", "")))
print("EFFACE  thermo_mac        :", repr(database.get_meta("reception_thermo_mac", "")))
print("EFFACE  camera_lens       :", repr(database.get_meta("camera_lens_position", "")))
print("EFFACE  remote_locked     :", repr(database.get_meta("remote_locked", "")))
print("GARDE   tuya_access_id    :", repr(database.get_meta("tuya_access_id", "")))
print("GARDE   tuya_secret       :", repr(database.get_meta("tuya_access_secret", "")))
print("GARDE   tuya_region       :", repr(database.get_meta("tuya_region", "")))
ok = (not devs and not sups and not wifi
      and not database.get_meta("setup_done", "")
      and not database.get_meta("camera_lens_position", "")
      and not database.get_meta("remote_locked", "")
      and database.get_meta("tuya_access_id", "") == "MON_ID_TUYA"
      and database.get_meta("tuya_access_secret", "") == "MON_SECRET_TUYA")
print("\\nRESULTAT :", "OK" if ok else "ECHEC")
sys.exit(0 if ok else 1)
'''
r = subprocess.run([sys.executable, "-c", check], env=env, capture_output=True, text=True)
print(r.stdout.strip() or r.stderr.strip())
cleanup(sandbox)
sys.exit(r.returncode)
