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
        self.demandes = []
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.port = self.httpd.server_port
        self.fil = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.fil.start()

    def _handler(self):
        routes, demandes = self.routes, self.demandes

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                demandes.append(self.path)
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


class _ServeurEntetes:
    """Répond (code, en-têtes, corps) et garde le User-Agent de chaque requête."""
    def __init__(self, code, entetes, corps):
        self.agents = []
        agents = self.agents

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                agents.append(self.headers.get("User-Agent"))
                self.send_response(code)
                for k, v in entetes.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(corps)
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d/sitemap.xml" % self.httpd.server_port
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def arreter(self):
        self.httpd.shutdown()


def test_plan_de_site_lu_sous_le_nom_de_l_outil(journal):
    """Régression du 24.09.2026 : un faux Chrome se faisait refuser (403) par Akamai,
    qui laissait passer Bifurq-AIO."""
    s = _ServeurEntetes(200, {"Content-Type": "application/xml"}, VIDE)
    try:
        sitemap.plan_de_site([s.url], journal, strict=True)
    finally:
        s.arreter()
    assert s.agents and s.agents[0].startswith("Bifurq-AIO/")


def test_plan_de_site_bloque_nomme_la_protection(journal):
    from test_http_check import PAGE_AKAMAI
    s = _ServeurEntetes(403, {"Content-Type": "text/html"}, PAGE_AKAMAI.encode())
    try:
        with pytest.raises(sitemap.ErreurPlanDeSite) as erreur:
            sitemap.plan_de_site([s.url], journal, strict=True)
    finally:
        s.arreter()
    assert "protection anti-robots Akamai" in str(erreur.value)


def test_adresses_entourees_de_cdata(journal):
    """Régression du 25.09.2026 : All in One SEO (WordPress) et PrestaShop écrivent
    <loc><![CDATA[...]]></loc>, et deux sites étaient lus comme vides."""
    s = _Serveur({})
    racine = "http://127.0.0.1:%d" % s.port
    s.routes["/sitemap.xml"] = (("""<?xml version="1.0" encoding="UTF-8"?>
<?xml-stylesheet type="text/xsl" href="/default-sitemap.xsl?sitemap=root"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
	<sitemap>
		<loc><![CDATA[%s/page-sitemap.xml]]></loc>
		<lastmod><![CDATA[2026-09-21T12:30:55+00:00]]></lastmod>
	</sitemap>
</sitemapindex>""" % racine).encode(), "text/xml; charset=UTF-8", False)
    s.routes["/page-sitemap.xml"] = (("""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
<url>
<loc><![CDATA[%s/es/]]></loc>
<image:image><image:loc><![CDATA[%s/img/logo.jpg]]></image:loc></image:image>
</url>
<url><loc> <![CDATA[ %s/es/cadenas/402-cadena ]]> </loc></url>
<url><loc>%s/es/contacto</loc></url>
</urlset>""" % (racine, racine, racine, racine)).encode(), "text/xml", False)
    try:
        pages = sitemap.plan_de_site([racine + "/sitemap.xml"], journal, strict=True)
    finally:
        s.arreter()
    # "/" final retiré par urls.norm, <image:loc> jamais pris pour une page
    assert pages == {racine + "/es", racine + "/es/cadenas/402-cadena", racine + "/es/contacto"}


def test_adresses_illisibles_levent_une_erreur_en_strict(journal):
    s = _Serveur({"/sitemap.xml": (b"<urlset><url><loc><a>http://x/page</a></loc></url></urlset>", "text/xml", False)})
    try:
        with pytest.raises(RuntimeError, match="ne sait pas lire"):
            sitemap.plan_de_site(["http://127.0.0.1:%d/sitemap.xml" % s.port], journal, strict=True)
    finally:
        s.arreter()


def test_lecture_arretee_entre_deux_fichiers(journal):
    s = _Serveur({})
    s.routes["/sitemap.xml"] = (INDEX.replace(b"%PORT%", str(s.port).encode()), "application/xml", False)
    s.routes["/sous-plan.xml"] = (SOUS_PLAN.replace(b"%PORT%", str(s.port).encode()), "application/xml", False)
    lus = []

    class Annulee(Exception):
        pass

    def verifier():
        if lus:
            raise Annulee()
        lus.append(1)
    try:
        with pytest.raises(Annulee):
            sitemap.plan_de_site(["http://127.0.0.1:%d/sitemap.xml" % s.port], journal, strict=True, verifier=verifier)
    finally:
        s.arreter()
    assert lus == [1] and s.demandes == ["/sitemap.xml"]      # le sous-plan jamais demandé
