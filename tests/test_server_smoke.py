"""Le serveur local répond réellement (pas seulement : le code compile), sur les
routes qui ne demandent pas de vrai compte Google."""
import http.client
import http.server
import os
import threading
import urllib.parse

import pytest

from veille_ia import config, gsc_api, oauth, oauth_client, plateforme, sitemap, watch
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


def _formulaire_activer(*proprietes):
    return [("proprietes", p) for p in proprietes] + [("au_demarrage", "on"), ("seuil", "15"),
                                                        ("jeton", server._session["jeton_formulaire"])]


def test_activer_ajoute_les_sites_puis_un_second_envoi_ramene_a_mes_sites(serveur, monkeypatch):
    monkeypatch.setattr(sitemap, "deviner_sitemaps",
                        lambda racine: [racine + "sitemap_index.xml"] if "a.fr" in racine else [])
    monkeypatch.setattr(plateforme, "planifier", lambda *args: None)
    monkeypatch.setattr(server, "lancer_analyse", lambda: True)
    os.makedirs(config.dossier_config(), exist_ok=True)
    with open(server._chemin_temp(), "w", encoding="utf-8") as f:
        f.write('{"refresh_token": "r"}')
    monkeypatch.setitem(server._session, "jeton_temp", server._chemin_temp())

    code, _, lieu = _requete(serveur, "POST", "/activer", _formulaire_activer("https://a.fr/", "sc-domain:b.fr"))
    assert (code, lieu) == (303, "/")
    sites = {cfg["propriete"]: cfg for cfg in config.lire()["sites"].values()}
    assert sites["https://a.fr/"]["sitemaps"] == ["https://a.fr/sitemap_index.xml"]
    assert sites["sc-domain:b.fr"]["sitemaps"] == ["https://b.fr/sitemap.xml"]      # rien trouvé : repli

    # double clic : le second envoi arrive une fois la connexion temporaire consommée
    code, _, lieu = _requete(serveur, "POST", "/activer", _formulaire_activer("https://a.fr/", "sc-domain:b.fr"))
    assert (code, lieu) == (303, "/")


def test_activer_sans_connexion_google_renvoie_vers_google(serveur):
    code, _, lieu = _requete(serveur, "POST", "/activer", _formulaire_activer("sc-domain:c.fr"))
    assert (code, lieu) == (303, "/connecter")


def _reconnecter(port, monkeypatch, cle, proprietes_du_compte):
    """Reconnexion du site cle avec un compte Google qui voit proprietes_du_compte."""
    monkeypatch.setattr(oauth, "echanger_code", lambda code, uri: {"refresh_token": "nouveau-compte"})
    monkeypatch.setattr(gsc_api, "lister_proprietes", lambda chemin: [
        {"siteUrl": p, "permissionLevel": "siteOwner"} for p in proprietes_du_compte])
    monkeypatch.setattr(server, "lancer_analyse", lambda: True)
    _requete(port, "GET", "/connecter?site=" + cle)
    return _requete(port, "GET", "/oauth2/callback?code=c&state=" + server._session["etat_oauth"])


def _deux_sites_connectes():
    for cle, propriete in (("agence-fr", "sc-domain:agence.fr"), ("client-com", "sc-domain:client.com")):
        config.ajouter_site(cle, nom=propriete.split(":")[1], propriete=propriete, sitemaps=[])
        with open(config.chemin_jeton(cle), "w", encoding="utf-8") as f:
            f.write('{"refresh_token": "ancien-%s"}' % cle)


def _jeton(cle):
    with open(config.chemin_jeton(cle), encoding="utf-8") as f:
        return f.read()


def test_reconnecter_avec_un_compte_sans_acces_au_site_ne_change_rien(serveur, monkeypatch):
    _deux_sites_connectes()
    code, corps, _ = _reconnecter(serveur, monkeypatch, "client-com", ["sc-domain:agence.fr"])
    assert "Mauvais compte Google" in corps and "client.com" in corps
    assert "ancien-client-com" in _jeton("client-com")
    assert "ancien-agence-fr" in _jeton("agence-fr")          # pas remplacée en silence
    assert not os.path.exists(server._chemin_temp())


def test_reconnecter_avec_le_bon_compte_met_a_jour_les_sites_accessibles(serveur, monkeypatch):
    _deux_sites_connectes()
    code, _, lieu = _reconnecter(serveur, monkeypatch, "client-com", ["sc-domain:client.com"])
    assert (code, lieu) == (302, "/")
    assert "nouveau-compte" in _jeton("client-com")
    assert "ancien-agence-fr" in _jeton("agence-fr")          # ce compte ne le voit pas


@pytest.mark.skipif(os.name != "nt", reason="partage de port propre à Windows")
def test_une_autre_copie_de_l_outil_ne_prend_pas_le_meme_port():
    premiere = server.Serveur(("127.0.0.1", 0), server.Handler)
    try:
        with pytest.raises(OSError):
            server.Serveur(("127.0.0.1", premiere.server_port), server.Handler)
        with pytest.raises(OSError):                     # une ancienne version non plus
            http.server.ThreadingHTTPServer(("127.0.0.1", premiere.server_port), server.Handler)
    finally:
        premiere.server_close()


def test_page_inconnue_404(serveur):
    code, _, _ = _requete(serveur, "GET", "/nimporte-quoi")
    assert code == 404


def test_ping(serveur):
    code, corps, _ = _requete(serveur, "GET", "/ping")
    assert code == 200 and corps == "%s %s" % (server.PING, server.EMPREINTE)


def test_masquer_la_consigne_de_mes_sites(serveur):
    config.ajouter_site("exemple", nom="exemple.fr", propriete="sc-domain:exemple.fr", sitemaps=[])
    assert "Vous pouvez fermer cet onglet." in _requete(serveur, "GET", "/")[1]
    code, _, lieu = _requete(serveur, "POST", "/masquer-consigne", {"jeton": server._session["jeton_formulaire"]})
    assert (code, lieu) == (303, "/")
    assert "Vous pouvez fermer cet onglet." not in _requete(serveur, "GET", "/")[1]


# --- mise à jour en un clic ---
def _annoncer(version):
    from veille_ia import mise_a_jour
    mise_a_jour._ecrire({"verifie": 0, "version": version, "nouveautes": "Plus rapide."})


def _version_suivante():
    from veille_ia import __version__
    majeur, mineur, _ = (int(x) for x in __version__.split("."))
    return "%d.%d.0" % (majeur, mineur + 1)


class _TimerImmediat:
    def __init__(self, delai, fonction, args=()):
        self.fonction, self.args = fonction, args

    def start(self):
        self.fonction(*self.args)


def test_bandeau_de_mise_a_jour_dans_mes_sites(serveur):
    config.ajouter_site("exemple", nom="exemple.fr", propriete="sc-domain:exemple.fr", sitemaps=[])
    _annoncer(_version_suivante())
    code, corps, _ = _requete(serveur, "GET", "/")
    assert code == 200
    assert "La version %s de Bifurq AIO est disponible." % _version_suivante() in corps
    assert 'action="/mettre-a-jour"' in corps and "Plus rapide." in corps


def test_mettre_a_jour_telecharge_puis_lance_l_installateur_une_seule_fois(serveur, monkeypatch):
    from veille_ia import mise_a_jour
    monkeypatch.setitem(server._session, "mise_a_jour", None)
    _annoncer(_version_suivante())
    telecharges, lances = [], []
    monkeypatch.setattr(mise_a_jour, "telecharger", lambda v: telecharges.append(v) or "C:/code")
    monkeypatch.setattr(mise_a_jour, "lancer_installateur", lambda dossier, port: lances.append((dossier, port)))
    monkeypatch.setattr(server.threading, "Timer", _TimerImmediat)
    monkeypatch.setattr(server, "analyse_active", lambda: False)     # une analyse d'un autre test ne gêne pas
    jeton = {"jeton": server._session["jeton_formulaire"]}
    code, corps, _ = _requete(serveur, "POST", "/mettre-a-jour", jeton)
    assert code == 200 and "Mise à jour en cours" in corps and "Installation de la version" in corps
    assert telecharges == [_version_suivante()] and lances == [("C:/code", serveur)]
    code, corps, _ = _requete(serveur, "POST", "/mettre-a-jour", jeton)       # second clic
    assert code == 200 and "Mise à jour en cours" in corps and len(lances) == 1


def test_mettre_a_jour_sans_nouvelle_version_revient_a_mes_sites(serveur, monkeypatch):
    monkeypatch.setitem(server._session, "mise_a_jour", None)
    code, _, lieu = _requete(serveur, "POST", "/mettre-a-jour", {"jeton": server._session["jeton_formulaire"]})
    assert code == 303 and lieu == "/"


def test_telechargement_rate_rien_n_est_lance(serveur, monkeypatch):
    from veille_ia import mise_a_jour
    monkeypatch.setitem(server._session, "mise_a_jour", None)
    _annoncer(_version_suivante())

    def echec(version):
        raise OSError("hors ligne")
    monkeypatch.setattr(mise_a_jour, "telecharger", echec)
    monkeypatch.setattr(mise_a_jour, "lancer_installateur", lambda *a: pytest.fail("installateur lancé"))
    code, corps, _ = _requete(serveur, "POST", "/mettre-a-jour", {"jeton": server._session["jeton_formulaire"]})
    assert code == 502 and "Mise à jour impossible" in corps
    assert server._session["mise_a_jour"] is None


def test_apres_la_mise_a_jour_mes_sites_le_confirme(serveur):
    from veille_ia import __version__
    config.ajouter_site("exemple", nom="exemple.fr", propriete="sc-domain:exemple.fr", sitemaps=[])
    code, corps, _ = _requete(serveur, "GET", "/?maj=%s" % __version__)
    assert "Bifurq AIO est passé à la version %s." % __version__ in corps


def test_options_de_la_nouvelle_interface():
    assert server._arguments(["--port", "51234", "--sans-navigateur"]) == (51234, False)
    assert server._arguments([]) == (server.PORT_PREFERE, True)


# --- analyse d'un site ou des sites affichés ---
def _analyses(monkeypatch):
    lancees = []
    monkeypatch.setattr(server, "lancer_analyse", lambda cles=None: lancees.append(cles) or True)
    return lancees


def _deux_sites():
    for cle in ("a", "b"):
        config.ajouter_site(cle, nom=cle + ".fr", propriete="sc-domain:%s.fr" % cle, sitemaps=[])


def test_analyser_tous_les_sites_ou_seulement_certains(serveur, monkeypatch):
    _deux_sites()
    lancees = _analyses(monkeypatch)
    jeton = ("jeton", server._session["jeton_formulaire"])
    assert _requete(serveur, "POST", "/analyser", [jeton])[0] == 303
    assert _requete(serveur, "POST", "/analyser", [jeton, ("cle", "b")])[0] == 303
    assert _requete(serveur, "POST", "/analyser", [jeton, ("cle", "a"), ("cle", "b")])[0] == 303
    assert lancees == [None, ["b"], ["a", "b"]]


def test_analyser_depuis_la_page_du_site_y_revient(serveur, monkeypatch):
    _deux_sites()
    _analyses(monkeypatch)
    code, _, lieu = _requete(serveur, "POST", "/analyser", [("jeton", server._session["jeton_formulaire"]),
                                                            ("cle", "a"), ("retour", "site")])
    assert code == 303 and lieu == "/site?cle=a"


def test_analyser_un_site_retire_ne_lance_rien(serveur, monkeypatch):
    _deux_sites()
    lancees = _analyses(monkeypatch)
    code, _, lieu = _requete(serveur, "POST", "/analyser", [("jeton", server._session["jeton_formulaire"]),
                                                            ("cle", "disparu")])
    assert code == 303 and lieu == "/" and lancees == []
