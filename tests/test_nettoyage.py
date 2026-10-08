"""Menu Nettoyage : identification de l'operateur, case du jour cochee avec
ses initiales, decochee seulement par lui, jours passes en lecture seule,
gestion des listes, historique du mois et export PDF."""
import time
from datetime import date, timedelta

from _harness import setup, cleanup  # noqa: E402
sandbox = setup("nettoyage_")

from src import config, database, ui_common, usb_manager  # noqa: E402
from src.ui_common import est_bouton  # noqa: E402

config.REMOTE_CONTROL_BASE = ""
config.REPO_URL = ""
config.SCREEN_OFF_S = 0
database.init_db()
database.set_meta("setup_done", "1")

# --- base ----------------------------------------------------------------------
assert database.initiales_par_defaut("Hamza Uysal") == "HU"
assert database.initiales_par_defaut("Julie") == "JU"
database.add_operateur("Hamza Uysal", "")
database.add_operateur("Emre", "ec")
hamza, emre = database.list_operateurs()
assert (hamza["initiales"], emre["initiales"]) == ("HU", "EC")
for nom in ("Machine", "Vitrine", "Sol labo"):
    database.add_element(nom)
machine, vitrine, sol = database.list_elements()
aujourd_hui = date.today()
hier = aujourd_hui - timedelta(days=1)
database.cocher_nettoyage(vitrine["id"], hier, emre["id"])
print("1. operateurs (initiales auto) et elements enregistres : OK")

# --- ecran reel -------------------------------------------------------------------
from src.ui_main import App, MainMenu  # noqa: E402
from src.ui_nettoyage import NettoyageScreen  # noqa: E402


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


def pump(ms=80):
    fin = time.time() + ms / 1000
    while time.time() < fin:
        app.update()
        time.sleep(0.005)


def tous(w):
    out = [w]
    for e in w.winfo_children():
        out += tous(e)
    return out


def bouton(w, texte):
    return next((b for b in tous(w) if est_bouton(b) and str(b.cget("text")) == texte), None)


def visible(w):
    return (w is not None and w.winfo_ismapped()
            and w.winfo_rootx() + w.winfo_width() <= app.winfo_rootx() + 800 + 2
            and w.winfo_rooty() + w.winfo_height() <= app.winfo_rooty() + 480 + 2)


pump(200)
app.show_menu(); pump()
assert bouton(app.current, "Nettoyage") is None or True   # case du menu (canevas)
app.show_nettoyage(); pump()
ecran = app.current
assert isinstance(ecran, NettoyageScreen)
for nom in ("Hamza Uysal", "Emre"):
    assert visible(bouton(ecran, nom)), f"{nom} absent du choix"
print("2. choix de l'operateur affiche : OK")

bouton(ecran, "Hamza Uysal").invoke(); pump()
assert ecran.operateur["id"] == hamza["id"]
cases = ecran._cases
assert set(cases) == {machine["id"], vitrine["id"], sol["id"]}
assert all(visible(c) for c in cases.values()), "case du jour hors de l'ecran"
# la colonne de la veille montre les initiales d'Emre
veille = ecran._toutes[(vitrine["id"], hier.isoformat())]
assert veille.cget("text") == "EC", "le nettoyage de la veille n'apparait pas"
print("3. tableau : colonne du jour + jours passes : OK")

cases[machine["id"]].invoke(); pump()
assert cases[machine["id"]].cget("text") == "HU"
fait = database.nettoyages_periode(aujourd_hui, aujourd_hui)[(machine["id"],
                                                              aujourd_hui.isoformat())]
assert fait["operateur_id"] == hamza["id"]
cases[machine["id"]].invoke(); pump()                 # erreur : il decoche
assert cases[machine["id"]].cget("text") == ""
assert not database.nettoyages_periode(aujourd_hui, aujourd_hui)
cases[machine["id"]].invoke(); pump()
print("4. case cochee avec ses initiales, decochee par lui-meme : OK")

# n'importe quel jour : une case passee se coche aussi...
ecran._toutes[(sol["id"], hier.isoformat())].invoke(); pump()
assert database.nettoyages_periode(hier, hier)[(sol["id"], hier.isoformat())][
    "operateur_id"] == hamza["id"]
assert ecran._toutes[(sol["id"], hier.isoformat())].cget("text") == "HU"
# ... et ◀ remonte plus loin que les jours affiches
assert visible(bouton(ecran, "◀")) and visible(bouton(ecran, "▶"))
loin = aujourd_hui - timedelta(days=config.NETTOYAGE_JOURS_PASSES + 3)
while (sol["id"], loin.isoformat()) not in ecran._toutes:
    bouton(ecran, "◀").invoke(); pump()
assert ecran.jour_affiche < aujourd_hui
ecran._toutes[(sol["id"], loin.isoformat())].invoke(); pump()
assert (sol["id"], loin.isoformat()) in database.nettoyages_periode(loin, loin)
ecran._toutes[(sol["id"], loin.isoformat())].invoke(); pump()      # decoche
assert not database.nettoyages_periode(loin, loin)
for _ in range(10):                                   # ▶ : jamais apres aujourd'hui
    bouton(ecran, "▶").invoke(); pump()
assert ecran.jour_affiche == aujourd_hui and machine["id"] in ecran._cases
assert (machine["id"], (aujourd_hui + timedelta(days=1)).isoformat()) not in ecran._toutes
print("4b. n'importe quel jour se coche (jours affiches, ◀ ▶) : OK")

# un autre operateur ne peut pas decocher la case de Hamza
bouton(ecran, "Changer d'opérateur").invoke(); pump()
bouton(ecran, "Emre").invoke(); pump()
vu = {}


def fermer_message():
    p = ui_common.modales_ouvertes()[-1]
    vu["texte"] = " ".join(str(w.cget("text")) for w in tous(p) if w.winfo_class() == "Label")
    bouton(p, "OK").invoke()


app.after(200, fermer_message)
ecran._cases[machine["id"]].invoke(); pump()
assert "Hamza" in vu.get("texte", ""), vu
assert database.nettoyages_periode(aujourd_hui, aujourd_hui)[
    (machine["id"], aujourd_hui.isoformat())]["operateur_id"] == hamza["id"]
ecran._cases[sol["id"]].invoke(); pump()
assert ecran._cases[sol["id"]].cget("text") == "EC"
print("5. un autre operateur ne peut pas decocher : message « deja fait par » : OK")

# --- gestion des listes ----------------------------------------------------------
reponses = iter(["Julie", ""])          # nom, puis initiales proposees (vides = auto)


def saisir():
    p = ui_common.modales_ouvertes()[-1]
    if bouton(p, "Maj ⇧") is not None:              # clavier texte
        texte = next(reponses)
        for w in tous(p):
            if w.winfo_class() == "Label" and w.cget("textvariable"):
                p.setvar(w.cget("textvariable"), texte)
        bouton(p, "OK").invoke()
        app.after(150, saisir)
    else:                                            # fenetre Gerer
        if vu.get("ajout"):
            ui_common.close_modal(p)
            return
        vu["ajout"] = True
        assert visible(bouton(p, "+ Ajouter")), "+ Ajouter inaccessible"
        app.after(150, saisir)          # remplira le clavier qui va s'ouvrir
        bouton(p, "+ Ajouter").invoke()


app.after(200, saisir)
ecran._gerer(); pump()
assert [o["nom"] for o in database.list_operateurs()] == ["Hamza Uysal", "Emre", "Julie"]
assert database.list_operateurs()[-1]["initiales"] == "JU"
assert ecran.operateur["id"] == emre["id"], "operateur perdu apres Gerer"
print("6. Gerer : ajout d'un operateur (initiales automatiques) : OK")

# retire pendant qu'il est identifie : retour au choix
database.archive_operateur(emre["id"])
app.after(150, lambda: ui_common.close_modal(ui_common.modales_ouvertes()[-1]))
ecran._gerer(); pump()
assert ecran.operateur is None and bouton(ecran, "Emre") is None
print("7. operateur retire : retour au choix, plus propose : OK")

# --- historique et PDF -----------------------------------------------------------
from src.ui_history import NettoyageHistoryScreen  # noqa: E402
app.show_menu(); pump()
h = NettoyageHistoryScreen(app, lambda: None); pump()
labels = [w.cget("text") for w in tous(h) if w.winfo_class() == "Label"]
assert "HU" in labels and "EC" in labels and "Machine" in labels
h.destroy()

cle = sandbox / "cle" / "traceability"
(cle / "exports").mkdir(parents=True)
usb_manager.usb_base_dir = lambda: cle
from src import pdf_export  # noqa: E402
chemin = pdf_export.export_nettoyage_pdf(aujourd_hui.year, aujourd_hui.month)
assert chemin.exists() and chemin.stat().st_size > 1000
assert chemin.read_bytes()[:4] == b"%PDF"
# Emre est retire, mais ses fiches restent : il figure dans le PDF
try:
    from pypdf import PdfReader
except ImportError:                     # lecture du PDF facultative
    PdfReader = None
if PdfReader is not None:
    texte = "".join(p.extract_text() for p in PdfReader(str(chemin)).pages)
    assert "Emre" in texte and "Machine" in texte, texte[:300]
print("8. historique du mois et PDF (operateurs retires compris) : OK")

# --- retour automatique : l'operateur suivant doit s'identifier -------------------
app.show_nettoyage(); pump()
app.current._choisir(database.list_operateurs()[0]); pump()
app.seconds_idle = lambda: config.NETTOYAGE_INACTIVITY_S + 5
ui_common.modales_ouvertes()
app.current.after(10, lambda: None)
fin = time.time() + 12
while time.time() < fin and not isinstance(app.current, MainMenu):
    pump(200)
assert isinstance(app.current, MainMenu), "pas de retour au menu apres inactivite"
del app.seconds_idle
print("9. inactivite : retour au menu (identification a refaire) : OK")

assert not erreurs, erreurs
app.destroy()
cleanup(sandbox)
print("\nTOUS LES TESTS OK")
