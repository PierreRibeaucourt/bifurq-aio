# Signaler une faille de sécurité

Ne pas ouvrir d'issue publique pour une faille de sécurité (fuite possible de jeton, contournement
de la vérification `state` OAuth, etc.). Contacter le mainteneur du dépôt directement, en privé,
via son profil GitHub, avec le détail nécessaire pour reproduire.

Ce que cet outil manipule comme données sensibles, à garder en tête en le relisant :
- un jeton OAuth Google (`client_id`, `client_secret`, `refresh_token`) par site, stocké en clair
  dans `config\<site>\jeton_gsc.json`, jamais commité (voir `.gitignore`) ;
- éventuellement des identifiants DataForSEO fournis par l'utilisateur, dans `config\sites.json`,
  jamais commités non plus.

Le `client_id`/`client_secret` du client OAuth partagé (`veille_ia/oauth_client.py`) est, lui,
public par conception (voir `SETUP_OAUTH.md`) : ce n'est pas une faille de le voir dans le code.
