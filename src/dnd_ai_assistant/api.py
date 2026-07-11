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
from .adventure_generator import extract_json_object
from .ai_dm import generate_dm_suggestion
from .ai_keeper import generate_keeper_suggestion
from .ai_provider import AIProvider
from .coc_briefing import build_coc_briefing
from .coc_runtime import COCRuntime, COCScenario, coc_demo_scenario_names, coc_keeper_hint, create_coc_demo_scenario, handle_coc_action
from .coc_generator import COCScenarioRequest, generate_coc_scenario_text
from .coc_review import coc_review_to_dict
from .coc_serialization import coc_scenario_from_dict, coc_scenario_to_dict, load_coc_scenario, save_coc_scenario
from .core.campaign import Campaign, Visibility
from .core.serialization import campaign_to_dict, load_campaign, save_campaign
from .rules_corpus import RuleCorpus
from .sample_data import sample_adventure_character, sample_adventure_template


@dataclass
class APIState:
    campaigns: dict[str, Campaign] = field(default_factory=dict)
    coc_scenarios: dict[str, COCScenario] = field(default_factory=dict)
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
                "current_location_name": _campaign_location_name(campaign),
                "character_count": len(campaign.characters),
                "session_event_count": len(campaign.session_log),
                "active_combat": campaign.active_combat is not None,
            }
            for campaign in state.campaigns.values()
        ],
        "coc_scenarios": [_coc_scenario_list_item(scenario) for scenario in state.coc_scenarios.values()],
    }


def list_coc_scenarios(state: APIState) -> dict:
    return {
        "scenarios": [_coc_scenario_list_item(scenario) for scenario in state.coc_scenarios.values()],
    }


def import_coc_scenario(state: APIState, scenario_data: dict) -> dict:
    try:
        scenario = coc_scenario_from_dict(scenario_data)
    except (KeyError, TypeError, ValueError) as exc:
        raise APIError(400, f"Invalid COC scenario: {exc}", "invalid_coc_scenario") from exc
    state.coc_scenarios[scenario.id] = scenario
    _persist_coc_scenario(state, scenario)
    return {
        "scenario_id": scenario.id,
        "scenario": coc_scenario_to_dict(scenario),
    }


def generate_coc_scenario(state: APIState, request_data: dict) -> dict:
    if state.ai_provider is None:
        raise APIError(503, "AI provider is not configured.", "ai_provider_not_configured")
    try:
        request = COCScenarioRequest(
            premise=str(request_data.get("premise", "")),
            investigator_occupation=str(request_data.get("investigator_occupation", "Antiquarian")),
            duration_hours=_int_body(request_data, "duration_hours", 2),
            tone=str(request_data.get("tone", "slow-burn cosmic horror")),
            location_count=_int_body(request_data, "location_count", 2),
            clue_count=_int_body(request_data, "clue_count", 4),
            npc_count=_int_body(request_data, "npc_count", 1),
        )
        max_attempts = _int_body(request_data, "max_attempts", 1)
        require_review_ok = bool(request_data.get("require_review_ok", False))
        model_text = generate_coc_scenario_text(
            request,
            state.ai_provider,
            max_attempts=max_attempts,
            require_review_ok=require_review_ok,
        )
        response = import_coc_scenario(state, json.loads(extract_json_object(model_text)))
    except RuntimeError as exc:
        raise APIError(502, str(exc), "ai_provider_error") from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise APIError(400, str(exc), "invalid_coc_generation_request") from exc
    response["metadata"] = {
        "premise": request.premise,
        "model_text_length": len(model_text),
        "require_review_ok": require_review_ok,
    }
    response["review"] = coc_review_to_dict(state.coc_scenarios[response["scenario_id"]])
    return response


def delete_campaign(state: APIState, campaign_id: str) -> dict:
    _campaign_or_404(state, campaign_id)
    del state.campaigns[campaign_id]
    _delete_persisted_campaign(state, campaign_id)
    return {"deleted": True, "campaign_id": campaign_id}


def campaign_state(state: APIState, campaign_id: str) -> dict:
    return campaign_to_dict(_campaign_or_404(state, campaign_id))


def campaign_log(state: APIState, campaign_id: str, limit: int = 50, visibility: str | None = None) -> dict:
    if limit < 1:
        raise APIError(400, "limit must be at least 1.", "invalid_limit")
    campaign = _campaign_or_404(state, campaign_id)
    selected_visibility = _parse_visibility(visibility)
    filtered_events = [
        event for event in campaign.session_log if selected_visibility is None or event.visibility == selected_visibility
    ]
    events = filtered_events[-limit:]
    return {
        "campaign_id": campaign.id,
        "visibility": None if selected_visibility is None else selected_visibility.value,
        "event_count": len(campaign.session_log),
        "filtered_count": len(filtered_events),
        "returned_count": len(events),
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
        "system_id": campaign.system_id,
        "tone": campaign.tone,
        "party_level": campaign.party_level,
        "current_location_id": campaign.current_location_id,
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
                "conditions": sorted(character.conditions),
                "death_saves": {
                    "successes": character.death_save_successes,
                    "failures": character.death_save_failures,
                },
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
        "coc_scenario_count": len(state.coc_scenarios),
        "features": {
            "rules_search": state.rules_corpus is not None,
            "ai_dm": state.ai_provider is not None,
            "persistent_state": state.state_dir is not None,
        },
    }


def create_coc_demo(state: APIState, scenario_name: str = "briar_house") -> dict:
    try:
        scenario = create_coc_demo_scenario(scenario_name)
    except ValueError as exc:
        raise APIError(400, str(exc), "unknown_coc_demo_scenario") from exc
    state.coc_scenarios[scenario.id] = scenario
    _persist_coc_scenario(state, scenario)
    return {
        "scenario_id": scenario.id,
        "demo_scenario": scenario_name,
        "available_demo_scenarios": coc_demo_scenario_names(),
        "scenario": coc_scenario_to_dict(scenario),
    }


def coc_summary(state: APIState, scenario_id: str) -> dict:
    scenario = _coc_scenario_or_404(state, scenario_id)
    investigator = scenario.investigator
    location = scenario.current_location()
    discovered = [clue for clue in scenario.clues if clue.discovered]
    partial = [
        clue for clue in scenario.clues if clue.partial_discovered and not clue.discovered
    ]
    return {
        "id": scenario.id,
        "title": scenario.title,
        "system": "Call of Cthulhu 7e",
        "system_id": "coc7e",
        "location": location.name,
        "location_id": scenario.current_location_id,
        "description": location.description,
        "exits": [
            {
                "name": name,
                "location_id": location_id,
                "available": _coc_exit_available(scenario, name),
                "requirements": dict(location.exit_requirements.get(name, {})),
            }
            for name, location_id in location.exits.items()
        ],
        "npcs": [
            {"id": npc.id, "name": npc.name, "description": npc.description}
            for npc in _visible_coc_npcs(scenario)
        ],
        "completed": scenario.completed,
        "completion_requirements": {key: list(value) for key, value in scenario.completion_requirements.items()},
        "completion_progress": _coc_completion_progress(scenario),
        "keeper_hint": coc_keeper_hint(scenario),
        "inventory": list(scenario.inventory),
        "investigator": {
            "name": investigator.name,
            "occupation": investigator.occupation,
            "current_hp": investigator.current_hp,
            "max_hp": investigator.max_hp,
            "current_mp": investigator.current_mp,
            "max_mp": investigator.max_mp,
            "current_sanity": investigator.current_sanity,
            "max_sanity": investigator.max_sanity,
            "luck": investigator.luck,
            "conditions": sorted(investigator.conditions),
        },
        "clue_count": len(scenario.clues),
        "discovered_clue_count": len(discovered),
        "partial_clue_count": len(partial),
        "discovered_clues": [
            {"id": clue.id, "title": clue.title, "text": clue.text}
            for clue in discovered
        ],
        "partial_clues": [
            {
                "id": clue.id,
                "title": clue.title,
                "text": clue.failure_text or "",
                "evidence": clue.failure_evidence,
                "push_attempted": clue.push_attempted,
                "luck_cost": _coc_luck_cost(clue),
            }
            for clue in partial
        ],
        "available_actions": _coc_available_actions(scenario),
        "session_event_count": len(scenario.session_log),
        "recent_events": list(scenario.session_log[-20:]),
    }


def run_coc_action(state: APIState, scenario_id: str, action: str, seed: int = 1) -> dict:
    if not action.strip():
        raise APIError(400, "Action cannot be empty.", "empty_action")
    scenario = _coc_scenario_or_404(state, scenario_id)
    runtime = COCRuntime(scenario, rng=random.Random(seed))
    keep_going = handle_coc_action(runtime, action)
    _persist_coc_scenario(state, scenario)
    return {
        "scenario_id": scenario.id,
        "keep_going": keep_going,
        "transcript": runtime.flush(),
        "scenario": coc_scenario_to_dict(scenario),
        "summary": coc_summary(state, scenario.id),
    }


def coc_player_card(state: APIState, scenario_id: str) -> dict:
    scenario = _coc_scenario_or_404(state, scenario_id)
    investigator = scenario.investigator
    discovered = [clue for clue in scenario.clues if clue.discovered]
    partial = [clue for clue in scenario.clues if clue.partial_discovered and not clue.discovered]
    return {
        "scenario_id": scenario.id,
        "title": scenario.title,
        "system_id": "coc7e",
        "completed": scenario.completed,
        "location": scenario.current_location().name,
        "investigator": {
            "name": investigator.name,
            "occupation": investigator.occupation,
            "hp": {"current": investigator.current_hp, "max": investigator.max_hp},
            "mp": {"current": investigator.current_mp, "max": investigator.max_mp},
            "sanity": {"current": investigator.current_sanity, "max": investigator.max_sanity},
            "luck": investigator.luck,
            "conditions": sorted(investigator.conditions),
            "skills": {name: investigator.skills[name] for name in sorted(investigator.skills)},
        },
        "inventory": list(scenario.inventory),
        "discovered_clues": [
            {"id": clue.id, "title": clue.title, "text": clue.text, "evidence": clue.evidence}
            for clue in discovered
        ],
        "partial_leads": [
            {"id": clue.id, "title": clue.title, "text": clue.failure_text or "", "evidence": clue.failure_evidence}
            for clue in partial
        ],
        "available_actions": _coc_player_actions(scenario),
    }


def coc_briefing(state: APIState, scenario_id: str) -> dict:
    return build_coc_briefing(_coc_scenario_or_404(state, scenario_id))


def coc_review(state: APIState, scenario_id: str) -> dict:
    return coc_review_to_dict(_coc_scenario_or_404(state, scenario_id))


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
    except RuntimeError as exc:
        raise APIError(502, str(exc), "ai_provider_error") from exc
    except ValueError as exc:
        raise APIError(400, str(exc), "invalid_dm_suggestion_request") from exc
    return {
        "campaign_id": campaign.id,
        "suggestion": suggestion.to_dict(include_prompt=include_prompt),
        "metadata": {
            "action": action,
            "rules_count": len(suggestion.rules),
            "used_rules": bool(suggestion.rules),
            "included_prompt": include_prompt,
        },
    }


def suggest_coc_keeper_turn(state: APIState, scenario_id: str, action: str, include_prompt: bool = False) -> dict:
    if state.ai_provider is None:
        raise APIError(503, "AI provider is not configured.", "ai_provider_not_configured")
    scenario = _coc_scenario_or_404(state, scenario_id)
    try:
        suggestion = generate_keeper_suggestion(scenario, action, state.ai_provider, include_prompt=include_prompt)
    except RuntimeError as exc:
        raise APIError(502, str(exc), "ai_provider_error") from exc
    except ValueError as exc:
        raise APIError(400, str(exc), "invalid_keeper_suggestion_request") from exc
    return {
        "scenario_id": scenario.id,
        "suggestion": suggestion.to_dict(include_prompt=include_prompt),
        "metadata": {
            "action": action,
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
    if method == "GET" and parts == ["coc"]:
        return list_coc_scenarios(state)
    if method == "POST" and parts == ["coc", "import"]:
        scenario = body.get("scenario")
        if not isinstance(scenario, dict):
            raise APIError(400, "Missing COC scenario object.", "missing_coc_scenario")
        return import_coc_scenario(state, scenario)
    if method == "POST" and parts == ["coc", "generate"]:
        return generate_coc_scenario(state, body)
    if method == "POST" and parts == ["campaigns", "import"]:
        adventure = body.get("adventure")
        if not isinstance(adventure, dict):
            raise APIError(400, "Missing adventure object.", "missing_adventure")
        return import_adventure(state, adventure)
    if method == "POST" and parts == ["campaigns", "demo"]:
        return create_demo_campaign(state)
    if method == "POST" and parts == ["campaigns", "demo-with-character"]:
        return create_playable_demo_campaign(state)
    if method == "GET" and parts == ["coc", "demo-options"]:
        return {"scenarios": coc_demo_scenario_names()}
    if method == "POST" and parts == ["coc", "demo"]:
        return create_coc_demo(state, str(body.get("scenario", "briar_house")))
    if method == "GET" and len(parts) == 3 and parts[0] == "coc" and parts[2] == "summary":
        return coc_summary(state, parts[1])
    if method == "GET" and len(parts) == 3 and parts[0] == "coc" and parts[2] == "player-card":
        return coc_player_card(state, parts[1])
    if method == "GET" and len(parts) == 3 and parts[0] == "coc" and parts[2] == "briefing":
        return coc_briefing(state, parts[1])
    if method == "GET" and len(parts) == 3 and parts[0] == "coc" and parts[2] == "review":
        return coc_review(state, parts[1])
    if method == "POST" and len(parts) == 3 and parts[0] == "coc" and parts[2] == "actions":
        action = str(body.get("action", ""))
        seed = _int_body(body, "seed", 1)
        return run_coc_action(state, parts[1], action, seed=seed)
    if method == "POST" and len(parts) == 3 and parts[0] == "coc" and parts[2] == "keeper-suggestion":
        action = str(body.get("action", ""))
        include_prompt = bool(body.get("include_prompt", False))
        return suggest_coc_keeper_turn(state, parts[1], action, include_prompt=include_prompt)
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
        return campaign_log(
            state,
            parts[1],
            limit=_int_query(query, "limit", 50),
            visibility=query.get("visibility"),
        )
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
        if path.name.startswith("coc_"):
            scenario = load_coc_scenario(path)
            state.coc_scenarios[scenario.id] = scenario
            continue
        campaign = load_campaign(path)
        state.campaigns[campaign.id] = campaign


def _campaign_or_404(state: APIState, campaign_id: str) -> Campaign:
    campaign = state.campaigns.get(campaign_id)
    if campaign is None:
        raise APIError(404, "Campaign not found.", "campaign_not_found")
    return campaign


def _coc_scenario_or_404(state: APIState, scenario_id: str) -> COCScenario:
    scenario = state.coc_scenarios.get(scenario_id)
    if scenario is None:
        raise APIError(404, "COC scenario not found.", "coc_scenario_not_found")
    return scenario


def _coc_scenario_list_item(scenario: COCScenario) -> dict:
    location = scenario.current_location()
    completion_counts = _coc_completion_counts(scenario)
    return {
        "id": scenario.id,
        "title": scenario.title,
        "system": "Call of Cthulhu 7e",
        "system_id": "coc7e",
        "location": location.name,
        "location_id": scenario.current_location_id,
        "completed": scenario.completed,
        "inventory_count": len(scenario.inventory),
        "npc_count": len(scenario.npcs),
        "investigator_name": scenario.investigator.name,
        "current_sanity": scenario.investigator.current_sanity,
        "max_sanity": scenario.investigator.max_sanity,
        "discovered_clue_count": sum(1 for clue in scenario.clues if clue.discovered),
        "partial_clue_count": sum(
            1 for clue in scenario.clues if clue.partial_discovered and not clue.discovered
        ),
        "clue_count": len(scenario.clues),
        "completion_required_count": completion_counts["required"],
        "completion_remaining_count": completion_counts["remaining"],
        "session_event_count": len(scenario.session_log),
    }


def _campaign_location_name(campaign: Campaign) -> str | None:
    if campaign.current_location_id is None:
        return None
    location = campaign.locations.get(campaign.current_location_id)
    return None if location is None else location.name


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


def _persist_coc_scenario(state: APIState, scenario: COCScenario) -> None:
    if state.state_dir is None:
        return
    state.state_dir.mkdir(parents=True, exist_ok=True)
    save_coc_scenario(scenario, state.state_dir / f"{scenario.id}.json")


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
    if value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise APIError(400, f"{key} must be an integer.", "invalid_integer") from exc


def _parse_visibility(value: str | None) -> Visibility | None:
    if value is None or value == "":
        return None
    normalized = value.lower().replace("-", "_")
    try:
        return Visibility(normalized)
    except ValueError as exc:
        raise APIError(400, "visibility must be public or dm_only.", "invalid_visibility") from exc


def _active_combat_summary(campaign: Campaign) -> dict | None:
    combat = campaign.active_combat
    if combat is None:
        return None
    return {
        "encounter_id": combat.get("encounter_id"),
        "round": combat.get("round", 1),
        "turn": combat.get("turn"),
        "monster_action_strategy": combat.get("monster_action_strategy", _current_monster_action_strategy(combat)),
        "last_automatic_action": combat.get("last_automatic_action", ""),
        "morale_hint": combat.get("morale_hint", ""),
        "combatant_count": len(combat.get("initiative", [])),
        "initiative": [
            {
                "name": entry.get("name"),
                "initiative_total": entry.get("initiative_total", 0),
                "armor_class": entry.get("armor_class"),
                "current_hp": entry.get("current_hp"),
                "is_player": entry.get("is_player", False),
                "defeated": _combatant_defeated(entry),
                "conditions": _combatant_conditions(campaign, entry),
                "death_saves": _combatant_death_saves(campaign, entry),
                "action_strategy": entry.get("action_strategy"),
            }
            for entry in combat.get("initiative", [])
        ],
        "current_resources": combat.get("resources", {}).get(combat.get("turn"), {}),
        "targetable_enemies": _targetable_combatant_names(combat, allies=False),
        "targetable_allies": _targetable_combatant_names(combat, allies=True),
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


def _current_monster_action_strategy(combat: dict) -> str:
    turn = combat.get("turn")
    current = next((entry for entry in combat.get("initiative", []) if entry.get("name") == turn), None)
    if current is None or current.get("is_player") is not False:
        return "default_attack"
    return str(current.get("action_strategy") or "default_attack")


def _available_actions(campaign: Campaign, active_combat: dict | None) -> list[str]:
    actions = ["look", "inspect", "talk", "quests", "log"]
    location = campaign.locations.get(campaign.current_location_id or "")
    if location is not None:
        actions.extend(f"go {campaign.locations[location_id].name.lower()}" for location_id in location.connected_location_ids if location_id in campaign.locations)
        for npc in campaign.npcs.values():
            if npc.location_id != location.id:
                continue
            actions.append(f"talk {npc.name.lower()}")
            name_alias = npc.name.split()[0].lower() if npc.name.split() else ""
            if name_alias:
                actions.append(f"talk {name_alias}")
            if npc.role:
                actions.append(f"talk {npc.role.lower()}")
        if any(encounter.location_id == location.id and not encounter.resolved for encounter in campaign.encounters.values()):
            actions.append("fight")
    if active_combat is not None:
        actions.extend([
            "combat",
            "attack",
            "dash",
            "disengage",
            "dodge",
            "grapple",
            "shove",
            "escape grapple",
            "condition",
            "clear condition",
            "end turn",
            "flee",
            "surrender",
            "accept surrender",
            "resolve encounter",
        ])
        turn = str(active_combat.get("turn") or "")
        current = next((entry for entry in active_combat.get("initiative", []) if entry.get("name") == turn), None)
        known_spells = _known_spell_action_names(campaign, turn)
        actions.extend(f"cast {spell}" for spell in known_spells)
        actions.extend(_death_save_actions(campaign))
        for combatant in active_combat.get("initiative", []):
            name = str(combatant.get("name") or "")
            if not name or int(combatant.get("current_hp") or 0) <= 0:
                continue
            same_side = current is not None and bool(combatant.get("is_player")) == bool(current.get("is_player"))
            if name != turn and not same_side:
                actions.append(f"attack {name.lower()}")
                actions.append(f"grapple {name.lower()}")
                actions.append(f"shove {name.lower()}")
                for spell in known_spells:
                    if spell in {"sacred flame", "guiding bolt", "magic missile"}:
                        actions.append(f"cast {spell} {name.lower()}")
            if same_side:
                for spell in known_spells:
                    if spell in {"cure wounds", "healing word"}:
                        actions.append(f"cast {spell} {name.lower()}")
    return list(dict.fromkeys(actions))


def _coc_completion_counts(scenario: COCScenario) -> dict:
    progress = _coc_completion_progress(scenario)
    required = sum(len(group["required"]) for group in progress.values())
    remaining = sum(len(group["remaining"]) for group in progress.values())
    return {"required": required, "remaining": remaining}

def _coc_completion_progress(scenario: COCScenario) -> dict:
    requirements = scenario.completion_requirements
    discovered_ids = {clue.id for clue in scenario.clues if clue.discovered}
    inventory = set(scenario.inventory)
    talked_npc_ids = set(scenario.talked_npc_ids)
    return {
        "required_clue_ids": _requirement_progress(requirements.get("required_clue_ids", []), discovered_ids),
        "required_evidence": _requirement_progress(requirements.get("required_evidence", []), inventory),
        "required_location_ids": _requirement_progress(
            requirements.get("required_location_ids", []),
            {scenario.current_location_id} if scenario.current_location_id else set(),
        ),
        "required_npc_ids": _requirement_progress(requirements.get("required_npc_ids", []), talked_npc_ids),
    }


def _requirement_progress(required: list[str], current: set[str]) -> dict:
    remaining = [value for value in required if value not in current]
    return {
        "required": list(required),
        "remaining": remaining,
        "complete": not remaining,
    }


def _coc_player_actions(scenario: COCScenario) -> list[str]:
    actions = []
    for action in _coc_available_actions(scenario):
        if action.startswith("keeper note "):
            continue
        actions.append(action)
    return actions


def _coc_available_actions(scenario: COCScenario) -> list[str]:
    actions = ["look", "status", "skills", "recap", "progress", "hint", "note <text>", "keeper note <text>", "san check 0/1d4", "take damage 1d4", "spend luck 5", "recover luck 1d10", "sanity", "clues", "inventory", "conclude", "quit"]
    if scenario.investigator.current_hp < scenario.investigator.max_hp:
        actions.append("first aid")
        actions.append("heal 1d3")
    location = scenario.current_location()
    actions.extend(f"go {exit_name}" for exit_name in sorted(location.exits))
    for npc in _visible_coc_npcs(scenario):
        actions.append(f"talk {npc.name.lower()}")
        actions.append(f"talk {npc.id.replace('_', ' ')}")
    for clue in scenario.clues:
        if clue.discovered:
            continue
        if scenario.current_location_id and clue.location_id not in {None, scenario.current_location_id}:
            continue
        clue_title = clue.title.lower()
        clue_id = clue.id.replace("_", " ")
        actions.append(f"inspect {clue_title}")
        actions.append(f"inspect {clue_id}")
        actions.append(f"search {clue_title}")
        actions.append(f"search {clue_id}")
        if clue.skill:
            actions.append(f"inspect {clue_title} bonus")
            actions.append(f"inspect {clue_title} penalty")
            actions.append(f"search {clue_title} bonus")
            actions.append(f"search {clue_title} penalty")
        clue_words = f"{clue_id} {clue_title}"
        if any(word in clue_words for word in ("journal", "diary", "letter", "book", "note")):
            actions.append(f"read {clue_title}")
            actions.append(f"read {clue_id}")
        if any(word in clue_words for word in ("voice", "voices", "whisper", "well", "sound")):
            actions.append(f"listen {clue_title}")
            actions.append(f"listen {clue_id}")
        if clue.skill:
            actions.append(f"check {clue.skill}")
            actions.append(f"check {clue.skill} bonus")
            actions.append(f"check {clue.skill} penalty")
        if clue.partial_discovered and not clue.push_attempted:
            actions.append(f"push {clue.title.lower()}")
            actions.append(f"push {clue.id.replace('_', ' ')}")
        if _coc_luck_cost(clue) is not None:
            actions.append(f"spend luck {clue.title.lower()}")
            actions.append(f"spend luck {clue.id.replace('_', ' ')}")
    return list(dict.fromkeys(actions))


def _coc_luck_cost(clue) -> int | None:
    if clue.discovered:
        return None
    if clue.last_check_total is None or clue.last_required_total is None:
        return None
    if clue.last_check_level == "fumble":
        return None
    cost = clue.last_check_total - clue.last_required_total
    if cost <= 0:
        return None
    return cost

def _coc_exit_available(scenario: COCScenario, exit_name: str) -> bool:
    requirement = scenario.current_location().exit_requirements.get(exit_name, {})
    return _coc_requirement_met(scenario, requirement)


def _coc_requirement_met(scenario: COCScenario, requirement: dict) -> bool:
    required_clue_ids = set(requirement.get("required_clue_ids", []))
    if required_clue_ids:
        discovered_ids = {clue.id for clue in scenario.clues if clue.discovered}
        if not required_clue_ids.issubset(discovered_ids):
            return False
    required_evidence = set(requirement.get("required_evidence", []))
    if required_evidence and not required_evidence.issubset(set(scenario.inventory)):
        return False
    return True


def _visible_coc_npcs(scenario: COCScenario) -> list:
    if not scenario.current_location_id:
        return scenario.npcs
    return [npc for npc in scenario.npcs if npc.location_id in {None, scenario.current_location_id}]


def _death_save_actions(campaign: Campaign) -> list[str]:
    actions: list[str] = []
    for character in campaign.characters.values():
        if character.current_hp > 0 or "dead" in character.conditions:
            continue
        if "stable" not in character.conditions:
            actions.append(f"death save {character.name.lower()}")
            actions.append(f"stabilize {character.name.lower()}")
    return actions


def _combatant_conditions(campaign: Campaign, entry: dict) -> list[str]:
    conditions = {str(condition) for condition in entry.get("conditions", [])}
    character = campaign.characters.get(str(entry.get("name") or ""))
    if character is not None:
        conditions.update(character.conditions)
    return sorted(conditions)


def _combatant_death_saves(campaign: Campaign, entry: dict) -> dict | None:
    character = campaign.characters.get(str(entry.get("name") or ""))
    if character is None:
        return None
    return {
        "successes": character.death_save_successes,
        "failures": character.death_save_failures,
    }


def _combatant_defeated(entry: dict) -> bool:
    return "current_hp" in entry and int(entry.get("current_hp") or 0) <= 0


def _known_spell_action_names(campaign: Campaign, character_name: str) -> list[str]:
    character = campaign.characters.get(character_name)
    if character is None or character.spellcasting is None:
        return []
    return [spell.name.lower() for spell in character.spellcasting.known_spells]


def _targetable_combatant_names(combat: dict, allies: bool) -> list[str]:
    turn = combat.get("turn")
    current = next((entry for entry in combat.get("initiative", []) if entry.get("name") == turn), None)
    if current is None or "is_player" not in current:
        return []
    current_side = bool(current.get("is_player"))
    return [
        str(entry.get("name"))
        for entry in combat.get("initiative", [])
        if entry.get("name")
        and entry.get("name") != turn
        and not _combatant_defeated(entry)
        and (bool(entry.get("is_player")) == current_side) == allies
    ]


def _event_message(event) -> dict:
    return {
        "id": event.id,
        "actor": event.actor,
        "content": event.content,
        "visibility": event.visibility.value,
        "created_at": event.created_at.isoformat(),
    }
