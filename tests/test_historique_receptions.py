"""Rejoue le rattrapage d'une reception oubliee dans l'historique :
+ Ajouter -> fournisseur -> jour -> temperature, puis modification et
suppression de la ligne creee."""
import tkinter as tk
from datetime import date, datetime

from _harness import setup, cleanup  # noqa: E402

sandbox = setup("recept_")
from src import config, database  # noqa: E402
from src import ui_common as uc  # noqa: E402

database.init_db()
database.add_supplier("Bigard")

root = tk.Tk()
root.geometry("800x480")
config.SCREEN_W, config.SCREEN_H = 800, 480
root.withdraw()

from src.ui_history import ReceptionHistoryScreen  # noqa: E402

scr = ReceptionHistoryScreen(root, lambda: None)
root.update()


def find_button(widget, label):
    if isinstance(widget, tk.Button) and str(widget.cget("text")) == label:
        return widget
    for child in widget.winfo_children():
        found = find_button(child, label)
        if found is not None:
            return found
    return None


# Pilote le pave numerique (il bloque l'appel tant qu'il est ouvert)
def driver():
    for panel in list(uc._OPEN_MODALS):
        if find_button(panel, "OK") is not None:          # pave numerique
            find_button(panel, "4").invoke()
            find_button(panel, ".").invoke()
            find_button(panel, "5").invoke()
            find_button(panel, "OK").invoke()
        elif find_button(panel, "Confirmer") is not None:  # confirmation
            find_button(panel, "Confirmer").invoke()
    root.after(50, driver)


root.after(50, driver)

print("receptions au depart :", len(database.receptions_in_range(
    date(scr.year, scr.month, 1), date(scr.year, scr.month, 28))))

# --- 1. + Ajouter -> fournisseur ---
assert find_button(scr, "+ Ajouter") is not None, "bouton « + Ajouter » absent"
scr._add()
root.update()
btn = find_button(root, "Bigard")
print("1. panneau fournisseur      :", "OK" if btn else "ABSENT")
assert btn is not None
btn.invoke()
root.update()

# --- 2. choix du jour (le 3 du mois affiche) ---
btn_jour = find_button(root, "3")
print("2. grille des jours         :", "OK" if btn_jour else "ABSENTE")
assert btn_jour is not None
btn_jour.invoke()          # ouvre le pave numerique, pilote par driver()
root.update()

# --- 3. la reception est enregistree a la date choisie ---
recs = database.receptions_in_range(date(scr.year, scr.month, 1),
                                    date(scr.year, scr.month, 28))
print("3. receptions apres ajout   :", len(recs))
assert len(recs) == 1, "la reception n'a pas ete enregistree"
r = recs[0]
dt = datetime.fromisoformat(r["created_at"])
print(f"   -> {r['supplier_name']} le {dt.strftime('%d/%m/%Y a %H:%M')} "
      f": {r['temperature']}°C")
assert dt.day == 3 and dt.hour == 9 and dt.minute == 0, "date/heure incorrecte"
assert r["temperature"] == 4.5, f"temperature incorrecte : {r['temperature']}"

# --- 4. jours a venir inaccessibles (mois en cours) ---
today = date.today()
if scr.year == today.year and scr.month == today.month and today.day < 28:
    futur = find_button(root, str(today.day + 1))
    scr._add()
    root.update()
    find_button(root, "Bigard").invoke()
    root.update()
    futur = find_button(root, str(today.day + 1))
    etat = str(futur.cget("state")) if futur else "?"
    print("4. jour a venir             :", etat, "(doit etre disabled)")
    assert etat == "disabled", "un jour futur est selectionnable"
    find_button(root, "Annuler").invoke()
    root.update()

# --- 5. modification puis suppression ---
scr._edit(r)               # pave numerique pilote : remet 4.5
root.update()
scr._delete(r)         # la confirmation est validee par driver()
root.update()
restant = database.receptions_in_range(date(scr.year, scr.month, 1),
                                       date(scr.year, scr.month, 28))
print("5. apres suppression        :", len(restant), "reception(s)")
assert not restant, "la suppression n'a pas fonctionne"

root.destroy()
cleanup(sandbox)
print("\nTOUS LES TESTS OK")
