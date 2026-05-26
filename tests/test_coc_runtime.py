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
        self.assertIn("SAN 60/60", output)

    def test_inspect_reveals_obvious_clue_and_applies_sanity_loss(self) -> None:
        scenario = create_sample_coc_scenario()
        runtime = COCRuntime(scenario, rng=random.Random(1))

        handle_coc_action(runtime, "inspect portrait")
        output = runtime.flush()

        self.assertIn("Clue found - Scratched Portrait", output)
        self.assertIn("SAN loss 2", output)
        self.assertEqual(scenario.investigator.current_sanity, 58)

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

    def test_help_and_quit(self) -> None:
        runtime = COCRuntime(create_sample_coc_scenario())

        self.assertTrue(handle_coc_action(runtime, "help"))
        self.assertFalse(handle_coc_action(runtime, "quit"))
        output = runtime.flush()

        self.assertIn("Actions:", output)
        self.assertIn("investigation pauses", output)

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

    def test_go_moves_between_locations_and_reveals_local_clues(self) -> None:
        scenario = create_sample_coc_scenario()
        runtime = COCRuntime(scenario)

        handle_coc_action(runtime, "go cellar")
        handle_coc_action(runtime, "inspect lantern")
        output = runtime.flush()

        self.assertEqual(scenario.current_location_id, "cellar")
        self.assertIn("You move to Briar House Cellar", output)
        self.assertIn("Clue found - Black Wick", output)

    def test_inspect_cannot_find_clue_in_other_location(self) -> None:
        runtime = COCRuntime(create_sample_coc_scenario())

        handle_coc_action(runtime, "inspect lantern")
        output = runtime.flush()

        self.assertIn("no clear lead", output)


if __name__ == "__main__":
    unittest.main()
