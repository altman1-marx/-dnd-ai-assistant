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
    discovered: bool = False


@dataclass
class COCLocation:
    id: str
    name: str
    description: str
    exits: dict[str, str] = field(default_factory=dict)


@dataclass
class COCScenario:
    title: str
    location: str
    description: str
    investigator: Investigator
    clues: list[COCClue] = field(default_factory=list)
    locations: dict[str, COCLocation] = field(default_factory=dict)
    current_location_id: str | None = None
    inventory: list[str] = field(default_factory=list)
    ending_text: str = ""
    completed: bool = False
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

    def flush(self) -> str:
        output = "\n".join(self.transcript)
        self.transcript.clear()
        return output


def create_sample_coc_scenario() -> COCScenario:
    investigator = Investigator(
        name="Eleanor Vale",
        occupation="Antiquarian",
        characteristics={"str": 45, "con": 55, "siz": 60, "dex": 50, "app": 55, "int": 70, "pow": 60, "edu": 75},
        skills={"library use": 55, "spot hidden": 45, "occult": 40, "psychology": 35},
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
            exits={"cellar": "cellar"},
        ),
        "cellar": COCLocation(
            id="cellar",
            name="Briar House Cellar",
            description="Wet stone steps descend to a cramped cellar where a brass lantern hangs cold and unlit.",
            exits={"study": "study"},
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
                id="lantern_wick",
                title="Black Wick",
                text="The lantern wick is braided from black hair and sea grass. It twitches when named.",
                location_id="cellar",
                evidence="Black wick sample",
                skill=None,
                sanity_loss=2,
            ),
        ],
        locations=locations,
        current_location_id="study",
        ending_text="With enough clues gathered, the cellar route is clear. The lantern waits below.",
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
            "Keeper: Actions: look, status, go <exit>, inspect <target>, check <skill>, sanity, clues, inventory, quit."
        )
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
    if normalized.startswith("go "):
        _move_coc_location(runtime, normalized[len("go ") :].strip())
        return True
    if normalized.startswith("inspect "):
        _inspect_coc_target(runtime, normalized[len("inspect ") :].strip())
        return True
    if normalized.startswith("check "):
        _manual_coc_check(runtime, normalized[len("check ") :].strip())
        return True
    runtime.narrate("Keeper: That action is not supported yet.")
    return True


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
            runtime.narrate("Keeper: Something is here, but the pattern does not come together yet.")
            return
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
    success = _success_rank(check.success_level.value) >= _success_rank(required)
    runtime.narrate(
        f"Keeper: {investigator.name} rolls {clue.skill} {check.total} vs {skill_value}: "
        f"{check.success_level.value}; needs {required}."
    )
    return success


def _reveal_coc_clue(runtime: COCRuntime, clue: COCClue) -> None:
    clue.discovered = True
    runtime.narrate(f"Keeper: Clue found - {clue.title}: {clue.text}")
    if clue.sanity_loss > 0:
        runtime.scenario.investigator.lose_sanity(clue.sanity_loss)
        runtime.narrate(f"Keeper: SAN loss {clue.sanity_loss}.")
    if clue.evidence:
        _add_inventory_item(runtime, clue.evidence)
    if all(clue.discovered for clue in runtime.scenario.clues):
        runtime.scenario.completed = True
        runtime.narrate(f"Keeper: {runtime.scenario.ending_text}")


def _describe_discovered_clues(runtime: COCRuntime) -> None:
    discovered = [clue for clue in runtime.scenario.clues if clue.discovered]
    if not discovered:
        runtime.narrate("Keeper: No clues discovered yet.")
        return
    for clue in discovered:
        runtime.narrate(f"- {clue.title}: {clue.text}")


def _describe_coc_status(runtime: COCRuntime) -> None:
    investigator = runtime.scenario.investigator
    location = runtime.scenario.current_location()
    discovered = sum(1 for clue in runtime.scenario.clues if clue.discovered)
    total = len(runtime.scenario.clues)
    runtime.narrate(
        f"Keeper: {investigator.name} ({investigator.occupation}) - "
        f"location {location.name}, "
        f"HP {investigator.current_hp}/{investigator.max_hp}, "
        f"MP {investigator.current_mp}/{investigator.max_mp}, "
        f"SAN {investigator.current_sanity}/{investigator.max_sanity}, "
        f"Luck {investigator.luck}, clues {discovered}/{total}, evidence {len(runtime.scenario.inventory)}, "
        f"conditions: {', '.join(sorted(investigator.conditions)) or 'none'}."
    )


def _describe_inventory(runtime: COCRuntime) -> None:
    if not runtime.scenario.inventory:
        runtime.narrate("Keeper: No evidence collected yet.")
        return
    runtime.narrate("Keeper: Evidence: " + ", ".join(runtime.scenario.inventory) + ".")


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
    if destination_id is None:
        for exit_name, exit_destination in location.exits.items():
            if normalized in {exit_name.lower(), exit_destination.lower()}:
                destination_id = exit_destination
                break
    if destination_id is None or destination_id not in scenario.locations:
        runtime.narrate("Keeper: You cannot reach that place from here.")
        return
    scenario.current_location_id = destination_id
    destination = scenario.current_location()
    scenario.location = destination.name
    scenario.description = destination.description
    runtime.narrate(f"Keeper: You move to {destination.name}.")
    runtime.narrate(f"Keeper: {destination.description}")
    if destination.exits:
        runtime.narrate(f"Keeper: Exits: {', '.join(sorted(destination.exits))}.")


def _visible_clues(scenario: COCScenario) -> list[COCClue]:
    current_location_id = scenario.current_location_id
    if not current_location_id:
        return scenario.clues
    return [clue for clue in scenario.clues if clue.location_id in {None, current_location_id}]


def _match_clue(clues: list[COCClue], target: str) -> COCClue | None:
    normalized = target.strip().lower()
    for clue in clues:
        haystack = f"{clue.id} {clue.title}".lower().replace("_", " ")
        if normalized in haystack:
            return clue
    return None


def _required_success_level(difficulty: str) -> str:
    normalized = difficulty.strip().lower()
    if normalized in {"regular", "hard", "extreme"}:
        return normalized
    return "regular"


def _success_rank(level: str) -> int:
    return {
        "fumble": -1,
        "failure": 0,
        "regular": 1,
        "hard": 2,
        "extreme": 3,
        "critical": 4,
    }.get(level, 0)
