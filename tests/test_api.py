import unittest

from dnd_ai_assistant.adventure import create_adventure_template
from dnd_ai_assistant.api import APIError, APIState, campaign_state, import_adventure, route_request, run_campaign_action


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
        action = route_request(state, "POST", f"/campaigns/{campaign_id}/actions", {"action": "inspect", "seed": 1})

        self.assertEqual(fetched["id"], campaign_id)
        self.assertIn("Clue found", action["transcript"])

    def test_route_request_reports_bad_import_body(self) -> None:
        with self.assertRaises(APIError) as context:
            route_request(APIState(), "POST", "/campaigns/import", {})

        self.assertEqual(context.exception.status, 400)


if __name__ == "__main__":
    unittest.main()
