# -*- coding: utf-8 -*-
"""macOS : application Bifurq AIO dans ~/Applications (Launchpad, Spotlight), analyses
planifiées par launchd, notifications affichées par l'application.

L'application est une applet AppleScript (osacompile, présent sur tout Mac). macOS
attribue les notifications à l'application qui les affiche, et la relance quand on
clique dessus : un "display notification" lancé par osascript est attribué à l'Éditeur
de script, et un clic ne mène pas à l'outil (relevé du 28.09.2026). L'outil dépose donc
chaque notification dans config/notifications_mac et lance l'application, qui l'affiche
puis se ferme ; lancée sans notification en attente (clic sur une notification,
Launchpad, Spotlight), elle ouvre l'interface.

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
import time

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


def dossier_notifications():
    return os.path.join(config.dossier_config(), "notifications_mac")


def _chaine(s):
    """Une chaîne AppleScript entre guillemets."""
    return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"')


def script_applet():
    """L'AppleScript de l'application : affiche les notifications en attente (un fichier
    chacune : titre, puis texte), sinon lance l'interface, détachée, qui rouvre la page si
    elle tourne déjà. Aucune erreur n'y ouvre de fenêtre : l'outil attend la fin de
    l'application pour savoir si la notification est partie."""
    # "cd X; nohup ... &" et surtout pas "cd X && nohup ... &" : là, toute la liste passerait en
    # arrière-plan dans un sous-shell qui garde ouverte la sortie qu'attend "do shell script", et
    # l'application ne se fermerait jamais (relevé du 28.09.2026 sur le Mac de l'intégration continue)
    lancer = "cd %s || exit 1; nohup %s -m veille_ia.installer.server >> config/serveur.log 2>&1 &" % (
        shlex.quote(config.racine()), shlex.quote(plateforme.python_de_l_outil()))
    return "\n".join([
        "on run",
        "set attente to " + _chaine(dossier_notifications()),
        "set affichees to 0",
        "try",
        "set noms to paragraphs of (do shell script \"ls -1 \" & quoted form of attente & \" 2>/dev/null; true\")",
        "on error",
        "set noms to {}",
        "end try",
        "repeat with element in noms",
        "set nom to (contents of element) as text",
        "if nom is not \"\" then",
        "try",
        "set chemin to attente & \"/\" & nom",
        "set lignes to paragraphs of (do shell script \"cat \" & quoted form of chemin)",
        "do shell script \"rm -f \" & quoted form of chemin",
        "if (count of lignes) > 1 then",
        "display notification (item 2 of lignes) with title (item 1 of lignes)",
        "set affichees to affichees + 1",
        "end if",
        "end try",
        "end if",
        "end repeat",
        "if affichees is 0 then",
        "try",
        "do shell script " + _chaine(lancer),
        "end try",
        "end if",
        "end run",
    ])


def script_application():
    """Application de secours, si osacompile échoue : lance l'interface détachée puis rend
    la main. Un second clic sur l'application relance ce script, qui rouvre alors la page de
    l'interface déjà en route."""
    racine = config.racine()
    return ("#!/bin/sh\n"
            "cd %s || exit 1\n"
            "nohup %s -m veille_ia.installer.server >> config/serveur.log 2>&1 &\n"
            % (shlex.quote(racine), shlex.quote(plateforme.python_de_l_outil())))


def _infos_application():
    return {"CFBundleName": plateforme.NOM, "CFBundleDisplayName": plateforme.NOM,
            "CFBundleIdentifier": ETIQUETTE, "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "LSUIElement": True}                   # pas d'icône dans le Dock : tout se passe dans le navigateur


def _creer_applet(app):
    """L'applet AppleScript, à notre nom et à notre icône, signée à nouveau sur place (sans
    signature valide, un Mac à puce Apple refuse de la lancer). Rend False en cas d'échec."""
    if not shutil.which("osacompile"):
        return False
    commande = ["osacompile", "-o", app]
    for ligne in script_applet().splitlines():
        commande += ["-e", ligne]
    if subprocess.run(commande, capture_output=True, timeout=60).returncode != 0:
        return False
    contenu = os.path.join(app, "Contents")
    with open(os.path.join(contenu, "Info.plist"), "rb") as f:
        infos = plistlib.load(f)
    infos.update(_infos_application())
    # icône : le catalogue Assets.car des applets récentes passerait avant le fichier .icns
    infos.pop("CFBundleIconName", None)
    try:
        os.remove(os.path.join(contenu, "Resources", "Assets.car"))
    except FileNotFoundError:
        pass
    with open(os.path.join(contenu, "Info.plist"), "wb") as f:
        plistlib.dump(infos, f)
    icone = os.path.join(config.racine(), "icone.icns")
    if os.path.isfile(icone):
        shutil.copyfile(icone, os.path.join(contenu, "Resources", "%s.icns" % infos.get("CFBundleIconFile", "applet")))
    signer = ["codesign", "--force", "--sign", "-", app]
    return (subprocess.run(signer, capture_output=True, timeout=60).returncode == 0
            and subprocess.run(["codesign", "--verify", app], capture_output=True, timeout=60).returncode == 0)


def creer_raccourci():
    app = chemin_application()
    contenu = os.path.join(app, "Contents")
    shutil.rmtree(app, ignore_errors=True)
    os.makedirs(os.path.dirname(app), exist_ok=True)
    if _creer_applet(app):
        _enregistrer(app)
        return
    shutil.rmtree(app, ignore_errors=True)
    os.makedirs(os.path.join(contenu, "MacOS"))
    os.makedirs(os.path.join(contenu, "Resources"))
    infos = dict(_infos_application(), CFBundleExecutable="bifurq-aio", CFBundlePackageType="APPL",
                 CFBundleIconFile="icone")
    with open(os.path.join(contenu, "Info.plist"), "wb") as f:
        plistlib.dump(infos, f)
    executable = os.path.join(contenu, "MacOS", "bifurq-aio")
    with open(executable, "w", encoding="utf-8") as f:
        f.write(script_application())
    os.chmod(executable, 0o755)
    icone = os.path.join(config.racine(), "icone.icns")
    if os.path.isfile(icone):
        shutil.copyfile(icone, os.path.join(contenu, "Resources", "icone.icns"))
    _enregistrer(app)


def _enregistrer(app):
    # enregistrée tout de suite auprès de Launchpad et Spotlight (confort seulement)
    lsregister = ("/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework"
                  "/Support/lsregister")
    if os.path.isfile(lsregister):
        subprocess.run([lsregister, "-f", app], capture_output=True, timeout=30)


def _une_ligne(s):
    return " ".join(str(s).split())


def notifier(titre, texte, rapport=""):
    """Centre de notifications, par l'application (un clic dessus ouvre l'outil) ; à défaut
    (application absente ou d'avant la version 0.5.7), par osascript, sans clic possible."""
    app = chemin_application()
    if os.path.isfile(os.path.join(app, "Contents", "MacOS", "applet")):
        dossier = dossier_notifications()
        os.makedirs(dossier, exist_ok=True)
        fichier = os.path.join(dossier, "%d-%d.txt" % (time.time_ns(), os.getpid()))
        with open(fichier, "w", encoding="utf-8") as f:
            f.write("%s\n%s\n" % (_une_ligne(titre), _une_ligne(texte)))
        try:
            # -W : attendre que l'application se ferme, notification affichée
            subprocess.run(["open", "-g", "-W", "-a", app], capture_output=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            pass
        if not os.path.exists(fichier):
            return
        os.remove(fichier)                         # pas prise par l'application : osascript
    _notifier_par_osascript(titre, texte)


def _notifier_par_osascript(titre, texte):
    """Les textes passent en arguments du script : aucun échappement AppleScript à gérer."""
    script = ["on run argv", "display notification (item 2 of argv) with title (item 1 of argv)", "end run"]
    commande = ["osascript"]
    for ligne in script:
        commande += ["-e", ligne]
    r = subprocess.run(commande + [titre, texte], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError("osascript : %s" % (r.stderr or r.stdout).strip()[:300])
