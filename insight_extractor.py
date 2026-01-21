"""
LLM-based insight extraction, title generation, timestamp extraction, and framework content.
Uses Anthropic. Loads prompts from prompts/operators/ (or prompts/{prompt_set}/).
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
DEFAULT_PROMPT_SET = "operators"


def _load_prompt(name: str, prompt_set: str = DEFAULT_PROMPT_SET) -> str:
    p = PROMPTS_DIR / prompt_set / f"{name}.md"
    if not p.exists():
        p = PROMPTS_DIR / DEFAULT_PROMPT_SET / f"{name}.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _anthropic_message(system: str, user: str, model: str = "claude-sonnet-4-20250514") -> str:
    try:
        import anthropic
    except ImportError:
        return ""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return ""
    c = anthropic.Anthropic(api_key=api_key)
    r = c.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    if r.content and len(r.content) > 0 and hasattr(r.content[0], "text"):
        return r.content[0].text
    return ""


# --- Category names as in prompts and DB ---
CATEGORIES = [
    "Frameworks and exercises",
    "Points of view and perspectives",
    "Business ideas",
    "Stories and anecdotes",
    "Quotes",
    "Products",
]


def _parse_insight_block(block: str, category: str) -> list[dict[str, str]]:
    """Parse a category block: * [Title]: [Desc] or * "[Quote]" – [Person]."""
    out: list[dict[str, str]] = []
    for line in block.splitlines():
        line = line.strip()
        if not line or not line.startswith("*"):
            continue
        line = line[1:].strip()
        # Quote: * "Quote" – Person
        mq = re.match(r'^"([^"]+)"\s*[–—\-]\s*(.+)$', line)
        if mq:
            out.append({"title": mq.group(2).strip(), "description": mq.group(1).strip(), "category": category})
            continue
        # * Title: Description
        if ": " in line:
            t, d = line.split(": ", 1)
            out.append({"title": t.strip(), "description": d.strip(), "category": category})
        else:
            out.append({"title": line, "description": "", "category": category})
    return out


def parse_extract_insights_output(text: str) -> list[dict[str, str]]:
    """
    Parse the ---...--- output from extract_insights into list of {category, title, description}.
    Handles one block with multiple "Category Name:" sections and/or multiple --- blocks.
    """
    out: list[dict[str, str]] = []
    # Normalize: strip leading/trailing ---, then split by --- to get blocks
    t = re.sub(r"^\s*---+\s*\n?", "", text)
    t = re.sub(r"\n?---+\s*$", "", t)
    blocks = re.split(r"\n---+\n", t)
    for block in blocks:
        block = block.strip()
        if not block or "(none)" in block.lower():
            continue
        lines = block.splitlines()
        if not lines:
            continue
        # Within a block, category headers are lines like "Frameworks and exercises:" (end with :, no *).
        # Subsequent * lines belong to that category until the next header.
        category = ""
        current: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # New category header: "Category Name:" (no leading *)
            if not stripped.startswith("*") and stripped.endswith(":"):
                if current and category:
                    out.extend(_parse_insight_block("\n".join(current), category))
                category = stripped.rstrip(":").strip()
                current = []
            elif stripped.startswith("*"):
                current.append(stripped)
        if current and category:
            out.extend(_parse_insight_block("\n".join(current), category))
        # If no category headers in block, treat first line as category (legacy)
        if not out and not category and lines:
            cat_line = lines[0].rstrip(":")
            if not cat_line.startswith("*"):
                category = cat_line.strip()
                rest = "\n".join(lines[1:])
                out.extend(_parse_insight_block(rest, category))
    return out


def extract_insights(transcript: str, prompt_set: str = DEFAULT_PROMPT_SET) -> list[dict[str, str]]:
    """
    Run insight extraction on a transcript chunk. Returns list of {category, title, description}.
    """
    tpl = _load_prompt("extract_insights_system", prompt_set)
    if not tpl:
        return []
    user = tpl.replace("{transcript}", transcript)
    # System empty; full prompt in user is fine for many setups. If your prompt has a system part, split.
    system = "You are an expert eCommerce and DTC podcast analyst. Follow the instructions exactly."
    raw = _anthropic_message(system, user)
    return parse_extract_insights_output(raw)


def generate_title(insight: str, prompt_set: str = DEFAULT_PROMPT_SET) -> str:
    """Generate a short title for an insight. insight can be title + description or just description."""
    tpl = _load_prompt("title_generation", prompt_set)
    if not tpl:
        return ""
    user = tpl.replace("{insight}", insight)
    system = "Output only the title in <title>...</title>. No other text."
    raw = _anthropic_message(system, user)
    m = re.search(r"<title>([^<]*)</title>", raw, re.DOTALL)
    return m.group(1).strip() if m else raw.strip()[:120]


def _parse_time(s: str) -> float | None:
    """HH:MM:SS or MM:SS -> seconds."""
    if not s:
        return None
    s = s.strip()
    n = [int(x) for x in re.findall(r"\d+", s)]
    if not n:
        return None
    if len(n) == 1:
        return float(n[0])
    if len(n) == 2:
        return float(n[0] * 60 + n[1])
    return float(n[0] * 3600 + n[1] * 60 + n[2])


def extract_timestamps(transcript: str, insight: str, prompt_set: str = DEFAULT_PROMPT_SET) -> tuple[float | None, float | None]:
    """Extract start and end timestamps for when the insight is discussed. Returns (start_sec, end_sec)."""
    tpl = _load_prompt("timestamp_extraction", prompt_set)
    if not tpl:
        return (None, None)
    user = tpl.replace("{transcript}", transcript).replace("{insight}", insight)
    system = "Output only <start_time>HH:MM:SS</start_time> and <end_time>HH:MM:SS</end_time>. No other text."
    raw = _anthropic_message(system, user)
    st = re.search(r"<start_time>([^<]*)</start_time>", raw)
    et = re.search(r"<end_time>([^<]*)</end_time>", raw)
    return (_parse_time(st.group(1)) if st else None, _parse_time(et.group(1)) if et else None)


def make_framework(topic: str, raw_transcript: str, prompt_set: str = DEFAULT_PROMPT_SET) -> str:
    """Generate framework markdown for a topic from a transcript segment."""
    tpl = _load_prompt("make_framework_content", prompt_set)
    if not tpl:
        return ""
    user = tpl.replace("{topic}", topic).replace("{raw_transcript}", raw_transcript)
    system = "Output only the framework markdown inside <FrameWork>...</FrameWork>. No other text."
    raw = _anthropic_message(system, user)
    m = re.search(r"<FrameWork>([\s\S]*?)</FrameWork>", raw)
    return m.group(1).strip() if m else raw.strip()
