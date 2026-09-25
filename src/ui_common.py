"""Widgets et helpers UI communs, optimises pour ecran tactile 800x480 paysage."""
import time
import tkinter as tk
from . import config, ui_rounded


# AUCUNE fenetre modale dans cette appli.
#
# Sur le Pi, l'appli tourne en plein ecran -topmost. Un Toplevel modal
# (focus exclusif via grab_set) s'y est revele capable de figer completement
# l'application : la fenetre passe derriere la fenetre principale, ou n'est
# pas refermable, mais capte tous les clics -> plus rien ne repond, et il faut
# redemarrer le service. Le probleme est survenu sur plusieurs ecrans.
#
# Tout ce qui « s'ouvre par-dessus » est donc un CADRE superpose : un voile
# plein ecran (qui absorbe les clics et donne l'effet modal) contenant un
# panneau centre. Un cadre ne prend jamais le focus exclusif et ne peut pas
# passer derriere la fenetre principale : il ne peut donc pas figer l'appli.
# L'API est inchangee pour les appelants (parent.wait_window fonctionne aussi
# bien sur un cadre que sur une fenetre).
_OPEN_MODALS = []


# Minuteurs des ecrans fermes. widget.after() enregistre une commande que Tk
# supprime avec le widget : si le minuteur n'avait pas encore sonne, Tk tente
# ensuite d'appeler une commande disparue et ecrit « invalid command name »
# dans le journal systeme — a chaque changement d'ecran. On annule donc les
# minuteurs d'un widget au moment ou il est detruit.
_after_origine = tk.Misc.after
_destroy_origine = tk.BaseWidget.destroy


def _after(self, ms, func=None, *args):
    ident = _after_origine(self, ms, func, *args)
    if func is not None:
        attente = self.__dict__.setdefault("_minuteurs", [])
        attente.append(ident)
        if len(attente) > 64:           # oublier ceux qui ont deja sonne
            encore = set(self.tk.splitlist(self.tk.call("after", "info")))
            attente[:] = [i for i in attente if i in encore]
    return ident


def _destroy(self):
    for ident in self.__dict__.pop("_minuteurs", ()):
        try:
            self.after_cancel(ident)
        except (tk.TclError, ValueError):
            pass
    _destroy_origine(self)


tk.Misc.after = _after
tk.BaseWidget.destroy = _destroy


class WifiIcon(tk.Canvas):
    """Icone WiFi : verte connecte, rouge barree deconnecte, grise inconnu."""

    def __init__(self, parent, bg):
        super().__init__(parent, width=38, height=28, bg=bg,
                         highlightthickness=0, bd=0)
        self._bg = bg
        self.online = None
        self.set_online(None)

    def set_online(self, online):
        self.online = online
        color = (config.COLOR_MUTED if online is None
                 else config.COLOR_SUCCESS if online else config.COLOR_DANGER)
        self.delete("all")
        cx, cy = 19, 24
        for r in (8, 14, 20):
            self.create_arc(cx - r, cy - r, cx + r, cy + r, start=45, extent=90,
                            style="arc", outline=color, width=3)
        self.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=color, outline=color)
        if online is False:
            self.create_line(5, 3, 33, 26, fill=self._bg, width=7)   # marge
            self.create_line(5, 3, 33, 26, fill=color, width=3)      # la barre


# Protection contre les « doubles touches » : un contact parasite ou un second
# appui impatient juste apres un changement d'ecran atterrirait sur un bouton
# du NOUVEL ecran (mauvais menu, mauvais fournisseur...). Pendant un court
# instant apres l'arrivee sur un ecran, ses widgets ignorent le toucher.
_TAP_TAG = "TapGuard"
_guard_until = 0.0


def _swallow(_event):
    return "break" if time.time() < _guard_until else None


def install_tap_guard(screen, seconds=0.4):
    """A appeler quand un ecran vient de s'afficher : ses widgets (present a
    cet instant) ignorent le toucher pendant `seconds`."""
    global _guard_until
    _guard_until = time.time() + seconds
    root = screen.winfo_toplevel()
    if not getattr(root, "_tap_guard_pret", False):
        # une seule fois : chaque bind_class enregistre une commande Tk jamais
        # liberee, qui s'accumulerait a chaque changement d'ecran
        root.bind_class(_TAP_TAG, "<ButtonPress-1>", _swallow)
        root.bind_class(_TAP_TAG, "<ButtonRelease-1>", _swallow)
        root._tap_guard_pret = True

    def poser(w):
        tags = w.bindtags()
        if _TAP_TAG not in tags:
            w.bindtags((_TAP_TAG,) + tags)
        for enfant in w.winfo_children():
            poser(enfant)

    poser(screen)
    # Un nouvel ecran se place au-dessus de tout : verrouillage, alerte et
    # veille doivent repasser devant lui (sinon un retour automatique au menu
    # rendrait l'appli utilisable malgre le verrouillage).
    relever = getattr(root, "relever_voiles", None)
    if relever is not None:
        relever()


def bind_drag_scroll(canvas, container=None, horizontal=False):
    """Permet de faire defiler `canvas` en glissant le doigt n'importe ou sur
    son contenu, pas seulement sur la barre laterale (trop etroite au doigt).
    Le glissement suit exactement le doigt (pas de scroll par a-coups).

    Se pose sur le canevas et tout ce qu'il contient, SAUF les boutons :
    demarrer un glissement sur un bouton ne doit jamais faire defiler a sa
    place, pour ne pas gener un appui. A rappeler apres chaque reconstruction
    du contenu : seuls les widgets nouveaux sont equipes (un widget deja
    equipe ne l'est pas deux fois, sinon le defilement s'accelererait)."""
    etat = {"x": 0, "y": 0}

    def presser(event):
        etat["x"], etat["y"] = event.x_root, event.y_root

    def glisser(event):
        bbox = canvas.bbox("all")
        if bbox is None:
            return
        dx, dy = event.x_root - etat["x"], event.y_root - etat["y"]
        etat["x"], etat["y"] = event.x_root, event.y_root
        hauteur = bbox[3] - bbox[1]
        if hauteur > canvas.winfo_height():
            haut, _ = canvas.yview()
            canvas.yview_moveto(max(0.0, min(1.0, haut - dy / hauteur)))
        largeur = bbox[2] - bbox[0]
        if horizontal and largeur > canvas.winfo_width():
            gauche, _ = canvas.xview()
            canvas.xview_moveto(max(0.0, min(1.0, gauche - dx / largeur)))

    def poser(widget):
        if not getattr(widget, "_glissement", False):
            widget.bind("<ButtonPress-1>", presser, add="+")
            widget.bind("<B1-Motion>", glisser, add="+")
            widget._glissement = True
        for enfant in widget.winfo_children():
            if not est_bouton(enfant):
                poser(enfant)

    poser(canvas)
    if container is not None and container.master is not canvas:
        poser(container)


class ZoneDefilante(tk.Frame):
    """Liste qui defile (au doigt ou par la barre) : ce qui ne tient pas a
    l'ecran reste accessible au lieu d'etre rogne. Les lignes se placent dans
    .interieur ; appeler .actualiser() apres chaque reconstruction.

    Le canevas demande une hauteur minime : la zone prend la place restante
    sans jamais pousser hors de l'ecran les boutons places en dessous (a
    condition de packer ces boutons AVANT la zone, cote « bottom »)."""

    def __init__(self, parent, bg, horizontal=False):
        super().__init__(parent, bg=bg)
        self._horizontal = horizontal
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0,
                                width=40, height=40)
        self.barre = tk.Scrollbar(self, orient="vertical",
                                  command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.barre.set)
        if horizontal:
            self.barre_h = tk.Scrollbar(self, orient="horizontal",
                                        command=self.canvas.xview)
            self.canvas.configure(xscrollcommand=self.barre_h.set)
            self.barre_h.pack(side="bottom", fill="x")
        self.barre.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.interieur = tk.Frame(self.canvas, bg=bg)
        self._fenetre = self.canvas.create_window((0, 0), window=self.interieur,
                                                  anchor="nw")
        self.interieur.bind("<Configure>", lambda e: self._region())
        self.canvas.bind("<Configure>", self._taille)

    def _taille(self, event):
        if not self._horizontal:        # les lignes occupent toute la largeur
            self.canvas.itemconfigure(self._fenetre, width=event.width)
        self._region()

    def _region(self):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def vider(self):
        for w in self.interieur.winfo_children():
            w.destroy()
        self.canvas.yview_moveto(0)
        self.canvas.xview_moveto(0)

    def actualiser(self):
        bind_drag_scroll(self.canvas, horizontal=self._horizontal)


def schedule_auto_return(widget, seconds, back_fn, _tick_ms=10_000):
    """Revient automatiquement (back_fn) apres `seconds` sans contact tactile
    nulle part dans l'appli. S'appuie sur le suivi tactile deja tenu par App
    pour la veille d'ecran (App.seconds_idle) plutot que d'ajouter un second
    bind_all global, qu'on ne pourrait pas retirer independamment de celui de
    la veille. Suspendu tant qu'une fenetre superposee (numpad, confirmation)
    est ouverte, pour ne jamais detruire un ecran sous un panneau actif.
    A appeler une fois dans __init__, apres avoir construit l'ecran."""
    def tick():
        if not widget.winfo_exists():
            return
        if not modales_ouvertes() and widget.winfo_toplevel().seconds_idle() > seconds:
            back_fn()
            return
        widget.after(_tick_ms, tick)
    widget.after(_tick_ms, tick)


def open_modal(parent, w, h, color=None):
    """Panneau superpose et centre, en remplacement des fenetres modales.
    Fermer avec close_modal()."""
    root = parent.winfo_toplevel()
    veil = tk.Frame(root, bg=config.COLOR_BG)   # absorbe les clics exterieurs
    veil.place(relx=0, rely=0, relwidth=1, relheight=1)
    panel = tk.Frame(veil, bg=config.COLOR_BG)
    style_popup(panel, color)
    panel.place(relx=0.5, rely=0.5, anchor="center",
                width=min(w, config.SCREEN_W - 4),
                height=min(h, config.SCREEN_H - 4))
    veil.lift()
    panel._veil = veil
    _OPEN_MODALS.append(panel)
    return panel


def ajuster_modal(panel):
    """Agrandit le panneau si son contenu ne tient pas (police plus grande que
    celle du Pi, titre sur deux lignes...), sans jamais depasser l'ecran. A
    appeler une fois le contenu construit."""
    panel.update_idletasks()
    infos = panel.place_info()
    w = max(int(float(infos.get("width") or 0)), panel.winfo_reqwidth())
    h = max(int(float(infos.get("height") or 0)), panel.winfo_reqheight())
    panel.place_configure(width=min(w, config.SCREEN_W - 4),
                          height=min(h, config.SCREEN_H - 4))


def modales_ouvertes():
    """Panneaux superposes encore affiches. Ceux qui ont disparu entre-temps
    (detruits avec leur ecran) sont oublies : un panneau fantome suspendrait
    sinon pour toujours le retour automatique au menu."""
    _OPEN_MODALS[:] = [p for p in _OPEN_MODALS if p.winfo_exists()]
    return _OPEN_MODALS


def close_modal(panel):
    """Ferme le panneau et son voile."""
    if panel in _OPEN_MODALS:
        _OPEN_MODALS.remove(panel)
    try:
        getattr(panel, "_veil", panel).destroy()
    except Exception:
        pass


def close_all_modals():
    """Referme tous les panneaux ouverts : filet de securite si une erreur
    interrompt la construction de l'un d'eux (son voile masquerait sinon
    l'ecran)."""
    for panel in list(_OPEN_MODALS):
        close_modal(panel)


def Button(master, **kw):
    """Bouton de toute l'appli : arrondi et qui s'enfonce en style « rounded »,
    bouton Tk ordinaire sinon. Meme interface dans les deux cas."""
    if config.STYLE == "rounded":
        return ui_rounded.RoundedButton(master, **kw)
    return tk.Button(master, **kw)


def est_bouton(widget):
    return isinstance(widget, tk.Button) or getattr(widget, "_bouton", False)


def make_button(master, text, command, bg=None, fg="white", font=None, **kw):
    return Button(
        master, text=text, command=command,
        bg=bg or config.COLOR_PRIMARY, fg=fg,
        font=font or config.FONT_BIG,
        activebackground=config.COLOR_MUTED,
        bd=0, relief="flat", padx=16, pady=12,
        highlightthickness=0, **kw,
    )


def style_popup(top, color=None):
    """Cadre visible autour d'un popup modal pour le distinguer de la fenetre
    qui se trouve derriere (pas de decoration native car overrideredirect)."""
    top.configure(highlightthickness=4,
                  highlightbackground=color or config.COLOR_PRIMARY,
                  highlightcolor=color or config.COLOR_PRIMARY)


def numpad_popup(parent, title="Saisie", initial="", allow_negative=True, allow_decimal=True):
    """Clavier numerique tactile modal. Retourne la chaine saisie ou None."""
    # un peu plus haut si le titre tient sur deux lignes
    top = open_modal(parent, 340, 385 if "\n" in title else 360)

    tk.Label(top, text=title, bg=config.COLOR_BG, fg=config.COLOR_FG,
             font=config.FONT_MED, wraplength=320,
             justify="center").pack(pady=(10, 4))

    value = tk.StringVar(value=initial)
    entry = tk.Label(top, textvariable=value, bg=config.COLOR_CARD, fg=config.COLOR_FG,
                     font=config.FONT_BIG, width=14, anchor="e", padx=10, pady=10)
    entry.pack(pady=4)

    grid = tk.Frame(top, bg=config.COLOR_BG)
    grid.pack(pady=6)

    def press(ch):
        cur = value.get()
        if ch == "⌫":
            value.set(cur[:-1])
        elif ch == "±":
            if not allow_negative:
                return
            if cur.startswith("-"):
                value.set(cur[1:])
            else:
                value.set("-" + cur)
        elif ch == ".":
            if not allow_decimal or "." in cur:
                return
            value.set(cur + ".")
        else:
            value.set(cur + ch)

    buttons = [
        ["7", "8", "9"],
        ["4", "5", "6"],
        ["1", "2", "3"],
        ["±", "0", "."],
    ]
    for r, row in enumerate(buttons):
        for c, ch in enumerate(row):
            Button(grid, text=ch, font=config.FONT_BIG, width=4, height=1,
                      bg=config.COLOR_CARD, fg=config.COLOR_FG, bd=0,
                      command=lambda x=ch: press(x)).grid(row=r, column=c, padx=3, pady=3)
    Button(grid, text="⌫", font=config.FONT_BIG, width=4, height=1,
              bg=config.COLOR_DANGER, fg="white", bd=0,
              command=lambda: press("⌫")).grid(row=0, column=3, rowspan=4, sticky="ns", padx=3, pady=3)

    result = {"v": None}

    def ok():
        result["v"] = value.get()
        close_modal(top)

    def cancel():
        close_modal(top)

    # OK / Annuler places AVANT les touches dans l'ordre de placement : si la
    # place manque, ce sont les touches qui se resserrent, jamais ces boutons
    btns = tk.Frame(top, bg=config.COLOR_BG)
    btns.pack(side="bottom", pady=8, fill="x", padx=12, before=grid)
    Button(btns, text="Annuler", font=config.FONT_MED, bg=config.COLOR_CARD,
              fg=config.COLOR_FG, bd=0, command=cancel).pack(side="left", expand=True, fill="x", padx=4, ipady=8)
    Button(btns, text="OK", font=config.FONT_MED, bg=config.COLOR_SUCCESS,
              fg="white", bd=0, command=ok).pack(side="right", expand=True, fill="x", padx=4, ipady=8)

    ajuster_modal(top)
    parent.wait_window(top)
    return result["v"]


def text_popup(parent, title="Saisie", initial=""):
    """Clavier texte simplifie (azerty). Retourne la chaine ou None."""
    w = min(620, config.SCREEN_W - 4)
    h = min(440, config.SCREEN_H - 10)
    top = open_modal(parent, w, h)

    tk.Label(top, text=title, bg=config.COLOR_BG, fg=config.COLOR_FG,
             font=config.FONT_MED).pack(pady=(6, 2))

    value = tk.StringVar(value=initial)
    entry = tk.Label(top, textvariable=value, bg=config.COLOR_CARD, fg=config.COLOR_FG,
                     font=config.FONT_BIG, anchor="w", padx=10, pady=6)
    entry.pack(pady=2, padx=6, fill="x")

    upper = [False]

    keyboard = [
        list("AZERTYUIOP"),
        list("QSDFGHJKLM"),
        list("WXCVBN0123"),
        list("456789-_ /"),
        list("ÉÈÊÀÇ'&.,:"),     # accents, apostrophe, et « : » des adresses MAC
    ]

    # Grille a colonnes de poids egal : remplit exactement la largeur de la fenetre
    grid = tk.Frame(top, bg=config.COLOR_BG)
    grid.pack(fill="x", padx=4, pady=2)
    for col in range(10):
        grid.columnconfigure(col, weight=1)

    touches = []

    def press(ch):
        value.set(value.get() + (ch if upper[0] else ch.lower()))

    def backspace():
        value.set(value.get()[:-1])

    def toggle_case():
        upper[0] = not upper[0]
        # les touches montrent ce qu'elles ecriront, et Maj montre son etat
        for bouton, ch in touches:
            bouton.config(text=ch if upper[0] else ch.lower())
        maj.config(bg=config.COLOR_PRIMARY if upper[0] else config.COLOR_CARD,
                   fg="white" if upper[0] else config.COLOR_FG)

    for r, row in enumerate(keyboard):
        for c, ch in enumerate(row):
            bouton = Button(grid, text=ch.lower(), font=config.FONT_SMALL,
                            bg=config.COLOR_CARD, fg=config.COLOR_FG, bd=0,
                            command=lambda x=ch: press(x))
            bouton.grid(row=r, column=c, sticky="ew", padx=1, pady=1, ipady=5)
            touches.append((bouton, ch))

    # Barre Espace / Maj / Suppr — meme principe grid a 3 colonnes proportionnelles
    actions = tk.Frame(top, bg=config.COLOR_BG)
    actions.pack(fill="x", padx=4, pady=2)
    actions.columnconfigure(0, weight=4)
    actions.columnconfigure(1, weight=2)
    actions.columnconfigure(2, weight=2)
    Button(actions, text="Espace", font=config.FONT_SMALL,
              bg=config.COLOR_CARD, fg=config.COLOR_FG, bd=0,
              command=lambda: press(" ")
              ).grid(row=0, column=0, sticky="ew", padx=1, pady=2, ipady=7)
    maj = Button(actions, text="Maj ⇧", font=config.FONT_SMALL,
                 bg=config.COLOR_CARD, fg=config.COLOR_FG, bd=0,
                 command=toggle_case)
    maj.grid(row=0, column=1, sticky="ew", padx=1, pady=2, ipady=7)
    Button(actions, text="⌫", font=config.FONT_SMALL,
              bg=config.COLOR_DANGER, fg="white", bd=0,
              command=backspace
              ).grid(row=0, column=2, sticky="ew", padx=1, pady=2, ipady=7)

    result = {"v": None}

    def ok():
        result["v"] = value.get().strip()
        close_modal(top)

    btns = tk.Frame(top, bg=config.COLOR_BG)
    btns.pack(side="bottom", pady=6, fill="x", padx=8, before=grid)
    Button(btns, text="Annuler", font=config.FONT_MED, bg=config.COLOR_CARD,
              fg=config.COLOR_FG, bd=0, command=lambda: close_modal(top)
              ).pack(side="left", expand=True, fill="x", padx=4, ipady=8)
    Button(btns, text="OK", font=config.FONT_MED, bg=config.COLOR_SUCCESS,
              fg="white", bd=0, command=ok
              ).pack(side="right", expand=True, fill="x", padx=4, ipady=8)

    ajuster_modal(top)
    parent.wait_window(top)
    return result["v"]


def _dialog(parent, title, msg, color, buttons):
    """Popup de dialogue tactile maison. Les messagebox natives de Tk sont
    proscrites : elles s'ouvrent DERRIERE la fenetre plein ecran -topmost du
    Pi (invisibles mais modales -> appli qui semble gelee).
    buttons : liste de (texte, valeur, couleur). Retourne la valeur choisie."""
    top = open_modal(parent, 420, 230, color)

    tk.Label(top, text=title, bg=config.COLOR_BG, fg=config.COLOR_FG,
             font=config.FONT_BIG).pack(pady=(18, 6))
    message = tk.Label(top, text=msg, bg=config.COLOR_BG, fg=config.COLOR_MUTED,
                       font=config.FONT_MED, wraplength=380, justify="center")
    message.pack(pady=4, expand=True)

    result = {"v": buttons[0][1]}  # valeur du 1er bouton si fermeture forcee

    btns = tk.Frame(top, bg=config.COLOR_BG)
    btns.pack(side="bottom", fill="x", padx=12, pady=12, before=message)

    def choose(v):
        result["v"] = v
        close_modal(top)

    for text, val, bg in buttons:
        Button(btns, text=text, font=config.FONT_MED, bg=bg, fg="white",
                  bd=0, command=lambda v=val: choose(v)
                  ).pack(side="left", expand=True, fill="x", padx=4, ipady=10)

    ajuster_modal(top)
    parent.wait_window(top)
    return result["v"]


def confirm(parent, title, msg) -> bool:
    return _dialog(parent, title, msg, config.COLOR_WARNING, [
        ("Annuler", False, config.COLOR_CARD),
        ("Confirmer", True, config.COLOR_DANGER),
    ])


def info(parent, title, msg):
    _dialog(parent, title, msg, config.COLOR_SUCCESS,
            [("OK", None, config.COLOR_PRIMARY)])


def error(parent, title, msg):
    _dialog(parent, title, msg, config.COLOR_DANGER,
            [("OK", None, config.COLOR_CARD)])
