# -*- coding: utf-8 -*-
"""Lecture d'un plan de site (sitemap XML), index de plans suivi récursivement."""
import gzip
import re
import time
import urllib.error
import urllib.request

from .erreurs import ErreurPlanDeSite
from .urls import norm

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
DELAI_COURTOISIE = 1.5


def lire_url(url):
    time.sleep(DELAI_COURTOISIE)
    r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60)
    brut = r.read()
    if url.endswith(".gz") or brut[:2] == b"\x1f\x8b":
        brut = gzip.decompress(brut)
    return brut.decode("utf-8", "replace")


def plan_de_site(racines, journal, strict=False):
    """strict=True : un sous-plan en erreur ou dont la réponse n'est manifestement pas
    un sitemap fait échouer l'appel, au lieu de rendre un plan incomplet qui ferait
    passer des pages réelles pour inventées (ou l'inverse). Un sitemap XML sans
    aucune <loc> reste légitime (type de contenu vide) : seule une réponse qui ne
    ressemble à aucun des deux formats attendus est une erreur."""
    pages, vus, file_ = set(), set(), list(racines)
    while file_ and len(vus) < 300:
        u = file_.pop(0)
        if u in vus:
            continue
        vus.add(u)
        try:
            x = lire_url(u)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ConnectionError) as e:
            journal("   plan de site %s : %s" % (u, getattr(e, "code", e)))
            if strict:
                raise ErreurPlanDeSite("Impossible de lire le plan de site de votre site (%s)." % u,
                                       "plan de site illisible : %s (%s)" % (u, getattr(e, "code", e)))
            continue
        locs = [l.replace("&amp;", "&").strip() for l in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", x)]
        if strict and not locs and "<urlset" not in x and "<sitemapindex" not in x:
            raise ErreurPlanDeSite(
                "Votre site a renvoyé une page à la place de son plan de site (%s). "
                "Cela arrive quand un pare-feu bloque la lecture." % u,
                "réponse qui n'est pas un plan de site : %s" % u)
        if "<sitemapindex" in x:
            file_ += locs
        else:
            # la regex ne capte que <loc>, jamais <image:loc> : aucune image n'entre ici
            pages |= {norm(l) for l in locs}
    journal("   plan de site : %d fichiers lus, %d pages" % (len(vus), len(pages)))
    return pages


def deviner_sitemaps(racine_site):
    """Essaie /sitemap.xml, puis lit robots.txt pour une ligne Sitemap: en repli.
    racine_site : ex. "https://www.exemple.fr". Rend une liste (peut être vide)."""
    candidat = racine_site.rstrip("/") + "/sitemap.xml"
    try:
        lire_url(candidat)
        return [candidat]
    except Exception:
        pass
    try:
        robots = lire_url(racine_site.rstrip("/") + "/robots.txt")
    except Exception:
        return []
    trouves = [l.split(":", 1)[1].strip() for l in robots.splitlines()
              if l.lower().startswith("sitemap:")]
    return trouves
