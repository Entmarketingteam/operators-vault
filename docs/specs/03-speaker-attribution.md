# Spec 3: Speaker Attribution & Diarization Post-Processing

## Problem

Deepgram's diarization (`diarize=True`) produces speaker labels as generic integers: `Speaker 0`, `Speaker 1`, `Speaker 2`, etc. This works for podcast host + guest (2 speakers), but masterminds with 5–8 operators are useless without real names. Queries like "What did Hudson say about CAC?" fail because the DB has no way to distinguish Hudson from other speakers.

**Current state:**
- `segments.speaker_label = "Speaker 0"` (text field, no FK)
- `insight_people` table exists but is never populated by batch extraction (only manually curated)
- Speaker pages do 4-tier FTS fallback to find mentions of a person's name in transcript text, but can't attribute an insight to a specific speaker with confidence

## Solution: Multi-Signal Post-Processing + Confidence Scoring

**Goal:** for each utterance/segment, attempt to map `Speaker N` → real name with a confidence score.

### Signals (in priority order)

1. **Self-introduction at stream start** (Highest confidence ~90%)
   - Pattern: "Hi, I'm [Name]" or "My name's [Name]" in first N utterances for each speaker
   - Extract and store speaker roster once per video

2. **Video description / guest list** (High confidence ~80%)
   - Check video description for a listed speaker order or guest roster
   - Match speakers to order if available

3. **Live chat mentions** (Medium-high confidence ~70%)
   - "Welcome [Name]!" or "@[Name] asked..." in live chat timestamps
   - Cross-reference with utterance start times

4. **Known operator roster** (Medium confidence ~60%)
   - If Hudson LeGrande is known to be a regular host, map Speaker 0 → Hudson
   - Airtable or manual roster of known participants

5. **Transcript keyword heuristics** (Low confidence ~40%)
   - If an utterance contains "I'm [Name]" mid-stream, tag future utterances from that speaker with that name
   - Risky; high false-positive rate with shared stories

6. **Fallback** (Confidence 0)
   - Keep `Speaker N` if all signals fail

### Data Model

**New table:** `speaker_roster` (per-video)
```sql
CREATE TABLE speaker_roster (
  id uuid PRIMARY KEY,
  video_id TEXT REFERENCES videos(video_id),
  speaker_label TEXT NOT NULL,  -- "Speaker 0", "Speaker 1", etc.
  inferred_name TEXT,           -- e.g. "Hudson LeGrande", NULL if unresolved
  confidence_score FLOAT,       -- 0.0–1.0
  signal_source TEXT,           -- "self_intro", "description", "chat", "roster", "heuristic", "fallback"
  created_at TIMESTAMP
);
```

**Modify:** `segments` table
```sql
ALTER TABLE segments ADD COLUMN speaker_name TEXT;  -- denormalized from speaker_roster for query speed
```

### Implementation

**File:** `~/Desktop/operators-vault/scripts/post_process_speakers.py` (NEW)

```python
def post_process_video_speakers(video_id: str, db: Database) -> None:
    """
    For a single ingested video, attempt to map speaker labels to real names.
    Runs after successful transcription.
    """
    roster = {}
    
    # Signal 1: self-intro scan
    intros = _scan_self_intros(video_id, db)
    roster.update({label: (name, 0.9) for label, name in intros.items()})
    
    # Signal 2: description parsing
    desc_roster = _parse_video_description(video_id)
    for label, name in desc_roster.items():
        if label not in roster:
            roster[label] = (name, 0.8)
    
    # Signal 3: live chat cross-reference
    chat_roster = _cross_ref_live_chat(video_id)
    for label, name in chat_roster.items():
        if label not in roster:
            roster[label] = (name, 0.7)
    
    # Signal 4: known operator roster (hardcoded for Hudson streams)
    if "hudson_legrande_mastermind" in podcast_slug(video_id):
        known = {"Speaker 0": ("Hudson LeGrande", 0.6)}  # Placeholder; needs Hudson's typical role
        for label, (name, score) in known.items():
            if label not in roster:
                roster[label] = (name, score)
    
    # Store in speaker_roster table
    for label, (name, conf) in roster.items():
        db.insert_speaker_roster(video_id, label, name, conf)
    
    # Denormalize to segments for query speed
    db.update_segments_speaker_names(video_id, roster)
```

**Callable:** `~/Desktop/operators-vault/pipeline.py` or `Makefile`
```bash
python scripts/post_process_speakers.py --video-id KifnZpGDxfs --podcast hudson_legrande_mastermind
```

**Integration:** hook into `pipeline.py:_process_one()` to auto-run post-processing after transcription completion (before insight extraction, so insights can reference speaker names).

## Verification

**Test 1: Self-Intro Detection**
```bash
# After running post-processing
psql -c "
SELECT speaker_label, inferred_name, confidence_score 
FROM speaker_roster 
WHERE video_id = 'KifnZpGDxfs'
ORDER BY confidence_score DESC;"

# Expected: real names for high-confidence speakers
```

**Test 2: Query By Speaker**
```bash
# Search API should now find insights by speaker name
curl 'https://superb-smile-production.up.railway.app/search?q=Hudson+LeGrande&source=hudson_legrande_mastermind' | jq '.results[0].speaker_name'

# Expected: "Hudson LeGrande" (not "Speaker 0")
```

## Limitations & Caveats

- **Self-introductions** may be missing if speakers don't introduce themselves (assumption error)
- **Chat cross-reference** requires live chat to be available (some videos disable it)
- **Heuristics** can misattribute if multiple speakers use the same names or patterns
- **Fallback** to generic `Speaker N` is acceptable; better to be uncertain than confidently wrong

## Future Improvements

1. **Fine-tuned speaker classifier** — train a model on known operator voices to predict speaker identity from audio
2. **Airtable roster sync** — pull list of known masterminds + regular participants from a central config
3. **Confidence threshold for publishing** — only surface speaker names with confidence > 0.75 to frontend
4. **Manual override UI** — frontend form for Ethan/Emily to correct misattributions
