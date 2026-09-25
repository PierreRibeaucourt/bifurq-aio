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


# page Akamai relevée le 24.09.2026, adresse et référence anonymisées
PAGE_AKAMAI = ("<HTML><HEAD>\n<TITLE>Access Denied</TITLE>\n</HEAD><BODY>\n<H1>Access Denied</H1>\n \n"
               "You don't have permission to access \"http&#58;&#47;&#47;www&#46;exemple&#46;fr&#47;sitemap&#46;xml\" "
               "on this server.<P>\nReference&#32;&#35;18&#46;1&#46;2&#46;3\n"
               "<P>https&#58;&#47;&#47;errors&#46;edgesuite&#46;net&#47;18&#46;1&#46;2&#46;3</P>\n</BODY>\n</HTML>")


def test_akamai_reconnu_meme_avec_une_page_encodee():
    assert http_check.protection(403, [("Content-Type", "text/html")], PAGE_AKAMAI) == "Akamai"
    assert http_check.protection(403, [("Server-Timing", "ak_p; desc=\"1_2_3\";dur=1")], "") == "Akamai"


def test_titres_d_une_page_du_site():
    page = ("<html><head><meta charset='iso-8859-1'><title>Caf\xe9 : bienfaits | Mon site</title></head>"
            "<body>" + "<a>menu</a>" * 50000 + "<h1>Le caf\xe9</h1></body></html>").encode("iso-8859-1")
    s = _Serveur({"/page": (200, {"Content-Type": "text/html; charset=iso-8859-1"}, page),
                  "/image": (200, {"Content-Type": "image/png"}, b"\x89PNG"),
                  "/bloquee": (403, {"Content-Type": "text/html"}, b"<title>Just a moment...</title>")})
    try:
        c = http_check.ControleurHTTP()
        lire = lambda chemin: c.lire_titres("http://127.0.0.1:%d%s" % (s.port, chemin))
        assert lire("/page") == ["Café : bienfaits | Mon site", "Café : bienfaits", "Le café"]
        assert lire("/image") is None and lire("/bloquee") is None and lire("/absente") is None
    finally:
        s.arreter()
