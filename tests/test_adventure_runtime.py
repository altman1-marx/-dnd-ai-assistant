import unittest

from dnd_ai_assistant.adventure import AdventureDefinition, create_adventure_template
from dnd_ai_assistant.adventure_importer import campaign_from_adventure
from dnd_ai_assistant.adventure_runtime import AdventureRuntime, describe_current_location, handle_adventure_action


class AdventureRuntimeTests(unittest.TestCase):
    def test_describe_current_location_shows_exits_and_npcs(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        describe_current_location(runtime)
        output = runtime.flush()

        self.assertIn("Village Square", output)
        self.assertIn("Exits: Old Road", output)
        self.assertIn("People here: Mayor Elin", output)

    def test_move_action_updates_current_location_and_records_event(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        keep_going = handle_adventure_action(runtime, "go old road")
        output = runtime.flush()

        self.assertTrue(keep_going)
        self.assertEqual(campaign.current_location_id, "loc_old_road")
        self.assertIn("Old Road", output)
        self.assertTrue(any("Moved to location: Old Road" in event.content for event in campaign.session_log))

    def test_move_rejects_unconnected_location(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "go moonlit glade")

        self.assertEqual(campaign.current_location_id, "loc_village_square")
        self.assertIn("cannot reach", runtime.flush())

    def test_inspect_reveals_current_location_clues(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "inspect")
        output = runtime.flush()

        clue = campaign.clues["clue_moon_ash"]
        self.assertTrue(clue.discovered)
        self.assertIn("Clue found - Moonlit Ash", output)
        self.assertTrue(any("Clue revealed: Moonlit Ash" in event.content for event in campaign.session_log))

    def test_inspect_reports_when_no_new_clues_remain(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "inspect")
        runtime.flush()
        handle_adventure_action(runtime, "inspect")

        self.assertIn("no new clues", runtime.flush())

    def test_quit_stops_runtime(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        self.assertFalse(handle_adventure_action(runtime, "quit"))


if __name__ == "__main__":
    unittest.main()
