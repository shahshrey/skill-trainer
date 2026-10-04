"""Rubric for the sql-queries suite: run the agent's query, diff the rows.

score(task, workdir, mode) -> {hard, soft, checks}

The agent's reply lands in <workdir>/output.txt. The rubric pulls the
last fenced block out of it (or the whole reply when there is no
fence), runs it read-only against the suite's own refs/shop.db (not the
workspace copy, which the agent could have edited), and compares the
rows with the task's reference query. Column names are
ignored; numbers match within a cent; row order matters only when the
task says "ordered": true.

hard is 1 only for an exact row match. soft gives partial credit so the
editor can tell "almost right" from "did not run":
  0.3  the query ran
  0.2  the column count matches
  0.5  scaled by row overlap (Jaccard) with the reference

A wrong answer also gets a symptom name. Each task carries probes: naive
queries that each break exactly one house convention. When the agent's
rows match a probe's rows, the checks say `symptom:<class>` and the
editor can look the class up in failure_classes.md. Stdlib only.
"""
from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path

DB = Path(__file__).resolve().parent / "refs" / "shop.db"
FENCE_RE = re.compile(r"```[\w-]*[ \t]*\n([\s\S]*?)```")
CENT = 0.011  # tolerance for money and averages
MAX_DIFF_ROWS = 2  # how many differing rows a receipt shows the editor
QUERY_SECONDS = 5.0  # a runaway query (cross join, endless CTE) is a wrong answer


def extract_sql(output: str) -> str:
    fences = FENCE_RE.findall(output)
    sql = fences[-1] if fences else output
    return sql.strip().rstrip(";").strip()


def run_query(db: Path, sql: str) -> list[tuple]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    deadline = time.monotonic() + QUERY_SECONDS
    con.set_progress_handler(lambda: time.monotonic() > deadline, 10_000)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def same_cell(a, b) -> bool:
    x, y = _number(a), _number(b)
    if x is not None and y is not None:
        return abs(x - y) <= CENT
    return str(a).strip() == str(b).strip()


def same_row(a: tuple, b: tuple) -> bool:
    return len(a) == len(b) and all(same_cell(x, y) for x, y in zip(a, b))


def diff_rows(want: list[tuple], got: list[tuple]) -> tuple[list[tuple], list[tuple]]:
    """Rows only in want (missing) and only in got (extra), order-insensitive."""
    unmatched = list(got)
    missing = []
    for row in want:
        match = next((g for g in unmatched if same_row(row, g)), None)
        if match is None:
            missing.append(row)
        else:
            unmatched.remove(match)
    return missing, unmatched


def same_rows(want: list[tuple], got: list[tuple]) -> bool:
    missing, extra = diff_rows(want, got)
    return not missing and not extra


def score(task: dict, workdir: Path, mode: str = "cheap") -> dict:
    workdir = Path(workdir)
    checks: list[str] = []
    output_path = workdir / "output.txt"
    output = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
    sql = extract_sql(output)
    if not sql:
        return {"hard": 0, "soft": 0.0, "checks": ["no_sql"]}

    want = run_query(DB, task["scoring"]["reference_sql"])
    try:
        got = run_query(DB, sql)
    except sqlite3.Error as exc:
        return {"hard": 0, "soft": 0.0, "checks": [f"sql_error:{str(exc)[:80]}"]}
    checks.append("ran")
    soft = 0.3

    want_cols = len(want[0]) if want else 0
    got_cols = len(got[0]) if got else 0
    if want and got and want_cols != got_cols:
        checks.append(f"cols:{got_cols}!={want_cols}")
    else:
        soft += 0.2

    missing, extra = diff_rows(want, got)
    matched = len(want) - len(missing)
    union = len(want) + len(extra)
    soft += 0.5 * (matched / union if union else 1.0)
    if len(got) != len(want):
        checks.append(f"rows:{len(got)}!={len(want)}")
    for row in missing[:MAX_DIFF_ROWS]:
        checks.append(f"missing_row:{row}")
    for row in extra[:MAX_DIFF_ROWS]:
        checks.append(f"extra_row:{row}")

    exact = not missing and not extra
    if exact and task["scoring"].get("ordered"):
        exact = all(same_row(w, g) for w, g in zip(want, got))
        if not exact:
            checks.append("order_differs")
            soft -= 0.1
    if exact:
        checks.append("rows_match")
    else:
        checks.extend(symptoms(task, DB, got))
    return {"hard": int(exact), "soft": round(soft, 4), "checks": checks}


def symptoms(task: dict, db: Path, got: list[tuple]) -> list[str]:
    """Names of the probes whose rows the agent reproduced."""
    matched = [f"symptom:{name}"
               for name, probe_sql in task["scoring"].get("probes", {}).items()
               if same_rows(run_query(db, probe_sql), got)]
    return matched or ["symptom:unclassified"]
