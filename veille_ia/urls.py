# -*- coding: utf-8 -*-
"""Normalisation d'URL et de chemin : comparer deux adresses malgré accents, casse,
protocole, www et barre oblique finale.

cle_chemin() doit rester idempotente : une clé déjà calculée, relue depuis un état
enregistré (fichier "déjà alertée" par exemple), doit redonner exactement la même
clé. Sans cette garantie, la même alerte reviendrait chaque jour (bug réel, déjà
rencontré en production)."""
import re
import unicodedata
import urllib.parse


def norm(u):
    """Une URL sans #fragment ni barre oblique finale."""
    return u.split("#")[0].rstrip("/")


def cle_url(u):
    """Clé de comparaison au plan de site : même page quelles que soient la forme des
    accents, la casse, le protocole, le www et la barre oblique finale. L'URL exacte
    reste celle qu'on inspecte et qu'on contrôle, cette clé ne sert qu'à comparer."""
    u = urllib.parse.unquote(u.split("#")[0].strip())
    u = unicodedata.normalize("NFC", u).lower()
    u = re.sub(r"^https?://(www\.)?", "", u)
    return u.rstrip("/")


def hote(u):
    return re.sub(r"^www\.", "", urllib.parse.urlparse(u).netloc.lower())


def chemin(u):
    """Le chemin d'une URL, sans domaine ni #fragment, sans barre oblique finale."""
    return re.sub(r"^https?://[^/]+", "", u.split("#")[0]).rstrip("/") or "/"


def cle_chemin(p):
    """Même forme pour un chemin de Search Console, d'un fichier ou d'une liste tenue
    à la main : accents décodés, minuscules, sans barre finale. Une URL complète est
    acceptée aussi bien qu'un chemin relatif, et le résultat est idempotent : passer
    une clé déjà normalisée à cle_chemin() la laisse inchangée."""
    if not p:
        return ""
    if not re.match(r"^https?://", p):
        p = "https://x/" + p.lstrip("/")
    k = cle_url(p)
    return k.split("/", 1)[1] if "/" in k else ""          # racine du site : clé vide
