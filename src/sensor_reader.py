"""Lecture combinee des capteurs de temperature : BLE (Brifit) + WiFi (Tuya).

Point d'entree unique pour les trois usages de l'appli (ecran releve du
jour, auto-releve de 3h, test dans Parametres) : on lit chaque famille de
capteurs avec son lecteur, et on fusionne les resultats.
"""
import logging

logger = logging.getLogger(__name__)


def read_all(sensors, cancel=None):
    """Lit tous les capteurs assignes a un appareil.

    sensors : lignes de database.list_ble_sensors().
    cancel  : threading.Event optionnel (interrompt le scan BLE).

    Retourne (results, err) :
      results : {cle_minuscule: temp_C} — cle = MAC (ble) ou Device ID (wifi)
      err     : message d'erreur agrege, ou None si tout s'est bien passe.
    NB : l'appelant doit tenir config.BLE_LOCK (partie scan BLE).
    """
    results = {}
    errors = []

    ble_macs = [s["mac"] for s in sensors
                if s["device_id"] and s.get("kind", "ble") != "wifi"]
    wifi_ids = [s["mac"] for s in sensors
                if s["device_id"] and s.get("kind") == "wifi"]

    if ble_macs:
        try:
            from . import ble_reader
            results.update(ble_reader.read_temperatures(ble_macs, cancel=cancel))
        except Exception as e:
            logger.warning("lecture BLE : %s", e)
            errors.append(f"BLE: {e}")

    if wifi_ids and not (cancel is not None and cancel.is_set()):
        try:
            from . import tuya_reader
            results.update(tuya_reader.read_temperatures(wifi_ids))
        except Exception as e:
            logger.warning("lecture WiFi/Tuya : %s", e)
            errors.append(f"WiFi: {e}")

    return results, (" ; ".join(errors) or None)
