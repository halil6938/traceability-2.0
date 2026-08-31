"""Extinction / rallumage de l'ecran du Pi.

Plusieurs methodes sont essayees, car cela depend du modele d'ecran :
  - retroeclairage des dalles DSI (/sys/class/backlight/*/bl_power) ;
  - DPMS via X11 (xset) ;
  - sortie HDMI (vcgencmd).
Toutes sont « au mieux » : un echec n'empeche rien, l'appli affiche de toute
facon un voile noir qui masque l'ecran et absorbe le premier contact.
"""
import glob
import logging
import subprocess

from . import config

logger = logging.getLogger(__name__)
if not logger.handlers:
    _h = logging.FileHandler(config.LOG_DIR / "screen.log")
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)


def _run(args):
    try:
        return subprocess.run(args, capture_output=True, timeout=5).returncode == 0
    except Exception:
        return False


def _backlight(value):
    """bl_power : 1 = eteint, 0 = allume."""
    done = False
    for path in glob.glob("/sys/class/backlight/*/bl_power"):
        try:
            with open(path, "w") as f:
                f.write(str(value))
            done = True
        except Exception as e:
            logger.info("retroeclairage %s : %s", path, e)
    return done


def off():
    """Eteint l'ecran."""
    ok = _backlight(1)
    ok = _run(["xset", "dpms", "force", "off"]) or ok
    ok = _run(["vcgencmd", "display_power", "0"]) or ok
    logger.info("extinction de l'ecran : %s", "ok" if ok else "aucune methode")
    return ok


def on():
    """Rallume l'ecran."""
    ok = _backlight(0)
    ok = _run(["xset", "dpms", "force", "on"]) or ok
    ok = _run(["vcgencmd", "display_power", "1"]) or ok
    return ok


def disable_os_blanking():
    """Desactive la veille du systeme : c'est l'appli qui gere l'extinction.

    Indispensable — avec la veille systeme, le contact qui rallume l'ecran est
    transmis a l'application et declenche le bouton situe sous le doigt :
    l'operateur se retrouve dans un menu au hasard. DPMS reste actif (sans
    delai automatique) pour que l'extinction commandee fonctionne encore.
    """
    _run(["xset", "s", "off"])
    _run(["xset", "s", "noblank"])
    _run(["xset", "dpms", "0", "0", "0"])
