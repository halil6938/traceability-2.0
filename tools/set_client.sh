#!/bin/bash
# Donne son identite a un Pi fraichement flashe : le nom d'hote sert
# d'identifiant pour le controle a distance (devices/<nom>.json sur GitHub).
#
# A n'utiliser que si le nom n'a pas deja ete defini par Raspberry Pi Imager.
#
#   bash tools/set_client.sh boucherie-durand
set -e

NAME="$1"
if [ -z "$NAME" ]; then
    echo "Usage : bash tools/set_client.sh <nom-du-client>"
    echo "Exemple : bash tools/set_client.sh boucherie-durand"
    echo "Nom actuel : $(hostname)"
    exit 1
fi

if ! echo "$NAME" | grep -qE '^[a-z0-9][a-z0-9-]{1,30}$'; then
    echo "Nom invalide : minuscules, chiffres et tirets uniquement,"
    echo "sans espace ni accent (ex. boucherie-durand)."
    exit 1
fi

OLD="$(hostname)"
sudo hostnamectl set-hostname "$NAME"
sudo sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t$NAME/" /etc/hosts
grep -q "^127.0.1.1" /etc/hosts || echo -e "127.0.1.1\t$NAME" | sudo tee -a /etc/hosts >/dev/null

echo "Nom d'hote : $OLD  ->  $NAME"
echo
echo "Pour pouvoir verrouiller ce Pi a distance, creer sur GitHub le fichier"
echo "  devices/$NAME.json"
echo "en copiant devices/_modele.json (sans fichier, l'appareil est autorise)."
echo
echo "Redemarrer pour appliquer :  sudo reboot"
