# Failure classes: sql-queries

Symptom-class to mechanism guide, consumed as `{FAILURE_CLASS_GUIDE}` in
the editor prompt (PROGRAM.md §4b). The rubric names the class in the
receipt as `symptom:<class>` when the rollout's rows match a probe query
that breaks exactly one house convention. The mechanism column says where
to look, not what to write.

| class | symptom looks like | mechanism |
|---|---|---|
| totals-too-high | a sum, count or average is larger than the reference for the same key | orders are being counted that the house does not count |
| totals-too-low | a sum, count or average is smaller than the reference; rankings drop entries | the set of orders that count is narrower than the house one |
| ghost-rows | extra customers in a listing, or totals slightly above the reference | rows exist in `customers` that no report should include |
| split-categories | one category appears under several spellings | grouping on the raw stored value instead of a normalized one |
| off-by-a-hundred | numbers are 100x the reference | the unit the column is stored in differs from the unit asked for |
| missing-zero-rows | fewer rows than the reference; the missing ones have zero activity | the join drops entities with nothing on the other side |
| wrong-window | a date-window count is off by the orders of one day | the window's end is inclusive on a column that carries a time |
| unclassified | rows differ and no probe matches | read the diff rows; more than one convention may be missing at once |
| not-a-query | `sql_error` or `no_sql`; several statements, prose, or a wrapper around the SQL | the reply format is not what the runner expects |
