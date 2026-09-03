"""Base commune aux tests : bac a sable isole et sortie lisible.

Chaque test s'execute avec un dossier personnel temporaire : la base, les
photos et les journaux du test n'ont donc aucun contact avec la configuration
reelle d'un Pi ni avec celle du PC.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def setup(prefix="test_"):
    """Prepare l'isolement et retourne le dossier temporaire du test.
    A appeler AVANT d'importer src.config, qui calcule ses chemins a partir du
    dossier personnel."""
    for flux in (sys.stdout, sys.stderr):
        try:                      # console Windows : eviter les erreurs d'accents
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sandbox = Path(tempfile.mkdtemp(prefix=prefix))
    os.environ["HOME"] = str(sandbox)
    os.environ["USERPROFILE"] = str(sandbox)
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    return sandbox


def cleanup(sandbox):
    shutil.rmtree(sandbox, ignore_errors=True)
