import datetime
import json
import os

import pytest

from veille_ia import config, gsc_api, sitemap, watch
from veille_ia.erreurs import ErreurConnexionGoogle, ErreurPlanDeSite

AUJOURD_HUI = datetime.date.today().isoformat()
FIN = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
ADRESSE = "https://exemple.fr/collections/complement-pour-le-sommeil"


class _ControleurHTTPFactice:
    def __init__(self, codes):
        self.codes = codes

    def controler(self, url):
        return {"code": self.codes.get(url, 200), "finale": url}


@pytest.fixture(autouse=True)
def _racine_isolee(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "racine", lambda: str(tmp_path))


def _site(seuil=15):
    return {"nom": "exemple.fr", "propriete": "sc-domain:exemple.fr",
            "sitemaps": ["https://exemple.fr/sitemap.xml"], "seuil_impressions": seuil, "dataforseo": None}


def _simuler(monkeypatch, plan, lignes, fin=FIN, inconnue=True):
    appels = []
    monkeypatch.setattr(sitemap, "plan_de_site", lambda racines, journal, strict=False: set(plan))
    monkeypatch.setattr(gsc_api, "dernier_jour", lambda chemin, propriete: fin)

    def donnees(chemin, propriete, debut, fin_, dims):
        appels.append((debut, fin_))
        return lignes
    monkeypatch.setattr(gsc_api, "donnees", donnees)
    monkeypatch.setattr(gsc_api, "inspecter", lambda chemin, url, propriete: {
        "url": url, "http": 200, "coverage": gsc_api.INCONNUE if inconnue else "Envoyée et indexée"})
    return appels


def test_propose_la_page_qui_ressemble(monkeypatch):
    _simuler(monkeypatch, {"https://exemple.fr/collections/complements-sommeil",
                           "https://exemple.fr/collections/complements-stress"},
             [{"URL": ADRESSE, "Impressions": 40}, {"URL": "https://exemple.fr/collections/complements-sommeil", "Impressions": 500}])
    r = watch.veille_site("exemple", _site(), _ControleurHTTPFactice({ADRESSE: 404}), lambda m: None, AUJOURD_HUI)
    assert len(r["a_rediriger"]) == 1
    d = r["a_rediriger"][0]
    assert d["adresse"] == ADRESSE
    assert d["cible_proposee"] == "/collections/complements-sommeil"
    assert d["cible_url"] == "https://exemple.fr/collections/complements-sommeil"


def test_aucune_page_ne_ressemble_previent_sans_cible(monkeypatch):
    """Process voulu : si aucune URL similaire n'est trouvée, juste prévenir."""
    inventee = "https://exemple.fr/blogs/news/recette-gateau-chocolat"
    _simuler(monkeypatch, {"https://exemple.fr/collections/magnesium-bisglycinate"},
             [{"URL": inventee, "Impressions": 40}])
    r = watch.veille_site("exemple", _site(), _ControleurHTTPFactice({inventee: 404}), lambda m: None, AUJOURD_HUI)
    assert len(r["a_rediriger"]) == 1
    assert r["a_rediriger"][0]["cible_url"] == ""
    assert r["a_rediriger"][0]["sure"] is False


def test_cumul_sur_trois_mois_avant_la_derniere_date_publiee(monkeypatch):
    """Régression du 24.09.2026 : le cumul partait du jour de connexion, après la
    dernière date publiée, et la Search Console refusait la requête."""
    appels = _simuler(monkeypatch, {"https://exemple.fr/collections/complements-sommeil"},
                      [{"URL": ADRESSE, "Impressions": 40}])
    watch.veille_site("exemple", _site(), _ControleurHTTPFactice({ADRESSE: 404}), lambda m: None, AUJOURD_HUI)
    for debut, fin in appels:
        assert debut <= fin == FIN
    assert (datetime.date.fromisoformat(FIN) - datetime.date.fromisoformat(appels[0][0])).days == watch.FENETRE_JOURS - 1


def test_sous_le_seuil_rien_a_corriger_mais_signale(monkeypatch):
    _simuler(monkeypatch, {"https://exemple.fr/collections/complements-sommeil"}, [{"URL": ADRESSE, "Impressions": 3}])
    r = watch.veille_site("exemple", _site(), _ControleurHTTPFactice({ADRESSE: 404}), lambda m: None, AUJOURD_HUI)
    assert r["a_rediriger"] == []
    assert any("moins de 15 fois" in i for i in r["infos"])


def test_page_connue_de_google_pas_inventee(monkeypatch):
    _simuler(monkeypatch, {"https://exemple.fr/collections/complements-sommeil"},
             [{"URL": ADRESSE, "Impressions": 40}], inconnue=False)
    r = watch.veille_site("exemple", _site(), _ControleurHTTPFactice({ADRESSE: 404}), lambda m: None, AUJOURD_HUI)
    assert r["a_rediriger"] == []


def test_adresse_deja_redirigee_sort_de_la_liste(monkeypatch):
    _simuler(monkeypatch, {"https://exemple.fr/collections/complements-sommeil"}, [{"URL": ADRESSE, "Impressions": 40}])
    r = watch.veille_site("exemple", _site(), _ControleurHTTPFactice({ADRESSE: 200}), lambda m: None, AUJOURD_HUI)
    assert r["a_rediriger"] == []
    assert r["resolues"] == ["collections/complement-pour-le-sommeil"]


def test_adresse_ecartee_ignoree(monkeypatch):
    _simuler(monkeypatch, {"https://exemple.fr/collections/complements-sommeil"}, [{"URL": ADRESSE, "Impressions": 40}])
    config.ajouter_ecartee("exemple", "collections/complement-pour-le-sommeil")
    r = watch.veille_site("exemple", _site(), _ControleurHTTPFactice({ADRESSE: 404}), lambda m: None, AUJOURD_HUI)
    assert r["a_rediriger"] == []


def test_site_sans_donnees_recentes_n_est_pas_une_panne(monkeypatch):
    _simuler(monkeypatch, set(), [], fin=None)
    r = watch.veille_site("exemple", _site(), _ControleurHTTPFactice({}), lambda m: None, AUJOURD_HUI)
    assert r["a_rediriger"] == [] and r["infos"]


def test_plan_de_site_vide_est_une_panne(monkeypatch):
    _simuler(monkeypatch, set(), [{"URL": ADRESSE, "Impressions": 40}])
    with pytest.raises(ErreurPlanDeSite):
        watch.veille_site("exemple", _site(), _ControleurHTTPFactice({}), lambda m: None, AUJOURD_HUI)


def test_executer_interactif_ecrit_l_etat_sans_notifier(monkeypatch):
    config.ajouter_site("exemple", nom="exemple.fr", propriete="sc-domain:exemple.fr",
                        sitemaps=["https://exemple.fr/sitemap.xml"])
    _simuler(monkeypatch, {"https://exemple.fr/collections/complements-sommeil"}, [{"URL": ADRESSE, "Impressions": 40}])
    monkeypatch.setattr("veille_ia.http_check.ControleurHTTP.controler",
                        lambda self, url: {"code": 404 if url == ADRESSE else 200, "finale": url})
    from veille_ia import notify_windows
    envois = []
    monkeypatch.setattr(notify_windows, "notifier", lambda *a, **k: envois.append(a) or True)
    watch.executer(interactif=True)
    etat = watch.lire_etat()
    assert etat["exemple"]["statut"] == "a_corriger"
    assert len(etat["exemple"]["a_rediriger"]) == 1
    assert envois == []
    assert not watch.analyse_en_cours()


def test_executer_range_une_panne_en_probleme_avec_son_action(monkeypatch):
    config.ajouter_site("exemple", nom="exemple.fr", propriete="sc-domain:exemple.fr",
                        sitemaps=["https://exemple.fr/sitemap.xml"])

    def expire(chemin, propriete):
        raise ErreurConnexionGoogle("La connexion à votre compte Google a expiré.")
    monkeypatch.setattr(gsc_api, "dernier_jour", expire)
    from veille_ia import notify_windows
    envois = []
    monkeypatch.setattr(notify_windows, "notifier", lambda *a, **k: envois.append(a) or True)
    watch.executer()
    watch.executer()                         # même panne, même jour : une seule notification
    e = watch.lire_etat()["exemple"]
    assert e["statut"] == "probleme"
    assert e["action"] == "reconnecter"
    assert "expiré" in e["message"]
    assert len(envois) == 1


def test_verrou_empeche_deux_analyses(monkeypatch):
    json.dump({"pid": os.getpid(), "debut": __import__("time").time()}, open(watch.chemin_verrou(), "w"))
    assert watch.executer() == {"deja_en_cours": True}


def test_resultat_d_un_site_visible_sans_attendre_la_fin_des_suivants(monkeypatch):
    for cle in ("a", "b"):
        config.ajouter_site(cle, nom=cle + ".fr", propriete="sc-domain:%s.fr" % cle,
                            sitemaps=["https://%s.fr/sitemap.xml" % cle])
    watch._ecrire_json(watch.chemin_etat(), {"a": {"statut": "ok", "date": "2026-01-01T09:00"}})
    etat_de_a_pendant_b = {}

    def veille_site(cle, cfg, controleur, journal, aujourd_hui=None, etape=None):
        if cle == "b":
            etat_de_a_pendant_b.update(watch.lire_etat()["a"])
        a_rediriger = [{"cle": "/x", "chemin": "/x", "adresse": "https://a.fr/x", "impressions": 20,
                        "impressions_7j": 2, "cible_url": "", "cible_proposee": "", "sure": False,
                        "ressemblance": 0.2}] if cle == "a" else []
        return {"site": cle, "fin_gsc": FIN, "a_rediriger": a_rediriger, "anomalies": [], "infos": [],
                "resolues": []}
    monkeypatch.setattr(watch, "veille_site", veille_site)
    from veille_ia import notify_windows
    monkeypatch.setattr(notify_windows, "notifier", lambda *a, **k: True)
    watch.executer(interactif=True)
    assert etat_de_a_pendant_b["statut"] == "a_corriger"          # nouvelle analyse, pas l'ancien "ok"
    assert watch.lire_etat()["b"]["statut"] == "ok"
