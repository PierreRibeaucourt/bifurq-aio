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
                code = codes.get(handler_self.path, 404)
                handler_self.send_response(code)
                handler_self.end_headers()

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
