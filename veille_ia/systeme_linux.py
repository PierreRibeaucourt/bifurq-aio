# -*- coding: utf-8 -*-
"""Linux : lanceur dans le menu des applications (fichier .desktop), analyses
planifiées par systemd (minuteries de l'utilisateur) ou, sans systemd, par cron,
notifications par notify-send.

Deux minuteries systemd pour un même service : "demarrage" (deux minutes après
l'ouverture de session, le temps que le réseau soit prêt), seulement activée pour la
prochaine session, et "quotidien" (Persistent : rattrapée au démarrage suivant si
l'ordinateur était éteint), lancée tout de suite. Avec cron, les notifications ne
s'affichent pas (cron ne connaît pas la session graphique) : elles restent dans
config/notifications.log."""
import os
import shlex
import shutil
import subprocess

from . import config, plateforme

NOM = "bifurq-aio"
MINUTERIES = ("demarrage", "quotidien")
MARQUE_CRON = "# " + NOM


def _xdg(variable, defaut):
    return os.environ.get(variable) or os.path.expanduser(defaut)


def dossier_unites():
    return os.path.join(_xdg("XDG_CONFIG_HOME", "~/.config"), "systemd", "user")


def chemin_lanceur():
    return os.path.join(_xdg("XDG_DATA_HOME", "~/.local/share"), "applications", NOM + ".desktop")


def _executer(commande, entree=None):
    return subprocess.run(commande, input=entree, capture_output=True, text=True, timeout=30)


def _systemctl(*args):
    return _executer(["systemctl", "--user"] + list(args))


def systemd_disponible():
    """systemd gère-t-il la session de l'utilisateur ? Non sur quelques distributions et
    dans les conteneurs."""
    if not shutil.which("systemctl"):
        return False
    try:
        return _systemctl("show-environment").returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _unite(texte):
    return texte.replace("%", "%%")                  # % introduit les variables de systemd


def _commande_systemd():
    return " ".join('"%s"' % c.replace("\\", "\\\\").replace('"', '\\"')
                    for c in (plateforme.python_de_l_outil(), plateforme.lanceur_des_analyses()))


def unites(au_demarrage, actif_heure_fixe, heure_fixe):
    """{nom de fichier: contenu} des unités systemd à écrire."""
    fichiers = {NOM + ".service": _unite(
        "[Unit]\nDescription=Bifurq AIO : analyse des adresses inventées par l'IA de Google\n\n"
        "[Service]\nType=oneshot\nWorkingDirectory=%s\nExecStart=%s\nTimeoutStartSec=3h\n"
        % (config.racine(), _commande_systemd()))}
    if au_demarrage:
        fichiers["%s-demarrage.timer" % NOM] = (
            "[Unit]\nDescription=Bifurq AIO : analyse à l'ouverture de session\n\n"
            "[Timer]\nOnStartupSec=2min\nUnit=%s.service\n\n[Install]\nWantedBy=timers.target\n" % NOM)
    if actif_heure_fixe:
        heure, minute = plateforme.heure_valide(heure_fixe)
        fichiers["%s-quotidien.timer" % NOM] = (
            "[Unit]\nDescription=Bifurq AIO : analyse quotidienne\n\n"
            "[Timer]\nOnCalendar=*-*-* %02d:%02d:00\nPersistent=true\nUnit=%s.service\n\n"
            "[Install]\nWantedBy=timers.target\n" % (heure, minute, NOM))
    return fichiers


def lignes_cron(au_demarrage, actif_heure_fixe, heure_fixe):
    commande = "cd %s && %s %s" % tuple(shlex.quote(c).replace("%", "\\%") for c in (
        config.racine(), plateforme.python_de_l_outil(), plateforme.lanceur_des_analyses()))
    lignes = []
    if au_demarrage:
        lignes.append("@reboot sleep 120 && %s %s" % (commande, MARQUE_CRON))
    if actif_heure_fixe:
        heure, minute = plateforme.heure_valide(heure_fixe)
        lignes.append("%d %d * * * %s %s" % (minute, heure, commande, MARQUE_CRON))
    return lignes


def _crontab_sans_l_outil():
    r = _executer(["crontab", "-l"])                 # sans crontab : code 1, "no crontab for ..."
    lignes = r.stdout.splitlines() if r.returncode == 0 else []
    return [l for l in lignes if not l.rstrip().endswith(MARQUE_CRON)]


def _ecrire_crontab(lignes):
    r = _executer(["crontab", "-"], "\n".join(lignes) + "\n" if lignes else "")
    if r.returncode != 0:
        raise RuntimeError("crontab refusée : %s" % (r.stderr or r.stdout).strip()[:300])


def _retirer_systemd():
    for nom in MINUTERIES:
        _systemctl("disable", "--now", "%s-%s.timer" % (NOM, nom))
    for f in [NOM + ".service"] + ["%s-%s.timer" % (NOM, nom) for nom in MINUTERIES]:
        try:
            os.remove(os.path.join(dossier_unites(), f))
        except FileNotFoundError:
            pass
    _systemctl("daemon-reload")


def retirer_planification():
    if systemd_disponible():
        _retirer_systemd()
    if shutil.which("crontab"):
        avant = _executer(["crontab", "-l"])
        if avant.returncode == 0 and MARQUE_CRON in avant.stdout:
            _ecrire_crontab(_crontab_sans_l_outil())


def planifier(au_demarrage, actif_heure_fixe, heure_fixe):
    retirer_planification()
    if systemd_disponible():
        os.makedirs(dossier_unites(), exist_ok=True)
        for nom, contenu in unites(au_demarrage, actif_heure_fixe, heure_fixe).items():
            with open(os.path.join(dossier_unites(), nom), "w", encoding="utf-8") as f:
                f.write(contenu)
        _systemctl("daemon-reload")
        commandes = []
        if au_demarrage:
            commandes.append(["enable", "%s-demarrage.timer" % NOM])
        if actif_heure_fixe:
            commandes.append(["enable", "--now", "%s-quotidien.timer" % NOM])
        for args in commandes:
            r = _systemctl(*args)
            if r.returncode != 0:
                raise RuntimeError("systemd refuse la minuterie : %s" % (r.stderr or r.stdout).strip()[:300])
        return
    if shutil.which("crontab"):
        _ecrire_crontab(_crontab_sans_l_outil() + lignes_cron(au_demarrage, actif_heure_fixe, heure_fixe))
        return
    raise RuntimeError("ni systemd ni cron sur cet ordinateur : les analyses automatiques ne peuvent pas "
                       "être programmées")


def _champ_desktop(texte):
    """Argument entre guillemets de la clé Exec : les échappements de la clé, puis ceux
    des chaînes du fichier (d'où les barres obliques doublées), et %% pour un %."""
    texte = texte.replace("\\", "\\" * 4)
    for car in ('"', "`", "$"):
        texte = texte.replace(car, "\\\\" + car)
    return '"%s"' % texte.replace("%", "%%")


def lanceur():
    """Contenu du fichier .desktop (spécification freedesktop.org)."""
    racine = config.racine()
    return ("[Desktop Entry]\nType=Application\nName=%s\n"
            "Comment=Veille des adresses inventées par l'IA de Google\n"
            "Exec=%s -m veille_ia.installer.server\nPath=%s\nIcon=%s\n"
            "Terminal=false\nCategories=Network;\nStartupNotify=false\n"
            % (plateforme.NOM, _champ_desktop(plateforme.python_de_l_outil()), racine,
               os.path.join(racine, "icone.png")))


def creer_raccourci():
    chemin = chemin_lanceur()
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(lanceur())
    if shutil.which("update-desktop-database"):      # confort : le menu se met à jour tout de suite
        _executer(["update-desktop-database", os.path.dirname(chemin)])


def notifier(titre, texte, rapport=""):
    if not shutil.which("notify-send"):
        raise RuntimeError("notify-send absent (paquet libnotify-bin ou libnotify)")
    commande = ["notify-send", "--app-name=" + plateforme.NOM]
    icone = os.path.join(config.racine(), "icone.png")
    if os.path.isfile(icone):
        commande.append("--icon=" + icone)
    r = _executer(commande + [titre, texte])
    if r.returncode != 0:
        raise RuntimeError("notify-send : %s" % (r.stderr or r.stdout).strip()[:300])
