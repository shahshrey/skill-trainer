#!/usr/bin/env python3
"""LLM-as-judge scoring (score.py mode ``judge``).

Not every skill can be scored deterministically: UI design, how human a
text reads, the quality of a review. This mode asks an LLM for a
STRUCTURED verdict and feeds the same ``{hard, soft, checks}`` into the
unchanged paired gate. It is a separate way to measure, never a
replacement: a suite picks its mode in scoring.md.

Usage:
  judge.py --check --suite tasks/X            readiness + dataset/rubric report
  judge.py --suite tasks/X --workdir <ws>     score one workspace (debug)

Suite contract (all under tasks/X/):
  judge.md        the judge prompt for THIS skill: the criteria, their
                  weights, what pass means. Part of the scoring contract
                  (score.py hashes it into rubric_version).
  scoring.md      ```json {"default_mode": "judge", "judge": {...}}```
                  judge keys (all optional): model (MiniMax-M3), base_url,
                  samples (1), temperature (0), timeout (240), max_tokens
                  (8000), max_attempts (3), criteria_weights {name: w},
                  pass_threshold (0.7)
  task rows       "reference": "<path relative to suite>" or
                  "reference_text": "<inline>"  -> DATASET mode: the judge
                  scores closeness to what good looks like.
                  Neither -> RUBRIC mode: judge.md alone defines good.
                  "judge_inputs": ["<workdir-relative globs>"] files the
                  judge should see besides output.txt (e.g. the fixture
                  the agent worked on).

What "good" means, in priority order:
  1. A DATASET of good outputs (reference per task). Preferred: a concrete
     target to climb toward, exactly like deterministic suites.
  2. A RUBRIC only. Works only as well as judge.md describes the ideal.
  ``--check`` reports which mode each task runs in and warns about (2).

Transport: MiniMax M3 via its OpenAI-compatible endpoint, through the
LangChain SDK (ChatOpenAI). The endpoint ignores response_format
json_schema and forced tool_choice, and prefixes content with <think>
blocks, so structured output = bind_tools(tool_choice="auto") with a
tool-call parse, falling back to JSON extracted from the think-stripped
content. Both paths validate against the same schema.

Aggregation over N samples: soft = mean(overall), hard = majority(passed)
(ties fail closed). Verdicts are cached in <workdir>/judge.json keyed by
(rubric, model, samples, prompt, reference, inputs, output): rescoring a
batch never re-spends.

API key: MINIMAX_API_KEY in the environment, else the repo .env
(MINIMAX_API_KEY or MINIMAX-API-KEY). LangChain deps come from
requirements-judge.txt and are imported only inside call_model(), so the
rest of the harness stays stdlib-only.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from score import suite_config

DEFAULT_BASE_URL = "https://api.minimax.io/v1"
DEFAULT_MODEL = "MiniMax-M3"
KEY_NAMES = ("MINIMAX_API_KEY", "MINIMAX-API-KEY")
THINK_RE = re.compile(r"<think>[\s\S]*?</think>\s*", re.IGNORECASE)
INPUT_CAP = 16000  # chars per judge input file; keeps the prompt bounded

DEFAULTS = {"model": DEFAULT_MODEL, "base_url": DEFAULT_BASE_URL, "samples": 1,
            "temperature": 0.0, "timeout": 240, "max_tokens": 8000, "max_attempts": 3,
            "pass_threshold": 0.7, "criteria_weights": None}

VERDICT_TOOL = {
    "type": "function",
    "function": {
        "name": "record_verdict",
        "description": "Record the structured verdict for the output under evaluation.",
        "parameters": {
            "type": "object",
            "properties": {
                "criteria": {
                    "type": "array",
                    "description": "One entry per criterion named in the rubric.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "score": {"type": "number", "description": "0.0 to 1.0"},
                            "evidence": {"type": "string",
                                         "description": "What in the output earned this score."},
                        },
                        "required": ["name", "score", "evidence"],
                    },
                },
                "overall": {"type": "number", "description": "0.0 to 1.0"},
                "passed": {"type": "boolean"},
                "reasoning": {"type": "string",
                              "description": "Two to five sentences; name the biggest gap."},
            },
            "required": ["criteria", "overall", "passed", "reasoning"],
        },
    },
}

SYSTEM_SUFFIX = """

## Verdict protocol

Call the `record_verdict` tool exactly once with your verdict. Score every
criterion named above from 0.0 to 1.0 and quote the evidence. `overall` is
the weighted combination the rubric describes; `passed` follows the
rubric's pass rule. If you cannot call the tool, reply with ONLY a JSON
object with the same fields (criteria, overall, passed, reasoning).
"""


# --- configuration -------------------------------------------------------------

def find_env_file(start: Path | None = None) -> Path | None:
    here = start or Path(__file__).resolve().parent
    for d in (here, *here.parents):
        if (d / ".env").is_file():
            return d / ".env"
    return None


def load_api_key(env_file: Path | None = None) -> str | None:
    for name in KEY_NAMES:
        if os.environ.get(name):
            return os.environ[name]
    path = env_file if env_file is not None else find_env_file()
    if path is None or not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        if key.strip() in KEY_NAMES:
            return val.strip().strip("'\"") or None
    return None


def judge_config(config: dict) -> dict:
    return dict(DEFAULTS, **(config.get("judge") or {}))


def suite_tasks(suite: Path) -> list[dict]:
    """Every task row across train/val/test, each tagged with its split."""
    rows = []
    for split in ("train", "val", "test"):
        path = suite / f"{split}.jsonl"
        if path.exists():
            rows += [{"split": split, **json.loads(line)}
                     for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows


def load_rubric(suite: Path) -> str:
    path = suite / "judge.md"
    if not path.exists():
        raise FileNotFoundError(f"scoring mode 'judge' but {path} is missing")
    return path.read_text(encoding="utf-8")


def resolve_reference(task: dict, suite: Path) -> str | None:
    """Dataset mode reference text, or None for rubric mode."""
    if task.get("reference_text"):
        return str(task["reference_text"])
    rel = task.get("reference")
    if not rel:
        return None
    path = suite / rel
    if not path.is_file():
        raise FileNotFoundError(f"task {task.get('id')!r}: reference {rel!r} not found under {suite}")
    return path.read_text(encoding="utf-8")


def collect_inputs(task: dict, workdir: Path) -> dict[str, str]:
    """{relative path: content} for every judge_inputs glob, capped."""
    found: dict[str, str] = {}
    for pattern in task.get("judge_inputs") or []:
        for hit in sorted(glob.glob(str(workdir / pattern), recursive=True)):
            p = Path(hit)
            if p.is_file():
                text = p.read_text(encoding="utf-8", errors="replace")
                if len(text) > INPUT_CAP:
                    text = text[:INPUT_CAP] + f"\n... [truncated at {INPUT_CAP} chars]"
                found[str(p.relative_to(workdir))] = text
    return found


# --- prompt --------------------------------------------------------------------

def build_messages(rubric: str, task: dict, output: str, reference: str | None,
                   inputs: dict[str, str]) -> tuple[str, str]:
    system = rubric.rstrip() + SYSTEM_SUFFIX
    parts = ["## Task prompt given to the agent\n", str(task.get("prompt", "")).rstrip(), "\n"]
    if reference is not None:
        parts += ["\n## Reference: what a good output looks like for this task\n",
                  "Score the output by how closely it achieves what the reference "
                  "achieves. The reference is the target, not a template to match "
                  "verbatim.\n\n", reference.rstrip(), "\n"]
    else:
        parts += ["\n## Reference\n", "No reference is provided for this task. Judge the "
                  "output against the rubric criteria alone.\n"]
    for rel, text in inputs.items():
        parts += [f"\n## Input file: {rel}\n", "```\n", text.rstrip(), "\n```\n"]
    parts += ["\n## Output under evaluation\n", "```\n", output.rstrip(), "\n```\n"]
    return system, "".join(parts)


# --- model call (LangChain; the only non-stdlib code path) ---------------------

def make_llm(cfg: dict, api_key: str):
    from langchain_openai import ChatOpenAI  # noqa: PLC0415 (lazy: optional dep)
    llm = ChatOpenAI(model=cfg["model"], base_url=cfg["base_url"], api_key=api_key,
                     temperature=float(cfg["temperature"]), timeout=int(cfg["timeout"]),
                     max_tokens=int(cfg["max_tokens"]), max_retries=2)
    # MiniMax rejects a forced tool_choice; "auto" reliably yields the call.
    return llm.bind_tools([VERDICT_TOOL], tool_choice="auto")


def call_model(messages: tuple[str, str], cfg: dict, api_key: str) -> dict:
    """{"tool_args": dict | None, "content": str} from one model round-trip."""
    from langchain_core.messages import HumanMessage, SystemMessage  # noqa: PLC0415
    system, user = messages
    resp = make_llm(cfg, api_key).invoke([SystemMessage(content=system),
                                          HumanMessage(content=user)])
    tool_args = None
    for call in getattr(resp, "tool_calls", None) or []:
        if call.get("name") == VERDICT_TOOL["function"]["name"]:
            tool_args = call.get("args")
            break
    content = resp.content
    if isinstance(content, list):  # some providers return content parts
        content = "".join(part.get("text", "") if isinstance(part, dict) else str(part)
                          for part in content)
    return {"tool_args": tool_args, "content": content or ""}


# --- verdict parsing / validation --------------------------------------------------

def _clamp(x) -> float:
    if isinstance(x, str) and x.strip().lower() in ("true", "false"):
        x = x.strip().lower() == "true"  # a stray true/false in a score slot
    return max(0.0, min(1.0, float(x)))  # float(True) == 1.0


def validate_verdict(obj: dict) -> dict:
    if not isinstance(obj, dict) or not isinstance(obj.get("criteria"), list) or not obj["criteria"]:
        raise ValueError("verdict must carry a non-empty 'criteria' list")
    criteria = []
    for c in obj["criteria"]:
        if not isinstance(c, dict) or "name" not in c or "score" not in c:
            raise ValueError(f"criterion missing name/score: {c!r}")
        criteria.append({"name": str(c["name"]), "score": _clamp(c["score"]),
                         "evidence": str(c.get("evidence", ""))})
    overall = obj.get("overall")
    overall = (_clamp(overall) if overall is not None
               else sum(c["score"] for c in criteria) / len(criteria))
    passed = obj.get("passed")
    if isinstance(passed, str):
        passed = passed.strip().lower() in ("true", "yes", "pass", "1")
    elif passed is None:
        passed = overall >= DEFAULTS["pass_threshold"]
    return {"criteria": criteria, "overall": round(overall, 4), "passed": bool(passed),
            "reasoning": str(obj.get("reasoning", ""))}


def _first_json_object(text: str) -> dict | None:
    dec = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                obj, _ = dec.raw_decode(text[i:])
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and "criteria" in obj:
                return obj
    return None


def parse_verdict(raw: dict) -> dict:
    tool_err: Exception | None = None
    if raw.get("tool_args"):
        try:
            return validate_verdict(raw["tool_args"])
        except ValueError as exc:  # garbled tool call: the content may still carry JSON
            tool_err = exc
    obj = _first_json_object(THINK_RE.sub("", raw.get("content") or ""))
    if obj is None:
        raise ValueError(f"no JSON verdict in content and no usable tool call ({tool_err or 'none'})")
    return validate_verdict(obj)


# --- scoring -----------------------------------------------------------------------

def _cache_key(rubric: str, cfg: dict, task: dict, reference: str | None,
               inputs: dict[str, str], output: str) -> str:
    h = hashlib.sha256()
    for part in (rubric, cfg["model"], str(cfg["samples"]), str(cfg["temperature"]),
                 json.dumps(cfg.get("criteria_weights"), sort_keys=True),
                 str(task.get("prompt", "")), reference or "", json.dumps(inputs, sort_keys=True),
                 output):
        h.update(part.encode("utf-8", "replace"))
        h.update(b"\0")
    return h.hexdigest()


def _weighted_overall(verdict: dict, weights: dict | None) -> float:
    if not weights:
        return verdict["overall"]
    scores = {c["name"]: c["score"] for c in verdict["criteria"]}
    total = sum(float(w) for w in weights.values()) or 1.0
    return round(sum(float(w) * scores.get(name, 0.0) for name, w in weights.items()) / total, 4)


def aggregate(samples: list[dict], weights: dict | None) -> tuple[int, float, list[str]]:
    n = len(samples)
    overalls = [_weighted_overall(s, weights) for s in samples]
    soft = round(sum(overalls) / n, 4)
    hard = int(sum(1 for s in samples if s["passed"]) * 2 > n)  # ties fail closed
    per_crit: dict[str, list[float]] = {}
    for s in samples:
        for c in s["criteria"]:
            if weights and c["name"] not in weights:
                continue  # models sometimes echo overall/passed as criteria
            per_crit.setdefault(c["name"], []).append(c["score"])
    checks = [f"crit:{name}={round(sum(v) / len(v), 4)}" for name, v in per_crit.items()]
    checks.append("judge:pass" if hard else "judge:fail")
    return hard, soft, checks


def _cached_samples(cache_path: Path, key: str, n: int) -> list[dict] | None:
    """Verdicts saved by an earlier scoring of the same (rubric, output, ...)."""
    if not cache_path.exists():
        return None
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    samples = cached.get("samples") or []
    return samples if cached.get("key") == key and len(samples) == n else None


def _one_verdict(messages: tuple[str, str], cfg: dict, api_key: str, model_call) -> dict:
    """One validated verdict; a malformed reply is retried with a correction
    appended, because at temperature 0 the same prompt reproduces the same
    malformed reply."""
    system, user = messages
    last_err: Exception | None = None
    for attempt in range(int(cfg["max_attempts"])):
        try:
            return parse_verdict(model_call((system, user), cfg, api_key))
        except ValueError as exc:
            last_err = exc
            user += (f"\n\n## Correction (attempt {attempt + 2})\nYour previous verdict was "
                     f"rejected: {str(exc)[:300]}. Every criterion needs a numeric score from "
                     "0.0 to 1.0, `overall` is a number, `passed` is a boolean, `reasoning` is "
                     "a string. Call the tool again, or reply with only the JSON object.")
    raise ValueError(f"judge: unparseable verdict after retries: {last_err}")


def judge_output(task: dict, workdir: Path, suite: Path, config: dict, *,
                 call_model=None, api_key: str | None = None,
                 env_file: Path | None = None) -> dict:
    model_call = call_model or globals()["call_model"]  # resolved late: tests patch it
    cfg = judge_config(config)
    rubric = load_rubric(suite)
    reference = resolve_reference(task, suite)
    mode = "dataset" if reference is not None else "rubric"
    inputs = collect_inputs(task, workdir)
    output_path = workdir / "output.txt"
    output = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
    key = _cache_key(rubric, cfg, task, reference, inputs, output)
    n = int(cfg["samples"])

    cache_path = workdir / "judge.json"
    samples = _cached_samples(cache_path, key, n)
    if samples is None:
        api_key = api_key or load_api_key(env_file)
        if not api_key:
            raise RuntimeError("judge: no MiniMax API key (set MINIMAX_API_KEY or put "
                               "MINIMAX-API-KEY=... in the repo .env)")
        messages = build_messages(rubric, task, output, reference, inputs)
        with ThreadPoolExecutor(max_workers=n) as pool:  # independent network calls
            samples = list(pool.map(lambda _: _one_verdict(messages, cfg, api_key, model_call),
                                    range(n)))
        cache_path.write_text(json.dumps({"key": key, "model": cfg["model"], "mode": mode,
                                          "samples": samples}, indent=2), encoding="utf-8")

    hard, soft, checks = aggregate(samples, cfg.get("criteria_weights"))
    return {"hard": hard, "soft": soft, "checks": [*checks, f"ref:{mode}"], "judge_mode": mode}


# --- readiness check ---------------------------------------------------------------

def check(suite: Path, env_file: Path | None = None) -> dict:
    """Readiness report: key, deps, judge.md, and per-task dataset/rubric mode."""
    try:
        import langchain_openai  # noqa: F401, PLC0415
        deps = True
    except ImportError:
        deps = False
    key = bool(load_api_key(env_file))
    has_rubric = (suite / "judge.md").is_file()
    cfg = judge_config(suite_config(suite))
    missing: list[str] = []
    by_split: dict[str, dict[str, int]] = {}
    for row in suite_tasks(suite):
        counts = by_split.setdefault(row["split"], {"dataset": 0, "rubric": 0})
        ref = row.get("reference")
        if row.get("reference_text") or (ref and (suite / ref).is_file()):
            counts["dataset"] += 1
        elif ref:
            missing.append(str(row.get("id")))
        else:
            counts["rubric"] += 1
    dataset = sum(c["dataset"] for c in by_split.values())
    rubric_only = sum(c["rubric"] for c in by_split.values())
    warnings = []
    if not deps:
        warnings.append("LangChain not importable: .venv/bin/pip install -r requirements-judge.txt")
    if not key:
        warnings.append("no MiniMax API key: set MINIMAX_API_KEY or MINIMAX-API-KEY=... in .env")
    if not has_rubric:
        warnings.append("judge.md missing: the suite has no judge prompt / rubric")
    if missing:
        warnings.append(f"{len(missing)} task(s) point at a reference file that does not exist")
    if rubric_only:
        warnings.append(
            f"{rubric_only} task(s) run in RUBRIC-ONLY mode (no reference). Their verdicts "
            "are only as good as judge.md's description of the ideal. Preferred: give each "
            "task a 'reference' (a good output) so the loop climbs toward a dataset.")
    return {"ready": deps and key and has_rubric and not missing, "deps": deps, "key": key,
            "judge_md": has_rubric, "model": cfg["model"], "samples": int(cfg["samples"]),
            "tasks": {"dataset": dataset, "rubric": rubric_only, "missing_reference": missing,
                      "by_split": by_split},
            "warnings": warnings}


def print_check(report: dict) -> None:
    t = report["tasks"]
    print(f"judge readiness: {'READY' if report['ready'] else 'NOT READY'}")
    print(f"  model={report['model']} samples={report['samples']} deps={report['deps']} "
          f"key={report['key']} judge.md={report['judge_md']}")
    print(f"  tasks: {t['dataset']} dataset-mode (scored against a reference), "
          f"{t['rubric']} rubric-only, {len(t['missing_reference'])} with a missing reference")
    for split, counts in t["by_split"].items():
        print(f"    {split}: dataset={counts['dataset']} rubric={counts['rubric']}")
    for w in report["warnings"]:
        print(f"  warning: {w}")
    print(json.dumps(report, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--suite", required=True)
    ap.add_argument("--check", action="store_true", help="readiness report; exit 1 if not ready")
    ap.add_argument("--workdir", help="score one workspace and print the result")
    args = ap.parse_args()
    suite = Path(args.suite)
    if args.check:
        report = check(suite)
        print_check(report)
        sys.exit(0 if report["ready"] else 1)
    if not args.workdir:
        ap.error("--check or --workdir is required")
    wd = Path(args.workdir)
    task = json.loads((wd / "task.json").read_text(encoding="utf-8"))
    print(json.dumps(judge_output(task, wd, suite, suite_config(suite)), indent=2))


if __name__ == "__main__":
    main()
