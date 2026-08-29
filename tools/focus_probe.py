"""Diagnostic du moteur de mise au point (VCM) de la camera.

Ouvre la camera avec l'algorithme AF injecte dans le tuning (comme l'appli),
balaye LensPosition de bout en bout et affiche pour chaque position :
  - la position DEMANDEE,
  - la position REELLEMENT appliquee (lue dans les metadonnees),
  - la nettete mesuree (variance du laplacien, zone centrale).

Colonne « reelle » vide ou nettete constante = le moteur ne bouge pas.
Le message « Could not set LENS_POSITION - no AF algorithm » signifie que le
tuning du capteur n'a pas de bloc AF (c'est ce que l'appli corrige).

A lancer sur le Pi, appli arretee, avec un ticket contraste bien eclaire :
    sudo systemctl stop traceability
    python3 tools/focus_probe.py
    sudo systemctl start traceability
"""
import sys
import time
from pathlib import Path

import cv2
from picamera2 import Picamera2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.camera_scan import tuning_with_af  # noqa: E402

STEPS = 16
SETTLE_S = 0.5


def sharpness(arr):
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    return cv2.Laplacian(gray[h // 4:3 * h // 4, w // 4:3 * w // 4],
                         cv2.CV_64F).var()


def open_camera():
    """Ouvre la camera avec le tuning enrichi de l'algorithme AF."""
    cam = Picamera2()
    model = str(cam.camera_properties.get("Model", "")).lower()
    tuning = tuning_with_af(model)
    print("Modele camera :", model)
    if tuning is None:
        print("Tuning AF     : deja present (ou tuning introuvable)")
        return cam
    print("Tuning AF     : algorithme 'rpi.af' injecte")
    cam.close()
    return Picamera2(tuning=tuning)


def main():
    picam = open_camera()
    picam.configure(picam.create_preview_configuration(
        main={"size": (1296, 972), "format": "RGB888"}))
    picam.start()
    time.sleep(1.5)  # laisser l'auto-exposition converger

    ctrls = picam.camera_controls
    print("LensPosition  :", ctrls.get("LensPosition"))
    print("AfMode        :", ctrls.get("AfMode"))
    if "LensPosition" not in ctrls:
        print("\n>>> PAS DE MOTEUR DE MISE AU POINT : rien a calibrer.")
        picam.stop()
        picam.close()
        return

    try:
        from libcamera import controls as lc
        picam.set_controls({"AfMode": lc.AfModeEnum.Manual})
        print("AF manuel     : OK")
    except Exception as e:
        print("AF manuel     : ECHEC ->", e)

    lo, hi = float(ctrls["LensPosition"][0]), float(ctrls["LensPosition"][1])
    print(f"\nBalayage de {lo:.2f} a {hi:.2f} ({STEPS} positions)\n")
    print(f"{'demandee':>9} {'reelle':>9} {'nettete':>10}")
    print("-" * 31)

    results = []
    for i in range(STEPS):
        pos = lo + (hi - lo) * i / (STEPS - 1)
        try:
            picam.set_controls({"LensPosition": pos})
        except Exception as e:
            print("ECHEC set_controls LensPosition :", e)
            break
        time.sleep(SETTLE_S)
        picam.capture_array()                 # purge le buffer en cours
        meta = picam.capture_metadata()
        score = sharpness(picam.capture_array())
        real = meta.get("LensPosition")
        results.append((pos, real, score))
        print(f"{pos:9.2f} {('%.2f' % real) if real is not None else '-':>9}"
              f" {score:10.0f}")

    picam.stop()
    picam.close()
    if not results:
        return

    print("-" * 31)
    best = max(results, key=lambda r: r[2])
    lo_s = min(r[2] for r in results)
    hi_s = max(r[2] for r in results)
    moved = any(r[1] is not None for r in results)
    varied = lo_s > 0 and hi_s / lo_s >= 1.15

    print(f"Meilleure position : {best[0]:.2f}  (nettete {best[2]:.0f})")
    if lo_s > 0:
        print(f"Variation de nettete : x{hi_s / lo_s:.2f}")
    if not moved:
        print(">>> La position reelle n'est JAMAIS remontee : le moteur n'est "
              "pas pilote. Verifier 'dtoverlay=ov5647,vcm' et "
              "'camera_auto_detect=0' dans /boot/firmware/config.txt.")
    elif hi_s < 50:
        print(">>> Nettete tres faible partout : cible sans contraste ou scene "
              "trop sombre. Viser un ticket imprime, bien eclaire, qui remplit "
              "le centre de l'image, puis relancer.")
    elif not varied:
        print(">>> La nettete ne varie pas malgre le deplacement : verifier que "
              "la cible est bien dans la zone centrale.")
    else:
        print(">>> Le moteur repond et la nettete varie : la calibration dans "
              "l'appli va fonctionner.")


if __name__ == "__main__":
    main()
