from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum


class PercentileRollMode(str, Enum):
    NORMAL = "normal"
    BONUS = "bonus"
    PENALTY = "penalty"


class COCSuccessLevel(str, Enum):
    FUMBLE = "fumble"
    FAILURE = "failure"
    REGULAR = "regular"
    HARD = "hard"
    EXTREME = "extreme"
    CRITICAL = "critical"


@dataclass(frozen=True)
class PercentileCheck:
    skill_value: int
    mode: PercentileRollMode
    ones_die: int
    tens_dice: tuple[int, ...]
    chosen_tens: int
    total: int
    success_level: COCSuccessLevel
    success: bool


COC_CHARACTERISTICS = ("str", "con", "siz", "dex", "app", "int", "pow", "edu")


@dataclass
class Investigator:
    name: str
    occupation: str
    characteristics: dict[str, int]
    skills: dict[str, int] = field(default_factory=dict)
    max_hp: int | None = None
    current_hp: int | None = None
    max_mp: int | None = None
    current_mp: int | None = None
    max_sanity: int | None = None
    current_sanity: int | None = None
    luck: int = 50
    conditions: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        missing = set(COC_CHARACTERISTICS) - set(self.characteristics)
        if missing:
            raise ValueError(f"Missing COC characteristics: {', '.join(sorted(missing))}")
        for characteristic in COC_CHARACTERISTICS:
            value = self.characteristics[characteristic]
            if value < 1 or value > 99:
                raise ValueError("COC characteristics must be between 1 and 99.")
        self.skills = {normalize_skill_name(name): value for name, value in self.skills.items()}
        for value in self.skills.values():
            if value < 0 or value > 100:
                raise ValueError("COC skill values must be between 0 and 100.")
        if self.max_hp is None:
            self.max_hp = max(1, (self.characteristics["con"] + self.characteristics["siz"]) // 10)
        if self.current_hp is None:
            self.current_hp = self.max_hp
        if self.max_mp is None:
            self.max_mp = max(0, self.characteristics["pow"] // 5)
        if self.current_mp is None:
            self.current_mp = self.max_mp
        if self.max_sanity is None:
            self.max_sanity = min(99, self.characteristics["pow"])
        if self.current_sanity is None:
            self.current_sanity = self.max_sanity
        if self.current_hp < 0 or self.current_hp > self.max_hp:
            raise ValueError("Current HP must be between 0 and max HP.")
        if self.current_mp < 0 or self.current_mp > self.max_mp:
            raise ValueError("Current MP must be between 0 and max MP.")
        if self.current_sanity < 0 or self.current_sanity > self.max_sanity:
            raise ValueError("Current sanity must be between 0 and max sanity.")
        if self.luck < 0 or self.luck > 100:
            raise ValueError("Luck must be between 0 and 100.")

    def skill_value(self, skill_name: str) -> int:
        return self.skills.get(normalize_skill_name(skill_name), 0)

    def apply_damage(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("Damage cannot be negative.")
        assert self.current_hp is not None
        assert self.max_hp is not None
        self.current_hp = max(0, self.current_hp - amount)
        if amount >= self.max_hp // 2 and amount > 0:
            self.conditions.add("major_wound")
        if self.current_hp == 0:
            self.conditions.add("dying")
            self.conditions.add("unconscious")

    def heal(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("Healing cannot be negative.")
        assert self.current_hp is not None
        assert self.max_hp is not None
        self.current_hp = min(self.max_hp, self.current_hp + amount)
        if self.current_hp > 0:
            self.conditions.discard("dying")
            self.conditions.discard("unconscious")

    def lose_sanity(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("Sanity loss cannot be negative.")
        assert self.current_sanity is not None
        self.current_sanity = max(0, self.current_sanity - amount)
        if amount >= 5:
            self.conditions.add("temporary_insanity")
        if self.current_sanity == 0:
            self.conditions.add("indefinite_insanity")


def normalize_skill_name(skill_name: str) -> str:
    return " ".join(skill_name.strip().lower().replace("_", " ").replace("-", " ").split())


def roll_percentile_check(
    skill_value: int,
    mode: PercentileRollMode = PercentileRollMode.NORMAL,
    rng: random.Random | None = None,
) -> PercentileCheck:
    if skill_value < 0 or skill_value > 100:
        raise ValueError("COC 7e skill value must be between 0 and 100.")
    rng = rng or random.Random()
    ones_die = rng.randint(0, 9)
    tens_dice = _roll_tens_dice(mode, rng)
    chosen_tens = _choose_tens_die(tens_dice, mode)
    total = _percentile_total(chosen_tens, ones_die)
    success_level = _success_level(total, skill_value)
    return PercentileCheck(
        skill_value=skill_value,
        mode=mode,
        ones_die=ones_die,
        tens_dice=tens_dice,
        chosen_tens=chosen_tens,
        total=total,
        success_level=success_level,
        success=success_level not in {COCSuccessLevel.FAILURE, COCSuccessLevel.FUMBLE},
    )


def _roll_tens_dice(mode: PercentileRollMode, rng: random.Random) -> tuple[int, ...]:
    if mode == PercentileRollMode.NORMAL:
        return (rng.randint(0, 9),)
    if mode in {PercentileRollMode.BONUS, PercentileRollMode.PENALTY}:
        return (rng.randint(0, 9), rng.randint(0, 9))
    raise ValueError(f"Unsupported percentile roll mode: {mode}")


def _choose_tens_die(tens_dice: tuple[int, ...], mode: PercentileRollMode) -> int:
    if mode == PercentileRollMode.PENALTY:
        return max(tens_dice)
    return min(tens_dice)


def _percentile_total(tens_die: int, ones_die: int) -> int:
    if tens_die == 0 and ones_die == 0:
        return 100
    return tens_die * 10 + ones_die


def _success_level(total: int, skill_value: int) -> COCSuccessLevel:
    if total == 1:
        return COCSuccessLevel.CRITICAL
    if _is_fumble(total, skill_value):
        return COCSuccessLevel.FUMBLE
    if total > skill_value:
        return COCSuccessLevel.FAILURE
    if total <= max(1, skill_value // 5):
        return COCSuccessLevel.EXTREME
    if total <= max(1, skill_value // 2):
        return COCSuccessLevel.HARD
    return COCSuccessLevel.REGULAR


def _is_fumble(total: int, skill_value: int) -> bool:
    if skill_value < 50:
        return total >= 96
    return total == 100
