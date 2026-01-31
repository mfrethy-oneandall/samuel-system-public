"""MCP tools for reading and searching HA config files."""

import json

from samuel import config_reader


async def read_config(filename: str) -> str:
    """Read a Home Assistant config file and return its contents.

    Args:
        filename: Config file name, e.g. "house_mode.yaml" or
                  "packages/house_mode.yaml". Also accepts names without
                  the .yaml extension.
    """
    content = config_reader.read_yaml_raw(filename)
    if content is None:
        available = [
            str(p.relative_to(config_reader.get_repo_path()))
            for p in config_reader.find_yaml_files()
        ]
        return (
            f"File '{filename}' not found.\n\n"
            f"Available config files:\n" +
            "\n".join(f"  - {f}" for f in available)
        )
    return content


async def list_packages() -> str:
    """List all HA package files with their automations and helpers.

    Returns a summary of each package in the packages/ directory.
    """
    repo = config_reader.get_repo_path()
    pkg_dir = repo / "packages"
    if not pkg_dir.is_dir():
        return "No packages/ directory found."

    lines = []
    for path in sorted(pkg_dir.glob("*.yaml")):
        name = path.name
        data = config_reader.read_yaml(str(path))
        if not data:
            lines.append(f"- {name}: (empty or parse error)")
            continue

        parts = []
        # Count automations
        autos = data.get("automation", [])
        if isinstance(autos, list):
            aliases = [a.get("alias", "?") for a in autos if isinstance(a, dict)]
            parts.append(f"{len(aliases)} automation(s)")

        # Count helpers
        for key in ("input_number", "input_boolean", "input_button",
                     "input_select", "timer"):
            section = data.get(key)
            if isinstance(section, dict):
                parts.append(f"{len(section)} {key}")

        # Count scripts
        scripts = data.get("script")
        if isinstance(scripts, dict):
            parts.append(f"{len(scripts)} script(s)")

        summary = ", ".join(parts) if parts else "config only"
        lines.append(f"- **{name}**: {summary}")

    return "\n".join(lines)


async def list_automations() -> str:
    """List all automations across all config files.

    Returns each automation's alias, trigger summary, and source file.
    """
    autos = config_reader.extract_automations()
    if not autos:
        return "No automations found."

    lines = []
    current_file = ""
    for a in sorted(autos, key=lambda x: (x["file"], x["alias"])):
        if a["file"] != current_file:
            current_file = a["file"]
            lines.append(f"\n### {current_file}")
        triggers = "; ".join(a["triggers"]) if a["triggers"] else "none"
        lines.append(f"- **{a['alias']}** (id: {a['id']})")
        lines.append(f"  Triggers: {triggers}")

    return "\n".join(lines)


async def list_scripts() -> str:
    """List all scripts with their key actions.

    Returns each script's name, alias, and action summary.
    """
    scripts = config_reader.extract_scripts()
    if not scripts:
        return "No scripts found."

    lines = []
    current_file = ""
    for s in sorted(scripts, key=lambda x: (x["file"], x["name"])):
        if s["file"] != current_file:
            current_file = s["file"]
            lines.append(f"\n### {current_file}")
        alias = f" ({s['alias']})" if s["alias"] else ""
        lines.append(f"- **{s['name']}**{alias}")
        for action in s["actions"][:5]:
            lines.append(f"  - {action}")
        if len(s["actions"]) > 5:
            lines.append(f"  - ... and {len(s['actions']) - 5} more")

    return "\n".join(lines)


async def search_config(pattern: str) -> str:
    """Search across all config files for a pattern.

    Args:
        pattern: Case-insensitive search pattern (supports regex).

    Returns matching lines with file name and line number.
    """
    results = config_reader.search_yaml(pattern)
    if not results:
        return f"No matches found for '{pattern}'."

    lines = [f"Found {len(results)} match(es) for '{pattern}':\n"]
    current_file = ""
    for r in results:
        if r["file"] != current_file:
            current_file = r["file"]
            lines.append(f"\n**{current_file}:**")
        lines.append(f"  line {r['line']}: {r['text']}")

    return "\n".join(lines)
