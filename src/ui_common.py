"""Widgets et helpers UI communs, optimises pour ecran tactile 800x480 paysage."""
import tkinter as tk
from . import config


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


def make_button(master, text, command, bg=None, fg="white", font=None, **kw):
    return tk.Button(
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
    top = open_modal(parent, 340, 360)

    tk.Label(top, text=title, bg=config.COLOR_BG, fg=config.COLOR_FG,
             font=config.FONT_MED).pack(pady=(10, 4))

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
            tk.Button(grid, text=ch, font=config.FONT_BIG, width=4, height=1,
                      bg=config.COLOR_CARD, fg=config.COLOR_FG, bd=0,
                      command=lambda x=ch: press(x)).grid(row=r, column=c, padx=3, pady=3)
    tk.Button(grid, text="⌫", font=config.FONT_BIG, width=4, height=1,
              bg=config.COLOR_DANGER, fg="white", bd=0,
              command=lambda: press("⌫")).grid(row=0, column=3, rowspan=4, sticky="ns", padx=3, pady=3)

    result = {"v": None}

    def ok():
        result["v"] = value.get()
        close_modal(top)

    def cancel():
        close_modal(top)

    btns = tk.Frame(top, bg=config.COLOR_BG)
    btns.pack(pady=8, fill="x", padx=12)
    tk.Button(btns, text="Annuler", font=config.FONT_MED, bg=config.COLOR_CARD,
              fg=config.COLOR_FG, bd=0, command=cancel).pack(side="left", expand=True, fill="x", padx=4, ipady=8)
    tk.Button(btns, text="OK", font=config.FONT_MED, bg=config.COLOR_SUCCESS,
              fg="white", bd=0, command=ok).pack(side="right", expand=True, fill="x", padx=4, ipady=8)

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
    ]

    # Grille a colonnes de poids egal : remplit exactement la largeur de la fenetre
    grid = tk.Frame(top, bg=config.COLOR_BG)
    grid.pack(fill="x", padx=4, pady=2)
    for col in range(10):
        grid.columnconfigure(col, weight=1)

    def press(ch):
        value.set(value.get() + (ch if upper[0] else ch.lower()))

    def backspace():
        value.set(value.get()[:-1])

    def toggle_case():
        upper[0] = not upper[0]

    for r, row in enumerate(keyboard):
        for c, ch in enumerate(row):
            tk.Button(grid, text=ch, font=config.FONT_SMALL,
                      bg=config.COLOR_CARD, fg=config.COLOR_FG, bd=0,
                      command=lambda x=ch: press(x)
                      ).grid(row=r, column=c, sticky="ew", padx=1, pady=2, ipady=7)

    # Barre Espace / Maj / Suppr — meme principe grid a 3 colonnes proportionnelles
    actions = tk.Frame(top, bg=config.COLOR_BG)
    actions.pack(fill="x", padx=4, pady=2)
    actions.columnconfigure(0, weight=4)
    actions.columnconfigure(1, weight=2)
    actions.columnconfigure(2, weight=2)
    tk.Button(actions, text="Espace", font=config.FONT_SMALL,
              bg=config.COLOR_CARD, fg=config.COLOR_FG, bd=0,
              command=lambda: press(" ")
              ).grid(row=0, column=0, sticky="ew", padx=1, pady=2, ipady=9)
    tk.Button(actions, text="Maj ⇧", font=config.FONT_SMALL,
              bg=config.COLOR_CARD, fg=config.COLOR_FG, bd=0,
              command=toggle_case
              ).grid(row=0, column=1, sticky="ew", padx=1, pady=2, ipady=9)
    tk.Button(actions, text="⌫", font=config.FONT_SMALL,
              bg=config.COLOR_DANGER, fg="white", bd=0,
              command=backspace
              ).grid(row=0, column=2, sticky="ew", padx=1, pady=2, ipady=9)

    result = {"v": None}

    def ok():
        result["v"] = value.get().strip()
        close_modal(top)

    btns = tk.Frame(top, bg=config.COLOR_BG)
    btns.pack(pady=6, fill="x", padx=8)
    tk.Button(btns, text="Annuler", font=config.FONT_MED, bg=config.COLOR_CARD,
              fg=config.COLOR_FG, bd=0, command=lambda: close_modal(top)
              ).pack(side="left", expand=True, fill="x", padx=4, ipady=8)
    tk.Button(btns, text="OK", font=config.FONT_MED, bg=config.COLOR_SUCCESS,
              fg="white", bd=0, command=ok
              ).pack(side="right", expand=True, fill="x", padx=4, ipady=8)

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
    tk.Label(top, text=msg, bg=config.COLOR_BG, fg=config.COLOR_MUTED,
             font=config.FONT_MED, wraplength=380, justify="center"
             ).pack(pady=4, expand=True)

    result = {"v": buttons[0][1]}  # valeur du 1er bouton si fermeture forcee

    btns = tk.Frame(top, bg=config.COLOR_BG)
    btns.pack(side="bottom", fill="x", padx=12, pady=12)

    def choose(v):
        result["v"] = v
        close_modal(top)

    for text, val, bg in buttons:
        tk.Button(btns, text=text, font=config.FONT_MED, bg=bg, fg="white",
                  bd=0, command=lambda v=val: choose(v)
                  ).pack(side="left", expand=True, fill="x", padx=4, ipady=10)

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
