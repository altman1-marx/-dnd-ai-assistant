import unittest

from dnd_ai_assistant.core.campaign import Campaign
from dnd_ai_assistant.core.store import InMemoryCampaignStore


class InMemoryCampaignStoreTests(unittest.TestCase):
    def test_save_get_and_list_campaigns(self) -> None:
        store = InMemoryCampaignStore()
        campaign = Campaign("The Bell Beneath Ashford")

        saved = store.save(campaign)

        self.assertIs(saved, campaign)
        self.assertIs(store.get(campaign.id), campaign)
        self.assertEqual(store.list(), [campaign])

    def test_get_unknown_campaign_raises_clear_error(self) -> None:
        store = InMemoryCampaignStore()

        with self.assertRaisesRegex(KeyError, "Campaign not found: missing"):
            store.get("missing")


if __name__ == "__main__":
    unittest.main()
