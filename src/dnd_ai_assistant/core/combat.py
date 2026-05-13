from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

from .character import Character
from .config import DEFAULT_RULES_CONFIG
from .initiative import Combatant, InitiativeTracker
from .spells import Spell


class ActionResource(str, Enum):
    ACTION = "action"
    BONUS_ACTION = "bonus_action"
    REACTION = "reaction"
    MOVEMENT = "movement"


@dataclass
class TurnResources:
    action: bool = True
    bonus_action: bool = True
    reaction: bool = True
    movement: int = DEFAULT_RULES_CONFIG.default_movement_speed

    def ensure_available(self, resource: ActionResource, amount: int = 0) -> None:
        if resource == ActionResource.MOVEMENT:
            if amount <= 0:
                raise ValueError("Movement amount must be positive.")
            if amount > self.movement:
                raise ValueError("Not enough movement remaining.")
            return
        if amount:
            raise ValueError("Only movement accepts an amount.")
        if not getattr(self, resource.value):
            raise ValueError(f"{resource.value} already spent.")

    def spend(self, resource: ActionResource, amount: int = 0) -> None:
        self.ensure_available(resource, amount)
        if resource == ActionResource.MOVEMENT:
            self.movement -= amount
            return

        setattr(self, resource.value, False)

    def reset_for_turn(self, movement_speed: int = DEFAULT_RULES_CONFIG.default_movement_speed) -> None:
        self.action = True
        self.bonus_action = True
        self.movement = movement_speed

    def reset_for_round(self) -> None:
        self.reaction = True


@dataclass
class CombatState:
    tracker: InitiativeTracker
    movement_speeds: dict[str, int] = field(default_factory=dict)
    resources: dict[str, TurnResources] = field(default_factory=dict)

    @classmethod
    def from_combatants(
        cls,
        combatants: list[Combatant],
        rng: random.Random | None = None,
        movement_speeds: dict[str, int] | None = None,
    ) -> "CombatState":
        tracker = InitiativeTracker(list(combatants))
        if all(combatant.initiative_roll is not None for combatant in tracker.combatants):
            tracker.sort()
        else:
            tracker.roll_missing_initiative(rng)
        speeds = movement_speeds or {}
        state = cls(tracker=tracker, movement_speeds=speeds)
        for combatant in tracker.combatants:
            state.resources[combatant.name] = TurnResources(
                movement=speeds.get(combatant.name, DEFAULT_RULES_CONFIG.default_movement_speed)
            )
        state.current_resources().reset_for_turn(state.current_speed())
        return state

    def current(self) -> Combatant:
        return self.tracker.current()

    def current_speed(self) -> int:
        return self.movement_speeds.get(self.current().name, DEFAULT_RULES_CONFIG.default_movement_speed)

    def current_resources(self) -> TurnResources:
        return self.resources[self.current().name]

    def spend(self, resource: ActionResource, amount: int = 0) -> None:
        self.current_resources().spend(resource, amount)

    def cast_spell(self, caster: Character, spell_name: str, slot_level: int | None = None) -> Spell:
        if caster.name != self.current().name:
            raise ValueError(f"It is not {caster.name}'s turn.")
        if caster.spellcasting is None:
            raise ValueError(f"{caster.name} cannot cast spells.")

        spell = caster.spellcasting.spell_named(spell_name)
        resource = action_resource_for_spell(spell)
        self.current_resources().ensure_available(resource)
        cast_spell = caster.spellcasting.cast_spell(spell.name, slot_level=slot_level)
        self.current_resources().spend(resource)
        return cast_spell

    def end_turn(self) -> Combatant:
        previous_round = self.tracker.round_number
        next_combatant = self.tracker.advance()
        if self.tracker.round_number != previous_round:
            for resources in self.resources.values():
                resources.reset_for_round()
        self.current_resources().reset_for_turn(self.current_speed())
        return next_combatant


def action_resource_for_spell(spell: Spell) -> ActionResource:
    casting_time = spell.casting_time.strip().lower()
    if "bonus action" in casting_time:
        return ActionResource.BONUS_ACTION
    if "reaction" in casting_time:
        return ActionResource.REACTION
    return ActionResource.ACTION
