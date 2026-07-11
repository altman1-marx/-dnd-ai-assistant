from __future__ import annotations

from .coc_runtime import COCScenario


def build_coc_briefing(scenario: COCScenario) -> dict:
    """Build a Keeper-facing snapshot for resuming or running a COC scene."""
    location = scenario.current_location()
    investigator = scenario.investigator
    discovered = [clue for clue in scenario.clues if clue.discovered]
    partial = [clue for clue in scenario.clues if clue.partial_discovered and not clue.discovered]
    hidden = [clue for clue in scenario.clues if not clue.discovered]
    blocked_exits = _blocked_exits(scenario)
    remaining_goals = _remaining_completion_goals(scenario)
    risks = _risks(scenario, blocked_exits, remaining_goals)
    next_actions = _next_actions(scenario, partial, hidden, blocked_exits, remaining_goals)
    open_threads = _open_threads(scenario, partial, hidden, blocked_exits, remaining_goals)
    spotlight_actions = _spotlight_actions(scenario, partial, hidden, blocked_exits, remaining_goals)
    briefing = {
        "scenario_id": scenario.id,
        "title": scenario.title,
        "completed": scenario.completed,
        "location": {
            "id": location.id,
            "name": location.name,
            "description": location.description,
            "exits": sorted(location.exits),
            "blocked_exits": blocked_exits,
        },
        "investigator": {
            "name": investigator.name,
            "occupation": investigator.occupation,
            "hp": f"{investigator.current_hp}/{investigator.max_hp}",
            "sanity": f"{investigator.current_sanity}/{investigator.max_sanity}",
            "luck": investigator.luck,
            "conditions": sorted(investigator.conditions),
        },
        "progress": {
            "discovered_clues": len(discovered),
            "partial_clues": len(partial),
            "total_clues": len(scenario.clues),
            "inventory": list(scenario.inventory),
            "remaining_goals": remaining_goals,
        },
        "keeper_notes": {
            "visible_npcs": [npc.name for npc in scenario.npcs if npc.location_id in {None, location.id}],
            "partial_leads": [_clue_brief(clue) for clue in partial],
            "hidden_clues": [_clue_brief(clue) for clue in hidden],
            "recent_events": list(scenario.session_log[-8:]),
        },
        "risks": risks,
        "next_actions": next_actions,
        "open_threads": open_threads,
        "spotlight_actions": spotlight_actions,
    }
    briefing["text"] = render_coc_briefing(briefing)
    return briefing


def render_coc_briefing(briefing: dict) -> str:
    lines = [
        f"COC Keeper Briefing: {briefing['title']}",
        f"Location: {briefing['location']['name']}",
        f"Investigator: {briefing['investigator']['name']} | HP {briefing['investigator']['hp']} | SAN {briefing['investigator']['sanity']} | Luck {briefing['investigator']['luck']}",
        f"Progress: {briefing['progress']['discovered_clues']}/{briefing['progress']['total_clues']} clues discovered, {briefing['progress']['partial_clues']} partial lead(s).",
    ]
    conditions = briefing["investigator"].get("conditions") or []
    if conditions:
        lines.append("Conditions: " + ", ".join(conditions))
    if briefing["progress"].get("inventory"):
        lines.append("Evidence: " + ", ".join(briefing["progress"]["inventory"]))
    if briefing["risks"]:
        lines.append("Risks:")
        lines.extend(f"- {risk}" for risk in briefing["risks"])
    if briefing["next_actions"]:
        lines.append("Next Keeper moves:")
        lines.extend(f"- {action}" for action in briefing["next_actions"])
    if briefing.get("open_threads"):
        lines.append("Open threads:")
        lines.extend(f"- {thread}" for thread in briefing["open_threads"])
    if briefing.get("spotlight_actions"):
        lines.append("Spotlight actions:")
        lines.extend(f"- {action}" for action in briefing["spotlight_actions"])
    if briefing["keeper_notes"].get("partial_leads"):
        lines.append("Partial leads:")
        lines.extend(f"- {lead['title']}: {lead['text']}" for lead in briefing["keeper_notes"]["partial_leads"])
    if briefing["keeper_notes"].get("hidden_clues"):
        lines.append("Hidden clue queue:")
        for clue in briefing["keeper_notes"]["hidden_clues"][:5]:
            gate = clue["skill"] or "automatic"
            lines.append(f"- {clue['title']} ({gate}, {clue['difficulty']})")
    if briefing["keeper_notes"].get("recent_events"):
        lines.append("Recent table log:")
        lines.extend(f"- {event}" for event in briefing["keeper_notes"]["recent_events"])
    return "\n".join(lines)


def _clue_brief(clue) -> dict:
    return {
        "id": clue.id,
        "title": clue.title,
        "text": clue.failure_text if clue.partial_discovered and not clue.discovered else clue.text,
        "location_id": clue.location_id,
        "skill": clue.skill,
        "difficulty": clue.difficulty,
        "sanity_loss": clue.sanity_loss,
        "push_attempted": clue.push_attempted,
    }


def _blocked_exits(scenario: COCScenario) -> list[dict]:
    location = scenario.current_location()
    blocked = []
    for name, requirement in location.exit_requirements.items():
        if not _requirement_met(scenario, requirement):
            blocked.append({
                "name": name,
                "message": requirement.get("message", "Exit is blocked by unmet investigation requirements."),
                "requirements": dict(requirement),
            })
    return blocked


def _remaining_completion_goals(scenario: COCScenario) -> dict[str, list[str]]:
    remaining: dict[str, list[str]] = {}
    discovered_ids = {clue.id for clue in scenario.clues if clue.discovered}
    evidence = set(scenario.inventory)
    visited = {scenario.current_location_id} if scenario.current_location_id else set()
    talked = set(scenario.talked_npc_ids)
    current = {
        "required_clue_ids": discovered_ids,
        "required_evidence": evidence,
        "required_location_ids": visited,
        "required_npc_ids": talked,
    }
    for key, required_values in scenario.completion_requirements.items():
        missing = [value for value in required_values if value not in current.get(key, set())]
        if missing:
            remaining[key] = missing
    return remaining


def _risks(scenario: COCScenario, blocked_exits: list[dict], remaining_goals: dict[str, list[str]]) -> list[str]:
    risks: list[str] = []
    investigator = scenario.investigator
    if investigator.conditions:
        risks.append("Active investigator conditions: " + ", ".join(sorted(investigator.conditions)) + ".")
    if investigator.current_sanity <= max(1, investigator.max_sanity // 2):
        risks.append("Investigator sanity is at or below half; avoid piling on unavoidable SAN loss.")
    if blocked_exits:
        risks.append("At least one exit is blocked by unmet clues or evidence.")
    if remaining_goals:
        risks.append("The ending is still gated by unresolved completion requirements.")
    if scenario.completed:
        risks.append("Scenario is completed; use the briefing for epilogue or recap only.")
    return risks


def _open_threads(
    scenario: COCScenario,
    partial: list,
    hidden: list,
    blocked_exits: list[dict],
    remaining_goals: dict[str, list[str]],
) -> list[str]:
    threads: list[str] = []
    for clue in partial:
        threads.append(f"Partial lead unresolved: {clue.title}.")
    for exit_data in blocked_exits:
        threads.append(f"Blocked route: {exit_data['name']}.")
    for key, values in remaining_goals.items():
        threads.append(f"Ending gate {key}: {', '.join(values)}.")
    current_location_id = scenario.current_location().id
    local_hidden = [clue.title for clue in hidden if clue.location_id in {None, current_location_id}]
    if local_hidden:
        threads.append("Local clue opportunities: " + ", ".join(local_hidden) + ".")
    elif hidden:
        threads.append("Remote clue opportunities: " + ", ".join(clue.title for clue in hidden[:3]) + ".")
    return threads


def _spotlight_actions(
    scenario: COCScenario,
    partial: list,
    hidden: list,
    blocked_exits: list[dict],
    remaining_goals: dict[str, list[str]],
) -> list[str]:
    actions: list[str] = []
    if partial:
        lead = partial[0]
        actions.extend([f"push {lead.title.lower()}", f"spend luck {lead.title.lower()}"])
    clue = _best_hidden_clue(scenario, hidden) if hidden else None
    if clue is not None:
        verb = _natural_clue_verb(clue)
        actions.append(f"{verb} {clue.title.lower()}")
        if clue.skill:
            actions.append(f"check {clue.skill}")
    if blocked_exits:
        actions.append("hint")
    if remaining_goals and not actions:
        actions.append("progress")
    if scenario.completed:
        actions.append("recap")
    return list(dict.fromkeys(actions[:5]))


def _natural_clue_verb(clue) -> str:
    text = f"{clue.id} {clue.title}".lower()
    if any(word in text for word in ("journal", "diary", "letter", "book", "note")):
        return "read"
    if any(word in text for word in ("voice", "voices", "whisper", "well", "sound")):
        return "listen"
    return "inspect"


def _next_actions(scenario: COCScenario, partial: list, hidden: list, blocked_exits: list[dict], remaining_goals: dict[str, list[str]]) -> list[str]:
    actions: list[str] = []
    if partial:
        lead = partial[0]
        actions.append(f"Offer a push roll or Luck spend around {lead.title}.")
    if blocked_exits:
        actions.append(f"Point pressure toward the blocked {blocked_exits[0]['name']} route without giving away the solution.")
    if hidden:
        clue = _best_hidden_clue(scenario, hidden)
        actions.append(f"Frame the next scene around {clue.title}.")
    if remaining_goals:
        keys = ", ".join(sorted(remaining_goals))
        actions.append(f"Track remaining ending gates: {keys}.")
    if not actions:
        actions.append("Invite the investigator to conclude the case or record an epilogue note.")
    return actions


def _best_hidden_clue(scenario: COCScenario, hidden: list):
    current_location_id = scenario.current_location().id
    for clue in hidden:
        if clue.location_id in {None, current_location_id}:
            return clue
    return hidden[0]


def _requirement_met(scenario: COCScenario, requirement: dict) -> bool:
    discovered_ids = {clue.id for clue in scenario.clues if clue.discovered}
    evidence = set(scenario.inventory)
    for clue_id in requirement.get("required_clue_ids", []):
        if clue_id not in discovered_ids:
            return False
    for item in requirement.get("required_evidence", []):
        if item not in evidence:
            return False
    return True
