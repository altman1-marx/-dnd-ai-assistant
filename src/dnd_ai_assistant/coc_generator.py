from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .adventure_generator import build_repair_prompt, extract_json_object
from .ai_provider import AIProvider
from .coc_runtime import COCScenario
from .coc_serialization import coc_scenario_from_dict, coc_scenario_to_dict


@dataclass(frozen=True)
class COCScenarioRequest:
    premise: str
    investigator_occupation: str = "Antiquarian"
    duration_hours: int = 2
    tone: str = "slow-burn cosmic horror"
    location_count: int = 2
    clue_count: int = 4
    npc_count: int = 1

    def __post_init__(self) -> None:
        if not self.premise.strip():
            raise ValueError("Premise cannot be empty.")
        if not self.investigator_occupation.strip():
            raise ValueError("Investigator occupation cannot be empty.")
        if self.duration_hours < 1:
            raise ValueError("Duration must be at least 1 hour.")
        if self.location_count < 1:
            raise ValueError("Location count must be at least 1.")
        if self.clue_count < 1:
            raise ValueError("Clue count must be at least 1.")
        if self.npc_count < 0:
            raise ValueError("NPC count cannot be negative.")


def build_coc_scenario_prompt(request: COCScenarioRequest) -> str:
    return "\n".join(
        [
            "You are designing a short Call of Cthulhu 7e investigation for an AI tabletop assistant.",
            "Return only valid JSON. Do not wrap it in markdown.",
            "The JSON must match this shape:",
            _schema_instructions(),
            "",
            "Design constraints:",
            f"- Premise: {request.premise}",
            f"- Investigator occupation: {request.investigator_occupation}",
            f"- Target duration: {request.duration_hours} hours",
            f"- Tone: {request.tone}",
            f"- Location count: {request.location_count}",
            f"- Clue count: {request.clue_count}",
            f"- NPC count: {request.npc_count}",
            "",
            "Quality requirements:",
            "- Write for investigation, dread, evidence, and player choice rather than combat.",
            "- Include connected locations with exits that reference existing location ids.",
            "- Put at least one clue in each important location.",
            "- Give clues stable ids, optional skill gates, optional evidence names, and modest SAN loss.",
            "- Keep investigator characteristics between 1 and 99 and skills between 0 and 100.",
            "- Set current_location_id to the first playable location.",
            "- Keep all location_id references valid.",
        ]
    )


def coc_scenario_from_model_text(text: str) -> COCScenario:
    return coc_scenario_from_dict(json.loads(extract_json_object(text)))


def write_coc_scenario_from_model_text(text: str, path: str | Path) -> COCScenario:
    scenario = coc_scenario_from_model_text(text)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(coc_scenario_to_dict(scenario), ensure_ascii=False, indent=2), encoding="utf-8")
    return scenario


def generate_coc_scenario_text(
    request: COCScenarioRequest,
    provider: AIProvider,
    max_attempts: int = 1,
) -> str:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1.")
    prompt = build_coc_scenario_prompt(request)
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        model_text = provider.generate_text(prompt)
        try:
            coc_scenario_from_model_text(model_text)
            return model_text
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            if attempt == max_attempts - 1:
                break
            prompt = build_repair_prompt(model_text, str(exc))
    raise ValueError(f"Model did not produce a valid COC scenario after {max_attempts} attempt(s): {last_error}")


def generate_coc_scenario_file(
    request: COCScenarioRequest,
    provider: AIProvider,
    output_path: str | Path,
    max_attempts: int = 1,
) -> COCScenario:
    model_text = generate_coc_scenario_text(request, provider, max_attempts=max_attempts)
    return write_coc_scenario_from_model_text(model_text, output_path)


def _schema_instructions() -> str:
    return json.dumps(
        {
            "title": "string",
            "location": "current location name",
            "description": "current location description",
            "investigator": {
                "name": "string",
                "occupation": "string",
                "characteristics": {"str": 45, "con": 55, "siz": 60, "dex": 50, "app": 55, "int": 70, "pow": 60, "edu": 75},
                "skills": {"library use": 55, "spot hidden": 45, "occult": 40},
                "luck": 50,
            },
            "locations": [
                {"id": "study", "name": "Briar House Study", "description": "string", "exits": {"cellar": "cellar"}}
            ],
            "current_location_id": "study",
            "npcs": [
                {
                    "id": "mrs_ember",
                    "name": "Mrs. Ember",
                    "description": "string",
                    "location_id": "study",
                    "dialogue": ["short line"],
                }
            ],
            "clues": [
                {
                    "id": "portrait_truth",
                    "title": "Scratched Portrait",
                    "text": "string",
                    "location_id": "study",
                    "evidence": "Torn portrait canvas",
                    "skill": None,
                    "difficulty": "regular|hard|extreme",
                    "sanity_loss": 2,
                }
            ],
            "inventory": [],
            "ending_text": "string",
        },
        ensure_ascii=False,
        indent=2,
    )
