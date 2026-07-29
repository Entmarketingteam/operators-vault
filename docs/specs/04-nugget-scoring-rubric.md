# Spec 4: Nugget Scoring Rubric (Quality Filtering)

## Problem

A 6-hour mastermind stream, when transcribed and auto-extracted into insights, generates ~150–250 raw bullets (7–10 categories × 20–35 insights per category). Most are useful, but some are:
- **Generic filler** ("scaling is important", "test your messaging")
- **Partial or contextless** ("X said yes" without explaining what X is)
- **Duplicates** (same insight re-stated in different ways)
- **False positives** (extraction artifacts from diarization errors or garbled audio)

Publishing all 250 insights to operators overwhelms signal with noise. A **scoring rubric** selects the top 30–50 highest-confidence nuggets per stream, suitable for digests and top-hit queries.

## Scoring Dimensions

Each extracted insight gets scored 0–100 on 5 independent dimensions. Final score = weighted average.

### 1. Specificity (0–25 points)
How concrete and data-rich is this nugget?

| Score | Criteria | Example |
|-------|----------|---------|
| 25 | Named person + number + tactic | "Danny Yeung paid $50k CAC on a $250 first purchase" |
| 20 | Named person + number OR named person + tactic (2/3) | "Danny Yeung paid $50k CAC" or "Danny does cohort segmentation" |
| 15 | Specific tactic + number (no name) or generic person + specifics | "$50k CAC in email channel" or "A operator runs MV cohorts" |
| 10 | One specific element (name, number, or tactic) | "$50k" or "email channel" or "Danny Yeung" |
| 5 | Vague reference | "high spend" or "testing" |
| 0 | Generic advice | "retention is important" |

### 2. Actionability (0–20 points)
Can an operator use this tomorrow?

| Score | Criteria | Example |
|-------|----------|---------|
| 20 | Step-by-step method or direct recipe | "Segment cohorts by m1, m3, m6 retention; target >60% m1 to unlock non-dilutive capital" |
| 15 | Tactic + outcome, no steps | "Use cohort segmentation to qualify investors" |
| 10 | Tactical direction | "Focus on retention mechanics" |
| 5 | Inspirational but abstract | "Think bigger about unit economics" |
| 0 | Pure observation | "Retention varies by channel" |

### 3. Source Confidence (0–20 points)
How credible is the source?

| Score | Criteria | Example |
|-------|----------|---------|
| 20 | Named 8-9 figure operator | "Hudson LeGrande (founder, $X00M revenue)" |
| 15 | Named 7-figure operator or verifiable expert | "Danny Yeung (GC Growth Coach, DTC expert)" |
| 10 | Named but tier unclear | "An operator mentioned..." |
| 5 | Unattributed or "someone said" | "Consensus was..." |
| 0 | Unknown or low-trust source | Extracted from context-free audio fragment |

### 4. Novelty (0–20 points)
Is this new insight or repetition?

| Score | Criteria | Example |
|-------|----------|---------|
| 20 | Unique claim not in prior ingests | "First time any source mentioned X-product for Y-use" |
| 15 | Rare (mentioned 1–2 times across all sources) | "Cohort segmentation by m3 retention" (seen in 1 prior podcast) |
| 10 | Common (mentioned 3–5 times) | "Email retention is strong" |
| 5 | Repeated (mentioned >5 times) | "A/B test your messaging" |
| 0 | Obvious/assumed knowledge | "Test before scaling" |

### 5. Signal vs Noise (0–15 points)
Is this a real insight or extraction artifact?

| Score | Criteria | Example |
|-------|----------|---------|
| 15 | Natural language, clear grammar, unambiguous intent | "Danny Yeung charges 50% equity, 50% cash." |
| 10 | Slightly garbled but interpretable | "Danny Yeung takes 50-50 deal structures (equity-cash split)." |
| 5 | Mostly interpretable with context loss | "...Yeung ... 50 ... deal ... structure" |
| 0 | Unintelligible, likely transcription error | "Yeung X50 Deu Strateg" |

## Weighting & Thresholds

**Final Score** = 0.25×Specificity + 0.20×Actionability + 0.20×Confidence + 0.20×Novelty + 0.15×Signal

**Score Distribution & Use:**
- **≥85:** Tier 1 (Top tier) — include in weekly digest, publish to Slack #ops-alerts
- **70–84:** Tier 2 (High quality) — include in vault search results, highlight in "Top Insights" page
- **55–69:** Tier 3 (Standard) — searchable, lower rank in results
- **<55:** Tier 4 (Low) — indexed but hidden in default search (accessible via advanced filter)

## Implementation

**File:** `~/Desktop/operators-vault/scripts/score_insights.py` (NEW)

```python
def score_insight(insight: dict) -> dict:
    """
    Score a single insight dict across 5 dimensions.
    Returns: {...insight, score: 0–100, tier: "1"|"2"|"3"|"4"}
    """
    spec = _score_specificity(insight)
    action = _score_actionability(insight)
    conf = _score_confidence(insight, video_id, speaker_name)
    novel = _score_novelty(insight)
    signal = _score_signal_quality(insight)
    
    score = (0.25*spec + 0.20*action + 0.20*conf + 0.20*novel + 0.15*signal)
    
    if score >= 85:
        tier = "1"
    elif score >= 70:
        tier = "2"
    elif score >= 55:
        tier = "3"
    else:
        tier = "4"
    
    return {**insight, score: round(score, 1), tier: tier}
```

**Integration:** `pipeline.py` or `scripts/batch_score_insights.py`
```bash
# After insight extraction, run scoring
python scripts/score_insights.py --podcast hudson_legrande_mastermind
```

**DB changes:**
```sql
ALTER TABLE insights ADD COLUMN score FLOAT, tier TEXT;
CREATE INDEX idx_insights_score ON insights(score DESC);
CREATE INDEX idx_insights_tier ON insights(tier);
```

## Verification

**Test 1: Score Distribution**
```bash
psql -c "
SELECT tier, COUNT(*) as count, AVG(score) as avg_score
FROM insights 
WHERE podcast = 'hudson_legrande_mastermind'
GROUP BY tier
ORDER BY tier;"

# Expected: 20–30% Tier 1, 30–40% Tier 2, 25–35% Tier 3, 10–20% Tier 4
```

**Test 2: High-Score Spot Check**
```bash
psql -c "
SELECT title, category, score, speaker_name
FROM insights 
WHERE podcast = 'hudson_legrande_mastermind' AND score >= 85
LIMIT 10;"

# Expected: specific, named, actionable insights
```

## Tuning

If distribution is skewed (e.g., too many Tier 1 insights):
- Raise thresholds (85→87, 70→75)
- OR lower individual-dimension scoring (e.g., Specificity max 20 instead of 25)
- OR adjust weights (increase Novelty weight to penalize obvious insights)

**No single "correct" weighting** — tune based on what Ethan/Emily find most useful after first 1–2 ingests.
