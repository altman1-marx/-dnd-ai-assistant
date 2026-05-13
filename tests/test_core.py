import random
import unittest

from dnd_ai_assistant.core.character import Character
from dnd_ai_assistant.core.campaign import Campaign, Clue, Encounter, Location, NPC
from dnd_ai_assistant.core.dice import ConstantTerm, parse_dice_expression, roll
from dnd_ai_assistant.core.dnd5e import RollMode, ability_modifier, proficiency_bonus, roll_attack, roll_d20_check


class DiceTests(unittest.TestCase):
    def test_parse_dice_expression(self) -> None:
        terms = parse_dice_expression("2d6+3-1d4")
        self.assertEqual(len(terms), 3)
        self.assertIsInstance(terms[1], ConstantTerm)
        self.assertIsInstance(terms[1].value, int)

    def test_roll_is_deterministic_with_seed(self) -> None:
        result = roll("2d6+3", random.Random(1))
        self.assertEqual(result.rolls, ((2, 5),))
        self.assertEqual(result.total, 10)
        self.assertEqual(result.modifier, 3)


class Dnd5eTests(unittest.TestCase):
    def test_ability_modifier(self) -> None:
        self.assertEqual(ability_modifier(8), -1)
        self.assertEqual(ability_modifier(10), 0)
        self.assertEqual(ability_modifier(16), 3)

    def test_proficiency_bonus(self) -> None:
        self.assertEqual(proficiency_bonus(1), 2)
        self.assertEqual(proficiency_bonus(5), 3)
        self.assertEqual(proficiency_bonus(17), 6)

    def test_advantage_check_uses_higher_roll(self) -> None:
        check = roll_d20_check(modifier=2, dc=12, mode=RollMode.ADVANTAGE, rng=random.Random(1))
        self.assertEqual(check.d20_rolls, (5, 19))
        self.assertEqual(check.chosen_d20, 19)
        self.assertEqual(check.total, 21)
        self.assertTrue(check.success)

    def test_attack_roll_deals_damage_on_hit(self) -> None:
        attack = roll_attack(attack_bonus=8, target_ac=13, damage_expression="1d6+2", rng=random.Random(1))

        self.assertTrue(attack.hit)
        self.assertEqual(attack.attack.total, 13)
        self.assertEqual(attack.damage.total, 7)

    def test_attack_natural_20_is_critical_hit(self) -> None:
        attack = roll_attack(attack_bonus=0, target_ac=99, damage_expression="1d6+2", rng=random.Random(5))

        self.assertTrue(attack.hit)
        self.assertTrue(attack.attack.natural_20)
        self.assertEqual(attack.damage.rolls, ((3, 6),))
        self.assertEqual(attack.damage.total, 11)
        self.assertEqual(attack.damage.modifier, 2)

    def test_attack_natural_1_misses_even_with_high_bonus(self) -> None:
        attack = roll_attack(attack_bonus=99, target_ac=5, damage_expression="1d6+2", rng=random.Random(31))

        self.assertFalse(attack.hit)
        self.assertTrue(attack.attack.natural_1)
        self.assertIsNone(attack.damage)


class CharacterTests(unittest.TestCase):
    def test_damage_and_healing(self) -> None:
        character = Character(
            name="Ari",
            player_name="Player",
            class_name="Fighter",
            level=3,
            ancestry="Human",
            ability_scores={"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 8},
            armor_class=16,
            max_hp=28,
            current_hp=28,
            saving_throw_proficiencies={"str", "con"},
        )

        self.assertEqual(character.proficiency_bonus, 2)
        self.assertEqual(character.saving_throw_modifier("str"), 5)
        character.apply_damage(30)
        self.assertEqual(character.current_hp, 0)
        self.assertTrue(character.is_unconscious)
        character.heal(7)
        self.assertEqual(character.current_hp, 7)

    def test_skill_modifier_uses_skill_ability_and_proficiency(self) -> None:
        character = Character(
            name="Ari",
            player_name="Player",
            class_name="Rogue",
            level=5,
            ancestry="Halfling",
            ability_scores={"str": 8, "dex": 16, "con": 12, "int": 14, "wis": 10, "cha": 13},
            armor_class=15,
            max_hp=31,
            current_hp=31,
            skill_proficiencies={"stealth", "investigation"},
        )

        self.assertEqual(character.skill_modifier("Stealth"), 6)
        self.assertEqual(character.skill_modifier("investigation"), 5)
        self.assertEqual(character.skill_modifier("perception"), 0)

    def test_character_normalizes_skill_names(self) -> None:
        character = Character(
            name="Ari",
            player_name="Player",
            class_name="Rogue",
            level=1,
            ancestry="Halfling",
            ability_scores={"str": 8, "dex": 16, "con": 12, "int": 14, "wis": 10, "cha": 13},
            armor_class=15,
            max_hp=9,
            current_hp=9,
            skill_proficiencies={"Sleight of Hand"},
        )

        self.assertEqual(character.skill_modifier("sleight-of-hand"), 5)

    def test_character_rejects_invalid_state(self) -> None:
        with self.assertRaises(ValueError):
            Character(
                name="Ari",
                player_name="Player",
                class_name="Fighter",
                level=21,
                ancestry="Human",
                ability_scores={"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 8},
                armor_class=16,
                max_hp=28,
                current_hp=28,
            )

    def test_campaign_rejects_duplicate_character_names(self) -> None:
        campaign = Campaign("Roadside Ambush")
        character = Character(
            name="Ari",
            player_name="Player",
            class_name="Fighter",
            level=3,
            ancestry="Human",
            ability_scores={"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 8},
            armor_class=16,
            max_hp=28,
            current_hp=28,
        )

        campaign.add_character(character)

        with self.assertRaises(ValueError):
            campaign.add_character(character)

    def test_campaign_rejects_unknown_location_references(self) -> None:
        campaign = Campaign("Roadside Ambush")

        with self.assertRaises(ValueError):
            campaign.add_npc(NPC("Mira", "mayor", "Worried.", location_id="loc_missing"))
        with self.assertRaises(ValueError):
            campaign.add_clue(Clue("Ash", "Black ash.", location_id="loc_missing"))
        with self.assertRaises(ValueError):
            campaign.add_encounter(Encounter("Ambush", location_id="loc_missing"))

    def test_campaign_rejects_duplicate_entity_ids(self) -> None:
        campaign = Campaign("Roadside Ambush")
        location = Location("Old Road", "A muddy road.", id="loc_1")

        campaign.add_location(location)

        with self.assertRaises(ValueError):
            campaign.add_location(Location("Old Road", "A muddy road.", id="loc_1"))


if __name__ == "__main__":
    unittest.main()
