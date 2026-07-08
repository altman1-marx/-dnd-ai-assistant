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
    def test_inspection_aliases_search_read_and_listen(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.investigator.skills["psychology"] = 100
        runtime = COCRuntime(scenario, rng=random.Random(1))

        handle_coc_action(runtime, "read journal")
        handle_coc_action(runtime, "search portrait")
        handle_coc_action(runtime, "go garden")
        handle_coc_action(runtime, "listen to well")
        output = runtime.flush()

        self.assertIn("Waterlogged Journal", output)
        self.assertIn("Scratched Portrait", output)
        self.assertIn("Voices in the Well", output)
        self.assertIn("Recorded well whisper", scenario.inventory)

    def test_skill_gated_clue_failure_can_reveal_partial_lead(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.investigator.skills["spot hidden"] = 1
        runtime = COCRuntime(scenario, rng=random.Random(1))

        handle_coc_action(runtime, "inspect hearth")
        output = runtime.flush()

        self.assertIn("needs hard", output)
        self.assertIn("Partial clue - Ashen Spiral", output)
        self.assertIn("points toward the scratched portrait", output)
        self.assertFalse(scenario.clues[1].discovered)
        self.assertTrue(scenario.clues[1].partial_discovered)
        self.assertIn("Charcoal spiral rubbing", scenario.inventory)


    def test_skill_gated_clue_inspection_supports_bonus_and_penalty_dice(self) -> None:
        bonus_scenario = create_sample_coc_scenario()
        penalty_scenario = create_sample_coc_scenario()
        bonus_scenario.investigator.skills["spot hidden"] = 1
        penalty_scenario.investigator.skills["spot hidden"] = 1
        bonus_runtime = COCRuntime(bonus_scenario, rng=random.Random(1))
        penalty_runtime = COCRuntime(penalty_scenario, rng=random.Random(1))

        handle_coc_action(bonus_runtime, "inspect hearth bonus")
        handle_coc_action(penalty_runtime, "inspect hearth penalty")
        bonus_output = bonus_runtime.flush()
        penalty_output = penalty_runtime.flush()

        self.assertIn("rolls spot hidden (bonus die)", bonus_output)
        self.assertIn("rolls spot hidden (penalty die)", penalty_output)
        self.assertTrue(bonus_scenario.clues[1].partial_discovered)
        self.assertTrue(penalty_scenario.clues[1].partial_discovered)
    def test_spend_luck_can_convert_failed_clue_check(self) -> None:
        scenario = create_sample_coc_scenario()
        clue = scenario.clues[1]
        clue.partial_discovered = True
        clue.last_check_total = 50
        clue.last_required_total = 45
        clue.last_check_level = "failure"
        runtime = COCRuntime(scenario)

        handle_coc_action(runtime, "spend luck hearth")
        output = runtime.flush()

        self.assertIn("spends 5 Luck", output)
        self.assertEqual(scenario.investigator.luck, 45)
        self.assertTrue(clue.discovered)
        self.assertIsNone(clue.last_check_total)

    def test_spend_luck_reports_insufficient_luck_and_fumble(self) -> None:
        scenario = create_sample_coc_scenario()
        clue = scenario.clues[1]
        clue.partial_discovered = True
        clue.last_check_total = 90
        clue.last_required_total = 20
        clue.last_check_level = "failure"
        runtime = COCRuntime(scenario)

        handle_coc_action(runtime, "spend luck hearth")
        low_luck_output = runtime.flush()
        clue.last_check_total = 96
        clue.last_required_total = 45
        clue.last_check_level = "fumble"
        handle_coc_action(runtime, "spend luck hearth")
        fumble_output = runtime.flush()

        self.assertIn("needs 70 Luck", low_luck_output)
        self.assertFalse(clue.discovered)
        self.assertIn("cannot erase a fumble", fumble_output)


    def test_push_roll_can_turn_partial_clue_into_full_clue(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.investigator.skills["spot hidden"] = 1
        runtime = COCRuntime(scenario, rng=random.Random(1))

        handle_coc_action(runtime, "inspect hearth")
        runtime.flush()
        scenario.investigator.skills["spot hidden"] = 99
        handle_coc_action(runtime, "push hearth")
        output = runtime.flush()

        self.assertIn("pushed investigation pays off", output)
        self.assertTrue(scenario.clues[1].discovered)
        self.assertTrue(scenario.clues[1].push_attempted)
        self.assertIn("Ash rubbing", scenario.inventory)

    def test_push_roll_failure_has_consequence_and_cannot_repeat(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.investigator.skills["spot hidden"] = 1
        runtime = COCRuntime(scenario, rng=random.Random(1))

        handle_coc_action(runtime, "inspect hearth")
        runtime.flush()
        handle_coc_action(runtime, "push hearth")
        first_output = runtime.flush()
        handle_coc_action(runtime, "push hearth")
        second_output = runtime.flush()

        self.assertIn("Push roll fails", first_output)
        self.assertIn("rattled", scenario.investigator.conditions)
        self.assertEqual(scenario.investigator.current_sanity, 59)
        self.assertTrue(scenario.clues[1].push_attempted)
        self.assertIn("already been pushed", second_output)


    def test_skill_gated_clue_without_failure_text_still_blocks_on_failure(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.clues[1].failure_text = None
        scenario.clues[1].failure_evidence = None
        scenario.investigator.skills["spot hidden"] = 1
        runtime = COCRuntime(scenario, rng=random.Random(1))

        handle_coc_action(runtime, "inspect hearth")
        output = runtime.flush()

        self.assertIn("does not come together", output)
        self.assertFalse(scenario.clues[1].discovered)
        self.assertFalse(scenario.clues[1].partial_discovered)

    def test_partial_clues_are_reported_in_clues_status_and_recap(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.investigator.skills["spot hidden"] = 1
        runtime = COCRuntime(scenario, rng=random.Random(1))

        handle_coc_action(runtime, "inspect hearth")
        runtime.flush()
        handle_coc_action(runtime, "clues")
        clues_output = runtime.flush()
        handle_coc_action(runtime, "status")
        status_output = runtime.flush()
        handle_coc_action(runtime, "recap")
        recap_output = runtime.flush()

        self.assertIn("Partial lead - Ashen Spiral", clues_output)
        self.assertIn("partial 1", status_output)
        self.assertIn("partial 1", recap_output)


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

    def test_conclude_requires_completion_goals(self) -> None:
        scenario = create_sample_coc_scenario()
        runtime = COCRuntime(scenario)

        handle_coc_action(runtime, "conclude")
        output = runtime.flush()

        self.assertFalse(scenario.completed)
        self.assertIn("cannot be concluded", output)
        self.assertIn("Ending progress", output)

    def test_conclude_can_close_case_when_requirements_are_met(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.completed = False
        for clue in scenario.clues:
            if clue.id in {"portrait_truth", "lantern_wick"}:
                clue.discovered = True
        scenario.inventory.append("Black wick sample")
        scenario.current_location_id = "cellar"
        runtime = COCRuntime(scenario)

        handle_coc_action(runtime, "solve case")
        output = runtime.flush()

        self.assertTrue(scenario.completed)
        self.assertIn("close the case", output)
        self.assertIn("The lantern waits below", output)

    def test_garden_branch_has_constable_and_optional_clues(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.investigator.skills["spot hidden"] = 100
        runtime = COCRuntime(scenario, rng=random.Random(1))

        handle_coc_action(runtime, "go garden")
        handle_coc_action(runtime, "talk hale")
        handle_coc_action(runtime, "inspect rain gauge")
        output = runtime.flush()

        self.assertEqual(scenario.current_location_id, "garden")
        self.assertIn("Rain-Drowned Garden", output)
        self.assertIn("Constable Hale", output)
        self.assertIn("Backward Rain Gauge", output)
        self.assertIn("Backward rain gauge sketch", scenario.inventory)




    def test_sanity_check_rolls_loss_expression(self) -> None:
        scenario = create_sample_coc_scenario()
        runtime = COCRuntime(scenario, rng=random.Random(1))

        handle_coc_action(runtime, "san check 0/1d4")
        output = runtime.flush()

        self.assertIn("rolls SAN", output)
        self.assertIn("SAN loss", output)
        self.assertLessEqual(scenario.investigator.current_sanity, scenario.investigator.max_sanity)
        self.assertIn("SAN", output)


    def test_sanity_check_reports_new_insanity_condition(self) -> None:
        scenario = create_sample_coc_scenario()
        runtime = COCRuntime(scenario, rng=random.Random(1))

        handle_coc_action(runtime, "san check 5/5")
        output = runtime.flush()

        self.assertIn("SAN condition gained - temporary_insanity", output)
        self.assertIn("temporary_insanity", scenario.investigator.conditions)

    def test_sanity_check_reports_bad_format(self) -> None:
        runtime = COCRuntime(create_sample_coc_scenario())

        handle_coc_action(runtime, "san check 1d4")
        output = runtime.flush()

        self.assertIn("Use san check <success loss>/<failure loss>", output)

    def test_manual_check_reports_success_thresholds(self) -> None:
        scenario = create_sample_coc_scenario()
        runtime = COCRuntime(scenario, rng=random.Random(1))

        handle_coc_action(runtime, "check psychology")
        output = runtime.flush()

        self.assertIn("rolls psychology", output)
        self.assertIn("targets regular 35, hard 17, extreme 7", output)


    def test_manual_check_supports_bonus_and_penalty_dice(self) -> None:
        bonus_runtime = COCRuntime(create_sample_coc_scenario(), rng=random.Random(1))
        penalty_runtime = COCRuntime(create_sample_coc_scenario(), rng=random.Random(1))

        handle_coc_action(bonus_runtime, "check psychology bonus")
        handle_coc_action(penalty_runtime, "check psychology penalty")
        bonus_output = bonus_runtime.flush()
        penalty_output = penalty_runtime.flush()

        self.assertIn("rolls psychology (bonus die)", bonus_output)
        self.assertIn("rolls psychology (penalty die)", penalty_output)
        self.assertIn("targets regular 35, hard 17, extreme 7", bonus_output)
        self.assertIn("targets regular 35, hard 17, extreme 7", penalty_output)

    def test_note_actions_record_session_context(self) -> None:
        scenario = create_sample_coc_scenario()
        runtime = COCRuntime(scenario)

        handle_coc_action(runtime, "note I suspect the rain gauge")
        handle_coc_action(runtime, "keeper note Hale is hiding fear")
        output = runtime.flush()

        self.assertIn("Player note: I suspect the rain gauge", output)
        self.assertIn("Keeper note: Hale is hiding fear", output)
        self.assertIn("Player note: I suspect the rain gauge", scenario.session_log)
        self.assertIn("Keeper note: Hale is hiding fear", scenario.session_log)

    def test_help_and_quit(self) -> None:
        runtime = COCRuntime(create_sample_coc_scenario())

        self.assertTrue(handle_coc_action(runtime, "help"))
        self.assertFalse(handle_coc_action(runtime, "quit"))
        output = runtime.flush()

        self.assertIn("Actions:", output)
        self.assertIn("note <text>", output)
        self.assertIn("san check <success>/<failure>", output)
        self.assertIn("investigation pauses", output)

    def test_hint_points_to_next_completion_step(self) -> None:
        scenario = create_sample_coc_scenario()
        runtime = COCRuntime(scenario)

        handle_coc_action(runtime, "hint")
        output = runtime.flush()

        self.assertIn("Hint", output)
        self.assertIn("inspect scratched portrait", output)
    def test_hint_uses_natural_actions_for_clue_types(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.completion_requirements = {}
        runtime = COCRuntime(scenario)

        handle_coc_action(runtime, "hint")
        study_output = runtime.flush()
        scenario.current_location_id = "garden"
        for clue in scenario.clues:
            if clue.id == "rain_gauge":
                clue.discovered = True
        handle_coc_action(runtime, "hint")
        garden_output = runtime.flush()

        self.assertIn("read waterlogged journal", study_output)
        self.assertIn("listen voices in the well", garden_output)

    def test_hint_moves_to_next_location_after_gate_clue(self) -> None:
        scenario = create_sample_coc_scenario()
        runtime = COCRuntime(scenario)

        handle_coc_action(runtime, "inspect portrait")
        runtime.flush()
        handle_coc_action(runtime, "hint")
        output = runtime.flush()

        self.assertIn("Briar House Cellar", output)


    def test_recap_reports_state_and_next_lead(self) -> None:
        scenario = create_sample_coc_scenario()
        runtime = COCRuntime(scenario)

        handle_coc_action(runtime, "inspect portrait")
        runtime.flush()
        handle_coc_action(runtime, "recap")
        output = runtime.flush()

        self.assertIn("Recap", output)
        self.assertIn("Briar House Study", output)
        self.assertIn("clues 1/6", output)
        self.assertIn("Scratched Portrait", output)
        self.assertIn("Next lead", output)


    def test_progress_reports_completion_requirements(self) -> None:
        scenario = create_sample_coc_scenario()
        runtime = COCRuntime(scenario)

        handle_coc_action(runtime, "progress")
        output = runtime.flush()

        self.assertIn("Ending progress", output)
        self.assertIn("clues 0/2", output)
        self.assertIn("evidence 0/1", output)
        self.assertIn("locations 0/1", output)

    def test_skills_action_lists_investigator_skills(self) -> None:
        runtime = COCRuntime(create_sample_coc_scenario())

        handle_coc_action(runtime, "skills")
        output = runtime.flush()

        self.assertIn("Eleanor Vale skills", output)
        self.assertIn("library use 55", output)
        self.assertIn("spot hidden 45", output)


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
        self.assertIn("clues 1/6", output)
        self.assertIn("evidence 0", output)

    def test_manual_damage_and_healing_update_hp_conditions(self) -> None:
        scenario = create_sample_coc_scenario()
        runtime = COCRuntime(scenario, rng=random.Random(1))

        handle_coc_action(runtime, "take damage 20")
        damage_output = runtime.flush()
        damage_conditions = set(scenario.investigator.conditions)
        handle_coc_action(runtime, "heal 1")
        heal_output = runtime.flush()

        self.assertIn("takes 20 damage", damage_output)
        self.assertIn("Physical condition gained", damage_output)
        self.assertIn("major_wound", damage_conditions)
        self.assertIn("dying", damage_conditions)
        self.assertIn("unconscious", damage_conditions)
        self.assertNotIn("dying", scenario.investigator.conditions)
        self.assertNotIn("unconscious", scenario.investigator.conditions)
        self.assertIn("recovers 1 HP", heal_output)
        self.assertEqual(scenario.investigator.current_hp, 1)

    def test_manual_damage_reports_invalid_expression(self) -> None:
        runtime = COCRuntime(create_sample_coc_scenario())

        handle_coc_action(runtime, "take damage not dice")
        output = runtime.flush()

        self.assertIn("Damage expression is invalid", output)

    def test_first_aid_can_restore_one_hp(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.investigator.apply_damage(3)
        scenario.investigator.skills["first aid"] = 100
        runtime = COCRuntime(scenario, rng=random.Random(1))

        handle_coc_action(runtime, "first aid")
        output = runtime.flush()

        self.assertIn("rolls first aid", output)
        self.assertIn("restores 1 HP", output)
        self.assertEqual(scenario.investigator.current_hp, scenario.investigator.max_hp - 2)

    def test_first_aid_reports_full_hp_and_failure(self) -> None:
        scenario = create_sample_coc_scenario()
        runtime = COCRuntime(scenario, rng=random.Random(1))

        handle_coc_action(runtime, "first aid")
        full_output = runtime.flush()
        scenario.investigator.apply_damage(2)
        scenario.investigator.skills["first aid"] = 0
        handle_coc_action(runtime, "first aid")
        failed_output = runtime.flush()

        self.assertIn("does not need first aid", full_output)
        self.assertIn("wound remains untreated", failed_output)
        self.assertEqual(scenario.investigator.current_hp, scenario.investigator.max_hp - 2)


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
