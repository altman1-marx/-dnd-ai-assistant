from __future__ import annotations

import random
import re
from dataclasses import dataclass


_DICE_RE = re.compile(r"^\s*(?:(?P<count>\d*)d(?P<sides>\d+)|(?P<constant>\d+))\s*$", re.IGNORECASE)
_TOKEN_RE = re.compile(r"([+-]?)\s*([^+-]+)")


@dataclass(frozen=True)
class DiceTerm:
    count: int
    sides: int
    sign: int = 1


@dataclass(frozen=True)
class ConstantTerm:
    value: int
    sign: int = 1


@dataclass(frozen=True)
class DiceRoll:
    expression: str
    total: int
    rolls: tuple[tuple[int, ...], ...]
    modifier: int


def parse_dice_expression(expression: str) -> list[DiceTerm | ConstantTerm]:
    """Parse expressions such as 1d20+5, 2d6+3, d8-1."""
    if not expression or not expression.strip():
        raise ValueError("Dice expression cannot be empty.")

    terms: list[DiceTerm | ConstantTerm] = []
    position = 0
    for token in _TOKEN_RE.finditer(expression):
        if token.start() != position and expression[position:token.start()].strip():
            raise ValueError(f"Invalid dice expression: {expression}")
        position = token.end()

        sign = -1 if token.group(1) == "-" else 1
        body = token.group(2).strip()
        match = _DICE_RE.match(body)
        if not match:
            raise ValueError(f"Invalid dice term: {body}")

        if match.group("constant") is not None:
            terms.append(ConstantTerm(value=int(match.group("constant")), sign=sign))
            continue

        count_text = match.group("count")
        count = int(count_text) if count_text else 1
        sides = int(match.group("sides"))
        if count <= 0:
            raise ValueError("Dice count must be positive.")
        if sides <= 1:
            raise ValueError("Dice must have at least 2 sides.")
        terms.append(DiceTerm(count=count, sides=sides, sign=sign))

    if position != len(expression) and expression[position:].strip():
        raise ValueError(f"Invalid dice expression: {expression}")
    if not terms:
        raise ValueError(f"Invalid dice expression: {expression}")
    return terms


def roll(expression: str, rng: random.Random | None = None) -> DiceRoll:
    """Roll a dice expression and return the total plus raw dice results."""
    rng = rng or random.Random()
    rolls: list[tuple[int, ...]] = []
    modifier = 0
    total = 0
    for term in parse_dice_expression(expression):
        if isinstance(term, ConstantTerm):
            value = term.sign * term.value
            modifier += value
            total += value
            continue

        term_rolls = tuple(rng.randint(1, term.sides) for _ in range(term.count))
        rolls.append(term_rolls)
        total += term.sign * sum(term_rolls)

    return DiceRoll(expression=expression, total=total, rolls=tuple(rolls), modifier=modifier)

