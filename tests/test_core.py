import random
import unittest

from dnd_ai_assistant.core.character import Character
from dnd_ai_assistant.core.dice import parse_dice_expression, roll
from dnd_ai_assistant.core.dnd5e import RollMode, ability_modifier, proficiency_bonus, roll_attack, roll_d20_check


class DiceTests(unittest.TestCase):
    def test_parse_dice_expression(self) -> None:
        terms = parse_dice_expression("2d6+3-1d4")
        self.assertEqual(len(terms), 3)

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


if __name__ == "__main__":
    unittest.main()
