import unittest

from dnd_ai_assistant.adventure import AdventureDefinition, create_adventure_template
from dnd_ai_assistant.adventure_map import location_adjacency, render_mermaid_map, render_text_map


class AdventureMapTests(unittest.TestCase):
    def test_location_adjacency_is_bidirectional(self) -> None:
        adventure = AdventureDefinition(create_adventure_template("Moonlit Road"))

        adjacency = location_adjacency(adventure)

        self.assertIn("loc_old_road", adjacency["loc_village_square"])
        self.assertIn("loc_village_square", adjacency["loc_old_road"])

    def test_render_text_map_marks_start_and_final_locations(self) -> None:
        adventure = AdventureDefinition(create_adventure_template("Moonlit Road"))

        output = render_text_map(adventure)

        self.assertIn("[start] Village Square", output)
        self.assertIn("[final] Moonlit Glade", output)
        self.assertIn("requires Moonlit Ash", output)
        self.assertIn("Old Road", output)

    def test_render_mermaid_map_outputs_graph_edges_once(self) -> None:
        adventure = AdventureDefinition(create_adventure_template("Moonlit Road"))

        output = render_mermaid_map(adventure)

        self.assertIn("graph TD", output)
        self.assertEqual(output.count("loc_village_square"), 1)
        self.assertIn("loc_old_road", output)
        self.assertIn("requires Moonlit Ash", output)


if __name__ == "__main__":
    unittest.main()
