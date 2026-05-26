from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from .coc_runtime import COCClue, COCScenario
from .core.coc7e import Investigator


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
                "skill": clue.skill,
                "difficulty": clue.difficulty,
                "sanity_loss": clue.sanity_loss,
                "discovered": clue.discovered,
            }
            for clue in scenario.clues
        ],
        "ending_text": scenario.ending_text,
        "completed": scenario.completed,
    }


def coc_scenario_from_dict(data: dict) -> COCScenario:
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
                skill=clue.get("skill"),
                difficulty=clue.get("difficulty", "regular"),
                sanity_loss=clue.get("sanity_loss", 0),
                discovered=clue.get("discovered", False),
            )
            for clue in data.get("clues", [])
        ],
        ending_text=data.get("ending_text", ""),
        completed=data.get("completed", False),
        id=data.get("id", None) or f"coc_{uuid4().hex[:12]}",
    )


def save_coc_scenario(scenario: COCScenario, path: str | Path) -> None:
    Path(path).write_text(json.dumps(coc_scenario_to_dict(scenario), indent=2), encoding="utf-8")


def load_coc_scenario(path: str | Path) -> COCScenario:
    return coc_scenario_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
