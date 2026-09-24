import json
import socket
import urllib.parse

import pytest

from veille_ia import oauth, oauth_client


@pytest.fixture(autouse=True)
def _client_configure(monkeypatch):
    monkeypatch.setattr(oauth_client, "CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    monkeypatch.setattr(oauth_client, "CLIENT_SECRET", "test-secret")


def test_client_non_configure_leve_une_erreur_claire(monkeypatch):
    monkeypatch.setattr(oauth_client, "CLIENT_ID", "À_REMPLACER.apps.googleusercontent.com")
    with pytest.raises(RuntimeError, match="SETUP_OAUTH"):
        oauth.url_autorisation("http://127.0.0.1:8765/oauth2/callback", "etat")


def test_url_autorisation_contient_les_bons_parametres():
    url = oauth.url_autorisation("http://127.0.0.1:8765/oauth2/callback", "un-etat-aleatoire")
    assert url.startswith(oauth.AUTH_URL)
    assert "client_id=test-client-id" in url
    assert "state=un-etat-aleatoire" in url
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "select_account" in url            # choix du compte à chaque connexion
    assert "scope=" in url and "webmasters.readonly" in url


def test_nouvel_etat_est_different_a_chaque_appel():
    assert oauth.nouvel_etat() != oauth.nouvel_etat()


def test_enregistrer_jeton_refuse_sans_refresh_token(tmp_path):
    with pytest.raises(RuntimeError, match="renouvellement"):
        oauth.enregistrer_jeton(str(tmp_path / "jeton.json"), {"access_token": "abc"})


def test_enregistrer_jeton_ecrit_le_bon_schema(tmp_path):
    chemin = str(tmp_path / "site" / "jeton.json")
    oauth.enregistrer_jeton(chemin, {"access_token": "abc", "refresh_token": "def", "expires_in": 3600})
    import json
    donnees = json.load(open(chemin, encoding="utf-8"))
    assert set(donnees) == {"client_id", "client_secret", "refresh_token", "token_uri"}
    assert donnees["refresh_token"] == "def"


class _Reponse:
    def __init__(self, donnees):
        self.donnees = donnees

    def read(self):
        return json.dumps(self.donnees).encode()


def test_nouvelle_connexion_dans_le_meme_fichier_utilise_le_nouveau_compte(tmp_path, monkeypatch):
    """Le fichier temporaire sert à chaque connexion : la liste des sites doit venir du
    compte qui vient de se connecter, pas du précédent resté en mémoire."""
    monkeypatch.setattr(oauth, "_cache", {})
    acces = {"compte-a": "acces-a", "compte-b": "acces-b"}
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: _Reponse(
        {"access_token": acces[urllib.parse.parse_qs(req.data.decode())["refresh_token"][0]], "expires_in": 3600}))
    chemin = str(tmp_path / "_temp_jeton.json")
    oauth.enregistrer_jeton(chemin, {"refresh_token": "compte-a"})
    assert oauth.jeton_frais(chemin) == "acces-a"
    oauth.enregistrer_jeton(chemin, {"refresh_token": "compte-b"})
    assert oauth.jeton_frais(chemin) == "acces-b"


def test_trouver_port_libre_retombe_sur_un_port_ephemere_si_occupe():
    occupe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupe.bind(("127.0.0.1", 0))
    occupe.listen(1)
    port_pris = occupe.getsockname()[1]
    try:
        s = oauth.trouver_port_libre(port_pris)
        try:
            assert s.getsockname()[1] != port_pris
        finally:
            s.close()
    finally:
        occupe.close()


def test_trouver_port_libre_garde_le_port_prefere_si_disponible():
    libre = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    libre.bind(("127.0.0.1", 0))
    port = libre.getsockname()[1]
    libre.close()
    s = oauth.trouver_port_libre(port)
    try:
        assert s.getsockname()[1] == port
    finally:
        s.close()
