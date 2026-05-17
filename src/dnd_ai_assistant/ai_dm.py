from __future__ import annotations

from dataclasses import dataclass

from .ai_provider import AIProvider
from .core.campaign import Campaign
from .rules_corpus import RuleCorpus, RuleSearchResult, render_rules_context


@dataclass(frozen=True)
class DMSuggestion:
    action: str
    text: str
    rules: list[RuleSearchResult]
    prompt: str

    def to_dict(self, include_prompt: bool = False) -> dict:
        data = {
            "action": self.action,
            "text": self.text,
            "rules": [result.to_dict() for result in self.rules],
        }
        if include_prompt:
            data["prompt"] = self.prompt
        return data


def generate_dm_suggestion(
    campaign: Campaign,
    action: str,
    provider: AIProvider,
    rules_corpus: RuleCorpus | None = None,
    include_prompt: bool = False,
) -> DMSuggestion:
    if not action.strip():
        raise ValueError("Action cannot be empty.")
    rules = _rules_for_action(campaign, action, rules_corpus)
    prompt = build_dm_prompt(campaign, action, render_rules_context(rules))
    text = provider.generate_text(prompt).strip()
    if not text:
        raise ValueError("AI provider returned an empty DM suggestion.")
    return DMSuggestion(action=action, text=text, rules=rules, prompt=prompt if include_prompt else "")


def build_dm_prompt(campaign: Campaign, action: str, rules_context: str | None = None) -> str:
    lines = [
        "You are an assistant DM for a DND 5e tabletop session.",
        "Write a concise DM-facing suggestion for the next narration or ruling.",
        "Do not mutate campaign state. Do not invent mechanical outcomes that should be resolved by tools.",
        "If a check, attack, spell, or save is needed, recommend the tool/rule action instead of rolling yourself.",
        "",
        "Campaign state:",
        _campaign_snapshot(campaign),
        "",
        f"Player action: {action.strip()}",
    ]
    if rules_context:
        lines.extend(["", "Relevant rules:", rules_context])
    lines.extend(
        [
            "",
            "Return 2 to 5 short bullet points:",
            "- immediate narration",
            "- likely rule/tool call if any",
            "- what public information to reveal",
            "- what DM-only note to keep hidden if relevant",
        ]
    )
    return "\n".join(lines)


def _rules_for_action(campaign: Campaign, action: str, rules_corpus: RuleCorpus | None) -> list[RuleSearchResult]:
    if rules_corpus is None:
        return []
    query = " ".join([action, campaign.system, campaign.tone, "ability check attack spell saving throw"])
    return rules_corpus.search(query, limit=3)


def _campaign_snapshot(campaign: Campaign) -> str:
    location = campaign.locations.get(campaign.current_location_id or "")
    characters = ", ".join(
        f"{character.name} level {character.level} {character.class_name} HP {character.current_hp}/{character.max_hp}"
        for character in campaign.characters.values()
    ) or "none"
    active_quests = ", ".join(
        quest.title for quest in campaign.quests.values() if quest.status == "active"
    ) or "none"
    discovered_clues = ", ".join(
        clue.title for clue in campaign.clues.values() if clue.discovered
    ) or "none"
    lines = [
        f"Title: {campaign.title}",
        f"System: {campaign.system}",
        f"Tone: {campaign.tone}",
        f"Party level: {campaign.party_level}",
        f"Current location: {location.name if location else 'none'}",
        f"Location description: {location.public_description if location else 'none'}",
        f"Characters: {characters}",
        f"Active quests: {active_quests}",
        f"Discovered clues: {discovered_clues}",
        f"Active combat: {'yes' if campaign.active_combat else 'no'}",
    ]
    if location is not None:
        npcs = ", ".join(npc.name for npc in campaign.npcs.values() if npc.location_id == location.id) or "none"
        exits = ", ".join(
            campaign.locations[location_id].name
            for location_id in location.connected_location_ids
            if location_id in campaign.locations
        ) or "none"
        lines.extend([f"Visible NPCs: {npcs}", f"Visible exits: {exits}"])
    return "\n".join(lines)
