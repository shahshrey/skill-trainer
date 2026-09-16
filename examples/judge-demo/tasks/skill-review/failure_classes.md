# Failure classes: skill-review (judge-mode suite)

Receipts carry the judge's per-criterion scores (`crit:<name>=<score>`)
and its reasoning from `judge.json`. Map them to skill mechanisms like so:

| check pattern | mechanism in the skill |
|---|---|
| `crit:defect_recall` low, reasoning names MISSED codes | The skill's checklist does not tell the reviewer to look for that defect class. Add the specific check (what to grep for, where) rather than a general "be thorough". Defect classes: invalid/reserved names, second-person or vague or trigger-less or over-long descriptions, Windows paths, nested reference chains, time-sensitive statements, option lists without a default, inconsistent terms, obvious explanations, extraneous user-facing files, missing referenced scripts, unexplained magic numbers, second-person body voice, buried quick start, directory/name mismatch, undocumented binary dependencies. |
| `crit:precision` low | The reviewer flags things the reference calls clean, or invents issues. The skill should require quoting the offending text/location for every finding and forbid speculative findings. |
| `crit:actionability` low | Findings without concrete fixes. The skill should require a fix per finding and a corrected description in a yaml block whenever the description is at fault. |
| `crit:format` low | The report shape drifts. The skill should state the exact section list and order. |
| `output_empty` | The agent produced no final message (timeout or crash). Not a skill gap unless systematic. |

The reasoning line from the judge is written to be fed back verbatim; it
names the biggest gap first.
