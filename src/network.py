"""Etat de la connexion internet (pour l'icone WiFi du menu)."""
import os
import socket

# GitHub d'abord : c'est lui que l'appli interroge pour les mises a jour et le
# controle a distance. Repli sur une adresse IP pour distinguer « pas
# d'internet » de « GitHub injoignable ». Simple ouverture de connexion : rien
# n'est envoye.
_CIBLES = (("raw.githubusercontent.com", 443), ("1.1.1.1", 53))


def is_online(timeout=2.0):
    if os.environ.get("TRACEABILITY_TEST"):
        return True                     # les tests n'ouvrent aucune connexion
    for hote, port in _CIBLES:
        try:
            with socket.create_connection((hote, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False
