# M0+M1: Scaffold, Data, CI Skeleton, First Skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the skills-platform-lab monorepo with a private GitHub remote, a parquet price warehouse, a green CI skeleton, and the `factor_correlation` skill running in local Claude Code (laptop context).

**Architecture:** uv-workspace monorepo. `data/` is a workspace member (`lab_data` package) providing a deterministic synthetic-fixtures generator and a Stooq ingest script that writes `data/warehouse/prices.parquet`. The skill lives at `skills/factor_correlation/` with SKILL.md (contract + system prompt) at the skill root and code in an inner `factor_correlation` package; it reads parquet directly via DuckDB (the deliberate ungoverned laptop path), exposed to Claude Code through a `.claude/skills/` symlink and a JSON-emitting CLI.

**Tech Stack:** Python 3.12, uv workspaces, pandas, numpy, DuckDB, pyarrow, requests, pytest, ruff, mypy, GitHub Actions, gh CLI.

**Spec:** `docs/superpowers/specs/2026-06-06-skills-platform-lab-design.md`

**Note on spec deviation (locked in here):** the spec tree shows `data/ingest.py` as a bare script. For testability the plan makes `data/` a proper workspace member with code in `data/lab_data/`. Same for skill code: SKILL.md and `evals/` stay at the skill root per spec, Python code goes in an inner `factor_correlation` package so multiple skills never collide on module names.

---

## File structure after this plan

```
skills-platform-lab/
├── pyproject.toml                  # workspace root (virtual): members, dev deps, ruff/mypy/pytest config
├── .python-version                 # 3.12
├── .gitignore
├── README.md                       # stub
├── LEARNINGS.md                    # stub with first entry format
├── uv.lock                         # committed
├── .github/workflows/ci.yaml      # ruff + mypy + pytest on push/PR
├── .claude/skills/
│   └── factor_correlation -> ../../skills/factor_correlation   # symlink
├── data/
│   ├── pyproject.toml              # package: lab-data
│   ├── tickers.txt                 # 50 tickers
│   ├── lab_data/
│   │   ├── __init__.py
│   │   ├── fixtures.py             # deterministic synthetic prices (seeded)
│   │   └── ingest.py               # Stooq → data/warehouse/prices.parquet
│   ├── tests/
│   │   ├── test_fixtures.py
│   │   └── test_ingest.py
│   ├── fixtures/                   # generated, gitignored
│   └── warehouse/                  # generated, gitignored
├── skills/factor_correlation/
│   ├── pyproject.toml              # package: factor-correlation
│   ├── SKILL.md                    # frontmatter contract + agent instructions
│   ├── factor_correlation/
│   │   ├── __init__.py
│   │   ├── cli.py                  # JSON-emitting entrypoint
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── fetch.py            # get_prices via DuckDB over parquet
│   │       └── compute.py          # daily_returns, correlation_matrix
│   └── tests/
│       ├── test_compute.py
│       ├── test_fetch.py
│       └── test_cli.py
└── docs/superpowers/...            # spec + this plan
```

Responsibilities: `fixtures.py` = synthetic data only; `ingest.py` = network download + parse only; `fetch.py` = warehouse read only; `compute.py` = pure math only; `cli.py` = argument parsing + JSON shaping only. No module does two of these.

---

## Task 1: Workspace root scaffold

**Files:**
- Create: `pyproject.toml`, `.python-version`, `.gitignore`, `README.md`, `LEARNINGS.md`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "skills-platform-lab"
version = "0.1.0"
description = "Governed skills platform prototype: registry monorepo, eval-gated CI, capability-token MCP, skill host"
requires-python = ">=3.12"

[tool.uv.workspace]
members = ["data", "skills/*"]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "ruff>=0.4",
    "mypy>=1.10",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
ignore_missing_imports = true
exclude = ["\\.venv"]
```

Note: `skills/*` is a glob (zero matches is fine until Task 8); `data` is a literal member, so Task 2 must create it before `uv sync` succeeds. That's why this task only verifies at Step 6 of Task 2.

- [ ] **Step 2: Create `.python-version`**

```
3.12
```

- [ ] **Step 3: Create `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
.DS_Store
data/warehouse/
data/fixtures/
```

- [ ] **Step 4: Create `README.md`**

```markdown
# skills-platform-lab

A working prototype of a governed skills platform: skill registry monorepo with
eval-gated CI, CI/CD-as-governance, a capability-token-validated MCP server, and
a skill-host runtime. Learning project; public data only.

Design: `docs/superpowers/specs/2026-06-06-skills-platform-lab-design.md`

## Quickstart

    uv sync --all-packages
    uv run python -m lab_data.ingest          # build the price warehouse (network)
    uv run pytest -q
```

- [ ] **Step 5: Create `LEARNINGS.md`**

```markdown
# Learnings

Running log of operational gotchas found while building this. Format:

## YYYY-MM-DD — <area>: <one-line finding>
What happened, why it matters, what we changed.
```

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .python-version .gitignore README.md LEARNINGS.md
git commit -m "chore: workspace root scaffold"
```

---

## Task 2: `lab_data` package + synthetic fixtures generator

**Files:**
- Create: `data/pyproject.toml`, `data/lab_data/__init__.py`, `data/lab_data/fixtures.py`
- Test: `data/tests/test_fixtures.py`

- [ ] **Step 1: Create `data/pyproject.toml`**

```toml
[project]
name = "lab-data"
version = "0.1.0"
description = "Price warehouse: synthetic fixtures and Stooq ingest"
requires-python = ">=3.12"
dependencies = [
    "pandas>=2.2",
    "numpy>=1.26",
    "pyarrow>=16",
    "requests>=2.32",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["lab_data"]
```

- [ ] **Step 2: Create empty `data/lab_data/__init__.py` and run `uv sync`**

Run: `cd /Users/ukran1um/Projects/learning/skills-platform-lab && uv sync --all-packages`
Expected: resolves and installs; `uv.lock` created. (Fails if Task 1 files are wrong.)

- [ ] **Step 3: Write the failing test `data/tests/test_fixtures.py`**

```python
from datetime import date

import pandas as pd

from lab_data.fixtures import make_prices


def test_fixture_prices_deterministic():
    a = make_prices()
    b = make_prices()
    pd.testing.assert_frame_equal(a, b)


def test_fixture_prices_schema_and_bounds():
    df = make_prices(tickers=["AAPL"], start=date(2025, 1, 1), end=date(2025, 1, 31))
    assert list(df.columns) == ["ticker", "date", "close"]
    assert set(df["ticker"]) == {"AAPL"}
    assert (df["close"] > 0).all()
    assert all(d.weekday() < 5 for d in df["date"])  # weekdays only
    assert df["date"].min() >= date(2025, 1, 1)
    assert df["date"].max() <= date(2025, 1, 31)
```

- [ ] **Step 4: Run test to verify it fails**

Run: `uv run pytest data/tests/test_fixtures.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lab_data.fixtures'`

- [ ] **Step 5: Write `data/lab_data/fixtures.py`**

```python
"""Deterministic synthetic price fixtures for tests and evals."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA", "SPY"]
SEED = 42


def make_prices(
    tickers: list[str] | None = None,
    start: date = date(2024, 1, 1),
    end: date = date(2025, 12, 31),
    seed: int = SEED,
) -> pd.DataFrame:
    """Geometric random walk, weekdays only. Same seed -> identical frame."""
    tickers = tickers or DEFAULT_TICKERS
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(start, end)
    frames = []
    for ticker in tickers:
        log_returns = rng.normal(loc=0.0003, scale=0.02, size=len(days))
        close = 100.0 * np.exp(np.cumsum(log_returns))
        frames.append(pd.DataFrame({"ticker": ticker, "date": days.date, "close": close}))
    return pd.concat(frames, ignore_index=True)


def write_parquet(out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    make_prices().to_parquet(out_path, index=False)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("data/fixtures/prices.parquet"))
    args = parser.parse_args()
    print(f"wrote {write_parquet(args.out)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest data/tests/test_fixtures.py -v`
Expected: 2 PASS

- [ ] **Step 7: Generate the fixtures file once and confirm it lands in the gitignored dir**

Run: `uv run python -m lab_data.fixtures && git status --short data/`
Expected: `wrote data/fixtures/prices.parquet`; git status shows nothing under `data/fixtures/`

- [ ] **Step 8: Commit**

```bash
git add data/pyproject.toml data/lab_data data/tests/test_fixtures.py uv.lock
git commit -m "feat: lab_data package with deterministic synthetic price fixtures"
```

---

## Task 3: Stooq ingest

**Files:**
- Create: `data/lab_data/ingest.py`, `data/tickers.txt`
- Test: `data/tests/test_ingest.py`

- [ ] **Step 1: Write the failing test `data/tests/test_ingest.py`** (no network: tests the parser only)

```python
import pytest

from lab_data.ingest import parse_stooq_csv, stooq_symbol

STOOQ_CSV = """Date,Open,High,Low,Close,Volume
2025-01-02,243.0,245.5,241.1,244.2,1000000
2025-01-03,244.5,246.0,243.0,245.9,900000
"""


def test_stooq_symbol():
    assert stooq_symbol("AAPL") == "aapl.us"
    assert stooq_symbol("brk-b") == "brk-b.us"


def test_parse_stooq_csv():
    df = parse_stooq_csv("aapl", STOOQ_CSV)
    assert list(df.columns) == ["ticker", "date", "close"]
    assert set(df["ticker"]) == {"AAPL"}
    assert len(df) == 2
    assert df["close"].tolist() == [244.2, 245.9]


def test_parse_stooq_csv_rejects_garbage():
    with pytest.raises(ValueError, match="unexpected response"):
        parse_stooq_csv("aapl", "No data")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest data/tests/test_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lab_data.ingest'`

- [ ] **Step 3: Write `data/lab_data/ingest.py`**

```python
"""Download daily closes from Stooq into the warehouse parquet."""

from __future__ import annotations

import argparse
import io
import time
from pathlib import Path

import pandas as pd
import requests

STOOQ_URL = "https://stooq.com/q/d/l/?s={symbol}&i=d"


def stooq_symbol(ticker: str) -> str:
    return f"{ticker.lower()}.us"


def parse_stooq_csv(ticker: str, csv_text: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(csv_text))
    if "Close" not in df.columns:
        raise ValueError(f"unexpected response for {ticker}: {csv_text[:80]!r}")
    return pd.DataFrame(
        {
            "ticker": ticker.upper(),
            "date": pd.to_datetime(df["Date"]).dt.date,
            "close": df["Close"].astype(float),
        }
    )


def fetch_ticker(ticker: str, session: requests.Session) -> pd.DataFrame:
    resp = session.get(STOOQ_URL.format(symbol=stooq_symbol(ticker)), timeout=30)
    resp.raise_for_status()
    return parse_stooq_csv(ticker, resp.text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers-file", type=Path, default=Path("data/tickers.txt"))
    parser.add_argument("--out", type=Path, default=Path("data/warehouse/prices.parquet"))
    args = parser.parse_args()
    tickers = [t.strip() for t in args.tickers_file.read_text().splitlines() if t.strip()]
    session = requests.Session()
    frames = []
    for i, ticker in enumerate(tickers):
        try:
            frames.append(fetch_ticker(ticker, session))
            print(f"[{i + 1}/{len(tickers)}] {ticker} ok")
        except Exception as exc:  # noqa: BLE001 — skip-and-report is correct ingest behavior
            print(f"[{i + 1}/{len(tickers)}] {ticker} FAILED: {exc}")
        time.sleep(0.5)  # be polite to stooq
    if not frames:
        raise SystemExit("no tickers downloaded")
    df = pd.concat(frames, ignore_index=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(f"wrote {len(df)} rows / {df['ticker'].nunique()} tickers to {args.out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest data/tests/test_ingest.py -v`
Expected: 3 PASS

- [ ] **Step 5: Create `data/tickers.txt`** (50 lines)

```
AAPL
MSFT
NVDA
AMZN
GOOGL
META
TSLA
BRK-B
JPM
V
UNH
XOM
LLY
JNJ
PG
MA
HD
COST
ABBV
MRK
AVGO
PEP
KO
ADBE
WMT
CRM
BAC
TMO
CSCO
NFLX
AMD
ORCL
INTC
DIS
ABT
WFC
QCOM
CAT
IBM
GE
T
VZ
NKE
AXP
GS
BA
MCD
LIN
SPY
QQQ
```

- [ ] **Step 6: Run the real ingest (network) and sanity-check the warehouse**

Run: `uv run python -m lab_data.ingest`
Expected: per-ticker progress lines, final `wrote N rows / ~50 tickers to data/warehouse/prices.parquet`. A few FAILED tickers are acceptable (note them); zero downloads is not.

Run: `uv run python -c "import duckdb; print(duckdb.sql(\"SELECT ticker, count(*) n, min(date), max(date) FROM read_parquet('data/warehouse/prices.parquet') GROUP BY ticker ORDER BY ticker LIMIT 5\"))"`
Expected: 5 rows with plausible date ranges (decades of history is normal for Stooq).

- [ ] **Step 7: Commit**

```bash
git add data/lab_data/ingest.py data/tickers.txt data/tests/test_ingest.py
git commit -m "feat: stooq ingest into parquet warehouse"
```

---

## Task 4: CI skeleton

**Files:**
- Create: `.github/workflows/ci.yaml`

- [ ] **Step 1: Create `.github/workflows/ci.yaml`**

```yaml
name: ci

on:
  push:
    branches: [main]
  pull_request:

jobs:
  checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - name: Sync workspace
        run: uv sync --all-packages
      - name: Lint
        run: uv run ruff check .
      - name: Type-check
        run: uv run mypy .
      - name: Unit tests
        run: uv run pytest -q
```

- [ ] **Step 2: Run all three gates locally exactly as CI will**

Run: `uv run ruff check . && uv run mypy . && uv run pytest -q`
Expected: ruff clean, mypy clean, all tests pass. Fix anything before committing — this is the same bar CI enforces.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yaml
git commit -m "ci: lint, type-check, test skeleton"
```

---

## Task 5: Private GitHub remote + first green CI run

**Files:** none (remote operations)

- [ ] **Step 1: Verify gh auth**

Run: `gh auth status`
Expected: logged in. If not, user runs `! gh auth login` interactively.

- [ ] **Step 2: Create the private repo and push** (confirm with user before running — outward-facing)

```bash
cd /Users/ukran1um/Projects/learning/skills-platform-lab
gh repo create skills-platform-lab --private --source . --remote origin --push
```

Expected: repo created under the user's account, `main` pushed.

- [ ] **Step 3: Watch the first CI run**

Run: `gh run watch --exit-status` (or `gh run list --limit 1` until status is `completed success`)
Expected: green. **M0 acceptance met:** `uv sync` clean, warehouse parquet built, CI green.

If red: read the failing step's log (`gh run view --log-failed`), fix, commit, push, re-watch. Common first-run issue: mypy or ruff version drift between local and CI — pin via `uv.lock` is already in place, so failures should be real code issues.

---

## Task 6: `factor_correlation` skill package + SKILL.md

**Files:**
- Create: `skills/factor_correlation/pyproject.toml`, `skills/factor_correlation/SKILL.md`, `skills/factor_correlation/factor_correlation/__init__.py`, `skills/factor_correlation/factor_correlation/tools/__init__.py`

- [ ] **Step 1: Create `skills/factor_correlation/pyproject.toml`**

```toml
[project]
name = "factor-correlation"
version = "0.1.0"
description = "Pearson correlation of daily returns between tickers"
requires-python = ">=3.12"
dependencies = [
    "duckdb>=1.0",
    "pandas>=2.2",
    "pyarrow>=16",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["factor_correlation"]
```

- [ ] **Step 2: Create `skills/factor_correlation/SKILL.md`**

```markdown
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
```

- [ ] **Step 3: Create empty package inits and sync**

Create empty files `skills/factor_correlation/factor_correlation/__init__.py` and `skills/factor_correlation/factor_correlation/tools/__init__.py`.

Run: `uv sync --all-packages`
Expected: `factor-correlation` appears as a workspace member (picked up by the `skills/*` glob).

- [ ] **Step 4: Commit**

```bash
git add skills/factor_correlation uv.lock
git commit -m "feat: factor_correlation skill package scaffold with SKILL.md contract"
```

---

## Task 7: compute module (pure math)

**Files:**
- Create: `skills/factor_correlation/factor_correlation/tools/compute.py`
- Test: `skills/factor_correlation/tests/test_compute.py`

- [ ] **Step 1: Write the failing test `skills/factor_correlation/tests/test_compute.py`**

```python
from datetime import date

import pandas as pd
import pytest

from factor_correlation.tools.compute import correlation_matrix, daily_returns

DATES = [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6), date(2025, 1, 7)]


def _prices(ticker: str, closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"ticker": ticker, "date": DATES, "close": closes})


def _closes_from_returns(start: float, returns: list[float]) -> list[float]:
    closes = [start]
    for r in returns:
        closes.append(closes[-1] * (1 + r))
    return closes


def test_daily_returns_shape():
    prices = _prices("AAA", [100.0, 110.0, 104.5, 112.86])
    returns = daily_returns(prices)
    assert list(returns.columns) == ["AAA"]
    assert len(returns) == 3  # n-1 return rows
    assert returns["AAA"].iloc[0] == pytest.approx(0.10)


def test_perfectly_correlated_pair():
    a = _closes_from_returns(100.0, [0.10, -0.05, 0.08])
    b = [x * 2 for x in a]  # scaled prices -> identical returns
    prices = pd.concat([_prices("AAA", a), _prices("BBB", b)], ignore_index=True)
    corr = correlation_matrix(prices)
    assert corr.loc["AAA", "BBB"] == pytest.approx(1.0)


def test_inversely_correlated_pair():
    a = _closes_from_returns(100.0, [0.10, -0.05, 0.08])
    c = _closes_from_returns(100.0, [-0.10, 0.05, -0.08])  # negated returns
    prices = pd.concat([_prices("AAA", a), _prices("CCC", c)], ignore_index=True)
    corr = correlation_matrix(prices)
    assert corr.loc["AAA", "CCC"] == pytest.approx(-1.0, abs=1e-3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest skills/factor_correlation/tests/test_compute.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'factor_correlation.tools.compute'`

- [ ] **Step 3: Write `skills/factor_correlation/factor_correlation/tools/compute.py`**

```python
"""Pure correlation math. No I/O here."""

from __future__ import annotations

import pandas as pd


def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Long (ticker, date, close) -> wide frame of daily pct-change returns."""
    wide = prices.pivot(index="date", columns="ticker", values="close").sort_index()
    return wide.pct_change(fill_method=None).dropna(how="all")


def correlation_matrix(prices: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation of daily returns, pairwise over shared dates."""
    return daily_returns(prices).corr(method="pearson")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest skills/factor_correlation/tests/test_compute.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add skills/factor_correlation/factor_correlation/tools/compute.py skills/factor_correlation/tests/test_compute.py
git commit -m "feat: correlation math for factor_correlation skill"
```

---

## Task 8: fetch module (warehouse read)

**Files:**
- Create: `skills/factor_correlation/factor_correlation/tools/fetch.py`
- Test: `skills/factor_correlation/tests/test_fetch.py`

- [ ] **Step 1: Write the failing test `skills/factor_correlation/tests/test_fetch.py`**

```python
from datetime import date
from pathlib import Path

import pytest

from factor_correlation.tools.fetch import get_prices
from lab_data.fixtures import write_parquet


@pytest.fixture()
def warehouse(tmp_path: Path) -> Path:
    return write_parquet(tmp_path / "prices.parquet")


def test_get_prices_filters_tickers_and_dates(warehouse: Path):
    df = get_prices(["AAPL", "MSFT"], date(2025, 1, 1), date(2025, 3, 31), parquet=warehouse)
    assert set(df["ticker"]) == {"AAPL", "MSFT"}
    assert df["date"].min() >= date(2025, 1, 1)
    assert df["date"].max() <= date(2025, 3, 31)
    assert list(df.columns) == ["ticker", "date", "close"]


def test_get_prices_is_case_insensitive(warehouse: Path):
    df = get_prices(["aapl"], date(2025, 1, 1), date(2025, 1, 31), parquet=warehouse)
    assert set(df["ticker"]) == {"AAPL"}


def test_get_prices_missing_warehouse_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="warehouse parquet not found"):
        get_prices(["AAPL"], date(2025, 1, 1), date(2025, 1, 31), parquet=tmp_path / "nope.parquet")
```

Note: this test imports `lab_data` across workspace members — that's intentional (fixtures are the shared test substrate) and works because both are installed in the one workspace venv.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest skills/factor_correlation/tests/test_fetch.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'factor_correlation.tools.fetch'`

- [ ] **Step 3: Write `skills/factor_correlation/factor_correlation/tools/fetch.py`**

```python
"""Load prices from the warehouse parquet (laptop context: direct file access)."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

DEFAULT_WAREHOUSE = Path("data/warehouse/prices.parquet")
ENV_VAR = "PRICES_PARQUET"


def warehouse_path() -> Path:
    return Path(os.environ.get(ENV_VAR, str(DEFAULT_WAREHOUSE)))


def get_prices(
    tickers: list[str],
    start: date,
    end: date,
    parquet: Path | None = None,
) -> pd.DataFrame:
    parquet = parquet or warehouse_path()
    if not parquet.exists():
        raise FileNotFoundError(
            f"warehouse parquet not found at {parquet}; "
            f"run `uv run python -m lab_data.ingest` or set ${ENV_VAR}"
        )
    upper = [t.upper() for t in tickers]
    placeholders = ",".join("?" for _ in upper)
    query = f"""
        SELECT ticker, date, close
        FROM read_parquet(?)
        WHERE ticker IN ({placeholders}) AND date BETWEEN ? AND ?
        ORDER BY ticker, date
    """
    df = duckdb.execute(query, [str(parquet), *upper, start, end]).df()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest skills/factor_correlation/tests/test_fetch.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add skills/factor_correlation/factor_correlation/tools/fetch.py skills/factor_correlation/tests/test_fetch.py
git commit -m "feat: warehouse price fetch for factor_correlation skill"
```

---

## Task 9: CLI entrypoint

**Files:**
- Create: `skills/factor_correlation/factor_correlation/cli.py`
- Test: `skills/factor_correlation/tests/test_cli.py`

- [ ] **Step 1: Write the failing test `skills/factor_correlation/tests/test_cli.py`**

```python
import json
from datetime import date
from pathlib import Path

import pytest

from factor_correlation.cli import run
from lab_data.fixtures import write_parquet


@pytest.fixture()
def warehouse_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = write_parquet(tmp_path / "prices.parquet")
    monkeypatch.setenv("PRICES_PARQUET", str(path))
    return path


def test_run_two_tickers_has_correlation_value(warehouse_env: Path):
    result = run(["AAPL", "MSFT"], date(2025, 1, 1), date(2025, 6, 30))
    assert result["tickers"] == ["AAPL", "MSFT"]
    assert "correlation_value" in result
    assert -1.0 <= result["correlation_value"] <= 1.0
    assert result["matrix"]["AAPL"]["MSFT"] == result["correlation_value"]
    json.dumps(result)  # must be JSON-serializable


def test_run_three_tickers_matrix_only(warehouse_env: Path):
    result = run(["AAPL", "MSFT", "NVDA"], date(2025, 1, 1), date(2025, 6, 30))
    assert "correlation_value" not in result
    assert set(result["matrix"].keys()) == {"AAPL", "MSFT", "NVDA"}
    assert result["matrix"]["AAPL"]["AAPL"] == pytest.approx(1.0)


def test_run_unknown_ticker_exits(warehouse_env: Path):
    with pytest.raises(SystemExit, match="no price data"):
        run(["ZZZTOP"], date(2025, 1, 1), date(2025, 6, 30))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest skills/factor_correlation/tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'factor_correlation.cli'`

- [ ] **Step 3: Write `skills/factor_correlation/factor_correlation/cli.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest skills/factor_correlation/tests/test_cli.py -v`
Expected: 3 PASS

- [ ] **Step 5: Run the CLI against the real warehouse**

Run: `uv run python -m factor_correlation.cli AAPL MSFT --start 2025-01-01 --end 2025-12-31`
Expected: JSON with a plausible `correlation_value` (large-cap tech pairs typically land ~0.5–0.8). Record the number — the manual checkpoint in Task 11 compares against it.

- [ ] **Step 6: Commit**

```bash
git add skills/factor_correlation/factor_correlation/cli.py skills/factor_correlation/tests/test_cli.py
git commit -m "feat: JSON CLI for factor_correlation skill"
```

---

## Task 10: Wire skill into local Claude Code

**Files:**
- Create: `.claude/skills/factor_correlation` (symlink)

- [ ] **Step 1: Create the symlink**

```bash
mkdir -p .claude/skills
ln -s ../../skills/factor_correlation .claude/skills/factor_correlation
```

Run: `ls -la .claude/skills/ && cat .claude/skills/factor_correlation/SKILL.md | head -5`
Expected: symlink resolves; frontmatter prints.

- [ ] **Step 2: Commit** (the symlink is committed so the wiring is reproducible)

```bash
git add .claude/skills
git commit -m "feat: expose factor_correlation to local Claude Code via skills symlink"
```

- [ ] **Step 3: Push and verify CI is still green**

```bash
git push && gh run watch --exit-status
```

Expected: green — now including all skill tests.

---

## Task 11: Manual checkpoint — M1 acceptance (user-run)

**Files:** none

- [ ] **Step 1: User verification.** In a NEW Claude Code session at the repo root, ask:

> "How correlated were AAPL and MSFT daily returns in 2025?"

Expected behavior:
1. Claude Code discovers and invokes the `factor_correlation` skill (visible in the transcript).
2. It runs the CLI from SKILL.md via Bash.
3. The reported number matches Task 9 Step 5's direct CLI run (same window).
4. The answer mentions it's a correlation of daily returns and names the window.

If the skill is NOT discovered: check `claude skills` / the skills listing in that session; if symlinked skills aren't picked up, replace the symlink with a checked-in copy of SKILL.md under `.claude/skills/factor_correlation/` that references the canonical path — and record the symlink limitation in LEARNINGS.md.

- [ ] **Step 2: Record the first LEARNINGS.md entry** (whatever was actually observed — discovery quirks, the agent ignoring reporting rules, ingest failures from Task 3, anything). Commit:

```bash
git add LEARNINGS.md
git commit -m "docs: first learnings from laptop-context skill run"
git push
```

**M1 acceptance met when:** the skill answers correctly in local Claude Code from local parquet.

---

## Self-review notes (run after drafting; issues found and fixed inline)

- **Spec coverage:** M0 acceptance (uv sync / ingest / CI green) → Tasks 1–5. M1 acceptance (skill in local Claude Code) → Tasks 6–11. Fixtures generator (spec: "small fixtures set for staging/evals") → Task 2, reused by Tasks 8–9 tests exactly as the spec's eval-harness laptop mode will.
- **Type consistency:** `make_prices`/`parse_stooq_csv`/`get_prices` all emit `(ticker: str, date: datetime.date, close: float)`; `daily_returns` pivots on those names; `run()` consumes both. `write_parquet(out_path)` signature matches all call sites.
- **Placeholder scan:** clean — every code step has complete code; every run step has a command and expected output.
- **Known risk:** Stooq throttling or symbol misses during Task 3 Step 6 — the skip-and-report loop tolerates partial failure; acceptance requires "a few FAILED at most," and failures go to LEARNINGS.md.
