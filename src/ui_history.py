"""Ecran historique : Tickets (photos), Temperatures ou Receptions."""
import tkinter as tk
from datetime import date, datetime
from calendar import monthrange
from . import config, database, pdf_export
from .ui_common import make_button, numpad_popup, info, error, confirm

MONTHS = ["Janvier", "Fevrier", "Mars", "Avril", "Mai", "Juin",
          "Juillet", "Aout", "Septembre", "Octobre", "Novembre", "Decembre"]


# ---------------------------------------------------------------------------
# Landing
# ---------------------------------------------------------------------------

class HistoryScreen(tk.Frame):
    """Menu de choix : Tickets ou Temperatures."""

    def __init__(self, master, on_done):
        super().__init__(master, bg=config.COLOR_BG)
        self.on_done = on_done
        self.pack(fill="both", expand=True)

        header = tk.Frame(self, bg=config.COLOR_BG)
        header.pack(fill="x", padx=16, pady=(10, 4))
        tk.Button(header, text="← Retour", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
                  command=self._back).pack(side="left")
        tk.Label(header, text="Historique", bg=config.COLOR_BG,
                 fg=config.COLOR_FG, font=config.FONT_TITLE).pack(side="left", padx=12)

        grid = tk.Frame(self, bg=config.COLOR_BG)
        grid.pack(fill="both", expand=True, padx=20, pady=20)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.columnconfigure(2, weight=1)
        grid.rowconfigure(0, weight=1)

        self._big_card(grid, "📷", "Tickets",
                       "Consulter les photos de tickets",
                       config.COLOR_PRIMARY, self._show_tickets
                       ).grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self._big_card(grid, "🌡", "Temperatures",
                       "Tableau mensuel des releves",
                       config.COLOR_SUCCESS, self._show_temperatures
                       ).grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        self._big_card(grid, "📦", "Réceptions",
                       "Relevés des produits livrés",
                       config.COLOR_WARNING, self._show_receptions
                       ).grid(row=0, column=2, sticky="nsew", padx=8, pady=8)

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

    def _show_tickets(self):
        self.destroy()
        PhotoHistoryScreen(self.master,
                           lambda: HistoryScreen(self.master, self.on_done))

    def _show_temperatures(self):
        self.destroy()
        TemperatureHistoryScreen(self.master,
                                 lambda: HistoryScreen(self.master, self.on_done))

    def _show_receptions(self):
        self.destroy()
        ReceptionHistoryScreen(self.master,
                               lambda: HistoryScreen(self.master, self.on_done))

    def _back(self):
        self.destroy()
        self.on_done()


# ---------------------------------------------------------------------------
# Visionneuse de tickets
# ---------------------------------------------------------------------------

class PhotoHistoryScreen(tk.Frame):
    """Affichage plein ecran des photos de tickets, navigation par mois."""

    def __init__(self, master, on_done):
        super().__init__(master, bg="black")
        self.on_done = on_done
        self.pack(fill="both", expand=True)

        today = date.today()
        self.year = today.year
        self.month = today.month
        self.photos = []
        self.idx = 0
        self._tkimg = None

        # Header
        header = tk.Frame(self, bg="black")
        header.pack(fill="x", padx=8, pady=6)
        tk.Button(header, text="← Retour", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
                  command=self._back).pack(side="left")
        tk.Label(header, text="Tickets", bg="black", fg="white",
                 font=config.FONT_MED).pack(side="left", padx=10)

        # Navigation par mois
        nav = tk.Frame(self, bg="black")
        nav.pack(fill="x", padx=8)
        tk.Button(nav, text="◀", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=16, pady=4,
                  command=self._prev_month).pack(side="left")
        self.month_lbl = tk.Label(nav, text="", bg="black", fg="white",
                                  font=config.FONT_MED)
        self.month_lbl.pack(side="left", expand=True)
        tk.Button(nav, text="▶", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=16, pady=4,
                  command=self._next_month).pack(side="right")

        # Zone photo
        self.photo_lbl = tk.Label(self, bg="black")
        self.photo_lbl.pack(fill="both", expand=True)
        self.empty_lbl = tk.Label(self, text="Aucune photo ce mois",
                                  bg="black", fg=config.COLOR_MUTED,
                                  font=config.FONT_BIG)

        # Navigation photo
        nav2 = tk.Frame(self, bg="black")
        nav2.pack(fill="x", padx=8, pady=(6, 2))
        tk.Button(nav2, text="◀", font=config.FONT_BIG,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=24, pady=8,
                  command=self._prev_photo).pack(side="left")
        tk.Button(nav2, text="▶", font=config.FONT_BIG,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=24, pady=8,
                  command=self._next_photo).pack(side="right")
        self.info_lbl = tk.Label(nav2, text="", bg="black",
                                 fg=config.COLOR_MUTED, font=config.FONT_SMALL,
                                 justify="center")
        self.info_lbl.pack(expand=True)

        # Bouton supprimer
        del_bar = tk.Frame(self, bg="black")
        del_bar.pack(fill="x", padx=8, pady=(0, 6))
        self.del_btn = tk.Button(del_bar, text="🗑  Supprimer cette photo",
                                 font=config.FONT_MED,
                                 bg=config.COLOR_DANGER, fg="white", bd=0,
                                 pady=8, command=self._delete_current)
        self.del_btn.pack(fill="x")

        self._load_month()

    def _load_month(self):
        from . import usb_manager
        self.month_lbl.config(text=f"{MONTHS[self.month - 1]} {self.year}")
        self.photos = usb_manager.list_photos_for_month(self.year, self.month)
        # Ouvrir sur la derniere photo prise (la plus recente du mois)
        self.idx = max(0, len(self.photos) - 1)
        self._show_current()

    def _show_current(self):
        if not self.photos:
            self.photo_lbl.pack_forget()
            self.empty_lbl.pack(fill="both", expand=True)
            self.info_lbl.config(text="")
            self.del_btn.config(state="disabled")
            return

        self.del_btn.config(state="normal")

        self.empty_lbl.pack_forget()
        self.photo_lbl.pack(fill="both", expand=True)

        path = self.photos[self.idx]
        try:
            from PIL import Image, ImageTk
            img = Image.open(path)
            img.thumbnail((config.SCREEN_W, 580), Image.LANCZOS)
            self._tkimg = ImageTk.PhotoImage(img)
            self.photo_lbl.config(image=self._tkimg, text="")
        except Exception:
            self.photo_lbl.config(image="", text="Erreur chargement",
                                  fg="white", font=config.FONT_MED)

        # Extraire la date du nom de fichier : photo_YYYY-MM-DD[_N].jpg
        try:
            date_str = path.stem.split("_")[1]   # YYYY-MM-DD
            d = date.fromisoformat(date_str)
            label = d.strftime("%d/%m/%Y")
        except Exception:
            label = path.name

        self.info_lbl.config(
            text=f"{self.idx + 1} / {len(self.photos)}  —  {label}"
        )

    def _delete_current(self):
        if not self.photos:
            return
        path = self.photos[self.idx]
        if not confirm(self, "Supprimer", f"Supprimer cette photo ?\n{path.name}"):
            return
        try:
            path.unlink(missing_ok=True)
        except OSError as e:
            error(self, "Erreur", f"Impossible de supprimer :\n{e}")
            return
        # Aussi retirer l'entree pending si elle existe
        try:
            database.remove_pending_photo_by_path(str(path))
        except Exception:
            pass
        self.photos.pop(self.idx)
        # Ajuster l'index si on était sur la dernière photo
        if self.idx >= len(self.photos):
            self.idx = max(0, len(self.photos) - 1)
        self._show_current()

    def _prev_photo(self):
        if self.photos and self.idx > 0:
            self.idx -= 1
            self._show_current()

    def _next_photo(self):
        if self.photos and self.idx < len(self.photos) - 1:
            self.idx += 1
            self._show_current()

    def _prev_month(self):
        self.month -= 1
        if self.month < 1:
            self.month = 12
            self.year -= 1
        self._load_month()

    def _next_month(self):
        self.month += 1
        if self.month > 12:
            self.month = 1
            self.year += 1
        self._load_month()

    def _back(self):
        self.destroy()
        self.on_done()


# ---------------------------------------------------------------------------
# Tableau temperatures
# ---------------------------------------------------------------------------

class TemperatureHistoryScreen(tk.Frame):
    """Tableau mensuel des releves de temperature."""

    def __init__(self, master, on_done):
        super().__init__(master, bg=config.COLOR_BG)
        self.on_done = on_done
        self.pack(fill="both", expand=True)

        today = date.today()
        self.year = today.year
        self.month = today.month

        header = tk.Frame(self, bg=config.COLOR_BG)
        header.pack(fill="x", padx=10, pady=6)
        tk.Button(header, text="← Retour", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
                  command=self._back).pack(side="left")
        self.title_lbl = tk.Label(header, text="", bg=config.COLOR_BG,
                                  fg=config.COLOR_FG, font=config.FONT_MED)
        self.title_lbl.pack(side="left", padx=8)
        tk.Button(header, text="Export PDF", font=config.FONT_MED,
                  bg=config.COLOR_SUCCESS, fg="white", bd=0, padx=10, pady=4,
                  command=self._export).pack(side="right", padx=4)

        nav = tk.Frame(self, bg=config.COLOR_BG)
        nav.pack(fill="x", padx=10)
        tk.Button(nav, text="◀ Mois precedent", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
                  command=self._prev_month).pack(side="left")
        tk.Button(nav, text="Mois suivant ▶", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
                  command=self._next_month).pack(side="right")

        container = tk.Frame(self, bg=config.COLOR_BG)
        container.pack(fill="both", expand=True, padx=10, pady=6)
        canvas = tk.Canvas(container, bg=config.COLOR_BG, highlightthickness=0)
        sb = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.table_frame = tk.Frame(canvas, bg=config.COLOR_BG)
        self.table_frame.bind("<Configure>",
                              lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.table_frame, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.canvas = canvas

        self._render()

    def _prev_month(self):
        self.month -= 1
        if self.month < 1:
            self.month = 12
            self.year -= 1
        self._render()

    def _next_month(self):
        self.month += 1
        if self.month > 12:
            self.month = 1
            self.year += 1
        self._render()

    def _render(self):
        self.title_lbl.config(text=f"Histo. {MONTHS[self.month-1][:4]}. {self.year}")
        for w in self.table_frame.winfo_children():
            w.destroy()

        start = date(self.year, self.month, 1)
        end = date(self.year, self.month, monthrange(self.year, self.month)[1])
        readings = database.readings_in_range(start, end)
        devices = database.list_devices()

        if not devices:
            tk.Label(self.table_frame, text="(aucun appareil)", bg=config.COLOR_BG,
                     fg=config.COLOR_MUTED, font=config.FONT_MED).pack(pady=20)
            return

        idx = {(r["device_id"], r["reading_date"]): r for r in readings}

        head = tk.Frame(self.table_frame, bg=config.COLOR_BG)
        head.pack(fill="x")
        tk.Label(head, text="Jour", bg=config.COLOR_BG, fg=config.COLOR_MUTED,
                 font=config.FONT_SMALL, width=6, anchor="w"
                 ).pack(side="left", padx=2)
        for d in devices:
            tk.Label(head, text=d["name"][:10], bg=config.COLOR_BG,
                     fg=config.COLOR_MUTED, font=config.FONT_SMALL,
                     width=10, anchor="w"
                     ).pack(side="left", padx=2)

        for day_num in range(1, monthrange(self.year, self.month)[1] + 1):
            day = date(self.year, self.month, day_num)
            row = tk.Frame(self.table_frame, bg=config.COLOR_CARD)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=f"{day_num:02d}", bg=config.COLOR_CARD,
                     fg=config.COLOR_FG, font=config.FONT_MED, width=6, anchor="w"
                     ).pack(side="left", padx=2, pady=4)
            for d in devices:
                entry = idx.get((d["id"], day.isoformat()))
                self._cell(row, d, day, entry)

    def _cell(self, parent, device, day, entry):
        if entry is None:
            text, bg, fg = "—", config.COLOR_CARD, config.COLOR_MUTED
        else:
            text = f"{entry['temperature']:g}°"
            out = (entry["temperature"] < device["temp_min"]
                   or entry["temperature"] > device["temp_max"])
            bg = config.COLOR_DANGER if out else config.COLOR_CARD
            fg = "white" if out else config.COLOR_FG

        tk.Button(parent, text=text, bg=bg, fg=fg, font=config.FONT_MED,
                  width=10, bd=0, height=1,
                  command=lambda: self._edit(device, day, entry)
                  ).pack(side="left", padx=2, pady=2)

    def _edit(self, device, day, entry):
        if day > date.today():
            return
        initial = f"{entry['temperature']:g}" if entry else ""
        v = numpad_popup(self, f"{device['name']} — {day.strftime('%d/%m/%Y')}",
                         initial=initial)
        if v is None or v == "":
            return
        try:
            val = float(v)
        except ValueError:
            return
        database.save_reading(device["id"], day, val)
        self._render()

    def _export(self):
        try:
            path = pdf_export.export_month_pdf(self.year, self.month)
        except Exception as e:
            error(self, "Erreur export", str(e))
            return
        if path is None:
            error(self, "USB absente", "Branchez une cle USB pour exporter.")
            return
        info(self, "Export OK", f"Fichier enregistre :\n{path.name}")

    def _back(self):
        self.destroy()
        self.on_done()


# ---------------------------------------------------------------------------
# Liste des receptions
# ---------------------------------------------------------------------------

class ReceptionHistoryScreen(tk.Frame):
    """Liste mensuelle des releves de reception (date, fournisseur, temp)."""

    def __init__(self, master, on_done):
        super().__init__(master, bg=config.COLOR_BG)
        self.on_done = on_done
        self.pack(fill="both", expand=True)

        today = date.today()
        self.year = today.year
        self.month = today.month

        header = tk.Frame(self, bg=config.COLOR_BG)
        header.pack(fill="x", padx=10, pady=6)
        tk.Button(header, text="← Retour", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
                  command=self._back).pack(side="left")
        self.title_lbl = tk.Label(header, text="", bg=config.COLOR_BG,
                                  fg=config.COLOR_FG, font=config.FONT_MED)
        self.title_lbl.pack(side="left", padx=8)
        tk.Button(header, text="Export PDF", font=config.FONT_MED,
                  bg=config.COLOR_SUCCESS, fg="white", bd=0, padx=10, pady=4,
                  command=self._export).pack(side="right", padx=4)

        nav = tk.Frame(self, bg=config.COLOR_BG)
        nav.pack(fill="x", padx=10)
        tk.Button(nav, text="◀ Mois precedent", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
                  command=self._prev_month).pack(side="left")
        tk.Button(nav, text="Mois suivant ▶", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
                  command=self._next_month).pack(side="right")

        container = tk.Frame(self, bg=config.COLOR_BG)
        container.pack(fill="both", expand=True, padx=10, pady=6)
        canvas = tk.Canvas(container, bg=config.COLOR_BG, highlightthickness=0)
        sb = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.list_frame = tk.Frame(canvas, bg=config.COLOR_BG)
        self.list_frame.bind("<Configure>",
                             lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.list_frame, anchor="nw",
                             width=config.SCREEN_W - 40)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._render()

    def _prev_month(self):
        self.month -= 1
        if self.month < 1:
            self.month = 12
            self.year -= 1
        self._render()

    def _next_month(self):
        self.month += 1
        if self.month > 12:
            self.month = 1
            self.year += 1
        self._render()

    def _render(self):
        self.title_lbl.config(
            text=f"Réceptions {MONTHS[self.month-1]} {self.year}")
        for w in self.list_frame.winfo_children():
            w.destroy()

        start = date(self.year, self.month, 1)
        end = date(self.year, self.month, monthrange(self.year, self.month)[1])
        receptions = database.receptions_in_range(start, end)

        if not receptions:
            tk.Label(self.list_frame, text="(aucune réception ce mois)",
                     bg=config.COLOR_BG, fg=config.COLOR_MUTED,
                     font=config.FONT_MED).pack(pady=30)
            return

        for r in receptions:
            dt = datetime.fromisoformat(r["created_at"])
            row = tk.Frame(self.list_frame, bg=config.COLOR_CARD)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=dt.strftime("%d/%m  %H:%M"), bg=config.COLOR_CARD,
                     fg=config.COLOR_MUTED, font=config.FONT_MED, width=12,
                     anchor="w").pack(side="left", padx=8, pady=6)
            tk.Label(row, text=r["supplier_name"], bg=config.COLOR_CARD,
                     fg=config.COLOR_FG, font=config.FONT_MED, anchor="w"
                     ).pack(side="left", padx=4, expand=True, fill="x")
            tk.Label(row, text=f"{r['temperature']:.1f}°C", bg=config.COLOR_CARD,
                     fg=config.COLOR_SUCCESS, font=config.FONT_MED
                     ).pack(side="right", padx=12)

    def _export(self):
        try:
            path = pdf_export.export_month_pdf(self.year, self.month)
        except Exception as e:
            error(self, "Erreur export", str(e))
            return
        if path is None:
            error(self, "USB absente", "Branchez une cle USB pour exporter.")
            return
        info(self, "Export OK", f"Fichier enregistre :\n{path.name}")

    def _back(self):
        self.destroy()
        self.on_done()
