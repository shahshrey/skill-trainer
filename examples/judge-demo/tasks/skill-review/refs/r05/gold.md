## Skill Review: api-client

### Summary
Three defects were planted: a vague description lacking specifics, a mismatch between the directory name and frontmatter name, and an options list without a stated default.

### Planted defects (must all be found)
1. **desc-vague** — frontmatter description: The description "Helps with APIs and code generation." is generic and unspecific; it does not convey what the skill actually does (generate typed HTTP clients from OpenAPI specs) or when to use it, making it unclear whether this skill is relevant for a given task.
2. **dir-name-mismatch** — SKILL.md frontmatter vs directory path: The frontmatter declares `name: api-http-client` while the directory is named `api-client`; the name must match the directory name so they stay in sync.
3. **options-no-default** — SKILL.md Configuration section, HTTP library choice: The text lists "use requests, httpx, or aiohttp" without stating which is the default; readers need to know which library to expect if they don't specify a preference.

### What is clean (a good review does NOT flag these)
- The body's overview states when the skill applies (consuming a REST API with generated bindings)
- Overview and quick-start sections provide actionable guidance
- Code example demonstrates realistic usage
- All linked files exist and paths use forward slashes

### Expected recommendations
1. Replace the description with a specific one:
```yaml
description: Generates a fully typed Python HTTP client from an OpenAPI 3.0+ specification, with request validation and response parsing. Use when you need production-ready bindings to consume a REST API.
```
2. Rename the directory from `api-client` to `api-http-client` to match the frontmatter `name` field.
3. Add a default to the HTTP library choice in the Configuration section:
```
- `http_library`: Client library to use; options are "requests" (default), "httpx", or "aiohttp"
```
