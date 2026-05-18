from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qsl, urlparse

from .adventure import AdventureDefinition, validate_adventure
from .adventure_importer import campaign_from_adventure
from .adventure_runtime import AdventureRuntime, handle_adventure_action
from .ai_dm import generate_dm_suggestion
from .ai_provider import AIProvider
from .core.campaign import Campaign
from .core.serialization import campaign_to_dict, load_campaign, save_campaign
from .rules_corpus import RuleCorpus
from .sample_data import sample_adventure_character, sample_adventure_template


@dataclass
class APIState:
    campaigns: dict[str, Campaign] = field(default_factory=dict)
    rules_corpus: RuleCorpus | None = None
    ai_provider: AIProvider | None = None
    state_dir: Path | None = None


class APIError(Exception):
    def __init__(self, status: int, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code or _default_error_code(status)

    def to_response(self) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
            },
            "error_message": self.message,
        }


def import_adventure(state: APIState, adventure_data: dict) -> dict:
    adventure = AdventureDefinition(adventure_data)
    validate_adventure(adventure)
    campaign = campaign_from_adventure(adventure)
    state.campaigns[campaign.id] = campaign
    _persist_campaign(state, campaign)
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


def list_campaigns(state: APIState) -> dict:
    return {
        "campaigns": [
            {
                "id": campaign.id,
                "title": campaign.title,
                "party_level": campaign.party_level,
                "current_location_id": campaign.current_location_id,
                "character_count": len(campaign.characters),
                "session_event_count": len(campaign.session_log),
                "active_combat": campaign.active_combat is not None,
            }
            for campaign in state.campaigns.values()
        ]
    }


def delete_campaign(state: APIState, campaign_id: str) -> dict:
    _campaign_or_404(state, campaign_id)
    del state.campaigns[campaign_id]
    _delete_persisted_campaign(state, campaign_id)
    return {"deleted": True, "campaign_id": campaign_id}


def campaign_state(state: APIState, campaign_id: str) -> dict:
    return campaign_to_dict(_campaign_or_404(state, campaign_id))


def campaign_log(state: APIState, campaign_id: str, limit: int = 50) -> dict:
    if limit < 1:
        raise APIError(400, "limit must be at least 1.", "invalid_limit")
    campaign = _campaign_or_404(state, campaign_id)
    events = campaign.session_log[-limit:]
    return {
        "campaign_id": campaign.id,
        "events": [_event_message(event) for event in events],
    }


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
        "session_event_count": len(campaign.session_log),
        "active_combat": active_combat,
        "available_actions": _available_actions(campaign, active_combat),
        "recent_events": [_event_message(event) for event in campaign.session_log[-10:]],
    }


def add_sample_character(state: APIState, campaign_id: str) -> dict:
    campaign = _campaign_or_404(state, campaign_id)
    character = sample_adventure_character()
    if character.name in campaign.characters:
        raise APIError(400, f"Character already exists: {character.name}")
    campaign.add_character(character)
    _persist_campaign(state, campaign)
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
        raise APIError(400, "Action cannot be empty.", "empty_action")
    campaign = _campaign_or_404(state, campaign_id)
    event_count = len(campaign.session_log)
    runtime = AdventureRuntime(campaign, rng=random.Random(seed))
    keep_going = handle_adventure_action(runtime, action)
    _persist_campaign(state, campaign)
    return {
        "campaign_id": campaign.id,
        "keep_going": keep_going,
        "transcript": runtime.flush(),
        "messages": [_event_message(event) for event in campaign.session_log[event_count:]],
        "campaign": campaign_to_dict(campaign),
    }


def search_rules(state: APIState, query: str, limit: int = 5) -> dict:
    if state.rules_corpus is None:
        raise APIError(503, "Rules corpus is not configured.", "rules_corpus_not_configured")
    try:
        results = state.rules_corpus.search(query, limit=limit)
    except ValueError as exc:
        raise APIError(400, str(exc), "invalid_rules_query") from exc
    return {"query": query, "results": [result.to_dict() for result in results]}


def health_status(state: APIState) -> dict:
    return {
        "ok": True,
        "campaign_count": len(state.campaigns),
        "features": {
            "rules_search": state.rules_corpus is not None,
            "ai_dm": state.ai_provider is not None,
            "persistent_state": state.state_dir is not None,
        },
    }


def suggest_dm_turn(state: APIState, campaign_id: str, action: str, include_prompt: bool = False) -> dict:
    if state.ai_provider is None:
        raise APIError(503, "AI provider is not configured.", "ai_provider_not_configured")
    campaign = _campaign_or_404(state, campaign_id)
    try:
        suggestion = generate_dm_suggestion(
            campaign,
            action,
            state.ai_provider,
            rules_corpus=state.rules_corpus,
            include_prompt=include_prompt,
        )
    except ValueError as exc:
        raise APIError(400, str(exc), "invalid_dm_suggestion_request") from exc
    return {
        "campaign_id": campaign.id,
        "suggestion": suggestion.to_dict(include_prompt=include_prompt),
        "metadata": {
            "rules_count": len(suggestion.rules),
            "used_rules": bool(suggestion.rules),
            "included_prompt": include_prompt,
        },
    }


def create_handler(state: APIState) -> type[BaseHTTPRequestHandler]:
    class DNDAPIHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._handle("GET")

        def do_POST(self) -> None:
            self._handle("POST")

        def do_DELETE(self) -> None:
            self._handle("DELETE")

        def do_OPTIONS(self) -> None:
            self._write_json(200, {"ok": True})

        def log_message(self, format: str, *args) -> None:
            return

        def _handle(self, method: str) -> None:
            try:
                response = route_request(state, method, self.path, self._read_json())
                self._write_json(200, response)
            except APIError as exc:
                self._write_json(exc.status, exc.to_response())
            except Exception as exc:
                self._write_json(500, _error_response("internal_error", str(exc)))

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            if length == 0:
                return {}
            try:
                return json.loads(self.rfile.read(length).decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise APIError(400, "Request body must be valid JSON.", "invalid_json") from exc

        def _write_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return DNDAPIHandler


def route_request(state: APIState, method: str, path: str, body: dict) -> dict:
    parsed = urlparse(path)
    query = _query_params(parsed.query)
    parts = [part for part in parsed.path.split("/") if part]
    if method == "GET" and parts == ["health"]:
        return health_status(state)
    if method == "GET" and parts == ["campaigns"]:
        return list_campaigns(state)
    if method == "POST" and parts == ["campaigns", "import"]:
        adventure = body.get("adventure")
        if not isinstance(adventure, dict):
            raise APIError(400, "Missing adventure object.", "missing_adventure")
        return import_adventure(state, adventure)
    if method == "POST" and parts == ["campaigns", "demo"]:
        return create_demo_campaign(state)
    if method == "POST" and parts == ["campaigns", "demo-with-character"]:
        return create_playable_demo_campaign(state)
    if method == "POST" and parts == ["rules", "search"]:
        query = str(body.get("query", ""))
        limit = _int_body(body, "limit", 5)
        return search_rules(state, query, limit=limit)
    if method == "GET" and len(parts) == 2 and parts[0] == "campaigns":
        return campaign_state(state, parts[1])
    if method == "DELETE" and len(parts) == 2 and parts[0] == "campaigns":
        return delete_campaign(state, parts[1])
    if method == "GET" and len(parts) == 3 and parts[0] == "campaigns" and parts[2] == "summary":
        return campaign_summary(state, parts[1])
    if method == "GET" and len(parts) == 3 and parts[0] == "campaigns" and parts[2] == "log":
        return campaign_log(state, parts[1], limit=_int_query(query, "limit", 50))
    if method == "POST" and len(parts) == 3 and parts[0] == "campaigns" and parts[2] == "sample-character":
        return add_sample_character(state, parts[1])
    if method == "POST" and len(parts) == 3 and parts[0] == "campaigns" and parts[2] == "actions":
        action = str(body.get("action", ""))
        seed = _int_body(body, "seed", 1)
        return run_campaign_action(state, parts[1], action, seed=seed)
    if method == "POST" and len(parts) == 3 and parts[0] == "campaigns" and parts[2] == "dm-suggestion":
        action = str(body.get("action", ""))
        include_prompt = bool(body.get("include_prompt", False))
        return suggest_dm_turn(state, parts[1], action, include_prompt=include_prompt)
    raise APIError(404, "Route not found.", "route_not_found")


def run_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    state: APIState | None = None,
    rules_corpus_path: str | None = None,
    ai_provider: AIProvider | None = None,
    state_dir: str | None = None,
    server_factory: Callable[..., ThreadingHTTPServer] = ThreadingHTTPServer,
) -> None:
    api_state = state or APIState()
    if state_dir is not None:
        api_state.state_dir = Path(state_dir)
        load_campaigns_from_state_dir(api_state)
    if rules_corpus_path is not None:
        api_state.rules_corpus = RuleCorpus.load_jsonl(rules_corpus_path)
    if ai_provider is not None:
        api_state.ai_provider = ai_provider
    server = server_factory((host, port), create_handler(api_state))
    server.serve_forever()


def load_campaigns_from_state_dir(state: APIState) -> None:
    if state.state_dir is None:
        return
    state.state_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(state.state_dir.glob("*.json")):
        campaign = load_campaign(path)
        state.campaigns[campaign.id] = campaign


def _campaign_or_404(state: APIState, campaign_id: str) -> Campaign:
    campaign = state.campaigns.get(campaign_id)
    if campaign is None:
        raise APIError(404, "Campaign not found.", "campaign_not_found")
    return campaign


def _error_response(code: str, message: str) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
        },
        "error_message": message,
    }


def _default_error_code(status: int) -> str:
    if status == 400:
        return "bad_request"
    if status == 404:
        return "not_found"
    if status == 503:
        return "service_unavailable"
    return "api_error"


def _persist_campaign(state: APIState, campaign: Campaign) -> None:
    if state.state_dir is None:
        return
    state.state_dir.mkdir(parents=True, exist_ok=True)
    save_campaign(campaign, state.state_dir / f"{campaign.id}.json")


def _delete_persisted_campaign(state: APIState, campaign_id: str) -> None:
    if state.state_dir is None:
        return
    path = state.state_dir / f"{campaign_id}.json"
    if path.exists():
        path.unlink()


def _int_body(body: dict, key: str, default: int) -> int:
    value = body.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise APIError(400, f"{key} must be an integer.", "invalid_integer") from exc


def _query_params(query: str) -> dict[str, str]:
    return {key: value for key, value in parse_qsl(query)}


def _int_query(query: dict[str, str], key: str, default: int) -> int:
    value = query.get(key, str(default))
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise APIError(400, f"{key} must be an integer.", "invalid_integer") from exc


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
