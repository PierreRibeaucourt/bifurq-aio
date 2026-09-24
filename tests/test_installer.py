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
