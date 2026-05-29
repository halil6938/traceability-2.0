#!/usr/bin/env python3
"""Point d'entree de l'application Traceability."""
import sys
import traceback
from datetime import date, datetime

from src import config, database, purge, usb_manager
from src.ui_main import App


def daily_tasks():
    """Taches au demarrage : purge + sync USB."""
    last = database.get_meta("last_purge")
    today_s = date.today().isoformat()
    if last != today_s:
        try:
            purge.purge_old_photos()
        except Exception:
            traceback.print_exc()
        database.set_meta("last_purge", today_s)
    try:
        usb_manager.sync_pending()
    except Exception:
        traceback.print_exc()


def main():
    database.init_db()
    daily_tasks()
    app = App()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log = config.LOG_DIR / f"crash_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        with open(log, "w") as f:
            traceback.print_exc(file=f)
        traceback.print_exc()
        sys.exit(1)
