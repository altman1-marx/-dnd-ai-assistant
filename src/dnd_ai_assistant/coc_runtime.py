from __future__ import annotations

import random
from dataclasses import dataclass, field
from uuid import uuid4

from .core.coc7e import Investigator, PercentileRollMode, roll_percentile_check


@dataclass
class COCClue:
    id: str
    title: str
    text: str
    location_id: str | None = None
    evidence: str | None = None
    skill: str | None = None
    difficulty: str = "regular"
    sanity_loss: int = 0
    failure_text: str | None = None
    failure_evidence: str | None = None
    failure_sanity_loss: int = 0
    discovered: bool = False
    partial_discovered: bool = False
    push_attempted: bool = False
    last_check_total: int | None = None
    last_required_total: int | None = None
    last_check_level: str | None = None


@dataclass
class COCLocation:
    id: str
    name: str
    description: str
    exits: dict[str, str] = field(default_factory=dict)
    exit_requirements: dict[str, dict] = field(default_factory=dict)


@dataclass
class COCNPC:
    id: str
    name: str
    description: str
    location_id: str | None = None
    dialogue: list[str] = field(default_factory=list)


@dataclass
class COCScenario:
    title: str
    location: str
    description: str
    investigator: Investigator
    clues: list[COCClue] = field(default_factory=list)
    npcs: list[COCNPC] = field(default_factory=list)
    locations: dict[str, COCLocation] = field(default_factory=dict)
    current_location_id: str | None = None
    inventory: list[str] = field(default_factory=list)
    completion_requirements: dict[str, list[str]] = field(default_factory=dict)
    talked_npc_ids: set[str] = field(default_factory=set)
    ending_text: str = ""
    completed: bool = False
    session_log: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: f"coc_{uuid4().hex[:12]}")

    def current_location(self) -> COCLocation:
        if self.current_location_id and self.current_location_id in self.locations:
            return self.locations[self.current_location_id]
        return COCLocation(id="legacy", name=self.location, description=self.description)


@dataclass
class COCRuntime:
    scenario: COCScenario
    transcript: list[str] = field(default_factory=list)
    rng: random.Random = field(default_factory=random.Random)

    def narrate(self, line: str) -> None:
        self.transcript.append(line)
        self.scenario.session_log.append(line)

    def flush(self) -> str:
        output = "\n".join(self.transcript)
        self.transcript.clear()
        return output


def create_sample_coc_scenario() -> COCScenario:
    investigator = Investigator(
        name="Eleanor Vale",
        occupation="Antiquarian",
        characteristics={"str": 45, "con": 55, "siz": 60, "dex": 50, "app": 55, "int": 70, "pow": 60, "edu": 75},
        skills={"library use": 55, "spot hidden": 45, "occult": 40, "psychology": 35, "first aid": 50},
        luck=50,
    )
    locations = {
        "study": COCLocation(
            id="study",
            name="Briar House Study",
            description=(
                "Rain presses against the study windows. A locked writing desk, a soot-stained "
                "hearth, and a portrait with scratched-out eyes wait in the lamplight."
            ),
            exits={"cellar": "cellar", "garden": "garden"},
            exit_requirements={
                "cellar": {
                    "required_clue_ids": ["portrait_truth"],
                    "required_evidence": ["Torn portrait canvas"],
                    "message": "The portrait passage is still hidden; the cellar route is not clear yet.",
                }
            },
        ),
        "cellar": COCLocation(
            id="cellar",
            name="Briar House Cellar",
            description="Wet stone steps descend to a cramped cellar where a brass lantern hangs cold and unlit.",
            exits={"study": "study", "garden": "garden"},
        ),
        "garden": COCLocation(
            id="garden",
            name="Rain-Drowned Garden",
            description=(
                "The rear garden is flooded ankle-deep. Bell-shaped flowers lean toward the house, "
                "and a rain gauge ticks like a metronome beside an old well."
            ),
            exits={"study": "study", "cellar": "cellar"},
        ),
    }
    return COCScenario(
        title="The Lantern Under Briar House",
        location="Briar House Study",
        description=locations["study"].description,
        investigator=investigator,
        clues=[
            COCClue(
                id="desk_journal",
                title="Waterlogged Journal",
                text="The journal names a lantern buried under the house and repeats the phrase 'do not trim the wick'.",
                location_id="study",
                evidence="Waterlogged journal",
                skill="library use",
                difficulty="regular",
                failure_text="The journal pages are waterlogged, but a repeated lighthouse sketch stands out.",
                failure_evidence="Watermarked lighthouse sketch",
            ),
            COCClue(
                id="hearth_symbol",
                title="Ashen Spiral",
                text="The ash forms a spiral that seems to bend toward your hand. The shape is older than the house.",
                location_id="study",
                evidence="Ash rubbing",
                skill="spot hidden",
                difficulty="hard",
                sanity_loss=1,
                failure_text="The spiral points toward the scratched portrait, but its full meaning remains unclear.",
                failure_evidence="Charcoal spiral rubbing",
            ),
            COCClue(
                id="portrait_truth",
                title="Scratched Portrait",
                text="Behind the torn canvas is a narrow crawlspace descending into wet stone.",
                location_id="study",
                evidence="Torn portrait canvas",
                skill=None,
                sanity_loss=2,
            ),
            COCClue(
                id="rain_gauge",
                title="Backward Rain Gauge",
                text="The rain gauge has been filling upward from below. Its markings match the spiral in the hearth ash.",
                location_id="garden",
                evidence="Backward rain gauge sketch",
                skill="spot hidden",
                difficulty="regular",
                failure_text="The gauge is wrong in a way that points back toward the hearth spiral.",
                failure_evidence="Mud-smeared gauge note",
            ),
            COCClue(
                id="well_whispers",
                title="Voices in the Well",
                text="A voice under the well repeats Mrs. Ember's warning in Mr. Briar's cadence.",
                location_id="garden",
                evidence="Recorded well whisper",
                skill="psychology",
                difficulty="hard",
                sanity_loss=1,
                failure_text="The cadence is familiar, but fear makes the words hard to place.",
                failure_evidence="Shaken witness impression",
                failure_sanity_loss=1,
            ),
            COCClue(
                id="lantern_wick",
                title="Black Wick",
                text="The lantern wick is braided from black hair and sea grass. It twitches when named.",
                location_id="cellar",
                evidence="Black wick sample",
                skill=None,
                sanity_loss=2,
            ),
        ],
        npcs=[
            COCNPC(
                id="mrs_ember",
                name="Mrs. Ember",
                description="The housekeeper waits by the study door, twisting a ring of old keys.",
                location_id="study",
                dialogue=[
                    "Mr. Briar forbade us from trimming the lantern wick.",
                    "The cellar door swells shut when the rain is heavy, but the portrait passage still breathes.",
                ],
            ),
            COCNPC(
                id="constable_hale",
                name="Constable Hale",
                description="A soaked constable guards the garden path and refuses to look directly into the well.",
                location_id="garden",
                dialogue=[
                    "I heard the bell below the soil, not above it.",
                    "The rain gauge was empty at dusk and overflowing by midnight, but the sky never changed.",
                ],
            ),
        ],
        locations=locations,
        current_location_id="study",
        completion_requirements={
            "required_clue_ids": ["portrait_truth", "lantern_wick"],
            "required_evidence": ["Black wick sample"],
            "required_location_ids": ["cellar"],
        },
        ending_text=("With enough clues gathered, the cellar route is clear. The lantern waits below, "
                     "and the house exhales as if something has chosen to sleep again."),
    )


def describe_coc_scene(runtime: COCRuntime) -> None:
    scenario = runtime.scenario
    investigator = scenario.investigator
    location = scenario.current_location()
    runtime.narrate(f"Keeper: {scenario.title}")
    runtime.narrate(f"Keeper: {location.name}")
    runtime.narrate(f"Keeper: {location.description}")
    if location.exits:
        runtime.narrate(f"Keeper: Exits: {', '.join(sorted(location.exits))}.")
    npcs = _visible_npcs(scenario)
    if npcs:
        runtime.narrate(f"Keeper: Present: {', '.join(npc.name for npc in npcs)}.")
    runtime.narrate(
        f"Keeper: Investigator: {investigator.name}, HP {investigator.current_hp}/{investigator.max_hp}, "
        f"SAN {investigator.current_sanity}/{investigator.max_sanity}, Luck {investigator.luck}."
    )


def handle_coc_action(runtime: COCRuntime, action: str) -> bool:
    normalized = action.strip().lower()
    if not normalized:
        return True
    runtime.narrate(f"Player: {action}")
    if normalized in {"quit", "exit"}:
        runtime.narrate("Keeper: The investigation pauses here.")
        return False
    if normalized in {"help", "?"}:
        runtime.narrate(
            "Keeper: Actions: look, status, recap, progress, hint, note <text>, keeper note <text>, go <exit>, inspect/search/read/listen/examine <target>, talk <npc>, check <skill>, push <target>, spend luck <target>, first aid, conclude, sanity, clues, inventory, quit."
        )
        return True
    if normalized in {"recap", "summary"}:
        _describe_coc_recap(runtime)
        return True
    if normalized in {"hint", "nudge"}:
        _describe_keeper_hint(runtime)
        return True
    if normalized in {"progress", "ending"}:
        _describe_completion_progress(runtime)
        return True
    if normalized in {"conclude", "solve", "solve case", "close case"}:
        _conclude_coc_scenario(runtime)
        return True
    if normalized == "status":
        _describe_coc_status(runtime)
        return True
    if normalized in {"look", "look around"}:
        describe_coc_scene(runtime)
        return True
    if normalized == "sanity":
        investigator = runtime.scenario.investigator
        runtime.narrate(
            f"Keeper: {investigator.name} has SAN {investigator.current_sanity}/{investigator.max_sanity}; "
            f"conditions: {', '.join(sorted(investigator.conditions)) or 'none'}."
        )
        return True
    if normalized == "clues":
        _describe_discovered_clues(runtime)
        return True
    if normalized in {"inventory", "evidence"}:
        _describe_inventory(runtime)
        return True
    if normalized in {"first aid", "first aid self"}:
        _use_first_aid(runtime)
        return True
    if normalized.startswith("keeper note "):
        _record_coc_note(runtime, action[len("keeper note ") :].strip(), keeper_only=True)
        return True
    if normalized.startswith("note "):
        _record_coc_note(runtime, action[len("note ") :].strip(), keeper_only=False)
        return True
    if normalized.startswith("go "):
        _move_coc_location(runtime, normalized[len("go ") :].strip())
        return True
    inspect_target = _inspection_alias_target(normalized)
    if inspect_target is not None:
        _inspect_coc_target(runtime, inspect_target)
        return True
    if normalized.startswith("push "):
        _push_coc_target(runtime, normalized[len("push ") :].strip())
        return True
    if normalized.startswith("spend luck "):
        _spend_luck_on_coc_target(runtime, normalized[len("spend luck ") :].strip())
        return True
    if normalized.startswith("talk "):
        _talk_to_coc_npc(runtime, normalized[len("talk ") :].strip())
        return True
    if normalized.startswith("check "):
        _manual_coc_check(runtime, normalized[len("check ") :].strip())
        return True
    runtime.narrate("Keeper: That action is not supported yet.")
    return True


def _record_coc_note(runtime: COCRuntime, text: str, keeper_only: bool = False) -> None:
    if not text.strip():
        runtime.narrate("Keeper: Note text cannot be empty.")
        return
    prefix = "Keeper note" if keeper_only else "Player note"
    runtime.narrate(f"{prefix}: {text.strip()}")

def _use_first_aid(runtime: COCRuntime) -> None:
    investigator = runtime.scenario.investigator
    if investigator.current_hp >= investigator.max_hp:
        runtime.narrate(f"Keeper: {investigator.name} does not need first aid right now.")
        return
    value = investigator.skill_value("first aid")
    check = roll_percentile_check(value, rng=runtime.rng)
    runtime.narrate(
        f"Keeper: {investigator.name} rolls first aid {check.total} vs {value}: {check.success_level.value}."
    )
    if not check.success:
        runtime.narrate("Keeper: The wound remains untreated.")
        return
    before = investigator.current_hp
    investigator.heal(1)
    healed = investigator.current_hp - before
    runtime.narrate(f"Keeper: First aid restores {healed} HP; HP {investigator.current_hp}/{investigator.max_hp}.")

def _inspection_alias_target(normalized_action: str) -> str | None:
    for verb in ("listen to", "inspect", "search", "read", "listen", "examine"):
        prefix = f"{verb} "
        if normalized_action.startswith(prefix):
            return normalized_action[len(prefix) :].strip()
    return None


def _inspect_coc_target(runtime: COCRuntime, target: str) -> None:
    clue = _match_clue(_visible_clues(runtime.scenario), target)
    if clue is None:
        runtime.narrate("Keeper: You find no clear lead there.")
        return
    if clue.discovered:
        runtime.narrate(f"Keeper: You have already found {clue.title}: {clue.text}")
        return
    if clue.skill is not None:
        if not _passes_clue_check(runtime, clue):
            _reveal_partial_coc_clue(runtime, clue)
            return
    _reveal_coc_clue(runtime, clue)


def _push_coc_target(runtime: COCRuntime, target: str) -> None:
    clue = _match_clue(_visible_clues(runtime.scenario), target)
    if clue is None:
        runtime.narrate("Keeper: There is no failed lead here to push.")
        return
    if clue.discovered:
        runtime.narrate(f"Keeper: {clue.title} is already fully understood.")
        return
    if not clue.partial_discovered:
        runtime.narrate(f"Keeper: Push {clue.title} only after a failed inspection has exposed a partial lead.")
        return
    if clue.push_attempted:
        runtime.narrate(f"Keeper: {clue.title} has already been pushed; find another angle.")
        return
    clue.push_attempted = True
    if _passes_clue_check(runtime, clue):
        runtime.narrate(f"Keeper: The pushed investigation pays off for {clue.title}.")
        _reveal_coc_clue(runtime, clue)
        return
    runtime.scenario.investigator.lose_sanity(1)
    runtime.scenario.investigator.conditions.add("rattled")
    runtime.narrate(f"Keeper: Push roll fails for {clue.title}; SAN loss 1 and condition rattled.")

def _spend_luck_on_coc_target(runtime: COCRuntime, target: str) -> None:
    clue = _match_clue(_visible_clues(runtime.scenario), target)
    if clue is None:
        runtime.narrate("Keeper: There is no failed lead here to save with Luck.")
        return
    if clue.discovered:
        runtime.narrate(f"Keeper: {clue.title} is already fully understood.")
        return
    if clue.last_check_total is None or clue.last_required_total is None:
        runtime.narrate(f"Keeper: No failed roll for {clue.title} is waiting for Luck spending.")
        return
    if clue.last_check_level == "fumble":
        runtime.narrate(f"Keeper: Luck cannot erase a fumble on {clue.title}.")
        return
    cost = clue.last_check_total - clue.last_required_total
    if cost <= 0:
        runtime.narrate(f"Keeper: {clue.title} does not need Luck spending right now.")
        return
    investigator = runtime.scenario.investigator
    if investigator.luck < cost:
        runtime.narrate(f"Keeper: {investigator.name} needs {cost} Luck for {clue.title}, but has {investigator.luck}.")
        return
    investigator.luck -= cost
    runtime.narrate(f"Keeper: {investigator.name} spends {cost} Luck on {clue.title}; Luck is now {investigator.luck}.")
    _reveal_coc_clue(runtime, clue)


def _manual_coc_check(runtime: COCRuntime, skill_name: str) -> None:
    investigator = runtime.scenario.investigator
    value = investigator.skill_value(skill_name)
    check = roll_percentile_check(value, rng=runtime.rng)
    runtime.narrate(
        f"Keeper: {investigator.name} rolls {skill_name} {check.total} vs {value}: {check.success_level.value}."
    )


def _passes_clue_check(runtime: COCRuntime, clue: COCClue) -> bool:
    investigator = runtime.scenario.investigator
    skill_value = investigator.skill_value(clue.skill or "")
    check = roll_percentile_check(skill_value, mode=PercentileRollMode.NORMAL, rng=runtime.rng)
    required = _required_success_level(clue.difficulty)
    required_total = _required_total_for_success(skill_value, required)
    success = _success_rank(check.success_level.value) >= _success_rank(required)
    clue.last_check_total = check.total
    clue.last_required_total = required_total
    clue.last_check_level = check.success_level.value
    runtime.narrate(
        f"Keeper: {investigator.name} rolls {clue.skill} {check.total} vs {skill_value}: "
        f"{check.success_level.value}; needs {required}."
    )
    return success


def _reveal_partial_coc_clue(runtime: COCRuntime, clue: COCClue) -> None:
    if not clue.failure_text:
        runtime.narrate("Keeper: Something is here, but the pattern does not come together yet.")
        return
    if clue.partial_discovered:
        runtime.narrate(f"Keeper: You have already found the partial lead for {clue.title}: {clue.failure_text}")
        return
    clue.partial_discovered = True
    runtime.narrate(f"Keeper: Partial clue - {clue.title}: {clue.failure_text}")
    if clue.failure_sanity_loss > 0:
        runtime.scenario.investigator.lose_sanity(clue.failure_sanity_loss)
        runtime.narrate(f"Keeper: SAN loss {clue.failure_sanity_loss}.")
    if clue.failure_evidence:
        _add_inventory_item(runtime, clue.failure_evidence)

def _reveal_coc_clue(runtime: COCRuntime, clue: COCClue) -> None:
    clue.discovered = True
    clue.last_check_total = None
    clue.last_required_total = None
    clue.last_check_level = None
    runtime.narrate(f"Keeper: Clue found - {clue.title}: {clue.text}")
    if clue.sanity_loss > 0:
        runtime.scenario.investigator.lose_sanity(clue.sanity_loss)
        runtime.narrate(f"Keeper: SAN loss {clue.sanity_loss}.")
    if clue.evidence:
        _add_inventory_item(runtime, clue.evidence)
    _maybe_complete_scenario(runtime)


def _describe_discovered_clues(runtime: COCRuntime) -> None:
    discovered = [clue for clue in runtime.scenario.clues if clue.discovered]
    partial = [clue for clue in runtime.scenario.clues if clue.partial_discovered and not clue.discovered]
    if not discovered and not partial:
        runtime.narrate("Keeper: No clues discovered yet.")
        return
    for clue in discovered:
        runtime.narrate(f"- {clue.title}: {clue.text}")
    for clue in partial:
        runtime.narrate(f"- Partial lead - {clue.title}: {clue.failure_text or 'Unconfirmed lead.'}")


def _describe_coc_status(runtime: COCRuntime) -> None:
    investigator = runtime.scenario.investigator
    location = runtime.scenario.current_location()
    discovered = sum(1 for clue in runtime.scenario.clues if clue.discovered)
    total = len(runtime.scenario.clues)
    partial = sum(1 for clue in runtime.scenario.clues if clue.partial_discovered and not clue.discovered)
    runtime.narrate(
        f"Keeper: {investigator.name} ({investigator.occupation}) - "
        f"location {location.name}, "
        f"HP {investigator.current_hp}/{investigator.max_hp}, "
        f"MP {investigator.current_mp}/{investigator.max_mp}, "
        f"SAN {investigator.current_sanity}/{investigator.max_sanity}, "
        f"Luck {investigator.luck}, clues {discovered}/{total}, partial {partial}, "
        f"evidence {len(runtime.scenario.inventory)}, "
        f"conditions: {', '.join(sorted(investigator.conditions)) or 'none'}."
    )


def _describe_coc_recap(runtime: COCRuntime) -> None:
    scenario = runtime.scenario
    location = scenario.current_location()
    discovered = [clue for clue in scenario.clues if clue.discovered]
    partial = [clue for clue in scenario.clues if clue.partial_discovered and not clue.discovered]
    evidence = ", ".join(scenario.inventory) if scenario.inventory else "none"
    latest_clue = discovered[-1].title if discovered else "none"
    runtime.narrate(
        f"Keeper: Recap: {scenario.title}; location {location.name}; "
        f"clues {len(discovered)}/{len(scenario.clues)}; partial {len(partial)}; "
        f"latest clue {latest_clue}; evidence {evidence}."
    )
    runtime.narrate(f"Keeper: Next lead: {coc_keeper_hint(scenario)}")

def _describe_completion_progress(runtime: COCRuntime) -> None:
    scenario = runtime.scenario
    requirements = scenario.completion_requirements
    if not requirements:
        discovered = sum(1 for clue in scenario.clues if clue.discovered)
        runtime.narrate(f"Keeper: Ending progress: clues {discovered}/{len(scenario.clues)} discovered.")
        return
    discovered_ids = {clue.id for clue in scenario.clues if clue.discovered}
    inventory = set(scenario.inventory)
    current_locations = {scenario.current_location_id} if scenario.current_location_id else set()
    pieces = [
        _progress_piece("clues", requirements.get("required_clue_ids", []), discovered_ids),
        _progress_piece("evidence", requirements.get("required_evidence", []), inventory),
        _progress_piece("locations", requirements.get("required_location_ids", []), current_locations),
        _progress_piece("NPCs", requirements.get("required_npc_ids", []), scenario.talked_npc_ids),
    ]
    runtime.narrate("Keeper: Ending progress: " + ", ".join(piece for piece in pieces if piece) + ".")


def _conclude_coc_scenario(runtime: COCRuntime) -> None:
    scenario = runtime.scenario
    if scenario.completed:
        runtime.narrate("Keeper: The case is already concluded.")
        if scenario.ending_text:
            runtime.narrate(f"Keeper: {scenario.ending_text}")
        return
    if not _completion_requirements_met(scenario):
        runtime.narrate("Keeper: The case cannot be concluded yet; key evidence is still missing.")
        _describe_completion_progress(runtime)
        return
    scenario.completed = True
    runtime.narrate("Keeper: You put the evidence together and close the case.")
    if scenario.ending_text:
        runtime.narrate(f"Keeper: {scenario.ending_text}")

def _progress_piece(label: str, required: list[str], current: set[str]) -> str:
    if not required:
        return ""
    met = len([value for value in required if value in current])
    return f"{label} {met}/{len(required)}"


def _describe_keeper_hint(runtime: COCRuntime) -> None:
    runtime.narrate(f"Keeper: Hint: {coc_keeper_hint(runtime.scenario)}")


def coc_keeper_hint(scenario: COCScenario) -> str:
    if scenario.completed:
        return "The core investigation is complete; review your evidence or close the scene."
    requirements = scenario.completion_requirements
    if not requirements:
        undiscovered = _visible_undiscovered_clues(scenario)
        if undiscovered:
            return f"Something nearby deserves attention: {_preferred_clue_action(undiscovered[0])}."
        return "Review the clues you have and look for any place or witness you have not revisited."
    hint = _hint_for_required_clues(scenario, requirements.get("required_clue_ids", []))
    if hint:
        return hint
    hint = _hint_for_required_evidence(scenario, requirements.get("required_evidence", []))
    if hint:
        return hint
    hint = _hint_for_required_locations(scenario, requirements.get("required_location_ids", []))
    if hint:
        return hint
    hint = _hint_for_required_npcs(scenario, requirements.get("required_npc_ids", []))
    if hint:
        return hint
    return "You have met the listed goals; take one more look around or check progress."


def _hint_for_required_clues(scenario: COCScenario, required_clue_ids: list[str]) -> str:
    discovered_ids = {clue.id for clue in scenario.clues if clue.discovered}
    for clue_id in required_clue_ids:
        if clue_id in discovered_ids:
            continue
        clue = _clue_by_id(scenario, clue_id)
        if clue is None:
            continue
        return _hint_for_clue(scenario, clue)
    return ""


def _hint_for_required_evidence(scenario: COCScenario, required_evidence: list[str]) -> str:
    inventory = set(scenario.inventory)
    for evidence in required_evidence:
        if evidence in inventory:
            continue
        clue = next((candidate for candidate in scenario.clues if candidate.evidence == evidence), None)
        if clue is not None:
            return _hint_for_clue(scenario, clue)
    return ""


def _hint_for_required_locations(scenario: COCScenario, required_location_ids: list[str]) -> str:
    for location_id in required_location_ids:
        if scenario.current_location_id == location_id:
            continue
        location = scenario.current_location()
        exit_name = next((name for name, destination in location.exits.items() if destination == location_id), "")
        if exit_name and _exit_requirement_met(scenario, location.exit_requirements.get(exit_name, {})):
            return f"The way is open now: go {exit_name}."
        if exit_name:
            return _hint_for_blocked_exit(scenario, exit_name)
        destination = scenario.locations.get(location_id)
        if destination is not None:
            return f"Your goal points toward {destination.name}; look for a route or clue leading there."
    return ""


def _hint_for_required_npcs(scenario: COCScenario, required_npc_ids: list[str]) -> str:
    for npc_id in required_npc_ids:
        if npc_id in scenario.talked_npc_ids:
            continue
        npc = next((candidate for candidate in scenario.npcs if candidate.id == npc_id), None)
        if npc is None:
            continue
        if npc.location_id in {None, scenario.current_location_id}:
            return f"A witness may still help: talk {npc.name.lower()}."
        location = scenario.locations.get(npc.location_id or "")
        if location is not None:
            return f"{npc.name} may know more; find a way to {location.name}."
    return ""


def _hint_for_clue(scenario: COCScenario, clue: COCClue) -> str:
    if clue.location_id in {None, scenario.current_location_id}:
        if clue.skill:
            return f"Something here may yield to {clue.skill}: {_preferred_clue_action(clue)}."
        return f"Something here deserves attention: {_preferred_clue_action(clue)}."
    location = scenario.locations.get(clue.location_id or "")
    if location is not None:
        return f"A missing lead is likely in {location.name}; find a route there."
    return "A required clue is still hidden; review unexplored leads."


def _preferred_clue_action(clue: COCClue) -> str:
    clue_title = clue.title.lower()
    clue_words = f"{clue.id.replace('_', ' ')} {clue_title}"
    if any(word in clue_words for word in ("journal", "diary", "letter", "book", "note")):
        return f"read {clue_title}"
    if any(word in clue_words for word in ("voice", "voices", "whisper", "well", "sound")):
        return f"listen {clue_title}"
    return f"inspect {clue_title}"


def _hint_for_blocked_exit(scenario: COCScenario, exit_name: str) -> str:
    requirement = scenario.current_location().exit_requirements.get(exit_name, {})
    for clue_id in requirement.get("required_clue_ids", []):
        clue = _clue_by_id(scenario, clue_id)
        if clue is not None and not clue.discovered:
            return _hint_for_clue(scenario, clue)
    for evidence in requirement.get("required_evidence", []):
        if evidence in scenario.inventory:
            continue
        clue = next((candidate for candidate in scenario.clues if candidate.evidence == evidence), None)
        if clue is not None:
            return _hint_for_clue(scenario, clue)
    return f"The {exit_name} route is still blocked; inspect the current location more closely."


def _visible_undiscovered_clues(scenario: COCScenario) -> list[COCClue]:
    return [clue for clue in _visible_clues(scenario) if not clue.discovered]


def _clue_by_id(scenario: COCScenario, clue_id: str) -> COCClue | None:
    return next((clue for clue in scenario.clues if clue.id == clue_id), None)


def _describe_inventory(runtime: COCRuntime) -> None:
    if not runtime.scenario.inventory:
        runtime.narrate("Keeper: No evidence collected yet.")
        return
    runtime.narrate("Keeper: Evidence: " + ", ".join(runtime.scenario.inventory) + ".")


def _talk_to_coc_npc(runtime: COCRuntime, target: str) -> None:
    npc = _match_npc(_visible_npcs(runtime.scenario), target)
    if npc is None:
        runtime.narrate("Keeper: No one by that name is here.")
        return
    runtime.narrate(f"Keeper: {npc.name}: {npc.description}")
    if not npc.dialogue:
        runtime.narrate(f"{npc.name}: I have nothing more to add.")
        runtime.scenario.talked_npc_ids.add(npc.id)
        _maybe_complete_scenario(runtime)
        return
    for line in npc.dialogue:
        runtime.narrate(f"{npc.name}: {line}")
    runtime.scenario.talked_npc_ids.add(npc.id)
    _maybe_complete_scenario(runtime)


def _add_inventory_item(runtime: COCRuntime, item: str) -> None:
    if item in runtime.scenario.inventory:
        return
    runtime.scenario.inventory.append(item)
    runtime.narrate(f"Keeper: Evidence collected - {item}.")


def _move_coc_location(runtime: COCRuntime, target: str) -> None:
    scenario = runtime.scenario
    location = scenario.current_location()
    normalized = target.strip().lower()
    destination_id = location.exits.get(normalized)
    exit_name = normalized if destination_id is not None else None
    if destination_id is None:
        for exit_name, exit_destination in location.exits.items():
            if normalized in {exit_name.lower(), exit_destination.lower()}:
                destination_id = exit_destination
                exit_name = exit_name
                break
    if destination_id is None or destination_id not in scenario.locations:
        runtime.narrate("Keeper: You cannot reach that place from here.")
        return
    requirement = location.exit_requirements.get(exit_name or "")
    if requirement and not _exit_requirement_met(scenario, requirement):
        runtime.narrate(f"Keeper: {requirement.get('message') or 'Something still blocks the way.'}")
        return
    scenario.current_location_id = destination_id
    destination = scenario.current_location()
    scenario.location = destination.name
    scenario.description = destination.description
    runtime.narrate(f"Keeper: You move to {destination.name}.")
    runtime.narrate(f"Keeper: {destination.description}")
    if destination.exits:
        runtime.narrate(f"Keeper: Exits: {', '.join(sorted(destination.exits))}.")
    npcs = _visible_npcs(scenario)
    if npcs:
        runtime.narrate(f"Keeper: Present: {', '.join(npc.name for npc in npcs)}.")
    _maybe_complete_scenario(runtime)

def _exit_requirement_met(scenario: COCScenario, requirement: dict) -> bool:
    required_clue_ids = set(requirement.get("required_clue_ids", []))
    if required_clue_ids:
        discovered_ids = {clue.id for clue in scenario.clues if clue.discovered}
        if not required_clue_ids.issubset(discovered_ids):
            return False
    required_evidence = set(requirement.get("required_evidence", []))
    if required_evidence and not required_evidence.issubset(set(scenario.inventory)):
        return False
    return True


def _maybe_complete_scenario(runtime: COCRuntime) -> None:
    scenario = runtime.scenario
    if scenario.completed:
        return
    if not _completion_requirements_met(scenario):
        return
    scenario.completed = True
    if scenario.ending_text:
        runtime.narrate(f"Keeper: {scenario.ending_text}")


def _completion_requirements_met(scenario: COCScenario) -> bool:
    requirements = scenario.completion_requirements
    if not requirements:
        return bool(scenario.clues) and all(clue.discovered for clue in scenario.clues)
    discovered_ids = {clue.id for clue in scenario.clues if clue.discovered}
    required_clue_ids = set(requirements.get("required_clue_ids", []))
    if required_clue_ids and not required_clue_ids.issubset(discovered_ids):
        return False
    required_evidence = set(requirements.get("required_evidence", []))
    if required_evidence and not required_evidence.issubset(set(scenario.inventory)):
        return False
    required_location_ids = set(requirements.get("required_location_ids", []))
    if required_location_ids and scenario.current_location_id not in required_location_ids:
        return False
    required_npc_ids = set(requirements.get("required_npc_ids", []))
    if required_npc_ids and not required_npc_ids.issubset(scenario.talked_npc_ids):
        return False
    return True


def _visible_clues(scenario: COCScenario) -> list[COCClue]:
    current_location_id = scenario.current_location_id
    if not current_location_id:
        return scenario.clues
    return [clue for clue in scenario.clues if clue.location_id in {None, current_location_id}]


def _visible_npcs(scenario: COCScenario) -> list[COCNPC]:
    current_location_id = scenario.current_location_id
    if not current_location_id:
        return scenario.npcs
    return [npc for npc in scenario.npcs if npc.location_id in {None, current_location_id}]


def _match_clue(clues: list[COCClue], target: str) -> COCClue | None:
    normalized = target.strip().lower()
    for clue in clues:
        haystack = f"{clue.id} {clue.title}".lower().replace("_", " ")
        if normalized in haystack:
            return clue
    return None


def _match_npc(npcs: list[COCNPC], target: str) -> COCNPC | None:
    normalized = target.strip().lower()
    for npc in npcs:
        haystack = f"{npc.id} {npc.name}".lower().replace("_", " ")
        if normalized in haystack:
            return npc
    return None


def _required_success_level(difficulty: str) -> str:
    normalized = difficulty.strip().lower()
    if normalized in {"regular", "hard", "extreme"}:
        return normalized
    return "regular"


def _required_total_for_success(skill_value: int, required: str) -> int:
    if required == "extreme":
        return max(1, skill_value // 5)
    if required == "hard":
        return max(1, skill_value // 2)
    return skill_value


def _success_rank(level: str) -> int:
    return {
        "fumble": -1,
        "failure": 0,
        "regular": 1,
        "hard": 2,
        "extreme": 3,
        "critical": 4,
    }.get(level, 0)
