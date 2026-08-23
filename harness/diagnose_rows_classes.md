# Failure-class guide: row-set suites (diagnose_rows.py)

Class -> mechanism guide for suites whose rubrics append
`harness/diagnose_rows.py` checks. A suite that uses those checks should
ship this content (plus any suite-specific classes) as
`tasks/<suite>/failure_classes.md`; the manager pastes that file into the
editor prompt's `{FAILURE_CLASS_GUIDE}` slot.

- `rows_extra_only`: a scope/filter rule is missing (status, draft,
  dedup-existence). Add the missing filter rule.
- `rows_missing_only`: something over-filters. Soften or scope a filter.
- `order_wrong` / `order_wrong_reversed`: an ordering convention (metric
  direction or tie-break) is missing or backwards.
- `values_rounding_grain`: rounding happens at the wrong level or
  precision. State where and to how many places, for that shape only.
- `values_scaled_*`: a systematic multiplier, usually missed dedup,
  discount, or unit conversion. Name the mechanism.
- `values_drift`: per-row irregular error, usually a per-row lookup
  (as-of join, fallback) done wrong.
- `sql_error` / `script_error`: the skill let syntax through. Add a
  verification step, not content rules.
