import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_tokens(text: str) -> List[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if len(w) > 2]


def jaccard_similarity(a: str, b: str) -> float:
    a_set = set(normalize_tokens(a))
    b_set = set(normalize_tokens(b))
    if not a_set and not b_set:
        return 0.0
    return len(a_set & b_set) / max(len(a_set | b_set), 1)


def script_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def generate_script(topic: str, template_id: str) -> str:
    if template_id == "hook_3tips_cta":
        return (
            f"Stop scrolling: {topic} can save you real time today.\n"
            f"Tip one: Start with one tiny workflow for {topic.lower()} and automate the repetitive step.\n"
            f"Tip two: Track results for 7 days so you keep what works and drop what doesn't.\n"
            f"Tip three: Use templates instead of starting from scratch every time.\n"
            "Comment your bottleneck and I will make the next short about it."
        )
    if template_id == "myth_vs_fact":
        return (
            f"Myth: {topic} only helps power users.\n"
            "Why people believe it: the tools look complicated at first glance.\n"
            f"Fact: {topic} works best when you start with one simple repeatable task.\n"
            "Do this today: automate one task that takes more than five minutes.\n"
            "Follow for daily practical workflows."
        )
    return (
        f"Top three ways to use {topic} in under 30 seconds.\n"
        "Number one: idea generation with a strict output format.\n"
        "Number two: draft cleanup with a quality checklist.\n"
        "Number three: recurring task automation with templates.\n"
        "Save this and test one workflow today."
    )


def _sanitize_topic(topic: str, max_chars: int = 56) -> str:
    clean = re.sub(r"\s+", " ", topic).strip(" -|:")
    return clean[:max_chars].strip()


def _youtube_shorts_title(topic: str, template_id: str) -> str:
    subject = _sanitize_topic(topic)
    if template_id == "hook_3tips_cta":
        title = f"3 AI productivity wins in 30s: {subject}"
    elif template_id == "myth_vs_fact":
        title = f"AI myth vs fact: {subject}"
    else:
        title = f"Top 3 AI shortcuts: {subject}"
    if "#shorts" not in title.lower():
        title = f"{title} #shorts"
    return title[:100]


def _tiktok_caption(topic: str, template_id: str) -> str:
    subject = _sanitize_topic(topic, max_chars=72)
    if template_id == "myth_vs_fact":
        hook = f"Myth vs fact: {subject}"
    elif template_id == "hook_3tips_cta":
        hook = f"3 things to try today: {subject}"
    else:
        hook = f"Quick top 3: {subject}"
    return f"{hook}\n#tiktok #productivity #aitools #shorts"


def make_metadata(topic: str, script_text: str, template_id: str) -> Dict[str, str]:
    youtube_title = _youtube_shorts_title(topic, template_id)
    youtube_description = (
        f"{script_text}\n\n"
        "Short-form educational content made with original scripting and legally licensed assets.\n"
        "#shorts #aitools #productivity"
    )
    return {
        "title": youtube_title[:100],
        "description": youtube_description,
        "tiktok_caption": _tiktok_caption(topic, template_id),
        "is_short_form": True,
    }


def quality_gate(script_text: str, existing_texts: List[str], threshold: float = 0.72) -> Tuple[bool, float]:
    highest = 0.0
    for text in existing_texts:
        sim = jaccard_similarity(script_text, text)
        if sim > highest:
            highest = sim
    return highest < threshold, highest


def build_script_queue(
    trend_file: Path,
    niche_config_file: Path,
    output_file: Path,
    max_items: int = 12,
) -> dict:
    trends = load_json(trend_file).get("ideas", [])
    niche = load_json(niche_config_file)
    templates = [t["id"] for t in niche["content_templates"]]

    queue = []
    kept_texts: List[str] = []
    for idx, idea in enumerate(trends):
        if len(queue) >= max_items:
            break
        template_id = templates[idx % len(templates)]
        topic = idea["topic"]
        script_text = generate_script(topic, template_id)
        passed, similarity = quality_gate(script_text, kept_texts)
        if not passed:
            continue
        kept_texts.append(script_text)
        queue.append(
            {
                "script_id": script_hash(script_text),
                "topic": topic,
                "template_id": template_id,
                "script_text": script_text,
                "metadata": make_metadata(topic, script_text, template_id),
                "source": {
                    "feed": idea.get("source_feed", ""),
                    "url": idea.get("source_url", ""),
                },
                "qc": {"similarity_max": round(similarity, 4), "approved": True},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "items": queue}
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
