"""ASS subtitles: large bold text, centered (Shorts / Reels / TikTok)."""
from pathlib import Path
from typing import List


def _ass_escape(text: str) -> str:
    t = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    return t.replace(",", "‚")


def _fmt_ass_time(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    whole = int(s)
    cs = int(round((s - whole) * 100))
    if cs >= 100:
        whole += 1
        cs = 0
    return f"{h}:{m:02d}:{whole:02d}.{cs:02d}"


def _word_weight(line: str) -> float:
    w = max(1.0, float(len(line.split())))
    return w


def write_ass_centered(
    lines: List[str],
    total_duration_sec: float,
    out_path: Path,
    font_size: int = 78,
    start_pad_sec: float = 0.12,
    end_pad_sec: float = 0.08,
) -> None:
    """
    Time each line in proportion to word count (closer to how TTS paces speech than equal slots).
    Optional padding trims the window so cues are not glued to file edges (TTS attack / tail).
    """
    cleaned = [ln.strip() for ln in lines if ln.strip()]
    if not cleaned:
        cleaned = [" "]

    start_pad = max(0.0, start_pad_sec)
    end_pad = max(0.0, end_pad_sec)
    window = max(0.5, total_duration_sec - start_pad - end_pad)
    weights = [_word_weight(ln) for ln in cleaned]
    total_w = sum(weights)
    if total_w <= 0:
        total_w = 1.0
    raw = [max(0.12, window * (w / total_w)) for w in weights]
    s_raw = sum(raw)
    durs = [r * (window / s_raw) for r in raw]

    header = f"""[Script Info]
Title: VideoAutomation
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},&H00FFFFFF,&H000000FF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,5,3,5,80,80,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    t = start_pad
    for idx, line in enumerate(cleaned):
        dur = durs[idx]
        end_t = t + dur
        start = _fmt_ass_time(t)
        end = _fmt_ass_time(min(end_t, total_duration_sec))
        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{_ass_escape(line)}")
        t = end_t
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
