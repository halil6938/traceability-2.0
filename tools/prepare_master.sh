#!/bin/bash
# Prepare CE Pi pour le clonage de sa carte SD (deploiement multi-clients).
#
# Efface les donnees du client, les identifiants uniques a la machine et les
# reseaux WiFi memorises, pour que l'image servant de modele soit vierge.
# Les reglages systeme (rotation ecran, overlay camera, service au demarrage)
# sont conserves : c'est tout l'interet du clonage.
#
#   bash tools/prepare_master.sh              # efface aussi les WiFi memorises
#   bash tools/prepare_master.sh --garder-wifi
#
# A la fin : ETEINDRE (sudo poweroff), ne pas redemarrer, puis copier la carte.
set -e

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
KEEP_WIFI=0
[ "$1" = "--garder-wifi" ] && KEEP_WIFI=1

echo "=================================================================="
echo " PREPARATION DE L'IMAGE MODELE"
echo "=================================================================="
echo "Ce script va effacer DEFINITIVEMENT sur ce Pi :"
echo "  - tous les relevés, réceptions, appareils, fournisseurs, capteurs"
echo "  - la calibration caméra et le MAC du pistolet"
echo "  - les photos en attente et les logs"
echo "  - les clés SSH, l'identifiant machine"
[ "$KEEP_WIFI" = "0" ] && echo "  - les réseaux WiFi mémorisés (ce Pi perdra sa connexion !)"
echo
echo "Les clés cloud Tuya et tous les réglages système sont conservés."
echo
read -r -p "Continuer ? (tapez OUI en majuscules) " answer
[ "$answer" = "OUI" ] || { echo "Annulé."; exit 1; }

echo
echo ">>> Arret de l'application..."
sudo systemctl stop traceability || true

echo ">>> Effacement des donnees du client..."
python3 "$APP_DIR/tools/reset_client_data.py"

echo ">>> Effacement de l'historique du terminal..."
cat /dev/null > "$HOME/.bash_history" 2>/dev/null || true
history -c 2>/dev/null || true

echo ">>> Reinitialisation de l'identifiant machine..."
sudo truncate -s 0 /etc/machine-id
sudo rm -f /var/lib/dbus/machine-id
sudo rm -f /etc/dhcpcd.duid   # evite que deux Pi demandent la meme IP

echo ">>> Preparation de la regeneration des cles SSH..."
if systemctl list-unit-files 2>/dev/null | grep -q '^regenerate_ssh_host_keys'; then
    sudo systemctl enable regenerate_ssh_host_keys.service >/dev/null 2>&1 || true
else
    sudo tee /etc/systemd/system/regen-ssh-keys.service >/dev/null <<'UNIT'
[Unit]
Description=Regenere les cles hote SSH si elles sont absentes
ConditionPathExists=!/etc/ssh/ssh_host_rsa_key
Before=ssh.service
[Install]
WantedBy=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/ssh-keygen -A
UNIT
    sudo systemctl enable regen-ssh-keys.service >/dev/null 2>&1 || true
fi
sudo rm -f /etc/ssh/ssh_host_*

if [ "$KEEP_WIFI" = "0" ]; then
    echo ">>> Effacement des reseaux WiFi memorises..."
    sudo rm -f /etc/NetworkManager/system-connections/*.nmconnection 2>/dev/null || true
    sudo rm -f /etc/wpa_supplicant/wpa_supplicant.conf 2>/dev/null || true
fi

echo
echo "=================================================================="
echo " IMAGE MODELE PRETE"
echo "=================================================================="
echo "1. ETEINDRE MAINTENANT (ne pas redemarrer) :   sudo poweroff"
echo "2. Sortir la carte SD et en faire une image sur le PC"
echo "   (Raspberry Pi Imager > Lire, ou Win32DiskImager > Read)."
echo "3. Flasher chaque nouveau Pi avec cette image, en definissant dans"
echo "   les reglages avances de l'Imager : un NOM D'HOTE UNIQUE (= nom du"
echo "   client, ex. boucherie-durand) et le WiFi du magasin."
echo "4. Sur place : assistant de configuration, capteurs, puis"
echo "   Parametres > Test camera > Calibrer."
echo
