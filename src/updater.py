"""Mise a jour automatique du code depuis GitHub.

Chaque Pi compare periodiquement le code deploye a la branche du depot. Si
elle a avance, il recupere la nouvelle version, la verifie, puis redemarre.

Garde-fous (une mauvaise version poussee ne doit pas paralyser les magasins) :
  - mise a jour uniquement quand l'appli est au repos (menu principal) ;
  - en mode "auto", uniquement pendant les heures creuses — sauf si la mise a
    jour attend depuis plus de 24 h (cas d'un Pi eteint la nuit) ;
  - verification que le nouveau code demarre (import complet) AVANT de
    l'adopter ; en cas d'echec, retour automatique a la version precedente ;
  - pilotage par appareil depuis devices/<hostname>.json :
        "update": "auto" (defaut) | "now" (des que possible) | "off"

Le redemarrage se fait en sortant en code d'erreur : systemd relance le
service (Restart=on-failure). Aucun privilege sudo n'est necessaire.
"""
import logging
import shutil
import subprocess
import sys
from pathlib import Path

from . import config, database

RESTART_EXIT_CODE = 42
# Fichiers/dossiers copies du depot vers le dossier de l'appli
SYNC_ITEMS = ("main.py", "requirements.txt", "install.sh",
              "traceability.service", "src", "tools")

APP_DIR = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)
if not logger.handlers:
    _h = logging.FileHandler(config.LOG_DIR / "update.log")
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)


def _run(args, cwd=None, timeout=120):
    return subprocess.run(args, cwd=str(cwd) if cwd else None,
                          capture_output=True, text=True, timeout=timeout)


def _git(*args, timeout=120):
    return _run(["git", *args], cwd=config.REPO_DIR, timeout=timeout)


def mode():
    """Mode de mise a jour de cet appareil : auto | now | off."""
    value = (database.get_meta("remote_update", "") or "auto").strip().lower()
    return value if value in ("auto", "now", "off") else "auto"


def current_version():
    """Version du code en place : le commit deploye par la mise a jour
    automatique, sinon le HEAD du depot local (cas d'une installation faite a
    la main). Chaine vide si le depot n'est pas la."""
    commit = database.get_meta("deployed_commit", "") or ""
    if commit:
        return commit
    if (Path(config.REPO_DIR) / ".git").is_dir():
        try:
            return _rev("HEAD") or ""
        except Exception:
            return ""
    return ""


def repo_ready():
    """Depot local pret (clone au besoin). Retourne le chemin, ou None."""
    repo = Path(config.REPO_DIR)
    if (repo / ".git").is_dir():
        return repo
    if not config.REPO_URL:
        return None
    logger.info("clonage du depot dans %s", repo)
    try:
        repo.parent.mkdir(parents=True, exist_ok=True)
        r = _run(["git", "clone", "--depth", "50", "--branch", config.REPO_BRANCH,
                  config.REPO_URL, str(repo)], timeout=600)
    except Exception as e:
        logger.warning("clonage impossible : %s", e)
        return None
    if r.returncode != 0:
        logger.warning("clonage echoue : %s", r.stderr.strip()[:200])
        return None
    return repo


def _rev(ref):
    r = _git("rev-parse", ref)
    return r.stdout.strip() if r.returncode == 0 else None


def check_available():
    """Recupere les nouveautes du depot. Retourne le commit cible si une mise
    a jour est disponible, sinon None."""
    if repo_ready() is None:
        return None
    try:
        r = _git("fetch", "--quiet", "origin", config.REPO_BRANCH)
    except Exception as e:
        logger.info("verification impossible : %s", e)
        return None
    if r.returncode != 0:
        logger.info("fetch echoue : %s", r.stderr.strip()[:200])
        return None
    target = _rev(f"origin/{config.REPO_BRANCH}")
    if not target:
        return None
    deployed = database.get_meta("deployed_commit", "") or _rev("HEAD")
    return target if target != deployed else None


def _sync_to_app_dir(repo):
    """Copie le code du depot vers le dossier de l'appli."""
    if repo.resolve() == APP_DIR.resolve():
        return  # l'appli tourne deja depuis le depot
    for item in SYNC_ITEMS:
        src, dst = repo / item, APP_DIR / item
        if not src.exists():
            continue
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
    for cache in APP_DIR.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def _health_ok():
    """Verifie que le nouveau code se charge entierement."""
    code = ("import sys; sys.path.insert(0, %r); "
            "import src.ui_main, src.updater, src.remote_lock" % str(APP_DIR))
    try:
        r = _run([sys.executable, "-c", code], cwd=APP_DIR, timeout=90)
    except Exception as e:
        logger.warning("verification du nouveau code impossible : %s", e)
        return False
    if r.returncode != 0:
        logger.error("nouveau code invalide : %s", r.stderr.strip()[-400:])
        return False
    return True


def perform_update(target):
    """Applique la mise a jour, avec retour arriere si le code ne demarre pas.
    Retourne True si le code a change et qu'il faut redemarrer."""
    repo = repo_ready()
    if repo is None:
        return False
    previous = _rev("HEAD")
    r = _git("reset", "--hard", target)
    if r.returncode != 0:
        logger.warning("mise a jour impossible : %s", r.stderr.strip()[:200])
        return False
    try:
        _sync_to_app_dir(repo)
        if not _health_ok():
            raise RuntimeError("le nouveau code ne demarre pas")
    except Exception as e:
        logger.error("RETOUR ARRIERE vers %s : %s", (previous or "?")[:8], e)
        if previous:
            _git("reset", "--hard", previous)
            try:
                _sync_to_app_dir(repo)
            except Exception as e2:
                logger.error("retour arriere incomplet : %s", e2)
        return False

    database.set_meta("deployed_commit", target)
    _install_requirements(repo, previous, target)
    logger.info("mise a jour %s -> %s appliquee", (previous or "?")[:8], target[:8])
    return True


def _install_requirements(repo, previous, target):
    """Installe les nouvelles dependances si requirements.txt a change.
    Echec non bloquant : le code est deja en place et verifie."""
    if not previous:
        return
    r = _git("diff", "--name-only", previous, target)
    if r.returncode != 0 or "requirements.txt" not in r.stdout:
        return
    logger.info("requirements.txt modifie : installation des dependances")
    try:
        out = _run([sys.executable, "-m", "pip", "install",
                    "--break-system-packages", "-r",
                    str(repo / "requirements.txt")], timeout=600)
        if out.returncode != 0:
            logger.warning("pip : %s", out.stderr.strip()[-300:])
    except Exception as e:
        logger.warning("pip impossible : %s", e)
