"""Verifie le defilement au doigt (bind_drag_scroll) sur les 3 ecrans a
listes deroulantes : releve du jour, historique des temperatures, historique
des receptions.
- glisser sur une zone libre (Label) fait defiler ;
- glisser en partant d'un BOUTON ne fait PAS defiler, pour ne jamais gener
  un appui (Modifier/Suppr, cellule du tableau...) ;
- ca fonctionne encore apres une reconstruction de la liste (changement de
  mois), qui recree tous les widgets."""
import tkinter as tk
from datetime import date, timedelta

from _harness import setup, cleanup  # noqa: E402
sandbox = setup("glisse_")

from src import config, database  # noqa: E402

database.init_db()
config.SCREEN_W, config.SCREEN_H = 800, 480

root = tk.Tk()
root.geometry("800x480")
root.withdraw()


def glisser_doigt(widget, dy):
    """Simule un glissement tactile en deux temps, comme un vrai doigt."""
    x = widget.winfo_rootx() + 10
    y = widget.winfo_rooty() + 10
    widget.event_generate("<ButtonPress-1>", x=10, y=10, rootx=x, rooty=y)
    root.update()
    widget.event_generate("<B1-Motion>", x=10, y=10 + dy, rootx=x, rooty=y + dy)
    root.update()


# --- de quoi remplir largement l'ecran, pour que le defilement soit possible ---
for i in range(20):
    database.add_device(f"Frigo {i:02d}", 0, 4)
database.add_supplier("Bigard")
fournisseur = database.list_suppliers()[0]["id"]
today = date.today()
for i in range(25):
    database.save_reception(fournisseur, 4.0 + i * 0.1,
                            today - timedelta(days=i % 27))

# =====================================================================
print("=== 1. Releve du jour (TemperatureScreen) ===")
from src.ui_temperature import TemperatureScreen  # noqa: E402

scr = TemperatureScreen(root, lambda: None)
root.update()

# une Label du tableau : element non-bouton, tire de rows_frame
labels = [w for w in scr.rows_frame.winfo_children()
         if isinstance(w, tk.Frame)]
assert labels, "aucune ligne construite"
premiere_ligne = labels[0]
une_label = next(w for w in premiere_ligne.winfo_children()
                 if isinstance(w, tk.Label))
un_bouton = next(w for w in premiere_ligne.winfo_children()
                 if isinstance(w, tk.Button))

avant = scr.canvas.yview()[0]
glisser_doigt(une_label, -400)   # glisse vers le haut : fait defiler vers le bas
apres = scr.canvas.yview()[0]
print(f"1a. glissement sur une Label : {avant:.3f} -> {apres:.3f}")
assert apres > avant, "le glissement sur une zone libre ne fait pas defiler"

avant2 = scr.canvas.yview()[0]
glisser_doigt(un_bouton, -400)
apres2 = scr.canvas.yview()[0]
print(f"1b. glissement sur un Bouton : {avant2:.3f} -> {apres2:.3f} "
      "(doit rester identique)")
assert apres2 == avant2, "un glissement demarre sur un bouton fait defiler"

# =====================================================================
print("\n=== 2. Historique des temperatures (tableau, cellules = boutons) ===")
from src.ui_history import TemperatureHistoryScreen  # noqa: E402

scr.destroy()
scr2 = TemperatureHistoryScreen(root, lambda: None)
root.update()

# la seule zone "libre" du tableau : le numero du jour (Label), 1ere colonne
premiere_row = [w for w in scr2.table_frame.winfo_children()
                if isinstance(w, tk.Frame)][1]  # [0] = ligne d'en-tete
jour_lbl = premiere_row.winfo_children()[0]
assert isinstance(jour_lbl, tk.Label), "1ere case attendue : le numero du jour"
cellule_bouton = next(w for w in premiere_row.winfo_children()
                      if isinstance(w, tk.Button))

avant3 = scr2.canvas.yview()[0]
glisser_doigt(jour_lbl, -300)
apres3 = scr2.canvas.yview()[0]
print(f"2a. glissement sur le n° du jour : {avant3:.3f} -> {apres3:.3f}")
assert apres3 > avant3, "le glissement sur le numero du jour ne defile pas"

avant4 = scr2.canvas.yview()[0]
glisser_doigt(cellule_bouton, -300)
apres4 = scr2.canvas.yview()[0]
print(f"2b. glissement sur une cellule   : {avant4:.3f} -> {apres4:.3f} "
      "(doit rester identique)")
assert apres4 == avant4, "un glissement sur une cellule fait defiler"

# changement de mois : la liste est entierement reconstruite, le glissement
# doit rester actif sur les NOUVEAUX widgets
scr2._prev_month()
root.update()
nouvelle_row = [w for w in scr2.table_frame.winfo_children()
               if isinstance(w, tk.Frame)][1]
nouveau_jour_lbl = nouvelle_row.winfo_children()[0]
avant5 = scr2.canvas.yview()[0]
glisser_doigt(nouveau_jour_lbl, -300)
apres5 = scr2.canvas.yview()[0]
print(f"2c. apres changement de mois     : {avant5:.3f} -> {apres5:.3f}")
assert apres5 > avant5, "le glissement ne fonctionne plus apres reconstruction"

# =====================================================================
print("\n=== 3. Historique des receptions ===")
from src.ui_history import ReceptionHistoryScreen  # noqa: E402

scr2.destroy()
scr3 = ReceptionHistoryScreen(root, lambda: None)
root.update()

rows = [w for w in scr3.list_frame.winfo_children() if isinstance(w, tk.Frame)]
assert len(rows) >= 5, f"attendu plusieurs receptions, trouve {len(rows)}"
label_fournisseur = next(w for w in rows[0].winfo_children()
                         if isinstance(w, tk.Label))
bouton_suppr = next(w for w in rows[0].winfo_children()
                    if isinstance(w, tk.Button) and w.cget("text") == "Suppr")

avant6 = scr3.canvas.yview()[0]
glisser_doigt(label_fournisseur, -300)
apres6 = scr3.canvas.yview()[0]
print(f"3a. glissement sur le fournisseur : {avant6:.3f} -> {apres6:.3f}")
assert apres6 > avant6, "le glissement sur une ligne ne defile pas"

avant7 = scr3.canvas.yview()[0]
glisser_doigt(bouton_suppr, -300)
apres7 = scr3.canvas.yview()[0]
print(f"3b. glissement sur « Suppr »      : {avant7:.3f} -> {apres7:.3f} "
      "(doit rester identique)")
assert apres7 == avant7, "un glissement demarre sur Suppr fait defiler"

root.destroy()
cleanup(sandbox)
print("\nTOUS LES TESTS OK")
