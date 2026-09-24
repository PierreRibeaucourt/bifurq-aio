# -*- coding: utf-8 -*-
"""Paquets d'installation par double-clic pour macOS et Linux, construits par GitHub
Actions pour chaque version et joints à sa publication (Release) :

  python3 outils/paquets.py dist

- Bifurq-AIO-Mac.zip : l'application Installer Bifurq AIO. Elle lance installer.pyw,
  qu'elle contient, avec le Python du Mac. Sans signature Apple : au premier lancement,
  macOS demande une autorisation (Réglages Système > Confidentialité et sécurité).
- bifurq-aio.deb (Ubuntu, Debian, Mint) et bifurq-aio.rpm (Fedora, openSUSE) : l'outil
  dans /opt/bifurq-aio et Bifurq AIO dans le menu des applications. À la première
  ouverture, cette entrée installe l'outil dans le dossier de l'utilisateur, comme
  installer.pyw sous Windows ; ensuite, elle ouvre son interface. Un double-clic sur le
  paquet l'ouvre dans la logithèque de la distribution.

Le .zip et le .deb sont construits ici même, en Python. Le .rpm demande rpmbuild (paquet
rpm) ; sans lui, il est sauté."""
import gzip
import hashlib
import io
import os
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# ce qu'installer.pyw copie dans le dossier de l'utilisateur (A_COPIER) : rien d'autre
FICHIERS = ("veille_ia", "scripts_windows", "lancer_veille.pyw", "installer.pyw", "icone.ico", "icone.icns",
            "icone.png", "requirements.txt", "LICENSE", "README.md")
NOM = "Bifurq AIO"
PAQUET = "bifurq-aio"
OPT = "/opt/bifurq-aio"
DESCRIPTION = "Veille des adresses inventées par l'IA de Google"
SITE = "https://pierreribeaucourt.github.io/bifurq-aio/"
MAINTENEUR = "Pierre Ribeaucourt <208388986+PierreRibeaucourt@users.noreply.github.com>"
APPLICATION_MAC = "Installer Bifurq AIO.app"
# noms des fichiers publiés : le site les télécharge sous releases/latest/download/
ZIP_MAC, DEB, RPM = "Bifurq-AIO-Mac.zip", "bifurq-aio.deb", "bifurq-aio.rpm"


def version():
    texte = io.open(os.path.join(RACINE, "veille_ia", "__init__.py"), encoding="utf-8").read()
    return re.search(r'^__version__ = "([0-9.]+)"', texte, re.M).group(1)


def date_fixe():
    """Date des fichiers des paquets : celle du dernier commit, pour des paquets identiques
    d'une construction à l'autre."""
    try:
        return int(os.environ.get("SOURCE_DATE_EPOCH") or subprocess.run(
            ["git", "-C", RACINE, "log", "-1", "--format=%ct"], capture_output=True, text=True).stdout.strip())
    except (OSError, ValueError):
        return int(time.time())


def fichiers_du_code():
    """(chemin relatif avec des /, chemin sur le disque) de chaque fichier de l'outil."""
    for nom in FICHIERS:
        chemin = os.path.join(RACINE, nom)
        if os.path.isfile(chemin):
            yield nom, chemin
            continue
        for dossier, sous_dossiers, fichiers in os.walk(chemin):
            sous_dossiers[:] = sorted(d for d in sous_dossiers if d != "__pycache__")
            for f in sorted(fichiers):
                if f.endswith((".pyc", ".pyo")):
                    continue
                complet = os.path.join(dossier, f)
                yield os.path.relpath(complet, RACINE).replace(os.sep, "/"), complet


# --- macOS ----------------------------------------------------------------------------------------
SCRIPT_MAC = r"""#!/bin/sh
# Installer Bifurq AIO : lance installer.pyw, livré dans Resources/code, avec le Python du Mac.
CODE="$(cd "$(dirname "$0")/../Resources/code" && pwd)"
valide() { [ -x "$1" ] && "$1" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; }
PYTHON=""
for p in /Library/Frameworks/Python.framework/Versions/Current/bin/python3 /opt/homebrew/bin/python3 \
        /usr/local/bin/python3; do
    if valide "$p"; then PYTHON=$p; break; fi
done
# celui de macOS seulement avec les outils de développement : sans eux, /usr/bin/python3
# propose de les installer au lieu de répondre
if [ -z "$PYTHON" ] && xcode-select -p >/dev/null 2>&1 && valide /usr/bin/python3; then PYTHON=/usr/bin/python3; fi
if [ -z "$PYTHON" ]; then
    choix=$(osascript -e 'on run argv' -e 'activate' \
        -e 'display dialog (item 1 of argv) with title "Bifurq AIO" buttons {"Plus tard", "Télécharger Python"} default button 2 with icon caution' \
        -e 'end run' "Bifurq AIO a besoin de Python 3.8 ou plus récent. Téléchargez-le sur python.org et installez-le, puis ouvrez à nouveau Installer Bifurq AIO." 2>/dev/null)
    case "$choix" in *Python*) open "https://www.python.org/downloads/macos/" ;; esac
    exit 1
fi
exec "$PYTHON" "$CODE/installer.pyw"
"""


def _entree_zip(nom, mode, date):
    info = zipfile.ZipInfo(nom, time.localtime(date)[:6])
    info.create_system = 3                      # Unix : l'Utilitaire d'archive garde les droits
    info.external_attr = mode << 16
    if stat.S_ISDIR(mode):
        info.external_attr |= 0x10
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def zip_mac(sortie):
    date = date_fixe()
    app = APPLICATION_MAC + "/Contents/"
    infos = {"CFBundleName": "Installer " + NOM, "CFBundleDisplayName": "Installer " + NOM,
             "CFBundleIdentifier": "io.github.pierreribeaucourt.bifurq-aio.installateur",
             "CFBundleExecutable": "installer", "CFBundlePackageType": "APPL", "CFBundleIconFile": "icone",
             "CFBundleShortVersionString": version(), "CFBundleVersion": version(),
             "LSMinimumSystemVersion": "10.13", "LSUIElement": True}
    fichiers = [(app + "Info.plist", 0o644, plistlib.dumps(infos)),
                (app + "MacOS/installer", 0o755, SCRIPT_MAC.encode("utf-8")),
                (app + "Resources/icone.icns", 0o644, open(os.path.join(RACINE, "icone.icns"), "rb").read())]
    for relatif, chemin in fichiers_du_code():
        fichiers.append((app + "Resources/code/" + relatif, 0o644, open(chemin, "rb").read()))
    dossiers = sorted({"/".join(nom.split("/")[:i]) + "/" for nom, _, _ in fichiers
                       for i in range(1, nom.count("/") + 1)})
    with zipfile.ZipFile(sortie, "w") as z:
        for d in dossiers:
            z.writestr(_entree_zip(d, stat.S_IFDIR | 0o755, date), b"")
        for nom, mode, contenu in fichiers:
            z.writestr(_entree_zip(nom, stat.S_IFREG | mode, date), contenu)
    return sortie


# --- Linux : arborescence commune au .deb et au .rpm ---------------------------------------------
LANCEUR_LINUX = r"""#!/bin/sh
# Bifurq AIO dans le menu des applications, installé par le paquet .deb ou .rpm.
# Première ouverture, ou paquet plus récent que l'outil de l'utilisateur : installer.pyw
# copie l'outil dans le dossier de l'utilisateur et l'ouvre. Ensuite : son interface.
PAQUET=/opt/bifurq-aio
D="${XDG_DATA_HOME:-$HOME/.local/share}/bifurq-aio"
if [ -x "$D/config/venv/bin/python3" ] && python3 - "$PAQUET" "$D" <<'FIN'
import re, sys
def version(dossier):
    try:
        texte = open(dossier + "/veille_ia/__init__.py", encoding="utf-8").read()
        return tuple(int(x) for x in re.search(r'__version__ = "([0-9.]+)"', texte).group(1).split("."))
    except Exception:
        return None
paquet, installe = version(sys.argv[1]), version(sys.argv[2])
sys.exit(0 if installe and paquet and installe >= paquet else 1)
FIN
then
    cd "$D" && exec config/venv/bin/python3 -m veille_ia.installer.server
fi
exec python3 "$PAQUET/installer.pyw"
"""

LANCEUR_DESKTOP = """[Desktop Entry]
Type=Application
Name=%s
Comment=%s
Exec=%s/bifurq-aio
Icon=bifurq-aio
Terminal=false
Categories=Network;
StartupNotify=false
""" % (NOM, DESCRIPTION, OPT)

METAINFO = """<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>io.github.pierreribeaucourt.bifurq_aio</id>
  <metadata_license>MIT</metadata_license>
  <project_license>MIT</project_license>
  <name>%s</name>
  <summary>%s</summary>
  <description>
    <p>Repère dans votre Search Console les adresses de votre site inventées par l'IA de Google
    (AI Overview, AI Mode) et vous indique vers quelle page les rediriger.</p>
  </description>
  <launchable type="desktop-id">bifurq-aio.desktop</launchable>
  <url type="homepage">%s</url>
  <developer id="io.github.pierreribeaucourt"><name>Pierre Ribeaucourt</name></developer>
  <content_rating type="oars-1.1"/>
  <releases><release version="%%s" date="%%s"/></releases>
</component>
""" % (NOM, DESCRIPTION, SITE)


def arborescence_linux():
    """[(chemin absolu dans le système, mode, contenu)] des fichiers installés."""
    fichiers = [(OPT + "/" + relatif, 0o644, open(chemin, "rb").read()) for relatif, chemin in fichiers_du_code()]
    fichiers += [(OPT + "/bifurq-aio", 0o755, LANCEUR_LINUX.encode("utf-8")),
                 ("/usr/share/applications/bifurq-aio.desktop", 0o644, LANCEUR_DESKTOP.encode("utf-8")),
                 ("/usr/share/icons/hicolor/256x256/apps/bifurq-aio.png", 0o644,
                  open(os.path.join(RACINE, "icone.png"), "rb").read()),
                 ("/usr/share/metainfo/io.github.pierreribeaucourt.bifurq_aio.metainfo.xml", 0o644,
                  (METAINFO % (version(), time.strftime("%Y-%m-%d", time.gmtime(date_fixe())))).encode("utf-8"))]
    return fichiers


def _dossiers(chemins):
    return sorted({"/".join(c.split("/")[:i]) for c in chemins for i in range(2, c.count("/") + 1)})


def _tar_gz(entrees, date):
    """entrees : [(nom, mode, contenu ou None pour un dossier)] -> octets d'un .tar.gz."""
    tampon = io.BytesIO()
    with gzip.GzipFile(fileobj=tampon, mode="wb", mtime=date) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as tar:
            for nom, mode, contenu in entrees:
                info = tarfile.TarInfo(nom)
                info.mode, info.mtime, info.uid, info.gid, info.uname, info.gname = mode, date, 0, 0, "root", "root"
                if contenu is None:
                    info.type = tarfile.DIRTYPE
                    tar.addfile(info)
                else:
                    info.size = len(contenu)
                    tar.addfile(info, io.BytesIO(contenu))
    return tampon.getvalue()


def _ar(membres, date):
    """Archive ar, l'enveloppe d'un .deb."""
    sortie = [b"!<arch>\n"]
    for nom, contenu in membres:
        entete = "%-16s%-12d%-6d%-6d%-8s%-10d`\n" % (nom, date, 0, 0, "100644", len(contenu))
        sortie += [entete.encode("ascii"), contenu, b"\n" if len(contenu) % 2 else b""]
    return b"".join(sortie)


def deb(sortie):
    date = date_fixe()
    fichiers = arborescence_linux()
    taille = sum(len(c) for _, _, c in fichiers) // 1024 + 1
    controle = ("Package: %s\nVersion: %s\nArchitecture: all\nMaintainer: %s\nDepends: python3 (>= 3.8)\n"
                "Section: web\nPriority: optional\nHomepage: %s\nInstalled-Size: %d\n"
                "Description: %s\n Repère dans la Search Console les adresses d'un site inventées par l'IA de\n"
                " Google (AI Overview, AI Mode) et indique vers quelle page les rediriger.\n"
                % (PAQUET, version(), MAINTENEUR, SITE, taille, DESCRIPTION))
    sommes = "".join("%s  %s\n" % (hashlib.md5(c).hexdigest(), n.lstrip("/")) for n, _, c in fichiers)
    donnees = [("./", 0o755, None)] + [("." + d + "/", 0o755, None) for d in _dossiers([n for n, _, _ in fichiers])]
    donnees += [("." + n, m, c) for n, m, c in sorted(fichiers)]
    membres = [("debian-binary", b"2.0\n"),
               ("control.tar.gz", _tar_gz([("./", 0o755, None), ("./control", 0o644, controle.encode("utf-8")),
                                           ("./md5sums", 0o644, sommes.encode("utf-8"))], date)),
               ("data.tar.gz", _tar_gz(donnees, date))]
    with open(sortie, "wb") as f:
        f.write(_ar(membres, date))
    return sortie


SPEC = """Name: %(paquet)s
Version: %(version)s
Release: 1
Summary: %(description)s
License: MIT
URL: %(site)s
BuildArch: noarch
Requires: python3 >= 3.8
AutoReqProv: no
%%global debug_package %%{nil}
%%global __os_install_post %%{nil}

%%description
Repère dans la Search Console les adresses d'un site inventées par l'IA de Google
(AI Overview, AI Mode) et indique vers quelle page les rediriger.

%%install
cp -a %(arbre)s/. %%{buildroot}/

%%files
%%defattr(-,root,root,-)
%(opt)s
/usr/share/applications/bifurq-aio.desktop
/usr/share/icons/hicolor/256x256/apps/bifurq-aio.png
/usr/share/metainfo/io.github.pierreribeaucourt.bifurq_aio.metainfo.xml
"""


def rpm(sortie):
    if not shutil.which("rpmbuild"):
        return None
    travail = tempfile.mkdtemp()
    try:
        arbre = os.path.join(travail, "arbre")
        for nom, mode, contenu in arborescence_linux():
            chemin = arbre + nom
            os.makedirs(os.path.dirname(chemin), exist_ok=True)
            with open(chemin, "wb") as f:
                f.write(contenu)
            os.chmod(chemin, mode)
        spec = os.path.join(travail, "bifurq-aio.spec")
        io.open(spec, "w", encoding="utf-8").write(SPEC % {
            "paquet": PAQUET, "version": version(), "description": DESCRIPTION, "site": SITE, "arbre": arbre,
            "opt": OPT})
        r = subprocess.run(["rpmbuild", "-bb", "--define", "_topdir %s" % os.path.join(travail, "rpmbuild"),
                            "--define", "_build_id_links none", spec], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("rpmbuild : %s" % (r.stderr or r.stdout)[-1500:])
        for dossier, _, fichiers in os.walk(os.path.join(travail, "rpmbuild", "RPMS")):
            for f in fichiers:
                if f.endswith(".rpm"):
                    shutil.copyfile(os.path.join(dossier, f), sortie)
                    return sortie
        raise RuntimeError("rpmbuild n'a produit aucun paquet")
    finally:
        shutil.rmtree(travail, ignore_errors=True)


def construire(dossier):
    os.makedirs(dossier, exist_ok=True)
    faits = [zip_mac(os.path.join(dossier, ZIP_MAC)), deb(os.path.join(dossier, DEB)), rpm(os.path.join(dossier, RPM))]
    return [f for f in faits if f]


if __name__ == "__main__":
    for f in construire(sys.argv[1] if len(sys.argv) > 1 else "dist"):
        print("%s  %d octets" % (f, os.path.getsize(f)))
