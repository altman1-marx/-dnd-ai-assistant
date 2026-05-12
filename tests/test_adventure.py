import tempfile
import unittest
from pathlib import Path

from dnd_ai_assistant.adventure import (
    AdventureDefinition,
    create_adventure_template,
    load_adventure,
    validate_adventure,
    write_adventure_template,
)


class AdventureTests(unittest.TestCase):
    def test_template_is_valid(self) -> None:
        adventure = AdventureDefinition(create_adventure_template("Moonlit Road"))

        self.assertEqual(validate_adventure(adventure), [])
        self.assertEqual(adventure.campaign["title"], "Moonlit Road")
        self.assertEqual(adventure.start_location_id, "loc_village_square")

    def test_write_and_load_adventure_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adventure.json"
            write_adventure_template(path, "Goblin Road")
            adventure = load_adventure(path)

        self.assertEqual(adventure.campaign["title"], "Goblin Road")
        self.assertEqual(len(adventure.locations), 3)

    def test_validate_adventure_reports_unknown_location_references(self) -> None:
        raw = create_adventure_template("Broken Road")
        raw["clues"][0]["location_id"] = "loc_missing"

        with self.assertRaises(ValueError) as context:
            validate_adventure(AdventureDefinition(raw))

        self.assertIn("Unknown location id for clues.clue_moon_ash.location_id", str(context.exception))

    def test_validate_adventure_reports_unreachable_locations(self) -> None:
        raw = create_adventure_template("Broken Road")
        raw["locations"].append(
            {
                "id": "loc_lonely_tower",
                "name": "Lonely Tower",
                "public_description": "A tower with no path leading to it.",
                "connections": [],
            }
        )

        with self.assertRaises(ValueError) as context:
            validate_adventure(AdventureDefinition(raw))

        self.assertIn("Unreachable locations from start: loc_lonely_tower", str(context.exception))

    def test_validate_adventure_reports_duplicate_ids(self) -> None:
        raw = create_adventure_template("Broken Road")
        raw["locations"].append(dict(raw["locations"][0]))

        with self.assertRaises(ValueError) as context:
            validate_adventure(AdventureDefinition(raw))

        self.assertIn("Duplicate locations id: loc_village_square", str(context.exception))

    def test_validate_adventure_reports_structural_errors_before_graph_checks(self) -> None:
        raw = create_adventure_template("Broken Road")
        raw["locations"] = "not a list"

        with self.assertRaises(ValueError) as context:
            validate_adventure(AdventureDefinition(raw))

        self.assertIn("locations must be a list", str(context.exception))

    def test_validate_adventure_reports_invalid_monster_entries(self) -> None:
        raw = create_adventure_template("Broken Road")
        raw["encounters"][0]["monsters"] = [{"name": "Ash Goblin"}]

        with self.assertRaises(ValueError) as context:
            validate_adventure(AdventureDefinition(raw))

        self.assertIn("Missing encounters[0].monsters[0] key: armor_class", str(context.exception))


if __name__ == "__main__":
    unittest.main()
