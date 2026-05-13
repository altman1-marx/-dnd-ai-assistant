import json
import tempfile
import unittest
from pathlib import Path

from dnd_ai_assistant.adventure import create_adventure_template
from dnd_ai_assistant.ai_provider import MockProvider
from dnd_ai_assistant.adventure_generator import (
    AdventureRequest,
    adventure_from_model_text,
    build_repair_prompt,
    build_adventure_prompt,
    extract_json_object,
    generate_adventure_files,
    generate_adventure_text,
    write_adventure_from_model_text,
    write_campaign_from_model_text,
)


class SequenceProvider:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []

    def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.responses.pop(0)


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
        self.assertIn('"check"', prompt)
        self.assertIn('"requires_clue_ids"', prompt)
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

    def test_write_campaign_from_model_text_writes_adventure_and_campaign(self) -> None:
        raw = create_adventure_template("Moonlit Road")

        with tempfile.TemporaryDirectory() as tmp:
            adventure_path = Path(tmp) / "adventure.json"
            campaign_path = Path(tmp) / "campaign.json"
            adventure, campaign = write_campaign_from_model_text(
                json.dumps(raw),
                adventure_path,
                campaign_path,
            )
            written_campaign = json.loads(campaign_path.read_text(encoding="utf-8"))

        self.assertEqual(adventure.campaign["title"], "Moonlit Road")
        self.assertEqual(campaign.title, "Moonlit Road")
        self.assertEqual(written_campaign["title"], "Moonlit Road")

    def test_generate_adventure_files_uses_provider_and_writes_outputs(self) -> None:
        raw = create_adventure_template("Moonlit Road")
        provider = MockProvider("```json\n" + json.dumps(raw) + "\n```")

        with tempfile.TemporaryDirectory() as tmp:
            adventure_path = Path(tmp) / "adventure.json"
            campaign_path = Path(tmp) / "campaign.json"
            adventure, campaign, review = generate_adventure_files(
                AdventureRequest(premise="A moonlit road."),
                provider,
                adventure_path,
                campaign_path,
            )

        self.assertEqual(adventure.campaign["title"], "Moonlit Road")
        self.assertEqual(campaign.title, "Moonlit Road")
        self.assertFalse(review.ok)

    def test_generate_adventure_text_repairs_invalid_first_response(self) -> None:
        raw = create_adventure_template("Moonlit Road")
        provider = SequenceProvider(['{"campaign": {}}', json.dumps(raw)])

        text = generate_adventure_text(AdventureRequest(premise="A moonlit road."), provider, max_attempts=2)

        self.assertEqual(json.loads(text)["campaign"]["title"], "Moonlit Road")
        self.assertEqual(len(provider.prompts), 2)
        self.assertIn("Validation error:", provider.prompts[1])

    def test_generate_adventure_text_fails_after_max_attempts(self) -> None:
        provider = SequenceProvider(['{"campaign": {}}', '{"campaign": {}}'])

        with self.assertRaisesRegex(ValueError, "after 2 attempt"):
            generate_adventure_text(AdventureRequest(premise="A moonlit road."), provider, max_attempts=2)

    def test_build_repair_prompt_includes_error_and_previous_response(self) -> None:
        prompt = build_repair_prompt("bad output", "Missing top-level key: locations")

        self.assertIn("Missing top-level key: locations", prompt)
        self.assertIn("bad output", prompt)


if __name__ == "__main__":
    unittest.main()
