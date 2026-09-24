# -*- coding: utf-8 -*-
"""Pages de l'outil, en chaînes Python : aucune dépendance à installer."""
import html
import json

from ..report import SCRIPT_TABLEAU, entete_site, tableau_adresses
from ..style import gabarit

e = html.escape

RETOUR = '<a class="fil" href="/"><span aria-hidden="true">←</span>Mes sites</a>'


def _jeton(jeton):
    return '<input type="hidden" name="jeton" value="%s">' % e(jeton)


def _minuscule(texte):
    return texte[:1].lower() + texte[1:]


def texte_planification(planif):
    if not planif.get("active", True):
        return "La surveillance automatique est arrêtée."
    moments = []
    if planif.get("au_demarrage"):
        moments.append("à chaque démarrage de l'ordinateur")
    if planif.get("actif_heure_fixe"):
        moments.append("chaque jour à %s" % planif.get("heure_fixe", "09:15"))
    return "Analyse automatique %s." % " et ".join(moments) if moments else "Aucune analyse automatique."


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
    return gabarit("Veille des adresses inventées", """
<section class="accueil">
<div>
<h1>Soyez prévenu quand Google invente une adresse de votre site</h1>
<p class="chapo">Les réponses de l'IA de Google citent parfois des pages de votre site qui n'existent pas.
Les internautes qui cliquent arrivent sur une page d'erreur. Cet outil repère ces adresses et vous indique
vers quelle page les rediriger.</p>
<a class="bouton grand" href="/connecter">Connecter mon compte Google</a>
<p class="meta" style="margin-top:14px">L'outil lit vos données Search Console sans pouvoir les modifier.
Elles restent sur votre ordinateur.</p>
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


def tableau_de_bord(sites, etat, en_cours, progression, planif, jeton):
    actif = (progression or {}).get("site") if en_cours else None
    lignes = []
    for cle, cfg in sites.items():
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
        actions.append('<a class="bouton secondaire" href="/modifier?cle=%s">Modifier</a>' % e(cle))
        lignes.append(entete_site(cfg["nom"], es, en_cours=actif == cfg["nom"], lien=lien, actions="".join(actions),
                                  details=False, classe="carte-site"))
    chantier = ""
    if en_cours:
        detail = ""
        if progression:
            detail = " : %s, %s" % (e(progression.get("site", "")), e(_minuscule(progression.get("etape", ""))))
        chantier = ('<div class="chantier" role="status"><span class="roue"></span><p>Analyse en cours%s. '
                    'Cette page se met à jour toute seule.</p></div>' % detail)
    bouton = ('<button class="bouton" type="submit" disabled><span class="roue"></span>Analyse en cours</button>'
              if en_cours else '<button class="bouton" type="submit">Analyser maintenant</button>')
    corps = """<div class="entete"><div><h1>Vos sites</h1>
<p class="sous">%s <a href="/reglages">Changer</a></p></div>
<div class="actions"><form class="enligne" method="post" action="/analyser">%s%s</form>
<a class="bouton secondaire" href="/connecter">Ajouter un site</a></div></div>%s%s""" % (
        e(texte_planification(planif)), _jeton(jeton), bouton, chantier, "".join(lignes))
    return gabarit("Vos sites", corps, rafraichir=3 if en_cours else None, onglet="sites")


def page_site(cle, cfg, es, en_cours, jeton, nb_ignorees):
    def ignorer(d):
        return ('<form class="enligne" method="post" action="/ignorer">%s<input type="hidden" name="cle" value="%s">'
                '<input type="hidden" name="adresse" value="%s"><button class="lien" type="submit">Ignorer</button></form>'
                % (_jeton(jeton), e(cle), e(d["cle"])))
    ignorees = ('<p class="pied">%d adresse%s ignorée%s sur ce site.</p>'
                % (nb_ignorees, "s" if nb_ignorees > 1 else "", "s" if nb_ignorees > 1 else "")) if nb_ignorees else ""
    modifier = '<a class="bouton secondaire" href="/modifier?cle=%s">Modifier ce site</a>' % e(cle)
    corps = "%s%s%s%s" % (RETOUR, entete_site(cfg["nom"], es, en_cours, niveau=1, actions=modifier),
                          tableau_adresses(es, ignorer, cfg["nom"]), ignorees)
    return gabarit(cfg["nom"], corps, script=SCRIPT_TABLEAU, onglet="sites")


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
        cases.append('<label class="choix%s"><input type="checkbox" name="proprietes" value="%s"%s>'
                     '<span class="choix-texte"><b>%s</b>%s</span></label>'
                     % (" inactif" if deja else "", e(p["propriete"]), " checked disabled" if deja else "",
                        e(p["nom"]), '<span class="meta">Déjà surveillé</span>' if deja else ""))
    quand = ""
    if premiere_fois:
        quand = ('<fieldset class="quand"><legend>Quand vérifier ?</legend><div class="quand-choix">%s</div></fieldset>'
                 % _choix_planification(planif))
    bloc_erreur = '<div class="encadre probleme"><p>%s</p></div>' % e(erreur) if erreur else ""
    # Réglages et bouton dans une barre collée en bas de l'écran : avec beaucoup de
    # propriétés Search Console, ils restent à portée sans faire défiler toute la liste.
    corps = """<div class="etroit"><h1>Quel site voulez-vous surveiller ?</h1>
<p class="sous">Voici les sites auxquels ce compte Google a accès dans la Search Console.</p>%s
<form class="choisir" method="post" action="/activer">%s
<div>%s</div>
<div class="barre-fixe">%s
<div class="barre-bas">%s
<div class="barre-action"><span class="compteur" aria-live="polite"></span>
<button class="bouton grand" type="submit">Lancer la surveillance</button></div></div>
</div>
</form></div>""" % (bloc_erreur, _jeton(jeton), "".join(cases), quand,
                    _reglages_avances(_champ_seuil(15) + _champs_dataforseo()))
    return gabarit("Choisir un site", corps, onglet="sites", script=SCRIPT_CHOISIR)


# Compte les sites cochés, et empêche un second envoi pendant l'activation (qui lit le plan
# de site de chaque site choisi) : un double clic renverrait vers la connexion Google.
SCRIPT_CHOISIR = """(function(){
var f=document.querySelector('form.choisir');if(!f)return;
var n=f.querySelector('.compteur'),b=f.querySelector('.barre-action button');
function maj(){var k=f.querySelectorAll('input[name=proprietes]:checked:not(:disabled)').length;
n.textContent=k===0?'Aucun site coché':k===1?'1 site coché':k+' sites cochés';}
f.addEventListener('change',maj);maj();
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


def erreur(titre, message, action_href=None, action_texte=None):
    bouton = ('<a class="bouton" href="%s">%s</a>' % (e(action_href), e(action_texte))) if action_href else ""
    return gabarit(titre, """<div class="etroit"><h1>%s</h1><div class="encadre probleme"><p>%s</p></div>
<div class="actions bloc-actions">%s<a class="bouton secondaire" href="/">Retour à l'accueil</a></div></div>"""
                   % (e(titre), e(message), bouton))
