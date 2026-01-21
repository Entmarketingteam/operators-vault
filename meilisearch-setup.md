# Meilisearch Index – Operators Vault

Index name: `operators_insights`

## Primary key

- `id` (string, e.g. UUID from `insights.id`)

## Document shape

```json
{
  "id": "uuid-from-insights-id",
  "video_id": "dQw4w9WgXcQ",
  "podcast": "9operators",
  "category": "Frameworks and exercises",
  "title": "Creative Testing Cadence at Hexclad",
  "description": "Test 5–10 new concepts per month; kill underperformers by day 3–5.",
  "start_time_sec": 1245.5,
  "end_time_sec": 1380.0,
  "framework_markdown": "optional markdown or null"
}
```

## Filterable attributes

- `podcast` — `9operators` | `marketing_operator` | `finance_operators`
- `category` — e.g. `Frameworks and exercises`, `Points of view and perspectives`, …
- `video_id`

## Searchable attributes (order)

1. `title`
2. `description`
3. `framework_markdown`

## Sortable attributes (for `?sort=` on `/search`)

- `start_time_sec`, `title`, `category` — e.g. `?sort=start_time_sec:asc` or `?sort=title:desc`

## Creating the index (optional)

If the index does not exist, the pipeline will create it and set:

- `filterableAttributes`: `["podcast", "category", "video_id"]`
- `searchableAttributes`: `["title", "description", "framework_markdown"]`
- `sortableAttributes`: `["start_time_sec", "title", "category"]`

Using the Meilisearch Python client:

```python
index = client.index("operators_insights")
index.update_filterable_attributes(["podcast", "category", "video_id"])
index.update_searchable_attributes(["title", "description", "framework_markdown"])
index.update_sortable_attributes(["start_time_sec", "title", "category"])
```

---

## Fix `/search` on Railway (`invalid_api_key`)

If `GET /search` returns `invalid_api_key` from Meilisearch:

1. **Meilisearch (Cloud or self‑host):** Create or pick an API key that has **search** and **index** on `operators_insights`. The **default/admin key** usually has both; restricted keys must include:
   - `indexes = ['operators_insights']`
   - `actions = ['search', 'documents.add', 'documents.update', ...]` (at least `search` for `/search`; `documents.*` for the pipeline).
2. **Railway:** Project → **superb-smile** (or your service) → **Variables** → set:
   - `MEILISEARCH_API_KEY` = that key (replace any wrong or placeholder).
   - `MEILISEARCH_HOST` = `https://ms-9c9b9506a325-38835.nyc.meilisearch.io` (or your Meilisearch host) if not set.  
   **Or from project root** (with `RAILWAY_API_TOKEN`, `MEILISEARCH_API_KEY`, `MEILISEARCH_HOST` in `.env`):  
   `python scripts/set_railway_meilisearch.py` — uses Railway GraphQL API to set both variables.
3. **Redeploy** so the new env is picked up (Railway often auto-deploys on variable change), then try `GET /search?q=test`.
