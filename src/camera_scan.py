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
        status_text = "MODE TEST — aucune photo enregistree" if test_mode else "Recherche d'une etiquette..."
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
        """Active l'autofocus continu si la camera le supporte (Camera v3,
        Arducam AF, modeles generiques...)."""
        try:
            from libcamera import controls
            self.picam.set_controls({"AfMode": controls.AfModeEnum.Continuous})
        except Exception:
            pass  # camera a focale fixe : on ignore

    def _init_camera(self):
        if HAS_PICAMERA:
            self.picam = Picamera2()
            cfg = self.picam.create_preview_configuration(
                main={"size": config.PREVIEW_RESOLUTION, "format": "RGB888"}
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
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.PREVIEW_RESOLUTION[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.PREVIEW_RESOLUTION[1])
            self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
            self.capture_fn = self._capture_opencv
            self.read_fn = self._read_opencv

    def _apply_rotation(self, rgb_array):
        """Applique CAMERA_ROTATION (0/90/180/270) sur un tableau numpy RGB."""
        if config.CAMERA_ROTATION == 0:
            return rgb_array
        img = Image.fromarray(rgb_array)
        # PIL rotate() est anti-horaire, donc on inverse le signe
        img = img.rotate(-config.CAMERA_ROTATION, expand=True)
        return np.array(img)

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
        # Declencher un cycle d'autofocus complet avant la photo (cameras AF)
        try:
            self.picam.autofocus_cycle()
        except Exception:
            time.sleep(0.8)  # focale fixe : on laisse juste l'expo se stabiliser
        arr = self.picam.capture_array()
        # Appliquer la rotation a la photo finale aussi
        if config.CAMERA_ROTATION != 0:
            img = Image.fromarray(arr).rotate(-config.CAMERA_ROTATION, expand=True)
        else:
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
        if config.CAMERA_ROTATION != 0:
            frame = cv2.cvtColor(
                self._apply_rotation(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)),
                cv2.COLOR_RGB2BGR)
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return buf.tobytes()

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
    def _loop(self):
        if self._stop:
            return
        frame = self.read_fn()
        if frame is not None:
            rect = self._detect_rectangle(frame)
            display = frame.copy()
            if rect is not None:
                cv2.drawContours(display, [rect], -1, (0, 255, 0), 4)
                self._stable_count += 1
                self.status.config(
                    text=f"Etiquette detectee... {self._stable_count}/{config.RECT_STABLE_FRAMES}",
                    fg=config.COLOR_SUCCESS,
                )
                if (self._stable_count >= config.RECT_STABLE_FRAMES
                        and not self._capturing
                        and time.time() - self._last_capture > 2):
                    if self.test_mode:
                        # Mode test : flash vert sans capture
                        self._stable_count = 0
                        self._last_capture = time.time()
                        self.after(0, self._show_test_flash)
                    else:
                        self._capturing = True
                        threading.Thread(target=self._do_capture, daemon=True).start()
            else:
                self._stable_count = max(0, self._stable_count - 1)
                self.status.config(text="Recherche d'une etiquette...", fg="white")

            img = Image.fromarray(display).resize((config.SCREEN_W, config.SCREEN_H))
            self._tkimg = ImageTk.PhotoImage(img)
            self.preview_label.config(image=self._tkimg)

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

    def _show_test_flash(self):
        """Flash vert en mode test : rectangle detecte, mais pas de capture."""
        self.flash.place(relx=0, rely=0, relwidth=1, relheight=1)
        lbl = tk.Label(self.flash, text="Rectangle detecte ✓\n(mode test — non enregistre)",
                       bg="white", fg=config.COLOR_SUCCESS, font=config.FONT_BIG,
                       justify="center")
        lbl.place(relx=0.5, rely=0.5, anchor="center")
        self.after(800, lambda: (lbl.destroy(), self.flash.place_forget()))

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
