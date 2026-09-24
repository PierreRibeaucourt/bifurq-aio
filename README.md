# Bifurq AIO

**Veille des adresses inventées par l'IA de Google.**

Les réponses de l'IA de Google (AI Overview et AI Mode) citent parfois une adresse de votre site
qui n'a jamais existé. Il s'agit souvent d'une vraie adresse déformée par un mot sauté, une faute
de frappe ou un titre transformé en adresse. L'internaute qui clique tombe sur une page d'erreur.

Cet outil repère ces adresses dans votre Search Console et vérifie qu'elles répondent bien en
erreur. Il vous indique vers quelle page les rediriger et vous prévient par une notification
Windows.

**Ce qu'il fait à chaque analyse :**
1. il cherche les adresses de votre site qui remplissent quatre conditions : Google les a
   affichées au moins 15 fois ces 7 derniers jours, jusqu'à la veille ; elles sont absentes du plan
   de site ; Google ne les a jamais explorées ; elles répondent en erreur 404 ou 410 ;
2. il cherche dans votre plan de site la page qui ressemble le plus à chaque adresse inventée ;
3. il propose cette page comme destination de la redirection quand elle est assez proche. Vous
   choisissez la destination quand aucune page ne ressemble assez.

Vous posez vous-même les redirections sur votre site.

Les pages supprimées sans redirection ne sont pas signalées. Google les a explorées quand elles
existaient et la Search Console les liste dans le rapport **Pages** au motif **Introuvable (404)**.
Le détail de l'analyse est sur la page [Comment fonctionne l'outil](https://pierreribeaucourt.github.io/bifurq-aio/fonctionnement.html).

## Installation

**Windows uniquement pour l'instant.**

1. Si Python n'est pas encore installé sur votre ordinateur : téléchargez-le sur
   [python.org/downloads](https://www.python.org/downloads/) et suivez l'installation.
2. Téléchargez l'outil avec le bouton **Télécharger pour Windows** de la
   [page de l'outil](https://pierreribeaucourt.github.io/bifurq-aio/) et décompressez le fichier ZIP.
3. Double-cliquez sur **installer** (le fichier `installer.pyw`). L'outil s'installe sans droits
   d'administrateur dans votre dossier d'applications Windows (`%LOCALAPPDATA%\Bifurq AIO`).
4. L'outil s'ouvre dans votre navigateur. Un raccourci **Bifurq AIO** est ajouté sur votre bureau
   pour y revenir plus tard.
5. Vous pouvez supprimer le fichier ZIP et le dossier téléchargés : l'outil n'en a plus besoin.

**Mettre à jour** : un bandeau annonce chaque nouvelle version en haut de **Vos sites**. Cliquez
sur **Mettre à jour** : l'outil télécharge et installe la nouvelle version, puis la page se
recharge. Vos sites, connexions Google et réglages sont conservés.

## Première utilisation

1. Cliquez sur **Connecter mon compte Google** et choisissez le compte qui a accès à la Search
   Console de votre site. L'outil demande seulement l'accès en lecture à la Search Console
   (`webmasters.readonly`).
2. Cochez le ou les sites à surveiller.
3. Choisissez quand vérifier : à chaque démarrage de l'ordinateur, tous les jours à une heure
   fixe ou les deux.
4. Cliquez sur **Lancer la surveillance**. Une première analyse démarre tout de suite.

## Au quotidien

- **Vos sites** : un panneau par site donne son état (tout va bien, nombre d'adresses à
  corriger, problème). Les sites à traiter s'affichent en premier et l'analyse commence par eux.
  Le bouton **Analyser** d'un site relance l'analyse de ce seul site. **Analyser maintenant**
  relance celle de tous les sites.
- **Recherche et filtres** : à partir de 7 sites, un champ de recherche et des filtres par état
  apparaissent au-dessus de la liste. Le bouton du haut analyse alors les sites affichés.
- **Voir les adresses** : un tableau liste les adresses inventées de la plus vue à la moins vue.
  Il indique pour chacune la page proposée et un niveau de confiance (**Sûre** ou
  **À vérifier**). Un bouton copie chaque adresse pour la coller dans votre outil de redirection.
- **Exporter le tableau** : télécharge le tableau en fichier CSV à ouvrir dans Excel.
- **Ignorer** : retire une adresse que vous ne voulez pas traiter. Elle ne sera plus signalée.
- **Modifier** : change le nom affiché, le nombre de vues minimum avant alerte ou le plan de site.
  Le bouton **Retirer ce site** s'y trouve aussi.
- **Réglages** : change le moment des analyses automatiques ou les arrête.

Une notification Windows apparaît quand une analyse automatique trouve une nouvelle adresse à
corriger. Un clic dessus ouvre le rapport. Le dernier rapport se trouve aussi dans
`%LOCALAPPDATA%\Bifurq AIO\config\rapport.html`. Les rapports des 60 derniers jours sont dans le
dossier `rapports` à côté.

## Quelles données sortent de votre ordinateur

- Vers l'API Google Search Console : les requêtes nécessaires à l'analyse. Elles portent sur des
  données déjà visibles dans votre Search Console.
- Vers votre propre site : une requête par adresse pour vérifier qu'elle répond bien en erreur.
- Vers DataForSEO si vous avez renseigné vos identifiants (facultatif) : la même vérification.
  Elle sert quand votre site bloque les requêtes venues de votre ordinateur.
- Vers GitHub, qui héberge le site de l'outil : la lecture du numéro de la dernière version une
  fois par jour, et le téléchargement de la nouvelle version quand vous cliquez sur
  **Mettre à jour**.

Rien d'autre n'est envoyé. Aucune donnée ne passe par un serveur de l'auteur de l'outil.

Le détail est dans les [règles de confidentialité](https://pierreribeaucourt.github.io/bifurq-aio/confidentialite.html).

## Désinstaller

1. Ouvrez l'outil et cliquez sur **Modifier** puis **Retirer ce site** pour chaque site. La tâche
   planifiée Windows est supprimée avec le dernier site.
2. Supprimez le dossier `%LOCALAPPDATA%\Bifurq AIO` (collez ce chemin dans la barre
   d'adresse de l'Explorateur) et le raccourci du bureau.

Pour retirer la tâche planifiée sans passer par l'outil : ouvrez le Planificateur de tâches
Windows et supprimez la tâche **Bifurq AIO**.

## Dépannage

- **Windows demande avec quelle application ouvrir `installer`** : Python n'est pas installé.
  Installez-le (étape 1 de l'installation) puis double-cliquez à nouveau sur `installer`.
- **Une fenêtre *L'installation n'a pas pu se terminer* s'affiche** : le détail est dans
  `%LOCALAPPDATA%\Bifurq AIO\config\installation.log`. Joignez ce fichier si vous signalez le
  problème.
- **Aucun site trouvé après la connexion** : le compte Google choisi n'a pas accès à la Search
  Console du site. Ajoutez-le comme utilisateur sur
  [search.google.com/search-console](https://search.google.com/search-console) puis
  reconnectez-vous.
- **Le message *Votre site bloque l'outil* s'affiche sous un site** : une protection
  anti-robots comme Cloudflare, DataDome ou Akamai répond à la place de votre site. L'outil ne
  peut alors pas tester ses adresses. Autorisez l'adresse IP de votre ordinateur dans cette
  protection en suivant [la marche à suivre](https://pierreribeaucourt.github.io/bifurq-aio/fonctionnement.html#site-protege).
- **L'outil ne répond plus dans le navigateur** : il s'arrête seul après 45 minutes sans usage.
  Rouvrez-le avec le raccourci du bureau.

## Pour les développeurs

Pour lancer les tests et comprendre l'organisation du code : [CONTRIBUTING.md](CONTRIBUTING.md).
Pour utiliser votre propre client Google OAuth : [SETUP_OAUTH.md](SETUP_OAUTH.md).
