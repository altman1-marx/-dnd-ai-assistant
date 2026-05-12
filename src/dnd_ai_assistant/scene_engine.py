from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

from .core.character import Character
from .core.campaign import Campaign, Clue, Location, Monster
from .core.dm_tools import DMTools
from .core.dnd5e import RollMode
from .scenario import SceneDefinition, load_scene


@dataclass
class SceneSession:
    tools: DMTools
    campaign: Campaign
    hero: Character
    location: Location
    clue: Clue
    scene: SceneDefinition
    inspected: bool = False
    opened_path: bool = False
    transcript: list[str] = field(default_factory=list)

    def narrate(self, line: str) -> None:
        self.transcript.append(line)

    def flush(self) -> str:
        output = "\n".join(self.transcript)
        self.transcript.clear()
        return output


def build_character(scene: SceneDefinition) -> Character:
    data = scene.hero
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
    )


def build_scene_session(seed: int, scene_path: str | Path | None = None) -> SceneSession:
    scene = load_scene(scene_path)
    campaign_data = scene.campaign
    tools = DMTools(rng=random.Random(seed))
    campaign = tools.create_campaign(
        title=campaign_data["title"],
        party_level=campaign_data["party_level"],
        tone=campaign_data["tone"],
        public_lore=campaign_data.get("public_lore", ""),
        dm_secrets=campaign_data.get("dm_secrets", ""),
    ).data

    hero = build_character(scene)
    tools.add_character(campaign.id, hero)

    location_data = scene.location
    location = tools.add_location(
        campaign.id,
        name=location_data["name"],
        public_description=location_data["public_description"],
        dm_notes=location_data.get("dm_notes", ""),
    ).data
    npc_data = scene.npc
    tools.add_npc(
        campaign.id,
        name=npc_data["name"],
        role=npc_data["role"],
        public_description=npc_data["public_description"],
        dm_secret=npc_data.get("dm_secret", ""),
        location_id=location.id,
    )
    clue_data = scene.clue
    clue = tools.add_clue(
        campaign.id,
        title=clue_data["title"],
        public_text=clue_data["public_text"],
        dm_secret=clue_data.get("dm_secret", ""),
        location_id=location.id,
    ).data
    quest_data = scene.quest
    tools.add_quest(campaign.id, title=quest_data["title"], summary=quest_data["summary"])
    if scene.encounter is not None:
        encounter_data = scene.encounter
        tools.add_encounter(
            campaign.id,
            title=encounter_data["title"],
            location_id=location.id,
            difficulty=encounter_data.get("difficulty", "medium"),
            trigger=encounter_data.get("trigger", ""),
            reward=encounter_data.get("reward", ""),
            monsters=[
                Monster(
                    name=monster["name"],
                    armor_class=monster["armor_class"],
                    max_hp=monster["max_hp"],
                    current_hp=monster["current_hp"],
                    initiative_modifier=monster.get("initiative_modifier", 0),
                    attack_bonus=monster.get("attack_bonus", 0),
                    damage=monster.get("damage", "1d4"),
                )
                for monster in encounter_data.get("monsters", [])
            ],
        )
    return SceneSession(tools=tools, campaign=campaign, hero=hero, location=location, clue=clue, scene=scene)


def describe_scene(session: SceneSession) -> None:
    for line in session.scene.text["intro"]:
        session.narrate(f"DM: {line.format(hero=session.hero.name)}")


def matches_action(session: SceneSession, action_name: str, normalized: str) -> bool:
    aliases = session.scene.actions.get(action_name, [])
    return any(alias.lower() in normalized for alias in aliases)


def handle_player_action(session: SceneSession, action: str) -> bool:
    normalized = action.strip().lower()
    if not normalized:
        return True
    session.narrate(f"Player: {action}")
    session.tools.record_event(session.campaign.id, actor=session.hero.name, content=action)

    if matches_action(session, "quit", normalized):
        session.narrate(f"DM: {session.scene.text['pause']}")
        return False
    if matches_action(session, "help", normalized):
        session.narrate("DM: Available actions: look around, inspect rope, open stairway, log, quit.")
        return True
    if matches_action(session, "log", normalized):
        session.narrate("DM: Session log:")
        for event in session.campaign.session_log:
            session.narrate(f"- [{event.actor}] {event.content}")
        return True
    if matches_action(session, "look", normalized):
        session.narrate(f"DM: {session.scene.text['look']}")
        return True
    if matches_action(session, "inspect", normalized):
        return resolve_inspection(session)
    if matches_action(session, "open", normalized):
        return resolve_open_path(session)

    session.narrate(f"DM: {session.scene.text['unknown']}")
    return True


def resolve_inspection(session: SceneSession) -> bool:
    if session.inspected:
        session.narrate(f"DM: {session.scene.text['inspect_repeat']}")
        return True

    session.inspected = True
    session.tools.reveal_clue(session.campaign.id, session.clue.id)
    check_data = session.scene.checks["inspect_rope"]
    skill_name = check_data.get("skill")
    if skill_name is not None:
        check = session.tools.roll_skill_check(
            session.campaign.id,
            character_name=session.hero.name,
            skill_name=skill_name,
            dc=check_data["dc"],
            mode=RollMode(check_data["mode"]),
        ).data
    else:
        modifier = session.hero.ability_modifier(check_data["ability"])
        if check_data.get("proficient", False):
            modifier += session.hero.proficiency_bonus
        check = session.tools.roll_check(
            session.campaign.id,
            character_name=session.hero.name,
            modifier=modifier,
            dc=check_data["dc"],
            mode=RollMode(check_data["mode"]),
        ).data
    session.narrate(f"DM: {session.scene.text['inspect_first']}")
    session.narrate(
        f"System: {check_data['label']} with {check.mode.value} vs DC {check.dc} -> "
        f"rolls {check.d20_rolls}, total {check.total}."
    )
    if check.success:
        session.narrate(f"DM: {session.scene.text['inspect_success']}")
    else:
        session.narrate(f"DM: {session.scene.text['inspect_failure']}")
    return True


def resolve_open_path(session: SceneSession) -> bool:
    if not session.inspected:
        session.narrate(f"DM: {session.scene.text['stairway_locked']}")
        return True
    if session.opened_path:
        session.narrate(f"DM: {session.scene.text['stairway_repeat']}")
        return True

    session.opened_path = True
    session.tools.record_event(
        session.campaign.id,
        actor="DM",
        content="The sealed path opened after the clue was found.",
    )
    session.narrate(f"DM: {session.scene.text['stairway_open']}")
    return True
