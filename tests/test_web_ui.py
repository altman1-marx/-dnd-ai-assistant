import unittest
from pathlib import Path


class WebUITests(unittest.TestCase):
    def test_index_references_core_api_endpoints_and_controls(self) -> None:
        html = Path("web/index.html").read_text(encoding="utf-8")

        self.assertIn("/health", html)
        self.assertIn("/campaigns/import", html)
        self.assertIn("/sample-character", html)
        self.assertIn("/summary", html)
        self.assertIn("/actions", html)
        self.assertIn('id="adventureFile"', html)
        self.assertIn('id="actionInput"', html)
        self.assertIn("data-action=\"cast sacred flame sprite\"", html)

    def test_index_does_not_depend_on_external_assets(self) -> None:
        html = Path("web/index.html").read_text(encoding="utf-8")

        self.assertNotIn("https://", html)
        self.assertNotIn("http://cdn", html.lower())
        self.assertNotIn("<script src=", html.lower())
        self.assertNotIn("<link rel=\"stylesheet\"", html.lower())


if __name__ == "__main__":
    unittest.main()
