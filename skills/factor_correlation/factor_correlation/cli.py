"""CLI entrypoint used by Claude Code (laptop context) and humans."""

from __future__ import annotations

import argparse
import json
from datetime import date
from typing import Any

from factor_correlation.tools.compute import correlation_matrix
from factor_correlation.tools.fetch import get_prices


def run(tickers: list[str], start: date, end: date) -> dict[str, Any]:
    prices = get_prices(tickers, start, end)
    if prices.empty:
        raise SystemExit(f"no price data for {tickers} between {start} and {end}")
    corr = correlation_matrix(prices)
    cols = sorted(corr.columns.tolist())
    # Honor SKILL.md's "name it and stop" rule: a partially-missing request
    # (some tickers present, some absent) must fail loudly rather than silently
    # dropping the absent ones from the matrix.
    missing = [t.upper() for t in tickers if t.upper() not in cols]
    if missing:
        raise SystemExit(f"ticker(s) not found in warehouse: {', '.join(sorted(missing))}")
    result: dict[str, Any] = {
        "tickers": cols,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "matrix": {a: {b: round(float(corr.loc[a, b]), 6) for b in cols} for a in cols},
    }
    if len(cols) == 2:
        result["correlation_value"] = round(float(corr.loc[cols[0], cols[1]]), 6)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Correlation of daily returns between tickers")
    parser.add_argument("tickers", nargs="+")
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.tickers, args.start, args.end), indent=2))


if __name__ == "__main__":
    main()
