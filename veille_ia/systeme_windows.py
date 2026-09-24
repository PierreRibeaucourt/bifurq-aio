# -*- coding: utf-8 -*-
"""Windows : tâche planifiée et notification (toast natif) par les scripts PowerShell de
scripts_windows/, raccourci sur le bureau. Aucune manipulation de PowerShell n'est
demandée à l'utilisateur : ce module construit les commandes et les exécute pour lui."""
import os
import subprocess

from . import config, plateforme

NOM_TACHE = plateforme.NOM
SANS_FENETRE = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _script(nom):
    return os.path.join(config.racine(), "scripts_windows", nom)


def _ps(texte):
    return "'" + texte.replace("'", "''") + "'"


def _powershell(args, timeout=60):
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass"] + args, capture_output=True,
                       text=True, timeout=timeout, creationflags=SANS_FENETRE)
    if r.returncode != 0:
        raise RuntimeError("commande PowerShell refusée : %s" % ((r.stderr or r.stdout) or "").strip()[:500])
    return (r.stdout or "").strip()


def planifier(au_demarrage, actif_heure_fixe, heure_fixe):
    args = ["-File", _script("planifier.ps1"), "-NomTache", NOM_TACHE,
            "-CheminPythonw", plateforme.python_de_l_outil(), "-CheminScript", plateforme.lanceur_des_analyses()]
    if au_demarrage:
        args.append("-AuDemarrage")
    if actif_heure_fixe:
        args += ["-HeureFixe", "-Heure", heure_fixe]
    return _powershell(args)


def retirer_planification():
    return _powershell(["-File", _script("planifier.ps1"), "-NomTache", NOM_TACHE, "-Desinstaller"])


def creer_raccourci(dossier=None):
    """Raccourci dans dossier (par défaut : le bureau de l'utilisateur, y compris un
    bureau déplacé dans OneDrive)."""
    racine = config.racine()
    icone = os.path.join(racine, "icone.ico")
    cible = "[Environment]::GetFolderPath('Desktop')" if dossier is None else _ps(dossier)
    script = ("$d=%s;$p=Join-Path $d %s;"
              "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($p);"
              "$s.TargetPath=%s;$s.Arguments='-m veille_ia.installer.server';$s.WorkingDirectory=%s;"
              "$s.Description=%s;%s$s.Save();$p"
              % (cible, _ps(plateforme.NOM + ".lnk"), _ps(plateforme.python_de_l_outil()), _ps(racine),
                 _ps("Ouvre Bifurq AIO, la veille des adresses inventées par l'IA de Google"),
                 "$s.IconLocation=%s;" % _ps(icone + ",0") if os.path.isfile(icone) else ""))
    try:
        return _powershell(["-Command", script])
    except RuntimeError as ex:
        raise RuntimeError("raccourci non créé : %s" % ex)


def notifier(titre, texte, rapport=""):
    """Toast natif ; un clic ouvre le rapport s'il est donné."""
    args = ["-File", _script("notifier.ps1"), "-Titre", titre, "-Texte", texte]
    if rapport:
        args += ["-Rapport", rapport]
    _powershell(args)
