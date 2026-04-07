import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict


DEFAULT_FEEDS = [
    "https://www.reddit.com/r/AmItheAsshole/hot.rss",
    "https://www.reddit.com/r/relationship_advice/hot.rss",
    "https://www.reddit.com/r/TrueOffMyChest/hot.rss",
    "https://www.reddit.com/r/BestofRedditorUpdates/hot.rss",
]


def _clean_text(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    value = re.sub(r"\[.*?\]", "", value).strip()
    return value


def _clean_html_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _looks_like_update_post(title: str) -> bool:
    t = (title or "").strip().lower()
    return t.startswith("update:") or t.startswith("update -") or t.startswith("final update")


def _fetch_reddit_selftext(post_url: str) -> str:
    if not post_url or "reddit.com" not in post_url:
        return ""
    try:
        req = urllib.request.Request(
            post_url.rstrip("/") + ".json?raw_json=1",
            headers={"User-Agent": "VideoAutomationBot/1.0"},
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        post = payload[0]["data"]["children"][0]["data"]
        text = post.get("selftext", "") or ""
        return _clean_text(text)[:5000]
    except Exception:  # noqa: BLE001
        return ""


def _extract_comment_verdicts(raw_comments: list) -> Dict[str, int]:
    counts = {"NTA": 0, "YTA": 0, "ESH": 0, "NAH": 0}
    for child in raw_comments:
        data = (child or {}).get("data", {})
        body = str(data.get("body", "")).upper()
        if not body:
            continue
        for key in counts:
            if re.search(rf"\b{key}\b", body):
                counts[key] += 1
    return counts


def _fetch_reddit_post_context(post_url: str) -> Dict[str, object]:
    if not post_url or "reddit.com" not in post_url:
        return {"summary": "", "verdict_counts": {}}
    try:
        req = urllib.request.Request(
            post_url.rstrip("/") + ".json?raw_json=1&limit=25",
            headers={"User-Agent": "VideoAutomationBot/1.0"},
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        post = payload[0]["data"]["children"][0]["data"]
        comments = payload[1]["data"]["children"] if len(payload) > 1 else []
        summary = _clean_text(post.get("selftext", "") or "")[:5000]
        verdict_counts = _extract_comment_verdicts(comments)
        return {"summary": summary, "verdict_counts": verdict_counts}
    except Exception:  # noqa: BLE001
        return {"summary": "", "verdict_counts": {}}


def fetch_rss_titles(url: str, limit: int = 15) -> List[Dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "VideoAutomationBot/1.0"})
    with urllib.request.urlopen(req, timeout=20) as response:
        xml_data = response.read()
    root = ET.fromstring(xml_data)
    entries = []
    for item in root.findall(".//{http://www.w3.org/2005/Atom}entry")[:limit]:
        title_node = item.find("{http://www.w3.org/2005/Atom}title")
        link_node = item.find("{http://www.w3.org/2005/Atom}link")
        summary_node = item.find("{http://www.w3.org/2005/Atom}content")
        if summary_node is None:
            summary_node = item.find("{http://www.w3.org/2005/Atom}summary")
        title = _clean_text(title_node.text if title_node is not None else "")
        link = link_node.attrib.get("href", "") if link_node is not None else ""
        summary = _clean_html_text(summary_node.text if summary_node is not None else "")
        if title:
            context = _fetch_reddit_post_context(link)
            full_text = str(context.get("summary", "")).strip()
            entries.append(
                {
                    "title": title,
                    "url": link,
                    "summary": (full_text or summary)[:5000],
                    "verdict_counts": context.get("verdict_counts", {}),
                }
            )
    return entries


def ingest_trends(
    output_path: Path,
    feeds: List[str] = None,
    per_feed_limit: int = 10,
    include_update_posts: bool = False,
) -> dict:
    feeds = feeds or DEFAULT_FEEDS
    seen = set()
    ideas = []
    for feed in feeds:
        try:
            entries = fetch_rss_titles(feed, per_feed_limit)
            for item in entries:
                title = item["title"]
                if not include_update_posts and _looks_like_update_post(title):
                    continue
                key = title.lower()
                if key in seen:
                    continue
                seen.add(key)
                ideas.append(
                    {
                        "topic": title,
                        "source_url": item["url"],
                        "source_feed": feed,
                        "summary": item.get("summary", ""),
                        "verdict_counts": item.get("verdict_counts", {}),
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
