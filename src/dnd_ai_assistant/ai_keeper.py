from __future__ import annotations

from dataclasses import dataclass

from .ai_provider import AIProvider
from .coc_runtime import COCScenario, coc_keeper_hint


@dataclass(frozen=True)
class KeeperSuggestion:
    action: str
    text: str
    prompt: str

    def to_dict(self, include_prompt: bool = False) -> dict:
        data = {
            "action": self.action,
            "text": self.text,
        }
        if include_prompt:
            data["prompt"] = self.prompt
        return data


def generate_keeper_suggestion(
    scenario: COCScenario,
    action: str,
    provider: AIProvider,
    include_prompt: bool = False,
) -> KeeperSuggestion:
    if not action.strip():
        raise ValueError("Action cannot be empty.")
    prompt = build_keeper_prompt(scenario, action)
    text = provider.generate_text(prompt).strip()
    if not text:
        raise ValueError("AI provider returned an empty Keeper suggestion.")
    return KeeperSuggestion(action=action, text=text, prompt=prompt if include_prompt else "")


def build_keeper_prompt(scenario: COCScenario, action: str) -> str:
    lines = [
        "You are a Keeper assistant for a Call of Cthulhu 7th edition investigation.",
        "Write a concise Keeper-facing suggestion for the next narration, clue handling, or tension beat.",
        "Do not mutate scenario state. Do not mark clues discovered, move locations, or change SAN/HP yourself.",
        "If a roll, clue reveal, movement, or inventory update is needed, recommend the runtime action instead.",
        "",
        "Scenario state:",
        _scenario_snapshot(scenario),
        "",
        f"Player action: {action.strip()}",
        "",
        "Return 2 to 5 short bullet points:",
        "- immediate eerie narration",
        "- likely runtime action or skill check if any",
        "- what public clue/evidence to reveal only if the tool confirms it",
        "- what Keeper-only implication to preserve for later",
    ]
    return "\n".join(lines)


def _scenario_snapshot(scenario: COCScenario) -> str:
    location = scenario.current_location()
    investigator = scenario.investigator
    discovered = ", ".join(clue.title for clue in scenario.clues if clue.discovered) or "none"
    undiscovered_here = ", ".join(
        clue.title
        for clue in scenario.clues
        if not clue.discovered and clue.location_id in {None, scenario.current_location_id}
    ) or "none"
    npcs_here = ", ".join(
        npc.name for npc in scenario.npcs if npc.location_id in {None, scenario.current_location_id}
    ) or "none"
    exits = ", ".join(f"{name}->{location_id}" for name, location_id in location.exits.items()) or "none"
    evidence = ", ".join(scenario.inventory) or "none"
    conditions = ", ".join(sorted(investigator.conditions)) or "none"
    return "\n".join(
        [
            f"Title: {scenario.title}",
            "System: Call of Cthulhu 7e",
            f"Current location: {location.name}",
            f"Location description: {location.description}",
            f"Visible exits: {exits}",
            f"Visible NPCs: {npcs_here}",
            f"Investigator: {investigator.name} ({investigator.occupation})",
            f"HP/MP/SAN/Luck: {investigator.current_hp}/{investigator.current_mp}/{investigator.current_sanity}/{investigator.luck}",
            f"Conditions: {conditions}",
            f"Discovered clues: {discovered}",
            f"Undiscovered clues at current location: {undiscovered_here}",
            f"Evidence inventory: {evidence}",
            f"Completion goals: {_completion_goal_summary(scenario)}",
            f"Deterministic keeper hint: {coc_keeper_hint(scenario)}",
            f"Completed: {'yes' if scenario.completed else 'no'}",
        ]
    )

def _completion_goal_summary(scenario: COCScenario) -> str:
    requirements = scenario.completion_requirements
    if not requirements:
        discovered = sum(1 for clue in scenario.clues if clue.discovered)
        return f"legacy clues {discovered}/{len(scenario.clues)}"
    discovered_ids = {clue.id for clue in scenario.clues if clue.discovered}
    inventory = set(scenario.inventory)
    current_locations = {scenario.current_location_id} if scenario.current_location_id else set()
    pieces = [
        _goal_piece("clues", requirements.get("required_clue_ids", []), discovered_ids),
        _goal_piece("evidence", requirements.get("required_evidence", []), inventory),
        _goal_piece("locations", requirements.get("required_location_ids", []), current_locations),
        _goal_piece("NPCs", requirements.get("required_npc_ids", []), scenario.talked_npc_ids),
    ]
    return ", ".join(piece for piece in pieces if piece) or "no explicit goals"


def _goal_piece(label: str, required: list[str], current: set[str]) -> str:
    if not required:
        return ""
    met = len([value for value in required if value in current])
    return f"{label} {met}/{len(required)}"
