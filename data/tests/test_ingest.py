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
