# -*- coding: utf-8 -*-
"""Lanceur sans console des analyses planifiées : tâche planifiée Windows (pythonw.exe),
agent launchd sur macOS, minuterie systemd ou cron sous Linux.

La sortie standard est redirigée vers config/sortie.log avant de lancer la veille, pour
qu'aucune fenêtre ne s'ouvre et que tout reste lisible après coup. Si le script plante
avant même d'écrire son propre journal, une notification le dit explicitement (un
silence ne doit jamais se lire comme "rien à signaler").

--attendre N : attendre N secondes avant l'analyse (lancement à l'ouverture de session
sur macOS, où launchd ne sait pas retarder un agent : le réseau doit être prêt)."""
import io
import os
import sys
import time
import traceback

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

D = os.path.join(ICI, "config")
os.makedirs(D, exist_ok=True)
sortie = io.open(os.path.join(D, "sortie.log"), "a", encoding="utf-8")
sys.stdout = sys.stderr = sortie
os.chdir(ICI)

try:
    if "--attendre" in sys.argv:
        i = sys.argv.index("--attendre")
        if i + 1 < len(sys.argv) and sys.argv[i + 1].isdigit():
            time.sleep(int(sys.argv[i + 1]))
    from veille_ia import watch
    watch.executer()
    try:
        from veille_ia import mise_a_jour
        mise_a_jour.verifier()         # une nouvelle version s'annonce à la prochaine ouverture de l'interface
    except Exception:
        traceback.print_exc()
except BaseException:
    traceback.print_exc()
    try:
        from veille_ia import plateforme
        plateforme.notifier("Bifurq AIO : plantage", "Le script s'est arrêté avant la fin. Voir %s."
                            % os.path.join("config", "sortie.log"))
    except Exception:
        pass
    raise
finally:
    sortie.flush()
