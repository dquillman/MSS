
import sys
import os
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print(f"CWD: {os.getcwd()}")
print(f"Initial sys.path: {sys.path}")

# Exact logic from api_server.py
_project_root = Path(__file__).parent.parent
print(f"Project root: {_project_root}")
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
    print(f"Added project root to sys.path")

print(f"Modified sys.path: {sys.path}")

try:
    # When installed as a package or run via `flask --app web.api_server`
    from web import database as database  # type: ignore
    logger.info("[DATABASE] Successfully imported database module")
except Exception as e1:
    logger.warning(f"[DATABASE] First import attempt failed: {e1}", exc_info=True)
    try:
        # When running directly: `python web\api_server.py`
        import database  # type: ignore
        logger.info("[DATABASE] Successfully imported database module (direct import)")
    except Exception as e2:
        logger.error(f"[DATABASE] Both import attempts failed. First: {e1}, Second: {e2}", exc_info=True)
