# Framework Content – 9 Operators, Marketing Operator, Finance Operator

Your goal is to turn a **topic** and **raw transcript** into a concise, structured **framework** in markdown. Use the speaker’s wording and style. No fluff.

## Guidelines

- **Remove the fluff** — only dense information directly from the transcript.
- **Bullet points** — use bullets for key pieces; mix parent bullets and children when needed.
- **Mini summary first** — one short, factual summary of what the framework is about.
- **Use the speaker’s wording and style** — structured and concise, not paraphrased loosely.
- **Do not** start with a heavy title like "Elon Musk's Hiring Process"; go straight into the topic summary.
- Output structured markdown inside `<FrameWork>...</FrameWork>` tags.

---

## Operators-style example

**Topic:** Paid media creative testing loop at a 9-figure DTC brand

**Example raw_transcript (1–2 paragraphs):**

We refresh creatives every 2–3 weeks, or as soon as we see CTR or CVR start to dip—that’s usually creative fatigue. We’re testing 5–10 new concepts a month. Anything that’s underperforming by day 3–5 gets killed; we don’t let it run. Winners we scale to 20–30% of spend. Creative and media are both in-house; we use an internal dashboard plus a creative platform to track which concepts are driving ROAS. Agency can work but you need a tight feedback loop so they’re not shipping stuff that’s already fatigued.

**Example FrameWork:**

<FrameWork>
**Mini summary:** When to refresh, how many to test, when to kill, when to scale, and who owns it.

- **When to refresh:** Every 2–3 weeks, or when CTR/CVR drops (creative fatigue).
- **Test and kill cadence:** 5–10 new concepts per month; kill underperformers by day 3–5.
- **Scale criteria:** Scale winners to 20–30% of spend.
- **Ownership and tools:** In-house creative and media; internal dashboard and creative platform to track ROAS. Agency works if feedback loop is tight.
</FrameWork>

Use **Operators terms**: CAC, ROAS, creative fatigue, UGC, CTR, CVR, etc. Same shape as other frameworks: mini summary first, then logical sections.

---

## Input

<topic>
{topic}
</topic>

<raw_transcript>
{raw_transcript}
</raw_transcript>

---

Respond with a structured markdown framework inside `<FrameWork>...</FrameWork>`.
