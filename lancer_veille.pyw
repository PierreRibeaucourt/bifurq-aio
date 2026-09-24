# -*- coding: utf-8 -*-
"""Lanceur sans console de la veille (tâche planifiée Windows, via pythonw.exe).

pythonw n'a pas de sortie standard : on la redirige vers config/sortie.log avant de
lancer la veille, pour qu'aucune fenêtre ne s'ouvre et que tout reste lisible après
coup. Si le script plante avant même d'écrire son propre journal, une notification
le dit explicitement (un silence ne doit jamais se lire comme "rien à signaler")."""
import io
import os
import sys
import traceback

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

D = os.path.join(ICI, "config")
os.makedirs(D, exist_ok=True)
sortie = io.open(os.path.join(D, "sortie.log"), "a", encoding="utf-8")
sys.stdout = sys.stderr = sortie
os.chdir(ICI)

try:
    from veille_ia import watch
    watch.executer()
except BaseException:
    traceback.print_exc()
    try:
        from veille_ia import notify_windows
        notify_windows.notifier("Veille adresses inventées : plantage",
                                "Le script s'est arrêté avant la fin. Voir config\\sortie.log.")
    except Exception:
        pass
    raise
finally:
    sortie.flush()
