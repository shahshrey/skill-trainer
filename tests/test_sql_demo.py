"""The bundled examples/sql-demo suite must keep working on a fresh clone:
the tutorial builds it step by step and trains against it. Deterministic,
no LLM calls: the rubric runs SQL, nothing else."""
import importlib.util
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from lint_skill import lint
from score import score_task, suite_config

REPO = Path(__file__).resolve().parent.parent
EX = REPO / "examples" / "sql-demo"
SKILL = EX / "skills" / "sql-queries" / "SKILL.md"
SUITE = EX / "tasks" / "sql-queries"
DB = SUITE / "refs" / "shop.db"


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rubric = _load(SUITE / "rubric.py")
build_db = _load(SUITE / "build_db.py")


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


ALL_TASKS = [t for split in ("train", "val", "test")
             for t in load_jsonl(SUITE / f"{split}.jsonl")]
BY_ID = {t["id"]: t for t in ALL_TASKS}
IDS = list(BY_ID)


def workspace(tmp_path: Path, task: dict, reply: str) -> Path:
    wd = tmp_path / task["id"]
    wd.mkdir(parents=True)
    shutil.copy(DB, wd / "shop.db")
    (wd / "output.txt").write_text(reply)
    return wd


def fenced(sql: str) -> str:
    return "```sql\n" + sql + ";\n```"


def test_skill_passes_lint_in_both_deploy_modes():
    for mode in ("prompt", "package"):
        assert lint(SKILL, deploy_mode=mode)["status"] == "pass", mode


def test_build_db_is_deterministic(tmp_path):
    build_db.build(tmp_path)
    query = "SELECT * FROM orders ORDER BY id"
    assert (sqlite3.connect(tmp_path / "shop.db").execute(query).fetchall()
            == sqlite3.connect(DB).execute(query).fetchall())
    assert (tmp_path / "schema.sql").read_text() == (SUITE / "refs" / "schema.sql").read_text()


@pytest.mark.parametrize("task_id", IDS)
def test_reference_query_scores_hard_one_through_score_py(tmp_path, task_id):
    task = BY_ID[task_id]
    wd = workspace(tmp_path, task, fenced(task["scoring"]["reference_sql"]))
    result = score_task(task, wd, "cheap", suite_config(SUITE), rubric, suite=SUITE)
    assert result == {"hard": 1, "soft": 1.0, "checks": ["ran", "rows_match"], "mode": "rubric"}


@pytest.mark.parametrize("task_id", IDS)
def test_every_probe_fails_and_names_its_own_symptom(tmp_path, task_id):
    """Each probe breaks one convention, so it must score 0 and the rubric
    must attribute the failure to that probe's class. A probe whose rows
    equal the reference could never fire and is a suite bug."""
    task = BY_ID[task_id]
    assert task["scoring"]["probes"], "task ships no probes"
    for symptom, sql in task["scoring"]["probes"].items():
        result = rubric.score(task, workspace(tmp_path / symptom, task, fenced(sql)))
        assert result["hard"] == 0, (task_id, symptom)
        assert f"symptom:{symptom}" in result["checks"], (task_id, symptom, result)


def test_multiple_statements_are_not_a_query(tmp_path):
    task = BY_ID["t04-top3-products"]
    result = rubric.score(task, workspace(tmp_path, task, "SELECT 1; SELECT 2"))
    assert result["hard"] == 0
    assert result["checks"][0].startswith("sql_error")


def test_prose_around_the_fence_is_tolerated(tmp_path):
    task = BY_ID["t03-orders-in-march"]
    reply = ("Here is the query:\n\n" + fenced(task["scoring"]["reference_sql"])
             + "\n\nThis counts March orders.")
    assert rubric.score(task, workspace(tmp_path, task, reply))["hard"] == 1


def test_sqlite_tagged_fence_is_extracted(tmp_path):
    task = BY_ID["t01-total-revenue"]
    reply = "```sqlite\n" + task["scoring"]["reference_sql"] + ";\n```"
    assert rubric.score(task, workspace(tmp_path, task, reply))["hard"] == 1


def test_runaway_query_is_interrupted(tmp_path, monkeypatch):
    monkeypatch.setattr(rubric, "QUERY_SECONDS", 0.2)
    task = BY_ID["t01-total-revenue"]
    endless = "WITH RECURSIVE r(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM r) SELECT x FROM r"
    result = rubric.score(task, workspace(tmp_path, task, endless))
    assert result["hard"] == 0
    assert result["checks"][0].startswith("sql_error")


def test_editing_the_workspace_db_does_not_move_the_reference(tmp_path):
    """A rollout that deletes the test accounts from its own shop.db copy
    must not turn the naive query into a pass."""
    task = BY_ID["t01-total-revenue"]
    wd = workspace(tmp_path, task, fenced(task["scoring"]["probes"]["ghost-rows"]))
    con = sqlite3.connect(wd / "shop.db")
    con.execute("DELETE FROM customers WHERE email LIKE '%@example.com'")
    con.commit()
    con.close()
    assert rubric.score(task, wd)["hard"] == 0


def test_ordered_tasks_reject_a_reshuffled_ranking(tmp_path):
    task = BY_ID["t04-top3-products"]
    # same three rows as the reference, presented lowest first
    sql = f"SELECT * FROM ({task['scoring']['reference_sql']}) ORDER BY 2 ASC"
    result = rubric.score(task, workspace(tmp_path, task, sql))
    assert result["hard"] == 0
    assert "order_differs" in result["checks"]


def test_unrecognized_wrong_answer_is_unclassified(tmp_path):
    task = BY_ID["t01-total-revenue"]
    result = rubric.score(task, workspace(tmp_path, task, "SELECT 42"))
    assert result["hard"] == 0
    assert "symptom:unclassified" in result["checks"]
