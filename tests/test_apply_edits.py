"""Edit application: four ops, malformed targets, protected refusal."""
from apply_edits import apply_edits

SKILL = """---
name: demo
description: Demo skill. Use when testing.
---

# Demo

Rule one: always be kind.

Rule two: never be late.

<!-- PROTECTED:SLOW_UPDATE:START -->
Strategic guidance lives here.
<!-- PROTECTED:SLOW_UPDATE:END -->
"""


def test_append_inserts_before_protected_block():
    out, errs = apply_edits(SKILL, [{"op": "append", "content": "Rule three: stay calm."}])
    assert not errs
    assert out.index("Rule three") < out.index("PROTECTED:SLOW_UPDATE:START")


def test_append_at_eof_without_protected_block():
    plain = "# Demo\n\nBody.\n"
    out, errs = apply_edits(plain, [{"op": "append", "content": "Tail."}])
    assert not errs
    assert out.endswith("Tail.\n")


def test_insert_after():
    out, errs = apply_edits(SKILL, [{
        "op": "insert_after", "target": "Rule one: always be kind.",
        "content": "Rule 1b: smile."}])
    assert not errs
    assert "always be kind.\nRule 1b: smile." in out


def test_replace():
    out, errs = apply_edits(SKILL, [{
        "op": "replace", "target": "never be late", "content": "never be early"}])
    assert not errs
    assert "never be early" in out and "never be late" not in out


def test_delete():
    out, errs = apply_edits(SKILL, [{"op": "delete", "target": "Rule two: never be late.\n"}])
    assert not errs
    assert "never be late" not in out


def test_malformed_target_errors_and_leaves_text_untouched():
    out, errs = apply_edits(SKILL, [{"op": "replace", "target": "nonexistent", "content": "x"}])
    assert errs and "not found" in errs[0]
    assert out == SKILL


def test_ambiguous_target_refused():
    doubled = SKILL + "\nRule one: always be kind.\n"
    out, errs = apply_edits(doubled, [{"op": "delete", "target": "Rule one: always be kind."}])
    assert errs and "ambiguous" in errs[0]
    assert out == doubled


def test_protected_section_edit_refused():
    out, errs = apply_edits(SKILL, [{
        "op": "replace", "target": "Strategic guidance lives here.", "content": "hacked"}])
    assert errs and "protected" in errs[0]
    assert out == SKILL


def test_frontmatter_edit_refused():
    out, errs = apply_edits(SKILL, [{
        "op": "replace", "target": "name: demo", "content": "name: evil"}])
    assert errs and "protected" in errs[0]
    assert out == SKILL


def test_all_or_nothing_on_partial_failure():
    out, errs = apply_edits(SKILL, [
        {"op": "append", "content": "Good edit."},
        {"op": "delete", "target": "nonexistent"},
    ])
    assert errs
    assert out == SKILL  # first edit rolled back too


def test_unknown_op_refused():
    out, errs = apply_edits(SKILL, [{"op": "rewrite_all", "content": "x"}])
    assert errs and "unknown op" in errs[0]
    assert out == SKILL
