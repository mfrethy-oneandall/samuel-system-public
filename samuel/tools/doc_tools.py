"""MCP tools for reading project documentation."""

from samuel.config_reader import get_repo_path


async def read_doc(filename: str) -> str:
    """Read a documentation file from the docs/ directory.

    Args:
        filename: Doc filename, e.g. "system_map.md" or
                  "lighting_standards.md". The "docs/" prefix is optional.
    """
    repo = get_repo_path()
    docs_dir = repo / "docs"

    # Strip leading docs/ if provided
    if filename.startswith("docs/"):
        filename = filename[5:]

    path = docs_dir / filename
    if path.exists():
        return path.read_text()

    # Try adding .md
    if not filename.endswith(".md"):
        path = docs_dir / (filename + ".md")
        if path.exists():
            return path.read_text()

    # List available docs
    available = []
    if docs_dir.is_dir():
        for p in sorted(docs_dir.rglob("*.md")):
            available.append(str(p.relative_to(docs_dir)))

    return (
        f"File '{filename}' not found in docs/.\n\n"
        f"Available docs:\n" +
        "\n".join(f"  - {f}" for f in available)
    )


async def get_system_map() -> str:
    """Return the full system architecture map.

    This is a shortcut for reading docs/system_map.md — the most
    comprehensive reference for the home automation setup.
    """
    return await read_doc("system_map.md")
