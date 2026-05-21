import random
import unittest

from dnd_ai_assistant.adventure import AdventureDefinition, create_adventure_template
from dnd_ai_assistant.adventure_importer import campaign_from_adventure
from dnd_ai_assistant.adventure_runtime import AdventureRuntime, describe_current_location, handle_adventure_action
from dnd_ai_assistant.core.character import Character
from dnd_ai_assistant.core.spells import Spell, Spellcasting


class AdventureRuntimeTests(unittest.TestCase):
    def test_describe_current_location_shows_exits_and_npcs(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        describe_current_location(runtime)
        output = runtime.flush()

        self.assertIn("Village Square", output)
        self.assertIn("Exits: Old Road", output)
        self.assertIn("People here: Mayor Elin", output)

    def test_move_action_updates_current_location_and_records_event(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        keep_going = handle_adventure_action(runtime, "go old road")
        output = runtime.flush()

        self.assertTrue(keep_going)
        self.assertEqual(campaign.current_location_id, "loc_old_road")
        self.assertIn("Old Road", output)
        self.assertTrue(any("Moved to location: Old Road" in event.content for event in campaign.session_log))

    def test_runtime_uses_campaign_action_aliases(self) -> None:
        raw = create_adventure_template("Moonlit Road")
        raw["runtime_actions"] = {
            "study": {"aliases": ["study"], "handler": "inspect"},
            "travel": {"aliases": ["travel"], "handler": "move"},
            "quit": {"aliases": ["stop"], "handler": "quit"},
        }
        campaign = campaign_from_adventure(AdventureDefinition(raw))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "study")
        runtime.flush()
        handle_adventure_action(runtime, "travel old road")

        self.assertTrue(campaign.clues["clue_moon_ash"].discovered)
        self.assertEqual(campaign.current_location_id, "loc_old_road")

    def test_help_lists_runtime_actions(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "help")

        self.assertIn("Available actions", runtime.flush())

    def test_talk_action_speaks_with_current_location_npc(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "talk mayor")
        output = runtime.flush()

        self.assertIn("Mayor Elin:", output)
        self.assertIn("missing travelers", output)
        self.assertTrue(any(event.actor == "Mayor Elin" for event in campaign.session_log))

    def test_talk_action_reports_missing_npc(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "talk stranger")

        self.assertIn("not here", runtime.flush())

    def test_talk_action_reports_empty_location(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        campaign.clues["clue_moon_ash"].discovered = True
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "go old road")
        runtime.flush()
        handle_adventure_action(runtime, "talk")

        self.assertIn("no one here", runtime.flush())

    def test_encounter_action_shows_current_location_encounter(self) -> None:
        raw = create_adventure_template("Moonlit Road")
        raw["encounters"][0]["monsters"] = [
            {"name": "Lantern Sprite", "armor_class": 13, "max_hp": 7, "current_hp": 7}
        ]
        campaign = campaign_from_adventure(AdventureDefinition(raw))
        campaign.clues["clue_moon_ash"].discovered = True
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "go old road")
        runtime.flush()
        handle_adventure_action(runtime, "fight")
        output = runtime.flush()

        self.assertIn("Encounter - Lantern Sprites", output)
        self.assertIn("Lantern Sprite (AC 13, HP 7/7)", output)
        self.assertTrue(any("Encounter started: Lantern Sprites" in event.content for event in campaign.session_log))

    def test_encounter_action_creates_active_combat(self) -> None:
        raw = create_adventure_template("Moonlit Road")
        raw["encounters"][0]["monsters"] = [
            {"name": "Lantern Sprite", "armor_class": 13, "max_hp": 7, "current_hp": 7, "initiative_modifier": 2}
        ]
        campaign = campaign_from_adventure(AdventureDefinition(raw))
        campaign.add_character(_scout())
        campaign.clues["clue_moon_ash"].discovered = True
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "go old road")
        runtime.flush()
        handle_adventure_action(runtime, "fight")
        output = runtime.flush()

        self.assertIsNotNone(campaign.active_combat)
        self.assertEqual(campaign.active_combat["encounter_id"], "enc_lantern_sprites")
        self.assertIn("Lantern Sprite", [entry["name"] for entry in campaign.active_combat["initiative"]])
        self.assertIn("Initiative order", output)
        self.assertIn("Current turn", output)

    def test_combat_status_reports_active_combat(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        campaign.active_combat = {
            "round": 1,
            "turn": "Kael",
            "initiative": [{"name": "Kael", "initiative_total": 18}, {"name": "Goblin", "initiative_total": 12}],
        }
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "combat")
        output = runtime.flush()

        self.assertIn("round 1", output)
        self.assertIn("turn: Kael", output)
        self.assertIn("Kael 18", output)

    def test_end_turn_advances_active_combat(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        campaign.active_combat = {
            "round": 1,
            "turn": "Kael",
            "initiative": [{"name": "Kael", "initiative_total": 18}, {"name": "Goblin", "initiative_total": 12}],
        }
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "end turn")
        first_output = runtime.flush()
        handle_adventure_action(runtime, "end turn")
        second_output = runtime.flush()

        self.assertIn("turn: Goblin", first_output)
        self.assertIn("round 2, turn: Kael", second_output)
        self.assertEqual(campaign.active_combat["round"], 2)

    def test_end_turn_runs_automatic_monster_action(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        campaign.add_character(_scout())
        campaign.active_combat = {
            "round": 1,
            "turn": "Kael",
            "initiative": [
                {"name": "Kael", "initiative_total": 18, "is_player": True, "armor_class": 14, "current_hp": 12},
                {
                    "name": "Lantern Sprite",
                    "initiative_total": 12,
                    "is_player": False,
                    "armor_class": 13,
                    "current_hp": 7,
                    "attack_bonus": 20,
                    "damage": "1d4+2",
                },
            ],
            "resources": {
                "Kael": {"action": False, "bonus_action": True, "reaction": True, "movement": 0},
                "Lantern Sprite": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
            },
        }
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "end turn")
        output = runtime.flush()

        self.assertIn("Automatic monster action", output)
        self.assertIn("Lantern Sprite attacks Kael", output)
        self.assertIn("round 2, turn: Kael", output)
        self.assertTrue(any(event.actor == "System" and "Automatic monster action" in event.content for event in campaign.session_log))
        self.assertEqual(campaign.active_combat["turn"], "Kael")
        self.assertLess(campaign.characters["Kael"].current_hp, campaign.characters["Kael"].max_hp)

    def test_end_turn_skips_defeated_combatants(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        campaign.active_combat = {
            "round": 1,
            "turn": "Kael",
            "initiative": [
                {"name": "Kael", "initiative_total": 18, "is_player": True, "current_hp": 12},
                {"name": "Fallen Sprite", "initiative_total": 14, "is_player": False, "current_hp": 0},
                {"name": "Mira", "initiative_total": 12, "is_player": True, "current_hp": 9},
            ],
            "resources": {
                "Kael": {"action": False, "bonus_action": True, "reaction": True, "movement": 0},
                "Fallen Sprite": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
                "Mira": {"action": False, "bonus_action": False, "reaction": False, "movement": 0},
            },
        }
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "end turn")
        output = runtime.flush()

        self.assertEqual(campaign.active_combat["turn"], "Mira")
        self.assertIn("turn: Mira", output)
        self.assertTrue(campaign.active_combat["resources"]["Mira"]["action"])
        self.assertTrue(campaign.active_combat["resources"]["Mira"]["bonus_action"])

    def test_combat_resource_actions_spend_current_turn_resources(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        campaign.active_combat = {
            "round": 1,
            "turn": "Kael",
            "initiative": [{"name": "Kael", "initiative_total": 18}],
            "resources": {"Kael": {"action": True, "bonus_action": True, "reaction": True, "movement": 30}},
        }
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "use action")
        runtime.flush()
        handle_adventure_action(runtime, "use action")
        output = runtime.flush()
        handle_adventure_action(runtime, "spend movement 10")
        movement_output = runtime.flush()

        self.assertFalse(campaign.active_combat["resources"]["Kael"]["action"])
        self.assertIn("already used action", output)
        self.assertEqual(campaign.active_combat["resources"]["Kael"]["movement"], 20)
        self.assertIn("20 feet remaining", movement_output)

    def test_attack_action_hits_target_and_spends_action(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        campaign.add_character(_scout())
        campaign.active_combat = {
            "round": 1,
            "turn": "Lantern Sprite",
            "initiative": [
                {
                    "name": "Lantern Sprite",
                    "initiative_total": 18,
                    "armor_class": 13,
                    "current_hp": 7,
                    "attack_bonus": 20,
                    "damage": "1d4+2",
                },
                {"name": "Kael", "initiative_total": 12, "armor_class": 14, "current_hp": 12},
            ],
            "resources": {
                "Lantern Sprite": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
                "Kael": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
            },
        }
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "attack kael")
        output = runtime.flush()

        self.assertIn("attacks Kael", output)
        self.assertLess(campaign.characters["Kael"].current_hp, campaign.characters["Kael"].max_hp)
        self.assertFalse(campaign.active_combat["resources"]["Lantern Sprite"]["action"])

    def test_attack_action_reports_missing_target(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        campaign.active_combat = {
            "round": 1,
            "turn": "Kael",
            "initiative": [{"name": "Kael", "initiative_total": 18, "armor_class": 14, "current_hp": 12}],
            "resources": {"Kael": {"action": True, "bonus_action": True, "reaction": True, "movement": 30}},
        }
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "attack dragon")

        self.assertIn("Target is not in active combat", runtime.flush())

    def test_attack_action_respects_character_damage_resistance(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        scout = _scout()
        scout.damage_resistances.add("fire")
        campaign.add_character(scout)
        campaign.active_combat = {
            "round": 1,
            "turn": "Lantern Sprite",
            "initiative": [
                {
                    "name": "Lantern Sprite",
                    "initiative_total": 18,
                    "armor_class": 13,
                    "current_hp": 7,
                    "attack_bonus": 20,
                    "damage": "8",
                    "damage_type": "fire",
                },
                {"name": "Kael", "initiative_total": 12, "armor_class": 14, "current_hp": 12},
            ],
            "resources": {
                "Lantern Sprite": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
                "Kael": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
            },
        }
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "attack kael")
        output = runtime.flush()

        self.assertEqual(campaign.characters["Kael"].current_hp, 8)
        self.assertEqual(campaign.active_combat["initiative"][1]["current_hp"], 8)
        self.assertIn("4 fire damage (8 before adjustments)", output)

    def test_damage_can_break_concentration(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        caster = _caster()
        caster.max_hp = 100
        caster.current_hp = 100
        caster.spellcasting.concentration_spell_name = "Bless"
        campaign.add_character(caster)
        campaign.active_combat = {
            "round": 1,
            "turn": "Lantern Sprite",
            "initiative": [
                {
                    "name": "Lantern Sprite",
                    "initiative_total": 18,
                    "is_player": False,
                    "armor_class": 13,
                    "current_hp": 7,
                    "attack_bonus": 20,
                    "damage": "60",
                },
                {"name": "Leth", "initiative_total": 12, "is_player": True, "armor_class": 16, "current_hp": 100},
            ],
            "resources": {
                "Lantern Sprite": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
                "Leth": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
            },
        }
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "attack leth")
        output = runtime.flush()

        self.assertIsNone(campaign.characters["Leth"].spellcasting.concentration_spell_name)
        self.assertIn("Concentration check", output)
        self.assertIn("Concentration on Bless ends", output)

    def test_successful_concentration_check_keeps_spell(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        caster = _caster()
        caster.spellcasting.concentration_spell_name = "Bless"
        campaign.add_character(caster)
        campaign.active_combat = {
            "round": 1,
            "turn": "Lantern Sprite",
            "initiative": [
                {
                    "name": "Lantern Sprite",
                    "initiative_total": 18,
                    "is_player": False,
                    "armor_class": 13,
                    "current_hp": 7,
                    "attack_bonus": 20,
                    "damage": "1",
                },
                {"name": "Leth", "initiative_total": 12, "is_player": True, "armor_class": 16, "current_hp": 24},
            ],
            "resources": {
                "Lantern Sprite": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
                "Leth": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
            },
        }
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "attack leth")
        output = runtime.flush()

        self.assertEqual(campaign.characters["Leth"].spellcasting.concentration_spell_name, "Bless")
        self.assertIn("Concentration check", output)
        self.assertIn("success", output)

    def test_attack_action_respects_combatant_damage_immunity(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        campaign.add_character(_scout())
        campaign.active_combat = {
            "round": 1,
            "turn": "Kael",
            "initiative": [
                {
                    "name": "Kael",
                    "initiative_total": 18,
                    "armor_class": 14,
                    "current_hp": 12,
                    "attack_bonus": 20,
                    "damage": "8",
                    "damage_type": "poison",
                },
                {
                    "name": "Training Dummy",
                    "initiative_total": 12,
                    "armor_class": 10,
                    "current_hp": 10,
                    "damage_immunities": ["poison"],
                },
            ],
            "resources": {
                "Kael": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
                "Training Dummy": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
            },
        }
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "attack dummy")
        output = runtime.flush()

        self.assertEqual(campaign.active_combat["initiative"][1]["current_hp"], 10)
        self.assertIn("0 poison damage (8 before adjustments)", output)

    def test_attack_action_resolves_encounter_when_hostiles_are_defeated(self) -> None:
        raw = create_adventure_template("Moonlit Road")
        raw["encounters"][0]["monsters"] = [
            {"name": "Lantern Sprite", "armor_class": 10, "max_hp": 1, "current_hp": 1}
        ]
        campaign = campaign_from_adventure(AdventureDefinition(raw))
        campaign.add_character(_scout())
        campaign.active_combat = {
            "encounter_id": "enc_lantern_sprites",
            "round": 1,
            "turn": "Kael",
            "initiative": [
                {
                    "name": "Kael",
                    "initiative_total": 18,
                    "is_player": True,
                    "armor_class": 14,
                    "current_hp": 12,
                    "attack_bonus": 20,
                    "damage": "8",
                },
                {
                    "name": "Lantern Sprite",
                    "initiative_total": 12,
                    "is_player": False,
                    "armor_class": 10,
                    "current_hp": 1,
                },
            ],
            "resources": {
                "Kael": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
                "Lantern Sprite": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
            },
        }
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "attack sprite")
        output = runtime.flush()

        self.assertIsNone(campaign.active_combat)
        self.assertTrue(campaign.encounters["enc_lantern_sprites"].resolved)
        self.assertIn("All hostile combatants are defeated", output)

    def test_attack_action_ends_combat_when_players_are_defeated(self) -> None:
        raw = create_adventure_template("Moonlit Road")
        campaign = campaign_from_adventure(AdventureDefinition(raw))
        scout = _scout()
        scout.current_hp = 1
        campaign.add_character(scout)
        campaign.active_combat = {
            "encounter_id": "enc_lantern_sprites",
            "round": 1,
            "turn": "Lantern Sprite",
            "initiative": [
                {
                    "name": "Lantern Sprite",
                    "initiative_total": 18,
                    "is_player": False,
                    "armor_class": 13,
                    "current_hp": 7,
                    "attack_bonus": 20,
                    "damage": "8",
                },
                {"name": "Kael", "initiative_total": 12, "is_player": True, "armor_class": 14, "current_hp": 1},
            ],
            "resources": {
                "Lantern Sprite": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
                "Kael": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
            },
        }
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "attack kael")
        output = runtime.flush()

        self.assertIsNone(campaign.active_combat)
        self.assertFalse(campaign.encounters["enc_lantern_sprites"].resolved)
        self.assertIn("unconscious", campaign.characters["Kael"].conditions)
        self.assertIn("Combat ended: Lantern Sprites", output)
        self.assertIn("All player combatants are defeated", output)

    def test_cast_spell_spends_slot_and_action_resource(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        campaign.add_character(_caster())
        campaign.active_combat = {
            "round": 1,
            "turn": "Leth",
            "initiative": [{"name": "Leth", "initiative_total": 18, "armor_class": 16, "current_hp": 24}],
            "resources": {"Leth": {"action": True, "bonus_action": True, "reaction": True, "movement": 30}},
        }
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "cast bless")
        output = runtime.flush()

        caster = campaign.characters["Leth"]
        self.assertFalse(campaign.active_combat["resources"]["Leth"]["action"])
        self.assertEqual(caster.spellcasting.available_slots(1), 1)
        self.assertEqual(caster.spellcasting.concentration_spell_name, "Bless")
        self.assertIn("casts Bless using a level 1 slot", output)

    def test_cast_bonus_action_spell_spends_bonus_action(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        campaign.add_character(_caster())
        campaign.active_combat = {
            "round": 1,
            "turn": "Leth",
            "initiative": [{"name": "Leth", "initiative_total": 18, "armor_class": 16, "current_hp": 24}],
            "resources": {"Leth": {"action": True, "bonus_action": True, "reaction": True, "movement": 30}},
        }
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "cast healing word")

        self.assertTrue(campaign.active_combat["resources"]["Leth"]["action"])
        self.assertFalse(campaign.active_combat["resources"]["Leth"]["bonus_action"])
        self.assertEqual(campaign.characters["Leth"].spellcasting.available_slots(1), 1)

    def test_healing_spell_restores_target_hp_and_syncs_combat(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        caster = _caster()
        target = _scout()
        target.current_hp = 5
        campaign.add_character(caster)
        campaign.add_character(target)
        campaign.active_combat = {
            "round": 1,
            "turn": "Leth",
            "initiative": [
                {"name": "Leth", "initiative_total": 18, "armor_class": 16, "current_hp": 24},
                {"name": "Kael", "initiative_total": 12, "armor_class": 14, "current_hp": 5},
            ],
            "resources": {"Leth": {"action": True, "bonus_action": True, "reaction": True, "movement": 30}},
        }
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "cast cure wounds kael")
        output = runtime.flush()

        self.assertGreater(campaign.characters["Kael"].current_hp, 5)
        self.assertEqual(campaign.active_combat["initiative"][1]["current_hp"], campaign.characters["Kael"].current_hp)
        self.assertIn("Kael heals", output)

    def test_healing_spell_invalid_target_does_not_spend_resources(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        campaign.add_character(_caster())
        campaign.active_combat = {
            "round": 1,
            "turn": "Leth",
            "initiative": [{"name": "Leth", "initiative_total": 18, "armor_class": 16, "current_hp": 12}],
            "resources": {"Leth": {"action": True, "bonus_action": True, "reaction": True, "movement": 30}},
        }
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "cast cure wounds stranger")
        output = runtime.flush()

        self.assertTrue(campaign.active_combat["resources"]["Leth"]["action"])
        self.assertEqual(campaign.characters["Leth"].spellcasting.available_slots(1), 2)
        self.assertIn("healing has no valid target", output)

    def test_sacred_flame_forces_save_and_deals_radiant_damage(self) -> None:
        raw = create_adventure_template("Moonlit Road")
        raw["encounters"][0]["monsters"] = [
            {
                "name": "Lantern Sprite",
                "armor_class": 13,
                "max_hp": 7,
                "current_hp": 7,
                "ability_scores": {"str": 8, "dex": 8, "con": 10, "int": 10, "wis": 10, "cha": 10},
            }
        ]
        campaign = campaign_from_adventure(AdventureDefinition(raw))
        campaign.add_character(_caster())
        campaign.active_combat = {
            "encounter_id": "enc_lantern_sprites",
            "round": 1,
            "turn": "Leth",
            "initiative": [
                {"name": "Leth", "initiative_total": 18, "is_player": True, "armor_class": 16, "current_hp": 24},
                {
                    "name": "Lantern Sprite",
                    "initiative_total": 12,
                    "is_player": False,
                    "armor_class": 13,
                    "current_hp": 7,
                },
            ],
            "resources": {
                "Leth": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
                "Lantern Sprite": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
            },
        }
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "cast sacred flame sprite")
        output = runtime.flush()

        self.assertLess(campaign.encounters["enc_lantern_sprites"].monsters[0].current_hp, 7)
        self.assertFalse(campaign.active_combat["resources"]["Leth"]["action"])
        self.assertEqual(campaign.characters["Leth"].spellcasting.available_slots(1), 2)
        self.assertIn("Dexterity save", output)
        self.assertIn("radiant damage", output)

    def test_spell_damage_resolves_encounter_when_hostiles_are_defeated(self) -> None:
        raw = create_adventure_template("Moonlit Road")
        raw["encounters"][0]["monsters"] = [
            {
                "name": "Lantern Sprite",
                "armor_class": 13,
                "max_hp": 1,
                "current_hp": 1,
                "ability_scores": {"str": 8, "dex": 8, "con": 10, "int": 10, "wis": 10, "cha": 10},
            }
        ]
        campaign = campaign_from_adventure(AdventureDefinition(raw))
        campaign.add_character(_caster())
        campaign.active_combat = {
            "encounter_id": "enc_lantern_sprites",
            "round": 1,
            "turn": "Leth",
            "initiative": [
                {"name": "Leth", "initiative_total": 18, "is_player": True, "armor_class": 16, "current_hp": 24},
                {
                    "name": "Lantern Sprite",
                    "initiative_total": 12,
                    "is_player": False,
                    "armor_class": 13,
                    "current_hp": 1,
                },
            ],
            "resources": {
                "Leth": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
                "Lantern Sprite": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
            },
        }
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "cast sacred flame sprite")
        output = runtime.flush()

        self.assertIsNone(campaign.active_combat)
        self.assertTrue(campaign.encounters["enc_lantern_sprites"].resolved)
        self.assertIn("All hostile combatants are defeated", output)

    def test_burning_hands_damages_multiple_hostile_targets(self) -> None:
        raw = create_adventure_template("Moonlit Road")
        raw["encounters"][0]["monsters"] = [
            {
                "name": "Lantern Sprite",
                "armor_class": 13,
                "max_hp": 20,
                "current_hp": 20,
                "ability_scores": {"str": 8, "dex": 8, "con": 10, "int": 10, "wis": 10, "cha": 10},
            },
            {
                "name": "Ash Imp",
                "armor_class": 12,
                "max_hp": 20,
                "current_hp": 20,
                "ability_scores": {"str": 8, "dex": 18, "con": 10, "int": 10, "wis": 10, "cha": 10},
            },
        ]
        campaign = campaign_from_adventure(AdventureDefinition(raw))
        campaign.add_character(_caster())
        campaign.active_combat = {
            "encounter_id": "enc_lantern_sprites",
            "round": 1,
            "turn": "Leth",
            "initiative": [
                {"name": "Leth", "initiative_total": 18, "is_player": True, "armor_class": 16, "current_hp": 24},
                {
                    "name": "Lantern Sprite",
                    "initiative_total": 12,
                    "is_player": False,
                    "armor_class": 13,
                    "current_hp": 20,
                },
                {"name": "Ash Imp", "initiative_total": 10, "is_player": False, "armor_class": 12, "current_hp": 20},
            ],
            "resources": {
                "Leth": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
                "Lantern Sprite": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
                "Ash Imp": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
            },
        }
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "cast burning hands")
        output = runtime.flush()

        self.assertLess(campaign.encounters["enc_lantern_sprites"].monsters[0].current_hp, 20)
        self.assertLess(campaign.encounters["enc_lantern_sprites"].monsters[1].current_hp, 20)
        self.assertFalse(campaign.active_combat["resources"]["Leth"]["action"])
        self.assertEqual(campaign.characters["Leth"].spellcasting.available_slots(1), 1)
        self.assertIn("Burning Hands hits 2 hostile target", output)
        self.assertIn("fire damage", output)

    def test_burning_hands_resolves_encounter_when_all_hostiles_fall(self) -> None:
        raw = create_adventure_template("Moonlit Road")
        raw["encounters"][0]["monsters"] = [
            {
                "name": "Lantern Sprite",
                "armor_class": 13,
                "max_hp": 1,
                "current_hp": 1,
                "ability_scores": {"str": 8, "dex": 8, "con": 10, "int": 10, "wis": 10, "cha": 10},
            },
            {
                "name": "Ash Imp",
                "armor_class": 12,
                "max_hp": 1,
                "current_hp": 1,
                "ability_scores": {"str": 8, "dex": 8, "con": 10, "int": 10, "wis": 10, "cha": 10},
            },
        ]
        campaign = campaign_from_adventure(AdventureDefinition(raw))
        campaign.add_character(_caster())
        campaign.active_combat = {
            "encounter_id": "enc_lantern_sprites",
            "round": 1,
            "turn": "Leth",
            "initiative": [
                {"name": "Leth", "initiative_total": 18, "is_player": True, "armor_class": 16, "current_hp": 24},
                {
                    "name": "Lantern Sprite",
                    "initiative_total": 12,
                    "is_player": False,
                    "armor_class": 13,
                    "current_hp": 1,
                },
                {"name": "Ash Imp", "initiative_total": 10, "is_player": False, "armor_class": 12, "current_hp": 1},
            ],
            "resources": {
                "Leth": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
                "Lantern Sprite": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
                "Ash Imp": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
            },
        }
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "cast burning hands")
        output = runtime.flush()

        self.assertIsNone(campaign.active_combat)
        self.assertTrue(campaign.encounters["enc_lantern_sprites"].resolved)
        self.assertIn("All hostile combatants are defeated", output)

    def test_sacred_flame_invalid_target_does_not_spend_resources(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        campaign.add_character(_caster())
        campaign.active_combat = {
            "round": 1,
            "turn": "Leth",
            "initiative": [{"name": "Leth", "initiative_total": 18, "is_player": True, "armor_class": 16, "current_hp": 24}],
            "resources": {"Leth": {"action": True, "bonus_action": True, "reaction": True, "movement": 30}},
        }
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "cast sacred flame stranger")
        output = runtime.flush()

        self.assertTrue(campaign.active_combat["resources"]["Leth"]["action"])
        self.assertEqual(campaign.characters["Leth"].spellcasting.available_slots(1), 2)
        self.assertIn("spell has no valid target", output)

    def test_guiding_bolt_uses_spell_attack_and_slot(self) -> None:
        raw = create_adventure_template("Moonlit Road")
        raw["encounters"][0]["monsters"] = [
            {"name": "Lantern Sprite", "armor_class": 1, "max_hp": 20, "current_hp": 20}
        ]
        campaign = campaign_from_adventure(AdventureDefinition(raw))
        campaign.add_character(_caster())
        campaign.active_combat = {
            "encounter_id": "enc_lantern_sprites",
            "round": 1,
            "turn": "Leth",
            "initiative": [
                {"name": "Leth", "initiative_total": 18, "is_player": True, "armor_class": 16, "current_hp": 24},
                {
                    "name": "Lantern Sprite",
                    "initiative_total": 12,
                    "is_player": False,
                    "armor_class": 1,
                    "current_hp": 20,
                },
            ],
            "resources": {
                "Leth": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
                "Lantern Sprite": {"action": True, "bonus_action": True, "reaction": True, "movement": 30},
            },
        }
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "cast guiding bolt sprite")
        output = runtime.flush()

        self.assertLess(campaign.encounters["enc_lantern_sprites"].monsters[0].current_hp, 20)
        self.assertFalse(campaign.active_combat["resources"]["Leth"]["action"])
        self.assertEqual(campaign.characters["Leth"].spellcasting.available_slots(1), 1)
        self.assertIn("Guiding Bolt spell attack", output)
        self.assertIn("radiant damage", output)

    def test_failed_spell_cast_does_not_spend_action(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        caster = _caster()
        caster.spellcasting.expend_slot(1)
        caster.spellcasting.expend_slot(1)
        campaign.add_character(caster)
        campaign.active_combat = {
            "round": 1,
            "turn": "Leth",
            "initiative": [{"name": "Leth", "initiative_total": 18, "armor_class": 16, "current_hp": 24}],
            "resources": {"Leth": {"action": True, "bonus_action": True, "reaction": True, "movement": 30}},
        }
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "cast bless")
        output = runtime.flush()

        self.assertTrue(campaign.active_combat["resources"]["Leth"]["action"])
        self.assertIn("No level 1 spell slots remaining", output)

    def test_end_turn_resets_next_turn_resources(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        campaign.active_combat = {
            "round": 1,
            "turn": "Kael",
            "initiative": [{"name": "Kael", "initiative_total": 18}, {"name": "Goblin", "initiative_total": 12}],
            "resources": {
                "Kael": {"action": False, "bonus_action": False, "reaction": False, "movement": 0},
                "Goblin": {"action": False, "bonus_action": False, "reaction": False, "movement": 0},
            },
        }
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "end turn")

        goblin = campaign.active_combat["resources"]["Goblin"]
        self.assertTrue(goblin["action"])
        self.assertTrue(goblin["bonus_action"])
        self.assertFalse(goblin["reaction"])
        self.assertEqual(goblin["movement"], 30)

    def test_resolve_encounter_marks_encounter_done_and_clears_combat(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        campaign.active_combat = {"encounter_id": "enc_lantern_sprites", "round": 1, "turn": "Kael", "initiative": []}
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "resolve encounter")
        output = runtime.flush()

        self.assertIsNone(campaign.active_combat)
        self.assertTrue(campaign.encounters["enc_lantern_sprites"].resolved)
        self.assertIn("Encounter resolved: Lantern Sprites", output)
        self.assertTrue(any("Encounter resolved" in event.content for event in campaign.session_log))

    def test_resolve_encounter_reports_when_none_active(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "resolve encounter")

        self.assertIn("no active encounter", runtime.flush())

    def test_encounter_action_reports_when_none_present(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "fight")

        self.assertIn("no active encounter", runtime.flush())

    def test_quests_action_lists_quest_status(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "quests")
        output = runtime.flush()

        self.assertIn("Quests:", output)
        self.assertIn("[active] Find the Missing Travelers", output)

    def test_complete_quest_updates_status_and_records_event(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "complete quest missing travelers")
        output = runtime.flush()

        self.assertEqual(campaign.quests["quest_find_travelers"].status, "completed")
        self.assertIn("active -> completed", output)
        self.assertTrue(any("Quest status changed" in event.content for event in campaign.session_log))

    def test_fail_quest_updates_status(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "abandon quest")

        self.assertEqual(campaign.quests["quest_find_travelers"].status, "failed")
        self.assertIn("active -> failed", runtime.flush())

    def test_complete_quest_reports_missing_target(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "complete quest dragon")

        self.assertIn("Quest not found", runtime.flush())

    def test_move_rejects_unconnected_location(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "go moonlit glade")

        self.assertEqual(campaign.current_location_id, "loc_village_square")
        self.assertIn("cannot reach", runtime.flush())

    def test_move_rejects_location_when_required_clue_is_missing(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "go old road")
        runtime.flush()
        handle_adventure_action(runtime, "go moonlit glade")
        output = runtime.flush()

        self.assertEqual(campaign.current_location_id, "loc_old_road")
        self.assertIn("Find more clues", output)

    def test_move_allows_location_when_required_clue_is_discovered(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "inspect")
        runtime.flush()
        handle_adventure_action(runtime, "go old road")
        runtime.flush()
        handle_adventure_action(runtime, "go moonlit glade")

        self.assertEqual(campaign.current_location_id, "loc_moonlit_glade")
        self.assertIn("Moonlit Glade", runtime.flush())

    def test_inspect_reveals_current_location_clues(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "inspect")
        output = runtime.flush()

        clue = campaign.clues["clue_moon_ash"]
        self.assertTrue(clue.discovered)
        self.assertIn("Clue found - Moonlit Ash", output)
        self.assertTrue(any("Clue revealed: Moonlit Ash" in event.content for event in campaign.session_log))

    def test_inspect_target_reveals_matching_clue(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "inspect ash")
        output = runtime.flush()

        self.assertTrue(campaign.clues["clue_moon_ash"].discovered)
        self.assertIn("Clue found - Moonlit Ash", output)

    def test_inspect_target_reports_no_match(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "inspect statue")

        self.assertFalse(campaign.clues["clue_moon_ash"].discovered)
        self.assertIn("matching", runtime.flush())

    def test_inspect_reports_when_no_new_clues_remain(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "inspect")
        runtime.flush()
        handle_adventure_action(runtime, "inspect")

        self.assertIn("no new clues", runtime.flush())

    def test_inspect_uses_clue_skill_check_when_character_exists(self) -> None:
        raw = create_adventure_template("Moonlit Road")
        raw["clues"][0]["check"] = {"skill": "survival", "dc": 10, "mode": "normal", "label": "Survival"}
        campaign = campaign_from_adventure(AdventureDefinition(raw))
        campaign.add_character(_scout())
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "inspect")
        output = runtime.flush()

        self.assertTrue(campaign.clues["clue_moon_ash"].discovered)
        self.assertIn("rolls Survival", output)
        self.assertIn("success", output)

    def test_inspect_keeps_checked_clue_hidden_on_failure(self) -> None:
        raw = create_adventure_template("Moonlit Road")
        raw["clues"][0]["check"] = {"skill": "survival", "dc": 20, "mode": "normal", "label": "Survival"}
        campaign = campaign_from_adventure(AdventureDefinition(raw))
        campaign.add_character(_scout())
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "inspect")
        output = runtime.flush()

        self.assertFalse(campaign.clues["clue_moon_ash"].discovered)
        self.assertIn("failure", output)
        self.assertIn("do not find anything new", output)

    def test_quit_stops_runtime(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        runtime = AdventureRuntime(campaign)

        self.assertFalse(handle_adventure_action(runtime, "quit"))

    def test_death_save_third_success_stabilizes_character(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        scout = _scout()
        scout.current_hp = 0
        scout.conditions.add("unconscious")
        scout.death_save_successes = 2
        campaign.add_character(scout)
        runtime = AdventureRuntime(campaign, rng=random.Random(9))

        handle_adventure_action(runtime, "death save kael")
        output = runtime.flush()

        self.assertIn("stable", campaign.characters["Kael"].conditions)
        self.assertIn("unconscious", campaign.characters["Kael"].conditions)
        self.assertEqual(campaign.characters["Kael"].death_save_successes, 0)
        self.assertEqual(campaign.characters["Kael"].death_save_failures, 0)
        self.assertIn("succeeds on a death save", output)

    def test_death_save_third_failure_marks_character_dead(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        scout = _scout()
        scout.current_hp = 0
        scout.conditions.add("unconscious")
        scout.death_save_failures = 2
        campaign.add_character(scout)
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "death save kael")

        self.assertIn("dead", campaign.characters["Kael"].conditions)
        self.assertEqual(campaign.characters["Kael"].death_save_failures, 3)

    def test_death_save_natural_20_revives_character(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        scout = _scout()
        scout.current_hp = 0
        scout.conditions.add("unconscious")
        scout.death_save_failures = 1
        campaign.add_character(scout)
        runtime = AdventureRuntime(campaign, rng=random.Random(5))

        handle_adventure_action(runtime, "death save kael")

        self.assertEqual(campaign.characters["Kael"].current_hp, 1)
        self.assertNotIn("unconscious", campaign.characters["Kael"].conditions)
        self.assertEqual(campaign.characters["Kael"].death_save_successes, 0)
        self.assertEqual(campaign.characters["Kael"].death_save_failures, 0)

    def test_stabilize_marks_unconscious_character_stable(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        scout = _scout()
        scout.current_hp = 0
        scout.conditions.add("unconscious")
        scout.death_save_failures = 2
        campaign.add_character(scout)
        runtime = AdventureRuntime(campaign)

        handle_adventure_action(runtime, "stabilize kael")

        self.assertEqual(campaign.characters["Kael"].current_hp, 0)
        self.assertIn("stable", campaign.characters["Kael"].conditions)
        self.assertIn("unconscious", campaign.characters["Kael"].conditions)
        self.assertEqual(campaign.characters["Kael"].death_save_failures, 0)

    def test_damage_to_unconscious_character_adds_death_save_failure(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        scout = _scout()
        scout.current_hp = 0
        scout.conditions.update({"unconscious", "stable"})
        campaign.add_character(scout)
        campaign.active_combat = {
            "round": 1,
            "turn": "Lantern Sprite",
            "initiative": [
                {
                    "name": "Lantern Sprite",
                    "initiative_total": 18,
                    "is_player": False,
                    "armor_class": 13,
                    "current_hp": 7,
                    "attack_bonus": 20,
                    "damage": "1",
                },
                {"name": "Kael", "initiative_total": 12, "is_player": True, "armor_class": 14, "current_hp": 0},
            ],
            "resources": {"Lantern Sprite": {"action": True, "bonus_action": True, "reaction": True, "movement": 30}},
        }
        runtime = AdventureRuntime(campaign, rng=random.Random(1))

        handle_adventure_action(runtime, "attack kael")
        output = runtime.flush()

        self.assertEqual(campaign.characters["Kael"].death_save_failures, 1)
        self.assertNotIn("stable", campaign.characters["Kael"].conditions)
        self.assertIn("takes damage while unconscious", output)


def _scout() -> Character:
    return Character(
        name="Kael",
        player_name="Player",
        class_name="Ranger",
        level=1,
        ancestry="Human",
        ability_scores={"str": 10, "dex": 14, "con": 12, "int": 10, "wis": 16, "cha": 8},
        armor_class=14,
        max_hp=12,
        current_hp=12,
        skill_proficiencies={"survival"},
    )


def _caster() -> Character:
    return Character(
        name="Leth",
        player_name="Player",
        class_name="Cleric",
        level=3,
        ancestry="Human",
        ability_scores={"str": 10, "dex": 10, "con": 14, "int": 10, "wis": 16, "cha": 12},
        armor_class=16,
        max_hp=24,
        current_hp=24,
        spellcasting=Spellcasting(
            ability="wis",
            slots_by_level={1: 2},
            known_spells=[
                Spell("Bless", 1, concentration=True),
                Spell("Burning Hands", 1),
                Spell("Cure Wounds", 1),
                Spell("Guiding Bolt", 1),
                Spell("Healing Word", 1, casting_time="1 bonus action"),
                Spell("Sacred Flame", 0),
            ],
        ),
    )


if __name__ == "__main__":
    unittest.main()
