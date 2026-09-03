"""Lance tous les tests du dossier tests/.

    python tests/run_all.py

Chaque test s'execute dans son propre processus, avec des donnees isolees dans
un dossier temporaire : ni la configuration d'un Pi ni celle du PC ne sont
touchees, et rien n'est envoye sur le reseau.

Certains tests ouvrent brievement une fenetre (ils pilotent l'interface pour
verifier, par exemple, qu'un contact sur l'ecran en veille ne declenche aucun
bouton) : c'est normal, ne pas y toucher pendant l'execution.

A lancer avant de fabriquer une carte SD, ou apres toute modification.
"""
import subprocess
import sys
import time
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
DELAI_MAX = 180  # secondes par test


def main():
    fichiers = sorted(DOSSIER.glob("test_*.py"))
    if not fichiers:
        print("Aucun test trouve.")
        return 1

    print(f"{len(fichiers)} tests\n" + "=" * 62)
    echecs = []
    for fichier in fichiers:
        debut = time.perf_counter()
        try:
            r = subprocess.run([sys.executable, str(fichier)],
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace",
                               timeout=DELAI_MAX)
            ok = r.returncode == 0
            sortie = (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            ok, sortie = False, f"(delai de {DELAI_MAX} s depasse)"
        duree = time.perf_counter() - debut
        print(f"{'OK  ' if ok else 'ECHEC'}  {fichier.stem:<32} {duree:5.1f} s")
        if not ok:
            echecs.append((fichier.stem, sortie))

    print("=" * 62)
    if not echecs:
        print(f"Tous les tests passent ({len(fichiers)}/{len(fichiers)}).")
        return 0

    print(f"{len(echecs)} test(s) en echec :\n")
    for nom, sortie in echecs:
        print(f"--- {nom} " + "-" * (58 - len(nom)))
        for ligne in sortie.strip().splitlines()[-15:]:
            print("   ", ligne)
        print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
