"""Genere la fiche de procedure PDF : installation chez un nouveau client.

    python3 tools/make_procedure_pdf.py [chemin_de_sortie]

Regenerer la fiche apres toute evolution de la procedure d'installation.
Aucun emoji dans le PDF : les polices integrees de ReportLab ne les
contiennent pas (ils apparaitraient en carres noirs).
"""
import sys
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

BG = colors.HexColor("#1e293b")
PRIMARY = colors.HexColor("#0ea5e9")
WARNING = colors.HexColor("#f59e0b")
DANGER = colors.HexColor("#ef4444")
SUCCESS = colors.HexColor("#22c55e")
MUTED = colors.HexColor("#64748b")
LIGHT = colors.HexColor("#f1f5f9")

styles = getSampleStyleSheet()
S_TITLE = ParagraphStyle("t", parent=styles["Title"], fontSize=19, leading=23,
                         textColor=BG, spaceAfter=2)
S_SUB = ParagraphStyle("s", parent=styles["Normal"], fontSize=9.5, leading=13,
                       textColor=MUTED, alignment=TA_CENTER, spaceAfter=10)
S_PHASE = ParagraphStyle("p", parent=styles["Normal"], fontSize=11.5,
                         leading=14, textColor=colors.white,
                         fontName="Helvetica-Bold")
S_BODY = ParagraphStyle("b", parent=styles["Normal"], fontSize=9.5, leading=13.5)
S_STEP = ParagraphStyle("st", parent=S_BODY, fontSize=9.5, leading=13)
S_NOTE = ParagraphStyle("n", parent=S_BODY, fontSize=9, leading=12,
                        textColor=colors.HexColor("#7c2d12"))
S_CODE = ParagraphStyle("c", parent=styles["Normal"], fontName="Courier",
                        fontSize=8.5, leading=11.5,
                        textColor=colors.HexColor("#0f172a"))


def phase(num, title):
    """Bandeau de phase (num entier, ou libelle libre comme MEMO)."""
    tag = f"PHASE {num}" if isinstance(num, int) else str(num)
    t = Table([[Paragraph(f"{tag} &nbsp;&nbsp;|&nbsp;&nbsp; {title}",
                          S_PHASE)]], colWidths=[170 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _checkbox():
    """Carre a cocher de taille fixe (pas de glyphe unicode : les polices
    integrees n'en ont pas). Table imbriquee pour qu'il ne s'etire pas quand
    le texte de la ligne tient sur plusieurs lignes."""
    b = Table([[""]], colWidths=[4 * mm], rowHeights=[4 * mm])
    b.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, MUTED)]))
    return b


def steps(items):
    """Liste a cocher."""
    rows = [[_checkbox(), Paragraph(txt, S_STEP)] for txt in items]
    t = Table(rows, colWidths=[9 * mm, 161 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, -1), 3),
        ("TOPPADDING", (0, 0), (0, -1), 4),
        ("TOPPADDING", (1, 0), (1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def code(*lines):
    rows = [[Paragraph(ln.replace("<", "&lt;"), S_CODE)] for ln in lines]
    t = Table(rows, colWidths=[161 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e2e8f0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, PRIMARY),
    ]))
    return Table([["", t]], colWidths=[9 * mm, 161 * mm],
                 style=[("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5)])


def callout(text, color=WARNING, label="ATTENTION"):
    t = Table([[Paragraph(f"<b>{label}</b> &nbsp; {text}", S_NOTE)]],
              colWidths=[170 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef3c7")
         if color is WARNING else colors.HexColor("#fee2e2")),
        ("LINEBEFORE", (0, 0), (0, -1), 3, color),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def build(path):
    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=15 * mm, bottomMargin=13 * mm,
                            title="Traceability 2.0 - Installation client",
                            author="Traceability 2.0")
    st = []

    st.append(Paragraph("Installation chez un nouveau client", S_TITLE))
    st.append(Paragraph(
        f"Traceability 2.0 &nbsp;|&nbsp; fiche de procedure &nbsp;|&nbsp; "
        f"mise a jour du {date.today().strftime('%d/%m/%Y')}", S_SUB))

    # ---- Phase 0
    st.append(phase(0, "Fabriquer l'image modele (une seule fois)"))
    st.append(Spacer(1, 4))
    st.append(steps([
        "Sur le Pi de reference, tout verifier une derniere fois "
        "(scan, releves, reception, camera).",
        "Effacer les donnees du client et les identifiants de la machine :"]))
    st.append(code("bash ~/traceability-app/tools/prepare_master.sh",
                   "sudo poweroff"))
    st.append(steps([
        "Sortir la carte SD, la lire sur le PC avec Raspberry Pi Imager "
        "(bouton <b>Lire</b>) pour obtenir un fichier .img.",
        "Conserver ce .img : c'est le modele, reutilisable pour tous les clients."]))
    st.append(Spacer(1, 5))
    st.append(callout("Eteindre le Pi apres le script, ne pas le redemarrer : "
                      "il n'a plus de WiFi ni de configuration."))
    st.append(Spacer(1, 9))

    # ---- Phase 1
    st.append(phase(1, "Preparer la carte SD du client (~10 min)"))
    st.append(Spacer(1, 4))
    st.append(steps([
        "Raspberry Pi Imager : <b>Choisir l'OS</b> puis <i>Utiliser une image "
        "personnalisee</i>, selectionner le .img.",
        "Choisir la carte SD, cliquer <b>Suivant</b> puis "
        "<b>Modifier les reglages</b>.",
        "<b>Nom d'hote</b> = nom du client, en minuscules avec tirets "
        "(exemple : boucherie-durand). C'est l'identifiant du Pi pour le "
        "verrouillage et les mises a jour a distance.",
        "<b>WiFi</b> du magasin (reseau 2,4 GHz uniquement).",
        "Ecrire l'image sur la carte."]))
    st.append(Spacer(1, 5))
    st.append(callout(
        "Laisser DECOCHEE la case &laquo; nom d'utilisateur et mot de passe &raquo;. "
        "Le compte stpriest doit rester intact : un autre nom empeche "
        "l'application de demarrer.", DANGER, "A NE PAS FAIRE"))
    st.append(Spacer(1, 9))

    # ---- Phase 2
    st.append(phase(2, "Montage sur place"))
    st.append(Spacer(1, 4))
    st.append(steps([
        "Carte SD dans le Pi, ecran, camera (nappe CSI), <b>cle USB</b> "
        "(photos et exports PDF), alimentation.",
        "Fixer la camera a sa position definitive avant de calibrer (phase 3d).",
        "L'application demarre seule. Verifier le nom de la machine :"]))
    st.append(code("hostname"))
    st.append(steps([
        "Si le nom est incorrect, le corriger puis redemarrer :"]))
    st.append(code("bash ~/traceability-app/tools/set_client.sh boucherie-durand",
                   "sudo reboot"))
    st.append(Spacer(1, 9))

    # ---- Phase 3
    st.append(phase(3, "Configuration dans l'application (~15 min)"))
    st.append(Spacer(1, 4))
    st.append(Paragraph("<b>a) Les appareils</b> (frigos et congelateurs)", S_BODY))
    st.append(steps([
        "L'assistant du premier demarrage demande d'en creer un : nom, "
        "temperature MIN, temperature MAX. Ces seuils declenchent les alertes.",
        "Pour les suivants : <b>Parametres &gt; + Ajouter</b>."]))
    st.append(Spacer(1, 3))
    st.append(Paragraph("<b>b) Les capteurs de temperature</b> "
                        "(Parametres &gt; Capteurs temp.)", S_BODY))
    st.append(steps([
        "<b>Ajouter BLE</b> : capteurs allumes et proches. Ils s'affichent avec "
        "leur temperature actuelle, ce qui permet d'identifier lequel est dans "
        "quel frigo. Le bouton <b>Adresse</b> permet une saisie manuelle.",
        "<b>Ajouter WiFi</b> (capteurs Tuya) : le capteur doit d'abord etre "
        "appaire dans l'application Smart Life du fournisseur, sinon il "
        "n'apparait pas dans la liste.",
        "<b>Assigner</b> chaque capteur a son appareil, puis <b>Tester</b> "
        "pour verifier que les temperatures remontent."]))
    st.append(Spacer(1, 3))
    st.append(Paragraph("<b>c) La reception</b> "
                        "(Reception &gt; Fournisseurs)", S_BODY))
    st.append(steps([
        "Saisir les fournisseurs du client.",
        "<b>Pistolet BLE</b> puis <b>Detecter</b> : appuyer sur la gachette "
        "pendant la recherche. La MAC peut aussi etre saisie a la main."]))
    st.append(Spacer(1, 3))
    st.append(Paragraph("<b>d) La camera</b> "
                        "(Parametres &gt; Test camera)", S_BODY))
    st.append(steps([
        "Placer un ticket imprime bien eclaire a sa distance definitive, puis "
        "<b>Calibrer</b> (environ 10 s, sans rien bouger).",
        "Verifier ensuite un scan reel, et la lisibilite de la photo."]))
    st.append(Spacer(1, 5))
    st.append(callout("La mise au point depend du montage : la calibration est "
                      "a refaire sur CHAQUE installation."))
    st.append(Spacer(1, 9))

    # ---- Phase 4
    st.append(phase(4, "Enregistrer le client pour le controle a distance"))
    st.append(Spacer(1, 4))
    st.append(steps([
        "Sur GitHub, dossier <b>devices/</b>, creer le fichier "
        "<b>&lt;nom-du-client&gt;.json</b> en copiant _modele.json :"]))
    st.append(code('{ "locked": false, "message": "", "config": {}, '
                   '"update": "auto" }'))
    st.append(steps([
        "Pour bloquer ce client : passer <b>locked</b> a true et ecrire un "
        "message. Effet en 20 secondes environ ; le blocage resiste au "
        "redemarrage et a une coupure internet.",
        "<b>update</b> : auto (mises a jour la nuit, recommande), now "
        "(immediat) ou off (fige la version)."]))
    st.append(Spacer(1, 9))

    # ---- Memo
    st.append(KeepTogether([
        phase("MEMO", "Depannage et verifications"),
        Spacer(1, 4),
        Paragraph("Version installee et nom du Pi : en bas de l'ecran "
                  "<b>Parametres</b>.", S_BODY),
        Spacer(1, 3),
        code("sudo systemctl restart traceability     # redemarrer l'application",
             "journalctl -u traceability -n 40        # journal de l'application",
             "cat ~/traceability/logs/update.log      # mises a jour",
             "cat ~/traceability/logs/ble_thermo.log  # pistolet infrarouge",
             "python3 ~/traceability-app/tools/focus_probe.py   # test du focus"),
        Paragraph("Le code se met a jour tout seul depuis GitHub : rien a "
                  "transferer sur les Pi apres une correction.", S_BODY),
        Spacer(1, 3),
        Paragraph("L'ecran se met en veille apres 10 minutes sans contact. Le "
                  "premier contact rallume seulement : il ne declenche aucun "
                  "bouton. Delai reglable a distance (SCREEN_OFF_S).", S_BODY),
    ]))

    doc.build(st)
    return path


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1
               else "docs/procedure-nouveau-client.pdf")
    out.parent.mkdir(parents=True, exist_ok=True)
    build(out)
    print(f"PDF genere : {out}")
