#!/bin/sh
# Installation de Bifurq AIO sur macOS et Linux. À coller dans le Terminal :
#
#   curl -fsSL https://pierreribeaucourt.github.io/bifurq-aio/installer.sh | sh
#
# Télécharge la dernière version publiée depuis GitHub puis lance son installateur
# (installer.pyw), qui copie l'outil dans votre dossier personnel, sans droits
# d'administrateur, et l'ouvre dans votre navigateur. Relancer la même ligne met
# l'outil à jour en gardant vos sites et réglages.
#
# Un fichier téléchargé par curl ne porte pas la marque de quarantaine de macOS :
# Gatekeeper ne bloque ni cette installation ni l'application qu'elle crée.
#
# Pour les essais : BIFURQ_ZIP remplace l'adresse du ZIP (file:// accepté).

set -eu

SITE="https://pierreribeaucourt.github.io/bifurq-aio"
DEPOT="https://github.com/PierreRibeaucourt/bifurq-aio"

erreur() {
    printf '\n%s\n\n' "$1" >&2
    exit 1
}

trouver_python() {
    for p in python3 python; do
        if command -v "$p" >/dev/null 2>&1 \
                && "$p" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then
            command -v "$p"
            return 0
        fi
    done
    return 1
}

principal() {
    if ! PYTHON=$(trouver_python); then
        if [ "$(uname)" = "Darwin" ]; then
            erreur "Python 3 n'est pas installé sur ce Mac. Téléchargez-le sur https://www.python.org/downloads/ et installez-le, puis collez à nouveau la ligne d'installation. Si macOS propose d'installer les outils de développement, acceptez : ils contiennent aussi Python."
        fi
        erreur "Python 3.8 ou plus récent est nécessaire. Installez le paquet python3 de votre distribution (par exemple : sudo apt install python3), puis collez à nouveau la ligne d'installation."
    fi
    command -v curl >/dev/null 2>&1 || erreur "La commande curl est nécessaire pour télécharger l'outil."

    ZIP="${BIFURQ_ZIP:-}"
    if [ -z "$ZIP" ]; then
        VERSION=$(curl -fsSL "$SITE/version.json" \
            | "$PYTHON" -c 'import json, sys; print(json.load(sys.stdin)["version"])' 2>/dev/null) \
            || erreur "La dernière version n'a pas pu être lue sur $SITE. Vérifiez votre connexion à Internet et réessayez."
        case "$VERSION" in
            *[!0-9.]* | "") erreur "Numéro de version illisible sur $SITE : $VERSION" ;;
        esac
        ZIP="$DEPOT/archive/refs/tags/v$VERSION.zip"
        printf 'Téléchargement de Bifurq AIO %s...\n' "$VERSION"
    fi

    TEMP=$(mktemp -d)
    trap 'rm -rf "$TEMP"' EXIT
    curl -fsSL "$ZIP" -o "$TEMP/bifurq-aio.zip" \
        || erreur "Le téléchargement a échoué. Vérifiez votre connexion à Internet et réessayez."
    "$PYTHON" -m zipfile -e "$TEMP/bifurq-aio.zip" "$TEMP/code"
    INSTALLATEUR=$(find "$TEMP/code" -name installer.pyw -type f | head -n 1)
    [ -n "$INSTALLATEUR" ] || erreur "Le téléchargement ne contient pas l'installateur de l'outil."

    printf 'Installation...\n'
    "$PYTHON" "$INSTALLATEUR" --terminal </dev/null
}

# tout le script est lu avant de s'exécuter : un téléchargement coupé ne lance rien
principal "$@"
