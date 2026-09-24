# -*- coding: utf-8 -*-
"""Installateur de l'outil.

Windows : un double-clic depuis l'Explorateur. Un .pyw plutôt qu'un .bat : le Contrôle
intelligent des applications de Windows 11 bloque les .bat téléchargés (marque
"provient d'Internet"), sans bouton pour passer outre, alors qu'il laisse Python ouvrir
un .pyw. pythonw n'a pas de console : une erreur s'affiche dans une boîte de dialogue,
jamais en silence.

macOS et Linux : lancé par installer.sh, la ligne à coller dans le Terminal donnée sur
le site de l'outil, ou directement avec python3 installer.pyw. Les messages
s'affichent dans le Terminal.

L'outil est copié dans un dossier fixe (plateforme.dossier_installation :
%LOCALAPPDATA%\\Bifurq AIO, ~/Library/Application Support/Bifurq AIO ou
~/.local/share/bifurq-aio), et non lancé depuis le dossier téléchargé : chaque nouveau
téléchargement arrive dans un dossier différent ("... (1)", "... (2)"), qui deviendrait
sinon une installation de plus, vide. Relancer un installateur plus récent met donc
l'outil à jour en gardant ses sites et réglages (config/), et le dossier téléchargé
peut être supprimé.

Étapes : copie du code, reprise des sites d'une installation faite dans un dossier
téléchargé (avant ce dossier fixe), environnement Python (config/venv, sans pip :
aucune dépendance externe), raccourci et analyses planifiées remis sur le dossier fixe,
puis lancement de l'interface, qui s'ouvre dans le navigateur."""
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import traceback
import urllib.request
import venv

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)                  # le code de ce téléchargement, pas celui d'une autre copie
from veille_ia import plateforme  # noqa: E402

DESTINATION = plateforme.dossier_installation()
A_COPIER = ("veille_ia", "scripts_windows", "lancer_veille.pyw", "installer.pyw", "icone.ico", "icone.icns",
            "icone.png", "requirements.txt", "LICENSE", "README.md")
A_NE_PAS_REPRENDRE = ("venv", "serveur.json", "_temp_jeton.json", "installation.log")
TITRE = "Bifurq AIO"
SANS_FENETRE = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def dans_un_terminal():
    """Lancé depuis un Terminal (installer.sh passe --terminal, qui capte parfois la
    sortie) plutôt que par un double-clic ou par le bouton Mettre à jour."""
    return "--terminal" in sys.argv or bool(sys.stdout and sys.stdout.isatty())


def message(texte, erreur=False):
    if plateforme.SYSTEME == "windows":
        import ctypes
        # icône, premier plan et au-dessus des autres fenêtres : le navigateur s'ouvre en même temps
        ctypes.windll.user32.MessageBoxW(None, texte, TITRE, (0x10 if erreur else 0x40) | 0x10000 | 0x40000)
        return
    if sys.stdout:
        print("\n%s\n" % texte, file=sys.stderr if erreur else sys.stdout, flush=True)
    if not dans_un_terminal():
        fenetre(texte, erreur)


def fenetre(texte, erreur=False):
    """Le message dans une fenêtre, sans Terminal : boîte de dialogue sur macOS ; sous
    Linux, zenity (GNOME) ou kdialog (KDE), sinon une notification."""
    if plateforme.SYSTEME == "mac":
        commandes = [["osascript", "-e", "on run argv", "-e", "activate", "-e",
                      'display dialog (item 2 of argv) with title (item 1 of argv) buttons {"OK"} '
                      'default button "OK" with icon %s giving up after 600' % ("stop" if erreur else "note"),
                      "-e", "end run", TITRE, texte]]
    else:
        commandes = [["zenity", "--error" if erreur else "--info", "--title", TITRE, "--width", "460", "--text", texte],
                     ["kdialog", "--title", TITRE, "--error" if erreur else "--msgbox", texte],
                     ["notify-send", "--app-name=" + TITRE, TITRE, texte]]
    for commande in commandes:                   # le premier qui s'affiche
        try:
            if shutil.which(commande[0]) and subprocess.run(commande, capture_output=True, timeout=660).returncode in (0, 1):
                return
        except Exception:
            pass


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
                    return (os.path.isfile(plateforme.python_du_venv(dossier_venv))
                            and os.path.isdir(valeur.strip()))
    except OSError:
        pass
    return False


def commande_interface(dossier_venv, port=None):
    """port : mise à jour lancée depuis l'interface. La nouvelle interface reprend son port
    sans ouvrir d'onglet : la page restée ouverte la retrouve et s'y recharge."""
    commande = [plateforme.python_du_venv(dossier_venv), "-m", "veille_ia.installer.server"]
    if port:
        commande += ["--port", str(port), "--sans-navigateur"]
    return commande


def lancer_interface(destination, dossier_venv, port=None):
    commande = commande_interface(dossier_venv, port)
    if os.name == "nt":
        subprocess.Popen(commande, cwd=destination, close_fds=True)
        return
    # sa propre session : l'interface survit à la fermeture du Terminal ; sa sortie va
    # dans son journal
    with io.open(os.path.join(destination, "config", "serveur.log"), "a", encoding="utf-8") as journal:
        subprocess.Popen(commande, cwd=destination, close_fds=True, start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=journal, stderr=journal)


def adresse_interface(destination, delai=10.0):
    """Adresse de l'interface lancée, pour le Terminal : le navigateur peut ne pas
    s'ouvrir tout seul (ordinateur sans écran, navigateur par défaut absent)."""
    fin = time.time() + delai
    while time.time() < fin:
        try:
            with io.open(os.path.join(destination, "config", "serveur.json"), encoding="utf-8") as f:
                adresse = "http://127.0.0.1:%d/" % json.load(f)["port"]
            urllib.request.urlopen(adresse + "ping", timeout=1).close()
            return adresse
        except Exception:
            time.sleep(0.3)
    return None


def installer(source=ICI, destination=DESTINATION, port=None):
    """Rend le message de fin à afficher, ou None (installateur relancé depuis le dossier
    installé lui-même : simple réparation, rien à annoncer)."""
    depuis_telechargement = not meme_dossier(source, destination)
    mise_a_jour = _a_des_sites(os.path.join(destination, "config"))
    reprise = False
    if depuis_telechargement:
        copier_outil(source, destination)
        arreter_interface(source)                      # ancienne installation dans ce dossier
        reprise = reprendre_configuration(source, destination)
    if plateforme.SYSTEME == "windows":
        retirer_marques_internet(destination)
    dossier_venv = os.path.join(destination, "config", "venv")
    if not environnement_valide(dossier_venv):
        # liens vers le Python de base hors Windows, comme python3 -m venv : une mise à jour
        # mineure de Python ne casse pas l'environnement
        venv.create(dossier_venv, clear=True, with_pip=False, symlinks=os.name != "nt")
    # raccourci, analyses planifiées remises sur ce dossier : par le code installé, avec
    # python.exe sans fenêtre plutôt que pythonw sous Windows, pour recueillir une erreur
    r = subprocess.run([plateforme.python_du_venv(dossier_venv, console=True), "-m", "veille_ia.installation"],
                       cwd=destination, capture_output=True, text=True, timeout=180, creationflags=SANS_FENETRE)
    if r.returncode != 0:
        raise RuntimeError("analyses planifiées non mises en place : %s" % (r.stderr or r.stdout).strip()[-600:])
    lancer_interface(destination, dossier_venv, port)
    if not depuis_telechargement:
        return None
    if mise_a_jour:
        debut = "Bifurq AIO est à jour. Vos sites et réglages sont conservés."
    elif reprise:
        debut = ("Bifurq AIO est installé. Les sites de votre installation "
                 "précédente ont été repris.")
    else:
        debut = "Bifurq AIO est installé."
    rouvrir = re.sub(r"</?b>", "", plateforme.raccourci())
    texte = "%s\n\nL'outil s'ouvre dans votre navigateur. Pour le rouvrir plus tard : %s." % (debut, rouvrir)
    if plateforme.SYSTEME == "windows":
        return texte + ("\n\nVous pouvez supprimer le fichier ZIP et le dossier téléchargés : l'outil n'en a "
                        "plus besoin.")
    adresse = adresse_interface(destination)
    texte += "\nAdresse de l'outil : %s" % adresse if adresse else ""
    if plateforme.SYSTEME == "mac" and ".app/Contents/" in source:
        texte += ("\n\nVous pouvez supprimer l'application Installer Bifurq AIO et le fichier ZIP téléchargés : "
                  "l'outil n'en a plus besoin.")
    return texte


if __name__ == "__main__":
    if sys.version_info < (3, 8):
        message("Cet outil demande Python 3.8 ou plus récent. Installez la dernière version depuis "
                "python.org, puis relancez l'installateur.", erreur=True)
        sys.exit(1)
    # --mise-a-jour PORT : lancé par le bouton Mettre à jour de l'interface, sans message de
    # fin (la page ouverte montre la nouvelle version) ; une erreur s'affiche quand même
    port = None
    if len(sys.argv) > 2 and sys.argv[1] == "--mise-a-jour" and sys.argv[2].isdigit():
        port = int(sys.argv[2])
    try:
        fin = installer(port=port)
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
    if fin and not port:
        message(fin)
