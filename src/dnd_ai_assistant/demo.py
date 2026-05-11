from __future__ import annotations

import argparse
import random
from dataclasses import dataclass, field

from .core.character import Character
from .core.campaign import Campaign, Clue, Location
from .core.dm_tools import DMTools
from .core.dnd5e import RollMode


@dataclass
class SampleCampaign:
    tools: DMTools
    campaign: Campaign
    hero: Character
    chapel: Location
    clue: Clue
    inspected_rope: bool = False
    opened_stairway: bool = False
    transcript: list[str] = field(default_factory=list)

    def narrate(self, line: str) -> None:
        self.transcript.append(line)


def build_sample_character() -> Character:
    return Character(
        name="Kael",
        player_name="Altman",
        class_name="Ranger",
        level=2,
        ancestry="Wood Elf",
        ability_scores={"str": 10, "dex": 16, "con": 12, "int": 10, "wis": 14, "cha": 8},
        armor_class=15,
        max_hp=18,
        current_hp=18,
        skill_proficiencies={"perception", "survival"},
        saving_throw_proficiencies={"str", "dex"},
    )


def build_sample_campaign(seed: int) -> SampleCampaign:
    tools = DMTools(rng=random.Random(seed))
    campaign = tools.create_campaign(
        title="The Bell Beneath Ashford",
        party_level=2,
        tone="dark fantasy investigation",
        public_lore="Ashford is a mining town where the old chapel bell has begun ringing underground.",
        dm_secrets="The bell is a planar anchor hidden beneath the chapel crypt.",
    ).data

    hero = build_sample_character()
    tools.add_character(campaign.id, hero)

    chapel = tools.add_location(
        campaign.id,
        name="Old Chapel",
        public_description="A cracked chapel with a silent bronze bell and a sealed stairway.",
        dm_notes="The sealed stairway leads to the crypt anchor.",
    ).data
    tools.add_npc(
        campaign.id,
        name="Mira Voss",
        role="worried mayor",
        public_description="A careful woman trying to keep Ashford calm.",
        dm_secret="She hears the bell in her dreams.",
        location_id=chapel.id,
    )
    clue = tools.add_clue(
        campaign.id,
        title="Ash on the Bell Rope",
        public_text="The bell rope is dusted with black ash that smells faintly of sulfur.",
        dm_secret="The ash came from the lower crypt.",
        location_id=chapel.id,
    ).data
    tools.add_quest(
        campaign.id,
        title="Find the Source of the Bell",
        summary="Investigate why the chapel bell rings from below ground.",
    )
    return SampleCampaign(tools=tools, campaign=campaign, hero=hero, chapel=chapel, clue=clue)


def run_quickstart(seed: int) -> str:
    sample = build_sample_campaign(seed)
    tools = sample.tools
    campaign = sample.campaign
    hero = sample.hero
    chapel = sample.chapel
    clue = sample.clue

    tools.record_event(
        campaign.id,
        actor="DM",
        content="Kael enters the Old Chapel and studies the bell rope.",
    )
    tools.reveal_clue(campaign.id, clue.id)
    check = tools.roll_check(
        campaign.id,
        character_name=hero.name,
        modifier=hero.ability_modifier("wis") + hero.proficiency_bonus,
        dc=15,
        mode=RollMode.ADVANTAGE,
    ).data

    lines = [
        f"Campaign: {campaign.title}",
        f"Tone: {campaign.tone}",
        f"Party level: {campaign.party_level}",
        "",
        "Characters:",
        f"- {hero.name}, level {hero.level} {hero.ancestry} {hero.class_name} "
        f"(AC {hero.armor_class}, HP {hero.current_hp}/{hero.max_hp})",
        "",
        "Locations:",
        f"- {chapel.name}: {chapel.public_description}",
        "",
        "Revealed clues:",
        f"- {clue.title}: {clue.public_text}",
        "",
        "Check:",
        f"- {hero.name} rolls Perception with advantage vs DC 15",
        f"- d20 rolls: {', '.join(str(value) for value in check.d20_rolls)}",
        f"- total: {check.total}",
        f"- success: {check.success}",
        "",
        "Session log:",
    ]
    lines.extend(f"- [{event.actor}] {event.content}" for event in campaign.session_log)
    return "\n".join(lines)


def describe_scene(sample: SampleCampaign) -> None:
    sample.narrate(f"DM: {sample.hero.name} stands inside the Old Chapel.")
    sample.narrate(
        "DM: A bronze bell hangs above a sealed stairway. The bell rope is stained with black dust."
    )
    sample.narrate("DM: Try actions like 'look around', 'inspect rope', 'open stairway', 'log', or 'quit'.")


def handle_player_action(sample: SampleCampaign, action: str) -> bool:
    normalized = action.strip().lower()
    if not normalized:
        return True
    sample.narrate(f"Player: {action}")
    sample.tools.record_event(sample.campaign.id, actor=sample.hero.name, content=action)

    if normalized in {"quit", "exit"}:
        sample.narrate("DM: The scene pauses here.")
        return False

    if normalized in {"help", "?"}:
        sample.narrate("DM: Available actions: look around, inspect rope, open stairway, log, quit.")
        return True

    if "log" in normalized:
        sample.narrate("DM: Session log:")
        for event in sample.campaign.session_log:
            sample.narrate(f"- [{event.actor}] {event.content}")
        return True

    if "look" in normalized or "around" in normalized:
        sample.narrate(
            "DM: The chapel is cold. The pews are empty, the altar is cracked, and the bell rope moves without wind."
        )
        return True

    if "rope" in normalized or "bell" in normalized or "inspect" in normalized:
        if not sample.inspected_rope:
            sample.inspected_rope = True
            sample.tools.reveal_clue(sample.campaign.id, sample.clue.id)
            check = sample.tools.roll_check(
                sample.campaign.id,
                character_name=sample.hero.name,
                modifier=sample.hero.ability_modifier("wis") + sample.hero.proficiency_bonus,
                dc=15,
                mode=RollMode.ADVANTAGE,
            ).data
            sample.narrate("DM: You examine the bell rope. Black ash clings to your glove.")
            sample.narrate(
                f"System: Perception with advantage vs DC 15 -> rolls {check.d20_rolls}, total {check.total}."
            )
            if check.success:
                sample.narrate(
                    "DM: You notice the ash trail leading under the sealed stairway. Something below is warm."
                )
            else:
                sample.narrate("DM: You find the ash, but its source is unclear.")
        else:
            sample.narrate("DM: You already found the black ash on the rope.")
        return True

    if "stair" in normalized or "door" in normalized or "open" in normalized:
        if not sample.inspected_rope:
            sample.narrate("DM: The stairway seal does not move. The bell rope may hold a clue.")
            return True
        if not sample.opened_stairway:
            sample.opened_stairway = True
            sample.tools.record_event(
                sample.campaign.id,
                actor="DM",
                content="The sealed stairway opened after the clue was found.",
            )
            sample.narrate(
                "DM: The seal grinds open. Warm air rises from the crypt, carrying the sound of a distant bell."
            )
        else:
            sample.narrate("DM: The stairway is already open.")
        return True

    sample.narrate("DM: The current prototype does not know how to resolve that yet.")
    return True


def run_scripted_scene(seed: int, actions: list[str]) -> str:
    sample = build_sample_campaign(seed)
    describe_scene(sample)
    for action in actions:
        if not handle_player_action(sample, action):
            break
    return "\n".join(sample.transcript)


def run_interactive_scene(seed: int) -> int:
    sample = build_sample_campaign(seed)
    describe_scene(sample)
    print("\n".join(sample.transcript))
    sample.transcript.clear()

    while True:
        action = input("> ")
        keep_going = handle_player_action(sample, action)
        if sample.transcript:
            print("\n".join(sample.transcript))
            sample.transcript.clear()
        if not keep_going:
            return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run small DND AI assistant demos.")
    subparsers = parser.add_subparsers(dest="command")

    quickstart = subparsers.add_parser("quickstart", help="Run a small deterministic campaign demo.")
    quickstart.add_argument("--seed", type=int, default=1, help="Random seed for reproducible rolls.")

    play = subparsers.add_parser("play", help="Play a tiny scripted chapel scene.")
    play.add_argument("--seed", type=int, default=1, help="Random seed for reproducible rolls.")
    play.add_argument(
        "--action",
        action="append",
        default=[],
        help="Run a non-interactive action. Repeat this option to script a scene.",
    )

    args = parser.parse_args()
    if args.command == "quickstart":
        print(run_quickstart(args.seed))
        return 0
    if args.command == "play":
        if args.action:
            print(run_scripted_scene(args.seed, args.action))
            return 0
        return run_interactive_scene(args.seed)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
