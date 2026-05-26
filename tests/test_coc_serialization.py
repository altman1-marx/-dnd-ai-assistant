import tempfile
import unittest
from pathlib import Path

from dnd_ai_assistant.coc_runtime import create_sample_coc_scenario
from dnd_ai_assistant.coc_serialization import coc_scenario_from_dict, coc_scenario_to_dict, load_coc_scenario, save_coc_scenario


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


if __name__ == "__main__":
    unittest.main()
