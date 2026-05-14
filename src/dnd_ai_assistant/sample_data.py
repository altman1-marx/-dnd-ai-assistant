from __future__ import annotations

from .core.character import Character
from .core.spells import Spell, Spellcasting


def sample_adventure_template() -> dict:
    return {
        "campaign": {
            "title": "Moonlit Road",
            "party_level": 1,
            "tone": "heroic fantasy mystery",
            "public_hook": "A village asks for help after strange lights appear near the old road.",
            "dm_secret": "The lights are a lure created by a trapped fey creature.",
        },
        "start_location_id": "loc_village_square",
        "final_location_id": "loc_moonlit_glade",
        "locations": [
            {
                "id": "loc_village_square",
                "name": "Village Square",
                "public_description": "A quiet square where anxious locals gather around a dry fountain.",
                "dm_notes": "The fountain stones point toward the old road when moonlight hits them.",
                "connections": ["loc_old_road"],
            },
            {
                "id": "loc_old_road",
                "name": "Old Road",
                "public_description": "A mossy path under leaning trees and pale lantern-like lights.",
                "dm_notes": "The lights retreat if threatened but approach music or kindness.",
                "connections": ["loc_village_square", "loc_moonlit_glade"],
            },
            {
                "id": "loc_moonlit_glade",
                "name": "Moonlit Glade",
                "public_description": "A silver clearing where roots coil around a cracked stone arch.",
                "dm_notes": "The arch is the source of the fey disturbance.",
                "connections": ["loc_old_road"],
                "requires_clue_ids": ["clue_moon_ash"],
            },
        ],
        "npcs": [
            {
                "id": "npc_mayor_elin",
                "name": "Mayor Elin",
                "role": "worried quest giver",
                "public_description": "A tired mayor clutching a list of missing travelers.",
                "dm_secret": "She once promised the fey protection and forgot the bargain.",
                "dialogue": "Please find the missing travelers before the lights take anyone else.",
                "location_id": "loc_village_square",
            }
        ],
        "clues": [
            {
                "id": "clue_moon_ash",
                "title": "Moonlit Ash",
                "public_text": "Silver ash clings to footprints heading toward the old road.",
                "dm_secret": "The ash falls from the cracked arch in the glade.",
                "location_id": "loc_village_square",
                "check": {
                    "skill": "survival",
                    "dc": 10,
                    "mode": "normal",
                    "label": "Survival",
                },
            }
        ],
        "quests": [
            {
                "id": "quest_find_travelers",
                "title": "Find the Missing Travelers",
                "summary": "Follow the strange lights and discover why travelers vanish near the old road.",
            }
        ],
        "encounters": [
            {
                "id": "enc_lantern_sprites",
                "title": "Lantern Sprites",
                "location_id": "loc_old_road",
                "difficulty": "easy",
                "trigger": "The party follows the lights without caution.",
                "reward": "A sprite offers a moon-silver charm if spared.",
                "monsters": [
                    {
                        "name": "Lantern Sprite",
                        "armor_class": 13,
                        "max_hp": 7,
                        "current_hp": 7,
                        "ability_scores": {"str": 8, "dex": 8, "con": 10, "int": 10, "wis": 10, "cha": 10},
                    }
                ],
            }
        ],
        "endings": [
            {
                "id": "ending_bargain_mended",
                "title": "The Bargain Mended",
                "summary": "The party repairs the broken promise and the missing travelers return.",
            }
        ],
        "opening": {
            "player_text": "The village square is hushed as pale lights flicker beyond the old road.",
            "dm_notes": "Start with Mayor Elin asking the party to investigate before moonrise.",
        },
    }


def sample_adventure_character() -> Character:
    return Character(
        name="Leth",
        player_name="Sample Player",
        class_name="Cleric",
        level=3,
        ancestry="Human",
        ability_scores={"str": 10, "dex": 10, "con": 14, "int": 10, "wis": 16, "cha": 12},
        armor_class=16,
        max_hp=24,
        current_hp=24,
        skill_proficiencies={"insight", "medicine", "religion"},
        saving_throw_proficiencies={"wis", "cha"},
        spellcasting=Spellcasting(
            ability="wis",
            slots_by_level={1: 4, 2: 2},
            known_spells=[
                Spell("Bless", 1, concentration=True),
                Spell("Cure Wounds", 1),
                Spell("Healing Word", 1, casting_time="1 bonus action"),
                Spell("Sacred Flame", 0),
            ],
        ),
    )
