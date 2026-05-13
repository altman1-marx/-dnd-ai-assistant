import tempfile
import unittest
from pathlib import Path

from dnd_ai_assistant.core.campaign import Clue, Monster
from dnd_ai_assistant.core.character import Character
from dnd_ai_assistant.core.serialization import campaign_from_dict, campaign_to_dict, load_campaign, save_campaign
from dnd_ai_assistant.core.spells import Spell, Spellcasting
from dnd_ai_assistant.demo import build_sample_campaign, handle_player_action


class SerializationTests(unittest.TestCase):
    def test_campaign_round_trip_dict(self) -> None:
        sample = build_sample_campaign(seed=1)
        handle_player_action(sample, "inspect rope")

        data = campaign_to_dict(sample.campaign)
        restored = campaign_from_dict(data)

        self.assertEqual(restored.title, sample.campaign.title)
        self.assertIn("Kael", restored.characters)
        self.assertEqual(restored.current_location_id, sample.campaign.current_location_id)
        self.assertEqual(len(restored.locations), 1)
        self.assertEqual(len(restored.session_log), len(sample.campaign.session_log))
        self.assertTrue(next(iter(restored.clues.values())).discovered)

    def test_campaign_round_trip_location_required_clues(self) -> None:
        sample = build_sample_campaign(seed=1)
        clue = next(iter(sample.campaign.clues.values()))
        sample.location.requires_clue_ids.append(clue.id)

        restored = campaign_from_dict(campaign_to_dict(sample.campaign))

        location = next(iter(restored.locations.values()))
        self.assertEqual(location.requires_clue_ids, [clue.id])

    def test_campaign_round_trip_encounter(self) -> None:
        sample = build_sample_campaign(seed=1)
        sample.tools.add_encounter(
            sample.campaign.id,
            title="Ash Goblin Ambush",
            location_id=sample.location.id,
            monsters=[Monster(name="Ash Goblin", armor_class=13, max_hp=7, current_hp=7)],
        )

        restored = campaign_from_dict(campaign_to_dict(sample.campaign))

        self.assertEqual(len(restored.encounters), 2)
        encounter = next(iter(restored.encounters.values()))
        self.assertTrue(any(monster.name == "Ash Goblin" for encounter in restored.encounters.values() for monster in encounter.monsters))

    def test_campaign_round_trip_monster_saves(self) -> None:
        sample = build_sample_campaign(seed=1)
        sample.tools.add_encounter(
            sample.campaign.id,
            title="Ash Goblin Ambush",
            location_id=sample.location.id,
            monsters=[
                Monster(
                    name="Ash Goblin Scout",
                    armor_class=13,
                    max_hp=7,
                    current_hp=7,
                    ability_scores={"str": 8, "dex": 14, "con": 10, "int": 10, "wis": 9, "cha": 8},
                    saving_throw_proficiencies={"dex"},
                    proficiency_bonus=2,
                    damage_resistances={"fire"},
                    damage_vulnerabilities={"radiant"},
                    damage_immunities={"poison"},
                    damage_type="slashing",
                )
            ],
        )

        restored = campaign_from_dict(campaign_to_dict(sample.campaign))
        monster = next(
            monster
            for encounter in restored.encounters.values()
            for monster in encounter.monsters
            if monster.name == "Ash Goblin Scout"
        )

        self.assertEqual(monster.ability_scores["dex"], 14)
        self.assertEqual(monster.saving_throw_proficiencies, {"dex"})
        self.assertEqual(monster.saving_throw_modifier("dex"), 4)
        self.assertEqual(monster.damage_resistances, {"fire"})
        self.assertEqual(monster.damage_vulnerabilities, {"radiant"})
        self.assertEqual(monster.damage_immunities, {"poison"})
        self.assertEqual(monster.damage_type, "slashing")

    def test_campaign_round_trip_clue_check(self) -> None:
        sample = build_sample_campaign(seed=1)
        sample.campaign.add_clue(
            Clue(
                title="Silver Ash",
                public_text="The ash points toward the road.",
                location_id=sample.location.id,
                check={"skill": "survival", "dc": 12, "mode": "normal", "label": "Survival"},
            )
        )

        restored = campaign_from_dict(campaign_to_dict(sample.campaign))
        clue = next(clue for clue in restored.clues.values() if clue.title == "Silver Ash")

        self.assertEqual(clue.check["skill"], "survival")
        self.assertEqual(clue.check["dc"], 12)

    def test_campaign_save_and_load_file(self) -> None:
        sample = build_sample_campaign(seed=1)
        handle_player_action(sample, "look around")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "campaign.json"
            save_campaign(sample.campaign, path)
            restored = load_campaign(path)

        self.assertEqual(restored.title, "The Bell Beneath Ashford")
        self.assertEqual(restored.session_log[0].actor, "Kael")

    def test_character_spellcasting_round_trip(self) -> None:
        sample = build_sample_campaign(seed=1)
        sample.tools.add_character(
            sample.campaign.id,
            Character(
                name="Leth",
                player_name="Player",
                class_name="Cleric",
                level=5,
                ancestry="Human",
                ability_scores={"str": 10, "dex": 10, "con": 14, "int": 10, "wis": 16, "cha": 12},
                armor_class=16,
                max_hp=38,
                current_hp=38,
                damage_resistances={"fire"},
                spellcasting=Spellcasting(
                    ability="wis",
                    slots_by_level={1: 4, 2: 3},
                    expended_slots_by_level={1: 1},
                    known_spells=[Spell("Cure Wounds", 1, school="evocation")],
                    prepared_spell_names={"Cure Wounds"},
                ),
            ),
        )

        restored = campaign_from_dict(campaign_to_dict(sample.campaign))
        spellcasting = restored.characters["Leth"].spellcasting

        self.assertIsNotNone(spellcasting)
        self.assertEqual(spellcasting.available_slots(1), 3)
        self.assertEqual(restored.characters["Leth"].spell_save_dc, 14)
        self.assertEqual(restored.characters["Leth"].damage_resistances, {"fire"})


if __name__ == "__main__":
    unittest.main()
