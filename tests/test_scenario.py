import unittest

from dnd_ai_assistant.scenario import SceneDefinition, load_scene, validate_scene


class ScenarioTests(unittest.TestCase):
    def test_load_default_scene(self) -> None:
        scene = load_scene()

        self.assertEqual(scene.campaign["title"], "The Bell Beneath Ashford")
        self.assertEqual(scene.hero["name"], "Kael")
        self.assertEqual(scene.location["name"], "Old Chapel")
        self.assertEqual(scene.checks["inspect_rope"]["dc"], 15)

    def test_validate_scene_reports_missing_keys(self) -> None:
        with self.assertRaises(ValueError) as context:
            validate_scene(SceneDefinition({"campaign": {}}))

        self.assertIn("Missing top-level key: hero", str(context.exception))


if __name__ == "__main__":
    unittest.main()
