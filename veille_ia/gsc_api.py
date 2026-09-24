# -*- coding: utf-8 -*-
"""Appels directs à l'API Google Search Console, avec le jeton OAuth de l'utilisateur
(voir oauth.py). Aucun service intermédiaire : le poste parle directement à Google.

Deux familles d'endpoint chez Google, couvertes par le même accès (webmasters.readonly) :
  - "Webmasters v3" (www.googleapis.com/webmasters/v3/...) : liste des propriétés et
    données agrégées (searchAnalytics.query) ;
  - "Search Console v1" (searchconsole.googleapis.com/v1/...) : inspection d'URL."""
import datetime
import json
import urllib.error
import urllib.parse
import urllib.request

from . import oauth
from .erreurs import ErreurAccesSearchConsole, ErreurConnexionGoogle, ErreurDonnees, ErreurReseau

BASE_WEBMASTERS = "https://www.googleapis.com/webmasters/v3"
INSPECTION_URL = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
INCONNUE = "Google ne reconnaît pas cette URL"
_NOMS_DIMENSION = {"page": "URL", "date": "Date", "query": "Requete", "country": "Pays"}


def _message_google(corps):
    try:
        return json.loads(corps)["error"]["message"]
    except (ValueError, KeyError, TypeError):
        return corps[:300]


def _appel(chemin_jeton, url, methode="GET", corps=None):
    jeton = oauth.jeton_frais(chemin_jeton)
    data = json.dumps(corps).encode() if corps is not None else None
    req = urllib.request.Request(url, data=data, method=methode,
                                 headers={"Authorization": "Bearer " + jeton, "Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=90).read().decode())
    except urllib.error.HTTPError as e:
        detail = "HTTP %s %s : %s" % (e.code, url, _message_google(e.read().decode("utf-8", "replace")))
        if e.code == 401:
            raise ErreurConnexionGoogle("La connexion à votre compte Google a expiré.", detail)
        if e.code == 403:
            raise ErreurAccesSearchConsole(
                "Ce compte Google n'a pas accès à la Search Console de ce site.", detail)
        raise ErreurDonnees("La Search Console a refusé la demande (%s)." % _message_google(detail), detail)
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise ErreurReseau("Google ne répond pas : connexion Internet coupée ? Nouvel essai à la "
                           "prochaine analyse.", str(e))


def lister_proprietes(chemin_jeton):
    """[{"siteUrl", "permissionLevel"}, ...] des propriétés accessibles au compte."""
    return _appel(chemin_jeton, BASE_WEBMASTERS + "/sites").get("siteEntry") or []


def donnees(chemin_jeton, propriete, debut, fin, dimensions=("page",), limite=25000, frais=False):
    """Une ligne par valeur de dimension. ("page",) -> {"URL", "Clics", "Impressions",
    "CTR", "Position"} ; ("date",) -> {"Date", ...}. frais=True : données fraîches
    (dataState "all"), publiées avec un jour de retard au lieu de trois."""
    url = "%s/sites/%s/searchAnalytics/query" % (BASE_WEBMASTERS, urllib.parse.quote(propriete, safe=""))
    corps = {"startDate": debut, "endDate": fin, "dimensions": list(dimensions), "rowLimit": limite}
    if frais:
        corps["dataState"] = "all"
    r = _appel(chemin_jeton, url, "POST", corps)
    noms = [_NOMS_DIMENSION.get(d, d) for d in dimensions]
    out = []
    for ligne in r.get("rows") or []:
        d = dict(zip(noms, ligne["keys"]))
        d["Clics"] = ligne.get("clicks", 0)
        d["Impressions"] = ligne.get("impressions", 0)
        d["CTR"] = ligne.get("ctr", 0.0)
        d["Position"] = ligne.get("position", 0.0)
        out.append(d)
    return out


def dernier_jour(chemin_jeton, propriete):
    """Dernier jour complet des données fraîches de la Search Console : la veille en
    général (le jour en cours n'en a qu'une partie). None si le site n'a eu aucune
    impression sur les 10 derniers jours."""
    auj = datetime.date.today()
    hier = str(auj - datetime.timedelta(days=1))
    L = donnees(chemin_jeton, propriete, str(auj - datetime.timedelta(days=10)), hier, ("date",), frais=True)
    return max(x["Date"] for x in L) if L else None


def inspecter(chemin_jeton, url, propriete):
    """Inspection d'URL : INCONNUE ("Google ne reconnaît pas cette URL") est la
    signature d'une adresse jamais explorée par Google, donc jamais réelle."""
    corps = {"inspectionUrl": url, "siteUrl": propriete, "languageCode": "fr-FR"}
    try:
        r = _appel(chemin_jeton, INSPECTION_URL, "POST", corps)
    except ErreurConnexionGoogle:
        raise
    except Exception as e:
        code = 403 if isinstance(e, ErreurAccesSearchConsole) else None
        return {"url": url, "http": code, "erreur": getattr(e, "detail", str(e))[:200]}
    idx = (r.get("inspectionResult") or {}).get("indexStatusResult") or {}
    return {"url": url, "http": 200, "coverage": idx.get("coverageState"), "crawl": idx.get("lastCrawlTime"),
            "referring": idx.get("referringUrls"), "canonical": idx.get("googleCanonical")}


def proprietes_lisibles(liste):
    """Une entrée par site, lisible par n'importe qui : "exemple.fr" au lieu de
    "sc-domain:exemple.fr" et "https://www.exemple.fr/" listés séparément. La
    propriété de domaine est préférée (elle couvre www, sans www, http et https).
    Les propriétés non vérifiées, sans accès aux données, sont écartées."""
    choix = {}
    for p in liste:
        if p.get("permissionLevel") == "siteUnverifiedUser":
            continue
        u = p["siteUrl"]
        if u.startswith("sc-domain:"):
            nom = u[len("sc-domain:"):]
        else:
            nom = urllib.parse.urlparse(u).netloc
            chemin = urllib.parse.urlparse(u).path.strip("/")
            if chemin:
                nom += "/" + chemin
        nom = nom.lower()
        if nom.startswith("www."):
            nom = nom[4:]
        if nom not in choix or u.startswith("sc-domain:"):
            choix[nom] = u
    return [{"nom": n, "propriete": choix[n]} for n in sorted(choix)]
