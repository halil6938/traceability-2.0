"""Menu principal + routeur d'écrans."""
import tkinter as tk
import threading
from datetime import date, datetime, timedelta
from . import config, database, usb_manager
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

        if not database.get_meta("setup_done"):
            SetupWizard(self, self.show_menu)
        else:
            self.show_menu()

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
        self._big_card(grid, "🌡", "Relevé de température",
                       "Saisir les temperatures du jour",
                       config.COLOR_SUCCESS, self.app.show_temperature
                       ).grid(row=0, column=1, sticky="nsew", padx=8, pady=4)
        self._big_card(grid, "📷", "Scan ticket",
                       "Prendre une photo automatique",
                       config.COLOR_PRIMARY, self.app.show_scan
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
