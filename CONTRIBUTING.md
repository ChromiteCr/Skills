# Contributing

This repository starts empty by design. Add components only when they solve a repeated, well-defined task.

## Adding a Skill

Create `skills/<skill-name>/SKILL.md`. Use lowercase kebab-case names. Keep the main file concise; place templates, references, and deterministic scripts beside it only when needed. Add a matching evaluation case under `tests/cases/` before asking for review.

## Adding an agent or integration

- Add specialized subagents to `agents/` as Markdown files with valid frontmatter.
- Add plugin-wide hooks to `hooks/hooks.json`; do not create broad automatic hooks without explicit review.
- Add MCP configuration at `.mcp.json` only when its authentication and user-configuration model are documented.
- Add LSP configuration at `.lsp.json` only for a concrete language-support need.

Run `./scripts/validate.sh` and load the plugin locally with `claude --plugin-dir "$(pwd)"` before publishing.
