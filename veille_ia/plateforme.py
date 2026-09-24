# -*- coding: utf-8 -*-
"""Ce qui change d'un système à l'autre : dossier d'installation, Python de
l'environnement de l'outil, raccourci pour le rouvrir, analyses planifiées et
notifications. Le reste de l'outil passe par ces fonctions.

Windows : systeme_windows (PowerShell). macOS : systeme_mac (launchd, osascript).
Linux : systeme_linux (systemd ou cron, notify-send)."""
import datetime
import io
import os
import sys

from . import config

NOM = "Bifurq AIO"
SYSTEME = "windows" if os.name == "nt" else ("mac" if sys.platform == "darwin" else "linux")

# pour rouvrir l'outil, en fin de phrase : "Pour revenir ici : ..."
RACCOURCI = {"windows": "le raccourci <b>%s</b> de votre bureau" % NOM,
             "mac": "l'application <b>%s</b>, dans Launchpad ou avec Spotlight" % NOM,
             "linux": "l'application <b>%s</b> du menu des applications" % NOM}

# fin du texte d'une notification : seul Windows ouvre le rapport au clic
APPEL_NOTIFICATION = {"windows": "Cliquez pour voir quoi faire.",
                      "mac": "Ouvrez %s pour voir quoi faire." % NOM,
                      "linux": "Ouvrez %s pour voir quoi faire." % NOM}


def raccourci(systeme=None):
    return RACCOURCI[systeme or SYSTEME]


def appel_notification(systeme=None):
    return APPEL_NOTIFICATION[systeme or SYSTEME]


def dossier_installation(systeme=None):
    """Dossier fixe où installer.pyw copie l'outil, propre à l'utilisateur, sans droits
    d'administrateur."""
    systeme = systeme or SYSTEME
    if systeme == "windows":
        return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local"), NOM)
    if systeme == "mac":
        return os.path.join(os.path.expanduser("~/Library/Application Support"), NOM)
    return os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "bifurq-aio")


def python_du_venv(dossier_venv, console=False, systeme=None):
    """Python de l'environnement de l'outil. Sous Windows, pythonw.exe n'ouvre aucune
    fenêtre ; console=True donne python.exe, pour recueillir la sortie d'une commande."""
    if (systeme or SYSTEME) == "windows":
        return os.path.join(dossier_venv, "Scripts", "python.exe" if console else "pythonw.exe")
    return os.path.join(dossier_venv, "bin", "python3")


def python_de_l_outil(console=False):
    return python_du_venv(os.path.join(config.racine(), "config", "venv"), console)


def lanceur_des_analyses():
    return os.path.join(config.racine(), "lancer_veille.pyw")


def processus_actif(pid):
    """Le processus pid tourne-t-il encore ? Dans le doute, oui : un verrou ne doit pas
    être volé à une analyse en cours."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if SYSTEME == "windows":
        # sans os.kill : sous Windows, os.kill termine le processus au lieu de le sonder
        try:
            import ctypes
            k = ctypes.windll.kernel32
            h = k.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            code = ctypes.c_ulong()
            ok = k.GetExitCodeProcess(h, ctypes.byref(code))
            k.CloseHandle(h)
            return bool(ok) and code.value == 259          # STILL_ACTIVE
        except Exception:
            return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True                                        # existe, mais appartient à un autre compte
    return True


def _systeme():
    if SYSTEME == "windows":
        from . import systeme_windows as module
    elif SYSTEME == "mac":
        from . import systeme_mac as module
    else:
        from . import systeme_linux as module
    return module


def heure_valide(heure_fixe):
    """(heure, minute) de "09:15", ou ValueError."""
    t = datetime.datetime.strptime((heure_fixe or "").strip(), "%H:%M")
    return t.hour, t.minute


def planifier(au_demarrage, actif_heure_fixe, heure_fixe):
    """Analyses automatiques : à l'ouverture de session (deux minutes après, le temps que
    le réseau soit prêt), chaque jour à heure_fixe, ou les deux."""
    if not au_demarrage and not actif_heure_fixe:
        raise ValueError("au moins un déclenchement (démarrage ou heure fixe) doit être actif")
    heure_valide(heure_fixe)
    return _systeme().planifier(au_demarrage, actif_heure_fixe, heure_fixe)


def retirer_planification():
    return _systeme().retirer_planification()


def creer_raccourci():
    return _systeme().creer_raccourci()


CERTIFICATS_MACOS = "/etc/ssl/cert.pem"


def preparer_certificats(systeme=None):
    """Le Python de python.org pour macOS ne lit pas les certificats du système tant que
    son script Install Certificates n'a pas été lancé : toute connexion HTTPS échoue
    (Google, plans de site, mises à jour). macOS fournit les mêmes certificats dans
    /etc/ssl/cert.pem. Rend le fichier retenu, ou None si rien n'est à changer."""
    if (systeme or SYSTEME) != "mac" or os.environ.get("SSL_CERT_FILE"):
        return None
    import ssl
    chemins = ssl.get_default_verify_paths()
    if (chemins.cafile and os.path.isfile(chemins.cafile)) or (chemins.capath and os.path.isdir(chemins.capath)
                                                               and os.listdir(chemins.capath)):
        return None
    if not os.path.isfile(CERTIFICATS_MACOS):
        return None
    os.environ["SSL_CERT_FILE"] = CERTIFICATS_MACOS         # lu à chaque connexion HTTPS
    return CERTIFICATS_MACOS


def notifier(titre, texte, rapport="", journal=None):
    """Notification du système, et son historique texte en secours : une notification
    effacée disparaît, notifications.log reste lisible après coup. Rend True si la
    notification est partie."""
    j = journal or (lambda m: None)
    try:
        _systeme().notifier(titre[:120], texte[:230], rapport)
    except Exception as ex:
        j("notification en échec : %s" % str(ex)[:300])
        return False
    with io.open(os.path.join(config.dossier_config(), "notifications.log"), "a", encoding="utf-8") as f:
        f.write("%s  %s | %s\n" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), titre, texte))
    return True
