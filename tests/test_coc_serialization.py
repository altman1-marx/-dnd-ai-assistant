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
        scenario.clues[1].push_attempted = True
        scenario.clues[1].last_check_total = 50
        scenario.clues[1].last_required_total = 45
        scenario.clues[1].last_check_level = "failure"
        scenario.inventory.append("Waterlogged journal")
        scenario.visited_location_ids.add("garden")
        scenario.investigator.lose_sanity(3)
        scenario.completed = True

        restored = coc_scenario_from_dict(coc_scenario_to_dict(scenario))

        self.assertEqual(restored.title, scenario.title)
        self.assertEqual(restored.investigator.name, "Eleanor Vale")
        self.assertEqual(restored.investigator.current_sanity, 57)
        self.assertTrue(restored.clues[0].discovered)
        self.assertTrue(restored.completed)
        self.assertEqual(restored.current_location_id, "study")
        self.assertEqual(restored.visited_location_ids, {"garden", "study"})
        self.assertEqual(restored.inventory, ["Waterlogged journal"])
        self.assertIn("cellar", restored.locations["study"].exits)
        self.assertIn("cellar", restored.locations["study"].exit_requirements)
        self.assertEqual(restored.npcs[0].name, "Mrs. Ember")
        self.assertEqual(restored.completion_requirements["required_clue_ids"], ["portrait_truth", "lantern_wick"])
        self.assertEqual(restored.talked_npc_ids, set())
        self.assertEqual(restored.clues[1].failure_evidence, "Charcoal spiral rubbing")
        self.assertFalse(restored.clues[1].partial_discovered)
        self.assertTrue(restored.clues[1].push_attempted)
        self.assertEqual(restored.clues[1].last_check_total, 50)
        self.assertEqual(restored.clues[1].last_required_total, 45)
        self.assertEqual(restored.clues[1].last_check_level, "failure")

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

    def test_coc_scenario_without_visited_locations_uses_current_location(self) -> None:
        data = coc_scenario_to_dict(create_sample_coc_scenario())
        del data["visited_location_ids"]

        restored = coc_scenario_from_dict(data)

        self.assertEqual(restored.visited_location_ids, {"study"})

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

    def test_validate_coc_scenario_data_rejects_unknown_location_references(self) -> None:
        data = coc_scenario_to_dict(create_sample_coc_scenario())
        data["clues"][0]["location_id"] = "attic"

        with self.assertRaisesRegex(COCScenarioValidationError, "unknown location"):
            validate_coc_scenario_data(data)

    def test_validate_coc_scenario_data_rejects_bad_visited_location(self) -> None:
        data = coc_scenario_to_dict(create_sample_coc_scenario())
        data["visited_location_ids"] = ["attic"]

        with self.assertRaisesRegex(COCScenarioValidationError, "visited_location_ids references unknown location"):
            validate_coc_scenario_data(data)

    def test_validate_coc_scenario_data_rejects_bad_exit_reference(self) -> None:
        data = coc_scenario_to_dict(create_sample_coc_scenario())
        data["locations"][0]["exits"]["attic"] = "attic"

        with self.assertRaisesRegex(COCScenarioValidationError, "unknown location"):
            validate_coc_scenario_data(data)

    def test_validate_coc_scenario_data_rejects_bad_exit_requirement_reference(self) -> None:
        data = coc_scenario_to_dict(create_sample_coc_scenario())
        data["locations"][0]["exit_requirements"]["attic"] = {"required_clue_ids": ["portrait_truth"]}

        with self.assertRaisesRegex(COCScenarioValidationError, "existing exit"):
            validate_coc_scenario_data(data)

    def test_validate_coc_scenario_data_rejects_bad_exit_requirement_shape(self) -> None:
        data = coc_scenario_to_dict(create_sample_coc_scenario())
        data["locations"][0]["exit_requirements"]["cellar"]["required_clue_ids"] = "portrait_truth"

        with self.assertRaisesRegex(COCScenarioValidationError, "required_clue_ids must be a list"):
            validate_coc_scenario_data(data)

    def test_validate_coc_scenario_data_rejects_bad_completion_requirement_shape(self) -> None:
        data = coc_scenario_to_dict(create_sample_coc_scenario())
        data["completion_requirements"]["required_clue_ids"] = "portrait_truth"

        with self.assertRaisesRegex(COCScenarioValidationError, "completion_requirements.required_clue_ids must be a list"):
            validate_coc_scenario_data(data)

    def test_validate_coc_scenario_data_rejects_bad_completion_requirement_reference(self) -> None:
        data = coc_scenario_to_dict(create_sample_coc_scenario())
        data["completion_requirements"]["required_location_ids"] = ["attic"]

        with self.assertRaisesRegex(COCScenarioValidationError, "unknown value: attic"):
            validate_coc_scenario_data(data)


    def test_validate_coc_scenario_data_rejects_bad_failure_fields(self) -> None:
        data = coc_scenario_to_dict(create_sample_coc_scenario())
        data["clues"][1]["failure_text"] = ""

        with self.assertRaisesRegex(COCScenarioValidationError, "failure_text"):
            validate_coc_scenario_data(data)

    def test_validate_coc_scenario_data_rejects_bad_partial_discovered(self) -> None:
        data = coc_scenario_to_dict(create_sample_coc_scenario())
        data["clues"][1]["partial_discovered"] = "yes"

        with self.assertRaisesRegex(COCScenarioValidationError, "partial_discovered"):
            validate_coc_scenario_data(data)


    def test_validate_coc_scenario_data_rejects_bad_push_attempted(self) -> None:
        data = coc_scenario_to_dict(create_sample_coc_scenario())
        data["clues"][1]["push_attempted"] = "yes"

        with self.assertRaisesRegex(COCScenarioValidationError, "push_attempted"):
            validate_coc_scenario_data(data)

    def test_validate_coc_scenario_data_rejects_bad_last_check_fields(self) -> None:
        data = coc_scenario_to_dict(create_sample_coc_scenario())
        data["clues"][1]["last_check_total"] = 0

        with self.assertRaisesRegex(COCScenarioValidationError, "last_check_total"):
            validate_coc_scenario_data(data)

        data = coc_scenario_to_dict(create_sample_coc_scenario())
        data["clues"][1]["last_check_level"] = "legendary"

        with self.assertRaisesRegex(COCScenarioValidationError, "last_check_level"):
            validate_coc_scenario_data(data)

    def test_validate_coc_scenario_data_rejects_bad_inventory(self) -> None:
        data = coc_scenario_to_dict(create_sample_coc_scenario())
        data["inventory"] = [""]

        with self.assertRaisesRegex(COCScenarioValidationError, "inventory"):
            validate_coc_scenario_data(data)

    def test_validate_coc_scenario_data_rejects_unknown_npc_location(self) -> None:
        data = coc_scenario_to_dict(create_sample_coc_scenario())
        data["npcs"][0]["location_id"] = "attic"

        with self.assertRaisesRegex(COCScenarioValidationError, "npcs.*unknown location"):
            validate_coc_scenario_data(data)

    def test_validate_coc_scenario_data_rejects_duplicate_npc_id(self) -> None:
        data = coc_scenario_to_dict(create_sample_coc_scenario())
        data["npcs"].append(dict(data["npcs"][0]))

        with self.assertRaisesRegex(COCScenarioValidationError, "duplicate npc id"):
            validate_coc_scenario_data(data)


if __name__ == "__main__":
    unittest.main()
