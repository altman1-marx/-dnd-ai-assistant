from __future__ import annotations

import random
from dataclasses import dataclass, field

from .core.combat import ActionResource, CombatState, action_resource_for_spell
from .core.campaign import Campaign, Encounter, Location, NPC, Clue, SessionEvent
from .core.character import Character
from .core.config import DEFAULT_RULES_CONFIG
from .core.damage import adjusted_damage_amount
from .core.dnd5e import RollMode, roll_attack, roll_d20_check, roll_damage
from .core.initiative import Combatant
from .core.skills import skill_label
from .core.spells import Spell


QUEST_COMPLETE_STATUS = "completed"
QUEST_FAILED_STATUS = "failed"


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
    "spend_movement": {"aliases": ["spend movement", "use movement"], "handler": "spend_movement"},
    "attack": {"aliases": ["attack", "strike"], "handler": "attack"},
    "cast_spell": {"aliases": ["cast", "cast spell"], "handler": "cast_spell"},
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
    if handler == "spend_movement":
        spend_active_combat_movement(runtime, action_match.get("argument", ""))
        return True
    if handler == "attack":
        attack_active_combat_target(runtime, action_match.get("argument", ""))
        return True
    if handler == "cast_spell":
        cast_active_combat_spell(runtime, action_match.get("argument", ""))
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
    next_index = current_index + 1
    if next_index >= len(initiative):
        next_index = 0
        combat["round"] = combat.get("round", 1) + 1
        for resources in _active_resources(combat).values():
            resources["reaction"] = True
    combat["turn"] = initiative[next_index]["name"]
    _reset_turn_resources(combat, combat["turn"])
    runtime.campaign.record_event(
        SessionEvent(actor="DM", content=f"Combat advanced to round {combat['round']}: {combat['turn']}.")
    )
    runtime.narrate(f"DM: Combat advances to round {combat['round']}, turn: {combat['turn']}.")


def spend_active_combat_resource(runtime: AdventureRuntime, resource: str) -> None:
    combat = runtime.campaign.active_combat
    if combat is None:
        runtime.narrate("DM: There is no active combat.")
        return
    turn = combat.get("turn")
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
    resources = _active_resources(combat).setdefault(turn, _default_turn_resources())
    remaining = resources.get("movement", DEFAULT_RULES_CONFIG.default_movement_speed)
    if amount > remaining:
        runtime.narrate("DM: Not enough movement remaining.")
        return
    resources["movement"] = remaining - amount
    runtime.campaign.record_event(SessionEvent(actor="DM", content=f"{turn} moved {amount} feet."))
    runtime.narrate(f"DM: {turn} moves {amount} feet, {resources['movement']} feet remaining.")


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
    if attacker["name"] == defender["name"]:
        runtime.narrate("DM: A combatant cannot attack itself.")
        return
    if not _active_resources(combat).setdefault(attacker["name"], _default_turn_resources()).get("action", True):
        runtime.narrate(f"DM: {attacker['name']} has already used action.")
        return

    attack = roll_attack(
        attack_bonus=attacker.get("attack_bonus", 0),
        target_ac=defender.get("armor_class", 10),
        damage_expression=attacker.get("damage", "1d4"),
        rng=runtime.rng,
    )
    _active_resources(combat)[attacker["name"]]["action"] = False
    if attack.hit and attack.damage is not None:
        before = defender.get("current_hp", 0)
        damage_type = attacker.get("damage_type", "untyped")
        damage_amount = _apply_combat_damage(runtime.campaign, defender, attack.damage.total, damage_type)
        adjustment = ""
        if damage_amount != attack.damage.total:
            adjustment = f" ({attack.damage.total} before adjustments)"
        content = (
            f"{attacker['name']} attacks {defender['name']}: {attack.attack.total} vs AC {defender.get('armor_class')}, "
            f"hit for {damage_amount} {damage_type} damage{adjustment}: HP {before} -> {defender['current_hp']}."
        )
    else:
        content = f"{attacker['name']} attacks {defender['name']}: {attack.attack.total} vs AC {defender.get('armor_class')}, miss."
    runtime.campaign.record_event(SessionEvent(actor="DM", content=content))
    runtime.narrate(f"DM: {content}")
    if attack.hit and _all_hostile_combatants_defeated(combat):
        _finish_active_encounter(runtime, "All hostile combatants are defeated.")


def cast_active_combat_spell(runtime: AdventureRuntime, spell_text: str) -> None:
    combat = runtime.campaign.active_combat
    if combat is None:
        runtime.narrate("DM: There is no active combat.")
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
    runtime.campaign.record_event(SessionEvent(actor="DM", content=content))
    runtime.narrate(f"DM: {content}")


def resolve_active_encounter(runtime: AdventureRuntime) -> bool:
    combat = runtime.campaign.active_combat
    if combat is None:
        runtime.narrate("DM: There is no active encounter to resolve.")
        return True
    _finish_active_encounter(runtime, "Encounter resolved manually.")
    return True


def _finish_active_encounter(runtime: AdventureRuntime, reason: str) -> None:
    combat = runtime.campaign.active_combat
    if combat is None:
        return
    encounter_id = combat.get("encounter_id")
    encounter = runtime.campaign.encounters.get(encounter_id)
    if encounter is not None:
        encounter.resolved = True
        content = f"Encounter resolved: {encounter.title}. {reason}"
        if encounter.reward:
            content += f" Reward: {encounter.reward}"
    else:
        content = f"Encounter resolved: {encounter_id}. {reason}"
    runtime.campaign.active_combat = None
    runtime.campaign.record_event(SessionEvent(actor="DM", content=content))
    runtime.narrate(f"DM: {content}")


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


def _apply_spell_effect(
    runtime: AdventureRuntime,
    caster: Character,
    spell_name: str,
    slot_level: int | None,
    target_text: str,
) -> str:
    normalized = spell_name.strip().lower()
    if normalized not in {"cure wounds", "healing word"}:
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


def _attack_profile(encounter: Encounter, name: str) -> dict:
    for monster in encounter.monsters:
        if monster.name == name:
            return {"attack_bonus": monster.attack_bonus, "damage": monster.damage, "damage_type": monster.damage_type}
    return {"attack_bonus": 0, "damage": "1d4", "damage_type": "untyped"}


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
    for combatant in combat.get("initiative", []):
        combatant_name = combatant["name"].lower()
        if normalized == combatant_name or normalized in combatant_name:
            return combatant
    return None


def _apply_combat_damage(campaign: Campaign, combatant: dict, amount: int, damage_type: str | None) -> int:
    character = campaign.characters.get(combatant["name"])
    if character is not None:
        adjusted = character.apply_damage(amount, damage_type)
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


def _all_hostile_combatants_defeated(combat: dict) -> bool:
    hostiles = [entry for entry in combat.get("initiative", []) if entry.get("is_player") is False]
    return bool(hostiles) and all(entry.get("current_hp", 0) <= 0 for entry in hostiles)


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
    return campaign.runtime_actions or DEFAULT_RUNTIME_ACTIONS


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
            } and normalized.startswith(alias_text + " "):
                return {"name": action_name, "handler": handler, "argument": normalized[len(alias_text) :].strip()}
            if normalized == alias_text:
                return {"name": action_name, "handler": handler}
    return {"name": "", "handler": ""}
