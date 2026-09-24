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


def test_mes_sites_dit_qu_on_peut_fermer_l_onglet_et_quand_l_analyse_tourne():
    html = pages.tableau_de_bord(SITES, ETAT, False, None, dict(PLANIF, actif_heure_fixe=True, heure_fixe="08:30"), "j")
    assert "Vous pouvez fermer cet onglet." in html
    assert "à chaque démarrage de l'ordinateur et chaque jour à 08:30" in html
    assert "raccourci <b>Bifurq AIO</b> sur votre bureau" in html
    arretee = pages.tableau_de_bord(SITES, ETAT, False, None, dict(PLANIF, active=False), "j")
    assert "aucune analyse ne se lance toute seule" in arretee and "même onglet fermé" not in arretee


def test_site_deja_suivi_grise_dans_le_choix():
    html = pages.choisir([{"propriete": "sc-domain:a.fr", "nom": "a.fr"}, {"propriete": "sc-domain:c.fr", "nom": "c.fr"}],
                         {"sc-domain:a.fr"}, False, PLANIF, "j")
    assert 'class="choix inactif"' in html and "Déjà surveillé" in html


def test_bouton_et_reglages_dans_la_barre_fixe_sous_la_liste():
    html = pages.choisir([{"propriete": "sc-domain:c.fr", "nom": "c.fr"}], set(), True, PLANIF, "j")
    barre = html[html.index('class="barre-fixe"'):]
    assert "Lancer la surveillance" in barre and 'name="au_demarrage"' in barre and "Réglages avancés" in barre
    assert html.index('value="sc-domain:c.fr"') < html.index('class="barre-fixe"')
    fenetre = html[html.index('<dialog id="reglages"'):html.index("</dialog>")]    # réglages dans une fenêtre
    assert 'name="seuil"' in fenetre and 'name="dataforseo_login"' in fenetre
    assert "</form>" not in fenetre and html.index("</dialog>") < html.index("</form>")    # envoyés avec le reste


def test_champ_de_recherche_seulement_pour_une_longue_liste_et_hors_du_formulaire():
    beaucoup = [{"propriete": "sc-domain:s%d.fr" % i, "nom": "s%d.fr" % i} for i in range(pages.SEUIL_RECHERCHE + 1)]
    html = pages.choisir(beaucoup, set(), False, PLANIF, "j")
    assert html.index('type="search"') < html.index('<form class="choisir"')    # Entrée n'envoie rien
    assert 'data-nom="s0.fr sc-domain:s0.fr"' in html
    peu = beaucoup[:pages.SEUIL_RECHERCHE]
    assert 'type="search"' not in pages.choisir(peu, set(), False, PLANIF, "j")


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


def test_auteur_en_bas_de_mes_sites():
    html = pages.tableau_de_bord(SITES, ETAT, False, None, PLANIF, "j")
    assert html.rindex("carte-site") < html.index('class="auteur"')          # après les sites
    assert 'href="https://www.linkedin.com/in/pierre-ribeaucourt/" target="_blank" rel="noopener"' in html


def test_consigne_masquee_laisse_le_rappel_des_analyses_sous_le_titre():
    html = pages.tableau_de_bord(SITES, ETAT, False, None, PLANIF, "j", consigne=False)
    assert "Vous pouvez fermer cet onglet." not in html
    assert "Analyse automatique à chaque démarrage de l&#x27;ordinateur." in html and 'href="/reglages">Changer' in html
    assert 'action="/masquer-consigne"' in pages.tableau_de_bord(SITES, ETAT, False, None, PLANIF, "j")


def test_lien_vers_le_site_de_l_outil_en_bas_de_chaque_page():
    ecrans = [pages.accueil(), pages.tableau_de_bord(SITES, ETAT, False, None, PLANIF, "j"),
              pages.page_modifier("a", dict(SITES["a"], sitemaps=[]), "j"), pages.reglages(PLANIF, "j"),
              pages.choisir([], set(), True, PLANIF, "j"), pages.erreur("Titre", "Message")]
    for html in ecrans:
        pied = html[html.index('<footer class="pied-outil">'):]
        assert html.index("</main>") < html.index('<footer class="pied-outil">')
        assert 'href="https://pierreribeaucourt.github.io/bifurq-aio/" target="_blank" rel="noopener"' in pied
        assert "Bifurq AIO" in pied


def test_mise_a_jour_attendue_a_la_fin_de_l_analyse():
    maj = {"version": "9.9.9", "nouveautes": "Plus rapide."}
    pendant = pages.tableau_de_bord(SITES, ETAT, True, None, PLANIF, "j", maj=maj)
    assert '<button class="bouton" type="submit" disabled>Mettre à jour</button>' in pendant
    apres = pages.tableau_de_bord(SITES, ETAT, False, None, PLANIF, "j", maj=maj)
    assert '<button class="bouton" type="submit">Mettre à jour</button>' in apres
    assert "Mettre à jour" not in pages.tableau_de_bord(SITES, ETAT, False, None, PLANIF, "j")


def test_page_d_attente_recharge_la_nouvelle_version():
    html = pages.mise_a_jour_en_cours("9.9.9", "123")
    assert 'var ancienne="123",version="9.9.9"' in html and 'fetch("/ping"' in html
    assert 'id="lent" hidden' in html
    for interdit in ("«", "»", "—", "–"):
        assert interdit not in html
