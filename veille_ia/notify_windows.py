# -*- coding: utf-8 -*-
"""Notification Windows (toast natif), et son historique texte en secours : le
centre de notifications Windows ne garde un bandeau que tant qu'il n'est pas
effacé, notifications.log reste lisible même après coup."""
import datetime
import io
import os
import subprocess

from . import config

NOTIFIER_PS1 = os.path.join(config.racine(), "scripts_windows", "notifier.ps1")


def notifier(titre, texte, rapport="", journal=None):
    """Rend True si la notification est partie."""
    j = journal or (lambda m: None)
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", NOTIFIER_PS1,
           "-Titre", titre[:120], "-Texte", texte[:230]]
    if rapport:
        cmd += ["-Rapport", rapport]
    try:
        r = subprocess.run(cmd, check=False, timeout=60, capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        j("notification en échec : délai dépassé")
        return False
    if r.returncode != 0:
        j("notification en échec (code %s) : %s" % (r.returncode, (r.stderr or "")[:300]))
        return False
    with io.open(os.path.join(config.dossier_config(), "notifications.log"), "a", encoding="utf-8") as f:
        f.write("%s  %s | %s\n" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), titre, texte))
    return True
