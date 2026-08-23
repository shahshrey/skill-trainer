"""harvest.py: recurring user requests across sessions become candidates;
one-offs, meta lines, and single-session repeats do not (plan §10)."""
import json
import subprocess
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent / "harness"

ASK_A1 = "Make me an animated GIF infographic of our deploy pipeline with five stages"
ASK_A2 = "Can you make an animated gif infographic showing the deploy pipeline stages?"
ASK_B = "Rename the variable foo to bar in utils.py"


def claude_rec(text):
    return json.dumps({"type": "user", "cwd": "/Users/x/proj",
                       "message": {"role": "user", "content": [
                           {"type": "text", "text": text}]}})


def make_tree(tmp_path):
    proj = tmp_path / ".claude" / "projects" / "-Users-x-proj"
    proj.mkdir(parents=True)
    (proj / "s1.jsonl").write_text("\n".join([
        claude_rec(ASK_A1),
        claude_rec("thanks, that works now, perfect"),
        claude_rec("<command-name>/model</command-name>"),  # meta: skipped
        claude_rec(ASK_B),
    ]))
    (proj / "s2.jsonl").write_text("\n".join([
        claude_rec(ASK_A2),
        claude_rec("Draft a haiku about databases for the team newsletter page"),
    ]))
    return tmp_path


def harvest(tmp_path, *extra):
    out = tmp_path / "cand.jsonl"
    r = subprocess.run([sys.executable, str(HARNESS / "harvest.py"),
                        "--source", "claude", "--root", str(tmp_path),
                        "--out", str(out), *extra],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    return [json.loads(l) for l in out.read_text().splitlines()]


def test_recurring_request_across_sessions_is_a_candidate(tmp_path):
    cands = harvest(make_tree(tmp_path))
    assert len(cands) == 1
    c = cands[0]
    assert "deploy pipeline" in c["prompt"].lower()
    assert c["occurrences"] == 2 and c["sessions"] == 2
    assert len(c["sources"]) == 2 and all("#" in s for s in c["sources"])


def test_positive_followup_marks_observed_good(tmp_path):
    c = harvest(make_tree(tmp_path))[0]
    assert c["observed_good"] is True


def test_single_session_repeat_is_not_recurrence(tmp_path):
    proj = tmp_path / ".claude" / "projects" / "-Users-x-proj"
    proj.mkdir(parents=True)
    (proj / "solo.jsonl").write_text("\n".join([claude_rec(ASK_A1),
                                                claude_rec(ASK_A2)]))
    assert harvest(tmp_path) == []


def test_project_filter_excludes_other_projects(tmp_path):
    make_tree(tmp_path)
    assert harvest(tmp_path, "--project", "/Users/x/other") == []
    assert len(harvest(tmp_path, "--project", "/Users/x/proj")) == 1
