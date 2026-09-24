# -*- coding: utf-8 -*-
"""Serveur web local de l'outil : connexion Google, choix des sites, tableau de bord,
réglages. Bibliothèque standard uniquement (http.server).

Un seul utilisateur, sur son propre poste : l'état de la connexion en cours reste un
dict en mémoire. Trois protections tout de même :
  - le serveur n'écoute que 127.0.0.1 et refuse tout nom d'hôte autre que
    127.0.0.1 ou localhost (une page web piégée ne peut pas l'atteindre par un nom
    de domaine qui pointerait vers le poste) ;
  - toute action (formulaire POST) porte un jeton tiré au démarrage : une autre page
    ouverte dans le navigateur ne peut pas déclencher d'action à la place de
    l'utilisateur ;
  - la connexion Google vérifie le paramètre state renvoyé par Google.

Une seule instance à la fois : relancer l'outil (raccourci du bureau) rouvre la page
de l'instance déjà en route. Le serveur s'arrête seul après 45 minutes sans usage."""
import http.server
import io
import json
import os
import re
import secrets
import socket
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor

from .. import __version__, config, gsc_api, mise_a_jour, oauth, scheduler_windows, sitemap, watch
from ..erreurs import expliquer
from . import pages

PORT_PREFERE = 8765
REDIRECT_PATH = "/oauth2/callback"
INACTIVITE_MAX = 45 * 60
PING = "bifurq-aio"


def _empreinte():
    """Date du fichier de code le plus récent : une instance déjà ouverte avec une
    empreinte différente sert une ancienne version et doit céder la place."""
    paquet = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    plus_recent = 0.0
    for dossier, _, fichiers in os.walk(paquet):
        for f in fichiers:
            if f.endswith(".py"):
                plus_recent = max(plus_recent, os.path.getmtime(os.path.join(dossier, f)))
    return "%d" % plus_recent


EMPREINTE = _empreinte()

_session = {"etat_oauth": None, "jeton_temp": None, "reconnecter": None, "fil": None,
            "jeton_formulaire": secrets.token_urlsafe(24), "derniere_requete": time.time(),
            "mise_a_jour": None}


# --- analyse en arrière-plan -----------------------------------------------------------------
def analyse_active():
    f = _session.get("fil")
    return (f is not None and f.is_alive()) or watch.analyse_en_cours()


def lancer_analyse():
    if analyse_active():
        return False

    def travail():
        try:
            watch.executer(interactif=True)
        except Exception:
            _journal(traceback.format_exc())
    f = threading.Thread(target=travail, daemon=True)
    _session["fil"] = f
    f.start()
    return True


# --- utilitaires ---------------------------------------------------------------------------------
def _journal(texte):
    try:
        with io.open(os.path.join(config.dossier_config(), "serveur.log"), "a", encoding="utf-8") as f:
            f.write("%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M"), texte))
    except OSError:
        pass


def _chemin_temp():
    return os.path.join(config.dossier_config(), "_temp_jeton.json")


def _effacer_temp():
    try:
        os.remove(_chemin_temp())
    except OSError:
        pass
    _session["jeton_temp"] = None


def _nom_lisible(propriete):
    return gsc_api.proprietes_lisibles([{"siteUrl": propriete}])[0]["nom"]


def _cle_depuis_propriete(propriete, sites):
    cle = re.sub(r"[^a-z0-9]+", "-", _nom_lisible(propriete)).strip("-") or "site"
    base, n = cle, 2
    while cle in sites:
        cle = "%s-%d" % (base, n)
        n += 1
    return cle


def _racine_http(propriete):
    if propriete.startswith("http"):
        return propriete
    return "https://" + propriete.split(":", 1)[-1]


def _un(champs, nom, defaut=""):
    return (champs.get(nom) or [defaut])[0]


# --- requêtes ------------------------------------------------------------------------------------
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _hote_autorise(self):
        h = (self.headers.get("Host") or "").lower()
        port = self.server.server_port
        return h in ("127.0.0.1:%d" % port, "localhost:%d" % port)

    def _repondre(self, corps, code=200, type_contenu="text/html; charset=utf-8"):
        data = corps.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", type_contenu)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _rediriger(self, url, code=302):
        self.send_response(code)
        self.send_header("Location", url)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _redirect_uri(self):
        return "http://127.0.0.1:%d%s" % (self.server.server_port, REDIRECT_PATH)

    def _probleme(self, ex):
        _journal(traceback.format_exc())
        message, action = expliquer(ex)
        if action == "reconnecter":
            self._repondre(pages.erreur("Connexion Google à renouveler", message, "/connecter",
                                        "Reconnecter mon compte Google"), 500)
        else:
            self._repondre(pages.erreur("Un problème est survenu", message), 500)

    def do_GET(self):
        _session["derniere_requete"] = time.time()
        if not self._hote_autorise():
            return self._repondre("Accès refusé", 403, "text/plain; charset=utf-8")
        chemin, _, requete = self.path.partition("?")
        q = urllib.parse.parse_qs(requete)
        try:
            if chemin == "/ping":
                return self._repondre("%s %s" % (PING, EMPREINTE), 200, "text/plain; charset=utf-8")
            if chemin == "/":
                return self._accueil(q)
            if chemin == "/connecter":
                return self._connecter(q)
            if chemin == REDIRECT_PATH:
                return self._callback(q)
            if chemin == "/choisir":
                return self._choisir()
            if chemin == "/site":
                return self._site(q)
            if chemin == "/modifier":
                sites = config.lire()["sites"]
                cle = _un(q, "cle")
                if cle not in sites:
                    return self._rediriger("/")
                return self._repondre(pages.page_modifier(cle, sites[cle], _session["jeton_formulaire"]))
            if chemin == "/reglages":
                # après /arreter, la page affiche d'elle-même que la surveillance est arrêtée
                return self._repondre(pages.reglages(config.lire()["planification"], _session["jeton_formulaire"]))
            return self._repondre(pages.erreur("Page introuvable", "Cette page n'existe pas."), 404)
        except Exception as ex:
            self._probleme(ex)

    def do_POST(self):
        _session["derniere_requete"] = time.time()
        if not self._hote_autorise():
            return self._repondre("Accès refusé", 403, "text/plain; charset=utf-8")
        longueur = int(self.headers.get("Content-Length", 0) or 0)
        champs = urllib.parse.parse_qs(self.rfile.read(longueur).decode("utf-8") if longueur else "")
        if _un(champs, "jeton") != _session["jeton_formulaire"]:
            return self._repondre(pages.erreur("Action expirée", "Cette page date d'une session précédente de "
                                               "l'outil. Revenez à l'accueil et recommencez."), 403)
        try:
            routes = {"/activer": self._activer, "/analyser": self._analyser, "/ignorer": self._ignorer,
                      "/retirer": self._retirer, "/reglages": self._reglages, "/arreter": self._arreter,
                      "/modifier": self._modifier, "/masquer-consigne": self._masquer_consigne,
                      "/mettre-a-jour": self._mettre_a_jour}
            if self.path not in routes:
                return self._repondre(pages.erreur("Page introuvable", "Cette page n'existe pas."), 404)
            routes[self.path](champs)
        except Exception as ex:
            self._probleme(ex)

    # --- pages ---
    def _accueil(self, q=None):
        donnees = config.lire()
        if not donnees["sites"]:
            return self._repondre(pages.accueil())
        en_cours = analyse_active()
        self._repondre(pages.tableau_de_bord(donnees["sites"], watch.lire_etat(), en_cours,
                                             watch.lire_progression() if en_cours else None,
                                             donnees["planification"], _session["jeton_formulaire"],
                                             consigne=not donnees.get("interface", {}).get("consigne_masquee"),
                                             maj=mise_a_jour.disponible(),
                                             a_jour=_un(q or {}, "maj") == __version__))

    def _connecter(self, q):
        _session["reconnecter"] = _un(q, "site") or None
        _session["etat_oauth"] = oauth.nouvel_etat()
        self._rediriger(oauth.url_autorisation(self._redirect_uri(), _session["etat_oauth"]))

    def _callback(self, q):
        if _un(q, "error"):
            return self._repondre(pages.erreur("Connexion annulée", "Google n'a pas donné l'accès. Vous pouvez "
                                               "recommencer quand vous voulez.", "/connecter", "Recommencer"))
        code, etat = _un(q, "code"), _un(q, "state")
        if not code or not etat or etat != _session.get("etat_oauth"):
            return self._repondre(pages.erreur("Connexion interrompue", "La connexion n'a pas abouti. "
                                               "Recommencez depuis l'accueil.", "/connecter", "Recommencer"))
        _session["etat_oauth"] = None
        oauth.enregistrer_jeton(_chemin_temp(), oauth.echanger_code(code, self._redirect_uri()))
        _session["jeton_temp"] = _chemin_temp()
        if _session.get("reconnecter"):
            return self._reconnecter()
        self._rediriger("/choisir")

    def _reconnecter(self):
        """Le nouveau jeton sert au site à reconnecter et à tous les autres sites suivis que
        ce compte Google peut lire. Si ce compte n'a pas accès au site à reconnecter, rien ne
        change : un autre compte ne doit pas remplacer en silence une connexion qui marche."""
        cible, _session["reconnecter"] = _session["reconnecter"], None
        sites = config.lire()["sites"]
        accessibles = {p["siteUrl"] for p in gsc_api.lister_proprietes(_chemin_temp())
                       if p.get("permissionLevel") != "siteUnverifiedUser"}
        if cible in sites and sites[cible]["propriete"] not in accessibles:
            _effacer_temp()
            return self._repondre(pages.erreur(
                "Mauvais compte Google", "Ce compte Google n'a pas accès à la Search Console de %s. "
                "Reconnectez-vous avec le compte qui la gère." % sites[cible]["nom"],
                "/connecter?site=%s" % urllib.parse.quote(cible), "Choisir un autre compte"))
        contenu = io.open(_chemin_temp(), encoding="utf-8").read()
        mis_a_jour = 0
        for cle, cfg in sites.items():
            if cfg["propriete"] in accessibles:
                io.open(config.chemin_jeton(cle), "w", encoding="utf-8").write(contenu)
                mis_a_jour += 1
        _effacer_temp()
        if not mis_a_jour:
            return self._repondre(pages.erreur(
                "Mauvais compte Google", "Ce compte Google n'a accès à aucun des sites surveillés. "
                "Reconnectez-vous avec le compte qui gère la Search Console de vos sites.",
                "/connecter", "Choisir un autre compte"))
        lancer_analyse()
        self._rediriger("/")

    def _choisir(self, erreur=None):
        if not _session.get("jeton_temp") or not os.path.exists(_chemin_temp()):
            return self._rediriger("/connecter")
        donnees = config.lire()
        liste = gsc_api.proprietes_lisibles(gsc_api.lister_proprietes(_chemin_temp()))
        suivies = {cfg["propriete"] for cfg in donnees["sites"].values()}
        self._repondre(pages.choisir(liste, suivies, not donnees["sites"], donnees["planification"],
                                     _session["jeton_formulaire"], erreur))

    def _site(self, q):
        cle = _un(q, "cle")
        sites = config.lire()["sites"]
        if cle not in sites:
            return self._rediriger("/")
        self._repondre(pages.page_site(cle, sites[cle], watch.lire_etat().get(cle) or {}, analyse_active(),
                                       _session["jeton_formulaire"], len(config.lire_ecartees(cle))))

    # --- actions ---
    def _activer(self, champs):
        donnees = config.lire()
        choisies = [p for p in champs.get("proprietes") or []
                    if p not in {cfg["propriete"] for cfg in donnees["sites"].values()}]
        if not _session.get("jeton_temp") or not os.path.exists(_chemin_temp()):
            # formulaire envoyé une seconde fois (double clic pendant l'activation) : les sites
            # sont déjà ajoutés, retour à la liste plutôt qu'une nouvelle connexion Google
            if donnees["sites"] and not choisies:
                return self._rediriger("/", 303)
            return self._rediriger("/connecter", 303)
        premiere_fois = not donnees["sites"]
        if not choisies:
            return self._choisir("Cochez au moins un site.")
        au_demarrage = "au_demarrage" in champs
        actif_heure_fixe = "actif_heure_fixe" in champs
        heure_fixe = _un(champs, "heure_fixe", "09:15") or "09:15"
        if premiere_fois and not au_demarrage and not actif_heure_fixe:
            return self._choisir("Cochez au moins un moment de vérification.")
        try:
            seuil = max(1, int(_un(champs, "seuil", "15") or 15))
        except ValueError:
            seuil = 15
        login, motdepasse = _un(champs, "dataforseo_login").strip(), _un(champs, "dataforseo_password").strip()
        dataforseo = {"login": login, "password": motdepasse} if login and motdepasse else None

        contenu = io.open(_chemin_temp(), encoding="utf-8").read()
        racines = [_racine_http(p) for p in choisies]
        with ThreadPoolExecutor(max_workers=min(8, len(racines))) as pool:   # un site lent ne retarde pas les autres
            plans = list(pool.map(sitemap.deviner_sitemaps, racines))
        for propriete, racine, trouves in zip(choisies, racines, plans):
            cle = _cle_depuis_propriete(propriete, config.lire()["sites"])
            sitemaps = trouves or [racine.rstrip("/") + "/sitemap.xml"]
            config.ajouter_site(cle, nom=_nom_lisible(propriete), propriete=propriete, sitemaps=sitemaps,
                                seuil_impressions=seuil, dataforseo=dataforseo)
            io.open(config.chemin_jeton(cle), "w", encoding="utf-8").write(contenu)
        _effacer_temp()
        if premiere_fois:
            config.definir_planification(au_demarrage, actif_heure_fixe, heure_fixe)
            scheduler_windows.installer(au_demarrage, actif_heure_fixe, heure_fixe)
        lancer_analyse()
        self._rediriger("/", 303)

    def _masquer_consigne(self, champs):
        config.masquer_consigne()
        self._rediriger("/", 303)

    def _mettre_a_jour(self, champs):
        """Télécharge la nouvelle version, répond par une page qui attend la nouvelle
        interface, puis lance l'installateur, qui arrêtera celle-ci."""
        maj = mise_a_jour.disponible()
        if _session["mise_a_jour"]:                    # second clic : déjà en route
            return self._repondre(pages.mise_a_jour_en_cours(_session["mise_a_jour"], EMPREINTE))
        if not maj or analyse_active():
            return self._rediriger("/", 303)
        try:
            dossier_code = mise_a_jour.telecharger(maj["version"])
        except Exception:
            _journal(traceback.format_exc())
            return self._repondre(pages.erreur(
                "Mise à jour impossible", "La version %s n'a pas pu être téléchargée. Vérifiez votre connexion "
                "à Internet et réessayez." % maj["version"]), 502)
        _session["mise_a_jour"] = maj["version"]
        self._repondre(pages.mise_a_jour_en_cours(maj["version"], EMPREINTE))
        threading.Timer(1.0, mise_a_jour.lancer_installateur, (dossier_code, self.server.server_port)).start()

    def _analyser(self, champs):
        lancer_analyse()
        self._rediriger("/", 303)

    def _ignorer(self, champs):
        cle, adresse = _un(champs, "cle"), _un(champs, "adresse")
        if cle in config.lire()["sites"] and adresse:
            config.ajouter_ecartee(cle, adresse)
            watch.retirer_adresse(cle, adresse)
        self._rediriger("/site?cle=%s" % urllib.parse.quote(cle), 303)

    def _modifier(self, champs):
        cle = _un(champs, "cle")
        sites = config.lire()["sites"]
        if cle not in sites:
            return self._rediriger("/", 303)
        try:
            seuil = int(_un(champs, "seuil", "15"))
            if seuil < 1:
                raise ValueError
        except ValueError:
            return self._repondre(pages.page_modifier(cle, sites[cle], _session["jeton_formulaire"],
                                                      "Le nombre de vues minimum doit être un nombre entier, 1 ou plus."))
        plans = _un(champs, "sitemaps").splitlines()
        if not any(p.strip().startswith("http") for p in plans):
            return self._repondre(pages.page_modifier(cle, sites[cle], _session["jeton_formulaire"],
                                                      "Indiquez au moins une adresse de plan de site, commençant par https://."))
        login, motdepasse = _un(champs, "dataforseo_login").strip(), _un(champs, "dataforseo_password").strip()
        if "retirer_dataforseo" in champs:
            config.modifier_site(cle, _un(champs, "nom"), plans, seuil, None)
        elif login and motdepasse:
            config.modifier_site(cle, _un(champs, "nom"), plans, seuil, {"login": login, "password": motdepasse})
        else:
            config.modifier_site(cle, _un(champs, "nom"), plans, seuil)
        self._rediriger("/", 303)

    def _retirer(self, champs):
        cle = _un(champs, "cle")
        if cle in config.lire()["sites"]:
            config.retirer_site(cle)
            watch.oublier_site(cle)
            if not config.lire()["sites"]:
                scheduler_windows.desinstaller()
        self._rediriger("/", 303)

    def _reglages(self, champs):
        au_demarrage = "au_demarrage" in champs
        actif_heure_fixe = "actif_heure_fixe" in champs
        heure_fixe = _un(champs, "heure_fixe", "09:15") or "09:15"
        try:
            planif = config.definir_planification(au_demarrage, actif_heure_fixe, heure_fixe)
        except ValueError as ex:
            return self._repondre(pages.reglages(config.lire()["planification"], _session["jeton_formulaire"],
                                                 erreur=str(ex)))
        if config.lire()["sites"]:
            scheduler_windows.installer(au_demarrage, actif_heure_fixe, heure_fixe)
        self._repondre(pages.reglages(planif, _session["jeton_formulaire"], message="Réglages enregistrés."))

    def _arreter(self, champs):
        scheduler_windows.desinstaller()
        config.desactiver_planification()
        self._rediriger("/reglages?arret=1", 303)


# --- démarrage -----------------------------------------------------------------------------------
class Serveur(http.server.ThreadingHTTPServer):
    """Port réservé à cette seule copie de l'outil. Sous Windows, SO_REUSEADDR (posé par
    défaut par http.server) laisse une seconde copie, installée dans un autre dossier, se
    lier au même port : le navigateur parle alors à l'une ou à l'autre au hasard, et la
    connexion Google, gardée en mémoire par l'une, manque à l'autre."""
    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def _fichier_instance():
    return os.path.join(config.dossier_config(), "serveur.json")


def _instance_existante():
    """(port, pid, empreinte) de l'instance déjà ouverte, ou None."""
    try:
        infos = json.load(io.open(_fichier_instance(), encoding="utf-8"))
        reponse = urllib.request.urlopen("http://127.0.0.1:%d/ping" % infos["port"], timeout=2).read().decode()
    except Exception:
        return None
    nom, _, empreinte = reponse.partition(" ")
    return (infos["port"], infos.get("pid"), empreinte) if nom == PING else None


def _remplacer_instance(port, pid):
    """Arrête une instance qui sert une ancienne version du code."""
    import signal
    if pid:
        try:
            os.kill(int(pid), signal.SIGTERM)           # sous Windows : fin immédiate du processus
        except OSError:
            pass
    for _ in range(20):                                 # attendre que le port se libère
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/ping" % port, timeout=0.5)
            time.sleep(0.25)
        except Exception:
            return


def demarrer(port_prefere=PORT_PREFERE, ouvrir_navigateur=True):
    if sys.stdout is None:                   # lancé par pythonw (raccourci) : aucune console
        sortie = io.open(os.path.join(config.dossier_config(), "serveur.log"), "a", encoding="utf-8")
        sys.stdout = sys.stderr = sortie
    instance = _instance_existante()
    if instance:
        port, pid, empreinte = instance
        if empreinte == EMPREINTE:
            if ouvrir_navigateur:
                webbrowser.open("http://127.0.0.1:%d/" % port)
            return
        print("ancienne version ouverte (%s) : remplacée" % (empreinte or "sans empreinte"), flush=True)
        _remplacer_instance(port, pid)
    try:
        httpd = Serveur(("127.0.0.1", port_prefere), Handler)
    except OSError:                          # port pris, par exemple par une autre copie de l'outil
        httpd = Serveur(("127.0.0.1", 0), Handler)
    url = "http://127.0.0.1:%d/" % httpd.server_port
    io.open(_fichier_instance(), "w", encoding="utf-8").write(json.dumps({"port": httpd.server_port, "pid": os.getpid()}))

    def veilleur():
        while True:
            time.sleep(60)
            if time.time() - _session["derniere_requete"] > INACTIVITE_MAX and not analyse_active():
                httpd.shutdown()
                return
    threading.Thread(target=veilleur, daemon=True).start()
    print("outil ouvert sur %s" % url, flush=True)
    # nouvelle version : lue en parallèle, avant l'ouverture de la page si elle répond vite
    verification = threading.Thread(target=mise_a_jour.verifier, daemon=True)
    verification.start()
    if ouvrir_navigateur:
        verification.join(1.5)
        threading.Timer(0.1, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        _effacer_temp()
        try:
            os.remove(_fichier_instance())
        except OSError:
            pass


def _arguments(args):
    """--port N (port à reprendre, après une mise à jour) et --sans-navigateur."""
    port = PORT_PREFERE
    if "--port" in args:
        i = args.index("--port")
        if i + 1 < len(args) and args[i + 1].isdigit():
            port = int(args[i + 1])
    return port, "--sans-navigateur" not in args


if __name__ == "__main__":
    port, navigateur = _arguments(sys.argv[1:])
    demarrer(port, navigateur)
