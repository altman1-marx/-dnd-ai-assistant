import unittest

from dnd_ai_assistant.ai_keeper import build_keeper_prompt, generate_keeper_suggestion
from dnd_ai_assistant.ai_provider import MockProvider
from dnd_ai_assistant.coc_runtime import create_sample_coc_scenario


class AIKeeperTests(unittest.TestCase):
    def test_build_keeper_prompt_uses_coc_state_and_guardrails(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.inventory.append("Torn portrait canvas")
        scenario.session_log.extend(["Player: inspect portrait", "Keeper: Clue found - Scratched Portrait"])

        prompt = build_keeper_prompt(scenario, "talk to Mrs. Ember")

        self.assertIn("Call of Cthulhu 7th edition", prompt)
        self.assertIn("Do not mutate scenario state", prompt)
        self.assertIn("Briar House Study", prompt)
        self.assertIn("Mrs. Ember", prompt)
        self.assertIn("Torn portrait canvas", prompt)
        self.assertIn("Completion goals", prompt)
        self.assertIn("Deterministic keeper hint", prompt)
        self.assertIn("Recent session log", prompt)
        self.assertIn("Player: inspect portrait", prompt)
        self.assertIn("Clue found - Scratched Portrait", prompt)
        self.assertIn("clues 0/2", prompt)
        self.assertIn("talk to Mrs. Ember", prompt)


    def test_build_keeper_prompt_limits_recent_session_log(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.session_log = [f"Keeper: beat {index}" for index in range(20)]

        prompt = build_keeper_prompt(scenario, "look")

        self.assertIn("Recent session log", prompt)
        self.assertNotIn("beat 0", prompt)
        self.assertIn("beat 8", prompt)
        self.assertIn("beat 19", prompt)

    def test_build_keeper_prompt_includes_partial_leads_and_luck_costs(self) -> None:
        scenario = create_sample_coc_scenario()
        clue = scenario.clues[1]
        clue.partial_discovered = True
        clue.last_check_total = 50
        clue.last_required_total = 45
        clue.last_check_level = "failure"

        prompt = build_keeper_prompt(scenario, "what now?")

        self.assertIn("Partial leads", prompt)
        self.assertIn("Ashen Spiral", prompt)
        self.assertIn("Luck cost 5", prompt)
        self.assertIn("push ashen spiral", prompt)
        self.assertIn("spend luck ashen spiral", prompt)


    def test_build_keeper_prompt_prefers_listen_for_auditory_clues(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.current_location_id = "garden"

        prompt = build_keeper_prompt(scenario, "what do I hear?")

        self.assertIn("listen voices in the well", prompt)
        self.assertIn("listen voices in the well bonus", prompt)
        self.assertIn("search backward rain gauge", prompt)
        self.assertIn("check spot hidden penalty", prompt)


    def test_build_keeper_prompt_lists_executable_runtime_actions(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.current_location_id = "garden"

        prompt = build_keeper_prompt(scenario, "what now?")

        self.assertIn("san check 0/1d4", prompt)
        self.assertIn("listen voices in the well bonus", prompt)
        self.assertIn("check psychology penalty", prompt)
        self.assertIn("search backward rain gauge", prompt)
    def test_generate_keeper_suggestion_uses_provider_without_mutating_state(self) -> None:
        scenario = create_sample_coc_scenario()
        before_inventory = list(scenario.inventory)

        suggestion = generate_keeper_suggestion(
            scenario,
            "inspect the portrait",
            MockProvider("- Let the rain hush the room.\n- Recommend inspect portrait."),
            include_prompt=True,
        )

        self.assertIn("rain hush", suggestion.text)
        self.assertIn("Scenario state:", suggestion.prompt)
        self.assertEqual(scenario.inventory, before_inventory)

    def test_generate_keeper_suggestion_rejects_empty_action_and_response(self) -> None:
        scenario = create_sample_coc_scenario()

        with self.assertRaisesRegex(ValueError, "Action cannot be empty"):
            generate_keeper_suggestion(scenario, " ", MockProvider("ok"))
        with self.assertRaisesRegex(ValueError, "empty Keeper suggestion"):
            generate_keeper_suggestion(scenario, "look", MockProvider(" "))


if __name__ == "__main__":
    unittest.main()
