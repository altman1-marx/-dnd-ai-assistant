from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from .character import Character
from .damage import normalize_damage_type, normalize_damage_types
from .dnd5e import ability_modifier


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


ABILITY_NAMES = ("str", "dex", "con", "int", "wis", "cha")


class Visibility(str, Enum):
    PUBLIC = "public"
    DM_ONLY = "dm_only"


@dataclass
class Location:
    name: str
    public_description: str
    dm_notes: str = ""
    connected_location_ids: list[str] = field(default_factory=list)
    requires_clue_ids: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: new_id("loc"))


@dataclass
class NPC:
    name: str
    role: str
    public_description: str
    dm_secret: str = ""
    dialogue: str = ""
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
    check: dict | None = None
    id: str = field(default_factory=lambda: new_id("clue"))


@dataclass
class Quest:
    title: str
    summary: str
    status: str = "active"
    id: str = field(default_factory=lambda: new_id("quest"))


@dataclass
class Monster:
    name: str
    armor_class: int
    max_hp: int
    current_hp: int
    ability_scores: dict[str, int] = field(
        default_factory=lambda: {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
    )
    saving_throw_proficiencies: set[str] = field(default_factory=set)
    proficiency_bonus: int = 2
    damage_resistances: set[str] = field(default_factory=set)
    damage_vulnerabilities: set[str] = field(default_factory=set)
    damage_immunities: set[str] = field(default_factory=set)
    initiative_modifier: int = 0
    attack_bonus: int = 0
    damage: str = "1d4"
    damage_type: str = "untyped"
    id: str = field(default_factory=lambda: new_id("mon"))

    def __post_init__(self) -> None:
        missing = set(ABILITY_NAMES) - set(self.ability_scores)
        if missing:
            raise ValueError(f"Missing monster ability scores: {', '.join(sorted(missing))}")
        for ability in ABILITY_NAMES:
            ability_modifier(self.ability_scores[ability])
        unknown_saves = set(self.saving_throw_proficiencies) - set(ABILITY_NAMES)
        if unknown_saves:
            raise ValueError(f"Unknown monster saving throw proficiencies: {', '.join(sorted(unknown_saves))}")
        self.damage_resistances = normalize_damage_types(self.damage_resistances)
        self.damage_vulnerabilities = normalize_damage_types(self.damage_vulnerabilities)
        self.damage_immunities = normalize_damage_types(self.damage_immunities)
        self.damage_type = normalize_damage_type(self.damage_type)
        if self.armor_class <= 0:
            raise ValueError("Monster armor class must be positive.")
        if self.max_hp <= 0:
            raise ValueError("Monster max HP must be positive.")
        if self.current_hp < 0:
            raise ValueError("Monster current HP cannot be negative.")
        if self.current_hp > self.max_hp:
            raise ValueError("Monster current HP cannot exceed max HP.")
        if self.proficiency_bonus < 0:
            raise ValueError("Monster proficiency bonus cannot be negative.")

    def ability_modifier(self, ability: str) -> int:
        return ability_modifier(self.ability_scores[ability])

    def saving_throw_modifier(self, ability: str) -> int:
        modifier = self.ability_modifier(ability)
        if ability in self.saving_throw_proficiencies:
            modifier += self.proficiency_bonus
        return modifier


@dataclass
class Encounter:
    title: str
    location_id: str | None = None
    difficulty: str = "medium"
    trigger: str = ""
    reward: str = ""
    monsters: list[Monster] = field(default_factory=list)
    resolved: bool = False
    id: str = field(default_factory=lambda: new_id("enc"))


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
    current_location_id: str | None = None
    runtime_actions: dict[str, dict] = field(default_factory=dict)
    id: str = field(default_factory=lambda: new_id("camp"))
    characters: dict[str, Character] = field(default_factory=dict)
    locations: dict[str, Location] = field(default_factory=dict)
    npcs: dict[str, NPC] = field(default_factory=dict)
    clues: dict[str, Clue] = field(default_factory=dict)
    quests: dict[str, Quest] = field(default_factory=dict)
    encounters: dict[str, Encounter] = field(default_factory=dict)
    session_log: list[SessionEvent] = field(default_factory=list)

    def add_character(self, character: Character) -> None:
        if character.name in self.characters:
            raise ValueError(f"Character already exists: {character.name}")
        self.characters[character.name] = character

    def add_location(self, location: Location) -> None:
        if location.id in self.locations:
            raise ValueError(f"Location already exists: {location.id}")
        self.locations[location.id] = location

    def add_npc(self, npc: NPC) -> None:
        if npc.location_id is not None and npc.location_id not in self.locations:
            raise ValueError(f"Unknown location id: {npc.location_id}")
        if npc.id in self.npcs:
            raise ValueError(f"NPC already exists: {npc.id}")
        self.npcs[npc.id] = npc

    def add_clue(self, clue: Clue) -> None:
        if clue.location_id is not None and clue.location_id not in self.locations:
            raise ValueError(f"Unknown location id: {clue.location_id}")
        if clue.id in self.clues:
            raise ValueError(f"Clue already exists: {clue.id}")
        self.clues[clue.id] = clue

    def add_quest(self, quest: Quest) -> None:
        if quest.id in self.quests:
            raise ValueError(f"Quest already exists: {quest.id}")
        self.quests[quest.id] = quest

    def add_encounter(self, encounter: Encounter) -> None:
        if encounter.location_id is not None and encounter.location_id not in self.locations:
            raise ValueError(f"Unknown location id: {encounter.location_id}")
        if encounter.id in self.encounters:
            raise ValueError(f"Encounter already exists: {encounter.id}")
        self.encounters[encounter.id] = encounter

    def record_event(self, event: SessionEvent) -> None:
        self.session_log.append(event)
