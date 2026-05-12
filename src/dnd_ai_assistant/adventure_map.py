from __future__ import annotations

from .adventure import AdventureDefinition


def location_adjacency(adventure: AdventureDefinition) -> dict[str, list[str]]:
    location_ids = {location["id"] for location in adventure.locations}
    adjacency: dict[str, set[str]] = {location_id: set() for location_id in location_ids}
    for location in adventure.locations:
        location_id = location["id"]
        for connected_id in location.get("connections", []):
            if connected_id not in location_ids:
                continue
            adjacency[location_id].add(connected_id)
            adjacency[connected_id].add(location_id)
    return {location_id: sorted(connected_ids) for location_id, connected_ids in adjacency.items()}


def render_text_map(adventure: AdventureDefinition) -> str:
    names = _location_names(adventure)
    adjacency = location_adjacency(adventure)
    lines = [f"Adventure map: {adventure.campaign['title']}"]
    for location_id in sorted(adjacency):
        connected = adjacency[location_id]
        if connected:
            targets = ", ".join(names[connected_id] for connected_id in connected)
        else:
            targets = "(no connections)"
        marker = _location_marker(adventure, location_id)
        lines.append(f"- {marker}{names[location_id]} -> {targets}")
    return "\n".join(lines)


def render_mermaid_map(adventure: AdventureDefinition) -> str:
    names = _location_names(adventure)
    adjacency = location_adjacency(adventure)
    lines = ["graph TD"]
    rendered_edges: set[tuple[str, str]] = set()
    for location_id in sorted(adjacency):
        if not adjacency[location_id]:
            lines.append(f'  {location_id}["{_escape_mermaid_label(names[location_id])}"]')
        for connected_id in adjacency[location_id]:
            edge = tuple(sorted((location_id, connected_id)))
            if edge in rendered_edges:
                continue
            rendered_edges.add(edge)
            left, right = edge
            lines.append(
                f'  {left}["{_escape_mermaid_label(names[left])}"] --- '
                f'{right}["{_escape_mermaid_label(names[right])}"]'
            )
    return "\n".join(lines)


def _location_names(adventure: AdventureDefinition) -> dict[str, str]:
    return {location["id"]: location["name"] for location in adventure.locations}


def _location_marker(adventure: AdventureDefinition, location_id: str) -> str:
    markers = []
    if location_id == adventure.start_location_id:
        markers.append("start")
    if location_id == adventure.final_location_id:
        markers.append("final")
    return f"[{', '.join(markers)}] " if markers else ""


def _escape_mermaid_label(label: str) -> str:
    return label.replace('"', '\\"')
