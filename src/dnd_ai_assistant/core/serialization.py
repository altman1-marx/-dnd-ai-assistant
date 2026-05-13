from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .campaign import Campaign, Clue, Encounter, Location, Monster, NPC, Quest, SessionEvent, Visibility
from .character import Character
from .spells import Spell, Spellcasting


def spell_to_dict(spell: Spell) -> dict:
    return {
        "name": spell.name,
        "level": spell.level,
        "school": spell.school,
        "casting_time": spell.casting_time,
        "range_text": spell.range_text,
        "components": spell.components,
        "duration": spell.duration,
        "concentration": spell.concentration,
        "description": spell.description,
    }


def spell_from_dict(data: dict) -> Spell:
    return Spell(
        name=data["name"],
        level=data["level"],
        school=data.get("school", ""),
        casting_time=data.get("casting_time", "1 action"),
        range_text=data.get("range_text", ""),
        components=data.get("components", ""),
        duration=data.get("duration", ""),
        concentration=data.get("concentration", False),
        description=data.get("description", ""),
    )


def spellcasting_to_dict(spellcasting: Spellcasting | None) -> dict | None:
    if spellcasting is None:
        return None
    return {
        "ability": spellcasting.ability,
        "slots_by_level": {str(level): slots for level, slots in spellcasting.slots_by_level.items()},
        "expended_slots_by_level": {
            str(level): slots for level, slots in spellcasting.expended_slots_by_level.items()
        },
        "known_spells": [spell_to_dict(spell) for spell in spellcasting.known_spells],
        "prepared_spell_names": sorted(spellcasting.prepared_spell_names),
        "concentration_spell_name": spellcasting.concentration_spell_name,
    }


def spellcasting_from_dict(data: dict | None) -> Spellcasting | None:
    if data is None:
        return None
    return Spellcasting(
        ability=data["ability"],
        slots_by_level={int(level): slots for level, slots in data.get("slots_by_level", {}).items()},
        expended_slots_by_level={
            int(level): slots for level, slots in data.get("expended_slots_by_level", {}).items()
        },
        known_spells=[spell_from_dict(spell) for spell in data.get("known_spells", [])],
        prepared_spell_names=set(data.get("prepared_spell_names", [])),
        concentration_spell_name=data.get("concentration_spell_name"),
    )


def character_to_dict(character: Character) -> dict:
    return {
        "name": character.name,
        "player_name": character.player_name,
        "class_name": character.class_name,
        "level": character.level,
        "ancestry": character.ancestry,
        "ability_scores": character.ability_scores,
        "armor_class": character.armor_class,
        "max_hp": character.max_hp,
        "current_hp": character.current_hp,
        "skill_proficiencies": sorted(character.skill_proficiencies),
        "saving_throw_proficiencies": sorted(character.saving_throw_proficiencies),
        "damage_resistances": sorted(character.damage_resistances),
        "damage_vulnerabilities": sorted(character.damage_vulnerabilities),
        "damage_immunities": sorted(character.damage_immunities),
        "conditions": sorted(character.conditions),
        "inventory": list(character.inventory),
        "spellcasting": spellcasting_to_dict(character.spellcasting),
    }


def character_from_dict(data: dict) -> Character:
    return Character(
        name=data["name"],
        player_name=data["player_name"],
        class_name=data["class_name"],
        level=data["level"],
        ancestry=data["ancestry"],
        ability_scores=data["ability_scores"],
        armor_class=data["armor_class"],
        max_hp=data["max_hp"],
        current_hp=data["current_hp"],
        skill_proficiencies=set(data.get("skill_proficiencies", [])),
        saving_throw_proficiencies=set(data.get("saving_throw_proficiencies", [])),
        damage_resistances=set(data.get("damage_resistances", [])),
        damage_vulnerabilities=set(data.get("damage_vulnerabilities", [])),
        damage_immunities=set(data.get("damage_immunities", [])),
        conditions=set(data.get("conditions", [])),
        inventory=list(data.get("inventory", [])),
        spellcasting=spellcasting_from_dict(data.get("spellcasting")),
    )


def campaign_to_dict(campaign: Campaign) -> dict:
    return {
        "id": campaign.id,
        "title": campaign.title,
        "system": campaign.system,
        "tone": campaign.tone,
        "party_level": campaign.party_level,
        "public_lore": campaign.public_lore,
        "dm_secrets": campaign.dm_secrets,
        "current_location_id": campaign.current_location_id,
        "characters": {name: character_to_dict(character) for name, character in campaign.characters.items()},
        "locations": {
            item_id: {
                "id": location.id,
                "name": location.name,
                "public_description": location.public_description,
                "dm_notes": location.dm_notes,
                "connected_location_ids": location.connected_location_ids,
                "requires_clue_ids": location.requires_clue_ids,
            }
            for item_id, location in campaign.locations.items()
        },
        "npcs": {
            item_id: {
                "id": npc.id,
                "name": npc.name,
                "role": npc.role,
                "public_description": npc.public_description,
                "dm_secret": npc.dm_secret,
                "attitude": npc.attitude,
                "location_id": npc.location_id,
            }
            for item_id, npc in campaign.npcs.items()
        },
        "clues": {
            item_id: {
                "id": clue.id,
                "title": clue.title,
                "public_text": clue.public_text,
                "dm_secret": clue.dm_secret,
                "discovered": clue.discovered,
                "location_id": clue.location_id,
                "check": clue.check,
            }
            for item_id, clue in campaign.clues.items()
        },
        "quests": {
            item_id: {
                "id": quest.id,
                "title": quest.title,
                "summary": quest.summary,
                "status": quest.status,
            }
            for item_id, quest in campaign.quests.items()
        },
        "encounters": {
            item_id: {
                "id": encounter.id,
                "title": encounter.title,
                "location_id": encounter.location_id,
                "difficulty": encounter.difficulty,
                "trigger": encounter.trigger,
                "reward": encounter.reward,
                "resolved": encounter.resolved,
                "monsters": [
                    {
                        "id": monster.id,
                        "name": monster.name,
                        "armor_class": monster.armor_class,
                        "max_hp": monster.max_hp,
                        "current_hp": monster.current_hp,
                        "ability_scores": monster.ability_scores,
                        "saving_throw_proficiencies": sorted(monster.saving_throw_proficiencies),
                        "proficiency_bonus": monster.proficiency_bonus,
                        "damage_resistances": sorted(monster.damage_resistances),
                        "damage_vulnerabilities": sorted(monster.damage_vulnerabilities),
                        "damage_immunities": sorted(monster.damage_immunities),
                        "initiative_modifier": monster.initiative_modifier,
                        "attack_bonus": monster.attack_bonus,
                        "damage": monster.damage,
                        "damage_type": monster.damage_type,
                    }
                    for monster in encounter.monsters
                ],
            }
            for item_id, encounter in campaign.encounters.items()
        },
        "session_log": [
            {
                "id": event.id,
                "actor": event.actor,
                "content": event.content,
                "visibility": event.visibility.value,
                "created_at": event.created_at.isoformat(),
            }
            for event in campaign.session_log
        ],
    }


def campaign_from_dict(data: dict) -> Campaign:
    campaign = Campaign(
        id=data["id"],
        title=data["title"],
        system=data.get("system", "DND 5e"),
        tone=data.get("tone", "heroic fantasy"),
        party_level=data.get("party_level", 1),
        public_lore=data.get("public_lore", ""),
        dm_secrets=data.get("dm_secrets", ""),
        current_location_id=data.get("current_location_id"),
    )
    for character in data.get("characters", {}).values():
        campaign.add_character(character_from_dict(character))
    for location in data.get("locations", {}).values():
        campaign.add_location(
            Location(
                id=location["id"],
                name=location["name"],
                public_description=location["public_description"],
                dm_notes=location.get("dm_notes", ""),
                connected_location_ids=list(location.get("connected_location_ids", [])),
                requires_clue_ids=list(location.get("requires_clue_ids", [])),
            )
        )
    for npc in data.get("npcs", {}).values():
        campaign.add_npc(
            NPC(
                id=npc["id"],
                name=npc["name"],
                role=npc["role"],
                public_description=npc["public_description"],
                dm_secret=npc.get("dm_secret", ""),
                attitude=npc.get("attitude", "neutral"),
                location_id=npc.get("location_id"),
            )
        )
    for clue in data.get("clues", {}).values():
        campaign.add_clue(
            Clue(
                id=clue["id"],
                title=clue["title"],
                public_text=clue["public_text"],
                dm_secret=clue.get("dm_secret", ""),
                discovered=clue.get("discovered", False),
                location_id=clue.get("location_id"),
                check=clue.get("check"),
            )
        )
    for quest in data.get("quests", {}).values():
        campaign.add_quest(
            Quest(
                id=quest["id"],
                title=quest["title"],
                summary=quest["summary"],
                status=quest.get("status", "active"),
            )
        )
    for encounter in data.get("encounters", {}).values():
        campaign.add_encounter(
            Encounter(
                id=encounter["id"],
                title=encounter["title"],
                location_id=encounter.get("location_id"),
                difficulty=encounter.get("difficulty", "medium"),
                trigger=encounter.get("trigger", ""),
                reward=encounter.get("reward", ""),
                resolved=encounter.get("resolved", False),
                monsters=[
                    Monster(
                        id=monster["id"],
                        name=monster["name"],
                        armor_class=monster["armor_class"],
                        max_hp=monster["max_hp"],
                        current_hp=monster["current_hp"],
                        ability_scores=monster.get(
                            "ability_scores",
                            {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
                        ),
                        saving_throw_proficiencies=set(monster.get("saving_throw_proficiencies", [])),
                        proficiency_bonus=monster.get("proficiency_bonus", 2),
                        damage_resistances=set(monster.get("damage_resistances", [])),
                        damage_vulnerabilities=set(monster.get("damage_vulnerabilities", [])),
                        damage_immunities=set(monster.get("damage_immunities", [])),
                        initiative_modifier=monster.get("initiative_modifier", 0),
                        attack_bonus=monster.get("attack_bonus", 0),
                        damage=monster.get("damage", "1d4"),
                        damage_type=monster.get("damage_type", "untyped"),
                    )
                    for monster in encounter.get("monsters", [])
                ],
            )
        )
    for event in data.get("session_log", []):
        campaign.record_event(
            SessionEvent(
                id=event["id"],
                actor=event["actor"],
                content=event["content"],
                visibility=Visibility(event.get("visibility", Visibility.PUBLIC.value)),
                created_at=datetime.fromisoformat(event["created_at"]),
            )
        )
    return campaign


def save_campaign(campaign: Campaign, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(campaign_to_dict(campaign), ensure_ascii=False, indent=2), encoding="utf-8")


def load_campaign(path: str | Path) -> Campaign:
    return campaign_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
