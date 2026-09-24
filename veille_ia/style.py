# -*- coding: utf-8 -*-
"""Apparence commune à l'interface et au rapport ouvert depuis la notification.

Habillage Déviation : la signalétique routière. Une adresse inventée est une route
qui n'existe pas, la redirection est la déviation. Noir, jaune de chantier, titres
en Bahnschrift, un panneau par site. Polices : uniquement celles livrées avec
Windows 10 et 11 (Bahnschrift, Segoe UI, Cascadia), rien à télécharger."""
import html
import urllib.parse

from . import __version__

NOM_OUTIL = "Bifurq AIO"

CSS = """
:root{color-scheme:light;
--fond:#E9EAEC;--surface:#FFFFFF;--surface-2:#F6F6F4;--texte:#121417;--doux:#545B65;--trait:#D8DBDF;
--trait-fort:#9EA4AC;--noir:#121417;--jaune:#FFC21A;--jaune-fonce:#F2AF00;--jaune-pale:#FFF5D1;
--vert:#0B6B3A;--vert-pale:#E3F1E8;--vert-texte:#0A4F2C;--rouge:#C8281E;--rouge-pale:#FBE3E1;--rouge-texte:#8C1C14;
--titre:"Bahnschrift","DIN Alternate","Arial Narrow",sans-serif;
--police:"Segoe UI Variable Text","Segoe UI",system-ui,sans-serif;
--mono:"Cascadia Mono","Cascadia Code",Consolas,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--fond);color:var(--texte);font:15px/1.55 var(--police);
  display:flex;flex-direction:column;min-height:100vh}
a{color:var(--texte);text-underline-offset:3px}
p{margin:0 0 10px}
code{font-family:var(--mono);font-size:.92em}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
h1,h2{font-family:var(--titre);font-weight:700;font-stretch:87.5%;text-wrap:balance;margin:0}
h1{font-size:40px;line-height:1.08}
h2{font-size:22px;line-height:1.2}

/* bandeau */
.bandeau{background:var(--noir);color:#fff;border-bottom:5px solid var(--jaune)}
.bandeau-int{max-width:1320px;margin:0 auto;padding:12px 24px;display:flex;align-items:center;
  justify-content:space-between;gap:16px}
.marque{display:flex;align-items:center;gap:11px;font:700 18px/1 var(--titre);font-stretch:87.5%;
  letter-spacing:.01em;color:#fff;text-decoration:none}
.marque svg{flex:none}
.bandeau nav{display:flex;gap:4px}
.bandeau nav a{color:#fff;opacity:.78;text-decoration:none;padding:8px 12px;border-radius:3px;font-weight:600;
  font-size:14px}
.bandeau nav a:hover{opacity:1;background:rgba(255,255,255,.1)}
.bandeau nav a[aria-current]{opacity:1;box-shadow:inset 0 -3px 0 var(--jaune)}

/* page : elle remplit la fenêtre, le pied de page reste en bas */
.page{width:100%;max-width:1320px;margin:0 auto;padding:30px 24px 48px;flex:1 0 auto}
.etroit{max-width:760px}
.fil{display:inline-flex;align-items:center;gap:6px;margin-bottom:16px;color:var(--doux);font-weight:600;
  font-size:14px;text-decoration:none}
.fil:hover{color:var(--texte)}
.entete{display:flex;align-items:flex-end;justify-content:space-between;gap:16px 24px;flex-wrap:wrap;
  margin-bottom:22px}
.sous{margin:8px 0 0;color:var(--doux);max-width:75ch}
.meta{margin:3px 0 0;font-size:13px;color:var(--doux)}
.doux{color:var(--doux)}
.pied{margin-top:28px;font-size:13px;color:var(--doux)}

/* boutons */
.actions{display:flex;flex-wrap:wrap;align-items:center;gap:10px}
.bloc-actions{margin-top:20px}
form.enligne{display:inline}
.bouton{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:40px;padding:0 18px;
  border:2px solid var(--jaune);border-radius:3px;background:var(--jaune);color:var(--noir);
  font:600 14.5px/1.2 var(--police);text-decoration:none;white-space:nowrap;cursor:pointer}
.bouton:hover{background:var(--jaune-fonce);border-color:var(--jaune-fonce)}
.bouton.secondaire{background:var(--surface);border-color:var(--noir)}
.bouton.secondaire:hover{background:var(--noir);color:#fff}
.bouton.danger{background:var(--surface);border-color:var(--rouge);color:var(--rouge)}
.bouton.danger:hover{background:var(--rouge);color:#fff}
.bouton.grand{min-height:50px;padding:0 26px;font-size:16px}
.bouton.petit{min-height:34px;padding:0 12px;font-size:13.5px}
.bouton[disabled]{background:var(--trait);border-color:var(--trait);color:var(--doux);cursor:default}
button.lien{background:none;border:0;padding:4px 2px;color:var(--doux);font:inherit;font-size:13.5px;
  cursor:pointer;text-decoration:underline;text-underline-offset:3px}
button.lien:hover{color:var(--rouge)}
.bouton:focus-visible,a:focus-visible,input:focus-visible,textarea:focus-visible,summary:focus-visible,
button:focus-visible{outline:2px solid var(--noir);outline-offset:2px;box-shadow:0 0 0 5px var(--jaune)}

/* panneaux : l'état d'un site, lisible de loin */
.panneau{flex:none;width:86px;height:86px;border-radius:5px;display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:3px;font-family:var(--titre);font-stretch:87.5%;font-weight:700;text-align:center;
  line-height:1}
.panneau .n{font-size:34px;font-variant-numeric:tabular-nums}
.panneau .l{font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;padding:0 8px}
.panneau svg{display:block}
.panneau.a_corriger,.panneau.incomplet{background:var(--jaune);color:var(--noir);
  box-shadow:inset 0 0 0 4px var(--jaune),inset 0 0 0 6px var(--noir)}
.panneau.ok{background:var(--vert);color:#fff;box-shadow:inset 0 0 0 4px var(--vert),inset 0 0 0 6px #fff}
.panneau.probleme{background:var(--rouge);color:#fff;box-shadow:inset 0 0 0 4px var(--rouge),inset 0 0 0 6px #fff}
.panneau.aucun{background:var(--surface);color:var(--doux);border:2px dashed var(--trait-fort)}
.panneau.encours{background:var(--noir);color:var(--jaune)}
.panneau.encours .roue{width:24px;height:24px;border-width:3px}

/* un site : panneau, texte, actions */
.site{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:10px 20px;align-items:center}
.carte-site{background:var(--surface);border:1px solid var(--trait);border-radius:4px;padding:18px 20px;
  margin-top:12px}
.site-texte h1,.site-texte h2{margin-bottom:4px}
.site-texte h2 a{text-decoration:none}
.site-texte h2 a:hover{text-decoration:underline;text-decoration-color:var(--jaune);text-decoration-thickness:3px}
.phrase{margin:0}
.phrase.probleme{color:var(--rouge-texte);font-weight:600}
.site-texte .encadre{margin-top:10px}
.site-actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}
.bloc-site{margin-top:30px}
.carte-site[hidden]{display:none}

/* Mes sites, longue liste : recherche et filtres par état, discrets */
.outils-sites{display:flex;align-items:center;flex-wrap:wrap;gap:8px 14px;margin:22px 0 0}
.outils-sites input{flex:0 1 240px;min-width:0;padding:6px 10px;border:1px solid var(--trait-fort);border-radius:3px;
  background:var(--surface);color:var(--texte);font:14px/1.4 var(--police)}
.filtres{display:flex;flex-wrap:wrap;gap:2px}
.filtre{padding:4px 8px;border:0;border-radius:3px;background:none;color:var(--doux);font:13px/1.4 var(--police);
  cursor:pointer}
.filtre b{font-weight:600}
.filtre:hover{color:var(--texte);background:rgba(18,20,23,.06)}
.filtre[aria-pressed="true"]{color:var(--texte);box-shadow:inset 0 -2px 0 var(--jaune)}
#sites-vide{margin-top:14px}
@media (max-width:640px){.outils-sites input{flex-basis:100%}}

/* mode d'emploi en tête de Mes sites */
.consigne{position:relative;margin:0 0 16px;padding:14px 52px 14px 18px;background:var(--surface);
  border:1px solid var(--trait);border-left:5px solid var(--noir);border-radius:4px}
.consigne-fermer{position:absolute;top:8px;right:8px;margin:0}
.consigne-fermer button{width:34px;height:34px;border:0;border-radius:3px;background:none;color:var(--doux);
  font-size:24px;line-height:1;cursor:pointer}
.consigne-fermer button:hover{background:var(--surface-2);color:var(--texte)}
.consigne-titre{margin:0 0 6px;font-weight:700}
.consigne ul{margin:0;padding-left:20px}
.consigne li{margin:3px 0;font-size:14px;color:var(--doux)}
.consigne li::marker{color:var(--jaune-fonce)}
.consigne a{color:var(--texte)}

/* encadrés */
.encadre{border-left:5px solid;border-radius:3px;padding:11px 14px;margin-top:14px;font-size:14px}
.encadre p{margin:0}
.encadre.alerte{background:var(--jaune-pale);border-color:var(--jaune);color:var(--noir)}
.encadre.probleme{background:var(--rouge-pale);border-color:var(--rouge);color:var(--rouge-texte)}
.encadre.succes{background:var(--vert-pale);border-color:var(--vert);color:var(--vert-texte)}
.chantier{position:relative;display:flex;align-items:center;gap:12px;margin-top:4px;padding:19px 16px 13px;
  background:var(--noir);color:#fff;border-radius:4px;overflow:hidden}
.chantier::before{content:"";position:absolute;left:0;right:0;top:0;height:6px;
  background:repeating-linear-gradient(-45deg,var(--jaune) 0 12px,var(--noir) 12px 24px)}
.chantier p{margin:0}
.chantier .roue{color:var(--jaune)}
.roue{flex:none;display:inline-block;width:14px;height:14px;border:2px solid currentColor;
  border-right-color:transparent;border-radius:50%;animation:tourne .8s linear infinite}
@keyframes tourne{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion:reduce){.roue{animation:none}}

/* tableau des adresses */
.barre-outils{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;
  margin:26px 0 10px}
.barre-outils p{margin:0;color:var(--doux);font-size:14px}
.conteneur-tableau{background:var(--surface);border:1px solid var(--trait);border-radius:4px}
table.recap{width:100%;border-collapse:separate;border-spacing:0;table-layout:fixed;font-size:14px}
.recap col.c-vues{width:96px}.recap col.c-fleche{width:38px}.recap col.c-confiance{width:118px}
.recap col.c-action{width:92px}
.recap th{position:sticky;top:0;z-index:2;height:44px;padding:0 14px;background:var(--noir);color:#fff;
  text-align:left;white-space:nowrap;font:700 13px/1 var(--titre);font-stretch:87.5%;text-transform:uppercase;
  letter-spacing:.07em}
.recap th:first-child{border-top-left-radius:3px}
.recap th:last-child{border-top-right-radius:3px}
.recap th small{font:400 11.5px/1 var(--police);text-transform:none;letter-spacing:0;opacity:.75}
.recap td{height:48px;padding:0 14px;border-top:1px solid var(--trait);white-space:nowrap;overflow:hidden;
  vertical-align:middle}
.recap tbody tr:first-child td{border-top:0}
.recap tbody tr:nth-child(even) td{background:var(--surface-2)}
.recap tbody tr:hover td{background:var(--jaune-pale)}
.recap .n{text-align:right}
.recap td.n{font:700 18px/1 var(--titre);font-variant-numeric:tabular-nums}
.recap td.c-fleche{padding:0;text-align:center}
.recap td.fin{text-align:right}
.url{display:flex;align-items:center;gap:6px;min-width:0}
.url a{display:flex;min-width:0;color:var(--texte);text-decoration:none;font:13px/1.3 var(--mono)}
.url a:hover span{text-decoration:underline;text-decoration-color:var(--jaune-fonce);text-decoration-thickness:2px}
.url .debut{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.url .fin{flex:none;white-space:nowrap}
.fleche{display:inline-flex;align-items:center;justify-content:center;width:24px;height:22px;border-radius:3px;
  background:var(--jaune);color:var(--noir);font-weight:700;font-size:14px}
.vide{color:var(--doux)}
.copier{flex:none;display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;padding:0;
  border:1px solid transparent;border-radius:3px;background:none;color:var(--doux);cursor:pointer}
.copier:hover{border-color:var(--trait-fort);color:var(--texte)}
.copier.copie{border-color:var(--vert);color:var(--vert)}
.tag{flex:none;display:inline-flex;align-items:center;height:22px;padding:0 8px;border-radius:3px;
  font:700 12px/1 var(--titre);font-stretch:87.5%;text-transform:uppercase;letter-spacing:.07em;white-space:nowrap}
.tag.sure{background:var(--vert);color:#fff}
.tag.averifier{background:var(--jaune);color:var(--noir)}
.tag.nouveau{background:var(--noir);color:var(--jaune)}
.legende{display:flex;flex-wrap:wrap;gap:8px 22px;margin-top:12px;font-size:13px;color:var(--doux)}
.legende>span{display:inline-flex;align-items:center;gap:7px}

/* formulaires */
.carte{background:var(--surface);border:1px solid var(--trait);border-radius:4px;padding:22px 24px;margin-top:16px}
.carte>h2{margin-bottom:6px}
.carte.danger{border-top:5px solid var(--rouge);margin-top:44px}
.champ{display:block;margin-top:22px}
.champ:first-child{margin-top:0}
.champ .nom{display:block;font-weight:600}
.champ .aide{display:block;margin-top:1px;font-size:13px;color:var(--doux)}
.champ input,.champ textarea{display:block;margin-top:8px}
input[type=number],input[type=time],input[type=text],input[type=password],textarea{padding:9px 11px;
  border:1.5px solid var(--trait-fort);border-radius:3px;font:inherit;background:var(--surface);color:var(--texte);
  max-width:100%}
input[type=text],input[type=password],textarea{width:100%}
input.court{width:120px}
input:hover,textarea:hover{border-color:var(--doux)}
textarea{font-family:var(--mono);font-size:13px;resize:vertical}
label.choix{display:flex;gap:14px;align-items:center;padding:14px 16px;border:1.5px solid var(--trait);
  border-radius:4px;margin-top:8px;cursor:pointer;background:var(--surface)}
label.choix:hover{border-color:var(--trait-fort)}
label.choix:has(input[type=checkbox]:checked:not(:disabled)){border-color:var(--noir);background:var(--jaune-pale)}
label.choix>input[type=checkbox]{flex:none;margin:0;width:18px;height:18px;accent-color:var(--noir)}
label.choix.inactif{cursor:default;background:var(--surface-2);color:var(--doux)}
.choix-texte{display:flex;flex-direction:column;gap:2px}
.choix-texte b{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.choix-texte input[type=time]{padding:3px 8px}
.section-titre{margin:30px 0 4px}
details.avance{margin-top:22px;border:1.5px solid var(--trait);border-radius:4px;background:var(--surface)}
details.avance>summary{display:flex;align-items:center;gap:12px;padding:14px 16px;cursor:pointer;font-weight:600;
  list-style:none}
details.avance>summary::-webkit-details-marker{display:none}
details.avance>summary::before{content:"";width:7px;height:7px;border-right:2px solid;border-bottom:2px solid;
  transform:rotate(-45deg);transition:transform .15s}
details.avance[open]>summary::before{transform:rotate(45deg)}
details.avance>summary .aide{font-weight:400;font-size:13px;color:var(--doux)}
.avance-contenu{padding:18px 16px 20px;border-top:1px solid var(--trait)}

/* choix des sites : filtre au-dessus de la liste */
.recherche{margin:20px 0 4px}
.recherche input{display:block;width:100%;padding:11px 14px;border:1.5px solid var(--trait-fort);border-radius:3px;
  font:inherit;font-size:15.5px;background:var(--surface);color:var(--texte)}
.recherche input:hover{border-color:var(--doux)}
.recherche p{margin:14px 0 0}
label.choix[hidden]{display:none}

/* choix des sites : réglages et bouton collés en bas de l'écran, même avec une longue liste */
.barre-fixe{position:sticky;bottom:0;z-index:3;margin-top:18px;padding:14px 18px;background:var(--surface);
  border:1px solid var(--trait);border-top:4px solid var(--noir);border-radius:4px 4px 0 0;
  box-shadow:0 -14px 30px -18px rgba(18,20,23,.45)}
fieldset.quand{margin:0 0 12px;padding:0;border:0;min-width:0}
fieldset.quand legend{padding:0;margin-bottom:8px;font:700 13px/1 var(--titre);font-stretch:87.5%;
  text-transform:uppercase;letter-spacing:.07em}
.quand-choix{display:flex;flex-wrap:wrap;gap:8px}
.quand-choix label.choix{margin-top:0;padding:8px 12px;gap:10px}
.quand-choix .meta{display:none}
.barre-bas{display:flex;align-items:center;justify-content:space-between;gap:12px 20px;flex-wrap:wrap}
.ouvrir-reglages{display:grid;grid-template-columns:auto auto;align-items:center;gap:1px 9px;padding:6px 8px 6px 4px;
  border:0;border-radius:3px;background:none;font:inherit;color:var(--texte);text-align:left;cursor:pointer}
.ouvrir-reglages svg{grid-row:1/3}
.ouvrir-titre{font-weight:600;text-decoration:underline;text-decoration-color:var(--trait-fort);text-underline-offset:3px}
.ouvrir-reglages:hover .ouvrir-titre{text-decoration-color:var(--jaune-fonce);text-decoration-thickness:2px}
.resume-reglages{font-size:13px;color:var(--doux)}

/* fenêtre des réglages avancés */
dialog.dialogue{width:min(560px,calc(100vw - 32px));max-height:calc(100vh - 48px);padding:0;border:0;border-radius:6px;
  background:var(--surface);color:var(--texte);box-shadow:0 30px 80px -20px rgba(18,20,23,.6);overflow:auto}
dialog.dialogue::backdrop{background:rgba(18,20,23,.55)}
.dialogue-tete{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px 12px 24px;
  background:var(--noir);color:#fff;border-bottom:5px solid var(--jaune)}
.dialogue-fermer{width:36px;height:36px;border:0;border-radius:3px;background:none;color:#fff;font-size:26px;
  line-height:1;cursor:pointer}
.dialogue-fermer:hover{background:rgba(255,255,255,.12)}
.dialogue-corps{padding:20px 24px 6px}
.dialogue-corps>p.doux{margin:0 0 20px;font-size:14px}
.dialogue-corps .champ:first-of-type{margin-top:0}
.dialogue-pied{display:flex;justify-content:flex-end;padding:18px 24px 22px}
.barre-action{display:flex;align-items:center;gap:14px;margin-left:auto}
.compteur{font-size:14px;color:var(--doux);white-space:nowrap}

/* accueil */
.accueil{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:40px;align-items:center;
  padding:26px 0 8px}
.accueil h1{font-size:50px;line-height:1.02}
.chapo{margin:18px 0 26px;font-size:17px;color:var(--doux);max-width:56ch}
.pancarte{background:var(--jaune);border-radius:8px;padding:26px 26px 24px;color:var(--noir);
  box-shadow:inset 0 0 0 7px var(--jaune),inset 0 0 0 10px var(--noir),0 18px 40px -22px rgba(18,20,23,.55);
  transform:rotate(-1.5deg)}
.pancarte-titre{display:block;font:700 34px/1 var(--titre);font-stretch:87.5%;text-transform:uppercase;
  letter-spacing:.04em;text-align:center;margin-bottom:18px}
.pancarte-ligne{display:flex;align-items:center;gap:10px;font:14px/1.3 var(--mono);padding:9px 12px;
  border-radius:3px;background:rgba(255,255,255,.55)}
.pancarte-ligne+.pancarte-ligne{margin-top:8px}
.pancarte-ligne s{text-decoration-color:var(--rouge);text-decoration-thickness:2px}
.pancarte-ligne .fleche{background:var(--noir);color:var(--jaune)}
.pancarte-ligne .croix{display:inline-flex;align-items:center;justify-content:center;width:24px;height:22px;
  border-radius:3px;background:var(--rouge);color:#fff;font-weight:700;font-family:var(--police)}
ol.etapes{list-style:none;counter-reset:etape;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;
  margin:44px 0 0;padding:0}
ol.etapes li{counter-increment:etape;display:flex;gap:14px;align-items:flex-start;background:var(--surface);
  border:1px solid var(--trait);border-radius:4px;padding:16px 18px}
ol.etapes li::before{content:counter(etape);flex:none;display:flex;align-items:center;justify-content:center;
  width:34px;height:34px;border-radius:3px;background:var(--noir);color:var(--jaune);font:700 19px/1 var(--titre)}

@media (max-width:900px){
  .conteneur-tableau{overflow-x:auto}
  table.recap{min-width:860px}
  .recap th{position:static}
  .accueil{grid-template-columns:1fr}
  ol.etapes{grid-template-columns:1fr}
}
@media (max-width:640px){
  h1{font-size:30px}.accueil h1{font-size:36px}
  .page{padding:22px 16px 36px}.bandeau-int{padding:12px 16px}
  .site{grid-template-columns:auto minmax(0,1fr)}
  .site-actions{grid-column:1/-1;justify-content:flex-start}
  .panneau{width:64px;height:64px}.panneau .n{font-size:28px}
  .barre-fixe{padding:12px 14px}
  .barre-action{width:100%;flex-wrap:wrap}.barre-action .bouton{flex:1 1 auto}
}

/* auteur : bandeau noir à bande de chantier, en bas de Mes sites et du rapport. Au moins 96 px
   sous le contenu, et au bas de la page quand elle est courte. */
.avant-auteur{height:96px}
.page:has(> .auteur){display:flex;flex-direction:column}
.page:has(> .auteur) > .avant-auteur{height:auto;flex:1 0 96px}
.auteur{position:relative;display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:16px 22px;
  align-items:center;padding:28px 24px 22px;background:var(--noir);color:#fff;border-radius:4px;
  overflow:hidden}
.auteur::before{content:"";position:absolute;left:0;right:0;top:0;height:6px;
  background:repeating-linear-gradient(-45deg,var(--jaune) 0 12px,var(--noir) 12px 24px)}
.avatar{width:64px;height:64px;border-radius:6px;display:flex;align-items:center;justify-content:center;
  background:var(--jaune);color:var(--noir);font:700 28px/1 var(--titre);font-stretch:87.5%;
  box-shadow:inset 0 0 0 4px var(--jaune),inset 0 0 0 6px var(--noir)}
.auteur p{margin:0}
.auteur .auteur-sur{font:700 12px/1 var(--titre);font-stretch:87.5%;text-transform:uppercase;letter-spacing:.08em;
  color:var(--jaune)}
.auteur .auteur-nom{margin-top:5px;font:700 24px/1.1 var(--titre);font-stretch:87.5%}
.auteur .auteur-texte{margin-top:6px;font-size:14px;color:#D5D8DC;max-width:62ch}
@media (max-width:640px){.auteur{grid-template-columns:auto minmax(0,1fr)}.auteur .bouton{grid-column:1/-1}}

/* nouvelle version disponible, en haut de Mes sites */
.maj{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px 24px;margin-bottom:18px;
  padding:16px 20px;background:var(--surface);border:1px solid var(--trait);border-left:6px solid var(--jaune);
  border-radius:4px}
.maj p{margin:0}
.maj p+p{margin-top:4px}
.maj-titre{font-weight:700}
.maj-action{display:flex;flex-direction:column;align-items:flex-end;gap:4px}
@media (max-width:640px){.maj-action{align-items:stretch;width:100%}}

/* pied de page : la marque et le site de l'outil, sur toutes les pages */
.pied-outil{background:var(--surface);border-top:1px solid var(--trait)}
.pied-int{max-width:1320px;margin:0 auto;padding:14px 24px;display:flex;align-items:center;flex-wrap:wrap;
  gap:8px 18px;font-size:13px;color:var(--doux)}
.pied-int p{margin:0}
.pied-marque{display:flex;align-items:center;gap:8px;font:700 16px/1 var(--titre);font-stretch:87.5%;
  color:var(--texte)}
.pied-marque svg{flex:none}
.pied-int .pied-liens{margin-left:auto;display:flex;flex-wrap:wrap;gap:6px 18px}
.pied-liens a{display:inline-flex;align-items:center;gap:5px;color:var(--doux);font-weight:600;
  overflow-wrap:anywhere}
.pied-liens a:hover{color:var(--texte)}
.pied-liens svg{flex:none}
@media (max-width:640px){.pied-int{padding:14px 16px}.pied-int .pied-liens{margin-left:0}}
"""

LINKEDIN = "https://www.linkedin.com/in/pierre-ribeaucourt/"
SITE = "https://pierreribeaucourt.github.io/bifurq-aio/"
FONCTIONNEMENT = SITE + "fonctionnement.html"
ICONE_EXTERNE = ('<svg width="11" height="11" viewBox="0 0 12 12" aria-hidden="true"><path d="M4.5 2.5h5v5M9.5 2.5l-7 7" '
                 'fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def bandeau_auteur():
    """L'auteur de l'outil, en bas de Mes sites et du rapport ouvert par les notifications."""
    return ('<div class="avant-auteur"></div>'
            '<aside class="auteur" aria-label="Auteur de l\'outil"><div class="avatar" aria-hidden="true">PR</div>'
            '<div><p class="auteur-sur">Un outil gratuit créé par</p><p class="auteur-nom">Pierre Ribeaucourt</p>'
            '<p class="auteur-texte">Cet outil vous rend service ? Dites-le-moi sur LinkedIn, avec une idée '
            'd\'amélioration ou un retour.</p></div>'
            '<a class="bouton" href="%s" target="_blank" rel="noopener">Me retrouver sur LinkedIn</a></aside>'
            % LINKEDIN)


def pied_outil():
    """La marque et le lien vers le site de l'outil, en bas de toutes les pages et du rapport."""
    lien = '<a href="%s" target="_blank" rel="noopener">%s%s</a>'
    return ('<footer class="pied-outil"><div class="pied-int">'
            '<p class="pied-marque">%s<span>%s</span></p>'
            '<p>Veille des adresses inventées par l\'IA de Google</p><p>Version %s</p>'
            '<p class="pied-liens">%s%s</p></div></footer>'
            % (logo(22), NOM_OUTIL, __version__, lien % (SITE, "pierreribeaucourt.github.io/bifurq-aio", ICONE_EXTERNE),
               lien % (FONCTIONNEMENT, "Comment fonctionne l'outil", ICONE_EXTERNE)))


def logo(taille=28):
    """Un panneau de déviation : flèche qui monte puis tourne à droite."""
    return ('<svg width="%d" height="%d" viewBox="0 0 28 28" aria-hidden="true">'
            '<rect width="28" height="28" rx="5" fill="#FFC21A"/>'
            '<rect x="2.6" y="2.6" width="22.8" height="22.8" rx="3" fill="none" stroke="#121417" stroke-width="1.5"/>'
            '<path d="M10 21.5v-6a3.5 3.5 0 0 1 3.5-3.5H19" fill="none" stroke="#121417" stroke-width="2.6" '
            'stroke-linecap="round"/><path d="M16 8.2l3.8 3.8-3.8 3.8" fill="none" stroke="#121417" '
            'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>' % (taille, taille))


FAVICON = "data:image/svg+xml," + urllib.parse.quote(logo(64).replace(' aria-hidden="true"', ' xmlns="http://www.w3.org/2000/svg"'))


def gabarit(titre, corps, rafraichir=None, navigation=True, script="", onglet=None):
    """Page complète. rafraichir : secondes avant rechargement automatique.
    navigation=False : rapport ouvert en fichier, aucun lien vers l'outil.
    onglet : "sites" ou "reglages", pour marquer l'entrée du menu en cours."""
    if navigation:
        marque = '<a class="marque" href="/">%s<span>%s</span></a>' % (logo(), NOM_OUTIL)
        nav = "<nav>%s</nav>" % "".join(
            '<a href="%s"%s>%s</a>' % (href, ' aria-current="page"' if onglet == nom else "", texte)
            for nom, href, texte in (("sites", "/", "Mes sites"), ("reglages", "/reglages", "Réglages")))
    else:
        marque, nav = '<div class="marque">%s<span>%s</span></div>' % (logo(), NOM_OUTIL), ""
    meta = '<meta http-equiv="refresh" content="%d">' % rafraichir if rafraichir else ""
    return ("""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">%s
<title>%s</title><link rel="icon" href="%s"><style>%s</style></head><body>
<header class="bandeau"><div class="bandeau-int">%s%s</div></header>
<main class="page">%s</main>%s%s</body></html>"""
            % (meta, html.escape(titre), FAVICON, CSS, marque, nav, corps, pied_outil(),
               "<script>%s</script>" % script if script else ""))
