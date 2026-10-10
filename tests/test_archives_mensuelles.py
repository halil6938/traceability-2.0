"""Archives mensuelles : le 1er du mois, les tableaux du mois ecoule
(temperatures, receptions, nettoyage) sont enregistres en PDF sur la cle USB,
un dossier par element, un fichier par mois ; mois manques rattrapes, cle absente = reessai."""
from datetime import date, datetime

from _harness import setup, cleanup  # noqa: E402
sandbox = setup("archives_")

from src import archives, config, database, usb_manager  # noqa: E402

config.REMOTE_CONTROL_BASE = ""
config.REPO_URL = ""
database.init_db()

# donnees de septembre 2026
database.add_device("Frigo viande", 0, 4)
frigo = database.list_devices()[0]
database.save_reading(frigo["id"], date(2026, 9, 3), 3.2)
database.save_reading(frigo["id"], date(2026, 9, 4), 6.5)          # hors seuil
database.add_supplier("Bigard")
bigard = database.list_suppliers()[0]
database.save_reception(bigard["id"], 2.5, datetime(2026, 9, 10, 7, 30))
database.add_operateur("Hamza Uysal", "")
database.add_element("Machine")
database.cocher_nettoyage(database.list_elements()[0]["id"], date(2026, 9, 15),
                          database.list_operateurs()[0]["id"])

le_1er = date(2026, 10, 1)
cle = sandbox / "cle" / "traceability"

# 1. cle absente : rien n'est fait, on reessaiera
usb_manager.usb_base_dir = lambda: None
assert archives.mois_a_archiver(le_1er) == [(2026, 9)]
assert archives.archiver_en_attente(le_1er) == []
assert archives.mois_a_archiver(le_1er) == [(2026, 9)], "mois perdu sans cle"
print("1. cle absente : archive remise a plus tard : OK")

# 2. cle presente : dossier du mois avec les 3 tableaux
usb_manager.usb_base_dir = lambda: cle
(cle / "exports").mkdir(parents=True)
faits = archives.archiver_en_attente(le_1er)
attendus = [cle / "temperatures" / "temperatures_2026-09.pdf",
            cle / "receptions" / "receptions_2026-09.pdf",
            cle / "nettoyage" / "nettoyage_2026-09.pdf"]
assert faits == attendus, faits
for f in attendus:
    assert f.exists() and f.read_bytes()[:4] == b"%PDF", f
assert archives.mois_a_archiver(le_1er) == [], "archive refaite"
assert archives.mois_a_archiver(date(2026, 10, 25)) == []
try:
    from pypdf import PdfReader
except ImportError:                     # lecture du PDF facultative
    PdfReader = None
if PdfReader is not None:
    def texte(f):
        return "".join(p.extract_text() for p in PdfReader(str(f)).pages)
    assert "Frigo viande" in texte(attendus[0])
    assert "Bigard" not in texte(attendus[0]), "receptions en double"
    assert "Bigard" in texte(attendus[1])
    assert "Machine" in texte(attendus[2])
print("2. le 1er : un dossier par element, fichier du mois dedans : OK")

# 3. Pi eteint ou cle absente plusieurs mois : les mois manques sont rattrapes
assert archives.mois_a_archiver(date(2027, 1, 3)) == [(2026, 10), (2026, 11), (2026, 12)]
faits = archives.archiver_en_attente(date(2027, 1, 3))
assert sorted(f.name for f in (cle / "nettoyage").iterdir()) == [
    "nettoyage_2026-09.pdf", "nettoyage_2026-10.pdf", "nettoyage_2026-11.pdf",
    "nettoyage_2026-12.pdf"]
assert len(faits) == 9, faits
assert database.get_meta("archive_mois") == "2026-12"
print("3. mois manques rattrapes (changement d'annee compris) : OK")

# 4. premiere mise en service : seulement le mois ecoule, pas tout l'historique
database.set_meta("archive_mois", "")
assert archives.mois_a_archiver(date(2027, 3, 1)) == [(2027, 2)]
print("4. premiere fois : seulement le mois ecoule : OK")

# 5. l'export manuel (Historique) est inchange : releves + receptions, dans exports/
from src import pdf_export  # noqa: E402
chemin = pdf_export.export_month_pdf(2026, 9)
assert chemin == cle / "exports" / "releves_2026-09.pdf" and chemin.exists()
if PdfReader is not None:
    assert "Bigard" in "".join(p.extract_text() for p in PdfReader(str(chemin)).pages)
print("5. export manuel de l'historique inchange : OK")

# 6. dans l'appli : la tache de nuit fait l'archive en tache de fond
import time  # noqa: E402
from src import ui_main  # noqa: E402


class Nuit(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime.combine(date.today(), datetime.min.time()).replace(hour=3)


ui_main.datetime = Nuit
usb_manager.find_usb_mount = lambda: cle.parent
database.set_meta("archive_mois", "")
database.set_meta("sauvegarde_date", date.today().isoformat())   # deja sauvegarde
attendu = archives.mois_a_archiver()
assert len(attendu) == 1
config.SCREEN_OFF_S = 0
database.set_meta("setup_done", "1")
app = ui_main.App()
app.withdraw()
app._sauvegarde_tick()
fin = time.time() + 30
while time.time() < fin and archives.mois_a_archiver():
    app.update()
    time.sleep(0.05)
a, m = attendu[0]
assert (cle / "nettoyage" / f"nettoyage_{a}-{m:02d}.pdf").exists(), \
    "la tache de nuit n'a pas fait l'archive"
app.destroy()
print("6. appli : archive faite par la tache de nuit (cle branchee, apres 2 h) : OK")

cleanup(sandbox)
print("\nTOUS LES TESTS OK")
