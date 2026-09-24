import io
import json
import urllib.error

import pytest

from veille_ia import gsc_api, oauth
from veille_ia.erreurs import ErreurAccesSearchConsole, ErreurConnexionGoogle, ErreurDonnees


class _ReponseFactice:
    def __init__(self, corps):
        self._corps = json.dumps(corps).encode()

    def read(self):
        return self._corps


def _erreur_http(code, message):
    corps = json.dumps({"error": {"code": code, "message": message}}).encode()
    return urllib.error.HTTPError("https://x", code, "err", {}, io.BytesIO(corps))


@pytest.fixture(autouse=True)
def _jeton_factice(monkeypatch):
    monkeypatch.setattr(oauth, "jeton_frais", lambda chemin: "jeton-de-test")


def test_donnees_construit_la_bonne_requete(monkeypatch):
    capture = {}

    def faux_urlopen(req, timeout=None):
        capture["url"] = req.full_url
        capture["headers"] = dict(req.headers)
        capture["corps"] = json.loads(req.data.decode())
        return _ReponseFactice({"rows": [{"keys": ["https://exemple.fr/page"], "clicks": 3,
                                          "impressions": 40, "ctr": 0.075, "position": 4.2}]})

    monkeypatch.setattr("urllib.request.urlopen", faux_urlopen)
    lignes = gsc_api.donnees("j.json", "sc-domain:exemple.fr", "2026-09-01", "2026-09-20", ("page",))
    assert capture["url"] == "https://www.googleapis.com/webmasters/v3/sites/sc-domain%3Aexemple.fr/searchAnalytics/query"
    assert capture["headers"]["Authorization"] == "Bearer jeton-de-test"
    assert capture["corps"] == {"startDate": "2026-09-01", "endDate": "2026-09-20", "dimensions": ["page"], "rowLimit": 25000}
    assert lignes == [{"URL": "https://exemple.fr/page", "Clics": 3, "Impressions": 40, "CTR": 0.075, "Position": 4.2}]


def test_401_devient_une_connexion_a_renouveler(monkeypatch):
    def faux_urlopen(req, timeout=None):
        raise _erreur_http(401, "Invalid Credentials")
    monkeypatch.setattr("urllib.request.urlopen", faux_urlopen)
    with pytest.raises(ErreurConnexionGoogle) as e:
        gsc_api.lister_proprietes("j.json")
    assert e.value.action == "reconnecter"


def test_403_devient_un_acces_refuse(monkeypatch):
    def faux_urlopen(req, timeout=None):
        raise _erreur_http(403, "User does not have sufficient permission")
    monkeypatch.setattr("urllib.request.urlopen", faux_urlopen)
    with pytest.raises(ErreurAccesSearchConsole):
        gsc_api.donnees("j.json", "sc-domain:exemple.fr", "2026-09-01", "2026-09-20")


def test_400_garde_le_message_de_google(monkeypatch):
    def faux_urlopen(req, timeout=None):
        raise _erreur_http(400, "End date cannot precede the start date.")
    monkeypatch.setattr("urllib.request.urlopen", faux_urlopen)
    with pytest.raises(ErreurDonnees) as e:
        gsc_api.donnees("j.json", "sc-domain:exemple.fr", "2026-09-24", "2026-09-21")
    assert "End date cannot precede the start date." in e.value.message


def test_dernier_jour_sans_donnees_rend_none(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: _ReponseFactice({"rows": []}))
    assert gsc_api.dernier_jour("j.json", "sc-domain:exemple.fr") is None


def test_inspecter_signature_inconnue(monkeypatch):
    def faux_urlopen(req, timeout=None):
        assert req.full_url == gsc_api.INSPECTION_URL
        return _ReponseFactice({"inspectionResult": {"indexStatusResult": {"coverageState": gsc_api.INCONNUE}}})
    monkeypatch.setattr("urllib.request.urlopen", faux_urlopen)
    r = gsc_api.inspecter("j.json", "https://exemple.fr/adresse-inventee", "sc-domain:exemple.fr")
    assert r["coverage"] == gsc_api.INCONNUE and r["http"] == 200


def test_inspecter_connexion_expiree_interrompt_le_site(monkeypatch):
    def faux_urlopen(req, timeout=None):
        raise _erreur_http(401, "Invalid Credentials")
    monkeypatch.setattr("urllib.request.urlopen", faux_urlopen)
    with pytest.raises(ErreurConnexionGoogle):
        gsc_api.inspecter("j.json", "https://exemple.fr/x", "sc-domain:exemple.fr")


def test_proprietes_lisibles_fusionne_et_prefere_le_domaine():
    liste = [{"siteUrl": "https://www.exemple.fr/", "permissionLevel": "siteOwner"},
             {"siteUrl": "sc-domain:exemple.fr", "permissionLevel": "siteOwner"},
             {"siteUrl": "https://autre.fr/", "permissionLevel": "siteFullUser"},
             {"siteUrl": "https://nonverifie.fr/", "permissionLevel": "siteUnverifiedUser"}]
    assert gsc_api.proprietes_lisibles(liste) == [
        {"nom": "autre.fr", "propriete": "https://autre.fr/"},
        {"nom": "exemple.fr", "propriete": "sc-domain:exemple.fr"}]
