from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import urlparse

from .adventure import AdventureDefinition, validate_adventure
from .adventure_importer import campaign_from_adventure
from .adventure_runtime import AdventureRuntime, handle_adventure_action
from .core.campaign import Campaign
from .core.serialization import campaign_to_dict
from .sample_data import sample_adventure_character, sample_adventure_template


@dataclass
class APIState:
    campaigns: dict[str, Campaign] = field(default_factory=dict)


class APIError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def import_adventure(state: APIState, adventure_data: dict) -> dict:
    adventure = AdventureDefinition(adventure_data)
    validate_adventure(adventure)
    campaign = campaign_from_adventure(adventure)
    state.campaigns[campaign.id] = campaign
    return {
        "campaign_id": campaign.id,
        "campaign": campaign_to_dict(campaign),
    }


def create_demo_campaign(state: APIState) -> dict:
    return import_adventure(state, sample_adventure_template())


def create_playable_demo_campaign(state: APIState) -> dict:
    response = create_demo_campaign(state)
    add_sample_character(state, response["campaign_id"])
    return {
        "campaign_id": response["campaign_id"],
        "campaign": campaign_to_dict(state.campaigns[response["campaign_id"]]),
    }


def campaign_state(state: APIState, campaign_id: str) -> dict:
    return campaign_to_dict(_campaign_or_404(state, campaign_id))


def campaign_summary(state: APIState, campaign_id: str) -> dict:
    campaign = _campaign_or_404(state, campaign_id)
    location = campaign.locations.get(campaign.current_location_id or "")
    active_combat = _active_combat_summary(campaign)
    return {
        "id": campaign.id,
        "title": campaign.title,
        "system": campaign.system,
        "tone": campaign.tone,
        "party_level": campaign.party_level,
        "current_location": None
        if location is None
        else {
            "id": location.id,
            "name": location.name,
            "public_description": location.public_description,
            "exits": [
                {"id": location_id, "name": campaign.locations[location_id].name}
                for location_id in location.connected_location_ids
                if location_id in campaign.locations
            ],
            "npcs": [
                {
                    "id": npc.id,
                    "name": npc.name,
                    "role": npc.role,
                    "public_description": npc.public_description,
                }
                for npc in campaign.npcs.values()
                if npc.location_id == location.id
            ],
        },
        "characters": [
            {
                "name": character.name,
                "player_name": character.player_name,
                "class_name": character.class_name,
                "level": character.level,
                "ancestry": character.ancestry,
                "armor_class": character.armor_class,
                "current_hp": character.current_hp,
                "max_hp": character.max_hp,
                "spellcasting": _spellcasting_summary(character),
            }
            for character in campaign.characters.values()
        ],
        "quest_count": len(campaign.quests),
        "active_quest_count": sum(1 for quest in campaign.quests.values() if quest.status == "active"),
        "clue_count": len(campaign.clues),
        "discovered_clue_count": sum(1 for clue in campaign.clues.values() if clue.discovered),
        "active_combat": active_combat,
        "available_actions": _available_actions(campaign, active_combat),
    }


def add_sample_character(state: APIState, campaign_id: str) -> dict:
    campaign = _campaign_or_404(state, campaign_id)
    character = sample_adventure_character()
    if character.name in campaign.characters:
        raise APIError(400, f"Character already exists: {character.name}")
    campaign.add_character(character)
    return {
        "campaign_id": campaign.id,
        "character": {
            "name": character.name,
            "class_name": character.class_name,
            "level": character.level,
            "ancestry": character.ancestry,
        },
        "campaign": campaign_to_dict(campaign),
    }


def run_campaign_action(state: APIState, campaign_id: str, action: str, seed: int = 1) -> dict:
    if not action.strip():
        raise APIError(400, "Action cannot be empty.")
    campaign = _campaign_or_404(state, campaign_id)
    event_count = len(campaign.session_log)
    runtime = AdventureRuntime(campaign, rng=random.Random(seed))
    keep_going = handle_adventure_action(runtime, action)
    return {
        "campaign_id": campaign.id,
        "keep_going": keep_going,
        "transcript": runtime.flush(),
        "messages": [_event_message(event) for event in campaign.session_log[event_count:]],
        "campaign": campaign_to_dict(campaign),
    }


def create_handler(state: APIState) -> type[BaseHTTPRequestHandler]:
    class DNDAPIHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._handle("GET")

        def do_POST(self) -> None:
            self._handle("POST")

        def do_OPTIONS(self) -> None:
            self._write_json(200, {"ok": True})

        def log_message(self, format: str, *args) -> None:
            return

        def _handle(self, method: str) -> None:
            try:
                response = route_request(state, method, self.path, self._read_json())
                self._write_json(200, response)
            except APIError as exc:
                self._write_json(exc.status, {"error": exc.message})
            except Exception as exc:
                self._write_json(500, {"error": str(exc)})

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            if length == 0:
                return {}
            try:
                return json.loads(self.rfile.read(length).decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise APIError(400, "Request body must be valid JSON.") from exc

        def _write_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return DNDAPIHandler


def route_request(state: APIState, method: str, path: str, body: dict) -> dict:
    parsed = urlparse(path)
    parts = [part for part in parsed.path.split("/") if part]
    if method == "GET" and parts == ["health"]:
        return {"ok": True}
    if method == "POST" and parts == ["campaigns", "import"]:
        adventure = body.get("adventure")
        if not isinstance(adventure, dict):
            raise APIError(400, "Missing adventure object.")
        return import_adventure(state, adventure)
    if method == "POST" and parts == ["campaigns", "demo"]:
        return create_demo_campaign(state)
    if method == "POST" and parts == ["campaigns", "demo-with-character"]:
        return create_playable_demo_campaign(state)
    if method == "GET" and len(parts) == 2 and parts[0] == "campaigns":
        return campaign_state(state, parts[1])
    if method == "GET" and len(parts) == 3 and parts[0] == "campaigns" and parts[2] == "summary":
        return campaign_summary(state, parts[1])
    if method == "POST" and len(parts) == 3 and parts[0] == "campaigns" and parts[2] == "sample-character":
        return add_sample_character(state, parts[1])
    if method == "POST" and len(parts) == 3 and parts[0] == "campaigns" and parts[2] == "actions":
        action = str(body.get("action", ""))
        seed = int(body.get("seed", 1))
        return run_campaign_action(state, parts[1], action, seed=seed)
    raise APIError(404, "Route not found.")


def run_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    state: APIState | None = None,
    server_factory: Callable[..., ThreadingHTTPServer] = ThreadingHTTPServer,
) -> None:
    api_state = state or APIState()
    server = server_factory((host, port), create_handler(api_state))
    server.serve_forever()


def _campaign_or_404(state: APIState, campaign_id: str) -> Campaign:
    campaign = state.campaigns.get(campaign_id)
    if campaign is None:
        raise APIError(404, "Campaign not found.")
    return campaign


def _active_combat_summary(campaign: Campaign) -> dict | None:
    combat = campaign.active_combat
    if combat is None:
        return None
    return {
        "encounter_id": combat.get("encounter_id"),
        "round": combat.get("round", 1),
        "turn": combat.get("turn"),
        "initiative": [
            {
                "name": entry.get("name"),
                "initiative_total": entry.get("initiative_total", 0),
                "armor_class": entry.get("armor_class"),
                "current_hp": entry.get("current_hp"),
                "is_player": entry.get("is_player", False),
            }
            for entry in combat.get("initiative", [])
        ],
        "current_resources": combat.get("resources", {}).get(combat.get("turn"), {}),
    }


def _spellcasting_summary(character) -> dict | None:
    if character.spellcasting is None:
        return None
    spellcasting = character.spellcasting
    return {
        "ability": spellcasting.ability,
        "slots": [
            {
                "level": level,
                "total": total,
                "expended": spellcasting.expended_slots_by_level.get(level, 0),
                "available": spellcasting.available_slots(level),
            }
            for level, total in sorted(spellcasting.slots_by_level.items())
        ],
        "known_spells": [
            {
                "name": spell.name,
                "level": spell.level,
                "casting_time": spell.casting_time,
                "concentration": spell.concentration,
            }
            for spell in spellcasting.known_spells
        ],
        "concentration_spell_name": spellcasting.concentration_spell_name,
    }


def _available_actions(campaign: Campaign, active_combat: dict | None) -> list[str]:
    actions = ["look", "inspect", "talk", "quests", "log"]
    location = campaign.locations.get(campaign.current_location_id or "")
    if location is not None:
        actions.extend(f"go {campaign.locations[location_id].name.lower()}" for location_id in location.connected_location_ids if location_id in campaign.locations)
        if any(npc.location_id == location.id for npc in campaign.npcs.values()):
            actions.append("talk mayor")
        if any(encounter.location_id == location.id and not encounter.resolved for encounter in campaign.encounters.values()):
            actions.append("fight")
    if active_combat is not None:
        actions.extend(["combat", "attack", "cast sacred flame", "cast cure wounds", "end turn", "resolve encounter"])
    return list(dict.fromkeys(actions))


def _event_message(event) -> dict:
    return {
        "id": event.id,
        "actor": event.actor,
        "content": event.content,
        "visibility": event.visibility.value,
        "created_at": event.created_at.isoformat(),
    }
