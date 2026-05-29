"""Detection de la cle USB et synchronisation des photos en attente."""
import shutil
from datetime import datetime
from pathlib import Path
from . import config, database


def find_usb_mount() -> Path | None:
    candidates = []
    for base in [Path("/media"), Path("/run/media")]:
        if not base.exists():
            continue
        try:
            for lvl1 in base.iterdir():
                if not lvl1.is_dir():
                    continue
                candidates.append(lvl1)
                try:
                    for lvl2 in lvl1.iterdir():
                        if lvl2.is_dir():
                            candidates.append(lvl2)
                except PermissionError:
                    pass
        except PermissionError:
            pass

    for candidate in candidates:
        try:
            test = candidate / ".traceability_test"
            test.touch()
            test.unlink()
            return candidate
        except (OSError, PermissionError):
            continue
    return None


def usb_base_dir() -> Path | None:
    mount = find_usb_mount()
    if mount is None:
        return None
    base = mount / config.USB_SUBDIR
    (base / "photos").mkdir(parents=True, exist_ok=True)
    (base / "exports").mkdir(parents=True, exist_ok=True)
    return base


def photos_dir_for(dt: datetime) -> Path | None:
    base = usb_base_dir()
    if base is None:
        return None
    month_dir = base / "photos" / dt.strftime("%Y-%m")
    month_dir.mkdir(parents=True, exist_ok=True)
    return month_dir


def _unique_name(dest_dir: Path, date_str: str) -> str:
    """Retourne photo_YYYY-MM-DD.jpg (ou _2, _3...) sans conflit dans dest_dir."""
    name = f"photo_{date_str}.jpg"
    n = 2
    while (dest_dir / name).exists():
        name = f"photo_{date_str}_{n}.jpg"
        n += 1
    return name


def save_photo(image_bytes_or_path, taken_at: datetime) -> tuple[Path, bool]:
    date_str = taken_at.strftime("%Y-%m-%d")
    usb_month = photos_dir_for(taken_at)

    if usb_month is not None:
        filename = _unique_name(usb_month, date_str)
        dest = usb_month / filename
        _write(dest, image_bytes_or_path)
        return dest, True

    # Pas d'USB : on stocke en pending
    filename = _unique_name(config.PENDING_DIR, date_str)
    dest = config.PENDING_DIR / filename
    _write(dest, image_bytes_or_path)
    database.add_pending_photo(str(dest), taken_at)
    return dest, False


def _write(dest: Path, src):
    if isinstance(src, (str, Path)):
        shutil.copy2(src, dest)
    else:
        with open(dest, "wb") as f:
            f.write(src)


def sync_pending() -> int:
    """Copie les photos en attente vers l'USB. Retourne le nombre synced."""
    base = usb_base_dir()
    if base is None:
        return 0
    synced = 0
    for p in database.list_pending_photos():
        src = Path(p["local_path"])
        if not src.exists():
            database.remove_pending_photo(p["id"])
            continue
        try:
            taken_at = datetime.fromisoformat(p["taken_at"])
        except ValueError:
            taken_at = datetime.now()
        month_dir = base / "photos" / taken_at.strftime("%Y-%m")
        month_dir.mkdir(parents=True, exist_ok=True)
        date_str = taken_at.strftime("%Y-%m-%d")
        filename = _unique_name(month_dir, date_str)
        dest = month_dir / filename
        try:
            shutil.copy2(src, dest)
            src.unlink(missing_ok=True)
            database.remove_pending_photo(p["id"])
            synced += 1
        except OSError:
            break
    return synced


def list_photos_for_month(year: int, month: int) -> list[Path]:
    """Retourne les photos d'un mois donne (USB + pending), triees par nom."""
    month_str = f"{year:04d}-{month:02d}"
    photos = []

    base = usb_base_dir()
    if base is not None:
        month_dir = base / "photos" / month_str
        if month_dir.exists():
            photos.extend(sorted(month_dir.glob("*.jpg")))

    # Photos en attente pour ce mois
    for p in sorted(config.PENDING_DIR.glob(f"photo_{month_str}*.jpg")):
        photos.append(p)

    return photos


def list_all_photos() -> list[Path]:
    """Retourne toutes les photos (USB + pending) triees par date descendante."""
    photos = []
    base = usb_base_dir()
    if base is not None:
        photos.extend((base / "photos").rglob("*.jpg"))
    photos.extend(config.PENDING_DIR.glob("*.jpg"))
    photos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return photos
