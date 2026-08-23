"""Phase 3 dispatcher: N parallel rollouts, receipts persisted, heartbeat
kills a stale worker and requeues it exactly once (PROGRAM.md §6)."""
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent / "harness"
BATCH = str(HARNESS / "rollout_batch.py")


def make_suite(tmp_path, n=4):
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "scoring.md").write_text(
        '```json\n{"default_mode": "exact", "mixed_weight": 0.5}\n```\n')
    items = [{"id": f"t{i:02d}", "suite": "primary", "requires": ["say-hello"],
              "scoring": {"mode": "exact", "expected": "RESULT: solved"}}
             for i in range(n)]
    (suite / "train.jsonl").write_text("\n".join(json.dumps(i) for i in items))
    skill = tmp_path / "SKILL.md"
    skill.write_text("# Skill\nAlways say hello first.\n")
    return suite, skill


def make_runner(tmp_path, script_body):
    runner = tmp_path / "runner.sh"
    runner.write_text("#!/bin/sh\n" + script_body)
    runner.chmod(runner.stat().st_mode | stat.S_IEXEC)
    return runner


def run_batch(*extra, check=False):
    r = subprocess.run([sys.executable, BATCH, *extra],
                       capture_output=True, text=True, timeout=120)
    if check:
        assert r.returncode == 0, r.stdout + r.stderr
    return r


def test_parallel_batch_completes_with_receipts_and_scores(tmp_path):
    suite, skill = make_suite(tmp_path, n=4)
    out = tmp_path / "out"
    r = run_batch("--skill", str(skill), "--suite", str(suite),
                  "--tasks", "t00,t01,t02,t03", "--out", str(out),
                  "--jobs", "4", "--score", check=True)
    summary = json.loads(r.stdout)
    assert summary["jobs"] == 4 and len(summary["completed"]) == 4
    assert summary["crashed"] == [] and summary["requeued"] == []
    for name in summary["completed"]:
        ws = out / name
        assert (ws / "output.txt").exists() and (ws / "task.json").exists()
        result = json.loads((ws / "result.json").read_text())
        assert result["status"] == "done" and result["attempts"] == 1
        assert result["report"]["task"] == name.rsplit("_s", 1)[0]
    assert (out / "scores.json").exists()
    assert summary["aggregate"]["overall"]["hard"] == 1.0


def test_workers_actually_run_in_parallel(tmp_path):
    runner = make_runner(tmp_path, 'mkdir -p "$3"\nsleep 0.6\n'
                                   'echo done > "$3/output.txt"\necho "{}"\n')
    start = time.monotonic()
    r = run_batch("--runner", str(runner), "--tasks", "a,b,c,d",
                  "--out", str(tmp_path / "out"), "--jobs", "4",
                  "--timeout", "30", check=True)
    wall = time.monotonic() - start
    assert len(json.loads(r.stdout)["completed"]) == 4
    assert wall < 2.0, f"4 x 0.6s jobs took {wall:.1f}s, not parallel"


def test_hung_worker_killed_and_requeued_once(tmp_path):
    # First attempt hangs (a flag file marks it); the requeued attempt succeeds.
    flags = tmp_path / "flags"
    flags.mkdir()
    runner = make_runner(tmp_path, f'''mkdir -p "$3"
flag="{flags}/$1.flag"
if [ ! -f "$flag" ]; then touch "$flag"; sleep 60; fi
echo done > "$3/output.txt"
echo '{{"recovered": true}}'
''')
    r = run_batch("--runner", str(runner), "--tasks", "hang1",
                  "--out", str(tmp_path / "out"), "--timeout", "1", check=True)
    summary = json.loads(r.stdout)
    assert summary["completed"] == ["hang1_s0"]
    assert summary["requeued"] == ["hang1_s0"]
    assert "stale worker hang1_s0 killed" in r.stderr
    result = json.loads((tmp_path / "out" / "hang1_s0" / "result.json").read_text())
    assert result["attempts"] == 2 and result["status"] == "done"
    assert result["report"] == {"recovered": True}


def test_worker_hung_twice_is_crashed_not_completed(tmp_path):
    runner = make_runner(tmp_path, 'mkdir -p "$3"\nsleep 60\n')
    r = run_batch("--runner", str(runner), "--tasks", "dead1",
                  "--out", str(tmp_path / "out"), "--timeout", "1")
    assert r.returncode == 1
    summary = json.loads(r.stdout)
    assert summary["crashed"] == ["dead1_s0"] and summary["completed"] == []
    result = json.loads((tmp_path / "out" / "dead1_s0" / "result.json").read_text())
    assert result["status"] == "crashed" and result["attempts"] == 2


def test_stale_kill_reaps_the_whole_process_group(tmp_path):
    # The hung sleep is a CHILD of the runner shell; killing only the shell
    # would leak it. Record the child pid, then assert it is gone afterward.
    pidfile = tmp_path / "sleep.pid"
    runner = make_runner(tmp_path, f'mkdir -p "$3"\nsleep 60 &\n'
                                   f'echo $! > "{pidfile}"\nwait\n')
    run_batch("--runner", str(runner), "--tasks", "grp1",
              "--out", str(tmp_path / "out"), "--timeout", "1")
    pid = int(pidfile.read_text().strip())
    time.sleep(0.3)
    try:
        os.kill(pid, 0)
        alive = True
    except ProcessLookupError:
        alive = False
    assert not alive, f"orphaned sleep child pid={pid} survived the group kill"


def test_stage_root_threads_through_to_run_task(tmp_path):
    """--stage-root adds --stage only for tasks that have a staging dir."""
    import argparse
    sys.path.insert(0, str(HARNESS))
    from rollout_batch import Job, build_cmd
    (tmp_path / "stages" / "t00").mkdir(parents=True)
    args = argparse.Namespace(runner=None, skill="s", suite="su",
                              backend="mock", mode="cheap", timeout=5,
                              stage_root=str(tmp_path / "stages"))
    staged = build_cmd(args, Job("t00", 0, tmp_path / "w0"))
    bare = build_cmd(args, Job("t01", 0, tmp_path / "w1"))
    assert staged[-2:] == ["--stage", str(tmp_path / "stages" / "t00")]
    assert "--stage" not in bare
