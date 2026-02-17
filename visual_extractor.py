"""
Extract visual moments (screen-share/slide mentions) from transcripts using LLM.
"""
from __future__ import annotations

import os
import re
from typing import Any


def _anthropic_message(system: str, user: str, model: str = "claude-sonnet-4-5-20250929") -> str:
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
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    if r.content and len(r.content) > 0 and hasattr(r.content[0], "text"):
        return r.content[0].text
    return ""


def extract_visual_moments(transcript: str, timestamped_transcript: str = "") -> list[dict[str, Any]]:
    """
    Extract visual moments (screen-share, slides, decks) from transcript.
    Returns list of {start_time_sec, end_time_sec, description, transcript_excerpt}.
    """
    system = (
        "Extract moments where the speaker shows something visual: slides, screen shares, decks, dashboards, "
        "charts, or any visual content. Output as JSON array: "
        '[{"start_time_sec": "HH:MM:SS", "end_time_sec": "HH:MM:SS" (optional), "description": "What is shown", "transcript_excerpt": "relevant quote"}]. '
        "Only include actual visual moments (not just mentions). Output only JSON, no other text."
    )
    user = f"Transcript:\n{timestamped_transcript or transcript[:4000]}"
    raw = _anthropic_message(system, user)
    try:
        import json
        m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.DOTALL)
        if m:
            raw = m.group(1)
        moments = json.loads(raw)
        if isinstance(moments, list):
            out = []
            for m in moments:
                start_str = m.get("start_time_sec", "")
                end_str = m.get("end_time_sec", "")
                start_sec = _parse_time(start_str) if start_str else None
                end_sec = _parse_time(end_str) if end_str else None
                if start_sec is not None:
                    out.append({
                        "start_time_sec": start_sec,
                        "end_time_sec": end_sec,
                        "description": m.get("description", "").strip(),
                        "transcript_excerpt": m.get("transcript_excerpt", "").strip(),
                    })
            return out
    except Exception:
        pass
    return []


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
