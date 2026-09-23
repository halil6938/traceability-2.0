"""Style « arrondi » : les memes couleurs que le style classique, des cases aux
coins arrondis, et un vrai effet de bouton qui s'enfonce.

Les formes sont dessinees avec Pillow a 4x puis reduites (bords lisses, ce que
le canevas Tk ne sait pas faire seul) et mises en cache. Chaque case a un
rebord plus sombre en dessous : a l'appui, la face descend sur ce rebord et
son contenu la suit. L'action n'est validee qu'au relachement SUR la case ;
glisser le doigt ailleurs avant de relacher l'annule.
"""
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

from . import config

RAYON = 22
REBORD = 6          # epaisseur du rebord visible sous une case au repos
ENFONCEMENT = 4     # de combien la face descend quand on appuie
ZONE_MORTE = 12     # bande sur le pourtour d'une case ou un appui est ignore :
                    # un doigt qui vise le bord ne doit pas ouvrir la case voisine

_SCALE = 4
_cache = {}
_tailles = {}      # tailles de tk.Button de reference deja mesurees


def _rgb(hex_color):
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def assombrir(hex_color, facteur):
    r, g, b = (int(c * facteur) for c in _rgb(hex_color))
    return f"#{r:02x}{g:02x}{b:02x}"


def rounded_image(w, h, radius, fill):
    """Rectangle arrondi lisse (RGBA), mis en cache."""
    key = (w, h, radius, fill)
    if key not in _cache:
        s = _SCALE
        img = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle(
            [0, 0, w * s - 1, h * s - 1], radius=radius * s, fill=_rgb(fill))
        _cache[key] = ImageTk.PhotoImage(img.resize((w, h), Image.LANCZOS))
    return _cache[key]


class _Touche(tk.Canvas):
    """Case qui s'enfonce au contact et valide au relachement sur elle-meme."""

    def __init__(self, parent, w, h, fill, command, rayon=RAYON, fond=None):
        super().__init__(parent, width=w, height=h, bg=fond or config.COLOR_BG,
                         highlightthickness=0, bd=0, cursor="hand2")
        self._width, self._height, self._command = w, h, command
        self._armed = False
        face_h = h - REBORD
        rayon = min(rayon, face_h // 2)
        self._rebord = self.create_image(
            0, 0, image=rounded_image(w, h, rayon, assombrir(fill, 0.6)),
            anchor="nw")
        self._face_repos = rounded_image(w, face_h, rayon, fill)
        self._face_appuyee = rounded_image(w, face_h, rayon, assombrir(fill, 0.88))
        self._face = self.create_image(0, 0, image=self._face_repos, anchor="nw")
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _contenu(self):
        """Tout ce qui suit la face quand elle s'enfonce."""
        return [i for i in self.find_all() if i != self._rebord]

    def _dans_zone_active(self, x, y):
        return (ZONE_MORTE <= x < self._width - ZONE_MORTE
                and ZONE_MORTE <= y < self._height - ZONE_MORTE)

    def _on_press(self, event):
        if not self._dans_zone_active(event.x, event.y):
            return                      # appui sur le pourtour : ignore
        self._armed = True
        self.itemconfigure(self._face, image=self._face_appuyee)
        for item in self._contenu():
            self.move(item, 0, ENFONCEMENT)

    def _on_release(self, event):
        if not self._armed:
            return                      # appui ignore (ex. juste apres un changement d'ecran)
        self._armed = False
        self.itemconfigure(self._face, image=self._face_repos)
        for item in self._contenu():
            self.move(item, 0, -ENFONCEMENT)
        if 0 <= event.x < self._width and 0 <= event.y < self._height:
            self._command()


class Card(_Touche):
    """Grande case coloree : pictogramme, titre et sous-titre centres."""

    def __init__(self, parent, w, h, icon, title, subtitle, color, command):
        super().__init__(parent, w, h, color, command)
        cx = w // 2
        icone = self.create_text(cx, 18, text=icon, fill="white",
                                 font=("DejaVu Sans", 48), anchor="n")
        y = self.bbox(icone)[3] + 2
        titre = self.create_text(cx, y, text=title, fill="white", anchor="n",
                                 font=config.FONT_BIG, width=w - 10,
                                 justify="center")
        y = self.bbox(titre)[3] + 6
        self.create_text(cx, y, text=subtitle, fill="white", anchor="n",
                         font=config.FONT_SMALL, width=w - 10, justify="center")


class Bouton(_Touche):
    """Bouton secondaire arrondi (Historique, Parametres)."""

    def __init__(self, parent, w, h, text, command):
        super().__init__(parent, w, h, config.COLOR_CARD, command)
        self.create_text(w // 2, (h - REBORD) // 2, text=text, fill="white",
                         font=config.FONT_MED)


class RoundedButton(tk.Canvas):
    """Bouton arrondi qui s'enfonce, avec l'interface d'un tk.Button (text,
    command, font, bg, fg, padx, pady, width, height, state ; config, cget,
    invoke), pour remplacer les boutons de toute l'appli sans reecrire les
    ecrans. Sa taille naturelle suit le texte ; s'il est etire par la
    disposition (fill, expand, sticky), la forme est redessinee a la taille
    reelle."""

    _bouton = True          # reconnu par bind_drag_scroll (comme un tk.Button)
    ZONE_MORTE_BOUTON = 3   # petite marge : boutons parfois serres les uns contre les autres

    def __init__(self, master, text="", command=None, font=None, bg=None,
                 fg="white", padx=None, pady=None, width=None, height=None,
                 state="normal", wraplength=0, **autres):
        try:
            fond = master.cget("bg")
        except tk.TclError:
            fond = config.COLOR_BG
        super().__init__(master, bg=fond, highlightthickness=0, bd=0,
                         cursor="hand2")
        from tkinter import font as tkfont
        self._opts = {"text": text, "command": command, "bg": bg or config.COLOR_PRIMARY,
                      "fg": fg,
                      "padx": int(padx) if padx is not None else int(self.winfo_fpixels("3m")),
                      "pady": int(pady) if pady is not None else int(self.winfo_fpixels("1m")),
                      "width": width, "height": height, "state": state,
                      "wraplength": wraplength}
        # options qui influent sur la taille d'un tk.Button : rejouees a l'identique
        # sur un bouton de mesure (voir _appliquer_taille_naturelle)
        self._kw_taille = {k: v for k, v in (
            ("padx", padx), ("pady", pady), ("width", width), ("height", height),
            ("wraplength", wraplength or None), ("bd", autres.get("bd")),
            ("highlightthickness", autres.get("highlightthickness")),
            ("relief", autres.get("relief"))) if v is not None}
        self._font = tkfont.Font(font=font or config.FONT_MED)
        self._font_spec = font or config.FONT_MED
        self._armed = self._appuye = False
        self._taille = None
        self._appliquer_taille_naturelle()
        self.bind("<Configure>", self._on_configure)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._dessiner()

    # --- geometrie ---

    def _rebord(self, h):
        return max(3, min(REBORD, h // 9))

    def _appliquer_taille_naturelle(self):
        """Taille = celle qu'aurait un tk.Button avec les memes options, mesuree
        sur un bouton jetable : les regles internes de Tk (marges par defaut,
        largeur en caracteres...) varient avec la police et la plateforme, et
        un ecart ferait deborder les cadres a taille fixe (pave numerique)."""
        o = self._opts
        texte = str(o["text"])
        kw = {k: o[k] for k in ("padx", "pady", "width", "height", "wraplength")
              if k in self._kw_taille}
        kw.update({k: v for k, v in self._kw_taille.items() if k not in kw})
        cle = (str(self._font_spec), "" if kw.get("width") else texte,
               texte.count("\n"), tuple(sorted(kw.items())))
        if cle not in _tailles:
            ref = tk.Button(self, text=texte, font=self._font_spec, **kw)
            ref.update_idletasks()
            _tailles[cle] = (ref.winfo_reqwidth(), ref.winfo_reqheight())
            ref.destroy()
        w, h = _tailles[cle]
        tk.Canvas.configure(self, width=w, height=h)
        self._taille = (w, h)

    def _on_configure(self, event):
        if (event.width, event.height) != self._taille:
            self._taille = (event.width, event.height)
            self._dessiner()

    # --- dessin ---

    def _dessiner(self):
        w, h = self._taille
        if w < 8 or h < 8:
            return
        self.delete("all")
        o = self._opts
        rebord = self._rebord(h)
        enfonce = ENFONCEMENT if h > 20 else 2
        face_h = h - rebord
        rayon = max(4, min(14, face_h // 2))
        actif = o["state"] != "disabled"
        self.create_image(0, 0, image=rounded_image(w, h, rayon, assombrir(o["bg"], 0.6)),
                          anchor="nw")
        dy = min(enfonce, rebord) if self._appuye else 0
        couleur = assombrir(o["bg"], 0.88) if self._appuye else o["bg"]
        self._face = rounded_image(w, face_h, rayon, couleur)
        self.create_image(0, dy, image=self._face, anchor="nw")
        fg = o["fg"]
        if not actif and fg == "white":
            fg = config.COLOR_MUTED
        largeur_txt = o["wraplength"] or max(w - 2 * o["padx"], 10)
        self.create_text(w // 2, face_h // 2 + dy, text=o["text"], fill=fg,
                         font=self._font_spec, width=largeur_txt, justify="center")

    # --- toucher ---

    def _dans_zone(self, x, y):
        z = self.ZONE_MORTE_BOUTON
        w, h = self._taille
        return z <= x < w - z and z <= y < h - z

    def _on_press(self, event):
        if self._opts["state"] == "disabled" or not self._dans_zone(event.x, event.y):
            return
        self._armed = self._appuye = True
        self._dessiner()

    def _on_release(self, event):
        if not self._armed:
            return                      # appui ignore (zone morte, protection...)
        self._armed = self._appuye = False
        self._dessiner()
        w, h = self._taille
        if 0 <= event.x < w and 0 <= event.y < h:
            self.invoke()

    # --- interface tk.Button ---

    def invoke(self):
        if self._opts["state"] != "disabled" and self._opts["command"]:
            return self._opts["command"]()

    def flash(self):
        pass

    def configure(self, cnf=None, **kw):
        if cnf:
            kw = {**cnf, **kw}
        if not kw:
            return None
        retaille = False
        for cle, val in kw.items():
            if cle == "font":
                from tkinter import font as tkfont
                self._font = tkfont.Font(font=val)
                self._font_spec = val
                retaille = True
            elif cle in self._opts:
                self._opts[cle] = val
                retaille = retaille or cle in ("text", "padx", "pady", "width",
                                               "height", "wraplength")
            elif cle == "cursor":
                tk.Canvas.configure(self, cursor=val)
            # les autres options d'un tk.Button (bd, relief, activebackground,
            # highlightthickness...) n'ont pas d'objet ici : ignorees
        if retaille:
            self._appliquer_taille_naturelle()
        self._dessiner()
        return None

    config = configure

    def cget(self, cle):
        if cle == "font":
            return self._font_spec
        if cle in self._opts:
            return self._opts[cle]
        return tk.Canvas.cget(self, cle)


# --- Menu Historique : liste de lignes pleine largeur, fond quasi noir ---
HIST_FOND = "#0f1316"          # nettement plus sombre que le fond du reste de l'appli
HIST_LIGNE = "#181d21"
HIST_LIGNE_APPUYEE = "#232a30"
HIST_TEXTE_DISCRET = "#9aa5ad"
HIST_RAYON = 12
HIST_BARRE = 7                 # largeur de la barre de couleur a gauche


def ligne_image(w, h, rayon, face, accent):
    """Ligne arrondie avec une barre de couleur sur son bord gauche."""
    key = ("ligne", w, h, rayon, face, accent)
    if key not in _cache:
        s = _SCALE
        img = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, w * s - 1, h * s - 1], radius=rayon * s,
                            fill=_rgb(accent))
        d.rounded_rectangle([HIST_BARRE * s, 0, w * s - 1, h * s - 1],
                            radius=rayon * s, fill=_rgb(face),
                            corners=(False, True, True, False))
        _cache[key] = ImageTk.PhotoImage(img.resize((w, h), Image.LANCZOS))
    return _cache[key]


class Ligne(_Touche):
    """Ligne du menu Historique : numero, titre, sous-titre, fleche, et une
    barre de la couleur de la rubrique. Meme effet d'enfoncement que le reste."""

    def __init__(self, parent, w, h, numero, titre, sous_titre, accent, command):
        super().__init__(parent, w, h, HIST_LIGNE, command,
                         rayon=HIST_RAYON, fond=HIST_FOND)
        face_h = h - REBORD
        rayon = min(HIST_RAYON, face_h // 2)
        self._face_repos = ligne_image(w, face_h, rayon, HIST_LIGNE, accent)
        self._face_appuyee = ligne_image(w, face_h, rayon, HIST_LIGNE_APPUYEE, accent)
        self.itemconfigure(self._face, image=self._face_repos)

        milieu = face_h // 2
        self.create_text(HIST_BARRE + 34, milieu, text=numero, fill=HIST_TEXTE_DISCRET,
                         font=("DejaVu Sans Mono", 16), anchor="w")
        t = self.create_text(HIST_BARRE + 96, 0, text=titre, fill="white",
                             font=config.FONT_BIG, anchor="nw")
        sb = self.create_text(HIST_BARRE + 96, 0, text=sous_titre,
                              fill=HIST_TEXTE_DISCRET, font=config.FONT_MED,
                              anchor="nw", width=w - 240)
        tb, sbb = self.bbox(t), self.bbox(sb)
        hauteur = (tb[3] - tb[1]) + 4 + (sbb[3] - sbb[1])
        haut = (face_h - hauteur) // 2
        self.coords(t, HIST_BARRE + 96, haut)
        self.coords(sb, HIST_BARRE + 96, haut + (tb[3] - tb[1]) + 4)
        self.create_text(w - 40, milieu, text="→", fill=HIST_TEXTE_DISCRET,
                         font=("DejaVu Sans", 24))
