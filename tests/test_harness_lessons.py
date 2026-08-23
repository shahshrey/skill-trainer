"""Generic modules harvested from the 2026-08-04 production sweep:
failure-shape diagnosis, attempt carry-forward, escalation policy, and
orphaned-worker detection (PROGRAM §5/§6)."""
import numpy as np

from carryforward import harvest, stage
from diagnosis import failure_signature, worst_blocks
from escalation import next_plan, update_stalls
from rollout_batch import find_orphans


# ---- diagnosis ------------------------------------------------------------

def test_signature_pass():
    assert failure_signature([0.9, 0.95], 0.8) == \
        {"kind": "pass", "fail_ranges": []}


def test_signature_uniform_shortfall():
    # everything fails by a similar margin: a global property is wrong
    sig = failure_signature([0.79] * 30, 0.8)
    assert sig["kind"] == "uniform_shortfall"
    assert sig["fail_ranges"] == [[0, 29]]


def test_signature_clustered_shortfall():
    # a minority of units fail, contiguously: wrong only in those spans
    scores = [0.9] * 100 + [0.7] * 10 + [0.9] * 38
    sig = failure_signature(scores, 0.8)
    assert sig["kind"] == "clustered_shortfall"
    assert sig["fail_ranges"] == [[100, 109]]


def test_signature_scattered():
    # majority failing but with real spread: no clean pattern
    scores = [0.5, 0.9, 0.6, 0.9, 0.55, 0.7, 0.65, 0.75, 0.6, 0.5]
    assert failure_signature(scores, 0.8)["kind"] == "scattered"


def test_worst_blocks_localizes_the_bad_region():
    ref = np.zeros((90, 90))
    cand = ref.copy()
    cand[45:90, 0:45] = 255            # bottom-left block ruined
    metric = lambda a, b: 1.0 - float(np.abs(a - b).mean()) / 255
    blocks = worst_blocks(cand, ref, metric, block=45)
    assert blocks[0] == {"score": 0.0, "x_frac": 0.0, "y_frac": 0.5}
    assert len(blocks) == 1            # matching blocks not reported


# ---- carryforward ---------------------------------------------------------

def test_harvest_and_stage_round_trip(tmp_path):
    wd, entry, staged = (tmp_path / d for d in ("wd", "entry", "staged"))
    for d in (wd, entry, staged):
        d.mkdir()
    (wd / "output.txt").write_bytes(b"x" * 5000 + b"ROOT CAUSE: font face")
    (wd / "_diff_title.png").write_bytes(b"png")
    (wd / "page.html").write_text("<html>")   # not an artifact: no _ prefix
    harvest(wd, entry)
    assert (entry / "conclusion.txt").read_text().endswith("font face")
    assert len((entry / "conclusion.txt").read_bytes()) <= 2000
    assert [p.name for p in (entry / "artifacts").iterdir()] == \
        ["_diff_title.png"]
    conclusion = stage(entry, staged)
    assert conclusion.endswith("font face")
    assert (staged / "_diff_title.png").exists()
    assert not (staged / "page.html").exists()


def test_harvest_caps_artifact_size(tmp_path):
    wd, entry = tmp_path / "wd", tmp_path / "entry"
    wd.mkdir(), entry.mkdir()
    (wd / "_huge.png").write_bytes(b"x" * 500_000)     # over 400KB: dropped
    (wd / "_small.png").write_bytes(b"x")
    harvest(wd, entry)
    assert [p.name for p in (entry / "artifacts").iterdir()] == ["_small.png"]


def test_stage_without_harvested_entry_is_a_noop(tmp_path):
    entry, staged = tmp_path / "entry", tmp_path / "staged"
    entry.mkdir(), staged.mkdir()
    assert stage(entry, staged) == ""
    assert list(staged.iterdir()) == []


# ---- escalation -----------------------------------------------------------

def test_escalation_ladder():
    base = 1800
    assert next_plan(0, False, base) == {"timeout": 1800, "stage": True}
    # timeout on the last attempt: give the retry room, keep the staging
    assert next_plan(0, True, base) == {"timeout": 3600, "stage": True}
    # one stalled round: same strategy, more time
    assert next_plan(1, False, base) == {"timeout": 3600, "stage": True}
    # repeated stalls: alternate scratch attempts to escape the local optimum
    assert next_plan(2, False, base) == {"timeout": 3600, "stage": False}
    assert next_plan(3, False, base) == {"timeout": 3600, "stage": True}
    assert next_plan(4, False, base) == {"timeout": 3600, "stage": False}


def test_update_stalls():
    stalls = {"a": 1}
    update_stalls(stalls, {"a": False, "b": True})
    assert stalls == {"a": 2, "b": 0}
    update_stalls(stalls, {"a": True})
    assert stalls["a"] == 0


# ---- orphaned-worker detection --------------------------------------------

def test_find_orphans_detects_reparented_wrappers_and_children():
    ps = "\n".join([
        "  1     0 /sbin/launchd",
        "  500   1 sh -c __copilot_pid_path=/tmp/x copilot -p prompt",
        "  501 500 node /usr/local/bin/copilot",
        # live wrapper: parent is a run_task process, not PID 1
        "  600 400 sh -c __copilot_pid_path=/tmp/y copilot -p prompt",
        "  601 600 node /usr/local/bin/copilot",
        "  700   1 some-unrelated-daemon",
    ])
    assert sorted(find_orphans(ps, "__copilot_pid_path")) == [500, 501]


# ---- backend command builders ---------------------------------------------

def test_positional_prompt_backends_are_dash_safe():
    """Injected skill text usually opens with '---' frontmatter; backends
    that take the prompt positionally must fence it behind '--' or the CLI
    parses it as an option (cursor did, 2026-08-06)."""
    from run_task import BACKENDS
    for backend in ("cursor", "codex"):
        cmd = BACKENDS[backend]("do the task", "---\nname: x\n---\nbody", [])
        payload = cmd[-1]
        assert payload.startswith("---")
        assert cmd[cmd.index("--") + 1] == payload


def test_cursor_orphan_marker_ignores_ide_worker_daemons():
    """Cursor's IDE keeps its own `worker start` daemons at ppid 1; only
    harness-launched headless workers (-p --force --trust) may be reaped."""
    ps = "\n".join([
        "  1     0 /sbin/launchd",
        "  900   1 cursor-agent --api-key x worker start --worker-dir /repo",
        "  910   1 cursor-agent -p --force --trust --model m -- prompt",
        "  911 910 node helper",
        "  920 400 cursor-agent -p --force --trust --model m -- prompt",
    ])
    from rollout_batch import ORPHAN_MARKERS
    assert sorted(find_orphans(ps, ORPHAN_MARKERS["cursor"])) == [910, 911]


# ---- verdict provenance ----------------------------------------------------

def test_provenance_stamp_and_stale():
    from provenance import stamp, stale
    meta = stamp({"hard": 1}, "v5")
    assert not stale(meta, "v5")
    assert stale(meta, "v6")          # rubric upgraded: re-judge
    assert stale({"hard": 1}, "v5")   # unversioned verdict: always stale


def test_provenance_demote_keeps_history():
    from provenance import demote, stamp
    meta = stamp({"hard": 1, "score": 0.9}, "v4")
    demote(meta, ["live_anim_broken"], version="v5")
    assert meta["hard"] == 0
    assert meta["previous"] == {"hard": 1, "rubric_version": "v4"}
    assert meta["demoted_by"] == ["live_anim_broken"]
    assert meta["rubric_version"] == "v5"
    # idempotent: a second demotion must not overwrite the original history
    demote(meta, ["other"], version="v6")
    assert meta["previous"]["rubric_version"] == "v4"
