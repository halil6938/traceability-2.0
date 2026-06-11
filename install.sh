#!/bin/bash
# Installation de Traceability sur Raspberry Pi OS (32 bits).
# A executer avec : bash install.sh  (depuis le dossier traceability/)
set -e

USER_NAME="${SUDO_USER:-$USER}"
USER_HOME=$(eval echo "~$USER_NAME")
APP_DIR="$USER_HOME/traceability-app"

echo ">>> Installation des dependances systeme..."
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-tk python3-picamera2 \
                        python3-pil python3-pil.imagetk \
                        libopenjp2-7 libopenblas0 fonts-dejavu

echo ">>> Copie de l'application vers $APP_DIR..."
mkdir -p "$APP_DIR"
cp -r ./* "$APP_DIR/"
chown -R "$USER_NAME":"$USER_NAME" "$APP_DIR"

echo ">>> Installation des dependances Python..."
pip3 install --break-system-packages -r "$APP_DIR/requirements.txt" || \
    pip3 install -r "$APP_DIR/requirements.txt"

echo ">>> Installation du service systemd..."
sudo cp "$APP_DIR/traceability.service" /etc/systemd/system/traceability.service
sudo sed -i "s|__USER__|$USER_NAME|g; s|__APPDIR__|$APP_DIR|g" \
    /etc/systemd/system/traceability.service

sudo systemctl daemon-reload
sudo systemctl enable traceability.service

echo ""
echo "✅ Installation terminee."
echo "   Lancement manuel : sudo systemctl start traceability"
echo "   Au prochain demarrage, l'appli se lancera automatiquement."
echo "   Logs : journalctl -u traceability -f"
