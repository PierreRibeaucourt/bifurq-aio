__version__ = "0.5.3"

# certificats HTTPS du Python de python.org sur macOS : voir plateforme.preparer_certificats
from . import plateforme as _plateforme  # noqa: E402

_plateforme.preparer_certificats()
