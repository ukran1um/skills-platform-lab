# Learnings

Running log of operational gotchas found while building this. Format:

## YYYY-MM-DD — <area>: <one-line finding>
What happened, why it matters, what we changed.

## 2026-06-08 — data ingest: Stooq added a JS proof-of-work wall; switched to yfinance
Stooq's CSV download endpoint now returns a JavaScript SHA-256 proof-of-work challenge
to all non-browser HTTP clients (requests/curl get an HTML wall, 0 rows). Swapped the
ingest to yfinance (Yahoo), which works headless with no API key and returns adjusted
closes. Lesson: a "no-API-key public data source" is a standing liability — the resilient
move is one batched download through a maintained library, plus deterministic synthetic
fixtures (lab_data.fixtures) for tests/CI so the build never depends on a live scrape.
