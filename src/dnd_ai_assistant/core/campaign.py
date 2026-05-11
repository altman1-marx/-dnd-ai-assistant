from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from .character import Character


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class Visibility(str, Enum):
    PUBLIC = "public"
    DM_ONLY = "dm_only"


@dataclass
class Location:
    name: str
    public_description: str
    dm_notes: str = ""
    connected_location_ids: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: new_id("loc"))


@dataclass
class NPC:
    name: str
    role: str
    public_description: str
    dm_secret: str = ""
    attitude: str = "neutral"
    location_id: str | None = None
    id: str = field(default_factory=lambda: new_id("npc"))


@dataclass
class Clue:
    title: str
    public_text: str
    dm_secret: str = ""
    discovered: bool = False
    location_id: str | None = None
    id: str = field(default_factory=lambda: new_id("clue"))


@dataclass
class Quest:
    title: str
    summary: str
    status: str = "active"
    id: str = field(default_factory=lambda: new_id("quest"))


@dataclass
class SessionEvent:
    actor: str
    content: str
    visibility: Visibility = Visibility.PUBLIC
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    id: str = field(default_factory=lambda: new_id("event"))


@dataclass
class Campaign:
    title: str
    system: str = "DND 5e"
    tone: str = "heroic fantasy"
    party_level: int = 1
    public_lore: str = ""
    dm_secrets: str = ""
    id: str = field(default_factory=lambda: new_id("camp"))
    characters: dict[str, Character] = field(default_factory=dict)
    locations: dict[str, Location] = field(default_factory=dict)
    npcs: dict[str, NPC] = field(default_factory=dict)
    clues: dict[str, Clue] = field(default_factory=dict)
    quests: dict[str, Quest] = field(default_factory=dict)
    session_log: list[SessionEvent] = field(default_factory=list)

    def add_character(self, character: Character) -> None:
        self.characters[character.name] = character

    def add_location(self, location: Location) -> None:
        self.locations[location.id] = location

    def add_npc(self, npc: NPC) -> None:
        if npc.location_id is not None and npc.location_id not in self.locations:
            raise ValueError(f"Unknown location id: {npc.location_id}")
        self.npcs[npc.id] = npc

    def add_clue(self, clue: Clue) -> None:
        if clue.location_id is not None and clue.location_id not in self.locations:
            raise ValueError(f"Unknown location id: {clue.location_id}")
        self.clues[clue.id] = clue

    def add_quest(self, quest: Quest) -> None:
        self.quests[quest.id] = quest

    def record_event(self, event: SessionEvent) -> None:
        self.session_log.append(event)
