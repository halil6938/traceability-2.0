"""Purge automatique des photos > 6 mois (USB + pending)."""
from datetime import datetime, timedelta
from . import config, usb_manager


def purge_old_photos() -> int:
    cutoff = datetime.now() - timedelta(days=config.PHOTO_RETENTION_DAYS)
    removed = 0
    for photo in usb_manager.list_all_photos():
        try:
            mtime = datetime.fromtimestamp(photo.stat().st_mtime)
            if mtime < cutoff:
                photo.unlink()
                removed += 1
        except OSError:
            continue
    # Nettoyage dossiers mois vides sur USB
    base = usb_manager.usb_base_dir()
    if base is not None:
        for month_dir in (base / "photos").iterdir():
            if month_dir.is_dir() and not any(month_dir.iterdir()):
                try:
                    month_dir.rmdir()
                except OSError:
                    pass
    return removed
