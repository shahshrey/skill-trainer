"""Audit script: each audit catches its violation and passes clean runs."""
import json
from pathlib import Path

import audit_run
from audit_run import audit_leakage, audit_monotone, audit_reproposal, load_tsv

TSV = """# comment
commit\tepoch\tstep\tmode\tval_mixed\tval_hard\tval_soft\tsec_mixed\tn_val_rollouts\tstatus\tedits_applied\tdescription
aaa1111\t0\t0\tcheap\t0.50\t0.5\t0.5\t\t12\tkeep_best\t0\tbaseline
bbb2222\t0\t1\tcheap\t0.60\t0.6\t0.6\t\t12\tkeep_best\t1\tgood edit
ccc3333\t0\t2\tcheap\t0.55\t0.5\t0.6\t\t12\tdiscard\t1\tappend@"": "Always do X"
ddd4444\t0\t3\tcheap\t0.55\t0.5\t0.6\t\t12\tdiscard\t1\tappend@"": "Always do X"
eee5555\t1\t9\tcheap\t0.55\t0.5\t0.6\t\t12\tdiscard\t1\tappend@"": "Always do X"
"""


def write_tsv(tmp_path: Path, text: str = TSV) -> list[dict]:
    p = tmp_path / "results.tsv"
    p.write_text(text)
    return load_tsv(p)


def test_load_tsv_skips_comments(tmp_path):
    rows = write_tsv(tmp_path)
    assert len(rows) == 5
    assert rows[0]["status"] == "keep_best"


def test_reproposal_caught_within_epoch_only(tmp_path):
    rows = write_tsv(tmp_path)
    failures = audit_reproposal(rows)
    assert len(failures) == 1  # step 3 repeats step 2's edit; epoch 1 repeat is fine
    assert "step 3" in failures[0]


def test_monotone_flags_decreasing_best(tmp_path):
    bad = TSV.replace('bbb2222\t0\t1\tcheap\t0.60', 'bbb2222\t0\t1\tcheap\t0.40')
    rows = write_tsv(tmp_path, bad)
    failures = audit_monotone(rows, None, "cheap", tmp_path)
    assert failures and "decreased" in failures[0]


def test_monotone_clean(tmp_path):
    rows = write_tsv(tmp_path)
    assert audit_monotone(rows, None, "cheap", tmp_path) == []


def test_leakage_detects_val_id_in_editor_prompt(tmp_path):
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "val.jsonl").write_text(json.dumps(
        {"id": "val-secret-1", "prompt": "Clone the reference GIF exactly as shown in the input."}) + "\n")
    run = tmp_path / "run"
    (run / "step_1").mkdir(parents=True)
    (run / "step_1" / "editor_error_filled.md").write_text(
        "receipts mention val-secret-1 accidentally")
    failures = audit_leakage(run, suite)
    assert failures and "val-secret-1" in failures[0]


def test_leakage_clean_run(tmp_path):
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "val.jsonl").write_text(json.dumps({"id": "val-1", "prompt": "hidden"}) + "\n")
    run = tmp_path / "run"
    (run / "step_1").mkdir(parents=True)
    (run / "step_1" / "editor_error_filled.md").write_text("only train receipts here")
    assert audit_leakage(run, suite) == []


def _skill_repo(tmp_path, commits):
    """Tiny repo whose skill file evolves per (subject, protected_content)."""
    import subprocess
    repo = tmp_path / "repo"
    (repo / "skills").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    skill = repo / "skills" / "SKILL.md"
    shas = []
    for subject, protected in commits:
        skill.write_text("# S\nbody\n\n<!-- PROTECTED:SLOW_UPDATE:START -->\n"
                         f"{protected}\n<!-- PROTECTED:SLOW_UPDATE:END -->\n")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", subject], check=True)
        shas.append(subprocess.run(["git", "-C", str(repo), "rev-parse", "--short=7", "HEAD"],
                                   capture_output=True, text=True).stdout.strip())
    return repo, skill, shas


def test_protected_flags_nonepoch_change_and_since_exempts_history(tmp_path):
    repo, skill, shas = _skill_repo(tmp_path, [
        ("import skill", "v0"),
        ("dev commit touches protected", "v1"),   # pre-run history
        ("epoch 1 boundary", "v2"),                # legal in-run change
    ])
    full = audit_run.audit_protected(skill, repo)
    assert any("dev commit" in f for f in full)
    scoped = audit_run.audit_protected(skill, repo, since=shas[1])
    assert scoped == []  # run started at shas[1]; earlier history is exempt


def test_reproposal_ignores_identical_gate_reasons():
    """sql05 false positive: two DIFFERENT edits rejected with numerically
    identical paired-gate reasons must not be flagged as a re-proposal."""
    import sys
    from pathlib import Path as P
    sys.path.insert(0, str(P(__file__).resolve().parent.parent / "harness"))
    from audit_run import audit_reproposal
    rows = [
        {"epoch": "0", "step": "1", "status": "discard", "description":
         'gate reject (paired +0.0190, se 0.0190, not significant) | '
         'replace@"- Dedupe events": "keep the first row per key"'},
        {"epoch": "0", "step": "3", "status": "discard", "description":
         'gate reject (paired +0.0190, se 0.0190, not significant) | '
         'insert_after@"- Use the exact output": "time series sort asc"'},
    ]
    assert audit_reproposal(rows) == []
    # a genuinely re-proposed edit op must still be caught
    rows.append({"epoch": "0", "step": "5", "status": "discard",
                 "description":
                 'gate reject (paired -0.02) | '
                 'replace@"- Dedupe events": "keep the first row per key"'})
    assert len(audit_reproposal(rows)) == 1
