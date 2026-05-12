import json
import tempfile
import unittest
from pathlib import Path

from dnd_ai_assistant.adventure import create_adventure_template
from dnd_ai_assistant.adventure_generator import (
    AdventureRequest,
    adventure_from_model_text,
    build_adventure_prompt,
    extract_json_object,
    write_adventure_from_model_text,
)


class AdventureGeneratorTests(unittest.TestCase):
    def test_build_adventure_prompt_contains_request_and_schema(self) -> None:
        prompt = build_adventure_prompt(
            AdventureRequest(
                premise="A bell rings under a ruined chapel.",
                party_level=2,
                player_count=3,
                duration_hours=2,
                tone="dark fantasy investigation",
            )
        )

        self.assertIn("Return only valid JSON", prompt)
        self.assertIn("A bell rings under a ruined chapel.", prompt)
        self.assertIn('"start_location_id"', prompt)
        self.assertIn("Party level: 2", prompt)

    def test_extract_json_object_accepts_markdown_fenced_json(self) -> None:
        raw = create_adventure_template("Moonlit Road")
        text = "```json\n" + json.dumps(raw) + "\n```"

        extracted = extract_json_object(text)

        self.assertEqual(json.loads(extracted)["campaign"]["title"], "Moonlit Road")

    def test_adventure_from_model_text_validates_output(self) -> None:
        raw = create_adventure_template("Moonlit Road")

        adventure = adventure_from_model_text(json.dumps(raw))

        self.assertEqual(adventure.campaign["title"], "Moonlit Road")

    def test_write_adventure_from_model_text_writes_clean_json(self) -> None:
        raw = create_adventure_template("Moonlit Road")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adventure.json"
            adventure = write_adventure_from_model_text(json.dumps(raw), path)
            written = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(adventure.campaign["title"], "Moonlit Road")
        self.assertEqual(written["campaign"]["title"], "Moonlit Road")

    def test_adventure_from_model_text_rejects_invalid_json_shape(self) -> None:
        with self.assertRaises(ValueError):
            adventure_from_model_text('{"campaign": {}}')


if __name__ == "__main__":
    unittest.main()
