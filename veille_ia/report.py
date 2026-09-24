# -*- coding: utf-8 -*-
"""Affichage de l'état d'un site et de ses adresses inventées, commun à l'interface
et au rapport HTML que la notification Windows ouvre."""
import csv
import datetime
import html
import io
import os
import re
import urllib.parse

from .style import FONCTIONNEMENT, bandeau_auteur, gabarit

e = html.escape

MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre")

# caractères de fin d'adresse toujours visibles : quand une adresse est trop longue
# pour sa colonne, c'est le milieu qui est coupé, jamais la fin qui les distingue
FIN_VISIBLE = 20

ICONE_COPIER = ('<svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><rect x="5" y="5" width="9" '
                'height="9" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M11 5V3.5A1.5 1.5 '
                '0 0 0 9.5 2h-6A1.5 1.5 0 0 0 2 3.5v6A1.5 1.5 0 0 0 3.5 11H5" fill="none" stroke="currentColor" '
                'stroke-width="1.6"/></svg>')
ICONE_EXPORTER = ('<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8M4.5 6.5 8 10l3.5'
                  '-3.5M2.5 13.5h11" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
                  'stroke-linejoin="round"/></svg>')
ICONE_OK = ('<svg width="34" height="34" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" '
            'fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>')

# copie d'une adresse et export du tableau en CSV (séparateur ; et BOM pour Excel)
SCRIPT_TABLEAU = r"""document.addEventListener('click',function(ev){
  var c=ev.target.closest('[data-copier]');
  if(c){navigator.clipboard.writeText(c.getAttribute('data-copier')).then(function(){
    c.classList.add('copie');setTimeout(function(){c.classList.remove('copie')},1400);});return;}
  var x=ev.target.closest('[data-csv]');if(!x)return;
  var texte='﻿'+x.getAttribute('data-csv').replace(/\n/g,'\r\n');
  var a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([texte],{type:'text/csv;charset=utf-8'}));
  a.download=x.getAttribute('data-fichier');document.body.appendChild(a);a.click();
  setTimeout(function(){URL.revokeObjectURL(a.href);a.remove();},1000);
});"""


def quand(iso):
    """"aujourd'hui à 10:01", "hier à 18:30", "le 21/09 à 09:15"."""
    if not iso:
        return ""
    d = datetime.datetime.fromisoformat(iso)
    jours = (datetime.date.today() - d.date()).days
    heure = d.strftime("%H:%M")
    if jours == 0:
        return "aujourd'hui à %s" % heure
    if jours == 1:
        return "hier à %s" % heure
    return "le %s à %s" % (d.strftime("%d/%m"), heure)


def date_longue(iso):
    """"24 septembre 2026", "1er octobre 2026"."""
    d = datetime.datetime.fromisoformat(iso)
    return "%s %s %d" % ("1er" if d.day == 1 else d.day, MOIS[d.month - 1], d.year)


def _s(n):
    return "s" if n > 1 else ""


def lisible(url):
    """Adresse décodée pour l'affichage : "5000-€" plutôt que "5000-%E2%82%AC"."""
    try:
        return urllib.parse.unquote(url, errors="strict")
    except UnicodeDecodeError:
        return url


# ordre des sites dans Mes sites, le rapport et l'analyse : ceux à traiter d'abord
ORDRE_STATUTS = ("probleme", "a_corriger", "incomplet", "aucun", "ok")


def statut_du_site(etat_site):
    s = (etat_site or {}).get("statut")
    return s if s in ORDRE_STATUTS else "aucun"


def ordre_des_sites(sites, etat):
    """Les clés des sites dans l'ordre d'affichage : par état, le plus d'adresses à
    corriger en tête, puis par nom."""
    def rang(cle):
        es = etat.get(cle) or {}
        return (ORDRE_STATUTS.index(statut_du_site(es)), -len(es.get("a_rediriger") or []),
                sites[cle].get("nom", cle).lower(), cle)
    return sorted(sites, key=rang)


def panneau(etat_site, en_cours=False):
    """Le panneau qui donne l'état d'un site d'un coup d'oeil."""
    es = etat_site or {}
    statut = es.get("statut")
    n = len(es.get("a_rediriger") or [])

    def p(classe, etiquette, dessin, legende):
        return ('<div class="panneau %s" role="img" aria-label="%s">%s<span class="l" aria-hidden="true">%s</span></div>'
                % (classe, etiquette, dessin, legende))
    if en_cours:
        return p("encours", "Analyse en cours", '<span class="roue"></span>', "en cours")
    if statut == "a_corriger":
        return p("a_corriger", "%d adresse%s à corriger" % (n, _s(n)), '<span class="n">%d</span>' % n, "à corriger")
    if statut == "ok":
        return p("ok", "Tout va bien", ICONE_OK, "tout va bien")
    if statut == "incomplet":
        return p("incomplet", "Analyse incomplète", '<span class="n">!</span>', "incomplet")
    if statut == "probleme":
        return p("probleme", "Problème", '<span class="n">!</span>', "problème")
    return p("aucun", "Pas encore analysé", '<span class="n">?</span>', "à venir")


def resume(etat_site, details=True):
    """Ce qu'il faut savoir du site en une phrase, puis la date et les alertes.
    details=False : sans les informations secondaires (tableau de bord)."""
    es = etat_site or {}
    statut = es.get("statut")
    n = len(es.get("a_rediriger") or [])
    blocs = []
    if statut == "probleme":
        blocs.append('<p class="phrase probleme">%s</p>' % e(es.get("message") or "L'analyse n'a pas abouti."))
        if n:
            blocs.append('<p class="meta">Résultat de l\'analyse précédente : %d adresse%s à corriger.</p>' % (n, _s(n)))
    elif statut == "a_corriger":
        avec = len([d for d in es["a_rediriger"] if d.get("cible_url")])
        if n == 1:
            phrase = "Google montre une adresse de votre site qui n'existe pas."
            if avec:
                phrase += " Une page de destination est proposée."
        else:
            phrase = "Google montre %d adresses de votre site qui n'existent pas." % n
            if avec == 1:
                phrase += " Une page de destination est proposée pour l'une d'entre elles."
            elif avec:
                phrase += " Une page de destination est proposée pour %d d'entre elles." % avec
            else:
                phrase += " Aucune ne ressemble assez à une page existante pour proposer une destination."
        blocs.append('<p class="phrase">%s</p>' % phrase)
    elif statut == "ok":
        blocs.append('<p class="phrase">Aucune adresse inventée à corriger.</p>')
    elif statut == "incomplet":                  # des adresses n'ont pas pu être vérifiées
        blocs.append('<p class="phrase">Aucune adresse inventée confirmée pour l\'instant.</p>')
    else:
        blocs.append('<p class="phrase">La première analyse n\'a pas encore eu lieu.</p>')
    if es.get("date"):
        blocs.append('<p class="meta">Dernière analyse : %s.</p>' % quand(es["date"]))
    protection = es.get("protection")
    for a in es.get("anomalies") or []:
        aide = ""
        if protection and protection in a:       # le message qui nomme la protection du site
            aide = (' <a href="%s#site-protege" target="_blank" rel="noopener">Comment faire</a>'
                    % FONCTIONNEMENT)
        blocs.append('<div class="encadre alerte"><p>%s%s</p></div>' % (e(a), aide))
    if details:
        for i in es.get("infos") or []:
            blocs.append('<p class="meta">%s</p>' % e(i))
    return "".join(blocs)


def entete_site(nom, etat_site, en_cours=False, niveau=2, lien=None, actions="", details=True, classe="",
                attributs=""):
    """Panneau, nom du site, résumé et boutons, sur une ligne. attributs : ajoutés à la
    balise du site (données de la recherche et des filtres de Mes sites)."""
    titre = '<a href="%s">%s</a>' % (e(lien), e(nom)) if lien else e(nom)
    return ('<div class="site %s"%s>%s<div class="site-texte"><h%d>%s</h%d>%s</div>%s</div>'
            % (classe, " " + attributs if attributs else "", panneau(etat_site, en_cours), niveau, titre, niveau,
               resume(etat_site, details),
               '<div class="site-actions">%s</div>' % actions if actions else ""))


def _tries(es):
    return sorted(es.get("a_rediriger") or [], key=lambda d: -d["impressions"])


def _confiance(d):
    if not d.get("cible_url"):
        return "Aucune page similaire"
    return "Sûre" if d.get("sure") else "À vérifier"


def csv_adresses(es):
    """Le tableau en CSV pour Excel : séparateur point-virgule, adresses telles que
    les boutons de copie les donnent, prêtes pour un menu de redirection."""
    sortie = io.StringIO()
    w = csv.writer(sortie, delimiter=";", lineterminator="\n")
    w.writerow(["Adresse inventée", "Rediriger vers", "Confiance", "Vues (7 jours)"])
    for d in _tries(es):
        w.writerow([d["chemin"], d["cible_proposee"] if d.get("cible_url") else "", _confiance(d), d["impressions"]])
    return sortie.getvalue()


def nom_fichier_export(nom_site, date_iso):
    base = re.sub(r"[^a-z0-9.]+", "-", (nom_site or "site").lower()).strip("-") or "site"
    return "adresses-inventees_%s_%s.csv" % (base, (date_iso or "")[:10] or datetime.date.today().isoformat())


def _url(chemin, url, copier, nouvelle=False):
    texte = lisible(chemin)
    debut, fin = (texte[:-FIN_VISIBLE], texte[-FIN_VISIBLE:]) if len(texte) > FIN_VISIBLE + 10 else (texte, "")
    bouton = ('<button class="copier" type="button" data-copier="%s" title="Copier" aria-label="Copier %s">%s</button>'
              % (e(chemin), e(texte), ICONE_COPIER)) if copier else ""
    return ('<div class="url">%s<a href="%s" target="_blank" rel="noopener" title="%s"><span class="debut">%s</span>'
            '<span class="fin">%s</span></a>%s</div>'
            % ('<span class="tag nouveau">Nouvelle</span>' if nouvelle else "", e(url), e(texte), e(debut), e(fin),
               bouton))


def tableau_adresses(es, actions=None, nom_site=""):
    """Tableau récapitulatif, une ligne par adresse, par nombre de vues décroissant.
    Toutes les lignes ont la même hauteur : une adresse trop longue est coupée au
    milieu, en entier au survol, dans la copie et dans l'export.
    actions : fonction d -> HTML de la dernière colonne (interface), None pour le
    rapport ouvert en fichier (ni copie ni action possible)."""
    adresses = _tries(es)
    if not adresses:
        return ""
    nouvelles = set(es.get("nouvelles") or [])
    copier = actions is not None
    lignes = []
    for d in adresses:
        if d.get("cible_url"):
            fleche = '<span class="fleche" aria-hidden="true">→</span>'
            cible = _url(d["cible_proposee"], d["cible_url"], copier)
            confiance = ('<span class="tag sure">Sûre</span>' if d.get("sure")
                         else '<span class="tag averifier">À vérifier</span>')
        else:
            fleche, cible, confiance = "", '<span class="vide">Aucune page similaire</span>', ""
        lignes.append('<tr><td class="n">%d</td><td>%s</td><td class="c-fleche">%s</td><td>%s</td><td>%s</td>%s</tr>'
                      % (d["impressions"], _url(d["chemin"], d["adresse"], copier, d["cle"] in nouvelles), fleche,
                         cible, confiance, '<td class="fin">%s</td>' % actions(d) if actions else ""))
    n = len(adresses)
    legende = ['<span><span class="tag sure">Sûre</span>l\'adresse inventée reprend presque mot pour mot la page '
               'proposée.</span>',
               '<span><span class="tag averifier">À vérifier</span>elle ne lui ressemble qu\'en partie.</span>',
               '<span>Aucune page similaire : la destination est à votre choix.</span>']
    if nouvelles & {d["cle"] for d in adresses}:
        legende.append('<span><span class="tag nouveau">Nouvelle</span>apparue depuis la notification précédente.</span>')
    return """<div class="barre-outils"><p>%d adresse%s, de la plus vue à la moins vue.</p>
<button class="bouton secondaire petit" type="button" data-csv="%s" data-fichier="%s">%sExporter le tableau</button></div>
<div class="conteneur-tableau"><table class="recap">
<colgroup><col class="c-vues"><col><col class="c-fleche"><col><col class="c-confiance">%s</colgroup>
<thead><tr><th class="n">Vues <small>7 jours</small></th><th>Adresse inventée</th><th><span class="sr">Redirection</span></th>
<th>Rediriger vers</th><th>Confiance</th>%s</tr></thead>
<tbody>%s</tbody></table></div>
<div class="legende">%s</div>""" % (
        n, _s(n), e(csv_adresses(es)), e(nom_fichier_export(nom_site, es.get("date"))), ICONE_EXPORTER,
        '<col class="c-action">' if actions else "", "<th></th>" if actions else "", "".join(lignes), "".join(legende))


def rendre(etat, sites, maintenant):
    """Rapport autonome (ouvert en fichier par la notification) : tous les sites."""
    blocs = []
    for cle in ordre_des_sites(sites, etat):
        cfg, es = sites[cle], etat.get(cle) or {}
        blocs.append('<section class="bloc-site">%s%s</section>'
                     % (entete_site(cfg["nom"], es, classe="carte-site"), tableau_adresses(es, nom_site=cfg["nom"])))
    heure = datetime.datetime.fromisoformat(maintenant).strftime("%H:%M")
    corps = ("<div class=\"entete\"><div><h1>Rapport du %s</h1>"
             "<p class=\"sous\">Analyse terminée à %s. Pour ignorer une adresse ou modifier un site, ouvrez l'outil "
             "avec le raccourci <b>Bifurq AIO</b> de votre bureau.</p></div></div>%s%s"
             "<p class=\"pied\">Rapports précédents : dossier <code>config\\rapports</code> de l'outil.</p>"
             % (date_longue(maintenant), heure, "".join(blocs), bandeau_auteur()))
    return gabarit("Rapport du %s" % date_longue(maintenant), corps, navigation=False, script=SCRIPT_TABLEAU)


def ecrire(dossier_donnees, contenu_html, date_jour, garder_historique=60):
    """Écrit rapport.html (atomique) et une copie datée dans rapports/, purge au-delà
    de garder_historique jours. Rend le chemin de rapport.html."""
    os.makedirs(dossier_donnees, exist_ok=True)
    chemin_rapport = os.path.join(dossier_donnees, "rapport.html")
    tmp = chemin_rapport + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(contenu_html)
    os.replace(tmp, chemin_rapport)
    archives = os.path.join(dossier_donnees, "rapports")
    os.makedirs(archives, exist_ok=True)
    io.open(os.path.join(archives, "rapport_%s.html" % date_jour), "w", encoding="utf-8").write(contenu_html)
    trop_vieux = sorted(os.listdir(archives))[:-garder_historique] if garder_historique else []
    for f in trop_vieux:
        os.remove(os.path.join(archives, f))
    return chemin_rapport
