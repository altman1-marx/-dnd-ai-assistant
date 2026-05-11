from __future__ import annotations

import random
from dataclasses import dataclass

from .campaign import Campaign, Clue, Encounter, Location, Monster, NPC, Quest, SessionEvent, Visibility
from .character import Character
from .dnd5e import D20Check, RollMode, roll_d20_check
from .store import InMemoryCampaignStore


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    message: str
    data: object | None = None


class DMTools:
    """Tool layer that an AI DM can call instead of mutating state directly."""

    def __init__(self, store: InMemoryCampaignStore | None = None, rng: random.Random | None = None) -> None:
        self.store = store or InMemoryCampaignStore()
        self.rng = rng or random.Random()

    def create_campaign(
        self,
        title: str,
        party_level: int,
        tone: str = "heroic fantasy",
        public_lore: str = "",
        dm_secrets: str = "",
    ) -> ToolResult:
        campaign = Campaign(
            title=title,
            party_level=party_level,
            tone=tone,
            public_lore=public_lore,
            dm_secrets=dm_secrets,
        )
        self.store.save(campaign)
        return ToolResult(True, f"Created campaign: {campaign.title}", campaign)

    def add_character(self, campaign_id: str, character: Character) -> ToolResult:
        campaign = self.store.get(campaign_id)
        campaign.add_character(character)
        return ToolResult(True, f"Added character: {character.name}", character)

    def add_location(
        self,
        campaign_id: str,
        name: str,
        public_description: str,
        dm_notes: str = "",
    ) -> ToolResult:
        campaign = self.store.get(campaign_id)
        location = Location(name=name, public_description=public_description, dm_notes=dm_notes)
        campaign.add_location(location)
        return ToolResult(True, f"Added location: {location.name}", location)

    def add_npc(
        self,
        campaign_id: str,
        name: str,
        role: str,
        public_description: str,
        dm_secret: str = "",
        attitude: str = "neutral",
        location_id: str | None = None,
    ) -> ToolResult:
        campaign = self.store.get(campaign_id)
        npc = NPC(
            name=name,
            role=role,
            public_description=public_description,
            dm_secret=dm_secret,
            attitude=attitude,
            location_id=location_id,
        )
        campaign.add_npc(npc)
        return ToolResult(True, f"Added NPC: {npc.name}", npc)

    def add_clue(
        self,
        campaign_id: str,
        title: str,
        public_text: str,
        dm_secret: str = "",
        location_id: str | None = None,
    ) -> ToolResult:
        campaign = self.store.get(campaign_id)
        clue = Clue(title=title, public_text=public_text, dm_secret=dm_secret, location_id=location_id)
        campaign.add_clue(clue)
        return ToolResult(True, f"Added clue: {clue.title}", clue)

    def reveal_clue(self, campaign_id: str, clue_id: str) -> ToolResult:
        campaign = self.store.get(campaign_id)
        clue = campaign.clues[clue_id]
        clue.discovered = True
        campaign.record_event(SessionEvent(actor="DM", content=f"Clue revealed: {clue.title}"))
        return ToolResult(True, f"Revealed clue: {clue.title}", clue)

    def add_quest(self, campaign_id: str, title: str, summary: str) -> ToolResult:
        campaign = self.store.get(campaign_id)
        quest = Quest(title=title, summary=summary)
        campaign.add_quest(quest)
        return ToolResult(True, f"Added quest: {quest.title}", quest)

    def add_encounter(
        self,
        campaign_id: str,
        title: str,
        monsters: list[Monster],
        location_id: str | None = None,
        difficulty: str = "medium",
        trigger: str = "",
        reward: str = "",
    ) -> ToolResult:
        campaign = self.store.get(campaign_id)
        encounter = Encounter(
            title=title,
            monsters=monsters,
            location_id=location_id,
            difficulty=difficulty,
            trigger=trigger,
            reward=reward,
        )
        campaign.add_encounter(encounter)
        return ToolResult(True, f"Added encounter: {encounter.title}", encounter)

    def resolve_encounter(self, campaign_id: str, encounter_id: str) -> ToolResult:
        campaign = self.store.get(campaign_id)
        encounter = campaign.encounters[encounter_id]
        encounter.resolved = True
        campaign.record_event(SessionEvent(actor="DM", content=f"Encounter resolved: {encounter.title}"))
        return ToolResult(True, f"Resolved encounter: {encounter.title}", encounter)

    def record_event(
        self,
        campaign_id: str,
        actor: str,
        content: str,
        visibility: Visibility = Visibility.PUBLIC,
    ) -> ToolResult:
        campaign = self.store.get(campaign_id)
        event = SessionEvent(actor=actor, content=content, visibility=visibility)
        campaign.record_event(event)
        return ToolResult(True, "Recorded event.", event)

    def roll_check(
        self,
        campaign_id: str,
        character_name: str,
        modifier: int,
        dc: int,
        mode: RollMode = RollMode.NORMAL,
    ) -> ToolResult:
        campaign = self.store.get(campaign_id)
        if character_name not in campaign.characters:
            return ToolResult(False, f"Character not found: {character_name}")
        check: D20Check = roll_d20_check(modifier=modifier, dc=dc, mode=mode, rng=self.rng)
        outcome = "success" if check.success else "failure"
        campaign.record_event(
            SessionEvent(
                actor="System",
                content=f"{character_name} rolled {check.total} vs DC {dc}: {outcome}.",
            )
        )
        return ToolResult(True, f"Rolled d20 check: {outcome}", check)

    def apply_damage(self, campaign_id: str, character_name: str, amount: int) -> ToolResult:
        campaign = self.store.get(campaign_id)
        if character_name not in campaign.characters:
            return ToolResult(False, f"Character not found: {character_name}")
        character = campaign.characters[character_name]
        before = character.current_hp
        character.apply_damage(amount)
        campaign.record_event(
            SessionEvent(
                actor="System",
                content=f"{character_name} took {amount} damage: HP {before} -> {character.current_hp}.",
            )
        )
        return ToolResult(True, f"Applied {amount} damage to {character_name}.", character)

    def heal_character(self, campaign_id: str, character_name: str, amount: int) -> ToolResult:
        campaign = self.store.get(campaign_id)
        if character_name not in campaign.characters:
            return ToolResult(False, f"Character not found: {character_name}")
        character = campaign.characters[character_name]
        before = character.current_hp
        character.heal(amount)
        campaign.record_event(
            SessionEvent(
                actor="System",
                content=f"{character_name} healed {amount}: HP {before} -> {character.current_hp}.",
            )
        )
        return ToolResult(True, f"Healed {character_name} for {amount}.", character)
