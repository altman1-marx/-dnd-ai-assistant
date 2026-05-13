import unittest
import tempfile
from pathlib import Path

from dnd_ai_assistant.scenario import SceneDefinition, create_scene_template, load_scene, validate_scene, write_scene_template


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
        self.assertEqual(scene.actions["inspect"]["handler"], "inspect_clue")

    def test_validate_scene_reports_invalid_action_references(self) -> None:
        raw = create_scene_template("Broken Road")
        raw["actions"]["inspect"]["check_id"] = "missing_check"
        raw["actions"]["look"]["text"] = "missing_text"

        with self.assertRaises(ValueError) as context:
            validate_scene(SceneDefinition(raw))

        message = str(context.exception)
        self.assertIn("actions.look.text references unknown text: missing_text", message)
        self.assertIn("actions.inspect.check_id references unknown check: missing_check", message)


if __name__ == "__main__":
    unittest.main()
