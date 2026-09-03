"""Menu principal + routeur d'écrans."""
import tkinter as tk
import os
import threading
import time
from datetime import date, datetime, timedelta

from . import (config, database, heartbeat, remote_lock, screen, updater,
               usb_manager)
from .camera_scan import CameraScanScreen
from .ui_temperature import TemperatureScreen
from .ui_history import HistoryScreen
from .ui_settings import SettingsScreen
from .ui_setup import SetupWizard
from .ui_reception import ReceptionScreen


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Traceability")
        self.configure(bg=config.COLOR_BG)

        # Lire les vraies dimensions de l'ecran
        self.update_idletasks()
        config.SCREEN_W = self.winfo_screenwidth()
        config.SCREEN_H = self.winfo_screenheight()

        # Plein ecran + passe au-dessus de la taskbar
        self.attributes("-fullscreen", True)
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()

        self.current = None
        self._lock_overlay = None

        # Reglages a distance memorises (couleurs...) : appliques AVANT de
        # construire les ecrans pour qu'ils prennent effet des le demarrage.
        _locked_cache, _msg_cache, _cfg_cache = remote_lock.cached_state()
        remote_lock.apply_config(_cfg_cache)

        if not database.get_meta("setup_done"):
            SetupWizard(self, self.show_menu)
        else:
            self.show_menu()

        # Verrou a distance : si le dernier etat connu etait « bloque », on
        # affiche le blocage immediatement (avant meme le reseau) -> survit
        # au redemarrage et hors ligne.
        if _locked_cache:
            self._show_lock_overlay(_msg_cache)
        self.after(2000, self._lock_tick)

        # Mise a jour automatique du code depuis GitHub
        self.after(60_000, self._update_tick)

        # Signe de vie Telegram (en ligne + version)
        self.after(20_000, self._heartbeat_tick)

        # Veille de l'ecran, geree par l'appli (voir _sleep)
        self._sleep_overlay = None
        self._last_touch = time.time()
        screen.disable_os_blanking()
        # Rallumer systematiquement au demarrage : une mise a jour (ou un
        # redemarrage) peut survenir pendant la veille, et le retroeclairage
        # resterait eteint alors que l'appli se croit reveillee.
        threading.Thread(target=screen.on, daemon=True).start()
        for evt in ("<Button-1>", "<ButtonRelease-1>", "<Key>"):
            self.bind_all(evt, self._note_activity, add="+")
        self.after(30_000, self._sleep_tick)

        # Sync USB periodique
        self.after(1500, self._periodic_sync)

        # Scheduler BLE : verifie toutes les minutes si c'est l'heure de lire
        self.after(10_000, self._ble_tick)

        # Purge automatique quotidienne des photos > 6 mois
        self.after(8_000, self._purge_tick)

    def _clear(self):
        if self.current and self.current.winfo_exists():
            self.current.destroy()
        self.current = None

    def show_menu(self):
        self._clear()
        self.current = MainMenu(self, self)
        self.after(800, self._check_ble_alert)

    def show_scan(self):
        self._clear()
        self.current = CameraScanScreen(self, self.show_menu)

    def show_temperature(self):
        self._clear()
        self.current = TemperatureScreen(self, self.show_menu)

    def show_reception(self):
        self._clear()
        self.current = ReceptionScreen(self, self.show_menu)

    def show_history(self):
        self._clear()
        self.current = HistoryScreen(self, self.show_menu)

    def show_settings(self):
        self._clear()
        self.current = SettingsScreen(self, self.show_menu)

    def _periodic_sync(self):
        try:
            usb_manager.sync_pending()
        except Exception:
            pass
        self.after(30_000, self._periodic_sync)

    # --- Scheduler BLE 3h du matin ---

    def _ble_tick(self):
        now = datetime.now()
        if now.hour == 3 and now.minute < 5:
            today = date.today().isoformat()
            if database.get_meta("ble_auto_date") != today:
                database.set_meta("ble_auto_date", today)
                threading.Thread(target=self._do_ble_auto, daemon=True).start()
        self.after(60_000, self._ble_tick)

    def _do_ble_auto(self):
        from . import sensor_reader
        sensors = database.list_ble_sensors()
        if not any(s["device_id"] for s in sensors):
            return
        try:
            with config.BLE_LOCK:
                results, _ = sensor_reader.read_all(sensors)
        except Exception:
            return
        today = date.today()
        devices = {d["id"]: d for d in database.list_devices()}
        alerts = []
        for s in sensors:
            if not s["device_id"]:
                continue
            temp = results.get(s["mac"].lower())
            if temp is not None:
                database.save_reading(s["device_id"], today, temp)
                dev = devices.get(s["device_id"])
                if dev and temp > dev["temp_max"]:
                    alerts.append(
                        f"{dev['name']} : {temp:.1f}°C  (max autorise : {dev['temp_max']:g}°C)"
                    )
        if alerts:
            database.set_meta("ble_temp_alert", "\n".join(alerts))

    # --- Alarme temperature ---

    def _check_ble_alert(self):
        msg = database.get_meta("ble_temp_alert")
        if msg:
            database.set_meta("ble_temp_alert", "")
            self._show_alarm(msg)

    def _show_alarm(self, message):
        overlay = tk.Frame(self, bg=config.COLOR_DANGER)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        overlay.lift()

        tk.Label(overlay, text="⚠  ALERTE TEMPERATURE",
                 bg=config.COLOR_DANGER, fg="white",
                 font=config.FONT_TITLE).pack(pady=(60, 24))

        for line in message.split("\n"):
            tk.Label(overlay, text=line,
                     bg=config.COLOR_DANGER, fg="white",
                     font=config.FONT_BIG).pack(pady=4)

        tk.Label(overlay,
                 text="\nTemperature superieure au seuil !\nVerifiez vos appareils.",
                 bg=config.COLOR_DANGER, fg="white",
                 font=config.FONT_MED, justify="center").pack(pady=16)

        tk.Button(overlay, text="   OK   ", font=config.FONT_BIG,
                  bg="white", fg=config.COLOR_DANGER, bd=0,
                  padx=40, pady=16,
                  command=overlay.destroy).pack()

    # --- Purge automatique ---

    def _purge_tick(self):
        now = datetime.now()
        if now.hour == 2 and now.minute < 5:
            today = date.today().isoformat()
            if database.get_meta("purge_last_date") != today:
                database.set_meta("purge_last_date", today)
                threading.Thread(target=self._do_purge, daemon=True).start()
        self.after(60_000, self._purge_tick)  # verifie chaque minute

    def _do_purge(self):
        try:
            from . import purge
            purge.purge_old_photos()
        except Exception:
            pass

    # --- Signe de vie ---

    def _heartbeat_tick(self):
        """Envoi en tache de fond : le reseau ne doit jamais figer l'ecran."""
        threading.Thread(target=self._do_heartbeat, daemon=True).start()
        self.after(config.HEARTBEAT_CHECK_S * 1000, self._heartbeat_tick)

    def _do_heartbeat(self):
        try:
            heartbeat.tick()
        except Exception:
            pass

    # --- Veille de l'ecran ---

    def _note_activity(self, _event=None):
        self._last_touch = time.time()

    def _sleep_tick(self):
        if (config.SCREEN_OFF_S and self._sleep_overlay is None
                and time.time() - self._last_touch > config.SCREEN_OFF_S):
            self._sleep()
        self.after(10_000, self._sleep_tick)

    def _sleep(self):
        """Met l'ecran en veille : voile noir + extinction du retroeclairage.

        Le voile est essentiel : il ABSORBE le contact qui reveille l'appareil,
        qui sinon declencherait le bouton situe sous le doigt et ferait
        atterrir l'operateur dans un menu au hasard.
        """
        overlay = tk.Frame(self, bg="black", cursor="none")
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        overlay.lift()
        overlay.bind("<Button-1>", lambda e: "break")   # le contact ne passe pas
        overlay.bind("<ButtonRelease-1>", self._wake)
        self._sleep_overlay = overlay
        threading.Thread(target=screen.off, daemon=True).start()

    def _wake(self, _event=None):
        """Premier contact : on rallume, sans rien declencher d'autre."""
        if self._sleep_overlay is not None:
            self._sleep_overlay.destroy()
            self._sleep_overlay = None
        self._last_touch = time.time()
        threading.Thread(target=screen.on, daemon=True).start()
        return "break"

    # --- Mise a jour automatique ---

    def _update_ready(self):
        """Conditions pour appliquer une mise a jour maintenant : appli au
        repos (menu principal) et, en mode « auto », heures creuses — sauf si
        la mise a jour attend depuis trop longtemps (Pi eteint la nuit)."""
        if not isinstance(self.current, MainMenu):
            return False            # ne jamais interrompre un scan ou une mesure
        mode = updater.mode()
        if mode == "off":
            return False
        if mode == "now":
            return True
        start, end = config.UPDATE_QUIET_HOURS
        if start <= datetime.now().hour < end:
            return True
        since = database.get_meta("update_pending_since", "")
        if since:
            try:
                waited = datetime.now() - datetime.fromisoformat(since)
                return waited.total_seconds() > config.UPDATE_MAX_PENDING_H * 3600
            except ValueError:
                return False
        return False

    def _update_tick(self):
        """Verifie la disponibilite d'une mise a jour, en tache de fond."""
        box = {}

        def do():
            try:
                box["target"] = updater.check_available()
            except Exception:
                box["target"] = None
            box["done"] = True

        def poll():
            if not self.winfo_exists():
                return
            if not box.get("done"):
                self.after(500, poll)
                return
            target = box.get("target")
            if target:
                # memoriser depuis quand elle attend (pour les Pi eteints la nuit)
                if not database.get_meta("update_pending_since", ""):
                    database.set_meta("update_pending_since",
                                      datetime.now().isoformat())
                if self._update_ready():
                    self._apply_update(target)
                    return
            else:
                database.set_meta("update_pending_since", "")
            self.after(config.UPDATE_CHECK_S * 1000, self._update_tick)

        threading.Thread(target=do, daemon=True).start()
        self.after(500, poll)

    def _apply_update(self, target):
        """Applique la mise a jour puis redemarre l'appli (systemd relance)."""
        overlay = tk.Frame(self, bg=config.COLOR_BG)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        overlay.lift()
        tk.Label(overlay, text="Mise à jour en cours…", bg=config.COLOR_BG,
                 fg=config.COLOR_FG, font=config.FONT_TITLE).pack(pady=(150, 12))
        tk.Label(overlay, text="L'application va redémarrer automatiquement.",
                 bg=config.COLOR_BG, fg=config.COLOR_MUTED,
                 font=config.FONT_MED).pack()
        box = {}

        def do():
            try:
                box["ok"] = updater.perform_update(target)
            except Exception:
                box["ok"] = False
            box["done"] = True

        def poll():
            if not box.get("done"):
                self.after(500, poll)
                return
            if box.get("ok"):
                database.set_meta("update_pending_since", "")
                os._exit(updater.RESTART_EXIT_CODE)  # systemd relance le service
            overlay.destroy()  # echec : on reste sur l'ancienne version
            self.after(config.UPDATE_CHECK_S * 1000, self._update_tick)

        threading.Thread(target=do, daemon=True).start()
        self.after(500, poll)

    # --- Verrou a distance ---

    def _lock_tick(self):
        """Verifie l'etat distant en tache de fond (n'gele jamais l'UI) et
        applique le resultat (affiche/retire le blocage)."""
        box = {}

        def do():
            try:
                box["res"] = remote_lock.refresh()
            except Exception:
                box["res"] = None

        def poll():
            if not self.winfo_exists():
                return
            if "res" not in box:
                self.after(200, poll)
                return
            if box["res"] is not None:
                locked, message = box["res"]
                if locked:
                    self._show_lock_overlay(message)
                else:
                    self._hide_lock_overlay()
            self.after(config.REMOTE_POLL_S * 1000, self._lock_tick)

        threading.Thread(target=do, daemon=True).start()
        self.after(200, poll)

    def _show_lock_overlay(self, message):
        """Overlay plein ecran non fermable : bloque toute l'appli."""
        if self._lock_overlay is not None and self._lock_overlay.winfo_exists():
            # deja affiche : on met juste le message a jour
            self._lock_msg.config(text=message or "Application suspendue.")
            self._lock_overlay.lift()
            return
        ov = tk.Frame(self, bg=config.COLOR_BG)
        ov.place(relx=0, rely=0, relwidth=1, relheight=1)
        ov.lift()
        tk.Label(ov, text="🔒", bg=config.COLOR_BG, fg=config.COLOR_DANGER,
                 font=("DejaVu Sans", 64)).pack(pady=(70, 10))
        self._lock_msg = tk.Label(
            ov, text=message or "Application suspendue.",
            bg=config.COLOR_BG, fg=config.COLOR_FG, font=config.FONT_TITLE,
            wraplength=config.SCREEN_W - 80, justify="center")
        self._lock_msg.pack(pady=10, padx=40)
        self._lock_overlay = ov

    def _hide_lock_overlay(self):
        if self._lock_overlay is not None:
            if self._lock_overlay.winfo_exists():
                self._lock_overlay.destroy()
            self._lock_overlay = None


class MainMenu(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=config.COLOR_BG)
        self.app = app
        self.pack(fill="both", expand=True)

        # Header
        header = tk.Frame(self, bg=config.COLOR_BG)
        header.pack(fill="x", padx=16, pady=(10, 4))
        tk.Label(header, text="Traceability", bg=config.COLOR_BG,
                 fg=config.COLOR_FG, font=config.FONT_TITLE).pack(side="left")
        self.usb_lbl = tk.Label(header, text="USB ✗", bg=config.COLOR_BG,
                                fg=config.COLOR_WARNING, font=config.FONT_SMALL)
        self.usb_lbl.pack(side="right")
        self.clock_lbl = tk.Label(header, text="", bg=config.COLOR_BG,
                                  fg=config.COLOR_MUTED, font=config.FONT_SMALL)
        self.clock_lbl.pack(side="right", padx=12)

        # Alerte releves manquants (veille)
        self.alert = tk.Label(self, text="", bg=config.COLOR_BG,
                              fg=config.COLOR_WARNING, font=config.FONT_MED)
        self.alert.pack(fill="x", padx=16)

        # Deux grosses cartes empilees l'une sur l'autre
        grid = tk.Frame(self, bg=config.COLOR_BG)
        grid.pack(fill="both", expand=True, padx=20, pady=6)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.columnconfigure(2, weight=1)
        grid.rowconfigure(0, weight=1)

        self._big_card(grid, "📦", "Réception",
                       "Température des produits livrés",
                       config.COLOR_WARNING, self.app.show_reception
                       ).grid(row=0, column=0, sticky="nsew", padx=8, pady=4)
        self._big_card(grid, "📷", "Scan ticket",
                       "Prendre une photo automatique",
                       config.COLOR_PRIMARY, self.app.show_scan
                       ).grid(row=0, column=1, sticky="nsew", padx=8, pady=4)
        self._big_card(grid, "🌡", "Relevé de température",
                       "Saisir les temperatures du jour",
                       config.COLOR_SUCCESS, self.app.show_temperature
                       ).grid(row=0, column=2, sticky="nsew", padx=8, pady=4)

        # Bas : historique + parametres
        bottom = tk.Frame(self, bg=config.COLOR_BG)
        bottom.pack(fill="x", padx=20, pady=(0, 10))
        tk.Button(bottom, text="📊 Historique", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=16, pady=10,
                  command=self.app.show_history).pack(side="left", expand=True, fill="x", padx=4)
        tk.Button(bottom, text="⚙ Paramètres", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=16, pady=10,
                  command=self.app.show_settings).pack(side="right", expand=True, fill="x", padx=4)

        self._refresh_status()
        self._check_alerts()

    def _big_card(self, parent, icon, title, subtitle, color, command):
        card = tk.Frame(parent, bg=color, cursor="hand2")
        card.bind("<Button-1>", lambda e: command())
        tk.Label(card, text=icon, bg=color, fg="white",
                 font=("DejaVu Sans", 48)).pack(pady=(20, 0))
        tk.Label(card, text=title, bg=color, fg="white",
                 font=config.FONT_BIG, wraplength=220).pack()
        tk.Label(card, text=subtitle, bg=color, fg="white",
                 font=config.FONT_SMALL, wraplength=220).pack(pady=(4, 0))
        for w in card.winfo_children():
            w.bind("<Button-1>", lambda e: command())
        return card

    def _refresh_status(self):
        usb_ok = usb_manager.find_usb_mount() is not None
        self.clock_lbl.config(text=datetime.now().strftime("%d/%m/%Y  %H:%M"))
        self.usb_lbl.config(
            text="USB ✓" if usb_ok else "USB ✗",
            fg=config.COLOR_SUCCESS if usb_ok else config.COLOR_WARNING,
        )
        self.after(10_000, self._refresh_status)

    def _check_alerts(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        missing = []
        for info in database.last_reading_date_per_device():
            if info["last_date"] is None or info["last_date"] < yesterday:
                missing.append(info["name"])
        if missing:
            self.alert.config(
                text=f"⚠ Relevé manquant pour : {', '.join(missing)}"
            )
        else:
            self.alert.config(text="")
