# function_app.py
"""
Azure Functions - Govy Backend
Slim orchestrator: registra blueprints por dominio.
"""
import sys
from pathlib import Path

import azure.functions as func

# ---- Path bootstrap ----
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blueprints.bp_core import bp as bp_core
from blueprints.bp_editais import bp as bp_editais
from blueprints.bp_doctrine import bp as bp_doctrine
from blueprints.bp_juris import bp as bp_juris
from blueprints.bp_kb_juris import bp as bp_kb_juris
from blueprints.bp_kb_content import bp as bp_kb_content
from blueprints.bp_legal import bp as bp_legal
from blueprints.bp_tce import bp as bp_tce
from blueprints.bp_diagnostics import bp as bp_diagnostics
from blueprints.bp_copilot import bp as bp_copilot

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

app.register_functions(bp_core)
app.register_functions(bp_editais)
app.register_functions(bp_doctrine)
app.register_functions(bp_juris)
app.register_functions(bp_kb_juris)
app.register_functions(bp_kb_content)
app.register_functions(bp_legal)
app.register_functions(bp_tce)
app.register_functions(bp_diagnostics)
app.register_functions(bp_copilot)
