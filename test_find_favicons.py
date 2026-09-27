import unittest
from unittest.mock import patch

from find_favicons import discover, official_websites, resolve, resolve_candidates, main
import io
from contextlib import redirect_stdout, redirect_stderr


def statement(url, rank="normal", **extra):
    return dict(rank=rank, mainsnak={"snaktype": "value", "datavalue": {"value": url}}, **extra)


def entity(*claims):
    return {"claims": {"P856": list(claims)}}


class FaviconTests(unittest.TestCase):
    def test_direct_url_bypasses_lookup(self):
        with patch("find_favicons.wikidata") as api:
            self.assertEqual(resolve("example.com"), "https://example.com")
            api.assert_not_called()

    def test_statement_selection(self):
        data = entity(statement("https://old.com", qualifiers={"P582": []}),
                      statement("https://deprecated.com", "deprecated"),
                      statement("https://normal.com"),
                      statement("https://current.com", "preferred"))
        self.assertEqual(official_websites(data), ["https://current.com"])

    def test_brand_with_noncompany_name_match(self):
        with patch("find_favicons.wikidata", side_effect=[
            {"search": [{"id": "Q1", "label": "Nike"}, {"id": "Q2", "label": "Nike"}]},
            {"entities": {"Q1": entity(), "Q2": entity(statement("https://nike.com"))}},
        ]):
            self.assertEqual(resolve("Nike"), "https://nike.com")

    def test_ambiguous_brand(self):
        with patch("find_favicons.wikidata", side_effect=[
            {"search": [{"id": "Q1", "label": "Acme"}, {"id": "Q2", "label": "Acme"}]},
            {"entities": {"Q1": entity(statement("https://one.com")), "Q2": entity(statement("https://two.com"))}},
        ]):
            self.assertEqual(resolve_candidates("Acme"), ["https://one.com", "https://two.com"])

    def test_missing_brand(self):
        with patch("find_favicons.wikidata", return_value={"search": []}):
            with self.assertRaisesRegex(ValueError, "No result found"):
                resolve("Unknown Brand")

    def test_first_result_selected(self):
        with patch("find_favicons.resolve_candidates", return_value=["https://one.com", "https://two.com"]):
            self.assertEqual(resolve("Acme"), "https://one.com")

    def test_no_result_uses_stderr(self):
        out, err = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["find_favicons.py", "resolve-all", "Missing"]), patch("find_favicons.wikidata", return_value={"search": []}), redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(main(), 1)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("No result found", err.getvalue())

    def test_icon_discovery(self):
        html = '<base href="/assets/"><link rel="shortcut icon" sizes="16x16" href="a.ico"><link rel="icon" sizes="128x128" href="b.png">'
        self.assertEqual(list(discover("https://example.com/page", html)), [
            "https://example.com/assets/b.png", "https://example.com/assets/a.ico",
            "https://example.com/favicon.ico",
        ])


if __name__ == "__main__":
    unittest.main()
