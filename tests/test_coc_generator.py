import json
import tempfile
import unittest
from pathlib import Path

from dnd_ai_assistant.ai_provider import MockProvider
from dnd_ai_assistant.coc_generator import (
    COCScenarioRequest,
    build_coc_scenario_prompt,
    coc_scenario_from_model_text,
    generate_coc_scenario_file,
    generate_coc_scenario_text,
    write_coc_scenario_from_model_text,
)
from dnd_ai_assistant.coc_runtime import create_sample_coc_scenario
from dnd_ai_assistant.coc_serialization import coc_scenario_to_dict


class SequenceProvider:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []

    def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.responses.pop(0)


class COCGeneratorTests(unittest.TestCase):
    def test_build_coc_scenario_prompt_contains_request_and_schema(self) -> None:
        prompt = build_coc_scenario_prompt(
            COCScenarioRequest(
                premise="A lighthouse bell rings under a black tide.",
                investigator_occupation="Journalist",
                location_count=3,
                clue_count=5,
                npc_count=2,
            )
        )

        self.assertIn("Call of Cthulhu 7e", prompt)
        self.assertIn("Return only valid JSON", prompt)
        self.assertIn("lighthouse bell", prompt)
        self.assertIn("Journalist", prompt)
        self.assertIn('"locations"', prompt)
        self.assertIn('"current_location_id"', prompt)
        self.assertIn('"evidence"', prompt)
        self.assertIn('"exit_requirements"', prompt)
        self.assertIn('"required_clue_ids"', prompt)
        self.assertIn('"completion_requirements"', prompt)
        self.assertIn('"failure_text"', prompt)
        self.assertIn('"failure_evidence"', prompt)

    def test_coc_scenario_from_model_text_accepts_fenced_json(self) -> None:
        raw = coc_scenario_to_dict(create_sample_coc_scenario())
        text = "```json\n" + json.dumps(raw) + "\n```"

        scenario = coc_scenario_from_model_text(text)

        self.assertEqual(scenario.title, "The Lantern Under Briar House")
        self.assertEqual(scenario.current_location_id, "study")

    def test_write_coc_scenario_from_model_text_writes_clean_json(self) -> None:
        raw = coc_scenario_to_dict(create_sample_coc_scenario())

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "coc.json"
            scenario = write_coc_scenario_from_model_text(json.dumps(raw), path)
            written = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(scenario.title, "The Lantern Under Briar House")
        self.assertIn("locations", written)

    def test_generate_coc_scenario_text_repairs_invalid_first_response(self) -> None:
        raw = coc_scenario_to_dict(create_sample_coc_scenario())
        provider = SequenceProvider(['{"title": "Broken"}', json.dumps(raw)])

        text = generate_coc_scenario_text(COCScenarioRequest(premise="A damp house."), provider, max_attempts=2)

        self.assertEqual(json.loads(text)["title"], "The Lantern Under Briar House")
        self.assertEqual(len(provider.prompts), 2)
        self.assertIn("Validation error:", provider.prompts[1])

    def test_generate_coc_scenario_text_can_require_review_ok(self) -> None:
        thin = coc_scenario_to_dict(create_sample_coc_scenario())
        thin["clues"] = thin["clues"][:1]
        thin["completion_requirements"] = {}
        thin["locations"][0]["exit_requirements"] = {}
        rich = coc_scenario_to_dict(create_sample_coc_scenario())
        provider = SequenceProvider([json.dumps(thin), json.dumps(rich)])

        text = generate_coc_scenario_text(
            COCScenarioRequest(premise="A damp house."),
            provider,
            max_attempts=2,
            require_review_ok=True,
        )

        self.assertEqual(json.loads(text)["title"], "The Lantern Under Briar House")
        self.assertEqual(len(provider.prompts), 2)
        self.assertIn("COC scenario review did not pass", provider.prompts[1])

    def test_generate_coc_scenario_text_fails_after_max_attempts(self) -> None:
        provider = SequenceProvider(['{"title": "Broken"}'])

        with self.assertRaisesRegex(ValueError, "after 1 attempt"):
            generate_coc_scenario_text(COCScenarioRequest(premise="A damp house."), provider, max_attempts=1)

    def test_generate_coc_scenario_file_uses_provider_and_writes_output(self) -> None:
        raw = coc_scenario_to_dict(create_sample_coc_scenario())

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "coc.json"
            scenario = generate_coc_scenario_file(
                COCScenarioRequest(premise="A damp house."),
                MockProvider("```json\n" + json.dumps(raw) + "\n```"),
                path,
            )

        self.assertEqual(scenario.title, "The Lantern Under Briar House")

    def test_coc_scenario_request_validates_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "Premise"):
            COCScenarioRequest(premise=" ")
        with self.assertRaisesRegex(ValueError, "Location count"):
            COCScenarioRequest(premise="A house.", location_count=0)


if __name__ == "__main__":
    unittest.main()
