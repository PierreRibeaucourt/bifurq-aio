# -*- coding: utf-8 -*-
"""Pages de l'outil, en chaînes Python : aucune dépendance à installer."""
import html
import json

from .. import __version__
from ..report import SCRIPT_TABLEAU, entete_site, tableau_adresses
from ..style import NOM_OUTIL, bandeau_auteur, gabarit

e = html.escape

RETOUR = '<a class="fil" href="/"><span aria-hidden="true">←</span>Mes sites</a>'


def _jeton(jeton):
    return '<input type="hidden" name="jeton" value="%s">' % e(jeton)


def _minuscule(texte):
    return texte[:1].lower() + texte[1:]


def _moments(planif):
    """"à chaque démarrage de l'ordinateur et chaque jour à 09:15", ou "" si rien n'est prévu."""
    if not planif.get("active", True):
        return ""
    moments = []
    if planif.get("au_demarrage"):
        moments.append("à chaque démarrage de l'ordinateur")
    if planif.get("actif_heure_fixe"):
        moments.append("chaque jour à %s" % planif.get("heure_fixe", "09:15"))
    return " et ".join(moments)


def texte_planification(planif):
    if not planif.get("active", True):
        return "La surveillance automatique est arrêtée."
    moments = _moments(planif)
    return "Analyse automatique %s." % moments if moments else "Aucune analyse automatique."


def _consigne(planif, jeton):
    """Ce que l'utilisateur peut faire une fois ses sites ajoutés : fermer l'onglet, et comment
    l'outil continue sans lui. Une croix la masque pour de bon."""
    moments = _moments(planif)
    if moments:
        quand = ('Les analyses se lancent toutes seules %s, même onglet fermé. <a href="/reglages">Changer</a>'
                 % e(moments, quote=False))
    else:
        quand = ('La surveillance automatique est arrêtée : aucune analyse ne se lance toute seule. '
                 '<a href="/reglages">La reprendre</a>')
    return """<section class="consigne" aria-label="Fonctionnement de l'outil">
<form class="consigne-fermer" method="post" action="/masquer-consigne">%s<button type="submit"
title="Ne plus afficher ce message" aria-label="Ne plus afficher ce message">×</button></form>
<p class="consigne-titre">Vous pouvez fermer cet onglet.</p>
<ul><li>%s</li>
<li>Une notification Windows vous prévient dès qu'une nouvelle adresse est à corriger. Les analyses lancées depuis
cette page n'en envoient pas : le résultat s'affiche ici.</li>
<li>Pour revenir ici : raccourci <b>%s</b> sur votre bureau.</li></ul>
</section>""" % (_jeton(jeton), quand, e(NOM_OUTIL))


def _choix_planification(planif):
    return """<label class="choix"><input type="checkbox" name="au_demarrage"%s>
<span class="choix-texte"><b>À chaque démarrage de l'ordinateur</b>
<span class="meta">Deux minutes après l'ouverture de votre session.</span></span></label>
<label class="choix"><input type="checkbox" name="actif_heure_fixe"%s>
<span class="choix-texte"><b>Tous les jours à <input type="time" name="heure_fixe" value="%s"></b>
<span class="meta">Si l'ordinateur est éteint à cette heure, l'analyse a lieu au démarrage suivant.</span></span></label>""" % (
        " checked" if planif.get("au_demarrage", True) else "",
        " checked" if planif.get("actif_heure_fixe") else "",
        e(planif.get("heure_fixe") or "09:15"))


def _champ(nom, aide, controle):
    return '<label class="champ"><span class="nom">%s</span>%s%s</label>' % (
        nom, '<span class="aide">%s</span>' % aide if aide else "", controle)


def _champ_seuil(seuil):
    return _champ("Nombre de vues minimum avant alerte",
                  "Une adresse inventée vue moins souvent dans Google en 3 mois n'est pas signalée.",
                  '<input class="court" type="number" name="seuil" value="%d" min="1">' % seuil)


def _reglages_avances(contenu, ouvert=False):
    return ('<details class="avance"%s><summary>Réglages avancés</summary><div class="avance-contenu">%s</div></details>'
            % (" open" if ouvert else "", contenu))


def _champs_dataforseo(dataforseo=None):
    deja = ""
    if dataforseo:
        deja = ('<label class="choix"><input type="checkbox" name="retirer_dataforseo">'
                '<span class="choix-texte"><b>Ne plus utiliser DataForSEO</b>'
                '<span class="meta">Identifiant enregistré : %s</span></span></label>' % e(dataforseo.get("login", "")))
    return (_champ("Identifiant DataForSEO",
                   "Facultatif. Utile seulement si votre site bloque les vérifications faites depuis votre ordinateur.",
                   '<input type="text" name="dataforseo_login" autocomplete="off">')
            + _champ("Mot de passe DataForSEO", "", '<input type="password" name="dataforseo_password" autocomplete="off">')
            + deja)


def accueil():
    return gabarit(NOM_OUTIL, """
<section class="accueil">
<div>
<h1>Soyez prévenu quand Google invente une adresse de votre site</h1>
<p class="chapo">Les réponses de l'IA de Google citent parfois des pages de votre site qui n'existent pas.
Les internautes qui cliquent arrivent sur une page d'erreur. Cet outil repère ces adresses et vous indique
vers quelle page les rediriger.</p>
<a class="bouton grand" href="/connecter">Connecter mon compte Google</a>
<p class="meta" style="margin-top:14px">L'outil lit vos données Search Console sans pouvoir les modifier.
Elles restent sur votre ordinateur.</p>
<p class="meta">Un outil gratuit créé par <a href="https://www.linkedin.com/in/pierre-ribeaucourt/" target="_blank"
rel="noopener">Pierre Ribeaucourt</a>.</p>
</div>
<div class="pancarte" aria-hidden="true">
<span class="pancarte-titre">Déviation</span>
<div class="pancarte-ligne"><span class="croix">×</span><s>/guide/choisir-son-velo-electrque</s></div>
<div class="pancarte-ligne"><span class="fleche">→</span><span>/guide/choisir-son-velo-electrique</span></div>
</div>
</section>
<ol class="etapes">
<li>Connectez le compte Google qui gère votre Search Console.</li>
<li>Choisissez le site à surveiller.</li>
<li>Recevez une notification dès qu'une adresse est à corriger.</li>
</ol>""", navigation=False)


def _bandeau_mise_a_jour(maj, en_cours, jeton):
    """Nouvelle version disponible : ses nouveautés et le bouton qui l'installe."""
    if en_cours:
        bouton = ('<button class="bouton" type="submit" disabled>Mettre à jour</button>'
                  '<p class="meta">Possible à la fin de l\'analyse en cours.</p>')
    else:
        bouton = '<button class="bouton" type="submit">Mettre à jour</button>'
    nouveautes = '<p>%s</p>' % e(maj["nouveautes"]) if maj.get("nouveautes") else ""
    return ('<section class="maj" aria-label="Nouvelle version"><div><p class="maj-titre">La version %s de %s est '
            'disponible.</p>%s<p class="meta">Vos sites et réglages sont conservés.</p></div>'
            '<form class="maj-action" method="post" action="/mettre-a-jour">%s%s</form></section>'
            % (e(maj["version"]), e(NOM_OUTIL), nouveautes, _jeton(jeton), bouton))


# Mes sites : les sites à traiter d'abord, puis ceux qui vont bien
ORDRE_STATUTS = ("probleme", "a_corriger", "incomplet", "aucun", "ok")
LIBELLES_STATUTS = {"probleme": "Problème", "a_corriger": "À corriger", "incomplet": "Incomplet",
                    "aucun": "À venir", "ok": "Tout va bien"}


def _statut(es):
    s = es.get("statut")
    return s if s in LIBELLES_STATUTS else "aucun"


def _ordre(cle, cfg, es):
    return (ORDRE_STATUTS.index(_statut(es)), -len(es.get("a_rediriger") or []), cfg["nom"].lower(), cle)


def _bouton_analyser(cle, jeton, en_cours, texte="Analyser", retour=False):
    """Analyse de ce seul site."""
    return ('<form class="enligne" method="post" action="/analyser">%s<input type="hidden" name="cle" value="%s">%s'
            '<button class="bouton secondaire" type="submit"%s>%s</button></form>'
            % (_jeton(jeton), e(cle), '<input type="hidden" name="retour" value="site">' if retour else "",
               " disabled" if en_cours else "", texte))


def _outils_sites(sites, etat):
    """Recherche et compteurs par état, discrets, seulement pour une longue liste."""
    if len(sites) <= SEUIL_RECHERCHE:
        return ""
    compte = {}
    for cle in sites:
        s = _statut(etat.get(cle) or {})
        compte[s] = compte.get(s, 0) + 1
    filtres = ['<button type="button" class="filtre" data-statut="" aria-pressed="true">Tous <b>%d</b></button>'
               % len(sites)]
    filtres += ['<button type="button" class="filtre" data-statut="%s" aria-pressed="false">%s <b>%d</b></button>'
                % (s, LIBELLES_STATUTS[s], compte[s]) for s in ORDRE_STATUTS if compte.get(s)]
    return ('<div class="outils-sites"><label class="sr" for="recherche-sites">Rechercher un site</label>'
            '<input type="search" id="recherche-sites" placeholder="Rechercher un site" autocomplete="off">'
            '<div class="filtres" role="group" aria-label="Afficher les sites selon leur état">%s</div></div>'
            '<p class="meta" id="sites-vide" hidden>Aucun site ne correspond.</p>' % "".join(filtres))


SCRIPT_SITES = r"""(function(){
var cartes=[].slice.call(document.querySelectorAll('.carte-site[data-cle]'));
var q=document.getElementById('recherche-sites'),vide=document.getElementById('sites-vide');
var filtres=[].slice.call(document.querySelectorAll('.filtre[data-statut]'));
var form=document.querySelector('form.analyser-sites');
var cles=form&&form.querySelector('.cles'),bouton=form&&form.querySelector('button');
var libre=form&&!form.hasAttribute('data-en-cours'),statut='',MEMOIRE='bifurq-filtre-sites';
function plat(s){return s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'');}
function lire(){try{var v=JSON.parse(sessionStorage.getItem(MEMOIRE)||'{}');if(q&&v.q)q.value=v.q;statut=v.statut||'';}catch(e){}}
function garder(){try{sessionStorage.setItem(MEMOIRE,JSON.stringify({q:q?q.value:'',statut:statut}));}catch(e){}}
function appliquer(){
var t=q?plat(q.value.trim()):'',vus=[];
cartes.forEach(function(c){var ok=(!t||plat(c.getAttribute('data-nom')).indexOf(t)>-1)&&(!statut||c.getAttribute('data-statut')===statut);
c.hidden=!ok;if(ok)vus.push(c.getAttribute('data-cle'));});
filtres.forEach(function(f){f.setAttribute('aria-pressed',f.getAttribute('data-statut')===statut?'true':'false');});
if(vide)vide.hidden=vus.length>0;
if(libre){cles.innerHTML='';
if(t||statut){vus.forEach(function(k){var i=document.createElement('input');i.type='hidden';i.name='cle';i.value=k;cles.appendChild(i);});
bouton.textContent=vus.length===1?'Analyser le site affiché':'Analyser les '+vus.length+' sites affichés';bouton.disabled=vus.length===0;}
else{bouton.textContent='Analyser maintenant';bouton.disabled=false;}}
garder();}
if(q){q.addEventListener('input',appliquer);
q.addEventListener('keydown',function(ev){if(ev.key==='Escape'){q.value='';appliquer();}});}
filtres.forEach(function(f){f.addEventListener('click',function(){var s=f.getAttribute('data-statut');statut=s===statut?'':s;appliquer();});});
lire();
if(!filtres.some(function(f){return f.getAttribute('data-statut')===statut;}))statut='';
appliquer();
if(document.querySelector('[data-rafraichir]')){(function boucle(){setTimeout(function(){
if(q&&document.activeElement===q)boucle();else location.reload();},3000);})();}
})();"""


def tableau_de_bord(sites, etat, en_cours, progression, planif, jeton, consigne=True, maj=None, a_jour=False):
    actif = (progression or {}).get("site") if en_cours else None
    lignes = []
    for cle, cfg in sorted(sites.items(), key=lambda kv: _ordre(kv[0], kv[1], etat.get(kv[0]) or {})):
        es = etat.get(cle) or {}
        lien = "/site?cle=%s" % e(cle)
        actions = []
        reconnecter = es.get("statut") == "probleme" and es.get("action") == "reconnecter"
        if reconnecter:
            actions.append('<a class="bouton" href="/connecter?site=%s">Reconnecter mon compte Google</a>' % e(cle))
        if es.get("a_rediriger"):
            actions.append('<a class="bouton%s" href="%s">Voir les adresses</a>' % (" secondaire" if reconnecter else "", lien))
        elif es.get("statut"):
            actions.append('<a class="bouton secondaire" href="%s">Voir le détail</a>' % lien)
        actions.append(_bouton_analyser(cle, jeton, en_cours))
        actions.append('<a class="bouton secondaire" href="/modifier?cle=%s">Modifier</a>' % e(cle))
        attributs = 'data-cle="%s" data-nom="%s" data-statut="%s"' % (
            e(cle), e("%s %s" % (cfg["nom"], cfg.get("propriete", ""))), _statut(es))
        lignes.append(entete_site(cfg["nom"], es, en_cours=actif == cfg["nom"], lien=lien, actions="".join(actions),
                                  details=False, classe="carte-site", attributs=attributs))
    chantier = ""
    if en_cours:
        detail = ""
        if progression:
            detail = " : %s, %s" % (e(progression.get("site", "")), e(_minuscule(progression.get("etape", ""))))
        # rechargée par SCRIPT_SITES, qui attend si l'on tape dans la recherche
        chantier = ('<div class="chantier" role="status" data-rafraichir><span class="roue"></span><p>Analyse en '
                    'cours%s. Cette page se met à jour toute seule.</p></div>' % detail)
    bouton = ('<button class="bouton" type="submit" disabled><span class="roue"></span>Analyse en cours</button>'
              if en_cours else '<button class="bouton" type="submit">Analyser maintenant</button>')
    # consigne masquée : le moment des analyses reste rappelé sous le titre
    rappel = "" if consigne else '<p class="sous">%s <a href="/reglages">Changer</a></p>' % e(texte_planification(planif))
    annonce = ""
    if a_jour:
        annonce = ('<div class="encadre succes" role="status"><p>%s est passé à la version %s.</p></div>'
                   % (e(NOM_OUTIL), e(__version__)))
    elif maj:
        annonce = _bandeau_mise_a_jour(maj, en_cours, jeton)
    # sans recherche ni filtre, le bouton du haut analyse tous les sites ; avec, SCRIPT_SITES
    # y ajoute les sites affichés
    corps = """<div class="entete"><div><h1>Vos sites</h1>%s</div>
<div class="actions"><form class="enligne analyser-sites" method="post" action="/analyser"%s>%s<span class="cles"></span>%s</form>
<a class="bouton secondaire" href="/connecter">Ajouter un site</a></div></div>%s%s%s%s%s%s""" % (
        rappel, " data-en-cours" if en_cours else "", _jeton(jeton), bouton, annonce,
        _consigne(planif, jeton) if consigne else "", chantier, _outils_sites(sites, etat), "".join(lignes),
        bandeau_auteur())
    return gabarit("Vos sites", corps, onglet="sites", script=SCRIPT_SITES)


def page_site(cle, cfg, es, en_cours, jeton, nb_ignorees, analyse_du_site=None):
    """en_cours : une analyse tourne (boutons désactivés, page rechargée) ;
    analyse_du_site : c'est ce site qu'elle analyse en ce moment (panneau en cours)."""
    if analyse_du_site is None:
        analyse_du_site = en_cours
    def ignorer(d):
        return ('<form class="enligne" method="post" action="/ignorer">%s<input type="hidden" name="cle" value="%s">'
                '<input type="hidden" name="adresse" value="%s"><button class="lien" type="submit">Ignorer</button></form>'
                % (_jeton(jeton), e(cle), e(d["cle"])))
    ignorees = ('<p class="pied">%d adresse%s ignorée%s sur ce site.</p>'
                % (nb_ignorees, "s" if nb_ignorees > 1 else "", "s" if nb_ignorees > 1 else "")) if nb_ignorees else ""
    actions = (_bouton_analyser(cle, jeton, en_cours, "Analyser ce site", retour=True)
               + '<a class="bouton secondaire" href="/modifier?cle=%s">Modifier ce site</a>' % e(cle))
    corps = "%s%s%s%s" % (RETOUR, entete_site(cfg["nom"], es, analyse_du_site, niveau=1, actions=actions),
                          tableau_adresses(es, ignorer, cfg["nom"]), ignorees)
    return gabarit(cfg["nom"], corps, script=SCRIPT_TABLEAU, onglet="sites", rafraichir=3 if en_cours else None)


def page_modifier(cle, cfg, jeton, erreur=None):
    bloc = '<div class="encadre probleme"><p>%s</p></div>' % e(erreur) if erreur else ""
    confirmer = "return confirm(%s)" % json.dumps("Arrêter de surveiller %s ?" % cfg["nom"])
    plans = _champ("Plan de site", "Une adresse par ligne.",
                   '<textarea name="sitemaps" rows="3">%s</textarea>' % e("\n".join(cfg.get("sitemaps") or [])))
    corps = """%s<div class="etroit"><h1>Modifier %s</h1>
<p class="sous">Propriété Search Console : %s</p>%s
<form method="post" action="/modifier">%s<input type="hidden" name="cle" value="%s">
<section class="carte">%s%s%s</section>
%s
<div class="actions bloc-actions"><button class="bouton" type="submit">Enregistrer</button>
<a class="bouton secondaire" href="/">Annuler</a></div>
</form>
<section class="carte danger"><h2>Retirer ce site</h2>
<p class="doux">L'outil arrête de le surveiller et efface ses données sur cet ordinateur.</p>
<form method="post" action="/retirer" onsubmit="%s">%s<input type="hidden" name="cle" value="%s">
<button class="bouton danger" type="submit">Retirer ce site</button></form></section></div>""" % (
        RETOUR, e(cfg["nom"]), e(cfg["propriete"]), bloc, _jeton(jeton), e(cle),
        _champ("Nom affiché", "", '<input type="text" name="nom" value="%s">' % e(cfg["nom"])),
        _champ_seuil(cfg.get("seuil_impressions", 15)), plans,
        _reglages_avances(_champs_dataforseo(cfg.get("dataforseo")), ouvert=bool(cfg.get("dataforseo"))),
        e(confirmer), _jeton(jeton), e(cle))
    return gabarit("Modifier %s" % cfg["nom"], corps, onglet="sites")


def choisir(proprietes, suivies, premiere_fois, planif, jeton, erreur=None):
    if not proprietes:
        return gabarit("Aucun site trouvé", """<div class="etroit">
<h1>Aucun site trouvé sur ce compte Google</h1>
<p class="sous">Ce compte n'a accès à aucun site dans la Search Console. Connectez-vous avec le compte qui gère
votre site, ou ajoutez d'abord ce compte comme utilisateur dans la Search Console de votre site.</p>
<div class="actions bloc-actions"><a class="bouton" href="/connecter">Changer de compte Google</a>
<a class="bouton secondaire" href="/">Retour</a></div></div>""", onglet="sites")
    cases = []
    for p in proprietes:
        deja = p["propriete"] in suivies
        cases.append('<label class="choix%s" data-nom="%s"><input type="checkbox" name="proprietes" value="%s"%s>'
                     '<span class="choix-texte"><b>%s</b>%s</span></label>'
                     % (" inactif" if deja else "", e(p["nom"] + " " + p["propriete"]), e(p["propriete"]),
                        " checked disabled" if deja else "", e(p["nom"]),
                        '<span class="meta">Déjà surveillé</span>' if deja else ""))
    # Filtre à la volée, hors du formulaire : Entrée dans le champ n'envoie rien.
    recherche = ""
    if len(proprietes) > SEUIL_RECHERCHE:
        recherche = ('<div class="recherche"><label class="sr" for="filtre">Filtrer les sites</label>'
                     '<input type="search" id="filtre" placeholder="Filtrer les %d sites" autocomplete="off" autofocus>'
                     '<p id="filtre-vide" class="doux" hidden>Aucun site ne correspond à cette recherche.</p></div>'
                     % len(proprietes))
    quand = ""
    if premiere_fois:
        quand = ('<fieldset class="quand"><legend>Quand vérifier ?</legend><div class="quand-choix">%s</div></fieldset>'
                 % _choix_planification(planif))
    bloc_erreur = '<div class="encadre probleme"><p>%s</p></div>' % e(erreur) if erreur else ""
    # Réglages et bouton dans une barre collée en bas de l'écran : avec beaucoup de
    # propriétés Search Console, ils restent à portée sans faire défiler toute la liste.
    corps = """<div class="etroit"><h1>Quel site voulez-vous surveiller ?</h1>
<p class="sous">Voici les sites auxquels ce compte Google a accès dans la Search Console.</p>%s%s
<form class="choisir" method="post" action="/activer" novalidate>%s
<div>%s</div>
<div class="barre-fixe">%s
<div class="barre-bas">
<button type="button" class="ouvrir-reglages" aria-haspopup="dialog">%s<span class="ouvrir-titre">Réglages avancés</span>
<span class="resume-reglages">Alerte dès 15 vues · sans DataForSEO</span></button>
<div class="barre-action"><span class="compteur" aria-live="polite"></span>
<button class="bouton grand" type="submit">Lancer la surveillance</button></div></div>
</div>
<dialog id="reglages" class="dialogue" aria-labelledby="reglages-titre">
<div class="dialogue-tete"><h2 id="reglages-titre">Réglages avancés</h2>
<button type="button" class="dialogue-fermer" data-fermer aria-label="Fermer">×</button></div>
<div class="dialogue-corps"><p class="doux">Ils s'appliquent aux sites cochés. Vous pourrez les changer ensuite site par
site, avec le bouton Modifier.</p>%s</div>
<div class="dialogue-pied"><button type="button" class="bouton" data-fermer>Valider</button></div>
</dialog>
</form></div>""" % (bloc_erreur, recherche, _jeton(jeton), "".join(cases), quand, ICONE_REGLAGES,
                    _champ_seuil(15) + _champs_dataforseo())
    return gabarit("Choisir un site", corps, onglet="sites", script=SCRIPT_CHOISIR)


SEUIL_RECHERCHE = 6      # au-delà, un champ filtre la liste des propriétés

ICONE_REGLAGES = ('<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" fill="none" stroke="currentColor" '
                  'stroke-width="1.8" stroke-linecap="round"><path d="M2 4.5h14M2 9h14M2 13.5h14"/>'
                  '<circle cx="6" cy="4.5" r="2" fill="#FFC21A"/><circle cx="12" cy="9" r="2" fill="#FFC21A"/>'
                  '<circle cx="7.5" cy="13.5" r="2" fill="#FFC21A"/></svg>')

# Filtre la liste à la volée (sans accents ni majuscules ; Échap vide le champ), compte les
# sites cochés, masqués compris, ouvre les réglages avancés dans une fenêtre (Entrée dans un
# champ la referme au lieu de lancer la surveillance) et en résume les valeurs dans la barre,
# et empêche un second envoi pendant l'activation (qui lit le plan de site de chaque site
# choisi) : un double clic renverrait vers la connexion Google.
SCRIPT_CHOISIR = r"""(function(){
var f=document.querySelector('form.choisir');if(!f)return;
var n=f.querySelector('.compteur'),b=f.querySelector('.barre-action button');
function maj(){var k=f.querySelectorAll('input[name=proprietes]:checked:not(:disabled)').length;
n.textContent=k===0?'Aucun site coché':k===1?'1 site coché':k+' sites cochés';}
f.addEventListener('change',maj);maj();
var q=document.getElementById('filtre'),vide=document.getElementById('filtre-vide');
if(q){var cases=[].slice.call(f.querySelectorAll('label.choix[data-nom]'));
function plat(s){return s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');}
function filtrer(){var t=plat(q.value.trim()),vus=0;
cases.forEach(function(c){var ok=!t||plat(c.getAttribute('data-nom')).indexOf(t)>-1;c.hidden=!ok;if(ok)vus++;});
vide.hidden=vus>0;}
q.addEventListener('input',filtrer);
q.addEventListener('keydown',function(ev){if(ev.key==='Escape'){q.value='';filtrer();}});
filtrer();}
var d=document.getElementById('reglages'),resume=f.querySelector('.resume-reglages');
function resumer(){var s=parseInt(f.querySelector('input[name=seuil]').value,10)||15,
l=f.querySelector('input[name=dataforseo_login]').value.trim();
resume.textContent='Alerte dès '+s+' vue'+(s>1?'s':'')+' · '+(l?'avec DataForSEO':'sans DataForSEO');}
if(d&&d.showModal){
f.querySelector('.ouvrir-reglages').addEventListener('click',function(){d.showModal();});
[].forEach.call(d.querySelectorAll('[data-fermer]'),function(x){x.addEventListener('click',function(){d.close();});});
d.addEventListener('click',function(ev){if(ev.target===d)d.close();});
d.addEventListener('keydown',function(ev){if(ev.key==='Enter'&&ev.target.tagName==='INPUT'){ev.preventDefault();d.close();}});
d.addEventListener('close',resumer);}
f.addEventListener('submit',function(ev){
if(f.getAttribute('data-envoye')){ev.preventDefault();return;}
f.setAttribute('data-envoye','1');b.disabled=true;
b.innerHTML='<span class="roue" aria-hidden="true"></span>Lancement en cours';
n.textContent='Cela peut prendre une minute.';});
window.addEventListener('pageshow',function(ev){if(!ev.persisted)return;
f.removeAttribute('data-envoye');b.disabled=false;b.textContent='Lancer la surveillance';maj();});
})();"""


def reglages(planif, jeton, message=None, erreur=None):
    bloc = ""
    if message:
        bloc = '<div class="encadre succes"><p>%s</p></div>' % e(message)
    if erreur:
        bloc = '<div class="encadre probleme"><p>%s</p></div>' % e(erreur)
    active = planif.get("active", True)
    if not active and not erreur:
        bloc += ('<div class="encadre alerte"><p>La surveillance automatique est arrêtée. Cochez un moment de '
                 'vérification et enregistrez pour la reprendre.</p></div>')
    arret = ""
    if active:
        arret = """<section class="carte"><h2>Arrêter la surveillance automatique</h2>
<p class="doux">L'outil ne se lancera plus tout seul. Vos sites restent enregistrés et vous pourrez reprendre
depuis cette page.</p>
<form method="post" action="/arreter">%s<button class="bouton secondaire" type="submit">Arrêter la surveillance</button></form>
</section>""" % _jeton(jeton)
    corps = """<div class="etroit"><h1>Réglages</h1>%s
<form method="post" action="/reglages">%s
<section class="carte"><h2>Quand vérifier ?</h2>%s
<div class="actions bloc-actions"><button class="bouton" type="submit">Enregistrer</button></div></section>
</form>%s</div>""" % (bloc, _jeton(jeton), _choix_planification(planif), arret)
    return gabarit("Réglages", corps, onglet="reglages")


SCRIPT_MISE_A_JOUR = """(function(){
var ancienne=%s,version=%s,debut=Date.now();
function suite(){
  if(Date.now()-debut>150000){document.getElementById("lent").hidden=false;return;}
  setTimeout(essai,1500);
}
function essai(){
  fetch("/ping",{cache:"no-store"}).then(function(r){return r.text();}).then(function(t){
    var p=t.split(" ");
    if(p[0]==="bifurq-aio"&&p[1]!==ancienne){location.replace("/?maj="+encodeURIComponent(version));}
    else{suite();}
  }).catch(suite);
}
setTimeout(essai,3000);
})();"""


def mise_a_jour_en_cours(version, empreinte):
    """Attend la nouvelle interface (même port, autre empreinte), puis s'y recharge."""
    corps = ("""<div class="etroit"><h1>Mise à jour en cours</h1>
<div class="chantier" role="status"><span class="roue"></span><p>Installation de la version %s. Cette page se
recharge toute seule dans quelques secondes.</p></div>
<div class="encadre alerte" id="lent" hidden><p>La mise à jour prend plus de temps que prévu. Fermez cette page
et rouvrez %s avec le raccourci de votre bureau.</p></div></div>""" % (e(version), e(NOM_OUTIL)))
    return gabarit("Mise à jour", corps, navigation=False,
                   script=SCRIPT_MISE_A_JOUR % (json.dumps(empreinte), json.dumps(version)))


def erreur(titre, message, action_href=None, action_texte=None):
    bouton = ('<a class="bouton" href="%s">%s</a>' % (e(action_href), e(action_texte))) if action_href else ""
    return gabarit(titre, """<div class="etroit"><h1>%s</h1><div class="encadre probleme"><p>%s</p></div>
<div class="actions bloc-actions">%s<a class="bouton secondaire" href="/">Retour à l'accueil</a></div></div>"""
                   % (e(titre), e(message), bouton))
