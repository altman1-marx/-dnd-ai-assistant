import unittest

from dnd_ai_assistant.core.coc7e import COCSuccessLevel, Investigator, PercentileRollMode, roll_percentile_check


class SequenceRNG:
    def __init__(self, values: list[int]) -> None:
        self.values = list(values)

    def randint(self, low: int, high: int) -> int:
        value = self.values.pop(0)
        if value < low or value > high:
            raise AssertionError(f"Test RNG value out of range: {value}")
        return value


class COC7ETests(unittest.TestCase):
    def test_percentile_check_reports_success_level(self) -> None:
        check = roll_percentile_check(60, rng=SequenceRNG([4, 2]))

        self.assertEqual(check.total, 24)
        self.assertEqual(check.success_level, COCSuccessLevel.HARD)
        self.assertTrue(check.success)

    def test_bonus_die_chooses_lower_tens_die(self) -> None:
        check = roll_percentile_check(60, mode=PercentileRollMode.BONUS, rng=SequenceRNG([4, 2, 1]))

        self.assertEqual(check.tens_dice, (2, 1))
        self.assertEqual(check.chosen_tens, 1)
        self.assertEqual(check.total, 14)
        self.assertEqual(check.success_level, COCSuccessLevel.HARD)

    def test_penalty_die_chooses_higher_tens_die(self) -> None:
        check = roll_percentile_check(60, mode=PercentileRollMode.PENALTY, rng=SequenceRNG([4, 2, 1]))

        self.assertEqual(check.tens_dice, (2, 1))
        self.assertEqual(check.chosen_tens, 2)
        self.assertEqual(check.total, 24)

    def test_critical_and_fumble_rules(self) -> None:
        critical = roll_percentile_check(5, rng=SequenceRNG([1, 0]))
        fumble = roll_percentile_check(40, rng=SequenceRNG([6, 9]))

        self.assertEqual(critical.total, 1)
        self.assertEqual(critical.success_level, COCSuccessLevel.CRITICAL)
        self.assertEqual(fumble.total, 96)
        self.assertEqual(fumble.success_level, COCSuccessLevel.FUMBLE)

    def test_rejects_invalid_skill_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "skill value"):
            roll_percentile_check(101)

    def test_investigator_derives_resources_and_normalizes_skills(self) -> None:
        investigator = _investigator()

        self.assertEqual(investigator.max_hp, 11)
        self.assertEqual(investigator.current_hp, 11)
        self.assertEqual(investigator.max_mp, 12)
        self.assertEqual(investigator.current_sanity, 60)
        self.assertEqual(investigator.skill_value("Library-Use"), 55)

    def test_investigator_damage_and_sanity_update_conditions(self) -> None:
        investigator = _investigator()

        investigator.apply_damage(6)
        investigator.lose_sanity(5)

        self.assertEqual(investigator.current_hp, 5)
        self.assertIn("major_wound", investigator.conditions)
        self.assertEqual(investigator.current_sanity, 55)
        self.assertIn("temporary_insanity", investigator.conditions)

    def test_investigator_rejects_missing_characteristics(self) -> None:
        with self.assertRaisesRegex(ValueError, "Missing COC characteristics"):
            Investigator(name="Broken", occupation="Antiquarian", characteristics={"str": 50})


def _investigator() -> Investigator:
    return Investigator(
        name="Eleanor Vale",
        occupation="Antiquarian",
        characteristics={"str": 45, "con": 55, "siz": 60, "dex": 50, "app": 55, "int": 70, "pow": 60, "edu": 75},
        skills={"library_use": 55, "spot hidden": 45},
        luck=50,
    )


if __name__ == "__main__":
    unittest.main()
