import importlib.util
import io
import os
import plistlib
import shutil
import stat
import subprocess
import sys
import tarfile
import zipfile

import pytest

from conftest import RACINE
from veille_ia import __version__

sys.path.insert(0, os.path.join(RACINE, "outils"))
import paquets  # noqa: E402

spec = importlib.util.spec_from_loader(
    "installeur", importlib.machinery.SourceFileLoader("installeur", os.path.join(RACINE, "installer.pyw")))
installeur = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installeur)


def test_paquets_contiennent_ce_que_l_installateur_copie():
    assert paquets.FICHIERS == installeur.A_COPIER
    assert paquets.version() == __version__


def _membres_ar(contenu):
    assert contenu.startswith(b"!<arch>\n")
    i, membres = 8, {}
    while i < len(contenu):
        entete = contenu[i:i + 60]
        nom, taille = entete[:16].decode().strip(), int(entete[48:58])
        membres[nom] = contenu[i + 60:i + 60 + taille]
        i += 60 + taille + (taille % 2)
    return membres


def test_application_mac(tmp_path):
    chemin = paquets.zip_mac(str(tmp_path / "Bifurq-AIO-Mac.zip"))
    with zipfile.ZipFile(chemin) as z:
        noms = z.namelist()
        app = "Installer Bifurq AIO.app/Contents/"
        infos = plistlib.loads(z.read(app + "Info.plist"))
        assert infos["CFBundleExecutable"] == "installer" and infos["CFBundleShortVersionString"] == __version__
        # droits Unix gardés à l'extraction : le script doit rester exécutable
        mode = z.getinfo(app + "MacOS/installer").external_attr >> 16
        assert stat.S_ISREG(mode) and mode & 0o111
        assert app + "Resources/code/installer.pyw" in noms and app + "Resources/code/veille_ia/watch.py" in noms
        assert app + "Resources/icone.icns" in noms
        assert not any("/tests/" in n or "/docs/" in n or "__pycache__" in n for n in noms)


def test_paquet_deb(tmp_path):
    membres = _membres_ar(open(paquets.deb(str(tmp_path / "bifurq-aio.deb")), "rb").read())
    assert list(membres) == ["debian-binary", "control.tar.gz", "data.tar.gz"] and membres["debian-binary"] == b"2.0\n"
    with tarfile.open(fileobj=io.BytesIO(membres["control.tar.gz"])) as t:
        controle = t.extractfile("./control").read().decode("utf-8")
    assert "Version: %s\n" % __version__ in controle and "Depends: python3 (>= 3.8)" in controle
    with tarfile.open(fileobj=io.BytesIO(membres["data.tar.gz"])) as t:
        lanceur = t.getmember("./opt/bifurq-aio/bifurq-aio")
        assert lanceur.mode == 0o755 and lanceur.uid == 0
        assert "./opt/bifurq-aio/veille_ia/watch.py" in t.getnames()
        entree = t.extractfile("./usr/share/applications/bifurq-aio.desktop").read().decode("utf-8")
    assert "Exec=/opt/bifurq-aio/bifurq-aio\n" in entree


@pytest.mark.skipif(not shutil.which("dpkg-deb"), reason="dpkg-deb absent")
def test_paquet_deb_lu_par_dpkg(tmp_path):
    chemin = paquets.deb(str(tmp_path / "bifurq-aio.deb"))
    r = subprocess.run(["dpkg-deb", "--info", chemin], capture_output=True, text=True)
    assert r.returncode == 0 and "Package: bifurq-aio" in r.stdout, r.stderr
    assert "./opt/bifurq-aio/installer.pyw" in subprocess.run(["dpkg-deb", "--contents", chemin],
                                                              capture_output=True, text=True).stdout


@pytest.mark.skipif(not shutil.which("rpmbuild"), reason="rpmbuild absent")
def test_paquet_rpm(tmp_path):
    chemin = paquets.rpm(str(tmp_path / "bifurq-aio.rpm"))
    infos = subprocess.run(["rpm", "-qpi", chemin], capture_output=True, text=True).stdout
    assert "bifurq-aio" in infos and __version__ in infos
    fichiers = subprocess.run(["rpm", "-qpl", chemin], capture_output=True, text=True).stdout.split()
    assert "/opt/bifurq-aio/bifurq-aio" in fichiers and "/usr/share/applications/bifurq-aio.desktop" in fichiers
    dependances = subprocess.run(["rpm", "-qpR", chemin], capture_output=True, text=True).stdout
    assert "python3 >= 3.8" in dependances and "python(abi)" not in dependances


@pytest.mark.skipif(os.name == "nt", reason="sh")
def test_scripts_des_paquets_valides_pour_sh(tmp_path):
    for nom, contenu in (("mac", paquets.SCRIPT_MAC), ("linux", paquets.LANCEUR_LINUX)):
        f = tmp_path / nom
        f.write_text(contenu, encoding="utf-8")
        r = subprocess.run(["sh", "-n", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, (nom, r.stderr)


def test_installateur_lance_par_un_double_clic_parle_dans_une_fenetre(monkeypatch):
    fenetres = []
    monkeypatch.setattr(installeur.plateforme, "SYSTEME", "linux")
    monkeypatch.setattr(installeur, "fenetre", lambda texte, erreur=False: fenetres.append(texte))
    monkeypatch.setattr(installeur.sys, "argv", ["installer.pyw"])
    monkeypatch.setattr(installeur.sys, "stdout", io.StringIO())
    installeur.message("Bifurq AIO est installé.")
    assert fenetres == ["Bifurq AIO est installé."]
    monkeypatch.setattr(installeur.sys, "argv", ["installer.pyw", "--terminal"])
    installeur.message("Bifurq AIO est installé.")
    assert len(fenetres) == 1                        # installer.sh : le Terminal suffit


def test_le_site_telecharge_les_paquets_publies():
    with io.open(os.path.join(RACINE, "docs", "index.html"), encoding="utf-8") as f:
        page = f.read()
    for nom in (paquets.ZIP_MAC, paquets.DEB, paquets.RPM):
        assert 'href="https://github.com/PierreRibeaucourt/bifurq-aio/releases/latest/download/%s"' % nom in page
