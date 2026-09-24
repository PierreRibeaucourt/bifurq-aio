# -*- coding: utf-8 -*-
"""Raccourci sur le bureau pour rouvrir l'outil sans repasser par installer.bat.

  python -m veille_ia.raccourci"""
import os
import subprocess
import sys

from . import config

NOM = "Veille des adresses inventées"


def _ps(texte):
    return "'" + texte.replace("'", "''") + "'"


def creer_raccourci(dossier=None):
    """Crée le raccourci dans dossier (par défaut : le bureau de l'utilisateur, y
    compris un bureau déplacé dans OneDrive)."""
    racine = config.racine()
    pythonw = os.path.join(racine, "config", "venv", "Scripts", "pythonw.exe")
    cible = "[Environment]::GetFolderPath('Desktop')" if dossier is None else _ps(dossier)
    script = ("$d=%s;$p=Join-Path $d %s;"
              "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($p);"
              "$s.TargetPath=%s;$s.Arguments='-m veille_ia.installer.server';$s.WorkingDirectory=%s;"
              "$s.Description=%s;$s.Save();$p"
              % (cible, _ps(NOM + ".lnk"), _ps(pythonw), _ps(racine), _ps("Ouvre l'outil de veille des adresses inventées")))
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                       capture_output=True, text=True, timeout=60,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise RuntimeError("raccourci non créé : %s" % (r.stderr or r.stdout).strip()[:300])


if __name__ == "__main__":
    try:
        creer_raccourci()
        print("Raccourci ajoute sur le bureau.")
    except Exception:
        print("Le raccourci n'a pas pu etre cree. Relancez installer.bat pour rouvrir l'outil.")
        sys.exit(0)
