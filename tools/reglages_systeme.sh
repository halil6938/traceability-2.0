#!/bin/bash
# Releve les reglages systeme du Pi (hors depot) : a lancer sur une machine
# qui fonctionne, pour pouvoir les reproduire a l'identique ailleurs.
#
#     bash ~/traceability-app/tools/reglages_systeme.sh
#
# Ne modifie rien, se contente d'afficher.

CONFIG_TXT="/boot/firmware/config.txt"
[ -f "$CONFIG_TXT" ] || CONFIG_TXT="/boot/config.txt"
CMDLINE="/boot/firmware/cmdline.txt"
[ -f "$CMDLINE" ] || CMDLINE="/boot/cmdline.txt"

echo "===== MACHINE ====="
echo "hostname : $(hostname)"
echo "user     : $USER"
echo "modele   : $(tr -d '\0' < /proc/device-tree/model 2>/dev/null)"
echo "OS       : $(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME")"
echo "session  : ${XDG_SESSION_TYPE:-?} / bureau : ${XDG_CURRENT_DESKTOP:-?}"

echo
echo "===== $CONFIG_TXT (lignes actives) ====="
grep -vE '^\s*(#|$)' "$CONFIG_TXT" 2>/dev/null

echo
echo "===== $CMDLINE ====="
cat "$CMDLINE" 2>/dev/null

echo
echo "===== ROTATION DE L'ECRAN ====="
for f in ~/.config/wayfire.ini ~/.config/labwc/autostart \
         ~/.config/autostart/*.desktop /etc/xdg/labwc/autostart; do
    [ -f "$f" ] && { echo "--- $f"; grep -iE 'transform|rotate|randr|output' "$f" 2>/dev/null; }
done
command -v wlr-randr >/dev/null && { echo "--- wlr-randr"; wlr-randr 2>/dev/null | head -20; }
command -v xrandr >/dev/null && { echo "--- xrandr"; DISPLAY=:0 xrandr 2>/dev/null | grep -E ' connected|primary'; }

echo
echo "===== SERVICE ====="
systemctl is-enabled traceability 2>/dev/null
systemctl is-active traceability 2>/dev/null

echo
echo "===== FIN — copier tout ce qui precede ====="
