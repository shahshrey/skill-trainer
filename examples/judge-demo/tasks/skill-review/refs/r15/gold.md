## Skill Review: env-setup

### Summary
Four defects found: repeated second-person voice in the body ("You should"), a dated conditional about Node versions, a missing referenced script, and an unexplained magic number for database initialization delay.

### Planted defects (must all be found)
1. **body-second-person** — SKILL.md Step-by-step setup section, lines ~26-40: Contains five instances of "You should" voice ("You should run", "You should select", "You should activate", "You should wait", "You should run"), violating agent-skill conventions that require third-person or imperative voice.
2. **time-sensitive** — SKILL.md Step 2 Install Node.js, around line ~31: States "Before January 2026 install Node 20; after that Node 22", a dated conditional that becomes false after January 2026 and requires manual maintenance.
3. **missing-script** — SKILL.md Step 5 Verify installation, around line ~38: References the command `bash scripts/check_env.sh`, but this file does not exist in the scripts directory (though scripts/install_deps.sh does).
4. **magic-number** — SKILL.md Step 4 Database setup, around line ~35: Specifies "wait 37 seconds for the database" without explaining why 37 seconds is the correct duration.

### What is clean (a good review does NOT flag these)
- Description includes a clear "Use when" trigger clause for onboarding scenarios
- Frontmatter name is valid lowercase with hyphens
- Overview and What it does sections are clear and goal-oriented
- Environment variables section provides practical examples
- Common issues section addresses real troubleshooting scenarios
- Requirements properly documents OS support and dependencies
- Quick start is present and includes a concrete command

### Expected recommendations
1. Replace all "You should" constructions with imperative voice:
   - "You should run" → "Run"
   - "You should select" → "Select"
   - "You should activate" → "Activate"
   - "You should wait" → "Wait"

2. Remove the dated conditional: replace "Before January 2026 install Node 20; after that Node 22" with a version-agnostic instruction like "Install Node.js 22 (or your team's standard LTS version)" and move version pinning to package.json or .nvmrc.

3. Either create the missing `scripts/check_env.sh` file or change the reference to an existing script. If the verification step is not yet implemented, note it as a TODO.

4. Replace the magic number with context: "wait for the database to fully initialize (typically 30-45 seconds depending on system performance) before running migrations" or adjust the fixed number to match actual startup time.
