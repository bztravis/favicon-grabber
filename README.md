# Favicon Grabber

Copy a website's favicon as a PNG image from Raycast.

## Setup

Keep `favicon-grabber.sh` and `find_favicons.py` in the same directory, and add
that directory to Raycast's Script Commands directories. Python 3 is required;
the script checks PATH and common Homebrew locations. All other tools are
included with macOS.

Run **Favicon Grabber** in Raycast and enter a brand name, domain, or HTTP/HTTPS URL.
You can also run:

```bash
./favicon-grabber.sh example.com
./favicon-grabber.sh Nike
```

The command replaces your clipboard with the downloaded image on success.
Paste into an app that accepts images.

## Selection and limitations

Declared favicons are tried first, largest advertised size first, followed by
declared Apple touch icons and `/favicon.ico`. Relative URLs and HTML base URLs
are supported. Images are converted with macOS `sips`; SVG declarations are
skipped. ICO frame selection is determined by `sips`.

Each download has a 15-second timeout, a 10 MiB limit, and a maximum of five
redirects. Sites requiring login, JavaScript, or bot verification may fail.
Brand names are searched on Wikidata using its free public API, then resolved
using the official website property (`P856`). Preferred statements take priority;
deprecated statements and statements with an end date are ignored. Exact name
matches take priority among results with websites. If multiple domains remain,
the command lists them and asks you to run again with a domain. Small brands may
be missing. Domains and URLs bypass Wikidata. Brand searches are sent to Wikidata.

No API key or third-party favicon service is used. Failed retrieval or conversion
leaves the clipboard untouched. Temporary downloads are removed on exit.
