import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from dnd_ai_assistant.adventure import AdventureDefinition, create_adventure_template
from dnd_ai_assistant.adventure_importer import campaign_from_adventure
from dnd_ai_assistant.core.serialization import load_campaign, save_campaign
from dnd_ai_assistant.demo import main, run_combat_demo, run_initiative_demo, run_quickstart, run_scripted_scene, summarize_state
from dnd_ai_assistant.scenario import create_scene_template


class DemoTests(unittest.TestCase):
    def test_quickstart_contains_expected_sections(self) -> None:
        output = run_quickstart(seed=1)

        self.assertIn("Campaign: The Bell Beneath Ashford", output)
        self.assertIn("Characters:", output)
        self.assertIn("Revealed clues:", output)
        self.assertIn("d20 rolls: 5, 19", output)
        self.assertIn("total: 23", output)
        self.assertIn("[System] Kael rolled Perception 23 vs DC 15: success.", output)

    def test_scripted_scene_resolves_basic_actions(self) -> None:
        output = run_scripted_scene(seed=1, actions=["look around", "inspect rope", "open stairway", "quit"])

        self.assertIn("DM: Kael stands inside the Old Chapel.", output)
        self.assertIn("Player: inspect rope", output)
        self.assertIn("System: Perception with advantage vs DC 15 -> rolls (5, 19), total 23.", output)
        self.assertIn("DM: The seal grinds open.", output)
        self.assertIn("DM: The scene pauses here.", output)

    def test_stairway_requires_clue_first(self) -> None:
        output = run_scripted_scene(seed=1, actions=["open stairway"])

        self.assertIn("The stairway seal does not move", output)

    def test_scene_action_aliases_support_chinese_input(self) -> None:
        output = run_scripted_scene(seed=1, actions=["观察四周", "检查钟绳"])

        self.assertIn("The chapel is cold.", output)
        self.assertIn("Black ash clings", output)

    def test_scripted_scene_uses_data_driven_action_handlers(self) -> None:
        raw = create_scene_template("Data Road")
        raw["text"]["listen"] = "You hear a bell under the floor."
        raw["actions"]["listen"] = {"aliases": ["listen", "hear"], "handler": "say_text", "text": "listen"}
        raw["actions"]["inspect"]["aliases"] = ["study rope"]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scene.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            output = run_scripted_scene(seed=1, actions=["listen", "study rope"], scene_path=path)

        self.assertIn("You hear a bell under the floor.", output)
        self.assertIn("Describe the first inspection result.", output)

    def test_scripted_scene_can_save_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            output = run_scripted_scene(seed=1, actions=["inspect rope", "quit"], save_state_path=path)

            self.assertTrue(path.exists())
            self.assertIn("Saved campaign state", output)

    def test_state_summary_reads_saved_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            run_scripted_scene(seed=1, actions=["inspect rope", "quit"], save_state_path=path)
            summary = summarize_state(path)

        self.assertIn("Campaign: The Bell Beneath Ashford", summary)
        self.assertIn("Characters: 1", summary)
        self.assertIn("Current location: Old Chapel", summary)
        self.assertIn("Clues: 1/1 discovered", summary)

    def test_state_summary_shows_active_combat(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        campaign.active_combat = {
            "encounter_id": "enc_lantern_sprites",
            "round": 1,
            "turn": "Kael",
            "initiative": [{"name": "Kael", "initiative_total": 18, "armor_class": 14, "current_hp": 12}],
            "resources": {"Kael": {"action": True, "bonus_action": False, "reaction": True, "movement": 20}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            save_campaign(campaign, path)
            summary = summarize_state(path)

        self.assertIn("Active combat:", summary)
        self.assertIn("Turn: Kael", summary)
        self.assertIn("Kael: 18 initiative, AC 14, HP 12", summary)
        self.assertIn("Current resources: action=True, bonus_action=False, reaction=True, movement=20", summary)

    def test_initiative_demo_prints_order_and_turns(self) -> None:
        output = run_initiative_demo(seed=1, rounds=1)

        self.assertIn("Initiative order:", output)
        self.assertIn("Ash Goblin: d20 19 + 2 = 21", output)
        self.assertIn("Round 1: Ash Goblin", output)

    def test_combat_demo_resolves_scene_attack(self) -> None:
        output = run_combat_demo(seed=1)

        self.assertIn("Encounter: Ash Goblin in the Crypt", output)
        self.assertIn("Attacker: Ash Goblin", output)
        self.assertIn("Attack total: 9", output)
        self.assertIn("Hit: False", output)
        self.assertIn("Target HP: 18/18", output)

    def test_combat_demo_can_save_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "combat_state.json"
            output = run_combat_demo(seed=1, save_state_path=path)

            self.assertTrue(path.exists())
            self.assertIn("Saved campaign state", output)

    def test_play_adventure_state_cli_moves_and_saves(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "campaign.json"
            save_campaign(campaign, state_path)
            argv = [
                "dnd-ai-assistant",
                "play-adventure-state",
                str(state_path),
                "--action",
                "go old road",
                "--save-state",
                str(state_path),
            ]

            with patch("sys.argv", argv), patch("builtins.print"):
                exit_code = main()
            loaded = load_campaign(state_path)

        self.assertEqual(exit_code, 0)
        self.assertEqual(loaded.current_location_id, "loc_old_road")

    def test_play_adventure_state_cli_can_add_sample_character(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "campaign.json"
            save_campaign(campaign, state_path)
            argv = [
                "dnd-ai-assistant",
                "play-adventure-state",
                str(state_path),
                "--seed",
                "5",
                "--add-sample-character",
                "--action",
                "look",
                "--save-state",
                str(state_path),
            ]

            with patch("sys.argv", argv), patch("builtins.print"):
                exit_code = main()
            loaded = load_campaign(state_path)

        self.assertEqual(exit_code, 0)
        self.assertIn("Leth", loaded.characters)
        self.assertIsNotNone(loaded.characters["Leth"].spellcasting)
        self.assertEqual(loaded.characters["Leth"].spellcasting.available_slots(1), 4)

    def test_play_adventure_state_cli_runs_combat_spell_flow(self) -> None:
        raw = create_adventure_template("Moonlit Road")
        raw["encounters"][0]["monsters"] = [
            {
                "name": "Lantern Sprite",
                "armor_class": 13,
                "max_hp": 7,
                "current_hp": 7,
                "ability_scores": {"str": 8, "dex": 8, "con": 10, "int": 10, "wis": 10, "cha": 10},
            }
        ]
        campaign = campaign_from_adventure(AdventureDefinition(raw))
        campaign.clues["clue_moon_ash"].discovered = True
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "campaign.json"
            save_campaign(campaign, state_path)
            argv = [
                "dnd-ai-assistant",
                "play-adventure-state",
                str(state_path),
                "--seed",
                "5",
                "--add-sample-character",
                "--action",
                "go old road",
                "--action",
                "fight",
                "--action",
                "cast sacred flame sprite",
                "--save-state",
                str(state_path),
            ]

            with patch("sys.argv", argv), patch("builtins.print"):
                exit_code = main()
            loaded = load_campaign(state_path)

        self.assertEqual(exit_code, 0)
        self.assertIn("Leth", loaded.characters)
        self.assertIsNotNone(loaded.active_combat)
        self.assertLess(loaded.encounters["enc_lantern_sprites"].monsters[0].current_hp, 7)
        self.assertFalse(loaded.active_combat["resources"]["Leth"]["action"])

    def test_serve_api_cli_starts_server(self) -> None:
        argv = ["dnd-ai-assistant", "serve-api", "--host", "0.0.0.0", "--port", "8123"]

        with patch("sys.argv", argv), patch("builtins.print"), patch("dnd_ai_assistant.demo.run_server") as server:
            exit_code = main()

        self.assertEqual(exit_code, 0)
        server.assert_called_once_with("0.0.0.0", 8123)


if __name__ == "__main__":
    unittest.main()
