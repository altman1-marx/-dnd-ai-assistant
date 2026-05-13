from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from .core.dnd5e import RollMode
from .core.skills import skill_ability


REQUIRED_TOP_LEVEL_KEYS = (
    "campaign",
    "start_location_id",
    "final_location_id",
    "locations",
    "npcs",
    "clues",
    "quests",
    "encounters",
    "endings",
    "opening",
)
REQUIRED_CAMPAIGN_KEYS = ("title", "party_level", "tone")
REQUIRED_LOCATION_KEYS = ("id", "name", "public_description")
REQUIRED_NPC_KEYS = ("id", "name", "role", "public_description", "location_id")
REQUIRED_CLUE_KEYS = ("id", "title", "public_text", "location_id")
REQUIRED_QUEST_KEYS = ("id", "title", "summary")
REQUIRED_ENCOUNTER_KEYS = ("id", "title", "location_id", "difficulty")
REQUIRED_MONSTER_KEYS = ("name", "armor_class", "max_hp")
REQUIRED_ENDING_KEYS = ("id", "title", "summary")
REQUIRED_OPENING_KEYS = ("player_text", "dm_notes")
ABILITY_NAMES = ("str", "dex", "con", "int", "wis", "cha")
SUPPORTED_RUNTIME_HANDLERS = {"look", "inspect", "talk", "encounter", "move", "log", "help", "quit"}


@dataclass(frozen=True)
class AdventureDefinition:
    raw: dict

    @property
    def campaign(self) -> dict:
        return self.raw["campaign"]

    @property
    def locations(self) -> list[dict]:
        return self.raw["locations"]

    @property
    def npcs(self) -> list[dict]:
        return self.raw["npcs"]

    @property
    def clues(self) -> list[dict]:
        return self.raw["clues"]

    @property
    def quests(self) -> list[dict]:
        return self.raw["quests"]

    @property
    def encounters(self) -> list[dict]:
        return self.raw["encounters"]

    @property
    def endings(self) -> list[dict]:
        return self.raw["endings"]

    @property
    def opening(self) -> dict:
        return self.raw["opening"]

    @property
    def start_location_id(self) -> str:
        return self.raw["start_location_id"]

    @property
    def final_location_id(self) -> str:
        return self.raw["final_location_id"]


def load_adventure(path: str | Path) -> AdventureDefinition:
    with Path(path).open("r", encoding="utf-8") as f:
        adventure = AdventureDefinition(json.load(f))
    validate_adventure(adventure)
    return adventure


def validate_adventure(adventure: AdventureDefinition) -> list[str]:
    errors: list[str] = []
    raw = adventure.raw
    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key not in raw:
            errors.append(f"Missing top-level key: {key}")
    if errors:
        raise ValueError("; ".join(errors))

    _require_keys("campaign", adventure.campaign, REQUIRED_CAMPAIGN_KEYS, errors)
    _require_keys("opening", adventure.opening, REQUIRED_OPENING_KEYS, errors)
    _validate_required_items("locations", adventure.locations, REQUIRED_LOCATION_KEYS, errors)
    _validate_required_items("npcs", adventure.npcs, REQUIRED_NPC_KEYS, errors)
    _validate_required_items("clues", adventure.clues, REQUIRED_CLUE_KEYS, errors)
    _validate_required_items("quests", adventure.quests, REQUIRED_QUEST_KEYS, errors)
    _validate_required_items("encounters", adventure.encounters, REQUIRED_ENCOUNTER_KEYS, errors)
    _validate_encounter_monsters(adventure.encounters, errors)
    _validate_required_items("endings", adventure.endings, REQUIRED_ENDING_KEYS, errors)
    if errors:
        raise ValueError("; ".join(errors))

    location_ids = _collect_unique_ids("locations", adventure.locations, errors)
    _collect_unique_ids("npcs", adventure.npcs, errors)
    clue_ids = _collect_unique_ids("clues", adventure.clues, errors)
    _collect_unique_ids("quests", adventure.quests, errors)
    _collect_unique_ids("encounters", adventure.encounters, errors)
    _collect_unique_ids("endings", adventure.endings, errors)

    if not adventure.locations:
        errors.append("Adventure must include at least one location.")
    if not adventure.clues:
        errors.append("Adventure must include at least one clue.")
    if not adventure.quests:
        errors.append("Adventure must include at least one quest.")
    if not adventure.endings:
        errors.append("Adventure must include at least one ending.")

    _validate_location_reference("start_location_id", adventure.start_location_id, location_ids, errors)
    _validate_location_reference("final_location_id", adventure.final_location_id, location_ids, errors)
    for location in adventure.locations:
        _validate_required_clues(
            f"locations.{location.get('id', '<missing>')}.requires_clue_ids",
            location.get("requires_clue_ids", []),
            clue_ids,
            errors,
        )
    for npc in adventure.npcs:
        _validate_location_reference(f"npcs.{npc.get('id', '<missing>')}.location_id", npc.get("location_id"), location_ids, errors)
    for clue in adventure.clues:
        _validate_location_reference(
            f"clues.{clue.get('id', '<missing>')}.location_id", clue.get("location_id"), location_ids, errors
        )
        _validate_optional_check(f"clues.{clue.get('id', '<missing>')}.check", clue.get("check"), errors)
    for encounter in adventure.encounters:
        _validate_location_reference(
            f"encounters.{encounter.get('id', '<missing>')}.location_id",
            encounter.get("location_id"),
            location_ids,
            errors,
        )
    _validate_runtime_actions(adventure.raw.get("runtime_actions"), errors)

    if location_ids:
        _validate_connections(adventure, location_ids, errors)

    if errors:
        raise ValueError("; ".join(errors))
    return []


def create_adventure_template(title: str) -> dict:
    return {
        "campaign": {
            "title": title,
            "party_level": 1,
            "tone": "heroic fantasy mystery",
            "public_hook": "A village asks for help after strange lights appear near the old road.",
            "dm_secret": "The lights are a lure created by a trapped fey creature.",
        },
        "start_location_id": "loc_village_square",
        "final_location_id": "loc_moonlit_glade",
        "locations": [
            {
                "id": "loc_village_square",
                "name": "Village Square",
                "public_description": "A quiet square where anxious locals gather around a dry fountain.",
                "dm_notes": "The fountain stones point toward the old road when moonlight hits them.",
                "connections": ["loc_old_road"],
            },
            {
                "id": "loc_old_road",
                "name": "Old Road",
                "public_description": "A mossy path under leaning trees and pale lantern-like lights.",
                "dm_notes": "The lights retreat if threatened but approach music or kindness.",
                "connections": ["loc_village_square", "loc_moonlit_glade"],
            },
            {
                "id": "loc_moonlit_glade",
                "name": "Moonlit Glade",
                "public_description": "A silver clearing where roots coil around a cracked stone arch.",
                "dm_notes": "The arch is the source of the fey disturbance.",
                "connections": ["loc_old_road"],
                "requires_clue_ids": ["clue_moon_ash"],
            },
        ],
        "npcs": [
            {
                "id": "npc_mayor_elin",
                "name": "Mayor Elin",
                "role": "worried quest giver",
                "public_description": "A tired mayor clutching a list of missing travelers.",
                "dm_secret": "She once promised the fey protection and forgot the bargain.",
                "dialogue": "Please find the missing travelers before the lights take anyone else.",
                "location_id": "loc_village_square",
            }
        ],
        "clues": [
            {
                "id": "clue_moon_ash",
                "title": "Moonlit Ash",
                "public_text": "Silver ash clings to footprints heading toward the old road.",
                "dm_secret": "The ash falls from the cracked arch in the glade.",
                "location_id": "loc_village_square",
                "check": {"skill": "survival", "dc": 10, "mode": "normal", "label": "Survival"},
            }
        ],
        "quests": [
            {
                "id": "quest_find_travelers",
                "title": "Find the Missing Travelers",
                "summary": "Follow the strange lights and discover why travelers vanish near the old road.",
            }
        ],
        "encounters": [
            {
                "id": "enc_lantern_sprites",
                "title": "Lantern Sprites",
                "location_id": "loc_old_road",
                "difficulty": "easy",
                "trigger": "The party follows the lights without caution.",
                "reward": "A sprite offers a moon-silver charm if spared.",
                "monsters": [],
            }
        ],
        "endings": [
            {
                "id": "ending_bargain_mended",
                "title": "The Bargain Mended",
                "summary": "The party repairs the broken promise and the missing travelers return.",
            }
        ],
        "opening": {
            "player_text": "The village square is hushed as pale lights flicker beyond the old road.",
            "dm_notes": "Start with Mayor Elin asking the party to investigate before moonrise.",
        },
    }


def write_adventure_template(path: str | Path, title: str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(create_adventure_template(title), ensure_ascii=False, indent=2), encoding="utf-8")


def _require_keys(name: str, item: dict, keys: tuple[str, ...], errors: list[str]) -> None:
    for key in keys:
        if key not in item:
            errors.append(f"Missing {name} key: {key}")


def _validate_required_items(name: str, items: list[dict], keys: tuple[str, ...], errors: list[str]) -> None:
    if not isinstance(items, list):
        errors.append(f"{name} must be a list.")
        return
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{name}[{index}] must be an object.")
            continue
        _require_keys(f"{name}[{index}]", item, keys, errors)


def _validate_encounter_monsters(encounters: list[dict], errors: list[str]) -> None:
    if not isinstance(encounters, list):
        return
    for encounter_index, encounter in enumerate(encounters):
        if not isinstance(encounter, dict):
            continue
        monsters = encounter.get("monsters", [])
        if not isinstance(monsters, list):
            errors.append(f"encounters[{encounter_index}].monsters must be a list.")
            continue
        for monster_index, monster in enumerate(monsters):
            if not isinstance(monster, dict):
                errors.append(f"encounters[{encounter_index}].monsters[{monster_index}] must be an object.")
                continue
            _require_keys(
                f"encounters[{encounter_index}].monsters[{monster_index}]",
                monster,
                REQUIRED_MONSTER_KEYS,
                errors,
            )
            _validate_optional_monster_abilities(
                f"encounters[{encounter_index}].monsters[{monster_index}]",
                monster,
                errors,
            )


def _collect_unique_ids(name: str, items: list[dict], errors: list[str]) -> set[str]:
    ids: set[str] = set()
    for item in items:
        item_id = item.get("id") if isinstance(item, dict) else None
        if item_id is None:
            continue
        if item_id in ids:
            errors.append(f"Duplicate {name} id: {item_id}")
        ids.add(item_id)
    return ids


def _validate_location_reference(name: str, location_id: object, location_ids: set[str], errors: list[str]) -> None:
    if not isinstance(location_id, str):
        errors.append(f"{name} must be a location id string.")
        return
    if location_id not in location_ids:
        errors.append(f"Unknown location id for {name}: {location_id}")


def _validate_required_clues(name: str, clue_ids: object, known_clue_ids: set[str], errors: list[str]) -> None:
    if not isinstance(clue_ids, list):
        errors.append(f"{name} must be a list.")
        return
    for clue_id in clue_ids:
        if not isinstance(clue_id, str):
            errors.append(f"{name} entries must be clue id strings.")
        elif clue_id not in known_clue_ids:
            errors.append(f"Unknown clue id for {name}: {clue_id}")


def _validate_runtime_actions(actions: object, errors: list[str]) -> None:
    if actions is None:
        return
    if not isinstance(actions, dict):
        errors.append("runtime_actions must be an object.")
        return
    for action_name, action in actions.items():
        if not isinstance(action, dict):
            errors.append(f"runtime_actions.{action_name} must be an object.")
            continue
        aliases = action.get("aliases", [])
        if not isinstance(aliases, list) or not all(isinstance(alias, str) for alias in aliases):
            errors.append(f"runtime_actions.{action_name}.aliases must be a list of strings.")
        handler = action.get("handler", action_name)
        if handler not in SUPPORTED_RUNTIME_HANDLERS:
            errors.append(f"runtime_actions.{action_name}.handler is unsupported: {handler}")


def _validate_optional_check(name: str, check: object, errors: list[str]) -> None:
    if check is None:
        return
    if not isinstance(check, dict):
        errors.append(f"{name} must be an object.")
        return
    for key in ("skill", "dc"):
        if key not in check:
            errors.append(f"Missing {name} key: {key}")
    if "skill" in check:
        try:
            skill_ability(check["skill"])
        except ValueError as exc:
            errors.append(str(exc))
    if "dc" in check and (not isinstance(check["dc"], int) or check["dc"] < 0):
        errors.append(f"{name}.dc must be a non-negative integer.")
    if "mode" in check:
        try:
            RollMode(check["mode"])
        except ValueError:
            errors.append(f"{name}.mode must be normal, advantage, or disadvantage.")


def _validate_optional_monster_abilities(name: str, monster: dict, errors: list[str]) -> None:
    ability_scores = monster.get("ability_scores")
    if ability_scores is not None:
        if not isinstance(ability_scores, dict):
            errors.append(f"{name}.ability_scores must be an object.")
        else:
            missing = set(ABILITY_NAMES) - set(ability_scores)
            if missing:
                errors.append(f"{name}.ability_scores missing: {', '.join(sorted(missing))}")
            for ability, score in ability_scores.items():
                if ability not in ABILITY_NAMES:
                    errors.append(f"{name}.ability_scores has unknown ability: {ability}")
                elif not isinstance(score, int) or score < 1 or score > 30:
                    errors.append(f"{name}.ability_scores.{ability} must be an integer from 1 to 30.")

    saving_throws = monster.get("saving_throw_proficiencies")
    if saving_throws is not None:
        if not isinstance(saving_throws, list):
            errors.append(f"{name}.saving_throw_proficiencies must be a list.")
        else:
            unknown = sorted(save for save in saving_throws if save not in ABILITY_NAMES)
            if unknown:
                errors.append(f"{name}.saving_throw_proficiencies has unknown abilities: {', '.join(unknown)}")

    proficiency = monster.get("proficiency_bonus")
    if proficiency is not None and (not isinstance(proficiency, int) or proficiency < 0):
        errors.append(f"{name}.proficiency_bonus must be a non-negative integer.")

    for key in ("damage_resistances", "damage_vulnerabilities", "damage_immunities"):
        value = monster.get(key)
        if value is not None and not isinstance(value, list):
            errors.append(f"{name}.{key} must be a list.")


def _validate_connections(adventure: AdventureDefinition, location_ids: set[str], errors: list[str]) -> None:
    adjacency: dict[str, set[str]] = {location_id: set() for location_id in location_ids}
    for location in adventure.locations:
        location_id = location["id"]
        for connected_id in location.get("connections", []):
            if connected_id not in location_ids:
                errors.append(f"Unknown connected location id for {location_id}: {connected_id}")
                continue
            adjacency[location_id].add(connected_id)
            adjacency[connected_id].add(location_id)

    reachable = _reachable_locations(adventure.start_location_id, adjacency)
    missing = location_ids - reachable
    if missing:
        errors.append(f"Unreachable locations from start: {', '.join(sorted(missing))}")
    if adventure.final_location_id not in reachable:
        errors.append(f"Final location is unreachable from start: {adventure.final_location_id}")


def _reachable_locations(start_id: str, adjacency: dict[str, set[str]]) -> set[str]:
    if start_id not in adjacency:
        return set()
    queue: deque[str] = deque([start_id])
    visited: set[str] = set()
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        queue.extend(adjacency[current] - visited)
    return visited
