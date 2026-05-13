from __future__ import annotations

import random
from dataclasses import dataclass, field

from .core.campaign import Campaign, Encounter, Location, NPC, Clue, SessionEvent
from .core.character import Character
from .core.dnd5e import RollMode, roll_d20_check
from .core.skills import skill_label


@dataclass
class AdventureRuntime:
    campaign: Campaign
    transcript: list[str] = field(default_factory=list)
    rng: random.Random = field(default_factory=random.Random)

    def narrate(self, line: str) -> None:
        self.transcript.append(line)

    def flush(self) -> str:
        output = "\n".join(self.transcript)
        self.transcript.clear()
        return output


def describe_current_location(runtime: AdventureRuntime) -> None:
    location = current_location(runtime.campaign)
    runtime.narrate(f"DM: {location.name}")
    runtime.narrate(f"DM: {location.public_description}")
    exits = [runtime.campaign.locations[location_id].name for location_id in location.connected_location_ids]
    if exits:
        runtime.narrate(f"DM: Exits: {', '.join(exits)}.")
    npcs = _npcs_at(runtime.campaign, location.id)
    if npcs:
        runtime.narrate("DM: People here: " + ", ".join(npc.name for npc in npcs) + ".")
    clues = _discovered_clues_at(runtime.campaign, location.id)
    if clues:
        runtime.narrate("DM: Known clues here: " + ", ".join(clue.title for clue in clues) + ".")
    encounters = _encounters_at(runtime.campaign, location.id)
    if encounters:
        runtime.narrate("DM: Potential encounters: " + ", ".join(encounter.title for encounter in encounters) + ".")


def handle_adventure_action(runtime: AdventureRuntime, action: str) -> bool:
    normalized = action.strip().lower()
    if not normalized:
        return True
    runtime.narrate(f"Player: {action}")
    runtime.campaign.record_event(SessionEvent(actor="Player", content=action))

    if normalized in {"quit", "exit"}:
        runtime.narrate("DM: The adventure pauses here.")
        return False
    if normalized in {"look", "look around", "where am i", "观察", "查看"}:
        describe_current_location(runtime)
        return True
    if normalized in {"inspect", "search", "investigate", "检查", "调查", "搜索"}:
        reveal_location_clues(runtime)
        return True
    if normalized in {"log", "日志"}:
        runtime.narrate("DM: Session log:")
        for event in runtime.campaign.session_log:
            runtime.narrate(f"- [{event.actor}] {event.content}")
        return True
    if normalized.startswith("go ") or normalized.startswith("move "):
        destination = normalized.split(" ", 1)[1].strip()
        return move_to(runtime, destination)

    runtime.narrate("DM: This adventure runtime only knows look, go <location>, log, and quit for now.")
    return True


def reveal_location_clues(runtime: AdventureRuntime) -> None:
    location = current_location(runtime.campaign)
    hidden_clues = [
        clue
        for clue in runtime.campaign.clues.values()
        if clue.location_id == location.id and not clue.discovered
    ]
    if not hidden_clues:
        runtime.narrate("DM: You find no new clues here.")
        return
    for clue in hidden_clues:
        if not _passes_clue_check(runtime, clue):
            runtime.narrate("DM: You do not find anything new yet.")
            continue
        clue.discovered = True
        runtime.campaign.record_event(SessionEvent(actor="DM", content=f"Clue revealed: {clue.title}"))
        runtime.narrate(f"DM: Clue found - {clue.title}: {clue.public_text}")


def move_to(runtime: AdventureRuntime, destination: str) -> bool:
    current = current_location(runtime.campaign)
    destination_id = _match_connected_location(runtime.campaign, current, destination)
    if destination_id is None:
        runtime.narrate("DM: You cannot reach that location from here.")
        return True
    new_location = runtime.campaign.locations[destination_id]
    missing_clues = _missing_required_clues(runtime.campaign, new_location)
    if missing_clues:
        runtime.narrate("DM: Something still blocks the way. Find more clues before going there.")
        return True
    runtime.campaign.current_location_id = destination_id
    runtime.campaign.record_event(SessionEvent(actor="DM", content=f"Moved to location: {new_location.name}"))
    describe_current_location(runtime)
    return True


def current_location(campaign: Campaign) -> Location:
    if campaign.current_location_id is None:
        raise ValueError("Campaign has no current location.")
    try:
        return campaign.locations[campaign.current_location_id]
    except KeyError as exc:
        raise ValueError(f"Unknown current location id: {campaign.current_location_id}") from exc


def _match_connected_location(campaign: Campaign, current: Location, destination: str) -> str | None:
    for location_id in current.connected_location_ids:
        location = campaign.locations[location_id]
        if destination == location_id.lower() or destination in location.name.lower():
            return location_id
    return None


def _missing_required_clues(campaign: Campaign, location: Location) -> list[str]:
    missing: list[str] = []
    for clue_id in location.requires_clue_ids:
        clue = campaign.clues.get(clue_id)
        if clue is None or not clue.discovered:
            missing.append(clue_id)
    return missing


def _npcs_at(campaign: Campaign, location_id: str) -> list[NPC]:
    return [npc for npc in campaign.npcs.values() if npc.location_id == location_id]


def _discovered_clues_at(campaign: Campaign, location_id: str) -> list[Clue]:
    return [clue for clue in campaign.clues.values() if clue.location_id == location_id and clue.discovered]


def _encounters_at(campaign: Campaign, location_id: str) -> list[Encounter]:
    return [
        encounter
        for encounter in campaign.encounters.values()
        if encounter.location_id == location_id and not encounter.resolved
    ]


def _passes_clue_check(runtime: AdventureRuntime, clue: Clue) -> bool:
    if clue.check is None:
        return True
    character = _first_character(runtime.campaign)
    if character is None:
        return True

    skill = str(clue.check.get("skill", "perception"))
    dc = int(clue.check.get("dc", 10))
    mode = RollMode(str(clue.check.get("mode", RollMode.NORMAL.value)))
    label = str(clue.check.get("label", skill_label(skill)))
    modifier = character.skill_modifier(skill)
    result = roll_d20_check(modifier=modifier, dc=dc, mode=mode, rng=runtime.rng)
    outcome = "success" if result.success else "failure"

    runtime.narrate(
        f"System: {character.name} rolls {label} ({mode.value}) vs DC {dc}: "
        f"{list(result.d20_rolls)} + {modifier} = {result.total} ({outcome})."
    )
    runtime.campaign.record_event(
        SessionEvent(
            actor="System",
            content=f"{character.name} rolled {label} {result.total} vs DC {dc}: {outcome}.",
        )
    )
    return bool(result.success)


def _first_character(campaign: Campaign) -> Character | None:
    return next(iter(campaign.characters.values()), None)
