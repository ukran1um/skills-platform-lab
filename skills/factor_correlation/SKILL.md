---
name: factor_correlation
version: 0.1.0
owner: egor
description: Compute Pearson correlations of daily returns between stock/ETF tickers from the local price warehouse. Use when asked how correlated two or more tickers are over a date range.
blast_radius: low
allowed_mcp_servers: [data_mcp]
required_scopes: [prices:read]
eval:
  golden_set: evals/golden.yaml
  threshold: 0.8
---

# Factor Correlation

Answer questions about how stock/ETF returns relate over a date window, using the tools provided.

## Available tools
- `list_tickers` — which tickers exist in the warehouse.
- `compute_correlation(tickers, start, end)` — Pearson correlation of daily returns; returns a matrix (and a correlation_value for two tickers). Use for correlations.
- `get_returns_stats(ticker, start, end)` — mean daily return, volatility, n_days for one ticker. Use for volatility/return stats.
- `run_sql(query)` — read-only SELECT over `prices(ticker, date, close)`. Use ONLY for questions the typed tools cannot answer (e.g. max/min close).

## How to work
- Prefer the typed tools over `run_sql` whenever they cover the question.
- For "which is more correlated" questions, call `compute_correlation` once for all tickers, then compare.

## Reporting rules
- Report correlations to two decimal places and name the date window used.
- These are correlations of DAILY RETURNS, not price levels — say so explicitly.
- If a requested ticker is missing from the warehouse, name it and stop; never guess values.
