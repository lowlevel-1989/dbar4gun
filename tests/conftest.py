import os
import sys

# permite ejecutar pytest desde la raiz sin instalar el paquete
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
