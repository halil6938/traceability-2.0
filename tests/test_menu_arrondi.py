"""Menu principal : style arrondi (effet d'enfoncement, validation au
relachement), icone WiFi, et protection contre les doubles touches qui
faisaient parfois ouvrir le mauvais menu."""
import time
import tkinter as tk

from _harness import setup, cleanup  # noqa: E402
sandbox = setup("arrondi_")

from src import config, database, network, remote_lock, ui_common, ui_rounded  # noqa: E402
from src.ui_main import MainMenu  # noqa: E402

database.init_db()
config.SCREEN_W, config.SCREEN_H = 800, 480
appels = []


class AppStub:
    def show_reception(self): appels.append("reception")
    def show_scan(self): appels.append("scan")
    def show_temperature(self): appels.append("temperature")
    def show_history(self): appels.append("historique")
    def show_settings(self): appels.append("parametres")


def touches(w):
    trouves = [w] if isinstance(w, ui_rounded._Touche) else []
    for e in w.winfo_children():
        trouves += touches(e)
    return trouves


root = tk.Tk()
root.geometry("800x480")


def evt(widget, seq, x=40, y=40):
    widget.event_generate(seq, x=x, y=y)
    root.update()


def attendre_reseau(menu, attendu):
    for _ in range(100):
        root.update()
        if menu.wifi.online == attendu:
            return True
        time.sleep(0.02)
    return False


# 1. style classique inchange, mais avec l'icone WiFi
network.is_online = lambda: True
config.STYLE = "classic"
m = MainMenu(root, AppStub())
root.update()
assert not touches(m)
assert attendre_reseau(m, True)
print("1. style classique inchange, icone WiFi presente : OK")
m.destroy()

# 2. style arrondi : 3 cases + 2 boutons, memes couleurs que le classique
config.STYLE = "rounded"
m = MainMenu(root, AppStub())
root.update()
cases = touches(m)
assert len(cases) == 5, len(cases)
assert all(hasattr(m, a) for a in ("usb_lbl", "clock_lbl", "alert", "wifi"))
print("2. style arrondi : 3 cases + 2 boutons : OK")

case = cases[0]
ui_common._guard_until = 0.0            # pas de protection active pour ces essais

# 3. appui : la face descend, le contenu la suit, rien n'est declenche
y_avant = case.coords(case._face)[1]
texte = [i for i in case.find_all() if case.type(i) == "text"][0]
ty_avant = case.coords(texte)[1]
evt(case, "<ButtonPress-1>")
assert case.coords(texte)[1] == ty_avant + ui_rounded.ENFONCEMENT, "le contenu ne suit pas"
assert case.itemcget(case._face, "image") == str(case._face_appuyee)
assert not appels
print("3. appui : la case s'enfonce, contenu inclus, rien declenche : OK")

# 4. relachement sur la case : action + retour a la position de repos
evt(case, "<ButtonRelease-1>")
assert appels == ["reception"], appels
assert case.coords(texte)[1] == ty_avant and case.coords(case._face)[1] == y_avant
print("4. relachement : action declenchee, la case remonte : OK")

# 5. relachement hors de la case : annule, mais la case remonte quand meme
evt(case, "<ButtonPress-1>")
evt(case, "<ButtonRelease-1>", 900, 900)
assert appels == ["reception"] and case.coords(texte)[1] == ty_avant
print("5. relachement hors de la case : annule : OK")

# 6. les 5 elements declenchent chacun leur action
appels.clear()
for e in cases:
    evt(e, "<ButtonPress-1>", 40, 30)
    evt(e, "<ButtonRelease-1>", 40, 30)
assert sorted(appels) == sorted(
    ["reception", "scan", "temperature", "historique", "parametres"]), appels
print("6. les 5 elements declenchent chacun leur action : OK")

# 6b. zone morte : un appui sur le pourtour d'une case est ignore
appels.clear()
case = cases[1]
ty0 = case.coords([i for i in case.find_all() if case.type(i) == "text"][0])[1]
for x, y in ((3, 100), (case._width - 3, 100), (100, 3), (100, case._height - 3),
             (ui_rounded.ZONE_MORTE - 1, 100)):
    evt(case, "<ButtonPress-1>", x, y)
    assert case.coords([i for i in case.find_all() if case.type(i) == "text"][0])[1] == ty0,         f"la case s'enfonce pour un appui sur le pourtour ({x},{y})"
    evt(case, "<ButtonRelease-1>", x, y)
assert appels == [], f"un appui sur le pourtour a declenche : {appels}"
# juste a l'interieur de la zone active : pris en compte
evt(case, "<ButtonPress-1>", ui_rounded.ZONE_MORTE, ui_rounded.ZONE_MORTE)
evt(case, "<ButtonRelease-1>", ui_rounded.ZONE_MORTE, ui_rounded.ZONE_MORTE)
assert appels == ["scan"], appels
print("6b. appui sur le pourtour ignore, juste a l'interieur pris en compte : OK")

# 6c. espacement : les cases sont bien separees de 28 px (>= 5 mm sur l'ecran)
root.update()
x_cases = sorted((c.winfo_x(), c.winfo_x() + c.winfo_width()) for c in cases[:3])
ecarts = [x_cases[i + 1][0] - x_cases[i][1] for i in range(2)]
assert ecarts == [28, 28], ecarts
print(f"6c. espace entre les cases : {ecarts[0]} px : OK")

# 7. icone WiFi : verte connecte, rouge barree deconnecte
assert attendre_reseau(m, True)
verte = {m.wifi.itemcget(i, "outline") for i in m.wifi.find_all()
         if m.wifi.type(i) == "arc"}
assert verte == {config.COLOR_SUCCESS}, verte
barres = [i for i in m.wifi.find_all() if m.wifi.type(i) == "line"]
assert not barres
print("7. connecte : icone verte, sans barre : OK")

network.is_online = lambda: False
m._refresh_status()                       # relance un test de connexion
assert attendre_reseau(m, False)
rouge = {m.wifi.itemcget(i, "outline") for i in m.wifi.find_all()
         if m.wifi.type(i) == "arc"}
assert rouge == {config.COLOR_DANGER}, rouge
barres = [i for i in m.wifi.find_all() if m.wifi.type(i) == "line"]
assert len(barres) == 2 and m.wifi.itemcget(barres[-1], "fill") == config.COLOR_DANGER
print("8. deconnecte : icone rouge barree : OK")

# 9. protection contre les doubles touches : un appui juste apres l'arrivee
#    sur un ecran est ignore (bouton ordinaire ET case arrondie)
m.destroy()
ecran = tk.Frame(root)
ecran.pack()
clics = []
bouton = tk.Button(ecran, text="Retour", command=lambda: clics.append("bouton"))
bouton.pack()
case2 = ui_rounded.Bouton(ecran, 200, 60, "Test", lambda: clics.append("case"))
case2.pack()
root.update()
evt(bouton, "<Enter>", 10, 10)            # pointeur sur le bouton : il se declencherait
ui_common.install_tap_guard(ecran, seconds=0.3)
for w in (bouton, case2):
    evt(w, "<ButtonPress-1>", 40, 30)
    evt(w, "<ButtonRelease-1>", 40, 30)
assert clics == [], f"un toucher pendant la protection a declenche : {clics}"
print("9. touchers juste apres l'arrivee sur l'ecran : ignores : OK")

time.sleep(0.4)                           # la protection est terminee
for w in (bouton, case2):
    evt(w, "<ButtonPress-1>", 40, 30)
    evt(w, "<ButtonRelease-1>", 40, 30)
assert clics == ["bouton", "case"], clics
print("10. apres la protection : les touchers fonctionnent : OK")

# 11. un appui ignore ne declenche rien meme si le relachement arrive apres
clics.clear()
ui_common.install_tap_guard(ecran, seconds=0.2)
evt(case2, "<ButtonPress-1>", 40, 30)     # ignore
time.sleep(0.3)
evt(case2, "<ButtonRelease-1>", 40, 30)   # la protection est finie
assert clics == [], "un relachement isole a declenche l'action"
print("11. relachement seul apres un appui ignore : rien : OK")

# 12. le style est reglable a distance ; valeur invalide refusee
remote_lock.apply_config({"STYLE": "rounded"})
assert config.STYLE == "rounded"
remote_lock.apply_config({"STYLE": "n-importe-quoi"})
assert config.STYLE == "rounded"
print("12. STYLE reglable a distance, invalide refuse : OK")

# 13. tableau mensuel des temperatures : cases en boutons Tk ordinaires (il y en a
#     des centaines), le reste de l'ecran restant arrondi
from src.ui_common import est_bouton  # noqa: E402
from src.ui_history import TemperatureHistoryScreen  # noqa: E402
for nom, mn, mx in (("Frigo A", 0, 4), ("Frigo B", 0, 4)):
    database.add_device(nom, mn, mx)
config.STYLE = "rounded"
t = TemperatureHistoryScreen(root, lambda: None)
root.update()


def tous(w):
    out = [w]
    for e in w.winfo_children():
        out += tous(e)
    return out


cellules = [w for w in tous(t.table_frame) if est_bouton(w)]
assert len(cellules) >= 28 * 2, len(cellules)
assert all(isinstance(c, tk.Button) for c in cellules), "une case du tableau est arrondie"
entete = [w for w in tous(t) if getattr(w, "_bouton", False)]
assert entete, "les boutons du haut de l'ecran doivent rester arrondis"
print(f"13. tableau mensuel : {len(cellules)} cases en boutons ordinaires, "
      f"{len(entete)} boutons du haut arrondis : OK")
t.destroy()

root.destroy()
cleanup(sandbox)
print("\nTOUS LES TESTS OK")
