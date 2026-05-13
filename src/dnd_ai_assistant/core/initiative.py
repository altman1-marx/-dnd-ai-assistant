from __future__ import annotations

import random
from dataclasses import dataclass

from .dice import roll


@dataclass
class Combatant:
    name: str
    initiative_modifier: int = 0
    armor_class: int | None = None
    current_hp: int | None = None
    is_player: bool = False
    initiative_roll: int | None = None

    @property
    def initiative_total(self) -> int:
        if self.initiative_roll is None:
            return self.initiative_modifier
        return self.initiative_roll + self.initiative_modifier


class InitiativeTracker:
    def __init__(self, combatants: list[Combatant] | None = None) -> None:
        self.combatants = combatants or []
        self.turn_index = 0
        self.round_number = 1

    def add(self, combatant: Combatant) -> None:
        self.combatants.append(combatant)

    def roll_initiative(self, rng: random.Random | None = None) -> None:
        rng = rng or random.Random()
        for combatant in self.combatants:
            combatant.initiative_roll = roll("1d20", rng).total
        self.sort()

    def roll_missing_initiative(self, rng: random.Random | None = None) -> None:
        rng = rng or random.Random()
        for combatant in self.combatants:
            if combatant.initiative_roll is None:
                combatant.initiative_roll = roll("1d20", rng).total
        self.sort()

    def sort(self) -> None:
        self.combatants.sort(
            key=lambda combatant: (combatant.initiative_total, combatant.initiative_modifier, combatant.name),
            reverse=True,
        )
        self.turn_index = 0
        self.round_number = 1

    def current(self) -> Combatant:
        if not self.combatants:
            raise ValueError("Initiative tracker has no combatants.")
        return self.combatants[self.turn_index]

    def advance(self) -> Combatant:
        if not self.combatants:
            raise ValueError("Initiative tracker has no combatants.")
        self.turn_index += 1
        if self.turn_index >= len(self.combatants):
            self.turn_index = 0
            self.round_number += 1
        return self.current()

    def order(self) -> list[str]:
        return [combatant.name for combatant in self.combatants]
