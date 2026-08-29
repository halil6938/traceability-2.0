"""Diagnostic du moteur de mise au point (VCM) de la camera.

Balaye LensPosition de bout en bout et affiche, pour chaque position :
  - la position DEMANDEE,
  - la position REELLEMENT appliquee (lue dans les metadonnees),
  - la nettete mesuree (variance du laplacien, zone centrale).

Si la colonne « reelle » ne suit pas la demande, ou si la nettete ne varie
pas, c'est que le moteur n'est pas pilote (overlay vcm absent, module sans
moteur, ou controle refuse par le pilote).

A lancer sur le Pi, appli arretee, avec un ticket bien en place :
    sudo systemctl stop traceability
    python3 tools/focus_probe.py
    sudo systemctl start traceability
"""
import time

import cv2
from picamera2 import Picamera2

STEPS = 16
SETTLE_S = 0.5


def sharpness(arr):
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    return cv2.Laplacian(gray[h // 4:3 * h // 4, w // 4:3 * w // 4],
                         cv2.CV_64F).var()


def main():
    picam = Picamera2()
    picam.configure(picam.create_preview_configuration(
        main={"size": (1296, 972), "format": "RGB888"}))
    picam.start()
    time.sleep(1.0)

    ctrls = picam.camera_controls
    print("Modele camera :", picam.camera_properties.get("Model"))
    print("LensPosition  :", ctrls.get("LensPosition"))
    print("AfMode        :", ctrls.get("AfMode"))
    if "LensPosition" not in ctrls:
        print("\n>>> PAS DE MOTEUR DE MISE AU POINT EXPOSE : rien a calibrer.")
        picam.stop(), picam.close()
        return

    try:
        from libcamera import controls as lc
        picam.set_controls({"AfMode": lc.AfModeEnum.Manual})
        print("Passage en AF manuel : OK")
    except Exception as e:
        print("Passage en AF manuel : ECHEC ->", e)

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
        picam.capture_array()          # purge le buffer en cours
        meta = picam.capture_metadata()
        arr = picam.capture_array()
        real = meta.get("LensPosition")
        score = sharpness(arr)
        results.append((pos, real, score))
        print(f"{pos:9.2f} {('%.2f' % real) if real is not None else '   ?':>9}"
              f" {score:10.0f}")

    if results:
        best = max(results, key=lambda r: r[2])
        lo_s = min(r[2] for r in results)
        hi_s = max(r[2] for r in results)
        print("-" * 31)
        print(f"Meilleure position : {best[0]:.2f}  (nettete {best[2]:.0f})")
        print(f"Variation de nettete : x{hi_s / lo_s:.2f}" if lo_s > 0 else "")
        if lo_s > 0 and hi_s / lo_s < 1.15:
            print(">>> La nettete ne varie quasiment pas : la lentille ne bouge "
                  "PAS. Verifier 'dtoverlay=ov5647,vcm' et camera_auto_detect=0 "
                  "dans /boot/firmware/config.txt, ou viser une cible contrastee.")
        else:
            print(">>> Le moteur repond : la calibration dans l'appli doit "
                  "fonctionner.")

    picam.stop()
    picam.close()


if __name__ == "__main__":
    main()
