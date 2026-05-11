import unittest

from dnd_ai_assistant.scenario import load_scene


class ScenarioTests(unittest.TestCase):
    def test_load_default_scene(self) -> None:
        scene = load_scene()

        self.assertEqual(scene.campaign["title"], "The Bell Beneath Ashford")
        self.assertEqual(scene.hero["name"], "Kael")
        self.assertEqual(scene.location["name"], "Old Chapel")
        self.assertEqual(scene.checks["inspect_rope"]["dc"], 15)


if __name__ == "__main__":
    unittest.main()

