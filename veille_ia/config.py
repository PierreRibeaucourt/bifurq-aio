# -*- coding: utf-8 -*-
"""Configuration utilisateur : config/sites.json (jamais versionné), plus un dossier
par site pour son jeton et ses caches. Rien ici n'est écrit à la main par
l'utilisateur : la page de gestion de l'installateur web lit et écrit ce fichier."""
import datetime
import io
import json
import os

VERSION = 1
DEFAUT = {"version": VERSION,
          "planification": {"active": True, "au_demarrage": True, "actif_heure_fixe": False, "heure_fixe": "09:15"},
          "sites": {}}


def racine():
    """Dossier racine du dépôt (parent du paquet veille_ia)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def dossier_config():
    d = os.path.join(racine(), "config")
    os.makedirs(d, exist_ok=True)
    return d


def chemin_sites_json():
    return os.path.join(dossier_config(), "sites.json")


def dossier_site(cle):
    d = os.path.join(dossier_config(), cle)
    os.makedirs(d, exist_ok=True)
    return d


def chemin_jeton(cle):
    return os.path.join(dossier_site(cle), "jeton_gsc.json")


def lire():
    p = chemin_sites_json()
    if not os.path.exists(p):
        return json.loads(json.dumps(DEFAUT))      # copie profonde
    donnees = json.load(io.open(p, encoding="utf-8-sig"))
    donnees.setdefault("planification", dict(DEFAUT["planification"]))
    donnees.setdefault("sites", {})
    return donnees


def ecrire(donnees):
    p = chemin_sites_json()
    tmp = p + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(json.dumps(donnees, ensure_ascii=False, indent=1))
    os.replace(tmp, p)


def ajouter_site(cle, nom, propriete, sitemaps, seuil_impressions=15, dataforseo=None):
    donnees = lire()
    donnees["sites"][cle] = {
        "nom": nom, "propriete": propriete, "sitemaps": list(sitemaps),
        "seuil_impressions": seuil_impressions, "jeton": "%s/jeton_gsc.json" % cle,
        "dataforseo": dataforseo, "ajoute_le": datetime.date.today().isoformat()}
    ecrire(donnees)
    return donnees["sites"][cle]


_INCHANGE = object()


def modifier_site(cle, nom, sitemaps, seuil_impressions, dataforseo=_INCHANGE):
    """dataforseo : {"login", "password"}, None pour les retirer, ou omis pour les garder."""
    donnees = lire()
    site = donnees["sites"][cle]
    site["nom"] = nom.strip() or site["nom"]
    site["sitemaps"] = [s.strip() for s in sitemaps if s.strip()] or site["sitemaps"]
    site["seuil_impressions"] = max(1, int(seuil_impressions))
    if dataforseo is not _INCHANGE:
        site["dataforseo"] = dataforseo
    ecrire(donnees)
    return site


def retirer_site(cle):
    """Retire le site et efface ses données locales, jeton Google compris."""
    import shutil
    donnees = lire()
    donnees["sites"].pop(cle, None)
    ecrire(donnees)
    d = os.path.join(dossier_config(), cle)
    if cle and os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)


def definir_planification(au_demarrage, actif_heure_fixe, heure_fixe):
    if not au_demarrage and not actif_heure_fixe:
        raise ValueError("Cochez au moins un moment de vérification.")
    donnees = lire()
    donnees["planification"] = {"active": True, "au_demarrage": bool(au_demarrage),
                                "actif_heure_fixe": bool(actif_heure_fixe), "heure_fixe": heure_fixe}
    ecrire(donnees)
    return donnees["planification"]


def desactiver_planification():
    donnees = lire()
    donnees["planification"]["active"] = False
    ecrire(donnees)


def lire_ecartees(cle):
    return set(json.load(io.open(os.path.join(dossier_site(cle), "ecartees.json"), encoding="utf-8-sig"))) \
        if os.path.exists(os.path.join(dossier_site(cle), "ecartees.json")) else set()


def ajouter_ecartee(cle, chemin_page):
    p = os.path.join(dossier_site(cle), "ecartees.json")
    ecartees = sorted(lire_ecartees(cle) | {chemin_page})
    tmp = p + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(json.dumps(ecartees, ensure_ascii=False, indent=1))
    os.replace(tmp, p)
