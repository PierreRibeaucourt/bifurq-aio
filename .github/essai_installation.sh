#!/bin/sh
# Installation réelle de l'outil sur macOS ou Linux, depuis le code du dépôt, par
# docs/installer.sh lu sur l'entrée standard comme avec curl ... | sh. Vérifie ensuite
# l'interface, le raccourci, la planification, une analyse planifiée, la notification
# et la mise à jour lancée depuis l'interface.
#
# Chaque vérification ratée devient une annotation ::error:: de GitHub Actions.
set -u

ECHECS=0
ok() { printf '  ok : %s\n' "$1"; }
ko() { printf '::error title=%s::%s\n' "$1" "$(printf '%s' "$2" | tr '\n' ' ' | cut -c1-900)"; ECHECS=$((ECHECS + 1)); }
etape() { printf '\n===== %s\n' "$1"; }
verifier() {                        # verifier "description" commande...
    description=$1; shift
    if sortie=$("$@" 2>&1); then ok "$description"; else ko "$description" "$sortie"; fi
}
pid_interface() { python3 -c "import json;print(json.load(open('$D/config/serveur.json'))['pid'])" 2>/dev/null; }
attendre_interface() {              # attendre_interface [pid à voir remplacé]
    i=0
    while [ $i -lt 30 ]; do
        p=$(pid_interface)
        if [ -n "$p" ] && [ "$p" != "${1:-}" ] && curl -fs http://127.0.0.1:8765/ping >/dev/null; then return 0; fi
        sleep 1; i=$((i + 1))
    done
    return 1
}

SYSTEME=$(uname)
# PYTHON_ESSAI : un Python précis (celui de python.org), trouvé en premier par installer.sh
if [ -n "${PYTHON_ESSAI:-}" ]; then PATH="$(dirname "$PYTHON_ESSAI"):$PATH"; export PATH; fi
PYTHON=$(command -v python3)
echo "Système : $SYSTEME, Python : $PYTHON ($($PYTHON --version 2>&1))"
if [ "$SYSTEME" = "Darwin" ]; then
    D="$HOME/Library/Application Support/Bifurq AIO"
else
    D="$HOME/.local/share/bifurq-aio"
    # session systemd de l'utilisateur, comme sur un poste de travail
    sudo -n loginctl enable-linger "$(id -un)"
    export XDG_RUNTIME_DIR="/run/user/$(id -u)"
    for i in 1 2 3 4 5 6 7 8 9 10; do [ -S "$XDG_RUNTIME_DIR/bus" ] && break; sleep 1; done
    export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
    # un serveur de notifications, comme dans une session graphique : dunst sur un écran virtuel
    if ! command -v dunst >/dev/null || ! command -v Xvfb >/dev/null || ! command -v notify-send >/dev/null; then
        sudo -n apt-get install -y -qq xvfb dunst libnotify-bin >/dev/null 2>&1
    fi
    Xvfb :99 >/dev/null 2>&1 &
    sleep 1
    DISPLAY=:99 dunst >/dev/null 2>&1 &
    sleep 1
fi
DEPOT=$(pwd)

etape "ZIP du dépôt, au format des archives GitHub"
TEMP=$(mktemp -d)
mkdir -p "$TEMP/zip/bifurq-aio-essai"
cp -R veille_ia scripts_windows installer.pyw lancer_veille.pyw icone.ico icone.icns icone.png requirements.txt \
    LICENSE README.md "$TEMP/zip/bifurq-aio-essai/"
(cd "$TEMP/zip" && "$PYTHON" -m zipfile -c "$TEMP/bifurq-aio.zip" bifurq-aio-essai)

if [ "$SYSTEME" = "Darwin" ]; then
    etape "HTTPS avec ce Python, sans l'outil"
    if "$PYTHON" -c "import urllib.request; urllib.request.urlopen('https://pierreribeaucourt.github.io/bifurq-aio/version.json', timeout=20)" 2>/dev/null
    then echo "::notice title=HTTPS::$PYTHON lit les certificats tout seul"
    else echo "::notice title=HTTPS::$PYTHON sans certificats : HTTPS impossible sans l'outil"; fi
fi

etape "Installation : cat installer.sh | sh"
DEBUT=$(date +%s)
sortie=$(cat docs/installer.sh | BIFURQ_ZIP="file://$TEMP/bifurq-aio.zip" sh 2>&1); code=$?
FIN=$(date +%s)
printf '%s\n' "$sortie"
[ $code -eq 0 ] && ok "installer.sh se termine sans erreur" || ko "installer.sh" "code $code : $sortie"
verifier "interface ouverte" attendre_interface
echo "::notice title=Délais::installation terminée en $((FIN - DEBUT)) s, interface prête après $(( $(date +%s) - DEBUT )) s"
verifier "environnement Python" "$D/config/venv/bin/python3" -c "import veille_ia"
case "$sortie" in *"Adresse de l'outil : http://127.0.0.1:"*) ok "adresse de l'outil affichée" ;;
    *) ko "message de fin" "$sortie | serveur.log : $(tail -5 "$D/config/serveur.log" 2>&1)" ;; esac
verifier "HTTPS depuis l'outil (version publiée)" "$D/config/venv/bin/python3" -c "
from veille_ia import mise_a_jour
etat = mise_a_jour.verifier(force=True)
assert etat.get('version'), etat"
verifier "page d'accueil" sh -c "curl -fs http://127.0.0.1:8765/ | grep -q '<title>Bifurq AIO</title>'"

etape "Raccourci"
if [ "$SYSTEME" = "Darwin" ]; then
    APP="$HOME/Applications/Bifurq AIO.app"
    verifier "Info.plist de l'application" plutil -lint "$APP/Contents/Info.plist"
    verifier "script de l'application exécutable" test -x "$APP/Contents/MacOS/bifurq-aio"
    verifier "icône de l'application" test -s "$APP/Contents/Resources/icone.icns"
    ls -la "$APP/Contents/MacOS"
    # l'application relance l'interface arrêtée
    kill "$(pid_interface)"; sleep 1
    verifier "open lance l'application" open "$APP"
    verifier "l'application rouvre l'interface" attendre_interface
    xattr -l "$APP" "$APP/Contents/MacOS/bifurq-aio"
else
    LANCEUR="$HOME/.local/share/applications/bifurq-aio.desktop"
    cat "$LANCEUR"
    if ! command -v desktop-file-validate >/dev/null; then
        sudo -n apt-get install -y -qq desktop-file-utils >/dev/null 2>&1
    fi
    verifier "lanceur du menu des applications valide" desktop-file-validate "$LANCEUR"
fi

etape "Planification : à l'ouverture de session et chaque jour à 09:15"
cd "$D" || exit 1
lignes() { cat config/sortie.log 2>/dev/null | wc -l; }
AVANT=$(lignes)
verifier "planifier" config/venv/bin/python3 -c "from veille_ia import plateforme; plateforme.planifier(True, True, '09:15')"
sleep 3
if [ "$(lignes)" != "$AVANT" ]; then ko "aucune analyse à la planification" "$(tail -3 config/sortie.log)"
else ok "aucune analyse lancée par la planification elle-même"; fi
if [ "$SYSTEME" = "Darwin" ]; then
    ETIQUETTE=io.github.pierreribeaucourt.bifurq-aio
    AGENTS="$HOME/Library/LaunchAgents"
    verifier "agent du démarrage valide" plutil -lint "$AGENTS/$ETIQUETTE.demarrage.plist"
    verifier "agent quotidien valide" plutil -lint "$AGENTS/$ETIQUETTE.quotidien.plist"
    verifier "agent quotidien chargé" launchctl print "gui/$(id -u)/$ETIQUETTE.quotidien"
    launchctl print "gui/$(id -u)/$ETIQUETTE.quotidien" | grep -iE "state|program|calendar|Hour|Minute" | head -12
    etape "Analyse planifiée lancée par launchd"
    verifier "kickstart de l'agent" launchctl kickstart "gui/$(id -u)/$ETIQUETTE.quotidien"
else
    systemctl --user list-timers --all --no-pager | grep -i bifurq
    verifier "minuterie quotidienne active" systemctl --user is-active bifurq-aio-quotidien.timer
    verifier "minuterie du démarrage activée" systemctl --user is-enabled bifurq-aio-demarrage.timer
    etape "Analyse planifiée lancée par systemd"
    verifier "service de l'analyse" systemctl --user start bifurq-aio.service
fi
i=0; while [ $i -lt 30 ] && [ "$(lignes)" = "$AVANT" ]; do sleep 1; i=$((i + 1)); done
if tail -1 config/sortie.log 2>/dev/null | grep -q "aucun site configuré"; then ok "l'analyse planifiée a tourné"
else ko "analyse planifiée" "$(tail -5 config/sortie.log config/veille.log 2>&1)"; fi

etape "Notification"
verifier "notification envoyée" config/venv/bin/python3 -c "
import sys
from veille_ia import plateforme
sys.exit(0 if plateforme.notifier('Bifurq AIO', 'Essai de notification', '', print) else 1)"

etape "Retrait de la planification"
verifier "retirer" config/venv/bin/python3 -c "from veille_ia import plateforme; plateforme.retirer_planification()"
if [ "$SYSTEME" = "Darwin" ]; then
    if launchctl print "gui/$(id -u)/$ETIQUETTE.quotidien" >/dev/null 2>&1; then ko "retrait" "agent toujours chargé"
    else ok "agent déchargé"; fi
    verifier "agents supprimés" sh -c "! ls '$AGENTS' | grep -q bifurq"
else
    verifier "minuteries supprimées" sh -c "! systemctl --user list-timers --all --no-pager | grep -qi bifurq"
fi

etape "Mise à jour lancée depuis l'interface"
AVANT=$(pid_interface)
touch "$DEPOT/veille_ia/__init__.py"
verifier "installateur lancé" config/venv/bin/python3 -c \
    "from veille_ia import mise_a_jour; print(mise_a_jour.python_de_base()); mise_a_jour.lancer_installateur('$DEPOT', 8765)"
verifier "nouvelle interface sur le même port" attendre_interface "$AVANT"
if kill -0 "$AVANT" 2>/dev/null; then ko "ancienne interface" "toujours en route"; else ok "ancienne interface arrêtée"; fi

etape "Journaux"
for f in serveur.log installation.log sortie.log veille.log notifications.log; do
    [ -f "config/$f" ] && { echo "--- $f"; tail -15 "config/$f"; }
done

echo
if [ $ECHECS -gt 0 ]; then echo "$ECHECS vérification(s) en échec"; exit 1; fi
echo "Toutes les vérifications passent."
