import unittest
import tempfile
import json
from pathlib import Path
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dnd_ai_assistant.adventure import create_adventure_template
from dnd_ai_assistant.api import (
    APIError,
    APIState,
    add_sample_character,
    campaign_log,
    campaign_state,
    campaign_summary,
    coc_review,
    coc_summary,
    create_coc_demo,
    create_handler,
    create_demo_campaign,
    create_playable_demo_campaign,
    delete_campaign,
    health_status,
    generate_coc_scenario,
    import_adventure,
    import_coc_scenario,
    list_campaigns,
    list_coc_scenarios,
    load_campaigns_from_state_dir,
    route_request,
    run_campaign_action,
    run_coc_action,
    search_rules,
    suggest_coc_keeper_turn,
    suggest_dm_turn,
)
from dnd_ai_assistant.ai_provider import MockProvider
from dnd_ai_assistant.coc_runtime import create_sample_coc_scenario
from dnd_ai_assistant.coc_serialization import coc_scenario_to_dict
from dnd_ai_assistant.core.campaign import SessionEvent, Visibility
from dnd_ai_assistant.core.serialization import load_campaign
from dnd_ai_assistant.rules_corpus import RuleChunk, RuleCorpus


class FailingProvider:
    def generate_text(self, prompt: str) -> str:
        raise RuntimeError("provider exploded")


class APITests(unittest.TestCase):
    def _rules_corpus(self) -> RuleCorpus:
        return RuleCorpus(
            [
                RuleChunk(
                    source_id="test",
                    title="Test Rules",
                    section="Grappling",
                    text="A grapple uses the Attack action.",
                    url="https://example.test/grapple",
                    license="test",
                )
            ]
        )

    def test_import_adventure_stores_campaign(self) -> None:
        state = APIState()

        response = import_adventure(state, create_adventure_template("Moonlit Road"))

        self.assertIn(response["campaign_id"], state.campaigns)
        self.assertEqual(response["campaign"]["title"], "Moonlit Road")

    def test_health_status_reports_enabled_features(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = APIState(rules_corpus=self._rules_corpus(), ai_provider=MockProvider("ok"), state_dir=Path(tmp))
            create_demo_campaign(state)

            response = health_status(state)

        self.assertTrue(response["ok"])
        self.assertEqual(response["campaign_count"], 1)
        self.assertTrue(response["features"]["rules_search"])
        self.assertTrue(response["features"]["ai_dm"])
        self.assertTrue(response["features"]["persistent_state"])

    def test_create_demo_campaign_includes_combat_ready_encounter(self) -> None:
        state = APIState()

        response = create_demo_campaign(state)

        campaign = state.campaigns[response["campaign_id"]]
        monster = campaign.encounters["enc_lantern_sprites"].monsters[0]
        self.assertEqual(campaign.title, "Moonlit Road")
        self.assertEqual(monster.name, "Lantern Sprite")

    def test_create_playable_demo_campaign_adds_sample_character(self) -> None:
        state = APIState()

        response = create_playable_demo_campaign(state)

        campaign = state.campaigns[response["campaign_id"]]
        self.assertIn("Leth", campaign.characters)
        self.assertIn("Leth", response["campaign"]["characters"])

    def test_create_coc_demo_and_summary(self) -> None:
        state = APIState()

        response = create_coc_demo(state)
        summary = coc_summary(state, response["scenario_id"])

        self.assertIn(response["scenario_id"], state.coc_scenarios)
        self.assertEqual(summary["system_id"], "coc7e")
        self.assertFalse(summary["completed"])
        self.assertEqual(summary["investigator"]["name"], "Eleanor Vale")
        self.assertEqual(summary["location_id"], "study")
        self.assertEqual(summary["exits"][0]["name"], "cellar")
        self.assertEqual(summary["npcs"][0]["name"], "Mrs. Ember")
        self.assertEqual(summary["clue_count"], 6)
        self.assertEqual(summary["partial_clue_count"], 0)
        self.assertEqual(summary["inventory"], [])
        self.assertIn("go cellar", summary["available_actions"])
        self.assertIn("go garden", summary["available_actions"])
        self.assertIn("talk mrs. ember", summary["available_actions"])
        self.assertIn("inventory", summary["available_actions"])
        self.assertIn("conclude", summary["available_actions"])
        self.assertNotIn("first aid", summary["available_actions"])
        self.assertIn("inspect scratched portrait", summary["available_actions"])
        self.assertIn("search scratched portrait", summary["available_actions"])
        self.assertIn("inspect waterlogged journal bonus", summary["available_actions"])
        self.assertIn("search waterlogged journal penalty", summary["available_actions"])
        self.assertIn("read waterlogged journal", summary["available_actions"])
        self.assertIn("check library use bonus", summary["available_actions"])
        self.assertIn("check library use penalty", summary["available_actions"])
        self.assertIn("note <text>", summary["available_actions"])
        self.assertIn("keeper note <text>", summary["available_actions"])
        self.assertIn("san check 0/1d4", summary["available_actions"])

    def test_coc_summary_suggests_listen_actions_for_auditory_clues(self) -> None:
        state = APIState()
        response = create_coc_demo(state)
        scenario = state.coc_scenarios[response["scenario_id"]]
        scenario.current_location_id = "garden"

        summary = coc_summary(state, response["scenario_id"])

        self.assertIn("listen voices in the well", summary["available_actions"])
        self.assertIn("listen well whispers", summary["available_actions"])

    def test_coc_summary_suggests_first_aid_when_injured(self) -> None:
        state = APIState()
        scenario_id = create_coc_demo(state)["scenario_id"]
        state.coc_scenarios[scenario_id].investigator.apply_damage(2)

        summary = coc_summary(state, scenario_id)

        self.assertIn("first aid", summary["available_actions"])

    def test_coc_review_returns_quality_report(self) -> None:
        state = APIState()
        scenario_id = create_coc_demo(state)["scenario_id"]

        response = coc_review(state, scenario_id)

        self.assertEqual(response["title"], "The Lantern Under Briar House")
        self.assertTrue(response["ok"])
        self.assertEqual(response["counts"]["locations"], 3)

    def test_import_coc_scenario_stores_scenario(self) -> None:
        state = APIState()
        scenario_data = coc_scenario_to_dict(create_sample_coc_scenario())
        scenario_data["title"] = "The Glass Lake"
        del scenario_data["id"]

        response = import_coc_scenario(state, scenario_data)

        self.assertIn(response["scenario_id"], state.coc_scenarios)
        self.assertTrue(response["scenario_id"].startswith("coc_"))
        self.assertEqual(response["scenario"]["title"], "The Glass Lake")

    def test_import_coc_scenario_reports_invalid_body(self) -> None:
        with self.assertRaises(APIError) as context:
            import_coc_scenario(APIState(), {"title": "Incomplete"})

        self.assertEqual(context.exception.status, 400)
        self.assertEqual(context.exception.code, "invalid_coc_scenario")

    def test_generate_coc_scenario_uses_provider_and_imports_result(self) -> None:
        scenario_text = json.dumps(coc_scenario_to_dict(create_sample_coc_scenario()))
        state = APIState(ai_provider=MockProvider("```json\n" + scenario_text + "\n```"))

        response = generate_coc_scenario(state, {"premise": "A house hums in the rain.", "max_attempts": 1})

        self.assertIn(response["scenario_id"], state.coc_scenarios)
        self.assertEqual(response["scenario"]["title"], "The Lantern Under Briar House")
        self.assertEqual(response["metadata"]["premise"], "A house hums in the rain.")
        self.assertFalse(response["metadata"]["require_review_ok"])
        self.assertTrue(response["review"]["ok"])

    def test_generate_coc_scenario_reports_missing_provider(self) -> None:
        with self.assertRaises(APIError) as context:
            generate_coc_scenario(APIState(), {"premise": "A house hums in the rain."})

        self.assertEqual(context.exception.status, 503)

    def test_generate_coc_scenario_reports_invalid_request(self) -> None:
        state = APIState(ai_provider=MockProvider("{}"))

        with self.assertRaises(APIError) as context:
            generate_coc_scenario(state, {"premise": " "})

        self.assertEqual(context.exception.status, 400)

    def test_run_coc_action_updates_scenario(self) -> None:
        state = APIState()
        scenario_id = create_coc_demo(state)["scenario_id"]

        response = run_coc_action(state, scenario_id, "inspect portrait", seed=1)

        self.assertTrue(response["keep_going"])
        self.assertIn("Clue found - Scratched Portrait", response["transcript"])
        self.assertEqual(response["summary"]["investigator"]["current_sanity"], 58)
        self.assertEqual(response["summary"]["discovered_clue_count"], 1)
        self.assertEqual(response["summary"]["inventory"], ["Torn portrait canvas"])
        self.assertGreater(response["summary"]["session_event_count"], 0)
        self.assertIn("Clue found - Scratched Portrait", "\n".join(response["summary"]["recent_events"]))


    def test_run_coc_note_action_updates_recent_events(self) -> None:
        state = APIState()
        scenario_id = create_coc_demo(state)["scenario_id"]

        response = run_coc_action(state, scenario_id, "note I distrust the well", seed=1)

        self.assertIn("Player note: I distrust the well", response["transcript"])
        self.assertIn("Player note: I distrust the well", response["summary"]["recent_events"])
        self.assertGreater(response["summary"]["session_event_count"], 0)

    def test_coc_summary_exposes_partial_clues_after_soft_failure(self) -> None:
        state = APIState()
        scenario_id = create_coc_demo(state)["scenario_id"]
        state.coc_scenarios[scenario_id].investigator.skills["spot hidden"] = 1

        response = run_coc_action(state, scenario_id, "inspect hearth", seed=1)
        listed = list_coc_scenarios(state)["scenarios"][0]

        self.assertIn("Partial clue - Ashen Spiral", response["transcript"])
        self.assertEqual(response["summary"]["discovered_clue_count"], 0)
        self.assertEqual(response["summary"]["partial_clue_count"], 1)
        self.assertEqual(response["summary"]["partial_clues"][0]["title"], "Ashen Spiral")
        self.assertFalse(response["summary"]["partial_clues"][0]["push_attempted"])
        self.assertIn("push ashen spiral", response["summary"]["available_actions"])
        self.assertIsNotNone(response["summary"]["partial_clues"][0]["luck_cost"])
        self.assertIn("spend luck ashen spiral", response["summary"]["available_actions"])
        self.assertIn("Charcoal spiral rubbing", response["summary"]["inventory"])
        self.assertEqual(listed["partial_clue_count"], 1)

    def test_list_campaigns_returns_memory_campaigns(self) -> None:
        state = APIState()
        first_id = create_demo_campaign(state)["campaign_id"]
        second_id = create_playable_demo_campaign(state)["campaign_id"]
        coc_id = create_coc_demo(state)["scenario_id"]

        response = list_campaigns(state)

        ids = [campaign["id"] for campaign in response["campaigns"]]
        self.assertEqual(ids, [first_id, second_id])
        self.assertEqual(response["campaigns"][0]["character_count"], 0)
        self.assertEqual(response["campaigns"][1]["character_count"], 1)
        self.assertEqual(response["campaigns"][0]["current_location_name"], "Village Square")
        self.assertIn("session_event_count", response["campaigns"][0])
        self.assertEqual(response["coc_scenarios"][0]["id"], coc_id)
        self.assertEqual(response["coc_scenarios"][0]["system_id"], "coc7e")

    def test_list_coc_scenarios_returns_memory_scenarios(self) -> None:
        state = APIState()
        scenario_id = create_coc_demo(state)["scenario_id"]
        run_coc_action(state, scenario_id, "inspect portrait", seed=1)

        response = list_coc_scenarios(state)

        self.assertEqual(response["scenarios"][0]["id"], scenario_id)
        self.assertEqual(response["scenarios"][0]["title"], "The Lantern Under Briar House")
        self.assertEqual(response["scenarios"][0]["system_id"], "coc7e")
        self.assertEqual(response["scenarios"][0]["location"], "Briar House Study")
        self.assertEqual(response["scenarios"][0]["location_id"], "study")
        self.assertEqual(response["scenarios"][0]["investigator_name"], "Eleanor Vale")
        self.assertEqual(response["scenarios"][0]["current_sanity"], 58)
        self.assertFalse(response["scenarios"][0]["completed"])
        self.assertEqual(response["scenarios"][0]["inventory_count"], 1)
        self.assertGreater(response["scenarios"][0]["session_event_count"], 0)
        self.assertEqual(response["scenarios"][0]["npc_count"], 2)
        self.assertEqual(response["scenarios"][0]["discovered_clue_count"], 1)
        self.assertEqual(response["scenarios"][0]["partial_clue_count"], 0)
        self.assertEqual(response["scenarios"][0]["clue_count"], 6)

    def test_delete_campaign_removes_campaign(self) -> None:
        state = APIState()
        campaign_id = create_demo_campaign(state)["campaign_id"]

        response = delete_campaign(state, campaign_id)

        self.assertTrue(response["deleted"])
        self.assertNotIn(campaign_id, state.campaigns)

    def test_delete_campaign_reports_missing_campaign(self) -> None:
        with self.assertRaises(APIError) as context:
            delete_campaign(APIState(), "missing")

        self.assertEqual(context.exception.status, 404)

    def test_state_dir_persists_import_action_and_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = APIState(state_dir=Path(tmp))
            campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]
            path = Path(tmp) / f"{campaign_id}.json"

            self.assertTrue(path.exists())
            run_campaign_action(state, campaign_id, "go old road", seed=1)
            self.assertEqual(load_campaign(path).current_location_id, "loc_old_road")
            delete_campaign(state, campaign_id)
            self.assertFalse(path.exists())

    def test_state_dir_persists_and_loads_coc_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            writer_state = APIState(state_dir=Path(tmp))
            scenario_id = create_coc_demo(writer_state)["scenario_id"]
            run_coc_action(writer_state, scenario_id, "inspect portrait", seed=1)

            reader_state = APIState(state_dir=Path(tmp))
            load_campaigns_from_state_dir(reader_state)

        self.assertIn(scenario_id, reader_state.coc_scenarios)
        self.assertEqual(reader_state.coc_scenarios[scenario_id].investigator.current_sanity, 58)
        self.assertTrue(reader_state.coc_scenarios[scenario_id].session_log)

    def test_load_campaigns_from_state_dir_reads_existing_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            writer_state = APIState(state_dir=Path(tmp))
            campaign_id = import_adventure(writer_state, create_adventure_template("Moonlit Road"))["campaign_id"]
            reader_state = APIState(state_dir=Path(tmp))

            load_campaigns_from_state_dir(reader_state)

        self.assertIn(campaign_id, reader_state.campaigns)

    def test_campaign_state_reports_missing_campaign(self) -> None:
        with self.assertRaises(APIError) as context:
            campaign_state(APIState(), "missing")

        self.assertEqual(context.exception.status, 404)
        self.assertEqual(context.exception.code, "campaign_not_found")
        self.assertEqual(context.exception.message, "Campaign not found.")
        self.assertEqual(context.exception.to_response()["error"]["code"], "campaign_not_found")

    def test_add_sample_character_updates_campaign(self) -> None:
        state = APIState()
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]

        response = add_sample_character(state, campaign_id)

        self.assertEqual(response["character"]["name"], "Leth")
        self.assertIn("Leth", state.campaigns[campaign_id].characters)
        self.assertIn("Leth", response["campaign"]["characters"])

    def test_add_sample_character_rejects_duplicate(self) -> None:
        state = APIState()
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]
        add_sample_character(state, campaign_id)

        with self.assertRaises(APIError) as context:
            add_sample_character(state, campaign_id)

        self.assertEqual(context.exception.status, 400)
        self.assertIn("Character already exists", context.exception.message)

    def test_add_sample_character_reports_missing_campaign(self) -> None:
        with self.assertRaises(APIError) as context:
            add_sample_character(APIState(), "missing")

        self.assertEqual(context.exception.status, 404)

    def test_campaign_summary_returns_panel_data(self) -> None:
        state = APIState()
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]
        add_sample_character(state, campaign_id)
        campaign = state.campaigns[campaign_id]
        campaign.record_event(SessionEvent(actor="DM", content="The village waits."))
        campaign.active_combat = {
            "encounter_id": "enc_lantern_sprites",
            "round": 2,
            "turn": "Leth",
            "initiative": [
                {"name": "Leth", "initiative_total": 18, "armor_class": 16, "current_hp": 24, "is_player": True},
                {"name": "Lantern Sprite", "initiative_total": 12, "armor_class": 13, "current_hp": 7, "is_player": False},
            ],
            "resources": {"Leth": {"action": True, "bonus_action": False, "reaction": True, "movement": 20}},
        }

        summary = campaign_summary(state, campaign_id)

        self.assertEqual(summary["id"], campaign_id)
        self.assertEqual(summary["system_id"], "dnd5e")
        self.assertEqual(summary["current_location_id"], "loc_village_square")
        self.assertEqual(summary["current_location"]["name"], "Village Square")
        self.assertEqual(summary["current_location"]["exits"][0]["name"], "Old Road")
        self.assertEqual(summary["current_location"]["npcs"][0]["name"], "Mayor Elin")
        self.assertEqual(summary["characters"][0]["name"], "Leth")
        self.assertEqual(summary["characters"][0]["conditions"], [])
        self.assertEqual(summary["characters"][0]["death_saves"], {"successes": 0, "failures": 0})
        self.assertEqual(summary["characters"][0]["spellcasting"]["slots"][0]["available"], 4)
        self.assertTrue(any(spell["name"] == "Sacred Flame" for spell in summary["characters"][0]["spellcasting"]["known_spells"]))
        self.assertTrue(any(spell["name"] == "Guiding Bolt" for spell in summary["characters"][0]["spellcasting"]["known_spells"]))
        self.assertEqual(summary["quest_count"], 1)
        self.assertEqual(summary["clue_count"], 1)
        self.assertGreater(summary["session_event_count"], 0)
        self.assertEqual(summary["active_combat"]["round"], 2)
        self.assertEqual(summary["active_combat"]["monster_action_strategy"], "default_attack")
        self.assertEqual(summary["active_combat"]["last_automatic_action"], "")
        self.assertEqual(summary["active_combat"]["morale_hint"], "")
        self.assertEqual(summary["active_combat"]["combatant_count"], 2)
        self.assertFalse(summary["active_combat"]["initiative"][0]["defeated"])
        self.assertEqual(summary["active_combat"]["initiative"][0]["conditions"], [])
        self.assertEqual(summary["active_combat"]["initiative"][0]["death_saves"], {"successes": 0, "failures": 0})
        self.assertEqual(summary["active_combat"]["targetable_enemies"], ["Lantern Sprite"])
        self.assertEqual(summary["active_combat"]["targetable_allies"], [])
        self.assertEqual(summary["active_combat"]["current_resources"]["movement"], 20)
        self.assertEqual(summary["recent_events"][-1]["content"], "The village waits.")
        self.assertIn("talk mayor elin", summary["available_actions"])
        self.assertIn("talk mayor", summary["available_actions"])
        self.assertIn("attack lantern sprite", summary["available_actions"])
        self.assertIn("dash", summary["available_actions"])
        self.assertIn("disengage", summary["available_actions"])
        self.assertIn("dodge", summary["available_actions"])
        self.assertIn("cast bless", summary["available_actions"])
        self.assertIn("cast burning hands", summary["available_actions"])
        self.assertIn("cast cure wounds", summary["available_actions"])
        self.assertIn("cast sacred flame lantern sprite", summary["available_actions"])
        self.assertIn("cast guiding bolt lantern sprite", summary["available_actions"])
        self.assertIn("cast magic missile lantern sprite", summary["available_actions"])
        self.assertIn("combat", summary["available_actions"])
        self.assertIn("condition", summary["available_actions"])
        self.assertIn("clear condition", summary["available_actions"])
        self.assertIn("flee", summary["available_actions"])
        self.assertIn("surrender", summary["available_actions"])
        self.assertIn("accept surrender", summary["available_actions"])

    def test_campaign_summary_exposes_monster_action_strategy(self) -> None:
        state = APIState()
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]
        add_sample_character(state, campaign_id)
        campaign = state.campaigns[campaign_id]
        campaign.active_combat = {
            "encounter_id": "enc_lantern_sprites",
            "round": 1,
            "turn": "Lantern Sprite",
            "monster_action_strategy": "concentrating",
            "last_automatic_action": "Automatic monster action: Lantern Sprite uses concentrating and targets Leth.",
            "morale_hint": "Hostile morale is wavering.",
            "initiative": [
                {"name": "Leth", "initiative_total": 18, "is_player": True, "armor_class": 16, "current_hp": 24},
                {
                    "name": "Lantern Sprite",
                    "initiative_total": 12,
                    "is_player": False,
                    "armor_class": 13,
                    "current_hp": 7,
                    "action_strategy": "concentrating",
                },
            ],
            "resources": {"Lantern Sprite": {"action": True, "bonus_action": True, "reaction": True, "movement": 30}},
        }

        summary = campaign_summary(state, campaign_id)

        self.assertEqual(summary["active_combat"]["monster_action_strategy"], "concentrating")
        self.assertEqual(
            summary["active_combat"]["last_automatic_action"],
            "Automatic monster action: Lantern Sprite uses concentrating and targets Leth.",
        )
        self.assertEqual(summary["active_combat"]["morale_hint"], "Hostile morale is wavering.")
        self.assertEqual(summary["active_combat"]["initiative"][1]["action_strategy"], "concentrating")

    def test_campaign_summary_combines_character_and_temporary_combat_conditions(self) -> None:
        state = APIState()
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]
        add_sample_character(state, campaign_id)
        campaign = state.campaigns[campaign_id]
        campaign.characters["Leth"].conditions.add("prone")
        campaign.active_combat = {
            "encounter_id": "enc_lantern_sprites",
            "round": 1,
            "turn": "Leth",
            "initiative": [
                {
                    "name": "Leth",
                    "initiative_total": 18,
                    "is_player": True,
                    "armor_class": 16,
                    "current_hp": 24,
                    "conditions": ["dodging"],
                }
            ],
            "resources": {"Leth": {"action": True, "bonus_action": True, "reaction": True, "movement": 30}},
        }

        summary = campaign_summary(state, campaign_id)

        self.assertEqual(summary["active_combat"]["initiative"][0]["conditions"], ["dodging", "prone"])

    def test_campaign_summary_suggests_death_save_and_stabilize_actions(self) -> None:
        state = APIState()
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]
        add_sample_character(state, campaign_id)
        campaign = state.campaigns[campaign_id]
        leth = campaign.characters["Leth"]
        leth.current_hp = 0
        leth.conditions.add("unconscious")
        leth.death_save_failures = 1
        campaign.active_combat = {
            "encounter_id": "enc_lantern_sprites",
            "round": 1,
            "turn": "Lantern Sprite",
            "initiative": [
                {"name": "Leth", "initiative_total": 18, "is_player": True, "armor_class": 16, "current_hp": 0},
                {"name": "Lantern Sprite", "initiative_total": 12, "is_player": False, "armor_class": 13, "current_hp": 7},
            ],
            "resources": {"Lantern Sprite": {"action": True, "bonus_action": True, "reaction": True, "movement": 30}},
        }

        summary = campaign_summary(state, campaign_id)

        self.assertEqual(summary["characters"][0]["death_saves"], {"successes": 0, "failures": 1})
        self.assertEqual(summary["active_combat"]["initiative"][0]["conditions"], ["unconscious"])
        self.assertEqual(summary["active_combat"]["initiative"][0]["death_saves"], {"successes": 0, "failures": 1})
        self.assertIn("death save leth", summary["available_actions"])
        self.assertIn("stabilize leth", summary["available_actions"])

    def test_campaign_summary_only_suggests_spells_for_current_character(self) -> None:
        state = APIState()
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]
        add_sample_character(state, campaign_id)
        campaign = state.campaigns[campaign_id]
        campaign.active_combat = {
            "encounter_id": "enc_lantern_sprites",
            "round": 1,
            "turn": "Lantern Sprite",
            "initiative": [
                {"name": "Leth", "initiative_total": 18, "is_player": True, "armor_class": 16, "current_hp": 24},
                {"name": "Lantern Sprite", "initiative_total": 12, "is_player": False, "armor_class": 13, "current_hp": 7},
            ],
            "resources": {
                "Leth": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
                "Lantern Sprite": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
            },
        }

        summary = campaign_summary(state, campaign_id)

        self.assertIn("attack leth", summary["available_actions"])
        self.assertNotIn("cast guiding bolt", summary["available_actions"])
        self.assertNotIn("cast sacred flame leth", summary["available_actions"])

    def test_campaign_summary_suggests_targeted_healing_spells_for_allies(self) -> None:
        state = APIState()
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]
        add_sample_character(state, campaign_id)
        campaign = state.campaigns[campaign_id]
        campaign.active_combat = {
            "encounter_id": "enc_lantern_sprites",
            "round": 1,
            "turn": "Leth",
            "initiative": [
                {"name": "Leth", "initiative_total": 18, "is_player": True, "armor_class": 16, "current_hp": 24},
                {"name": "Kael", "initiative_total": 14, "is_player": True, "armor_class": 14, "current_hp": 5},
                {"name": "Lantern Sprite", "initiative_total": 12, "is_player": False, "armor_class": 13, "current_hp": 7},
            ],
            "resources": {
                "Leth": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
                "Kael": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
                "Lantern Sprite": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
            },
        }

        summary = campaign_summary(state, campaign_id)

        self.assertIn("cast cure wounds leth", summary["available_actions"])
        self.assertIn("cast cure wounds kael", summary["available_actions"])
        self.assertIn("cast healing word kael", summary["available_actions"])

    def test_campaign_log_returns_limited_events(self) -> None:
        state = APIState()
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]
        campaign = state.campaigns[campaign_id]
        campaign.record_event(SessionEvent(actor="Player", content="First"))
        campaign.record_event(SessionEvent(actor="DM", content="Second"))

        response = campaign_log(state, campaign_id, limit=1)

        self.assertEqual(response["campaign_id"], campaign_id)
        self.assertEqual(len(response["events"]), 1)
        self.assertGreaterEqual(response["event_count"], 2)
        self.assertGreaterEqual(response["filtered_count"], 2)
        self.assertEqual(response["returned_count"], 1)
        self.assertEqual(response["events"][0]["content"], "Second")

    def test_campaign_log_filters_by_visibility(self) -> None:
        state = APIState()
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]
        campaign = state.campaigns[campaign_id]
        campaign.record_event(SessionEvent(actor="DM", content="Public", visibility=Visibility.PUBLIC))
        campaign.record_event(SessionEvent(actor="DM", content="Secret", visibility=Visibility.DM_ONLY))

        response = campaign_log(state, campaign_id, limit=10, visibility="dm-only")

        self.assertEqual(response["visibility"], "dm_only")
        self.assertEqual(response["filtered_count"], 2)
        self.assertTrue(all(event["visibility"] == "dm_only" for event in response["events"]))
        self.assertEqual(response["events"][-1]["content"], "Secret")

    def test_campaign_log_rejects_unknown_visibility(self) -> None:
        state = APIState()
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]

        with self.assertRaises(APIError) as context:
            campaign_log(state, campaign_id, visibility="players")

        self.assertEqual(context.exception.status, 400)
        self.assertEqual(context.exception.code, "invalid_visibility")

    def test_campaign_log_rejects_non_positive_limit(self) -> None:
        state = APIState()
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]

        with self.assertRaises(APIError) as context:
            campaign_log(state, campaign_id, limit=0)

        self.assertEqual(context.exception.status, 400)
        self.assertEqual(context.exception.code, "invalid_limit")

    def test_run_campaign_action_updates_campaign_and_returns_transcript(self) -> None:
        state = APIState()
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]

        response = run_campaign_action(state, campaign_id, "go old road", seed=1)

        self.assertTrue(response["keep_going"])
        self.assertEqual(response["campaign"]["current_location_id"], "loc_old_road")
        self.assertIn("Old Road", response["transcript"])
        self.assertEqual(response["messages"][0]["actor"], "Player")
        self.assertEqual(response["messages"][1]["actor"], "DM")

    def test_summary_drops_combat_actions_after_encounter_resolution(self) -> None:
        state = APIState()
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]
        add_sample_character(state, campaign_id)
        campaign = state.campaigns[campaign_id]
        campaign.active_combat = {
            "encounter_id": "enc_lantern_sprites",
            "round": 1,
            "turn": "Leth",
            "initiative": [
                {
                    "name": "Leth",
                    "initiative_total": 18,
                    "is_player": True,
                    "armor_class": 16,
                    "current_hp": 24,
                    "attack_bonus": 20,
                    "damage": "8",
                },
                {
                    "name": "Lantern Sprite",
                    "initiative_total": 12,
                    "is_player": False,
                    "armor_class": 10,
                    "current_hp": 1,
                },
            ],
            "resources": {
                "Leth": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
                "Lantern Sprite": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
            },
        }

        run_campaign_action(state, campaign_id, "attack sprite", seed=1)
        summary = campaign_summary(state, campaign_id)

        self.assertIsNone(summary["active_combat"])
        self.assertNotIn("attack lantern sprite", summary["available_actions"])
        self.assertNotIn("end turn", summary["available_actions"])

    def test_run_campaign_action_rejects_empty_action(self) -> None:
        state = APIState()
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]

        with self.assertRaises(APIError) as context:
            run_campaign_action(state, campaign_id, " ")

        self.assertEqual(context.exception.status, 400)

    def test_search_rules_uses_configured_corpus(self) -> None:
        state = APIState(rules_corpus=self._rules_corpus())

        response = search_rules(state, "grapple", limit=1)

        self.assertEqual(response["query"], "grapple")
        self.assertEqual(response["results"][0]["section"], "Grappling")

    def test_search_rules_reports_missing_corpus(self) -> None:
        with self.assertRaises(APIError) as context:
            search_rules(APIState(), "grapple")

        self.assertEqual(context.exception.status, 503)

    def test_suggest_dm_turn_uses_provider_without_mutating_campaign(self) -> None:
        state = APIState(ai_provider=MockProvider("- The road darkens."))
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]
        before_events = len(state.campaigns[campaign_id].session_log)

        response = suggest_dm_turn(state, campaign_id, "look down the road", include_prompt=True)

        self.assertEqual(response["campaign_id"], campaign_id)
        self.assertIn("road darkens", response["suggestion"]["text"])
        self.assertIn("prompt", response["suggestion"])
        self.assertEqual(response["metadata"]["action"], "look down the road")
        self.assertFalse(response["metadata"]["used_rules"])
        self.assertTrue(response["metadata"]["included_prompt"])
        self.assertEqual(len(state.campaigns[campaign_id].session_log), before_events)

    def test_suggest_dm_turn_reports_missing_provider(self) -> None:
        state = APIState()
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]

        with self.assertRaises(APIError) as context:
            suggest_dm_turn(state, campaign_id, "look")

        self.assertEqual(context.exception.status, 503)

    def test_suggest_dm_turn_reports_provider_failure(self) -> None:
        state = APIState(ai_provider=FailingProvider())
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]

        with self.assertRaises(APIError) as context:
            suggest_dm_turn(state, campaign_id, "look")

        self.assertEqual(context.exception.status, 502)
        self.assertEqual(context.exception.code, "ai_provider_error")

    def test_suggest_coc_keeper_turn_uses_provider_without_mutating_scenario(self) -> None:
        state = APIState(ai_provider=MockProvider("- The wallpaper seems damp."))
        scenario_id = create_coc_demo(state)["scenario_id"]
        before_inventory = list(state.coc_scenarios[scenario_id].inventory)

        response = suggest_coc_keeper_turn(state, scenario_id, "inspect portrait", include_prompt=True)

        self.assertEqual(response["scenario_id"], scenario_id)
        self.assertIn("wallpaper seems damp", response["suggestion"]["text"])
        self.assertIn("prompt", response["suggestion"])
        self.assertEqual(state.coc_scenarios[scenario_id].inventory, before_inventory)

    def test_suggest_coc_keeper_turn_reports_missing_provider(self) -> None:
        state = APIState()
        scenario_id = create_coc_demo(state)["scenario_id"]

        with self.assertRaises(APIError) as context:
            suggest_coc_keeper_turn(state, scenario_id, "look")

        self.assertEqual(context.exception.status, 503)

    def test_suggest_coc_keeper_turn_reports_provider_failure(self) -> None:
        state = APIState(ai_provider=FailingProvider())
        scenario_id = create_coc_demo(state)["scenario_id"]

        with self.assertRaises(APIError) as context:
            suggest_coc_keeper_turn(state, scenario_id, "look")

        self.assertEqual(context.exception.status, 502)
        self.assertEqual(context.exception.code, "ai_provider_error")

    def test_route_request_supports_health_import_state_and_action(self) -> None:
        state = APIState()

        self.assertTrue(route_request(state, "GET", "/health", {})["ok"])
        self.assertEqual(route_request(state, "GET", "/campaigns", {})["campaigns"], [])
        imported = route_request(
            state,
            "POST",
            "/campaigns/demo-with-character",
            {},
        )
        campaign_id = imported["campaign_id"]
        self.assertEqual(len(route_request(state, "GET", "/campaigns", {})["campaigns"]), 1)
        fetched = route_request(state, "GET", f"/campaigns/{campaign_id}", {})
        summary = route_request(state, "GET", f"/campaigns/{campaign_id}/summary", {})
        log = route_request(state, "GET", f"/campaigns/{campaign_id}/log?limit=2", {})
        dm_log = route_request(state, "GET", f"/campaigns/{campaign_id}/log?visibility=dm_only", {})
        default_log = route_request(state, "GET", f"/campaigns/{campaign_id}/log?limit=", {})
        action = route_request(state, "POST", f"/campaigns/{campaign_id}/actions", {"action": "inspect", "seed": 3})

        self.assertEqual(fetched["id"], campaign_id)
        self.assertEqual(summary["characters"][0]["name"], "Leth")
        self.assertLessEqual(len(log["events"]), 2)
        self.assertEqual(dm_log["visibility"], "dm_only")
        self.assertIn("events", default_log)
        self.assertIn("Clue found", action["transcript"])

        state.rules_corpus = self._rules_corpus()
        rules = route_request(state, "POST", "/rules/search", {"query": "grapple", "limit": 1})
        self.assertEqual(rules["results"][0]["section"], "Grappling")

        state.ai_provider = MockProvider("- Suggest a Perception check.")
        suggestion = route_request(
            state,
            "POST",
            f"/campaigns/{campaign_id}/dm-suggestion",
            {"action": "inspect ash"},
        )
        self.assertIn("Perception", suggestion["suggestion"]["text"])
        deleted = route_request(state, "DELETE", f"/campaigns/{campaign_id}", {})
        self.assertTrue(deleted["deleted"])

    def test_route_request_supports_coc_demo_summary_and_action(self) -> None:
        state = APIState()

        scenario_data = coc_scenario_to_dict(create_sample_coc_scenario())
        del scenario_data["id"]
        imported = route_request(state, "POST", "/coc/import", {"scenario": scenario_data})
        demo = route_request(state, "POST", "/coc/demo", {})
        scenarios = route_request(state, "GET", "/coc", {})
        summary = route_request(state, "GET", f"/coc/{demo['scenario_id']}/summary", {})
        review = route_request(state, "GET", f"/coc/{demo['scenario_id']}/review", {})
        action = route_request(state, "POST", f"/coc/{demo['scenario_id']}/actions", {"action": "inspect portrait"})
        keeper = route_request(
            APIState(ai_provider=MockProvider("- Keep the room tense."), coc_scenarios=state.coc_scenarios),
            "POST",
            f"/coc/{demo['scenario_id']}/keeper-suggestion",
            {"action": "look"},
        )
        generated_state = APIState(
            ai_provider=MockProvider(json.dumps(coc_scenario_to_dict(create_sample_coc_scenario())))
        )
        generated = route_request(
            generated_state,
            "POST",
            "/coc/generate",
            {"premise": "A house hums in the rain."},
        )

        self.assertEqual(scenarios["scenarios"][0]["id"], imported["scenario_id"])
        self.assertEqual(scenarios["scenarios"][1]["id"], demo["scenario_id"])
        self.assertEqual(scenarios["scenarios"][1]["completion_required_count"], 4)
        self.assertEqual(scenarios["scenarios"][1]["completion_remaining_count"], 4)
        self.assertEqual(summary["system_id"], "coc7e")
        self.assertFalse(summary["exits"][0]["available"])
        self.assertEqual(summary["exits"][0]["requirements"]["required_clue_ids"], ["portrait_truth"])
        self.assertTrue(action["summary"]["exits"][0]["available"])
        self.assertIn("progress", summary["available_actions"])
        self.assertIn("recap", summary["available_actions"])
        self.assertIn("hint", summary["available_actions"])
        self.assertIn("scratched portrait", summary["keeper_hint"])
        self.assertEqual(summary["completion_progress"]["required_clue_ids"]["remaining"], ["portrait_truth", "lantern_wick"])
        self.assertEqual(action["summary"]["completion_progress"]["required_clue_ids"]["remaining"], ["lantern_wick"])
        self.assertTrue(review["ok"])
        self.assertIn("Scratched Portrait", action["transcript"])
        self.assertIn("room tense", keeper["suggestion"]["text"])
        self.assertIn(generated["scenario_id"], generated_state.coc_scenarios)

    def test_route_request_reports_bad_import_body(self) -> None:
        with self.assertRaises(APIError) as context:
            route_request(APIState(), "POST", "/campaigns/import", {})

        self.assertEqual(context.exception.status, 400)
        with self.assertRaises(APIError) as coc_context:
            route_request(APIState(), "POST", "/coc/import", {})

        self.assertEqual(coc_context.exception.status, 400)

    def test_route_request_reports_invalid_numeric_body_fields(self) -> None:
        state = APIState(rules_corpus=self._rules_corpus())
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]

        with self.assertRaises(APIError) as seed_context:
            route_request(state, "POST", f"/campaigns/{campaign_id}/actions", {"action": "look", "seed": "bad"})
        with self.assertRaises(APIError) as limit_context:
            route_request(state, "POST", "/rules/search", {"query": "grapple", "limit": "bad"})

        self.assertEqual(seed_context.exception.status, 400)
        self.assertEqual(seed_context.exception.code, "invalid_integer")
        self.assertEqual(limit_context.exception.status, 400)
        self.assertEqual(limit_context.exception.code, "invalid_integer")

    def test_http_handler_supports_cors_preflight(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(APIState()))
        thread = Thread(target=server.handle_request)
        thread.start()
        try:
            request = Request(f"http://127.0.0.1:{server.server_port}/campaigns/import", method="OPTIONS")
            with urlopen(request, timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")
                self.assertIn("OPTIONS", response.headers["Access-Control-Allow-Methods"])
                self.assertIn("DELETE", response.headers["Access-Control-Allow-Methods"])
        finally:
            server.server_close()
            thread.join(timeout=5)

    def test_http_handler_returns_structured_error(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(APIState()))
        thread = Thread(target=server.handle_request)
        thread.start()
        try:
            request = Request(f"http://127.0.0.1:{server.server_port}/rules/search", data=b"{}", method="POST")
            request.add_header("Content-Type", "application/json")
            with self.assertRaises(HTTPError) as context:
                urlopen(request, timeout=5)
            body = json.loads(context.exception.read().decode("utf-8"))

            self.assertEqual(context.exception.code, 503)
            self.assertEqual(body["error"]["code"], "rules_corpus_not_configured")
            self.assertEqual(body["error_message"], "Rules corpus is not configured.")
        finally:
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
