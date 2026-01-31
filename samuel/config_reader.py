"""Reads and parses YAML config files from the ha-config repo."""

import os
import re
import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# Resolved once at import; overridden by env var if set
_repo_path: Path | None = None


def get_repo_path() -> Path:
    """Return the root of the ha-config repo.

    Requires the REPO_PATH environment variable to be set.
    """
    global _repo_path
    if _repo_path is None:
        env_path = os.environ.get("REPO_PATH")
        if not env_path:
            raise RuntimeError(
                "REPO_PATH not set — point it at your ha-config clone"
            )
        _repo_path = Path(env_path)
        logger.info("Repo path: %s", _repo_path)
    return _repo_path


def read_yaml(filename: str) -> dict | None:
    """Read and parse a YAML file. Returns parsed dict or None on error."""
    path = _resolve_config_path(filename)
    if not path or not path.exists():
        return None
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.error("YAML parse error in %s: %s", path, e)
        return None


def read_yaml_raw(filename: str) -> str | None:
    """Read a YAML file and return raw text content."""
    path = _resolve_config_path(filename)
    if not path or not path.exists():
        return None
    return path.read_text()


def find_yaml_files() -> list[Path]:
    """List all YAML config files in the repo (packages, scripts, etc.)."""
    repo = get_repo_path()
    files = []
    # Top-level config files
    for name in ("configuration.yaml", "scripts.yaml", "automations.yaml",
                 "scenes.yaml", "ui-lovelace.yaml"):
        p = repo / name
        if p.exists():
            files.append(p)
    # Package files
    pkg_dir = repo / "packages"
    if pkg_dir.is_dir():
        files.extend(sorted(pkg_dir.glob("*.yaml")))
    return files


def search_yaml(pattern: str) -> list[dict]:
    """Case-insensitive search across all YAML files.

    Returns list of {file, line, text} dicts.
    """
    regex = re.compile(pattern, re.IGNORECASE)
    results = []
    for path in find_yaml_files():
        try:
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                if regex.search(line):
                    results.append({
                        "file": str(path.relative_to(get_repo_path())),
                        "line": lineno,
                        "text": line.strip(),
                    })
        except Exception as e:
            logger.warning("Error reading %s: %s", path, e)
    return results


def extract_automations() -> list[dict]:
    """Extract all automations from all YAML files.

    Returns list of dicts with keys: id, alias, triggers, file.
    """
    automations = []
    for path in find_yaml_files():
        data = read_yaml(str(path))
        if not data:
            continue
        rel = str(path.relative_to(get_repo_path()))
        _extract_from_data(data, rel, automations)
    return automations


def _extract_from_data(data: dict | list, rel_path: str,
                       results: list[dict]) -> None:
    """Recursively find automation blocks in parsed YAML data."""
    if isinstance(data, dict):
        auto_list = data.get("automation")
        if isinstance(auto_list, list):
            for a in auto_list:
                if isinstance(a, dict):
                    results.append(_summarize_automation(a, rel_path))
        # Also check top-level list (automations.yaml format)
        for v in data.values():
            if isinstance(v, dict):
                _extract_from_data(v, rel_path, results)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "alias" in item:
                results.append(_summarize_automation(item, rel_path))


def _summarize_automation(auto: dict, rel_path: str) -> dict:
    """Build a summary dict from a raw automation dict."""
    triggers = auto.get("triggers") or auto.get("trigger") or []
    if not isinstance(triggers, list):
        triggers = [triggers]
    trigger_summaries = []
    for t in triggers:
        if isinstance(t, dict):
            parts = []
            if "platform" in t:
                parts.append(t["platform"])
            if "trigger" in t:
                parts.append(t["trigger"])
            if "event" in t:
                parts.append(str(t["event"]))
            if "at" in t:
                parts.append(f"at {t['at']}")
            if "entity_id" in t:
                eid = t["entity_id"]
                if isinstance(eid, list):
                    eid = ", ".join(eid)
                parts.append(eid)
            trigger_summaries.append(" ".join(parts))
    return {
        "id": auto.get("id", ""),
        "alias": auto.get("alias", ""),
        "triggers": trigger_summaries,
        "file": rel_path,
    }


def extract_scripts() -> list[dict]:
    """Extract all scripts from scripts.yaml and packages.

    Returns list of dicts with keys: name, alias, actions, file.
    """
    scripts = []
    for path in find_yaml_files():
        data = read_yaml(str(path))
        if not data:
            continue
        rel = str(path.relative_to(get_repo_path()))
        # scripts.yaml is a top-level dict of script_name: {sequence, alias}
        if isinstance(data, dict):
            script_section = data.get("script", data)
            if rel == "scripts.yaml":
                script_section = data
            for name, body in script_section.items():
                if isinstance(body, dict) and "sequence" in body:
                    actions = []
                    for step in body.get("sequence", []):
                        if isinstance(step, dict):
                            action = step.get("action") or step.get("service", "")
                            if action:
                                target = step.get("target", {})
                                eid = target.get("entity_id", "")
                                if isinstance(eid, list):
                                    eid = ", ".join(eid)
                                actions.append(f"{action} → {eid}" if eid else action)
                    scripts.append({
                        "name": name,
                        "alias": body.get("alias", ""),
                        "actions": actions,
                        "file": rel,
                    })
    return scripts


def _resolve_config_path(filename: str) -> Path | None:
    """Resolve a config filename to an absolute path."""
    repo = get_repo_path()
    # Try as-is first
    path = repo / filename
    if path.exists():
        return path
    # Try under packages/
    path = repo / "packages" / filename
    if path.exists():
        return path
    # Try adding .yaml
    if not filename.endswith(".yaml"):
        return _resolve_config_path(filename + ".yaml")
    return None
