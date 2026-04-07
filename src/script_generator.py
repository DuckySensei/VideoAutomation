import hashlib
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple


WORDS_PER_MINUTE = 150
MAX_VIDEO_SECONDS = 60
WORDS_PER_PART = int(WORDS_PER_MINUTE * (MAX_VIDEO_SECONDS / 60.0))
REDDIT_TEMPLATE_ID = "reddit_story"
STATE_FILE = Path("data") / "story_queue_state.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_story_state(base_dir: Path) -> Dict[str, object]:
    path = base_dir / STATE_FILE
    if not path.is_file():
        return {"seen_source_keys": [], "pending_parts": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"seen_source_keys": [], "pending_parts": []}
    return {
        "seen_source_keys": list(payload.get("seen_source_keys", [])),
        "pending_parts": list(payload.get("pending_parts", [])),
    }


def _save_story_state(base_dir: Path, state: Dict[str, object]) -> None:
    path = base_dir / STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


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


def _topic_focus(topic: str, max_chars: int = 90) -> str:
    text = re.sub(r"\s+", " ", topic or "").strip(" -|:")
    text = text.replace("—", " - ").replace("–", " - ")
    pieces = [p.strip(" -") for p in text.split(" - ") if p.strip(" -")]
    main = pieces[0] if pieces else text
    main = re.sub(r"[\"'`]", "", main).strip()
    return main[:max_chars].strip()


def _for_shell_text(value: str) -> str:
    text = (value or "").replace('"', "'").replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def _maybe_load_autonomous_env_local() -> None:
    # Local script-only runs may bypass env_loader; this keeps AI mode available.
    if os.getenv("OPENAI_API_KEY", "").strip():
        return
    path = Path("config") / "autonomous.env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value:
            os.environ.setdefault(key, value)


def _sanitize_topic(topic: str, max_chars: int = 56) -> str:
    clean = re.sub(r"\s+", " ", topic).strip(" -|:")
    return clean[:max_chars].strip()


def _drama_score(topic: str) -> int:
    drama_terms = {
        "aita",
        "asshole",
        "cheated",
        "divorce",
        "wedding",
        "boyfriend",
        "girlfriend",
        "husband",
        "wife",
        "toxic",
        "family",
        "roommate",
        "update",
        "caught",
        "lying",
    }
    tokens = set(normalize_tokens(topic))
    return len(tokens & drama_terms) * 2 + (1 if "?" in topic else 0)


def _ai_generate_story_structured(topic: str, source_summary: str = "") -> Dict[str, str]:
    _maybe_load_autonomous_env_local()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {}
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
    focus = _topic_focus(topic)
    summary = _for_shell_text(source_summary)[:1400]
    prompt = (
        "Create a Reddit story script package for short-form video.\n"
        f"Topic: {focus}\n"
        f"Available story context: {summary if summary else 'Title only; infer cautiously from title.'}\n"
        "Requirements:\n"
        "- Conversational voice, simple language\n"
        "- No fabricated facts beyond provided context\n"
        "- Return strict JSON with keys: setup, escalation, outcome, verdict\n"
        "- setup/escalation/outcome: each 55-95 words and complete sentences\n"
        "- verdict: one sentence summarizing likely Reddit consensus (NTA/YTA/ESH/NAH or mixed)\n"
        "- No markdown, no code fences"
    )
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": "You write captivating Reddit drama narrations."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.75,
            "max_tokens": 650,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        text = (text or "").strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        payload = json.loads(text[start : end + 1])
        return {
            "setup": str(payload.get("setup", "")).strip(),
            "escalation": str(payload.get("escalation", "")).strip(),
            "outcome": str(payload.get("outcome", "")).strip(),
            "verdict": str(payload.get("verdict", "")).strip(),
        }
    except Exception:  # noqa: BLE001
        return {}


def _verdict_line(verdict_counts: Dict[str, int], part_index: int, total_parts: int, ai_verdict: str = "") -> str:
    if total_parts > 1 and part_index < total_parts:
        return f"Reddit verdict so far: still unfolding. Comment 'part {part_index + 1}' for part {part_index + 1}."
    cleaned_ai = _for_shell_text(ai_verdict)
    if cleaned_ai:
        return f"Final Reddit verdict: {cleaned_ai}"
    if not verdict_counts:
        return "Final Reddit verdict: comments are mixed."
    ranked = sorted(verdict_counts.items(), key=lambda kv: kv[1], reverse=True)
    top_key, top_count = ranked[0]
    total = sum(verdict_counts.values()) or 1
    pct = int((top_count / total) * 100)
    return f"Final Reddit verdict: {top_key} leads with about {pct}% of verdict-tagged comments."


def _format_story_script(
    topic: str,
    story_text: str,
    part_index: int,
    total_parts: int,
    verdict_counts: Dict[str, int],
    ai_verdict: str = "",
) -> str:
    part_header = f"PART {part_index} OF {total_parts}" if total_parts > 1 else "SINGLE PART STORY"
    title_line = _topic_focus(topic, max_chars=120)
    verdict_line = _verdict_line(verdict_counts, part_index, total_parts, ai_verdict=ai_verdict)
    return f"{part_header}\nTitle: {title_line}\nStory: {story_text}\n{verdict_line}"


def _quality_story_part(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "")).strip()
    cleaned = cleaned.replace("..", ".")
    # Drop obvious clipped tails.
    cleaned = re.sub(r"\b(?:als|tho|becaus|whe|wit|somethin)\.$", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def _basic_story_cleanup(text: str) -> str:
    cleaned = _quality_story_part(text)
    replacements = {
        " dont ": " don't ",
        " cant ": " can't ",
        " im ": " I'm ",
        " ive ": " I've ",
        " its ": " it's ",
        " litterally ": " literally ",
        " a area ": " an area ",
        " AIRBNB ": " Airbnb ",
    }
    padded = f" {cleaned} "
    for old, new in replacements.items():
        padded = padded.replace(old, new)
    cleaned = padded.strip()
    cleaned = re.sub(r"\?{2,}", "?", cleaned)
    cleaned = re.sub(r"!{2,}", "!", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _rewrite_for_narration(text: str) -> str:
    _maybe_load_autonomous_env_local()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    seed = _basic_story_cleanup(text)
    if not api_key:
        return seed
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
    prompt = (
        "Rewrite the passage as a clean social-video narration.\n"
        "Constraints:\n"
        "- Keep original meaning and facts\n"
        "- Keep names/roles generic (no new details)\n"
        "- Improve grammar and clarity\n"
        "- Remove slang clutter and repeated filler\n"
        "- Keep similar length\n"
        "- Output plain text only\n\n"
        f"Passage:\n{seed}"
    )
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are an editor for short-form narration scripts."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 350,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        out = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        return _basic_story_cleanup(out or seed)
    except Exception:  # noqa: BLE001
        return seed


def _structured_from_summary(topic: str, source_summary: str, verdict_counts: Dict[str, int]) -> Dict[str, str]:
    focus = _topic_focus(topic, max_chars=110)
    cleaned = _for_shell_text(source_summary)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]
    if not sentences:
        sentences = [f"A Reddit post is trending: {focus}.", "People strongly disagree on whether OP handled it fairly."]
    setup = " ".join(sentences[:3]).strip()
    escalation = " ".join(sentences[3:6]).strip() or "As more details came out, commenters split into opposing sides and the conflict escalated."
    outcome = " ".join(sentences[6:9]).strip() or "The thread ended with no total consensus, but strong arguments on both sides."

    if verdict_counts:
        ranked = sorted(verdict_counts.items(), key=lambda kv: kv[1], reverse=True)
        verdict = f"Most verdict-tagged comments currently lean {ranked[0][0]}."
    else:
        verdict = "Commenters are still divided on who is in the wrong."
    return {"setup": setup, "escalation": escalation, "outcome": outcome, "verdict": verdict}


def _youtube_shorts_title(topic: str, part_index: int, total_parts: int) -> str:
    subject = _sanitize_topic(topic)
    if total_parts > 1:
        title = f"Part {part_index}/{total_parts} | Reddit story: {subject}"
    else:
        title = f"Reddit story: {subject}"
    if "#shorts" not in title.lower():
        title = f"{title} #shorts"
    return title[:100]


def _tiktok_caption(topic: str, part_index: int, total_parts: int) -> str:
    subject = _sanitize_topic(topic, max_chars=70)
    if total_parts > 1:
        head = f"Part {part_index}/{total_parts}: {subject}"
    else:
        head = f"Reddit story: {subject}"
    return f"{head}\n#redditstories #drama #storytime #shorts"


def make_metadata(topic: str, script_text: str, part_index: int, total_parts: int) -> Dict[str, str]:
    youtube_title = _for_shell_text(_youtube_shorts_title(topic, part_index, total_parts))
    youtube_description = (
        f"{_for_shell_text(script_text)}\n\n"
        "Source-inspired story recap transformed into original short-form commentary.\n"
        "#shorts #redditstories #storytime #drama"
    )
    return {
        "title": youtube_title[:100],
        "description": youtube_description,
        "tiktok_caption": _tiktok_caption(topic, part_index, total_parts),
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
    base_dir = trend_file.resolve().parent.parent
    state = _load_story_state(base_dir)
    seen_source_keys = set(str(x) for x in state.get("seen_source_keys", []))
    pending_parts = list(state.get("pending_parts", []))
    ranked_ideas = sorted(trends, key=lambda x: _drama_score(str(x.get("topic", ""))), reverse=True)

    queue = []
    kept_story_texts: List[str] = []

    # Always continue unfinished story parts first.
    while pending_parts and len(queue) < max_items:
        part_item = pending_parts.pop(0)
        if isinstance(part_item, dict):
            queue.append(part_item)

    for idea in ranked_ideas:
        if len(queue) >= max_items:
            break

        topic = str(idea.get("topic", "")).strip()
        source_url = str(idea.get("source_url", "")).strip()
        source_key = source_url or f"topic:{topic.lower()}"
        if source_key in seen_source_keys:
            continue
        source_summary = str(idea.get("summary", "")).strip()
        verdict_counts = idea.get("verdict_counts", {}) or {}
        structured = _ai_generate_story_structured(topic, source_summary=source_summary)
        setup = _quality_story_part(structured.get("setup", ""))
        escalation = _quality_story_part(structured.get("escalation", ""))
        outcome = _quality_story_part(structured.get("outcome", ""))
        ai_verdict = _quality_story_part(structured.get("verdict", ""))
        if not setup or not escalation or not outcome:
            fallback = _structured_from_summary(topic, source_summary, verdict_counts)
            setup = _quality_story_part(fallback.get("setup", ""))
            escalation = _quality_story_part(fallback.get("escalation", ""))
            outcome = _quality_story_part(fallback.get("outcome", ""))
            ai_verdict = _quality_story_part(fallback.get("verdict", ""))
            if not setup or not escalation or not outcome:
                continue

        setup = _rewrite_for_narration(setup)
        escalation = _rewrite_for_narration(escalation)
        outcome = _rewrite_for_narration(outcome)
        ai_verdict = _rewrite_for_narration(ai_verdict) if ai_verdict else ai_verdict

        story_text = f"{setup} {escalation} {outcome}".strip()
        passed, similarity = quality_gate(story_text, kept_story_texts)
        if not passed:
            continue
        kept_story_texts.append(story_text)

        setup_words = len(re.findall(r"\S+", setup))
        escalation_words = len(re.findall(r"\S+", escalation))
        outcome_words = len(re.findall(r"\S+", outcome))
        total_words = setup_words + escalation_words + outcome_words
        if total_words > WORDS_PER_PART:
            parts = [f"{setup} {escalation}".strip(), outcome]
        else:
            parts = [story_text]
        total_parts = len(parts)

        story_parts_payloads: List[Dict[str, object]] = []
        for idx, part_body in enumerate(parts, start=1):
            part_text = _format_story_script(topic, part_body, idx, total_parts, verdict_counts, ai_verdict=ai_verdict)
            story_parts_payloads.append(
                {
                    "script_id": script_hash(f"{topic}|part={idx}|{part_text}"),
                    "topic": topic,
                    "template_id": REDDIT_TEMPLATE_ID,
                    "script_text": part_text,
                    "metadata": make_metadata(topic, part_text, idx, total_parts),
                    "source": {
                        "feed": idea.get("source_feed", ""),
                        "url": source_url,
                    },
                    "series": {"part": idx, "total_parts": total_parts},
                    "qc": {"similarity_max": round(similarity, 4), "approved": True},
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        # Fill current queue; carry remainder to next run.
        available = max(0, max_items - len(queue))
        queue.extend(story_parts_payloads[:available])
        if len(story_parts_payloads) > available:
            pending_parts.extend(story_parts_payloads[available:])

        # Mark source as used once accepted so we never regenerate same story.
        seen_source_keys.add(source_key)

    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "items": queue}
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _save_story_state(
        base_dir,
        {
            "seen_source_keys": sorted(seen_source_keys),
            "pending_parts": pending_parts,
        },
    )
    return payload
