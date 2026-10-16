# WikiCard Learning System

A Streamlit app that helps students learn the US presidents: study cards, quizzes, a timed
competition with a leaderboard, analytics and an admin area. Card data is collected from Wikipedia
by the app itself (list page via `requests` + BeautifulSoup, article leads via the MediaWiki API)
and stored in PostgreSQL on Supabase. A bundled snapshot (`data/seed_us_presidents.json`) is used if
Wikipedia is unreachable. No LLM/AI services are used; hints and highlights are rule-based.

## Layout

| Path | Purpose |
| --- | --- |
| `app.py` | Entry point, navigation, setup page |
| `wikicard/db.py` | psycopg 3 + psycopg-pool data access, schema bootstrap |
| `wikicard/scraper.py` | Wikipedia harvesting, term merging, snapshot fallback |
| `wikicard/textutils.py` | Years, hints, highlight scoring |
| `wikicard/game.py` | Answer checking, scoring, leaderboard ranking |
| `wikicard/pages/` | One module per page |
| `supabase/schema.sql` | Tables, constraints, indexes, RLS (also applied on startup) |
| `tests/` | pytest suite |

## Run locally

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then edit
streamlit run app.py
```

`DATABASE_URL` may come from the environment or `st.secrets`. Use the Supabase **Session pooler**
URI (Project → Connect), never the IPv6-only `db.<ref>.supabase.co` host. `ADMIN_PASSWORD`
(optional) protects Build Database and Admin. If the database is not configured or unreachable, the
app shows the real error on a setup page within ~10 s.

## Deploy

1. Create a free Supabase project; optionally run `supabase/schema.sql` in the SQL editor (the app
   creates missing tables itself). RLS is enabled with no policies, so the public REST API returns `[]`.
2. Push the repo to GitHub, create an app on Streamlit Community Cloud, and paste the secrets.
3. On first start with an empty `cards` table the app harvests automatically (once per server start).
   After "Delete all cards" it stays empty until Refresh/Rebuild.

`.streamlit/config.toml` intentionally does not set `server.port`.

## Tests

```bash
pytest                                   # unit tests (database tests are skipped)
TEST_DATABASE_URL=postgresql://... pytest # also runs database tests
```

`TEST_DATABASE_URL` must point to a throwaway database: the tests drop and recreate the tables.
