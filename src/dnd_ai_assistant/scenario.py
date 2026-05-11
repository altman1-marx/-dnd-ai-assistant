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
    def text(self) -> dict:
        return self.raw["text"]

    @property
    def checks(self) -> dict:
        return self.raw["checks"]


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
