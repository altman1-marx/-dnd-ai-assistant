import tempfile
import unittest
from pathlib import Path

from dnd_ai_assistant.coc_runtime import create_sample_coc_scenario
from dnd_ai_assistant.coc_serialization import (
    COCScenarioValidationError,
    coc_scenario_from_dict,
    coc_scenario_to_dict,
    load_coc_scenario,
    save_coc_scenario,
    validate_coc_scenario_data,
)


class COCSerializationTests(unittest.TestCase):
    def test_coc_scenario_round_trips_dict(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.clues[0].discovered = True
        scenario.investigator.lose_sanity(3)
        scenario.completed = True

        restored = coc_scenario_from_dict(coc_scenario_to_dict(scenario))

        self.assertEqual(restored.title, scenario.title)
        self.assertEqual(restored.investigator.name, "Eleanor Vale")
        self.assertEqual(restored.investigator.current_sanity, 57)
        self.assertTrue(restored.clues[0].discovered)
        self.assertTrue(restored.completed)

    def test_coc_scenario_save_and_load_file(self) -> None:
        scenario = create_sample_coc_scenario()

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "coc.json"
            save_coc_scenario(scenario, path)
            restored = load_coc_scenario(path)

        self.assertEqual(restored.title, scenario.title)
        self.assertEqual(restored.investigator.skill_value("spot hidden"), 45)

    def test_coc_scenario_without_id_gets_generated_id(self) -> None:
        data = coc_scenario_to_dict(create_sample_coc_scenario())
        del data["id"]

        restored = coc_scenario_from_dict(data)

        self.assertTrue(restored.id.startswith("coc_"))
        self.assertNotEqual(restored.id, "coc_legacy")

    def test_validate_coc_scenario_data_accepts_sample(self) -> None:
        validate_coc_scenario_data(coc_scenario_to_dict(create_sample_coc_scenario()))

    def test_validate_coc_scenario_data_rejects_missing_required_field(self) -> None:
        data = coc_scenario_to_dict(create_sample_coc_scenario())
        del data["title"]

        with self.assertRaisesRegex(COCScenarioValidationError, "title"):
            validate_coc_scenario_data(data)

    def test_validate_coc_scenario_data_rejects_bad_characteristic(self) -> None:
        data = coc_scenario_to_dict(create_sample_coc_scenario())
        data["investigator"]["characteristics"]["pow"] = 120

        with self.assertRaisesRegex(COCScenarioValidationError, "pow.*between 1 and 99"):
            coc_scenario_from_dict(data)

    def test_validate_coc_scenario_data_rejects_duplicate_clue_id(self) -> None:
        data = coc_scenario_to_dict(create_sample_coc_scenario())
        data["clues"][1]["id"] = data["clues"][0]["id"]

        with self.assertRaisesRegex(COCScenarioValidationError, "duplicate clue id"):
            validate_coc_scenario_data(data)

    def test_validate_coc_scenario_data_rejects_empty_clues(self) -> None:
        data = coc_scenario_to_dict(create_sample_coc_scenario())
        data["clues"] = []

        with self.assertRaisesRegex(COCScenarioValidationError, "at least one clue"):
            validate_coc_scenario_data(data)

    def test_validate_coc_scenario_data_rejects_bad_clue_difficulty(self) -> None:
        data = coc_scenario_to_dict(create_sample_coc_scenario())
        data["clues"][0]["difficulty"] = "impossible"

        with self.assertRaisesRegex(COCScenarioValidationError, "difficulty"):
            validate_coc_scenario_data(data)


if __name__ == "__main__":
    unittest.main()
