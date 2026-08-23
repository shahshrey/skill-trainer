#!/usr/bin/env python3
"""Trainer meta-evaluation driver. Not pytest-collected.

  planted  ablate rules from the mock-demo reference skill, then run the
           training loop (real editor/LR LLM calls via `claude -p`, mock
           rollouts through the real harness CLI) and measure recovery.
  null     run the same loop on the pure-noise suite; a correct trainer
           accepts ~0 edits and ends in no-progress.

Runs in a disposable git worktree so the main checkout is never mutated;
artifacts are copied back to runs/meta/<name>/ afterwards.

  .venv/bin/python tests/meta_eval.py planted --ablate seamless-loop --max-steps 8
  .venv/bin/python tests/meta_eval.py planted --ablate seamless-loop state-a-default sync-same-stage-motion
  .venv/bin/python tests/meta_eval.py null --max-steps 5

Exit 0 iff the run meets its acceptance criterion.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = (str(REPO / ".venv" / "bin" / "python")
      if (REPO / ".venv").exists() else sys.executable)

ABLATABLE = {
    "cite-your-sources": "- Cite your sources for every factual claim.\n",
    "state-a-default": "- When options exist, state a default and move on.\n",
    "verify-before-delivery": "- Verify before delivery: open the artifact and look at it.\n",
    "one-term-per-concept": "- Use one term per concept throughout a document.\n",
    "examples-over-prose": "- Prefer examples over prose when explaining behavior.\n",
    "seamless-loop": "- A seamless loop is mandatory: the first and last frames must match.\n",
    "match-canvas-dimensions": "- Match canvas dimensions to the spec exactly before rendering.\n",
    "sync-same-stage-motion": "- Sync same-stage motion: parallel elements depart and arrive together.\n",
}


def sh(cmd: list[str], cwd: Path, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def parse_json_block(text: str) -> dict | None:
    """First complete valid JSON object anywhere in the text (lenient)."""
    dec = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                obj, _ = dec.raw_decode(text[i:])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue
    return None


def llm(prompt: str, timeout: int = 240) -> dict:
    last = ""
    for _ in range(2):  # malformed output gets exactly one retry (PROGRAM.md §5)
        proc = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True,
                              timeout=timeout, stdin=subprocess.DEVNULL)
        obj = parse_json_block(proc.stdout) if proc.returncode == 0 else None
        if obj is not None:
            return obj
        last = (proc.stdout or proc.stderr)[:500]
    raise RuntimeError(f"no valid JSON from LLM after retry: {last}")


class Run:
    def __init__(self, wt: Path, suite: str, k_seeds: int):
        self.wt = wt
        self.suite = suite
        self.k = k_seeds
        self.seed_counter = 0
        self.tsv: list[str] = []
        self.skill = wt / "skills" / "mock-demo" / "SKILL.md"
        self.val_ids = [json.loads(l)["id"] for l in
                        (wt / "tasks" / suite / "val.jsonl").read_text().splitlines()]
        self.train_ids = [json.loads(l)["id"] for l in
                          (wt / "tasks" / suite / "train.jsonl").read_text().splitlines()]

    def sha(self) -> str:
        return sh(["git", "rev-parse", "--short=7", "HEAD"], self.wt).stdout.strip()

    def rollout_batch(self, ids: list[str], batch_dir: Path, fresh_seeds: bool,
                      skill: Path | None = None) -> dict:
        for tid in ids:
            for j in range(self.k):
                seed = self.seed_counter + j if fresh_seeds else j
                r = sh([PY, str(REPO / "harness" / "run_task.py"),
                        "--skill", str(skill or self.skill),
                        "--suite", str(self.wt / "tasks" / self.suite),
                        "--task", tid, "--backend", "mock", "--seed", str(seed),
                        "--workdir", str(batch_dir / f"{tid}_s{seed}")], self.wt)
                assert r.returncode == 0, r.stderr
        if fresh_seeds:
            self.seed_counter += self.k
        r = sh([PY, str(REPO / "harness" / "score.py"), "--suite",
                str(self.wt / "tasks" / self.suite), "--batch", str(batch_dir)], self.wt)
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)

    def receipts(self, batch_dir: Path, scores: dict,
                 split: str = "fail") -> tuple[str, int, int]:
        picked = []
        n_fail = 0
        for name, res in sorted(scores["tasks"].items()):
            # scores keys are workspace names (task_s<seed>) since 2cdae71
            ws = batch_dir / name if (batch_dir / name).is_dir() else next(
                batch_dir.glob(f"{name}_s*"))
            out = (ws / "output.txt").read_text().strip()
            if not res["hard"]:
                n_fail += 1
            if bool(res["hard"]) == (split == "ok"):
                verdict = "solved" if res["hard"] else "unsolved"
                picked.append(f"Status: Done\nTask: {name}\nSummary: mock rollout, {verdict}\n"
                              f"Verification: hard={res['hard']} soft={res['soft']}\nEvidence:\n{out}\n")
        return "\n---\n".join(picked), n_fail, len(scores["tasks"])


def fill(template: str, **kw: str) -> str:
    for key, val in kw.items():
        template = template.replace("{" + key + "}", val)
    return template


def class_guide(suite_dir: Path) -> str:
    """Suite-owned class -> mechanism guide for {FAILURE_CLASS_GUIDE}
    (PROGRAM §4b); generic fallback when the suite ships none."""
    guide = suite_dir / "failure_classes.md"
    if guide.exists():
        return guide.read_text()
    return ("No class guide for this suite. Infer the mechanism from the "
            "check names and diagnostic excerpts in the receipts.")


def run_loop(run: Run, *, max_steps: int, target: float, min_delta: float,
             current: float, log: list[dict]) -> str:
    """Returns terminal state. Mutates log with per-step records."""
    best = current
    streak = 0
    noops = 0
    rejected_buffer: list[str] = []
    prompts_dir = run.wt / "prompts"

    for step in range(1, max_steps + 1):
        pre_sha = run.sha()
        step_dir = run.wt / "runs" / "meta" / f"step_{step}"
        train_scores = run.rollout_batch(run.train_ids, step_dir / "train", fresh_seeds=True)
        fail_receipts, n_fail, n_total = run.receipts(step_dir / "train", train_scores)
        if not fail_receipts:
            fail_receipts = "(no failed rollouts this batch)"

        editor_prompt = fill((prompts_dir / "editor_error.md").read_text(),
                             EDIT_BUDGET="5", SKILL_CONTENT=run.skill.read_text(),
                             META_CONTENT="(no observations yet)",
                             REJECTED_EDITS="\n".join(rejected_buffer) or "(none yet)",
                             FAILURE_CLASS_GUIDE=class_guide(run.wt / "tasks" / run.suite),
                             RECEIPTS=fail_receipts)
        edits = llm(editor_prompt).get("edits", [])

        applied = 0
        outcome = "reject"
        cand_mixed = current
        if edits:
            lr_prompt = fill((prompts_dir / "learning_rate.md").read_text(),
                             SKILL_CONTENT=run.skill.read_text(),
                             RANKED_ITEMS=json.dumps(edits, indent=2),
                             STEP_EVIDENCE=(f"Step {step}. Current val mixed {current:.4f}, best "
                                            f"{best:.4f}, min_delta {min_delta:.4f}. Train batch: "
                                            f"{n_fail}/{n_total} failed. Discard streak {streak}."))
            lr = max(0, min(int(llm(lr_prompt).get("learning_rate", 0)), len(edits)))
            if lr == 0 and noops >= 2:
                lr = 1  # exploration floor: a stalled optimizer learns nothing
            if lr > 0:
                use = {"edits": edits[:lr]}
                edits_path = step_dir / "edits.json"
                step_dir.mkdir(parents=True, exist_ok=True)
                edits_path.write_text(json.dumps(use, indent=2))
                prev_skill = step_dir / "pre_edit.md"
                prev_skill.write_text(run.skill.read_text())
                ap = sh([PY, str(REPO / "harness" / "apply_edits.py"),
                         "--skill", str(run.skill), "--edits", str(edits_path)], run.wt)
                if ap.returncode != 0:
                    # one retry with the error appended
                    retry_prompt = editor_prompt + ("\n\n## Correction: apply failed\n"
                                                    f"{ap.stderr.strip()}\nQuote targets verbatim "
                                                    "from the current skill above, or use append. "
                                                    "Respond again with the same JSON contract.")
                    edits = llm(retry_prompt).get("edits", [])
                    if edits:
                        edits_path.write_text(json.dumps({"edits": edits[:lr]}, indent=2))
                        ap = sh([PY, str(REPO / "harness" / "apply_edits.py"),
                                 "--skill", str(run.skill), "--edits", str(edits_path)], run.wt)
                if ap.returncode == 0:
                    lint = sh([PY, str(REPO / "harness" / "lint_skill.py"), "--skill",
                               str(run.skill), "--deploy-mode", "prompt",
                               "--prev-skill", str(prev_skill)], run.wt)
                    if lint.returncode == 2:
                        sh(["git", "checkout", "--", str(run.skill)], run.wt)
                        outcome = "lint_reject"
                    else:
                        applied = len(json.loads(edits_path.read_text())["edits"])
                        sh(["git", "commit", "-qam", f"step {step}"], run.wt)
                        val = run.rollout_batch(run.val_ids, step_dir / "val", fresh_seeds=True)
                        cand_mixed = val["aggregate"]["overall"]["mixed"]
                        gate = json.loads(sh(
                            [PY, str(REPO / "harness" / "gate.py"), "--candidate", str(cand_mixed),
                             "--current", str(current), "--best", str(best),
                             "--min-delta", str(min_delta)], run.wt).stdout)
                        outcome = gate["action"]
                        if outcome == "reject":
                            sh(["git", "reset", "--hard", "-q", pre_sha], run.wt)
                        else:
                            current, best = gate["new_current"], gate["new_best"]
                else:
                    sh(["git", "checkout", "--", str(run.skill)], run.wt)
                    outcome = "apply_crash"
            else:
                outcome = "noop"
        else:
            outcome = "noop"

        if outcome in ("reject", "lint_reject") and applied:
            summary = " | ".join(
                f'{e["op"]}@"{e.get("target", "")[:40]}": "{e.get("content", "")[:80]}"'
                for e in json.loads((step_dir / "edits.json").read_text())["edits"])
            rejected_buffer.append(
                f"Step {step} ({current:.4f} -> {cand_mixed:.4f}, {outcome}): {summary}")
        streak = 0 if outcome.startswith("accept") else streak + 1
        noops = noops + 1 if outcome == "noop" else 0
        log.append({"step": step, "outcome": outcome, "applied": applied,
                    "val_mixed": cand_mixed, "current": current, "streak": streak})
        print(f"  step {step}: {outcome} applied={applied} val={cand_mixed:.4f} "
              f"current={current:.4f} streak={streak}", flush=True)

        if current >= target - 1e-9:
            return "success"
        if streak >= 6:
            return "no-progress"
    return "exhausted"


def make_worktree(name: str) -> Path:
    wt = REPO / "runs" / "meta_wt" / name
    sh(["git", "worktree", "remove", "--force", str(wt)], REPO)
    sh(["git", "branch", "-qD", f"meta/{name}"], REPO)
    r = sh(["git", "worktree", "add", "-b", f"meta/{name}", str(wt), "HEAD"], REPO)
    assert r.returncode == 0, r.stderr
    # Seed the bundled example suite: tasks/ and skills/ are gitignored
    # (PROGRAM.md §8), so a HEAD checkout has neither. Force-add so the
    # loop's `git commit -qam` / `git reset --hard` see them as tracked.
    example = REPO / "examples" / "mock-demo"
    if not (wt / "tasks" / "mock-demo").exists():
        shutil.copytree(example / "tasks", wt / "tasks", dirs_exist_ok=True)
        shutil.copytree(example / "skills", wt / "skills", dirs_exist_ok=True)
        sh(["git", "add", "-f", "tasks", "skills"], wt)
        sh(["git", "commit", "-qm", "seed example suite from examples/mock-demo"], wt)
    return wt


def teardown(wt: Path, name: str, keep: Path) -> None:
    keep.mkdir(parents=True, exist_ok=True)
    for item in ("results.tsv", "runs/meta"):
        src = wt / item
        if src.exists():
            dest = keep / Path(item).name
            shutil.rmtree(dest, ignore_errors=True) if src.is_dir() else dest.unlink(missing_ok=True)
            shutil.move(str(src), str(dest))
    sh(["git", "worktree", "remove", "--force", str(wt)], REPO)
    sh(["git", "branch", "-qD", f"meta/{name}"], REPO)


def cmd_planted(args) -> int:
    name = f"planted-d{len(args.ablate)}-{int(time.time())}"
    wt = make_worktree(name)
    try:
        run = Run(wt, "mock-demo", k_seeds=1)
        skill_text = run.skill.read_text()
        for rule in args.ablate:
            line = ABLATABLE[rule]
            assert line in skill_text, f"rule line for {rule} not found"
            skill_text = skill_text.replace(line, "")
        run.skill.write_text(skill_text)
        sh(["git", "commit", "-qam", f"ablate {','.join(args.ablate)}"], run.wt)

        baselines = [run.rollout_batch(run.val_ids, wt / "runs" / "meta" / f"baseline_{i}",
                                       fresh_seeds=False)["aggregate"]["overall"]["mixed"]
                     for i in range(3)]
        min_delta = max(0.01, max(baselines) - min(baselines))
        baseline = sum(baselines) / 3
        print(f"[{name}] baseline={baseline:.4f} min_delta={min_delta:.4f} target=1.0")

        log: list[dict] = []
        terminal = run_loop(run, max_steps=args.max_steps, target=1.0,
                            min_delta=min_delta, current=baseline, log=log)
        final = log[-1]["current"] if log else baseline
        recovery = (final - baseline) / (1.0 - baseline) if baseline < 1.0 else 1.0
        report = {"run": name, "ablated": args.ablate, "baseline": round(baseline, 4),
                  "final": round(final, 4), "recovery_rate": round(recovery, 4),
                  "steps": len(log), "accepts": sum(1 for s in log if s["outcome"].startswith("accept")),
                  "terminal": terminal, "pass": recovery >= 2 / 3}
        print(json.dumps(report, indent=2))
        (REPO / "runs" / "meta" / name).mkdir(parents=True, exist_ok=True)
        (REPO / "runs" / "meta" / name / "report.json").write_text(json.dumps(report, indent=2))
        return 0 if report["pass"] else 1
    finally:
        teardown(wt, name, REPO / "runs" / "meta" / name)


def cmd_null(args) -> int:
    name = f"null-{int(time.time())}"
    wt = make_worktree(name)
    try:
        run = Run(wt, "mock-null", k_seeds=2)
        baselines = []
        for i in range(3):
            baselines.append(run.rollout_batch(run.val_ids, wt / "runs" / "meta" / f"baseline_{i}",
                                               fresh_seeds=True)["aggregate"]["overall"]["mixed"])
        min_delta = max(0.01, max(baselines) - min(baselines))
        baseline = sum(baselines) / 3
        print(f"[{name}] baselines={baselines} min_delta={min_delta:.4f}")

        log: list[dict] = []
        terminal = run_loop(run, max_steps=args.max_steps, target=2.0,  # unreachable
                            min_delta=min_delta, current=baseline, log=log)
        accepts = sum(1 for s in log if s["outcome"].startswith("accept"))
        report = {"run": name, "baseline": round(baseline, 4), "steps": len(log),
                  "accepts": accepts, "terminal": terminal,
                  "pass": accepts <= 1 and terminal in ("no-progress", "exhausted")}
        print(json.dumps(report, indent=2))
        (REPO / "runs" / "meta" / name).mkdir(parents=True, exist_ok=True)
        (REPO / "runs" / "meta" / name / "report.json").write_text(json.dumps(report, indent=2))
        return 0 if report["pass"] else 1
    finally:
        teardown(wt, name, REPO / "runs" / "meta" / name)


SLOW_RE = re.compile(
    r"(<!--\s*PROTECTED:SLOW_UPDATE:START\s*-->)([\s\S]*?)(<!--\s*PROTECTED:SLOW_UPDATE:END\s*-->)")


def replace_slow_update(skill_path: Path, content: str) -> str:
    """Returns the previous block content; writes the new one."""
    text = skill_path.read_text()
    m = SLOW_RE.search(text)
    assert m, "skill has no SLOW_UPDATE block"
    prev = m.group(2).strip()
    skill_path.write_text(text[:m.start()] + m.group(1) + "\n" + content.strip()
                          + "\n" + m.group(3) + text[m.end():])
    return prev


def compact_edits(edits: list[dict]) -> str:
    return " | ".join(f'{e["op"]}@"{e.get("target", "")[:40]}": "{e.get("content", "")[:80]}"'
                      for e in edits)


def buckets_text(prev_scores: dict, cur_scores: dict) -> str:
    buckets = {"regressions": [], "persistent failures": [],
               "improvements": [], "stable successes": []}
    for tid, cur in sorted(cur_scores["tasks"].items()):
        prev = prev_scores["tasks"].get(tid, {"hard": 0})
        key = {(1, 0): "regressions", (0, 0): "persistent failures",
               (0, 1): "improvements", (1, 1): "stable successes"}[
            (int(prev["hard"]), int(cur["hard"]))]
        buckets[key].append(f"{tid} (soft {prev.get('soft', 0)} -> {cur['soft']})")
    return "\n".join(f"### {name}\n" + ("\n".join(f"- {t}" for t in tasks) or "- (none)")
                     for name, tasks in buckets.items())


def cmd_epochs(args) -> int:
    """Full-machinery verification. The FULL machinery must recover a
    D-rule ablation: E-step epochs, ranker, LR, slow-update, meta-memory,
    results.tsv, best tag. Then audit_run.py audits over the run."""
    name = f"epochs-d{len(args.ablate)}-{int(time.time())}"
    wt = make_worktree(name)
    best_tag = f"best/mock-demo-{name}"
    suite_dir = wt / "tasks" / "mock-demo"
    run_dir = wt / "runs" / "meta"
    tsv = wt / "results.tsv"
    L = 5
    try:
        run = Run(wt, "mock-demo", k_seeds=1)
        meta_path = wt / "skills" / "mock-demo" / "META.md"
        meta_path.write_text("# Optimizer memory: mock-demo\n\n(no observations yet)\n")
        skill_text = run.skill.read_text()
        for rule in args.ablate:
            line = ABLATABLE[rule]
            assert line in skill_text, f"rule line for {rule} not found"
            skill_text = skill_text.replace(line, "")
        run.skill.write_text(skill_text)
        sh(["git", "add", "-A"], wt)
        sh(["git", "commit", "-qm", f"ablate {','.join(args.ablate)} + init META"], wt)

        baselines = [run.rollout_batch(run.val_ids, run_dir / f"baseline_{i}",
                                       fresh_seeds=True)["aggregate"]["overall"]["mixed"]
                     for i in range(3)]
        min_delta = max(0.01, max(baselines) - min(baselines))
        current = best = sum(baselines) / 3
        sh(["git", "tag", best_tag], wt)
        tsv.write_text(
            f"# run={name} skill=mock-demo backend=mock K=1 E={args.e_steps} L={L} mode=cheap-only\n"
            f"# min_delta_cheap={min_delta:.4f} primary=primary no-secondary\n"
            "commit\tepoch\tstep\tmode\tval_mixed\tval_hard\tval_soft\tsec_mixed"
            "\tn_val_rollouts\tstatus\tedits_applied\tdescription\n")

        def row(sha, epoch, step, agg, status, applied, desc):
            o = agg["overall"] if "overall" in agg else agg
            desc = desc.replace("\t", " ").replace("\n", " ")[:400]
            with tsv.open("a") as f:
                f.write(f"{sha}\t{epoch}\t{step}\tcheap\t{o['mixed']:.4f}\t{o['hard']:.4f}"
                        f"\t{o['soft']:.4f}\t\t{o.get('n', len(run.val_ids))}\t{status}"
                        f"\t{applied}\t{desc}\n")

        base_agg = {"mixed": current, "hard": 0.0, "soft": 0.0, "n": len(run.val_ids) * 3}
        row(run.sha(), 0, 0, base_agg, "keep_best", 0,
            f"baseline mean of 3; primaries={[round(b, 4) for b in baselines]}")
        print(f"[{name}] baseline={current:.4f} min_delta={min_delta:.4f} target=1.0",
              flush=True)

        prompts_dir = wt / "prompts"
        rejected_buffer: list[str] = []
        streak = noops = accepts = 0
        step = 0
        terminal = "exhausted"
        epochs_completed = 0
        epoch_step_log: list[str] = []
        prev_epoch_skill = run.skill.read_text()

        def persist_llm(step_dir: Path, stem: str, prompt: str) -> dict:
            step_dir.mkdir(parents=True, exist_ok=True)
            (step_dir / f"{stem}_prompt.md").write_text(prompt)
            out = llm(prompt)
            (step_dir / f"{stem}_response.json").write_text(json.dumps(out, indent=2))
            return out

        for epoch in range(1, args.epochs + 1):
            epoch_step_log = []
            for _ in range(args.e_steps):
                step += 1
                pre_sha = run.sha()
                step_dir = run_dir / f"step_{step}"
                train_scores = run.rollout_batch(run.train_ids, step_dir / "train",
                                                 fresh_seeds=True)
                fail_r, n_fail, n_total = run.receipts(step_dir / "train", train_scores)
                ok_r, _, _ = run.receipts(step_dir / "train", train_scores, split="ok")

                pool: list[dict] = []
                skill_now = run.skill.read_text()
                common = dict(EDIT_BUDGET=str(L), SKILL_CONTENT=skill_now,
                              META_CONTENT=meta_path.read_text(),
                              REJECTED_EDITS="\n".join(rejected_buffer[-6:]) or "(none yet)",
                              FAILURE_CLASS_GUIDE=class_guide(suite_dir))
                if fail_r:
                    out = persist_llm(step_dir, "editor_error",
                                      fill((prompts_dir / "editor_error.md").read_text(),
                                           RECEIPTS=fail_r, **common))
                    pool += out.get("edits", [])
                if ok_r:
                    out = persist_llm(step_dir, "editor_success",
                                      fill((prompts_dir / "editor_success.md").read_text(),
                                           RECEIPTS=ok_r, **common))
                    pool += out.get("edits", [])
                if len(pool) > L:
                    ranked = persist_llm(step_dir, "ranker",
                                         fill((prompts_dir / "ranker.md").read_text(),
                                              SELECT_BUDGET=str(L), SKILL_CONTENT=skill_now,
                                              EDIT_POOL=json.dumps(list(enumerate(pool)), indent=1)))
                    pool = [pool[i] for i in ranked.get("selected_indices", [])[:L]
                            if isinstance(i, int) and i < len(pool)]

                applied = 0
                outcome = "noop"
                cand_agg = None
                if pool:
                    lr_out = persist_llm(step_dir, "learning_rate",
                                         fill((prompts_dir / "learning_rate.md").read_text(),
                                              SKILL_CONTENT=skill_now,
                                              RANKED_ITEMS=json.dumps(pool, indent=1),
                                              STEP_EVIDENCE=(
                                                  f"Step {step} (epoch {epoch}). Current val mixed "
                                                  f"{current:.4f}, best {best:.4f}, min_delta "
                                                  f"{min_delta:.4f}. Train batch: {n_fail}/{n_total} "
                                                  f"failed. Discard streak {streak}.")))
                    lr = max(0, min(int(lr_out.get("learning_rate", 0)), len(pool)))
                    if lr == 0 and noops >= 2:
                        lr = 1  # exploration floor
                    if lr > 0:
                        use = pool[:lr]
                        edits_path = step_dir / "edits.json"
                        edits_path.write_text(json.dumps({"edits": use}, indent=1))
                        (step_dir / "pre_edit.md").write_text(skill_now)
                        ap = sh([PY, str(REPO / "harness" / "apply_edits.py"),
                                 "--skill", str(run.skill), "--edits", str(edits_path)], wt)
                        if ap.returncode != 0:
                            retry = persist_llm(
                                step_dir, "editor_error_retry",
                                fill((prompts_dir / "editor_error.md").read_text(),
                                     RECEIPTS=fail_r or ok_r, **common)
                                + f"\n\n## Correction: apply failed\n{ap.stderr.strip()}\n"
                                "Quote targets verbatim from the current skill above, or use "
                                "append. Respond again with the same JSON contract.")
                            use = retry.get("edits", [])[:max(lr, 1)]
                            if use:
                                edits_path.write_text(json.dumps({"edits": use}, indent=1))
                                ap = sh([PY, str(REPO / "harness" / "apply_edits.py"),
                                         "--skill", str(run.skill), "--edits", str(edits_path)], wt)
                        if ap.returncode != 0:
                            sh(["git", "checkout", "--", str(run.skill)], wt)
                            outcome = "crash"
                        else:
                            lint = sh([PY, str(REPO / "harness" / "lint_skill.py"),
                                       "--skill", str(run.skill), "--deploy-mode", "prompt",
                                       "--prev-skill", str(step_dir / "pre_edit.md")], wt)
                            if lint.returncode == 2:
                                sh(["git", "checkout", "--", str(run.skill)], wt)
                                outcome = "lint_reject"
                            else:
                                applied = len(use)
                                sh(["git", "commit", "-qam", f"step {step}"], wt)
                                val = run.rollout_batch(run.val_ids, step_dir / "val",
                                                        fresh_seeds=True)
                                cand_agg = val["aggregate"]["overall"]
                                gate = json.loads(sh(
                                    [PY, str(REPO / "harness" / "gate.py"),
                                     "--candidate", str(cand_agg["mixed"]),
                                     "--current", str(current), "--best", str(best),
                                     "--min-delta", str(min_delta)], wt).stdout)
                                outcome = gate["action"]
                                if outcome == "reject":
                                    sh(["git", "reset", "--hard", "-q", pre_sha], wt)
                                else:
                                    current = gate["new_current"]
                                    if outcome == "accept_new_best":
                                        best = gate["new_best"]
                                        sh(["git", "tag", "-f", best_tag], wt)

                sha = run.sha()
                edits_txt = compact_edits(use) if applied else ""
                fallback = {"mixed": current, "hard": 0.0, "soft": 0.0, "n": 0}
                if outcome.startswith("accept"):
                    accepts += 1
                    status = "keep_best" if outcome == "accept_new_best" else "keep"
                    row(sha, epoch, step, cand_agg, status, applied, edits_txt)
                elif outcome == "reject":
                    rejected_buffer.append(f"Step {step} (rejected by val gate): {edits_txt}")
                    row(sha, epoch, step, cand_agg, "discard", applied, edits_txt)
                elif outcome == "lint_reject":
                    rejected_buffer.append(f"Step {step} (lint-rejected): {edits_txt}")
                    row(sha, epoch, step, fallback, "discard", 0, "lint: candidate blocked")
                elif outcome == "crash":
                    row(sha, epoch, step, fallback, "crash", 0, "apply failed twice")
                else:
                    row(sha, epoch, step, fallback, "discard", 0,
                        f"noop: learning_rate=0 (pool={len(pool)})")
                streak = 0 if outcome.startswith("accept") else streak + 1
                noops = noops + 1 if outcome == "noop" else 0
                epoch_step_log.append(f"step {step}: {outcome} applied={applied} "
                                      f"val={cand_agg['mixed'] if cand_agg else current:.4f} "
                                      f"edits: {edits_txt or '(none)'}")
                print(f"  {epoch_step_log[-1].split(' edits:')[0]} current={current:.4f} "
                      f"streak={streak}", flush=True)
                if current >= 1.0 - 1e-9:
                    terminal = "success"
                    break
                if streak >= 6:
                    terminal = "no-progress"
                    break

            if terminal in ("success", "no-progress"):
                break

            # -- Epoch boundary (PROGRAM.md §4h) --------------------------------
            ep_dir = run_dir / f"epoch_{epoch}"
            # 1. authoritative pass on the epoch's final accepted skill
            boundary = run.rollout_batch(run.val_ids, ep_dir / "authoritative",
                                         fresh_seeds=True)["aggregate"]["overall"]
            if boundary["mixed"] > best + min_delta - 1e-12:
                best = boundary["mixed"]
                sh(["git", "tag", "-f", best_tag], wt)
                row(run.sha(), epoch, step, boundary, "keep_best", 0,
                    f"epoch {epoch} authoritative pass")
            else:
                row(run.sha(), epoch, step, boundary, "keep", 0,
                    f"epoch {epoch} authoritative pass")
            current = boundary["mixed"]
            # 2. longitudinal comparison + slow-update + meta-memory
            prev_skill_file = ep_dir / "prev_epoch_skill.md"
            prev_skill_file.parent.mkdir(parents=True, exist_ok=True)
            prev_skill_file.write_text(prev_epoch_skill)
            prev_scores = run.rollout_batch(run.train_ids, ep_dir / "train_prev",
                                            fresh_seeds=False, skill=prev_skill_file)
            cur_scores = run.rollout_batch(run.train_ids, ep_dir / "train_cur",
                                           fresh_seeds=False)
            comparison = buckets_text(prev_scores, cur_scores)
            skill_now = run.skill.read_text()
            prev_guidance = SLOW_RE.search(skill_now).group(2).strip() or "(empty)"
            slow = persist_llm(ep_dir, "slow_update",
                               fill((prompts_dir / "slow_update.md").read_text(),
                                    PREV_SKILL=prev_epoch_skill, SKILL_CONTENT=skill_now,
                                    PREV_GUIDANCE=prev_guidance, COMPARISON=comparison))
            mem = persist_llm(ep_dir, "meta_memory",
                              fill((prompts_dir / "meta_memory.md").read_text(),
                                   PREV_SKILL=prev_epoch_skill, SKILL_CONTENT=skill_now,
                                   META_CONTENT=meta_path.read_text(),
                                   STEP_LOG="\n".join(epoch_step_log),
                                   COMPARISON=comparison))
            pre_boundary_skill = skill_now
            replace_slow_update(run.skill, slow.get("slow_update_content", ""))
            meta_path.write_text(mem.get("meta_skill_content", meta_path.read_text()))
            sh(["git", "commit", "-qam", f"epoch {epoch} boundary"], wt)
            # 3. protected-block changes are not free: re-validate
            reval = run.rollout_batch(run.val_ids, ep_dir / "reval",
                                      fresh_seeds=True)["aggregate"]["overall"]
            if reval["mixed"] < boundary["mixed"] - min_delta:
                run.skill.write_text(pre_boundary_skill)  # keep META: tasks never see it
                sh(["git", "commit", "-qam", f"epoch {epoch} revert slow-update"], wt)
                row(run.sha(), epoch, step, reval, "discard", 0,
                    f"epoch: slow-update regressed {boundary['mixed']:.4f}->"
                    f"{reval['mixed']:.4f}, reverted")
            else:
                current = reval["mixed"]
                row(run.sha(), epoch, step, reval, "epoch", 0,
                    f"epoch {epoch} post-slow-update re-validation")
            epochs_completed = epoch
            prev_epoch_skill = run.skill.read_text()
            print(f"  epoch {epoch} boundary: authoritative={boundary['mixed']:.4f} "
                  f"reval={reval['mixed']:.4f} best={best:.4f}", flush=True)

        # -- audit_run.py audits over this run (worktree-local harness + git) --
        audit = sh([PY, str(wt / "harness" / "audit_run.py"),
                    "--run", str(run_dir), "--suite", str(suite_dir),
                    "--skill", str(run.skill), "--results", str(tsv),
                    "--best-tag", best_tag, "--authoritative-mode", "cheap"], wt)
        (run_dir / "audit.json").write_text(audit.stdout or audit.stderr)
        audit_ok = audit.returncode == 0

        baseline = sum(baselines) / 3
        recovery = (best - baseline) / (1.0 - baseline) if baseline < 1.0 else 1.0
        report = {"run": name, "ablated": args.ablate, "baseline": round(baseline, 4),
                  "final_best": round(best, 4), "recovery_rate": round(recovery, 4),
                  "steps": step, "accepts": accepts, "epochs_completed": epochs_completed,
                  "terminal": terminal, "audit": "pass" if audit_ok else "fail",
                  "pass": recovery >= 2 / 3 and audit_ok}
        print(json.dumps(report, indent=2))
        keep = REPO / "runs" / "meta" / name
        keep.mkdir(parents=True, exist_ok=True)
        (keep / "report.json").write_text(json.dumps(report, indent=2))
        return 0 if report["pass"] else 1
    finally:
        sh(["git", "tag", "-d", best_tag], REPO)
        teardown(wt, name, REPO / "runs" / "meta" / name)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("planted")
    p.add_argument("--ablate", nargs="+", required=True, choices=sorted(ABLATABLE))
    p.add_argument("--max-steps", type=int, default=8)
    n = sub.add_parser("null")
    n.add_argument("--max-steps", type=int, default=5)
    e = sub.add_parser("epochs", help="Phase 4: planted-defect run with full machinery")
    e.add_argument("--ablate", nargs="+", choices=sorted(ABLATABLE),
                   default=["seamless-loop", "state-a-default", "sync-same-stage-motion",
                            "verify-before-delivery", "one-term-per-concept"])
    e.add_argument("--epochs", type=int, default=2)
    e.add_argument("--e-steps", type=int, default=8)
    args = ap.parse_args()
    sys.exit({"planted": cmd_planted, "null": cmd_null, "epochs": cmd_epochs}[args.cmd](args))


if __name__ == "__main__":
    main()
