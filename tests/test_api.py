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
    import_adventure,
    route_request,
    run_campaign_action,
)


class APITests(unittest.TestCase):
    def test_import_adventure_stores_campaign(self) -> None:
        state = APIState()

        response = import_adventure(state, create_adventure_template("Moonlit Road"))

        self.assertIn(response["campaign_id"], state.campaigns)
        self.assertEqual(response["campaign"]["title"], "Moonlit Road")

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
        self.assertEqual(summary["characters"][0]["name"], "Leth")
        self.assertEqual(summary["quest_count"], 1)
        self.assertEqual(summary["clue_count"], 1)
        self.assertEqual(summary["active_combat"]["round"], 2)
        self.assertEqual(summary["active_combat"]["current_resources"]["movement"], 20)

    def test_run_campaign_action_updates_campaign_and_returns_transcript(self) -> None:
        state = APIState()
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]

        response = run_campaign_action(state, campaign_id, "go old road", seed=1)

        self.assertTrue(response["keep_going"])
        self.assertEqual(response["campaign"]["current_location_id"], "loc_old_road")
        self.assertIn("Old Road", response["transcript"])

    def test_run_campaign_action_rejects_empty_action(self) -> None:
        state = APIState()
        campaign_id = import_adventure(state, create_adventure_template("Moonlit Road"))["campaign_id"]

        with self.assertRaises(APIError) as context:
            run_campaign_action(state, campaign_id, " ")

        self.assertEqual(context.exception.status, 400)

    def test_route_request_supports_health_import_state_and_action(self) -> None:
        state = APIState()

        self.assertEqual(route_request(state, "GET", "/health", {}), {"ok": True})
        imported = route_request(
            state,
            "POST",
            "/campaigns/import",
            {"adventure": create_adventure_template("Moonlit Road")},
        )
        campaign_id = imported["campaign_id"]
        fetched = route_request(state, "GET", f"/campaigns/{campaign_id}", {})
        added = route_request(state, "POST", f"/campaigns/{campaign_id}/sample-character", {})
        summary = route_request(state, "GET", f"/campaigns/{campaign_id}/summary", {})
        action = route_request(state, "POST", f"/campaigns/{campaign_id}/actions", {"action": "inspect", "seed": 3})

        self.assertEqual(fetched["id"], campaign_id)
        self.assertEqual(added["character"]["name"], "Leth")
        self.assertEqual(summary["characters"][0]["name"], "Leth")
        self.assertIn("Clue found", action["transcript"])

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
        finally:
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
