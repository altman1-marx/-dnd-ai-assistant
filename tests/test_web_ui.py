import unittest
from pathlib import Path


class WebUITests(unittest.TestCase):
    def test_index_references_core_api_endpoints_and_controls(self) -> None:
        html = Path("web/index.html").read_text(encoding="utf-8")

        self.assertIn("/health", html)
        self.assertIn('api("GET", "/campaigns")', html)
        self.assertIn('api("DELETE", "/campaigns/" + campaignId)', html)
        self.assertIn("/campaigns/import", html)
        self.assertIn("/campaigns/demo-with-character", html)
        self.assertIn("/sample-character", html)
        self.assertIn("/summary", html)
        self.assertIn("/log?limit=50", html)
        self.assertIn("/actions", html)
        self.assertIn("/dm-suggestion", html)
        self.assertIn("/rules/search", html)
        self.assertIn('id="adventureFile"', html)
        self.assertIn('id="demoButton"', html)
        self.assertIn('id="campaignsButton"', html)
        self.assertIn('id="campaignList"', html)
        self.assertIn('id="rulesQuery"', html)
        self.assertIn('id="rulesResults"', html)
        self.assertIn('id="clearTranscriptButton"', html)
        self.assertIn('id="actionInput"', html)
        self.assertIn('id="dmButton"', html)
        self.assertIn("renderCampaignList", html)
        self.assertIn("refreshCampaignLog", html)
        self.assertIn("renderRecentEvents", html)
        self.assertIn("recent_events", html)
        self.assertIn("transcriptEventIds", html)
        self.assertIn("appendTranscriptMessage", html)
        self.assertIn("actorClass", html)
        self.assertIn("clearTranscriptView", html)
        self.assertIn(".message", html)
        self.assertIn("renderRulesResults", html)
        self.assertIn("ruleSourceSummary", html)
        self.assertIn("searchRules", html)
        self.assertIn("suggestTypedAction", html)
        self.assertIn("apiErrorFromResponse", html)
        self.assertIn("setupHint", html)
        self.assertIn("ai_provider_not_configured", html)
        self.assertIn("rules_corpus_not_configured", html)
        self.assertIn("featureLabel", html)
        self.assertIn("persistent_state", html)
        self.assertIn("available_actions", html)
        self.assertIn("renderQuickActions", html)
        self.assertIn("spellcasting.slots", html)
        self.assertIn("location.exits", html)
        self.assertNotIn("DEMO_ADVENTURE", html)

    def test_index_does_not_depend_on_external_assets(self) -> None:
        html = Path("web/index.html").read_text(encoding="utf-8")

        self.assertNotIn("https://", html)
        self.assertNotIn("http://cdn", html.lower())
        self.assertNotIn("<script src=", html.lower())
        self.assertNotIn("<link rel=\"stylesheet\"", html.lower())


if __name__ == "__main__":
    unittest.main()
