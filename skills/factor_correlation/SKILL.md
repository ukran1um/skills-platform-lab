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

Compute return correlations between tickers over a date window.

## How to run

From the repo root:

    uv run python -m factor_correlation.cli AAPL MSFT --start 2025-01-01 --end 2025-12-31

- Output is JSON: a `matrix` of pairwise Pearson correlations of daily returns,
  plus a top-level `correlation_value` when exactly two tickers are given.
- Data comes from `data/warehouse/prices.parquet` (override with $PRICES_PARQUET).
  If the warehouse file is missing, run `uv run python -m lab_data.ingest` first.

## Reporting rules

- Report correlations to two decimal places and name the date window used.
- These are correlations of daily returns, not price levels — say so explicitly.
- If a ticker is missing from the warehouse, name it and stop; never guess values.
