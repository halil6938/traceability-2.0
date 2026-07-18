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
        # Capteurs par defaut (INSERT OR IGNORE = ne re-insere pas si deja present)
        for mac, label in [
            ("6c:33:00:00:04:34", "Capteur BLE 1"),
            ("6c:8c:00:00:09:8c", "Capteur BLE 2"),
        ]:
            c.execute(
                "INSERT OR IGNORE INTO ble_sensors(mac, label) VALUES (?,?)",
                (mac, label),
            )

        # Migration : type de capteur ('ble' ou 'wifi' = Tuya cloud).
        # Pour un capteur wifi, la colonne mac contient le Device ID Tuya.
        cols = [r[1] for r in c.execute("PRAGMA table_info(ble_sensors)").fetchall()]
        if "kind" not in cols:
            c.execute("ALTER TABLE ble_sensors "
                      "ADD COLUMN kind TEXT NOT NULL DEFAULT 'ble'")


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

def list_devices():
    with connect() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM devices ORDER BY position, name"
        ).fetchall()]


def add_device(name: str, temp_min: float, temp_max: float):
    with connect() as c:
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


def delete_device(device_id: int):
    with connect() as c:
        c.execute("DELETE FROM devices WHERE id=?", (device_id,))


def devices_count() -> int:
    with connect() as c:
        return c.execute("SELECT COUNT(*) FROM devices").fetchone()[0]


# ---------- Relevés ----------

def get_reading(device_id: int, reading_date: date):
    with connect() as c:
        r = c.execute(
            "SELECT * FROM readings WHERE device_id=? AND reading_date=?",
            (device_id, reading_date.isoformat()),
        ).fetchone()
        return dict(r) if r else None


def save_reading(device_id: int, reading_date: date, temperature: float):
    """Crée ou écrase le relevé du jour pour cet appareil."""
    now = datetime.now().isoformat()
    with connect() as c:
        existing = c.execute(
            "SELECT id FROM readings WHERE device_id=? AND reading_date=?",
            (device_id, reading_date.isoformat()),
        ).fetchone()
        if existing:
            c.execute(
                "UPDATE readings SET temperature=?, updated_at=? WHERE id=?",
                (temperature, now, existing["id"]),
            )
        else:
            c.execute(
                "INSERT INTO readings(device_id, reading_date, temperature, created_at, updated_at) "
                "VALUES (?,?,?,?,?)",
                (device_id, reading_date.isoformat(), temperature, now, now),
            )


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

def list_suppliers():
    with connect() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM suppliers ORDER BY position, name"
        ).fetchall()]


def add_supplier(name: str):
    with connect() as c:
        pos = c.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM suppliers").fetchone()[0]
        c.execute(
            "INSERT INTO suppliers(name, position, created_at) VALUES (?,?,?)",
            (name.strip(), pos, datetime.now().isoformat()),
        )


def update_supplier(supplier_id: int, name: str):
    with connect() as c:
        c.execute("UPDATE suppliers SET name=? WHERE id=?", (name.strip(), supplier_id))


def delete_supplier(supplier_id: int):
    with connect() as c:
        c.execute("DELETE FROM suppliers WHERE id=?", (supplier_id,))


# ---------- Receptions ----------

def save_reception(supplier_id: int, temperature: float):
    """Enregistre un releve de reception (plusieurs possibles par jour)."""
    with connect() as c:
        c.execute(
            "INSERT INTO receptions(supplier_id, temperature, created_at) VALUES (?,?,?)",
            (supplier_id, temperature, datetime.now().isoformat()),
        )


def delete_reception(reception_id: int):
    """Supprime un releve de reception."""
    with connect() as c:
        c.execute("DELETE FROM receptions WHERE id = ?", (reception_id,))


def receptions_on(day: date):
    """Receptions d'une journee, plus recentes en premier."""
    with connect() as c:
        rows = c.execute(
            """SELECT r.*, s.name AS supplier_name
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
            """SELECT r.*, s.name AS supplier_name
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


# ---------- Meta ----------

def get_meta(key: str, default=None):
    with connect() as c:
        r = c.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default


def set_meta(key: str, value: str):
    with connect() as c:
        c.execute(
            "INSERT INTO meta(key, value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
