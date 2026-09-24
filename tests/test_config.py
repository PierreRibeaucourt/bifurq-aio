import os

import pytest

from veille_ia import config


@pytest.fixture(autouse=True)
def _racine_isolee(tmp_path, monkeypatch):
    """Chaque test lit/écrit dans un dossier temporaire, jamais le vrai config/ du
    poste : un test ne doit jamais pouvoir toucher un jeton ou un réglage réel."""
    monkeypatch.setattr(config, "racine", lambda: str(tmp_path))


def test_lire_sans_fichier_rend_le_defaut():
    donnees = config.lire()
    assert donnees["sites"] == {}
    assert donnees["planification"]["au_demarrage"] is True
    assert donnees["planification"]["active"] is True


def test_ajouter_puis_relire_site():
    config.ajouter_site("exemple", nom="exemple.fr", propriete="sc-domain:exemple.fr",
                        sitemaps=["https://exemple.fr/sitemap.xml"], seuil_impressions=20)
    site = config.lire()["sites"]["exemple"]
    assert site["propriete"] == "sc-domain:exemple.fr"
    assert site["seuil_impressions"] == 20


def test_retirer_site_efface_ses_donnees_et_son_jeton():
    config.ajouter_site("exemple", nom="exemple.fr", propriete="sc-domain:exemple.fr",
                        sitemaps=["https://exemple.fr/sitemap.xml"])
    open(config.chemin_jeton("exemple"), "w").write("{}")
    config.retirer_site("exemple")
    assert "exemple" not in config.lire()["sites"]
    assert not os.path.exists(os.path.join(config.dossier_config(), "exemple"))


def test_definir_planification_refuse_les_deux_desactives():
    with pytest.raises(ValueError):
        config.definir_planification(False, False, "09:15")


def test_desactiver_puis_reactiver_planification():
    config.definir_planification(True, False, "09:15")
    config.desactiver_planification()
    assert config.lire()["planification"]["active"] is False
    config.definir_planification(False, True, "08:00")
    p = config.lire()["planification"]
    assert p["active"] is True and p["actif_heure_fixe"] is True and p["heure_fixe"] == "08:00"


def test_ecartees_cumulent_sans_doublon():
    config.ajouter_ecartee("exemple", "collections/sommeil")
    config.ajouter_ecartee("exemple", "collections/stress")
    config.ajouter_ecartee("exemple", "collections/sommeil")
    assert config.lire_ecartees("exemple") == {"collections/sommeil", "collections/stress"}


def test_ecriture_atomique_pas_de_tmp_residuel():
    config.ecrire(config.lire())
    assert not os.path.exists(config.chemin_sites_json() + ".tmp")
