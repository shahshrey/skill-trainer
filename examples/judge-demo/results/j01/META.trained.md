# Optimizer memory: skill-review

## Epoch 0 — edit-style findings

**Safe pattern — checklist additions**
Adding a new defect-class entry to step 4 of the review process reliably expands recall without regressing existing checks. This is the primary lever for recall improvement. Use it in epoch 1.

**Unsafe patterns — do not repeat**
- Restricting the scope of any existing check caused regressions on tasks that relied on the broader scope.
- Adding concrete word examples to Voice (e.g., adding "your") created false positives on instructional text.
- Adding a Time check with staleness examples (calendar dates, version strings) caused false positives on temporal descriptions in normal usage (e.g., "monthly", "weekly").
- Adding reference-file quality or formatting sub-checks caused regressions on reference-heavy tasks.

## Key regression risks

- **Defaults over-fire**: Any wording that treats "multiple alternatives" as a flag will catch platform-specific commands that are legitimately conditional on the reader's OS. Defaults must require that all alternatives apply in the same environment.
- **Voice over-fire**: Expanding Voice examples beyond "you should" / "you must" risks catching legitimate instructional text. Keep Voice check minimal.
- **Time over-fire**: Recurring-interval vocabulary ("monthly", "weekly", "annually") is not a staleness signal. Time check should target explicit calendar dates and pinned version strings only.

## Persistent recall gaps (entering epoch 1)

- **inconsistent-terms**: Synonym proliferation across body text is persistently missed. The reviewer scans rather than enumerates; needs an explicit mechanical enumeration step.
- **dir-name-mismatch**: Suffix differences (not just single-character swaps) are accepted as matching. Needs character-by-character comparison instruction.
- **nested-refs**: Reviewer stops at the file list; does not open each reference file to check for further links.
- **body-second-person**: Occasional miss when second-person phrasing is embedded mid-paragraph.

## Patterns for epoch 1

- SLOW_UPDATE additions targeting the four recall gaps above are safe: they provide disambiguation without restricting scope.
- Continue checklist additions in step 4 for any new defect classes.
- Avoid adding worked examples to Voice or Time checks.
- Do not add sub-checks under References that evaluate reference-file content quality or formatting.
