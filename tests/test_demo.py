import unittest
import tempfile
from pathlib import Path

from dnd_ai_assistant.demo import run_quickstart, run_scripted_scene


class DemoTests(unittest.TestCase):
    def test_quickstart_contains_expected_sections(self) -> None:
        output = run_quickstart(seed=1)

        self.assertIn("Campaign: The Bell Beneath Ashford", output)
        self.assertIn("Characters:", output)
        self.assertIn("Revealed clues:", output)
        self.assertIn("d20 rolls: 5, 19", output)
        self.assertIn("total: 23", output)
        self.assertIn("[System] Kael rolled 23 vs DC 15: success.", output)

    def test_scripted_scene_resolves_basic_actions(self) -> None:
        output = run_scripted_scene(seed=1, actions=["look around", "inspect rope", "open stairway", "quit"])

        self.assertIn("DM: Kael stands inside the Old Chapel.", output)
        self.assertIn("Player: inspect rope", output)
        self.assertIn("System: Perception with advantage vs DC 15 -> rolls (5, 19), total 23.", output)
        self.assertIn("DM: The seal grinds open.", output)
        self.assertIn("DM: The scene pauses here.", output)

    def test_stairway_requires_clue_first(self) -> None:
        output = run_scripted_scene(seed=1, actions=["open stairway"])

        self.assertIn("The stairway seal does not move", output)

    def test_scripted_scene_can_save_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            output = run_scripted_scene(seed=1, actions=["inspect rope", "quit"], save_state_path=path)

            self.assertTrue(path.exists())
            self.assertIn("Saved campaign state", output)


if __name__ == "__main__":
    unittest.main()
