from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from .adventure import load_adventure, validate_adventure, write_adventure_template
from .adventure_generator import AdventureRequest, build_adventure_prompt, generate_adventure_files, rules_context_for_request, write_adventure_from_model_text, write_campaign_from_model_text
from .adventure_importer import campaign_from_adventure
from .adventure_map import render_mermaid_map, render_text_map
from .adventure_review import render_adventure_review, render_adventure_review_json
from .adventure_runtime import AdventureRuntime, describe_current_location, handle_adventure_action
from .ai_dm import generate_dm_suggestion
from .ai_provider import build_provider
from .api import run_server
from .core.dnd5e import RollMode
from .core.initiative import Combatant, InitiativeTracker
from .core.serialization import load_campaign, save_campaign
from .rules_corpus import DEFAULT_SRD_URL, RuleCorpus, build_srd_corpus, format_search_results
from .sample_data import sample_adventure_character
from .scenario import DEFAULT_SCENE_PATH, SceneDefinition, load_scene, validate_scene_file, write_scene_template
from .scene_engine import build_character, build_scene_session, describe_scene, handle_player_action


def build_sample_character(scene: SceneDefinition | None = None):
    return build_character(scene or load_scene())


def build_sample_campaign(seed: int, scene_path: str | Path | None = None):
    return build_scene_session(seed, scene_path)


def run_quickstart(seed: int) -> str:
    sample = build_sample_campaign(seed)
    tools = sample.tools
    campaign = sample.campaign
    hero = sample.hero
    chapel = sample.location
    clue = sample.clue

    tools.record_event(
        campaign.id,
        actor="DM",
        content="Kael enters the Old Chapel and studies the bell rope.",
    )
    tools.reveal_clue(campaign.id, clue.id)
    check_data = sample.scene.checks["inspect_rope"]
    check = tools.roll_skill_check(
        campaign.id,
        character_name=hero.name,
        skill_name=check_data.get("skill", "perception"),
        dc=check_data["dc"],
        mode=RollMode(check_data["mode"]),
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
        f"- {hero.name} rolls {check_data['label']} with {check.mode.value} vs DC {check.dc}",
        f"- d20 rolls: {', '.join(str(value) for value in check.d20_rolls)}",
        f"- total: {check.total}",
        f"- success: {check.success}",
        "",
        "Session log:",
    ]
    lines.extend(f"- [{event.actor}] {event.content}" for event in campaign.session_log)
    return "\n".join(lines)


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


def run_initiative_demo(seed: int, rounds: int, scene_path: str | Path | None = None) -> str:
    session = build_scene_session(seed, scene_path)
    combatants = [
        Combatant(
            session.hero.name,
            initiative_modifier=session.hero.ability_modifier("dex"),
            armor_class=session.hero.armor_class,
            current_hp=session.hero.current_hp,
            is_player=True,
        )
    ]
    for encounter in session.campaign.encounters.values():
        for monster in encounter.monsters:
            combatants.append(
                Combatant(
                    monster.name,
                    initiative_modifier=monster.initiative_modifier,
                    armor_class=monster.armor_class,
                    current_hp=monster.current_hp,
                )
            )
    if len(combatants) == 1:
        combatants.extend(
            [
                Combatant("Mira Voss", initiative_modifier=1, armor_class=12, current_hp=9),
                Combatant("Ash Goblin", initiative_modifier=2, armor_class=13, current_hp=7),
            ]
        )

    tracker = InitiativeTracker(combatants)
    tracker.roll_initiative(random.Random(seed))

    lines = ["Initiative order:"]
    for combatant in tracker.combatants:
        lines.append(
            f"- {combatant.name}: d20 {combatant.initiative_roll} + {combatant.initiative_modifier} "
            f"= {combatant.initiative_total}"
        )

    lines.append("")
    lines.append("Turns:")
    lines.append(f"- Round {tracker.round_number}: {tracker.current().name}")
    for _ in range(max(0, rounds * len(tracker.combatants) - 1)):
        current = tracker.advance()
        lines.append(f"- Round {tracker.round_number}: {current.name}")
    return "\n".join(lines)


def run_combat_demo(
    seed: int,
    scene_path: str | Path | None = None,
    save_state_path: str | Path | None = None,
) -> str:
    session = build_scene_session(seed, scene_path)
    encounter = next(iter(session.campaign.encounters.values()), None)
    if encounter is None or not encounter.monsters:
        return "No encounter found in this scene."

    monster = encounter.monsters[0]
    result = session.tools.attack_character(
        campaign_id=session.campaign.id,
        attacker_name=monster.name,
        target_name=session.hero.name,
        attack_bonus=monster.attack_bonus,
        damage_expression=monster.damage,
        damage_type=monster.damage_type,
    )
    attack = result.data
    lines = [
        f"Encounter: {encounter.title}",
        f"Attacker: {monster.name}",
        f"Target: {session.hero.name} (AC {session.hero.armor_class})",
        f"Attack total: {attack.attack.total}",
        f"Hit: {attack.hit}",
    ]
    if attack.damage is not None:
        lines.append(f"Damage: {attack.damage.total}")
    lines.append(f"Target HP: {session.hero.current_hp}/{session.hero.max_hp}")
    lines.append("")
    lines.append("Session log:")
    lines.extend(f"- [{event.actor}] {event.content}" for event in session.campaign.session_log)
    if save_state_path is not None:
        save_campaign(session.campaign, save_state_path)
        lines.append(f"System: Saved campaign state to {save_state_path}.")
    return "\n".join(lines)


def summarize_state(path: str | Path) -> str:
    campaign = load_campaign(path)
    lines = [
        f"Campaign: {campaign.title}",
        f"System: {campaign.system}",
        f"Tone: {campaign.tone}",
        f"Party level: {campaign.party_level}",
        "",
        f"Characters: {len(campaign.characters)}",
    ]
    for character in campaign.characters.values():
        lines.append(
            f"- {character.name}: level {character.level} {character.ancestry} {character.class_name}, "
            f"HP {character.current_hp}/{character.max_hp}, AC {character.armor_class}"
        )
    lines.extend(
        [
            "",
            f"Current location: {_current_location_summary(campaign)}",
            f"Locations: {len(campaign.locations)}",
            f"NPCs: {len(campaign.npcs)}",
            f"Clues: {sum(1 for clue in campaign.clues.values() if clue.discovered)}/{len(campaign.clues)} discovered",
            f"Quests: {len(campaign.quests)}",
            f"Encounters: {len(campaign.encounters)}",
            f"Session events: {len(campaign.session_log)}",
        ]
    )
    if campaign.active_combat is not None:
        active_combat = campaign.active_combat
        lines.extend(
            [
                "",
                "Active combat:",
                f"- Encounter: {active_combat.get('encounter_id', '<unknown>')}",
                f"- Round: {active_combat.get('round', 1)}",
                f"- Turn: {active_combat.get('turn', '<unknown>')}",
            ]
        )
        initiative = active_combat.get("initiative", [])
        if initiative:
            lines.append("- Initiative:")
            for combatant in initiative:
                hp_text = _combatant_hp_summary(campaign, combatant)
                lines.append(
                    f"  - {combatant.get('name', '<unknown>')}: "
                    f"{combatant.get('initiative_total', 0)} initiative, "
                    f"AC {combatant.get('armor_class', '?')}, {hp_text}"
                )
        resources = active_combat.get("resources", {})
        turn_resources = resources.get(active_combat.get("turn"), {})
        if turn_resources:
            lines.append(
                "- Current resources: "
                f"action={turn_resources.get('action', True)}, "
                f"bonus_action={turn_resources.get('bonus_action', True)}, "
                f"reaction={turn_resources.get('reaction', True)}, "
                f"movement={turn_resources.get('movement', 30)}"
            )
    if campaign.session_log:
        lines.append("")
        lines.append("Recent events:")
        for event in campaign.session_log[-5:]:
            lines.append(f"- [{event.actor}] {event.content}")
    return "\n".join(lines)


def _current_location_summary(campaign) -> str:
    if campaign.current_location_id is None:
        return "(none)"
    location = campaign.locations.get(campaign.current_location_id)
    if location is None:
        return f"(unknown: {campaign.current_location_id})"
    return location.name


def _combatant_hp_summary(campaign, combatant: dict) -> str:
    name = combatant.get("name", "")
    character = campaign.characters.get(name)
    if character is not None:
        return f"HP {character.current_hp}/{character.max_hp}"
    for encounter in campaign.encounters.values():
        for monster in encounter.monsters:
            if monster.name == name:
                return f"HP {monster.current_hp}/{monster.max_hp}"
    return f"HP {combatant.get('current_hp', '?')}"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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

    validate_adventure_parser = subparsers.add_parser("validate-adventure", help="Validate an adventure JSON file.")
    validate_adventure_parser.add_argument("path", help="Path to an adventure JSON file.")

    new_adventure = subparsers.add_parser("new-adventure", help="Write a starter adventure JSON template.")
    new_adventure.add_argument("--output", required=True, help="Where to write the adventure JSON file.")
    new_adventure.add_argument("--title", default="Untitled DND Adventure", help="Campaign title for the template.")

    adventure_map = subparsers.add_parser("adventure-map", help="Render an adventure location map.")
    adventure_map.add_argument("path", help="Path to an adventure JSON file.")
    adventure_map.add_argument("--format", choices=("text", "mermaid"), default="text", help="Map output format.")

    adventure_review = subparsers.add_parser("review-adventure", help="Review adventure content quality.")
    adventure_review.add_argument("path", help="Path to an adventure JSON file.")
    adventure_review.add_argument("--format", choices=("text", "json"), default="text", help="Review output format.")

    import_adventure = subparsers.add_parser("import-adventure", help="Import an adventure JSON as campaign state.")
    import_adventure.add_argument("path", help="Path to an adventure JSON file.")
    import_adventure.add_argument("--output", required=True, help="Where to write the campaign state JSON.")

    adventure_prompt = subparsers.add_parser("adventure-prompt", help="Print a prompt for an adventure-writing AI.")
    adventure_prompt.add_argument("--premise", required=True, help="Adventure premise or inspiration.")
    adventure_prompt.add_argument("--party-level", type=int, default=1, help="Target party level.")
    adventure_prompt.add_argument("--player-count", type=int, default=4, help="Number of players.")
    adventure_prompt.add_argument("--duration-hours", type=int, default=2, help="Target play time in hours.")
    adventure_prompt.add_argument("--tone", default="heroic fantasy mystery", help="Adventure tone.")
    adventure_prompt.add_argument("--combat-ratio", default="medium", help="Desired combat ratio.")
    adventure_prompt.add_argument("--puzzle-ratio", default="medium", help="Desired puzzle ratio.")
    adventure_prompt.add_argument("--rules-corpus", default=None, help="Optional JSONL rules corpus for prompt context.")

    clean_adventure = subparsers.add_parser(
        "clean-adventure-output",
        help="Extract and validate adventure JSON from an AI response file.",
    )
    clean_adventure.add_argument("input", help="Path to a text file containing model output.")
    clean_adventure.add_argument("--output", required=True, help="Where to write clean adventure JSON.")

    compile_adventure = subparsers.add_parser(
        "compile-adventure-output",
        help="Extract adventure JSON from an AI response and import it as campaign state.",
    )
    compile_adventure.add_argument("input", help="Path to a text file containing model output.")
    compile_adventure.add_argument("--adventure-output", required=True, help="Where to write clean adventure JSON.")
    compile_adventure.add_argument("--campaign-output", required=True, help="Where to write campaign state JSON.")

    generate_adventure = subparsers.add_parser(
        "generate-adventure",
        help="Generate adventure and campaign files through an AI provider.",
    )
    generate_adventure.add_argument("--premise", required=True, help="Adventure premise or inspiration.")
    generate_adventure.add_argument("--adventure-output", required=True, help="Where to write clean adventure JSON.")
    generate_adventure.add_argument("--campaign-output", required=True, help="Where to write campaign state JSON.")
    generate_adventure.add_argument("--provider", choices=("mock", "openai-compatible"), default="openai-compatible")
    generate_adventure.add_argument("--mock-response", default=None, help="Path to mock model output text.")
    generate_adventure.add_argument("--base-url", default=None, help="Override DND_AI_BASE_URL.")
    generate_adventure.add_argument("--model", default=None, help="Override DND_AI_MODEL.")
    generate_adventure.add_argument("--party-level", type=int, default=1, help="Target party level.")
    generate_adventure.add_argument("--player-count", type=int, default=4, help="Number of players.")
    generate_adventure.add_argument("--duration-hours", type=int, default=2, help="Target play time in hours.")
    generate_adventure.add_argument("--tone", default="heroic fantasy mystery", help="Adventure tone.")
    generate_adventure.add_argument("--combat-ratio", default="medium", help="Desired combat ratio.")
    generate_adventure.add_argument("--puzzle-ratio", default="medium", help="Desired puzzle ratio.")
    generate_adventure.add_argument("--rules-corpus", default=None, help="Optional JSONL rules corpus for prompt context.")
    generate_adventure.add_argument("--review-format", choices=("text", "json"), default="text")
    generate_adventure.add_argument("--max-attempts", type=int, default=1, help="Retry with repair prompts on invalid model output.")
    generate_adventure.add_argument(
        "--json-response-format",
        action="store_true",
        help="Request OpenAI-compatible JSON object response_format when supported.",
    )

    initiative = subparsers.add_parser("initiative", help="Run a small initiative tracker demo.")
    initiative.add_argument("--seed", type=int, default=1, help="Random seed for reproducible rolls.")
    initiative.add_argument("--rounds", type=int, default=2, help="How many rounds to print.")
    initiative.add_argument("--scene", default=None, help="Path to a scene JSON file.")

    combat = subparsers.add_parser("combat", help="Run a one-attack combat demo from scene encounter data.")
    combat.add_argument("--seed", type=int, default=1, help="Random seed for reproducible rolls.")
    combat.add_argument("--scene", default=None, help="Path to a scene JSON file.")
    combat.add_argument("--save-state", default=None, help="Write final campaign state to a JSON file.")

    state = subparsers.add_parser("state-summary", help="Print a saved campaign state summary.")
    state.add_argument("path", help="Path to a saved campaign JSON file.")

    adventure_play = subparsers.add_parser("play-adventure-state", help="Run generic actions against a campaign state.")
    adventure_play.add_argument("path", help="Path to a saved campaign JSON file.")
    adventure_play.add_argument("--seed", type=int, default=1, help="Random seed for reproducible adventure runtime rolls.")
    adventure_play.add_argument("--save-state", default=None, help="Where to save updated campaign state.")
    adventure_play.add_argument(
        "--add-sample-character",
        action="store_true",
        help="Add a ready-to-play sample cleric if the campaign has no characters.",
    )
    adventure_play.add_argument(
        "--action",
        action="append",
        default=[],
        help="Run a non-interactive action. Repeat to script the adventure runtime.",
    )

    serve_api = subparsers.add_parser("serve-api", help="Run the lightweight JSON API server.")
    serve_api.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    serve_api.add_argument("--port", type=int, default=8000, help="Port to bind.")
    serve_api.add_argument("--rules-corpus", default=None, help="Optional JSONL rules corpus for /rules/search.")
    serve_api.add_argument("--ai-provider", choices=("none", "mock", "openai-compatible"), default="none")
    serve_api.add_argument("--mock-response", default=None, help="Path to mock provider text for API AI routes.")
    serve_api.add_argument("--base-url", default=None, help="Override DND_AI_BASE_URL for API AI routes.")
    serve_api.add_argument("--model", default=None, help="Override DND_AI_MODEL for API AI routes.")

    build_rules = subparsers.add_parser("build-rules-corpus", help="Build a local DND rules JSONL corpus.")
    build_rules.add_argument("--source", choices=("srd",), default="srd", help="Rules source to build.")
    build_rules.add_argument("--source-url", default=None, help="Override the SRD HTML source URL.")
    build_rules.add_argument("--output", required=True, help="Where to write rules JSONL.")

    search_rules = subparsers.add_parser("search-rules", help="Search a local DND rules JSONL corpus.")
    search_rules.add_argument("--corpus", required=True, help="Path to rules JSONL corpus.")
    search_rules.add_argument("--query", required=True, help="Rules question or search query.")
    search_rules.add_argument("--limit", type=int, default=5, help="Maximum number of results.")

    dm_suggest = subparsers.add_parser("dm-suggest", help="Generate a DM suggestion for a saved campaign state.")
    dm_suggest.add_argument("path", help="Path to a saved campaign JSON file.")
    dm_suggest.add_argument("--action", required=True, help="Player action to advise on.")
    dm_suggest.add_argument("--provider", choices=("mock", "openai-compatible"), default="openai-compatible")
    dm_suggest.add_argument("--mock-response", default=None, help="Path to mock provider output text.")
    dm_suggest.add_argument("--base-url", default=None, help="Override DND_AI_BASE_URL.")
    dm_suggest.add_argument("--model", default=None, help="Override DND_AI_MODEL.")
    dm_suggest.add_argument("--rules-corpus", default=None, help="Optional JSONL rules corpus.")
    dm_suggest.add_argument("--include-prompt", action="store_true", help="Print the prompt after the suggestion.")

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
    if args.command == "validate-adventure":
        adventure = load_adventure(args.path)
        validate_adventure(adventure)
        print(f"Adventure OK: {args.path}")
        print(f"Title: {adventure.campaign['title']}")
        print(f"Locations: {len(adventure.locations)}")
        return 0
    if args.command == "new-adventure":
        write_adventure_template(args.output, args.title)
        print(f"Wrote adventure template: {args.output}")
        return 0
    if args.command == "adventure-map":
        adventure = load_adventure(args.path)
        if args.format == "mermaid":
            print(render_mermaid_map(adventure))
        else:
            print(render_text_map(adventure))
        return 0
    if args.command == "review-adventure":
        adventure = load_adventure(args.path)
        if args.format == "json":
            print(render_adventure_review_json(adventure))
        else:
            print(render_adventure_review(adventure))
        return 0
    if args.command == "import-adventure":
        adventure = load_adventure(args.path)
        campaign = campaign_from_adventure(adventure)
        save_campaign(campaign, args.output)
        print(f"Imported adventure: {adventure.campaign['title']}")
        print(f"Wrote campaign state: {args.output}")
        return 0
    if args.command == "adventure-prompt":
        request = AdventureRequest(
            premise=args.premise,
            party_level=args.party_level,
            player_count=args.player_count,
            duration_hours=args.duration_hours,
            tone=args.tone,
            combat_ratio=args.combat_ratio,
            puzzle_ratio=args.puzzle_ratio,
        )
        rules_corpus = RuleCorpus.load_jsonl(args.rules_corpus) if args.rules_corpus else None
        rules_context = None
        if rules_corpus is not None:
            rules_context = rules_context_for_request(request, rules_corpus)
        print(build_adventure_prompt(request, rules_context))
        return 0
    if args.command == "clean-adventure-output":
        text = Path(args.input).read_text(encoding="utf-8")
        adventure = write_adventure_from_model_text(text, args.output)
        print(f"Adventure OK: {args.output}")
        print(f"Title: {adventure.campaign['title']}")
        return 0
    if args.command == "compile-adventure-output":
        text = Path(args.input).read_text(encoding="utf-8")
        adventure, campaign = write_campaign_from_model_text(text, args.adventure_output, args.campaign_output)
        print(f"Adventure OK: {args.adventure_output}")
        print(f"Campaign OK: {args.campaign_output}")
        print(f"Title: {campaign.title}")
        print(f"Locations: {len(campaign.locations)}")
        print(f"Encounters: {len(campaign.encounters)}")
        return 0
    if args.command == "generate-adventure":
        mock_response_text = None
        if args.mock_response is not None:
            mock_response_text = Path(args.mock_response).read_text(encoding="utf-8")
        provider = build_provider(
            args.provider,
            mock_response_text=mock_response_text,
            base_url=args.base_url,
            model=args.model,
            response_format="json_object" if args.json_response_format else None,
        )
        request = AdventureRequest(
            premise=args.premise,
            party_level=args.party_level,
            player_count=args.player_count,
            duration_hours=args.duration_hours,
            tone=args.tone,
            combat_ratio=args.combat_ratio,
            puzzle_ratio=args.puzzle_ratio,
        )
        adventure, campaign, review = generate_adventure_files(
            request,
            provider,
            args.adventure_output,
            args.campaign_output,
            max_attempts=args.max_attempts,
            rules_corpus=RuleCorpus.load_jsonl(args.rules_corpus) if args.rules_corpus else None,
        )
        print(f"Adventure OK: {args.adventure_output}")
        print(f"Campaign OK: {args.campaign_output}")
        print(f"Title: {campaign.title}")
        if args.review_format == "json":
            print(render_adventure_review_json(adventure))
        else:
            print(render_adventure_review(adventure))
        return 0
    if args.command == "initiative":
        print(run_initiative_demo(args.seed, args.rounds, args.scene))
        return 0
    if args.command == "combat":
        print(run_combat_demo(args.seed, args.scene, args.save_state))
        return 0
    if args.command == "state-summary":
        print(summarize_state(args.path))
        return 0
    if args.command == "play-adventure-state":
        campaign = load_campaign(args.path)
        if args.add_sample_character and not campaign.characters:
            campaign.add_character(sample_adventure_character())
        runtime = AdventureRuntime(campaign, rng=random.Random(args.seed))
        describe_current_location(runtime)
        if args.action:
            for action in args.action:
                if not handle_adventure_action(runtime, action):
                    break
            if args.save_state is not None:
                save_campaign(campaign, args.save_state)
                runtime.narrate(f"System: Saved campaign state to {args.save_state}.")
            print(runtime.flush())
            return 0
        print(runtime.flush())
        while True:
            action = input("> ")
            if not handle_adventure_action(runtime, action):
                print(runtime.flush())
                if args.save_state is not None:
                    save_campaign(campaign, args.save_state)
                    print(f"System: Saved campaign state to {args.save_state}.")
                return 0
            if runtime.transcript:
                print(runtime.flush())
    if args.command == "serve-api":
        print(f"Serving DND AI Assistant API on http://{args.host}:{args.port}")
        ai_provider = None
        if args.ai_provider != "none":
            mock_response_text = Path(args.mock_response).read_text(encoding="utf-8") if args.mock_response else None
            ai_provider = build_provider(
                args.ai_provider,
                mock_response_text=mock_response_text,
                base_url=args.base_url,
                model=args.model,
            )
        if args.rules_corpus:
            run_server(args.host, args.port, rules_corpus_path=args.rules_corpus, ai_provider=ai_provider)
        else:
            if ai_provider is not None:
                run_server(args.host, args.port, ai_provider=ai_provider)
            else:
                run_server(args.host, args.port)
        return 0
    if args.command == "build-rules-corpus":
        if args.source == "srd":
            corpus = build_srd_corpus(args.output, source_url=args.source_url or DEFAULT_SRD_URL)
            print(f"Wrote rules corpus: {args.output}")
            print(f"Chunks: {len(corpus.chunks)}")
            return 0
    if args.command == "search-rules":
        corpus = RuleCorpus.load_jsonl(args.corpus)
        print(format_search_results(corpus.search(args.query, limit=args.limit)))
        return 0
    if args.command == "dm-suggest":
        mock_response_text = Path(args.mock_response).read_text(encoding="utf-8") if args.mock_response else None
        provider = build_provider(
            args.provider,
            mock_response_text=mock_response_text,
            base_url=args.base_url,
            model=args.model,
        )
        suggestion = generate_dm_suggestion(
            load_campaign(args.path),
            args.action,
            provider,
            rules_corpus=RuleCorpus.load_jsonl(args.rules_corpus) if args.rules_corpus else None,
            include_prompt=args.include_prompt,
        )
        print(suggestion.text)
        if args.include_prompt:
            print("")
            print("Prompt:")
            print(suggestion.prompt)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
