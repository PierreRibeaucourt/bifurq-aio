# -*- coding: utf-8 -*-
"""Installateur de l'outil : un double-clic depuis l'Explorateur Windows.

Un .pyw plutôt qu'un .bat : le Contrôle intelligent des applications de Windows 11
bloque les .bat téléchargés (marque "provient d'Internet"), sans bouton pour passer
outre, alors qu'il laisse Python ouvrir un .pyw. pythonw n'a pas de console : une
erreur s'affiche dans une boîte de dialogue, jamais en silence.

L'outil est copié dans un dossier fixe, %LOCALAPPDATA%\\Bifurq AIO, et non
lancé depuis le dossier téléchargé : chaque nouveau téléchargement arrive dans un
dossier différent ("... (1)", "... (2)"), qui deviendrait sinon une installation de
plus, vide. Relancer un installateur plus récent met donc l'outil à jour en gardant
ses sites et réglages (config\\), et le dossier téléchargé peut être supprimé.

Étapes : copie du code, reprise des sites d'une installation faite dans un dossier
téléchargé (avant ce dossier fixe), environnement Python (config\\venv, sans pip :
aucune dépendance externe), raccourci du bureau et tâche planifiée remise sur le
dossier fixe, puis lancement de l'interface, qui s'ouvre dans le navigateur."""
import ctypes
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import traceback
import venv

ICI = os.path.dirname(os.path.abspath(__file__))
DESTINATION = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local"),
                           "Bifurq AIO")
A_COPIER = ("veille_ia", "scripts_windows", "lancer_veille.pyw", "installer.pyw", "icone.ico",
            "requirements.txt", "LICENSE", "README.md")
A_NE_PAS_REPRENDRE = ("venv", "serveur.json", "_temp_jeton.json", "installation.log")
TITRE = "Bifurq AIO"
SANS_FENETRE = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def message(texte, erreur=False):
    # icône, premier plan et au-dessus des autres fenêtres : le navigateur s'ouvre en même temps
    ctypes.windll.user32.MessageBoxW(None, texte, TITRE, (0x10 if erreur else 0x40) | 0x10000 | 0x40000)


def meme_dossier(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def retirer_marques_internet(racine):
    """Retire la marque "provient d'Internet" (flux Zone.Identifier) des fichiers de
    l'outil, pour que Windows ne bride pas ses scripts PowerShell (notification, tâche
    planifiée). Sans effet sur un disque qui ne gère pas ces flux (clé USB en FAT)."""
    for dossier, sous_dossiers, fichiers in os.walk(racine):
        if dossier == racine:
            sous_dossiers[:] = [d for d in sous_dossiers if d not in ("config", ".git")]
        for f in fichiers:
            try:
                os.remove(os.path.join(dossier, f) + ":Zone.Identifier")
            except OSError:
                pass


def _synchroniser(source, destination):
    """destination devient une copie de source (hors __pycache__) : fichiers copiés,
    fichiers d'une version précédente disparus de source retirés."""
    attendus = set()
    for dossier, sous_dossiers, fichiers in os.walk(source):
        sous_dossiers[:] = [d for d in sous_dossiers if d != "__pycache__"]
        relatif = os.path.relpath(dossier, source)
        os.makedirs(os.path.join(destination, relatif), exist_ok=True)
        for f in fichiers:
            chemin = os.path.normpath(os.path.join(relatif, f))
            attendus.add(os.path.normcase(chemin))
            shutil.copyfile(os.path.join(source, chemin), os.path.join(destination, chemin))
    for dossier, sous_dossiers, fichiers in os.walk(destination):
        sous_dossiers[:] = [d for d in sous_dossiers if d != "__pycache__"]
        for f in fichiers:
            chemin = os.path.normpath(os.path.join(os.path.relpath(dossier, destination), f))
            if os.path.normcase(chemin) not in attendus:
                os.remove(os.path.join(destination, chemin))


def copier_outil(source, destination):
    """Copie ou met à jour le code de l'outil dans destination, sans toucher à config\\.
    copyfile ne copie que le contenu : pas la marque "provient d'Internet"."""
    os.makedirs(destination, exist_ok=True)
    for nom in A_COPIER:
        src, dst = os.path.join(source, nom), os.path.join(destination, nom)
        if os.path.isdir(src):
            _synchroniser(src, dst)
        elif os.path.isfile(src):
            shutil.copyfile(src, dst)


def _a_des_sites(dossier_config):
    try:
        with io.open(os.path.join(dossier_config, "sites.json"), encoding="utf-8") as f:
            return bool(json.load(f).get("sites"))
    except (OSError, ValueError):
        return False


def reprendre_configuration(source, destination):
    """Reprend les sites, connexions Google et rapports d'une installation lancée depuis
    son dossier téléchargé (versions d'avant le dossier fixe), si le dossier fixe n'a pas
    encore de sites. Rend True si une configuration a été reprise."""
    src, dst = os.path.join(source, "config"), os.path.join(destination, "config")
    if not _a_des_sites(src) or _a_des_sites(dst):
        return False
    os.makedirs(dst, exist_ok=True)
    for nom in os.listdir(src):
        if nom in A_NE_PAS_REPRENDRE:
            continue
        chemin = os.path.join(src, nom)
        if os.path.isdir(chemin):
            shutil.copytree(chemin, os.path.join(dst, nom), dirs_exist_ok=True, copy_function=shutil.copyfile)
        else:
            shutil.copyfile(chemin, os.path.join(dst, nom))
    return True


def arreter_interface(dossier):
    """Arrête l'interface lancée depuis dossier, pour libérer son port."""
    try:
        with io.open(os.path.join(dossier, "config", "serveur.json"), encoding="utf-8") as f:
            pid = json.load(f).get("pid")
        if pid:
            os.kill(int(pid), signal.SIGTERM)          # sous Windows : fin immédiate du processus
    except (OSError, ValueError, TypeError):
        pass


def environnement_valide(dossier_venv):
    """L'environnement existe et le Python sur lequel il repose est toujours installé
    (une mise à jour de Python peut retirer l'ancienne version)."""
    try:
        with io.open(os.path.join(dossier_venv, "pyvenv.cfg"), encoding="utf-8") as f:
            for ligne in f:
                cle, _, valeur = ligne.partition("=")
                if cle.strip() == "home":
                    return (os.path.isfile(os.path.join(dossier_venv, "Scripts", "pythonw.exe"))
                            and os.path.isdir(valeur.strip()))
    except OSError:
        pass
    return False


def installer(source=ICI, destination=DESTINATION):
    """Rend le message de fin à afficher, ou None (installateur relancé depuis le dossier
    installé lui-même : simple réparation, rien à annoncer)."""
    depuis_telechargement = not meme_dossier(source, destination)
    mise_a_jour = _a_des_sites(os.path.join(destination, "config"))
    reprise = False
    if depuis_telechargement:
        copier_outil(source, destination)
        arreter_interface(source)                      # ancienne installation dans ce dossier
        reprise = reprendre_configuration(source, destination)
    retirer_marques_internet(destination)
    dossier_venv = os.path.join(destination, "config", "venv")
    if not environnement_valide(dossier_venv):
        venv.create(dossier_venv, clear=True, with_pip=False)
    scripts = os.path.join(dossier_venv, "Scripts")
    # raccourci du bureau, tâche planifiée remise sur ce dossier : par le code installé, avec
    # python.exe sans fenêtre plutôt que pythonw, pour recueillir une éventuelle erreur
    r = subprocess.run([os.path.join(scripts, "python.exe"), "-m", "veille_ia.installation"], cwd=destination,
                       capture_output=True, text=True, timeout=180, creationflags=SANS_FENETRE)
    if r.returncode != 0:
        raise RuntimeError("tâche planifiée non mise en place : %s" % (r.stderr or r.stdout).strip()[-600:])
    subprocess.Popen([os.path.join(scripts, "pythonw.exe"), "-m", "veille_ia.installer.server"],
                     cwd=destination, close_fds=True)
    if not depuis_telechargement:
        return None
    if mise_a_jour:
        debut = "Bifurq AIO est à jour. Vos sites et réglages sont conservés."
    elif reprise:
        debut = ("Bifurq AIO est installé. Les sites de votre installation "
                 "précédente ont été repris.")
    else:
        debut = "Bifurq AIO est installé."
    return ("%s\n\nL'outil s'ouvre dans votre navigateur. Pour le rouvrir plus tard : raccourci "
            "Bifurq AIO sur votre bureau.\n\nVous pouvez supprimer le fichier ZIP et "
            "le dossier téléchargés : l'outil n'en a plus besoin." % debut)


if __name__ == "__main__":
    if sys.version_info < (3, 8):
        message("Cet outil demande Python 3.8 ou plus récent. Installez la dernière version depuis "
                "python.org, puis relancez l'installateur.", erreur=True)
        sys.exit(1)
    try:
        fin = installer()
    except Exception:
        detail = traceback.format_exc()
        journal = os.path.join(DESTINATION, "config", "installation.log")
        try:
            os.makedirs(os.path.dirname(journal), exist_ok=True)
            io.open(journal, "a", encoding="utf-8").write(detail)
        except OSError:
            pass
        message("L'installation n'a pas pu se terminer.\n\n%s\n\nLe détail est dans %s."
                % (detail.strip().splitlines()[-1], journal), erreur=True)
        sys.exit(1)
    if fin:
        message(fin)
