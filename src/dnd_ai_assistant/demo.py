from __future__ import annotations

import argparse
import random

from .core.character import Character
from .core.dm_tools import DMTools
from .core.dnd5e import RollMode


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


def run_quickstart(seed: int) -> str:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run small DND AI assistant demos.")
    subparsers = parser.add_subparsers(dest="command")

    quickstart = subparsers.add_parser("quickstart", help="Run a small deterministic campaign demo.")
    quickstart.add_argument("--seed", type=int, default=1, help="Random seed for reproducible rolls.")

    args = parser.parse_args()
    if args.command == "quickstart":
        print(run_quickstart(args.seed))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

