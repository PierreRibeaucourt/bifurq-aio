# -*- coding: utf-8 -*-
"""Identifiant du client OAuth Google partagé par tous les utilisateurs de l'outil.

Un seul projet Google Cloud, un seul client OAuth de type "Application de bureau",
créé une fois par le mainteneur du dépôt (voir SETUP_OAUTH.md) puis committé ici en
clair. C'est la pratique documentée par Google pour les applications installées
(RFC 8252 §5.3) : ce client_id/secret n'ouvre l'accès à aucune donnée sans que
l'utilisateur final se connecte lui-même et accepte l'écran de consentement Google
avec SON propre compte. Aucun autre identifiant (DataForSEO ou autre service) ne doit
jamais figurer ici : uniquement ce client OAuth Google, public par nature.

Dans un fork, remplacer ces deux valeurs par celles de son propre client (voir
SETUP_OAUTH.md). Des valeurs "À_REMPLACER" font échouer la connexion avec un
message explicite plutôt qu'en silence."""
CLIENT_ID = "584177051119-b29orfvgg7934nqnaqcam24ce7ddtjn5.apps.googleusercontent.com"
CLIENT_SECRET = "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"


def verifier_configure():
    if "À_REMPLACER" in CLIENT_ID or "À_REMPLACER" in CLIENT_SECRET:
        from .erreurs import ErreurVeille
        raise ErreurVeille(
            "La connexion Google de cet outil n'est pas encore configurée : voir SETUP_OAUTH.md "
            "et renseigner CLIENT_ID et CLIENT_SECRET dans veille_ia/oauth_client.py.")
