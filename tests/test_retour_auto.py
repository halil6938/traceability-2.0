"""Verifie ui_common.schedule_auto_return, le mecanisme de retour automatique
au menu utilise par Reception, Historique et Parametres apres une periode d'inactivite :
- se declenche quand le delai d'inactivite est depasse ;
- reste SUSPENDU tant qu'une fenetre superposee (numpad, confirmation) est
  ouverte, pour ne jamais detruire un ecran sous un panneau actif ;
- ne plante pas si l'ecran a deja ete detruit par ailleurs.

Les ecrans reels (ReceptionScreen, HistoryScreen et ses 3 sous-ecrans,
SettingsScreen) appellent tous ce meme helper, chacun avec son propre delai
configurable a distance ; la fin du fichier verifie l'ecran Reception reel."""
import time
import tkinter as tk

from _harness import setup, cleanup  # noqa: E402
sandbox = setup("retour_")

from src import ui_common as uc  # noqa: E402

root = tk.Tk()
root.geometry("800x480")
root.withdraw()

# App fournit normalement seconds_idle() (voir ui_main.App) ; on le simule
# ici pour piloter le delai sans attendre de vrais evenements tactiles.
etat = {"idle": 0.0}
root.seconds_idle = lambda: etat["idle"]


def attendre(tick_ms, tours=8):
    """Laisse passer plusieurs tours de la boucle Tk, assez pour que le
    prochain after(tick_ms) du helper se declenche."""
    for _ in range(tours):
        root.update()
        time.sleep(tick_ms / 1000)
        root.update()


# --- 1. se declenche une fois le delai depasse ---
appels = []
cadre = tk.Frame(root)
uc.schedule_auto_return(cadre, seconds=1, back_fn=lambda: appels.append("retour"),
                        _tick_ms=50)
etat["idle"] = 0.5
attendre(50)
print("1. avant le delai           :", len(appels), "appel(s) (attendu 0)")
assert not appels, "declenche trop tot"

etat["idle"] = 2.0
attendre(50)
print("2. apres le delai           :", len(appels), "appel(s) (attendu 1)")
assert appels == ["retour"], "ne s'est pas declenche"

# --- 2. suspendu tant qu'une fenetre superposee est ouverte ---
appels2 = []
cadre2 = tk.Frame(root)
panel = uc.open_modal(root, 300, 200)   # simule un numpad ou une confirmation
uc.schedule_auto_return(cadre2, seconds=1, back_fn=lambda: appels2.append("retour"),
                        _tick_ms=50)
etat["idle"] = 5.0                       # tres inactif...
attendre(50)
print("3. modale ouverte, inactif  :", len(appels2), "appel(s) (attendu 0)")
assert not appels2, "s'est declenche malgre une fenetre ouverte"

uc.close_modal(panel)
attendre(50)
print("4. modale fermee            :", len(appels2), "appel(s) (attendu 1)")
assert appels2 == ["retour"], "ne reprend pas une fois la fenetre fermee"

# --- 3. ne plante pas si l'ecran est deja detruit ---
appels3 = []
cadre3 = tk.Frame(root)
uc.schedule_auto_return(cadre3, seconds=1, back_fn=lambda: appels3.append("retour"),
                        _tick_ms=50)
cadre3.destroy()
etat["idle"] = 10.0
attendre(50)
print("5. ecran deja detruit       :", len(appels3), "appel(s) (attendu 0, pas d'erreur)")
assert not appels3

# --- 4. l'ecran Reception reel revient au menu, sauf pendant une saisie ---
from src import config, database, ui_reception  # noqa: E402
database.init_db()
database.add_supplier("Bigard")
vrai = ui_reception.auto_return
# meme helper, verifie plus souvent pour ne pas attendre 10 s par tour
ui_reception.auto_return = lambda w, s, f: vrai(w, s, f, _tick_ms=50)

retours = []
etat["idle"] = 0.0
ecran = ui_reception.ReceptionScreen(root, lambda: retours.append("menu"))
attendre(50)
print("6. Reception, actif         :", len(retours), "retour(s) (attendu 0)")
assert not retours and ecran.winfo_exists()

saisie = uc.open_modal(root, 300, 200)   # pave de temperature ouvert
etat["idle"] = config.RECEPTION_INACTIVITY_S + 60
attendre(50)
print("7. Reception, saisie ouverte:", len(retours), "retour(s) (attendu 0)")
assert not retours and ecran.winfo_exists(), "Reception fermee pendant une saisie"

uc.close_modal(saisie)
attendre(50)
print("8. Reception, inactif       :", len(retours), "retour(s) (attendu 1)")
assert retours == ["menu"] and not ecran.winfo_exists(), "Reception ne revient pas au menu"
ui_reception.auto_return = vrai

root.destroy()
cleanup(sandbox)
print("\nTOUS LES TESTS OK")
