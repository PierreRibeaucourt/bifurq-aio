import io
import json
import os
import zipfile

import pytest

from conftest import RACINE
from veille_ia import __version__, config, mise_a_jour


@pytest.fixture(autouse=True)
def _racine_isolee(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "racine", lambda: str(tmp_path))


def _en_ligne(monkeypatch, reponse):
    appels = []

    def lire():
        appels.append(1)
        if isinstance(reponse, Exception):
            raise reponse
        return reponse
    monkeypatch.setattr(mise_a_jour, "_lire_en_ligne", lire)
    return appels


def _plus_recente():
    majeur, mineur, _ = mise_a_jour.numero(__version__)
    return "%d.%d.0" % (majeur, mineur + 1)


def test_nouvelle_version_annoncee(monkeypatch):
    _en_ligne(monkeypatch, {"version": _plus_recente(), "nouveautes": "Plus rapide."})
    mise_a_jour.verifier(maintenant=1000.0)
    assert mise_a_jour.disponible() == {"version": _plus_recente(), "nouveautes": "Plus rapide."}


def test_meme_version_ou_plus_ancienne_rien_a_annoncer(monkeypatch):
    for version in (__version__, "0.0.1"):
        _en_ligne(monkeypatch, {"version": version})
        mise_a_jour.verifier(force=True)
        assert mise_a_jour.disponible() is None


def test_numeros_compares_comme_des_nombres():
    assert mise_a_jour.numero("0.10.0") > mise_a_jour.numero("0.9.0")


def test_une_seule_lecture_par_intervalle(monkeypatch):
    appels = _en_ligne(monkeypatch, {"version": __version__})
    mise_a_jour.verifier(maintenant=1000.0)
    mise_a_jour.verifier(maintenant=1000.0 + mise_a_jour.INTERVALLE - 1)
    assert len(appels) == 1
    mise_a_jour.verifier(maintenant=1000.0 + mise_a_jour.INTERVALLE)
    assert len(appels) == 2


def test_hors_ligne_rien_ne_casse_et_l_annonce_reste(monkeypatch):
    _en_ligne(monkeypatch, {"version": _plus_recente()})
    mise_a_jour.verifier(maintenant=1000.0)
    _en_ligne(monkeypatch, OSError("hors ligne"))
    mise_a_jour.verifier(maintenant=1000.0 + mise_a_jour.INTERVALLE)
    assert mise_a_jour.disponible()["version"] == _plus_recente()


def test_lecture_ratee_reessayee_au_bout_d_une_heure(monkeypatch):
    """Régression du 24.09.2026 : une lecture ratée juste après l'installation repoussait
    le prochain essai de 20 heures."""
    appels = _en_ligne(monkeypatch, OSError("hors ligne"))
    mise_a_jour.verifier(maintenant=1000.0)
    assert mise_a_jour.lire()["erreur"] == "OSError : hors ligne"
    mise_a_jour.verifier(maintenant=1000.0 + mise_a_jour.REESSAI - 1)
    assert len(appels) == 1
    _en_ligne(monkeypatch, {"version": _plus_recente()})
    mise_a_jour.verifier(maintenant=1000.0 + mise_a_jour.REESSAI)
    assert mise_a_jour.disponible()["version"] == _plus_recente()
    assert "erreur" not in mise_a_jour.lire()


def test_numero_illisible_ignore(monkeypatch):
    for version in ("../../ailleurs", "1.2", "v9.9.9", "", None):
        _en_ligne(monkeypatch, {"version": version})
        mise_a_jour.verifier(force=True)
        assert mise_a_jour.disponible() is None


def _zip(fichiers):
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        for nom in fichiers:
            z.writestr(nom, "")
    return tampon.getvalue()


def _telechargement(monkeypatch, tmp_path, contenu):
    monkeypatch.setattr(mise_a_jour.tempfile, "gettempdir", lambda: str(tmp_path))
    demandes = []

    def urlopen(req, timeout=None):
        demandes.append(req.full_url)
        return io.BytesIO(contenu)
    monkeypatch.setattr(mise_a_jour.urllib.request, "urlopen", urlopen)
    return demandes


def test_telecharge_l_etiquette_de_la_version_dans_le_depot(monkeypatch, tmp_path):
    demandes = _telechargement(monkeypatch, tmp_path, _zip(["bifurq-aio-9.9.9/installer.pyw",
                                                             "bifurq-aio-9.9.9/veille_ia/__init__.py"]))
    dossier = mise_a_jour.telecharger("9.9.9")
    assert demandes == ["https://github.com/PierreRibeaucourt/bifurq-aio/archive/refs/tags/v9.9.9.zip"]
    assert os.path.isfile(os.path.join(dossier, "installer.pyw"))
    assert os.path.commonpath([dossier, str(tmp_path)]) == str(tmp_path)


def test_telechargement_sans_installateur_refuse(monkeypatch, tmp_path):
    _telechargement(monkeypatch, tmp_path, _zip(["autre-chose/lisez-moi.txt"]))
    with pytest.raises(ValueError):
        mise_a_jour.telecharger("9.9.9")


def test_numero_illisible_jamais_telecharge(monkeypatch, tmp_path):
    demandes = _telechargement(monkeypatch, tmp_path, b"")
    with pytest.raises(ValueError):
        mise_a_jour.telecharger("../../ailleurs")
    assert demandes == []


def test_installateur_lance_avec_le_python_de_base(monkeypatch, tmp_path):
    python = "pythonw.exe" if os.name == "nt" else "python3"
    (tmp_path / "pyvenv.cfg").write_text("home = %s\n" % tmp_path, encoding="utf-8")
    (tmp_path / python).write_bytes(b"")
    monkeypatch.setattr(mise_a_jour.sys, "prefix", str(tmp_path))
    lances = []
    monkeypatch.setattr(mise_a_jour.subprocess, "Popen", lambda commande, **options: lances.append((commande, options)))
    mise_a_jour.lancer_installateur(str(tmp_path / "code"), 51234)
    commande, options = lances[0]
    assert commande == [str(tmp_path / python), os.path.join(str(tmp_path / "code"), "installer.pyw"),
                        "--mise-a-jour", "51234"]
    # détaché : l'installateur arrête l'interface qui l'a lancé, et doit lui survivre
    assert options.get("creationflags") if os.name == "nt" else options.get("start_new_session")


def test_version_publiee_concorde_avec_le_code_et_le_bouton_de_telechargement():
    """Procédure de publication (CONTRIBUTING.md) : les trois numéros changent ensemble."""
    with io.open(os.path.join(RACINE, "docs", "version.json"), encoding="utf-8") as f:
        publiee = json.load(f)
    assert publiee["version"] == __version__ and publiee["nouveautes"]
    with io.open(os.path.join(RACINE, "docs", "index.html"), encoding="utf-8") as f:
        assert 'href="%s"' % (mise_a_jour.URL_ZIP % __version__) in f.read()
