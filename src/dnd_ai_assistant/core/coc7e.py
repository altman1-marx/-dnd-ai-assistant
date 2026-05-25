from __future__ import annotations

import random
from dataclasses import dataclass
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

