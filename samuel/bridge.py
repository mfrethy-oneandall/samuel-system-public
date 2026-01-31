"""Samuel Bridge — lightweight REST server for HA integration.

Runs on port 5101 alongside the Samuel MCP server (port 5100).
Provides HTTP endpoints that Home Assistant can call via rest_command.

This is the Phase 2 bridge foundation — voice query routing
(POST /query) will be added later.

Endpoints:
  GET /ping   — uptime check
  GET /health — run health diagnostic, return JSON summary
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
import uvicorn

from samuel.tools import health_tools

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("samuel.bridge")


def _load_env() -> None:
    """Load environment from .env in the samuel-system repo root."""
    # Load .env from the samuel-system repo root (where this code lives)
    repo_root = Path(__file__).resolve().parent.parent
    env_path = repo_root / ".env"

    if env_path.exists():
        load_dotenv(env_path)
        logger.info("Loaded env from %s", env_path)

    # Require REPO_PATH to be set (points to ha-config clone)
    if not os.environ.get("REPO_PATH"):
        logger.error("REPO_PATH not set — point it at your ha-config clone")


async def ping(request):
    """Simple uptime check."""
    return JSONResponse({"status": "ok"})


async def health(request):
    """Run health diagnostic and return JSON summary."""
    try:
        report = await health_tools.generate_health_report()
        summary = health_tools.extract_summary(report)
        return JSONResponse(summary)
    except Exception:
        logger.exception("Health check failed")
        return JSONResponse(
            {"status": "error", "summary": "Health check failed"},
            status_code=500,
        )


routes = [
    Route("/ping", ping),
    Route("/health", health),
]

app = Starlette(routes=routes)


def main():
    """Run the Samuel Bridge server."""
    _load_env()
    host = os.environ.get("BRIDGE_HOST", "0.0.0.0")
    port = int(os.environ.get("BRIDGE_PORT", "5101"))
    logger.info("Starting Samuel Bridge on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
