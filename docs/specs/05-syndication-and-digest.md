# Spec 5: Outbound Syndication & Digest Loop

## Problem

Operators Vault today is **ingest-only, one-directional:** podcast/newsletter content → transcribe → extract → store in Supabase → searchable knowledge base. No outbound flow exists. Insights sit in the vault waiting for Ethan/Emily (or operators) to search for them. This is useful for research, but misses the **active discovery / spoon-feeding** pattern that scales engagement:

- Weekly "best nuggets" newsletter (curated Tier 1 insights from that week's ingests)
- Slack digest in #ops-alerts (top 5 insights from each new video)
- Rebalancing old/"trending" insights from the vault back into rotation for operators who don't search regularly

## Solution: Syndication Loop

**Workflow:**
1. **Trigger:** Every 24 hours (or per-video, after scoring completes)
2. **Selection:** Pull Tier 1 insights from last N hours, dedupe, rank by recency + score
3. **Format:** Convert to digest format (markdown with links back to vault)
4. **Publish:** 
   - Draft a Google Doc / Notion page for Ethan/Emily review (manual gate before wider distribution)
   - Optionally: push to Slack #ops-alerts webhook
   - Optionally: queue for weekly newsletter via Mailchimp/Substack
5. **Track:** log which insights were surfaced (avoid re-surfacing the same one weekly)

## Implementation: N8N Workflow

**File:** `/Users/ethanatchley/ent-agency-ai-ops/n8n-workflows/[new-id]-operators-vault-daily-digest.json`

### Nodes

1. **Daily Cron** — 8am EST every day
2. **Query Supabase** — fetch Tier 1 insights from last 24h, sorted by score DESC
3. **Dedupe** — JavaScript node, filter out any insight ID already surfaced in the past 7 days (check `syndication_log` table)
4. **Format Digest** — convert to markdown with:
   - Insight title + category
   - Source (video title, timestamp link)
   - Speaker name
   - "Read full insight" link → vault.vercel.app/insights/{id}
5. **Create Draft** — POST to Google Docs / Notion API with the formatted digest
6. **Slack Webhook** (optional) — send summary to #ops-alerts:
   ```
   📊 Daily Insight Digest
   - [Insight 1] (Hudson LeGrande, Deal Structures)
   - [Insight 2] (Danny Yeung, CAC Metrics)
   - ...
   🔗 Full digest: [Google Doc link]
   ```
7. **Log Surfaced** — insert records into `syndication_log` table (insight_id, surfaced_date, channel)

### Database Changes

**New table:** `syndication_log`
```sql
CREATE TABLE syndication_log (
  id uuid PRIMARY KEY,
  insight_id uuid REFERENCES insights(id),
  channel TEXT NOT NULL,  -- "email", "slack", "notion", "google_docs"
  surfaced_date TIMESTAMP DEFAULT NOW(),
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(insight_id, channel, DATE(surfaced_date))
);
```

**Modify:** `insights` table
```sql
ALTER TABLE insights ADD COLUMN syndication_count INT DEFAULT 0;  -- track popularity
```

## Integration Points

### Email Newsletter (Future)

If Ethan/Emily want a weekly "Operators Vault Digest" newsletter:
- N8N workflow generates markdown
- Zapier or Make.com integration to convert to newsletter format (Mailchimp/Substack/Ghost)
- Subscribe segment: "Operators (Tier 2+)" for testing, then widen to full list

### Slack Distribution

- #ops-alerts (daily) — top 5 insights from yesterday
- #dtc-strategies (weekly) — curated deep-dive on 1 topic (e.g. "Retention Mechanics")
- Creator DM (manual) — send Nicki's own podcast insights about her influencer deals

### Feedback Loop (Advanced)

When an operator clicks "Read full insight" from email/Slack:
- Track click-through via utm_source
- Log in `syndication_log` (channel = "email_click", "slack_click")
- Use engagement signal to re-rank insights for next digest (high-click insights get re-surfaced less often)

## Verification

**Test 1: Workflow Execution**
```bash
# Check n8n execution log for the daily digest workflow
# Expected: runs once daily at 8am EST, fetches 5–15 Tier 1 insights, creates draft

# Or manually trigger via n8n UI for testing
```

**Test 2: Google Doc Draft**
```bash
# After first run, check your Notion/Google Drive inbox for a "Operators Vault Daily Digest - [date]" doc
# Expected: formatted markdown with insight titles, categories, speaker names, and links
```

**Test 3: Syndication Tracking**
```bash
psql -c "
SELECT channel, COUNT(*) as count, MAX(surfaced_date)
FROM syndication_log 
GROUP BY channel;"

# Expected: records in "google_docs" (and "slack" if webhook enabled)
```

## Rollout Plan

**Phase 1 (Week 1):** Draft-only, manual review
- N8N workflow creates daily Google Doc
- Ethan/Emily review, copy/paste best insights to Slack #ops-alerts manually
- Gather feedback on format, content quality, frequency

**Phase 2 (Week 2–3):** Auto-Slack after manual approval
- Once format/content proves solid, enable Slack webhook
- Slack alerts go to #ops-alerts automatically (no manual copy/paste)
- Still manually review Google Doc drafts before wider distribution

**Phase 3 (Month 2):** Email/newsletter syndication
- If ops express interest in weekly email digest, set up Zapier integration
- Weekly digest email to "Operators of All Sizes" list (TBD)

## Constraints & Gotchas

- **Manual gate:** Any outbound channel (email, Slack, public newsletter) must pass Ethan/Emily review to avoid publishing low-quality or sensitive insights
- **Frequency:** Don't resend the same insight more than once per 30 days in any channel
- **Privacy:** Don't surface insights that contain non-public deal terms or confidential operator info without speaker permission (assumption: all insights are speaker-approved once published in vault)
- **Timezone:** N8N runs on UTC; hardcode 8am EST = 1pm UTC

## Future: Trending & Evergreen

**Idea:** separate "trending this week" digest (24h old insights rising in engagement) from "evergreen deep-dive" (older, stable, high-value insights re-surfaced on a 90-day cycle). Keeps operators who don't search regularly seeing fresh, curated content from the vault.
