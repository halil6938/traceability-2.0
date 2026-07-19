"""Ecran reception : releve de temperature des produits a l'arrivee, par fournisseur."""
import threading
import time
import tkinter as tk
from datetime import date, datetime

from . import config, database, ble_thermo
from .ui_common import (text_popup, numpad_popup, confirm, error,
                        open_modal, close_modal)


class ReceptionScreen(tk.Frame):
    def __init__(self, master, on_done):
        super().__init__(master, bg=config.COLOR_BG)
        self.on_done = on_done
        self.pack(fill="both", expand=True)

        header = tk.Frame(self, bg=config.COLOR_BG)
        header.pack(fill="x", padx=12, pady=8)
        tk.Button(header, text="← Retour", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
                  command=self._back).pack(side="left")
        tk.Label(header, text="Réception", bg=config.COLOR_BG,
                 fg=config.COLOR_FG, font=config.FONT_TITLE
                 ).pack(side="left", padx=16)
        tk.Button(header, text="⚙ Fournisseurs", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
                  command=self._manage_suppliers).pack(side="right")
        # Indicateur d'etat de la liaison au pistolet (mis a jour par polling)
        self.conn_lbl = tk.Label(header, text="", bg=config.COLOR_BG,
                                 fg=config.COLOR_MUTED, font=config.FONT_SMALL)
        self.conn_lbl.pack(side="right", padx=10)

        body = tk.Frame(self, bg=config.COLOR_BG)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        # Gauche : choix du fournisseur
        left = tk.Frame(body, bg=config.COLOR_BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(left, text="Choisir le fournisseur :", bg=config.COLOR_BG,
                 fg=config.COLOR_MUTED, font=config.FONT_MED
                 ).pack(anchor="w", pady=(0, 4))
        self.suppliers_frame = tk.Frame(left, bg=config.COLOR_BG)
        self.suppliers_frame.pack(fill="both", expand=True)

        # Droite : receptions du jour
        right = tk.Frame(body, bg=config.COLOR_CARD)
        right.grid(row=0, column=1, sticky="nsew")
        tk.Label(right, text="Réceptions du jour", bg=config.COLOR_CARD,
                 fg=config.COLOR_FG, font=config.FONT_MED
                 ).pack(anchor="w", padx=10, pady=(8, 4))
        self.today_frame = tk.Frame(right, bg=config.COLOR_CARD)
        self.today_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self._render_suppliers()
        self._render_today()

        # Connexion persistante au pistolet : lancee des l'entree dans l'ecran
        # (comme le demarrage de l'appli officielle), gardee ouverte tant qu'on
        # reste en Reception -> les mesures deviennent instantanees.
        self.conn = None
        self._suspended = False
        self._start_conn()
        self._poll_conn_status()
        # Differe la fenetre d'attente : l'ecran Reception doit d'abord etre
        # dessine, sinon le popup modal ne s'affiche pas.
        self.after(100, self._wait_for_gun)

    # --- connexion persistante au pistolet ---

    def _start_conn(self):
        """Demarre la liaison persistante au pistolet (si MAC configuree)."""
        mac = database.get_meta("reception_thermo_mac", "")
        if mac and ble_thermo.HAS_BLEAK:
            self.conn = ble_thermo.ThermoConnection(mac)
            self.conn.start()
        else:
            self.conn = None
        self._suspended = False

    def _stop_conn(self):
        """Coupe la liaison (libere le Bluetooth pour une autre operation)."""
        if self.conn is not None:
            self.conn.stop()
            self.conn = None
        self._suspended = True

    def _poll_conn_status(self):
        if not self.winfo_exists():
            return
        if self._suspended:
            txt, color = "🌡 Pistolet en pause", config.COLOR_MUTED
        elif self.conn is None:
            mac = database.get_meta("reception_thermo_mac", "")
            if not mac:
                txt, color = "🌡 Pistolet non configuré", config.COLOR_MUTED
            else:
                txt, color = "🌡 Bluetooth indisponible", config.COLOR_DANGER
        else:
            txt, color = {
                ble_thermo.ST_SCANNING: ("🔍 Recherche du pistolet…", config.COLOR_WARNING),
                ble_thermo.ST_CONNECTING: ("🔗 Connexion au pistolet…", config.COLOR_WARNING),
                ble_thermo.ST_CONNECTED: ("🌡 Pistolet connecté ✓", config.COLOR_SUCCESS),
                ble_thermo.ST_LOST: ("⚠ Pistolet hors ligne", config.COLOR_DANGER),
            }.get(self.conn.status, ("…", config.COLOR_MUTED))
        self.conn_lbl.config(text=txt, fg=color)
        self.after(500, self._poll_conn_status)

    def _wait_for_gun(self):
        """Overlay d'attente plein ecran : bloque le choix du fournisseur tant
        que le pistolet n'est pas connecte. Message rouge clignotant pendant la
        recherche, vert a la connexion (puis fermeture auto). Technique overlay
        (cf. alarme temperature) = fiable, sans Toplevel/grab."""
        if not self.winfo_exists() or self.conn is None:
            return  # ecran ferme, ou pas de pistolet configure (saisie manuelle)

        overlay = tk.Frame(self, bg=config.COLOR_BG)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        overlay.lift()

        tk.Label(overlay, text="Pistolet infrarouge", bg=config.COLOR_BG,
                 fg=config.COLOR_FG, font=config.FONT_TITLE).pack(pady=(90, 12))
        msg = tk.Label(overlay, text="🔍 Recherche du pistolet…",
                       bg=config.COLOR_BG, fg=config.COLOR_DANGER,
                       font=config.FONT_TITLE)
        msg.pack(pady=20)

        st = {"closed": False, "on": True, "after_id": None}

        def close():
            st["closed"] = True
            if st["after_id"] is not None:
                try:
                    overlay.after_cancel(st["after_id"])
                except Exception:
                    pass
            overlay.destroy()

        def go_back():
            close()
            self._back()

        def tick():
            if st["closed"] or not overlay.winfo_exists():
                return
            status = self.conn.status if self.conn is not None else None
            if status == ble_thermo.ST_CONNECTED:
                msg.config(text="✓ Pistolet connecté", fg=config.COLOR_SUCCESS)
                st["on"] = True
                st["after_id"] = overlay.after(900, close)  # voir le vert puis fermer
                return
            elif status == ble_thermo.ST_LOST:
                label = "⚠ Pistolet hors ligne — rallumez-le"
            else:
                label = "🔍 Recherche du pistolet…"
            # clignotement : alternance rouge vif / fondu sur le fond
            st["on"] = not st["on"]
            msg.config(text=label,
                       fg=config.COLOR_DANGER if st["on"] else config.COLOR_BG)
            st["after_id"] = overlay.after(500, tick)

        btns = tk.Frame(overlay, bg=config.COLOR_BG)
        btns.pack(pady=24)
        tk.Button(btns, text="← Retour", font=config.FONT_MED, bg=config.COLOR_CARD,
                  fg="white", bd=0, padx=16, pady=8, command=go_back
                  ).pack(side="left", padx=6)
        tk.Button(btns, text="⌨ Saisie manuelle", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=16, pady=8,
                  command=close).pack(side="left", padx=6)

        tick()

    # --- rendu ---

    def _render_suppliers(self):
        for w in self.suppliers_frame.winfo_children():
            w.destroy()
        suppliers = database.list_suppliers()
        if not suppliers:
            tk.Label(self.suppliers_frame,
                     text="(aucun fournisseur)\nUtilisez « ⚙ Fournisseurs » pour en ajouter.",
                     bg=config.COLOR_BG, fg=config.COLOR_MUTED,
                     font=config.FONT_MED, justify="center").pack(pady=40)
            return
        cols = 2
        for col in range(cols):
            self.suppliers_frame.columnconfigure(col, weight=1)
        for i, s in enumerate(suppliers):
            self.suppliers_frame.rowconfigure(i // cols, weight=1)
            tk.Button(self.suppliers_frame, text=s["name"], font=config.FONT_BIG,
                      bg=config.COLOR_PRIMARY, fg="white", bd=0,
                      wraplength=200,
                      command=lambda x=s: self._measure(x)
                      ).grid(row=i // cols, column=i % cols,
                             sticky="nsew", padx=4, pady=4)

    def _render_today(self):
        for w in self.today_frame.winfo_children():
            w.destroy()
        rows = database.receptions_on(date.today())
        if not rows:
            tk.Label(self.today_frame, text="(aucune réception)",
                     bg=config.COLOR_CARD, fg=config.COLOR_MUTED,
                     font=config.FONT_SMALL).pack(pady=16)
            return
        for r in rows[:10]:
            line = tk.Frame(self.today_frame, bg=config.COLOR_BG)
            line.pack(fill="x", pady=2)
            heure = datetime.fromisoformat(r["created_at"]).strftime("%H:%M")
            tk.Label(line, text=heure, bg=config.COLOR_BG, fg=config.COLOR_MUTED,
                     font=config.FONT_SMALL).pack(side="left", padx=6, pady=4)
            tk.Label(line, text=r["supplier_name"], bg=config.COLOR_BG,
                     fg=config.COLOR_FG, font=config.FONT_SMALL, anchor="w"
                     ).pack(side="left", padx=4, expand=True, fill="x")
            tk.Button(line, text="🗑", font=config.FONT_SMALL,
                      bg=config.COLOR_DANGER, fg="white", bd=0, width=3,
                      command=lambda x=r: self._delete_reception(x)
                      ).pack(side="right", padx=(4, 6), pady=2)
            tk.Label(line, text=f"{r['temperature']:.1f}°C", bg=config.COLOR_BG,
                     fg=config.COLOR_SUCCESS, font=config.FONT_SMALL
                     ).pack(side="right", padx=6)

    def _delete_reception(self, r):
        heure = datetime.fromisoformat(r["created_at"]).strftime("%H:%M")
        if confirm(self, "Supprimer",
                   f"Supprimer le relevé {r['supplier_name']} "
                   f"de {heure} ({r['temperature']:.1f}°C) ?"):
            database.delete_reception(r["id"])
            self._render_today()

    # --- mesure ---

    def _measure(self, supplier):
        """Popup : lecture BLE du thermometre, fallback saisie manuelle."""
        top = open_modal(self, 460, 320)

        tk.Label(top, text=f"Réception — {supplier['name']}",
                 bg=config.COLOR_BG, fg=config.COLOR_FG,
                 font=config.FONT_BIG).pack(pady=(14, 4))

        status_var = tk.StringVar(value="")
        status = tk.Label(top, textvariable=status_var, bg=config.COLOR_BG,
                          fg=config.COLOR_MUTED, font=config.FONT_SMALL,
                          wraplength=430)
        status.pack()

        temp_var = tk.StringVar(value="--.- °C")
        tk.Label(top, textvariable=temp_var, bg=config.COLOR_BG,
                 fg=config.COLOR_FG, font=("DejaVu Sans", 40, "bold")
                 ).pack(pady=8)

        state = {"temp": None, "closed": False, "after_id": None}
        conn = self.conn

        def set_temp(t):
            state["temp"] = t
            temp_var.set(f"{t:.1f} °C")
            save_btn.config(state="normal", bg=config.COLOR_SUCCESS)

        # La liaison au pistolet est deja ouverte. On NE capture PAS les
        # relevés d'ambiance epars : on detecte la GACHETTE par la cadence des
        # trames — pressee, le pistolet emet en rafale (~1/s) ; relachee, il se
        # tait. On affiche la mesure en direct pendant la pression et on fige
        # la valeur au relachement.
        if conn is not None:
            conn.poll()    # vide les vieilles mesures

        burst = {"last": 0.0, "temp": None, "active": False}
        GAP = 2.5  # secondes sans trame -> gachette relachee

        def poll_meas():
            if state["closed"]:
                return
            if conn is None:
                top.after(150, poll_meas)
                return
            now = time.monotonic()
            t = conn.poll()
            if t is not None:
                # une trame vient d'arriver
                if burst["last"] and (now - burst["last"]) < GAP:
                    # trames rapprochees = gachette pressee -> mesure en direct
                    burst["active"] = True
                    temp_var.set(f"{t:.1f} °C")
                    status_var.set("Mesure en cours — relâchez la gâchette…")
                    status.config(fg=config.COLOR_WARNING)
                burst["last"] = now
                burst["temp"] = t
            elif burst["active"] and burst["last"] and (now - burst["last"]) > GAP:
                # fin de rafale = gachette relachee -> on fige la valeur
                burst["active"] = False
                set_temp(burst["temp"])
                status_var.set("✓ Mesure prête — Enregistrer, ou visez à nouveau.")
                status.config(fg=config.COLOR_SUCCESS)
            elif state["temp"] is None and not burst["active"]:
                if conn.status == ble_thermo.ST_CONNECTED:
                    status_var.set("Visez le produit et appuyez sur la gâchette.")
                    status.config(fg=config.COLOR_WARNING)
                elif conn.status == ble_thermo.ST_LOST:
                    status_var.set("⚠ Pistolet hors ligne — rallumez-le,\n"
                                   "ou saisissez manuellement.")
                    status.config(fg=config.COLOR_DANGER)
                else:
                    status_var.set("Connexion au pistolet en cours…")
                    status.config(fg=config.COLOR_WARNING)
            state["after_id"] = top.after(150, poll_meas)

        if conn is None:
            status_var.set("Aucun pistolet configuré — saisie manuelle.")
            status.config(fg=config.COLOR_WARNING)

        def manual():
            v = numpad_popup(top, "Température (°C)")
            if v in (None, "", "-"):
                return
            try:
                set_temp(float(v))
            except ValueError:
                error(top, "Erreur", "Température invalide.")

        def close_popup():
            state["closed"] = True
            if state["after_id"] is not None:
                try:
                    top.after_cancel(state["after_id"])
                except Exception:
                    pass
            close_modal(top)  # liaison pistolet conservee pour la suite

        def save():
            database.save_reception(supplier["id"], state["temp"])
            close_popup()
            self._render_today()

        def cancel():
            close_popup()

        btns = tk.Frame(top, bg=config.COLOR_BG)
        btns.pack(side="bottom", fill="x", padx=12, pady=10)
        tk.Button(btns, text="Annuler", font=config.FONT_MED, bg=config.COLOR_CARD,
                  fg="white", bd=0, command=cancel
                  ).pack(side="left", expand=True, fill="x", padx=3, ipady=8)
        tk.Button(btns, text="⌨ Manuel", font=config.FONT_MED, bg=config.COLOR_CARD,
                  fg="white", bd=0, command=manual
                  ).pack(side="left", expand=True, fill="x", padx=3, ipady=8)
        save_btn = tk.Button(btns, text="Enregistrer", font=config.FONT_MED,
                             bg=config.COLOR_MUTED, fg="white", bd=0,
                             state="disabled", command=save)
        save_btn.pack(side="left", expand=True, fill="x", padx=3, ipady=8)

        poll_meas()
        self.wait_window(top)

    # --- gestion fournisseurs ---

    def _manage_suppliers(self):
        # Suspend la liaison persistante : libere le Bluetooth pour une
        # eventuelle detection du pistolet, et evite tout conflit d'adaptateur.
        self._stop_conn()

        top = open_modal(self, 520, 420)

        def close_mgr():
            close_modal(top)

        hdr = tk.Frame(top, bg=config.COLOR_BG)
        hdr.pack(fill="x", padx=10, pady=8)
        tk.Label(hdr, text="Fournisseurs", bg=config.COLOR_BG,
                 fg=config.COLOR_FG, font=config.FONT_BIG).pack(side="left")
        tk.Button(hdr, text="✕", bg=config.COLOR_DANGER, fg="white",
                  font=config.FONT_MED, bd=0, padx=12,
                  command=close_mgr).pack(side="right")

        body = tk.Frame(top, bg=config.COLOR_BG)
        body.pack(fill="both", expand=True, padx=10)

        def render():
            for w_ in body.winfo_children():
                w_.destroy()
            suppliers = database.list_suppliers()
            if not suppliers:
                tk.Label(body, text="(aucun fournisseur)", bg=config.COLOR_BG,
                         fg=config.COLOR_MUTED, font=config.FONT_MED).pack(pady=20)
            for s in suppliers:
                row = tk.Frame(body, bg=config.COLOR_CARD)
                row.pack(fill="x", pady=3)
                tk.Label(row, text=s["name"], bg=config.COLOR_CARD,
                         fg=config.COLOR_FG, font=config.FONT_MED, anchor="w"
                         ).pack(side="left", padx=12, pady=8, expand=True, fill="x")

                def edit(sup=s):
                    name = text_popup(top, "Nom du fournisseur", initial=sup["name"])
                    if name:
                        database.update_supplier(sup["id"], name)
                        render()
                        self._render_suppliers()

                def remove(sup=s):
                    if confirm(top, "Supprimer",
                               f"Supprimer '{sup['name']}' ?\n"
                               "Ses relevés de réception seront aussi supprimés."):
                        database.delete_supplier(sup["id"])
                        render()
                        self._render_suppliers()
                        self._render_today()

                tk.Button(row, text="Modifier", font=config.FONT_SMALL,
                          bg=config.COLOR_PRIMARY, fg="white", bd=0, padx=8,
                          command=edit).pack(side="right", padx=4, pady=4)
                tk.Button(row, text="🗑", font=config.FONT_MED, bg=config.COLOR_DANGER,
                          fg="white", bd=0, width=3,
                          command=remove).pack(side="right", padx=4, pady=4)

        render()

        bottom = tk.Frame(top, bg=config.COLOR_BG)
        bottom.pack(fill="x", padx=10, pady=8)

        def add():
            name = text_popup(top, "Nom du fournisseur")
            if not name:
                return
            try:
                database.add_supplier(name)
            except Exception as e:
                error(top, "Erreur", str(e))
                return
            render()
            self._render_suppliers()

        def config_thermo():
            cfg = open_modal(top, 460, 250)

            def close_cfg():
                close_modal(cfg)

            tk.Label(cfg, text="Pistolet Bluetooth", bg=config.COLOR_BG,
                     fg=config.COLOR_FG, font=config.FONT_BIG).pack(pady=(12, 2))
            mac_var = tk.StringVar(
                value=database.get_meta("reception_thermo_mac", "") or "(non configuré)")
            tk.Label(cfg, textvariable=mac_var, bg=config.COLOR_CARD,
                     fg=config.COLOR_FG, font=config.FONT_MED, padx=12, pady=6
                     ).pack(pady=4)
            st_var = tk.StringVar()
            st_lbl = tk.Label(cfg, textvariable=st_var, bg=config.COLOR_BG,
                              fg=config.COLOR_MUTED, font=config.FONT_SMALL,
                              wraplength=430)
            st_lbl.pack(pady=2)

            detect_state = {"running": False}

            def detect():
                if detect_state["running"]:
                    return
                detect_state["running"] = True
                st_var.set("Recherche... appuyez sur la gâchette du pistolet (max 15 s)")
                st_lbl.config(fg=config.COLOR_WARNING)
                box = {}

                def do():
                    with config.BLE_LOCK:
                        try:
                            box["found"] = ble_thermo.find_thermometer()
                        except Exception as e:
                            box["err"] = str(e)
                    box["done"] = True

                def poll():
                    if not cfg.winfo_exists():
                        return
                    if not box.get("done"):
                        cfg.after(200, poll)
                        return
                    detect_state["running"] = False
                    found, err = box.get("found"), box.get("err")
                    if found:
                        mac, name = found
                        database.set_meta("reception_thermo_mac", mac.lower())
                        mac_var.set(mac.lower())
                        st_var.set(f"✓ Détecté : {name}")
                        st_lbl.config(fg=config.COLOR_SUCCESS)
                    else:
                        st_var.set(f"✗ {err}" if err else
                                   "✗ Pistolet non trouvé — vérifiez qu'il est allumé")
                        st_lbl.config(fg=config.COLOR_DANGER)

                threading.Thread(target=do, daemon=True).start()
                cfg.after(200, poll)

            def manual():
                cur = database.get_meta("reception_thermo_mac", "")
                mac = text_popup(cfg, "MAC du pistolet BLE", initial=cur)
                if mac:
                    database.set_meta("reception_thermo_mac", mac.strip().lower())
                    mac_var.set(mac.strip().lower())

            cbtns = tk.Frame(cfg, bg=config.COLOR_BG)
            cbtns.pack(side="bottom", fill="x", padx=12, pady=10)
            tk.Button(cbtns, text="🔍 Détecter", font=config.FONT_MED,
                      bg=config.COLOR_PRIMARY, fg="white", bd=0, command=detect
                      ).pack(side="left", expand=True, fill="x", padx=3, ipady=8)
            tk.Button(cbtns, text="⌨ Saisir MAC", font=config.FONT_MED,
                      bg=config.COLOR_CARD, fg="white", bd=0, command=manual
                      ).pack(side="left", expand=True, fill="x", padx=3, ipady=8)
            tk.Button(cbtns, text="Fermer", font=config.FONT_MED,
                      bg=config.COLOR_CARD, fg="white", bd=0, command=close_cfg
                      ).pack(side="left", expand=True, fill="x", padx=3, ipady=8)

        tk.Button(bottom, text="+ Ajouter", font=config.FONT_MED,
                  bg=config.COLOR_PRIMARY, fg="white", bd=0, padx=12, pady=8,
                  command=add).pack(side="left", expand=True, fill="x", padx=3)
        tk.Button(bottom, text="🌡 Pistolet BLE", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=12, pady=8,
                  command=config_thermo).pack(side="right", expand=True, fill="x", padx=3)

        self.wait_window(top)
        # Reconnecte au pistolet (la MAC a peut-etre ete modifiee)
        self._start_conn()

    def _back(self):
        self._stop_conn()  # ferme la liaison persistante
        self.destroy()
        self.on_done()
