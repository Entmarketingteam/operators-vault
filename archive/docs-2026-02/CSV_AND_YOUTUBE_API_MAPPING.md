> **ARCHIVED — historical, does not reflect current state.** See `CLAUDE.md` at the repo root for what is actually true today. Archived 2026-09-03.

# CSV and YouTube API mapping

How the scraped (Chrome-extension) CSV and the YouTube Data API map into Operators Vault.

## Scraped CSV format (Chrome extension)

Example file: `Operators and Titans Podcast Historically until February 10 2026.csv`

- **First row** is a header (no video ID in col 0), so it is skipped automatically.
- **Columns** (0-indexed):

| Index | Example / header | We use it as |
|-------|-------------------|--------------|
| 0 | `https://www.youtube.com/watch?v=ViYLfFc3LyA` | **URL** → extract `video_id` |
| 1 | `https://i.ytimg.com/vi/.../hqdefault.jpg?...` | Thumbnail URL (ignored for seed; API provides later) |
| 2 | `59:10` or `1:46:56` | **Duration** (parsed to seconds; optional min length filter) |
| 3 | `Operators Titans E005: Peak 21 (with President Roman Khan)` or `E144: Do smaller teams = bigger wins?` | **Title**; also used to infer **podcast** when using combined CSV |
| 4 | `30K views` | Not used for seed (API gives exact view_count) |
| 5 | `6 days ago` | Not used for seed |

### Combined CSV (Operators + TITANS in one file)

When the file contains both 9 Operators and TITANS episodes (one channel export):

- Use upload key **`operators_and_titans`** in `POST /seed-links/csv` or `POST /backfill`.
- **Podcast per row** is inferred from the title:
  - Title starts with **"Operators Titans "** or **"Operator Titans "** → `podcast = "titans"`.
  - Otherwise → `podcast = "9operators"`.

So one CSV upload can fill both 9 Operators and TITANS in `seed_links` (and then backfill).

### Default path (local)

- Combined file: `%USERPROFILE%\Downloads\Operators and Titans Podcast Historically until February 10 2026.csv` (see `youtube_client.DEFAULT_CSV_PATHS["operators_and_titans"]`).

---

## YouTube Data API → Vault

When we **fetch from YouTube** (e.g. `fetch-new` or playlist/channel), we map API response fields as follows.

### Videos list (snippet + contentDetails + statistics)

| API path | Our DB / usage |
|----------|-----------------|
| `id` | `video_id` |
| `snippet.title` | `title` |
| `snippet.description` | `description` (truncated) |
| `snippet.publishedAt` | `published_at` |
| `snippet.channelId` | `channel_id` |
| `snippet.channelTitle` | `channel_title` |
| `snippet.thumbnails.medium/high.url` | `thumbnail_url` |
| `snippet.tags[]` | `tags` (comma‑joined, capped) |
| `contentDetails.duration` (ISO 8601, e.g. `PT1H27M30S`) | Parsed → `duration_seconds` |
| `statistics.viewCount` | `view_count` |
| `statistics.likeCount` | `like_count` |
| `statistics.commentCount` | `comment_count` |

### How we get 9 Operators vs TITANS from the API

- **TITANS**: If `YOUTUBE_PLAYLIST_TITANS` is set, we call **playlist** `videos.list` and tag every item as `podcast = "titans"`.
- **9 Operators (and others)**: We call **channel** `search.list` + `videos.list` and tag by the channel we requested (`9operators`, `marketing_operator`, `finance_operators`).
- The **Operators9** channel contains both 9 Operators and TITANS episodes. If you do *not* set `YOUTUBE_PLAYLIST_TITANS`, TITANS are not fetched from the API; the combined CSV is the way to get both from one source. If you set the TITANS playlist ID, the API will pull TITANS from that playlist and 9 Operators from the channel.

---

## Summary

| Source | URL / ID | Title | Duration | Podcast |
|--------|----------|--------|----------|---------|
| Scraped CSV | col 0 | col 3 | col 2 (parsed) | Filename or **from title** (combined CSV) |
| YouTube API | `id` | `snippet.title` | `contentDetails.duration` (parsed) | Playlist or channel mapping |

After seed or fetch, `videos` and `seed_links` share the same logical fields; the pipeline uses them for processing and search.
