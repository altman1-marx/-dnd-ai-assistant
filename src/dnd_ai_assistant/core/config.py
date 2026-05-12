from __future__ import annotations

from dataclasses import dataclass, field


DEFAULT_DC_BY_DIFFICULTY: dict[str, int] = {
    "very_easy": 5,
    "easy": 10,
    "medium": 15,
    "hard": 20,
    "very_hard": 25,
    "nearly_impossible": 30,
}


@dataclass(frozen=True)
class RulesConfig:
    dc_by_difficulty: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_DC_BY_DIFFICULTY))
    default_movement_speed: int = 30

    def dc(self, difficulty: str) -> int:
        key = difficulty.strip().lower().replace(" ", "_").replace("-", "_")
        try:
            return self.dc_by_difficulty[key]
        except KeyError as exc:
            raise ValueError(f"Unknown difficulty: {difficulty}") from exc


DEFAULT_RULES_CONFIG = RulesConfig()
