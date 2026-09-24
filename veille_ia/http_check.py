# -*- coding: utf-8 -*-
"""Code HTTP d'une adresse suspecte : confirme qu'elle répond bien 404 avant de la
proposer en redirection (un contrôle HTTP raté ne doit jamais se lire comme un 404).

Deux voies, choisies par site :
  - par défaut, une requête directe depuis le poste de l'utilisateur vers SON PROPRE
    site : légitime, à la différence d'un crawl de sites tiers. Un pare-feu ou un CDN
    peut renvoyer un code trompeur (403, 503) : à signaler comme "à vérifier", jamais
    comme un 404 confirmé ;
  - si l'utilisateur fournit ses propres identifiants DataForSEO, un contrôle par ce
    service, plus robuste contre les pare-feux, cadencé
    à 12 appels par minute au plus (limite du compte DataForSEO, quel qu'il soit)."""
import base64
import json
import time
import urllib.error
import urllib.request

UA = {"User-Agent": "Bifurq-AIO/0.1 (+https://github.com/PierreRibeaucourt/bifurq-aio ; outil local, verifie ses propres pages)"}
DELAI_COURTOISIE = 1.5
DATAFORSEO_URL = "https://api.dataforseo.com/v3/on_page/instant_pages"


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
        """Rend {"code": int, "finale": url} ou {"code": None, "erreur": str}."""
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
            return {"code": e.code, "finale": e.geturl()}
        except Exception as e:
            return {"code": None, "erreur": str(e)[:150]}

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
