"""Ecran d'assistant premier lancement : ajouter les appareils."""
import tkinter as tk
from . import config, database
from .ui_common import make_button, text_popup, numpad_popup, info, confirm


class SetupWizard(tk.Frame):
    def __init__(self, master, on_done):
        super().__init__(master, bg=config.COLOR_BG)
        self.on_done = on_done
        self.pack(fill="both", expand=True)

        tk.Label(self, text="Configuration initiale", bg=config.COLOR_BG,
                 fg=config.COLOR_FG, font=config.FONT_TITLE).pack(pady=(16, 4))
        tk.Label(self, text="Ajoutez vos frigos et congelateurs.",
                 bg=config.COLOR_BG, fg=config.COLOR_MUTED,
                 font=config.FONT_MED).pack(pady=(0, 8))

        self.list_frame = tk.Frame(self, bg=config.COLOR_BG)
        self.list_frame.pack(fill="both", expand=True, padx=20)

        actions = tk.Frame(self, bg=config.COLOR_BG)
        actions.pack(fill="x", padx=20, pady=12)
        make_button(actions, "+ Ajouter un appareil", self._add,
                    bg=config.COLOR_PRIMARY).pack(side="left", expand=True, fill="x", padx=4)
        make_button(actions, "Terminer", self._finish,
                    bg=config.COLOR_SUCCESS).pack(side="right", expand=True, fill="x", padx=4)

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
            row.pack(fill="x", pady=4)
            tk.Label(row, text=d["name"], bg=config.COLOR_CARD, fg=config.COLOR_FG,
                     font=config.FONT_MED, anchor="w").pack(side="left", padx=12, pady=10, expand=True, fill="x")
            tk.Label(row, text=f"{d['temp_min']:g}° / {d['temp_max']:g}°",
                     bg=config.COLOR_CARD, fg=config.COLOR_MUTED,
                     font=config.FONT_SMALL).pack(side="left", padx=8)
            tk.Button(row, text="🗑", font=config.FONT_MED, bg=config.COLOR_DANGER,
                      fg="white", bd=0, width=3,
                      command=lambda i=d["id"], n=d["name"]: self._delete(i, n)
                      ).pack(side="right", padx=8, pady=6)

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
            tmin_v = float(tmin)
            tmax_v = float(tmax)
        except ValueError:
            info(self, "Erreur", "Temperatures invalides.")
            return
        if tmin_v >= tmax_v:
            info(self, "Erreur", "MIN doit etre inferieur a MAX.")
            return
        try:
            database.add_device(name, tmin_v, tmax_v)
        except Exception as e:
            info(self, "Erreur", f"Impossible d'ajouter : {e}")
            return
        self._render()

    def _delete(self, device_id, name):
        if confirm(self, "Supprimer", f"Supprimer '{name}' ?"):
            database.delete_device(device_id)
            self._render()

    def _finish(self):
        if database.devices_count() == 0:
            info(self, "Vide", "Ajoutez au moins un appareil.")
            return
        database.set_meta("setup_done", "1")
        self.destroy()
        self.on_done()
