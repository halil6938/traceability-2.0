"""Lecture des capteurs de temperature Tuya WiFi via le cloud.

Ces capteurs a piles dorment en permanence : ils poussent leurs mesures au
cloud Tuya par a-coups (intervalle regulier ou variation de temperature).
On lit donc la DERNIERE valeur connue du cloud — exactement comme l'appli
Smart Life — via l'API v2.0 « shadow properties » (l'API status v1.0
renvoie vide pour ces modeles recents).

Configuration (stockee en meta dans la base locale) :
    tuya_access_id / tuya_access_secret : cles du projet iot.tuya.com
    tuya_region                         : eu (defaut), us, cn, in

NB : le plan gratuit Tuya (« Trial ») expire tous les 6 mois — le
renouveler en 2 clics sur iot.tuya.com si les lectures echouent en
erreur d'autorisation.
"""
import logging
import time

from . import config, database

# Codes de temperature, par ordre de preference : la sonde filaire externe
# d'abord (celle placee dans le frigo), sinon le capteur interne du boitier.
TEMP_CODES = ("temp_current_external", "temp_current")
TEMP_SCALE = 10.0        # valeurs cloud en dixiemes de degre (290 -> 29.0)
TEMP_MIN = -40.0
TEMP_MAX = 60.0
MAX_AGE_S = 4 * 3600.0   # mesure plus vieille -> consideree perimee (capteur HS)

try:
    import tinytuya
    HAS_TINYTUYA = True
except ImportError:
    HAS_TINYTUYA = False

logger = logging.getLogger(__name__)
if not logger.handlers:
    _h = logging.FileHandler(config.LOG_DIR / "tuya.log")
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)


def get_creds():
    """Cles cloud Tuya depuis la base, ou None si non configurees."""
    access_id = database.get_meta("tuya_access_id", "")
    secret = database.get_meta("tuya_access_secret", "")
    region = database.get_meta("tuya_region", "") or "eu"
    if not access_id or not secret:
        return None
    return {"access_id": access_id, "secret": secret, "region": region}


def set_creds(access_id: str, secret: str, region: str = "eu"):
    database.set_meta("tuya_access_id", access_id.strip())
    database.set_meta("tuya_access_secret", secret.strip())
    database.set_meta("tuya_region", (region or "eu").strip().lower())


def _cloud(creds):
    return tinytuya.Cloud(apiRegion=creds["region"],
                          apiKey=creds["access_id"],
                          apiSecret=creds["secret"])


def list_cloud_devices(creds=None):
    """Liste les appareils lies au projet Tuya : [{id, name, product}]."""
    if not HAS_TINYTUYA:
        raise RuntimeError("tinytuya non installe (pip install tinytuya)")
    creds = creds or get_creds()
    if creds is None:
        raise RuntimeError("Cloud Tuya non configure (cles manquantes)")
    devs = _cloud(creds).getdevices()
    if not isinstance(devs, list):
        raise RuntimeError(f"Cloud Tuya : {devs}")
    return [{"id": d.get("id", ""), "name": d.get("name", "?"),
             "product": d.get("product_name", "")} for d in devs]


def read_temperatures(device_ids, creds=None, max_age_s=MAX_AGE_S):
    """Lit la derniere temperature connue de chaque capteur via le cloud.
    Retourne {device_id_minuscule: temp_celsius}. Les mesures perimees
    (> max_age_s) ou aberrantes sont ignorees. Leve RuntimeError si
    tinytuya absent ou cles non configurees."""
    if not HAS_TINYTUYA:
        raise RuntimeError("tinytuya non installe (pip install tinytuya)")
    creds = creds or get_creds()
    if creds is None:
        raise RuntimeError("Cloud Tuya non configure (cles manquantes)")

    cloud = _cloud(creds)
    results = {}
    now_ms = time.time() * 1000.0
    for did in device_ids:
        try:
            r = cloud.cloudrequest(f"/v2.0/cloud/thing/{did}/shadow/properties",
                                   action="GET")
        except Exception as e:
            logger.warning("requete cloud %s : %s", did, e)
            continue
        if not isinstance(r, dict) or not r.get("success"):
            logger.warning("reponse cloud %s : %s", did, r)
            continue
        props = {p.get("code"): p
                 for p in (r.get("result") or {}).get("properties", [])}

        battery = props.get("battery_state", {}).get("value")
        if battery == "low":
            logger.warning("pile faible sur le capteur %s", did)

        for code in TEMP_CODES:
            p = props.get(code)
            if not p or p.get("value") is None:
                continue
            ts = p.get("time") or 0
            age = (now_ms - ts) / 1000.0 if ts else None
            if age is not None and age > max_age_s:
                logger.warning("mesure perimee %s (%s, agee de %.0f min)",
                               did, code, age / 60)
                break  # meme horodatage pour l'autre code : inutile d'essayer
            temp = round(p["value"] / TEMP_SCALE, 1)
            if not (TEMP_MIN <= temp <= TEMP_MAX):
                logger.warning("valeur aberrante %s (%s) : %.1f", did, code, temp)
                continue
            results[did.lower()] = temp
            logger.info("cloud %s : %s = %.1f C (age %.0f s)",
                        did, code, temp, age or -1)
            break
    return results
