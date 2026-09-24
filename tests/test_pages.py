from veille_ia.installer import pages

SITES = {"a": {"nom": "a.fr", "propriete": "sc-domain:a.fr"}, "b": {"nom": "b.fr", "propriete": "sc-domain:b.fr"}}
ETAT = {"a": {"statut": "ok", "date": "2026-09-24T10:00"}, "b": {"statut": "ok", "date": "2026-09-24T10:00"}}
PLANIF = {"active": True, "au_demarrage": True, "actif_heure_fixe": False, "heure_fixe": "09:15"}


def test_seul_le_site_analyse_affiche_en_cours():
    html = pages.tableau_de_bord(SITES, ETAT, True, {"site": "b.fr", "etape": "Lecture du plan de site"}, PLANIF, "j")
    assert html.count('aria-label="Analyse en cours"') == 1
    assert html.count('aria-label="Tout va bien"') == 1
    assert "b.fr, lecture du plan de site" in html


def test_analyse_en_cours_bouton_desactive():
    html = pages.tableau_de_bord(SITES, ETAT, True, None, PLANIF, "j")
    assert "disabled" in html and "Analyser maintenant" not in html


def test_site_deja_suivi_grise_dans_le_choix():
    html = pages.choisir([{"propriete": "sc-domain:a.fr", "nom": "a.fr"}, {"propriete": "sc-domain:c.fr", "nom": "c.fr"}],
                         {"sc-domain:a.fr"}, False, PLANIF, "j")
    assert 'class="choix inactif"' in html and "Déjà surveillé" in html


def test_reglages_surveillance_arretee():
    html = pages.reglages(dict(PLANIF, active=False), "j")
    assert "La surveillance automatique est arrêtée." in html and "Arrêter la surveillance" not in html


def test_dataforseo_range_dans_les_reglages_avances():
    html = pages.page_modifier("a", dict(SITES["a"], sitemaps=[]), "j")
    assert html.index('<details class="avance">') < html.index('name="dataforseo_login"')


def test_aucun_guillemet_francais_ni_tiret_cadratin():
    ecrans = [pages.accueil(), pages.tableau_de_bord(SITES, ETAT, False, None, PLANIF, "j"),
              pages.page_modifier("a", dict(SITES["a"], sitemaps=[]), "j"), pages.reglages(PLANIF, "j"),
              pages.choisir([], set(), True, PLANIF, "j"), pages.erreur("Titre", "Message")]
    for html in ecrans:
        for interdit in ("«", "»", "‹", "›", "—", "–"):
            assert interdit not in html
