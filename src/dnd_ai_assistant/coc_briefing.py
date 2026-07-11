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
    opening = _opening_brief(scenario, hidden, blocked_exits, spotlight_actions)
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
        "opening": opening,
    }
    briefing["text"] = render_coc_briefing(briefing)
    return briefing


def build_coc_table_packet(scenario: COCScenario) -> dict:
    """Build a compact pre-session packet for the Keeper and player-facing handout."""
    briefing = build_coc_briefing(scenario)
    investigator = scenario.investigator
    location = scenario.current_location()
    visible_npcs = [npc for npc in scenario.npcs if npc.location_id in {None, location.id}]
    player_actions = ["look", "status", "skills", "recap", "hint"]
    player_actions.extend(briefing["opening"].get("first_turn_actions", []))
    clue_map = _clue_map(scenario)
    npc_cards = _npc_cards(scenario)
    packet = {
        "scenario_id": scenario.id,
        "title": scenario.title,
        "system_id": "coc7e",
        "scenario_profile": _scenario_profile(scenario),
        "keeper_opening": briefing["opening"],
        "keeper_checklist": {
            "first_turn_actions": list(dict.fromkeys(player_actions))[:8],
            "hidden_clue_count": len([clue for clue in scenario.clues if not clue.discovered]),
            "safety_note": briefing["opening"].get("safety_note", ""),
            "open_threads": list(briefing.get("open_threads", [])),
            "scene_beats": _scene_beats(scenario, clue_map),
        },
        "clue_map": clue_map,
        "npc_cards": npc_cards,
        "player_handout": {
            "investigator": investigator.name,
            "occupation": investigator.occupation,
            "starting_location": location.name,
            "case_hook": briefing["opening"].get("investigator_hook", ""),
            "known_people": [npc.name for npc in visible_npcs],
            "known_evidence": list(scenario.inventory),
            "suggested_actions": list(dict.fromkeys(player_actions))[:8],
        },
    }
    packet["text"] = render_coc_table_packet(packet)
    return packet


def render_coc_table_packet(packet: dict) -> str:
    handout = packet["player_handout"]
    checklist = packet["keeper_checklist"]
    opening = packet["keeper_opening"]
    profile = packet.get("scenario_profile", {})
    lines = [
        f"COC Table Packet: {packet['title']}",
        f"Profile: {profile.get('location_count', 0)} locations, {profile.get('clue_count', 0)} clues, {profile.get('npc_count', 0)} NPCs, estimated {profile.get('estimated_minutes', 0)} minutes.",
        "Keeper opening:",
        f"- Read aloud: {opening.get('read_aloud', '')}",
        f"- Safety note: {opening.get('safety_note', '')}",
        "Player handout:",
        f"- Investigator: {handout['investigator']} ({handout['occupation']})",
        f"- Starting location: {handout['starting_location']}",
        f"- Case hook: {handout['case_hook']}",
    ]
    if handout.get("known_people"):
        lines.append("- Known people: " + ", ".join(handout["known_people"]))
    if handout.get("known_evidence"):
        lines.append("- Known evidence: " + ", ".join(handout["known_evidence"]))
    if handout.get("suggested_actions"):
        lines.append("- Suggested actions: " + ", ".join(handout["suggested_actions"]))
    lines.append("Keeper checklist:")
    lines.append(f"- Hidden clues: {checklist['hidden_clue_count']}")
    if checklist.get("scene_beats"):
        lines.append("- Scene beats: " + " | ".join(checklist["scene_beats"]))
    if checklist.get("first_turn_actions"):
        lines.append("- First turn buttons: " + ", ".join(checklist["first_turn_actions"]))
    if checklist.get("open_threads"):
        lines.append("- Open threads: " + " | ".join(checklist["open_threads"][:4]))
    if packet.get("clue_map"):
        lines.append("Clue map:")
        for location in packet["clue_map"]:
            clue_titles = ", ".join(clue["title"] for clue in location["clues"]) or "none"
            lines.append(f"- {location['location']}: {clue_titles}")
    if packet.get("npc_cards"):
        lines.append("NPC cards:")
        for npc in packet["npc_cards"]:
            lines.append(f"- {npc['name']} at {npc['location']}: {npc['keeper_use']}")
    return "\n".join(lines)


def _scenario_profile(scenario: COCScenario) -> dict:
    location_count = len(scenario.locations) or 1
    clue_count = len(scenario.clues)
    npc_count = len(scenario.npcs)
    estimated_minutes = 20 + location_count * 10 + clue_count * 5 + npc_count * 5
    return {
        "location_count": location_count,
        "clue_count": clue_count,
        "npc_count": npc_count,
        "estimated_minutes": estimated_minutes,
        "starting_location": scenario.current_location().name,
        "completion_gate_count": sum(len(values) for values in scenario.completion_requirements.values()),
    }


def _scene_beats(scenario: COCScenario, clue_map: list[dict]) -> list[str]:
    beats = [f"Open at {scenario.current_location().name}."]
    if clue_map:
        first_location = clue_map[0]
        if first_location["clues"]:
            beats.append(f"Surface {first_location['clues'][0]['title']} as the first tangible lead.")
    if scenario.completion_requirements:
        beats.append("Track ending gates before letting the case close.")
    if scenario.ending_text:
        beats.append("Use the ending text once the required evidence is in hand.")
    return beats[:5]


def _clue_map(scenario: COCScenario) -> list[dict]:
    location_names = {location_id: location.name for location_id, location in scenario.locations.items()}
    required_clue_ids = set(scenario.completion_requirements.get("required_clue_ids", []))
    mapped: list[dict] = []
    for location_id, location_name in location_names.items():
        clues = [clue for clue in scenario.clues if clue.location_id in {None, location_id}]
        mapped.append({
            "location_id": location_id,
            "location": location_name,
            "clues": [_clue_map_entry(clue, required_clue_ids) for clue in clues],
        })
    legacy_clues = [clue for clue in scenario.clues if clue.location_id and clue.location_id not in location_names]
    if legacy_clues:
        mapped.append({
            "location_id": "unknown",
            "location": "Unknown",
            "clues": [_clue_map_entry(clue, required_clue_ids) for clue in legacy_clues],
        })
    return mapped


def _clue_map_entry(clue, required_clue_ids: set[str]) -> dict:
    return {
        "id": clue.id,
        "title": clue.title,
        "status": "found" if clue.discovered else ("partial" if clue.partial_discovered else "hidden"),
        "required": clue.id in required_clue_ids,
        "action": f"{_natural_clue_verb(clue)} {clue.title.lower()}",
        "skill": clue.skill,
        "difficulty": clue.difficulty,
        "evidence": clue.evidence,
        "sanity_loss": clue.sanity_loss,
    }


def _npc_cards(scenario: COCScenario) -> list[dict]:
    location_names = {location_id: location.name for location_id, location in scenario.locations.items()}
    cards = []
    for npc in scenario.npcs:
        dialogue = list(npc.dialogue)
        cards.append({
            "id": npc.id,
            "name": npc.name,
            "location_id": npc.location_id,
            "location": location_names.get(npc.location_id or "", "Anywhere"),
            "description": npc.description,
            "first_line": dialogue[0] if dialogue else "",
            "keeper_use": _npc_keeper_use(npc),
        })
    return cards


def _npc_keeper_use(npc) -> str:
    if npc.dialogue:
        return f"Use them to deliver: {npc.dialogue[0]}"
    return "Use them as a human reaction shot and a reason to ask the investigator what they do next."

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
    opening = briefing.get("opening") or {}
    if opening:
        lines.append("Opening brief:")
        if opening.get("read_aloud"):
            lines.append("- Read aloud: " + opening["read_aloud"])
        if opening.get("investigator_hook"):
            lines.append("- Investigator hook: " + opening["investigator_hook"])
        if opening.get("first_objectives"):
            lines.append("- First objectives: " + "; ".join(opening["first_objectives"]))
        if opening.get("safety_note"):
            lines.append("- Safety note: " + opening["safety_note"])
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


def _opening_brief(
    scenario: COCScenario,
    hidden: list,
    blocked_exits: list[dict],
    spotlight_actions: list[str],
) -> dict:
    location = scenario.current_location()
    investigator = scenario.investigator
    local_hidden = [clue for clue in hidden if clue.location_id in {None, location.id}]
    first_clue = local_hidden[0] if local_hidden else (hidden[0] if hidden else None)
    objectives = [
        f"Establish why {investigator.name} is at {location.name}.",
        "Let the player choose how to inspect the first strange detail.",
    ]
    if first_clue is not None:
        objectives.append(f"Steer attention toward {first_clue.title} without naming it as the answer.")
    if blocked_exits:
        objectives.append(f"Foreshadow the blocked {blocked_exits[0]['name']} route and its pressure.")
    return {
        "read_aloud": _opening_read_aloud(scenario, first_clue),
        "investigator_hook": (
            f"{investigator.name}, a {investigator.occupation}, has enough expertise to notice what locals missed. "
            f"Ask what personal reason made them answer this case tonight."
        ),
        "first_objectives": objectives[:4],
        "first_turn_actions": list(spotlight_actions[:3]),
        "safety_note": "Confirm the table is comfortable with escalating dread, body horror, and loss of control before play.",
    }


def _opening_read_aloud(scenario: COCScenario, first_clue) -> str:
    location = scenario.current_location()
    clue_hint = ""
    if first_clue is not None:
        clue_hint = f" One detail refuses to sit still: {first_clue.title}."
    npc_names = [npc.name for npc in scenario.npcs if npc.location_id in {None, location.id}]
    npc_hint = f" {npc_names[0]} is close enough to answer questions." if npc_names else ""
    return f"At {location.name}, {location.description}{clue_hint}{npc_hint} What do you do first?"

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
    visited = _visited_location_ids(scenario)
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


def _visited_location_ids(scenario: COCScenario) -> set[str]:
    visited = set(scenario.visited_location_ids)
    if scenario.current_location_id:
        visited.add(scenario.current_location_id)
    return visited
