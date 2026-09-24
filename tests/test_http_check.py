import http.server
import threading

import pytest

from veille_ia import http_check


@pytest.fixture(autouse=True)
def _sans_delai_courtoisie(monkeypatch):
    monkeypatch.setattr(http_check, "DELAI_COURTOISIE", 0)


class _Serveur:
    def __init__(self, codes):
        self.codes = codes

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(handler_self):
                code, entetes, corps = codes.get(handler_self.path, 404), {}, b""
                if isinstance(code, tuple):
                    code, entetes, corps = code
                handler_self.send_response(code)
                for k, v in entetes.items():
                    handler_self.send_header(k, v)
                handler_self.end_headers()
                handler_self.wfile.write(corps)

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.httpd.server_port
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def arreter(self):
        self.httpd.shutdown()


def test_page_existante_200():
    s = _Serveur({"/existe": 200})
    try:
        c = http_check.ControleurHTTP()
        r = c.controler("http://127.0.0.1:%d/existe" % s.port)
    finally:
        s.arreter()
    assert r["code"] == 200


def test_page_404_confirmee():
    s = _Serveur({})
    try:
        c = http_check.ControleurHTTP()
        r = c.controler("http://127.0.0.1:%d/nexiste-pas" % s.port)
    finally:
        s.arreter()
    assert r["code"] == 404


def test_serveur_injoignable_rend_erreur_pas_un_code():
    c = http_check.ControleurHTTP()
    r = c.controler("http://127.0.0.1:1/rien")     # port 1 : refus de connexion quasi garanti
    assert r["code"] is None
    assert "erreur" in r


def _controler(reponses, chemin):
    s = _Serveur(reponses)
    try:
        return http_check.ControleurHTTP().controler("http://127.0.0.1:%d%s" % (s.port, chemin))
    finally:
        s.arreter()


def test_page_410_confirmee():
    r = _controler({"/partie": 410}, "/partie")
    assert r["code"] == 410 and "protection" not in r


def test_datadome_reconnu_a_ses_en_tetes():
    """Relevé le 24.09.2026 sur un site protégé par DataDome : 403, page captcha."""
    r = _controler({"/p": (403, {"X-DataDome": "protected", "Set-Cookie": "datadome=abc; Path=/"},
                           b"<html><p id=cmsg>Please enable JS</p><script src=https://ct.captcha-delivery.com/c.js>")}, "/p")
    assert r == {"code": 403, "finale": r["finale"], "protection": "DataDome"}


def test_challenge_cloudflare_reconnu():
    r = _controler({"/p": (403, {"Server": "cloudflare", "cf-mitigated": "challenge"}, b"<title>Just a moment...</title>")}, "/p")
    assert r["protection"] == "Cloudflare"


def test_refus_du_site_lui_meme_sans_protection_nommee():
    r = _controler({"/p": (403, {"Server": "Apache"}, b"<h1>Forbidden</h1>")}, "/p")
    assert r["code"] == 403 and "protection" not in r


def test_une_vraie_erreur_derriere_cloudflare_reste_une_erreur():
    assert http_check.protection(404, [("Server", "cloudflare")], "<title>404 | cloudflare</title>") is None
    assert http_check.protection(410, [("X-DataDome", "protected")], "") is None
    assert http_check.protection(200, [("cf-mitigated", "challenge")], "") is None


def test_page_de_blocage_cloudflare_seulement_si_servie_par_cloudflare():
    blocage = "<title>Attention Required! | Cloudflare</title>"
    assert http_check.protection(403, [("Server", "cloudflare")], blocage) == "Cloudflare"
    assert http_check.protection(403, [("Server", "nginx")], "un article qui parle de cloudflare") is None


def test_autres_protections_reconnues():
    assert http_check.protection(403, [("Server", "AkamaiGHost")], "Access Denied") == "Akamai"
    assert http_check.protection(403, [("X-Iinfo", "12-345")], "") == "Imperva"
    assert http_check.protection(403, [("X-Sucuri-ID", "11005")], "") == "Sucuri"
