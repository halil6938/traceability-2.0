"""Applique en une seule commande les identifiants communs a tous tes Pi.

    python3 tools/finaliser.py                  # cherche le fichier sur la cle USB
    python3 tools/finaliser.py --exemple        # cree un modele de fichier
    python3 tools/finaliser.py --fichier CHEMIN
    python3 tools/finaliser.py --etat           # ce qui est deja configure
    python3 tools/finaliser.py --exporter       # ecrit le fichier depuis CE Pi

Utile apres une installation depuis GitHub, ou les identifiants ne sont pas
herites d'une image : jeton Telegram et cles Tuya sont les memes sur toutes
tes machines, seul le nom d'hote differe.

Le fichier d'identifiants n'est JAMAIS copie sur le Pi ni dans le depot : il
est lu, applique, puis oublie. Garde la cle USB qui le contient, ne la laisse
pas chez un client.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import database  # noqa: E402

# cle du fichier -> cle en base
CHAMPS = {
    "telegram_token": "telegram_token",
    "telegram_chat_id": "telegram_chat_id",
    "tuya_access_id": "tuya_access_id",
    "tuya_access_secret": "tuya_access_secret",
    "tuya_region": "tuya_region",
}
SECRETS = ("telegram_token", "tuya_access_secret")
NOM_FICHIER = "identifiants.txt"

MODELE = """# Identifiants communs a tous les Pi Traceability.
# A garder sur une cle USB, hors de portee des clients.
# Lignes vides et lignes commencant par # ignorees.

telegram_token     = 1234567890:AA...
telegram_chat_id   = 987654321

# Facultatif : seulement si le client a un capteur WiFi Tuya
tuya_access_id     =
tuya_access_secret =
tuya_region        = eu
"""


def masquer(cle, valeur):
    if cle in SECRETS and len(valeur) > 12:
        return f"{valeur[:6]}...{valeur[-4:]}"
    return valeur


def chercher_fichier():
    """Cherche identifiants.txt sur les supports montes, puis a cote du depot."""
    for base in (Path("/media"), Path("/mnt")):
        if base.is_dir():
            for chemin in sorted(base.glob(f"*/*/{NOM_FICHIER}")):
                return chemin
            for chemin in sorted(base.glob(f"*/{NOM_FICHIER}")):
                return chemin
    local = Path(__file__).resolve().parent.parent / NOM_FICHIER
    return local if local.is_file() else None


def lire(chemin):
    """Fichier « cle = valeur », tolerant aux espaces et aux commentaires."""
    valeurs = {}
    inconnues = []
    for num, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), 1):
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#"):
            continue
        if "=" not in ligne:
            inconnues.append(f"ligne {num} : « {ligne[:40]} » (pas de =)")
            continue
        cle, _, valeur = ligne.partition("=")
        cle, valeur = cle.strip().lower(), valeur.strip()
        if cle not in CHAMPS:
            inconnues.append(f"ligne {num} : cle inconnue « {cle} »")
        elif valeur:
            valeurs[cle] = valeur
    return valeurs, inconnues


def etat():
    print(f"Machine : {__import__('socket').gethostname()}\n")
    for cle in CHAMPS:
        valeur = database.get_meta(cle, "") or ""
        etiquette = masquer(cle, valeur) if valeur else "— non configure"
        print(f"  {cle:<20} {etiquette}")
    return 0


OPTIONS = ("--etat", "--exemple", "--exporter", "--fichier")


def main(args):
    # Une option inconnue (ancienne version du script, faute de frappe) ne
    # doit pas passer inapercue et declencher autre chose.
    inconnues = [a for a in args if a.startswith("--") and a not in OPTIONS]
    if inconnues:
        print("Option inconnue : " + ", ".join(inconnues))
        print("Options possibles : " + "  ".join(OPTIONS))
        print("Sans option : cherche identifiants.txt sur la cle USB "
              "et l'applique.")
        return 1

    # Le script peut tourner avant le premier demarrage de l'application :
    # la base n'existe alors pas encore.
    database.init_db()

    if "--etat" in args:
        return etat()

    if "--exporter" in args:
        # Recuperer les identifiants d'une machine deja configuree pour les
        # reporter sur les suivantes, sans avoir a les retrouver ailleurs.
        i = args.index("--exporter")
        cible = Path(args[i + 1]) if i + 1 < len(args) else Path.cwd() / NOM_FICHIER
        if cible.exists():
            print(f"{cible} existe deja, rien n'a ete ecrit.")
            return 1
        valeurs = {c: (database.get_meta(c, "") or "") for c in CHAMPS}
        if not any(valeurs.values()):
            print("Cette machine n'a aucun identifiant enregistre.")
            return 1
        lignes = ["# Identifiants exportes depuis " + __import__("socket").gethostname(),
                  "# CONTIENT DES SECRETS EN CLAIR : garder sur cle USB,",
                  "# ne jamais laisser chez un client.", ""]
        lignes += [f"{c:<18} = {valeurs[c]}" for c in CHAMPS]
        cible.write_text("\n".join(lignes) + "\n", encoding="utf-8")
        print(f"Fichier ecrit : {cible}")
        for cle, valeur in valeurs.items():
            print(f"  {cle:<20} {masquer(cle, valeur) if valeur else '— vide'}")
        print("\nCopie-le sur ta cle USB, puis efface-le de cette machine :")
        print(f"    rm {cible}")
        return 0

    if "--exemple" in args:
        cible = Path.cwd() / NOM_FICHIER
        if cible.exists():
            print(f"{cible} existe deja, rien n'a ete ecrit.")
            return 1
        cible.write_text(MODELE, encoding="utf-8")
        print(f"Modele cree : {cible}")
        print("Remplis-le, copie-le sur ta cle USB, puis relance sans --exemple.")
        return 0

    if "--fichier" in args:
        i = args.index("--fichier")
        if i + 1 >= len(args):
            print("Usage : --fichier CHEMIN")
            return 1
        chemin = Path(args[i + 1])
    else:
        chemin = chercher_fichier()

    if chemin is None:
        print(f"Aucun fichier {NOM_FICHIER} trouve.")
        print("Branche la cle USB qui le contient, ou indique le chemin :")
        print(f"    python3 {Path(__file__).name} --fichier /media/.../{NOM_FICHIER}")
        print(f"Pour creer un modele : python3 {Path(__file__).name} --exemple")
        return 1
    if not chemin.is_file():
        print(f"Fichier introuvable : {chemin}")
        return 1

    valeurs, inconnues = lire(chemin)
    for avertissement in inconnues:
        print(f"  ignore — {avertissement}")
    if not valeurs:
        print(f"{chemin} ne contient aucune valeur renseignee.")
        return 1

    print(f"Lecture de {chemin}\n")
    for cle, valeur in valeurs.items():
        database.set_meta(CHAMPS[cle], valeur)
        print(f"  {cle:<20} -> {masquer(cle, valeur)}")

    print("\nEnregistre. Le fichier n'a pas ete copie sur cette machine.")
    if "telegram_token" in valeurs:
        print("Un message de confirmation Telegram partira dans la minute.")
    print("\nIl reste, pour cette machine :")
    print("  - le nom du client   : bash tools/set_client.sh <nom-du-client>")
    print("  - la rotation ecran  : Screen Configuration (180 degres)")
    print("  - la calibration du focus, camera en place")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
