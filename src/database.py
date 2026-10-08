"""Gestion de la base SQLite : appareils + relevés de température + photos en attente."""
import sqlite3
from datetime import date, datetime
from contextlib import contextmanager
from . import config


def init_db():
    with connect() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                temp_min REAL NOT NULL,
                temp_max REAL NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                reading_date TEXT NOT NULL,
                temperature REAL NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(device_id) REFERENCES devices(id) ON DELETE CASCADE,
                UNIQUE(device_id, reading_date)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS pending_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                local_path TEXT NOT NULL,
                taken_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                position INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS receptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER NOT NULL,
                temperature REAL NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS ble_sensors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL,
                device_id INTEGER,
                FOREIGN KEY(device_id) REFERENCES devices(id) ON DELETE SET NULL
            )
        """)
        # Aucun capteur par defaut : les adresses BLE sont propres a chaque
        # client, elles s'ajoutent depuis Parametres > Capteurs temp.

        # Migration : type de capteur ('ble' ou 'wifi' = Tuya cloud).
        # Pour un capteur wifi, la colonne mac contient le Device ID Tuya.
        cols = [r[1] for r in c.execute("PRAGMA table_info(ble_sensors)").fetchall()]
        if "kind" not in cols:
            c.execute("ALTER TABLE ble_sensors "
                      "ADD COLUMN kind TEXT NOT NULL DEFAULT 'ble'")

        # Provenance d'un releve : 'manuel' (saisi) ou 'capteur'. Un capteur ne
        # doit jamais ecraser une valeur saisie a la main. Les releves deja en
        # base sont consideres comme venant d'un capteur.
        _ajouter_colonne(c, "readings", "source", "TEXT NOT NULL DEFAULT 'capteur'")
        # Archivage : un appareil ou un fournisseur retire disparait des listes
        # mais son historique reste (registre sanitaire, controles).
        _ajouter_colonne(c, "devices", "archived", "INTEGER NOT NULL DEFAULT 0")
        _ajouter_colonne(c, "suppliers", "archived", "INTEGER NOT NULL DEFAULT 0")
        # Temperature maximale acceptee a la reception (vide = pas de controle)
        _ajouter_colonne(c, "suppliers", "temp_max", "REAL")

        # Fiche de suivi du nettoyage : qui (operateurs), quoi (elements a
        # nettoyer), et une case par element et par jour, comme sur papier.
        c.execute("""
            CREATE TABLE IF NOT EXISTS nettoyage_operateurs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL UNIQUE,
                initiales TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                archived INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS nettoyage_elements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL UNIQUE,
                position INTEGER NOT NULL DEFAULT 0,
                archived INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS nettoyages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                element_id INTEGER NOT NULL,
                jour TEXT NOT NULL,
                operateur_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(element_id) REFERENCES nettoyage_elements(id),
                FOREIGN KEY(operateur_id) REFERENCES nettoyage_operateurs(id),
                UNIQUE(element_id, jour)
            )
        """)


def _ajouter_colonne(c, table, colonne, definition):
    cols = [r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]
    if colonne not in cols:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {definition}")


@contextmanager
def connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------- Appareils ----------

def list_devices(include_archived=False):
    """Appareils en service (et aussi les archives si demande)."""
    sql = "SELECT * FROM devices"
    if not include_archived:
        sql += " WHERE archived = 0"
    with connect() as c:
        return [dict(r) for r in c.execute(sql + " ORDER BY position, name").fetchall()]


def devices_for_period(start: date, end: date):
    """Appareils a montrer pour une periode passee : ceux en service, plus les
    archives qui ont des releves sur la periode (l'historique reste complet)."""
    with connect() as c:
        return [dict(r) for r in c.execute(
            """SELECT * FROM devices d
               WHERE d.archived = 0 OR EXISTS (
                   SELECT 1 FROM readings r WHERE r.device_id = d.id
                   AND r.reading_date BETWEEN ? AND ?)
               ORDER BY d.position, d.name""",
            (start.isoformat(), end.isoformat())).fetchall()]


def add_device(name: str, temp_min: float, temp_max: float):
    """Ajoute un appareil. S'il en existe un archive du meme nom, il est remis
    en service (avec les nouveaux seuils) au lieu d'etre duplique."""
    with connect() as c:
        ancien = c.execute("SELECT id FROM devices WHERE name=? AND archived=1",
                           (name.strip(),)).fetchone()
        if ancien:
            c.execute("UPDATE devices SET archived=0, temp_min=?, temp_max=? WHERE id=?",
                      (temp_min, temp_max, ancien["id"]))
            return
        pos = c.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM devices").fetchone()[0]
        c.execute(
            "INSERT INTO devices(name, temp_min, temp_max, position, created_at) VALUES (?,?,?,?,?)",
            (name.strip(), temp_min, temp_max, pos, datetime.now().isoformat()),
        )


def update_device(device_id: int, name: str, temp_min: float, temp_max: float):
    with connect() as c:
        c.execute(
            "UPDATE devices SET name=?, temp_min=?, temp_max=? WHERE id=?",
            (name.strip(), temp_min, temp_max, device_id),
        )


def archive_device(device_id: int):
    """Retire un appareil du service sans effacer ses releves. Ses capteurs
    sont liberes (ils pourront etre assignes a un autre appareil)."""
    with connect() as c:
        c.execute("UPDATE devices SET archived=1 WHERE id=?", (device_id,))
        c.execute("UPDATE ble_sensors SET device_id=NULL WHERE device_id=?", (device_id,))


def delete_device(device_id: int):
    """Suppression definitive, releves compris (assistant de premiere mise en
    service uniquement : il n'y a pas encore d'historique)."""
    with connect() as c:
        c.execute("DELETE FROM devices WHERE id=?", (device_id,))


def devices_count() -> int:
    with connect() as c:
        return c.execute("SELECT COUNT(*) FROM devices WHERE archived=0").fetchone()[0]


# ---------- Relevés ----------

def get_reading(device_id: int, reading_date: date):
    with connect() as c:
        r = c.execute(
            "SELECT * FROM readings WHERE device_id=? AND reading_date=?",
            (device_id, reading_date.isoformat()),
        ).fetchone()
        return dict(r) if r else None


def save_reading(device_id: int, reading_date: date, temperature: float,
                 source: str = "manuel"):
    """Crée ou écrase le relevé du jour pour cet appareil.
    source : 'manuel' (saisie a l'ecran) ou 'capteur'."""
    now = datetime.now().isoformat()
    with connect() as c:
        existing = c.execute(
            "SELECT id FROM readings WHERE device_id=? AND reading_date=?",
            (device_id, reading_date.isoformat()),
        ).fetchone()
        if existing:
            c.execute(
                "UPDATE readings SET temperature=?, updated_at=?, source=? WHERE id=?",
                (temperature, now, source, existing["id"]),
            )
        else:
            c.execute(
                "INSERT INTO readings(device_id, reading_date, temperature, created_at, "
                "updated_at, source) VALUES (?,?,?,?,?,?)",
                (device_id, reading_date.isoformat(), temperature, now, now, source),
            )


def save_sensor_reading(device_id: int, reading_date: date, temperature: float) -> bool:
    """Enregistre la valeur d'un capteur, SAUF si une valeur a ete saisie a la
    main ce jour-la : la correction de l'operateur prime. Retourne True si la
    valeur du capteur a ete enregistree."""
    existant = get_reading(device_id, reading_date)
    if existant and existant.get("source") == "manuel":
        return False
    save_reading(device_id, reading_date, temperature, source="capteur")
    return True


def readings_in_range(start: date, end: date):
    """Retourne tous les relevés entre start et end inclus avec le nom de l'appareil."""
    with connect() as c:
        rows = c.execute(
            """SELECT r.*, d.name AS device_name, d.temp_min, d.temp_max
               FROM readings r JOIN devices d ON d.id = r.device_id
               WHERE r.reading_date BETWEEN ? AND ?
               ORDER BY r.reading_date DESC, d.position""",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [dict(r) for r in rows]


def last_reading_date_per_device():
    """Pour chaque appareil, retourne la derniere date de relevé (ou None)."""
    with connect() as c:
        rows = c.execute(
            """SELECT d.id, d.name, MAX(r.reading_date) AS last_date
               FROM devices d LEFT JOIN readings r ON r.device_id = d.id
               WHERE d.archived = 0
               GROUP BY d.id ORDER BY d.position"""
        ).fetchall()
        return [dict(r) for r in rows]


# ---------- Photos en attente (sync USB) ----------

def add_pending_photo(local_path: str, taken_at: datetime):
    with connect() as c:
        c.execute(
            "INSERT INTO pending_photos(local_path, taken_at) VALUES (?,?)",
            (local_path, taken_at.isoformat()),
        )


def list_pending_photos():
    with connect() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM pending_photos ORDER BY taken_at"
        ).fetchall()]


def remove_pending_photo(photo_id: int):
    with connect() as c:
        c.execute("DELETE FROM pending_photos WHERE id=?", (photo_id,))


def remove_pending_photo_by_path(local_path: str):
    with connect() as c:
        c.execute("DELETE FROM pending_photos WHERE local_path=?", (local_path,))


# ---------- Fournisseurs ----------

def list_suppliers(include_archived=False):
    sql = "SELECT * FROM suppliers"
    if not include_archived:
        sql += " WHERE archived = 0"
    with connect() as c:
        return [dict(r) for r in c.execute(sql + " ORDER BY position, name").fetchall()]


def add_supplier(name: str):
    """Ajoute un fournisseur ; un fournisseur archive du meme nom est remis en
    service (avec son historique) au lieu d'etre duplique."""
    with connect() as c:
        ancien = c.execute("SELECT id FROM suppliers WHERE name=? AND archived=1",
                           (name.strip(),)).fetchone()
        if ancien:
            c.execute("UPDATE suppliers SET archived=0 WHERE id=?", (ancien["id"],))
            return
        pos = c.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM suppliers").fetchone()[0]
        c.execute(
            "INSERT INTO suppliers(name, position, created_at) VALUES (?,?,?)",
            (name.strip(), pos, datetime.now().isoformat()),
        )


def update_supplier(supplier_id: int, name: str):
    with connect() as c:
        c.execute("UPDATE suppliers SET name=? WHERE id=?", (name.strip(), supplier_id))


def set_supplier_temp_max(supplier_id: int, temp_max):
    """Temperature maximale acceptee a la reception ; None = pas de controle."""
    with connect() as c:
        c.execute("UPDATE suppliers SET temp_max=? WHERE id=?", (temp_max, supplier_id))


def archive_supplier(supplier_id: int):
    """Retire un fournisseur des listes ; ses receptions restent dans
    l'historique et les exports (registre sanitaire)."""
    with connect() as c:
        c.execute("UPDATE suppliers SET archived=1 WHERE id=?", (supplier_id,))


def reception_hors_seuil(reception) -> bool:
    """Vrai si la temperature relevee depasse le maximum du fournisseur."""
    tmax = reception.get("supplier_temp_max")
    return tmax is not None and reception["temperature"] > tmax


# ---------- Receptions ----------

def save_reception(supplier_id: int, temperature: float, when=None):
    """Enregistre un releve de reception (plusieurs possibles par jour).
    when : datetime, pour rattraper une reception oubliee ; maintenant sinon."""
    with connect() as c:
        c.execute(
            "INSERT INTO receptions(supplier_id, temperature, created_at) VALUES (?,?,?)",
            (supplier_id, temperature, (when or datetime.now()).isoformat()),
        )


def update_reception(reception_id: int, temperature: float):
    """Corrige la temperature d'un releve existant."""
    with connect() as c:
        c.execute("UPDATE receptions SET temperature=? WHERE id=?",
                  (temperature, reception_id))


def delete_reception(reception_id: int):
    """Supprime un releve de reception."""
    with connect() as c:
        c.execute("DELETE FROM receptions WHERE id = ?", (reception_id,))


def receptions_on(day: date):
    """Receptions d'une journee, plus recentes en premier."""
    with connect() as c:
        rows = c.execute(
            """SELECT r.*, s.name AS supplier_name, s.temp_max AS supplier_temp_max
               FROM receptions r JOIN suppliers s ON s.id = r.supplier_id
               WHERE r.created_at BETWEEN ? AND ?
               ORDER BY r.created_at DESC""",
            (day.isoformat(), day.isoformat() + "T23:59:59"),
        ).fetchall()
        return [dict(r) for r in rows]


def receptions_in_range(start: date, end: date):
    """Receptions entre start et end inclus, plus recentes en premier."""
    with connect() as c:
        rows = c.execute(
            """SELECT r.*, s.name AS supplier_name, s.temp_max AS supplier_temp_max
               FROM receptions r JOIN suppliers s ON s.id = r.supplier_id
               WHERE r.created_at BETWEEN ? AND ?
               ORDER BY r.created_at DESC""",
            (start.isoformat(), end.isoformat() + "T23:59:59"),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------- Capteurs BLE ----------

def list_ble_sensors():
    """Retourne les capteurs (BLE et WiFi) avec le nom de l'appareil associe."""
    with connect() as c:
        rows = c.execute("""
            SELECT b.id, b.mac, b.label, b.kind, b.device_id,
                   d.name AS device_name
            FROM ble_sensors b
            LEFT JOIN devices d ON d.id = b.device_id
            ORDER BY b.id
        """).fetchall()
        return [dict(r) for r in rows]


def update_ble_sensor(sensor_id: int, label: str, device_id):
    """Met a jour le label et l'appareil associe d'un capteur."""
    with connect() as c:
        c.execute(
            "UPDATE ble_sensors SET label=?, device_id=? WHERE id=?",
            (label, device_id, sensor_id),
        )


def add_sensor(mac: str, label: str, kind: str = "ble"):
    """Ajoute un capteur. Pour kind='wifi', mac = Device ID Tuya."""
    with connect() as c:
        c.execute(
            "INSERT INTO ble_sensors(mac, label, kind) VALUES (?,?,?)",
            (mac, label, kind),
        )


def delete_sensor(sensor_id: int):
    with connect() as c:
        c.execute("DELETE FROM ble_sensors WHERE id=?", (sensor_id,))


# ---------- Nettoyage ----------
# Operateurs et elements retires sont archives, jamais effaces : la fiche d'un
# mois passe doit rester complete (controles sanitaires).

def initiales_par_defaut(nom: str) -> str:
    """« Hamza Uysal » -> « HU » ; « Hamza » -> « HA »."""
    mots = [m for m in nom.replace("-", " ").split() if m]
    if not mots:
        return ""
    if len(mots) == 1:
        return mots[0][:2].upper()
    return "".join(m[0] for m in mots[:3]).upper()


def _lister(table, include_archived):
    sql = f"SELECT * FROM {table}"
    if not include_archived:
        sql += " WHERE archived = 0"
    with connect() as c:
        return [dict(r) for r in c.execute(sql + " ORDER BY position, nom").fetchall()]


def _ajouter(table, nom, colonnes=(), valeurs=()):
    """Ajoute une ligne, ou remet en service une ligne archivee du meme nom."""
    nom = nom.strip()
    with connect() as c:
        ancien = c.execute(f"SELECT id FROM {table} WHERE nom=? AND archived=1",
                           (nom,)).fetchone()
        if ancien:
            sets = "".join(f", {col}=?" for col in colonnes)
            c.execute(f"UPDATE {table} SET archived=0{sets} WHERE id=?",
                      (*valeurs, ancien["id"]))
            return
        pos = c.execute(f"SELECT COALESCE(MAX(position), 0) + 1 FROM {table}").fetchone()[0]
        cols = "".join(f", {col}" for col in colonnes)
        marques = ", ?" * len(colonnes)
        c.execute(f"INSERT INTO {table}(nom{cols}, position, created_at) "
                  f"VALUES (?{marques}, ?, ?)",
                  (nom, *valeurs, pos, datetime.now().isoformat()))


def list_operateurs(include_archived=False):
    return _lister("nettoyage_operateurs", include_archived)


def add_operateur(nom: str, initiales: str):
    _ajouter("nettoyage_operateurs", nom, ("initiales",),
             (initiales.strip().upper() or initiales_par_defaut(nom),))


def update_operateur(operateur_id: int, nom: str, initiales: str):
    with connect() as c:
        c.execute("UPDATE nettoyage_operateurs SET nom=?, initiales=? WHERE id=?",
                  (nom.strip(), initiales.strip().upper() or initiales_par_defaut(nom),
                   operateur_id))


def archive_operateur(operateur_id: int):
    with connect() as c:
        c.execute("UPDATE nettoyage_operateurs SET archived=1 WHERE id=?", (operateur_id,))


def list_elements(include_archived=False):
    return _lister("nettoyage_elements", include_archived)


def add_element(nom: str):
    _ajouter("nettoyage_elements", nom)


def update_element(element_id: int, nom: str):
    with connect() as c:
        c.execute("UPDATE nettoyage_elements SET nom=? WHERE id=?", (nom.strip(), element_id))


def archive_element(element_id: int):
    with connect() as c:
        c.execute("UPDATE nettoyage_elements SET archived=1 WHERE id=?", (element_id,))


def deplacer_element(element_id: int, sens: int):
    """Monte (sens=-1) ou descend (+1) un element dans la liste."""
    elements = list_elements()
    ids = [e["id"] for e in elements]
    i = ids.index(element_id)
    j = i + sens
    if not 0 <= j < len(ids):
        return
    ids[i], ids[j] = ids[j], ids[i]
    with connect() as c:
        for pos, eid in enumerate(ids, start=1):
            c.execute("UPDATE nettoyage_elements SET position=? WHERE id=?", (pos, eid))


def elements_pour_periode(debut: date, fin: date):
    """Elements en service, plus ceux retires qui ont ete nettoyes sur la
    periode : la fiche d'un mois passe reste complete."""
    with connect() as c:
        return [dict(r) for r in c.execute(
            """SELECT * FROM nettoyage_elements e
               WHERE e.archived = 0 OR EXISTS (
                   SELECT 1 FROM nettoyages n WHERE n.element_id = e.id
                   AND n.jour BETWEEN ? AND ?)
               ORDER BY e.position, e.nom""",
            (debut.isoformat(), fin.isoformat())).fetchall()]


def nettoyages_periode(debut: date, fin: date):
    """{(element_id, 'AAAA-MM-JJ'): {operateur_id, initiales, nom}}."""
    with connect() as c:
        rows = c.execute(
            """SELECT n.element_id, n.jour, n.operateur_id, o.initiales, o.nom
               FROM nettoyages n JOIN nettoyage_operateurs o ON o.id = n.operateur_id
               WHERE n.jour BETWEEN ? AND ?""",
            (debut.isoformat(), fin.isoformat())).fetchall()
        return {(r["element_id"], r["jour"]): dict(r) for r in rows}


def cocher_nettoyage(element_id: int, jour: date, operateur_id: int) -> bool:
    """Enregistre que l'element a ete nettoye ce jour-la. False si la case
    etait deja cochee (par n'importe qui)."""
    with connect() as c:
        r = c.execute(
            "INSERT OR IGNORE INTO nettoyages(element_id, jour, operateur_id, created_at) "
            "VALUES (?,?,?,?)",
            (element_id, jour.isoformat(), operateur_id, datetime.now().isoformat()))
        return r.rowcount == 1


def decocher_nettoyage(element_id: int, jour: date, operateur_id: int) -> bool:
    """Annule une case, seulement si c'est bien cet operateur qui l'a cochee."""
    with connect() as c:
        r = c.execute(
            "DELETE FROM nettoyages WHERE element_id=? AND jour=? AND operateur_id=?",
            (element_id, jour.isoformat(), operateur_id))
        return r.rowcount == 1


# ---------- Meta ----------

def get_meta(key: str, default=None):
    with connect() as c:
        r = c.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default


def set_meta(key: str, value: str):
    """Enregistre une valeur. Rien n'est ecrit si elle n'a pas change : ces
    valeurs sont mises a jour toutes les 20 secondes, et chaque ecriture use
    la carte SD."""
    with connect() as c:
        r = c.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        if r is not None and r["value"] == value:
            return
        c.execute(
            "INSERT INTO meta(key, value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
