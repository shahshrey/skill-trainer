## Skill Review: docker-deploy

### Summary
Four defects were planted: user-facing documentation files are included in the skill directory, a paragraph explaining what container images are, second-person voice used repeatedly in the body, and use of jq and ssh binaries without documenting them as dependencies.

### Planted defects (must all be found)
1. **extraneous-files** — README.md and CHANGELOG.md in skill root: User-facing installation and changelog documentation should not be part of the skill package itself; these belong in project documentation outside the skill directory
2. **obvious-explanation** — SKILL.md Understanding Docker containers section lines 10-12: Entire paragraph explains what a Docker container image is, knowledge any developer already understands; wastes space that could be used for skill-specific guidance
3. **body-second-person** — SKILL.md Deployment workflow section lines 15, 17, 19: Uses "You should" voice in three consecutive sentences in the body text; must use third-person imperative or passive voice instead
4. **undocumented-binary** — SKILL.md Build configuration section line 29: Commands reference jq and ssh as required tools with no mention in the Prerequisites section or any documentation that these dependencies are required

### What is clean (a good review does NOT flag these)
- Frontmatter is properly formatted with name, description, and clear trigger clause
- Docker and SSH prerequisites listed with version requirements
- Deployment workflow section structure is logical
- Build configuration examples are realistic and complete
- Advanced options section provides clear guidance for multi-stage builds and private registries
- Error handling with deploy.log is documented

### Expected recommendations
1. Delete README.md and CHANGELOG.md from the skill directory; project documentation should live elsewhere
2. Remove the "Understanding Docker containers" section entirely; assume competent reader understanding
3. Replace second-person voice with imperative or passive voice. For example:
   - "You should start by..." → "Start by configuring your Dockerfile in the project root."
   - "you should prepare..." → "Prepare deployment credentials in environment variables..."
   - "you should run..." → "Run the deployment command to orchestrate..."
4. Add to Prerequisites section: `jq` (for JSON parsing) and `ssh` (for remote connectivity) are required and must be available in your PATH
