# Skills Library

An extensible Claude Code plugin repository for reusable Skills, specialized subagents, Hooks, MCP integrations, output styles, and supporting scripts. It is intentionally initialized without any Skills or agents.

## Repository layout

```text
.
├── .claude-plugin/       # Plugin and Marketplace manifests
├── agents/               # Future specialized subagents
├── hooks/                # Future lifecycle hooks (`hooks.json`)
├── skills/               # Future `<skill-name>/SKILL.md` directories
├── scripts/              # Shared validation and deterministic utilities
└── tests/                # Fixtures and repeatable evaluation cases
```

Future MCP and LSP configurations belong at the plugin root as `.mcp.json` and `.lsp.json`. Do not put component folders inside `.claude-plugin/`; only the manifests belong there.

## Local validation

```sh
./scripts/validate.sh
claude --plugin-dir "$(pwd)"
```

The first command checks the repository manifests and ensures this starter contains no Skills yet. The second loads the repository as a local Claude Code plugin; use it to test each new component before publication.

## Future publishing

Before making the repository public, replace the placeholder Marketplace owner, choose a real license, and update the plugin name if necessary. Once hosted at GitHub, users can add the Marketplace with:

```text
/plugin marketplace add <GitHub-owner>/<repository>
/plugin install skills-library@skills-library
```

Each published Skill should have a narrow purpose, a clear `description`, documented safe boundaries, and at least one repeatable test case. Keep deterministic work in scripts; keep reference material next to the Skill and load it only when needed.

## Contribution safety rules

- Prefer Skills and subagents with least-privilege tool access.
- Keep Hooks opt-in, narrowly matched, and independently tested; hooks can execute automatically.
- Never commit credentials or private endpoints. Use plugin user configuration for user-specific values.
- Validate every change before release and test plugin installation from a clean Claude Code session.
