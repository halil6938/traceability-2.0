"""Rejoue la sequence qui figeait l'appli : Parametres > + Ajouter, puis
trois dialogues enchaines (nom, MIN, MAX), pilotes automatiquement."""
import tkinter as tk

from _harness import setup, cleanup  # noqa: E402

sandbox = setup("appareil_")
from src import config, database  # noqa: E402
from src import ui_common as uc  # noqa: E402

database.init_db()
root = tk.Tk()
root.geometry("800x480")
config.SCREEN_W, config.SCREEN_H = 800, 480
root.withdraw()

from src.ui_settings import SettingsScreen  # noqa: E402

scr = SettingsScreen(root, lambda: None)
root.update()
print("appareils au depart :", len(database.list_devices()))


def find_button(widget, label):
    if isinstance(widget, tk.Button) and str(widget.cget("text")) == label:
        return widget
    for child in widget.winfo_children():
        found = find_button(child, label)
        if found is not None:
            return found
    return None


# Script : un dialogue apres l'autre (nom -> MIN -> MAX)
script = [["A", "OK"], ["5", "OK"], ["9", "OK"]]
state = {"i": 0, "vus": []}


def driver():
    if uc._OPEN_MODALS and state["i"] < len(script):
        panel = uc._OPEN_MODALS[-1]
        state["vus"].append(state["i"] + 1)
        for label in script[state["i"]]:
            btn = find_button(panel, label)
            assert btn is not None, f"bouton '{label}' introuvable (dialogue {state['i'] + 1})"
            btn.invoke()
        state["i"] += 1
    root.after(50, driver)


watchdog = {"expire": False}


def timeout():
    watchdog["expire"] = True
    root.destroy()


root.after(50, driver)
tid = root.after(20000, timeout)          # filet : 20 s max

scr._safe(scr._add)                        # <- l'action qui figeait l'appli

root.after_cancel(tid)
print("dialogues traites  :", state["vus"], "(attendu [1, 2, 3])")
assert not watchdog["expire"], "BLOCAGE : la sequence ne s'est jamais terminee"
assert state["i"] == 3, f"seulement {state['i']} dialogue(s) sur 3"

devs = database.list_devices()
print("appareils apres    :", len(devs))
for d in devs:
    print("   ->", d["name"], d["temp_min"], "/", d["temp_max"])
assert len(devs) == 1 and devs[0]["temp_min"] == 5 and devs[0]["temp_max"] == 9

root.update()
print("panneaux restants  :", len(uc._OPEN_MODALS), "(doit etre 0)")
assert not uc._OPEN_MODALS, "un panneau est reste ouvert"

root.destroy()
cleanup(sandbox)
print("\nTOUS LES TESTS OK")
