from __future__ import annotations

import argparse
import random
from dataclasses import dataclass, field
from pathlib import Path

from .core.character import Character
from .core.campaign import Campaign, Clue, Location
from .core.dm_tools import DMTools
from .core.dnd5e import RollMode
from .core.serialization import save_campaign
from .scenario import DEFAULT_SCENE_PATH, SceneDefinition, load_scene, validate_scene_file, write_scene_template


@dataclass
class SampleCampaign:
    tools: DMTools
    campaign: Campaign
    hero: Character
    chapel: Location
    clue: Clue
    scene: SceneDefinition
    inspected_rope: bool = False
    opened_stairway: bool = False
    transcript: list[str] = field(default_factory=list)

    def narrate(self, line: str) -> None:
        self.transcript.append(line)


def build_sample_character(scene: SceneDefinition | None = None) -> Character:
    data = (scene or load_scene()).hero
    return Character(
        name=data["name"],
        player_name=data["player_name"],
        class_name=data["class_name"],
        level=data["level"],
        ancestry=data["ancestry"],
        ability_scores=data["ability_scores"],
        armor_class=data["armor_class"],
        max_hp=data["max_hp"],
        current_hp=data["current_hp"],
        skill_proficiencies=set(data.get("skill_proficiencies", [])),
        saving_throw_proficiencies=set(data.get("saving_throw_proficiencies", [])),
    )


def build_sample_campaign(seed: int, scene_path: str | Path | None = None) -> SampleCampaign:
    scene = load_scene(scene_path)
    campaign_data = scene.campaign
    tools = DMTools(rng=random.Random(seed))
    campaign = tools.create_campaign(
        title=campaign_data["title"],
        party_level=campaign_data["party_level"],
        tone=campaign_data["tone"],
        public_lore=campaign_data.get("public_lore", ""),
        dm_secrets=campaign_data.get("dm_secrets", ""),
    ).data

    hero = build_sample_character(scene)
    tools.add_character(campaign.id, hero)

    location_data = scene.location
    chapel = tools.add_location(
        campaign.id,
        name=location_data["name"],
        public_description=location_data["public_description"],
        dm_notes=location_data.get("dm_notes", ""),
    ).data
    npc_data = scene.npc
    tools.add_npc(
        campaign.id,
        name=npc_data["name"],
        role=npc_data["role"],
        public_description=npc_data["public_description"],
        dm_secret=npc_data.get("dm_secret", ""),
        location_id=chapel.id,
    )
    clue_data = scene.clue
    clue = tools.add_clue(
        campaign.id,
        title=clue_data["title"],
        public_text=clue_data["public_text"],
        dm_secret=clue_data.get("dm_secret", ""),
        location_id=chapel.id,
    ).data
    quest_data = scene.quest
    tools.add_quest(
        campaign.id,
        title=quest_data["title"],
        summary=quest_data["summary"],
    )
    return SampleCampaign(tools=tools, campaign=campaign, hero=hero, chapel=chapel, clue=clue, scene=scene)


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
    for line in sample.scene.text["intro"]:
        sample.narrate(f"DM: {line.format(hero=sample.hero.name)}")


def handle_player_action(sample: SampleCampaign, action: str) -> bool:
    normalized = action.strip().lower()
    if not normalized:
        return True
    sample.narrate(f"Player: {action}")
    sample.tools.record_event(sample.campaign.id, actor=sample.hero.name, content=action)

    if normalized in {"quit", "exit"}:
        sample.narrate(f"DM: {sample.scene.text['pause']}")
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
        sample.narrate(f"DM: {sample.scene.text['look']}")
        return True

    if "rope" in normalized or "bell" in normalized or "inspect" in normalized:
        if not sample.inspected_rope:
            sample.inspected_rope = True
            sample.tools.reveal_clue(sample.campaign.id, sample.clue.id)
            check_data = sample.scene.checks["inspect_rope"]
            modifier = sample.hero.ability_modifier(check_data["ability"])
            if check_data.get("proficient", False):
                modifier += sample.hero.proficiency_bonus
            check = sample.tools.roll_check(
                sample.campaign.id,
                character_name=sample.hero.name,
                modifier=modifier,
                dc=check_data["dc"],
                mode=RollMode(check_data["mode"]),
            ).data
            sample.narrate(f"DM: {sample.scene.text['inspect_first']}")
            sample.narrate(
                f"System: {check_data['label']} with {check.mode.value} vs DC {check.dc} -> "
                f"rolls {check.d20_rolls}, total {check.total}."
            )
            if check.success:
                sample.narrate(f"DM: {sample.scene.text['inspect_success']}")
            else:
                sample.narrate(f"DM: {sample.scene.text['inspect_failure']}")
        else:
            sample.narrate(f"DM: {sample.scene.text['inspect_repeat']}")
        return True

    if "stair" in normalized or "door" in normalized or "open" in normalized:
        if not sample.inspected_rope:
            sample.narrate(f"DM: {sample.scene.text['stairway_locked']}")
            return True
        if not sample.opened_stairway:
            sample.opened_stairway = True
            sample.tools.record_event(
                sample.campaign.id,
                actor="DM",
                content="The sealed stairway opened after the clue was found.",
            )
            sample.narrate(f"DM: {sample.scene.text['stairway_open']}")
        else:
            sample.narrate(f"DM: {sample.scene.text['stairway_repeat']}")
        return True

    sample.narrate(f"DM: {sample.scene.text['unknown']}")
    return True


def run_scripted_scene(
    seed: int,
    actions: list[str],
    scene_path: str | Path | None = None,
    save_state_path: str | Path | None = None,
) -> str:
    sample = build_sample_campaign(seed, scene_path)
    describe_scene(sample)
    for action in actions:
        if not handle_player_action(sample, action):
            break
    if save_state_path is not None:
        save_campaign(sample.campaign, save_state_path)
        sample.narrate(f"System: Saved campaign state to {save_state_path}.")
    return "\n".join(sample.transcript)


def run_interactive_scene(
    seed: int,
    scene_path: str | Path | None = None,
    save_state_path: str | Path | None = None,
) -> int:
    sample = build_sample_campaign(seed, scene_path)
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
            if save_state_path is not None:
                save_campaign(sample.campaign, save_state_path)
                print(f"System: Saved campaign state to {save_state_path}.")
            return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run small DND AI assistant demos.")
    subparsers = parser.add_subparsers(dest="command")

    quickstart = subparsers.add_parser("quickstart", help="Run a small deterministic campaign demo.")
    quickstart.add_argument("--seed", type=int, default=1, help="Random seed for reproducible rolls.")

    play = subparsers.add_parser("play", help="Play a tiny scripted chapel scene.")
    play.add_argument("--seed", type=int, default=1, help="Random seed for reproducible rolls.")
    play.add_argument("--scene", default=None, help="Path to a scene JSON file.")
    play.add_argument("--save-state", default=None, help="Write final campaign state to a JSON file.")
    play.add_argument(
        "--action",
        action="append",
        default=[],
        help="Run a non-interactive action. Repeat this option to script a scene.",
    )

    validate = subparsers.add_parser("validate-scene", help="Validate a scene JSON file.")
    validate.add_argument("--scene", default=None, help="Path to a scene JSON file. Defaults to bundled old_chapel.")

    new_scene = subparsers.add_parser("new-scene", help="Write a starter scene JSON template.")
    new_scene.add_argument("--output", required=True, help="Where to write the scene JSON file.")
    new_scene.add_argument("--title", default="Untitled DND Adventure", help="Campaign title for the template.")

    args = parser.parse_args()
    if args.command == "quickstart":
        print(run_quickstart(args.seed))
        return 0
    if args.command == "play":
        if args.action:
            print(run_scripted_scene(args.seed, args.action, args.scene, args.save_state))
            return 0
        return run_interactive_scene(args.seed, args.scene, args.save_state)
    if args.command == "validate-scene":
        scene = validate_scene_file(args.scene)
        scene_path = args.scene or DEFAULT_SCENE_PATH
        print(f"Scene OK: {scene_path}")
        print(f"Title: {scene.campaign['title']}")
        return 0
    if args.command == "new-scene":
        write_scene_template(args.output, args.title)
        print(f"Wrote scene template: {args.output}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
