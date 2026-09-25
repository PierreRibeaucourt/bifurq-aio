# -*- coding: utf-8 -*-
"""Ressemblance de deux slugs, pour proposer une page cible probable quand une
adresse inventée par l'IA se révèle être la déformation d'une vraie page.

Deux signaux : la similarité de chaîne brute (difflib) et le recouvrement des mots,
une faute de frappe tolérée par mot. Aucun des deux ne suffit seul : la similarité de
chaîne rate les mots réordonnés, le recouvrement de mots rate les fautes de frappe
sur un mot entier absent tel quel.

L'IA de Google fabrique aussi l'adresse à partir du titre de la vraie page (relevé du
25.09.2026 : la page /dette-de-sommeil, titrée "Dette de sommeil : définition, calcul
et solutions durables", citée en /dette-de-sommeil-definition-calcul-et-solutions-durales).
D'où la comparaison avec les titres d'une page, lus par textes_de_page."""
import difflib
import html.parser
import re
import unicodedata
import urllib.parse


def plie(s):
    """Un slug en minuscules, sans accents ni ponctuation, mots séparés par un tiret."""
    s = urllib.parse.unquote(s).lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def mots(s):
    return [m for m in s.split("-") if m]


def recouvrement_mots(a, b):
    """Part des mots de a retrouvés dans b, une faute de frappe tolérée par mot."""
    ma, mb = mots(a), mots(b)
    if not ma or not mb:
        return 0.0
    ok = 0
    for m in ma:
        if m in mb or any(len(m) > 3 and difflib.SequenceMatcher(None, m, x).ratio() >= 0.8 for x in mb):
            ok += 1
    return ok / max(len(ma), len(mb))


def ressemblance(a, b):
    return 0.5 * difflib.SequenceMatcher(None, a, b).ratio() + 0.5 * recouvrement_mots(a, b)


class _LecteurTitres(html.parser.HTMLParser):
    """Balise <title>, titre de partage (og:title) et premier <h1> d'une page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.textes, self._dans, self._morceaux, self.h1_lu = {}, None, [], False

    def handle_starttag(self, balise, attributs):
        a = dict(attributs)
        if balise == "meta" and (a.get("property") or a.get("name") or "").lower() == "og:title" and a.get("content"):
            self.textes.setdefault("og", a["content"])
        elif (balise == "title" and "title" not in self.textes) or (balise == "h1" and not self.h1_lu):
            self._dans, self._morceaux = balise, []

    def handle_data(self, texte):
        if self._dans:
            self._morceaux.append(texte)

    def handle_endtag(self, balise):
        if balise == self._dans:
            self.textes.setdefault(balise, " ".join("".join(self._morceaux).split()))
            self.h1_lu = self.h1_lu or balise == "h1"
            self._dans = None


def textes_de_page(page):
    """Titres d'une page HTML à comparer à une adresse inventée : <title>, og:title et
    premier <h1>, chacun aussi sans le nom du site ajouté à la fin ("... | Mon site")."""
    lecteur = _LecteurTitres()
    try:
        lecteur.feed(page)
    except Exception:                    # HTML trop abîmé : on garde ce qui a été lu
        pass
    textes = []
    for t in lecteur.textes.values():
        for x in (t, re.split(r"\s+[|\u2013\u2014-]\s+(?=[^|\u2013\u2014-]*$)", t)[0]):
            if x and x not in textes:
                textes.append(x)
    return textes


def ressemblance_page(slug, slug_page, textes=()):
    """Ressemblance d'un slug inventé avec une page : son adresse ou l'un de ses titres."""
    return max([ressemblance(slug, slug_page)] + [ressemblance(slug, plie(t)) for t in textes])
