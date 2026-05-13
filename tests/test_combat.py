import random
import unittest

from dnd_ai_assistant.core.combat import ActionResource, CombatState
from dnd_ai_assistant.core.character import Character
from dnd_ai_assistant.core.initiative import Combatant
from dnd_ai_assistant.core.spells import Spell, Spellcasting


class CombatStateTests(unittest.TestCase):
    def test_combat_state_rolls_initiative_and_tracks_current_resources(self) -> None:
        state = CombatState.from_combatants(
            [
                Combatant("Kael", initiative_modifier=3, is_player=True),
                Combatant("Goblin", initiative_modifier=2),
            ],
            rng=random.Random(1),
            movement_speeds={"Kael": 35},
        )

        self.assertEqual(state.tracker.order(), ["Goblin", "Kael"])
        state.spend(ActionResource.ACTION)
        state.spend(ActionResource.MOVEMENT, amount=10)

        resources = state.current_resources()
        self.assertFalse(resources.action)
        self.assertEqual(resources.movement, 20)

    def test_combat_state_preserves_existing_initiative_rolls(self) -> None:
        state = CombatState.from_combatants(
            [Combatant("A", initiative_roll=20), Combatant("B")],
            rng=random.Random(1),
        )

        self.assertEqual(state.tracker.combatants[0].name, "A")
        self.assertEqual(state.tracker.combatants[0].initiative_roll, 20)
        self.assertEqual(state.resources["B"].movement, 30)

    def test_turn_resources_reset_on_next_turn_but_reaction_resets_each_round(self) -> None:
        state = CombatState.from_combatants(
            [Combatant("A", initiative_roll=10), Combatant("B", initiative_roll=5)]
        )
        self.assertEqual(state.tracker.order(), ["A", "B"])

        state.spend(ActionResource.REACTION)
        state.spend(ActionResource.BONUS_ACTION)

        state.end_turn()
        self.assertEqual(state.current().name, "B")
        self.assertFalse(state.resources["A"].reaction)
        self.assertTrue(state.resources["B"].bonus_action)

        state.end_turn()
        self.assertEqual(state.current().name, "A")
        self.assertEqual(state.tracker.round_number, 2)
        self.assertTrue(state.resources["A"].reaction)
        self.assertTrue(state.resources["A"].bonus_action)

    def test_cannot_spend_same_action_twice(self) -> None:
        state = CombatState.from_combatants([Combatant("A", initiative_roll=10)])

        state.spend(ActionResource.ACTION)

        with self.assertRaises(ValueError):
            state.spend(ActionResource.ACTION)

    def test_cast_spell_spends_slot_and_action_resource(self) -> None:
        state = CombatState.from_combatants([Combatant("Leth", initiative_roll=10)])
        caster = _caster()

        spell = state.cast_spell(caster, "Bless")

        self.assertEqual(spell.name, "Bless")
        self.assertFalse(state.current_resources().action)
        self.assertEqual(caster.spellcasting.available_slots(1), 1)
        self.assertEqual(caster.spellcasting.concentration_spell_name, "Bless")

    def test_cast_bonus_action_spell_spends_bonus_action(self) -> None:
        state = CombatState.from_combatants([Combatant("Leth", initiative_roll=10)])
        caster = _caster()

        spell = state.cast_spell(caster, "Healing Word")

        self.assertEqual(spell.name, "Healing Word")
        self.assertTrue(state.current_resources().action)
        self.assertFalse(state.current_resources().bonus_action)
        self.assertEqual(caster.spellcasting.available_slots(1), 1)

    def test_failed_spell_cast_does_not_spend_action(self) -> None:
        state = CombatState.from_combatants([Combatant("Leth", initiative_roll=10)])
        caster = _caster()
        caster.spellcasting.expend_slot(1)
        caster.spellcasting.expend_slot(1)

        with self.assertRaises(ValueError):
            state.cast_spell(caster, "Bless")

        self.assertTrue(state.current_resources().action)


def _caster() -> Character:
    return Character(
        name="Leth",
        player_name="Player",
        class_name="Cleric",
        level=3,
        ancestry="Human",
        ability_scores={"str": 10, "dex": 10, "con": 14, "int": 10, "wis": 16, "cha": 12},
        armor_class=16,
        max_hp=24,
        current_hp=24,
        spellcasting=Spellcasting(
            ability="wis",
            slots_by_level={1: 2},
            known_spells=[
                Spell("Bless", 1, concentration=True),
                Spell("Healing Word", 1, casting_time="1 bonus action"),
            ],
        ),
    )


if __name__ == "__main__":
    unittest.main()
