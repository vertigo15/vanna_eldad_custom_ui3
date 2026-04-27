"""Tests for the SELECT-only guard in `src.tools.sql_tool`."""

from __future__ import annotations

import pytest

from src.tools.sql_tool import is_read_only_sql


@pytest.mark.parametrize(
    "sql, expected",
    [
        ("SELECT 1", True),
        ("  select 1", True),
        ("SELECT *\nFROM foo", True),
        ("WITH cte AS (SELECT 1) SELECT * FROM cte", True),
        ("with cte as (select 1) select * from cte", True),
        ("-- a leading comment\nSELECT 1", True),
        ("/* foo */ SELECT 1", True),
        ("-- one\n/* two */\n-- three\nSELECT 1", True),
        ("INSERT INTO foo VALUES (1)", False),
        ("UPDATE foo SET x = 1", False),
        ("DELETE FROM foo", False),
        ("DROP TABLE foo", False),
        ("TRUNCATE foo", False),
        ("GRANT ALL ON foo TO bar", False),
        ("CREATE TABLE foo (id INT)", False),
        # Comment-prefixed mutation: the comment is stripped, then the leading
        # keyword check fails on DELETE.
        ("/* trick */ DELETE FROM foo", False),
        # EXPLAIN is intentionally rejected today (could revisit; reject is
        # the safer default for an LLM-driven runner).
        ("EXPLAIN SELECT 1", False),
        ("", False),
        ("   ", False),
        ("\n\n", False),
    ],
)
def test_is_read_only_sql(sql, expected):
    assert is_read_only_sql(sql) is expected
