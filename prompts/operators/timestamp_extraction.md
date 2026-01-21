# Timestamp Extraction – 9 Operators, Marketing Operator, Finance Operator

Your goal is to find the **start** and **end** timestamps for when a topic is discussed in the transcript. Identify when the topic is **first** discussed and when the discussion **ends** (they move to another topic).

## Instructions

- Only respond with the timestamps. No other text.
- Use the format: `HH:MM:SS` (e.g. `01:01:05`, `00:39:44`).
- Wrap in `<start_time>` and `<end_time>` tags.

## Example 1 (Operators-style)

**Transcript snippet:** Discussion of creative fatigue, when to refresh creatives, and CTR drop—then they move to Klaviyo.

**Insight:** "Creative fatigue happens after 2–3 weeks; refresh before CTR drops."

**Output:**
<start_time>00:42:10</start_time>
<end_time>00:45:30</end_time>

## Example 2 (Operators-style)

**Insight:** "Klaviyo flows for post-purchase and win-back."

**Logic:** Start when that topic is first mentioned; end when the conversation moves to a different subject.

**Output:**
<start_time>00:38:00</start_time>
<end_time>00:41:15</end_time>

---

## Input

<transcript>
{transcript}
</transcript>

<insight>
{insight}
</insight>

---

Respond with only:

<start_time>HH:MM:SS</start_time>
<end_time>HH:MM:SS</end_time>
