from veille_ia import urls


def test_cle_chemin_idempotente():
    """Bug réel déjà rencontré en production : une clé déjà normalisée, relue depuis
    un état enregistré, ne doit jamais reperdre son premier segment."""
    for p in ["https://exemple.fr/blogs/news/un-article", "/blogs/news/un-article",
              "blogs/news/un-article", "https://www.exemple.fr/Blogs/News/Un-Article/"]:
        k1 = urls.cle_chemin(p)
        k2 = urls.cle_chemin(k1)
        assert k1 == k2, (p, k1, k2)


def test_cle_chemin_accents_www_barre_finale():
    # cle_chemin decode un accent encode en URL (%C3%A9) vers le meme caractere que
    # l'accent litteral, mais NE RETIRE PAS l'accent (a la difference de
    # matching.plie, qui sert a un usage different : la comparaison floue de slugs).
    e_accent = chr(0xE9)
    a = urls.cle_chemin("https://www.exemple.fr/collections/compl%C3%A9ments-sommeil/")
    b = urls.cle_chemin("https://exemple.fr/collections/compl" + e_accent + "ments-sommeil")
    assert a == b == "collections/compl" + e_accent + "ments-sommeil"


def test_cle_chemin_racine_vide():
    assert urls.cle_chemin("https://exemple.fr/") == ""
    assert urls.cle_chemin("https://exemple.fr") == ""


def test_cle_chemin_vide():
    assert urls.cle_chemin("") == ""
    assert urls.cle_chemin(None) == ""


def test_cle_url_ignore_fragment_et_www():
    assert urls.cle_url("https://www.exemple.fr/page#ancre") == urls.cle_url("https://exemple.fr/page")


def test_hote_retire_www():
    assert urls.hote("https://www.exemple.fr/page") == "exemple.fr"
    assert urls.hote("https://exemple.fr/page") == "exemple.fr"


def test_chemin():
    assert urls.chemin("https://exemple.fr/blogs/news/article#h2") == "/blogs/news/article"
    assert urls.chemin("https://exemple.fr/") == "/"
    assert urls.chemin("https://exemple.fr") == "/"
