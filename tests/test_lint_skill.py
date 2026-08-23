"""Lint gate: known-bad fixture skills trigger the right exit class."""
from pathlib import Path

import pytest

from lint_skill import lint

GOOD = """---
name: good-skill
description: Renders looping GIF infographics from briefs. Use when the user wants an animated infographic or social GIF.
---

# Good skill

Do the thing well. Default fps is 12.
"""


def write(tmp_path: Path, text: str, name: str = "SKILL.md") -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_good_skill_passes(tmp_path):
    assert lint(write(tmp_path, GOOD))["status"] == "pass"


def test_oversized_body_fails(tmp_path):
    big = GOOD + "\n" * 520
    report = lint(write(tmp_path, big))
    assert report["status"] == "fail"
    assert any("500" in f for f in report["failed_required"])


def test_bad_name_fails(tmp_path):
    bad = GOOD.replace("name: good-skill", "name: Good_Skill!")
    assert lint(write(tmp_path, bad))["status"] == "fail"


def test_first_person_description_fails(tmp_path):
    bad = GOOD.replace("Renders looping", "I can render looping")
    report = lint(write(tmp_path, bad))
    assert report["status"] == "fail"
    assert any("first/second person" in f for f in report["failed_required"])


def test_missing_when_clause_fails(tmp_path):
    bad = GOOD.replace(
        "description: Renders looping GIF infographics from briefs. Use when the user wants an animated infographic or social GIF.",
        "description: Renders looping GIF infographics from briefs with animation primitives.")
    report = lint(write(tmp_path, bad))
    assert any("when-to-use" in f for f in report["failed_required"])


def test_prompt_mode_skips_frontmatter(tmp_path):
    bare = "# Bare skill\n\nJust body text, no frontmatter.\n"
    assert lint(write(tmp_path, bare), deploy_mode="prompt")["status"] == "pass"


def test_windows_path_fails(tmp_path):
    bad = GOOD + "\nRun scripts\\capture.py to render.\n"
    report = lint(write(tmp_path, bad))
    assert report["status"] == "fail"
    assert any("Windows" in f for f in report["failed_required"])


def test_time_sensitive_phrase_is_needs_work(tmp_path):
    bad = GOOD + "\nDo this before August 2025 for best results.\n"
    report = lint(write(tmp_path, bad))
    assert report["status"] == "needs_work"


def test_option_list_without_default_is_needs_work(tmp_path):
    bad = GOOD + "\nUse png or webp or jpeg for the base layer.\n"
    report = lint(write(tmp_path, bad))
    assert report["status"] == "needs_work"


def test_missing_linked_file_fails(tmp_path):
    bad = GOOD + "\nSee [the archetypes](ARCHETYPES.md) for details.\n"
    report = lint(write(tmp_path, bad))
    assert report["status"] == "fail"
    assert any("does not exist" in f for f in report["failed_required"])


def test_growth_guard_blocks_bloat(tmp_path):
    prev = write(tmp_path, GOOD, "prev.md")
    grown = GOOD + ("New rule line that pads the body considerably.\n" * 20)
    report = lint(write(tmp_path, grown), prev_skill=prev)
    assert report["status"] == "fail"
    assert any("growth" in f for f in report["failed_required"])


def test_growth_guard_floor_allows_single_rule_on_small_skill(tmp_path):
    prev = write(tmp_path, GOOD, "prev.md")
    grown = GOOD + "One new rule line, well under the absolute floor.\n"
    assert lint(write(tmp_path, grown), prev_skill=prev)["status"] == "pass"


def test_growth_guard_ignores_protected_blocks(tmp_path):
    prev = write(tmp_path, GOOD, "prev.md")
    grown = GOOD + ("\n<!-- PROTECTED:APPENDIX:START -->\n"
                    + "manager note\n" * 100
                    + "<!-- PROTECTED:APPENDIX:END -->\n")
    assert lint(write(tmp_path, grown), prev_skill=prev)["status"] == "pass"


def test_real_target_skill_passes_lint():
    # Discovery-based: lint whatever skill packages exist, never a
    # hardcoded skill name (the framework must outlive any one skill).
    root = Path(__file__).resolve().parent.parent
    skills = sorted(root.glob("skills/*/SKILL.md"))
    if not skills:
        pytest.skip("no skill package under skills/, nothing to lint")
    for skill_md in skills:
        report = lint(skill_md)
        assert report["status"] in ("pass", "needs_work"), report
        assert not report["failed_required"], report
