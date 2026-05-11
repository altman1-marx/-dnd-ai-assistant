from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SCENE_PATH = Path(__file__).parent / "scenes" / "old_chapel.json"

REQUIRED_TOP_LEVEL_KEYS = ("campaign", "hero", "location", "npc", "clue", "quest", "text", "checks")
REQUIRED_TEXT_KEYS = (
    "intro",
    "look",
    "inspect_first",
    "inspect_success",
    "inspect_failure",
    "inspect_repeat",
    "stairway_locked",
    "stairway_open",
    "stairway_repeat",
    "unknown",
    "pause",
)
REQUIRED_CAMPAIGN_KEYS = ("title", "party_level", "tone")
REQUIRED_HERO_KEYS = (
    "name",
    "player_name",
    "class_name",
    "level",
    "ancestry",
    "ability_scores",
    "armor_class",
    "max_hp",
    "current_hp",
)
REQUIRED_ABILITIES = ("str", "dex", "con", "int", "wis", "cha")


@dataclass(frozen=True)
class SceneDefinition:
    raw: dict

    @property
    def campaign(self) -> dict:
        return self.raw["campaign"]

    @property
    def hero(self) -> dict:
        return self.raw["hero"]

    @property
    def location(self) -> dict:
        return self.raw["location"]

    @property
    def npc(self) -> dict:
        return self.raw["npc"]

    @property
    def clue(self) -> dict:
        return self.raw["clue"]

    @property
    def quest(self) -> dict:
        return self.raw["quest"]

    @property
    def encounter(self) -> dict | None:
        return self.raw.get("encounter")

    @property
    def text(self) -> dict:
        return self.raw["text"]

    @property
    def checks(self) -> dict:
        return self.raw["checks"]

    @property
    def actions(self) -> dict:
        return self.raw.get("actions", {})


def load_scene(path: str | Path | None = None) -> SceneDefinition:
    scene_path = Path(path) if path is not None else DEFAULT_SCENE_PATH
    with scene_path.open("r", encoding="utf-8") as f:
        scene = SceneDefinition(json.load(f))
    validate_scene(scene)
    return scene


def validate_scene(scene: SceneDefinition) -> list[str]:
    errors: list[str] = []
    raw = scene.raw
    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key not in raw:
            errors.append(f"Missing top-level key: {key}")
    if errors:
        raise ValueError("; ".join(errors))

    for key in REQUIRED_CAMPAIGN_KEYS:
        if key not in scene.campaign:
            errors.append(f"Missing campaign key: {key}")
    for key in REQUIRED_HERO_KEYS:
        if key not in scene.hero:
            errors.append(f"Missing hero key: {key}")
    for ability in REQUIRED_ABILITIES:
        if ability not in scene.hero.get("ability_scores", {}):
            errors.append(f"Missing hero ability score: {ability}")
    for key in REQUIRED_TEXT_KEYS:
        if key not in scene.text:
            errors.append(f"Missing text key: {key}")
    if "inspect_rope" not in scene.checks:
        errors.append("Missing checks.inspect_rope")
    else:
        check = scene.checks["inspect_rope"]
        for key in ("ability", "dc", "mode", "label"):
            if key not in check:
                errors.append(f"Missing checks.inspect_rope key: {key}")

    if errors:
        raise ValueError("; ".join(errors))
    return []


def validate_scene_file(path: str | Path | None = None) -> SceneDefinition:
    return load_scene(path)


def create_scene_template(title: str) -> dict:
    return {
        "campaign": {
            "title": title,
            "party_level": 1,
            "tone": "heroic fantasy",
            "public_lore": "Write the player-facing premise here.",
            "dm_secrets": "Write hidden truths and future reveals here.",
        },
        "hero": {
            "name": "Example Hero",
            "player_name": "Player",
            "class_name": "Fighter",
            "level": 1,
            "ancestry": "Human",
            "ability_scores": {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 8},
            "armor_class": 16,
            "max_hp": 12,
            "current_hp": 12,
            "skill_proficiencies": ["athletics", "perception"],
            "saving_throw_proficiencies": ["str", "con"],
        },
        "location": {
            "name": "Starting Location",
            "public_description": "Describe what the players immediately perceive.",
            "dm_notes": "Describe hidden details, traps, or secret connections.",
        },
        "npc": {
            "name": "Quest Giver",
            "role": "local contact",
            "public_description": "Describe what the players can observe.",
            "dm_secret": "Describe what this NPC hides.",
        },
        "clue": {
            "title": "First Clue",
            "public_text": "Describe the clue once discovered.",
            "dm_secret": "Explain what the clue really means.",
        },
        "quest": {
            "title": "Opening Objective",
            "summary": "Describe the immediate goal for the party.",
        },
        "encounter": {
            "title": "First Encounter",
            "difficulty": "easy",
            "trigger": "Describe what starts the encounter.",
            "reward": "Describe the reward.",
            "monsters": [
                {
                    "name": "Training Goblin",
                    "armor_class": 13,
                    "max_hp": 7,
                    "current_hp": 7,
                    "initiative_modifier": 2,
                    "attack_bonus": 4,
                    "damage": "1d6+2",
                }
            ],
        },
        "text": {
            "intro": [
                "{hero} arrives at the starting location.",
                "Something is clearly wrong here.",
                "Try actions like 'look around', 'inspect rope', 'open stairway', 'log', or 'quit'.",
            ],
            "look": "Describe the room when the player looks around.",
            "inspect_first": "Describe the first inspection result.",
            "inspect_success": "Describe the extra information found on success.",
            "inspect_failure": "Describe the partial information found on failure.",
            "inspect_repeat": "Describe what happens if the player repeats the inspection.",
            "stairway_locked": "Describe why the next path is locked before the clue is found.",
            "stairway_open": "Describe the next path opening.",
            "stairway_repeat": "Describe the already-open path.",
            "unknown": "The current prototype does not know how to resolve that yet.",
            "pause": "The scene pauses here.",
        },
        "checks": {
            "inspect_rope": {
                "ability": "wis",
                "proficient": True,
                "dc": 12,
                "mode": "normal",
                "label": "Perception",
            }
        },
        "actions": {
            "look": ["look", "around"],
            "inspect": ["inspect", "rope", "bell"],
            "open": ["open", "stair", "door"],
            "log": ["log"],
            "help": ["help", "?"],
            "quit": ["quit", "exit"],
        },
    }


def write_scene_template(path: str | Path, title: str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scene = create_scene_template(title)
    output_path.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")
