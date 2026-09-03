"""Verifie la veille de l'ecran, et surtout que le contact qui reveille
l'appareil n'atteint PAS le bouton situe dessous (le probleme terrain :
l'operateur touchait l'ecran eteint et atterrissait dans un menu au hasard)."""
import time
import tkinter as tk

from _harness import setup, cleanup  # noqa: E402

sandbox = setup("veille_")
from src import config, database  # noqa: E402

database.init_db()
database.add_device("Frigo", 0, 4)
database.set_meta("setup_done", "1")
config.REMOTE_CONTROL_BASE = ""          # pas de reseau pendant le test

from src import ui_main  # noqa: E402

app = ui_main.App()
app.geometry("800x480+0+0")
app.attributes("-fullscreen", False)
app.update()
config.SCREEN_W, config.SCREEN_H = 800, 480
print("ecran de veille au depart :", app._sleep_overlay)

# --- reperer un bouton du menu (la ou le doigt se poserait) ---
menu = app.current
cards = [w for w in menu.winfo_children() if isinstance(w, tk.Frame)]
target = None
for frame in cards:
    for card in frame.winfo_children():
        if card.winfo_width() > 100:
            target = card
            break
    if target:
        break
assert target is not None, "aucune carte de menu trouvee"
x = target.winfo_rootx() + target.winfo_width() // 2
y = target.winfo_rooty() + target.winfo_height() // 2
avant = app.winfo_containing(x, y)
print("widget sous le doigt, ecran allume :", avant.winfo_class(),
      "(une carte du menu)")

# --- mise en veille ---
config.SCREEN_OFF_S = 1
app._last_touch = time.time() - 5
app._sleep_tick()
app.update()
assert app._sleep_overlay is not None, "l'ecran ne s'est pas mis en veille"
print("mise en veille                     : OK")

pendant = app.winfo_containing(x, y)
print("widget sous le doigt, ecran eteint  :", pendant.winfo_class(),
      "->", "le voile" if pendant is app._sleep_overlay else "PROBLEME")
assert pendant is app._sleep_overlay, \
    "le contact atteindrait le bouton : l'operateur changerait de menu !"

# --- reveil ---
res = app._wake()
app.update()
print("reveil renvoie                     :", repr(res), "(bloque l'evenement)")
assert res == "break", "l'evenement de reveil doit etre absorbe"
assert app._sleep_overlay is None, "le voile n'a pas ete retire"
apres = app.winfo_containing(x, y)
print("widget sous le doigt, apres reveil  :", apres.winfo_class(),
      "(le menu est de nouveau actif)")
assert apres is not None

# --- l'activite repousse la veille ---
config.SCREEN_OFF_S = 600
app._note_activity()
app._sleep_tick()
app.update()
assert app._sleep_overlay is None, "veille declenchee malgre l'activite"
print("activite recente -> pas de veille   : OK")

# --- veille desactivable ---
config.SCREEN_OFF_S = 0
app._last_touch = time.time() - 99999
app._sleep_tick()
app.update()
assert app._sleep_overlay is None, "veille declenchee alors qu'elle est desactivee"
print("SCREEN_OFF_S = 0 -> jamais de veille: OK")

app.destroy()
cleanup(sandbox)
print("\nTOUS LES TESTS OK")
