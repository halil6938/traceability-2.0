"""Ecran Nettoyage : fiche de suivi du nettoyage et de la desinfection.

L'operateur s'identifie (choix de son prenom), puis coche, dans la colonne du
jour, les elements qu'il a nettoyes : la case affiche ses initiales, comme sur
la fiche papier. Les jours precedents sont affiches a cote, en lecture seule.
Une case ne peut etre decochee que le jour meme, et par celui qui l'a cochee.
"""
import tkinter as tk
import tkinter.font as tkfont
from datetime import date, timedelta

from . import config, database
from .ui_common import (Button, ZoneDefilante, text_popup, confirm, error, info,
                        open_modal, close_modal, schedule_auto_return as auto_return)

JOURS_SEMAINE = ("lu", "ma", "me", "je", "ve", "sa", "di")
LARGEUR_NOM = 150          # colonne des elements (px)
LARGEUR_AUJOURDHUI = 96    # colonne du jour, la seule cochable
LARGEUR_PASSE_MIN = 40     # en dessous, on affiche moins de jours passes
HAUTEUR_LIGNE = 46
MAX_OPERATEURS_SANS_DEFILEMENT = 12


def colonnes(largeur_dispo, voulus):
    """(nombre de jours passes affichables, largeur d'une colonne passee)."""
    reste = largeur_dispo - LARGEUR_NOM - LARGEUR_AUJOURDHUI
    n = voulus
    while n > 0 and reste // n < LARGEUR_PASSE_MIN:
        n -= 1
    return n, (reste // n if n else 0)


def _police_nom(nom):
    """Plus petit si un mot du nom ne tient pas dans la colonne : sinon il
    serait coupe en plein mot (« Portes/Poign-ées »)."""
    mesure = tkfont.Font(font=config.FONT_MED)
    if all(mesure.measure(mot) <= LARGEUR_NOM - 12 for mot in nom.split()):
        return config.FONT_MED
    return config.FONT_SMALL


class NettoyageScreen(tk.Frame):
    def __init__(self, master, on_done):
        super().__init__(master, bg=config.COLOR_BG)
        self.on_done = on_done
        self.operateur = None
        self._cases = {}           # element_id -> bouton de la colonne du jour
        auto_return(self, config.NETTOYAGE_INACTIVITY_S, self._back)
        self.pack(fill="both", expand=True)

        header = tk.Frame(self, bg=config.COLOR_BG)
        header.pack(fill="x", padx=12, pady=8)
        Button(header, text="← Retour", font=config.FONT_MED,
               bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
               command=self._back).pack(side="left")
        tk.Label(header, text="Nettoyage", bg=config.COLOR_BG,
                 fg=config.COLOR_FG, font=config.FONT_TITLE).pack(side="left", padx=16)
        Button(header, text="⚙ Gérer", font=config.FONT_MED,
               bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
               command=self._gerer).pack(side="right")

        self.corps = tk.Frame(self, bg=config.COLOR_BG)
        self.corps.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self._afficher_choix()

    def _vider(self):
        for w in self.corps.winfo_children():
            w.destroy()
        self._cases = {}

    # --- 1. qui etes-vous ? ---

    def _afficher_choix(self):
        self.operateur = None
        self._vider()
        operateurs = database.list_operateurs()
        tk.Label(self.corps, text="Qui êtes-vous ?", bg=config.COLOR_BG,
                 fg=config.COLOR_MUTED, font=config.FONT_MED
                 ).pack(anchor="w", padx=4, pady=(0, 6))
        if not operateurs:
            tk.Label(self.corps, text="(aucun opérateur)\nAjoutez-les avec « ⚙ Gérer ».",
                     bg=config.COLOR_BG, fg=config.COLOR_MUTED, font=config.FONT_MED,
                     justify="center").pack(pady=40)
            return
        cols = 3
        if len(operateurs) > MAX_OPERATEURS_SANS_DEFILEMENT:
            zone = ZoneDefilante(self.corps, config.COLOR_BG)
            zone.pack(fill="both", expand=True)
            grille = zone.interieur
        else:
            zone, grille = None, tk.Frame(self.corps, bg=config.COLOR_BG)
            grille.pack(fill="both", expand=True)
        for col in range(cols):
            grille.columnconfigure(col, weight=1, uniform="op")
        for i, op in enumerate(operateurs):
            if zone is None:
                grille.rowconfigure(i // cols, weight=1)
            Button(grille, text=op["nom"], font=config.FONT_BIG,
                   bg=config.COLOR_NETTOYAGE, fg="white", bd=0, wraplength=220,
                   pady=14 if zone is not None else None,
                   command=lambda o=op: self._choisir(o)
                   ).grid(row=i // cols, column=i % cols, sticky="nsew", padx=5, pady=5)
        if zone is not None:
            zone.actualiser()

    def _choisir(self, operateur):
        self.operateur = operateur
        self._afficher_tableau()

    # --- 2. le tableau ---

    def _afficher_tableau(self):
        self._vider()
        op = self.operateur
        barre = tk.Frame(self.corps, bg=config.COLOR_BG)
        barre.pack(fill="x", pady=(0, 6))
        tk.Label(barre, text=f"👤 {op['nom']} ({op['initiales']})", bg=config.COLOR_BG,
                 fg=config.COLOR_FG, font=config.FONT_MED).pack(side="left", padx=4)
        Button(barre, text="Changer d'opérateur", font=config.FONT_SMALL,
               bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
               command=self._afficher_choix).pack(side="right")
        tk.Label(barre, text="Touchez la case du jour", bg=config.COLOR_BG,
                 fg=config.COLOR_MUTED, font=config.FONT_SMALL).pack(side="right", padx=10)

        elements = database.list_elements()
        if not elements:
            tk.Label(self.corps, text="(aucun élément à nettoyer)\n"
                     "Ajoutez-les avec « ⚙ Gérer ».", bg=config.COLOR_BG,
                     fg=config.COLOR_MUTED, font=config.FONT_MED,
                     justify="center").pack(pady=40)
            return

        aujourd_hui = date.today()
        dispo = config.SCREEN_W - 20 - config.SCROLLBAR_W - 4
        n_passes, larg_passe = colonnes(dispo, config.NETTOYAGE_JOURS_PASSES)
        jours = [aujourd_hui - timedelta(days=k) for k in range(n_passes, 0, -1)]
        faits = database.nettoyages_periode(jours[0] if jours else aujourd_hui,
                                            aujourd_hui)
        largeurs = [LARGEUR_NOM] + [larg_passe] * n_passes + [LARGEUR_AUJOURDHUI]

        # en-tete (hors de la zone qui defile : il reste visible)
        entete = tk.Frame(self.corps, bg=config.COLOR_BG)
        entete.pack(fill="x", padx=(0, config.SCROLLBAR_W))
        for col, w in enumerate(largeurs):
            entete.columnconfigure(col, minsize=w)
        tk.Label(entete, text="Élément", bg=config.COLOR_BG, fg=config.COLOR_MUTED,
                 font=config.FONT_SMALL, anchor="w").grid(row=0, column=0, sticky="w",
                                                          padx=6)
        for i, jour in enumerate(jours, start=1):
            tk.Label(entete, text=f"{JOURS_SEMAINE[jour.weekday()]}\n{jour.day:02d}",
                     bg=config.COLOR_BG, fg=config.COLOR_MUTED,
                     font=config.FONT_SMALL).grid(row=0, column=i, sticky="nsew")
        tk.Label(entete, text=f"Aujourd'hui\n{aujourd_hui.strftime('%d/%m')}",
                 bg=config.COLOR_NETTOYAGE, fg="white", font=config.FONT_SMALL
                 ).grid(row=0, column=n_passes + 1, sticky="nsew", padx=2)

        zone = ZoneDefilante(self.corps, config.COLOR_BG)
        zone.pack(fill="both", expand=True, pady=(2, 0))
        for e in elements:
            ligne = tk.Frame(zone.interieur, bg=config.COLOR_CARD, height=HAUTEUR_LIGNE)
            ligne.pack(fill="x", pady=2)
            ligne.grid_propagate(False)
            ligne.rowconfigure(0, weight=1)
            for col, w in enumerate(largeurs):
                ligne.columnconfigure(col, minsize=w)
            tk.Label(ligne, text=e["nom"], bg=config.COLOR_CARD, fg=config.COLOR_FG,
                     font=_police_nom(e["nom"]), anchor="w", wraplength=LARGEUR_NOM - 10,
                     justify="left").grid(row=0, column=0, sticky="w", padx=6)
            for i, jour in enumerate(jours, start=1):
                fait = faits.get((e["id"], jour.isoformat()))
                tk.Label(ligne, text=fait["initiales"] if fait else "·",
                         bg=config.COLOR_CARD,
                         fg=config.COLOR_SUCCESS if fait else config.COLOR_MUTED,
                         font=config.FONT_SMALL).grid(row=0, column=i, sticky="nsew")
            case = Button(ligne, text="", font=config.FONT_BIG, bg=config.COLOR_BG,
                          fg="white", bd=0,
                          command=lambda el=e: self._toucher(el))
            case.grid(row=0, column=n_passes + 1, sticky="nsew", padx=4, pady=3)
            self._cases[e["id"]] = case
            self._dessiner_case(e["id"], faits.get((e["id"], aujourd_hui.isoformat())))
        zone.actualiser()

    def _dessiner_case(self, element_id, fait):
        case = self._cases.get(element_id)
        if case is None:
            return
        if fait:
            case.config(text=fait["initiales"], bg=config.COLOR_SUCCESS)
        else:
            case.config(text="", bg=config.COLOR_BG)

    def _toucher(self, element):
        """Coche la case du jour, ou la decoche si c'est cet operateur qui
        l'avait cochee (erreur de case)."""
        op = self.operateur
        if op is None:
            return
        aujourd_hui = date.today()
        cle = (element["id"], aujourd_hui.isoformat())
        fait = database.nettoyages_periode(aujourd_hui, aujourd_hui).get(cle)
        if fait is None:
            database.cocher_nettoyage(element["id"], aujourd_hui, op["id"])
        elif fait["operateur_id"] == op["id"]:
            database.decocher_nettoyage(element["id"], aujourd_hui, op["id"])
        else:
            info(self, "Déjà fait",
                 f"« {element['nom']} » a déjà été nettoyé aujourd'hui\n"
                 f"par {fait['nom']} ({fait['initiales']}).")
            return
        self._dessiner_case(element["id"],
                            database.nettoyages_periode(aujourd_hui, aujourd_hui).get(cle))

    # --- gestion des listes ---

    def _gerer(self):
        top = open_modal(self, 560, 430, config.COLOR_NETTOYAGE)
        etat = {"onglet": "operateurs"}

        hdr = tk.Frame(top, bg=config.COLOR_BG)
        hdr.pack(fill="x", padx=10, pady=8)
        onglets = {}
        for cle, texte in (("operateurs", "👤 Opérateurs"), ("elements", "✨ Éléments")):
            onglets[cle] = Button(hdr, text=texte, font=config.FONT_MED,
                                  bg=config.COLOR_CARD, fg="white", bd=0, padx=10, pady=4,
                                  command=lambda c=cle: changer(c))
            onglets[cle].pack(side="left", padx=(0, 6))
        Button(hdr, text="✕", bg=config.COLOR_DANGER, fg="white", font=config.FONT_MED,
               bd=0, padx=12, command=lambda: close_modal(top)).pack(side="right")

        bas = tk.Frame(top, bg=config.COLOR_BG)
        bas.pack(side="bottom", fill="x", padx=10, pady=8)
        liste = ZoneDefilante(top, config.COLOR_BG)
        liste.pack(fill="both", expand=True, padx=10)

        def changer(onglet):
            etat["onglet"] = onglet
            for cle, b in onglets.items():
                b.config(bg=config.COLOR_NETTOYAGE if cle == onglet else config.COLOR_CARD)
            afficher()

        def afficher():
            liste.vider()
            if etat["onglet"] == "operateurs":
                lignes = database.list_operateurs()
                vide = "(aucun opérateur)"
            else:
                lignes = database.list_elements()
                vide = "(aucun élément)"
            if not lignes:
                tk.Label(liste.interieur, text=vide, bg=config.COLOR_BG,
                         fg=config.COLOR_MUTED, font=config.FONT_MED).pack(pady=20)
            for x in lignes:
                ligne = tk.Frame(liste.interieur, bg=config.COLOR_CARD)
                ligne.pack(fill="x", pady=3)
                Button(ligne, text="Modifier", font=config.FONT_SMALL,
                       bg=config.COLOR_PRIMARY, fg="white", bd=0, padx=8,
                       command=lambda v=x: modifier(v)).pack(side="right", padx=4, pady=4)
                Button(ligne, text="🗑", font=config.FONT_MED, bg=config.COLOR_DANGER,
                       fg="white", bd=0, width=3,
                       command=lambda v=x: retirer(v)).pack(side="right", padx=4, pady=4)
                if etat["onglet"] == "elements":
                    for sens, fleche in ((1, "▼"), (-1, "▲")):
                        Button(ligne, text=fleche, font=config.FONT_SMALL,
                               bg=config.COLOR_BG, fg="white", bd=0, width=2,
                               command=lambda v=x, s=sens: monter(v, s)
                               ).pack(side="right", padx=2, pady=4)
                texte = (f"{x['nom']}  ({x['initiales']})" if etat["onglet"] == "operateurs"
                         else x["nom"])
                tk.Label(ligne, text=texte, bg=config.COLOR_CARD, fg=config.COLOR_FG,
                         font=config.FONT_MED, anchor="w"
                         ).pack(side="left", padx=12, pady=8, expand=True, fill="x")
            liste.actualiser()

        def demander_operateur(nom_initial="", initiales=""):
            nom = text_popup(top, "Prénom (et nom) de l'opérateur", initial=nom_initial)
            if not nom:
                return None
            ini = text_popup(top, "Initiales (affichées dans les cases)",
                             initial=initiales or database.initiales_par_defaut(nom))
            if ini is None:
                return None
            return nom, (ini or database.initiales_par_defaut(nom))[:4]

        def ajouter():
            try:
                if etat["onglet"] == "operateurs":
                    rep = demander_operateur()
                    if rep:
                        database.add_operateur(*rep)
                else:
                    nom = text_popup(top, "Élément à nettoyer (ex. Sol labo)")
                    if nom:
                        database.add_element(nom)
            except Exception:
                error(top, "Erreur", "Ce nom existe déjà.")
            afficher()

        def modifier(x):
            try:
                if etat["onglet"] == "operateurs":
                    rep = demander_operateur(x["nom"], x["initiales"])
                    if rep:
                        database.update_operateur(x["id"], *rep)
                else:
                    nom = text_popup(top, "Élément à nettoyer", initial=x["nom"])
                    if nom:
                        database.update_element(x["id"], nom)
            except Exception:
                error(top, "Erreur", "Ce nom est déjà utilisé "
                      "(éventuellement par un élément ou un opérateur retiré).")
            afficher()

        def retirer(x):
            quoi = "l'opérateur" if etat["onglet"] == "operateurs" else "l'élément"
            if confirm(top, "Retirer", f"Retirer {quoi} « {x['nom']} » de la liste ?\n"
                       "Les fiches déjà remplies restent dans l'historique."):
                if etat["onglet"] == "operateurs":
                    database.archive_operateur(x["id"])
                else:
                    database.archive_element(x["id"])
                afficher()

        def monter(x, sens):
            database.deplacer_element(x["id"], sens)
            afficher()

        Button(bas, text="+ Ajouter", font=config.FONT_MED, bg=config.COLOR_PRIMARY,
               fg="white", bd=0, padx=12, pady=8, command=ajouter
               ).pack(fill="x", padx=3)
        changer("operateurs")

        self.wait_window(top)
        if not self.winfo_exists():
            return
        # l'operateur a pu etre renomme ou retire entre-temps
        op = self.operateur
        if op is not None:
            a_jour = next((o for o in database.list_operateurs() if o["id"] == op["id"]), None)
            if a_jour is None:
                self._afficher_choix()
                return
            self.operateur = a_jour
            self._afficher_tableau()
        else:
            self._afficher_choix()

    def _back(self):
        self.destroy()
        self.on_done()
