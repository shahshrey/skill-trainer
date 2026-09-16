## Skill Review: cron-scheduler

### Summary

Three defects undermine this cron scheduling guide: the description is vague and non-specific, the skill name mismatches its directory, and terminology for the scheduled unit of work is inconsistent throughout.

### Planted defects (must all be found)

1. **desc-vague** — SKILL.md frontmatter line 2: The description "Helps with scheduling things." is generic and unspecific. It provides no concrete details about what the skill covers or actionable trigger guidance for when to use it.

2. **dir-name-mismatch** — SKILL.md frontmatter line 1 vs. directory name: The frontmatter name is `cron-schedule` but the directory is `cron-scheduler`. Skill names must match their directory names.

3. **inconsistent-terms** — SKILL.md throughout (lines 22, 26, 30, 37, 49, 52, 54, 65): The skill mixes "job", "task", and "entry" to describe the same concept—a scheduled unit of work. Examples: "run recurring jobs" (description), "Setting Up a Cron Task" (heading), "typical cron job" (line 30), "scheduled entry ran" (line 37), "the entry has write permissions" (line 39), "Not testing the job command" (line 49), "Test the entry command" (line 54), "backup task is scheduled" (line 66).

### What is clean (a good review does NOT flag these)

- Cron syntax is explained with clear examples covering common patterns
- Step-by-step setup instructions include commands for testing and verification
- Monitoring section provides concrete log-inspection techniques for both Linux and macOS
- Debugging section explains the minimal environment in which cron runs
- Comprehensive checklist ensures jobs are properly tested and logged

### Expected recommendations

1. Rewrite the description to be specific and actionable:
   ```yaml
   description: Schedule and validate recurring Unix cron jobs with proper logging, error handling, and monitoring. Use when automating backups, maintenance tasks, or periodic data processing without a full orchestration system.
   ```

2. Rename the skill: change the frontmatter `name` from `cron-schedule` to `cron-scheduler` to match the directory.

3. Choose consistent terminology and apply it throughout. Use "job" as the primary term (standard cron terminology):
   - Replace "Setting Up a Cron Task" with "Setting Up a Cron Job"
   - Replace "if the scheduled entry ran" with "if the scheduled job ran"
   - Replace "ensure the entry has write permissions" with "ensure the job has write permissions"
   - Replace "Test the entry command" with "Test the job command"
   - Replace "backup task is scheduled" with "backup job is scheduled"
