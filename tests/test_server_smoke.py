"""Le serveur local répond réellement (pas seulement : le code compile), sur les
routes qui ne demandent pas de vrai compte Google."""
import http.client
import http.server
import threading
import urllib.parse

import pytest

from veille_ia import config, oauth_client, watch
from veille_ia.installer import server


@pytest.fixture
def serveur(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "racine", lambda: str(tmp_path))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield httpd.server_port
    finally:
        httpd.shutdown()


def _requete(port, methode, chemin, corps=None, hote=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    entetes = {"Host": hote or "127.0.0.1:%d" % port}
    donnees = None
    if corps is not None:
        donnees = urllib.parse.urlencode(corps)
        entetes["Content-Type"] = "application/x-www-form-urlencoded"
    conn.request(methode, chemin, body=donnees, headers=entetes)
    r = conn.getresponse()
    texte = r.read().decode("utf-8")
    conn.close()
    return r.status, texte, r.getheader("Location")


def test_accueil_sans_site(serveur):
    code, corps, _ = _requete(serveur, "GET", "/")
    assert code == 200
    assert "Connecter mon compte Google" in corps


def test_tableau_de_bord_affiche_l_etat_du_site(serveur):
    config.ajouter_site("exemple", nom="exemple.fr", propriete="sc-domain:exemple.fr", sitemaps=[])
    watch._ecrire_json(watch.chemin_etat(), {"exemple": {"statut": "probleme", "action": "reconnecter",
                                                         "message": "La connexion à votre compte Google a expiré.",
                                                         "date": "2026-09-24T10:00"}})
    code, corps, _ = _requete(serveur, "GET", "/")
    assert code == 200
    assert "exemple.fr" in corps and "Problème" in corps
    assert "La connexion à votre compte Google a expiré." in corps
    assert "Reconnecter mon compte Google" in corps


def test_connecter_sans_client_configure_echoue_lisiblement(serveur, monkeypatch):
    monkeypatch.setattr(oauth_client, "CLIENT_ID", "À_REMPLACER.apps.googleusercontent.com")
    code, corps, _ = _requete(serveur, "GET", "/connecter")
    assert code == 500
    assert "SETUP_OAUTH" in corps


def test_connecter_redirige_vers_google(serveur):
    code, _, lieu = _requete(serveur, "GET", "/connecter")
    assert code == 302
    assert lieu.startswith("https://accounts.google.com/")
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A" in lieu


def test_callback_refuse_un_state_inconnu(serveur):
    code, corps, _ = _requete(serveur, "GET", "/oauth2/callback?code=abc&state=pirate")
    assert "Connexion interrompue" in corps


def test_hote_etranger_refuse(serveur):
    code, _, _ = _requete(serveur, "GET", "/", hote="attaquant.example:80")
    assert code == 403


def test_action_sans_jeton_de_formulaire_refusee(serveur):
    config.ajouter_site("exemple", nom="exemple.fr", propriete="sc-domain:exemple.fr", sitemaps=[])
    code, _, _ = _requete(serveur, "POST", "/retirer", {"cle": "exemple"})
    assert code == 403
    assert "exemple" in config.lire()["sites"]


def test_ignorer_une_adresse(serveur):
    config.ajouter_site("exemple", nom="exemple.fr", propriete="sc-domain:exemple.fr", sitemaps=[])
    watch._ecrire_json(watch.chemin_etat(), {"exemple": {"statut": "a_corriger", "a_rediriger": [
        {"cle": "x", "chemin": "/x", "adresse": "https://exemple.fr/x", "impressions": 20, "impressions_7j": 2,
         "cible_url": "", "cible_proposee": "", "sure": False, "ressemblance": 0.2}]}})
    code, _, lieu = _requete(serveur, "POST", "/ignorer",
                             {"cle": "exemple", "adresse": "x", "jeton": server._session["jeton_formulaire"]})
    assert code == 303
    assert config.lire_ecartees("exemple") == {"x"}
    assert watch.lire_etat()["exemple"]["statut"] == "ok"


def test_modifier_un_site(serveur):
    config.ajouter_site("exemple", nom="exemple.fr", propriete="sc-domain:exemple.fr",
                        sitemaps=["https://exemple.fr/sitemap.xml"], seuil_impressions=15,
                        dataforseo={"login": "moi", "password": "secret"})
    code, corps, _ = _requete(serveur, "GET", "/modifier?cle=exemple")
    assert code == 200 and "secret" not in corps          # le mot de passe n'est jamais réaffiché
    code, _, _ = _requete(serveur, "POST", "/modifier", {
        "cle": "exemple", "nom": "Mon site", "seuil": "5",
        "sitemaps": "https://exemple.fr/sitemap.xml\nhttps://exemple.fr/blog-sitemap.xml",
        "jeton": server._session["jeton_formulaire"]})
    assert code == 303
    site = config.lire()["sites"]["exemple"]
    assert site["nom"] == "Mon site" and site["seuil_impressions"] == 5
    assert site["sitemaps"] == ["https://exemple.fr/sitemap.xml", "https://exemple.fr/blog-sitemap.xml"]
    assert site["dataforseo"] == {"login": "moi", "password": "secret"}      # gardé tel quel


def test_modifier_refuse_un_seuil_invalide(serveur):
    config.ajouter_site("exemple", nom="exemple.fr", propriete="sc-domain:exemple.fr",
                        sitemaps=["https://exemple.fr/sitemap.xml"])
    code, corps, _ = _requete(serveur, "POST", "/modifier", {
        "cle": "exemple", "nom": "x", "seuil": "zéro", "sitemaps": "https://exemple.fr/sitemap.xml",
        "jeton": server._session["jeton_formulaire"]})
    assert code == 200 and "nombre entier" in corps
    assert config.lire()["sites"]["exemple"]["seuil_impressions"] == 15


def test_page_inconnue_404(serveur):
    code, _, _ = _requete(serveur, "GET", "/nimporte-quoi")
    assert code == 404


def test_ping(serveur):
    code, corps, _ = _requete(serveur, "GET", "/ping")
    assert code == 200 and corps == "%s %s" % (server.PING, server.EMPREINTE)
