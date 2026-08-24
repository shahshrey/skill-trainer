#!/usr/bin/env python3
"""Parallel rollout dispatcher with heartbeat supervision (PROGRAM.md §6).

Usage:
  rollout_batch.py --skill PATH --suite DIR --tasks id1,id2 --out DIR \
      [--seeds 0] [--backend mock|claude|codex|cursor] [--mode cheap|full] \
      [--jobs 8] [--timeout 300] [--score] [--runner CMD]

One (task, seed) job per private workspace <out>/<task>_s<seed>/; workers
never share files. Workers run harness/run_task.py; --runner CMD substitutes
the worker command (invoked as: CMD <task> <seed> <workdir>), the testing
hook for the heartbeat path. run_task.py already enforces SIGTERM at
--timeout and SIGKILL at 2x, so the heartbeat guards the layer above it:
a worker PROCESS still alive past 2x timeout (+grace) is stale: its process
group is killed and the job is requeued ONCE; a second stall marks the job
crashed. Per-job result.json is persisted in the workspace; a batch summary
JSON prints to stdout. --score runs score.py --batch over --out afterward
and writes <out>/scores.json.

Exit 0 when every job completed (per-rollout exit codes are scoring's
concern, recorded in result.json), 1 when any job crashed at the dispatcher
level, 2 on scoring failure.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

from score import suite_config  # same-directory import; see judge.py

HARNESS = Path(__file__).resolve().parent


# Rate-limit / quota exhaustion produces tiny outputs that score 0 and
# silently poison a batch (m72hf lost days to this). Transient transport
# failures (connection lost, network errors) leave the same tiny-output
# signature when the backend's own retries give up. Detect both, retry with
# backoff, and refuse to score a batch that stays contaminated.
CONTAM_RE = re.compile(
    rb"limit|overload|quota|resets|too many requests|"
    rb"connection lost|network error|econnre|socket hang up", re.I)
CONTAM_MAX_BYTES = 300


# Some backends wrap the worker CLI in an intermediate shell. SIGKILLing a
# worker's process group (timeout, stale-kill, run termination) reparents
# that wrapper to PID 1, where it keeps consuming API tokens; copilot
# burned hours of quota this way (user report 2026-08-03). Marker table
# keyed by backend; add an entry when a new backend shows the pattern.
# Markers must match ONLY harness-launched workers: cursor's IDE runs its
# own long-lived `cursor-agent ... worker start` daemons at ppid 1, so the
# cursor marker is the headless flag triple no daemon invocation carries.
ORPHAN_MARKERS = {"copilot": "__copilot_pid_path",
                  "cursor": "-p --force --trust"}


def find_orphans(ps_text: str, marker: str) -> list[int]:
    """PIDs of orphaned worker wrappers (ppid 1 + marker in the command)
    plus their direct children, from `ps -axo pid=,ppid=,command=` output.
    Concurrent batches are safe: their live wrappers have a run_task
    ancestor, so ppid != 1."""
    procs: dict[int, tuple[int, str]] = {}
    for line in ps_text.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            procs[int(parts[0])] = (int(parts[1]), parts[2])
    tops = [p for p, (pp, cmd) in procs.items() if pp == 1 and marker in cmd]
    return tops + [p for p, (pp, _) in procs.items() if pp in tops]


def reap_orphans(backend: str) -> int:
    marker = ORPHAN_MARKERS.get(backend)
    if not marker:
        return 0
    ps = subprocess.run(["ps", "-axo", "pid=,ppid=,command="],
                        capture_output=True, text=True).stdout
    victims = find_orphans(ps, marker)
    for pid in victims:
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    return len(victims)


def contaminated(workdir: Path) -> bool:
    out = workdir / "output.txt"
    if not out.exists() or out.stat().st_size >= CONTAM_MAX_BYTES:
        return False
    return bool(CONTAM_RE.search(out.read_bytes()))


def limit_backoffs() -> list[float]:
    raw = os.environ.get("SKILL_TRAINER_LIMIT_BACKOFF", "300,900,2700")
    return [float(x) for x in raw.split(",") if x.strip()]


class Job:
    def __init__(self, task: str, seed: int, workdir: Path):
        self.task, self.seed, self.workdir = task, seed, workdir
        self.attempts = 0
        self.contam_attempts = 0
        self.not_before = 0.0
        self.proc: subprocess.Popen | None = None
        self.log = None
        self.started = 0.0
        self.exit_code: int | None = None

    @property
    def name(self) -> str:
        return f"{self.task}_s{self.seed}"


def build_cmd(args: argparse.Namespace, job: Job) -> list[str]:
    if args.runner:
        return [*args.runner.split(), job.task, str(job.seed), str(job.workdir)]
    cmd = [sys.executable, str(HARNESS / "run_task.py"),
           "--skill", args.skill, "--suite", args.suite, "--task", job.task,
           "--backend", args.backend, "--mode", args.mode,
           "--seed", str(job.seed), "--timeout", str(args.timeout),
           "--workdir", str(job.workdir)]
    if getattr(args, "stage_root", None):
        stage = Path(args.stage_root) / job.task
        if stage.is_dir():  # tasks without a staging dir author from scratch
            cmd += ["--stage", str(stage)]
    return cmd


def launch(args: argparse.Namespace, job: Job) -> bool:
    job.attempts += 1
    if job.attempts > 1 and job.workdir.exists():
        shutil.rmtree(job.workdir)  # stale partial artifacts must not score
    job.workdir.mkdir(parents=True, exist_ok=True)
    job.log = (job.workdir / "runner.out").open("w", encoding="utf-8")
    try:
        job.proc = subprocess.Popen(
            build_cmd(args, job), stdout=job.log, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, start_new_session=True)
    except OSError as exc:
        job.log.write(f"spawn failed: {exc}\n")
        job.log.close()
        return False
    job.started = time.monotonic()
    return True


def kill_group(job: Job) -> None:
    try:
        os.killpg(job.proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    job.proc.wait()
    job.log.close()


def finish(job: Job, status: str) -> None:
    if job.log and not job.log.closed:
        job.log.close()
    result = {"task": job.task, "seed": job.seed, "status": status,
              "attempts": job.attempts, "exit_code": job.exit_code}
    runner_out = job.workdir / "runner.out"
    if runner_out.exists():  # keep the worker's own report when it is JSON
        for line in reversed(runner_out.read_text(encoding="utf-8").splitlines()):
            if line.startswith("{"):
                try:
                    result["report"] = json.loads(line)
                except json.JSONDecodeError:
                    pass
                break
    job.workdir.mkdir(parents=True, exist_ok=True)
    (job.workdir / "result.json").write_text(json.dumps(result, indent=2),
                                             encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--skill")
    ap.add_argument("--suite")
    ap.add_argument("--tasks", required=True, help="comma-separated task ids")
    ap.add_argument("--seeds", default="0", help="comma-separated seeds")
    ap.add_argument("--backend", default="mock")
    ap.add_argument("--mode", choices=["cheap", "full"], default="cheap")
    ap.add_argument("--out", required=True)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--score", action="store_true",
                    help="run score.py --batch over --out afterward")
    ap.add_argument("--runner", help="substitute worker command (testing hook); "
                                     "invoked as: CMD <task> <seed> <workdir>")
    ap.add_argument("--stage-root", help="edit-from-feedback mode: for each "
                    "task with a <stage-root>/<task>/ directory, pass it to "
                    "run_task --stage (workspace pre-seeded with a prior "
                    "attempt + feedback; see the suite's prepare_edit.py)")
    ap.add_argument("--skip-existing", action="store_true",
                    help="skip task+seed combos whose workdir already holds a "
                         "clean completed rollout (resume a partial batch)")
    args = ap.parse_args()
    if not args.runner and not (args.skill and args.suite):
        ap.error("--skill and --suite are required (unless --runner)")

    out = Path(args.out)
    all_jobs = [Job(t, int(s), out / f"{t}_s{int(s)}")
                for t in args.tasks.split(",") for s in args.seeds.split(",")]
    skipped: list[Job] = []
    if args.skip_existing:
        def is_clean(j: Job) -> bool:
            res = j.workdir / "result.json"
            if not res.exists() or not (j.workdir / "output.txt").exists():
                return False
            try:
                status = json.loads(res.read_text()).get("status")
            except json.JSONDecodeError:
                return False
            return status == "done" and not contaminated(j.workdir)
        skipped = [j for j in all_jobs if is_clean(j)]
        all_jobs = [j for j in all_jobs if j not in skipped]
    queue = deque(all_jobs)
    total = len(queue) + len(skipped)
    backoffs = limit_backoffs()
    contam_final: list[Job] = []
    stale_after = 2 * args.timeout + max(2.0, 0.1 * args.timeout)
    poll = max(0.2, min(0.5, args.timeout / 10))
    running: list[Job] = []
    completed: list[Job] = []
    crashed: list[Job] = []

    while queue or running:
        while queue and len(running) < args.jobs:
            now = time.monotonic()
            job = next((j for j in queue if now >= j.not_before), None)
            if job is None:
                break  # every queued job is in limit backoff
            queue.remove(job)
            if launch(args, job):
                running.append(job)
            else:
                job.exit_code = None
                finish(job, "crashed")
                crashed.append(job)
        time.sleep(poll)
        for job in running[:]:
            rc = job.proc.poll()
            if rc is not None:
                running.remove(job)
                job.log.close()
                job.exit_code = rc
                if contaminated(job.workdir):
                    if job.contam_attempts < len(backoffs):
                        delay = backoffs[job.contam_attempts]
                        job.contam_attempts += 1
                        job.not_before = time.monotonic() + delay
                        job.attempts = 1  # relaunch wipes the poisoned workdir
                        print(f"limit-contaminated {job.name}; retry "
                              f"{job.contam_attempts}/{len(backoffs)} in "
                              f"{delay:.0f}s", file=sys.stderr, flush=True)
                        queue.append(job)
                    else:
                        finish(job, "contaminated")
                        contam_final.append(job)
                    continue
                finish(job, "done")
                completed.append(job)
            elif time.monotonic() - job.started > stale_after:
                running.remove(job)
                kill_group(job)
                if job.attempts < 2:  # heartbeat rule: requeue exactly once
                    print(f"stale worker {job.name} killed; requeueing",
                          file=sys.stderr, flush=True)
                    queue.append(job)
                else:
                    job.exit_code = None
                    finish(job, "crashed")
                    crashed.append(job)

    summary = {
        "jobs": total,
        "orphans_reaped": reap_orphans(args.backend),
        "completed": sorted(j.name for j in completed),
        "requeued": sorted(j.name for j in completed + crashed if j.attempts > 1),
        "crashed": sorted(j.name for j in crashed),
        "skipped": sorted(j.name for j in skipped),
        "contaminated": sorted(j.name for j in contam_final),
        "out": str(out),
    }
    if contam_final:
        # A poisoned batch must never produce scores.json; gating on it
        # corrupts the run. Exit 3 tells the driver: wait for the limit
        # window to clear, then re-dispatch with --skip-existing.
        print(json.dumps(summary, indent=2))
        sys.exit(3)
    if args.score and not crashed:
        cfg = suite_config(Path(args.suite))
        # Mock batches must never invoke a real judge CLI; otherwise the
        # suite's judge_backend wins, falling back to the rollout backend.
        judge_backend = ("mock" if args.backend == "mock"
                         else (cfg.get("judge_backend") or args.backend))
        jr = subprocess.run(
            [sys.executable, str(HARNESS / "judge.py"), "--suite", args.suite,
             "--batch", str(out), "--backend", judge_backend,
             "--jobs", str(args.jobs)],
            capture_output=True, text=True)
        if jr.returncode != 0:
            print(json.dumps(summary | {"judge_error": (jr.stderr or jr.stdout)[-500:]},
                             indent=2))
            sys.exit(2)
        r = subprocess.run(
            [sys.executable, str(HARNESS / "score.py"), "--suite", args.suite,
             "--batch", str(out), "--mode", args.mode,
             "--jobs", str(args.jobs)],
            capture_output=True, text=True)
        if r.returncode != 0:
            print(json.dumps(summary | {"score_error": r.stderr[-500:]}, indent=2))
            sys.exit(2)
        (out / "scores.json").write_text(r.stdout, encoding="utf-8")
        summary["aggregate"] = json.loads(r.stdout)["aggregate"]
    print(json.dumps(summary, indent=2))
    sys.exit(1 if crashed else 0)


if __name__ == "__main__":
    main()
