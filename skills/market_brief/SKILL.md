---
name: market_brief
version: 0.1.0
owner: egor
description: Write a short factual brief on one stock/ETF ticker over a date window — its price move and fundamentals. Use when asked for a brief, summary, or overview of a ticker.
blast_radius: low
allowed_mcp_servers: [data_mcp]
required_scopes: [prices:read, fundamentals:read]
eval:
  golden_set: evals/golden.yaml
  threshold: 0.7
---

# Market Brief

Write a short, factual brief on ONE ticker over a date window.

## How to answer
1. Call `get_market_data(ticker, start, end)` exactly once.
2. From its output, write 2–4 sentences: name the ticker and the date window; describe the
   price move over the period (direction and rough magnitude, using first vs last close); and
   mention the fundamentals note.
3. Be factual. Do not invent any figure that is not in the tool output. If the tool returns an
   error (e.g. no data), say so plainly and name the ticker — do not fabricate a brief.

## Available tools
- `get_market_data(ticker, start, end)` — returns first/last close, number of trading days,
  and fundamentals for the ticker over the window.
