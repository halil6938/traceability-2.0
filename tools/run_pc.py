"""Lance l'application sur un PC (Windows ou Linux) pour l'essayer sans Pi.

    python tools/run_pc.py

  - fenetre 800x480, comme l'ecran du Pi, sans plein ecran ;
  - donnees isolees dans le dossier _local/ : la configuration reelle d'un Pi
    n'est jamais touchee, et rien n'est envoye a l'exterieur ;
  - controle a distance, mise a jour automatique et signe de vie DESACTIVES
    (sinon un essai sur PC pourrait verrouiller ou mettre a jour la machine) ;
  - camera : la webcam du PC est utilisee si presente — le module Pi n'existe
    pas ici, donc l'autofocus et la calibration ne sont pas representatifs.

Echap bascule le plein ecran. Fermer la fenetre pour quitter.
Pour repartir de zero, supprimer le dossier _local/.
"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "_local"
DATA.mkdir(exist_ok=True)

# Doit etre fait AVANT d'importer src.config, qui calcule ses chemins a partir
# du dossier personnel.
os.environ["HOME"] = str(DATA)
os.environ["USERPROFILE"] = str(DATA)

sys.path.insert(0, str(REPO))
from src import config, database  # noqa: E402

# Un essai sur PC ne doit rien declencher a distance
config.REMOTE_CONTROL_BASE = ""   # ni verrou ni reglages distants
config.REPO_URL = ""              # pas de mise a jour automatique
config.SCREEN_OFF_S = 0           # pas de veille de l'ecran

from src.ui_main import App  # noqa: E402


def main():
    database.init_db()
    print(f"Donnees d'essai : {DATA}")
    print("Echap = plein ecran / fenetre.  Fermer la fenetre pour quitter.\n")

    app = App()
    # Repasser en fenetre a la taille de l'ecran du Pi, puis reconstruire le
    # menu : App() s'est dimensionne sur l'ecran du PC.
    app.attributes("-fullscreen", False)
    app.attributes("-topmost", False)
    app.geometry("800x480")
    config.SCREEN_W, config.SCREEN_H = 800, 480
    app.show_menu()
    app.mainloop()


if __name__ == "__main__":
    main()
