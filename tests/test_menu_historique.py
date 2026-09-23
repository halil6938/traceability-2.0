"""Menu Historique : en style arrondi, trois lignes pleine largeur sur fond
sombre (pour ne plus le confondre avec le menu principal), avec les intitulés
de l'appli ; l'ancien style reste intact."""
import tkinter as tk

from _harness import setup, cleanup  # noqa: E402
sandbox = setup("histmenu_")

from src import config, database, ui_common, ui_history, ui_rounded  # noqa: E402

database.init_db()
config.SCREEN_W, config.SCREEN_H = 800, 480
root = tk.Tk()
root.geometry("800x480")


def lignes(w):
    trouve = [w] if isinstance(w, ui_rounded.Ligne) else []
    for e in w.winfo_children():
        trouve += lignes(e)
    return trouve


def textes(c):
    return [c.itemcget(i, "text") for i in c.find_all() if c.type(i) == "text"]


# 1. ancien style intact : pas de lignes, meme fond que le reste
config.STYLE = "classic"
h = ui_history.HistoryScreen(root, lambda: None)
root.update()
assert not lignes(h) and h.cget("bg") == config.COLOR_BG
print("1. style classique inchange : OK")
h.destroy()

# 2. style arrondi : 3 lignes, fond sombre, intitules de l'appli, couleurs de l'appli
config.STYLE = "rounded"
h = ui_history.HistoryScreen(root, lambda: None)
root.update()
ls = lignes(h)
assert len(ls) == 3 and h.cget("bg") == ui_rounded.HIST_FOND
attendu = [("01", "Tickets", "Consulter les photos de tickets"),
           ("02", "Temperatures", "Tableau mensuel des releves"),
           ("03", "Réceptions", "Relevés des produits livrés")]
for c, (num, titre, sous) in zip(ls, attendu):
    t = textes(c)
    assert num in t and titre in t and sous in t, (t, titre)
assert [c.winfo_width() for c in ls] == [config.SCREEN_W - 48] * 3
print("2. 3 lignes pleine largeur, fond sombre, intitules de l'appli : OK")

# 3. les lignes ne se chevauchent pas et tiennent sous l'en-tete
ys = [(c.winfo_y(), c.winfo_y() + c.winfo_height()) for c in ls]
assert all(ys[i][1] < ys[i + 1][0] for i in range(2)), ys
assert ys[-1][1] < config.SCREEN_H, ys
print(f"3. tiennent dans l'ecran, espace entre lignes : {ys[1][0] - ys[0][1]} px : OK")

h.destroy()

# 4. un appui ouvre la bonne rubrique (Temperatures puis Receptions)
ui_common._guard_until = 0.0
for i, classe in ((1, ui_history.TemperatureHistoryScreen), (2, ui_history.ReceptionHistoryScreen)):
    h = ui_history.HistoryScreen(root, lambda: None)
    root.update()
    c = lignes(h)[i]
    c.event_generate("<ButtonPress-1>", x=200, y=40)
    root.update()
    assert c.itemcget(c._face, "image") == str(c._face_appuyee)
    c.event_generate("<ButtonRelease-1>", x=200, y=40)
    root.update()
    ouverts = [w for w in root.winfo_children() if isinstance(w, classe)]
    assert ouverts, f"la ligne {i + 1} n'ouvre pas {classe.__name__}"
    for w in ouverts:
        w.destroy()
    h.destroy()
print("4. un appui ouvre la bonne rubrique, avec l'effet d'enfoncement : OK")

# 5. un appui sur le pourtour de la ligne est ignore (pas de mauvaise rubrique)
h = ui_history.HistoryScreen(root, lambda: None)
root.update()
c = lignes(h)[0]
c.event_generate("<ButtonPress-1>", x=3, y=50)
c.event_generate("<ButtonRelease-1>", x=3, y=50)
root.update()
assert not [w for w in root.winfo_children()
            if isinstance(w, (ui_history.PhotoHistoryScreen,))]
assert h.winfo_exists()
print("5. appui sur le bord d'une ligne : ignore : OK")

root.destroy()
cleanup(sandbox)
print("\nTOUS LES TESTS OK")
