"""Corrections issues de l'audit complet de l'appli : chaque point est verifie
sur l'appli reelle (Bluetooth, camera et reseau simules)."""
import os
import time

from datetime import date, datetime

from _harness import setup, cleanup  # noqa: E402
sandbox = setup("audit_")

from src import (ble_thermo, config, database, remote_lock, sensor_reader,  # noqa: E402
                 ui_common, usb_manager)

config.REMOTE_CONTROL_BASE = ""
config.REPO_URL = ""
config.SCREEN_OFF_S = 0
database.init_db()
database.set_meta("setup_done", "1")


class FakeConn:
    arretes = 0

    def __init__(self, mac):
        self.status = ble_thermo.ST_CONNECTED

    def start(self):
        pass

    def stop(self):
        FakeConn.arretes += 1

    def poll(self):
        return None


class FakeCap:
    """Camera simulee : le test n'ouvre jamais la webcam du PC."""
    def __init__(self, *_a):
        import numpy as np
        self.image = np.full((480, 640, 3), 90, np.uint8)

    def set(self, *_a):
        return True

    def read(self):
        return True, self.image.copy()

    def release(self):
        pass


from src import camera_scan  # noqa: E402
camera_scan.HAS_PICAMERA = False
camera_scan.cv2.VideoCapture = FakeCap
ble_thermo.ThermoConnection = FakeConn
ble_thermo.HAS_BLEAK = True
sensor_reader.read_all = lambda sensors, cancel=None: ({}, None)
database.set_meta("reception_thermo_mac", "07:b4:ec:14:67:5a")

from src.ui_main import App, MainMenu  # noqa: E402
from src.ui_history import HistoryScreen, ReceptionHistoryScreen  # noqa: E402
from src.ui_settings import _normaliser_mac  # noqa: E402
from src.ui_setup import SetupWizard  # noqa: E402


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
erreurs_tcl, erreurs_py = [], []
app.report_callback_exception = lambda et, ev, tb: erreurs_py.append(f"{et.__name__}: {ev}")
app.tk.createcommand("py_bgerr", lambda msg: erreurs_tcl.append(msg))
app.tk.eval("proc bgerror {msg} {py_bgerr $msg}")


def pump(ms):
    fin = time.time() + ms / 1000
    while time.time() < fin:
        app.update()
        time.sleep(0.005)


def boutons(w):
    out = [w] if ui_common.est_bouton(w) else []
    for e in w.winfo_children():
        out += boutons(e)
    return out


def bouton(w, texte):
    return next((b for b in boutons(w) if str(b.cget("text")).strip() == texte), None)


def visible(w):
    if w is None or not w.winfo_ismapped() or w.winfo_width() < 10 or w.winfo_height() < 10:
        return False
    x, y = w.winfo_rootx(), w.winfo_rooty()
    x2, y2 = x + w.winfo_width(), y + w.winfo_height()
    p = w.master
    while p is not None:
        px, py = p.winfo_rootx(), p.winfo_rooty()
        if (x < px - 2 or y < py - 2 or x2 > px + p.winfo_width() + 2
                or y2 > py + p.winfo_height() + 2):
            return False
        p = p.master
    return True


def ecran(cls):
    return next((e for e in app.winfo_children() if isinstance(e, cls)), None)


def dessus():
    app.update()
    w = app.winfo_containing(app.winfo_rootx() + 400, app.winfo_rooty() + 300)
    while w is not None and w.master is not app:
        w = w.master
    return w


pump(300)

# 1. bouton avec une couleur nommee (plantait l'alerte en style arrondi) -----
style = config.STYLE
config.STYLE = "rounded"
b = ui_common.Button(app, text="OK", bg="white", fg="red")
b.destroy()
app.show_menu(); pump(100)
app._show_alarm("Frigo : 9.5°C")
pump(100)
assert bouton(app._alarme, "OK") is not None, "alerte sans bouton OK"
bouton(app._alarme, "OK").invoke(); pump(50)
config.STYLE = style
app.show_menu(); pump(100)
print("1. couleurs nommees et alerte en style arrondi : OK")

# 2. une saisie manuelle n'est pas ecrasee par un capteur ---------------------
database.add_device("Frigo viande", 0, 4)
dev = database.list_devices()[0]
aujourd_hui = date.today()
database.save_reading(dev["id"], aujourd_hui, 3.8)
assert database.save_sensor_reading(dev["id"], aujourd_hui, 5.2) is False
assert database.get_reading(dev["id"], aujourd_hui)["temperature"] == 3.8
autre = date(2020, 1, 1)
assert database.save_sensor_reading(dev["id"], autre, 5.2) is True
print("2. saisie manuelle conservee, valeur capteur enregistree sinon : OK")

# 3. archivage : l'historique reste -------------------------------------------
database.archive_device(dev["id"])
assert not database.list_devices()
assert database.get_reading(dev["id"], aujourd_hui) is not None
assert database.devices_for_period(aujourd_hui, aujourd_hui)
database.add_device("Frigo viande", 0, 4)
assert [d["id"] for d in database.list_devices()] == [dev["id"]]
database.add_supplier("Bigard")
sup = database.list_suppliers()[0]
database.set_supplier_temp_max(sup["id"], 4)
database.save_reception(sup["id"], 6.5)
rec = database.receptions_on(aujourd_hui)[0]
assert database.reception_hors_seuil(rec)
database.archive_supplier(sup["id"])
assert not database.list_suppliers() and database.receptions_on(aujourd_hui)
database.add_supplier("Bigard")
print("3. appareil et fournisseur retires sans perdre l'historique ; seuil : OK")

# 4. reglages a distance ------------------------------------------------------
avant = config.COLOR_PRIMARY
remote_lock.apply_config({"COLOR_PRIMARY": "#e11d48"})
remote_lock.apply_config({})
assert config.COLOR_PRIMARY == avant, "un reglage retire n'est pas annule"
remote_lock._fetch = lambda: {"locked": False, "message": "", "config": {}, "update": "auto"}
remote_lock.refresh()
ecritures = []
orig = database.set_meta
database.set_meta = lambda k, v: (ecritures.append(k), orig(k, v))
for _ in range(5):
    remote_lock.refresh()
database.set_meta = orig
assert not ecritures, f"ecritures inutiles : {ecritures}"
print("4. reglage retire annule, aucune ecriture quand rien ne change : OK")

# 5. listes longues : les boutons restent accessibles -------------------------
for i in range(11):
    database.add_device(f"Appareil {i}", 0, 4)
    database.add_supplier(f"Fournisseur {i}")
    database.add_sensor(f"aa:bb:cc:dd:ee:{i:02x}", f"Capteur {i}", "ble")
app.show_settings(); pump(150)
s = app.current
for t in ("+ Ajouter", "📡 Capteurs temp.", "📷 Test camera"):
    assert visible(bouton(s, t)), f"Parametres : '{t}' inaccessible"
assert bouton(s, "Quitter l'appli") is None, "Quitter ne doit plus etre un bouton"
s._ble_config(); pump(150)
top = ui_common.modales_ouvertes()[-1]
for t in ("🔍 Tester", "📡 Ajouter BLE", "🌐 Ajouter WiFi"):
    assert visible(bouton(top, t)), f"Capteurs : '{t}' inaccessible"
ui_common.close_modal(top)
s._back(); pump(100)

vus = {}


def inspecter():
    p = ui_common.modales_ouvertes()[-1]
    vus["ok"] = visible(bouton(p, "+ Ajouter")) and visible(bouton(p, "🌡 Pistolet BLE"))
    ui_common.close_modal(p)


app.show_reception(); pump(1200)
app.after(300, inspecter)
app.current._manage_suppliers(); pump(80)
assert vus["ok"], "gestion des fournisseurs : boutons inaccessibles"
app.current._back(); pump(100)

app.show_history(); pump(100)
ecran(HistoryScreen)._show_receptions(); pump(150)
rh = ecran(ReceptionHistoryScreen)
rh._add(); pump(120)
p = ui_common.modales_ouvertes()[-1]
assert visible(bouton(p, "Annuler")), "rattrapage : Annuler inaccessible"
ui_common.close_modal(p); rh._back(); pump(80)
ecran(HistoryScreen)._back(); pump(80)

wiz = SetupWizard(app, lambda: None)
app.current.pack_forget()
pump(120)
assert visible(bouton(wiz, "Terminer")), "assistant : Terminer inaccessible"
wiz.destroy(); app.show_menu(); pump(80)
print("5. avec 12 appareils / fournisseurs / capteurs, tout reste accessible : OK")

# 6. le verrouillage reste devant apres un retour automatique -----------------
app.show_settings(); pump(120)
app._show_lock_overlay("Suspendu"); pump(80)
app.current._back(); pump(150)
assert dessus() is app._lock_overlay, "le menu passe devant le verrouillage"
app._hide_lock_overlay(); pump(50)
print("6. verrouillage toujours au premier plan : OK")

# 7. la nuit, un ecran laisse ouvert revient au menu --------------------------
app.show_reception(); pump(1200)
arrets = FakeConn.arretes
h = datetime.now().hour
config.NUIT_HEURES = (h, (h + 1) % 24)
app.seconds_idle = lambda: 10_000
app._nuit_tick(); pump(600)
assert isinstance(app.current, MainMenu), "pas de retour au menu la nuit"
assert FakeConn.arretes > arrets, "le Bluetooth du pistolet n'a pas ete libere"
del app.seconds_idle                     # retour a la vraie mesure
config.NUIT_HEURES = (22, 5)
print("7. retour au menu la nuit, Bluetooth libere : OK")

# 8. alertes de temperature : trop froid aussi, et affichees sans attendre ----
d = database.list_devices()[0]
database.add_sensor("11:22:33:44:55:66", "Sonde", "ble")
sonde = [x for x in database.list_ble_sensors() if x["mac"] == "11:22:33:44:55:66"][0]
database.update_ble_sensor(sonde["id"], sonde["label"], d["id"])
sensor_reader.read_all = lambda sensors, cancel=None: ({"11:22:33:44:55:66": -3.0}, None)
app._releve_auto()
assert "trop froid" in (database.get_meta("ble_temp_alert") or ""), "pas d'alerte trop froid"
app.show_reception(); pump(1200)
app._check_ble_alert(); pump(80)
assert app._alarme is not None and app._alarme.winfo_exists(), "alerte non affichee"
bouton(app._alarme, "OK").invoke(); app.current._back(); pump(100)
sensor_reader.read_all = lambda sensors, cancel=None: ({}, None)
app._releve_en_cours = True
assert not app._update_ready(), "une mise a jour pourrait couper le releve"
app._releve_en_cours = False
print("8. alerte trop froid, affichee hors du menu ; pas de mise a jour pendant un releve : OK")

# 9. clavier : accents, apostrophe, « : », Maj visible ------------------------
resultat = {}


def taper():
    p = ui_common.modales_ouvertes()[-1]
    for t in ("é", "'", ":"):
        assert bouton(p, t) is not None, f"touche {t} absente"
    bouton(p, "Maj ⇧").invoke()
    assert bouton(p, "É") is not None, "Maj ne change pas les touches"
    bouton(p, "É").invoke()
    bouton(p, "Maj ⇧").invoke()
    bouton(p, "t").invoke()
    bouton(p, "'").invoke()
    assert visible(bouton(p, "OK")), "OK du clavier inaccessible"
    bouton(p, "OK").invoke()


app.after(200, taper)
resultat["v"] = ui_common.text_popup(app, "Nom")
assert resultat["v"] == "Ét'", resultat["v"]
assert _normaliser_mac("AA-BB-CC-DD-EE-FF") == "aa:bb:cc:dd:ee:ff"
assert _normaliser_mac("aabbccddeeff") == "aa:bb:cc:dd:ee:ff"
print("9. clavier (accents, apostrophe, :, Maj) et adresses MAC : OK")

# 10. detection de la cle USB sans y ecrire -----------------------------------
racine = sandbox / "media"
cle, dossier_sd = racine / "user" / "CLE", racine / "user" / "pas_une_cle"
cle.mkdir(parents=True)
dossier_sd.mkdir()
vrai_path, vrai_ismount = usb_manager.Path, os.path.ismount
usb_manager.Path = lambda chemin: racine if chemin == "/media" else vrai_path(chemin)
os.path.ismount = lambda chemin: str(chemin) == str(cle)
avant = sorted(p.name for p in cle.iterdir())
trouve = usb_manager.find_usb_mount()
os.path.ismount = vrai_ismount
usb_manager.Path = vrai_path
assert trouve == cle, f"cle non trouvee : {trouve}"
assert sorted(p.name for p in cle.iterdir()) == avant, "la detection a ecrit sur la cle"
print("10. cle USB detectee sans ecriture, dossier ordinaire ignore : OK")

# 11. navigation : ni erreurs systeme ni fuite ---------------------------------
from logging.handlers import RotatingFileHandler  # noqa: E402
assert isinstance(remote_lock.logger.handlers[0], RotatingFileHandler)
app.show_menu(); pump(100)
commandes = len(app.tk.call("info", "commands"))
erreurs_tcl.clear()
for _ in range(3):
    for ouvrir in (app.show_reception, app.show_temperature, app.show_settings,
                   app.show_history, app.show_scan):
        ouvrir(); pump(300)
        app.show_menu(); pump(80)
assert not erreurs_tcl, f"erreurs systeme : {erreurs_tcl[:2]}"
assert len(app.tk.call("info", "commands")) - commandes < 10, "fuite de commandes Tk"
print("11. navigation sans erreur systeme ni fuite ; journaux plafonnes : OK")

# 12. Quitter : reserve a un appui long ----------------------------------------
app.show_settings(); pump(100)
s = app.current
s._debut_appui_long(); pump(200); s._fin_appui_long(); pump(100)
assert not ui_common.modales_ouvertes(), "un appui bref a propose de quitter"
fermer = {}


def repondre():
    p = ui_common.modales_ouvertes()[-1]
    fermer["vu"] = bouton(p, "Confirmer") is not None
    bouton(p, "Annuler").invoke()


app.after(3300, repondre)
s._debut_appui_long(); pump(3600)
assert fermer.get("vu"), "l'appui long ne propose pas de quitter"
s._back(); pump(80)
print("12. Quitter : seulement par appui long de 3 s : OK")

# 13. fenetres de saisie : OK / Annuler toujours visibles, quelle que soit la
#     police (sur PC, la police du Pi est remplacee par une plus grande)
vus = {}


def controler(nom, textes):
    def f():
        p = ui_common.modales_ouvertes()[-1]
        pump(50)
        vus[nom] = all(visible(bouton(p, t)) for t in textes)
        ui_common.close_modal(p)
    app.after(300, f)


controler("pave, titre sur deux lignes", ("OK", "Annuler"))
ui_common.numpad_popup(app, "Bigard : temp. max acceptée (°C)\n(vide = pas de contrôle)")
controler("pave", ("OK", "Annuler"))
ui_common.numpad_popup(app, "Température (°C)")
controler("clavier", ("OK", "Annuler"))
ui_common.text_popup(app, "Nom")
controler("confirmation", ("Annuler", "Confirmer"))
ui_common.confirm(app, "Retirer", "Retirer 'Frigo viande' ?\nSes relevés restent "
                  "dans l'historique et les exports PDF.")
caches = [nom for nom, ok in vus.items() if not ok]
assert not caches, f"boutons caches : {caches}"
print("13. fenetres de saisie : OK et Annuler toujours visibles : OK")

assert not erreurs_py, f"erreurs pendant le test : {erreurs_py[:3]}"
app.destroy()
cleanup(sandbox)
print("\nTOUS LES TESTS OK")
