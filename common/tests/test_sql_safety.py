import pytest

from lab_common.sql_safety import validate_select_only


def test_select_passes():
    assert validate_select_only("SELECT count(*) FROM prices") == "SELECT count(*) FROM prices"


def test_with_cte_passes():
    q = "WITH x AS (SELECT 1 AS n) SELECT n FROM x"
    assert validate_select_only(q) == q


def test_trailing_semicolon_stripped():
    assert validate_select_only("SELECT 1;") == "SELECT 1"


def test_non_select_rejected():
    with pytest.raises(ValueError, match="SELECT"):
        validate_select_only("DROP TABLE prices")


def test_multiple_statements_rejected():
    with pytest.raises(ValueError, match="single statement"):
        validate_select_only("SELECT 1; SELECT 2")


def test_forbidden_keyword_rejected():
    with pytest.raises(ValueError, match="forbidden"):
        validate_select_only("SELECT * FROM prices; INSERT INTO prices VALUES (1)")
