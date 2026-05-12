import random
import unittest

from dnd_ai_assistant.core.campaign import Monster
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

    def test_roll_skill_check_uses_character_skill_modifier(self) -> None:
        tools = DMTools(rng=random.Random(1))
        campaign = tools.create_campaign("Roadside Ambush", party_level=2).data
        tools.add_character(campaign.id, sample_character())

        result = tools.roll_skill_check(
            campaign_id=campaign.id,
            character_name="Kael",
            skill_name="perception",
            dc=15,
            mode=RollMode.ADVANTAGE,
        )

        self.assertTrue(result.ok)
        check = result.data
        self.assertEqual(check.d20_rolls, (5, 19))
        self.assertEqual(check.total, 23)
        self.assertTrue(check.success)
        self.assertIn("Kael rolled Perception 23 vs DC 15", campaign.session_log[0].content)

    def test_damage_and_healing_tools_record_events(self) -> None:
        tools = DMTools(rng=random.Random(1))
        campaign = tools.create_campaign("Roadside Ambush", party_level=2).data
        tools.add_character(campaign.id, sample_character())

        damage = tools.apply_damage(campaign.id, "Kael", 6)
        heal = tools.heal_character(campaign.id, "Kael", 4)

        self.assertTrue(damage.ok)
        self.assertTrue(heal.ok)
        self.assertEqual(campaign.characters["Kael"].current_hp, 16)
        self.assertIn("Kael took 6 damage", campaign.session_log[0].content)
        self.assertIn("Kael healed 4", campaign.session_log[1].content)

    def test_attack_character_rolls_attack_and_damage(self) -> None:
        tools = DMTools(rng=random.Random(1))
        campaign = tools.create_campaign("Roadside Ambush", party_level=2).data
        tools.add_character(campaign.id, sample_character())

        result = tools.attack_character(
            campaign_id=campaign.id,
            attacker_name="Ash Goblin",
            target_name="Kael",
            attack_bonus=11,
            damage_expression="1d6+2",
        )

        self.assertTrue(result.ok)
        self.assertEqual(campaign.characters["Kael"].current_hp, 11)
        self.assertIn("hit for 7 damage", campaign.session_log[0].content)

    def test_add_and_resolve_encounter(self) -> None:
        tools = DMTools(rng=random.Random(1))
        campaign = tools.create_campaign("Roadside Ambush", party_level=2).data
        location = tools.add_location(campaign.id, "Old Road", "A muddy road through the woods.").data

        result = tools.add_encounter(
            campaign.id,
            title="Ash Goblin Ambush",
            location_id=location.id,
            difficulty="easy",
            trigger="The party opens the sealed stairway.",
            reward="A cracked copper bell charm.",
            monsters=[
                Monster(
                    name="Ash Goblin",
                    armor_class=13,
                    max_hp=7,
                    current_hp=7,
                    initiative_modifier=2,
                    attack_bonus=4,
                    damage="1d6+2",
                )
            ],
        )
        encounter = result.data
        resolved = tools.resolve_encounter(campaign.id, encounter.id)

        self.assertTrue(result.ok)
        self.assertTrue(resolved.ok)
        self.assertTrue(campaign.encounters[encounter.id].resolved)
        self.assertIn("Encounter resolved", campaign.session_log[0].content)


if __name__ == "__main__":
    unittest.main()
