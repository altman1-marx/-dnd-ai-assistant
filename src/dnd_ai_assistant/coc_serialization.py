from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from .coc_runtime import COCClue, COCLocation, COCNPC, COCScenario
from .core.coc7e import COC_CHARACTERISTICS, Investigator


class COCScenarioValidationError(ValueError):
    pass


def investigator_to_dict(investigator: Investigator) -> dict:
    return {
        "name": investigator.name,
        "occupation": investigator.occupation,
        "characteristics": dict(investigator.characteristics),
        "skills": dict(investigator.skills),
        "max_hp": investigator.max_hp,
        "current_hp": investigator.current_hp,
        "max_mp": investigator.max_mp,
        "current_mp": investigator.current_mp,
        "max_sanity": investigator.max_sanity,
        "current_sanity": investigator.current_sanity,
        "luck": investigator.luck,
        "conditions": sorted(investigator.conditions),
    }


def investigator_from_dict(data: dict) -> Investigator:
    return Investigator(
        name=data["name"],
        occupation=data["occupation"],
        characteristics=dict(data["characteristics"]),
        skills=dict(data.get("skills", {})),
        max_hp=data.get("max_hp"),
        current_hp=data.get("current_hp"),
        max_mp=data.get("max_mp"),
        current_mp=data.get("current_mp"),
        max_sanity=data.get("max_sanity"),
        current_sanity=data.get("current_sanity"),
        luck=data.get("luck", 50),
        conditions=set(data.get("conditions", [])),
    )


def coc_scenario_to_dict(scenario: COCScenario) -> dict:
    return {
        "id": scenario.id,
        "title": scenario.title,
        "system": "Call of Cthulhu 7e",
        "location": scenario.location,
        "description": scenario.description,
        "investigator": investigator_to_dict(scenario.investigator),
        "clues": [
            {
                "id": clue.id,
                "title": clue.title,
                "text": clue.text,
                "location_id": clue.location_id,
                "evidence": clue.evidence,
                "skill": clue.skill,
                "difficulty": clue.difficulty,
                "sanity_loss": clue.sanity_loss,
                "failure_text": clue.failure_text,
                "failure_evidence": clue.failure_evidence,
                "failure_sanity_loss": clue.failure_sanity_loss,
                "discovered": clue.discovered,
                "partial_discovered": clue.partial_discovered,
            }
            for clue in scenario.clues
        ],
        "locations": [
            {
                "id": location.id,
                "name": location.name,
                "description": location.description,
                "exits": dict(location.exits),
                "exit_requirements": dict(location.exit_requirements),
            }
            for location in scenario.locations.values()
        ],
        "npcs": [
            {
                "id": npc.id,
                "name": npc.name,
                "description": npc.description,
                "location_id": npc.location_id,
                "dialogue": list(npc.dialogue),
            }
            for npc in scenario.npcs
        ],
        "current_location_id": scenario.current_location_id,
        "inventory": list(scenario.inventory),
        "completion_requirements": {key: list(value) for key, value in scenario.completion_requirements.items()},
        "talked_npc_ids": sorted(scenario.talked_npc_ids),
        "ending_text": scenario.ending_text,
        "completed": scenario.completed,
    }


def coc_scenario_from_dict(data: dict) -> COCScenario:
    validate_coc_scenario_data(data)
    return COCScenario(
        title=data["title"],
        location=data["location"],
        description=data["description"],
        investigator=investigator_from_dict(data["investigator"]),
        clues=[
            COCClue(
                id=clue["id"],
                title=clue["title"],
                text=clue["text"],
                location_id=clue.get("location_id"),
                evidence=clue.get("evidence"),
                skill=clue.get("skill"),
                difficulty=clue.get("difficulty", "regular"),
                sanity_loss=clue.get("sanity_loss", 0),
                failure_text=clue.get("failure_text"),
                failure_evidence=clue.get("failure_evidence"),
                failure_sanity_loss=clue.get("failure_sanity_loss", 0),
                discovered=clue.get("discovered", False),
                partial_discovered=clue.get("partial_discovered", False),
            )
            for clue in data.get("clues", [])
        ],
        npcs=[
            COCNPC(
                id=npc["id"],
                name=npc["name"],
                description=npc["description"],
                location_id=npc.get("location_id"),
                dialogue=list(npc.get("dialogue", [])),
            )
            for npc in data.get("npcs", [])
        ],
        locations={
            location["id"]: COCLocation(
                id=location["id"],
                name=location["name"],
                description=location["description"],
                exits=dict(location.get("exits", {})),
                exit_requirements=dict(location.get("exit_requirements", {})),
            )
            for location in data.get("locations", [])
        },
        current_location_id=data.get("current_location_id"),
        inventory=list(data.get("inventory", [])),
        completion_requirements={key: list(value) for key, value in data.get("completion_requirements", {}).items()},
        talked_npc_ids=set(data.get("talked_npc_ids", [])),
        ending_text=data.get("ending_text", ""),
        completed=data.get("completed", False),
        id=data.get("id", None) or f"coc_{uuid4().hex[:12]}",
    )


def save_coc_scenario(scenario: COCScenario, path: str | Path) -> None:
    Path(path).write_text(json.dumps(coc_scenario_to_dict(scenario), indent=2), encoding="utf-8")


def load_coc_scenario(path: str | Path) -> COCScenario:
    return coc_scenario_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def validate_coc_scenario_data(data: dict) -> None:
    if not isinstance(data, dict):
        raise COCScenarioValidationError("scenario must be an object")
    _require_nonempty_string(data, "title")
    _require_nonempty_string(data, "location")
    _require_nonempty_string(data, "description")
    if "id" in data and data["id"] is not None:
        _require_nonempty_string(data, "id")
    if "ending_text" in data and not isinstance(data["ending_text"], str):
        raise COCScenarioValidationError("ending_text must be a string")
    if "completed" in data and not isinstance(data["completed"], bool):
        raise COCScenarioValidationError("completed must be a boolean")
    talked_npc_ids = data.get("talked_npc_ids", [])
    if not isinstance(talked_npc_ids, list):
        raise COCScenarioValidationError("talked_npc_ids must be a list")
    for npc_id in talked_npc_ids:
        if not isinstance(npc_id, str) or not npc_id.strip():
            raise COCScenarioValidationError("talked_npc_ids must contain non-empty strings")
    inventory = data.get("inventory", [])
    if not isinstance(inventory, list):
        raise COCScenarioValidationError("inventory must be a list")
    for item in inventory:
        if not isinstance(item, str) or not item.strip():
            raise COCScenarioValidationError("inventory must contain non-empty strings")
    _validate_investigator_data(_require_object(data, "investigator"))
    location_ids = _validate_locations_data(data.get("locations", []))
    current_location_id = data.get("current_location_id")
    if current_location_id is not None:
        if not isinstance(current_location_id, str) or not current_location_id.strip():
            raise COCScenarioValidationError("current_location_id must be a non-empty string")
        if current_location_id not in location_ids:
            raise COCScenarioValidationError(f"current_location_id references unknown location: {current_location_id}")
    clues = data.get("clues", [])
    if not isinstance(clues, list):
        raise COCScenarioValidationError("clues must be a list")
    if not clues:
        raise COCScenarioValidationError("clues must contain at least one clue")
    seen_ids: set[str] = set()
    for index, clue in enumerate(clues):
        _validate_clue_data(clue, index, seen_ids, location_ids)
    npc_ids = _validate_npcs_data(data.get("npcs", []), location_ids)
    evidence_names = {clue.get("evidence") for clue in clues if isinstance(clue, dict) and clue.get("evidence")}
    _validate_completion_requirements(
        data.get("completion_requirements", {}),
        clue_ids=seen_ids,
        evidence_names=evidence_names,
        location_ids=location_ids,
        npc_ids=npc_ids,
    )



def _validate_completion_requirements(
    requirements: object,
    clue_ids: set[str],
    evidence_names: set[str],
    location_ids: set[str],
    npc_ids: set[str],
) -> None:
    if not isinstance(requirements, dict):
        raise COCScenarioValidationError("completion_requirements must be an object")
    known_keys = {
        "required_clue_ids": clue_ids,
        "required_evidence": evidence_names,
        "required_location_ids": location_ids,
        "required_npc_ids": npc_ids,
    }
    for key, known_values in known_keys.items():
        values = requirements.get(key, [])
        if not isinstance(values, list):
            raise COCScenarioValidationError(f"completion_requirements.{key} must be a list")
        for value in values:
            if not isinstance(value, str) or not value.strip():
                raise COCScenarioValidationError(f"completion_requirements.{key} must contain non-empty strings")
            if value not in known_values:
                raise COCScenarioValidationError(
                    f"completion_requirements.{key} references unknown value: {value}"
                )


def _validate_investigator_data(data: dict) -> None:
    _require_nonempty_string(data, "name", prefix="investigator")
    _require_nonempty_string(data, "occupation", prefix="investigator")
    characteristics = _require_object(data, "characteristics", prefix="investigator")
    for characteristic in COC_CHARACTERISTICS:
        value = characteristics.get(characteristic)
        if not isinstance(value, int) or isinstance(value, bool):
            raise COCScenarioValidationError(f"investigator.characteristics.{characteristic} must be an integer")
        if value < 1 or value > 99:
            raise COCScenarioValidationError(
                f"investigator.characteristics.{characteristic} must be between 1 and 99"
            )
    skills = data.get("skills", {})
    if not isinstance(skills, dict):
        raise COCScenarioValidationError("investigator.skills must be an object")
    for skill_name, value in skills.items():
        if not isinstance(skill_name, str) or not skill_name.strip():
            raise COCScenarioValidationError("investigator.skills keys must be non-empty strings")
        _validate_int_range(value, f"investigator.skills.{skill_name}", 0, 100)
    _validate_optional_int_range(data, "max_hp", 1, 999, prefix="investigator")
    _validate_optional_int_range(data, "current_hp", 0, 999, prefix="investigator")
    _validate_optional_int_range(data, "max_mp", 0, 999, prefix="investigator")
    _validate_optional_int_range(data, "current_mp", 0, 999, prefix="investigator")
    _validate_optional_int_range(data, "max_sanity", 0, 99, prefix="investigator")
    _validate_optional_int_range(data, "current_sanity", 0, 99, prefix="investigator")
    _validate_optional_int_range(data, "luck", 0, 100, prefix="investigator")
    conditions = data.get("conditions", [])
    if not isinstance(conditions, list):
        raise COCScenarioValidationError("investigator.conditions must be a list")
    for condition in conditions:
        if not isinstance(condition, str) or not condition.strip():
            raise COCScenarioValidationError("investigator.conditions must contain non-empty strings")


def _validate_locations_data(locations: object) -> set[str]:
    if not isinstance(locations, list):
        raise COCScenarioValidationError("locations must be a list")
    seen_ids: set[str] = set()
    for index, location in enumerate(locations):
        if not isinstance(location, dict):
            raise COCScenarioValidationError(f"locations[{index}] must be an object")
        location_id = _require_nonempty_string(location, "id", prefix=f"locations[{index}]")
        if location_id in seen_ids:
            raise COCScenarioValidationError(f"duplicate location id: {location_id}")
        seen_ids.add(location_id)
        _require_nonempty_string(location, "name", prefix=f"locations[{index}]")
        _require_nonempty_string(location, "description", prefix=f"locations[{index}]")
        exits = location.get("exits", {})
        if not isinstance(exits, dict):
            raise COCScenarioValidationError(f"locations[{index}].exits must be an object")
        for exit_name, destination_id in exits.items():
            if not isinstance(exit_name, str) or not exit_name.strip():
                raise COCScenarioValidationError(f"locations[{index}].exits keys must be non-empty strings")
            if not isinstance(destination_id, str) or not destination_id.strip():
                raise COCScenarioValidationError(f"locations[{index}].exits.{exit_name} must be a non-empty string")
        requirements = location.get("exit_requirements", {})
        if not isinstance(requirements, dict):
            raise COCScenarioValidationError(f"locations[{index}].exit_requirements must be an object")
        for exit_name, requirement in requirements.items():
            if exit_name not in exits:
                raise COCScenarioValidationError(
                    f"locations[{index}].exit_requirements.{exit_name} must reference an existing exit"
                )
            _validate_exit_requirement(requirement, f"locations[{index}].exit_requirements.{exit_name}")
    for index, location in enumerate(locations):
        for exit_name, destination_id in location.get("exits", {}).items():
            if destination_id not in seen_ids:
                raise COCScenarioValidationError(
                    f"locations[{index}].exits.{exit_name} references unknown location: {destination_id}"
                )
    return seen_ids


def _validate_exit_requirement(requirement: object, path: str) -> None:
    if not isinstance(requirement, dict):
        raise COCScenarioValidationError(f"{path} must be an object")
    for key in ("required_clue_ids", "required_evidence"):
        values = requirement.get(key, [])
        if not isinstance(values, list):
            raise COCScenarioValidationError(f"{path}.{key} must be a list")
        for value in values:
            if not isinstance(value, str) or not value.strip():
                raise COCScenarioValidationError(f"{path}.{key} must contain non-empty strings")
    if "message" in requirement and not isinstance(requirement["message"], str):
        raise COCScenarioValidationError(f"{path}.message must be a string")


def _validate_clue_data(data: object, index: int, seen_ids: set[str], location_ids: set[str]) -> None:
    if not isinstance(data, dict):
        raise COCScenarioValidationError(f"clues[{index}] must be an object")
    clue_id = _require_nonempty_string(data, "id", prefix=f"clues[{index}]")
    if clue_id in seen_ids:
        raise COCScenarioValidationError(f"duplicate clue id: {clue_id}")
    seen_ids.add(clue_id)
    _require_nonempty_string(data, "title", prefix=f"clues[{index}]")
    _require_nonempty_string(data, "text", prefix=f"clues[{index}]")
    if data.get("skill") is not None:
        _require_nonempty_string(data, "skill", prefix=f"clues[{index}]")
    if data.get("evidence") is not None:
        _require_nonempty_string(data, "evidence", prefix=f"clues[{index}]")
    if data.get("failure_text") is not None:
        _require_nonempty_string(data, "failure_text", prefix=f"clues[{index}]")
    if data.get("failure_evidence") is not None:
        _require_nonempty_string(data, "failure_evidence", prefix=f"clues[{index}]")
    location_id = data.get("location_id")
    if location_id is not None:
        if not isinstance(location_id, str) or not location_id.strip():
            raise COCScenarioValidationError(f"clues[{index}].location_id must be a non-empty string")
        if location_ids and location_id not in location_ids:
            raise COCScenarioValidationError(f"clues[{index}].location_id references unknown location: {location_id}")
    difficulty = data.get("difficulty", "regular")
    if difficulty not in {"regular", "hard", "extreme"}:
        raise COCScenarioValidationError(f"clues[{index}].difficulty must be regular, hard, or extreme")
    _validate_optional_int_range(data, "sanity_loss", 0, 99, prefix=f"clues[{index}]")
    _validate_optional_int_range(data, "failure_sanity_loss", 0, 99, prefix=f"clues[{index}]")
    if "discovered" in data and not isinstance(data["discovered"], bool):
        raise COCScenarioValidationError(f"clues[{index}].discovered must be a boolean")
    if "partial_discovered" in data and not isinstance(data["partial_discovered"], bool):
        raise COCScenarioValidationError(f"clues[{index}].partial_discovered must be a boolean")


def _validate_npcs_data(npcs: object, location_ids: set[str]) -> set[str]:
    if not isinstance(npcs, list):
        raise COCScenarioValidationError("npcs must be a list")
    seen_ids: set[str] = set()
    for index, npc in enumerate(npcs):
        if not isinstance(npc, dict):
            raise COCScenarioValidationError(f"npcs[{index}] must be an object")
        npc_id = _require_nonempty_string(npc, "id", prefix=f"npcs[{index}]")
        if npc_id in seen_ids:
            raise COCScenarioValidationError(f"duplicate npc id: {npc_id}")
        seen_ids.add(npc_id)
        _require_nonempty_string(npc, "name", prefix=f"npcs[{index}]")
        _require_nonempty_string(npc, "description", prefix=f"npcs[{index}]")
        location_id = npc.get("location_id")
        if location_id is not None:
            if not isinstance(location_id, str) or not location_id.strip():
                raise COCScenarioValidationError(f"npcs[{index}].location_id must be a non-empty string")
            if location_ids and location_id not in location_ids:
                raise COCScenarioValidationError(f"npcs[{index}].location_id references unknown location: {location_id}")
        dialogue = npc.get("dialogue", [])
        if not isinstance(dialogue, list):
            raise COCScenarioValidationError(f"npcs[{index}].dialogue must be a list")
        for line in dialogue:
            if not isinstance(line, str) or not line.strip():
                raise COCScenarioValidationError(f"npcs[{index}].dialogue must contain non-empty strings")
    return seen_ids


def _require_nonempty_string(data: dict, key: str, prefix: str | None = None) -> str:
    value = data.get(key)
    path = f"{prefix}.{key}" if prefix else key
    if not isinstance(value, str) or not value.strip():
        raise COCScenarioValidationError(f"{path} must be a non-empty string")
    return value


def _require_object(data: dict, key: str, prefix: str | None = None) -> dict:
    value = data.get(key)
    path = f"{prefix}.{key}" if prefix else key
    if not isinstance(value, dict):
        raise COCScenarioValidationError(f"{path} must be an object")
    return value


def _validate_optional_int_range(data: dict, key: str, minimum: int, maximum: int, prefix: str | None = None) -> None:
    if key not in data or data[key] is None:
        return
    path = f"{prefix}.{key}" if prefix else key
    _validate_int_range(data[key], path, minimum, maximum)


def _validate_int_range(value: object, path: str, minimum: int, maximum: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise COCScenarioValidationError(f"{path} must be an integer")
    if value < minimum or value > maximum:
        raise COCScenarioValidationError(f"{path} must be between {minimum} and {maximum}")
