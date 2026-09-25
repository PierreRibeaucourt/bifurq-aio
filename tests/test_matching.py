from veille_ia import matching


def test_plie_accents_et_ponctuation():
    assert matching.plie("Compléments Alimentaires : Sommeil !") == "complements-alimentaires-sommeil"


def test_plie_url_encodee():
    assert matching.plie("compl%C3%A9ments") == "complements"


def test_ressemblance_identique_vaut_un():
    assert matching.ressemblance("magnesium-bisglycinate", "magnesium-bisglycinate") == 1.0


def test_ressemblance_deformation_ai_overview():
    """Cas réel de la catégorie de bug visée : un mot sauté par l'IA."""
    r_bonne = matching.ressemblance("aliments-a-eviter-sommeil", "aliments-a-eviter-pour-mieux-dormir")
    r_mauvaise = matching.ressemblance("aliments-a-eviter-sommeil", "magnesium-bisglycinate")
    assert r_bonne > r_mauvaise


def test_recouvrement_mots_tolere_une_faute_de_frappe():
    # ok/max(len(a), len(b)) : les 2 mots de a sont dans b (4 mots) -> 2/4
    assert matching.recouvrement_mots("berberine-bio", "berberine-bio-30-gelules") == 0.5
    assert matching.recouvrement_mots("berberine-bio", "berberine-bio") == 1.0
    assert matching.recouvrement_mots("berberine-bio", "nac-acetylcysteine") == 0.0


def test_recouvrement_mots_vide():
    assert matching.recouvrement_mots("", "quelque-chose") == 0.0
    assert matching.recouvrement_mots("quelque-chose", "") == 0.0


def test_textes_de_page_titre_partage_et_premier_h1():
    page = ('<html><head><title>Dette de sommeil : d&eacute;finition | Mon site</title>'
            '<meta content="Titre de partage" property="og:title"></head>'
            '<body><nav><a>Menu</a></nav><h1>Dette <em>de</em>\n  sommeil</h1><h1>Autre</h1></body></html>')
    assert matching.textes_de_page(page) == ["Dette de sommeil : définition | Mon site", "Dette de sommeil : définition",
                                             "Titre de partage", "Dette de sommeil"]


def test_textes_de_page_sans_titre_ni_html():
    assert matching.textes_de_page("") == []
    assert matching.textes_de_page("<title>Vitamine B12 - effet immédiat</title>") == [
        "Vitamine B12 - effet immédiat", "Vitamine B12"]


def test_adresse_fabriquee_a_partir_du_titre_de_la_page():
    """Cas réels du 25.09.2026 : l'IA de Google reprend le titre ou le h1 de la vraie page,
    que l'adresse de la page ne laisse pas deviner."""
    cas = (("dette-de-sommeil-definition-calcul-et-solutions-durales", "dette-de-sommeil",
            ["Dette de sommeil : définition, calcul et solutions durables"]),
           ("ginseng-bienfaits-et-selon-la-science", "ginseng-bienfaits-et-contre-indications",
            ["Ginseng : Bienfaits et contre-indications selon la science"]),
           ("sommeil-et-alimentation-que-manger-le-soir-pour-bien-dormir-aliments-a-privilegier",
            "sommeil-et-alimentation", ["Que manger le soir pour bien dormir ?",
                                        "Sommeil et alimentation : que manger le soir pour bien dormir ?"]))
    for inventee, slug_page, textes in cas:
        assert matching.ressemblance(inventee, slug_page) < 0.6
        assert matching.ressemblance_page(inventee, slug_page, textes) >= 0.75
    # sans titres, rien ne change
    assert matching.ressemblance_page("vitamine-b9", "stress-vitamine-b9") == matching.ressemblance(
        "vitamine-b9", "stress-vitamine-b9")
