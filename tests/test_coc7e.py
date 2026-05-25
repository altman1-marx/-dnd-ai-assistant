import unittest

from dnd_ai_assistant.core.coc7e import COCSuccessLevel, PercentileRollMode, roll_percentile_check


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


if __name__ == "__main__":
    unittest.main()
