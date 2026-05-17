import tempfile
import unittest
from pathlib import Path

from dnd_ai_assistant.rules_corpus import (
    RuleChunk,
    RuleCorpus,
    build_srd_corpus,
    chunks_from_html,
    format_search_results,
    render_rules_context,
)


def sample_chunks() -> list[RuleChunk]:
    return [
        RuleChunk(
            source_id="test",
            title="Test Rules",
            section="Grappling",
            text="When you want to grab a creature, you can use the Attack action to make a grapple.",
            url="https://example.test/grappling",
            license="test",
        ),
        RuleChunk(
            source_id="test",
            title="Test Rules",
            section="Spellcasting",
            text="A spellcaster uses spell slots to cast leveled spells and can maintain concentration.",
            url="https://example.test/spellcasting",
            license="test",
        ),
        RuleChunk(
            source_id="test",
            title="测试规则",
            section="擒抱",
            text="角色可以尝试擒抱一个生物。",
            url="https://example.test/cn",
            license="test",
        ),
    ]


class RuleCorpusTests(unittest.TestCase):
    def test_jsonl_round_trip_and_search_orders_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rules.jsonl"
            RuleCorpus(sample_chunks()).save_jsonl(path)

            corpus = RuleCorpus.load_jsonl(path)
            results = corpus.search("GRAPPLE attack grapple", limit=2)

        self.assertEqual(results[0].chunk.section, "Grappling")
        self.assertGreater(results[0].score, 0)
        self.assertEqual(results[0].to_dict()["section"], "Grappling")

    def test_load_jsonl_rejects_empty_and_bad_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.jsonl"
            bad = Path(tmp) / "bad.jsonl"
            empty.write_text("", encoding="utf-8")
            bad.write_text("{bad json", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "at least one chunk"):
                RuleCorpus.load_jsonl(empty)
            with self.assertRaisesRegex(ValueError, "Invalid JSONL"):
                RuleCorpus.load_jsonl(bad)

    def test_search_validates_query_and_supports_chinese_tokens(self) -> None:
        corpus = RuleCorpus(sample_chunks())

        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            corpus.search(" ")

        results = corpus.search("擒抱", limit=1)

        self.assertEqual(results[0].chunk.section, "擒抱")

    def test_chunks_from_html_cleans_markup_and_build_srd_uses_fetcher(self) -> None:
        html = """
        <html><body><h1>Combat</h1><p>Attack rolls decide whether attacks hit.</p>
        <script>ignore me</script><h2>Ability Checks</h2><p>Roll a d20.</p></body></html>
        """
        chunks = chunks_from_html(html, title="Fixture SRD", url="https://example.test/srd")

        self.assertEqual(chunks[0].section, "Combat")
        self.assertIn("Attack rolls", chunks[0].text)
        self.assertNotIn("ignore me", chunks[0].text)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "srd.jsonl"
            corpus = build_srd_corpus(path, source_url="https://example.test/srd", fetcher=lambda _: html)

            self.assertTrue(path.exists())
            self.assertGreaterEqual(len(corpus.chunks), 2)

    def test_rendering_helpers_show_source_and_context(self) -> None:
        corpus = RuleCorpus(sample_chunks())
        results = corpus.search("spell slots concentration")

        formatted = format_search_results(results)
        context = render_rules_context(results)

        self.assertIn("Spellcasting", formatted)
        self.assertIn("https://example.test/spellcasting", formatted)
        self.assertIn("spell slots", context)


if __name__ == "__main__":
    unittest.main()
