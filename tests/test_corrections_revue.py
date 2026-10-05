"""Corrections issues de la revue de code : chaque point est verifie sur l'appli
reelle (Bluetooth, camera, cle USB et depot git simules)."""
import time
from datetime import date, datetime

from _harness import setup, cleanup  # noqa: E402
sandbox = setup("revue_")

from src import (ble_thermo, config, database, remote_lock, sauvegarde,  # noqa: E402
                 sensor_reader, updater, usb_manager)

config.REMOTE_CONTROL_BASE = ""
config.REPO_URL = ""
config.SCREEN_OFF_S = 0
database.init_db()
database.set_meta("setup_done", "1")

# 1. pistolet : une trame coupee ou abimee n'invente plus de temperature ------
TL, TH, SS = 0x32, 0x00, 0x01                     # 5,0 °C
bonne = bytes([0xBC, 0x05, 0x00, 0x5F, TL, TH, SS, (0x64 + TL + TH + SS) & 0xFF])
assert ble_thermo.parse_frame(bonne)[0] == 5.0
assert ble_thermo.parse_frame(bonne[:6]) is None, "trame coupee decodee"
assert ble_thermo.parse_frame(bonne[:7] + b"\x00") is None, "checksum faux accepte"
assert ble_thermo.parse_frame(b"\x00\x12" + bonne)[0] == 5.0, "trame decalee perdue"
print("1. pistolet : seules les trames completes et verifiees comptent : OK")

# 4. reglages a distance bornes -----------------------------------------------
remote_lock.apply_config({"PHOTO_RETENTION_DAYS": 0, "HISTORY_INACTIVITY_S": 0,
                          "CAMERA_ROTATION": 45, "HEARTBEAT_HOUR": 30})
assert config.PHOTO_RETENTION_DAYS == 180, "0 jour de conservation accepte"
assert config.HISTORY_INACTIVITY_S == 180 and config.CAMERA_ROTATION == 180
assert config.HEARTBEAT_HOUR == 8
remote_lock.apply_config({"PHOTO_RETENTION_DAYS": 365, "SCREEN_OFF_S": 0,
                          "CAMERA_ROTATION": 90})
assert (config.PHOTO_RETENTION_DAYS, config.SCREEN_OFF_S, config.CAMERA_ROTATION) == (365, 0, 90)
remote_lock.apply_config({})
assert config.PHOTO_RETENTION_DAYS == 180 and config.CAMERA_ROTATION == 180
print("2. reglages a distance : valeurs dangereuses refusees, valeurs saines prises : OK")

# 3. sauvegarde de la base sur la cle USB -------------------------------------
cle = sandbox / "cle" / "traceability"
usb_manager.usb_base_dir = lambda: cle
database.add_device("Frigo A", 0, 4)
database.save_reading(database.list_devices()[0]["id"], date.today(), 3.1)
database.set_meta("telegram_token", "SECRET-TELEGRAM-123")
database.set_meta("tuya_access_secret", "SECRET-TUYA-456")
for i in range(16):                               # 16 jours de suite
    chemin = sauvegarde.sauvegarder(date(2026, 1, 1 + i))
copies = sorted((cle / "sauvegardes").glob("config_*.db"))
assert len(copies) == sauvegarde.JOURS_GARDES, len(copies)
assert copies[-1] == chemin and not (cle / "sauvegardes" / "en_cours.tmp").exists()
import sqlite3  # noqa: E402
c = sqlite3.connect(chemin)
assert c.execute("SELECT COUNT(*) FROM readings").fetchone()[0] == 1, "releve absent"
assert not c.execute("SELECT 1 FROM meta WHERE key LIKE '%token%' "
                     "OR key LIKE '%secret%'").fetchall(), "identifiants copies"
c.close()
brut = chemin.read_bytes()
assert b"SECRET-TELEGRAM" not in brut and b"SECRET-TUYA" not in brut, \
    "identifiants encore lisibles dans le fichier"
assert database.get_meta("telegram_token") == "SECRET-TELEGRAM-123", "base d'origine touchee"
usb_manager.usb_base_dir = lambda: None
assert sauvegarde.sauvegarder() is None
print("3. sauvegarde : copie complete, sans identifiants, 14 jours gardes : OK")

# 6. mise a jour : modules installes AVANT la verification --------------------
ordre = []
updater.repo_ready = lambda: sandbox
updater._rev = lambda ref: "ancien"
updater._git = lambda *a, **k: type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
updater._sync_to_app_dir = lambda repo: ordre.append("copie")
updater._install_requirements = lambda *a: ordre.append("modules")
updater._health_ok = lambda: (ordre.append("verification"), "modules" in ordre)[1]
assert updater.perform_update("nouveau"), "mise a jour avec nouveau module refusee"
assert ordre == ["copie", "modules", "verification"], ordre
print("4. mise a jour : nouveaux modules installes avant la verification : OK")

# --- ecrans : appli reelle -----------------------------------------------------
from src import camera_scan  # noqa: E402
camera_scan.HAS_PICAMERA = False
from src.ui_main import App, MainMenu  # noqa: E402


class TestApp(App):
    def attributes(self, *a):
        if a and a[0] in ("-fullscreen", "-topmost"):
            return None
        return super().attributes(*a)

    def winfo_screenwidth(self):
        return 800

    def winfo_screenheight(self):
        return 480

    def focus_force(self):
        pass


app = TestApp()
app.geometry("800x480+20+20")
erreurs = []
app.report_callback_exception = lambda et, ev, tb: erreurs.append(f"{et.__name__}: {ev}")


def pump(ms):
    fin = time.time() + ms / 1000
    while time.time() < fin:
        app.update()
        time.sleep(0.005)


pump(200)

# 5. camera indisponible : message clair, retour au menu propre ---------------
def camera_absente(self):
    raise RuntimeError("Camera __init__ sequence did not complete")


camera_scan.CameraScanScreen._init_camera = camera_absente
app.show_scan(); pump(150)
assert isinstance(app.current, camera_scan.CameraScanScreen), "ecran de scan non cree"
assert "indisponible" in app.current.preview_label.cget("text")
app.current._back(); pump(150)
assert isinstance(app.current, MainMenu)
restes = [w for w in app.winfo_children() if isinstance(w, camera_scan.CameraScanScreen)]
assert not restes, "l'ecran noir de la camera reste derriere le menu"
assert not erreurs, erreurs
print("5. camera absente : message affiche, retour au menu propre : OK")

# 2. releve automatique : nouvel essai tant qu'un appareil manque -------------
aujourd_hui = date.today()
for nom in ("Frigo B", "Frigo C"):
    database.add_device(nom, 0, 4)
appareils = {d["name"]: d["id"] for d in database.list_devices()}
database.save_reading(appareils["Frigo A"], aujourd_hui, 3.1)   # (deja releve)
for i, nom in enumerate(("Frigo B", "Frigo C")):
    database.add_sensor(f"aa:00:00:00:00:0{i}", nom, "ble")
for s in database.list_ble_sensors():
    database.update_ble_sensor(s["id"], s["label"], appareils[s["label"]])

lus = []


def capteurs(reponses):
    def lire(sensors, cancel=None):
        lus.append(sorted(s["mac"] for s in sensors))
        return reponses, None
    return lire


# 3 h : le capteur de Frigo C ne repond pas
sensor_reader.read_all = capteurs({"aa:00:00:00:00:00": 2.4})
app._releve_auto()
assert database.get_meta("ble_auto_date") != aujourd_hui.isoformat(), \
    "journee marquee faite alors qu'un appareil n'a pas de releve"
# essai suivant : seul Frigo C est relu, et le releve de Frigo B n'est pas remplace
sensor_reader.read_all = capteurs({"aa:00:00:00:00:00": 9.9, "aa:00:00:00:00:01": 3.0})
app._releve_auto()
assert lus[-1] == ["aa:00:00:00:00:01"], f"essai suivant : {lus[-1]}"
assert database.get_reading(appareils["Frigo B"], aujourd_hui)["temperature"] == 2.4
assert database.get_reading(appareils["Frigo C"], aujourd_hui)["temperature"] == 3.0
assert database.get_meta("ble_auto_date") == aujourd_hui.isoformat()

# le minuteur relance bien un essai une heure apres, pas avant
database.set_meta("ble_auto_date", "")
app._releve_en_cours = False
app._dernier_essai_releve = time.time() - 600
appels = []
app._do_ble_auto = lambda: appels.append(1)
heure = datetime.now().hour
app._ble_tick()
if heure >= 3:
    assert not appels, "nouvel essai lance avant une heure"
    app._dernier_essai_releve = time.time() - config.RELEVE_REESSAI_S - 1
    app._ble_tick(); pump(100)
    assert appels, "pas de nouvel essai au bout d'une heure"
print("6. releve auto : nouvel essai toutes les heures pour les seuls manquants : OK")

# alerte du jour : un appareil equipe sans releve est signale des 5 h
database.add_device("Frigo D", 0, 4)
appareils = {d["name"]: d["id"] for d in database.list_devices()}
database.add_sensor("aa:00:00:00:00:09", "Frigo D", "ble")
s = [x for x in database.list_ble_sensors() if x["mac"] == "aa:00:00:00:00:09"][0]
database.update_ble_sensor(s["id"], s["label"], appareils["Frigo D"])
database.add_device("Frigo manuel", 0, 4)            # sans capteur, jamais saisi
hier = date.fromordinal(aujourd_hui.toordinal() - 1)
database.save_reading(appareils["Frigo D"], hier, 3.0)
database.save_reading(database.list_devices()[-1]["id"], hier, 3.0)
config.RELEVE_ALERTE_HEURE = 0                        # « il est plus de 5 h »
app.show_menu(); pump(100)
app.current._check_alerts()
texte = app.current.alert.cget("text")
assert "Frigo D" in texte, f"appareil equipe sans releve du jour non signale : {texte!r}"
assert "Frigo manuel" not in texte, "appareil manuel signale des le matin"
config.RELEVE_ALERTE_HEURE = 24                       # « il est avant 5 h »
app.current._check_alerts()
assert "Frigo D" not in app.current.alert.cget("text")
config.RELEVE_ALERTE_HEURE = 5
print("7. ligne d'alerte : releve du jour manquant signale des 5 h : OK")

assert not erreurs, erreurs
app.destroy()
cleanup(sandbox)
print("\nTOUS LES TESTS OK")
