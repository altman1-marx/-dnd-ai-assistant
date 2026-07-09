import unittest

from dnd_ai_assistant.api import (
    APIState,
    coc_briefing,
    coc_player_card,
    create_coc_demo,
    run_coc_action,
)
from dnd_ai_assistant.demo import run_scripted_coc


class COCPlayabilityTests(unittest.TestCase):
    def test_sample_coc_scenario_can_reach_ending_from_cli_actions(self) -> None:
        output = run_scripted_coc(
            seed=5,
            actions=["look", "skills", "inspect portrait", "go cellar", "inspect lantern", "conclude"],
        )

        self.assertIn("Eleanor Vale skills", output)
        self.assertIn("Clue found - Scratched Portrait", output)
        self.assertIn("You move to Briar House Cellar", output)
        self.assertIn("Clue found - Black Wick", output)
        self.assertIn("The lantern waits below", output)
        self.assertIn("case is already concluded", output)

    def test_api_coc_table_tools_support_resume_and_player_view(self) -> None:
        state = APIState()
        scenario_id = create_coc_demo(state)["scenario_id"]

        run_coc_action(state, scenario_id, "inspect portrait", seed=5)
        run_coc_action(state, scenario_id, "take damage 1d4", seed=5)
        run_coc_action(state, scenario_id, "spend luck 5", seed=5)
        run_coc_action(state, scenario_id, "recover luck 10", seed=5)
        player_card = coc_player_card(state, scenario_id)
        briefing = coc_briefing(state, scenario_id)

        self.assertEqual(player_card["investigator"]["name"], "Eleanor Vale")
        self.assertLess(
            player_card["investigator"]["hp"]["current"],
            player_card["investigator"]["hp"]["max"],
        )
        self.assertEqual(player_card["investigator"]["luck"], 55)
        self.assertIn("Scratched Portrait", [clue["title"] for clue in player_card["discovered_clues"]])
        self.assertNotIn("hidden_clues", player_card)
        self.assertIn("COC Keeper Briefing", briefing["text"])
        self.assertTrue(briefing["next_actions"])


if __name__ == "__main__":
    unittest.main()