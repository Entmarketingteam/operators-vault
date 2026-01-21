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

## Creating the index (optional)

If the index does not exist, the pipeline will create it and set:

- `filterableAttributes`: `["podcast", "category", "video_id"]`
- `searchableAttributes`: `["title", "description", "framework_markdown"]`

Using the Meilisearch Python client:

```python
index = client.index("operators_insights")
index.update_filterable_attributes(["podcast", "category", "video_id"])
index.update_searchable_attributes(["title", "description", "framework_markdown"])
```
