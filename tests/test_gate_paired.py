"""Paired-seed gate tests (harness/gate.py decide_paired)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))
from gate import decide_paired  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


def batch(scores: dict[str, float], suite: str = "query") -> dict:
    """Build a scores.json 'tasks' dict from workspace->mixed (hard=soft=x)."""
    return {k: {"hard": v, "soft": v, "suite": suite} for k, v in scores.items()}


def grid(n: int, base: float, suite: str = "query") -> dict[str, float]:
    return {f"{suite}-{i:02d}_s{i % 2}": base for i in range(n)}


def test_uniform_gain_accepts():
    ref = batch(grid(10, 0.8))
    cand = batch({k: v + 0.05 for k, v in grid(10, 0.8).items()})
    r = decide_paired(cand, [ref], current=0.8, best=0.8,
                      primary_suite="query")
    assert r["action"] == "accept_new_best"
    assert r["paired"]["n_pairs"] == 10


def test_small_consistent_gain_beats_scalar_bar():
    """+0.02 everywhere: scalar gating with min_delta 0.03 would discard
    this real gain; the paired gate must accept it."""
    ref = batch(grid(20, 0.9))
    cand = batch({k: v + 0.02 for k, v in grid(20, 0.9).items()})
    r = decide_paired(cand, [ref], current=0.9, best=0.9,
                      primary_suite="query")
    assert r["action"] == "accept_new_best"


def test_sparse_real_gain_accepts():
    """3 fixed rollouts improve by +0.10, rest unchanged: the m72hf
    step-5 shape. Mean 0.015, z ~1.8 -> accept."""
    base = grid(20, 0.85)
    cand_scores = dict(base)
    for k in list(cand_scores)[:3]:
        cand_scores[k] += 0.10
    r = decide_paired(batch(cand_scores), [batch(base)], current=0.85,
                      best=0.85, primary_suite="query")
    assert r["action"] == "accept_new_best"
    assert r["paired"]["z_stat"] > 1.645


def test_pure_noise_rejects():
    """Alternating +/-0.1 with mean ~0 must reject."""
    base = grid(20, 0.8)
    cand_scores = {k: v + (0.1 if i % 2 else -0.1)
                   for i, (k, v) in enumerate(base.items())}
    r = decide_paired(batch(cand_scores), [batch(base)], current=0.8,
                      best=0.8, primary_suite="query")
    assert r["action"] == "reject"


def test_no_change_rejects():
    base = grid(12, 0.7)
    r = decide_paired(batch(base), [batch(base)], current=0.7, best=0.7,
                      primary_suite="query")
    assert r["action"] == "reject"


def test_insufficient_pairs_rejects():
    base = grid(4, 0.8)
    cand = batch({k: v + 0.1 for k, v in base.items()})
    r = decide_paired(cand, [batch(base)], current=0.8, best=0.8,
                      primary_suite="query")
    assert r["action"] == "reject" and "insufficient" in r["reason"]


def test_secondary_significant_regression_rejects():
    prim_ref = batch(grid(10, 0.8))
    prim_cand = batch({k: v + 0.05 for k, v in grid(10, 0.8).items()})
    sec_ref = batch(grid(8, 1.0, suite="ddl"), suite="ddl")
    sec_cand = batch({k: 0.8 for k in grid(8, 1.0, suite="ddl")}, suite="ddl")
    r = decide_paired({**prim_cand, **sec_cand}, [{**prim_ref, **sec_ref}],
                      current=0.8, best=0.8, primary_suite="query",
                      secondary_suite="ddl")
    assert r["action"] == "reject" and "secondary" in r["reason"]


def test_secondary_noise_dip_tolerated():
    prim_ref = batch(grid(10, 0.8))
    prim_cand = batch({k: v + 0.05 for k, v in grid(10, 0.8).items()})
    sec_keys = [f"d{i}_s0" for i in range(8)]
    sec_ref = {k: {"hard": 1.0, "soft": 1.0, "suite": "ddl"} for k in sec_keys}
    # one rollout dips, others unchanged: mean<0 but not significant
    sec_cand = {k: {"hard": 1.0 if i else 0.5, "soft": 1.0 if i else 0.5,
                    "suite": "ddl"} for i, k in enumerate(sec_keys)}
    r = decide_paired({**prim_cand, **sec_cand}, [{**prim_ref, **sec_ref}],
                      current=0.8, best=0.8, primary_suite="query",
                      secondary_suite="ddl")
    assert r["action"] == "accept_new_best"


def test_multiple_references_average():
    base = grid(10, 0.8)
    ref_low = batch({k: v - 0.05 for k, v in base.items()})
    ref_high = batch({k: v + 0.05 for k, v in base.items()})
    cand = batch({k: v + 0.03 for k, v in base.items()})
    r = decide_paired(cand, [ref_low, ref_high], current=0.8, best=0.8,
                      primary_suite="query")
    assert r["action"] == "accept_new_best"
    assert abs(r["paired"]["mean_delta"] - 0.03) < 1e-9


def test_unpaired_keys_excluded_and_counted():
    base = grid(10, 0.8)
    cand_scores = {k: v + 0.05 for k, v in base.items()}
    cand_scores["brand_new_s0"] = 0.9
    r = decide_paired(batch(cand_scores), [batch(base)], current=0.8,
                      best=0.8, primary_suite="query")
    assert r["paired"]["unpaired"] == 1
    assert r["paired"]["n_pairs"] == 10


def test_no_best_caps_at_accept():
    base = grid(10, 0.8)
    cand = batch({k: v + 0.05 for k, v in base.items()})
    r = decide_paired(cand, [batch(base)], current=0.8, best=0.8,
                      primary_suite="query", best_eligible=False)
    assert r["action"] == "accept"


def test_cli_paired(tmp_path):
    base = grid(10, 0.8)
    (tmp_path / "ref.json").write_text(json.dumps({"tasks": batch(base)}))
    (tmp_path / "cand.json").write_text(json.dumps(
        {"tasks": batch({k: v + 0.05 for k, v in base.items()})}))
    out = subprocess.run(
        [sys.executable, str(REPO / "harness" / "gate.py"), "--paired",
         "--candidate-scores", str(tmp_path / "cand.json"),
         "--reference-scores", str(tmp_path / "ref.json"),
         "--current", "0.8", "--best", "0.8", "--primary-suite", "query"],
        capture_output=True, text=True, check=True)
    decision = json.loads(out.stdout)
    assert decision["action"] == "accept_new_best"
    assert decision["paired"]["n_pairs"] == 10


def test_cli_scalar_mode_unchanged(tmp_path):
    out = subprocess.run(
        [sys.executable, str(REPO / "harness" / "gate.py"),
         "--candidate", "0.7", "--current", "0.65", "--best", "0.7",
         "--min-delta", "0.02"],
        capture_output=True, text=True, check=True)
    assert json.loads(out.stdout)["action"] == "accept"


def test_cli_paired_merges_candidate_extension(tmp_path):
    """Near-miss retest: the extension batch (new seeds) unions with the
    original candidate batch, and reference files covering those seeds
    pair up."""
    base = grid(10, 0.8)
    ext = {k.replace("_s0", "_s2").replace("_s1", "_s3"): v
           for k, v in base.items()}
    (tmp_path / "ref1.json").write_text(json.dumps({"tasks": batch(base)}))
    (tmp_path / "ref2.json").write_text(json.dumps({"tasks": batch(ext)}))
    (tmp_path / "cand1.json").write_text(json.dumps(
        {"tasks": batch({k: v + 0.03 for k, v in base.items()})}))
    (tmp_path / "cand2.json").write_text(json.dumps(
        {"tasks": batch({k: v + 0.03 for k, v in ext.items()})}))
    out = subprocess.run(
        [sys.executable, str(REPO / "harness" / "gate.py"), "--paired",
         "--candidate-scores", str(tmp_path / "cand1.json"),
         str(tmp_path / "cand2.json"),
         "--reference-scores", str(tmp_path / "ref1.json"),
         str(tmp_path / "ref2.json"),
         "--current", "0.8", "--best", "0.8", "--primary-suite", "query"],
        capture_output=True, text=True, check=True)
    decision = json.loads(out.stdout)
    assert decision["paired"]["n_pairs"] == 20
    assert decision["action"] == "accept_new_best"
