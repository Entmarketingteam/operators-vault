# Spec 2: Mastermind-Specific Insight Extraction Schema

## Problem

The current insight extraction prompt (`prompts/operators/extract_insights_system.md`) is designed for produced podcasts: finished episodes with a host, often a single guest, polished production. Masterminds (and similarly, roundtable discussions, multi-hour workshops) have a different signal profile:

- **Multiple speakers** (5–8 operator-level participants), rapid context-switching
- **High data density** — spend figures, deal structures, revenue benchmarks, specific names, tactics (e.g. "Danny Yeung paid $X CPA")
- **Raw, unpolished** — tangents, side conversations, no editing or post-production curation
- **Operator-to-operator** — assumes high baseline knowledge; fewer 101-level fundamentals
- **Q&A segments** — audience asks drive significant chunks

Current 7 categories (Frameworks, POVs, Business Ideas, Stories, Quotes, Products, Creator Tactics) capture some of this, but:
1. "Business Ideas" is too vague for mastermind-specific deal structures and spending strategies
2. No place to capture "who said this" when multi-speaker diarization is imperfect
3. Generic "Products" misses the specificity of "X tool costs $Y/mo and does Z"
4. Conflates high-value-specific nuggets ("$50k CAC on a $250 first purchase") with generic advice

## Solution: Extended Schema + Strict Filtering

### New Categories (Additive to Base 7)

1. **Deal Structures & Terms** — named deal terms, partnership splits, revenue shares
   - Example: "Danny Yeung took equity vs cash, 50/50 structure with brand X"
   
2. **Named Spend & Metrics** — attribution of specific numbers to specific tactics/operators
   - Example: "Hudson LeGrande spending $300–400k daily on 800 new ad tests per week"
   
3. **Operator-to-Operator Q&A** — direct answers to questions from participants (vs. generic advice)
   - Example: "@Mason asks about LTV payback — Danny responds: cohort needs 40% retention by M3"

### Stricter "Must Include a Number" Filter

Masterminds are data-dense. A real nugget includes:
- A specific number OR
- A named operator/brand/tactic OR  
- A quote (word-for-word callout) from a specific speaker

Generic statements ("retention is important", "test your messaging") are filtered out. Keeps signal-to-noise high.

### Prompt Changes

**File:** `~/Desktop/operators-vault/prompts/masterminds/extract_insights_system.md` (NEW)

Add to the base extraction logic:
```markdown
## Mastermind-Specific Instructions

Extract the same 7 base categories PLUS these 3 additive ones:

8. **Deal Structures & Terms** — specific partnership/deal terms, equity/cash splits, revenue shares
   - Include founder/operator names and brand names
   - Example: "Danny Yeung took 60% equity + 40% cash from GC deal"

9. **Named Spend & Metrics** — attribute specific numbers to operators and tactics
   - Always name who is spending what, when possible
   - Preserve the original number exactly (e.g. "$300–400k daily" not "high spend")

10. **Operator Q&A** — direct answers from one operator to another in real-time
   - Format: "[Questioner]: Q → [Responder]: A"
   - Preserve names and the exact exchange

## Number Filter

A nugget must include at least ONE of:
- A specific number ($X, Nk, X%, X/mo, etc.)
- A named operator, brand, or tactic ("Danny Yeung", "GC deal", "email capture")
- A direct quote (in quotes, speaker-attributed)

If none are present, filter out (confidence level = 0).
```

### Prompt Variant: `prompts/masterminds/extract_insights_system.md`

Clone from `prompts/operators/` as base; add the above 3 categories + number filter to the system instruction.

**File:** `~/Desktop/operators-vault/prompts/masterminds/` (directory, NEW)
- `extract_insights_system.md` (the above)
- `title_generation.md` (copy from operators/)
- `timestamp_extraction.md` (copy from operators/)
- `make_framework_content.md` (copy from operators/)

## Implementation

**Entry Point:** `pipeline.py:_load_prompt(name, prompt_set="masterminds")`

When `podcast = "hudson_legrande_mastermind"` (or any other mastermind slug), automatically use `prompt_set="masterminds"` instead of `"operators"`.

**Modified Files:**
- `pipeline.py` — add a mapping: `MASTERMIND_PODCAST_SLUGS = {"hudson_legrande_mastermind", ...}` at module level
- In `insight_extractor.py`, check: if podcast slug in `MASTERMIND_PODCAST_SLUGS`, use `prompt_set="masterminds"`

## Verification

**Test 1: Prompt Loading**
```bash
python3 -c "
from insight_extractor import _load_prompt
prompt = _load_prompt('extract_insights_system', prompt_set='masterminds')
assert 'Deal Structures' in prompt, 'New mastermind category missing'
print('✅ Mastermind prompt loads with 10 categories')
"
```

**Test 2: Filtering**
```bash
# After ingesting Hudson stream, query insights
psql -c "
SELECT category, title FROM insights 
WHERE podcast = 'hudson_legrande_mastermind'
  AND category IN ('Deal Structures & Terms', 'Named Spend & Metrics', 'Operator Q&A')
LIMIT 10;"

# Expected: real, data-dense insights (names, numbers, specific deals)
```

## Backward Compatibility

- Existing podcast/newsletter sources continue to use `prompt_set="operators"` / `prompt_set="newsletters"`
- Only new mastermind sources (or sources manually flagged as masterminds) use the extended schema
- No changes to DB schema or API
