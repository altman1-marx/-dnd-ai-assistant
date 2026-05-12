from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Spell:
    name: str
    level: int
    school: str = ""
    casting_time: str = "1 action"
    range_text: str = ""
    components: str = ""
    duration: str = ""
    concentration: bool = False
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Spell name cannot be empty.")
        if self.level < 0 or self.level > 9:
            raise ValueError("Spell level must be between 0 and 9.")


@dataclass
class Spellcasting:
    ability: str
    slots_by_level: dict[int, int] = field(default_factory=dict)
    expended_slots_by_level: dict[int, int] = field(default_factory=dict)
    known_spells: list[Spell] = field(default_factory=list)
    prepared_spell_names: set[str] = field(default_factory=set)
    concentration_spell_name: str | None = None

    def __post_init__(self) -> None:
        self.ability = self.ability.lower()
        for level, slots in self.slots_by_level.items():
            self._validate_slot_level(level)
            if slots < 0:
                raise ValueError("Spell slots cannot be negative.")
        for level, expended in self.expended_slots_by_level.items():
            self._validate_slot_level(level)
            if expended < 0:
                raise ValueError("Expended spell slots cannot be negative.")
            if expended > self.slots_by_level.get(level, 0):
                raise ValueError("Expended spell slots cannot exceed total slots.")

    @staticmethod
    def _validate_slot_level(level: int) -> None:
        if level < 1 or level > 9:
            raise ValueError("Spell slot level must be between 1 and 9.")

    def available_slots(self, level: int) -> int:
        self._validate_slot_level(level)
        return self.slots_by_level.get(level, 0) - self.expended_slots_by_level.get(level, 0)

    def expend_slot(self, level: int) -> None:
        if self.available_slots(level) <= 0:
            raise ValueError(f"No level {level} spell slots remaining.")
        self.expended_slots_by_level[level] = self.expended_slots_by_level.get(level, 0) + 1

    def recover_slots(self, level: int | None = None) -> None:
        if level is None:
            self.expended_slots_by_level.clear()
            return
        self._validate_slot_level(level)
        self.expended_slots_by_level[level] = 0
