# Samuel — Home Intelligence MCP Server

[![AI Augmented](https://img.shields.io/badge/AI%20Augmented-Claude%20MCP-6f42c1?logo=anthropic)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](requirements.txt)

Samuel is an MCP server and bridge that gives Claude live access to the Example Home HA config and state. It runs on a dedicated Linux box (`samuel`) alongside a read-only clone of `ha-config`.

> **Note:** This is a sanitized copy of a live deployment. Personal identifiers, device IDs, and network details have been replaced with placeholders. To use it, substitute your own HA host, token, and entity IDs.
>
> Built for [Home Assistant](https://www.home-assistant.io/); not affiliated with or endorsed by the Home Assistant project or Open Home Foundation.

## Quick Start

```bash
# On the Samuel box (Ubuntu Server):
cd ~/samuel-system
bash install.sh
```

The install script will:
1. Find Python 3.10+ (required by the MCP SDK)
2. Create a virtual environment at `.venv`
3. Install dependencies
4. Create `~/data/` for state persistence
5. Optionally install systemd services (auto-start on boot)

## Prerequisites

1. Clone this repo: `git clone git@github.com:your-github-user/samuel-system.git ~/samuel-system`
2. Clone ha-config (read-only): `git clone git@github.com:your-github-user/ha-config.git ~/ha-config`
3. Create `.env` from the example: `cp .env.example .env` and fill in values

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `HA_URL` | Yes | Home Assistant URL (e.g. `http://YOUR_HA_HOST:8123`) |
| `HA_TOKEN` | Yes | HA long-lived access token |
| `REPO_PATH` | Yes | Path to ha-config clone (e.g. `/home/samuel/ha-config`) |
| `DATA_DIR` | No | State persistence directory (default: `~/data`) |
| `SAMUEL_PORT` | No | MCP server port (default: `5100`) |
| `BRIDGE_PORT` | No | Bridge server port (default: `5101`) |

## Manual Run

```bash
source .venv/bin/activate
python -m samuel          # MCP server (port 5100)
python -m samuel.bridge   # Bridge server (port 5101)
```

## Connect Claude Code

```bash
claude mcp add --transport http samuel http://samuel.local:5100/mcp
```

## Connect Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "samuel": {
      "url": "http://samuel.local:5100/mcp"
    }
  }
}
```

## Available Tools

### Config Tools (read from ha-config repo)
| Tool | What It Does |
|------|-------------|
| `read_config` | Read any YAML config file |
| `list_packages` | List all packages with contents summary |
| `list_automations` | List all automations with triggers |
| `list_scripts` | List all scripts with actions |
| `search_config` | Regex search across all config files |

### State Tools (query HA API)
| Tool | What It Does |
|------|-------------|
| `get_entity_state` | Get entity state (supports fuzzy search) |
| `get_entities_by_domain` | List all entities for a domain |
| `get_area_state` | Get all entity states for a room/area |

### Doc Tools
| Tool | What It Does |
|------|-------------|
| `read_doc` | Read any doc from docs/ |
| `get_system_map` | Shortcut for the full system map |

### Health Tools
| Tool | What It Does |
|------|-------------|
| `generate_health_report` | Run health diagnostic with trend tracking |

## Service Management (systemd)

```bash
sudo systemctl status samuel-mcp       # Check status
sudo systemctl status samuel-bridge
sudo systemctl restart samuel-mcp      # Restart
sudo systemctl restart samuel-bridge
journalctl -u samuel-mcp -f            # Follow logs
journalctl -u samuel-bridge -f
```

## Standalone Health Report

The `diagnostics/morning_health.py` script can run independently (e.g. via cron):

```bash
source .venv/bin/activate
python diagnostics/morning_health.py --dry-run   # Preview
python diagnostics/morning_health.py              # Write to DATA_DIR
```

## Testing

```bash
# Start samuel, then in another terminal:
npx @modelcontextprotocol/inspector
# Connect to http://localhost:5100/mcp
# Try calling list_packages, search_config("quiet_hours"), etc.

# Test bridge:
curl http://localhost:5101/ping
curl http://localhost:5101/health
```

## Architecture

```
samuel-system (this repo)     ha-config (separate repo, read-only clone)
├── samuel/                   ├── packages/*.yaml
│   ├── server.py (MCP)      ├── scripts.yaml
│   ├── bridge.py (REST)     ├── docs/
│   ├── config_reader.py ──→ │   └── system_map.md
│   ├── ha_client.py ──→     └── ...
│   └── tools/                Home Assistant (HAOS VM)
├── diagnostics/              ├── /api/states ←── ha_client.py
├── systemd/                  └── /api/error_log ←── health_tools.py
└── .env
```

## Requirements

- Python 3.10+
- Ubuntu Server 24.04 LTS (or similar Linux with systemd)
- `.env` with `HA_URL`, `HA_TOKEN`, and `REPO_PATH`
- Network access to HA instance (for state/health tools)
- Local clone of ha-config (for config/doc tools)
