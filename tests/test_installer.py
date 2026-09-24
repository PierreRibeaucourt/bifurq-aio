import importlib.util
import os

import pytest

from conftest import RACINE

spec = importlib.util.spec_from_loader(
    "installeur", importlib.machinery.SourceFileLoader("installeur", os.path.join(RACINE, "installer.pyw")))
installeur = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installeur)


def _marquer(chemin):
    with open(chemin + ":Zone.Identifier", "w") as f:
        f.write("[ZoneTransfer]\nZoneId=3\n")


def _marque(chemin):
    return os.path.exists(chemin + ":Zone.Identifier")


@pytest.mark.skipif(os.name != "nt", reason="flux NTFS propres à Windows")
def test_retire_la_marque_internet_sauf_dans_config(tmp_path):
    racine = str(tmp_path)
    for rel in ("installer.pyw", os.path.join("scripts_windows", "notifier.ps1"), os.path.join("config", "sites.json")):
        chemin = os.path.join(racine, rel)
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        open(chemin, "w").close()
        _marquer(chemin)
    installeur.retirer_marques_internet(racine)
    assert not _marque(os.path.join(racine, "installer.pyw"))
    assert not _marque(os.path.join(racine, "scripts_windows", "notifier.ps1"))
    assert _marque(os.path.join(racine, "config", "sites.json"))


def test_environnement_valide(tmp_path):
    venv = tmp_path / "venv"
    assert not installeur.environnement_valide(str(venv))
    (venv / "Scripts").mkdir(parents=True)
    (venv / "Scripts" / "pythonw.exe").write_bytes(b"")
    (venv / "pyvenv.cfg").write_text("home = %s\nversion = 3.12.0\n" % tmp_path, encoding="utf-8")
    assert installeur.environnement_valide(str(venv))
    (venv / "pyvenv.cfg").write_text("home = %s\n" % (tmp_path / "python-desinstalle"), encoding="utf-8")
    assert not installeur.environnement_valide(str(venv))


def _ecrire(chemin, texte=""):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(texte)


def test_mise_a_jour_remplace_le_code_retire_l_ancien_et_garde_la_config(tmp_path):
    source, installe = str(tmp_path / "telechargement"), str(tmp_path / "installe")
    _ecrire(os.path.join(source, "veille_ia", "watch.py"), "nouveau")
    _ecrire(os.path.join(source, "veille_ia", "__pycache__", "watch.pyc"), "cache")
    _ecrire(os.path.join(source, "tests", "test_x.py"), "pas pour l'utilisateur")
    _ecrire(os.path.join(source, "installer.pyw"))
    _ecrire(os.path.join(installe, "veille_ia", "watch.py"), "ancien")
    _ecrire(os.path.join(installe, "veille_ia", "module_retire.py"), "ancien")
    _ecrire(os.path.join(installe, "config", "sites.json"), '{"sites": {"a": {}}}')

    installeur.copier_outil(source, installe)

    assert open(os.path.join(installe, "veille_ia", "watch.py"), encoding="utf-8").read() == "nouveau"
    assert not os.path.exists(os.path.join(installe, "veille_ia", "module_retire.py"))
    assert not os.path.exists(os.path.join(installe, "veille_ia", "__pycache__"))
    assert not os.path.exists(os.path.join(installe, "tests"))
    assert os.path.exists(os.path.join(installe, "installer.pyw"))
    assert open(os.path.join(installe, "config", "sites.json"), encoding="utf-8").read() == '{"sites": {"a": {}}}'


def test_reprend_les_sites_d_une_installation_dans_un_dossier_telecharge(tmp_path):
    source, installe = str(tmp_path / "telechargement"), str(tmp_path / "installe")
    _ecrire(os.path.join(source, "config", "sites.json"), '{"sites": {"exemple": {}}}')
    _ecrire(os.path.join(source, "config", "exemple", "jeton_gsc.json"), "jeton")
    _ecrire(os.path.join(source, "config", "venv", "pyvenv.cfg"), "home = ailleurs")
    _ecrire(os.path.join(source, "config", "serveur.json"), '{"pid": 1}')

    assert installeur.reprendre_configuration(source, installe)
    assert os.path.exists(os.path.join(installe, "config", "exemple", "jeton_gsc.json"))
    assert not os.path.exists(os.path.join(installe, "config", "venv"))          # recréé pour ce dossier
    assert not os.path.exists(os.path.join(installe, "config", "serveur.json"))


def test_ne_remplace_jamais_des_sites_deja_installes(tmp_path):
    source, installe = str(tmp_path / "telechargement"), str(tmp_path / "installe")
    _ecrire(os.path.join(source, "config", "sites.json"), '{"sites": {"vieux": {}}}')
    _ecrire(os.path.join(installe, "config", "sites.json"), '{"sites": {"actuel": {}}}')
    assert not installeur.reprendre_configuration(source, installe)
    assert "actuel" in open(os.path.join(installe, "config", "sites.json"), encoding="utf-8").read()


def test_installateur_lance_depuis_le_dossier_installe(tmp_path):
    assert installeur.meme_dossier(str(tmp_path), str(tmp_path / "." / ""))
    assert not installeur.meme_dossier(str(tmp_path / "a"), str(tmp_path / "b"))
