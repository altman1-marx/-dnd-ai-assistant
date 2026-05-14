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
from .sample_data import sample_adventure_character


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


def campaign_state(state: APIState, campaign_id: str) -> dict:
    return campaign_to_dict(_campaign_or_404(state, campaign_id))


def campaign_summary(state: APIState, campaign_id: str) -> dict:
    campaign = _campaign_or_404(state, campaign_id)
    location = campaign.locations.get(campaign.current_location_id or "")
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
            }
            for character in campaign.characters.values()
        ],
        "quest_count": len(campaign.quests),
        "active_quest_count": sum(1 for quest in campaign.quests.values() if quest.status == "active"),
        "clue_count": len(campaign.clues),
        "discovered_clue_count": sum(1 for clue in campaign.clues.values() if clue.discovered),
        "active_combat": _active_combat_summary(campaign),
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
    runtime = AdventureRuntime(campaign, rng=random.Random(seed))
    keep_going = handle_adventure_action(runtime, action)
    return {
        "campaign_id": campaign.id,
        "keep_going": keep_going,
        "transcript": runtime.flush(),
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
