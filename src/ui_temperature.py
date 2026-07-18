"""Ecran de releve de temperature : lecture BLE instantanee + correction manuelle."""
import tkinter as tk
import threading
from datetime import date
from . import config, database
from .ui_common import numpad_popup


class TemperatureScreen(tk.Frame):
    def __init__(self, master, on_done):
        super().__init__(master, bg=config.COLOR_BG)
        self.on_done = on_done
        self.pack(fill="both", expand=True)
        self.today = date.today()

        # Header
        header = tk.Frame(self, bg=config.COLOR_BG)
        header.pack(fill="x", padx=12, pady=8)
        tk.Button(header, text="← Retour", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
                  command=self._back).pack(side="left")
        tk.Label(header, text=f"Temperatures — {self.today.strftime('%d/%m/%Y')}",
                 bg=config.COLOR_BG, fg=config.COLOR_FG,
                 font=config.FONT_MED).pack(side="left", padx=10)

        # Barre de statut BLE
        self.status_var = tk.StringVar(value="Lecture BLE en cours...")
        self.status_lbl = tk.Label(self, textvariable=self.status_var,
                                   bg=config.COLOR_BG, fg=config.COLOR_WARNING,
                                   font=config.FONT_SMALL)
        self.status_lbl.pack(fill="x", padx=16, pady=(0, 4))

        # En-tetes colonnes
        head = tk.Frame(self, bg=config.COLOR_BG)
        head.pack(fill="x", padx=12)
        tk.Label(head, text="Appareil", bg=config.COLOR_BG, fg=config.COLOR_MUTED,
                 font=config.FONT_SMALL, width=16, anchor="w"
                 ).pack(side="left", padx=4)
        tk.Label(head, text="Seuils", bg=config.COLOR_BG, fg=config.COLOR_MUTED,
                 font=config.FONT_SMALL, width=9, anchor="w"
                 ).pack(side="left", padx=4)
        tk.Label(head, text="°C", bg=config.COLOR_BG, fg=config.COLOR_MUTED,
                 font=config.FONT_SMALL, anchor="w"
                 ).pack(side="left", padx=4)

        # Tableau scrollable
        container = tk.Frame(self, bg=config.COLOR_BG)
        container.pack(fill="both", expand=True, padx=12, pady=4)
        canvas = tk.Canvas(container, bg=config.COLOR_BG, highlightthickness=0)
        sb = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.rows_frame = tk.Frame(canvas, bg=config.COLOR_BG)
        self.rows_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.rows_frame, anchor="nw", width=440)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.rows = {}
        self._ble_cancel = threading.Event()
        self._render()
        self._start_ble_scan()

    # --- Affichage ---

    def _render(self):
        for w in self.rows_frame.winfo_children():
            w.destroy()
        self.rows = {}
        for d in database.list_devices():
            reading = database.get_reading(d["id"], self.today)
            self._make_row(d, reading)

    def _make_row(self, device, reading):
        row = tk.Frame(self.rows_frame, bg=config.COLOR_CARD)
        row.pack(fill="x", pady=3)

        tk.Label(row, text=device["name"][:16], bg=config.COLOR_CARD, fg=config.COLOR_FG,
                 font=config.FONT_MED, width=16, anchor="w"
                 ).pack(side="left", padx=8, pady=8)
        tk.Label(row, text=f"{device['temp_min']:g}/{device['temp_max']:g}°",
                 bg=config.COLOR_CARD, fg=config.COLOR_MUTED,
                 font=config.FONT_SMALL, width=9, anchor="w"
                 ).pack(side="left", padx=2)

        temp_var = tk.StringVar()
        if reading:
            temp_var.set(f"{reading['temperature']:g}")

        temp_lbl = tk.Label(row, textvariable=temp_var, bg=config.COLOR_BG,
                            fg=config.COLOR_FG, font=config.FONT_BIG,
                            width=6, anchor="center")
        temp_lbl.pack(side="left", padx=6, pady=4)

        alert_lbl = tk.Label(row, text="", bg=config.COLOR_CARD,
                             fg=config.COLOR_DANGER, font=config.FONT_SMALL)
        alert_lbl.pack(side="left", padx=4)

        def refresh_alert():
            try:
                v = float(temp_var.get())
            except (ValueError, TypeError):
                alert_lbl.config(text="")
                temp_lbl.config(bg=config.COLOR_BG, fg=config.COLOR_FG)
                return
            if v < device["temp_min"] or v > device["temp_max"]:
                alert_lbl.config(text="⚠ Hors seuils")
                temp_lbl.config(bg=config.COLOR_DANGER, fg="white")
            else:
                alert_lbl.config(text="✓")
                temp_lbl.config(bg=config.COLOR_SUCCESS, fg="white")

        refresh_alert()

        def edit():
            v = numpad_popup(self, f"Temperature '{device['name']}' (°C)",
                             initial=temp_var.get())
            if v is None or v == "":
                return
            try:
                val = float(v)
            except ValueError:
                return
            database.save_reading(device["id"], self.today, val)
            temp_var.set(f"{val:g}")
            refresh_alert()

        tk.Button(row, text="Saisir", font=config.FONT_MED,
                  bg=config.COLOR_PRIMARY, fg="white", bd=0, padx=10, pady=6,
                  command=edit).pack(side="right", padx=6, pady=4)

        self.rows[device["id"]] = (temp_var, refresh_alert)

    # --- Lecture BLE ---

    def _start_ble_scan(self):
        sensors = database.list_ble_sensors()
        if not any(s["device_id"] for s in sensors):
            self.status_var.set("Aucun capteur configure (voir Parametres)")
            self.status_lbl.config(fg=config.COLOR_MUTED)
            return
        self.status_var.set("Lecture des capteurs en cours...")
        self.status_lbl.config(fg=config.COLOR_WARNING)

        # Le thread capteurs ne touche JAMAIS a l'UI (Tk n'est pas thread-safe) :
        # il depose son resultat dans box, l'UI le lit par polling.
        cancel = self._ble_cancel
        box = {}

        def do():
            with config.BLE_LOCK:
                if cancel.is_set():
                    box["done"] = True
                    return
                from . import sensor_reader
                try:
                    box["results"], box["err"] = sensor_reader.read_all(
                        sensors, cancel=cancel)
                except Exception as e:
                    box["err"] = str(e)
            box["done"] = True

        def poll():
            if cancel.is_set() or not self.winfo_exists():
                return
            if not box.get("done"):
                self.after(200, poll)
                return
            if box.get("results"):
                self._apply_results(sensors, box["results"])
            elif box.get("err"):
                self.status_var.set(f"Erreur capteurs : {box['err']}")
                self.status_lbl.config(fg=config.COLOR_DANGER)
            else:
                self._apply_results(sensors, {})

        threading.Thread(target=do, daemon=True).start()
        self.after(200, poll)

    def _apply_results(self, sensors, results):
        if not self.winfo_exists():
            return
        found = []
        for s in sensors:
            if not s["device_id"]:
                continue
            temp = results.get(s["mac"].lower())
            if temp is not None:
                database.save_reading(s["device_id"], self.today, temp)
                found.append(f"{s['device_name']}: {temp:.1f}°C")

        self._render()

        if found:
            self.status_var.set("✓ " + "   ".join(found))
            self.status_lbl.config(fg=config.COLOR_SUCCESS)
        else:
            self.status_var.set("✗ Aucun capteur detecte (hors portee ?)")
            self.status_lbl.config(fg=config.COLOR_DANGER)

    def _back(self):
        self._ble_cancel.set()  # stoppe le scan BLE en cours immediatement
        self.destroy()
        self.on_done()
