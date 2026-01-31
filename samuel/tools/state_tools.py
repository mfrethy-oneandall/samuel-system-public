"""MCP tools for querying Home Assistant live state."""

from samuel import ha_client

# Known area → entity prefix mappings for area lookups
AREA_PREFIXES = {
    "front_room": ["light.front_room", "switch.fireplace", "switch.christmas",
                    "media_player.living_room"],
    "living_room": ["light.front_room", "switch.fireplace", "switch.christmas",
                     "media_player.living_room"],
    "porch": ["light.front_porch", "switch.front_porch"],
    "front_porch": ["light.front_porch", "switch.front_porch"],
    "hallway": ["light.zb_bulb_upstairs_hall", "switch.hallway",
                "binary_sensor.zb_motion_upstairs_hall"],
    "upstairs_hallway": ["light.zb_bulb_upstairs_hall", "switch.hallway",
                         "binary_sensor.zb_motion_upstairs_hall"],
    "stairs": ["switch.stairway"],
    "master_bath": ["light.master_bathroom", "binary_sensor.zb_motion_master_bath"],
    "master_bathroom": ["light.master_bathroom", "binary_sensor.zb_motion_master_bath"],
    "master_bedroom": ["light.master_bedroom_light", "light.YOUR_ZIGBEE_BULB_1",
                       "media_player.master_bedroom"],
    "bedroom": ["light.master_bedroom_light", "light.YOUR_ZIGBEE_BULB_1",
                "media_player.master_bedroom"],
    "bedroom_3": ["light.bedroom_3_light", "media_player.bedroom_3"],
}


async def get_entity_state(entity_id: str) -> str:
    """Get the current state of a Home Assistant entity.

    Args:
        entity_id: Full entity ID (e.g. "light.front_room_front_reading_light")
                   or a partial search term (e.g. "porch light", "reading light").
                   Partial terms will fuzzy-match against entity IDs and
                   friendly names.
    """
    # If it looks like a full entity_id, try direct lookup first
    if "." in entity_id and " " not in entity_id:
        state = await ha_client.get_state(entity_id)
        if state and "entity_id" in state:
            return _format_state(state)

    # Fuzzy search
    matches = await ha_client.find_entity(entity_id)
    if not matches:
        return f"No entity found matching '{entity_id}'."

    if len(matches) == 1:
        return _format_state(matches[0])

    # Multiple matches — show summary
    lines = [f"Found {len(matches)} entities matching '{entity_id}':\n"]
    for s in matches[:20]:
        fname = s.get("attributes", {}).get("friendly_name", "")
        lines.append(f"- **{s['entity_id']}** ({fname}): {s['state']}")
    if len(matches) > 20:
        lines.append(f"... and {len(matches) - 20} more")
    return "\n".join(lines)


async def get_entities_by_domain(domain: str) -> str:
    """List all entities for a given domain with their current state.

    Args:
        domain: Entity domain, e.g. "light", "switch", "automation",
                "input_boolean", "sensor", "binary_sensor", "timer".
    """
    states = await ha_client.get_states_by_domain(domain)
    if not states:
        return f"No entities found for domain '{domain}' (or HA is unreachable)."

    lines = [f"**{domain}** — {len(states)} entities:\n"]
    for s in sorted(states, key=lambda x: x["entity_id"]):
        fname = s.get("attributes", {}).get("friendly_name", "")
        state = s["state"]
        lines.append(f"- `{s['entity_id']}`: **{state}** ({fname})")
    return "\n".join(lines)


async def get_area_state(area: str) -> str:
    """Get the state of all entities in a home area.

    Args:
        area: Area name, e.g. "living room", "porch", "master bedroom",
              "hallway", "stairs", "master bath", "bedroom_3".
    """
    key = area.lower().replace(" ", "_").replace("'", "")
    prefixes = AREA_PREFIXES.get(key)
    if not prefixes:
        available = ", ".join(sorted(set(AREA_PREFIXES.keys())))
        return (
            f"Unknown area '{area}'.\n\n"
            f"Known areas: {available}"
        )

    all_states = await ha_client.get_states()
    if not all_states:
        return "Cannot connect to Home Assistant."

    matches = []
    for s in all_states:
        eid = s["entity_id"]
        if any(eid.startswith(p) for p in prefixes):
            matches.append(s)

    if not matches:
        return f"No entities found for area '{area}'."

    lines = [f"**{area.title()}** — {len(matches)} entities:\n"]
    for s in sorted(matches, key=lambda x: x["entity_id"]):
        fname = s.get("attributes", {}).get("friendly_name", "")
        state = s["state"]
        attrs = s.get("attributes", {})
        detail = ""
        if "brightness" in attrs:
            bri = round(attrs["brightness"] / 255 * 100)
            detail += f", brightness: {bri}%"
        if "color_temp_kelvin" in attrs:
            detail += f", {attrs['color_temp_kelvin']}K"
        if "temperature" in attrs:
            detail += f", temp: {attrs['temperature']}"
        lines.append(f"- `{s['entity_id']}`: **{state}**{detail} ({fname})")
    return "\n".join(lines)


def _format_state(state: dict) -> str:
    """Format a single entity state dict into a readable string."""
    eid = state["entity_id"]
    s = state["state"]
    attrs = state.get("attributes", {})
    fname = attrs.get("friendly_name", "")

    lines = [f"**{fname}** (`{eid}`)", f"State: **{s}**"]

    # Include relevant attributes
    skip = {"friendly_name", "supported_features", "supported_color_modes",
            "icon", "entity_picture", "attribution"}
    for k, v in sorted(attrs.items()):
        if k in skip or k.startswith("_"):
            continue
        if k == "brightness" and isinstance(v, (int, float)):
            lines.append(f"  brightness: {round(v / 255 * 100)}%")
        elif k == "color_temp_kelvin":
            lines.append(f"  color_temp: {v}K")
        else:
            lines.append(f"  {k}: {v}")

    last_changed = state.get("last_changed", "")
    if last_changed:
        lines.append(f"  last_changed: {last_changed}")

    return "\n".join(lines)
