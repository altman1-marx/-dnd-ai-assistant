from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .campaign import Campaign, Clue, Encounter, Location, Monster, NPC, Quest, SessionEvent, Visibility
from .character import Character


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
        "conditions": sorted(character.conditions),
        "inventory": list(character.inventory),
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
        conditions=set(data.get("conditions", [])),
        inventory=list(data.get("inventory", [])),
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
        "characters": {name: character_to_dict(character) for name, character in campaign.characters.items()},
        "locations": {
            item_id: {
                "id": location.id,
                "name": location.name,
                "public_description": location.public_description,
                "dm_notes": location.dm_notes,
                "connected_location_ids": location.connected_location_ids,
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
                        "initiative_modifier": monster.initiative_modifier,
                        "attack_bonus": monster.attack_bonus,
                        "damage": monster.damage,
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
                        initiative_modifier=monster.get("initiative_modifier", 0),
                        attack_bonus=monster.get("attack_bonus", 0),
                        damage=monster.get("damage", "1d4"),
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
