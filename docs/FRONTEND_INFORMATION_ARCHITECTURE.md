# Operators Vault – Front-End Information Architecture

**Purpose:** Define the navigation structure, routes, and page types so the UI matches the MFMVault-style experience. Use this alongside the full implementation plan when building the vault front end.

---

## 1. Left sidebar navigation (persistent)

Mirror the MFMVault structure: **Discover**, **Listen**, **Catalog**, **Connect**.

| Section   | Item            | Route / behavior |
|-----------|-----------------|-------------------|
| **Discover** | Search          | `/` or `/search` – main search page (query + facets). |
| **Discover** | Ask             | `/ask` – chat over the vault with preset modes. |
| **Listen**   | Business Ideas  | `/insights?type=business_ideas` (or `category=Business ideas`). Pre-filtered list view. |
| **Listen**   | Frameworks      | `/insights?type=frameworks`. |
| **Listen**   | Quotes          | `/insights?type=quote`. Include optional “Panzerisms only” chip. |
| **Listen**   | Stories        | `/insights?type=stories`. |
| **Listen**   | Opinions / POVs | `/insights?type=opinions` (category = Points of view and perspectives). |
| **Listen**   | Products       | `/insights?type=product`. Show company/brand when available. |
| **Listen**   | Visuals        | `/insights?type=visuals` – screen-share/slide moments (Phase 3). |
| **Catalog**  | Episodes       | `/episodes` – list all episodes by show (9 Operators, Marketing, Finance, TITANS); use videos + YouTube stats. |
| **Catalog**  | People         | `/people` – directory of hosts and guests (people table); search + tags. |
| **Connect**  | API            | Link to FastAPI docs (e.g. `/docs` or external). |
| **Connect**  | About          | `/about` – short copy on Operators Vault and data sources. |

**TITANS:** Either a top-level nav pill/tab that sets `podcast=titans` and stays in current view, or a sub-item under Catalog (e.g. “TITANS”) that goes to `/episodes?podcast=titans`. Prefer one consistent place (e.g. Discover or a “Shows” dropdown) so TITANS is first-class.

---

## 2. Routes summary

| Route | Purpose |
|-------|--------|
| `/` or `/search` | Main search: query + facets (podcast, type, category, person, company, Panzerisms, visuals). Results = cards with speaker, timestamp, type pill, “Watch” link. |
| `/ask` | Chat page: preset tiles (e.g. Idea generator, Highlights, Panzerisms, Brand breakdowns) + message input; responses cite episode + timestamp. |
| `/insights?type={quote\|frameworks\|product\|stories\|opinions\|business_ideas\|visuals}` | Dedicated list for that insight type. Optional `&panzerism=1` for Quotes. Layout: featured card at top (optional), then table/list with Storyteller, Title/Quote/Preview, Rating (optional), Listen/Link. |
| `/episodes` | Episode catalog. Filters: podcast (9 Operators, Marketing, Finance, TITANS). Cards or table: title, podcast, published date, duration, view count (when available), thumbnail. |
| `/episodes?podcast=titans` | TITANS-only episode list. |
| `/people` | People directory. Search box (“Search N people…”), grid of cards: avatar, name, role/tags. Click → person detail or filtered search. |
| `/person/{slug}` (optional) | Person detail: name, bio, list of episodes and insights (quotes, frameworks) by that person. Can be implemented as `/search?person=slug` with a person header. |
| `/company/{slug}` (optional) | Company/brand detail: name, type (brand/SaaS), episodes and insights mentioning them. Can be `/search?company=slug`. |
| `/about` | Static copy: what Operators Vault is, sources (YouTube, Operators network), link to 9operators.com. |
| `/docs` or external | API documentation. |

All search and insight list URLs should be **shareable** (query params for q, podcast, type, category, person_id, company_id, is_panzerism, etc.) with a “Copy link to search” (or “Copy link”) control.

---

## 3. Page layouts (reference)

- **Search (`/`, `/search`):** Hero with title “Search Operators Vault”, subtitle (e.g. “Explore 9 Operators, Marketing Operators, Finance Operators, TITANS”). Search bar + “Copy link to search”. Left column: facets (Type, Podcast, Episodes list, People/Speakers, Companies – with counts). Right: result cards (avatar optional, title, snippet with highlight, metadata: Speaker, Duration, Start time, Published; type pill; Watch link). |
- **Insight list (`/insights?type=...`):** Same left nav. Main: page title (e.g. “N Quotes shared on Operators”), optional featured card, then table/list of items with Storyteller, Quote/Title, Preview, Rating (if we add it), Listen/Check it out. |
- **People (`/people`):** Left nav. Main: “Friends of Operators” or “People”, search box, grid of people cards (avatar, name, role, tags). |
- **Episodes (`/episodes`):** Left nav. Main: “Episodes”, podcast filter tabs or dropdown, list/grid of episodes (thumbnail, title, podcast, date, duration, views). |
| **Ask (`/ask`):** Left nav. Main: “Ask Operators Vault”, subtitle (“Ask questions about the podcasts. Conversations are public.”). Category tabs (Featured, Business Ideas, Marketing Strategies, etc.). Tiles: Idea generator, Podcast highlights, Memorable quotes / Panzerisms, Business advice. Chat input at bottom. |

---

## 4. Implementation notes

- **Stack:** Keep vanilla HTML/CSS/JS + FastAPI for now. Each “route” can be a distinct HTML view (e.g. `search.html`, `insights.html`, `people.html`, `episodes.html`, `ask.html`) or a single-page app that reads `window.location.pathname` and `search` and renders the right layout.
- **Auth:** Same as current: Supabase Auth (Google / magic link) or token paste; Bearer token sent to `/search`, `/chat`, and any future authenticated endpoints.
- **Data:** All list and filter data comes from existing or planned API: `GET /search`, `GET /people`, `GET /companies`, `GET /stats`, `POST /chat`. Episodes list can be `GET /episodes` (new) or search with empty q and facet by video_id + video metadata from `/stats` or a dedicated endpoint.
- **Ratings:** MFMVault shows star ratings on insights; we don’t have that in the schema yet. Optional later: add `rating` or `prominence_score` to insights and show on cards.

This IA is the better route: it makes the target UI explicit so the existing backend plan (schema, search, chat, people, companies, Panzerisms, visuals) maps cleanly to the screens users see.
