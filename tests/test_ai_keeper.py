import unittest

from dnd_ai_assistant.ai_keeper import build_keeper_prompt, generate_keeper_suggestion
from dnd_ai_assistant.ai_provider import MockProvider
from dnd_ai_assistant.coc_runtime import create_sample_coc_scenario


class AIKeeperTests(unittest.TestCase):
    def test_build_keeper_prompt_uses_coc_state_and_guardrails(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.inventory.append("Torn portrait canvas")

        prompt = build_keeper_prompt(scenario, "talk to Mrs. Ember")

        self.assertIn("Call of Cthulhu 7th edition", prompt)
        self.assertIn("Do not mutate scenario state", prompt)
        self.assertIn("Briar House Study", prompt)
        self.assertIn("Mrs. Ember", prompt)
        self.assertIn("Torn portrait canvas", prompt)
        self.assertIn("Completion goals", prompt)
        self.assertIn("Deterministic keeper hint", prompt)
        self.assertIn("clues 0/2", prompt)
        self.assertIn("talk to Mrs. Ember", prompt)

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
