"""Ecran historique : Tickets (photos), Temperatures ou Receptions."""
import tkinter as tk
import tkinter.font as tkfont
from datetime import date, datetime, time
from calendar import monthrange
from . import config, database, pdf_export, ui_rounded
from .ui_common import (Button, ZoneDefilante, numpad_popup, info, error, confirm,
                        open_modal, close_modal, bind_drag_scroll, install_tap_guard,
                        schedule_auto_return as auto_return)

# Heure attribuee a une reception saisie a posteriori : l'heure exacte
# n'est pas connue, et seule la date compte pour ce releve.
RECEPTION_DEFAULT_TIME = time(9, 0)

MONTHS = ["Janvier", "Fevrier", "Mars", "Avril", "Mai", "Juin",
          "Juillet", "Aout", "Septembre", "Octobre", "Novembre", "Decembre"]


# ---------------------------------------------------------------------------
# Landing
# ---------------------------------------------------------------------------

def _retour_accueil(master, on_done):
    """Retour d'un sous-ecran vers l'accueil de l'historique."""
    install_tap_guard(HistoryScreen(master, on_done))


class HistoryScreen(tk.Frame):
    """Menu de choix : Tickets ou Temperatures."""

    def __init__(self, master, on_done):
        rounded = config.STYLE == "rounded"
        fond = ui_rounded.HIST_FOND if rounded else config.COLOR_BG
        super().__init__(master, bg=fond)
        self.on_done = on_done
        auto_return(self, config.HISTORY_INACTIVITY_S, self._back)
        self.pack(fill="both", expand=True)

        header = tk.Frame(self, bg=fond)
        header.pack(fill="x", padx=16, pady=(10, 4))
        Button(header, text="← Retour", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
                  command=self._back).pack(side="left")
        tk.Label(header, text="Historique", bg=fond,
                 fg=config.COLOR_FG, font=config.FONT_TITLE).pack(side="left", padx=12)

        if rounded:
            self._build_liste()
            return

        grid = tk.Frame(self, bg=config.COLOR_BG)
        grid.pack(fill="both", expand=True, padx=20, pady=20)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.columnconfigure(2, weight=1)
        grid.rowconfigure(0, weight=1)

        self._big_card(grid, "📷", "Tickets",
                       "Consulter les photos de tickets",
                       config.COLOR_PRIMARY, self._show_tickets
                       ).grid(row=0, column=0, **self._cellule())
        self._big_card(grid, "🌡", "Temperatures",
                       "Tableau mensuel des releves",
                       config.COLOR_SUCCESS, self._show_temperatures
                       ).grid(row=0, column=1, **self._cellule())
        self._big_card(grid, "📦", "Réceptions",
                       "Relevés des produits livrés",
                       config.COLOR_WARNING, self._show_receptions
                       ).grid(row=0, column=2, **self._cellule())

    def _build_liste(self):
        """Style arrondi : trois lignes pleines largeur sur fond quasi noir,
        pour ne plus confondre ce menu avec le menu principal (trois tuiles)."""
        lignes = tk.Frame(self, bg=ui_rounded.HIST_FOND)
        lignes.pack(padx=24, pady=(10, 0))
        specs = [
            ("01", "Tickets", "Consulter les photos de tickets",
             config.COLOR_PRIMARY, self._show_tickets),
            ("02", "Temperatures", "Tableau mensuel des releves",
             config.COLOR_SUCCESS, self._show_temperatures),
            ("03", "Réceptions", "Relevés des produits livrés",
             config.COLOR_WARNING, self._show_receptions),
        ]
        for i, (num, titre, sous, accent, cmd) in enumerate(specs):
            ui_rounded.Ligne(lignes, config.SCREEN_W - 48, 116, num, titre, sous,
                             accent, cmd).grid(row=i, column=0,
                                               pady=(0 if i == 0 else 12, 0))

    def _cellule(self):
        if config.STYLE == "rounded":
            return {"sticky": "", "padx": 14, "pady": 8}   # 28 px entre les cases
        return {"sticky": "nsew", "padx": 8, "pady": 8}

    def _big_card(self, parent, icon, title, subtitle, color, command):
        if config.STYLE == "rounded":
            larg = (config.SCREEN_W - 2 * 20 - 6 * 14) // 3
            return ui_rounded.Card(parent, larg, 300, icon, title, subtitle,
                                   color, command)
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
        install_tap_guard(PhotoHistoryScreen(
            self.master, lambda: _retour_accueil(self.master, self.on_done)))

    def _show_temperatures(self):
        self.destroy()
        install_tap_guard(TemperatureHistoryScreen(
            self.master, lambda: _retour_accueil(self.master, self.on_done)))

    def _show_receptions(self):
        self.destroy()
        install_tap_guard(ReceptionHistoryScreen(
            self.master, lambda: _retour_accueil(self.master, self.on_done)))

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
        auto_return(self, config.HISTORY_INACTIVITY_S, self._back)
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
        Button(header, text="← Retour", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
                  command=self._back).pack(side="left")
        tk.Label(header, text="Tickets", bg="black", fg="white",
                 font=config.FONT_MED).pack(side="left", padx=10)

        # Navigation par mois
        nav = tk.Frame(self, bg="black")
        nav.pack(fill="x", padx=8)
        Button(nav, text="◀", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=16, pady=4,
                  command=self._prev_month).pack(side="left")
        self.month_lbl = tk.Label(nav, text="", bg="black", fg="white",
                                  font=config.FONT_MED)
        self.month_lbl.pack(side="left", expand=True)
        Button(nav, text="▶", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=16, pady=4,
                  command=self._next_month).pack(side="right")

        # Zone photo : le label est « place » (et non « pack ») pour qu'une
        # grande image ne pousse jamais les barres de navigation hors de
        # l'ecran — c'est ce qui coupait l'apercu en deux.
        self.photo_area = tk.Frame(self, bg="black")
        self.photo_area.pack(fill="both", expand=True)
        self.photo_lbl = tk.Label(self.photo_area, bg="black")
        self.empty_lbl = tk.Label(self.photo_area, text="Aucune photo ce mois",
                                  bg="black", fg=config.COLOR_MUTED,
                                  font=config.FONT_BIG)

        # Navigation photo
        nav2 = tk.Frame(self, bg="black")
        nav2.pack(fill="x", padx=8, pady=(6, 2))
        Button(nav2, text="◀", font=config.FONT_BIG,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=24, pady=8,
                  command=self._prev_photo).pack(side="left")
        Button(nav2, text="▶", font=config.FONT_BIG,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=24, pady=8,
                  command=self._next_photo).pack(side="right")
        self.info_lbl = tk.Label(nav2, text="", bg="black",
                                 fg=config.COLOR_MUTED, font=config.FONT_SMALL,
                                 justify="center")
        self.info_lbl.pack(expand=True)

        # Bouton supprimer
        del_bar = tk.Frame(self, bg="black")
        del_bar.pack(fill="x", padx=8, pady=(0, 6))
        self.del_btn = Button(del_bar, text="🗑  Supprimer cette photo",
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

    def _photo_area_size(self):
        """Place reellement disponible pour la photo : l'ecran moins les barres
        de navigation. Mesuree, donc juste quelle que soit la taille d'ecran."""
        self.update_idletasks()
        w = self.photo_area.winfo_width()
        h = self.photo_area.winfo_height()
        if w < 50 or h < 50:          # avant le tout premier affichage
            w, h = config.SCREEN_W, max(120, config.SCREEN_H - 200)
        return max(50, w - 8), max(50, h - 8)

    def _show_current(self):
        if not self.photos:
            self.photo_lbl.place_forget()
            self.empty_lbl.place(relx=0.5, rely=0.5, anchor="center")
            self.info_lbl.config(text="")
            self.del_btn.config(state="disabled")
            return

        self.del_btn.config(state="normal")

        self.empty_lbl.place_forget()
        self.photo_lbl.place(relx=0.5, rely=0.5, anchor="center")

        path = self.photos[self.idx]
        try:
            from PIL import Image, ImageTk
            img = Image.open(path)
            img.thumbnail(self._photo_area_size(), Image.LANCZOS)
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
        auto_return(self, config.HISTORY_INACTIVITY_S, self._back)
        self.pack(fill="both", expand=True)

        today = date.today()
        self.year = today.year
        self.month = today.month

        header = tk.Frame(self, bg=config.COLOR_BG)
        header.pack(fill="x", padx=10, pady=6)
        Button(header, text="← Retour", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
                  command=self._back).pack(side="left")
        self.title_lbl = tk.Label(header, text="", bg=config.COLOR_BG,
                                  fg=config.COLOR_FG, font=config.FONT_MED)
        self.title_lbl.pack(side="left", padx=8)
        Button(header, text="Export PDF", font=config.FONT_MED,
                  bg=config.COLOR_SUCCESS, fg="white", bd=0, padx=10, pady=4,
                  command=self._export).pack(side="right", padx=4)

        nav = tk.Frame(self, bg=config.COLOR_BG)
        nav.pack(fill="x", padx=10)
        Button(nav, text="◀ Mois precedent", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
                  command=self._prev_month).pack(side="left")
        Button(nav, text="Mois suivant ▶", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
                  command=self._next_month).pack(side="right")

        # Defile dans les deux sens : au-dela de 5 appareils, les colonnes ne
        # tiennent plus dans la largeur de l'ecran.
        self.zone = ZoneDefilante(self, config.COLOR_BG, horizontal=True)
        self.zone.pack(fill="both", expand=True, padx=10, pady=6)
        self.canvas = self.zone.canvas
        self.table_frame = self.zone.interieur

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

    def _largeur_colonne(self, nb_appareils):
        """Largeur des colonnes (en caracteres) : resserrees quand il y a
        beaucoup d'appareils, sans descendre sous une largeur lisible ; au-dela,
        le tableau defile sur le cote."""
        chiffre = tkfont.Font(font=config.FONT_MED).measure("0")
        disponible = config.SCREEN_W - 40 - 18 - 7 * chiffre
        par_colonne = disponible // max(1, nb_appareils) - 8
        return max(6, min(10, par_colonne // chiffre))

    def _render(self):
        self.title_lbl.config(text=f"Histo. {MONTHS[self.month-1][:4]}. {self.year}")
        self.zone.vider()

        start = date(self.year, self.month, 1)
        end = date(self.year, self.month, monthrange(self.year, self.month)[1])
        readings = database.readings_in_range(start, end)
        # appareils en service + ceux retires qui ont des releves ce mois-la
        devices = database.devices_for_period(start, end)
        self._largeur = self._largeur_colonne(len(devices))

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
            tk.Label(head, text=d["name"][:self._largeur + 2], bg=config.COLOR_BG,
                     fg=config.COLOR_MUTED, font=config.FONT_SMALL,
                     width=self._largeur + 2, anchor="w"
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

        self.zone.actualiser()

    def _cell(self, parent, device, day, entry):
        if entry is None:
            text, bg, fg = "—", config.COLOR_CARD, config.COLOR_MUTED
        else:
            text = f"{entry['temperature']:g}°"
            out = (entry["temperature"] < device["temp_min"]
                   or entry["temperature"] > device["temp_max"])
            bg = config.COLOR_DANGER if out else config.COLOR_CARD
            fg = "white" if out else config.COLOR_FG

        # Bouton Tk ordinaire, meme en style arrondi : ce tableau en compte un
        # par jour et par appareil (des centaines), reconstruits a chaque
        # changement de mois ; des boutons dessines y seraient lents sur le Pi.
        tk.Button(parent, text=text, bg=bg, fg=fg, font=config.FONT_MED,
                  width=self._largeur, bd=0, height=1,
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
        auto_return(self, config.HISTORY_INACTIVITY_S, self._back)
        self.pack(fill="both", expand=True)

        today = date.today()
        self.year = today.year
        self.month = today.month

        header = tk.Frame(self, bg=config.COLOR_BG)
        header.pack(fill="x", padx=10, pady=6)
        Button(header, text="← Retour", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
                  command=self._back).pack(side="left")
        self.title_lbl = tk.Label(header, text="", bg=config.COLOR_BG,
                                  fg=config.COLOR_FG, font=config.FONT_MED)
        self.title_lbl.pack(side="left", padx=8)
        Button(header, text="Export PDF", font=config.FONT_MED,
                  bg=config.COLOR_SUCCESS, fg="white", bd=0, padx=10, pady=4,
                  command=self._export).pack(side="right", padx=4)
        Button(header, text="+ Ajouter", font=config.FONT_MED,
                  bg=config.COLOR_PRIMARY, fg="white", bd=0, padx=10, pady=4,
                  command=self._add).pack(side="right", padx=4)

        nav = tk.Frame(self, bg=config.COLOR_BG)
        nav.pack(fill="x", padx=10)
        Button(nav, text="◀ Mois precedent", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
                  command=self._prev_month).pack(side="left")
        Button(nav, text="Mois suivant ▶", font=config.FONT_MED,
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
            Button(row, text="Suppr", font=config.FONT_SMALL,
                      bg=config.COLOR_DANGER, fg="white", bd=0, padx=8, pady=4,
                      command=lambda x=r: self._delete(x)
                      ).pack(side="right", padx=(0, 8), pady=4)
            Button(row, text="Modifier", font=config.FONT_SMALL,
                      bg=config.COLOR_PRIMARY, fg="white", bd=0, padx=8, pady=4,
                      command=lambda x=r: self._edit(x)
                      ).pack(side="right", padx=4, pady=4)
            hors = database.reception_hors_seuil(r)
            tk.Label(row, text=("⚠ " if hors else "") + f"{r['temperature']:.1f}°C",
                     bg=config.COLOR_CARD,
                     fg=config.COLOR_DANGER if hors else config.COLOR_SUCCESS,
                     font=config.FONT_MED).pack(side="right", padx=12)
            tk.Label(row, text=r["supplier_name"], bg=config.COLOR_CARD,
                     fg=config.COLOR_FG, font=config.FONT_MED, anchor="w"
                     ).pack(side="left", padx=4, expand=True, fill="x")

        bind_drag_scroll(self.canvas, self.list_frame)

    # --- rattrapage d'une reception oubliee ---

    def _panel(self, titre, w, h):
        panel = open_modal(self, w, h, config.COLOR_PRIMARY)
        tk.Label(panel, text=titre, bg=config.COLOR_BG, fg=config.COLOR_FG,
                 font=config.FONT_MED).pack(pady=8)
        return panel

    def _add(self):
        """Saisie a posteriori : fournisseur, puis jour, puis temperature."""
        suppliers = database.list_suppliers()
        if not suppliers:
            error(self, "Aucun fournisseur",
                  "Ajoutez d'abord un fournisseur depuis\n"
                  "Réception ▸ Fournisseurs.")
            return
        h = min(80 + len(suppliers) * 52 + 50, config.SCREEN_H - 30)
        panel = self._panel("Quel fournisseur ?", 420, h)
        # Annuler d'abord, en bas : il reste visible meme avec beaucoup de
        # fournisseurs, dont la liste defile au-dessus
        Button(panel, text="Annuler", font=config.FONT_SMALL,
                  bg=config.COLOR_DANGER, fg="white", bd=0, pady=6,
                  command=lambda: close_modal(panel)
                  ).pack(side="bottom", fill="x", padx=16, pady=(6, 8))
        liste = ZoneDefilante(panel, config.COLOR_BG)
        liste.pack(fill="both", expand=True, padx=12)
        for s in suppliers:
            Button(liste.interieur, text=s["name"], font=config.FONT_MED,
                      bg=config.COLOR_CARD, fg=config.COLOR_FG, bd=0,
                      padx=12, pady=8,
                      command=(lambda x=s: (close_modal(panel),
                                            self._pick_day(x)))
                      ).pack(fill="x", padx=4, pady=2)
        liste.actualiser()

    def _pick_day(self, supplier):
        """Jours du mois affiche ; les jours a venir sont inactifs."""
        last = monthrange(self.year, self.month)[1]
        today = date.today()
        panel = self._panel(f"{supplier['name']} — quel jour ?", 440, 330)
        grid = tk.Frame(panel, bg=config.COLOR_BG)
        grid.pack(padx=10, pady=2)
        for col in range(7):
            grid.columnconfigure(col, weight=1)
        for day in range(1, last + 1):
            jour = date(self.year, self.month, day)
            btn = Button(grid, text=str(day), font=config.FONT_MED,
                            bg=config.COLOR_CARD, fg=config.COLOR_FG, bd=0,
                            width=3, pady=6,
                            command=(lambda d=jour: (close_modal(panel),
                                                     self._ask_temp(supplier, d))))
            if jour > today:
                btn.config(state="disabled", fg=config.COLOR_MUTED)
            btn.grid(row=(day - 1) // 7, column=(day - 1) % 7, padx=2, pady=2)
        Button(panel, text="Annuler", font=config.FONT_SMALL,
                  bg=config.COLOR_DANGER, fg="white", bd=0, pady=6,
                  command=lambda: close_modal(panel)
                  ).pack(fill="x", padx=16, pady=(8, 8))

    def _ask_temp(self, supplier, jour):
        v = numpad_popup(
            self, f"{supplier['name']} — {jour.strftime('%d/%m/%Y')} (°C)")
        if v in (None, "", "-"):
            return
        try:
            temp = float(v)
        except ValueError:
            error(self, "Erreur", "Température invalide.")
            return
        database.save_reception(
            supplier["id"], temp,
            datetime.combine(jour, RECEPTION_DEFAULT_TIME))
        self._render()

    def _edit(self, r):
        dt = datetime.fromisoformat(r["created_at"])
        v = numpad_popup(self,
                         f"{r['supplier_name']} — {dt.strftime('%d/%m/%Y')} (°C)",
                         initial=f"{r['temperature']:g}")
        if v in (None, "", "-"):
            return
        try:
            temp = float(v)
        except ValueError:
            error(self, "Erreur", "Température invalide.")
            return
        database.update_reception(r["id"], temp)
        self._render()

    def _delete(self, r):
        dt = datetime.fromisoformat(r["created_at"])
        if confirm(self, "Supprimer",
                   f"Supprimer le relevé {r['supplier_name']} du "
                   f"{dt.strftime('%d/%m/%Y')} ({r['temperature']:.1f}°C) ?"):
            database.delete_reception(r["id"])
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
