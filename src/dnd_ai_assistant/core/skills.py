from __future__ import annotations


SKILL_ABILITIES: dict[str, str] = {
    "acrobatics": "dex",
    "animal_handling": "wis",
    "arcana": "int",
    "athletics": "str",
    "deception": "cha",
    "history": "int",
    "insight": "wis",
    "intimidation": "cha",
    "investigation": "int",
    "medicine": "wis",
    "nature": "int",
    "perception": "wis",
    "performance": "cha",
    "persuasion": "cha",
    "religion": "int",
    "sleight_of_hand": "dex",
    "stealth": "dex",
    "survival": "wis",
}

SKILL_LABELS: dict[str, str] = {
    "acrobatics": "Acrobatics",
    "animal_handling": "Animal Handling",
    "arcana": "Arcana",
    "athletics": "Athletics",
    "deception": "Deception",
    "history": "History",
    "insight": "Insight",
    "intimidation": "Intimidation",
    "investigation": "Investigation",
    "medicine": "Medicine",
    "nature": "Nature",
    "perception": "Perception",
    "performance": "Performance",
    "persuasion": "Persuasion",
    "religion": "Religion",
    "sleight_of_hand": "Sleight of Hand",
    "stealth": "Stealth",
    "survival": "Survival",
}


def normalize_skill_name(skill_name: str) -> str:
    return skill_name.strip().lower().replace(" ", "_").replace("-", "_")


def skill_ability(skill_name: str) -> str:
    normalized = normalize_skill_name(skill_name)
    try:
        return SKILL_ABILITIES[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported DND 5e skill: {skill_name}") from exc


def skill_label(skill_name: str) -> str:
    normalized = normalize_skill_name(skill_name)
    return SKILL_LABELS.get(normalized, skill_name)
