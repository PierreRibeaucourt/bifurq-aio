# -*- coding: utf-8 -*-
"""Dernières étapes de l'installation, lancées par installer.pyw depuis le dossier
installé, avec son propre Python :

  python -m veille_ia.installation

Raccourci pour rouvrir l'outil (bureau Windows, application macOS, menu des
applications Linux), et analyses planifiées remises sur ce dossier quand des sites
sont déjà surveillés (mise à jour, ou reprise d'une installation faite dans un dossier
téléchargé, dont la tâche pointait encore vers ce dossier-là)."""
import traceback

from . import config, plateforme


def finaliser():
    try:
        plateforme.creer_raccourci()
    except Exception:
        traceback.print_exc()                # confort seulement : l'outil marche sans raccourci
    # une planification qui échoue fait échouer l'installation : sinon les analyses
    # automatiques s'arrêteraient sans que personne le sache
    donnees = config.lire()
    planif = donnees["planification"]
    if (donnees["sites"] and planif.get("active", True)
            and (planif.get("au_demarrage") or planif.get("actif_heure_fixe"))):
        plateforme.planifier(planif.get("au_demarrage"), planif.get("actif_heure_fixe"),
                             planif.get("heure_fixe") or "09:15")


if __name__ == "__main__":
    finaliser()
