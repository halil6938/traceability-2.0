"""Menu principal + routeur d'écrans."""
import json
import tkinter as tk
import os
import threading
import time
from datetime import date, datetime, timedelta

from . import (config, database, heartbeat, network, remote_lock, screen,
               ui_common, ui_rounded, updater, usb_manager)
from .camera_scan import CameraScanScreen
from .ui_common import Button, WifiIcon, install_tap_guard
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
        self._sleep_overlay = None
        self._alarme = None
        self._releve_en_cours = False     # releve automatique en cours (Bluetooth)
        self._sync_en_cours = False       # copie des photos vers la cle en cours

        # Reglages a distance memorises (couleurs...) : appliques AVANT de
        # construire les ecrans pour qu'ils prennent effet des le demarrage.
        _locked_cache, _msg_cache, _cfg_cache = remote_lock.cached_state()
        remote_lock.apply_config(_cfg_cache)
        remote_lock.config_changee()      # etat de depart : rien a redessiner

        if not database.get_meta("setup_done"):
            SetupWizard(self, self.show_menu)
        else:
            self.show_menu()

        # Verrou a distance : si le dernier etat connu etait « bloque », on
        # affiche le blocage immediatement (avant meme le reseau) -> survit
        # au redemarrage et hors ligne.
        if _locked_cache:
            self._show_lock_overlay(_msg_cache)
        self._last_locked = _locked_cache
        self.after(2000, self._lock_tick)

        # Mise a jour automatique du code depuis GitHub
        self.after(60_000, self._update_tick)

        # Signe de vie Telegram (en ligne + version)
        self.after(20_000, self._heartbeat_tick)

        # Veille de l'ecran, geree par l'appli (voir _sleep)
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

        # La nuit, retour au menu de tout ecran laisse ouvert (voir _nuit_tick)
        self.after(60_000, self._nuit_tick)

    def _clear(self):
        if self.current and self.current.winfo_exists():
            self.current.destroy()
        self.current = None

    def show_menu(self):
        self._clear()
        self.current = MainMenu(self, self)
        install_tap_guard(self.current)
        self.after(800, self._check_ble_alert)

    def show_scan(self):
        self._clear()
        self.current = CameraScanScreen(self, self.show_menu)
        install_tap_guard(self.current)

    def show_temperature(self):
        self._clear()
        self.current = TemperatureScreen(self, self.show_menu)
        install_tap_guard(self.current)

    def show_reception(self):
        self._clear()
        self.current = ReceptionScreen(self, self.show_menu)
        install_tap_guard(self.current)

    def show_history(self):
        self._clear()
        self.current = HistoryScreen(self, self.show_menu)
        install_tap_guard(self.current)

    def show_settings(self):
        self._clear()
        self.current = SettingsScreen(self, self.show_menu)
        install_tap_guard(self.current)

    def _periodic_sync(self):
        """Copie des photos en attente vers la cle, en tache de fond : faite
        sur l'ecran, elle le figerait le temps de copier (plusieurs secondes
        au rebranchement de la cle apres une journee sans elle)."""
        if not self._sync_en_cours:
            self._sync_en_cours = True

            def copier():
                try:
                    usb_manager.sync_pending()
                except Exception:
                    pass
                finally:
                    self._sync_en_cours = False

            threading.Thread(target=copier, daemon=True).start()
        self.after(30_000, self._periodic_sync)

    # --- Scheduler BLE 3h du matin ---

    def _ble_tick(self):
        """Releve automatique quotidien, a partir de 3 h. S'il n'a pas pu se
        faire a 3 h (Pi eteint, appli redemarree par une mise a jour), il se
        fait des que possible dans la journee au lieu d'etre perdu."""
        now = datetime.now()
        if now.hour >= 3 and not self._releve_en_cours:
            today = date.today().isoformat()
            if database.get_meta("ble_auto_date") != today:
                database.set_meta("ble_auto_date", today)
                self._releve_en_cours = True
                threading.Thread(target=self._do_ble_auto, daemon=True).start()
        self._check_ble_alert()       # une alerte ne doit pas attendre le menu
        self.after(60_000, self._ble_tick)

    def _do_ble_auto(self):
        try:
            self._releve_auto()
        finally:
            self._releve_en_cours = False

    def _releve_auto(self):
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
                # une valeur saisie a la main ce jour-la n'est pas ecrasee
                database.save_sensor_reading(s["device_id"], today, temp)
                dev = devices.get(s["device_id"])
                if dev and temp > dev["temp_max"]:
                    alerts.append(f"{dev['name']} : {temp:.1f}°C — trop chaud "
                                  f"(max autorisé : {dev['temp_max']:g}°C)")
                elif dev and temp < dev["temp_min"]:
                    # un frigo qui gele les produits est aussi un probleme
                    alerts.append(f"{dev['name']} : {temp:.1f}°C — trop froid "
                                  f"(min autorisé : {dev['temp_min']:g}°C)")
        if alerts:
            database.set_meta("ble_temp_alert", "\n".join(alerts))

    # --- Alarme temperature ---

    def _check_ble_alert(self):
        msg = database.get_meta("ble_temp_alert")
        if msg:
            database.set_meta("ble_temp_alert", "")
            if self._sleep_overlay is not None:
                self._wake()          # une alerte rallume l'ecran
            self._show_alarm(msg)

    def _show_alarm(self, message):
        if self._alarme is not None and self._alarme.winfo_exists():
            self._alarme.destroy()
        overlay = tk.Frame(self, bg=config.COLOR_DANGER)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._alarme = overlay
        self.relever_voiles()

        tk.Label(overlay, text="⚠  ALERTE TEMPERATURE",
                 bg=config.COLOR_DANGER, fg="white",
                 font=config.FONT_TITLE).pack(pady=(60, 24))

        for line in message.split("\n"):
            tk.Label(overlay, text=line,
                     bg=config.COLOR_DANGER, fg="white",
                     font=config.FONT_BIG).pack(pady=4)

        tk.Label(overlay,
                 text="\nTempérature hors des seuils !\nVérifiez vos appareils.",
                 bg=config.COLOR_DANGER, fg="white",
                 font=config.FONT_MED, justify="center").pack(pady=16)

        Button(overlay, text="   OK   ", font=config.FONT_BIG,
                  bg="white", fg=config.COLOR_DANGER, bd=0,
                  padx=40, pady=16,
                  command=overlay.destroy).pack()

    # --- Purge automatique ---

    def _purge_tick(self):
        """Purge quotidienne des vieilles photos, a partir de 2 h (ou des que
        possible si le Pi etait eteint a cette heure-la)."""
        now = datetime.now()
        if now.hour >= 2:
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

    def seconds_idle(self):
        """Temps ecoule depuis le dernier contact tactile, tous ecrans
        confondus (utilise par les ecrans a retour auto, voir ui_common)."""
        return time.time() - self._last_touch

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
        self.relever_voiles()
        threading.Thread(target=screen.off, daemon=True).start()

    def _wake(self, _event=None):
        """Premier contact : on rallume, sans rien declencher d'autre."""
        if self._sleep_overlay is not None:
            self._sleep_overlay.destroy()
            self._sleep_overlay = None
        self._last_touch = time.time()
        threading.Thread(target=screen.on, daemon=True).start()
        return "break"

    # --- Superpositions : alerte, verrou, veille ---

    def relever_voiles(self):
        """Remet les superpositions devant l'ecran courant, dans l'ordre :
        alerte, puis verrouillage, puis veille (tout en haut). Appele a chaque
        changement d'ecran : un nouvel ecran se place sinon au-dessus d'elles
        (un retour automatique au menu rendait l'appli utilisable malgre le
        verrouillage)."""
        for voile in (self._alarme, self._lock_overlay, self._sleep_overlay):
            if voile is not None and voile.winfo_exists():
                voile.lift()

    # --- Nuit : retour au menu ---

    def _nuit_tick(self):
        """De nuit, un ecran laisse ouvert (Reception, Releve...) est ferme
        apres un long moment sans contact : il garderait le Bluetooth reserve
        (le releve de 3 h serait bloque), empecherait les mises a jour, et le
        pistolet serait recherche toute la nuit."""
        debut, fin = config.NUIT_HEURES
        h = datetime.now().hour
        nuit = (h >= debut or h < fin) if debut > fin else (debut <= h < fin)
        if (nuit and self.seconds_idle() > config.NUIT_INACTIVITE_S
                and self._ecran_affiche() is not None
                and not isinstance(self._ecran_affiche(), MainMenu)):
            ui_common.close_all_modals()
            # laisser se terminer les fenetres qui viennent d'etre fermees
            self.after(300, self._retour_nuit)
        self.after(60_000, self._nuit_tick)

    def _ecran_affiche(self):
        """L'ecran reellement affiche (les sous-ecrans de l'historique ne sont
        pas enregistres dans self.current)."""
        for w in self.winfo_children():
            if isinstance(w, tk.Frame) and w.winfo_manager() == "pack":
                return w
        return None

    def _retour_nuit(self):
        ecran = self._ecran_affiche()
        if ecran is None or isinstance(ecran, MainMenu):
            return
        retour = getattr(ecran, "_back", None)
        if retour is not None:    # (l'assistant de premiere installation n'en a
            retour()              # pas : il reste ouvert) ; ferme proprement
                                  # Bluetooth, camera...

    # --- Mise a jour automatique ---

    def _update_ready(self):
        """Conditions pour appliquer une mise a jour maintenant : appli au
        repos (menu principal) et, en mode « auto », heures creuses — sauf si
        la mise a jour attend depuis trop longtemps (Pi eteint la nuit)."""
        if not isinstance(self.current, MainMenu):
            return False            # ne jamais interrompre un scan ou une mesure
        if self._releve_en_cours:
            return False            # ni le releve automatique des capteurs
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
            if (remote_lock.config_changee() and isinstance(self.current, MainMenu)
                    and not ui_common.modales_ouvertes()):
                self.show_menu()      # nouveaux reglages (style, couleurs) visibles
            if box["res"] is not None:
                locked, message = box["res"]
                if locked:
                    self._show_lock_overlay(message)
                else:
                    self._hide_lock_overlay()
                if locked != self._last_locked:
                    # confirmer tout de suite que l'ordre a ete recu, sans
                    # attendre le prochain signe de vie (30 min)
                    self._last_locked = locked
                    threading.Thread(target=self._do_heartbeat,
                                     daemon=True).start()
            self.after(config.REMOTE_POLL_S * 1000, self._lock_tick)

        threading.Thread(target=do, daemon=True).start()
        self.after(200, poll)

    def _show_lock_overlay(self, message):
        """Overlay plein ecran non fermable : bloque toute l'appli."""
        if self._lock_overlay is not None and self._lock_overlay.winfo_exists():
            # deja affiche : on met juste le message a jour
            self._lock_msg.config(text=message or "Application suspendue.")
            self.relever_voiles()
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
        self.relever_voiles()

    def _hide_lock_overlay(self):
        if self._lock_overlay is not None:
            if self._lock_overlay.winfo_exists():
                self._lock_overlay.destroy()
            self._lock_overlay = None


def _resume(noms, maxi=3):
    """« A, B, C et 4 autres » : la ligne d'alerte doit tenir sur l'ecran."""
    if len(noms) <= maxi:
        return ", ".join(noms)
    return ", ".join(noms[:maxi]) + f" et {len(noms) - maxi} autre(s)"


class MainMenu(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=config.COLOR_BG)
        self.app = app
        self._tours = 0
        self.pack(fill="both", expand=True)

        # En-tete : titre, puis (de droite a gauche) USB, WiFi, horloge
        header = tk.Frame(self, bg=config.COLOR_BG)
        header.pack(fill="x", padx=16, pady=(10, 4))
        tk.Label(header, text="Traceability", bg=config.COLOR_BG,
                 fg=config.COLOR_FG, font=config.FONT_TITLE).pack(side="left")
        self.usb_lbl = tk.Label(header, text="USB ✗", bg=config.COLOR_BG,
                                fg=config.COLOR_WARNING, font=config.FONT_SMALL)
        self.usb_lbl.pack(side="right")
        self.wifi = WifiIcon(header, config.COLOR_BG)
        self.wifi.pack(side="right", padx=(0, 10))
        self.clock_lbl = tk.Label(header, text="", bg=config.COLOR_BG,
                                  fg=config.COLOR_MUTED, font=config.FONT_SMALL)
        self.clock_lbl.pack(side="right", padx=12)

        # Alerte releves manquants (veille)
        self.alert = tk.Label(self, text="", bg=config.COLOR_BG, anchor="w",
                              fg=config.COLOR_WARNING, font=config.FONT_MED)
        self.alert.pack(fill="x", padx=16)

        if config.STYLE == "rounded":
            self._build_rounded()
        else:
            self._build_classic()

        self._refresh_status()
        self._check_alerts()

    def _build_rounded(self):
        """Cases aux coins arrondis qui s'enfoncent au toucher."""
        marge, ecart = 20, 28           # espace large : le doigt deborde
        larg = (config.SCREEN_W - 2 * marge - 2 * ecart) // 3
        haut = config.SCREEN_H - 206
        cartes = tk.Frame(self, bg=config.COLOR_BG)
        cartes.pack(padx=marge, pady=(6, 0))
        specs = [
            ("📦", "Réception", "Température des produits livrés",
             config.COLOR_WARNING, self.app.show_reception),
            ("📷", "Scan ticket", "Prendre une photo automatique",
             config.COLOR_PRIMARY, self.app.show_scan),
            ("🌡", "Relevé de température", "Saisir les temperatures du jour",
             config.COLOR_SUCCESS, self.app.show_temperature),
        ]
        for i, (icone, titre, sous, couleur, cmd) in enumerate(specs):
            ui_rounded.Card(cartes, larg, haut, icone, titre, sous, couleur,
                            cmd).grid(row=0, column=i,
                                      padx=(0 if i == 0 else ecart, 0))
        bas = tk.Frame(self, bg=config.COLOR_BG)
        bas.pack(padx=marge, pady=(20, 0))
        moitie = (config.SCREEN_W - 2 * marge - ecart) // 2
        ui_rounded.Bouton(bas, moitie, 56, "📊 Historique",
                          self.app.show_history).grid(row=0, column=0)
        ui_rounded.Bouton(bas, moitie, 56, "⚙ Paramètres",
                          self.app.show_settings).grid(row=0, column=1,
                                                       padx=(ecart, 0))

    def _build_classic(self):
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
        Button(bottom, text="📊 Historique", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=16, pady=10,
                  command=self.app.show_history).pack(side="left", expand=True, fill="x", padx=4)
        Button(bottom, text="⚙ Paramètres", font=config.FONT_MED,
                  bg=config.COLOR_CARD, fg="white", bd=0, padx=16, pady=10,
                  command=self.app.show_settings).pack(side="right", expand=True, fill="x", padx=4)

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
        """En-tete (toutes les 3 s) : horloge, cle USB, internet. Les tests
        reseau tournent en tache de fond au plus une fois par minute ; ici on
        ne fait que lire le dernier resultat."""
        network.actualiser_si_besoin()
        en_ligne, heure_ok = network.etat()
        if self.wifi.online != en_ligne:
            self.wifi.set_online(en_ligne)
        horloge = datetime.now().strftime("%d/%m/%Y  %H:%M")
        if heure_ok is False:
            # sans internet au demarrage, le Pi (sans horloge interne) peut
            # etre a la mauvaise heure : les enregistrements seraient mal dates
            self.clock_lbl.config(text="⚠ " + horloge + " (heure non vérifiée)",
                                  fg=config.COLOR_WARNING)
        else:
            self.clock_lbl.config(text=horloge, fg=config.COLOR_MUTED)
        usb_ok = usb_manager.find_usb_mount() is not None
        self.usb_lbl.config(
            text="USB ✓" if usb_ok else "USB ✗",
            fg=config.COLOR_SUCCESS if usb_ok else config.COLOR_WARNING,
        )
        self._tours += 1
        if self._tours % 20 == 0:      # environ une fois par minute
            self._check_alerts()
        self.after(3_000, self._refresh_status)

    def _check_alerts(self):
        """Ligne d'alerte : releves manquants, piles faibles des capteurs."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        messages = []
        missing = [info["name"] for info in database.last_reading_date_per_device()
                   if info["last_date"] is None or info["last_date"] < yesterday]
        if missing:
            messages.append("⚠ Relevé manquant : " + _resume(missing))
        try:
            faibles = set(json.loads(database.get_meta("capteurs_pile_faible", "") or "[]"))
        except ValueError:
            faibles = set()
        if faibles:
            noms = [s["device_name"] or s["label"] for s in database.list_ble_sensors()
                    if s["mac"].lower() in faibles]
            if noms:
                messages.append("🔋 Pile faible : " + _resume(noms, 2))
        texte = "   ·   ".join(messages)
        if len(texte) > 75 and len(missing) > 1:
            # trop long pour une ligne : le nombre d'appareils au lieu des noms
            messages[0] = f"⚠ Relevé manquant : {len(missing)} appareils"
            texte = "   ·   ".join(messages)
        self.alert.config(text=texte)
