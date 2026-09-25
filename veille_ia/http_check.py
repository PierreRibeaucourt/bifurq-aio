# -*- coding: utf-8 -*-
"""Code HTTP d'une adresse suspecte : confirme qu'elle répond bien en erreur (404 ou
410) avant de la proposer en redirection (un contrôle HTTP raté ne doit jamais se lire
comme une erreur confirmée).

Deux voies, choisies par site :
  - par défaut, une requête directe depuis le poste de l'utilisateur vers SON PROPRE
    site : légitime, à la différence d'un crawl de sites tiers. Un pare-feu ou un CDN
    peut renvoyer un code trompeur (403, 503) : à signaler comme "à vérifier", jamais
    comme une erreur confirmée. Quand la réponse vient d'une protection anti-robots
    reconnue (Cloudflare, DataDome...), on la nomme pour dire à l'utilisateur quoi faire ;
  - si l'utilisateur fournit ses propres identifiants DataForSEO, un contrôle par ce
    service, plus robuste contre les pare-feux, cadencé
    à 12 appels par minute au plus (limite du compte DataForSEO, quel qu'il soit).

Lit aussi les titres des vraies pages candidates à une redirection (lire_titres)."""
import base64
import html
import json
import time
import urllib.error
import urllib.request

from . import __version__, matching

UA ={"User-Agent": "Bifurq-AIO/%s (+https://github.com/PierreRibeaucourt/bifurq-aio ; outil local, verifie ses "
                    "propres pages)" % __version__}
DELAI_COURTOISIE = 1.5
DATAFORSEO_URL = "https://api.dataforseo.com/v3/on_page/instant_pages"
ERREURS = (404, 410)               # l'adresse n'existe pas : à rediriger
TAILLE_MAX_PAGE = 2_000_000        # octets lus d'une page pour ses titres

# Protections anti-robots : ce qui les trahit dans les en-têtes ou dans le début de la
# page qu'elles renvoient à la place du site (en minuscules).
PROTECTIONS = (
    ("Cloudflare", ("cf-mitigated:",), ("cloudflare",), "server: cloudflare"),
    ("DataDome", ("x-datadome:", "set-cookie: datadome="), ("captcha-delivery.com",), None),
    ("Akamai", ("server: akamaighost", "server-timing: ak_p;"), ("errors.edgesuite.net",), None),
    ("Imperva", ("x-iinfo:",), ("incapsula incident",), None),
    ("Sucuri", ("x-sucuri-id:", "x-sucuri-block:"), ("sucuri website firewall",), None),
)


def corrigee(code):
    """La page s'affiche, directement ou après redirection."""
    return isinstance(code, int) and 200 <= code < 400


def protection(code, entetes, debut):
    """Nom de la protection anti-robots qui a répondu à la place du site, ou None.
    entetes : [(nom, valeur)] ; debut : début de la page renvoyée. Une page qui s'affiche
    ou une vraie erreur 404/410 vient du site, jamais d'une protection."""
    if corrigee(code) or code in ERREURS:
        return None
    brut = "\n".join("%s: %s" % (k, v) for k, v in entetes).lower()
    debut = html.unescape(debut).lower()            # Akamai écrit errors&#46;edgesuite&#46;net
    for nom, dans_entetes, dans_page, avec_entete in PROTECTIONS:
        if any(s in brut for s in dans_entetes):
            return nom
        if any(s in debut for s in dans_page) and (avec_entete is None or avec_entete in brut):
            return nom
    return None


class ControleurHTTP:
    """Un contrôleur par exécution de la veille : garde la cadence et le compteur
    d'appels DataForSEO partagés entre tous les sites traités dans cette exécution."""

    def __init__(self, dataforseo=None, max_appels_dataforseo=120, pas_dataforseo=5.0):
        """dataforseo : {"login", "password"} de l'utilisateur, ou None pour la voie
        directe par défaut."""
        self.dataforseo = dataforseo
        self.max_appels = max_appels_dataforseo
        self.pas = pas_dataforseo
        self._dernier = 0.0
        self._appels = 0

    def controler(self, url):
        """Rend {"code": int, "finale": url}, avec "protection": nom si une protection
        anti-robots a répondu à la place du site, ou {"code": None, "erreur": str}."""
        if self.dataforseo:
            return self._controler_dataforseo(url)
        return self._controler_direct(url)

    def _controler_direct(self, url):
        time.sleep(DELAI_COURTOISIE)
        req = urllib.request.Request(url, headers=UA, method="GET")
        try:
            r = urllib.request.urlopen(req, timeout=30)
            return {"code": r.status, "finale": r.geturl()}
        except urllib.error.HTTPError as e:
            r = {"code": e.code, "finale": e.geturl()}
            if not corrigee(e.code) and e.code not in ERREURS:
                try:
                    debut = e.read(4096).decode("utf-8", "replace")
                except Exception:
                    debut = ""
                nom = protection(e.code, (e.headers or {}).items(), debut)
                if nom:
                    r["protection"] = nom
            return r
        except Exception as e:
            return {"code": None, "erreur": str(e)[:150]}

    def lire_titres(self, url):
        """Titres d'une page du site (voir matching.textes_de_page), toujours par une
        requête directe, ou None si la page ne s'affiche pas. Lus jusqu'à 2 Mo : le <h1>
        d'une page Shopify arrive après 500 Ko de menus."""
        time.sleep(DELAI_COURTOISIE)
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30)
            if "html" not in (r.headers.get_content_type() or ""):
                return None
            return matching.textes_de_page(r.read(TAILLE_MAX_PAGE).decode(r.headers.get_content_charset() or "utf-8",
                                                                          "replace"))
        except Exception:
            return None

    def _controler_dataforseo(self, url):
        if self._appels >= self.max_appels:
            return {"code": None, "erreur": "plafond de %d contrôles DataForSEO atteint pour cette exécution" % self.max_appels}
        jeton = base64.b64encode(("%s:%s" % (self.dataforseo["login"], self.dataforseo["password"])).encode()).decode()
        for essai in (1, 2):
            attente = self.pas - (time.time() - self._dernier)
            if attente > 0:
                time.sleep(attente)
            self._dernier = time.time()
            self._appels += 1
            req = urllib.request.Request(
                DATAFORSEO_URL, method="POST",
                data=json.dumps([{"url": url, "enable_javascript": False}]).encode(),
                headers={"Authorization": "Basic " + jeton, "Content-Type": "application/json"})
            try:
                r = json.loads(urllib.request.urlopen(req, timeout=60).read().decode())
                t = r["tasks"][0]
                if t["status_code"] in (40202, 40501) and essai == 1:    # débit ou domaine déjà en cours
                    time.sleep(60)
                    continue
                if t["status_code"] != 20000:
                    return {"code": None, "erreur": "DataForSEO %s %s" % (t["status_code"], t.get("status_message"))}
                it = ((t.get("result") or [{}])[0].get("items") or [{}])[0]
                if not it.get("status_code"):
                    return {"code": None, "erreur": "DataForSEO : réponse sans code HTTP"}
                return {"code": it["status_code"], "finale": it.get("url")}
            except Exception as e:
                if essai == 2:
                    return {"code": None, "erreur": str(e)[:150]}
                time.sleep(30)
        return {"code": None, "erreur": "DataForSEO : limite de débit persistante"}
