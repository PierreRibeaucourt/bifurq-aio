# -*- coding: utf-8 -*-
"""Connexion à la Search Console de l'utilisateur, flux OAuth pour application
installée (loopback local, RFC 8252) : aucun serveur intermédiaire, l'access token
va directement de Google au poste de l'utilisateur.

Le jeton est stocké au format standard (client_id, client_secret, refresh_token,
token_uri). jeton_frais() le garde en mémoire et le renouvelle 5 minutes avant
échéance, pour qu'une veille de plusieurs dizaines de minutes ne finisse jamais en
401."""
import io
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import oauth_client
from .erreurs import ErreurConnexionGoogle, ErreurReseau

_verrou = threading.Lock()

SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

_cache = {}                      # chemin de jeton -> (access_token, expiration_epoch)


def nouvel_etat():
    return secrets.token_urlsafe(24)


def url_autorisation(redirect_uri, state):
    oauth_client.verifier_configure()
    q = urllib.parse.urlencode({
        "client_id": oauth_client.CLIENT_ID, "redirect_uri": redirect_uri,
        "response_type": "code", "scope": SCOPE, "access_type": "offline",
        "prompt": "consent", "state": state, "include_granted_scopes": "true"})
    return AUTH_URL + "?" + q


def echanger_code(code, redirect_uri):
    """Rend {"access_token", "refresh_token", "expires_in", ...}. refresh_token n'est
    présent que grâce à access_type=offline&prompt=consent dans l'URL d'autorisation
    (sinon Google ne le renvoie qu'à la toute première connexion de ce compte)."""
    oauth_client.verifier_configure()
    corps = urllib.parse.urlencode({
        "code": code, "client_id": oauth_client.CLIENT_ID,
        "client_secret": oauth_client.CLIENT_SECRET, "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"}).encode()
    req = urllib.request.Request(TOKEN_URL, data=corps,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read())
    except urllib.error.HTTPError as e:
        raise ErreurConnexionGoogle("Google a refusé la connexion. Recommencez depuis l'accueil.",
                                    e.read().decode("utf-8", "replace")[:300])


def enregistrer_jeton(chemin, echange):
    if "refresh_token" not in echange:
        raise ErreurConnexionGoogle(
            "Google n'a pas renvoyé de jeton de renouvellement. Si ce compte Google a déjà "
            "autorisé cet outil, retirez l'accès sur myaccount.google.com/permissions puis "
            "recommencez la connexion.")
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    donnees = {"client_id": oauth_client.CLIENT_ID, "client_secret": oauth_client.CLIENT_SECRET,
               "refresh_token": echange["refresh_token"], "token_uri": TOKEN_URL}
    tmp = chemin + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(json.dumps(donnees, ensure_ascii=False, indent=1))
    os.replace(tmp, chemin)


def jeton_frais(chemin):
    """Access token (valable 1 h) rafraîchi depuis le refresh_token stocké dans le
    fichier pointé par chemin. Mis en cache mémoire, renouvelé 5 minutes avant
    échéance."""
    with _verrou:
        if chemin in _cache and _cache[chemin][1] > time.time():
            return _cache[chemin][0]
        if not os.path.exists(chemin):
            raise ErreurConnexionGoogle("Ce site n'est pas encore connecté à un compte Google.", chemin)
        t = json.load(io.open(chemin, encoding="utf-8"))
        corps = urllib.parse.urlencode({
            "client_id": t["client_id"], "client_secret": t["client_secret"],
            "refresh_token": t["refresh_token"], "grant_type": "refresh_token"}).encode()
        req = urllib.request.Request(t["token_uri"], data=corps,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=60).read())
        except urllib.error.HTTPError as e:
            raise ErreurConnexionGoogle("La connexion à votre compte Google a expiré ou a été retirée.",
                                        "renouvellement refusé : %s" % e.read().decode("utf-8", "replace")[:300])
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise ErreurReseau("Google ne répond pas : connexion Internet coupée ? Nouvel essai à la "
                               "prochaine analyse.", str(e))
        _cache[chemin] = (r["access_token"], time.time() + int(r.get("expires_in", 3600)) - 300)
        return _cache[chemin][0]


def trouver_port_libre(prefere):
    """Tente le port préféré (facile à retrouver pendant l'installation), retombe sur
    un port éphémère choisi par le système s'il est occupé. Rend un socket déjà lié
    (à passer à http.server), pas juste un numéro : évite une fenêtre de course entre
    "trouver un port libre" et "s'y lier"."""
    import socket
    for port in (prefere, 0):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return s
        except OSError:
            s.close()
    raise RuntimeError("aucun port disponible sur 127.0.0.1")
