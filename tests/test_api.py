import unittest
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.request import Request, urlopen

from dnd_ai_assistant.adventure import create_adventure_template
from dnd_ai_assistant.api import (
    APIError,
    APIState,
    add_sample_character,
    campaign_state,
    campaign_summary,
    create_handler,
    create_demo_campaign,
    create_playable_demo_campaign,
    delete_campaign,
    import_adventure,
    list_campaigns,
    route_request,
    run_campaign_action,
    search_rules,
)
from dnd_ai_assistant.rules_corpus import RuleChunk, RuleCorpus


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

    def test_list_campaigns_returns_memory_campaigns(self) -> None:
        state = APIState()
        first_id = create_demo_campaign(state)["campaign_id"]
        second_id = create_playable_demo_campaign(state)["campaign_id"]

        response = list_campaigns(state)

        ids = [campaign["id"] for campaign in response["campaigns"]]
        self.assertEqual(ids, [first_id, second_id])
        self.assertEqual(response["campaigns"][0]["character_count"], 0)
        self.assertEqual(response["campaigns"][1]["character_count"], 1)

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

    def test_campaign_state_reports_missing_campaign(self) -> None:
        with self.assertRaises(APIError) as context:
            campaign_state(APIState(), "missing")

        self.assertEqual(context.exception.status, 404)
        self.assertEqual(context.exception.message, "Campaign not found.")

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
        campaign.active_combat = {
            "encounter_id": "enc_lantern_sprites",
            "round": 2,
            "turn": "Leth",
            "initiative": [{"name": "Leth", "initiative_total": 18, "armor_class": 16, "current_hp": 24, "is_player": True}],
            "resources": {"Leth": {"action": True, "bonus_action": False, "reaction": True, "movement": 20}},
        }

        summary = campaign_summary(state, campaign_id)

        self.assertEqual(summary["id"], campaign_id)
        self.assertEqual(summary["current_location"]["name"], "Village Square")
        self.assertEqual(summary["current_location"]["exits"][0]["name"], "Old Road")
        self.assertEqual(summary["current_location"]["npcs"][0]["name"], "Mayor Elin")
        self.assertEqual(summary["characters"][0]["name"], "Leth")
        self.assertEqual(summary["characters"][0]["spellcasting"]["slots"][0]["available"], 4)
        self.assertTrue(any(spell["name"] == "Sacred Flame" for spell in summary["characters"][0]["spellcasting"]["known_spells"]))
        self.assertEqual(summary["quest_count"], 1)
        self.assertEqual(summary["clue_count"], 1)
        self.assertEqual(summary["active_combat"]["round"], 2)
        self.assertEqual(summary["active_combat"]["current_resources"]["movement"], 20)
        self.assertIn("talk mayor", summary["available_actions"])
        self.assertIn("combat", summary["available_actions"])

    def test_run_campaign_action_updates_campaign_and_returns_transcript(self) -> None:
        state = APIState()
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]

        response = run_campaign_action(state, campaign_id, "go old road", seed=1)

        self.assertTrue(response["keep_going"])
        self.assertEqual(response["campaign"]["current_location_id"], "loc_old_road")
        self.assertIn("Old Road", response["transcript"])
        self.assertEqual(response["messages"][0]["actor"], "Player")
        self.assertEqual(response["messages"][1]["actor"], "DM")

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

    def test_route_request_supports_health_import_state_and_action(self) -> None:
        state = APIState()

        self.assertEqual(route_request(state, "GET", "/health", {}), {"ok": True})
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
        action = route_request(state, "POST", f"/campaigns/{campaign_id}/actions", {"action": "inspect", "seed": 3})

        self.assertEqual(fetched["id"], campaign_id)
        self.assertEqual(summary["characters"][0]["name"], "Leth")
        self.assertIn("Clue found", action["transcript"])
        deleted = route_request(state, "DELETE", f"/campaigns/{campaign_id}", {})
        self.assertTrue(deleted["deleted"])

        state.rules_corpus = self._rules_corpus()
        rules = route_request(state, "POST", "/rules/search", {"query": "grapple", "limit": 1})
        self.assertEqual(rules["results"][0]["section"], "Grappling")

    def test_route_request_reports_bad_import_body(self) -> None:
        with self.assertRaises(APIError) as context:
            route_request(APIState(), "POST", "/campaigns/import", {})

        self.assertEqual(context.exception.status, 400)

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


if __name__ == "__main__":
    unittest.main()
