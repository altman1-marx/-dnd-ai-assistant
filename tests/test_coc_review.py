import json
import unittest

from dnd_ai_assistant.coc_review import (
    coc_review_to_dict,
    render_coc_review,
    render_coc_review_json,
    review_coc_scenario,
)
from dnd_ai_assistant.coc_runtime import create_sample_coc_scenario


class COCReviewTests(unittest.TestCase):
    def test_review_accepts_sample_scenario(self) -> None:
        scenario = create_sample_coc_scenario()

        review = review_coc_scenario(scenario)

        self.assertTrue(review.ok)
        self.assertTrue(any("reachable" in strength for strength in review.strengths))
        self.assertTrue(any("SAN loss" in strength for strength in review.strengths))
        self.assertTrue(any("Exit requirements" in strength for strength in review.strengths))
        self.assertTrue(any("Completion requirements" in strength for strength in review.strengths))

    def test_review_warns_about_thin_scenario(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.locations = {}
        scenario.clues = scenario.clues[:1]
        scenario.npcs = []
        scenario.ending_text = ""

        review = review_coc_scenario(scenario)

        self.assertFalse(review.ok)
        self.assertTrue(any("Add at least three clues" in warning for warning in review.warnings))
        self.assertTrue(any(finding.code == "ending_text" for finding in review.findings))

    def test_review_warns_about_unreachable_location(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.locations["attic"] = type(next(iter(scenario.locations.values())))(
            id="attic",
            name="Locked Attic",
            description="Dust waits above.",
            exits={},
        )

        review = review_coc_scenario(scenario)

        self.assertFalse(review.ok)
        self.assertTrue(any(finding.code == "unreachable_locations" for finding in review.findings))

    def test_review_warns_about_high_sanity_loss(self) -> None:
        scenario = create_sample_coc_scenario()
        for clue in scenario.clues:
            clue.sanity_loss = 5

        review = review_coc_scenario(scenario)

        self.assertFalse(review.ok)
        self.assertTrue(any(finding.code == "sanity_loss_budget" for finding in review.findings))

    def test_review_warns_about_bad_exit_requirement_references(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.locations["study"].exit_requirements["cellar"] = {
            "required_clue_ids": ["missing_clue"],
            "required_evidence": ["Missing evidence"],
            "message": "The way is still hidden.",
        }

        review = review_coc_scenario(scenario)

        self.assertFalse(review.ok)
        self.assertTrue(any(finding.code == "exit_requirement_clue" for finding in review.findings))
        self.assertTrue(any(finding.code == "exit_requirement_evidence" for finding in review.findings))

    def test_review_warns_about_bad_completion_requirement_references(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.completion_requirements = {
            "required_clue_ids": ["missing_clue"],
            "required_evidence": ["Missing evidence"],
            "required_location_ids": ["attic"],
            "required_npc_ids": ["missing_npc"],
        }

        review = review_coc_scenario(scenario)

        self.assertFalse(review.ok)
        self.assertTrue(any(finding.code == "completion_requirement_clue" for finding in review.findings))
        self.assertTrue(any(finding.code == "completion_requirement_evidence" for finding in review.findings))
        self.assertTrue(any(finding.code == "completion_requirement_location" for finding in review.findings))
        self.assertTrue(any(finding.code == "completion_requirement_npc" for finding in review.findings))


    def test_render_coc_review_outputs_sections(self) -> None:
        scenario = create_sample_coc_scenario()

        output = render_coc_review(scenario)

        self.assertIn("COC scenario review", output)
        self.assertIn("Status: OK", output)
        self.assertIn("Strengths:", output)

    def test_render_coc_review_json_outputs_counts(self) -> None:
        scenario = create_sample_coc_scenario()

        data = json.loads(render_coc_review_json(scenario))

        self.assertEqual(data["title"], scenario.title)
        self.assertEqual(data["counts"]["locations"], 2)
        self.assertEqual(data["counts"]["clues"], 4)
        self.assertEqual(data["counts"]["completion_goals"], 4)
        self.assertIn("findings", data)

    def test_coc_review_to_dict_is_machine_readable(self) -> None:
        scenario = create_sample_coc_scenario()

        data = coc_review_to_dict(scenario)

        self.assertTrue(data["ok"])
        self.assertEqual(data["counts"]["npcs"], 1)


if __name__ == "__main__":
    unittest.main()
