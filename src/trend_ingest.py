import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict


DEFAULT_FEEDS = [
    "https://www.reddit.com/r/artificial/hot.rss",
    "https://www.reddit.com/r/ChatGPT/hot.rss",
    "https://www.reddit.com/r/productivity/hot.rss",
]


def _clean_text(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    value = re.sub(r"\[.*?\]", "", value).strip()
    return value


def fetch_rss_titles(url: str, limit: int = 15) -> List[Dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "VideoAutomationBot/1.0"})
    with urllib.request.urlopen(req, timeout=20) as response:
        xml_data = response.read()
    root = ET.fromstring(xml_data)
    entries = []
    for item in root.findall(".//{http://www.w3.org/2005/Atom}entry")[:limit]:
        title_node = item.find("{http://www.w3.org/2005/Atom}title")
        link_node = item.find("{http://www.w3.org/2005/Atom}link")
        title = _clean_text(title_node.text if title_node is not None else "")
        link = link_node.attrib.get("href", "") if link_node is not None else ""
        if title:
            entries.append({"title": title, "url": link})
    return entries


def ingest_trends(output_path: Path, feeds: List[str] = None, per_feed_limit: int = 10) -> dict:
    feeds = feeds or DEFAULT_FEEDS
    seen = set()
    ideas = []
    for feed in feeds:
        try:
            entries = fetch_rss_titles(feed, per_feed_limit)
            for item in entries:
                title = item["title"]
                key = title.lower()
                if key in seen:
                    continue
                seen.add(key)
                ideas.append(
                    {
                        "topic": title,
                        "source_url": item["url"],
                        "source_feed": feed,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            ideas.append(
                {
                    "topic": f"Feed unavailable: {feed}",
                    "source_url": "",
                    "source_feed": feed,
                    "error": str(exc),
                }
            )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ideas": ideas,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
