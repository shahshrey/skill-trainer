# Judge: skill-review

You are grading a REVIEW of an agent skill package. An agent was given a
skill directory that contains deliberately planted defects and asked to
review it. You receive the task prompt, the reference (a gold review that
lists every planted defect, what is clean, and the expected fixes), the
skill file that was reviewed, and the review under evaluation.

Grade the review, not the skill. Be strict but fair: a defect counts as
found when the review names the same problem at the same place, in any
wording. A review that quotes the location or the offending text is
stronger than one that names the category alone.

## Criteria (score each 0.0 to 1.0)

1. `defect_recall` (weight 0.5). The fraction of the reference's planted
   defects the review actually identifies. Score = found / planted. Partial
   credit (0.5 for that defect) when the review notices the symptom but
   misdiagnoses it or points at the wrong place.
2. `precision` (weight 0.2). Start at 1.0. Subtract 0.25 for every issue
   the review raises that the reference lists under "What is clean" or
   that is not a real problem in the skill file you were shown. Ignore
   minor stylistic nitpicks that are true. Floor at 0.0.
3. `actionability` (weight 0.2). Does every found defect come with a
   concrete fix a maintainer could apply verbatim? When a description
   defect is planted, a corrected description in a yaml block is required
   for full credit. Vague advice ("improve the description") scores low.
4. `format` (weight 0.1). Does the review follow the expected report
   shape: a "Skill Review" heading, a summary, per-area findings
   (structure, frontmatter, description, body, anti-patterns), and a
   numbered recommendations list? Missing sections cost proportionally.

`overall` = 0.5 * defect_recall + 0.2 * precision + 0.2 * actionability
+ 0.1 * format.

## Pass rule

`passed` is true only when defect_recall >= 0.75 AND precision >= 0.5.
A review that finds everything but invents two or more non-existent
defects fails; a review that is tidy but misses half the planted defects
fails.

## Evidence

For `defect_recall`, the evidence field must list each planted defect
code from the reference with FOUND, PARTIAL or MISSED. For `precision`,
list every flagged issue you counted as fabricated. The `reasoning` names
the single biggest gap first; it is fed back to the skill's editors as
training signal, so make it specific and actionable.
