"""Samuel MCP Server — Home Intelligence Agent for Example Home.

Exposes Home Assistant config and state tools via MCP over HTTP,
allowing Claude Desktop or Claude Code to query the home setup.
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from samuel.tools import config_tools, state_tools, doc_tools, health_tools

# Configure logging (never use print — it corrupts MCP transport)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("samuel")


def _load_env() -> None:
    """Load environment from .env in the samuel-system repo root."""
    # Load .env from the samuel-system repo root (where this code lives)
    repo_root = Path(__file__).resolve().parent.parent
    env_path = repo_root / ".env"

    if env_path.exists():
        load_dotenv(env_path)
        logger.info("Loaded env from %s", env_path)
    else:
        logger.warning("No .env found at %s — using environment variables", env_path)

    # Require REPO_PATH to be set (points to ha-config clone)
    if not os.environ.get("REPO_PATH"):
        logger.error("REPO_PATH not set — point it at your ha-config clone")


def create_server() -> FastMCP:
    """Create and configure the Samuel MCP server."""
    _load_env()

    # Get host/port from environment (set defaults here for FastMCP constructor)
    port = int(os.environ.get("SAMUEL_PORT", "5100"))
    host = os.environ.get("SAMUEL_HOST", "0.0.0.0")

    mcp = FastMCP(
        "samuel",
        host=host,
        port=port,
        instructions=(
            "Samuel is the home intelligence agent for Example Home. "
            "Use the available tools to answer questions about the home "
            "automation config, check live entity states, and read "
            "documentation. Config tools read YAML files from the repo. "
            "State tools query the Home Assistant REST API for live data."
        ),
    )

    # --- Config tools ---
    @mcp.tool()
    async def read_config(filename: str) -> str:
        """Read a Home Assistant config file and return its contents.

        Args:
            filename: Config file name, e.g. "house_mode.yaml" or
                      "packages/house_mode.yaml".
        """
        return await config_tools.read_config(filename)

    @mcp.tool()
    async def list_packages() -> str:
        """List all HA package files with their automations and helpers."""
        return await config_tools.list_packages()

    @mcp.tool()
    async def list_automations() -> str:
        """List all automations across all config files with triggers."""
        return await config_tools.list_automations()

    @mcp.tool()
    async def list_scripts() -> str:
        """List all scripts with their key actions."""
        return await config_tools.list_scripts()

    @mcp.tool()
    async def search_config(pattern: str) -> str:
        """Search across all config files for a pattern (case-insensitive regex).

        Args:
            pattern: Search pattern, e.g. "quiet_hours", "reading_light",
                     "brightness_pct".
        """
        return await config_tools.search_config(pattern)

    # --- State tools ---
    @mcp.tool()
    async def get_entity_state(entity_id: str) -> str:
        """Get the current state of a Home Assistant entity.

        Args:
            entity_id: Full entity ID (e.g. "light.front_room_front_reading_light")
                       or partial search (e.g. "porch light", "reading light").
        """
        return await state_tools.get_entity_state(entity_id)

    @mcp.tool()
    async def get_entities_by_domain(domain: str) -> str:
        """List all entities for a domain with current state.

        Args:
            domain: Entity domain, e.g. "light", "switch", "automation",
                    "input_boolean", "sensor".
        """
        return await state_tools.get_entities_by_domain(domain)

    @mcp.tool()
    async def get_area_state(area: str) -> str:
        """Get the state of all entities in a home area.

        Args:
            area: Area name, e.g. "living room", "porch", "master bedroom",
                  "hallway", "stairs", "master bath".
        """
        return await state_tools.get_area_state(area)

    # --- Doc tools ---
    @mcp.tool()
    async def read_doc(filename: str) -> str:
        """Read a documentation file from the docs/ directory.

        Args:
            filename: Doc filename, e.g. "system_map.md",
                      "lighting_standards.md", "samuel_spec.md".
        """
        return await doc_tools.read_doc(filename)

    @mcp.tool()
    async def get_system_map() -> str:
        """Return the full system architecture map (docs/system_map.md)."""
        return await doc_tools.get_system_map()

    # --- Health tools ---
    @mcp.tool()
    async def generate_health_report() -> str:
        """Generate a health diagnostic report for Home Assistant.

        Returns a markdown report with error/warning counts, top issues,
        system info, and trend comparison with the previous run.
        """
        return await health_tools.generate_health_report()

    return mcp


# Entry point
mcp = create_server()


def main():
    """Run the Samuel MCP server."""
    port = int(os.environ.get("SAMUEL_PORT", "5100"))
    host = os.environ.get("SAMUEL_HOST", "0.0.0.0")
    logger.info("Starting Samuel on %s:%d", host, port)
    # FastMCP with host/port in constructor; just specify transport
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
