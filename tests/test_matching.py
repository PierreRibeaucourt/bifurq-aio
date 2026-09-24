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
