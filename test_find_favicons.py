import unittest
from unittest.mock import patch

from find_favicons import discover, official_websites, resolve


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
            with self.assertRaisesRegex(ValueError, "Multiple websites"):
                resolve("Acme")

    def test_missing_brand(self):
        with patch("find_favicons.wikidata", return_value={"search": []}):
            with self.assertRaisesRegex(ValueError, "No brand found"):
                resolve("Unknown Brand")

    def test_icon_discovery(self):
        html = '<base href="/assets/"><link rel="shortcut icon" sizes="16x16" href="a.ico"><link rel="icon" sizes="128x128" href="b.png">'
        self.assertEqual(list(discover("https://example.com/page", html)), [
            "https://example.com/assets/b.png", "https://example.com/assets/a.ico",
            "https://example.com/favicon.ico",
        ])


if __name__ == "__main__":
    unittest.main()
