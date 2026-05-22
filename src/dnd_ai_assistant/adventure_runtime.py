from __future__ import annotations

import random
from dataclasses import dataclass, field

from .core.combat import ActionResource, CombatState, action_resource_for_spell
from .core.campaign import Campaign, Encounter, Location, NPC, Clue, SessionEvent
from .core.character import Character
from .core.config import DEFAULT_RULES_CONFIG
from .core.damage import adjusted_damage_amount
from .core.dnd5e import RollMode, ability_modifier, roll_attack, roll_d20_check, roll_damage
from .core.initiative import Combatant
from .core.skills import skill_label
from .core.spells import Spell


QUEST_COMPLETE_STATUS = "completed"
QUEST_FAILED_STATUS = "failed"
SUPPORTED_COMBAT_CONDITIONS = {
    "blinded",
    "frightened",
    "grappled",
    "incapacitated",
    "poisoned",
    "prone",
    "restrained",
    "stunned",
}
TEMPORARY_COMBAT_CONDITIONS = {"disengaging", "dodging"}
ACTION_BLOCKING_CONDITIONS = {"dead", "incapacitated", "stunned", "unconscious"}
SHIELD_AC_BONUS = 5
SPELL_EFFECTS = {
    "burning hands": "area_save_damage",
    "cure wounds": "healing",
    "guiding bolt": "spell_attack",
    "healing word": "healing",
    "magic missile": "auto_damage",
    "sacred flame": "sacred_flame",
    "shield": "reaction_defense",
}
ATTACK_SPELLS = {
    "guiding bolt": {"damage": "4d6", "damage_type": "radiant"},
}
AUTO_DAMAGE_SPELLS = {
    "magic missile": {"missiles": 3, "damage": "1d4+1", "damage_type": "force"},
}
SAVE_DAMAGE_SPELLS = {
    "sacred flame": {"ability": "dex", "label": "Dexterity", "damage": "1d8", "damage_type": "radiant"},
}
AREA_SAVE_DAMAGE_SPELLS = {
    "burning hands": {"ability": "dex", "label": "Dexterity", "damage": "3d6", "damage_type": "fire"},
}


DEFAULT_RUNTIME_ACTIONS = {
    "look": {"aliases": ["look", "look around", "where am i"], "handler": "look"},
    "inspect": {"aliases": ["inspect", "search", "investigate"], "handler": "inspect"},
    "talk": {"aliases": ["talk", "speak", "ask"], "handler": "talk"},
    "encounter": {"aliases": ["fight", "start encounter", "encounter"], "handler": "encounter"},
    "combat_status": {"aliases": ["combat", "combat status"], "handler": "combat_status"},
    "end_turn": {"aliases": ["end turn", "next turn"], "handler": "end_turn"},
    "use_action": {"aliases": ["use action"], "handler": "use_action"},
    "use_bonus_action": {"aliases": ["use bonus action"], "handler": "use_bonus_action"},
    "use_reaction": {"aliases": ["use reaction"], "handler": "use_reaction"},
    "dash": {"aliases": ["dash"], "handler": "dash"},
    "disengage": {"aliases": ["disengage"], "handler": "disengage"},
    "dodge": {"aliases": ["dodge"], "handler": "dodge"},
    "grapple": {"aliases": ["grapple"], "handler": "grapple"},
    "shove": {"aliases": ["shove"], "handler": "shove"},
    "escape_grapple": {"aliases": ["escape grapple"], "handler": "escape_grapple"},
    "set_condition": {"aliases": ["condition", "apply condition"], "handler": "set_condition"},
    "clear_condition": {"aliases": ["clear condition", "remove condition"], "handler": "clear_condition"},
    "spend_movement": {"aliases": ["spend movement", "use movement"], "handler": "spend_movement"},
    "attack": {"aliases": ["attack", "strike"], "handler": "attack"},
    "cast_spell": {"aliases": ["cast", "cast spell"], "handler": "cast_spell"},
    "death_save": {"aliases": ["death save"], "handler": "death_save"},
    "stabilize": {"aliases": ["stabilize", "stabilise"], "handler": "stabilize"},
    "flee_combat": {"aliases": ["flee", "retreat", "run away"], "handler": "flee_combat"},
    "surrender_combat": {"aliases": ["surrender"], "handler": "surrender_combat"},
    "accept_surrender": {"aliases": ["accept surrender", "enemy surrender", "hostiles surrender"], "handler": "accept_surrender"},
    "resolve_encounter": {"aliases": ["resolve encounter", "end encounter"], "handler": "resolve_encounter"},
    "quests": {"aliases": ["quests", "quest log"], "handler": "quests"},
    "complete_quest": {"aliases": ["complete quest", "finish quest"], "handler": "complete_quest"},
    "fail_quest": {"aliases": ["fail quest", "abandon quest"], "handler": "fail_quest"},
    "move": {"aliases": ["go", "move", "travel"], "handler": "move"},
    "log": {"aliases": ["log"], "handler": "log"},
    "help": {"aliases": ["help", "?"], "handler": "help"},
    "quit": {"aliases": ["quit", "exit"], "handler": "quit"},
}


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

    action_match = _match_runtime_action(runtime.campaign, normalized)
    handler = action_match["handler"]

    if handler == "quit":
        runtime.narrate("DM: The adventure pauses here.")
        return False
    if handler == "help":
        runtime.narrate("DM: Available actions: " + ", ".join(_runtime_action_names(runtime.campaign)) + ".")
        return True
    if handler == "look":
        describe_current_location(runtime)
        return True
    if handler == "inspect":
        reveal_location_clues(runtime, action_match.get("argument", ""))
        return True
    if handler == "talk":
        target = action_match.get("argument", "")
        return talk_to_npc(runtime, target)
    if handler == "encounter":
        return start_location_encounter(runtime)
    if handler == "combat_status":
        describe_active_combat(runtime)
        return True
    if handler == "end_turn":
        advance_active_combat(runtime)
        return True
    if handler == "use_action":
        spend_active_combat_resource(runtime, "action")
        return True
    if handler == "use_bonus_action":
        spend_active_combat_resource(runtime, "bonus_action")
        return True
    if handler == "use_reaction":
        spend_active_combat_resource(runtime, "reaction")
        return True
    if handler in {"dash", "disengage", "dodge"}:
        perform_basic_combat_action(runtime, handler)
        return True
    if handler == "grapple":
        contest_combat_control(runtime, action_match.get("argument", ""), control="grapple")
        return True
    if handler == "shove":
        contest_combat_control(runtime, action_match.get("argument", ""), control="shove")
        return True
    if handler == "escape_grapple":
        escape_grapple(runtime)
        return True
    if handler == "set_condition":
        set_combat_condition(runtime, action_match.get("argument", ""), enabled=True)
        return True
    if handler == "clear_condition":
        set_combat_condition(runtime, action_match.get("argument", ""), enabled=False)
        return True
    if handler == "spend_movement":
        spend_active_combat_movement(runtime, action_match.get("argument", ""))
        return True
    if handler == "attack":
        attack_active_combat_target(runtime, action_match.get("argument", ""))
        return True
    if handler == "cast_spell":
        cast_active_combat_spell(runtime, action_match.get("argument", ""))
        return True
    if handler == "death_save":
        roll_death_save(runtime, action_match.get("argument", ""))
        return True
    if handler == "stabilize":
        stabilize_character(runtime, action_match.get("argument", ""))
        return True
    if handler == "flee_combat":
        flee_active_combat(runtime)
        return True
    if handler == "surrender_combat":
        surrender_active_combat(runtime)
        return True
    if handler == "accept_surrender":
        accept_hostile_surrender(runtime)
        return True
    if handler == "resolve_encounter":
        return resolve_active_encounter(runtime)
    if handler == "quests":
        describe_quests(runtime)
        return True
    if handler == "complete_quest":
        return set_quest_status(runtime, action_match.get("argument", ""), QUEST_COMPLETE_STATUS)
    if handler == "fail_quest":
        return set_quest_status(runtime, action_match.get("argument", ""), QUEST_FAILED_STATUS)
    if handler == "log":
        runtime.narrate("DM: Session log:")
        for event in runtime.campaign.session_log:
            runtime.narrate(f"- [{event.actor}] {event.content}")
        return True
    if handler == "move":
        destination = action_match.get("argument", "")
        if not destination:
            runtime.narrate("DM: Where do you want to go?")
            return True
        return move_to(runtime, destination)

    runtime.narrate("DM: This adventure runtime does not know how to resolve that yet.")
    return True


def reveal_location_clues(runtime: AdventureRuntime, target: str = "") -> None:
    location = current_location(runtime.campaign)
    hidden_clues = [
        clue
        for clue in runtime.campaign.clues.values()
        if clue.location_id == location.id and not clue.discovered
    ]
    if target:
        hidden_clues = [clue for clue in hidden_clues if _matches_clue(clue, target)]
        if not hidden_clues:
            runtime.narrate("DM: You do not find anything matching that here.")
            return
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


def talk_to_npc(runtime: AdventureRuntime, target: str = "") -> bool:
    location = current_location(runtime.campaign)
    npcs = _npcs_at(runtime.campaign, location.id)
    if not npcs:
        runtime.narrate("DM: There is no one here to talk to.")
        return True

    npc = _match_npc(npcs, target)
    if npc is None:
        if target:
            runtime.narrate("DM: That person is not here.")
        else:
            runtime.narrate("DM: Who do you want to talk to? " + ", ".join(npc.name for npc in npcs) + ".")
        return True

    line = npc.dialogue or npc.public_description
    runtime.campaign.record_event(SessionEvent(actor=npc.name, content=line))
    runtime.narrate(f"{npc.name}: {line}")
    return True


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


def start_location_encounter(runtime: AdventureRuntime) -> bool:
    location = current_location(runtime.campaign)
    encounters = _encounters_at(runtime.campaign, location.id)
    if not encounters:
        runtime.narrate("DM: There is no active encounter here.")
        return True

    encounter = encounters[0]
    runtime.campaign.record_event(SessionEvent(actor="DM", content=f"Encounter started: {encounter.title}"))
    runtime.narrate(f"DM: Encounter - {encounter.title} ({encounter.difficulty}).")
    if encounter.trigger:
        runtime.narrate(f"DM: Trigger: {encounter.trigger}")
    if encounter.monsters:
        monsters = ", ".join(
            f"{monster.name} (AC {monster.armor_class}, HP {monster.current_hp}/{monster.max_hp})"
            for monster in encounter.monsters
        )
        runtime.narrate(f"DM: Monsters: {monsters}.")
    else:
        runtime.narrate("DM: No monsters are listed for this encounter.")
    if encounter.reward:
        runtime.narrate(f"DM: Reward: {encounter.reward}")
    combatants = _combatants_for_encounter(runtime.campaign, encounter)
    if combatants:
        combat = CombatState.from_combatants(combatants, rng=runtime.rng)
        runtime.campaign.active_combat = _combat_summary(encounter, combat)
        runtime.narrate("DM: Initiative order: " + ", ".join(_initiative_line(combatant) for combatant in combat.tracker.combatants) + ".")
        runtime.narrate(f"DM: Current turn: {combat.current().name}.")
    return True


def describe_active_combat(runtime: AdventureRuntime) -> None:
    combat = runtime.campaign.active_combat
    if combat is None:
        runtime.narrate("DM: There is no active combat.")
        return
    runtime.narrate(f"DM: Active combat round {combat.get('round', 1)}, turn: {combat.get('turn', '<unknown>')}.")
    resources = _active_resources(combat)
    turn_resources = resources.get(combat.get("turn"), {})
    if turn_resources:
        runtime.narrate(
            "DM: Resources: "
            f"action={turn_resources.get('action', True)}, "
            f"bonus_action={turn_resources.get('bonus_action', True)}, "
            f"reaction={turn_resources.get('reaction', True)}, "
            f"movement={turn_resources.get('movement', DEFAULT_RULES_CONFIG.default_movement_speed)}."
        )
    initiative = combat.get("initiative", [])
    if initiative:
        runtime.narrate(
            "DM: Initiative order: "
            + ", ".join(f"{entry['name']} {entry.get('initiative_total', 0)}" for entry in initiative)
            + "."
        )


def advance_active_combat(runtime: AdventureRuntime) -> None:
    combat = runtime.campaign.active_combat
    if combat is None:
        runtime.narrate("DM: There is no active combat.")
        return
    initiative = combat.get("initiative", [])
    if not initiative:
        runtime.narrate("DM: Active combat has no initiative order.")
        return

    current_turn = combat.get("turn")
    current_index = next((index for index, entry in enumerate(initiative) if entry["name"] == current_turn), 0)
    next_index = _next_active_combatant_index(combat, current_index)
    if next_index is None:
        runtime.narrate("DM: No combatants are able to take a turn.")
        return
    combat["turn"] = initiative[next_index]["name"]
    _reset_turn_resources(combat, combat["turn"])
    runtime.campaign.record_event(
        SessionEvent(actor="DM", content=f"Combat advanced to round {combat['round']}: {combat['turn']}.")
    )
    runtime.narrate(f"DM: Combat advances to round {combat['round']}, turn: {combat['turn']}.")
    active = _active_combatant(combat, combat["turn"])
    if active is not None and active.get("is_player") is False and active.get("current_hp", 0) > 0:
        _run_automatic_monster_turn(runtime, active)


def spend_active_combat_resource(runtime: AdventureRuntime, resource: str) -> None:
    combat = runtime.campaign.active_combat
    if combat is None:
        runtime.narrate("DM: There is no active combat.")
        return
    turn = combat.get("turn")
    combatant = _active_combatant(combat, str(turn or ""))
    block = _combatant_action_block_reason(runtime.campaign, combatant)
    if block and resource in {"action", "bonus_action", "reaction"}:
        runtime.narrate(f"DM: {turn} cannot use {resource.replace('_', ' ')} while {block}.")
        return
    resources = _active_resources(combat).setdefault(turn, _default_turn_resources())
    if not resources.get(resource, True):
        runtime.narrate(f"DM: {turn} has already used {resource.replace('_', ' ')}.")
        return
    resources[resource] = False
    runtime.campaign.record_event(SessionEvent(actor="DM", content=f"{turn} used {resource.replace('_', ' ')}."))
    runtime.narrate(f"DM: {turn} uses {resource.replace('_', ' ')}.")


def spend_active_combat_movement(runtime: AdventureRuntime, amount_text: str) -> None:
    combat = runtime.campaign.active_combat
    if combat is None:
        runtime.narrate("DM: There is no active combat.")
        return
    try:
        amount = int(amount_text.strip())
    except ValueError:
        runtime.narrate("DM: How many feet of movement?")
        return
    if amount <= 0:
        runtime.narrate("DM: Movement must be positive.")
        return
    turn = combat.get("turn")
    combatant = _active_combatant(combat, str(turn or ""))
    block = _combatant_action_block_reason(runtime.campaign, combatant)
    if block in ACTION_BLOCKING_CONDITIONS:
        runtime.narrate(f"DM: {turn} cannot move while {block}.")
        return
    if combatant is not None and "grappled" in _combatant_condition_names(runtime.campaign, combatant):
        runtime.narrate(f"DM: {turn} is grappled and cannot spend movement.")
        return
    resources = _active_resources(combat).setdefault(turn, _default_turn_resources())
    remaining = resources.get("movement", DEFAULT_RULES_CONFIG.default_movement_speed)
    if amount > remaining:
        runtime.narrate("DM: Not enough movement remaining.")
        return
    resources["movement"] = remaining - amount
    runtime.campaign.record_event(SessionEvent(actor="DM", content=f"{turn} moved {amount} feet."))
    runtime.narrate(f"DM: {turn} moves {amount} feet, {resources['movement']} feet remaining.")
    _maybe_resolve_opportunity_attack(runtime, str(turn), resources)


def perform_basic_combat_action(runtime: AdventureRuntime, action: str) -> None:
    combat = runtime.campaign.active_combat
    if combat is None:
        runtime.narrate("DM: There is no active combat.")
        return
    turn = str(combat.get("turn") or "")
    combatant = _active_combatant(combat, turn)
    if combatant is None:
        runtime.narrate("DM: Current combatant is not in initiative.")
        return
    block = _combatant_action_block_reason(runtime.campaign, combatant)
    if block:
        runtime.narrate(f"DM: {turn} cannot take actions while {block}.")
        return
    resources = _active_resources(combat).setdefault(turn, _default_turn_resources())
    if not resources.get("action", True):
        runtime.narrate(f"DM: {turn} has already used action.")
        return
    resources["action"] = False
    if action == "dash":
        resources["movement"] = int(resources.get("movement", 0)) + DEFAULT_RULES_CONFIG.default_movement_speed
        content = f"{turn} dashes, increasing remaining movement to {resources['movement']} feet."
    elif action == "dodge":
        _set_combatant_condition(runtime.campaign, combatant, "dodging", True, persist_character=False)
        content = f"{turn} dodges; attacks against them have disadvantage until their next turn."
    elif action == "disengage":
        _set_combatant_condition(runtime.campaign, combatant, "disengaging", True, persist_character=False)
        content = f"{turn} disengages; they avoid opportunity attacks this turn."
    else:
        content = f"{turn} uses action."
    runtime.campaign.record_event(SessionEvent(actor="DM", content=content))
    runtime.narrate(f"DM: {content}")


def contest_combat_control(runtime: AdventureRuntime, target_text: str, control: str) -> None:
    combat = runtime.campaign.active_combat
    if combat is None:
        runtime.narrate("DM: There is no active combat.")
        return
    actor = _active_combatant(combat, str(combat.get("turn") or ""))
    target = _active_combatant(combat, target_text)
    if actor is None:
        runtime.narrate("DM: Current combatant is not in initiative.")
        return
    if target is None:
        runtime.narrate("DM: Target is not in active combat.")
        return
    if actor["name"] == target["name"]:
        runtime.narrate("DM: A combatant cannot target itself.")
        return
    if bool(actor.get("is_player")) == bool(target.get("is_player")):
        runtime.narrate("DM: Combat control actions need an opposing target.")
        return
    block = _combatant_action_block_reason(runtime.campaign, actor)
    if block:
        runtime.narrate(f"DM: {actor['name']} cannot take actions while {block}.")
        return
    resources = _active_resources(combat).setdefault(actor["name"], _default_turn_resources())
    if not resources.get("action", True):
        runtime.narrate(f"DM: {actor['name']} has already used action.")
        return
    resources["action"] = False

    attacker_check = roll_d20_check(modifier=_athletics_modifier(runtime.campaign, actor["name"]), rng=runtime.rng)
    defender_athletics = roll_d20_check(modifier=_athletics_modifier(runtime.campaign, target["name"]), rng=runtime.rng)
    defender_acrobatics = roll_d20_check(modifier=_acrobatics_modifier(runtime.campaign, target["name"]), rng=runtime.rng)
    defender_check = defender_athletics if defender_athletics.total >= defender_acrobatics.total else defender_acrobatics
    success = attacker_check.total >= defender_check.total

    if control == "grapple":
        effect = "grappled"
        if success:
            _set_combatant_condition(runtime.campaign, target, effect, True, persist_character=True)
            target["grappled_by"] = actor["name"]
            result_text = f"{target['name']} is grappled."
        else:
            result_text = "The grapple fails."
    else:
        effect = "prone"
        if success:
            _set_combatant_condition(runtime.campaign, target, effect, True, persist_character=True)
            result_text = f"{target['name']} is knocked prone."
        else:
            result_text = "The shove fails."

    content = (
        f"{actor['name']} tries to {control} {target['name']}: Athletics {attacker_check.total} vs "
        f"{target['name']} {defender_check.total}. {result_text}"
    )
    runtime.campaign.record_event(SessionEvent(actor="System", content=content))
    runtime.narrate(f"DM: {content}")


def escape_grapple(runtime: AdventureRuntime) -> None:
    combat = runtime.campaign.active_combat
    if combat is None:
        runtime.narrate("DM: There is no active combat.")
        return
    actor = _active_combatant(combat, str(combat.get("turn") or ""))
    if actor is None:
        runtime.narrate("DM: Current combatant is not in initiative.")
        return
    if "grappled" not in _combatant_condition_names(runtime.campaign, actor):
        runtime.narrate(f"DM: {actor['name']} is not grappled.")
        return
    block = _combatant_action_block_reason(runtime.campaign, actor)
    if block:
        runtime.narrate(f"DM: {actor['name']} cannot take actions while {block}.")
        return
    resources = _active_resources(combat).setdefault(actor["name"], _default_turn_resources())
    if not resources.get("action", True):
        runtime.narrate(f"DM: {actor['name']} has already used action.")
        return
    resources["action"] = False
    grappler = _active_combatant(combat, str(actor.get("grappled_by") or ""))
    if grappler is None:
        _set_combatant_condition(runtime.campaign, actor, "grappled", False, persist_character=True)
        actor.pop("grappled_by", None)
        runtime.narrate(f"DM: {actor['name']} is no longer grappled.")
        return
    escape_athletics = roll_d20_check(modifier=_athletics_modifier(runtime.campaign, actor["name"]), rng=runtime.rng)
    escape_acrobatics = roll_d20_check(modifier=_acrobatics_modifier(runtime.campaign, actor["name"]), rng=runtime.rng)
    escape_check = escape_athletics if escape_athletics.total >= escape_acrobatics.total else escape_acrobatics
    hold_check = roll_d20_check(modifier=_athletics_modifier(runtime.campaign, grappler["name"]), rng=runtime.rng)
    success = escape_check.total >= hold_check.total
    if success:
        _set_combatant_condition(runtime.campaign, actor, "grappled", False, persist_character=True)
        actor.pop("grappled_by", None)
        result_text = "The grapple ends."
    else:
        result_text = "The grapple holds."
    content = (
        f"{actor['name']} tries to escape the grapple: {escape_check.total} vs "
        f"{grappler['name']} Athletics {hold_check.total}. {result_text}"
    )
    runtime.campaign.record_event(SessionEvent(actor="System", content=content))
    runtime.narrate(f"DM: {content}")


def set_combat_condition(runtime: AdventureRuntime, target_text: str, enabled: bool) -> None:
    name, condition = _parse_condition_text(target_text)
    if not name or not condition:
        runtime.narrate(
            "DM: Use 'condition <target> <blinded|frightened|grappled|incapacitated|"
            "poisoned|prone|restrained|stunned>'."
        )
        return
    if condition not in SUPPORTED_COMBAT_CONDITIONS:
        runtime.narrate(f"DM: Unsupported condition: {condition}.")
        return
    combatant = _active_combatant(runtime.campaign.active_combat or {}, name)
    character = _match_character(runtime.campaign, name)
    if combatant is None and character is None:
        runtime.narrate("DM: Target is not in active combat or party characters.")
        return
    target_name = combatant["name"] if combatant is not None else character.name
    if character is not None:
        if enabled:
            character.conditions.add(condition)
        else:
            character.conditions.discard(condition)
    if combatant is not None:
        _set_combatant_condition(runtime.campaign, combatant, condition, enabled, persist_character=False)
        if condition == "grappled" and not enabled:
            combatant.pop("grappled_by", None)
    verb = "gains" if enabled else "loses"
    content = f"{target_name} {verb} {condition}."
    runtime.campaign.record_event(SessionEvent(actor="DM", content=content))
    runtime.narrate(f"DM: {content}")


def attack_active_combat_target(runtime: AdventureRuntime, target: str) -> None:
    combat = runtime.campaign.active_combat
    if combat is None:
        runtime.narrate("DM: There is no active combat.")
        return
    if not target.strip():
        runtime.narrate("DM: Who is the target?")
        return
    attacker = _active_combatant(combat, combat.get("turn", ""))
    defender = _active_combatant(combat, target)
    if attacker is None:
        runtime.narrate("DM: Current attacker is not in initiative.")
        return
    if defender is None:
        runtime.narrate("DM: Target is not in active combat.")
        return
    block = _combatant_action_block_reason(runtime.campaign, attacker)
    if block:
        runtime.narrate(f"DM: {attacker['name']} cannot attack while {block}.")
        return
    if attacker["name"] == defender["name"]:
        runtime.narrate("DM: A combatant cannot attack itself.")
        return
    if not _active_resources(combat).setdefault(attacker["name"], _default_turn_resources()).get("action", True):
        runtime.narrate(f"DM: {attacker['name']} has already used action.")
        return

    mode = _attack_mode(runtime.campaign, attacker, defender)
    effective_ac = defender.get("armor_class", 10)
    attack = roll_attack(
        attack_bonus=attacker.get("attack_bonus", 0),
        target_ac=effective_ac,
        damage_expression=attacker.get("damage", "1d4"),
        mode=mode,
        rng=runtime.rng,
    )
    shield_text = ""
    if attack.hit:
        shield_text = _try_apply_shield_reaction(
            runtime, defender, attack.attack.total, effective_ac, attack.attack.natural_20
        )
        if shield_text:
            effective_ac += SHIELD_AC_BONUS
            attack = type(attack)(
                attack=attack.attack,
                target_ac=effective_ac,
                hit=attack.attack.natural_20 or (attack.attack.total >= effective_ac and not attack.attack.natural_1),
                damage=attack.damage if attack.attack.total >= effective_ac or attack.attack.natural_20 else None,
            )
    _active_resources(combat)[attacker["name"]]["action"] = False
    if attack.hit and attack.damage is not None:
        before = defender.get("current_hp", 0)
        damage_type = attacker.get("damage_type", "untyped")
        was_unconscious = _is_unconscious_character(runtime.campaign, defender)
        damage_amount = _apply_combat_damage(runtime.campaign, defender, attack.damage.total, damage_type)
        adjustment = ""
        if damage_amount != attack.damage.total:
            adjustment = f" ({attack.damage.total} before adjustments)"
        content = (
            f"{attacker['name']} attacks {defender['name']}: {attack.attack.total} vs AC {effective_ac} ({mode.value}), "
            f"hit for {damage_amount} {damage_type} damage{adjustment}: HP {before} -> {defender['current_hp']}."
        )
        if shield_text:
            content += " " + shield_text
        concentration = _concentration_check_text(runtime, defender, damage_amount)
        if concentration:
            content += " " + concentration
        death_saves = _death_save_damage_text(runtime, defender, damage_amount, was_unconscious)
        if death_saves:
            content += " " + death_saves
    else:
        content = f"{attacker['name']} attacks {defender['name']}: {attack.attack.total} vs AC {effective_ac} ({mode.value}), miss."
        if shield_text:
            content += " " + shield_text
    runtime.campaign.record_event(SessionEvent(actor="System", content=content))
    runtime.narrate(f"DM: {content}")
    if attack.hit and _all_hostile_combatants_defeated(combat):
        _finish_active_encounter(runtime, "All hostile combatants are defeated.")
    elif attack.hit and _all_player_combatants_defeated(combat):
        _end_active_combat(runtime, "All player combatants are defeated.", mark_encounter_resolved=False)
    elif attack.hit:
        _maybe_record_morale_hint(runtime)


def cast_active_combat_spell(runtime: AdventureRuntime, spell_text: str) -> None:
    combat = runtime.campaign.active_combat
    if combat is None:
        runtime.narrate("DM: There is no active combat.")
        return
    caster_combatant = _active_combatant(combat, str(combat.get("turn") or ""))
    block = _combatant_action_block_reason(runtime.campaign, caster_combatant)
    if block:
        runtime.narrate(f"DM: {combat.get('turn')} cannot cast spells while {block}.")
        return
    spell_name, slot_level = _parse_spell_cast_text(spell_text)
    if not spell_name:
        runtime.narrate("DM: Which spell?")
        return
    caster_name = combat.get("turn", "")
    caster = runtime.campaign.characters.get(caster_name)
    if caster is None:
        runtime.narrate("DM: Only player characters can cast spells in the current runtime.")
        return
    if caster.spellcasting is None:
        runtime.narrate(f"DM: {caster.name} cannot cast spells.")
        return

    spell, target_text = _match_known_spell_with_target(caster, spell_name)
    if spell is None:
        runtime.narrate(f"DM: {caster.name} does not know that spell.")
        return

    resource = action_resource_for_spell(spell)
    resources = _active_resources(combat).setdefault(caster.name, _default_turn_resources())
    resource_name = _resource_key(resource)
    if not resources.get(resource_name, True):
        runtime.narrate(f"DM: {caster.name} has already used {resource_name.replace('_', ' ')}.")
        return
    target_error = _validate_spell_effect_target(runtime, spell.name, target_text)
    if target_error:
        runtime.narrate(f"DM: {target_error}")
        return

    try:
        cast_spell = caster.spellcasting.cast_spell(spell.name, slot_level=slot_level)
    except ValueError as exc:
        runtime.narrate(f"DM: {exc}")
        return

    resources[resource_name] = False
    slot_text = ""
    effective_level = None
    if cast_spell.level > 0:
        effective_level = slot_level if slot_level is not None else cast_spell.level
        slot_text = f" using a level {effective_level} slot"
    effect_text = _apply_spell_effect(runtime, caster, cast_spell.name, effective_level, target_text)
    content = f"{caster.name} casts {cast_spell.name}{slot_text}, spending {resource_name.replace('_', ' ')}."
    if effect_text:
        content += f" {effect_text}"
    runtime.campaign.record_event(SessionEvent(actor="System", content=content))
    runtime.narrate(f"DM: {content}")
    if runtime.campaign.active_combat is not None and _all_hostile_combatants_defeated(runtime.campaign.active_combat):
        _finish_active_encounter(runtime, "All hostile combatants are defeated.")
    elif runtime.campaign.active_combat is not None and _all_player_combatants_defeated(runtime.campaign.active_combat):
        _end_active_combat(runtime, "All player combatants are defeated.", mark_encounter_resolved=False)
    elif runtime.campaign.active_combat is not None and effect_text:
        _maybe_record_morale_hint(runtime)


def roll_death_save(runtime: AdventureRuntime, target: str) -> None:
    character = _match_character(runtime.campaign, target)
    if character is None:
        runtime.narrate("DM: Which character is making a death save?")
        return
    if character.current_hp > 0 or "unconscious" not in character.conditions:
        runtime.narrate(f"DM: {character.name} does not need a death save.")
        return
    if "stable" in character.conditions:
        runtime.narrate(f"DM: {character.name} is stable and does not need a death save.")
        return
    if "dead" in character.conditions:
        runtime.narrate(f"DM: {character.name} is already dead.")
        return

    result = roll_d20_check(rng=runtime.rng)
    if result.natural_20:
        character.heal(1)
        content = f"{character.name} rolls a natural 20 death save and regains 1 HP."
    elif result.natural_1:
        _add_death_save_failure(character, 2)
        content = f"{character.name} rolls a natural 1 death save: 2 failures."
    elif result.total >= 10:
        character.death_save_successes = min(3, character.death_save_successes + 1)
        content = f"{character.name} succeeds on a death save ({character.death_save_successes}/3 successes)."
        if character.death_save_successes >= 3:
            _stabilize(character)
            content += " They are stable."
    else:
        _add_death_save_failure(character, 1)
        content = f"{character.name} fails a death save ({character.death_save_failures}/3 failures)."
    if "dead" in character.conditions:
        content += " They die."
    runtime.campaign.record_event(SessionEvent(actor="DM", content=content))
    runtime.narrate(f"DM: {content}")


def stabilize_character(runtime: AdventureRuntime, target: str) -> None:
    character = _match_character(runtime.campaign, target)
    if character is None:
        runtime.narrate("DM: Which character do you want to stabilize?")
        return
    if character.current_hp > 0:
        runtime.narrate(f"DM: {character.name} is conscious and does not need stabilization.")
        return
    if "dead" in character.conditions:
        runtime.narrate(f"DM: {character.name} cannot be stabilized because they are dead.")
        return
    _stabilize(character)
    content = f"{character.name} is stable at 0 HP."
    runtime.campaign.record_event(SessionEvent(actor="DM", content=content))
    runtime.narrate(f"DM: {content}")


def resolve_active_encounter(runtime: AdventureRuntime) -> bool:
    combat = runtime.campaign.active_combat
    if combat is None:
        runtime.narrate("DM: There is no active encounter to resolve.")
        return True
    _finish_active_encounter(runtime, "Encounter resolved manually.")
    return True


def flee_active_combat(runtime: AdventureRuntime) -> None:
    if runtime.campaign.active_combat is None:
        runtime.narrate("DM: There is no active combat to flee.")
        return
    _end_active_combat(
        runtime,
        "The party retreats from combat. The encounter remains unresolved.",
        mark_encounter_resolved=False,
        outcome="fled",
    )


def surrender_active_combat(runtime: AdventureRuntime) -> None:
    if runtime.campaign.active_combat is None:
        runtime.narrate("DM: There is no active combat to surrender.")
        return
    _end_active_combat(
        runtime,
        "The party surrenders. The encounter remains unresolved.",
        mark_encounter_resolved=False,
        outcome="party_surrendered",
    )


def accept_hostile_surrender(runtime: AdventureRuntime) -> None:
    if runtime.campaign.active_combat is None:
        runtime.narrate("DM: There is no active combat where hostiles can surrender.")
        return
    _end_active_combat(
        runtime,
        "Hostile combatants surrender.",
        mark_encounter_resolved=True,
        outcome="hostiles_surrendered",
    )


def _finish_active_encounter(runtime: AdventureRuntime, reason: str) -> None:
    _end_active_combat(runtime, reason, mark_encounter_resolved=True, outcome="resolved")


def _end_active_combat(
    runtime: AdventureRuntime, reason: str, mark_encounter_resolved: bool, outcome: str = "ended"
) -> None:
    combat = runtime.campaign.active_combat
    if combat is None:
        return
    encounter_id = combat.get("encounter_id")
    encounter = runtime.campaign.encounters.get(encounter_id)
    combat["outcome"] = outcome
    if encounter is not None:
        if mark_encounter_resolved:
            encounter.resolved = True
        status = "Encounter resolved" if mark_encounter_resolved else "Combat ended"
        content = f"{status}: {encounter.title}. {reason}"
        if mark_encounter_resolved and encounter.reward:
            content += f" Reward: {encounter.reward}"
    else:
        status = "Encounter resolved" if mark_encounter_resolved else "Combat ended"
        content = f"{status}: {encounter_id}. {reason}"
    runtime.campaign.active_combat = None
    runtime.campaign.record_event(SessionEvent(actor="DM", content=content))
    runtime.narrate(f"DM: {content}")


def _run_automatic_monster_turn(runtime: AdventureRuntime, monster: dict) -> None:
    combat = runtime.campaign.active_combat
    if combat is None:
        return
    strategy = _monster_action_strategy(combat, monster)
    target = _automatic_monster_target(runtime.campaign, combat, strategy)
    if target is None:
        runtime.narrate(f"DM: {monster['name']} has no valid player target.")
        return
    summary = f"Automatic monster action: {monster['name']} uses {strategy} and targets {target['name']}."
    combat["monster_action_strategy"] = strategy
    combat["last_automatic_action"] = summary
    runtime.campaign.record_event(
        SessionEvent(actor="System", content=summary)
    )
    runtime.narrate(f"System: {summary}")
    attack_active_combat_target(runtime, target["name"])
    if runtime.campaign.active_combat is None:
        return
    advance_active_combat(runtime)


def _maybe_resolve_opportunity_attack(runtime: AdventureRuntime, mover_name: str, mover_resources: dict) -> None:
    combat = runtime.campaign.active_combat
    if combat is None or mover_resources.get("provoked_opportunity_attack"):
        return
    mover = _active_combatant(combat, mover_name)
    if mover is None or not _combatant_can_take_turn(mover):
        return
    mover_conditions = _combatant_condition_names(runtime.campaign, mover)
    if "disengaging" in mover_conditions:
        runtime.narrate(f"DM: {mover['name']} has Disengaged and avoids opportunity attacks.")
        return
    attacker = _first_opportunity_attacker(runtime.campaign, combat, mover)
    if attacker is None:
        return
    attacker_resources = _active_resources(combat).setdefault(attacker["name"], _default_turn_resources())
    attacker_resources["reaction"] = False
    mover_resources["provoked_opportunity_attack"] = True
    content = _resolve_reaction_attack(runtime, attacker, mover, "opportunity attack")
    combat["last_automatic_action"] = f"Opportunity attack: {content}"
    runtime.campaign.record_event(SessionEvent(actor="System", content=f"Opportunity attack: {content}"))
    runtime.narrate(f"System: Opportunity attack: {content}")
    if runtime.campaign.active_combat is None:
        return
    if _all_hostile_combatants_defeated(combat):
        _finish_active_encounter(runtime, "All hostile combatants are defeated.")
    elif _all_player_combatants_defeated(combat):
        _end_active_combat(runtime, "All player combatants are defeated.", mark_encounter_resolved=False)
    else:
        _maybe_record_morale_hint(runtime)


def _first_opportunity_attacker(campaign: Campaign, combat: dict, mover: dict) -> dict | None:
    for candidate in _living_hostile_combatants(combat, campaign, str(mover.get("name") or "")):
        if _combatant_action_block_reason(campaign, candidate):
            continue
        resources = _active_resources(combat).setdefault(candidate["name"], _default_turn_resources())
        if resources.get("reaction", True):
            return candidate
    return None


def _resolve_reaction_attack(
    runtime: AdventureRuntime, attacker: dict, defender: dict, attack_label: str
) -> str:
    mode = _attack_mode(runtime.campaign, attacker, defender)
    effective_ac = defender.get("armor_class", 10)
    attack = roll_attack(
        attack_bonus=attacker.get("attack_bonus", 0),
        target_ac=effective_ac,
        damage_expression=attacker.get("damage", "1d4"),
        mode=mode,
        rng=runtime.rng,
    )
    shield_text = ""
    if attack.hit:
        shield_text = _try_apply_shield_reaction(
            runtime, defender, attack.attack.total, effective_ac, attack.attack.natural_20
        )
        if shield_text:
            effective_ac += SHIELD_AC_BONUS
            attack = type(attack)(
                attack=attack.attack,
                target_ac=effective_ac,
                hit=attack.attack.natural_20 or (attack.attack.total >= effective_ac and not attack.attack.natural_1),
                damage=attack.damage if attack.attack.total >= effective_ac or attack.attack.natural_20 else None,
            )
    if attack.hit and attack.damage is not None:
        before = defender.get("current_hp", 0)
        damage_type = attacker.get("damage_type", "untyped")
        was_unconscious = _is_unconscious_character(runtime.campaign, defender)
        damage_amount = _apply_combat_damage(runtime.campaign, defender, attack.damage.total, damage_type)
        adjustment = ""
        if damage_amount != attack.damage.total:
            adjustment = f" ({attack.damage.total} before adjustments)"
        content = (
            f"{attacker['name']} makes an {attack_label} against {defender['name']}: "
            f"{attack.attack.total} vs AC {effective_ac} ({mode.value}), hit for "
            f"{damage_amount} {damage_type} damage{adjustment}: HP {before} -> {defender['current_hp']}."
        )
        if shield_text:
            content += " " + shield_text
        concentration = _concentration_check_text(runtime, defender, damage_amount)
        if concentration:
            content += " " + concentration
        death_saves = _death_save_damage_text(runtime, defender, damage_amount, was_unconscious)
        if death_saves:
            content += " " + death_saves
        return content
    content = (
        f"{attacker['name']} makes an {attack_label} against {defender['name']}: "
        f"{attack.attack.total} vs AC {effective_ac} ({mode.value}), miss."
    )
    if shield_text:
        content += " " + shield_text
    return content


def _maybe_record_morale_hint(runtime: AdventureRuntime) -> None:
    combat = runtime.campaign.active_combat
    if combat is None or combat.get("morale_prompted"):
        return
    if not _hostiles_are_wavering(combat):
        return
    hint = (
        "Hostile morale is wavering; consider parley, accept surrender if they yield, "
        "or let them flee instead of fighting to the last hit point."
    )
    combat["morale_prompted"] = True
    combat["morale_hint"] = hint
    runtime.campaign.record_event(SessionEvent(actor="System", content=f"Morale pressure: {hint}"))
    runtime.narrate(f"System: Morale pressure: {hint}")


def _hostiles_are_wavering(combat: dict) -> bool:
    hostiles = [entry for entry in combat.get("initiative", []) if entry.get("is_player") is False]
    if len(hostiles) < 2:
        return False
    living = [entry for entry in hostiles if int(entry.get("current_hp") or 0) > 0]
    defeated_count = len(hostiles) - len(living)
    return defeated_count > 0 and defeated_count >= len(hostiles) / 2


def _monster_action_strategy(combat: dict, monster: dict) -> str:
    strategy = str(monster.get("action_strategy") or combat.get("monster_action_strategy") or "default_attack")
    if strategy not in {"default_attack", "lowest_hp", "concentrating"}:
        return "default_attack"
    return strategy


def _automatic_monster_target(campaign: Campaign, combat: dict, strategy: str) -> dict | None:
    targets = [
        entry
        for entry in combat.get("initiative", [])
        if entry.get("is_player") is True and entry.get("current_hp", 0) > 0
    ]
    if not targets:
        return None
    if strategy == "lowest_hp":
        return min(targets, key=lambda entry: (entry.get("current_hp", 0), entry.get("name", "")))
    if strategy == "concentrating":
        concentrating = [
            entry
            for entry in targets
            if _character_is_concentrating(campaign, str(entry.get("name") or ""))
        ]
        if concentrating:
            return min(concentrating, key=lambda entry: (entry.get("current_hp", 0), entry.get("name", "")))
    return targets[0]


def describe_quests(runtime: AdventureRuntime) -> None:
    if not runtime.campaign.quests:
        runtime.narrate("DM: There are no quests in this campaign.")
        return

    runtime.narrate("DM: Quests:")
    for quest in runtime.campaign.quests.values():
        runtime.narrate(f"- [{quest.status}] {quest.title}: {quest.summary}")


def set_quest_status(runtime: AdventureRuntime, target: str, status: str) -> bool:
    quest = _match_quest(runtime.campaign, target)
    if quest is None:
        if target:
            runtime.narrate("DM: Quest not found.")
        else:
            runtime.narrate("DM: Which quest?")
        return True

    before = quest.status
    quest.status = status
    runtime.campaign.record_event(
        SessionEvent(actor="DM", content=f"Quest status changed: {quest.title} {before} -> {status}.")
    )
    runtime.narrate(f"DM: Quest updated - {quest.title}: {before} -> {status}.")
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


def _match_npc(npcs: list[NPC], target: str) -> NPC | None:
    normalized = target.strip().lower()
    if not normalized and len(npcs) == 1:
        return npcs[0]
    for npc in npcs:
        name = npc.name.lower()
        if normalized == npc.id.lower() or normalized == name or normalized in name:
            return npc
    return None


def _matches_clue(clue: Clue, target: str) -> bool:
    normalized = target.strip().lower()
    title = clue.title.lower()
    text = clue.public_text.lower()
    return normalized == clue.id.lower() or normalized in title or normalized in text


def _match_quest(campaign: Campaign, target: str):
    normalized = target.strip().lower()
    if not normalized and len(campaign.quests) == 1:
        return next(iter(campaign.quests.values()))
    for quest in campaign.quests.values():
        title = quest.title.lower()
        if normalized == quest.id.lower() or normalized == title or normalized in title:
            return quest
    return None


def _discovered_clues_at(campaign: Campaign, location_id: str) -> list[Clue]:
    return [clue for clue in campaign.clues.values() if clue.location_id == location_id and clue.discovered]


def _encounters_at(campaign: Campaign, location_id: str) -> list[Encounter]:
    return [
        encounter
        for encounter in campaign.encounters.values()
        if encounter.location_id == location_id and not encounter.resolved
    ]


def _combatants_for_encounter(campaign: Campaign, encounter: Encounter) -> list[Combatant]:
    combatants = [
        Combatant(
            name=character.name,
            initiative_modifier=character.ability_modifier("dex"),
            armor_class=character.armor_class,
            current_hp=character.current_hp,
            is_player=True,
        )
        for character in campaign.characters.values()
    ]
    combatants.extend(
        Combatant(
            name=monster.name,
            initiative_modifier=monster.initiative_modifier,
            armor_class=monster.armor_class,
            current_hp=monster.current_hp,
        )
        for monster in encounter.monsters
    )
    return combatants


def _combat_summary(encounter: Encounter, combat: CombatState) -> dict:
    resources = {
        combatant.name: _default_turn_resources()
        for combatant in combat.tracker.combatants
    }
    return {
        "encounter_id": encounter.id,
        "round": combat.tracker.round_number,
        "turn": combat.current().name,
        "resources": resources,
        "initiative": [
            {
                "name": combatant.name,
                "initiative_roll": combatant.initiative_roll,
                "initiative_modifier": combatant.initiative_modifier,
                "initiative_total": combatant.initiative_total,
                "is_player": combatant.is_player,
                "armor_class": combatant.armor_class,
                "current_hp": combatant.current_hp,
                **_attack_profile(encounter, combatant.name),
                **_defense_profile(encounter, combatant.name),
            }
            for combatant in combat.tracker.combatants
        ],
    }


def _initiative_line(combatant: Combatant) -> str:
    return f"{combatant.name} {combatant.initiative_total}"


def _active_resources(combat: dict) -> dict:
    return combat.setdefault("resources", {})


def _default_turn_resources() -> dict:
    return {
        "action": True,
        "bonus_action": True,
        "reaction": True,
        "movement": DEFAULT_RULES_CONFIG.default_movement_speed,
    }


def _resource_key(resource: ActionResource) -> str:
    return resource.value


def _parse_spell_cast_text(spell_text: str) -> tuple[str, int | None]:
    words = spell_text.strip().split()
    if not words:
        return "", None
    if len(words) >= 2 and words[-2].lower() == "level":
        try:
            return " ".join(words[:-2]), int(words[-1])
        except ValueError:
            return spell_text.strip(), None
    if len(words) >= 3 and words[-3].lower() == "at" and words[-2].lower() == "level":
        try:
            return " ".join(words[:-3]), int(words[-1])
        except ValueError:
            return spell_text.strip(), None
    return spell_text.strip(), None


def _match_known_spell_with_target(caster: Character, spell_text: str) -> tuple[Spell | None, str]:
    if caster.spellcasting is None:
        return None, ""
    normalized = spell_text.strip().lower()
    for spell in caster.spellcasting.known_spells:
        if spell.name.lower() == normalized:
            return spell, ""
    for spell in sorted(caster.spellcasting.known_spells, key=lambda item: len(item.name), reverse=True):
        spell_name = spell.name.lower()
        if normalized.startswith(spell_name + " "):
            target = spell_text[len(spell.name) :].strip()
            if target.lower().startswith("on "):
                target = target[3:].strip()
            return spell, target
    return None, ""


def _parse_condition_text(text: str) -> tuple[str, str]:
    words = text.strip().split()
    if len(words) < 2:
        return "", ""
    return " ".join(words[:-1]), words[-1].lower()


def _apply_spell_effect(
    runtime: AdventureRuntime,
    caster: Character,
    spell_name: str,
    slot_level: int | None,
    target_text: str,
) -> str:
    normalized = spell_name.strip().lower()
    effect = SPELL_EFFECTS.get(normalized)
    if effect == "sacred_flame":
        return _apply_sacred_flame(runtime, caster, target_text)
    if effect == "spell_attack":
        return _apply_spell_attack_spell(runtime, caster, normalized, target_text)
    if effect == "auto_damage":
        return _apply_auto_damage_spell(runtime, normalized, target_text)
    if effect == "area_save_damage":
        return _apply_area_save_damage_spell(runtime, caster, normalized)
    if effect != "healing":
        return ""

    target = _match_character(runtime.campaign, target_text) if target_text else caster
    if target is None:
        return "The healing has no valid target."

    level = max(1, slot_level or 1)
    die = "d4" if normalized == "healing word" else "d8"
    modifier = caster.ability_modifier(caster.spellcasting.ability) if caster.spellcasting is not None else 0
    healing = roll_damage(_signed_expression(f"{level}{die}", modifier), runtime.rng)
    before = target.current_hp
    target.heal(max(0, healing.total))
    _sync_combatant_hp(runtime.campaign.active_combat, target.name, target.current_hp)
    return f"{target.name} heals {target.current_hp - before} HP: {before} -> {target.current_hp}."


def _validate_spell_effect_target(runtime: AdventureRuntime, spell_name: str, target_text: str) -> str:
    normalized = spell_name.strip().lower()
    effect = SPELL_EFFECTS.get(normalized)
    if effect == "healing" and target_text and _match_character(runtime.campaign, target_text) is None:
        return "The healing has no valid target."
    if effect in {"sacred_flame", "spell_attack", "auto_damage"} and _active_combatant(runtime.campaign.active_combat or {}, target_text) is None:
        return "The spell has no valid target."
    if effect == "area_save_damage" and not _living_hostile_combatants(runtime.campaign.active_combat or {}, runtime.campaign, None):
        return "The spell has no valid targets."
    return ""


def _apply_sacred_flame(runtime: AdventureRuntime, caster: Character, target_text: str) -> str:
    return _apply_save_damage_spell(runtime, caster, "sacred flame", target_text)


def _apply_spell_attack_spell(runtime: AdventureRuntime, caster: Character, spell_name: str, target_text: str) -> str:
    combat = runtime.campaign.active_combat
    if combat is None:
        return "The spell has no active combat target."
    target = _active_combatant(combat, target_text)
    if target is None:
        return "The spell has no valid target."
    spell = ATTACK_SPELLS[spell_name]
    mode = _attack_mode(runtime.campaign, {"name": caster.name}, target)
    attack = roll_attack(
        attack_bonus=caster.spell_attack_modifier or 0,
        target_ac=target.get("armor_class", 10),
        damage_expression=str(spell["damage"]),
        mode=mode,
        rng=runtime.rng,
    )
    if attack.hit and attack.damage is not None:
        before = target.get("current_hp", 0)
        damage_type = str(spell["damage_type"])
        was_unconscious = _is_unconscious_character(runtime.campaign, target)
        damage_amount = _apply_combat_damage(runtime.campaign, target, attack.damage.total, damage_type)
        concentration = _concentration_check_text(runtime, target, damage_amount)
        text = (
            f"{spell_name.title()} spell attack {attack.attack.total} vs AC {target.get('armor_class')} ({mode.value}), "
            f"hit for {damage_amount} {damage_type} damage: HP {before} -> {target['current_hp']}."
        )
        death_saves = _death_save_damage_text(runtime, target, damage_amount, was_unconscious)
        for extra in (concentration, death_saves):
            if extra:
                text += " " + extra
        return text
    return f"{spell_name.title()} spell attack {attack.attack.total} vs AC {target.get('armor_class')} ({mode.value}), miss."


def _apply_auto_damage_spell(runtime: AdventureRuntime, spell_name: str, target_text: str) -> str:
    combat = runtime.campaign.active_combat
    if combat is None:
        return "The spell has no active combat target."
    target = _active_combatant(combat, target_text)
    if target is None:
        return "The spell has no valid target."
    spell = AUTO_DAMAGE_SPELLS[spell_name]
    missiles = int(spell["missiles"])
    damage_rolls = [roll_damage(str(spell["damage"]), runtime.rng) for _ in range(missiles)]
    raw_damage = sum(roll.total for roll in damage_rolls)
    damage_type = str(spell["damage_type"])
    before = target.get("current_hp", 0)
    was_unconscious = _is_unconscious_character(runtime.campaign, target)
    damage_amount = _apply_combat_damage(runtime.campaign, target, raw_damage, damage_type)
    text = (
        f"{spell_name.title()} hits {target['name']} with {missiles} missile(s) "
        f"for {damage_amount} {damage_type} damage: HP {before} -> {target['current_hp']}."
    )
    concentration = _concentration_check_text(runtime, target, damage_amount)
    death_saves = _death_save_damage_text(runtime, target, damage_amount, was_unconscious)
    for extra in (concentration, death_saves):
        if extra:
            text += " " + extra
    return text


def _apply_save_damage_spell(runtime: AdventureRuntime, caster: Character, spell_name: str, target_text: str) -> str:
    combat = runtime.campaign.active_combat
    if combat is None:
        return "The spell has no active combat target."
    target = _active_combatant(combat, target_text)
    if target is None:
        return "The spell has no valid target."

    spell = SAVE_DAMAGE_SPELLS[spell_name]
    ability = str(spell["ability"])
    dc = caster.spell_save_dc or 10
    modifier = _saving_throw_modifier(runtime.campaign, target["name"], ability)
    mode = _saving_throw_mode(runtime.campaign, target, ability)
    save = roll_d20_check(modifier=modifier, dc=dc, mode=mode, rng=runtime.rng)
    outcome = "success" if save.success else "failure"
    label = str(spell["label"])
    if save.success:
        return f"{target['name']} makes a {label} save {save.total} vs DC {dc} ({outcome}, {mode.value}) and takes no damage."

    damage = roll_damage(str(spell["damage"]), runtime.rng)
    before = target.get("current_hp", 0)
    damage_type = str(spell["damage_type"])
    was_unconscious = _is_unconscious_character(runtime.campaign, target)
    damage_amount = _apply_combat_damage(runtime.campaign, target, damage.total, damage_type)
    concentration = _concentration_check_text(runtime, target, damage_amount)
    text = (
        f"{target['name']} makes a {label} save {save.total} vs DC {dc} ({outcome}, {mode.value}) "
        f"and takes {damage_amount} {damage_type} damage: HP {before} -> {target['current_hp']}."
    )
    death_saves = _death_save_damage_text(runtime, target, damage_amount, was_unconscious)
    for extra in (concentration, death_saves):
        if extra:
            text += " " + extra
    return text


def _apply_area_save_damage_spell(runtime: AdventureRuntime, caster: Character, spell_name: str) -> str:
    combat = runtime.campaign.active_combat
    if combat is None:
        return "The spell has no active combat targets."
    targets = _living_hostile_combatants(combat, runtime.campaign, caster.name)
    if not targets:
        return "The spell has no valid targets."

    spell = AREA_SAVE_DAMAGE_SPELLS[spell_name]
    ability = str(spell["ability"])
    dc = caster.spell_save_dc or 10
    label = str(spell["label"])
    damage = roll_damage(str(spell["damage"]), runtime.rng)
    damage_type = str(spell["damage_type"])
    results: list[str] = []
    for target in targets:
        modifier = _saving_throw_modifier(runtime.campaign, target["name"], ability)
        mode = _saving_throw_mode(runtime.campaign, target, ability)
        save = roll_d20_check(modifier=modifier, dc=dc, mode=mode, rng=runtime.rng)
        outcome = "success" if save.success else "failure"
        raw_damage = damage.total // 2 if save.success else damage.total
        before = target.get("current_hp", 0)
        was_unconscious = _is_unconscious_character(runtime.campaign, target)
        damage_amount = _apply_combat_damage(runtime.campaign, target, raw_damage, damage_type)
        text = (
            f"{target['name']} makes a {label} save {save.total} vs DC {dc} ({outcome}, {mode.value}) "
            f"and takes {damage_amount} {damage_type} damage: HP {before} -> {target['current_hp']}."
        )
        concentration = _concentration_check_text(runtime, target, damage_amount)
        death_saves = _death_save_damage_text(runtime, target, damage_amount, was_unconscious)
        for extra in (concentration, death_saves):
            if extra:
                text += " " + extra
        results.append(text)
    return f"{spell_name.title()} hits {len(results)} hostile target(s). " + " ".join(results)


def _saving_throw_modifier(campaign: Campaign, name: str, ability: str) -> int:
    character = campaign.characters.get(name)
    if character is not None:
        return character.saving_throw_modifier(ability)
    for encounter in campaign.encounters.values():
        for monster in encounter.monsters:
            if monster.name == name:
                return monster.saving_throw_modifier(ability)
    return 0


def _athletics_modifier(campaign: Campaign, name: str) -> int:
    character = _match_character(campaign, name)
    if character is not None:
        return character.skill_modifier("athletics")
    monster = _match_monster(campaign, name)
    if monster is not None:
        return monster.ability_modifier("str") + monster.proficiency_bonus
    return _ability_modifier_from_combatant(campaign.active_combat or {}, name, "str")


def _acrobatics_modifier(campaign: Campaign, name: str) -> int:
    character = _match_character(campaign, name)
    if character is not None:
        return character.skill_modifier("acrobatics")
    monster = _match_monster(campaign, name)
    if monster is not None:
        return monster.ability_modifier("dex")
    return _ability_modifier_from_combatant(campaign.active_combat or {}, name, "dex")


def _match_monster(campaign: Campaign, name: str):
    normalized = name.strip().lower()
    for encounter in campaign.encounters.values():
        for monster in encounter.monsters:
            monster_name = monster.name.lower()
            if normalized == monster_name or normalized in monster_name:
                return monster
    return None


def _ability_modifier_from_combatant(combat: dict, name: str, ability: str) -> int:
    combatant = _active_combatant(combat, name)
    if combatant is None:
        return 0
    scores = combatant.get("ability_scores", {})
    if not isinstance(scores, dict):
        return 0
    try:
        return ability_modifier(int(scores.get(ability, 10)))
    except (TypeError, ValueError):
        return 0


def _attack_mode(campaign: Campaign, attacker: dict, defender: dict) -> RollMode:
    advantage = False
    disadvantage = False
    attacker_conditions = _combatant_condition_names(campaign, attacker)
    defender_conditions = _combatant_condition_names(campaign, defender)
    if attacker_conditions & {"blinded", "frightened", "poisoned", "prone", "restrained"}:
        disadvantage = True
    if defender_conditions & {"blinded", "prone", "restrained", "stunned", "unconscious"}:
        advantage = True
    if "dodging" in defender_conditions:
        disadvantage = True
    return _combined_roll_mode(advantage, disadvantage)


def _saving_throw_mode(campaign: Campaign, combatant: dict, ability: str) -> RollMode:
    conditions = _combatant_condition_names(campaign, combatant)
    if ability == "dex" and conditions & {"restrained", "stunned", "unconscious"}:
        return RollMode.DISADVANTAGE
    return RollMode.NORMAL


def _combined_roll_mode(advantage: bool, disadvantage: bool) -> RollMode:
    if advantage and not disadvantage:
        return RollMode.ADVANTAGE
    if disadvantage and not advantage:
        return RollMode.DISADVANTAGE
    return RollMode.NORMAL


def _combatant_condition_names(campaign: Campaign, combatant: dict) -> set[str]:
    if not combatant:
        return set()
    conditions = {str(condition).lower() for condition in combatant.get("conditions", [])}
    character = campaign.characters.get(str(combatant.get("name") or ""))
    if character is not None:
        conditions.update(condition.lower() for condition in character.conditions)
    return conditions


def _combatant_action_block_reason(campaign: Campaign, combatant: dict | None) -> str:
    if combatant is None:
        return ""
    conditions = _combatant_condition_names(campaign, combatant)
    for condition in ("dead", "unconscious", "stunned", "incapacitated"):
        if condition in conditions:
            return condition
    return ""


def _set_combatant_condition(
    campaign: Campaign, combatant: dict, condition: str, enabled: bool, persist_character: bool
) -> None:
    conditions = {str(item).lower() for item in combatant.get("conditions", [])}
    if enabled:
        conditions.add(condition)
    else:
        conditions.discard(condition)
    combatant["conditions"] = sorted(conditions)
    if persist_character:
        character = campaign.characters.get(str(combatant.get("name") or ""))
        if character is not None:
            if enabled:
                character.conditions.add(condition)
            else:
                character.conditions.discard(condition)


def _try_apply_shield_reaction(
    runtime: AdventureRuntime, defender: dict, attack_total: int, base_ac: int, natural_20: bool
) -> str:
    if natural_20 or attack_total >= base_ac + SHIELD_AC_BONUS:
        return ""
    if _combatant_action_block_reason(runtime.campaign, defender):
        return ""
    character = runtime.campaign.characters.get(defender["name"])
    if character is None or character.spellcasting is None:
        return ""
    try:
        spell = character.spellcasting.spell_named("Shield")
    except ValueError:
        return ""
    if spell.level != 1:
        return ""
    resources = _active_resources(runtime.campaign.active_combat or {}).setdefault(character.name, _default_turn_resources())
    if not resources.get("reaction", True):
        return ""
    try:
        character.spellcasting.expend_slot(1)
    except ValueError:
        return ""
    resources["reaction"] = False
    return f"{character.name} casts Shield as a reaction, raising AC to {base_ac + SHIELD_AC_BONUS}."


def _concentration_check_text(runtime: AdventureRuntime, combatant: dict, damage_amount: int) -> str:
    if damage_amount <= 0:
        return ""
    character = runtime.campaign.characters.get(combatant["name"])
    if character is None or character.spellcasting is None or character.spellcasting.concentration_spell_name is None:
        return ""
    dc = max(10, damage_amount // 2)
    modifier = character.saving_throw_modifier("con")
    result = roll_d20_check(modifier=modifier, dc=dc, rng=runtime.rng)
    outcome = "success" if result.success else "failure"
    text = f"Concentration check: {character.name} rolls CON save {result.total} vs DC {dc} ({outcome})."
    if not result.success:
        spell_name = character.spellcasting.concentration_spell_name
        character.spellcasting.concentration_spell_name = None
        text += f" Concentration on {spell_name} ends."
    return text


def _death_save_damage_text(
    runtime: AdventureRuntime, combatant: dict, damage_amount: int, was_unconscious: bool
) -> str:
    if damage_amount <= 0 or not was_unconscious:
        return ""
    character = runtime.campaign.characters.get(combatant["name"])
    if character is None or character.current_hp > 0 or "unconscious" not in character.conditions:
        return ""
    text = f"{character.name} takes damage while unconscious: 1 death save failure ({character.death_save_failures}/3)."
    if "dead" in character.conditions:
        text += " They die."
    return text


def _add_death_save_failure(character: Character, amount: int) -> None:
    character.death_save_failures = min(3, character.death_save_failures + amount)
    character.conditions.discard("stable")
    if character.death_save_failures >= 3:
        character.conditions.add("dead")


def _stabilize(character: Character) -> None:
    character.death_save_successes = 0
    character.death_save_failures = 0
    if character.current_hp == 0:
        character.conditions.add("unconscious")
    character.conditions.add("stable")


def _signed_expression(base: str, modifier: int) -> str:
    if modifier > 0:
        return f"{base}+{modifier}"
    if modifier < 0:
        return f"{base}{modifier}"
    return base


def _match_character(campaign: Campaign, target: str) -> Character | None:
    normalized = target.strip().lower()
    if not normalized and len(campaign.characters) == 1:
        return next(iter(campaign.characters.values()))
    for character in campaign.characters.values():
        name = character.name.lower()
        if normalized == name or normalized in name:
            return character
    return None


def _sync_combatant_hp(combat: dict | None, name: str, hp: int) -> None:
    if combat is None:
        return
    combatant = _active_combatant(combat, name)
    if combatant is not None:
        combatant["current_hp"] = hp


def _reset_turn_resources(combat: dict, name: str) -> None:
    resources = _active_resources(combat).setdefault(name, _default_turn_resources())
    resources["action"] = True
    resources["bonus_action"] = True
    resources["movement"] = DEFAULT_RULES_CONFIG.default_movement_speed
    resources.pop("provoked_opportunity_attack", None)
    combatant = _active_combatant(combat, name)
    if combatant is not None:
        conditions = {str(item).lower() for item in combatant.get("conditions", [])}
        conditions -= TEMPORARY_COMBAT_CONDITIONS
        combatant["conditions"] = sorted(conditions)


def _next_active_combatant_index(combat: dict, current_index: int) -> int | None:
    initiative = combat.get("initiative", [])
    if not initiative:
        return None
    index = current_index
    wrapped = False
    for _ in range(len(initiative)):
        index += 1
        if index >= len(initiative):
            index = 0
            wrapped = True
        if _combatant_can_take_turn(initiative[index]):
            if wrapped:
                combat["round"] = combat.get("round", 1) + 1
                for resources in _active_resources(combat).values():
                    resources["reaction"] = True
            return index
    return None


def _combatant_can_take_turn(combatant: dict) -> bool:
    if "current_hp" not in combatant:
        return True
    return int(combatant.get("current_hp") or 0) > 0


def _attack_profile(encounter: Encounter, name: str) -> dict:
    for monster in encounter.monsters:
        if monster.name == name:
            return {
                "attack_bonus": monster.attack_bonus,
                "damage": monster.damage,
                "damage_type": monster.damage_type,
                "action_strategy": monster.action_strategy,
            }
    return {"attack_bonus": 0, "damage": "1d4", "damage_type": "untyped", "action_strategy": "default_attack"}


def _defense_profile(encounter: Encounter, name: str) -> dict:
    for monster in encounter.monsters:
        if monster.name == name:
            return {
                "damage_resistances": sorted(monster.damage_resistances),
                "damage_vulnerabilities": sorted(monster.damage_vulnerabilities),
                "damage_immunities": sorted(monster.damage_immunities),
            }
    return {"damage_resistances": [], "damage_vulnerabilities": [], "damage_immunities": []}


def _active_combatant(combat: dict, name: str) -> dict | None:
    normalized = name.strip().lower()
    if not normalized:
        return None
    for combatant in combat.get("initiative", []):
        combatant_name = combatant["name"].lower()
        if normalized == combatant_name or normalized in combatant_name:
            return combatant
    return None


def _living_hostile_combatants(combat: dict, campaign: Campaign, actor_name: str | None) -> list[dict]:
    initiative = combat.get("initiative", [])
    actor = _active_combatant(combat, actor_name or combat.get("turn", ""))
    if actor is None:
        actor = next((entry for entry in initiative if entry.get("name") == combat.get("turn")), None)
    if actor is None or "is_player" not in actor:
        return []
    actor_side = bool(actor.get("is_player"))
    return [
        entry
        for entry in initiative
        if entry.get("name")
        and bool(entry.get("is_player")) != actor_side
        and int(entry.get("current_hp") or 0) > 0
        and not _character_has_condition(campaign, str(entry.get("name")), "dead")
    ]


def _character_has_condition(campaign: Campaign, name: str, condition: str) -> bool:
    character = campaign.characters.get(name)
    return bool(character is not None and condition in character.conditions)


def _character_is_concentrating(campaign: Campaign, name: str) -> bool:
    character = campaign.characters.get(name)
    return bool(
        character is not None
        and character.spellcasting is not None
        and character.spellcasting.concentration_spell_name is not None
    )


def _apply_combat_damage(campaign: Campaign, combatant: dict, amount: int, damage_type: str | None) -> int:
    character = campaign.characters.get(combatant["name"])
    if character is not None:
        was_unconscious = character.is_unconscious
        adjusted = character.apply_damage(amount, damage_type)
        if was_unconscious and adjusted > 0 and character.current_hp == 0 and "dead" not in character.conditions:
            _add_death_save_failure(character, 1)
        combatant["current_hp"] = character.current_hp
        return adjusted

    for encounter in campaign.encounters.values():
        for monster in encounter.monsters:
            if monster.name == combatant["name"]:
                adjusted = adjusted_damage_amount(
                    amount,
                    damage_type,
                    monster.damage_immunities,
                    monster.damage_resistances,
                    monster.damage_vulnerabilities,
                )
                monster.current_hp = max(0, monster.current_hp - adjusted)
                combatant["current_hp"] = monster.current_hp
                return adjusted

    adjusted = adjusted_damage_amount(
        amount,
        damage_type,
        set(combatant.get("damage_immunities", [])),
        set(combatant.get("damage_resistances", [])),
        set(combatant.get("damage_vulnerabilities", [])),
    )
    combatant["current_hp"] = max(0, combatant.get("current_hp", 0) - adjusted)
    return adjusted


def _is_unconscious_character(campaign: Campaign, combatant: dict) -> bool:
    character = campaign.characters.get(combatant["name"])
    return bool(character is not None and character.is_unconscious and "dead" not in character.conditions)


def _all_hostile_combatants_defeated(combat: dict) -> bool:
    hostiles = [entry for entry in combat.get("initiative", []) if entry.get("is_player") is False]
    return bool(hostiles) and all(entry.get("current_hp", 0) <= 0 for entry in hostiles)


def _all_player_combatants_defeated(combat: dict) -> bool:
    players = [entry for entry in combat.get("initiative", []) if entry.get("is_player") is True]
    return bool(players) and all(entry.get("current_hp", 0) <= 0 for entry in players)


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


def _runtime_actions(campaign: Campaign) -> dict[str, dict]:
    if not campaign.runtime_actions:
        return DEFAULT_RUNTIME_ACTIONS
    merged = dict(DEFAULT_RUNTIME_ACTIONS)
    merged.update(campaign.runtime_actions)
    return merged


def _runtime_action_names(campaign: Campaign) -> list[str]:
    return sorted(_runtime_actions(campaign))


def _match_runtime_action(campaign: Campaign, normalized: str) -> dict:
    for action_name, action in _runtime_actions(campaign).items():
        handler = action.get("handler", action_name)
        aliases = action.get("aliases", [action_name])
        for alias in aliases:
            alias_text = str(alias).strip().lower()
            if not alias_text:
                continue
            if handler in {
                "move",
                "talk",
                "inspect",
                "complete_quest",
                "fail_quest",
                "spend_movement",
                "attack",
                "cast_spell",
                "death_save",
                "stabilize",
                "grapple",
                "shove",
                "set_condition",
                "clear_condition",
            } and normalized.startswith(alias_text + " "):
                return {"name": action_name, "handler": handler, "argument": normalized[len(alias_text) :].strip()}
            if normalized == alias_text:
                return {"name": action_name, "handler": handler}
    return {"name": "", "handler": ""}
