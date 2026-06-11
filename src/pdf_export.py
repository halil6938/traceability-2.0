"""Export PDF des releves de temperature et receptions par mois."""
from datetime import date, datetime
from pathlib import Path
from calendar import monthrange

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from . import database, usb_manager


def export_month_pdf(year: int, month: int) -> Path | None:
    """Exporte le tableau mensuel sur la cle USB. Retourne le chemin, ou None si USB absente."""
    base = usb_manager.usb_base_dir()
    if base is None:
        return None

    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    readings = database.readings_in_range(start, end)
    devices = database.list_devices()

    # Matrice : devices en lignes, jours en colonnes
    days = [date(year, month, d) for d in range(1, monthrange(year, month)[1] + 1)]
    matrix = {d["id"]: {day.isoformat(): None for day in days} for d in devices}
    for r in readings:
        if r["device_id"] in matrix:
            matrix[r["device_id"]][r["reading_date"]] = (r["temperature"], r["temp_min"], r["temp_max"])

    out_path = base / "exports" / f"releves_{year}-{month:02d}.pdf"

    doc = SimpleDocTemplate(str(out_path), pagesize=(A4[1], A4[0]),  # paysage
                            leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"<b>Relevés de température — {month:02d}/{year}</b>", styles["Title"]),
        Spacer(1, 8),
    ]

    header = ["Appareil", "Seuils"] + [str(day.day) for day in days]
    data = [header]

    alert_cells = []
    for di, d in enumerate(devices, start=1):
        row = [d["name"], f"{d['temp_min']:g}/{d['temp_max']:g}"]
        for ci, day in enumerate(days, start=2):
            entry = matrix[d["id"]][day.isoformat()]
            if entry is None:
                row.append("")
            else:
                temp, tmin, tmax = entry
                row.append(f"{temp:g}")
                if temp < tmin or temp > tmax:
                    alert_cells.append((ci, di))
        data.append(row)

    col_widths = [80, 50] + [(A4[0] - 180) / len(days)] * len(days)
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0ea5e9")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ])
    for col, row in alert_cells:
        style.add("BACKGROUND", (col, row), (col, row), colors.HexColor("#fee2e2"))
        style.add("TEXTCOLOR", (col, row), (col, row), colors.HexColor("#b91c1c"))
        style.add("FONTNAME", (col, row), (col, row), "Helvetica-Bold")
    t.setStyle(style)
    story.append(t)
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Cellules rouges : hors seuils. Cellules vides : relevé manquant.",
        styles["Italic"]))

    # --- Section receptions ---
    receptions = database.receptions_in_range(start, end)
    if receptions:
        story.append(Spacer(1, 20))
        story.append(Paragraph(
            f"<b>Réceptions — {month:02d}/{year}</b>", styles["Heading2"]))
        story.append(Spacer(1, 6))

        rdata = [["Date", "Heure", "Fournisseur", "Température (°C)"]]
        for r in reversed(receptions):  # ordre chronologique
            dt = datetime.fromisoformat(r["created_at"])
            rdata.append([dt.strftime("%d/%m/%Y"), dt.strftime("%H:%M"),
                          r["supplier_name"], f"{r['temperature']:g}"])

        rt = Table(rdata, colWidths=[90, 60, 300, 110], repeatRows=1)
        rt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f59e0b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (3, 1), (3, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(rt)

    doc.build(story)
    return out_path
