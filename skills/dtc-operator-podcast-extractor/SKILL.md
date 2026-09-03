---
name: dtc-operator-podcast-extractor
description: Use when DTC podcasts need operator notes and clip signals.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, macos, linux]
metadata:
  hermes:
    tags: [ent, dtc, ecom, podcasts, transcripts, operator-notes, clips, cmo, p&l]
---

# DTC Operator Podcast Extractor

## When to Use

Use when the source is a podcast, interview, webinar, or long-form video featuring DTC / e-commerce operators, founders, CPG operators, media buyers, or brand builders, and the user wants actionable notes rather than a generic summary.

## Goal

Turn transcripts into operator-grade notes that answer:

- What is the core thesis?
- What are the operational implications?
- What should a brand/operator do differently on Monday?
- What quote or moment is clip-worthy?
- What metrics, KPIs, or accounting concepts matter?

## Strong signals to extract

Always look for:

- CM1 / CM2 / CM3, contribution margin, gross-to-net, COGS, delivery, freight, discounts, rebates
- P&L structure, conditional formatting rules, dashboards, weekly/monthly cadence
- inventory, demand planning, S&OP, product launch timing, price pack architecture
- creative strategy, media buying, attribution, incrementality, branded search, CAC/LTV
- founder/CEO operating system, meeting cadence, delegation, hiring, org design
- channel mix, content flywheels, influencer/creator strategy, retention, retention cohorts
- any explicit heuristics like "don’t do X", "this is free game", "we do Y instead"

## Host cue / emphasis detection

If the podcast is conversational, flag moments where the host or guest clearly signals importance:

- "free game"
- "this is huge"
- "I love that"
- laughter after a strong point
- repeated restatement of the same idea
- a hard tonal shift from casual to intense
- host cut-backs that reinforce the point
- moments where the host injects energy, validation, or urgency

These are often the best clip markers.

## Workflow

1. **Get the transcript**
   - Use the transcript tool or provided text.
   - If the transcript is large, chunk it before analysis.

2. **Build a structured readout**
   - 1-paragraph executive summary
   - topic sections with bullets
   - operator takeaways
   - KPI/accounting implications
   - what is tactical vs philosophical

3. **Extract applications**
   For each important point, translate it into one of:
   - what a brand should do
   - what a founder should stop doing
   - what a media buyer should monitor
   - what a finance/operator team should change
   - what a creator/marketing team should test

4. **Identify clip moments**
   - Include short timestamped moments when available
   - Quote the exact line or near-exact phrasing
   - Explain why it matters
   - Flag host reinforcement or reaction if present

5. **Add an operator lens**
   Convert abstract statements into practical categories such as:
   - P&L
   - creative
   - media
   - supply chain
   - org design
   - founder mentality
   - distribution / channels
   - retention / cohort math

6. **Keep the format usable**
   The default deliverable should be short, dense, and skimmable. For long outputs, save to a file and return the path plus a short summary.

## Output format

Prefer this structure:

- Source
- One-line thesis
- Key operator notes
- KPI / accounting notes
- Tactical applications
- Best quotes
- Best clip moments
- What I would do if I ran this brand

## Quality bar

A good output should let Ethan or Emily say:

- "I understand the business takeaways"
- "I know what to clip"
- "I know what to change in a brand"
- "I know which numbers matter"

## Pitfalls

- Do not give a generic summary when the user clearly wants operator application.
- Do not flatten the transcript into bland paraphrase.
- Do not miss metric language like CM1/CM2/CM3, contribution margin, or delivery assumptions.
- Do not ignore host reactions and reinforcement moments.
- Do not invent timestamps or quote language if the transcript does not support them.
- Do not over-dump a giant transcript into chat; save to file when needed.
