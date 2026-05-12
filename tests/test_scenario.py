import unittest
import tempfile
from pathlib import Path

from dnd_ai_assistant.scenario import SceneDefinition, load_scene, validate_scene, write_scene_template


class ScenarioTests(unittest.TestCase):
    def test_load_default_scene(self) -> None:
        scene = load_scene()

        self.assertEqual(scene.campaign["title"], "The Bell Beneath Ashford")
        self.assertEqual(scene.hero["name"], "Kael")
        self.assertEqual(scene.location["name"], "Old Chapel")
        self.assertEqual(scene.encounter["title"], "Ash Goblin in the Crypt")
        self.assertEqual(scene.checks["inspect_rope"]["skill"], "perception")
        self.assertEqual(scene.checks["inspect_rope"]["dc"], 15)

    def test_validate_scene_reports_missing_keys(self) -> None:
        with self.assertRaises(ValueError) as context:
            validate_scene(SceneDefinition({"campaign": {}}))

        self.assertIn("Missing top-level key: hero", str(context.exception))

    def test_write_scene_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scene.json"
            write_scene_template(path, "Goblin Road")
            scene = load_scene(path)

        self.assertEqual(scene.campaign["title"], "Goblin Road")
        self.assertEqual(scene.hero["name"], "Example Hero")


if __name__ == "__main__":
    unittest.main()
