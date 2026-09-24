# Contribuer

## Principe : bibliothèque standard d'abord

Le paquet `veille_ia` ne dépend d'aucun paquet tiers (voir `requirements.txt`). C'est
volontaire : un utilisateur non technique lance `installer.pyw`, et rien ne doit pouvoir échouer
à cause d'un paquet indisponible sur son réseau. Avant d'ajouter une dépendance, chercher une
solution avec `urllib`, `http.server`, `json`, `difflib`, etc. Si une dépendance est vraiment
nécessaire, en discuter dans une issue d'abord.

## Organisation du code

- `veille_ia/urls.py`, `sitemap.py`, `matching.py` : logique pure, sans secret ni appel réseau
  propre à un compte. C'est le cœur testable.
- `veille_ia/oauth.py`, `oauth_client.py`, `gsc_api.py` : connexion Google et appels à l'API
  Search Console, avec le jeton de l'utilisateur final.
- `veille_ia/http_check.py` : contrôle HTTP d'une adresse (direct, ou DataForSEO si
  l'utilisateur fournit ses identifiants), et reconnaissance des protections anti-robots
  (Cloudflare, DataDome...) qui répondent à la place du site.
- `veille_ia/watch.py` : orchestrateur, un passage de veille pour tous les sites configurés.
- `veille_ia/config.py` : lecture/écriture de `config/sites.json`.
- `veille_ia/installer/` : serveur web local (installation, gestion), zéro dépendance.
- `installer.pyw` : copie l'outil dans `%LOCALAPPDATA%\Bifurq AIO` (mise à jour si déjà
  installé, sites conservés), puis `veille_ia/installation.py` crée le raccourci et remet la tâche
  planifiée sur ce dossier. Pour développer, lancer plutôt l'interface depuis le dépôt :
  `python -m veille_ia.installer.server` (configuration dans `config\` du dépôt, non versionnée).
- `icone.ico` : icône du raccourci, même panneau de déviation que le logo (`veille_ia/style.py`).
- `scripts_windows/` : PowerShell, notification et tâche planifiée.

## Publier une version

Les outils installés lisent `docs/version.json` sur le site une fois par jour. Quand ce fichier
annonce un numéro plus récent que le leur, un bandeau **Mettre à jour** apparaît dans **Vos sites**.
Le bouton télécharge le ZIP de l'étiquette `v<numéro>` du dépôt et lance son installateur.

1. Changer `__version__` dans `veille_ia/__init__.py`, par exemple `0.3.0`.
2. Mettre le même numéro dans `docs/version.json`, avec une ou deux phrases sur les nouveautés.
   Elles s'affichent dans le bandeau.
3. Pointer le bouton **Télécharger pour Windows** de `docs/index.html` sur la nouvelle étiquette.
4. Lancer les tests : `tests/test_mise_a_jour.py` vérifie que ces trois numéros concordent.
5. Publier le commit et l'étiquette dans le même envoi :

```
git tag v0.3.0
git push origin main v0.3.0
```

Un envoi sur `main` sans changement de numéro ne propose rien aux outils installés.

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
