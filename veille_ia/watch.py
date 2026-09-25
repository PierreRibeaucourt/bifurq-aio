# -*- coding: utf-8 -*-
"""Analyse des sites : un passage par site, l'état de chaque site pour l'interface
(config/etat.json), le rapport et les notifications.

Le process, pour chaque site :
  1. repérer les adresses affichées ces 7 derniers jours d'après la Search Console
     (données fraîches, jusqu'à la veille : l'IA de Google cite une adresse inventée
     quelques jours tout au plus, relevé du 24.09.2026 sur 423 adresses), absentes du
     plan de site, que Google n'a jamais explorées (donc inventées), et qui répondent
     en erreur (404 ou 410) ;
  2. chercher, parmi les pages du plan de site, celle qui leur ressemble, par son
     adresse ou par son titre ;
  3. si une page ressemble assez, la proposer en redirection ; sinon, prévenir
     seulement.

CE QUI NE DOIT JAMAIS ARRIVER, ET COMMENT ON L'EMPÊCHE :
  - une panne lue comme "rien à corriger" : une inspection ou un contrôle HTTP en
    erreur, un plan de site illisible ou vide, une Search Console qui renvoie
    soudain beaucoup moins de pages mettent le site en problème, affiché et notifié ;
  - une alerte perdue : l'état "déjà alertée" n'est écrit qu'après une notification
    réussie (ou un affichage à l'écran) ; une adresse redirigée sort de l'état et
    sera de nouveau signalée si la redirection saute un jour ;
  - deux analyses en même temps (tâche planifiée et bouton de l'interface) : un
    verrou dans config/ ;
  - une analyse annulée lue comme "rien à corriger" : le site interrompu garde son
    état précédent, les sites suivants aussi ; seuls les sites finis sont mis à jour ;
  - une même panne notifiée à chaque démarrage de l'ordinateur : une fois par jour au plus."""
import collections
import concurrent.futures as cf
import datetime
import io
import json
import os
import re
import threading
import time
import traceback

from . import config, gsc_api, matching, plateforme, report, sitemap, urls
from .erreurs import ErreurDonnees, ErreurPlanDeSite, expliquer
from .http_check import ERREURS, ControleurHTTP, corrigee

INSPECTIONS_PAR_JOUR = 1000        # adresses vérifiées par site et par jour, toutes analyses du jour
                                   # comprises. Quota de Google : 2 000 par jour et par site, le reste
                                   # pour les autres outils branchés sur la même Search Console
CADENCE_INSPECTIONS = 0.125        # secondes entre deux inspections : 480 par minute au plus,
                                   # sous les 600 par minute et par site de Google
PAGES_HORS_PLAN_A_SIGNALER = 50    # vraies pages absentes du plan de site : au-delà, le dire
ECHECS_A_LA_SUITE = 5              # inspections en échec d'affilée (quota de Google, réseau) : arrêt
RECONTROLE_CORRIGEES = 7           # jours entre deux tests d'une adresse déjà corrigée
DUREE_MAX = 90 * 60                # au-delà, les sites restants sont reportés
VERROU_MAX = 3 * 3600              # un verrou plus vieux est celui d'une analyse morte
MIN_PAGES_REFERENCE = 20           # en dessous, pas de détection de chute brutale
SEUIL_PROPOSITION = 0.6            # ressemblance minimale pour proposer une page (calé le
                                   # 24.09.2026 sur un vrai site : 0,57 menait à une page sans rapport)
SEUIL_SURE, ECART_SUR = 0.75, 0.1  # correspondance sûre : score et avance sur la 2e
TITRES_A_LIRE = 5                  # pages les plus proches dont on lit les titres quand l'adresse
                                   # ne suffit pas (la bonne était 1re ou 2e sur 12 vrais cas)
VALIDITE_TITRES = 30               # jours avant de relire les titres d'une page
INCONNUE = gsc_api.INCONNUE


# --- fichiers ------------------------------------------------------------------------------
def _ecrire_json(p, obj):
    tmp = p + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=list)
    os.replace(tmp, p)


def _lire_json(p, defaut):
    if not os.path.exists(p):
        return defaut
    try:
        return json.load(io.open(p, encoding="utf-8-sig"))
    except ValueError as e:
        raise ErreurDonnees("Un fichier de l'outil est abîmé : %s." % os.path.basename(p), "%s (%s)" % (p, e))


def _lire_jsonl(p):
    """Dernière ligne par URL ; une ligne abîmée est ignorée, pas fatale."""
    out = {}
    if os.path.exists(p):
        for l in io.open(p, encoding="utf-8-sig"):
            if l.strip():
                try:
                    r = json.loads(l)
                    out[r["url"]] = r
                except (ValueError, KeyError):
                    pass
    return out


def _compacter(p, garder):
    if os.path.exists(p) and os.path.getsize(p) > 5_000_000:
        tmp = p + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            for r in garder.values():
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, p)


def _journal_vers(chemin_log):
    def _j(msg):
        l = "%s  %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), msg)
        print(l, flush=True)
        if os.path.exists(chemin_log) and os.path.getsize(chemin_log) > 1_000_000:
            os.replace(chemin_log, chemin_log + ".1")
        with io.open(chemin_log, "a", encoding="utf-8") as f:
            f.write(l + "\n")
    return _j


def date_fr(iso):
    return datetime.date.fromisoformat(iso[:10]).strftime("%d/%m/%Y")


# --- état, progression, verrou -------------------------------------------------------------
def chemin_etat():
    return os.path.join(config.dossier_config(), "etat.json")


def lire_etat():
    return _lire_json(chemin_etat(), {})


def retirer_adresse(cle, cle_adresse):
    """Après "Ignorer cette adresse" : la retire tout de suite de l'affichage."""
    etat = lire_etat()
    es = etat.get(cle)
    if not es:
        return
    es["a_rediriger"] = [d for d in es.get("a_rediriger") or [] if d["cle"] != cle_adresse]
    if es.get("statut") == "a_corriger" and not es["a_rediriger"]:
        es["statut"] = "incomplet" if es.get("anomalies") else "ok"
    _ecrire_json(chemin_etat(), etat)


def oublier_site(cle):
    etat = lire_etat()
    if etat.pop(cle, None) is not None:
        _ecrire_json(chemin_etat(), etat)


def chemin_progression():
    return os.path.join(config.dossier_config(), "progression.json")


def lire_progression():
    try:
        return _lire_json(chemin_progression(), None)
    except ErreurDonnees:
        return None


def chemin_verrou():
    return os.path.join(config.dossier_config(), "veille.lock")


def analyse_en_cours():
    p = chemin_verrou()
    if not os.path.exists(p):
        return False
    try:
        v = json.load(io.open(p, encoding="utf-8"))
    except ValueError:
        return False
    return time.time() - v.get("debut", 0) < VERROU_MAX and plateforme.processus_actif(v.get("pid", 0))


def _prendre_verrou():
    if analyse_en_cours():
        return False
    _ecrire_json(chemin_verrou(), {"pid": os.getpid(), "debut": time.time()})
    _retirer(chemin_annulation())              # une demande restée d'une analyse finie entre-temps
    _annulation_vue.clear()
    return True


def _rendre_verrou():
    for p in (chemin_verrou(), chemin_progression(), chemin_annulation()):
        _retirer(p)
    _annulation_vue.clear()


def _retirer(p):
    try:
        os.remove(p)
    except OSError:
        pass


# --- annulation (bouton Annuler de l'interface) ---------------------------------------------
# Un fichier dans config/ plutôt qu'un signal : l'analyse tourne soit dans l'interface (un fil,
# qu'on ne peut pas arrêter de l'extérieur), soit dans la tâche planifiée (un autre processus).
# Elle le regarde entre deux étapes et dans ses boucles longues, et s'arrête proprement.
class AnalyseAnnulee(Exception):
    """L'utilisateur a arrêté l'analyse depuis l'interface."""


def chemin_annulation():
    return os.path.join(config.dossier_config(), "annulation")


def demander_annulation(forcer=False):
    """Rend False si aucune analyse ne tourne (rien à annuler). forcer : l'interface voit son
    propre fil d'analyse vivant, même avec un verrou de plus de 3 heures (ordinateur en veille).
    Seule la présence du fichier compte : un ajout, sûr même pour deux clics simultanés
    (os.replace échoue alors sous Windows). Une demande restée sans analyse est effacée par la
    suivante quand elle prend le verrou."""
    if not (forcer or analyse_en_cours()):
        return False
    with io.open(chemin_annulation(), "a", encoding="utf-8") as f:
        f.write("%s\n" % time.time())
    return True


def annulation_demandee():
    """Une demande d'annulation attend (pour l'interface)."""
    return os.path.exists(chemin_annulation())


# Pour l'analyse : une annulation vue le reste jusqu'à la fin de l'analyse, même si le fichier
# disparaît entre-temps (fin d'une autre analyse restée active après une mise en veille).
_annulation_vue = set()


def _annulee():
    if annulation_demandee():
        _annulation_vue.add(True)
    return bool(_annulation_vue)


def verifier_annulation():
    if _annulee():
        raise AnalyseAnnulee()


# --- un site -----------------------------------------------------------------------------------
def veille_site(cle, cfg, controleur_http, journal, aujourd_hui=None, etape=None):
    """Un passage complet pour un site. Rend un dict de résultat, ou lève une
    ErreurVeille (l'appelant la range en problème, jamais lue comme "rien à faire")."""
    etape = etape or (lambda m: None)
    aujourd_hui = aujourd_hui or datetime.date.today().isoformat()
    D = config.dossier_site(cle)
    chemin_jeton = config.chemin_jeton(cle)
    anomalies, infos = [], []
    r = {"site": cle, "nom": cfg["nom"], "seuil": cfg["seuil_impressions"], "fin_gsc": None,
         "a_rediriger": [], "non_controlees": [], "anomalies": anomalies, "infos": infos,
         "resolues": [], "compte": {}, "protection": None}

    verifier_annulation()
    etape("Lecture de la Search Console")
    fin = gsc_api.dernier_jour(chemin_jeton, cfg["propriete"])
    if fin is None:
        infos.append("Votre site n'est apparu dans aucun résultat Google ces 10 derniers jours : "
                     "rien à analyser pour l'instant.")
        return r
    r["fin_gsc"] = fin
    fin_d = datetime.date.fromisoformat(fin)
    if (datetime.date.today() - fin_d).days > 6:
        anomalies.append("La Search Console n'a rien publié depuis le %s : l'analyse porte sur des "
                         "données anciennes." % date_fr(fin))
    debut7 = (fin_d - datetime.timedelta(days=6)).isoformat()

    recent = collections.Counter()
    for l in gsc_api.donnees(chemin_jeton, cfg["propriete"], debut7, fin, ("page",), frais=True):
        if "#" not in l["URL"] and "?" not in l["URL"]:
            recent[l["URL"]] += l["Impressions"]

    hist_p = os.path.join(D, "veille_historique.json")
    hist = _lire_json(hist_p, {})
    fenetre_30j = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    ref_gsc = max([v.get("pages_7j", 0) for k, v in hist.items() if k >= fenetre_30j] or [0])
    if ref_gsc >= MIN_PAGES_REFERENCE and len(recent) < 0.4 * ref_gsc:
        raise ErreurDonnees(
            "La Search Console renvoie beaucoup moins de pages que d'habitude (%d contre %d). "
            "Analyse suspendue pour ne pas conclure à tort ; nouvel essai à la prochaine analyse."
            % (len(recent), ref_gsc))
    if not recent:
        infos.append("Aucune page de votre site n'est apparue dans Google ces 7 derniers jours : "
                     "rien à analyser pour l'instant.")
        return r

    verifier_annulation()
    etape("Lecture du plan de site")
    plan = sitemap.plan_de_site(cfg["sitemaps"], journal, strict=True, verifier=verifier_annulation)
    if not plan:
        raise ErreurPlanDeSite("Le plan de site de votre site ne contient aucune page (%s)."
                               % ", ".join(cfg["sitemaps"]))
    ref_plan = max([v.get("plan", 0) for k, v in hist.items() if k >= fenetre_30j] or [0])
    if len(plan) < 0.8 * ref_plan:
        raise ErreurPlanDeSite(
            "Le plan de site contient beaucoup moins de pages que d'habitude (%d contre %d). "
            "Analyse suspendue pour ne pas conclure à tort." % (len(plan), ref_plan))
    cles_plan = {urls.cle_url(u) for u in plan}
    hotes = {urls.hote(u) for u in plan}

    def hors_plan(u):
        return urls.hote(u) in hotes and urls.cle_url(u) not in cles_plan

    variantes = collections.defaultdict(set)
    for u in recent:
        if hors_plan(u):
            variantes[urls.cle_chemin(u)].add(u)
    actifs = {urls.cle_chemin(u) for u in recent if hors_plan(u)}

    # inspection des variantes actives jamais inspectées, dans la limite du jour : d'abord celles
    # dont l'adresse est assez vue pour être à corriger, les plus vues en tête. Les autres ne
    # servent qu'au décompte des adresses inventées sous le seuil, avec ce qui reste de la limite.
    seuil = cfg["seuil_impressions"]
    vues = {p: sum(recent[u] for u in variantes[p]) for p in actifs}
    CI = os.path.join(D, "inspection.jsonl")
    insp_tout = _lire_jsonl(CI)
    insp = {u: x for u, x in insp_tout.items() if x.get("http") == 200}
    file_ = sorted({u for p in actifs for u in variantes[p] if u not in insp},
                   key=lambda u: (vues[urls.cle_chemin(u)] < seuil, -recent[u], u))
    # seules les inspections réussies comptent (une adresse vérifiée ne l'est plus jamais) : un
    # échec (réseau, quota) n'use pas la limite, et ECHECS_A_LA_SUITE borne les nouveaux essais
    faites = sum(1 for x in insp_tout.values() if x.get("veille") == aujourd_hui and x.get("http") == 200)
    a_inspecter = file_[:max(0, INSPECTIONS_PAR_JOUR - faites)]
    codes_insp = collections.Counter()
    cadence, prochaine, echecs_suite = threading.Lock(), [0.0], [0]

    def inspecter(u):
        # après une annulation, les inspections pas encore parties ne partent plus (None) ; après
        # ECHECS_A_LA_SUITE échecs d'affilée, plus aucune ne part (non_tentee) ; sinon une toutes
        # les CADENCE_INSPECTIONS secondes au plus, tous fils confondus
        if _annulee():
            return None
        with cadence:
            if echecs_suite[0] >= ECHECS_A_LA_SUITE:
                return {"url": u, "http": None, "non_tentee": True}
            depart = max(time.monotonic(), prochaine[0])
            prochaine[0] = depart + CADENCE_INSPECTIONS
        time.sleep(max(0.0, depart - time.monotonic()))
        if _annulee():
            return None
        x = gsc_api.inspecter(chemin_jeton, u, cfg["propriete"])
        with cadence:
            echecs_suite[0] = 0 if x.get("http") == 200 else echecs_suite[0] + 1
        return x
    verifier_annulation()
    sautees = 0
    if a_inspecter:
        etape("Vérification de %d adresse%s auprès de Google" % (len(a_inspecter), "s" if len(a_inspecter) > 1 else ""))
        with io.open(CI, "a", encoding="utf-8") as f, cf.ThreadPoolExecutor(6) as ex:
            for x in ex.map(inspecter, a_inspecter):
                if x is None:
                    sautees += 1
                    continue
                codes_insp[x.get("http")] += 1
                if x.get("non_tentee"):
                    continue
                f.write(json.dumps(dict(x, veille=aujourd_hui), ensure_ascii=False) + "\n")
                f.flush()
                insp_tout[x["url"]] = x
                if x.get("http") == 200:
                    insp[x["url"]] = x
    if sautees:                                # des adresses pas vérifiées : jamais un site complet
        raise AnalyseAnnulee()
    verifier_annulation()
    # une adresse assez vue pour être à corriger et pas vérifiée est toujours signalée ; les
    # autres, qui ne servent qu'au décompte sous le seuil, au-delà de 10 % d'échecs. Décompte par
    # adresse, toutes variantes comprises, comme les adresses à corriger.
    echouees = {urls.cle_chemin(u) for u in a_inspecter if u not in insp}
    echouees_seuil = {p for p in echouees if vues[p] >= seuil}
    # un échec n'use pas la limite du jour : il reste toujours de quoi réessayer à l'analyse suivante
    if codes_insp.get(403) or echouees_seuil or len(echouees) > 0.1 * max(1, len(a_inspecter)):
        journal("   inspections en échec : %s" % dict(codes_insp))
        anomalies.append("Google n'a pas pu vérifier %d adresse%s aujourd'hui : nouvel essai à la "
                         "prochaine analyse." % (len(echouees), "s" if len(echouees) > 1 else ""))
    reportees = len({urls.cle_chemin(u) for u in file_[len(a_inspecter):]
                     if vues[urls.cle_chemin(u)] >= seuil} - echouees_seuil)
    if reportees:
        s = "s" if reportees > 1 else ""
        anomalies.append("%d adresse%s vue%s au moins %d fois reste%s à vérifier auprès de Google (%s "
                         "adresses vérifiées par jour et par site au plus) : suite demain."
                         % (reportees, s, s, seuil, "nt" if reportees > 1 else "",
                            "{:,}".format(INSPECTIONS_PAR_JOUR).replace(",", "\xa0")))
    _compacter(CI, insp_tout)

    # de vraies pages absentes du plan de site : chacune coûte une vérification auprès de Google
    def indexee(x):
        c = ((x or {}).get("coverage") or "").lower()
        return "indexée" in c and "non indexée" not in c
    connues = sorted((p for p in actifs if any(indexee(insp.get(u)) for u in variantes[p])), key=lambda p: (-vues[p], p))
    if len(connues) >= PAGES_HORS_PLAN_A_SIGNALER:
        exemple = urls.chemin(max(sorted(variantes[connues[0]]), key=lambda u: recent[u]))
        infos.append("Google montre %d pages de votre site absentes du plan de site, par exemple %s. Chaque "
                     "nouvelle page absente du plan de site demande une vérification auprès de Google, dans la limite "
                     "de %s par jour. Ajoutez-les au plan de site, ou ajoutez les plans de site qui manquent dans "
                     "Modifier ce site." % (len(connues), exemple,
                                            "{:,}".format(INSPECTIONS_PAR_JOUR).replace(",", "\xa0")))

    ecartes = {urls.cle_chemin(p) for p in config.lire_ecartees(cle)}
    inventes = {p for p in actifs if any((insp.get(u) or {}).get("coverage") == INCONNUE for u in variantes[p])}
    suspects = {p: sorted(variantes[p]) for p in inventes
                if p not in ecartes and sum(recent[u] for u in variantes[p]) >= cfg["seuil_impressions"]}
    sous_seuil = len([p for p in inventes if p not in ecartes and p not in suspects])

    # contrôle HTTP : une adresse en erreur une fois par jour, une adresse corrigée tous les
    # RECONTROLE_CORRIGEES jours, une réponse bloquée ou en panne à chaque analyse (une fois la
    # protection du site réglée, Analyser maintenant doit le montrer tout de suite)
    if suspects:
        etape("Test de %d adresse%s sur votre site" % (len(suspects), "s" if len(suspects) > 1 else ""))
    CH = os.path.join(D, "codes_http.jsonl")
    http = _lire_jsonl(CH)
    limite = (datetime.date.today() - datetime.timedelta(days=RECONTROLE_CORRIGEES)).isoformat()
    non_controlees, resolues = [], set()
    with io.open(CH, "a", encoding="utf-8") as f:
        for p, us in suspects.items():
            for u in us:
                h = http.get(u) or {}
                code, veille = h.get("code"), h.get("veille") or ""
                frais = (code in ERREURS and veille == aujourd_hui) or (corrigee(code) and veille >= limite)
                if not frais:
                    verifier_annulation()
                    h = dict(controleur_http.controler(u), url=u, veille=aujourd_hui)
                    f.write(json.dumps(h, ensure_ascii=False) + "\n")
                    f.flush()
                    http[u] = h
            codes = [(http.get(u) or {}).get("code") for u in us]
            erreurs = [(http.get(u) or {}).get("erreur", "") for u in us]
            protections = [(http.get(u) or {}).get("protection") for u in us]
            if any(c in ERREURS for c in codes):
                continue
            if all(corrigee(c) for c in codes):
                resolues.add(p)
            elif any("Domain Not Found" in e for e in erreurs):
                resolues.add(p)                  # sous-domaine inexistant : aucune redirection possible
            else:
                non_controlees.append({"chemin": p, "codes": codes, "erreur": next((e for e in erreurs if e), ""),
                                       "protection": next((x for x in protections if x), None)})
    _compacter(CH, http)
    bloquees = [x for x in non_controlees if x["protection"]]
    if bloquees:
        n, r["protection"] = len(bloquees), bloquees[0]["protection"]
        anomalies.append("Votre site bloque l'outil (protection anti-robots %s) : %d adresse%s n'%s pas pu "
                         "être testée%s. Ajoutez l'adresse IP de cet ordinateur en exception dans %s pour "
                         "laisser passer l'outil." % (r["protection"], n, "s" if n > 1 else "",
                                                      "ont" if n > 1 else "a", "s" if n > 1 else "", r["protection"]))
    n = len(non_controlees) - len(bloquees)
    if n:
        anomalies.append("%d adresse%s n'%s pas pu être testée%s sur votre site (réponse bloquée ou "
                         "erreur du serveur) : nouvel essai à la prochaine analyse."
                         % (n, "s" if n > 1 else "", "ont" if n > 1 else "a", "s" if n > 1 else ""))

    # recherche d'une page similaire, par son adresse puis, si l'adresse ne suffit pas, par
    # les titres des pages les plus proches : proposée seulement si elle ressemble assez
    a_rediriger = []
    exclues = resolues | {x["chemin"] for x in non_controlees}
    if any(p not in exclues for p in suspects):
        etape("Recherche de pages similaires")
    CT = os.path.join(D, "titres.jsonl")
    titres = _lire_jsonl(CT)
    limite_titres = (datetime.date.today() - datetime.timedelta(days=VALIDITE_TITRES)).isoformat()

    def slug_de(u):
        return matching.plie(urls.chemin(u).rsplit("/", 1)[-1])

    def textes(v):
        t = titres.get(v) or {}
        # une page illisible (None) est réessayée le lendemain, une page lue au bout de 30 jours
        if not (t.get("veille") == aujourd_hui or (t.get("textes") is not None and t.get("veille", "") >= limite_titres)):
            verifier_annulation()
            t = {"url": v, "veille": aujourd_hui, "textes": controleur_http.lire_titres(v)}
            with io.open(CT, "a", encoding="utf-8") as f:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")
            titres[v] = t
        return t["textes"] or []

    def sure(notes):
        return notes[0][0] >= SEUIL_SURE and notes[0][0] - (notes[1][0] if len(notes) > 1 else 0.0) >= ECART_SUR

    for p, us in suspects.items():
        if p in exclues:
            continue
        exemple = next((u for u in us if (http.get(u) or {}).get("code") in ERREURS), None)
        if exemple is None:
            continue
        sec = urls.chemin(exemple).rsplit("/", 1)[0]
        pool = [v for v in plan if urls.chemin(v).rsplit("/", 1)[0] == sec] or list(plan)
        slug = slug_de(exemple)
        notes = sorted(((matching.ressemblance(slug, slug_de(v)), v) for v in pool), reverse=True)
        if notes and not sure(notes):
            notes[:TITRES_A_LIRE] = [(matching.ressemblance_page(slug, slug_de(v), textes(v)), v)
                                     for _, v in notes[:TITRES_A_LIRE]]
            notes.sort(reverse=True)
        score = notes[0][0] if notes else 0.0
        cible = notes[0][1] if notes and score >= SEUIL_PROPOSITION else ""
        a_rediriger.append({"chemin": urls.chemin(exemple), "cle": p, "adresse": exemple,
                            "impressions": sum(recent[u] for u in us),
                            "cible_url": cible, "cible_proposee": urls.chemin(cible) if cible else "",
                            "sure": bool(cible) and sure(notes),
                            "ressemblance": round(score, 2)})
    _compacter(CT, titres)
    a_rediriger.sort(key=lambda d: -d["impressions"])
    if sous_seuil:
        s = "s" if sous_seuil > 1 else ""
        infos.append("%d adresse%s inventée%s repérée%s, vue%s moins de %d fois dans Google ces 7 derniers jours : "
                     "pas assez pour justifier une redirection."
                     % (sous_seuil, s, s, s, s, cfg["seuil_impressions"]))

    hist[aujourd_hui] = {"pages_7j": len(recent), "plan": len(plan)}
    hist = {k: v for k, v in hist.items() if k >= (datetime.date.today() - datetime.timedelta(days=60)).isoformat()}
    _ecrire_json(hist_p, hist)
    r.update({"a_rediriger": a_rediriger, "non_controlees": non_controlees, "resolues": sorted(resolues),
              "compte": {"hors_plan_actifs": len(actifs), "inspectees": len(a_inspecter),
                         "inspections_ok": codes_insp.get(200, 0), "inventees_actives": len(inventes),
                         "suspects": len(suspects)}})
    return r


# --- tous les sites ----------------------------------------------------------------------------
def _nouvelles_du_site(r):
    """(fichier des adresses déjà signalées, adresses déjà signalées, nouvelles adresses) :
    nouvelle = jamais signalée, ou signalée puis résolue et de nouveau en erreur."""
    p = os.path.join(config.dossier_site(r["site"]), "veille_deja_alertees.json")
    deja = {urls.cle_chemin(x) for x in _lire_json(p, [])}
    deja -= set(r["resolues"])
    return p, deja, {d["cle"] for d in r["a_rediriger"]} - deja


def _etat_du_site(r, nouvelles, ancien, maintenant):
    statut = "a_corriger" if r["a_rediriger"] else ("incomplet" if r["anomalies"] else "ok")
    return {"date": maintenant, "statut": statut, "fin_gsc": r["fin_gsc"],
            "a_rediriger": r["a_rediriger"], "anomalies": r["anomalies"], "infos": r["infos"],
            "protection": r.get("protection"), "nouvelles": sorted(nouvelles), "probleme_notifie": ancien.get("probleme_notifie")}


def _publier_etat_du_site(cle, entree):
    """Écrit l'état d'un site dès la fin de son analyse : l'interface, rechargée toutes les
    3 secondes pendant une analyse, l'affiche sans attendre la fin des sites suivants."""
    etat = lire_etat()
    etat[cle] = entree
    _ecrire_json(chemin_etat(), etat)


def executer(test=False, interactif=False, cles=None):
    """Une analyse de tous les sites, ou des seuls sites de cles (bouton Analyser d'un
    site, ou des sites affichés dans l'interface). interactif=True : lancée depuis
    l'interface, que l'utilisateur regarde ; pas de notification, les adresses
    affichées comptent comme vues. Rend un résumé, ou {"deja_en_cours": True}."""
    if not _prendre_verrou():
        return {"deja_en_cours": True}
    try:
        return _executer(test, interactif, cles)
    finally:
        _rendre_verrou()


def _executer(test, interactif, cles=None):
    t0 = time.time()
    aujourd_hui = datetime.date.today().isoformat()
    maintenant = datetime.datetime.now().isoformat(timespec="minutes")
    D = config.dossier_config()
    journal = _journal_vers(os.path.join(D, "veille.log"))
    sites = config.lire()["sites"]
    if not sites:
        journal("aucun site configuré : rien à faire")
        return {"resultats": [], "echecs": {}, "reportes": [], "nouvelles": {}, "notifiee": False, "rapport": None,
                "annulee": False}

    resultats, echecs, reportes, entrees, suivis = [], {}, [], {}, {}
    annulee = False
    for cle in report.ordre_des_sites(sites, lire_etat()):      # dans l'ordre de Mes sites
        cfg = sites[cle]
        if cles is not None and cle not in cles:
            continue
        if _annulee():
            annulee = True
            break
        if time.time() - t0 > DUREE_MAX:
            reportes.append(cle)
            continue

        def etape(msg, _nom=cfg["nom"]):
            _ecrire_json(chemin_progression(), {"site": _nom, "etape": msg})
        controleur = ControleurHTTP(dataforseo=cfg.get("dataforseo"))
        try:
            r = veille_site(cle, cfg, controleur, journal, aujourd_hui, etape)
            resultats.append(r)
            journal("%-16s GSC au %s | %d à corriger%s" % (
                cfg["nom"], r["fin_gsc"], len(r["a_rediriger"]),
                (" | " + " ; ".join(r["anomalies"])) if r["anomalies"] else ""))
            suivis[cle] = _nouvelles_du_site(r)
            entrees[cle] = _etat_du_site(r, suivis[cle][2], lire_etat().get(cle, {}), maintenant)
        except AnalyseAnnulee:
            journal("%-16s analyse annulée : le site garde ses résultats précédents" % cfg["nom"])
            annulee = True
            break
        except Exception as ex:
            message, action = expliquer(ex)
            echecs[cle] = {"message": message, "action": action}
            journal("%-16s PROBLÈME : %s%s" % (cfg.get("nom", cle), message,
                                              (" | " + ex.detail) if getattr(ex, "detail", "") else ""))
            journal(traceback.format_exc())
            entrees[cle] = dict(lire_etat().get(cle, {}), date=maintenant, statut="probleme",
                                message=message, action=action)
        if not test:
            _publier_etat_du_site(cle, entrees[cle])

    nouvelles = {site: n for site, (_, _, n) in suivis.items() if n}

    # état de chaque site pour le rapport et les notifications
    etat = {k: v for k, v in lire_etat().items() if k in sites}
    etat.update(entrees)
    for cle in reportes:
        etat.setdefault(cle, {})["statut_passage"] = "reporte"

    chemin_rapport = report.ecrire(D, report.rendre(etat, sites, maintenant), aujourd_hui)

    # notifications
    envoyee = True
    total = sum(len(v) for v in nouvelles.values())
    if total and not interactif:
        if len(nouvelles) == 1:
            k = next(iter(nouvelles))
            titre = "%s : %d adresse%s à corriger" % (sites[k]["nom"], total, "s" if total > 1 else "")
        else:
            titre = "%d adresses à corriger sur %d sites" % (total, len(nouvelles))
        texte = "Google montre des adresses de votre site qui n'existent pas. " + plateforme.appel_notification()
        if test:
            journal("notification (non envoyée en test) : %s | %s" % (titre, texte))
        else:
            envoyee = plateforme.notifier(titre, texte, chemin_rapport, journal)

    # problèmes : une notification par jour au plus, et seulement si le problème a changé
    a_signaler = []
    for cle, e in etat.items():
        if e.get("statut") not in ("probleme", "incomplet"):
            continue
        message = e.get("message") or " ".join(e.get("anomalies") or [])
        deja_notifie = e.get("probleme_notifie") or {}
        if deja_notifie.get("date") == aujourd_hui and deja_notifie.get("message") == message:
            continue
        a_signaler.append((cle, message))
    if a_signaler and not interactif and not test:
        cle, message = a_signaler[0]
        titre = ("%s : analyse impossible" % sites[cle]["nom"] if etat[cle]["statut"] == "probleme"
                 else "%s : analyse incomplète" % sites[cle]["nom"])
        if len(a_signaler) > 1:
            titre = "Bifurq AIO : %d sites à vérifier" % len(a_signaler)
        if plateforme.notifier(titre, message[:200], chemin_rapport, journal):
            for cle, message in a_signaler:
                etat[cle]["probleme_notifie"] = {"date": aujourd_hui, "message": message}

    if not test:
        _ecrire_json(chemin_etat(), etat)
        for site, (p, deja, n) in suivis.items():
            _ecrire_json(p, sorted(deja | (n if envoyee else set())))
        _ecrire_json(os.path.join(D, "derniere_execution.json"),
                     {"date": maintenant, "sites_ok": [r["site"] for r in resultats], "echecs": echecs,
                      "reportes": reportes, "notification_envoyee": envoyee, "annulee": annulee})
        chemin_jour = os.path.join(D, "veille_%s.json" % aujourd_hui)
        jour = {"date": aujourd_hui, "resultats": resultats, "echecs": echecs, "reportes": reportes}
        if cles is not None or annulee:       # une partie des sites : les autres résultats du jour restent
            faits = {r["site"] for r in resultats} | set(echecs)
            ancien = _lire_json(chemin_jour, {})
            jour["resultats"] = [r for r in ancien.get("resultats", []) if r.get("site") not in faits] + resultats
            jour["echecs"] = dict({k: v for k, v in ancien.get("echecs", {}).items() if k not in faits}, **echecs)
        _ecrire_json(chemin_jour, jour)
        anciens = sorted(f for f in os.listdir(D) if re.match(r"veille_\d{4}-\d\d-\d\d\.json$", f))[:-60]
        for f in anciens:
            os.remove(os.path.join(D, f))

    journal("%s en %d min : %d à corriger dont %d nouvelles, %d site(s) en problème"
            % ("annulée par l'utilisateur" if annulee else "terminé", (time.time() - t0) // 60,
               sum(len(r["a_rediriger"]) for r in resultats), total, len(echecs)))
    return {"resultats": resultats, "echecs": echecs, "reportes": reportes, "nouvelles": nouvelles,
            "notifiee": envoyee, "rapport": chemin_rapport, "annulee": annulee}
