from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum

from .dice import DiceRoll, roll


class RollMode(str, Enum):
    NORMAL = "normal"
    ADVANTAGE = "advantage"
    DISADVANTAGE = "disadvantage"


@dataclass(frozen=True)
class D20Check:
    mode: RollMode
    dc: int | None
    modifier: int
    d20_rolls: tuple[int, ...]
    chosen_d20: int
    total: int
    success: bool | None
    natural_20: bool
    natural_1: bool


@dataclass(frozen=True)
class AttackRoll:
    attack: D20Check
    target_ac: int
    hit: bool
    damage: DiceRoll | None


def ability_modifier(score: int) -> int:
    if score < 1 or score > 30:
        raise ValueError("DND 5e ability scores should be between 1 and 30.")
    return (score - 10) // 2


def proficiency_bonus(level: int) -> int:
    if level < 1 or level > 20:
        raise ValueError("DND 5e character levels should be between 1 and 20.")
    return 2 + (level - 1) // 4


def roll_d20_check(
    modifier: int = 0,
    dc: int | None = None,
    mode: RollMode = RollMode.NORMAL,
    rng: random.Random | None = None,
) -> D20Check:
    rng = rng or random.Random()
    if dc is not None and dc < 0:
        raise ValueError("DC cannot be negative.")

    if mode == RollMode.NORMAL:
        d20_rolls = (roll("1d20", rng).total,)
        chosen = d20_rolls[0]
    elif mode == RollMode.ADVANTAGE:
        d20_rolls = (roll("1d20", rng).total, roll("1d20", rng).total)
        chosen = max(d20_rolls)
    elif mode == RollMode.DISADVANTAGE:
        d20_rolls = (roll("1d20", rng).total, roll("1d20", rng).total)
        chosen = min(d20_rolls)
    else:
        raise ValueError(f"Unsupported roll mode: {mode}")

    total = chosen + modifier
    success = None if dc is None else total >= dc
    return D20Check(
        mode=mode,
        dc=dc,
        modifier=modifier,
        d20_rolls=d20_rolls,
        chosen_d20=chosen,
        total=total,
        success=success,
        natural_20=chosen == 20,
        natural_1=chosen == 1,
    )


def roll_damage(expression: str, rng: random.Random | None = None) -> DiceRoll:
    return roll(expression, rng)


def roll_attack(
    attack_bonus: int,
    target_ac: int,
    damage_expression: str,
    mode: RollMode = RollMode.NORMAL,
    rng: random.Random | None = None,
) -> AttackRoll:
    rng = rng or random.Random()
    attack = roll_d20_check(modifier=attack_bonus, dc=target_ac, mode=mode, rng=rng)
    hit = bool(attack.success)
    damage = roll_damage(damage_expression, rng) if hit else None
    return AttackRoll(attack=attack, target_ac=target_ac, hit=hit, damage=damage)
