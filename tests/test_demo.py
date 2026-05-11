import unittest
import tempfile
from pathlib import Path

from dnd_ai_assistant.demo import run_initiative_demo, run_quickstart, run_scripted_scene, summarize_state


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

    def test_scene_action_aliases_support_chinese_input(self) -> None:
        output = run_scripted_scene(seed=1, actions=["观察四周", "检查钟绳"])

        self.assertIn("The chapel is cold.", output)
        self.assertIn("Black ash clings", output)

    def test_scripted_scene_can_save_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            output = run_scripted_scene(seed=1, actions=["inspect rope", "quit"], save_state_path=path)

            self.assertTrue(path.exists())
            self.assertIn("Saved campaign state", output)

    def test_state_summary_reads_saved_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            run_scripted_scene(seed=1, actions=["inspect rope", "quit"], save_state_path=path)
            summary = summarize_state(path)

        self.assertIn("Campaign: The Bell Beneath Ashford", summary)
        self.assertIn("Characters: 1", summary)
        self.assertIn("Clues: 1/1 discovered", summary)

    def test_initiative_demo_prints_order_and_turns(self) -> None:
        output = run_initiative_demo(seed=1, rounds=1)

        self.assertIn("Initiative order:", output)
        self.assertIn("Mira Voss: d20 19 + 1 = 20", output)
        self.assertIn("Round 1: Mira Voss", output)


if __name__ == "__main__":
    unittest.main()
