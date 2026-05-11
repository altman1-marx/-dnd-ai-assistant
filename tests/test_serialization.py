import tempfile
import unittest
from pathlib import Path

from dnd_ai_assistant.core.campaign import Monster
from dnd_ai_assistant.core.serialization import campaign_from_dict, campaign_to_dict, load_campaign, save_campaign
from dnd_ai_assistant.demo import build_sample_campaign, handle_player_action


class SerializationTests(unittest.TestCase):
    def test_campaign_round_trip_dict(self) -> None:
        sample = build_sample_campaign(seed=1)
        handle_player_action(sample, "inspect rope")

        data = campaign_to_dict(sample.campaign)
        restored = campaign_from_dict(data)

        self.assertEqual(restored.title, sample.campaign.title)
        self.assertIn("Kael", restored.characters)
        self.assertEqual(len(restored.locations), 1)
        self.assertEqual(len(restored.session_log), len(sample.campaign.session_log))
        self.assertTrue(next(iter(restored.clues.values())).discovered)

    def test_campaign_round_trip_encounter(self) -> None:
        sample = build_sample_campaign(seed=1)
        sample.tools.add_encounter(
            sample.campaign.id,
            title="Ash Goblin Ambush",
            location_id=sample.location.id,
            monsters=[Monster(name="Ash Goblin", armor_class=13, max_hp=7, current_hp=7)],
        )

        restored = campaign_from_dict(campaign_to_dict(sample.campaign))

        self.assertEqual(len(restored.encounters), 1)
        encounter = next(iter(restored.encounters.values()))
        self.assertEqual(encounter.monsters[0].name, "Ash Goblin")

    def test_campaign_save_and_load_file(self) -> None:
        sample = build_sample_campaign(seed=1)
        handle_player_action(sample, "look around")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "campaign.json"
            save_campaign(sample.campaign, path)
            restored = load_campaign(path)

        self.assertEqual(restored.title, "The Bell Beneath Ashford")
        self.assertEqual(restored.session_log[0].actor, "Kael")


if __name__ == "__main__":
    unittest.main()
