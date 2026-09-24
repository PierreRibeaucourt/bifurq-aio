# -*- coding: utf-8 -*-
"""Ressemblance de deux slugs, pour proposer une page cible probable quand une
adresse inventée par l'IA se révèle être la déformation d'une vraie page.

Deux signaux : la similarité de chaîne brute (difflib) et le recouvrement des mots,
une faute de frappe tolérée par mot. Aucun des deux ne suffit seul : la similarité de
chaîne rate les mots réordonnés, le recouvrement de mots rate les fautes de frappe
sur un mot entier absent tel quel."""
import difflib
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
