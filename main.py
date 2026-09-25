#!/usr/bin/env python3
"""Point d'entree de l'application Traceability."""
import sys
import traceback
from datetime import datetime

from src import config, database
from src.ui_main import App


def main():
    database.init_db()
    # La purge des vieilles photos et la copie des photos en attente vers la
    # cle sont faites par l'appli elle-meme, en tache de fond (voir App).
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
