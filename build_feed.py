from pathlib import Path
import json
import hashlib
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

import requests
from bs4 import BeautifulSoup

URL = "https://www.biblionet.gr/tina-mandilara-c80746"
FEED_TITLE = "Biblionet page changes - Tina Mandilara"
FEED_DESCRIPTION = "RSS feed generated from page-change detection"
MAX_ITEMS = 30

STATE_PATH = Path("state.json")
DOCS_DIR = Path("docs")
FEED_PATH = DOCS_DIR / "feed.xml"
INDEX_PATH = DOCS_DIR / "index.html"
NOJEKYLL_PATH = DOCS_DIR / ".nojekyll"


def fetch_visible_text(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    root = soup.body or soup
    text = " ".join(root.stripped_strings)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"last_hash": None, "items": []}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def ensure_docs() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    if not NOJEKYLL_PATH.exists():
        NOJEKYLL_PATH.write_text("", encoding="utf-8")

    if not INDEX_PATH.exists():
        INDEX_PATH.write_text(
            """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Feed</title>
</head>
<body>
  <p>This project publishes an RSS feed at <a href="./feed.xml">feed.xml</a>.</p>
</body>
</html>
""",
            encoding="utf-8"
        )


def build_rss(items: list[dict]) -> str:
    now = format_datetime(datetime.now(timezone.utc), usegmt=True)

    xml = []
    xml.append('<?xml version="1.0" encoding="UTF-8"?>')
    xml.append('<rss version="2.0">')
    xml.append('<channel>')
    xml.append(f"<title>{escape(FEED_TITLE)}</title>")
    xml.append(f"<link>{escape(URL)}</link>")
    xml.append(f"<description>{escape(FEED_DESCRIPTION)}</description>")
    xml.append(f"<lastBuildDate>{now}</lastBuildDate>")

    for item in items:
        xml.append("<item>")
        xml.append(f"<title>{escape(item['title'])}</title>")
        xml.append(f"<link>{escape(item['link'])}</link>")
        xml.append(f"<guid>{escape(item['guid'])}</guid>")
        xml.append(f"<pubDate>{escape(item['pubDate'])}</pubDate>")
        xml.append(f"<description>{escape(item['description'])}</description>")
        xml.append("</item>")

    xml.append("</channel>")
    xml.append("</rss>")
    return "\n".join(xml)


def main() -> None:
    ensure_docs()
    state = load_state()

    visible_text = fetch_visible_text(URL)
    current_hash = hashlib.sha256(visible_text.encode("utf-8")).hexdigest()
    now_dt = datetime.now(timezone.utc)
    now_rfc2822 = format_datetime(now_dt, usegmt=True)

    if current_hash != state.get("last_hash"):
        short_hash = current_hash[:12]
        item = {
            "title": f"Page updated: {FEED_TITLE}",
            "link": URL,
            "guid": f"{now_dt.strftime('%Y%m%dT%H%M%SZ')}-{short_hash}",
            "pubDate": now_rfc2822,
            "description": f"The monitored page changed. Snapshot hash: {short_hash}"
        }

        items = state.get("items", [])
        items.insert(0, item)
        state["items"] = items[:MAX_ITEMS]
        state["last_hash"] = current_hash
        save_state(state)

    FEED_PATH.write_text(build_rss(state["items"]), encoding="utf-8")


if __name__ == "__main__":
    main()