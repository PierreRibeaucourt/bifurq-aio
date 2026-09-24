# -*- coding: utf-8 -*-
"""Installateur de l'outil : un double-clic depuis l'Explorateur Windows.

Un .pyw plutôt qu'un .bat : le Contrôle intelligent des applications de Windows 11
bloque les .bat téléchargés (marque "provient d'Internet"), sans bouton pour passer
outre, alors qu'il laisse Python ouvrir un .pyw. pythonw n'a pas de console : une
erreur s'affiche dans une boîte de dialogue, jamais en silence.

Prépare l'environnement Python de l'outil (config\\venv, sans pip : aucune dépendance
externe), crée le raccourci du bureau, puis lance l'interface, qui s'ouvre dans le
navigateur. Relancer l'installateur ne refait que ce qui manque."""
import ctypes
import io
import os
import subprocess
import sys
import traceback
import venv

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
VENV = os.path.join(ICI, "config", "venv")
PYTHONW = os.path.join(VENV, "Scripts", "pythonw.exe")
TITRE = "Veille des adresses inventées"


def message(texte, erreur=False):
    ctypes.windll.user32.MessageBoxW(None, texte, TITRE, 0x10 if erreur else 0x40)


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


def installer():
    retirer_marques_internet(ICI)
    if not environnement_valide(VENV):
        venv.create(VENV, clear=True, with_pip=False)
    try:
        from veille_ia import raccourci
        raccourci.creer_raccourci()
    except Exception:
        pass                                 # confort seulement : relancer l'installateur rouvre l'outil
    subprocess.Popen([PYTHONW, "-m", "veille_ia.installer.server"], cwd=ICI, close_fds=True)


if __name__ == "__main__":
    if sys.version_info < (3, 8):
        message("Cet outil demande Python 3.8 ou plus récent. Installez la dernière version depuis "
                "python.org, puis relancez l'installateur.", erreur=True)
        sys.exit(1)
    try:
        installer()
    except Exception:
        detail = traceback.format_exc()
        try:
            os.makedirs(os.path.join(ICI, "config"), exist_ok=True)
            io.open(os.path.join(ICI, "config", "installation.log"), "a", encoding="utf-8").write(detail)
        except OSError:
            pass
        message("L'installation n'a pas pu se terminer.\n\n%s\nLe détail est dans config\\installation.log."
                % detail.strip().splitlines()[-1], erreur=True)
        sys.exit(1)
