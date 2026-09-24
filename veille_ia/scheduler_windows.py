# -*- coding: utf-8 -*-
"""Installation/retrait de la tâche planifiée Windows, depuis les choix cochés dans
l'installateur web (démarrage du PC, heure fixe, ou les deux). Aucune manipulation
de PowerShell n'est demandée à l'utilisateur : ce module construit la commande et
l'exécute pour lui."""
import os
import subprocess

from . import config

NOM_TACHE = "Veille adresses inventees IA"
PLANIFIER_PS1 = os.path.join(config.racine(), "scripts_windows", "planifier.ps1")


def pythonw_exe():
    return os.path.join(config.racine(), "config", "venv", "Scripts", "pythonw.exe")


def lancer_veille_pyw():
    return os.path.join(config.racine(), "lancer_veille.pyw")


def _powershell(args):
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", PLANIFIER_PS1] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise RuntimeError("commande PowerShell refusée : %s" % ((r.stderr or r.stdout) or "").strip()[:500])
    return (r.stdout or "").strip()


def installer(au_demarrage, actif_heure_fixe, heure_fixe):
    if not au_demarrage and not actif_heure_fixe:
        raise ValueError("au moins un déclenchement (démarrage ou heure fixe) doit être actif")
    args = ["-NomTache", NOM_TACHE, "-CheminPythonw", pythonw_exe(), "-CheminScript", lancer_veille_pyw()]
    if au_demarrage:
        args.append("-AuDemarrage")
    if actif_heure_fixe:
        args += ["-HeureFixe", "-Heure", heure_fixe]
    return _powershell(args)


def desinstaller():
    return _powershell(["-NomTache", NOM_TACHE, "-Desinstaller"])
