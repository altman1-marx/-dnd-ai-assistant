from __future__ import annotations

from .adventure import AdventureDefinition, validate_adventure
from .core.campaign import Campaign, Clue, Encounter, Location, Monster, NPC, Quest, SessionEvent, Visibility


def campaign_from_adventure(adventure: AdventureDefinition) -> Campaign:
    validate_adventure(adventure)
    campaign_data = adventure.campaign
    campaign = Campaign(
        title=campaign_data["title"],
        party_level=campaign_data["party_level"],
        tone=campaign_data["tone"],
        public_lore=campaign_data.get("public_hook", ""),
        dm_secrets=_combine_dm_secrets(adventure),
        current_location_id=adventure.start_location_id,
    )

    for location_data in adventure.locations:
        campaign.add_location(
            Location(
                id=location_data["id"],
                name=location_data["name"],
                public_description=location_data["public_description"],
                dm_notes=location_data.get("dm_notes", ""),
                connected_location_ids=list(location_data.get("connections", [])),
            )
        )

    for npc_data in adventure.npcs:
        campaign.add_npc(
            NPC(
                id=npc_data["id"],
                name=npc_data["name"],
                role=npc_data["role"],
                public_description=npc_data["public_description"],
                dm_secret=npc_data.get("dm_secret", ""),
                attitude=npc_data.get("attitude", "neutral"),
                location_id=npc_data.get("location_id"),
            )
        )

    for clue_data in adventure.clues:
        campaign.add_clue(
            Clue(
                id=clue_data["id"],
                title=clue_data["title"],
                public_text=clue_data["public_text"],
                dm_secret=clue_data.get("dm_secret", ""),
                discovered=clue_data.get("discovered", False),
                location_id=clue_data.get("location_id"),
                check=clue_data.get("check"),
            )
        )

    for quest_data in adventure.quests:
        campaign.add_quest(
            Quest(
                id=quest_data["id"],
                title=quest_data["title"],
                summary=quest_data["summary"],
                status=quest_data.get("status", "active"),
            )
        )

    for encounter_data in adventure.encounters:
        campaign.add_encounter(
            Encounter(
                id=encounter_data["id"],
                title=encounter_data["title"],
                location_id=encounter_data.get("location_id"),
                difficulty=encounter_data.get("difficulty", "medium"),
                trigger=encounter_data.get("trigger", ""),
                reward=encounter_data.get("reward", ""),
                monsters=[_monster_from_data(monster_data) for monster_data in encounter_data.get("monsters", [])],
            )
        )

    campaign.record_event(
        SessionEvent(actor="DM", content=adventure.opening["player_text"], visibility=Visibility.PUBLIC)
    )
    campaign.record_event(
        SessionEvent(actor="DM", content=adventure.opening["dm_notes"], visibility=Visibility.DM_ONLY)
    )
    return campaign


def _monster_from_data(data: dict) -> Monster:
    kwargs = {}
    if "id" in data:
        kwargs["id"] = data["id"]
    return Monster(
        name=data["name"],
        armor_class=data["armor_class"],
        max_hp=data["max_hp"],
        current_hp=data.get("current_hp", data["max_hp"]),
        ability_scores=data.get(
            "ability_scores",
            {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
        ),
        saving_throw_proficiencies=set(data.get("saving_throw_proficiencies", [])),
        proficiency_bonus=data.get("proficiency_bonus", 2),
        damage_resistances=set(data.get("damage_resistances", [])),
        damage_vulnerabilities=set(data.get("damage_vulnerabilities", [])),
        damage_immunities=set(data.get("damage_immunities", [])),
        initiative_modifier=data.get("initiative_modifier", 0),
        attack_bonus=data.get("attack_bonus", 0),
        damage=data.get("damage", "1d4"),
        damage_type=data.get("damage_type", "untyped"),
        **kwargs,
    )


def _combine_dm_secrets(adventure: AdventureDefinition) -> str:
    parts = []
    campaign_secret = adventure.campaign.get("dm_secret", "")
    if campaign_secret:
        parts.append(campaign_secret)
    for ending in adventure.endings:
        parts.append(f"Ending - {ending['title']}: {ending['summary']}")
    return "\n".join(parts)
