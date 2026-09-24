# -*- coding: utf-8 -*-
"""Nouvelle version de l'outil : repérée une fois par jour, installée en un clic.

La dernière version publiée est décrite par version.json, sur le site de l'outil : son
numéro et une phrase sur ses nouveautés. L'adresse du ZIP ne vient pas de ce fichier :
elle est construite ici, vers l'étiquette de cette version dans le dépôt GitHub de
l'outil, et nulle part ailleurs.

La mise à jour est l'installateur de la nouvelle version (installer.pyw), lancé après
son téléchargement : il copie le code, garde config\\ et relance l'interface, qui
remplace l'ancienne. Un fichier écrit par Python ne porte pas la marque "provient
d'Internet" : le Contrôle intelligent des applications ne bloque pas cet installateur."""
import glob
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

from . import __version__, config
from .style import SITE

URL_VERSION = SITE + "version.json"
URL_ZIP = "https://github.com/PierreRibeaucourt/bifurq-aio/archive/refs/tags/v%s.zip"
FORMAT = re.compile(r"^\d{1,4}\.\d{1,4}\.\d{1,4}$")
INTERVALLE = 20 * 3600             # secondes entre deux lectures de version.json
PREFIXE_TEMP = "bifurq-aio-maj-"
UA = {"User-Agent": "Bifurq-AIO/%s (+https://github.com/PierreRibeaucourt/bifurq-aio)" % __version__}


def numero(version):
    return tuple(int(x) for x in version.split("."))


def _fichier():
    return os.path.join(config.dossier_config(), "mise_a_jour.json")


def lire():
    """Dernière lecture de version.json : {"verifie": horodatage, "version", "nouveautes"}."""
    try:
        with io.open(_fichier(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _ecrire(etat):
    os.makedirs(config.dossier_config(), exist_ok=True)
    with io.open(_fichier(), "w", encoding="utf-8") as f:
        json.dump(etat, f, ensure_ascii=False)


def _lire_en_ligne():
    req = urllib.request.Request(URL_VERSION, headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=10).read().decode("utf-8"))


def verifier(maintenant=None, force=False):
    """Lit version.json au plus une fois toutes les INTERVALLE secondes. Une erreur
    (hors ligne, fichier illisible) ne gêne rien : nouvel essai à l'intervalle suivant."""
    maintenant = time.time() if maintenant is None else maintenant
    etat = lire()
    if not force and "verifie" in etat and maintenant - etat["verifie"] < INTERVALLE:
        return etat
    try:
        d = _lire_en_ligne()
        version = str(d.get("version", ""))
        if not FORMAT.match(version):
            raise ValueError("numéro de version illisible : %r" % version)
        etat = {"verifie": maintenant, "version": version, "nouveautes": str(d.get("nouveautes", ""))[:400]}
    except Exception:
        etat = dict(etat, verifie=maintenant)
    _ecrire(etat)
    return etat


def disponible():
    """{"version", "nouveautes"} d'une version plus récente que celle installée, ou None."""
    etat = lire()
    version = etat.get("version") or ""
    if FORMAT.match(version) and numero(version) > numero(__version__):
        return {"version": version, "nouveautes": etat.get("nouveautes", "")}
    return None


def _nettoyer_anciens_telechargements():
    for dossier in glob.glob(os.path.join(tempfile.gettempdir(), PREFIXE_TEMP + "*")):
        shutil.rmtree(dossier, ignore_errors=True)


def telecharger(version):
    """Télécharge et décompresse cette version. Rend le dossier qui contient son
    installateur."""
    if not FORMAT.match(version):
        raise ValueError("numéro de version illisible : %r" % version)
    _nettoyer_anciens_telechargements()
    dossier = tempfile.mkdtemp(prefix=PREFIXE_TEMP)
    archive = os.path.join(dossier, "bifurq-aio.zip")
    req = urllib.request.Request(URL_ZIP % version, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r, io.open(archive, "wb") as f:
        shutil.copyfileobj(r, f)
    code = os.path.join(dossier, "code")
    with zipfile.ZipFile(archive) as z:
        z.extractall(code)                   # extractall écarte les chemins absolus et les ".."
    for racine, _, fichiers in os.walk(code):
        if "installer.pyw" in fichiers and os.path.isdir(os.path.join(racine, "veille_ia")):
            return racine
    raise ValueError("le téléchargement ne contient pas l'installateur de l'outil")


def python_de_base():
    """pythonw.exe du Python sur lequel repose l'environnement de l'outil (config\\venv).
    L'installateur peut devoir recréer cet environnement : il ne doit pas tourner dedans."""
    try:
        with io.open(os.path.join(sys.prefix, "pyvenv.cfg"), encoding="utf-8") as f:
            for ligne in f:
                cle, _, valeur = ligne.partition("=")
                if cle.strip() == "home":
                    candidat = os.path.join(valeur.strip(), "pythonw.exe")
                    if os.path.isfile(candidat):
                        return candidat
    except OSError:
        pass
    return sys.executable


def lancer_installateur(dossier_code, port):
    """Lance l'installateur téléchargé, détaché de l'interface actuelle, qu'il remplacera.
    port : celui de l'interface actuelle, que la nouvelle reprend pour que la page ouverte
    la retrouve."""
    detache = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([python_de_base(), os.path.join(dossier_code, "installer.pyw"), "--mise-a-jour", str(port)],
                     cwd=dossier_code, close_fds=True, creationflags=detache)
