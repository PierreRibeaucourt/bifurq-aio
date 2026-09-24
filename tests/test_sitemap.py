import gzip
import http.server
import threading

import pytest

from veille_ia import sitemap

INDEX = b"""<?xml version="1.0"?>
<sitemapindex><sitemap><loc>http://127.0.0.1:%PORT%/sous-plan.xml</loc></sitemap></sitemapindex>"""
SOUS_PLAN = b"""<?xml version="1.0"?>
<urlset><url><loc>http://127.0.0.1:%PORT%/page-un</loc></url>
<url><loc>http://127.0.0.1:%PORT%/page-deux</loc></url></urlset>"""
VIDE = b"""<?xml version="1.0"?><urlset></urlset>"""
PAGE_BLOCAGE = b"<html><body>Acces refuse (pare-feu)</body></html>"


class _Serveur:
    def __init__(self, routes):
        self.routes = routes
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.port = self.httpd.server_port
        self.fil = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.fil.start()

    def _handler(self):
        routes = self.routes

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                corps, type_contenu, gzippe = routes.get(self.path, (None, None, False))
                if corps is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                if gzippe:
                    corps = gzip.compress(corps)
                self.send_response(200)
                self.send_header("Content-Type", type_contenu)
                self.end_headers()
                self.wfile.write(corps)
        return H

    def arreter(self):
        self.httpd.shutdown()


@pytest.fixture
def journal():
    return lambda msg: None


@pytest.fixture(autouse=True)
def _sans_delai_courtoisie(monkeypatch):
    """Le délai de courtoisie (1,5 s) est pour de vrais sites tiers, pas pour un
    serveur factice local : le neutraliser garde la suite de tests rapide."""
    monkeypatch.setattr(sitemap, "DELAI_COURTOISIE", 0)


def test_index_recursif_deux_niveaux(journal):
    s = _Serveur({})
    index = INDEX.replace(b"%PORT%", str(s.port).encode())
    sous = SOUS_PLAN.replace(b"%PORT%", str(s.port).encode())
    s.routes["/sitemap.xml"] = (index, "application/xml", False)
    s.routes["/sous-plan.xml"] = (sous, "application/xml", False)
    try:
        pages = sitemap.plan_de_site(["http://127.0.0.1:%d/sitemap.xml" % s.port], journal, strict=True)
    finally:
        s.arreter()
    assert pages == {"http://127.0.0.1:%d/page-un" % s.port, "http://127.0.0.1:%d/page-deux" % s.port}


def test_sitemap_vide_est_legitime(journal):
    s = _Serveur({"/sitemap.xml": (VIDE, "application/xml", False)})
    try:
        pages = sitemap.plan_de_site(["http://127.0.0.1:%d/sitemap.xml" % s.port], journal, strict=True)
    finally:
        s.arreter()
    assert pages == set()


def test_page_de_blocage_leve_en_strict(journal):
    s = _Serveur({"/sitemap.xml": (PAGE_BLOCAGE, "text/html", False)})
    try:
        with pytest.raises(RuntimeError):
            sitemap.plan_de_site(["http://127.0.0.1:%d/sitemap.xml" % s.port], journal, strict=True)
    finally:
        s.arreter()


def test_page_de_blocage_ignoree_hors_strict(journal):
    s = _Serveur({"/sitemap.xml": (PAGE_BLOCAGE, "text/html", False)})
    try:
        pages = sitemap.plan_de_site(["http://127.0.0.1:%d/sitemap.xml" % s.port], journal, strict=False)
    finally:
        s.arreter()
    assert pages == set()


def test_gzip_decompresse(journal):
    s = _Serveur({"/sitemap.xml.gz": (VIDE.replace(b"</urlset>", b"<url><loc>http://x/page</loc></url></urlset>"),
                                      "application/gzip", True)})
    try:
        pages = sitemap.plan_de_site(["http://127.0.0.1:%d/sitemap.xml.gz" % s.port], journal, strict=True)
    finally:
        s.arreter()
    assert pages == {"http://x/page"}
