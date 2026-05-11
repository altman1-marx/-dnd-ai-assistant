import unittest

from dnd_ai_assistant.demo import run_quickstart


class DemoTests(unittest.TestCase):
    def test_quickstart_contains_expected_sections(self) -> None:
        output = run_quickstart(seed=1)

        self.assertIn("Campaign: The Bell Beneath Ashford", output)
        self.assertIn("Characters:", output)
        self.assertIn("Revealed clues:", output)
        self.assertIn("d20 rolls: 5, 19", output)
        self.assertIn("total: 23", output)
        self.assertIn("[System] Kael rolled 23 vs DC 15: success.", output)


if __name__ == "__main__":
    unittest.main()

