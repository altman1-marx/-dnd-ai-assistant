import unittest

from dnd_ai_assistant.adventure import AdventureDefinition, create_adventure_template
from dnd_ai_assistant.adventure_importer import campaign_from_adventure
from dnd_ai_assistant.ai_dm import build_dm_prompt, generate_dm_suggestion
from dnd_ai_assistant.ai_provider import MockProvider
from dnd_ai_assistant.rules_corpus import RuleChunk, RuleCorpus


class AIDMTests(unittest.TestCase):
    def test_build_dm_prompt_uses_campaign_state_and_guardrails(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))

        prompt = build_dm_prompt(campaign, "inspect the ash", "Ability Checks: Roll a d20.")

        self.assertIn("Do not mutate campaign state", prompt)
        self.assertIn("Moonlit Road", prompt)
        self.assertIn("inspect the ash", prompt)
        self.assertIn("Ability Checks", prompt)

    def test_build_dm_prompt_includes_active_combat_targets(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        campaign.active_combat = {
            "round": 2,
            "turn": "Leth",
            "initiative": [
                {"name": "Leth", "initiative_total": 18, "is_player": True, "current_hp": 24},
                {"name": "Lantern Sprite", "initiative_total": 12, "is_player": False, "current_hp": 7},
            ],
        }

        prompt = build_dm_prompt(campaign, "cast guiding bolt lantern sprite")

        self.assertIn("Combat round: 2", prompt)
        self.assertIn("Combat turn: Leth", prompt)
        self.assertIn("Targetable enemies: Lantern Sprite", prompt)
        self.assertIn("Targetable allies: none", prompt)

    def test_build_dm_prompt_excludes_defeated_targets(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        campaign.active_combat = {
            "round": 2,
            "turn": "Leth",
            "initiative": [
                {"name": "Leth", "initiative_total": 18, "is_player": True, "current_hp": 24},
                {"name": "Fallen Sprite", "initiative_total": 12, "is_player": False, "current_hp": 0},
            ],
        }

        prompt = build_dm_prompt(campaign, "attack fallen sprite")

        self.assertIn("Fallen Sprite HP 0", prompt)
        self.assertIn("Targetable enemies: none", prompt)

    def test_generate_dm_suggestion_uses_provider_and_rules_without_mutating_state(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))
        before_events = len(campaign.session_log)
        corpus = RuleCorpus(
            [
                RuleChunk(
                    source_id="test",
                    title="Test Rules",
                    section="Ability Checks",
                    text="Ability checks use a d20.",
                    url="https://example.test/checks",
                    license="test",
                )
            ]
        )

        suggestion = generate_dm_suggestion(
            campaign,
            "inspect the ash",
            MockProvider("- Describe the ash.\n- Ask for a Wisdom check."),
            rules_corpus=corpus,
            include_prompt=True,
        )

        self.assertIn("Describe the ash", suggestion.text)
        self.assertEqual(suggestion.rules[0].chunk.section, "Ability Checks")
        self.assertIn("Relevant rules:", suggestion.prompt)
        self.assertEqual(len(campaign.session_log), before_events)

    def test_generate_dm_suggestion_rejects_empty_action_and_empty_response(self) -> None:
        campaign = campaign_from_adventure(AdventureDefinition(create_adventure_template("Moonlit Road")))

        with self.assertRaisesRegex(ValueError, "Action cannot be empty"):
            generate_dm_suggestion(campaign, " ", MockProvider("ok"))
        with self.assertRaisesRegex(ValueError, "empty DM suggestion"):
            generate_dm_suggestion(campaign, "look", MockProvider(" "))


if __name__ == "__main__":
    unittest.main()
