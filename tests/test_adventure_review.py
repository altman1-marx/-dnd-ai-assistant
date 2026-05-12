import unittest

from dnd_ai_assistant.adventure import AdventureDefinition, create_adventure_template
import json

from dnd_ai_assistant.adventure_review import (
    adventure_review_to_dict,
    render_adventure_review,
    render_adventure_review_json,
    review_adventure,
)


class AdventureReviewTests(unittest.TestCase):
    def test_review_warns_about_thin_template_content(self) -> None:
        adventure = AdventureDefinition(create_adventure_template("Moonlit Road"))

        review = review_adventure(adventure)

        self.assertFalse(review.ok)
        self.assertIn("Add at least two clues", review.warnings[0])
        self.assertTrue(any("Location count" in strength for strength in review.strengths))

    def test_review_accepts_richer_short_adventure(self) -> None:
        raw = create_adventure_template("Moonlit Road")
        raw["clues"].append(
            {
                "id": "clue_arch_splinter",
                "title": "Arch Splinter",
                "public_text": "A silver splinter hums near the old road.",
                "dm_secret": "It came from the moonlit glade arch.",
                "location_id": "loc_old_road",
            }
        )
        raw["encounters"][0]["monsters"] = [{"name": "Sprite", "armor_class": 13, "max_hp": 7}]

        review = review_adventure(AdventureDefinition(raw))

        self.assertTrue(review.ok)
        self.assertTrue(any("multiple clues" in strength for strength in review.strengths))

    def test_render_adventure_review_outputs_sections(self) -> None:
        adventure = AdventureDefinition(create_adventure_template("Moonlit Road"))

        output = render_adventure_review(adventure)

        self.assertIn("Adventure review: Moonlit Road", output)
        self.assertIn("Warnings:", output)
        self.assertIn("Strengths:", output)

    def test_render_adventure_review_json_outputs_counts(self) -> None:
        adventure = AdventureDefinition(create_adventure_template("Moonlit Road"))

        data = json.loads(render_adventure_review_json(adventure))

        self.assertEqual(data["title"], "Moonlit Road")
        self.assertEqual(data["counts"]["locations"], 3)
        self.assertIn("warnings", data)

    def test_adventure_review_to_dict_is_machine_readable(self) -> None:
        adventure = AdventureDefinition(create_adventure_template("Moonlit Road"))

        data = adventure_review_to_dict(adventure)

        self.assertFalse(data["ok"])
        self.assertEqual(data["counts"]["encounters"], 1)


if __name__ == "__main__":
    unittest.main()
