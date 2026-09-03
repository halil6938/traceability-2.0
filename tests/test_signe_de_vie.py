"""Verifie la logique du signe de vie sans rien envoyer sur le reseau :
message a l'installation, a chaque mise a jour, puis une fois par jour."""
from datetime import date, timedelta

from _harness import setup, cleanup  # noqa: E402

sandbox = setup("signe_")
from src import config, database, heartbeat, updater  # noqa: E402

database.init_db()
config.REPO_DIR = sandbox / "pas-de-depot"     # pas de git : version « inconnue »
config.DEVICE_ID = "boucherie-durand"
config.HEARTBEAT_HOUR = 0                      # message quotidien des minuit

envoyes = []
heartbeat.send = lambda text: (envoyes.append(text), True)[1]   # pas de reseau

# --- 1. non configure : rien ne part ---
heartbeat.tick()
print("1. sans configuration        ->", len(envoyes), "message(s) (attendu 0)")
assert not envoyes

# --- 2. configure : message d'installation ---
heartbeat.set_creds("123456:FAUX-JETON", "-100999")
version = {"v": "aaaaaaa"}
updater.current_version = lambda: version["v"]
heartbeat.tick()
print("2. premiere fois             ->", envoyes[-1])
assert len(envoyes) == 1 and "installe" in envoyes[-1]
assert "boucherie-durand" in envoyes[-1] and "aaaaaaa" in envoyes[-1]

# --- 3. rien de neuf le meme jour ---
heartbeat.tick()
heartbeat.tick()
print("3. rappels le meme jour      ->", len(envoyes), "message(s) au total (attendu 1)")
assert len(envoyes) == 1

# --- 4. jour suivant : message « en ligne » ---
database.set_meta("heartbeat_date", (date.today() - timedelta(days=1)).isoformat())
heartbeat.tick()
print("4. lendemain                 ->", envoyes[-1])
assert len(envoyes) == 2 and "en ligne" in envoyes[-1]
heartbeat.tick()
assert len(envoyes) == 2, "le message quotidien est parti deux fois"

# --- 5. mise a jour : message immediat, sans attendre le lendemain ---
version["v"] = "bbbbbbb"
heartbeat.tick()
print("5. apres une mise a jour     ->", envoyes[-1])
assert len(envoyes) == 3 and "mis a jour" in envoyes[-1] and "bbbbbbb" in envoyes[-1]

# --- 6. echec d'envoi : on reessaiera (rien n'est marque comme envoye) ---
heartbeat.send = lambda text: False
version["v"] = "ccccccc"
heartbeat.tick()
print("6. envoi en echec            -> version notee :",
      database.get_meta("heartbeat_version", ""), "(doit rester bbbbbbb)")
assert database.get_meta("heartbeat_version") == "bbbbbbb"

# --- 7. heure non atteinte : pas de message quotidien ---
heartbeat.send = lambda text: (envoyes.append(text), True)[1]
version["v"] = "bbbbbbb"
config.HEARTBEAT_HOUR = 23
database.set_meta("heartbeat_date", (date.today() - timedelta(days=1)).isoformat())
avant = len(envoyes)
heartbeat.tick()
from datetime import datetime  # noqa: E402
attendu = avant + (1 if datetime.now().hour >= 23 else 0)
print("7. avant l'heure du jour     ->", len(envoyes), f"message(s) (attendu {attendu})")
assert len(envoyes) == attendu

cleanup(sandbox)
print("\nTOUS LES TESTS OK")
