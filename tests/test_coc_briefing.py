import random
import unittest

from dnd_ai_assistant.coc_briefing import build_coc_briefing, render_coc_briefing
from dnd_ai_assistant.coc_runtime import COCRuntime, create_sample_coc_scenario, handle_coc_action


class COCBriefingTests(unittest.TestCase):
    def test_briefing_summarizes_keeper_state_and_hidden_clues(self) -> None:
        scenario = create_sample_coc_scenario()
        briefing = build_coc_briefing(scenario)

        self.assertEqual(briefing["title"], "The Lantern Under Briar House")
        self.assertEqual(briefing["location"]["name"], "Briar House Study")
        self.assertEqual(briefing["investigator"]["name"], "Eleanor Vale")
        self.assertEqual(briefing["progress"]["discovered_clues"], 0)
        self.assertEqual(briefing["progress"]["total_clues"], 6)
        self.assertTrue(briefing["location"]["blocked_exits"])
        self.assertTrue(briefing["keeper_notes"]["hidden_clues"])
        self.assertIn("Hidden clue queue", briefing["text"])
        self.assertIn("Next Keeper moves", briefing["text"])
        self.assertTrue(briefing["open_threads"])
        self.assertIn("Blocked route: cellar.", briefing["open_threads"])
        self.assertTrue(briefing["spotlight_actions"])
        self.assertIn("read waterlogged journal", briefing["spotlight_actions"])
        self.assertIn("Open threads", briefing["text"])
        self.assertIn("Spotlight actions", briefing["text"])

    def test_briefing_reports_partial_leads_risks_and_recent_log(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.investigator.skills["spot hidden"] = 1
        runtime = COCRuntime(scenario, rng=random.Random(1))
        handle_coc_action(runtime, "inspect hearth")

        briefing = build_coc_briefing(scenario)

        self.assertEqual(briefing["progress"]["partial_clues"], 1)
        self.assertEqual(briefing["keeper_notes"]["partial_leads"][0]["title"], "Ashen Spiral")
        self.assertTrue(any("blocked" in risk for risk in briefing["risks"]))
        self.assertTrue(any("push roll" in action.lower() for action in briefing["next_actions"]))
        self.assertIn("Partial lead unresolved: Ashen Spiral.", briefing["open_threads"])
        self.assertIn("push ashen spiral", briefing["spotlight_actions"])
        self.assertIn("spend luck ashen spiral", briefing["spotlight_actions"])
        self.assertIn("Partial leads", briefing["text"])
        self.assertIn("Recent table log", briefing["text"])
        self.assertIn("Player: inspect hearth", briefing["text"])

    def test_render_briefing_handles_completed_case(self) -> None:
        scenario = create_sample_coc_scenario()
        scenario.completed = True
        briefing = build_coc_briefing(scenario)
        text = render_coc_briefing(briefing)

        self.assertIn("completed", " ".join(briefing["risks"]).lower())
        self.assertIn("COC Keeper Briefing", text)


if __name__ == "__main__":
    unittest.main()
