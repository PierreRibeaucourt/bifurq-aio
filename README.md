# Bifurq AIO

**Veille des adresses inventées par l'IA de Google.**

Les réponses de l'IA de Google (AI Overview et AI Mode) citent parfois une adresse de votre site
qui n'a jamais existé. C'est souvent une déformation d'une vraie page : un mot sauté, une faute
de frappe, un titre transformé en adresse. L'internaute qui clique tombe sur une page d'erreur.

Cet outil surveille votre Search Console, repère ces adresses, vérifie qu'elles répondent bien
en erreur et vous indique vers quelle page les rediriger. Il vous prévient par une notification
Windows.

**Ce qu'il fait à chaque analyse :**
1. il cherche les adresses de votre site vues dans Google ces 7 derniers jours (et au moins 15
   fois en 3 mois), absentes du plan de site, que Google n'a jamais explorées, donc qui n'ont
   jamais existé, et qui répondent en erreur 404 ou 410 ;
2. il cherche, parmi les pages réelles de votre site, celle qui ressemble le plus à chaque
   adresse inventée ;
3. s'il en trouve une assez proche, il la propose comme destination de la redirection. Sinon, il
   vous signale l'adresse et vous choisissez la destination.

L'outil ne modifie rien sur votre site. Vous posez vous-même les redirections.

Les pages supprimées sans redirection ne sont pas signalées. Google les a explorées quand elles
existaient et la Search Console les liste dans le rapport **Pages** au motif **Introuvable (404)**.
Le détail de l'analyse est sur la page [Comment fonctionne l'outil](https://pierreribeaucourt.github.io/bifurq-aio/fonctionnement.html).

## Installation

**Windows uniquement pour l'instant.**

1. Si Python n'est pas encore installé sur votre ordinateur : téléchargez-le sur
   [python.org/downloads](https://www.python.org/downloads/) et suivez l'installation.
2. Téléchargez ce dépôt (bouton **Code** puis **Download ZIP** sur GitHub) et décompressez-le.
3. Double-cliquez sur **installer** (le fichier `installer.pyw`). L'outil s'installe dans
   `%LOCALAPPDATA%\Bifurq AIO`, votre dossier d'applications Windows, sans droits
   d'administrateur.
4. L'outil s'ouvre dans votre navigateur. Un raccourci **Bifurq AIO** est
   ajouté sur votre bureau pour y revenir plus tard.
5. Vous pouvez supprimer le fichier ZIP et le dossier téléchargés : l'outil n'en a plus besoin.

**Mettre à jour** : téléchargez la nouvelle version et double-cliquez sur **installer**, comme la
première fois. Vos sites, connexions Google et réglages sont conservés.

## Première utilisation

1. Cliquez sur **Connecter mon compte Google** et choisissez le compte qui a accès à la Search
   Console de votre site. L'outil demande seulement l'accès en lecture à la Search Console
   (`webmasters.readonly`).
2. Cochez le ou les sites à surveiller.
3. Choisissez quand vérifier : à chaque démarrage de l'ordinateur, tous les jours à une heure
   fixe, ou les deux.
4. Cliquez sur **Lancer la surveillance**. Une première analyse démarre tout de suite.

## Au quotidien

- **Vos sites** : un panneau par site donne son état (tout va bien, nombre d'adresses à
  corriger, problème). Le bouton **Analyser maintenant** relance une analyse à la demande.
- **Voir les adresses** : un tableau liste les adresses inventées, de la plus vue à la moins vue,
  avec la page proposée et un niveau de confiance (**Sûre** ou **À vérifier**). Un bouton copie
  chaque adresse, prête à coller dans votre menu de redirection.
- **Exporter le tableau** : télécharge le tableau en fichier CSV, qui s'ouvre dans Excel.
- **Ignorer** : retire une adresse que vous ne voulez pas traiter. Elle ne sera plus signalée.
- **Modifier** : change le nom affiché, le nombre de vues minimum avant alerte ou le plan de site,
  ou retire le site.
- **Réglages** : change le moment des analyses automatiques ou les arrête.

Quand une analyse automatique trouve une nouvelle adresse à corriger, une notification Windows
apparaît. Un clic dessus ouvre le rapport. Le dernier rapport se trouve aussi dans
`%LOCALAPPDATA%\Bifurq AIO\config\rapport.html`, et ceux des 60 derniers jours dans le
dossier `rapports` à côté.

## Quelles données sortent de votre ordinateur

- Vers l'API Google Search Console : les requêtes nécessaires à l'analyse, sur des données déjà
  visibles dans votre propre Search Console.
- Vers votre propre site : une requête par adresse pour vérifier qu'elle répond bien en erreur.
- Vers DataForSEO, seulement si vous avez renseigné vos propres identifiants (facultatif) : la
  même vérification, utile si votre site bloque les requêtes venues de votre ordinateur.

Rien d'autre n'est envoyé. Aucune donnée ne passe par un serveur de l'auteur de l'outil.

Le détail est dans les [règles de confidentialité](https://pierreribeaucourt.github.io/bifurq-aio/confidentialite.html).

## Désinstaller

1. Ouvrez l'outil, puis pour chaque site : **Modifier** puis **Retirer ce site**. Quand le dernier
   site est retiré, la tâche planifiée Windows est supprimée.
2. Supprimez le dossier `%LOCALAPPDATA%\Bifurq AIO` (collez ce chemin dans la barre
   d'adresse de l'Explorateur) et le raccourci du bureau.

Pour retirer la tâche planifiée sans passer par l'outil : ouvrez le Planificateur de tâches
Windows et supprimez la tâche **Bifurq AIO**.

## Dépannage

- **Windows demande avec quelle application ouvrir `installer`** : Python n'est pas installé.
  Installez-le (étape 1 de l'installation), puis double-cliquez à nouveau sur `installer`.
- **Une fenêtre *L'installation n'a pas pu se terminer* s'affiche** : le détail est dans
  `%LOCALAPPDATA%\Bifurq AIO\config\installation.log`, à joindre si vous signalez le
  problème.
- **Aucun site trouvé après la connexion** : le compte Google choisi n'a pas accès à la Search
  Console du site. Ajoutez-le comme utilisateur sur
  [search.google.com/search-console](https://search.google.com/search-console), puis
  reconnectez-vous.
- **Le message *Votre site bloque l'outil* s'affiche sous un site** : une protection
  anti-robots comme Cloudflare, DataDome ou Akamai répond à la place de votre site. L'outil ne
  peut alors pas tester ses adresses. Autorisez l'adresse IP de votre ordinateur dans cette
  protection en suivant [la marche à suivre](https://pierreribeaucourt.github.io/bifurq-aio/fonctionnement.html#site-protege).
- **L'outil ne répond plus dans le navigateur** : il s'arrête seul après 45 minutes sans usage.
  Rouvrez-le avec le raccourci du bureau.

## Pour les développeurs

Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour lancer les tests et comprendre l'organisation du
code, et [SETUP_OAUTH.md](SETUP_OAUTH.md) pour utiliser votre propre client Google OAuth.
