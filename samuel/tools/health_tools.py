"""Health diagnostic tools for Home Assistant.

Provides async health check analysis using Samuel's ha_client.
Shared by the MCP tool (server.py) and the REST bridge (bridge.py).
"""

import json
import logging
import os
import datetime
from pathlib import Path
from typing import Any

from samuel import ha_client

logger = logging.getLogger("samuel.health")


def _get_state_file() -> Path:
    """Return the path to the state file for diff comparisons.

    Uses DATA_DIR env var, or defaults to ~/data/latest_state.json.
    """
    data_dir = os.environ.get("DATA_DIR")
    if data_dir:
        return Path(data_dir) / "latest_state.json"
    return Path.home() / "data" / "latest_state.json"


def _parse_log(log_text: str) -> list[dict]:
    """Parse raw HA log text into structured entries."""
    entries = []
    current = None

    for line in log_text.splitlines():
        if " ERROR " in line or " WARNING " in line or " CRITICAL " in line:
            if current:
                entries.append(current)
            parts = line.split(" ", 3)
            if len(parts) >= 4:
                current = {
                    "timestamp": f"{parts[0]} {parts[1]}",
                    "level": parts[2],
                    "message": parts[3],
                }
            else:
                current = None
        elif current:
            current["message"] += "\n" + line

    if current:
        entries.append(current)
    return entries


def _analyze(logs: list[dict]) -> dict:
    """Analyze parsed log entries — counts, grouping, top offenders."""
    stats: dict[str, Any] = {
        "error_count": 0,
        "warning_count": 0,
        "unique_errors": {},
        "top_offenders": [],
    }

    for log in logs:
        if "ERROR" in log["level"]:
            stats["error_count"] += 1
        elif "WARNING" in log["level"]:
            stats["warning_count"] += 1

        signature = log["message"].split("\n")[0][:100]
        if signature not in stats["unique_errors"]:
            stats["unique_errors"][signature] = {
                "count": 0,
                "first_seen": log["timestamp"],
                "last_seen": log["timestamp"],
                "example": log["message"][:200],
            }
        entry = stats["unique_errors"][signature]
        entry["count"] += 1
        entry["last_seen"] = log["timestamp"]

    sorted_errors = sorted(
        stats["unique_errors"].items(),
        key=lambda x: x[1]["count"],
        reverse=True,
    )
    stats["top_offenders"] = [
        {"signature": k, **v} for k, v in sorted_errors[:20]
    ]
    return stats


def _load_previous() -> dict:
    """Load previous run state for diffing."""
    state_file = _get_state_file()
    if state_file.exists():
        try:
            return json.loads(state_file.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_state(stats: dict) -> None:
    """Persist current stats for next diff."""
    state_file = _get_state_file()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        state_file.write_text(json.dumps(stats, indent=2))
    except IOError as e:
        logger.error("Failed to save state: %s", e)


def _build_markdown(stats: dict, system: dict, diff_note: str) -> str:
    """Build a markdown health report."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    lines = [f"# Morning Health Packet: {today}"]

    if stats["error_count"] == 0 and stats["warning_count"] == 0:
        lines.append("## Status: All Clear")
    else:
        lines.append(
            f"## Issues Detected: {stats['error_count']} Errors, "
            f"{stats['warning_count']} Warnings"
        )

    if diff_note:
        lines.append(f"\n> {diff_note}\n")

    lines.append("## System Snapshot")
    lines.append(f"- **Version**: {system.get('version', 'unknown')}")
    lines.append(f"- **State**: {system.get('state', 'unknown')}")
    lines.append(f"- **Generated**: {datetime.datetime.now().isoformat()}")

    if stats["top_offenders"]:
        lines.append("\n## Top Unique Issues")
        lines.append("| Count | Level | Signature | Last Seen |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for item in stats["top_offenders"]:
            level = "ERR" if "ERROR" in item["signature"] else "WARN"
            sig = item["signature"].replace("|", "/")
            lines.append(
                f"| {item['count']} | {level} | `{sig}` | {item['last_seen']} |"
            )

    return "\n".join(lines)


async def generate_health_report() -> str:
    """Run a full health diagnostic and return a markdown report.

    Fetches /api/config and /api/error_log from HA, analyzes the logs,
    diffs against the previous run, and returns a formatted report.
    """
    # Fetch system config
    config = await ha_client.get_config()
    system = {
        "version": config.get("version", "unknown") if config else "unreachable",
        "state": config.get("state", "unknown") if config else "unreachable",
    }

    # Fetch and parse error log
    log_text = await ha_client.get_error_log()
    logs = _parse_log(log_text) if log_text else []
    stats = _analyze(logs)

    # Diff against previous run
    prev = _load_previous()
    if prev:
        delta = stats["error_count"] - prev.get("error_count", 0)
        if delta > 0:
            diff_note = f"**Trend**: +{delta} errors since last run."
        elif delta < 0:
            diff_note = f"**Trend**: {delta} errors (improvement)."
        else:
            diff_note = "**Trend**: Stable error count."
    else:
        diff_note = "First run: No previous data."

    # Save state for next diff
    _save_state(stats)

    return _build_markdown(stats, system, diff_note)


def extract_summary(report: str) -> dict:
    """Extract a JSON-friendly summary from a markdown report.

    Used by the bridge to return structured data to HA rest_command.
    """
    error_count = 0
    warning_count = 0
    status = "ok"

    for line in report.splitlines():
        if "Issues Detected:" in line:
            status = "issues"
            # Parse "N Errors, M Warnings" from the line
            for word in line.split():
                if word.isdigit():
                    if error_count == 0:
                        error_count = int(word)
                    else:
                        warning_count = int(word)
            break
        elif "All Clear" in line:
            status = "ok"
            break

    if status == "ok":
        summary = "Home Assistant is healthy. No errors or warnings found."
    else:
        summary = (
            f"Found {error_count} errors and {warning_count} warnings. "
            "Check the health report for details."
        )

    return {
        "status": status,
        "summary": summary,
        "errors": error_count,
        "warnings": warning_count,
    }
