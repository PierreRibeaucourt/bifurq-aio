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
    def __init__(self, codes, titres=None):
        self.codes, self.titres, self.titres_lus = codes, titres or {}, []

    def controler(self, url):
        r = self.codes.get(url, 200)
        return dict(r, finale=url) if isinstance(r, dict) else {"code": r, "finale": url}

    def lire_titres(self, url):
        self.titres_lus.append(url)
        return self.titres.get(url)


@pytest.fixture(autouse=True)
def _racine_isolee(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "racine", lambda: str(tmp_path))
    # jamais de vraie requête vers les sites d'exemple
    monkeypatch.setattr("veille_ia.http_check.ControleurHTTP.lire_titres", lambda self, url: None)


def _site(seuil=15):
    return {"nom": "exemple.fr", "propriete": "sc-domain:exemple.fr",
            "sitemaps": ["https://exemple.fr/sitemap.xml"], "seuil_impressions": seuil, "dataforseo": None}


def _simuler(monkeypatch, plan, lignes, fin=FIN, inconnue=True):
    appels = []
    def plan_de_site(racines, journal, strict=False, verifier=None):
        if verifier:
            verifier()
        return set(plan)
    monkeypatch.setattr(sitemap, "plan_de_site", plan_de_site)
    monkeypatch.setattr(gsc_api, "dernier_jour", lambda chemin, propriete: fin)

    def donnees(chemin, propriete, debut, fin_, dims, frais=False):
        appels.append((debut, fin_, frais))
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


INVENTEE = "https://exemple.fr/blogs/news/dette-de-sommeil-definition-calcul-et-solutions-durales"
VRAIE = "https://exemple.fr/blogs/news/dette-de-sommeil"
PLAN_BLOG = {VRAIE, "https://exemple.fr/blogs/news/sommeil-profond", "https://exemple.fr/blogs/news/calcul-imc",
             "https://exemple.fr/blogs/news/solutions-anti-stress", "https://exemple.fr/blogs/news/definition-du-stress",
             "https://exemple.fr/blogs/news/magnesium-et-sommeil"}


def test_propose_la_page_dont_le_titre_ressemble(monkeypatch):
    """L'IA de Google fabrique l'adresse à partir du titre de la vraie page."""
    _simuler(monkeypatch, PLAN_BLOG, [{"URL": INVENTEE, "Impressions": 40}])
    http = _ControleurHTTPFactice({INVENTEE: 404},
                                  {VRAIE: ["Dette de sommeil : définition, calcul et solutions durables"]})
    d = watch.veille_site("exemple", _site(), http, lambda m: None, AUJOURD_HUI)["a_rediriger"][0]
    assert (d["cible_url"], d["sure"]) == (VRAIE, True)
    assert VRAIE in http.titres_lus and len(http.titres_lus) == watch.TITRES_A_LIRE


def test_titres_gardes_et_page_illisible_reessayee_le_lendemain(monkeypatch):
    _simuler(monkeypatch, PLAN_BLOG, [{"URL": INVENTEE, "Impressions": 40}])
    titres = {VRAIE: ["Dette de sommeil : définition, calcul et solutions durables"]}
    watch.veille_site("exemple", _site(), _ControleurHTTPFactice({INVENTEE: 404}, titres), lambda m: None, AUJOURD_HUI)
    http = _ControleurHTTPFactice({INVENTEE: 404})
    d = watch.veille_site("exemple", _site(), http, lambda m: None, AUJOURD_HUI)["a_rediriger"][0]
    assert http.titres_lus == [] and d["cible_url"] == VRAIE        # titres lus gardés 30 jours
    demain = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    watch.veille_site("exemple", _site(), http, lambda m: None, demain)
    assert len(http.titres_lus) == watch.TITRES_A_LIRE - 1          # sauf les pages illisibles la veille
    assert VRAIE not in http.titres_lus


def test_adresse_proche_sans_lire_les_titres(monkeypatch):
    inventee = "https://exemple.fr/blogs/news/vitamine-b12-effet-immedit"
    _simuler(monkeypatch, {"https://exemple.fr/blogs/news/vitamine-b12-effet-immediat",
                           "https://exemple.fr/blogs/news/vitamine-d-et-soleil"}, [{"URL": inventee, "Impressions": 40}])
    http = _ControleurHTTPFactice({inventee: 404})
    d = watch.veille_site("exemple", _site(), http, lambda m: None, AUJOURD_HUI)["a_rediriger"][0]
    assert d["sure"] and d["cible_proposee"] == "/blogs/news/vitamine-b12-effet-immediat"
    assert http.titres_lus == []


def test_une_seule_lecture_des_7_derniers_jours_en_donnees_fraiches(monkeypatch):
    """Le 24.09.2026 : l'IA de Google ne cite une adresse inventée que quelques jours, les
    3 mois lus jusque-là ne servaient à rien et les données définitives arrivaient trop tard."""
    appels = _simuler(monkeypatch, {"https://exemple.fr/collections/complements-sommeil"},
                      [{"URL": ADRESSE, "Impressions": 40}])
    watch.veille_site("exemple", _site(), _ControleurHTTPFactice({ADRESSE: 404}), lambda m: None, AUJOURD_HUI)
    assert len(appels) == 1
    debut, fin, frais = appels[0]
    assert fin == FIN and frais is True
    assert (datetime.date.fromisoformat(FIN) - datetime.date.fromisoformat(debut)).days == 6


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
    from veille_ia import plateforme
    envois = []
    monkeypatch.setattr(plateforme, "notifier", lambda *a, **k: envois.append(a) or True)
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
    from veille_ia import plateforme
    envois = []
    monkeypatch.setattr(plateforme, "notifier", lambda *a, **k: envois.append(a) or True)
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
    watch._ecrire_json(watch.chemin_etat(), {"a": {"statut": "ok", "date": "2026-01-01T09:00"},
                                             "b": {"statut": "ok", "date": "2026-01-01T09:00"}})
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
    from veille_ia import plateforme
    monkeypatch.setattr(plateforme, "notifier", lambda *a, **k: True)
    watch.executer(interactif=True)
    assert etat_de_a_pendant_b["statut"] == "a_corriger"          # nouvelle analyse, pas l'ancien "ok"
    assert watch.lire_etat()["b"]["statut"] == "ok"


def test_sites_analyses_dans_l_ordre_de_mes_sites(monkeypatch):
    for cle in ("a", "b", "c", "d"):
        config.ajouter_site(cle, nom=cle + ".fr", propriete="sc-domain:%s.fr" % cle,
                            sitemaps=["https://%s.fr/sitemap.xml" % cle])
    watch._ecrire_json(watch.chemin_etat(), {"a": {"statut": "ok"}, "b": {"statut": "incomplet"},
                                             "d": {"statut": "probleme"}})
    analyses = []

    def veille_site(cle, cfg, controleur, journal, aujourd_hui=None, etape=None):
        analyses.append(cle)
        return {"site": cle, "fin_gsc": FIN, "a_rediriger": [], "anomalies": [], "infos": [], "resolues": []}
    monkeypatch.setattr(watch, "veille_site", veille_site)
    from veille_ia import plateforme
    monkeypatch.setattr(plateforme, "notifier", lambda *a, **k: True)
    watch.executer(interactif=True)
    assert analyses == ["d", "b", "c", "a"]         # problème, incomplet, jamais analysé, tout va bien
    analyses.clear()
    watch._ecrire_json(watch.chemin_etat(), {"a": {"statut": "probleme"}})
    watch.executer(interactif=True, cles=["c", "a"])
    assert analyses == ["a", "c"]


def test_erreur_410_a_corriger_comme_un_404(monkeypatch):
    _simuler(monkeypatch, {"https://exemple.fr/collections/complements-sommeil"}, [{"URL": ADRESSE, "Impressions": 40}])
    r = watch.veille_site("exemple", _site(), _ControleurHTTPFactice({ADRESSE: 410}), lambda m: None, AUJOURD_HUI)
    assert [d["adresse"] for d in r["a_rediriger"]] == [ADRESSE] and r["anomalies"] == []


def test_protection_anti_robots_nommee_et_rien_de_conclu(monkeypatch):
    _simuler(monkeypatch, {"https://exemple.fr/collections/complements-sommeil"}, [{"URL": ADRESSE, "Impressions": 40}])
    bloque = _ControleurHTTPFactice({ADRESSE: {"code": 403, "protection": "DataDome"}})
    r = watch.veille_site("exemple", _site(), bloque, lambda m: None, AUJOURD_HUI)
    assert r["a_rediriger"] == [] and r["resolues"] == [] and r["protection"] == "DataDome"
    assert r["anomalies"] == ["Votre site bloque l'outil (protection anti-robots DataDome) : 1 adresse n'a pas pu "
                              "être testée. Ajoutez l'adresse IP de cet ordinateur en exception dans DataDome "
                              "pour laisser passer l'outil."]
    etat = watch._etat_du_site(r, set(), {}, "2026-09-24T10:00")
    assert etat["statut"] == "incomplet" and etat["protection"] == "DataDome"


def test_adresse_bloquee_retestee_a_l_analyse_suivante_du_meme_jour(monkeypatch):
    """Une fois la protection réglée, Analyser maintenant doit le montrer tout de suite."""
    _simuler(monkeypatch, {"https://exemple.fr/collections/complements-sommeil"}, [{"URL": ADRESSE, "Impressions": 40}])
    r = watch.veille_site("exemple", _site(), _ControleurHTTPFactice({ADRESSE: 403}), lambda m: None, AUJOURD_HUI)
    assert r["a_rediriger"] == [] and "réponse bloquée" in r["anomalies"][0]
    r = watch.veille_site("exemple", _site(), _ControleurHTTPFactice({ADRESSE: 404}), lambda m: None, AUJOURD_HUI)
    assert [d["adresse"] for d in r["a_rediriger"]] == [ADRESSE] and r["anomalies"] == []


def test_erreur_confirmee_pas_retestee_le_meme_jour(monkeypatch):
    _simuler(monkeypatch, {"https://exemple.fr/collections/complements-sommeil"}, [{"URL": ADRESSE, "Impressions": 40}])
    watch.veille_site("exemple", _site(), _ControleurHTTPFactice({ADRESSE: 404}), lambda m: None, AUJOURD_HUI)

    class _Interdit:
        def controler(self, url):
            raise AssertionError("adresse retestée")
    r = watch.veille_site("exemple", _site(), _Interdit(), lambda m: None, AUJOURD_HUI)
    assert len(r["a_rediriger"]) == 1


def test_analyse_d_un_seul_site_garde_les_autres(monkeypatch):
    for cle in ("a", "b"):
        config.ajouter_site(cle, nom=cle + ".fr", propriete="sc-domain:%s.fr" % cle,
                            sitemaps=["https://%s.fr/sitemap.xml" % cle])
    watch._ecrire_json(watch.chemin_etat(), {"a": {"statut": "ok", "date": "2026-01-01T09:00"},
                                             "b": {"statut": "ok", "date": "2026-01-01T09:00"}})
    jour = os.path.join(config.dossier_config(), "veille_%s.json" % AUJOURD_HUI)
    watch._ecrire_json(jour, {"date": AUJOURD_HUI, "resultats": [{"site": "a"}, {"site": "b"}], "echecs": {},
                              "reportes": []})
    analyses = []

    def veille_site(cle, cfg, controleur, journal, aujourd_hui=None, etape=None):
        analyses.append(cle)
        return {"site": cle, "fin_gsc": FIN, "a_rediriger": [], "anomalies": ["incomplet"], "infos": [],
                "resolues": []}
    monkeypatch.setattr(watch, "veille_site", veille_site)
    from veille_ia import plateforme
    monkeypatch.setattr(plateforme, "notifier", lambda *a, **k: True)
    watch.executer(interactif=True, cles=["b"])
    assert analyses == ["b"]
    etat = watch.lire_etat()
    assert etat["a"]["statut"] == "ok" and etat["a"]["date"] == "2026-01-01T09:00"
    assert etat["b"]["statut"] == "incomplet"
    assert [r["site"] for r in watch._lire_json(jour, {})["resultats"]] == ["a", "b"]


# --- annulation (bouton Annuler de l'interface) ---
def _trois_sites_deja_analyses():
    for cle in ("a", "b", "c"):
        config.ajouter_site(cle, nom=cle + ".fr", propriete="sc-domain:%s.fr" % cle,
                            sitemaps=["https://%s.fr/sitemap.xml" % cle])
    ancien = {cle: {"statut": "ok", "date": "2026-01-01T09:00"} for cle in ("a", "b", "c")}
    watch._ecrire_json(watch.chemin_etat(), ancien)
    return ancien


def test_annulation_entre_deux_sites_garde_l_etat_des_suivants(monkeypatch):
    ancien = _trois_sites_deja_analyses()
    analyses = []

    def veille_site(cle, cfg, controleur, journal, aujourd_hui=None, etape=None):
        analyses.append(cle)
        assert watch.demander_annulation()           # clic sur Annuler pendant le premier site
        return {"site": cle, "fin_gsc": FIN, "a_rediriger": [], "anomalies": [], "infos": [], "resolues": []}
    monkeypatch.setattr(watch, "veille_site", veille_site)
    from veille_ia import plateforme
    envois = []
    monkeypatch.setattr(plateforme, "notifier", lambda *a, **k: envois.append(a) or True)
    r = watch.executer()
    assert r["annulee"] and len(analyses) == 1
    etat = watch.lire_etat()
    assert etat[analyses[0]]["date"] != ancien[analyses[0]]["date"]          # site fini : mis à jour
    for cle in {"a", "b", "c"} - set(analyses):
        assert etat[cle] == ancien[cle]                                        # les autres : inchangés
    derniere = json.load(open(os.path.join(config.dossier_config(), "derniere_execution.json"), encoding="utf-8"))
    assert derniere["annulee"] is True and derniere["echecs"] == {}
    assert not watch.analyse_en_cours() and not watch.annulation_demandee()
    assert envois == []


def test_annulation_pendant_un_site_ne_le_range_ni_en_probleme_ni_en_rien_a_corriger(monkeypatch):
    """Arrêté au milieu de ses tests HTTP, le site garde son état précédent."""
    config.ajouter_site("exemple", nom="exemple.fr", propriete="sc-domain:exemple.fr",
                        sitemaps=["https://exemple.fr/sitemap.xml"])
    ancien = {"statut": "a_corriger", "date": "2026-01-01T09:00", "a_rediriger": [
        {"cle": "x", "chemin": "/x", "adresse": "https://exemple.fr/x", "impressions": 20, "cible_url": "",
         "cible_proposee": "", "sure": False, "ressemblance": 0.2}]}
    watch._ecrire_json(watch.chemin_etat(), {"exemple": ancien})
    autre = "https://exemple.fr/collections/autre-invention"
    _simuler(monkeypatch, {"https://exemple.fr/collections/complements-sommeil"},
             [{"URL": ADRESSE, "Impressions": 40}, {"URL": autre, "Impressions": 40}])
    testees = []

    def controler(self, url):
        testees.append(url)
        watch.demander_annulation()
        return {"code": 404, "finale": url}
    monkeypatch.setattr("veille_ia.http_check.ControleurHTTP.controler", controler)
    r = watch.executer(interactif=True)
    assert r["annulee"] and r["echecs"] == {} and r["resultats"] == []
    assert len(testees) == 1                                    # la seconde adresse n'est pas testée
    assert watch.lire_etat()["exemple"] == ancien


def test_inspections_pas_encore_parties_abandonnees_apres_l_annulation(monkeypatch):
    config.ajouter_site("exemple", nom="exemple.fr", propriete="sc-domain:exemple.fr",
                        sitemaps=["https://exemple.fr/sitemap.xml"])
    inventees = ["https://exemple.fr/blogs/news/invention-%d" % i for i in range(60)]
    _simuler(monkeypatch, {"https://exemple.fr/blogs/news/vraie-page"},
             [{"URL": u, "Impressions": 40} for u in inventees])
    inspections = []

    def inspecter(chemin, url, propriete):
        inspections.append(url)
        watch.demander_annulation()
        return {"url": url, "http": 200, "coverage": gsc_api.INCONNUE}
    monkeypatch.setattr(gsc_api, "inspecter", inspecter)
    r = watch.executer(interactif=True)
    assert r["annulee"] and r["echecs"] == {}
    assert 1 <= len(inspections) <= 6                           # au plus les 6 déjà parties
    assert "exemple" not in watch.lire_etat()


def test_demande_d_annulation_restee_n_arrete_pas_l_analyse_suivante(monkeypatch):
    _trois_sites_deja_analyses()
    open(watch.chemin_annulation(), "w").close()                  # clic juste après la fin d'une analyse
    monkeypatch.setattr(watch, "veille_site", lambda cle, cfg, controleur, journal, aujourd_hui=None, etape=None: {
        "site": cle, "fin_gsc": FIN, "a_rediriger": [], "anomalies": [], "infos": [], "resolues": []})
    r = watch.executer(interactif=True)
    assert not r["annulee"] and len(r["resultats"]) == 3


def test_rien_a_annuler_sans_analyse_en_cours():
    assert watch.demander_annulation() is False
    assert not watch.annulation_demandee()


def test_annulation_d_une_partie_des_sites_garde_les_resultats_du_jour(monkeypatch):
    _trois_sites_deja_analyses()

    def veille_site(cle, cfg, controleur, journal, aujourd_hui=None, etape=None):
        return {"site": cle, "fin_gsc": FIN, "a_rediriger": [], "anomalies": [], "infos": [], "resolues": []}
    monkeypatch.setattr(watch, "veille_site", veille_site)
    watch.executer(interactif=True)
    jour = os.path.join(config.dossier_config(), "veille_%s.json" % AUJOURD_HUI)
    assert sorted(r["site"] for r in json.load(open(jour, encoding="utf-8"))["resultats"]) == ["a", "b", "c"]

    def veille_site_puis_annuler(cle, cfg, controleur, journal, aujourd_hui=None, etape=None):
        watch.demander_annulation()
        return veille_site(cle, cfg, controleur, journal, aujourd_hui, etape)
    monkeypatch.setattr(watch, "veille_site", veille_site_puis_annuler)
    assert watch.executer(interactif=True)["annulee"]
    assert sorted(r["site"] for r in json.load(open(jour, encoding="utf-8"))["resultats"]) == ["a", "b", "c"]


def _sans_reseau(monkeypatch):
    monkeypatch.setattr("veille_ia.http_check.ControleurHTTP.controler", lambda self, url: pytest.fail("réseau"))
    monkeypatch.setattr("veille_ia.http_check.ControleurHTTP.lire_titres", lambda self, url: pytest.fail("réseau"))


@pytest.mark.parametrize("fichier_efface", [False, True])
def test_inspections_annulees_jamais_lues_comme_un_site_complet(monkeypatch, fichier_efface):
    """Même si la demande disparaît avant la fin des inspections (fin d'une autre analyse),
    les adresses pas vérifiées ne laissent pas conclure à rien à corriger."""
    config.ajouter_site("exemple", nom="exemple.fr", propriete="sc-domain:exemple.fr",
                        sitemaps=["https://exemple.fr/sitemap.xml"])
    ancien = {"statut": "incomplet", "date": "2026-01-01T09:00", "anomalies": ["x"]}
    watch._ecrire_json(watch.chemin_etat(), {"exemple": ancien})
    inventees = ["https://exemple.fr/blogs/news/invention-%d" % i for i in range(30)]
    _simuler(monkeypatch, {"https://exemple.fr/blogs/news/vraie-page"},
             [{"URL": u, "Impressions": 40} for u in inventees])
    _sans_reseau(monkeypatch)
    premiere = []

    def inspecter(chemin, url, propriete):
        if not premiere:
            premiere.append(url)
            watch.demander_annulation()
            if fichier_efface:
                __import__("time").sleep(0.2)            # les autres fils voient la demande
                os.remove(watch.chemin_annulation())
        return {"url": url, "http": 200, "coverage": "Envoyée et indexée"}
    monkeypatch.setattr(gsc_api, "inspecter", inspecter)
    r = watch.executer(interactif=True)
    assert r["annulee"] and r["echecs"] == {}
    assert watch.lire_etat()["exemple"] == ancien


def test_annulation_pendant_la_lecture_du_plan_de_site(monkeypatch):
    ancien = _trois_sites_deja_analyses()
    _simuler(monkeypatch, {"https://a.fr/page"}, [{"URL": "https://a.fr/page", "Impressions": 40}])
    _sans_reseau(monkeypatch)
    monkeypatch.setattr(sitemap, "plan_de_site", lambda racines, journal, strict=False, verifier=None: (
        watch.demander_annulation(), verifier())[1])
    r = watch.executer(interactif=True)
    assert r["annulee"] and r["resultats"] == [] and r["echecs"] == {}
    assert watch.lire_etat() == ancien


def test_annulation_pendant_la_lecture_des_titres(monkeypatch):
    config.ajouter_site("exemple", nom="exemple.fr", propriete="sc-domain:exemple.fr",
                        sitemaps=["https://exemple.fr/sitemap.xml"])
    _simuler(monkeypatch, PLAN_BLOG, [{"URL": INVENTEE, "Impressions": 40}])
    monkeypatch.setattr("veille_ia.http_check.ControleurHTTP.controler",
                        lambda self, url: {"code": 404, "finale": url})
    lus = []

    def lire_titres(self, url):
        lus.append(url)
        watch.demander_annulation()
        return None
    monkeypatch.setattr("veille_ia.http_check.ControleurHTTP.lire_titres", lire_titres)
    r = watch.executer(interactif=True)
    assert r["annulee"] and len(lus) == 1
    assert "exemple" not in watch.lire_etat()


def test_analyse_planifiee_annulee_previent_des_sites_finis(monkeypatch):
    """Aucune alerte perdue : le site fini avant l'annulation est notifié et retenu comme
    signalé, les sites suivants ne sont pas touchés."""
    _trois_sites_deja_analyses()
    analyses = []

    def veille_site(cle, cfg, controleur, journal, aujourd_hui=None, etape=None):
        analyses.append(cle)
        watch.demander_annulation()
        return {"site": cle, "fin_gsc": FIN, "anomalies": [], "infos": [], "resolues": [], "a_rediriger": [
            {"cle": "blogs/x", "chemin": "/blogs/x", "adresse": "https://%s.fr/blogs/x" % cle, "impressions": 20,
             "cible_url": "", "cible_proposee": "", "sure": False, "ressemblance": 0.2}]}
    monkeypatch.setattr(watch, "veille_site", veille_site)
    from veille_ia import plateforme
    envois = []
    monkeypatch.setattr(plateforme, "notifier", lambda *a, **k: envois.append(a) or True)
    r = watch.executer()
    assert r["annulee"] and len(analyses) == 1 and len(envois) == 1
    fini = analyses[0]
    alertees = os.path.join(config.dossier_site(fini), "veille_deja_alertees.json")
    assert json.load(open(alertees, encoding="utf-8")) == ["blogs/x"]
    for cle in {"a", "b", "c"} - {fini}:
        assert not os.path.exists(os.path.join(config.dossier_site(cle), "veille_deja_alertees.json"))
    assert r["rapport"] and os.path.exists(r["rapport"])
