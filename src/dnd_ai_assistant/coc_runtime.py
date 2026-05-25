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
    skill: str | None = None
    difficulty: str = "regular"
    sanity_loss: int = 0
    discovered: bool = False


@dataclass
class COCScenario:
    title: str
    location: str
    description: str
    investigator: Investigator
    clues: list[COCClue] = field(default_factory=list)
    ending_text: str = ""
    id: str = field(default_factory=lambda: f"coc_{uuid4().hex[:12]}")


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
    return COCScenario(
        title="The Lantern Under Briar House",
        location="Briar House Study",
        description=(
            "Rain presses against the study windows. A locked writing desk, a soot-stained "
            "hearth, and a portrait with scratched-out eyes wait in the lamplight."
        ),
        investigator=investigator,
        clues=[
            COCClue(
                id="desk_journal",
                title="Waterlogged Journal",
                text="The journal names a lantern buried under the house and repeats the phrase 'do not trim the wick'.",
                skill="library use",
                difficulty="regular",
            ),
            COCClue(
                id="hearth_symbol",
                title="Ashen Spiral",
                text="The ash forms a spiral that seems to bend toward your hand. The shape is older than the house.",
                skill="spot hidden",
                difficulty="hard",
                sanity_loss=1,
            ),
            COCClue(
                id="portrait_truth",
                title="Scratched Portrait",
                text="Behind the torn canvas is a narrow crawlspace descending into wet stone.",
                skill=None,
                sanity_loss=2,
            ),
        ],
        ending_text="With enough clues gathered, the cellar route is clear. The lantern waits below.",
    )


def describe_coc_scene(runtime: COCRuntime) -> None:
    scenario = runtime.scenario
    investigator = scenario.investigator
    runtime.narrate(f"Keeper: {scenario.title}")
    runtime.narrate(f"Keeper: {scenario.location}")
    runtime.narrate(f"Keeper: {scenario.description}")
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
        runtime.narrate("Keeper: Actions: look, status, inspect <target>, check <skill>, sanity, clues, quit.")
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
    if normalized.startswith("inspect "):
        _inspect_coc_target(runtime, normalized[len("inspect ") :].strip())
        return True
    if normalized.startswith("check "):
        _manual_coc_check(runtime, normalized[len("check ") :].strip())
        return True
    runtime.narrate("Keeper: That action is not supported yet.")
    return True


def _inspect_coc_target(runtime: COCRuntime, target: str) -> None:
    clue = _match_clue(runtime.scenario.clues, target)
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
    if all(clue.discovered for clue in runtime.scenario.clues):
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
    discovered = sum(1 for clue in runtime.scenario.clues if clue.discovered)
    total = len(runtime.scenario.clues)
    runtime.narrate(
        f"Keeper: {investigator.name} ({investigator.occupation}) - "
        f"HP {investigator.current_hp}/{investigator.max_hp}, "
        f"MP {investigator.current_mp}/{investigator.max_mp}, "
        f"SAN {investigator.current_sanity}/{investigator.max_sanity}, "
        f"Luck {investigator.luck}, clues {discovered}/{total}, "
        f"conditions: {', '.join(sorted(investigator.conditions)) or 'none'}."
    )


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
