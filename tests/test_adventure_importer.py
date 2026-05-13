import tempfile
import unittest
from pathlib import Path

from dnd_ai_assistant.adventure import AdventureDefinition, create_adventure_template
from dnd_ai_assistant.adventure_importer import campaign_from_adventure
from dnd_ai_assistant.core.campaign import Visibility
from dnd_ai_assistant.core.serialization import load_campaign, save_campaign


class AdventureImporterTests(unittest.TestCase):
    def test_campaign_from_adventure_imports_core_entities(self) -> None:
        adventure = AdventureDefinition(create_adventure_template("Moonlit Road"))

        campaign = campaign_from_adventure(adventure)

        self.assertEqual(campaign.title, "Moonlit Road")
        self.assertEqual(campaign.party_level, 1)
        self.assertEqual(campaign.current_location_id, "loc_village_square")
        self.assertEqual(len(campaign.locations), 3)
        self.assertIn("loc_village_square", campaign.locations)
        self.assertEqual(campaign.locations["loc_village_square"].connected_location_ids, ["loc_old_road"])
        self.assertIn("npc_mayor_elin", campaign.npcs)
        self.assertIn("clue_moon_ash", campaign.clues)
        self.assertIn("quest_find_travelers", campaign.quests)
        self.assertIn("enc_lantern_sprites", campaign.encounters)

    def test_campaign_from_adventure_records_public_and_dm_opening_events(self) -> None:
        adventure = AdventureDefinition(create_adventure_template("Moonlit Road"))

        campaign = campaign_from_adventure(adventure)

        self.assertEqual(len(campaign.session_log), 2)
        self.assertEqual(campaign.session_log[0].visibility, Visibility.PUBLIC)
        self.assertEqual(campaign.session_log[1].visibility, Visibility.DM_ONLY)

    def test_imported_campaign_can_be_saved_and_loaded(self) -> None:
        adventure = AdventureDefinition(create_adventure_template("Moonlit Road"))
        campaign = campaign_from_adventure(adventure)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "campaign.json"
            save_campaign(campaign, path)
            loaded = load_campaign(path)

        self.assertEqual(loaded.title, "Moonlit Road")
        self.assertEqual(len(loaded.locations), 3)
        self.assertEqual(loaded.session_log[1].visibility, Visibility.DM_ONLY)

    def test_campaign_from_adventure_imports_monsters_with_generated_ids(self) -> None:
        raw = create_adventure_template("Moonlit Road")
        raw["encounters"][0]["monsters"] = [
            {"name": "Lantern Sprite", "armor_class": 13, "max_hp": 7, "attack_bonus": 4, "damage": "1d4+2"}
        ]

        campaign = campaign_from_adventure(AdventureDefinition(raw))
        monster = campaign.encounters["enc_lantern_sprites"].monsters[0]

        self.assertEqual(monster.name, "Lantern Sprite")
        self.assertTrue(monster.id.startswith("mon_"))


if __name__ == "__main__":
    unittest.main()
