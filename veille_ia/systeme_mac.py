# -*- coding: utf-8 -*-
"""macOS : application Bifurq AIO dans ~/Applications (Launchpad, Spotlight), analyses
planifiées par launchd, notifications par osascript.

L'application et les agents launchd sont écrits par l'outil lui-même, sur l'ordinateur
de l'utilisateur : ils ne portent pas la marque de quarantaine des téléchargements, et
Gatekeeper les laisse s'ouvrir sans signature Apple.

Deux agents, parce que launchd ne sait pas retarder un lancement à l'ouverture de
session : "demarrage" (RunAtLoad, l'analyse attend elle-même deux minutes que le réseau
soit prêt), seulement déposé dans ~/Library/LaunchAgents pour la prochaine session, et
"quotidien" (StartCalendarInterval, rattrapé au réveil si l'ordinateur dormait), chargé
tout de suite."""
import os
import plistlib
import shlex
import shutil
import subprocess

from . import __version__, config, plateforme

ETIQUETTE = "io.github.pierreribeaucourt.bifurq-aio"
AGENTS = ("demarrage", "quotidien")
ATTENTE_DEMARRAGE = 120


def dossier_agents():
    return os.path.expanduser("~/Library/LaunchAgents")


def chemin_agent(nom):
    return os.path.join(dossier_agents(), "%s.%s.plist" % (ETIQUETTE, nom))


def chemin_application():
    return os.path.expanduser("~/Applications/%s.app" % plateforme.NOM)


def _domaine():
    return "gui/%d" % os.getuid()


def _launchctl(*args):
    return subprocess.run(["launchctl"] + list(args), capture_output=True, text=True, timeout=30)


def definition_agent(nom, au_demarrage, heure_fixe=None):
    """Le contenu du fichier .plist d'un agent, en dict."""
    commande = [plateforme.python_de_l_outil(), plateforme.lanceur_des_analyses()]
    agent = {"Label": "%s.%s" % (ETIQUETTE, nom), "ProgramArguments": commande,
             "WorkingDirectory": config.racine()}
    if au_demarrage:
        agent["ProgramArguments"] = commande + ["--attendre", str(ATTENTE_DEMARRAGE)]
        agent["RunAtLoad"] = True
    else:
        heure, minute = plateforme.heure_valide(heure_fixe)
        agent["StartCalendarInterval"] = {"Hour": heure, "Minute": minute}
    return agent


def retirer_planification():
    for nom in AGENTS:
        _launchctl("bootout", "%s/%s.%s" % (_domaine(), ETIQUETTE, nom))     # absent : sans effet
        try:
            os.remove(chemin_agent(nom))
        except FileNotFoundError:
            pass


def planifier(au_demarrage, actif_heure_fixe, heure_fixe):
    retirer_planification()
    os.makedirs(dossier_agents(), exist_ok=True)
    if au_demarrage:
        with open(chemin_agent("demarrage"), "wb") as f:
            plistlib.dump(definition_agent("demarrage", True), f)
    if actif_heure_fixe:
        chemin = chemin_agent("quotidien")
        with open(chemin, "wb") as f:
            plistlib.dump(definition_agent("quotidien", False, heure_fixe), f)
        r = _launchctl("bootstrap", _domaine(), chemin)
        if r.returncode != 0:
            raise RuntimeError("analyse quotidienne refusée par launchd : %s" % (r.stderr or r.stdout).strip()[:300])


def script_application():
    """Lance l'interface détachée puis rend la main : un second clic sur l'application
    relance ce script, qui rouvre alors la page de l'interface déjà en route."""
    racine = config.racine()
    return ("#!/bin/sh\n"
            "cd %s || exit 1\n"
            "nohup %s -m veille_ia.installer.server >> config/serveur.log 2>&1 &\n"
            % (shlex.quote(racine), shlex.quote(plateforme.python_de_l_outil())))


def creer_raccourci():
    app = chemin_application()
    contenu = os.path.join(app, "Contents")
    shutil.rmtree(app, ignore_errors=True)
    os.makedirs(os.path.join(contenu, "MacOS"))
    os.makedirs(os.path.join(contenu, "Resources"))
    infos = {"CFBundleName": plateforme.NOM, "CFBundleDisplayName": plateforme.NOM,
             "CFBundleIdentifier": ETIQUETTE, "CFBundleExecutable": "bifurq-aio",
             "CFBundlePackageType": "APPL", "CFBundleShortVersionString": __version__,
             "CFBundleVersion": __version__, "CFBundleIconFile": "icone",
             "LSUIElement": True}                  # pas d'icône dans le Dock : tout se passe dans le navigateur
    with open(os.path.join(contenu, "Info.plist"), "wb") as f:
        plistlib.dump(infos, f)
    executable = os.path.join(contenu, "MacOS", "bifurq-aio")
    with open(executable, "w", encoding="utf-8") as f:
        f.write(script_application())
    os.chmod(executable, 0o755)
    icone = os.path.join(config.racine(), "icone.icns")
    if os.path.isfile(icone):
        shutil.copyfile(icone, os.path.join(contenu, "Resources", "icone.icns"))
    # enregistrée tout de suite auprès de Launchpad et Spotlight (confort seulement)
    lsregister = ("/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework"
                  "/Support/lsregister")
    if os.path.isfile(lsregister):
        subprocess.run([lsregister, "-f", app], capture_output=True, timeout=30)


def notifier(titre, texte, rapport=""):
    """Centre de notifications. Les textes passent en arguments du script : aucun
    échappement AppleScript à gérer."""
    script = ["on run argv", "display notification (item 2 of argv) with title (item 1 of argv)", "end run"]
    commande = ["osascript"]
    for ligne in script:
        commande += ["-e", ligne]
    r = subprocess.run(commande + [titre, texte], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError("osascript : %s" % (r.stderr or r.stdout).strip()[:300])
