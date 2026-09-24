#!/bin/sh
# Paquets d'installation par double-clic (outils/paquets.py), essayés comme un utilisateur :
# - Linux : .deb installé par apt (ce que fait la logithèque), puis « Bifurq AIO » ouvert
#   depuis le menu ; .rpm installé par dnf dans un conteneur Fedora ;
# - macOS : application téléchargée (marque de quarantaine), autorisée puis ouverte.
# Chaque vérification ratée devient une annotation ::error:: de GitHub Actions.
set -u

ECHECS=0
ok() { printf '  ok : %s\n' "$1"; }
ko() { printf '::error title=%s::%s\n' "$1" "$(printf '%s' "$2" | tr '\n' ' ' | cut -c1-900)"; ECHECS=$((ECHECS + 1)); }
etape() { printf '\n===== %s\n' "$1"; }
verifier() {
    description=$1; shift
    if resultat=$("$@" 2>&1); then ok "$description"; else ko "$description" "$resultat"; fi
}
interface() {                       # interface : attend que l'interface réponde
    i=0
    while [ $i -lt 40 ]; do curl -fs http://127.0.0.1:8765/ping >/dev/null && return 0; sleep 1; i=$((i + 1)); done
    return 1
}

etape "Construction"
if [ "$(uname)" = "Linux" ]; then sudo -n apt-get install -y -qq rpm desktop-file-utils >/dev/null 2>&1; fi
python3 outils/paquets.py dist
ls -l dist

if [ "$(uname)" = "Linux" ]; then
    D="$HOME/.local/share/bifurq-aio"
    etape "Paquet .deb"
    verifier "installation par apt" sudo -n env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$(pwd)/dist/bifurq-aio.deb"
    verifier "entrée du menu valide" desktop-file-validate /usr/share/applications/bifurq-aio.desktop
    /opt/bifurq-aio/bifurq-aio </dev/null >/tmp/lanceur.log 2>&1 &
    if interface; then ok "première ouverture : outil installé et ouvert"; else ko "première ouverture" "$(cat /tmp/lanceur.log)"; fi
    verifier "outil dans le dossier de l'utilisateur" test -x "$D/config/venv/bin/python3"
    AVANT=$(stat -c %Y "$D/veille_ia/watch.py")
    pkill -f veille_ia.installer.server; sleep 1
    /opt/bifurq-aio/bifurq-aio </dev/null >/tmp/lanceur2.log 2>&1 &
    if interface; then ok "seconde ouverture"; else ko "seconde ouverture" "$(cat /tmp/lanceur2.log)"; fi
    [ "$(stat -c %Y "$D/veille_ia/watch.py")" = "$AVANT" ] && ok "pas de réinstallation" || ko "seconde ouverture" "réinstallé"
    pkill -f veille_ia.installer.server
    verifier "désinstallation" sudo -n apt-get remove -y -qq bifurq-aio
    verifier "outil de l'utilisateur gardé" test -d "$D"

    etape "Paquet .rpm dans Fedora"
    sortie=$(docker run --rm -v "$(pwd)/dist:/dist:ro" fedora:latest sh -c '
        dnf install -y -q /dist/bifurq-aio.rpm >/dev/null && useradd -m essai &&
        su - essai -c "/opt/bifurq-aio/bifurq-aio </dev/null >/tmp/lanceur.log 2>&1 &
            for i in \$(seq 1 40); do curl -fs http://127.0.0.1:8765/ping && exit 0; sleep 1; done
            cat /tmp/lanceur.log; exit 1"' 2>&1)
    case "$sortie" in *bifurq-aio*) ok "rpm installé par dnf, outil ouvert" ;; *) ko "paquet .rpm" "$sortie" ;; esac
else
    etape "Application macOS, téléchargée"
    DOSSIER="$HOME/Downloads/essai-bifurq"
    rm -rf "$DOSSIER" && mkdir -p "$DOSSIER"
    cp dist/Bifurq-AIO-Mac.zip "$DOSSIER/"
    xattr -w com.apple.quarantine "0083;$(printf %x "$(date +%s)");Safari;" "$DOSSIER/Bifurq-AIO-Mac.zip"
    ditto -x -k "$DOSSIER/Bifurq-AIO-Mac.zip" "$DOSSIER"
    APP="$DOSSIER/Installer Bifurq AIO.app"
    xattr -w -r com.apple.quarantine "0083;$(printf %x "$(date +%s)");Safari;" "$APP" 2>/dev/null
    verifier "script de l'application exécutable" test -x "$APP/Contents/MacOS/installer"
    verifier "Info.plist valide" plutil -lint "$APP/Contents/Info.plist"
    echo "::notice title=Gatekeeper::$(spctl --assess --type execute -vv "$APP" 2>&1 | tr '\n' ' ')"
    # l'utilisateur autorise l'application (Ouvrir quand même) : macOS ne la bloque plus
    xattr -dr com.apple.quarantine "$APP"
    verifier "double-clic (open)" open "$APP"
    if interface; then ok "outil installé et ouvert"; else ko "application d'installation" "$(tail -5 "$HOME/Library/Application Support/Bifurq AIO/config/serveur.log" 2>&1)"; fi
    verifier "outil dans Application Support" test -x "$HOME/Library/Application Support/Bifurq AIO/config/venv/bin/python3"
    verifier "application Bifurq AIO créée" test -x "$HOME/Applications/Bifurq AIO.app/Contents/MacOS/bifurq-aio"
fi

echo
if [ $ECHECS -gt 0 ]; then echo "$ECHECS vérification(s) en échec"; exit 1; fi
echo "Toutes les vérifications passent."
