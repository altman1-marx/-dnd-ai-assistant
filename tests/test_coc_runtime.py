import random
import unittest

from dnd_ai_assistant.coc_runtime import COCRuntime, create_sample_coc_scenario, describe_coc_scene, handle_coc_action


class COCRuntimeTests(unittest.TestCase):
    def test_describe_scene_shows_investigator_state(self) -> None:
        runtime = COCRuntime(create_sample_coc_scenario())

        describe_coc_scene(runtime)
        output = runtime.flush()

        self.assertIn("The Lantern Under Briar House", output)
        self.assertIn("Briar House Study", output)
        self.assertIn("Exits: cellar", output)
        self.assertIn("Present: Mrs. Ember", output)
        self.assertIn("SAN 60/60", output)

    def test_inspect_reveals_obvious_clue_and_applies_sanity_loss(self) -> None:
        scenario = create_sample_coc_scenario()
        runtime = COCRuntime(scenario, rng=random.Random(1))

        handle_coc_action(runtime, "inspect portrait")
        output = runtime.flush()

        self.assertIn("Clue found - Scratched Portrait", output)
        self.assertIn("SAN loss 2", output)
        self.assertIn("Evidence collected - Torn portrait canvas", output)
        self.assertEqual(scenario.investigator.current_sanity, 58)
        self.assertEqual(scenario.inventory, ["Torn portrait canvas"])

    def test_skill_gated_clue_can_fail(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.investigator.skills["spot hidden"] = 1
        runtime = COCRuntime(scenario, rng=random.Random(1))

        handle_coc_action(runtime, "inspect hearth")
        output = runtime.flush()

        self.assertIn("needs hard", output)
        self.assertIn("does not come together", output)
        self.assertFalse(scenario.clues[1].discovered)

    def test_all_clues_revealed_triggers_ending(self) -> None:
        scenario = create_sample_coc_scenario()
        for clue in scenario.clues:
            clue.skill = None
        runtime = COCRuntime(scenario)

        handle_coc_action(runtime, "inspect journal")
        runtime.flush()
        handle_coc_action(runtime, "inspect hearth")
        runtime.flush()
        handle_coc_action(runtime, "inspect portrait")
        runtime.flush()
        handle_coc_action(runtime, "go cellar")
        runtime.flush()
        handle_coc_action(runtime, "inspect lantern")
        output = runtime.flush()

        self.assertIn("The lantern waits below", output)
        self.assertTrue(scenario.completed)

    def test_completion_requirements_trigger_ending_without_all_clues(self) -> None:
        scenario = create_sample_coc_scenario()
        runtime = COCRuntime(scenario)

        handle_coc_action(runtime, "inspect portrait")
        runtime.flush()
        handle_coc_action(runtime, "go cellar")
        runtime.flush()
        handle_coc_action(runtime, "inspect lantern")
        output = runtime.flush()

        self.assertTrue(scenario.completed)
        self.assertFalse(scenario.clues[0].discovered)
        self.assertIn("The lantern waits below", output)

    def test_completion_requirements_can_require_npc_conversation(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.completion_requirements = {"required_npc_ids": ["mrs_ember"]}
        runtime = COCRuntime(scenario)

        handle_coc_action(runtime, "talk ember")
        output = runtime.flush()

        self.assertTrue(scenario.completed)
        self.assertIn("The lantern waits below", output)


    def test_help_and_quit(self) -> None:
        runtime = COCRuntime(create_sample_coc_scenario())

        self.assertTrue(handle_coc_action(runtime, "help"))
        self.assertFalse(handle_coc_action(runtime, "quit"))
        output = runtime.flush()

        self.assertIn("Actions:", output)
        self.assertIn("investigation pauses", output)

    def test_hint_points_to_next_completion_step(self) -> None:
        scenario = create_sample_coc_scenario()
        runtime = COCRuntime(scenario)

        handle_coc_action(runtime, "hint")
        output = runtime.flush()

        self.assertIn("Hint", output)
        self.assertIn("inspect scratched portrait", output)

    def test_hint_moves_to_next_location_after_gate_clue(self) -> None:
        scenario = create_sample_coc_scenario()
        runtime = COCRuntime(scenario)

        handle_coc_action(runtime, "inspect portrait")
        runtime.flush()
        handle_coc_action(runtime, "hint")
        output = runtime.flush()

        self.assertIn("Briar House Cellar", output)


    def test_progress_reports_completion_requirements(self) -> None:
        scenario = create_sample_coc_scenario()
        runtime = COCRuntime(scenario)

        handle_coc_action(runtime, "progress")
        output = runtime.flush()

        self.assertIn("Ending progress", output)
        self.assertIn("clues 0/2", output)
        self.assertIn("evidence 0/1", output)
        self.assertIn("locations 0/1", output)


    def test_status_reports_resources_and_clue_progress(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.clues[0].discovered = True
        runtime = COCRuntime(scenario)

        handle_coc_action(runtime, "status")
        output = runtime.flush()

        self.assertIn("HP 11/11", output)
        self.assertIn("MP 12/12", output)
        self.assertIn("SAN 60/60", output)
        self.assertIn("location Briar House Study", output)
        self.assertIn("clues 1/4", output)
        self.assertIn("evidence 0", output)

    def test_go_moves_between_locations_and_reveals_local_clues(self) -> None:
        scenario = create_sample_coc_scenario()
        runtime = COCRuntime(scenario)

        handle_coc_action(runtime, "inspect portrait")
        runtime.flush()
        handle_coc_action(runtime, "go cellar")
        handle_coc_action(runtime, "inspect lantern")
        output = runtime.flush()

        self.assertEqual(scenario.current_location_id, "cellar")
        self.assertIn("You move to Briar House Cellar", output)
        self.assertIn("Clue found - Black Wick", output)

    def test_go_can_be_blocked_by_exit_requirements(self) -> None:
        scenario = create_sample_coc_scenario()
        runtime = COCRuntime(scenario)

        handle_coc_action(runtime, "go cellar")
        output = runtime.flush()

        self.assertEqual(scenario.current_location_id, "study")
        self.assertIn("portrait passage is still hidden", output)

    def test_inspect_cannot_find_clue_in_other_location(self) -> None:
        runtime = COCRuntime(create_sample_coc_scenario())

        handle_coc_action(runtime, "inspect lantern")
        output = runtime.flush()

        self.assertIn("no clear lead", output)

    def test_inventory_lists_collected_evidence(self) -> None:
        scenario = create_sample_coc_scenario()
        runtime = COCRuntime(scenario)

        handle_coc_action(runtime, "inspect portrait")
        runtime.flush()
        handle_coc_action(runtime, "inventory")
        output = runtime.flush()

        self.assertIn("Evidence: Torn portrait canvas", output)

    def test_talk_to_visible_npc(self) -> None:
        runtime = COCRuntime(create_sample_coc_scenario())

        handle_coc_action(runtime, "talk ember")
        output = runtime.flush()

        self.assertIn("Mrs. Ember", output)
        self.assertIn("forbade us from trimming", output)

    def test_talk_cannot_reach_npc_in_other_location(self) -> None:
        runtime = COCRuntime(create_sample_coc_scenario())

        handle_coc_action(runtime, "inspect portrait")
        runtime.flush()
        handle_coc_action(runtime, "go cellar")
        runtime.flush()
        handle_coc_action(runtime, "talk ember")
        output = runtime.flush()

        self.assertIn("No one by that name", output)


if __name__ == "__main__":
    unittest.main()
