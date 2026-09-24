# -*- coding: utf-8 -*-
"""Erreurs qui arrêtent l'analyse d'un site, avec un message lisible par n'importe
qui et, quand l'utilisateur peut la régler lui-même, l'action à lui proposer."""
import os


class ErreurVeille(RuntimeError):
    action = None                        # "reconnecter" : bouton de reconnexion Google

    def __init__(self, message, detail=""):
        super().__init__(message)
        self.message = message
        self.detail = detail             # détail technique, pour le journal seulement


class ErreurConnexionGoogle(ErreurVeille):
    action = "reconnecter"


class ErreurAccesSearchConsole(ErreurVeille):
    action = "reconnecter"


class ErreurReseau(ErreurVeille):
    pass


class ErreurPlanDeSite(ErreurVeille):
    pass


class ErreurDonnees(ErreurVeille):
    pass


def expliquer(exception):
    """(message pour l'utilisateur, action proposée ou None)."""
    if isinstance(exception, ErreurVeille):
        return exception.message, exception.action
    return ("Erreur inattendue pendant l'analyse. Le détail technique est dans le fichier "
            "%s." % os.path.join("config", "veille.log"), None)
