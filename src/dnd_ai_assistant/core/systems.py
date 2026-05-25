from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GameSystem:
    id: str
    label: str
    family: str
    default_tone: str


DND5E = GameSystem(
    id="dnd5e",
    label="DND 5e",
    family="fantasy",
    default_tone="heroic fantasy",
)
COC7E = GameSystem(
    id="coc7e",
    label="Call of Cthulhu 7e",
    family="horror investigation",
    default_tone="cosmic horror",
)

SUPPORTED_GAME_SYSTEMS = {
    DND5E.id: DND5E,
    COC7E.id: COC7E,
}
SYSTEM_ALIASES = {
    "d&d": DND5E.id,
    "d&d 5e": DND5E.id,
    "dnd": DND5E.id,
    "dnd 5e": DND5E.id,
    "dnd5e": DND5E.id,
    "dungeons and dragons 5e": DND5E.id,
    "5e": DND5E.id,
    "call of cthulhu": COC7E.id,
    "call of cthulhu 7e": COC7E.id,
    "coc": COC7E.id,
    "coc 7e": COC7E.id,
    "coc7e": COC7E.id,
}


def normalize_game_system(value: str | None) -> GameSystem:
    if value is None or not value.strip():
        return DND5E
    normalized = " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split())
    system_id = SYSTEM_ALIASES.get(normalized, normalized)
    if system_id in SUPPORTED_GAME_SYSTEMS:
        return SUPPORTED_GAME_SYSTEMS[system_id]
    raise ValueError(f"Unsupported game system: {value}")

