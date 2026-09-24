import os

from veille_ia import report

SITES = {"exemple": {"nom": "exemple.fr"}, "autre": {"nom": "autre<site>.fr"}}


def _adresse(cle="collections/x", cible="https://exemple.fr/collections/y", sure=True):
    return {"cle": cle, "chemin": "/" + cle, "adresse": "https://exemple.fr/" + cle, "impressions": 40,
            "impressions_7j": 5, "cible_url": cible, "cible_proposee": "/collections/y" if cible else "",
            "sure": sure, "ressemblance": 0.8}


def test_panneau_par_statut():
    assert 'aria-label="Tout va bien"' in report.panneau({"statut": "ok"})
    assert '"2 adresses à corriger"' in report.panneau({"statut": "a_corriger",
                                                         "a_rediriger": [_adresse(), _adresse("b")]})
    assert '"1 adresse à corriger"' in report.panneau({"statut": "a_corriger", "a_rediriger": [_adresse()]})
    assert '"Problème"' in report.panneau({"statut": "probleme"})
    assert '"Pas encore analysé"' in report.panneau({})
    assert '"Analyse en cours"' in report.panneau({"statut": "ok"}, en_cours=True)


def test_date_longue():
    assert report.date_longue("2026-09-24T10:31") == "24 septembre 2026"
    assert report.date_longue("2026-10-01T08:00") == "1er octobre 2026"


def test_resume_affiche_le_message_du_probleme():
    html = report.resume({"statut": "probleme", "message": "La connexion à votre compte Google a expiré."})
    assert "La connexion à votre compte Google a expiré." in html


def test_tableau_une_ligne_par_adresse_triee_par_vues():
    peu, beaucoup = _adresse("peu"), _adresse("beaucoup")
    peu["impressions"], beaucoup["impressions"] = 2, 90
    html = report.tableau_adresses({"a_rediriger": [peu, beaucoup]})
    assert html.count("<tr") == 3                       # en-tête et deux lignes
    assert html.index("/beaucoup") < html.index("/peu")


def test_tableau_cible_sure_a_verifier_ou_absente():
    html = report.tableau_adresses({"a_rediriger": [_adresse("a"), _adresse("b", sure=False), _adresse("c", cible="")]})
    assert "Sûre" in html and "À vérifier" in html and "Aucune page similaire" in html


def test_tableau_du_rapport_sans_copie_ni_action():
    html = report.tableau_adresses({"a_rediriger": [_adresse()]})
    assert "data-copier" not in html and 'class="c-action"' not in html
    assert "data-csv=" in html                          # l'export marche aussi depuis le fichier


def test_tableau_de_l_interface_avec_copie_et_action():
    html = report.tableau_adresses({"a_rediriger": [_adresse()]}, lambda d: "<b>ACTION</b>")
    assert 'data-copier="/collections/x"' in html and "<b>ACTION</b>" in html


def test_adresse_longue_coupee_au_milieu_mais_entiere_au_survol():
    chemin = "actualite/prix-damenagement-dune-voiture-pour-une-personne-handicapee"
    html = report.tableau_adresses({"a_rediriger": [_adresse(chemin)]})
    assert '<span class="fin">-personne-handicapee</span>' in html
    assert 'title="/%s"' % chemin in html


def test_export_csv_pour_excel():
    peu, beaucoup, sans = _adresse("peu"), _adresse("beaucoup", sure=False), _adresse("sans", cible="")
    peu["impressions"], beaucoup["impressions"], sans["impressions"] = 2, 90, 5
    lignes = report.csv_adresses({"a_rediriger": [peu, beaucoup, sans]}).splitlines()
    assert lignes[0] == "Adresse inventée;Rediriger vers;Confiance;Vues (7 jours)"
    assert lignes[1:] == ["/beaucoup;/collections/y;À vérifier;90", "/sans;;Aucune page similaire;5",
                          "/peu;/collections/y;Sûre;2"]


def test_export_nom_de_fichier():
    assert report.nom_fichier_export("exemple.fr", "2026-09-24T10:18") == \
        "adresses-inventees_exemple.fr_2026-09-24.csv"
    assert report.nom_fichier_export("Mon Site / Boutique", "2026-09-24T10:18") == \
        "adresses-inventees_mon-site-boutique_2026-09-24.csv"


def test_rapport_titre_date_en_toutes_lettres():
    html = report.rendre({}, SITES, "2026-09-24T10:31")
    assert "Rapport du 24 septembre 2026" in html and "du aujourd" not in html


def test_adresse_encodee_affichee_decodee():
    d = _adresse("financement/5000-%E2%82%AC")
    html = report.tableau_adresses({"a_rediriger": [d]})
    assert "5000-€" in html


def test_rendre_echappe_le_html():
    etat = {"exemple": {"statut": "a_corriger", "a_rediriger": [_adresse("<script>")], "date": "2026-09-24T10:00"}}
    html = report.rendre(etat, SITES, "2026-09-24T10:00")
    assert html.count("<script>") == 1                  # le seul script est celui de l'export
    assert "&lt;script&gt;" in html
    assert "autre&lt;site&gt;.fr" in html


def test_rendre_marque_les_nouvelles():
    etat = {"exemple": {"statut": "a_corriger", "a_rediriger": [_adresse()], "nouvelles": ["collections/x"]}}
    assert '<span class="tag nouveau">Nouvelle</span>' in report.rendre(etat, SITES, "2026-09-24T10:00")


def test_rapport_fichier_sans_liens_vers_le_serveur():
    html = report.rendre({}, SITES, "2026-09-24T10:00")
    assert 'href="/reglages"' not in html and 'href="/"' not in html


def test_aucun_guillemet_francais_ni_tiret_cadratin():
    etat = {"exemple": {"statut": "a_corriger", "a_rediriger": [_adresse(), _adresse("b", cible="")],
                        "anomalies": ["x"], "infos": ["y"], "date": "2026-09-24T10:00"}}
    html = report.rendre(etat, SITES, "2026-09-24T10:00")
    for interdit in ("«", "»", "—", "–"):
        assert interdit not in html


def test_ecrire_cree_rapport_et_archive(tmp_path):
    chemin = report.ecrire(str(tmp_path), report.rendre({}, SITES, "2026-09-24T10:00"), "2026-09-24")
    assert os.path.exists(chemin)
    assert os.path.exists(os.path.join(str(tmp_path), "rapports", "rapport_2026-09-24.html"))


def test_ecrire_purge_au_dela_de_l_historique(tmp_path):
    for i in range(5):
        report.ecrire(str(tmp_path), "<html></html>", "2026-09-%02d" % (i + 1), garder_historique=2)
    assert len(os.listdir(os.path.join(str(tmp_path), "rapports"))) == 2


def test_rapport_presente_l_auteur():
    html = report.rendre({}, SITES, "2026-09-24T10:31")
    assert "Pierre Ribeaucourt" in html and "linkedin.com/in/pierre-ribeaucourt" in html


def test_lien_d_aide_sous_le_message_de_protection_seulement():
    html = report.resume({"statut": "incomplet", "protection": "Cloudflare",
                          "anomalies": ["Votre site bloque l'outil (protection anti-robots Cloudflare) : ...",
                                        "Google n'a pas pu vérifier 2 adresses aujourd'hui."]})
    assert html.count("fonctionnement.html#site-protege") == 1
    assert html.index("Cloudflare) : ...") < html.index("#site-protege") < html.index("Google n&#x27;a pas pu")
    assert "#site-protege" not in report.resume({"statut": "incomplet", "anomalies": ["Autre chose."]})


def test_analyse_incomplete_ne_dit_pas_que_tout_est_verifie():
    html = report.resume({"statut": "incomplet", "anomalies": ["2 adresses n'ont pas pu être testées."]})
    assert "Aucune adresse inventée confirmée pour l'instant." in html
    assert "à corriger" not in html


def test_rapport_renvoie_vers_le_site_de_l_outil():
    html = report.rendre({"exemple": {"statut": "ok", "date": "2026-09-24T10:00"}}, SITES, "2026-09-24T10:00")
    assert 'href="https://pierreribeaucourt.github.io/bifurq-aio/"' in html
