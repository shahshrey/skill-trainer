"""Evidence-coverage audit (harness/coverage.py)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))
from coverage import normalize, report  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


def entry(hard: int, checks: list[str], suite: str = "query") -> dict:
    return {"hard": hard, "soft": float(hard), "checks": checks,
            "suite": suite}


def test_normalize_collapses_magnitudes():
    assert normalize("row_f1_0.372") == normalize("row_f1_0.981")
    assert normalize("rows_got_92_want_21") == normalize("rows_got_5_want_9")
    assert normalize("command_exit:1") == normalize("command_exit:2")
    assert normalize("order_wrong") == "order_wrong"


def test_starved_when_val_failure_class_absent_from_train():
    train = [entry(1, ["ran_ok", "exact"]), entry(0, ["ran_ok", "order_wrong"])]
    val = [entry(0, ["ran_ok", "columns_mismatch_got_2_want_3"]),
           entry(0, ["ran_ok", "order_wrong"]),
           entry(1, ["ran_ok", "exact"])]
    r = report(train, val)
    assert r["starved"] is True
    assert r["starved_fraction"] == 0.5
    assert r["val_only_signatures"][0]["checks"] == ["columns_mismatch_got_#_want_#"]


def test_not_starved_when_classes_overlap():
    train = [entry(0, ["ran_ok", "order_wrong"]), entry(1, ["ran_ok", "exact"])]
    val = [entry(0, ["ran_ok", "order_wrong"]), entry(1, ["ran_ok", "exact"])]
    r = report(train, val)
    assert r["starved"] is False and r["val_only_signatures"] == []


def test_benign_checks_never_form_signatures():
    """Checks that appear on passing rollouts (ran_ok etc.) are noise."""
    train = [entry(1, ["ran_ok", "columns_ok", "exact"])]
    val = [entry(0, ["ran_ok", "columns_ok", "not_exact"])]
    r = report(train, val)
    sig = r["val_only_signatures"][0]["checks"]
    assert sig == ["not_exact"]  # ran_ok / columns_ok stripped as benign


def test_report_is_leakage_safe():
    """No task ids, workspace names, or prompt text may appear."""
    train = [dict(entry(0, ["order_wrong"]), task="query-999",
                  secret="TOP-SECRET-TASK-TEXT")]
    val = [dict(entry(0, ["row_f1_0.1"]), task="query-888")]
    blob = json.dumps(report(train, val))
    assert "query-999" not in blob and "query-888" not in blob
    assert "TOP-SECRET" not in blob


def test_cli_on_synthetic_files(tmp_path):
    (tmp_path / "train.json").write_text(json.dumps(
        {"tasks": {"t1_s0": entry(0, ["order_wrong"])}}))
    (tmp_path / "val.json").write_text(json.dumps(
        {"tasks": {"v1_s0": entry(0, ["sql_error: near X"])}}))
    out = subprocess.run(
        [sys.executable, str(REPO / "harness" / "coverage.py"),
         "--train", str(tmp_path / "train.json"),
         "--val", str(tmp_path / "val.json")],
        capture_output=True, text=True, check=True)
    r = json.loads(out.stdout)
    assert r["starved"] is True and "v1_s0" not in out.stdout
