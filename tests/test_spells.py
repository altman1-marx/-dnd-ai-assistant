import unittest

from dnd_ai_assistant.core.character import Character
from dnd_ai_assistant.core.spells import Spell, Spellcasting


class SpellcastingTests(unittest.TestCase):
    def test_spellcasting_tracks_slot_expenditure_and_recovery(self) -> None:
        spellcasting = Spellcasting(
            ability="wis",
            slots_by_level={1: 2},
            known_spells=[Spell("Cure Wounds", 1, school="evocation")],
            prepared_spell_names={"Cure Wounds"},
        )

        self.assertEqual(spellcasting.available_slots(1), 2)
        spellcasting.expend_slot(1)
        self.assertEqual(spellcasting.available_slots(1), 1)
        spellcasting.recover_slots(1)
        self.assertEqual(spellcasting.available_slots(1), 2)

    def test_spellcasting_rejects_over_expended_slots(self) -> None:
        with self.assertRaises(ValueError):
            Spellcasting(ability="int", slots_by_level={1: 1}, expended_slots_by_level={1: 2})

    def test_character_reports_spell_dc_and_attack_modifier(self) -> None:
        character = Character(
            name="Leth",
            player_name="Player",
            class_name="Cleric",
            level=5,
            ancestry="Human",
            ability_scores={"str": 10, "dex": 10, "con": 14, "int": 10, "wis": 16, "cha": 12},
            armor_class=16,
            max_hp=38,
            current_hp=38,
            spellcasting=Spellcasting(ability="wis", slots_by_level={1: 4, 2: 3, 3: 2}),
        )

        self.assertEqual(character.spell_save_dc, 14)
        self.assertEqual(character.spell_attack_modifier, 6)


if __name__ == "__main__":
    unittest.main()
