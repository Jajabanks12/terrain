"""
Fetches Google News RSS headlines relevant to a state's insurance/litigation environment.
Results are cached for 5 minutes to avoid hammering the feed on rapid state switches.
"""

import urllib.parse
import feedparser
from datetime import datetime
from email.utils import parsedate_to_datetime


# Primary query terms — cast wide enough to catch nuclear verdicts, dram shop, tort reform
_PRIMARY_TERMS = (
    '"nuclear verdict" OR "liability lawsuit" OR "tort reform" '
    'OR "dram shop" OR "personal injury verdict" OR "jury award" '
    'OR "premises liability" OR "wrongful death lawsuit"'
)

# Fallback if primary returns nothing
_FALLBACK_TERMS = '"insurance lawsuit" OR "civil lawsuit" OR "personal injury"'


def _build_url(state_name: str, terms: str) -> str:
    query = f'"{state_name}" AND ({terms})'
    encoded = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"


def _parse_date(entry) -> str:
    """Return a short human-readable date string from a feedparser entry."""
    try:
        dt = parsedate_to_datetime(entry.get("published", ""))
        return dt.strftime("%b %d, %Y")
    except Exception:
        return entry.get("published", "")[:10]


def _parse_source(entry) -> str:
    """Extract publisher name from the entry source or title suffix."""
    # feedparser puts the source in entry.source.title for Google News
    src = getattr(getattr(entry, "source", None), "title", None)
    if src:
        return src
    # Fallback: Google News appends " - Publisher Name" to the title
    title = entry.get("title", "")
    if " - " in title:
        return title.rsplit(" - ", 1)[-1]
    return ""


def _clean_title(entry) -> str:
    """Remove the trailing ' - Publisher' suffix Google News appends."""
    title = entry.get("title", "").strip()
    if " - " in title:
        return title.rsplit(" - ", 1)[0].strip()
    return title


def fetch_state_news(state_name: str, max_results: int = 8) -> list[dict]:
    """
    Returns up to max_results headline dicts for the given state.
    Each dict has keys: title, link, source, date.
    Falls back to a broader query if the primary returns fewer than 2 results.
    Returns an empty list if both queries fail or the feed is unreachable.
    """
    for terms in (_PRIMARY_TERMS, _FALLBACK_TERMS):
        url = _build_url(state_name, terms)
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue

        entries = feed.get("entries", [])
        if len(entries) >= 2:
            results = []
            for e in entries[:max_results]:
                results.append({
                    "title":  _clean_title(e),
                    "link":   e.get("link", "#"),
                    "source": _parse_source(e),
                    "date":   _parse_date(e),
                })
            return results

    return []
