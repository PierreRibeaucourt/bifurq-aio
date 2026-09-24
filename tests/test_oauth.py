import socket

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
