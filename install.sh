#!/bin/bash
# Installation de Traceability sur un Raspberry Pi OS neuf.
#
#     git clone https://github.com/halil6938/traceability-2.0.git
#     cd traceability-2.0
#     bash install.sh
#
# Le script installe l'application ET les reglages systeme dont elle depend
# (surcouche camera). Il peut etre relance sans risque : chaque etape verifie
# ce qui est deja en place.
set -e

USER_NAME="${SUDO_USER:-$USER}"
USER_HOME=$(eval echo "~$USER_NAME")
APP_DIR="$USER_HOME/traceability-app"
MARQUE="# --- Traceability 2.0 : ne pas modifier cette section ---"

# ---------------------------------------------------------------------------
echo ">>> 1/5 Dependances systeme..."
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-tk python3-picamera2 \
                        python3-pil python3-pil.imagetk \
                        libopenjp2-7 libopenblas0 fonts-dejavu \
                        fonts-symbola git

# ---------------------------------------------------------------------------
echo ""
echo ">>> 2/5 Reglages camera dans config.txt..."
# Sans ces deux lignes, le moteur d'autofocus de l'OV5647-AF n'est pas pilote :
# l'image reste floue quoi que fasse l'application.
CONFIG_TXT="/boot/firmware/config.txt"
[ -f "$CONFIG_TXT" ] || CONFIG_TXT="/boot/config.txt"

if [ ! -f "$CONFIG_TXT" ]; then
    echo "    ATTENTION : config.txt introuvable, reglages camera non appliques."
elif grep -qF "$MARQUE" "$CONFIG_TXT"; then
    echo "    deja en place, rien a faire."
else
    sudo cp "$CONFIG_TXT" "$CONFIG_TXT.avant-traceability"
    echo "    sauvegarde : $CONFIG_TXT.avant-traceability"
    # Neutraliser une detection automatique qui prendrait le pas sur la surcouche
    sudo sed -i 's/^\s*camera_auto_detect=/#&/' "$CONFIG_TXT"
    # Ajouter notre section a la fin, dans [all] pour qu'elle s'applique toujours
    sudo tee -a "$CONFIG_TXT" >/dev/null <<EOF

$MARQUE
[all]
camera_auto_detect=0
dtoverlay=ov5647,vcm
EOF
    echo "    camera_auto_detect=0 et dtoverlay=ov5647,vcm ajoutes."
    echo "    (actif au prochain redemarrage)"
fi

# ---------------------------------------------------------------------------
echo ""
echo ">>> 3/5 Copie de l'application vers $APP_DIR..."
mkdir -p "$APP_DIR"
cp -r ./* "$APP_DIR/"
chown -R "$USER_NAME":"$USER_NAME" "$APP_DIR"

# ---------------------------------------------------------------------------
echo ""
echo ">>> 4/5 Modules Python (peut prendre 10 a 20 minutes)..."
pip3 install --break-system-packages -r "$APP_DIR/requirements.txt" || \
    pip3 install -r "$APP_DIR/requirements.txt"

# ---------------------------------------------------------------------------
echo ""
echo ">>> 5/5 Service de demarrage automatique..."
sudo cp "$APP_DIR/traceability.service" /etc/systemd/system/traceability.service
sudo sed -i "s|__USER__|$USER_NAME|g; s|__APPDIR__|$APP_DIR|g" \
    /etc/systemd/system/traceability.service
sudo systemctl daemon-reload
sudo systemctl enable traceability.service

# ---------------------------------------------------------------------------
cat <<EOF

==========================================================
 Installation terminee.
==========================================================

 A FAIRE MAINTENANT
   1. Redemarrer (indispensable pour la camera) :
          sudo reboot
   2. Orientation de l'ecran (montage habituel : 180 degres) :
          Menu > Preferences > Screen Configuration
          clic droit sur l'ecran > Orientation > Inverted, puis Appliquer
   3. Verifier la camera : Parametres > Test camera
   4. Calibrer le focus une fois la camera a sa place definitive
   5. Signe de vie Telegram (une fois par machine) :
          python3 $APP_DIR/tools/set_telegram.py <jeton> <chat_id>
   6. Cles Tuya si capteur WiFi : Parametres > Capteurs temp. > Cles

 Nom de la machine : $(hostname)
   il sert d'identifiant pour le verrouillage et les mises a jour ;
   pour le changer : bash $APP_DIR/tools/set_client.sh <nom-du-client>

 Journal en cas de souci : journalctl -u traceability -f
EOF
