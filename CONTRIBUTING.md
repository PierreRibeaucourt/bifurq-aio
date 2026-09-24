# Contribuer

## Principe : bibliothèque standard d'abord

Le paquet `veille_ia` ne dépend d'aucun paquet tiers (voir `requirements.txt`). C'est
volontaire : un utilisateur non technique lance `installer.bat`, et rien ne doit pouvoir échouer
à cause d'un paquet indisponible sur son réseau. Avant d'ajouter une dépendance, chercher une
solution avec `urllib`, `http.server`, `json`, `difflib`, etc. Si une dépendance est vraiment
nécessaire, en discuter dans une issue d'abord.

## Organisation du code

- `veille_ia/urls.py`, `sitemap.py`, `matching.py` : logique pure, sans secret ni appel réseau
  propre à un compte. C'est le cœur testable.
- `veille_ia/oauth.py`, `oauth_client.py`, `gsc_api.py` : connexion Google et appels à l'API
  Search Console, avec le jeton de l'utilisateur final.
- `veille_ia/http_check.py` : contrôle HTTP d'une adresse (direct, ou DataForSEO si
  l'utilisateur fournit ses identifiants).
- `veille_ia/watch.py` : orchestrateur, un passage de veille pour tous les sites configurés.
- `veille_ia/config.py` : lecture/écriture de `config/sites.json`.
- `veille_ia/installer/` : serveur web local (installation, gestion), zéro dépendance.
- `scripts_windows/` : PowerShell, notification et tâche planifiée.

## Lancer les tests

```
config\venv\Scripts\python.exe -m pytest tests\
```

(ou `python -m pytest tests\` dans un environnement où les dépendances de test sont installées ;
`pytest` lui-même est une dépendance de développement, pas une dépendance de l'outil).

## Signaler un faux positif ou un faux négatif de détection

Ouvrir une issue avec : l'adresse concernée, la propriété Search Console (sans partager vos
identifiants), et si possible un extrait de `config\<site>\inspection.jsonl` pour cette adresse.
Un faux positif (une vraie page ancienne signalée comme inventée) est plus grave qu'un faux
négatif : à traiter en priorité.

## Style

- Noms de fonctions et commentaires en français, cohérent avec le code existant.
- Pas de tiret cadratin ni demi-cadratin dans le code, les commentaires ou les messages de
  commit.
- Une fonction fait une chose ; la logique pure (testable sans réseau) reste séparée des appels
  réseau.
