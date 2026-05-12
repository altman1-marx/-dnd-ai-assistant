import unittest

from dnd_ai_assistant.core.config import DEFAULT_RULES_CONFIG, RulesConfig


class RulesConfigTests(unittest.TestCase):
    def test_default_dc_lookup_normalizes_difficulty_names(self) -> None:
        self.assertEqual(DEFAULT_RULES_CONFIG.dc("Very Easy"), 5)
        self.assertEqual(DEFAULT_RULES_CONFIG.dc("nearly-impossible"), 30)

    def test_custom_dc_lookup(self) -> None:
        config = RulesConfig(dc_by_difficulty={"risky": 17}, default_movement_speed=25)

        self.assertEqual(config.dc("risky"), 17)
        self.assertEqual(config.default_movement_speed, 25)

    def test_unknown_dc_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown difficulty"):
            DEFAULT_RULES_CONFIG.dc("mythic")


if __name__ == "__main__":
    unittest.main()
