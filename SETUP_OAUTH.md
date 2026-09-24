# Déclarer l'outil auprès de Google (une seule fois, par l'éditeur)

Pour que le bouton **Connecter mon compte Google** fonctionne, Google exige que l'outil soit
déclaré une fois par son éditeur. Les utilisateurs de l'outil ne font jamais cette étape : ils
cliquent sur le bouton, choisissent leur compte, cliquent sur **Autoriser**, et c'est tout.

Durée : une dizaine de minutes. Coût : aucun, sans carte bancaire.

## Avant de commencer

Utiliser un **compte Google dédié à l'outil**, pas un compte personnel ni professionnel :
- son adresse est visible par chaque utilisateur sur l'écran de connexion Google ;
- c'est le compte propriétaire qui porte les éventuelles sanctions de Google si le code public
  est détourné par un tiers ;
- l'outil cesse de fonctionner pour tout le monde si ce compte disparaît : un compte dédié se
  garde et se transmet.

Tout faire dans une **fenêtre de navigation privée** (Ctrl+Maj+N), pour ne jamais mélanger avec
un autre compte Google ouvert dans le navigateur.

## Étapes

**1. Créer le compte dédié.** Sur [accounts.google.com/signup](https://accounts.google.com/signup),
choisir **Pour mon usage personnel**, puis une adresse du type `veille.adresses.ia@gmail.com`.
Google peut demander un numéro de téléphone.

**2. Ouvrir Google Cloud.** Sur [console.cloud.google.com](https://console.cloud.google.com/),
connecté au compte dédié : pays France, accepter les conditions. Ignorer toute offre d'essai
gratuit qui demande une carte bancaire : elle n'est pas nécessaire.

**3. Créer le projet.** En haut à gauche, **Sélectionner un projet**, puis **Nouveau projet**.
Nom : `Veille adresses IA`. **Créer**, puis sélectionner ce projet dans le même menu.

**4. Activer l'accès à la Search Console.** Dans la barre de recherche en haut, taper
**Google Search Console API**, ouvrir le résultat, cliquer sur **Activer**.

**5. Déclarer l'application.** Sur
[console.cloud.google.com/auth/overview](https://console.cloud.google.com/auth/overview),
cliquer sur **Commencer** (Get started) :
- nom de l'application : `Veille des adresses inventées` ; e-mail d'assistance : le compte dédié ;
- audience : **Externe** ;
- coordonnées : le compte dédié ;
- accepter le règlement Google, puis **Créer**.

**6. Déclarer ce que l'outil lit.** Menu de gauche **Accès aux données** (Data access),
**Ajouter ou supprimer des champs d'application**. Filtrer sur `webmasters.readonly`, cocher la
ligne, **Mettre à jour**, puis **Enregistrer**. Noter sous quel titre elle apparaît (non
sensibles ou sensibles) : s'il s'agit des non sensibles, aucun utilisateur ne verra d'écran
d'avertissement et il n'y a pas de limite d'utilisateurs.

**7. Choisir qui peut se connecter.** Deux temps :
- **Pour tester, tout de suite** : menu de gauche **Audience**, section **Utilisateurs test**,
  ajouter l'adresse du compte Google qui a accès aux Search Console à tester. En mode Test,
  seuls ces comptes (100 au plus) peuvent se connecter, et leur connexion expire au bout de
  7 jours : suffisant pour valider l'outil.
- **Avant la diffusion publique** : Google exige, pour **Publier l'application**, une page
  d'accueil publique de l'outil et une page de règles de confidentialité, sur un domaine
  déclaré dans **Branding**, **Domaines autorisés**. La page d'accueil doit décrire l'outil et
  renvoyer vers les règles de confidentialité. Les deux pages sont dans le dossier `docs/`,
  publiées par GitHub Pages sur `https://pierreribeaucourt.github.io/veille-adresses-ia/` ; le
  domaine `pierreribeaucourt.github.io` doit être validé dans la Search Console par le compte
  dédié (fichier de validation dans le dépôt `PierreRibeaucourt.github.io`). Dans un fork,
  adapter ces adresses. Remplir ces deux adresses dans **Branding**,
  **sans ajouter de logo** (un logo déclenche une vérification par Google), puis **Audience**,
  **Publier l'application**. Le statut passe **En production** : n'importe qui peut alors se
  connecter, sans limite de nombre ni expiration. L'accès demandé étant classé non sensible,
  aucune vérification Google n'est nécessaire.

**8. Créer la clé de l'outil.** Menu de gauche **Clients**, **Créer un client**. Type
d'application : **Application de bureau**. Nom : `Veille adresses IA`. **Créer**. Dans la
fenêtre qui s'ouvre, cliquer **tout de suite** sur **Télécharger le fichier JSON** : Google ne
remontre plus jamais le code secret ensuite.

**9. Intégrer la clé au code.** Le fichier téléchargé (`client_secret_....json`) contient
l'identifiant et le code secret à reporter dans
[`veille_ia/oauth_client.py`](veille_ia/oauth_client.py), à la place des deux valeurs
`À_REMPLACER`. Ces deux valeurs sont publiques par nature (voir ci-dessous) : le fichier se
committe comme le reste du dépôt.

## Pourquoi cette clé peut être publique

Pour une application installée sur le poste de l'utilisateur, Google considère que la clé ne
peut pas rester secrète (RFC 8252 §5.3). Elle n'ouvre l'accès à aucune donnée : chaque
utilisateur doit se connecter lui-même avec son propre compte et cliquer sur **Autoriser**.
Ne jamais y mettre un autre identifiant (DataForSEO ou autre service).

## À surveiller ensuite

- **Quota** : partagé entre tous les utilisateurs de l'outil, au niveau du projet. À regarder
  dans **APIs et services**, **Quotas**, si la diffusion prend de l'ampleur.
- **Remplacement de la clé** : si elle doit être recréée un jour, chaque utilisateur devra se
  reconnecter depuis l'installateur.
