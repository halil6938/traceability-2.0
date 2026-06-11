"""Widgets et helpers UI communs, optimises pour ecran tactile 800x480 paysage."""
import tkinter as tk
from tkinter import messagebox
from . import config


def make_button(master, text, command, bg=None, fg="white", font=None, **kw):
    return tk.Button(
        master, text=text, command=command,
        bg=bg or config.COLOR_PRIMARY, fg=fg,
        font=font or config.FONT_BIG,
        activebackground=config.COLOR_MUTED,
        bd=0, relief="flat", padx=16, pady=12,
        highlightthickness=0, **kw,
    )


def make_card(master, **kw):
    return tk.Frame(master, bg=config.COLOR_CARD, **kw)


def style_popup(top, color=None):
    """Cadre visible autour d'un popup modal pour le distinguer de la fenetre
    qui se trouve derriere (pas de decoration native car overrideredirect)."""
    top.configure(highlightthickness=4,
                  highlightbackground=color or config.COLOR_PRIMARY,
                  highlightcolor=color or config.COLOR_PRIMARY)


def numpad_popup(parent, title="Saisie", initial="", allow_negative=True, allow_decimal=True):
    """Clavier numerique tactile modal. Retourne la chaine saisie ou None."""
    top = tk.Toplevel(parent)
    top.title(title)
    top.configure(bg=config.COLOR_BG)
    top.transient(parent)
    top.grab_set()
    w, h = 340, 360
    x = (config.SCREEN_W - w) // 2
    y = (config.SCREEN_H - h) // 2
    top.geometry(f"{w}x{h}+{x}+{y}")
    top.overrideredirect(True)
    style_popup(top)

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
        top.destroy()

    def cancel():
        top.destroy()

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
    top = tk.Toplevel(parent)
    top.title(title)
    top.configure(bg=config.COLOR_BG)
    top.transient(parent)
    top.grab_set()
    top.resizable(False, False)
    w = min(620, config.SCREEN_W - 4)
    h = min(440, config.SCREEN_H - 10)
    x = (config.SCREEN_W - w) // 2
    y = (config.SCREEN_H - h) // 2
    top.geometry(f"{w}x{h}+{x}+{y}")
    top.overrideredirect(True)
    style_popup(top)

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
        top.destroy()

    btns = tk.Frame(top, bg=config.COLOR_BG)
    btns.pack(pady=6, fill="x", padx=8)
    tk.Button(btns, text="Annuler", font=config.FONT_MED, bg=config.COLOR_CARD,
              fg=config.COLOR_FG, bd=0, command=top.destroy
              ).pack(side="left", expand=True, fill="x", padx=4, ipady=8)
    tk.Button(btns, text="OK", font=config.FONT_MED, bg=config.COLOR_SUCCESS,
              fg="white", bd=0, command=ok
              ).pack(side="right", expand=True, fill="x", padx=4, ipady=8)

    parent.wait_window(top)
    return result["v"]


def confirm(parent, title, msg) -> bool:
    return messagebox.askyesno(title, msg, parent=parent)


def info(parent, title, msg):
    messagebox.showinfo(title, msg, parent=parent)


def error(parent, title, msg):
    messagebox.showerror(title, msg, parent=parent)
