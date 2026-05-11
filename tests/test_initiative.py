import random
import unittest

from dnd_ai_assistant.core.initiative import Combatant, InitiativeTracker


class InitiativeTests(unittest.TestCase):
    def test_roll_initiative_orders_combatants(self) -> None:
        tracker = InitiativeTracker(
            [
                Combatant("Kael", initiative_modifier=3, is_player=True),
                Combatant("Goblin", initiative_modifier=2),
                Combatant("Cultist", initiative_modifier=1),
            ]
        )

        tracker.roll_initiative(random.Random(1))

        self.assertEqual(tracker.order(), ["Goblin", "Kael", "Cultist"])
        self.assertEqual(tracker.current().name, "Goblin")

    def test_advance_wraps_rounds(self) -> None:
        tracker = InitiativeTracker([Combatant("A", initiative_roll=10), Combatant("B", initiative_roll=5)])
        tracker.sort()

        self.assertEqual(tracker.current().name, "A")
        self.assertEqual(tracker.advance().name, "B")
        self.assertEqual(tracker.round_number, 1)
        self.assertEqual(tracker.advance().name, "A")
        self.assertEqual(tracker.round_number, 2)


if __name__ == "__main__":
    unittest.main()

