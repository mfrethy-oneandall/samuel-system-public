#!/usr/bin/env python3
"""
Morning Health Packet Generator for Home Assistant
Extracts logs, system stats, and generates a diff-based report for LLM consumption.
"""

import os
import sys
import json
import logging
import argparse
import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import requests
import subprocess

# Try to import dotenv, but don't fail if missing
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# Setup paths — use DATA_DIR env var or default to ~/data
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = Path(os.environ.get("DATA_DIR", Path.home() / "data"))

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("morning_health")

def manual_load_env(env_path: Path):
    """Manually parse .env file if python-dotenv is missing"""
    if not env_path.exists():
        return

    try:
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    # Basic quote removal
                    value = value.strip("'\"")
                    if key not in os.environ:
                        os.environ[key] = value
    except Exception as e:
        logger.warning(f"Failed to manually parse .env: {e}")

def setup_env():
    """Load environment variables from .env in the samuel-system repo root."""
    # Load .env from the samuel-system repo root
    env_path = SCRIPT_DIR.parent / ".env"
    if env_path.exists():
        if load_dotenv:
            load_dotenv(env_path)
        else:
            logger.warning("python-dotenv not installed. Using manual parsing.")
            manual_load_env(env_path)
    else:
        logger.warning(f"Message: {env_path} not found. Relying on system env vars.")

def get_ha_config() -> Dict[str, str]:
    """Get HA URL and Token from env"""
    url = os.getenv("HA_URL")
    token = os.getenv("HA_TOKEN")

    if not url or not token:
        logger.error("HA_URL or HA_TOKEN not set in environment.")
        sys.exit(1)

    # Strip trailing slash
    return {"url": url.rstrip("/"), "token": token}

def fetch_ha_api(endpoint: str) -> Any:
    """Fetch data from HA API"""
    config = get_ha_config()
    headers = {
        "Authorization": f"Bearer {config['token']}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(f"{config['url']}{endpoint}", headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch {endpoint}: {e}")
        return None

def fetch_logs_via_ssh() -> List[Dict]:
    """Fetch logs via SSH if API fails"""
    # Load SSH config from env
    host = os.getenv("HA_SSH_HOST")
    user = os.getenv("HA_SSH_USER", "root")
    port = os.getenv("HA_SSH_PORT", "22")
    key = os.getenv("HA_SSH_KEY")

    if not host:
        logger.warning("SSH host not configured. Skipping SSH log fetch.")
        return []

    cmd = ["ssh", "-p", port, "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5"]
    if key:
        # Expand tilde if present
        key_path = Path(key).expanduser()
        if key_path.exists():
            cmd.extend(["-i", str(key_path)])

    cmd.append(f"{user}@{host}")
    # Tail last 2000 lines to avoid massive transfer, or cat specific file
    cmd.append("tail -n 2000 /config/home-assistant.log")

    logger.info(f"Attempting SSH log fetch from {host}...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return parse_raw_log(result.stdout)
        else:
            logger.warning(f"SSH failed: {result.stderr}")
    except Exception as e:
        logger.warning(f"SSH execution error: {e}")

    return []

def fetch_logs_via_api() -> List[Dict]:
    """Fetch error logs"""
    config = get_ha_config()
    headers = {"Authorization": f"Bearer {config['token']}"}

    # Attempt API
    try:
        response = requests.get(f"{config['url']}/api/error_log", headers=headers, timeout=15)
        if response.status_code == 200:
            return parse_raw_log(response.text)
        else:
            logger.warning(f"Could not fetch logs via API: {response.status_code}. Trying SSH...")
            return fetch_logs_via_ssh()
    except Exception as e:
        logger.warning(f"Error fetching logs via API: {e}. Trying SSH...")
        return fetch_logs_via_ssh()

def parse_raw_log(log_text: str) -> List[Dict]:
    """Parse raw HA log text into structured dicts"""
    entries = []
    # Very basic parser - looks for YEAR-MO-DAY TIME WARNING/ERROR
    # This is brittle but sufficient for a summary

    lines = log_text.splitlines()
    current_entry = None

    for line in lines:
        if " ERROR " in line or " WARNING " in line or " CRITICAL " in line:
            if current_entry:
                entries.append(current_entry)

            parts = line.split(" ", 3)
            if len(parts) >= 4:
                # 2023-01-30 09:00:00.123 ERROR (MainThread) [component] message
                current_entry = {
                    "raw": line,
                    "timestamp": f"{parts[0]} {parts[1]}",
                    "level": parts[2],
                    "message": parts[3],
                    "count": 1
                }
        elif current_entry:
            # Append stack trace or continuation
            current_entry["message"] += "\n" + line

    if current_entry:
        entries.append(current_entry)

    return entries

def analyze_logs(logs: List[Dict]) -> Dict:
    """Group signals and count errors"""
    stats = {
        "error_count": 0,
        "warning_count": 0,
        "unique_errors": {},
        "top_offenders": []
    }

    for log in logs:
        if "ERROR" in log["level"]:
            stats["error_count"] += 1
        elif "WARNING" in log["level"]:
            stats["warning_count"] += 1

        # Create a signature based on the first line of the message (usually component + error)
        # Simplify message to avoid unique timestamps/IDs in message body
        signature = log["message"].split("\n")[0][:100]

        if signature not in stats["unique_errors"]:
            stats["unique_errors"][signature] = {
                "count": 0,
                "first_seen": log["timestamp"],
                "last_seen": log["timestamp"],
                "example": log["message"][:200] + "..."
            }

        entry = stats["unique_errors"][signature]
        entry["count"] += 1
        entry["last_seen"] = log["timestamp"]

    # Sort top offenders
    sorted_errors = sorted(
        stats["unique_errors"].items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )

    stats["top_offenders"] = [{"signature": k, **v} for k, v in sorted_errors[:20]]

    return stats

def get_system_stats() -> Dict:
    """Get HA System info"""
    # /api/config gives version, etc.
    # /api/states returns all states (can find uptime)

    config = fetch_ha_api("/api/config")

    # Find uptime from a sensor if it exists, or just return basic config
    return {
        "version": config.get("version", "unknown"),
        "state": config.get("state", "unknown"),
        "time_zone": config.get("time_zone", "unknown")
    }

def generate_markdown(stats: Dict, system: Dict, diff_note: str) -> str:
    """Generate the Health Packet Markdown"""
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    md = [f"# Morning Health Packet: {today}"]

    # Headline
    if stats["error_count"] == 0 and stats["warning_count"] == 0:
        md.append("## Status: All Clear")
    else:
        md.append(f"## Issues Detected: {stats['error_count']} Errors, {stats['warning_count']} Warnings")

    if diff_note:
        md.append(f"\n> {diff_note}\n")

    # System Info
    md.append("## System Snapshot")
    md.append(f"- **Version**: {system['version']}")
    md.append(f"- **State**: {system['state']}")
    md.append(f"- **Generated**: {datetime.datetime.now().isoformat()}")

    # Top Offenders
    if stats["top_offenders"]:
        md.append("\n## Top Unique Issues")
        md.append("| Count | Level | Signature | Last Seen |")
        md.append("| :--- | :--- | :--- | :--- |")

        for item in stats["top_offenders"]:
            # Extract level/component from signature if possible, or just use raw
            # This is rough parsing
            level = "ERR" if "ERROR" in item['signature'] else "WARN"
            sig_clean = item['signature'].replace("|", "/")
            md.append(f"| {item['count']} | {level} | `{sig_clean}` | {item['last_seen']} |")

    return "\n".join(md)

def load_previous_stats() -> Dict:
    """Load yesterday's stats for diffing"""
    state_file = DATA_DIR / "latest_state.json"
    if state_file.exists():
        try:
            with open(state_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}

def save_current_stats(stats: Dict):
    """Save current stats for tomorrow"""
    state_file = DATA_DIR / "latest_state.json"
    try:
        with open(state_file, "w") as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save state: {e}")

def main():
    parser = argparse.ArgumentParser(description="Generate HA Morning Health Packet")
    parser.add_argument("--dry-run", action="store_true", help="Don't write files")
    args = parser.parse_args()

    setup_env()

    logger.info("Fetching logs...")
    logs = fetch_logs_via_api()

    logger.info("Analyzing data...")
    log_stats = analyze_logs(logs)
    system_stats = get_system_stats()

    # Diff logic (Basic)
    prev_stats = load_previous_stats()
    diff_msg = ""
    if prev_stats:
        prev_err = prev_stats.get("error_count", 0)
        curr_err = log_stats["error_count"]
        delta = curr_err - prev_err
        if delta > 0:
            diff_msg = f"**Trend**: +{delta} errors since last run."
        elif delta < 0:
            diff_msg = f"**Trend**: {delta} errors (improvement)."
        else:
            diff_msg = "**Trend**: Stable error count."
    else:
        diff_msg = "First run: No previous data."

    # Generate Report
    report = generate_markdown(log_stats, system_stats, diff_msg)

    if args.dry_run:
        print(report)
    else:
        # Ensure output directory exists
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Write Report
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        filename = DATA_DIR / f"{today}_ha_health.md"

        logger.info(f"Writing report to {filename}")
        with open(filename, "w") as f:
            f.write(report)

        # Update State
        save_current_stats(log_stats)

    logger.info("Done.")

if __name__ == "__main__":
    main()
