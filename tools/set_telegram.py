"""Configure le signe de vie Telegram sur ce Pi (a faire sur le Pi modele,
avant de fabriquer l'image : les reglages seront herites par tous les clients).

Creer le bot, une seule fois :
  1. Dans Telegram, ecrire a @BotFather  ->  /newbot  ->  il donne un JETON.
  2. Ecrire n'importe quel message a votre nouveau bot (sinon il ne peut pas
     vous repondre).
  3. Recuperer l'identifiant de conversation :
         python3 tools/set_telegram.py --chat-id <jeton>

Utilisation :
  python3 tools/set_telegram.py <jeton> <chat_id>   enregistre la configuration
  python3 tools/set_telegram.py --test              envoie un message d'essai
  python3 tools/set_telegram.py --etat              affiche la configuration
  python3 tools/set_telegram.py --effacer           desactive le signe de vie
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import database, heartbeat, remote_lock  # noqa: E402


def trouver_chat_id(token):
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"Impossible d'interroger Telegram : {e}")
        return 1
    if not data.get("ok"):
        print("Jeton refuse par Telegram.")
        return 1
    chats = {}
    for upd in data.get("result", []):
        msg = upd.get("message") or upd.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if chat.get("id") is not None:
            chats[chat["id"]] = chat.get("title") or chat.get("first_name") or ""
    if not chats:
        print("Aucune conversation trouvee.\n"
              "Ecrivez d'abord un message a votre bot dans Telegram, "
              "puis relancez cette commande.")
        return 1
    print("Conversations trouvees :")
    for cid, nom in chats.items():
        print(f"  chat_id = {cid}   ({nom})")
    print("\nEnregistrer avec :\n"
          f"  python3 tools/set_telegram.py <jeton> {list(chats)[0]}")
    return 0


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1

    if args[0] == "--chat-id":
        if len(args) < 2:
            print("Usage : python3 tools/set_telegram.py --chat-id <jeton>")
            return 1
        return trouver_chat_id(args[1])

    if args[0] == "--etat":
        creds = heartbeat.get_creds()
        if creds is None:
            print("Signe de vie : non configure.")
            return 0
        token, chat = creds
        print("Signe de vie   : configure")
        print(f"  jeton        : {token[:8]}...{token[-4:]}")
        print(f"  chat_id      : {chat}")
        print(f"  appareil     : {remote_lock.device_id()}")
        print(f"  version notee: {database.get_meta('heartbeat_version', '') or '-'}")
        print(f"  dernier envoi: {database.get_meta('heartbeat_date', '') or '-'}")
        return 0

    if args[0] == "--effacer":
        database.set_meta("telegram_token", "")
        database.set_meta("telegram_chat_id", "")
        print("Signe de vie desactive.")
        return 0

    if args[0] == "--test":
        if heartbeat.get_creds() is None:
            print("Signe de vie non configure.")
            return 1
        device = remote_lock.device_id()
        ok = heartbeat.send(f"{device} — message d'essai")
        print("Message envoye." if ok else
              "Echec : verifiez le jeton, le chat_id et la connexion.")
        return 0 if ok else 1

    if len(args) < 2:
        print(__doc__)
        return 1
    heartbeat.set_creds(args[0], args[1])
    print("Configuration enregistree.")
    ok = heartbeat.send(f"{remote_lock.device_id()} — signe de vie active")
    print("Message de confirmation envoye." if ok else
          "ATTENTION : l'envoi a echoue, verifiez le jeton et le chat_id.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
