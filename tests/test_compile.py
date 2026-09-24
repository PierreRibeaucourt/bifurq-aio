import ast
import os

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _fichiers_python():
    for dossier in ("veille_ia",):
        for base, _, fichiers in os.walk(os.path.join(RACINE, dossier)):
            for f in fichiers:
                if f.endswith(".py"):
                    yield os.path.join(base, f)
    yield os.path.join(RACINE, "lancer_veille.pyw")
    yield os.path.join(RACINE, "installer.pyw")


def test_tous_les_fichiers_compilent():
    """Filet de sécurité minimal : un fichier avec une erreur de syntaxe casserait
    silencieusement la tâche planifiée (pythonw n'a pas de console)."""
    for chemin in _fichiers_python():
        with open(chemin, encoding="utf-8") as f:
            source = f.read()
        try:
            ast.parse(source, filename=chemin)
        except SyntaxError as e:
            raise AssertionError("erreur de syntaxe dans %s : %s" % (chemin, e))
