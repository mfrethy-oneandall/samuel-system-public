"""Async HTTP client for the Home Assistant REST API."""

import os
import logging
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)

_ha_url: str | None = None
_ha_token: str | None = None


def _get_config() -> tuple[str, str]:
    """Return (ha_url, ha_token) from environment."""
    global _ha_url, _ha_token
    if _ha_url is None:
        _ha_url = os.environ.get("HA_URL", "http://YOUR_HA_IP:8123")
        _ha_token = os.environ.get("HA_TOKEN", "")
        if not _ha_token:
            logger.warning("HA_TOKEN not set — state tools will fail")
    return _ha_url, _ha_token


def _headers() -> dict[str, str]:
    """Build auth headers for HA API."""
    _, token = _get_config()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


async def get_state(entity_id: str) -> dict | None:
    """Get current state of a single entity."""
    url, _ = _get_config()
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{url}/api/states/{entity_id}",
                headers=_headers(),
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            logger.error("Cannot connect to HA at %s", url)
            return None
        except httpx.HTTPStatusError as e:
            logger.error("HA API error: %s", e)
            return None


async def get_states() -> list[dict]:
    """Get state of all entities."""
    url, _ = _get_config()
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{url}/api/states",
                headers=_headers(),
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            logger.error("Cannot connect to HA at %s", url)
            return []
        except httpx.HTTPStatusError as e:
            logger.error("HA API error: %s", e)
            return []


async def get_states_by_domain(domain: str) -> list[dict]:
    """Get all entities matching a domain (e.g. 'light', 'automation')."""
    all_states = await get_states()
    prefix = f"{domain}."
    return [s for s in all_states if s["entity_id"].startswith(prefix)]


async def get_history(entity_id: str, hours: int = 24) -> list:
    """Get state history for an entity over the last N hours."""
    url, _ = _get_config()
    start = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{url}/api/history/period/{start}",
                headers=_headers(),
                params={
                    "filter_entity_id": entity_id,
                    "minimal_response": "true",
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data[0] if data else []
        except httpx.ConnectError:
            logger.error("Cannot connect to HA at %s", url)
            return []
        except httpx.HTTPStatusError as e:
            logger.error("HA API error: %s", e)
            return []


async def find_entity(search: str) -> list[dict]:
    """Fuzzy-find entities by partial name or entity_id match."""
    all_states = await get_states()
    search_lower = search.lower().replace(" ", "_")
    matches = []
    for s in all_states:
        eid = s["entity_id"].lower()
        fname = s.get("attributes", {}).get("friendly_name", "").lower()
        if search_lower in eid or search_lower in fname.replace(" ", "_"):
            matches.append(s)
    return matches


async def get_config() -> dict | None:
    """Get HA system configuration (version, state, timezone)."""
    url, _ = _get_config()
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{url}/api/config",
                headers=_headers(),
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            logger.error("Cannot connect to HA at %s", url)
            return None
        except httpx.HTTPStatusError as e:
            logger.error("HA API error: %s", e)
            return None


async def get_error_log() -> str | None:
    """Get HA error log as raw text."""
    url, _ = _get_config()
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{url}/api/error_log",
                headers=_headers(),
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.text
        except httpx.ConnectError:
            logger.error("Cannot connect to HA at %s", url)
            return None
        except httpx.HTTPStatusError as e:
            logger.error("HA API error: %s", e)
            return None
