"""Rate-limit contamination handling + --skip-existing (rollout_batch.py).

A limit-window rollout produces a tiny output mentioning the limit; the
driver must retry it with backoff, refuse to score a batch that stays
contaminated (exit 3, no scores.json), and support resuming a partial
batch without re-running clean workspaces.
"""
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent / "harness"
BATCH = str(HARNESS / "rollout_batch.py")

LIMIT_TEXT = "You've hit your session limit · resets 4:50am"


def make_runner(tmp_path, body):
    runner = tmp_path / "runner.sh"
    runner.write_text("#!/bin/sh\n" + body)
    runner.chmod(runner.stat().st_mode | stat.S_IEXEC)
    return runner


def run_batch(tmp_path, runner, *extra, backoff="0.1,0.1"):
    env = dict(os.environ, SKILL_TRAINER_LIMIT_BACKOFF=backoff)
    return subprocess.run(
        [sys.executable, BATCH, "--runner", str(runner),
         "--tasks", "t00,t01", "--seeds", "0",
         "--out", str(tmp_path / "out"), "--jobs", "2", "--timeout", "20",
         *extra],
        capture_output=True, text=True, timeout=120, env=env)


def test_persistent_contamination_blocks_scoring(tmp_path):
    runner = make_runner(
        tmp_path, f'echo "{LIMIT_TEXT}" > "$3/output.txt"\nexit 0\n')
    r = run_batch(tmp_path, runner)
    assert r.returncode == 3, r.stdout + r.stderr
    summary = json.loads(r.stdout)
    assert sorted(summary["contaminated"]) == ["t00_s0", "t01_s0"]
    assert not (tmp_path / "out" / "scores.json").exists()
    res = json.loads((tmp_path / "out" / "t00_s0" / "result.json").read_text())
    assert res["status"] == "contaminated"
    assert "retry" in r.stderr  # backoff retries actually happened


def test_transient_contamination_recovers(tmp_path):
    # first attempt per job hits the "limit"; retries succeed
    marker = tmp_path / "seen"
    marker.mkdir()
    runner = make_runner(tmp_path, f"""
if [ -f "{marker}/$1" ]; then
  echo "real answer output that is long enough to not look contaminated \
padding padding padding padding padding padding padding padding padding \
padding padding padding padding padding padding padding" > "$3/output.txt"
else
  touch "{marker}/$1"
  echo "{LIMIT_TEXT}" > "$3/output.txt"
fi
exit 0
""")
    r = run_batch(tmp_path, runner)
    assert r.returncode == 0, r.stdout + r.stderr
    summary = json.loads(r.stdout)
    assert summary["contaminated"] == []
    assert sorted(summary["completed"]) == ["t00_s0", "t01_s0"]
    out = (tmp_path / "out" / "t00_s0" / "output.txt").read_text()
    assert "real answer" in out  # poisoned workdir was wiped and re-run


def test_skip_existing_resumes_partial_batch(tmp_path):
    # pre-create one clean completed workspace
    done = tmp_path / "out" / "t00_s0"
    done.mkdir(parents=True)
    (done / "output.txt").write_text("clean prior output " * 20)
    (done / "result.json").write_text(json.dumps(
        {"task": "t00", "seed": 0, "status": "done", "attempts": 1,
         "exit_code": 0}))
    log = tmp_path / "invoked.log"
    runner = make_runner(
        tmp_path, f'echo "$1" >> "{log}"\n'
                  'echo "fresh rollout output with plenty of ordinary padding words '
                  'repeated enough times to be clearly a real answer: '
                  'alpha beta gamma delta epsilon zeta eta theta iota kappa '
                  'lambda mu nu xi omicron pi rho sigma tau upsilon phi chi '
                  'psi omega alpha beta gamma delta epsilon zeta eta theta '
                  'iota kappa lambda mu nu xi omicron pi rho sigma tau" '
                  '> "$3/output.txt"\n'
                  'exit 0\n')
    r = run_batch(tmp_path, runner, "--skip-existing")
    assert r.returncode == 0, r.stdout + r.stderr
    summary = json.loads(r.stdout)
    assert summary["skipped"] == ["t00_s0"]
    assert summary["completed"] == ["t01_s0"]
    assert summary["jobs"] == 2
    invoked = log.read_text().split()
    assert invoked == ["t01"]  # the clean workspace was never re-run
    assert "clean prior output" in (done / "output.txt").read_text()


def test_skip_existing_reruns_contaminated_workspace(tmp_path):
    poisoned = tmp_path / "out" / "t00_s0"
    poisoned.mkdir(parents=True)
    (poisoned / "output.txt").write_text(LIMIT_TEXT)
    (poisoned / "result.json").write_text(json.dumps(
        {"task": "t00", "seed": 0, "status": "done", "attempts": 1,
         "exit_code": 0}))
    runner = make_runner(
        tmp_path, 'echo "fresh rollout output with plenty of ordinary padding words '
                  'repeated enough times to be clearly a real answer: '
                  'alpha beta gamma delta epsilon zeta eta theta iota kappa '
                  'lambda mu nu xi omicron pi rho sigma tau upsilon phi chi '
                  'psi omega alpha beta gamma delta epsilon zeta eta theta '
                  'iota kappa lambda mu nu xi omicron pi rho sigma tau" '
                  '> "$3/output.txt"\n'
                  'exit 0\n')
    r = run_batch(tmp_path, runner, "--skip-existing")
    assert r.returncode == 0, r.stdout + r.stderr
    summary = json.loads(r.stdout)
    assert summary["skipped"] == []  # poisoned workspace does NOT count as clean
    assert "t00_s0" in summary["completed"]
    assert "fresh rollout output" in (poisoned / "output.txt").read_text()
