"""Teste la mise a jour automatique de bout en bout, avec un vrai depot git :
1. une mise a jour valide est detectee, appliquee et deployee ;
2. une mise a jour qui casse le code est REFUSEE et annulee (retour arriere).
"""
import shutil
import subprocess

from _harness import REPO, setup, cleanup  # noqa: E402

SRC = REPO
sandbox = setup("maj_")
home = sandbox
from src import config, database, updater  # noqa: E402


def git(*args, cwd):
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    assert r.returncode == 0, f"git {args}: {r.stderr}"
    return r.stdout.strip()


def copy_app(dst):
    dst.mkdir(parents=True, exist_ok=True)
    for item in ("main.py", "requirements.txt"):
        shutil.copy2(SRC / item, dst / item)
    shutil.copytree(SRC / "src", dst / "src", dirs_exist_ok=True)
    shutil.rmtree(dst / "src" / "__pycache__", ignore_errors=True)


# --- depot "GitHub" ---
origin = sandbox / "origin"
copy_app(origin)
git("init", "-b", "master", cwd=origin)
git("config", "user.email", "test@test", cwd=origin)
git("config", "user.name", "test", cwd=origin)
git("add", "-A", cwd=origin)
git("commit", "-qm", "version initiale", cwd=origin)
v1 = git("rev-parse", "HEAD", cwd=origin)

# --- Pi : depot local + dossier de l'appli ---
repo = home / "traceability-2.0"
app = home / "traceability-app"
subprocess.run(["git", "clone", "-q", str(origin), str(repo)], check=True)
copy_app(app)

config.REPO_URL = str(origin)
config.REPO_DIR = repo
config.REPO_BRANCH = "master"
updater.APP_DIR = app
database.init_db()
database.set_meta("deployed_commit", v1)

print("mode par defaut :", updater.mode())
print("mise a jour disponible au depart :", updater.check_available())
assert updater.check_available() is None

# --- 1. mise a jour VALIDE ---
(origin / "src" / "nouveaute.py").write_text('MARQUEUR = "v2"\n', encoding="utf-8")
git("add", "-A", cwd=origin)
git("commit", "-qm", "ajout nouveaute", cwd=origin)
v2 = git("rev-parse", "HEAD", cwd=origin)

target = updater.check_available()
print("\n1) mise a jour detectee :", (target or "aucune")[:8], "(attendu",
      v2[:8] + ")")
assert target == v2
ok = updater.perform_update(target)
print("   appliquee :", ok)
print("   fichier deploye dans l'appli :", (app / "src" / "nouveaute.py").exists())
print("   commit deploye :", database.get_meta("deployed_commit", "")[:8])
assert ok and (app / "src" / "nouveaute.py").exists()
assert database.get_meta("deployed_commit") == v2

# --- 2. mise a jour CASSEE -> doit etre refusee et annulee ---
(origin / "src" / "database.py").write_text(
    "def casse(:\n    pass\n", encoding="utf-8")  # erreur de syntaxe
git("add", "-A", cwd=origin)
git("commit", "-qm", "version cassee", cwd=origin)
v3 = git("rev-parse", "HEAD", cwd=origin)

target = updater.check_available()
print("\n2) mise a jour cassee detectee :", (target or "aucune")[:8])
assert target == v3
ok = updater.perform_update(target)
print("   appliquee :", ok, "(attendu False)")
deployed = database.get_meta("deployed_commit", "")
print("   commit deploye apres coup :", deployed[:8], "(doit rester", v2[:8] + ")")
db_txt = (app / "src" / "database.py").read_text(encoding="utf-8")
print("   database.py de l'appli intact :", "def casse(" not in db_txt)
print("   nouveaute.py toujours la :", (app / "src" / "nouveaute.py").exists())
assert not ok
assert deployed == v2
assert "def casse(" not in db_txt
assert (app / "src" / "nouveaute.py").exists()

# --- 3. commit qui ne touche QUE le fichier de controle -> pas de redemarrage ---
git("checkout", "-q", v2, "--", "src/database.py", cwd=origin)   # remet le bon code
(origin / "devices").mkdir(exist_ok=True)
(origin / "devices" / "client.json").write_text('{"locked": true}\n',
                                                encoding="utf-8")
git("add", "-A", cwd=origin)
git("commit", "-qm", "verrouillage du client", cwd=origin)
v4 = git("rev-parse", "HEAD", cwd=origin)
database.set_meta("deployed_commit", v2)          # on repart de la v2 saine
target = updater.check_available()
print("\n3) commit ne touchant que devices/ -> mise a jour proposee :",
      target or "aucune", "(attendu : aucune)")
print("   commit note sans redemarrage :",
      database.get_meta("deployed_commit", "")[:8], "(doit valoir", v4[:8] + ")")
assert target is None, "un commit sans code ne doit pas redemarrer l'appli"
assert database.get_meta("deployed_commit") == v4

print("\nlog de mise a jour :")
log = config.LOG_DIR / "update.log"
if log.exists():
    for line in log.read_text(encoding="utf-8").splitlines()[-4:]:
        print("   ", line)

cleanup(sandbox)
print("\nTOUS LES TESTS OK")
