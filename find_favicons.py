"""Normalize website URLs and discover favicon candidates using only the stdlib."""

import re
import json
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit


def wikidata(**params):
    url = "https://www.wikidata.org/w/api.php?" + urlencode(dict(format="json", **params))
    result = subprocess.run([
        "/usr/bin/curl", "--fail", "--silent", "--show-error",
        "--connect-timeout", "5", "--max-time", "20",
        "--user-agent", "FaviconGrabber/1.0 (personal Raycast script)", url,
    ], capture_output=True, text=True)
    if result.returncode:
        raise ValueError("Wikidata lookup failed. Try again or enter the website domain.")
    data = json.loads(result.stdout)
    if "error" in data:
        raise ValueError("Wikidata could not complete the lookup. Enter the website domain.")
    return data


def official_websites(entity):
    websites = []
    for claim in entity.get("claims", {}).get("P856", []):
        if claim.get("rank") == "deprecated" or "P582" in claim.get("qualifiers", {}):
            continue  # Ignore deprecated and explicitly ended website statements.
        snak = claim.get("mainsnak", {})
        if snak.get("snaktype") != "value":
            continue
        value = snak.get("datavalue", {}).get("value")
        if not isinstance(value, str):
            continue
        try:
            websites.append((claim.get("rank") == "preferred", normalize(value)))
        except ValueError:
            continue
    if any(preferred for preferred, _ in websites):
        websites = [(preferred, url) for preferred, url in websites if preferred]
    return list(dict.fromkeys(url for _, url in websites))


def resolve(value):
    value = value.strip()
    if not value:
        raise ValueError("Enter a brand name, domain, or website URL.")
    if "://" in value or value.startswith("//") or (not re.search(r"\s", value) and ("." in value or ":" in value or "/" in value or value == "localhost")):
        return normalize(value)
    results = wikidata(action="wbsearchentities", search=value, language="en", type="item", limit=10).get("search", [])
    if not results:
        raise ValueError("No brand found on Wikidata. Enter the website domain instead.")
    entities = wikidata(action="wbgetentities", ids="|".join(item["id"] for item in results), props="claims").get("entities", {})
    candidates = []
    for item in results:
        websites = official_websites(entities.get(item["id"], {}))
        for url in websites:
            exact = value.casefold() in {item.get("label", "").casefold(), item.get("match", {}).get("text", "").casefold()}
            candidates.append((exact, item.get("label", item["id"]), url))
    exact = [candidate for candidate in candidates if candidate[0]]
    if exact:
        candidates = exact
    domains = {urlsplit(url).hostname.removeprefix("www.") for _, _, url in candidates}
    if len(domains) == 1:
        return candidates[0][2]
    if not candidates:
        raise ValueError("No current official website (P856) found on Wikidata. Enter a domain instead.")
    choices = "; ".join(dict.fromkeys(f"{name}: {urlsplit(url).hostname}" for _, name, url in candidates))
    raise ValueError("Multiple websites found. Run again with a domain: " + choices)


def normalize(value):
    value = value.strip()
    if not value or re.search(r"[\s\x00-\x1f\x7f]", value):
        raise ValueError("Enter a domain or full website URL, such as example.com.")
    if value.startswith("//"):
        value = "https:" + value
    elif "://" not in value:
        value = "https://" + value
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("Enter a valid HTTP or HTTPS website URL.")
    if parts.username is not None or parts.password is not None:
        raise ValueError("URLs containing credentials are not supported.")
    _ = parts.port  # Validate the port before invoking curl.
    return urlunsplit(parts._replace(fragment=""))


class IconParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.base = None
        self.icons = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        href = attrs.get("href")
        if href is None:
            return
        if tag == "base" and self.base is None:
            self.base = href.strip()
        if tag != "link":
            return
        rel = (attrs.get("rel") or "").lower().split()
        if "icon" in rel:
            group = 0
        elif any(r in rel for r in ("apple-touch-icon", "apple-touch-icon-precomposed")):
            group = 1
        else:
            return
        if "svg" in (attrs.get("type") or "").lower():
            return
        sizes = re.findall(r"(?:^|\s)(\d+)x(\d+)(?=\s|$)", (attrs.get("sizes") or "").lower())
        area = max((int(w) * int(h) for w, h in sizes), default=0)
        self.icons.append((group, -area, href.strip()))

    handle_startendtag = handle_starttag


def discover(page_url, html):
    parser = IconParser()
    parser.feed(html)
    try:
        base = urljoin(page_url, parser.base) if parser.base is not None else page_url
    except ValueError:
        base = page_url
    parts = urlsplit(page_url)
    fallback = urlunsplit((parts.scheme, parts.netloc, "/favicon.ico", "", ""))
    candidates = []
    for item in sorted(parser.icons, key=lambda x: x[:2]):
        try:
            candidates.append(urljoin(base, item[2]))
        except ValueError:
            continue
    candidates.append(fallback)
    seen = set()
    for url in candidates:
        try:
            url = normalize(url)
        except ValueError:
            continue
        if urlsplit(url).path.lower().endswith(".svg") or url in seen:
            continue
        seen.add(url)
        yield url


def main():
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "resolve":
            print(resolve(sys.argv[2]))
        elif len(sys.argv) == 3 and sys.argv[1] == "normalize":
            print(normalize(sys.argv[2]))
        elif len(sys.argv) == 4 and sys.argv[1] == "discover":
            html = Path(sys.argv[3]).read_bytes().decode("utf-8", errors="replace")
            print("\n".join(discover(sys.argv[2], html)))
        else:
            raise ValueError("Usage: find_favicons.py normalize URL | discover URL HTML_FILE")
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
