import random
import unittest

from dnd_ai_assistant.core.combat import ActionResource, CombatState
from dnd_ai_assistant.core.initiative import Combatant


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


if __name__ == "__main__":
    unittest.main()
