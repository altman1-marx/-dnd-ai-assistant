from __future__ import annotations

from dataclasses import dataclass, field

from .dnd5e import ability_modifier, proficiency_bonus
from .skills import normalize_skill_name, skill_ability
from .spells import Spellcasting


ABILITY_NAMES = ("str", "dex", "con", "int", "wis", "cha")


@dataclass
class Character:
    name: str
    player_name: str
    class_name: str
    level: int
    ancestry: str
    ability_scores: dict[str, int]
    armor_class: int
    max_hp: int
    current_hp: int
    skill_proficiencies: set[str] = field(default_factory=set)
    saving_throw_proficiencies: set[str] = field(default_factory=set)
    conditions: set[str] = field(default_factory=set)
    inventory: list[str] = field(default_factory=list)
    spellcasting: Spellcasting | None = None

    def __post_init__(self) -> None:
        missing = set(ABILITY_NAMES) - set(self.ability_scores)
        if missing:
            raise ValueError(f"Missing ability scores: {', '.join(sorted(missing))}")
        proficiency_bonus(self.level)
        for ability in ABILITY_NAMES:
            ability_modifier(self.ability_scores[ability])
        if self.armor_class <= 0:
            raise ValueError("Armor class must be positive.")
        if self.current_hp > self.max_hp:
            raise ValueError("Current HP cannot exceed max HP.")
        if self.current_hp < 0:
            raise ValueError("Current HP cannot be negative.")
        if self.max_hp <= 0:
            raise ValueError("Max HP must be positive.")
        self.skill_proficiencies = {normalize_skill_name(skill) for skill in self.skill_proficiencies}
        unknown_saves = set(self.saving_throw_proficiencies) - set(ABILITY_NAMES)
        if unknown_saves:
            raise ValueError(f"Unknown saving throw proficiencies: {', '.join(sorted(unknown_saves))}")
        if self.spellcasting is not None and self.spellcasting.ability not in ABILITY_NAMES:
            raise ValueError(f"Unknown spellcasting ability: {self.spellcasting.ability}")

    @property
    def proficiency_bonus(self) -> int:
        return proficiency_bonus(self.level)

    def ability_modifier(self, ability: str) -> int:
        return ability_modifier(self.ability_scores[ability])

    def saving_throw_modifier(self, ability: str) -> int:
        modifier = self.ability_modifier(ability)
        if ability in self.saving_throw_proficiencies:
            modifier += self.proficiency_bonus
        return modifier

    def skill_modifier(self, skill_name: str) -> int:
        normalized = normalize_skill_name(skill_name)
        modifier = self.ability_modifier(skill_ability(normalized))
        if normalized in self.skill_proficiencies:
            modifier += self.proficiency_bonus
        return modifier

    def apply_damage(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("Damage cannot be negative.")
        self.current_hp = max(0, self.current_hp - amount)

    def heal(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("Healing cannot be negative.")
        self.current_hp = min(self.max_hp, self.current_hp + amount)

    @property
    def is_unconscious(self) -> bool:
        return self.current_hp == 0

    @property
    def spell_save_dc(self) -> int | None:
        if self.spellcasting is None:
            return None
        return 8 + self.proficiency_bonus + self.ability_modifier(self.spellcasting.ability)

    @property
    def spell_attack_modifier(self) -> int | None:
        if self.spellcasting is None:
            return None
        return self.proficiency_bonus + self.ability_modifier(self.spellcasting.ability)
