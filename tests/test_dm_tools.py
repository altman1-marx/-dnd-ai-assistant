import random
import unittest

from dnd_ai_assistant.core.character import Character
from dnd_ai_assistant.core.dm_tools import DMTools
from dnd_ai_assistant.core.dnd5e import RollMode


def sample_character() -> Character:
    return Character(
        name="Kael",
        player_name="Altman",
        class_name="Ranger",
        level=2,
        ancestry="Wood Elf",
        ability_scores={"str": 10, "dex": 16, "con": 12, "int": 10, "wis": 14, "cha": 8},
        armor_class=15,
        max_hp=18,
        current_hp=18,
        skill_proficiencies={"perception", "survival"},
        saving_throw_proficiencies={"str", "dex"},
    )


class DMToolsTests(unittest.TestCase):
    def test_create_campaign_and_add_content(self) -> None:
        tools = DMTools(rng=random.Random(1))

        created = tools.create_campaign(
            title="The Bell Beneath Ashford",
            party_level=2,
            tone="dark fantasy investigation",
            public_lore="Ashford is a mining town near the old forest.",
            dm_secrets="The chapel bell is a planar anchor.",
        )
        self.assertTrue(created.ok)
        campaign = created.data
        self.assertEqual(campaign.title, "The Bell Beneath Ashford")

        location_result = tools.add_location(
            campaign.id,
            name="Old Chapel",
            public_description="A cracked chapel with a silent bronze bell.",
            dm_notes="The bell vibrates near fiendish magic.",
        )
        location = location_result.data

        npc_result = tools.add_npc(
            campaign.id,
            name="Mira Voss",
            role="worried mayor",
            public_description="A careful woman trying to keep the town calm.",
            dm_secret="She has heard the bell in her dreams.",
            location_id=location.id,
        )
        self.assertTrue(npc_result.ok)

        clue_result = tools.add_clue(
            campaign.id,
            title="Ash on the Bell Rope",
            public_text="The rope is dusted with black ash.",
            dm_secret="The ash came from the lower crypt.",
            location_id=location.id,
        )
        clue = clue_result.data
        self.assertFalse(clue.discovered)

        reveal_result = tools.reveal_clue(campaign.id, clue.id)
        self.assertTrue(reveal_result.ok)
        self.assertTrue(clue.discovered)
        self.assertEqual(len(campaign.session_log), 1)

    def test_roll_check_records_event(self) -> None:
        tools = DMTools(rng=random.Random(1))
        campaign = tools.create_campaign("Roadside Ambush", party_level=2).data
        tools.add_character(campaign.id, sample_character())

        result = tools.roll_check(
            campaign_id=campaign.id,
            character_name="Kael",
            modifier=5,
            dc=15,
            mode=RollMode.ADVANTAGE,
        )

        self.assertTrue(result.ok)
        check = result.data
        self.assertEqual(check.d20_rolls, (5, 19))
        self.assertEqual(check.total, 24)
        self.assertTrue(check.success)
        self.assertEqual(len(campaign.session_log), 1)
        self.assertIn("Kael rolled 24 vs DC 15", campaign.session_log[0].content)


if __name__ == "__main__":
    unittest.main()

