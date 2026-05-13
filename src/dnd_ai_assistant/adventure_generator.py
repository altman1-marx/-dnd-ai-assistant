from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .adventure import AdventureDefinition, validate_adventure
from .adventure_importer import campaign_from_adventure
from .adventure_review import AdventureReview, review_adventure
from .ai_provider import AIProvider
from .core.campaign import Campaign
from .core.serialization import save_campaign


@dataclass(frozen=True)
class AdventureRequest:
    premise: str
    party_level: int = 1
    player_count: int = 4
    duration_hours: int = 2
    tone: str = "heroic fantasy mystery"
    combat_ratio: str = "medium"
    puzzle_ratio: str = "medium"

    def __post_init__(self) -> None:
        if not self.premise.strip():
            raise ValueError("Premise cannot be empty.")
        if self.party_level < 1 or self.party_level > 20:
            raise ValueError("Party level must be between 1 and 20.")
        if self.player_count < 1:
            raise ValueError("Player count must be positive.")
        if self.duration_hours < 1:
            raise ValueError("Duration must be at least 1 hour.")


def build_adventure_prompt(request: AdventureRequest) -> str:
    return "\n".join(
        [
            "You are designing a short DND 5e adventure for an AI tabletop assistant.",
            "Return only valid JSON. Do not wrap it in markdown.",
            "The JSON must match this shape:",
            _schema_instructions(),
            "",
            "Design constraints:",
            f"- Premise: {request.premise}",
            f"- Party level: {request.party_level}",
            f"- Player count: {request.player_count}",
            f"- Target duration: {request.duration_hours} hours",
            f"- Tone: {request.tone}",
            f"- Combat ratio: {request.combat_ratio}",
            f"- Puzzle ratio: {request.puzzle_ratio}",
            "",
            "Quality requirements:",
            "- Include 3 to 6 connected locations.",
            "- Include a clear start_location_id and final_location_id.",
            "- Include at least one clue, one quest, one encounter, and one ending.",
            "- Keep player-facing text spoiler-free.",
            "- Put secrets and twists only in dm_secret, dm_notes, or opening.dm_notes.",
            "- Use clue.check for clues that should require a DND 5e skill check; omit it for obvious clues.",
            "- Use stable ids like loc_old_chapel, npc_mayor_voss, clue_black_ash.",
            "- Make all location references point to existing location ids.",
        ]
    )


def adventure_from_model_text(text: str) -> AdventureDefinition:
    raw = json.loads(extract_json_object(text))
    adventure = AdventureDefinition(raw)
    validate_adventure(adventure)
    return adventure


def write_adventure_from_model_text(text: str, path: str | Path) -> AdventureDefinition:
    adventure = adventure_from_model_text(text)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(adventure.raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return adventure


def write_campaign_from_model_text(
    text: str,
    adventure_path: str | Path,
    campaign_path: str | Path,
) -> tuple[AdventureDefinition, Campaign]:
    adventure = write_adventure_from_model_text(text, adventure_path)
    campaign = campaign_from_adventure(adventure)
    save_campaign(campaign, campaign_path)
    return adventure, campaign


def generate_adventure_files(
    request: AdventureRequest,
    provider: AIProvider,
    adventure_path: str | Path,
    campaign_path: str | Path,
    max_attempts: int = 1,
) -> tuple[AdventureDefinition, Campaign, AdventureReview]:
    model_text = generate_adventure_text(request, provider, max_attempts=max_attempts)
    adventure, campaign = write_campaign_from_model_text(model_text, adventure_path, campaign_path)
    review = review_adventure(adventure)
    return adventure, campaign, review


def generate_adventure_text(request: AdventureRequest, provider: AIProvider, max_attempts: int = 1) -> str:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1.")

    prompt = build_adventure_prompt(request)
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        model_text = provider.generate_text(prompt)
        try:
            adventure_from_model_text(model_text)
            return model_text
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            if attempt == max_attempts - 1:
                break
            prompt = build_repair_prompt(model_text, str(exc))

    raise ValueError(f"Model did not produce a valid adventure after {max_attempts} attempt(s): {last_error}")


def build_repair_prompt(model_text: str, error_message: str) -> str:
    return "\n".join(
        [
            "The previous response was not a valid adventure JSON document.",
            "Return only a corrected complete JSON object. Do not wrap it in markdown.",
            "Validation error:",
            error_message,
            "",
            "Previous response:",
            model_text,
        ]
    )


def extract_json_object(text: str) -> str:
    stripped = _strip_markdown_fence(text.strip())
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model output.")
    return stripped[start : end + 1]


def _strip_markdown_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if len(lines) >= 3 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


def _schema_instructions() -> str:
    return json.dumps(
        {
            "campaign": {
                "title": "string",
                "party_level": "integer",
                "tone": "string",
                "public_hook": "string",
                "dm_secret": "string",
            },
            "start_location_id": "string",
            "final_location_id": "string",
            "locations": [
                {
                    "id": "string",
                    "name": "string",
                    "public_description": "string",
                    "dm_notes": "string",
                    "connections": ["location_id"],
                    "requires_clue_ids": ["clue_id"],
                }
            ],
            "npcs": [
                {
                    "id": "string",
                    "name": "string",
                    "role": "string",
                    "public_description": "string",
                    "dm_secret": "string",
                    "dialogue": "short in-character line",
                    "location_id": "location_id",
                }
            ],
            "clues": [
                {
                    "id": "string",
                    "title": "string",
                    "public_text": "string",
                    "dm_secret": "string",
                    "location_id": "location_id",
                    "check": {
                        "skill": "skill name",
                        "dc": "integer",
                        "mode": "normal|advantage|disadvantage",
                        "label": "string",
                    },
                }
            ],
            "quests": [{"id": "string", "title": "string", "summary": "string"}],
            "encounters": [
                {
                    "id": "string",
                    "title": "string",
                    "location_id": "location_id",
                    "difficulty": "easy|medium|hard",
                    "trigger": "string",
                    "reward": "string",
                    "monsters": [
                        {
                            "name": "string",
                            "armor_class": "integer",
                            "max_hp": "integer",
                            "ability_scores": {
                                "str": 10,
                                "dex": 10,
                                "con": 10,
                                "int": 10,
                                "wis": 10,
                                "cha": 10,
                            },
                            "saving_throw_proficiencies": ["dex"],
                            "proficiency_bonus": "integer",
                            "damage_resistances": ["fire"],
                            "damage_vulnerabilities": ["radiant"],
                            "damage_immunities": ["poison"],
                            "attack_bonus": "integer",
                            "damage": "dice expression",
                            "damage_type": (
                                "slashing|piercing|bludgeoning|fire|cold|radiant|necrotic|poison"
                            ),
                        }
                    ],
                }
            ],
            "endings": [{"id": "string", "title": "string", "summary": "string"}],
            "opening": {"player_text": "string", "dm_notes": "string"},
            "runtime_actions": {
                "look": {"aliases": ["look", "look around"], "handler": "look"},
                "inspect": {"aliases": ["inspect", "search"], "handler": "inspect"},
                "talk": {"aliases": ["talk", "speak", "ask"], "handler": "talk"},
                "encounter": {"aliases": ["fight", "start encounter", "encounter"], "handler": "encounter"},
                "move": {"aliases": ["go", "move", "travel"], "handler": "move"},
                "log": {"aliases": ["log"], "handler": "log"},
                "help": {"aliases": ["help", "?"], "handler": "help"},
                "quit": {"aliases": ["quit", "exit"], "handler": "quit"},
            },
        },
        ensure_ascii=False,
        indent=2,
    )
