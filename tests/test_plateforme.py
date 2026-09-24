import os
import plistlib
import shutil
import subprocess
import sys

import pytest

from veille_ia import config, plateforme, systeme_linux, systeme_mac

RACINE_AVEC_ESPACE = "Mon dossier l'outil"


@pytest.fixture(autouse=True)
def _racine_isolee(tmp_path, monkeypatch):
    racine = tmp_path / RACINE_AVEC_ESPACE
    racine.mkdir()
    monkeypatch.setattr(config, "racine", lambda: str(racine))
    return racine


def _resultat(code=0, sortie=""):
    return subprocess.CompletedProcess([], code, sortie, "")


# --- commun ---------------------------------------------------------------------------------------
def test_python_de_l_environnement_selon_le_systeme():
    assert plateforme.python_du_venv("V", systeme="windows") == os.path.join("V", "Scripts", "pythonw.exe")
    assert plateforme.python_du_venv("V", console=True, systeme="windows") == os.path.join("V", "Scripts",
                                                                                           "python.exe")
    assert plateforme.python_du_venv("V", systeme="mac") == os.path.join("V", "bin", "python3")
    assert plateforme.python_du_venv("V", systeme="linux") == os.path.join("V", "bin", "python3")


def test_chaque_systeme_dit_comment_rouvrir_l_outil():
    assert "bureau" in plateforme.raccourci("windows")
    assert "Launchpad" in plateforme.raccourci("mac")
    assert "menu des applications" in plateforme.raccourci("linux")
    assert plateforme.appel_notification("windows") == "Cliquez pour voir quoi faire."
    assert plateforme.appel_notification("mac") == "Ouvrez Bifurq AIO pour voir quoi faire."


def test_processus_actif():
    assert plateforme.processus_actif(os.getpid())
    fini = subprocess.Popen([sys.executable, "-c", "pass"])
    fini.wait()
    assert not plateforme.processus_actif(fini.pid)
    assert not plateforme.processus_actif(0) and not plateforme.processus_actif(None)


def test_heure_fixe_verifiee_avant_toute_planification():
    assert plateforme.heure_valide("08:05") == (8, 5)
    for mauvaise in ("", "25:00", "8h", "09:15; rm -rf ~"):
        with pytest.raises(ValueError):
            plateforme.planifier(False, True, mauvaise)
    with pytest.raises(ValueError):
        plateforme.planifier(False, False, "09:15")


def test_notification_gardee_dans_l_historique_ou_echec_journalise(monkeypatch):
    class Systeme:
        def notifier(self, titre, texte, rapport):
            if titre == "panne":
                raise RuntimeError("notify-send absent")
    monkeypatch.setattr(plateforme, "_systeme", lambda: Systeme())
    journal = []
    assert plateforme.notifier("Titre", "Texte", "rapport.html", journal.append)
    assert "Titre | Texte" in open(os.path.join(config.dossier_config(), "notifications.log"), encoding="utf-8").read()
    assert not plateforme.notifier("panne", "Texte", "", journal.append)
    assert journal == ["notification en échec : notify-send absent"]


# --- macOS ----------------------------------------------------------------------------------------
@pytest.fixture
def mac(tmp_path, monkeypatch):
    appels = []
    monkeypatch.setattr(systeme_mac, "dossier_agents", lambda: str(tmp_path / "LaunchAgents"))
    monkeypatch.setattr(systeme_mac, "chemin_application", lambda: str(tmp_path / "Applications" / "Bifurq AIO.app"))
    monkeypatch.setattr(systeme_mac, "_domaine", lambda: "gui/501")
    monkeypatch.setattr(systeme_mac, "_launchctl", lambda *args: appels.append(list(args)) or _resultat())
    monkeypatch.setattr(plateforme, "SYSTEME", "mac")
    return appels


def _plist(chemin):
    with open(chemin, "rb") as f:
        return plistlib.load(f)


def test_mac_analyse_au_demarrage_apres_deux_minutes_et_chaque_jour(mac, _racine_isolee):
    plateforme.planifier(True, True, "08:30")
    demarrage = _plist(systeme_mac.chemin_agent("demarrage"))
    python = os.path.join(str(_racine_isolee), "config", "venv", "bin", "python3")
    lanceur = os.path.join(str(_racine_isolee), "lancer_veille.pyw")
    assert demarrage["ProgramArguments"] == [python, lanceur, "--attendre", "120"]
    assert demarrage["RunAtLoad"] is True and demarrage["WorkingDirectory"] == str(_racine_isolee)
    quotidien = _plist(systeme_mac.chemin_agent("quotidien"))
    assert quotidien["ProgramArguments"] == [python, lanceur]
    assert quotidien["StartCalendarInterval"] == {"Hour": 8, "Minute": 30} and "RunAtLoad" not in quotidien
    # seul l'agent quotidien est chargé tout de suite : pas d'analyse surprise à l'installation
    assert ["bootstrap", "gui/501", systeme_mac.chemin_agent("quotidien")] in mac
    assert not any(a[0] == "bootstrap" and a[2].endswith("demarrage.plist") for a in mac)


def test_mac_changer_de_reglage_retire_l_ancien_agent(mac):
    plateforme.planifier(True, True, "08:30")
    mac.clear()
    plateforme.planifier(True, False, "08:30")
    assert ["bootout", "gui/501/io.github.pierreribeaucourt.bifurq-aio.quotidien"] in mac
    assert os.path.exists(systeme_mac.chemin_agent("demarrage"))
    assert not os.path.exists(systeme_mac.chemin_agent("quotidien"))
    plateforme.retirer_planification()
    assert not os.listdir(systeme_mac.dossier_agents())


def test_mac_refus_de_launchd_fait_echouer_la_planification(mac, monkeypatch):
    monkeypatch.setattr(systeme_mac, "_launchctl",
                        lambda *args: _resultat(5 if args[0] == "bootstrap" else 0, "Bootstrap failed: 5"))
    with pytest.raises(RuntimeError, match="launchd"):
        plateforme.planifier(False, True, "08:30")


def test_mac_application_qui_lance_l_interface(mac, _racine_isolee):
    plateforme.creer_raccourci()
    app = systeme_mac.chemin_application()
    infos = _plist(os.path.join(app, "Contents", "Info.plist"))
    assert infos["CFBundleExecutable"] == "bifurq-aio" and infos["LSUIElement"] is True
    executable = os.path.join(app, "Contents", "MacOS", "bifurq-aio")
    script = open(executable, encoding="utf-8").read()
    assert script.startswith("#!/bin/sh\n")
    assert "cd '%s' || exit" % str(_racine_isolee).replace("'", "'\"'\"'") in script
    assert "-m veille_ia.installer.server >> config/serveur.log 2>&1 &" in script
    if os.name != "nt":
        assert os.access(executable, os.X_OK)
        assert subprocess.run(["sh", "-n", executable]).returncode == 0


# --- Linux ----------------------------------------------------------------------------------------
@pytest.fixture
def linux(tmp_path, monkeypatch):
    appels = []
    monkeypatch.setattr(systeme_linux, "dossier_unites", lambda: str(tmp_path / "systemd"))
    monkeypatch.setattr(systeme_linux, "chemin_lanceur", lambda: str(tmp_path / "applications" / "bifurq-aio.desktop"))
    monkeypatch.setattr(systeme_linux, "_systemctl", lambda *args: appels.append(list(args)) or _resultat())
    monkeypatch.setattr(plateforme, "SYSTEME", "linux")
    return appels


@pytest.mark.skipif(os.name == "nt", reason="chemins POSIX dans les fichiers produits")
def test_linux_minuteries_systemd(linux, monkeypatch, _racine_isolee):
    monkeypatch.setattr(systeme_linux, "systemd_disponible", lambda: True)
    plateforme.planifier(True, True, "07:05")
    dossier = systeme_linux.dossier_unites()
    service = open(os.path.join(dossier, "bifurq-aio.service"), encoding="utf-8").read()
    assert "ExecStart=\"%s\" \"%s\"" % (os.path.join(str(_racine_isolee), "config", "venv", "bin", "python3"),
                                        os.path.join(str(_racine_isolee), "lancer_veille.pyw")) in service
    assert "WorkingDirectory=%s\n" % _racine_isolee in service and "Type=oneshot" in service
    assert "OnStartupSec=2min" in open(os.path.join(dossier, "bifurq-aio-demarrage.timer"), encoding="utf-8").read()
    quotidien = open(os.path.join(dossier, "bifurq-aio-quotidien.timer"), encoding="utf-8").read()
    assert "OnCalendar=*-*-* 07:05:00" in quotidien and "Persistent=true" in quotidien
    # la minuterie du démarrage attend la prochaine session ; la quotidienne part tout de suite
    assert ["enable", "bifurq-aio-demarrage.timer"] in linux
    assert ["enable", "--now", "bifurq-aio-quotidien.timer"] in linux


def test_linux_retrait_des_minuteries(linux, monkeypatch):
    monkeypatch.setattr(systeme_linux, "systemd_disponible", lambda: True)
    monkeypatch.setattr(systeme_linux.shutil, "which", lambda nom: None)
    plateforme.planifier(True, True, "07:05")
    plateforme.retirer_planification()
    assert ["disable", "--now", "bifurq-aio-quotidien.timer"] in linux
    assert not os.listdir(systeme_linux.dossier_unites())


def test_linux_sans_systemd_cron_garde_les_autres_lignes(linux, monkeypatch, _racine_isolee):
    monkeypatch.setattr(systeme_linux, "systemd_disponible", lambda: False)
    monkeypatch.setattr(systeme_linux.shutil, "which", lambda nom: "/usr/bin/" + nom if nom == "crontab" else None)
    crontab = {"texte": "MAILTO=moi\n0 3 * * * sauvegarde\n"}

    def executer(commande, entree=None):
        if commande == ["crontab", "-l"]:
            return _resultat(0, crontab["texte"])
        crontab["texte"] = entree
        return _resultat()
    monkeypatch.setattr(systeme_linux, "_executer", executer)
    plateforme.planifier(True, True, "07:05")
    plateforme.planifier(False, True, "21:40")               # nouveau réglage : les anciennes lignes partent
    lignes = crontab["texte"].splitlines()
    assert lignes[:2] == ["MAILTO=moi", "0 3 * * * sauvegarde"]
    assert len(lignes) == 3 and lignes[2].startswith("40 21 * * * cd '%s' && " % str(_racine_isolee).replace(
        "'", "'\"'\"'")) and lignes[2].endswith(" # bifurq-aio")
    plateforme.retirer_planification()
    assert crontab["texte"].splitlines() == ["MAILTO=moi", "0 3 * * * sauvegarde"]


def test_linux_ni_systemd_ni_cron(linux, monkeypatch):
    monkeypatch.setattr(systeme_linux, "systemd_disponible", lambda: False)
    monkeypatch.setattr(systeme_linux.shutil, "which", lambda nom: None)
    with pytest.raises(RuntimeError, match="ni systemd ni cron"):
        plateforme.planifier(True, False, "09:15")


@pytest.mark.skipif(os.name == "nt", reason="chemins POSIX dans les fichiers produits")
def test_linux_lanceur_du_menu_des_applications(linux, _racine_isolee):
    plateforme.creer_raccourci()
    contenu = open(systeme_linux.chemin_lanceur(), encoding="utf-8").read()
    python = os.path.join(str(_racine_isolee), "config", "venv", "bin", "python3")
    assert 'Exec="%s" -m veille_ia.installer.server\n' % python in contenu
    assert "Path=%s\n" % _racine_isolee in contenu and "Terminal=false" in contenu
    if shutil.which("desktop-file-validate"):
        r = subprocess.run(["desktop-file-validate", systeme_linux.chemin_lanceur()], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr


def test_linux_caracteres_speciaux_echappes_dans_le_lanceur():
    assert systeme_linux._champ_desktop('/a b/$x"`\\100%') == '"/a b/\\\\$x\\\\"\\\\`\\\\\\\\100%%"'
