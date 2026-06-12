"""Ecran parametres : gerer les appareils, lancer purge, export PDF, quitter."""
import tkinter as tk
import sys
import threading
from datetime import date
from . import config, database, pdf_export
from .ui_common import (make_button, text_popup, numpad_popup, style_popup,
                        info, confirm, error)


def _pick_device(parent, sensor, devices, on_done):
    """Popup de selection d'un appareil pour un capteur BLE."""
    pick = tk.Toplevel(parent)
    pick.configure(bg=config.COLOR_BG)
    pick.transient(parent)
    pick.grab_set()
    pick.overrideredirect(True)
    style_popup(pick, config.COLOR_SUCCESS)
    h = min(90 + len(devices) * 54 + 54, 400)
    w = 380
    x = (config.SCREEN_W - w) // 2
    y = (config.SCREEN_H - h) // 2
    pick.geometry(f"{w}x{h}+{x}+{y}")

    tk.Label(pick, text=f"Assigner '{sensor['label']}' a :",
             bg=config.COLOR_BG, fg=config.COLOR_FG,
             font=config.FONT_MED).pack(pady=8)

    def choose(device_id):
        database.update_ble_sensor(sensor["id"], sensor["label"], device_id)
        pick.destroy()
        on_done()

    for d in devices:
        tk.Button(pick, text=d["name"], font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg=config.COLOR_FG, bd=0,
                  padx=12, pady=8,
                  command=lambda did=d["id"]: choose(did)
                  ).pack(fill="x", padx=16, pady=2)

    tk.Button(pick, text="— Desassigner —", font=config.FONT_SMALL,
              bg=config.COLOR_DANGER, fg="white", bd=0, padx=12, pady=6,
              command=lambda: choose(None)
              ).pack(fill="x", padx=16, pady=(6, 8))


class SettingsScreen(tk.Frame):
    def __init__(self, master, on_done):
        super().__init__(master, bg=config.COLOR_BG)
        self.on_done = on_done
        self.pack(fill="both", expand=True)

        header = tk.Frame(self, bg=config.COLOR_BG)
        header.pack(fill="x", padx=12, pady=8)
        tk.Button(header, text="← Retour", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
                  command=self._back).pack(side="left")
        tk.Label(header, text="Parametres", bg=config.COLOR_BG,
                 fg=config.COLOR_FG, font=config.FONT_TITLE
                 ).pack(side="left", padx=16)

        tk.Label(self, text="Appareils enregistres", bg=config.COLOR_BG,
                 fg=config.COLOR_MUTED, font=config.FONT_MED
                 ).pack(anchor="w", padx=20, pady=(4, 2))

        self.list_frame = tk.Frame(self, bg=config.COLOR_BG)
        self.list_frame.pack(fill="both", expand=True, padx=20)

        actions = tk.Frame(self, bg=config.COLOR_BG)
        actions.pack(fill="x", padx=20, pady=4)
        make_button(actions, "+ Ajouter", self._add,
                    bg=config.COLOR_PRIMARY, font=config.FONT_MED
                    ).pack(expand=True, fill="x", padx=3)

        actions2 = tk.Frame(self, bg=config.COLOR_BG)
        actions2.pack(fill="x", padx=20, pady=4)
        make_button(actions2, "📡 Capteurs BLE", self._ble_config,
                    bg=config.COLOR_CARD, font=config.FONT_MED
                    ).pack(side="left", expand=True, fill="x", padx=3)
        make_button(actions2, "📄 Export PDF du mois", self._export_pdf,
                    bg=config.COLOR_SUCCESS, font=config.FONT_MED
                    ).pack(side="right", expand=True, fill="x", padx=3)

        actions3 = tk.Frame(self, bg=config.COLOR_BG)
        actions3.pack(fill="x", padx=20, pady=(0, 6))
        make_button(actions3, "📷 Test camera", self._test_camera,
                    bg=config.COLOR_CARD, font=config.FONT_MED
                    ).pack(side="left", expand=True, fill="x", padx=3)
        make_button(actions3, "Quitter l'appli", self._quit,
                    bg=config.COLOR_DANGER, font=config.FONT_MED
                    ).pack(side="right", expand=True, fill="x", padx=3)

        self._render()

    def _render(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        devices = database.list_devices()
        if not devices:
            tk.Label(self.list_frame, text="(aucun appareil)", bg=config.COLOR_BG,
                     fg=config.COLOR_MUTED, font=config.FONT_MED).pack(pady=20)
            return
        for d in devices:
            row = tk.Frame(self.list_frame, bg=config.COLOR_CARD)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=d["name"], bg=config.COLOR_CARD, fg=config.COLOR_FG,
                     font=config.FONT_MED, anchor="w"
                     ).pack(side="left", padx=12, pady=8, expand=True, fill="x")
            tk.Label(row, text=f"{d['temp_min']:g}° / {d['temp_max']:g}°",
                     bg=config.COLOR_CARD, fg=config.COLOR_MUTED,
                     font=config.FONT_SMALL).pack(side="left", padx=8)
            tk.Button(row, text="Modifier", font=config.FONT_SMALL,
                      bg=config.COLOR_PRIMARY, fg="white", bd=0, padx=8,
                      command=lambda x=d: self._edit(x)).pack(side="right", padx=4, pady=4)
            tk.Button(row, text="🗑", font=config.FONT_MED, bg=config.COLOR_DANGER,
                      fg="white", bd=0, width=3,
                      command=lambda i=d["id"], n=d["name"]: self._delete(i, n)
                      ).pack(side="right", padx=4, pady=4)

    def _add(self):
        name = text_popup(self, "Nom de l'appareil")
        if not name:
            return
        tmin = numpad_popup(self, f"Temperature MIN pour '{name}' (°C)")
        if tmin is None or tmin == "":
            return
        tmax = numpad_popup(self, f"Temperature MAX pour '{name}' (°C)")
        if tmax is None or tmax == "":
            return
        try:
            tmin_v, tmax_v = float(tmin), float(tmax)
        except ValueError:
            error(self, "Erreur", "Temperatures invalides.")
            return
        if tmin_v >= tmax_v:
            error(self, "Erreur", "MIN doit etre < MAX.")
            return
        try:
            database.add_device(name, tmin_v, tmax_v)
        except Exception as e:
            error(self, "Erreur", str(e))
            return
        self._render()

    def _edit(self, d):
        name = text_popup(self, "Nom de l'appareil", initial=d["name"])
        if not name:
            return
        tmin = numpad_popup(self, f"MIN (°C)", initial=f"{d['temp_min']:g}")
        if tmin is None or tmin == "":
            return
        tmax = numpad_popup(self, f"MAX (°C)", initial=f"{d['temp_max']:g}")
        if tmax is None or tmax == "":
            return
        try:
            tmin_v, tmax_v = float(tmin), float(tmax)
        except ValueError:
            error(self, "Erreur", "Temperatures invalides.")
            return
        if tmin_v >= tmax_v:
            error(self, "Erreur", "MIN doit etre < MAX.")
            return
        database.update_device(d["id"], name, tmin_v, tmax_v)
        self._render()

    def _delete(self, device_id, name):
        if confirm(self, "Supprimer",
                   f"Supprimer '{name}' ? Tous ses releves seront aussi supprimes."):
            database.delete_device(device_id)
            self._render()

    def _ble_config(self):
        """Popup de configuration des capteurs BLE."""
        from . import ble_reader

        top = tk.Toplevel(self)
        top.configure(bg=config.COLOR_BG)
        top.transient(self)
        top.grab_set()
        top.overrideredirect(True)
        style_popup(top)

        sensors = database.list_ble_sensors()
        h = max(300, 80 + len(sensors) * 90 + 90)
        w = 460
        x = (config.SCREEN_W - w) // 2
        y = (config.SCREEN_H - h) // 2
        top.geometry(f"{w}x{h}+{x}+{y}")

        # Titre
        hdr = tk.Frame(top, bg=config.COLOR_BG)
        hdr.pack(fill="x", padx=10, pady=8)
        tk.Label(hdr, text="Capteurs BLE", bg=config.COLOR_BG,
                 fg=config.COLOR_FG, font=config.FONT_BIG).pack(side="left")
        tk.Button(hdr, text="✕", bg=config.COLOR_DANGER, fg="white",
                  font=config.FONT_MED, bd=0, padx=12,
                  command=top.destroy).pack(side="right")

        body = tk.Frame(top, bg=config.COLOR_BG)
        body.pack(fill="both", expand=True, padx=10)

        status_var = tk.StringVar()
        status_lbl = None  # sera defini apres le bouton

        def render():
            for w in body.winfo_children():
                w.destroy()
            cur_sensors = database.list_ble_sensors()
            devices = database.list_devices()
            for s in cur_sensors:
                row = tk.Frame(body, bg=config.COLOR_CARD)
                row.pack(fill="x", pady=3)

                info_f = tk.Frame(row, bg=config.COLOR_CARD)
                info_f.pack(side="left", fill="x", expand=True, padx=8, pady=6)
                tk.Label(info_f, text=s["label"], bg=config.COLOR_CARD,
                         fg=config.COLOR_FG, font=config.FONT_MED,
                         anchor="w").pack(anchor="w")
                tk.Label(info_f, text=s["mac"], bg=config.COLOR_CARD,
                         fg=config.COLOR_MUTED, font=config.FONT_SMALL,
                         anchor="w").pack(anchor="w")

                assigned = s["device_name"] or "non assigne"
                tk.Label(row, text=assigned, bg=config.COLOR_CARD,
                         fg=config.COLOR_SUCCESS if s["device_id"] else config.COLOR_WARNING,
                         font=config.FONT_SMALL, width=12, anchor="w",
                         ).pack(side="left", padx=4)

                def pick(sensor=s, devs=devices):
                    _pick_device(top, sensor, devs, render)

                tk.Button(row, text="Assigner", font=config.FONT_SMALL,
                          bg=config.COLOR_PRIMARY, fg="white", bd=0,
                          padx=8, pady=4,
                          command=pick).pack(side="right", padx=6, pady=6)

        render()

        # Bouton Lire maintenant
        bottom = tk.Frame(top, bg=config.COLOR_BG)
        bottom.pack(fill="x", padx=10, pady=6)

        status_lbl = tk.Label(bottom, textvariable=status_var, bg=config.COLOR_BG,
                              fg=config.COLOR_MUTED, font=config.FONT_SMALL,
                              wraplength=430, justify="left")
        status_lbl.pack(side="bottom", anchor="w", pady=(4, 0))

        def read_now():
            cur_sensors = database.list_ble_sensors()
            macs = [s["mac"] for s in cur_sensors if s["device_id"]]
            if not macs:
                status_var.set("⚠ Aucun capteur assigne a un appareil")
                return
            status_var.set("Lecture BLE en cours... (max 25 s)")
            status_lbl.config(fg=config.COLOR_WARNING)

            # Le thread BLE ne touche pas a l'UI : resultat lu par polling
            box = {}

            def do():
                with config.BLE_LOCK:
                    try:
                        results = ble_reader.read_temperatures(macs)
                        # Mode TEST : affichage seulement, rien en base
                        found = []
                        for s in cur_sensors:
                            if not s["device_id"]:
                                continue
                            temp = results.get(s["mac"].lower())
                            if temp is not None:
                                found.append(f"{s['device_name']}: {temp:.1f}°C")
                        if found:
                            box["msg"] = "✓ Test (non enregistre) — " + "   ".join(found)
                            box["fg"] = config.COLOR_SUCCESS
                        else:
                            box["msg"] = "✗ Aucun capteur detecte (hors portee ?)"
                            box["fg"] = config.COLOR_DANGER
                    except Exception as e:
                        box["msg"] = f"Erreur: {e}"
                        box["fg"] = config.COLOR_DANGER
                box["done"] = True

            def poll():
                if not top.winfo_exists():
                    return
                if not box.get("done"):
                    top.after(200, poll)
                    return
                status_var.set(box["msg"])
                status_lbl.config(fg=box["fg"])

            threading.Thread(target=do, daemon=True).start()
            top.after(200, poll)

        tk.Button(bottom, text="🔍 Tester la lecture (sans enregistrer)",
                  font=config.FONT_MED,
                  bg=config.COLOR_PRIMARY, fg="white", bd=0, padx=12, pady=8,
                  command=read_now).pack(fill="x")

        self.wait_window(top)

    def _export_pdf(self):
        today = date.today()
        try:
            path = pdf_export.export_month_pdf(today.year, today.month)
        except Exception as e:
            error(self, "Erreur export", str(e))
            return
        if path is None:
            error(self, "USB absente", "Branchez une cle USB pour exporter.")
            return
        info(self, "Export OK", f"Fichier enregistre :\n{path.name}")

    def _test_camera(self):
        """Ouvre la camera en test de nettete : preview + score, sans capture."""
        from .camera_scan import CameraScanScreen
        app = self.master

        def back_to_settings():
            app._clear()
            app.current = SettingsScreen(app, app.show_menu)

        self.destroy()
        app.current = CameraScanScreen(app, back_to_settings, test_mode=True)

    def _quit(self):
        if confirm(self, "Quitter", "Fermer l'application ?"):
            sys.exit(0)

    def _back(self):
        self.destroy()
        self.on_done()
