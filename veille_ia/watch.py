# -*- coding: utf-8 -*-
"""Analyse des sites : un passage par site, l'état de chaque site pour l'interface
(config/etat.json), le rapport et les notifications.

Le process, pour chaque site :
  1. repérer les adresses qui ont des impressions récentes dans la Search Console,
     absentes du plan de site, que Google n'a jamais explorées (donc inventées), et
     qui répondent en erreur (404 ou 410) ;
  2. chercher, parmi les pages du plan de site, celle qui leur ressemble ;
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
  - une même panne notifiée à chaque démarrage du PC : une fois par jour au plus."""
import collections
import concurrent.futures as cf
import datetime
import io
import json
import os
import re
import time
import traceback

from . import config, gsc_api, matching, report, sitemap, urls
from .erreurs import ErreurDonnees, ErreurPlanDeSite, expliquer
from .http_check import ERREURS, ControleurHTTP, corrigee

FENETRE_JOURS = 90                 # cumul des impressions : les 3 derniers mois publiés
MAX_INSPECTIONS = 300              # par site et par jour ; quota Google : 2 000
RECONTROLE_CORRIGEES = 7           # jours entre deux tests d'une adresse déjà corrigée
DUREE_MAX = 90 * 60                # au-delà, les sites restants sont reportés
VERROU_MAX = 3 * 3600              # un verrou plus vieux est celui d'une analyse morte
MIN_PAGES_REFERENCE = 20           # en dessous, pas de détection de chute brutale
SEUIL_PROPOSITION = 0.6            # ressemblance minimale pour proposer une page (calé le
                                   # 24.09.2026 sur un vrai site : 0,57 menait à une page sans rapport)
SEUIL_SURE, ECART_SUR = 0.75, 0.1  # correspondance sûre : score et avance sur la 2e
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


def _processus_actif(pid):
    """Sans os.kill : sous Windows, os.kill termine le processus au lieu de le sonder."""
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, int(pid))        # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return bool(ok) and code.value == 259               # STILL_ACTIVE
    except Exception:
        return True                                         # dans le doute, ne pas voler le verrou


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
    return time.time() - v.get("debut", 0) < VERROU_MAX and _processus_actif(v.get("pid", 0))


def _prendre_verrou():
    if analyse_en_cours():
        return False
    _ecrire_json(chemin_verrou(), {"pid": os.getpid(), "debut": time.time()})
    return True


def _rendre_verrou():
    for p in (chemin_verrou(), chemin_progression()):
        try:
            os.remove(p)
        except OSError:
            pass


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
    debut = (fin_d - datetime.timedelta(days=FENETRE_JOURS - 1)).isoformat()

    cumul, recent = collections.Counter(), collections.Counter()
    for l in gsc_api.donnees(chemin_jeton, cfg["propriete"], debut, fin, ("page",)):
        if "#" not in l["URL"] and "?" not in l["URL"]:
            cumul[l["URL"]] += l["Impressions"]
    for l in gsc_api.donnees(chemin_jeton, cfg["propriete"], debut7, fin, ("page",)):
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

    etape("Lecture du plan de site")
    plan = sitemap.plan_de_site(cfg["sitemaps"], journal, strict=True)
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
    for u in cumul:
        if hors_plan(u):
            variantes[urls.cle_chemin(u)].add(u)
    actifs = {urls.cle_chemin(u) for u in recent if hors_plan(u)}

    # inspection des variantes actives jamais inspectées
    CI = os.path.join(D, "inspection.jsonl")
    insp_tout = _lire_jsonl(CI)
    insp = {u: x for u, x in insp_tout.items() if x.get("http") == 200}
    file_ = sorted({u for p in actifs for u in variantes[p] if u in recent and u not in insp}, key=lambda u: -recent[u])
    a_inspecter, reportees = file_[:MAX_INSPECTIONS], max(0, len(file_) - MAX_INSPECTIONS)
    codes_insp = collections.Counter()
    if a_inspecter:
        etape("Vérification de %d adresse%s auprès de Google" % (len(a_inspecter), "s" if len(a_inspecter) > 1 else ""))
        with io.open(CI, "a", encoding="utf-8") as f, cf.ThreadPoolExecutor(6) as ex:
            for x in ex.map(lambda u: gsc_api.inspecter(chemin_jeton, u, cfg["propriete"]), a_inspecter):
                codes_insp[x.get("http")] += 1
                f.write(json.dumps(dict(x, veille=aujourd_hui), ensure_ascii=False) + "\n")
                f.flush()
                insp_tout[x["url"]] = x
                if x.get("http") == 200:
                    insp[x["url"]] = x
    echecs_insp = sum(n for c, n in codes_insp.items() if c != 200)
    if codes_insp.get(403) or echecs_insp > 0.1 * max(1, len(a_inspecter)):
        journal("   inspections en échec : %s" % dict(codes_insp))
        anomalies.append("Google n'a pas pu vérifier %d adresse%s aujourd'hui : nouvel essai à la "
                         "prochaine analyse." % (echecs_insp, "s" if echecs_insp > 1 else ""))
    if reportees:
        anomalies.append("%d adresses restent à vérifier (limite quotidienne de Google atteinte) : "
                         "suite à la prochaine analyse." % reportees)
    _compacter(CI, insp_tout)

    ecartes = {urls.cle_chemin(p) for p in config.lire_ecartees(cle)}
    inventes = {p for p in actifs if any((insp.get(u) or {}).get("coverage") == INCONNUE for u in variantes[p])}
    suspects = {p: sorted(variantes[p]) for p in inventes
                if p not in ecartes and sum(cumul[u] for u in variantes[p]) >= cfg["seuil_impressions"]}
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

    # recherche d'une page similaire : proposée seulement si elle ressemble assez
    a_rediriger = []
    exclues = resolues | {x["chemin"] for x in non_controlees}
    if any(p not in exclues for p in suspects):
        etape("Recherche de pages similaires")
    for p, us in suspects.items():
        if p in exclues:
            continue
        exemple = next((u for u in us if (http.get(u) or {}).get("code") in ERREURS), None)
        if exemple is None:
            continue
        sec = urls.chemin(exemple).rsplit("/", 1)[0]
        pool = [v for v in plan if urls.chemin(v).rsplit("/", 1)[0] == sec] or list(plan)
        slug = matching.plie(urls.chemin(exemple).rsplit("/", 1)[-1])
        notes = sorted(((matching.ressemblance(slug, matching.plie(urls.chemin(v).rsplit("/", 1)[-1])), v)
                        for v in pool), reverse=True)[:2]
        score = notes[0][0] if notes else 0.0
        ecart = score - (notes[1][0] if len(notes) > 1 else 0.0)
        cible = notes[0][1] if notes and score >= SEUIL_PROPOSITION else ""
        a_rediriger.append({"chemin": urls.chemin(exemple), "cle": p, "adresse": exemple,
                            "impressions": sum(cumul[u] for u in us), "impressions_7j": sum(recent[u] for u in us),
                            "cible_url": cible, "cible_proposee": urls.chemin(cible) if cible else "",
                            "sure": bool(cible) and score >= SEUIL_SURE and ecart >= ECART_SUR,
                            "ressemblance": round(score, 2)})
    a_rediriger.sort(key=lambda d: -d["impressions"])
    if sous_seuil:
        s = "s" if sous_seuil > 1 else ""
        infos.append("%d adresse%s inventée%s repérée%s, vue%s moins de %d fois dans Google en 3 mois : "
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
    l'interface, que l'utilisateur regarde ; pas de notification Windows, les adresses
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
        return {"resultats": [], "echecs": {}, "reportes": [], "nouvelles": {}, "notifiee": False, "rapport": None}

    resultats, echecs, reportes, entrees, suivis = [], {}, [], {}, {}
    for cle, cfg in sites.items():
        if cles is not None and cle not in cles:
            continue
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
    from . import notify_windows
    envoyee = True
    total = sum(len(v) for v in nouvelles.values())
    if total and not interactif:
        if len(nouvelles) == 1:
            k = next(iter(nouvelles))
            titre = "%s : %d adresse%s à corriger" % (sites[k]["nom"], total, "s" if total > 1 else "")
        else:
            titre = "%d adresses à corriger sur %d sites" % (total, len(nouvelles))
        texte = "Google montre des adresses de votre site qui n'existent pas. Cliquez pour voir quoi faire."
        if test:
            journal("notification (non envoyée en test) : %s | %s" % (titre, texte))
        else:
            envoyee = notify_windows.notifier(titre, texte, chemin_rapport, journal)

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
        if notify_windows.notifier(titre, message[:200], chemin_rapport, journal):
            for cle, message in a_signaler:
                etat[cle]["probleme_notifie"] = {"date": aujourd_hui, "message": message}

    if not test:
        _ecrire_json(chemin_etat(), etat)
        for site, (p, deja, n) in suivis.items():
            _ecrire_json(p, sorted(deja | (n if envoyee else set())))
        _ecrire_json(os.path.join(D, "derniere_execution.json"),
                     {"date": maintenant, "sites_ok": [r["site"] for r in resultats], "echecs": echecs,
                      "reportes": reportes, "notification_envoyee": envoyee})
        chemin_jour = os.path.join(D, "veille_%s.json" % aujourd_hui)
        jour = {"date": aujourd_hui, "resultats": resultats, "echecs": echecs, "reportes": reportes}
        if cles is not None:                  # quelques sites : les autres résultats du jour restent
            ancien = _lire_json(chemin_jour, {})
            jour["resultats"] = [r for r in ancien.get("resultats", []) if r.get("site") not in cles] + resultats
            jour["echecs"] = dict({k: v for k, v in ancien.get("echecs", {}).items() if k not in cles}, **echecs)
        _ecrire_json(chemin_jour, jour)
        anciens = sorted(f for f in os.listdir(D) if re.match(r"veille_\d{4}-\d\d-\d\d\.json$", f))[:-60]
        for f in anciens:
            os.remove(os.path.join(D, f))

    journal("terminé en %d min : %d à corriger dont %d nouvelles, %d site(s) en problème"
            % ((time.time() - t0) // 60, sum(len(r["a_rediriger"]) for r in resultats), total, len(echecs)))
    return {"resultats": resultats, "echecs": echecs, "reportes": reportes, "nouvelles": nouvelles,
            "notifiee": envoyee, "rapport": chemin_rapport}
