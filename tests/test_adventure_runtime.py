import random
import unittest

from dnd_ai_assistant.adventure import AdventureDefinition, create_adventure_template
from dnd_ai_assistant.adventure_importer import campaign_from_adventure
from dnd_ai_assistant.adventure_runtime import AdventureRuntime, describe_current_location, handle_adventure_action
from dnd_ai_assistant.core.character import Character


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

    def test_runtime_uses_campaign_action_aliases(self) -> None:
        raw = create_adventure_template("Moonlit Road")
        raw["runtime_actions"] = {
            "study": {"aliases": ["study"], "handler": "inspect"},
            "travel": {"aliases": ["travel"], "handler": "move"},
            "quit": {"aliases": ["stop"], "handler": "quit"},
        }
        campaign = campaign_from_adventure(AdventureDefinition(raw))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "study")
        runtime.flush()
        handle_adventure_action(runtime, "travel old road")

        self.assertTrue(campaign.clues["clue_moon_ash"].discovered)
        self.assertEqual(campaign.current_location_id, "loc_old_road")

    def test_help_lists_runtime_actions(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "help")

        self.assertIn("Available actions", runtime.flush())

    def test_talk_action_speaks_with_current_location_npc(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "talk mayor")
        output = runtime.flush()

        self.assertIn("Mayor Elin:", output)
        self.assertIn("missing travelers", output)
        self.assertTrue(any(event.actor == "Mayor Elin" for event in campaign.session_log))

    def test_talk_action_reports_missing_npc(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "talk stranger")

        self.assertIn("not here", runtime.flush())

    def test_talk_action_reports_empty_location(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        campaign.clues["clue_moon_ash"].discovered = True
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "go old road")
        runtime.flush()
        handle_adventure_action(runtime, "talk")

        self.assertIn("no one here", runtime.flush())

    def test_move_rejects_unconnected_location(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "go moonlit glade")

        self.assertEqual(campaign.current_location_id, "loc_village_square")
        self.assertIn("cannot reach", runtime.flush())

    def test_move_rejects_location_when_required_clue_is_missing(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "go old road")
        runtime.flush()
        handle_adventure_action(runtime, "go moonlit glade")
        output = runtime.flush()

        self.assertEqual(campaign.current_location_id, "loc_old_road")
        self.assertIn("Find more clues", output)

    def test_move_allows_location_when_required_clue_is_discovered(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "inspect")
        runtime.flush()
        handle_adventure_action(runtime, "go old road")
        runtime.flush()
        handle_adventure_action(runtime, "go moonlit glade")

        self.assertEqual(campaign.current_location_id, "loc_moonlit_glade")
        self.assertIn("Moonlit Glade", runtime.flush())

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

    def test_inspect_uses_clue_skill_check_when_character_exists(self) -> None:
        raw = create_adventure_template("Moonlit Road")
        raw["clues"][0]["check"] = {"skill": "survival", "dc": 10, "mode": "normal", "label": "Survival"}
        campaign = campaign_from_adventure(AdventureDefinition(raw))
        campaign.add_character(_scout())
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "inspect")
        output = runtime.flush()

        self.assertTrue(campaign.clues["clue_moon_ash"].discovered)
        self.assertIn("rolls Survival", output)
        self.assertIn("success", output)

    def test_inspect_keeps_checked_clue_hidden_on_failure(self) -> None:
        raw = create_adventure_template("Moonlit Road")
        raw["clues"][0]["check"] = {"skill": "survival", "dc": 20, "mode": "normal", "label": "Survival"}
        campaign = campaign_from_adventure(AdventureDefinition(raw))
        campaign.add_character(_scout())
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "inspect")
        output = runtime.flush()

        self.assertFalse(campaign.clues["clue_moon_ash"].discovered)
        self.assertIn("failure", output)
        self.assertIn("do not find anything new", output)

    def test_quit_stops_runtime(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        self.assertFalse(handle_adventure_action(runtime, "quit"))


def _scout() -> Character:
    return Character(
        name="Kael",
        player_name="Player",
        class_name="Ranger",
        level=1,
        ancestry="Human",
        ability_scores={"str": 10, "dex": 14, "con": 12, "int": 10, "wis": 16, "cha": 8},
        armor_class=14,
        max_hp=12,
        current_hp=12,
        skill_proficiencies={"survival"},
    )


if __name__ == "__main__":
    unittest.main()
