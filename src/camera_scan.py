"""Ecran de scan : preview camera + detection auto rectangle blanc + capture."""
import tkinter as tk
from datetime import datetime
from pathlib import Path
import threading
import time

import cv2
import numpy as np
from PIL import Image, ImageTk

from . import config, usb_manager

try:
    from picamera2 import Picamera2
    HAS_PICAMERA = True
except ImportError:
    HAS_PICAMERA = False


class CameraScanScreen(tk.Frame):
    def __init__(self, master, on_done, test_mode=False):
        super().__init__(master, bg="black")
        self.on_done = on_done
        self.test_mode = test_mode
        self.pack(fill="both", expand=True)

        self.preview_label = tk.Label(self, bg="black")
        self.preview_label.pack(fill="both", expand=True)

        # Barre status + bouton retour
        bar = tk.Frame(self, bg="black")
        bar.place(relx=0, rely=0, relwidth=1, height=48)
        status_text = ("TEST CAMÉRA — image brute, réglez la distance du ticket"
                       if test_mode else "Recherche d'une etiquette...")
        status_color = config.COLOR_WARNING if test_mode else "white"
        self.status = tk.Label(bar, text=status_text,
                               fg=status_color, bg="black", font=config.FONT_MED)
        self.status.pack(side="left", padx=12)
        tk.Button(bar, text="← Retour", font=config.FONT_MED,
                  command=self._back, bg=config.COLOR_CARD, fg="white",
                  activebackground=config.COLOR_MUTED, bd=0, padx=16, pady=4
                  ).pack(side="right", padx=8, pady=4)

        self.flash = tk.Frame(self, bg="white")  # overlay flash au moment de la capture

        self._stop = False
        self._stable_count = 0
        self._last_capture = 0
        self._capturing = False
        self._sharp_max = 0.0  # meilleur score de nettete vu (mode test)

        self._init_camera()
        self.after(10, self._loop)

    # --- camera ---
    def _set_full_fov(self):
        """Force ScalerCrop sur la totalite du capteur = zoom minimal, champ max."""
        try:
            w, h = self.picam.camera_properties["PixelArraySize"]
            self.picam.set_controls({"ScalerCrop": (0, 0, w, h)})
        except Exception:
            pass  # si le controle n'est pas supporte, on ignore

    def _enable_autofocus_picamera(self):
        """Regle la mise au point. Module AF (OV5647-AF, Camera v3...) :
        - FOCUS_DISTANCE_CM > 0 : focus fige a cette distance (LensPosition,
          en dioptries = 100/cm) — fiable pour un montage a distance fixe ;
        - sinon : autofocus continu si le pilote l'expose (AfMode).
        Necessite dtoverlay=ov5647,vcm dans /boot/firmware/config.txt."""
        try:
            ctrls = self.picam.camera_controls
            if "LensPosition" in ctrls and config.FOCUS_DISTANCE_CM:
                lp = 100.0 / config.FOCUS_DISTANCE_CM
                lo, hi = ctrls["LensPosition"][0], ctrls["LensPosition"][1]
                self.picam.set_controls({"LensPosition": max(lo, min(hi, lp))})
            elif "AfMode" in ctrls:
                from libcamera import controls
                self.picam.set_controls({"AfMode": controls.AfModeEnum.Continuous})
        except Exception:
            pass  # camera a focale fixe : on ignore

    def _init_camera(self):
        preview_size = config.PREVIEW_RESOLUTION
        if HAS_PICAMERA:
            self.picam = Picamera2()
            cfg = self.picam.create_preview_configuration(
                main={"size": preview_size, "format": "RGB888"}
            )
            self.picam.configure(cfg)
            self.picam.start()
            self._set_full_fov()
            self._enable_autofocus_picamera()
            self.capture_fn = self._capture_picamera
            self.read_fn = self._read_picamera
        else:
            # Fallback webcam USB (dev sur PC)
            self.cap = cv2.VideoCapture(0)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, preview_size[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, preview_size[1])
            self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
            self.capture_fn = self._capture_opencv
            self.read_fn = self._read_opencv

    def _apply_rotation(self, rgb_array):
        """Applique CAMERA_ROTATION (0/90/180/270) sur un tableau numpy RGB."""
        if config.CAMERA_ROTATION == 90:
            return cv2.rotate(rgb_array, cv2.ROTATE_90_CLOCKWISE)
        if config.CAMERA_ROTATION == 180:
            return cv2.rotate(rgb_array, cv2.ROTATE_180)
        if config.CAMERA_ROTATION == 270:
            return cv2.rotate(rgb_array, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return rgb_array

    def _read_picamera(self):
        return self._apply_rotation(self.picam.capture_array())

    def _read_opencv(self):
        ok, frame = self.cap.read()
        if not ok:
            return None
        return self._apply_rotation(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    def _capture_picamera(self) -> bytes:
        import io
        self.picam.stop()
        # Pleine resolution du capteur (3280x2464 sur Camera v2) pour que le
        # texte du ticket reste lisible ; fallback sur CAMERA_RESOLUTION.
        try:
            full_res = tuple(self.picam.camera_properties["PixelArraySize"])
        except Exception:
            full_res = config.CAMERA_RESOLUTION
        hi_cfg = self.picam.create_still_configuration(
            main={"size": full_res, "format": "RGB888"}
        )
        self.picam.configure(hi_cfg)
        self.picam.start()
        self._set_full_fov()
        self._enable_autofocus_picamera()
        if config.FOCUS_DISTANCE_CM and "LensPosition" in self.picam.camera_controls:
            time.sleep(0.8)  # focus fige : laisser expo + lentille se stabiliser
        else:
            # Declencher un cycle d'autofocus complet avant la photo (cameras AF)
            try:
                self.picam.autofocus_cycle()
            except Exception:
                time.sleep(0.8)  # focale fixe : laisser l'expo se stabiliser
        arr = self.picam.capture_array()
        # Rotation puis recadrage sur l'etiquette
        arr = self._apply_rotation(arr)
        arr = self._crop_to_label(arr)
        img = Image.fromarray(arr)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        # remettre en preview
        self.picam.stop()
        cfg = self.picam.create_preview_configuration(
            main={"size": config.PREVIEW_RESOLUTION, "format": "RGB888"}
        )
        self.picam.configure(cfg)
        self.picam.start()
        self._set_full_fov()
        self._enable_autofocus_picamera()
        return buf.getvalue()

    def _capture_opencv(self) -> bytes:
        # Basculer la webcam en resolution max le temps de la capture
        # (le preview tourne en basse resolution pour la fluidite)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 4096)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 3072)  # le driver retombe sur son max reel
        # Purger le buffer + laisser l'autofocus/expo se refaire
        frame = None
        for _ in range(8):
            ok, f = self.cap.read()
            if ok:
                frame = f
            time.sleep(0.1)
        # Retour en resolution preview
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.PREVIEW_RESOLUTION[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.PREVIEW_RESOLUTION[1])
        if frame is None:
            return b""
        rgb = self._apply_rotation(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        rgb = self._crop_to_label(rgb)
        frame = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return buf.tobytes()

    def _crop_to_label(self, rgb_array):
        """Recadre sur l'etiquette detectee (+10% de marge). Si aucune
        etiquette n'est trouvee sur la photo, on la garde entiere."""
        if not config.CROP_TO_LABEL:
            return rgb_array
        try:
            rect = self._detect_rectangle(rgb_array)
        except Exception:
            return rgb_array
        if rect is None:
            return rgb_array
        x, y, w, h = cv2.boundingRect(rect)
        H, W = rgb_array.shape[:2]
        mx, my = int(w * 0.10), int(h * 0.10)
        x0, y0 = max(0, x - mx), max(0, y - my)
        x1, y1 = min(W, x + w + mx), min(H, y + h + my)
        return rgb_array[y0:y1, x0:x1]

    # --- detection rectangle ---
    def _detect_rectangle(self, rgb_frame) -> np.ndarray | None:
        gray = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        h, w = gray.shape
        min_area = h * w * config.RECT_MIN_AREA_RATIO
        kernel = np.ones((5, 5), np.uint8)

        # --- Methode 1 : seuillage adaptatif (robuste aux variations d'eclairage) ---
        adapt = cv2.adaptiveThreshold(
            blur, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 21, -4
        )
        adapt = cv2.morphologyEx(adapt, cv2.MORPH_CLOSE, kernel)

        # --- Methode 2 : Canny (fonctionne sur toute couleur d'etiquette) ---
        canny = cv2.Canny(blur, 30, 120)
        canny = cv2.dilate(canny, kernel, iterations=1)

        best = None
        best_area = 0

        for mask in (adapt, canny):
            contours, _ = cv2.findContours(
                mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < min_area or area <= best_area:
                    continue
                peri = cv2.arcLength(cnt, True)

                # Essai avec epsilon progressif pour trouver un quad
                for eps in (0.02, 0.03, 0.05):
                    approx = cv2.approxPolyDP(cnt, eps * peri, True)
                    if len(approx) == 4:
                        best = approx
                        best_area = area
                        break
                    # Si trop de sommets : on prend le rectangle englobant minimum
                    if len(approx) > 4:
                        rect = cv2.minAreaRect(cnt)
                        box = cv2.boxPoints(rect).astype(int)
                        best = box.reshape(-1, 1, 2)
                        best_area = area
                        break

        return best

    # --- boucle preview ---
    def _update_sharpness(self, frame):
        """Mode test : score de nettete (variance du laplacien) sur la zone
        centrale, affiche dans la barre de statut. L'image n'est pas modifiee."""
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        h, w = gray.shape
        score = cv2.Laplacian(gray[h // 4:3 * h // 4, w // 4:3 * w // 4],
                              cv2.CV_64F).var()
        self._sharp_max = max(self._sharp_max, score)
        ratio = score / self._sharp_max if self._sharp_max > 0 else 0.0
        color = (config.COLOR_SUCCESS if ratio > 0.8 else
                 config.COLOR_WARNING if ratio > 0.5 else config.COLOR_DANGER)
        self.status.config(
            text=f"Image brute — Netteté : {score:.0f} (meilleur : {self._sharp_max:.0f})",
            fg=color)

    def _show_frame(self, rgb_array):
        """Affiche l'image sans deformation (rapport conserve, lissage bilineaire)."""
        img = Image.fromarray(rgb_array)
        scale = min(config.SCREEN_W / img.width, config.SCREEN_H / img.height)
        img = img.resize((max(1, int(img.width * scale)),
                          max(1, int(img.height * scale))), Image.BILINEAR)
        self._tkimg = ImageTk.PhotoImage(img)
        self.preview_label.config(image=self._tkimg)

    def _loop(self):
        if self._stop:
            return
        frame = self.read_fn()
        if frame is not None:
            if self.test_mode:
                # Image brute : ni detection, ni trace, ni capture
                self._update_sharpness(frame)
            else:
                # Detection sur une copie reduite de moitie (CPU du Pi 3),
                # affichage en pleine definition
                half = cv2.resize(frame, (frame.shape[1] // 2, frame.shape[0] // 2),
                                  interpolation=cv2.INTER_AREA)
                rect = self._detect_rectangle(half)
                if rect is not None:
                    cv2.drawContours(frame, [rect * 2], -1, (0, 255, 0), 6)
                    self._stable_count += 1
                    self.status.config(
                        text=f"Etiquette detectee... {self._stable_count}/{config.RECT_STABLE_FRAMES}",
                        fg=config.COLOR_SUCCESS,
                    )
                    if (self._stable_count >= config.RECT_STABLE_FRAMES
                            and not self._capturing
                            and time.time() - self._last_capture > 2):
                        self._capturing = True
                        threading.Thread(target=self._do_capture, daemon=True).start()
                else:
                    self._stable_count = max(0, self._stable_count - 1)
                    self.status.config(text="Recherche d'une etiquette...", fg="white")

            self._show_frame(frame)

        self.after(30, self._loop)

    def _do_capture(self):
        try:
            data = self.capture_fn()
            if not data:
                return
            taken_at = datetime.now()
            dest, on_usb = usb_manager.save_photo(data, taken_at)
            self.after(0, lambda: self._show_flash(on_usb, dest))
        finally:
            self._last_capture = time.time()
            self._stable_count = 0
            self._capturing = False

    def _show_flash(self, on_usb: bool, dest: Path):
        self.flash.place(relx=0, rely=0, relwidth=1, relheight=1)
        msg = "Photo enregistree sur USB" if on_usb else "USB absente : photo en attente"
        lbl = tk.Label(self.flash, text=msg, bg="white",
                       fg=config.COLOR_SUCCESS if on_usb else config.COLOR_WARNING,
                       font=config.FONT_BIG)
        lbl.place(relx=0.5, rely=0.5, anchor="center")
        self.after(700, lambda: (lbl.destroy(), self.flash.place_forget()))

    def _back(self):
        self.destroy_camera()
        self.on_done()

    def destroy_camera(self):
        self._stop = True
        try:
            if HAS_PICAMERA:
                self.picam.stop()
                self.picam.close()
            else:
                self.cap.release()
        except Exception:
            pass
