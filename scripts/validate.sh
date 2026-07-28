#!/usr/bin/env sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

python3 - "$repo_root" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
required = [
    root / ".claude-plugin" / "plugin.json",
    root / ".claude-plugin" / "marketplace.json",
    root / "agents",
    root / "hooks",
    root / "scripts",
    root / "skills",
    root / "tests" / "cases",
    root / "tests" / "fixtures",
]

missing = [str(path.relative_to(root)) for path in required if not path.exists()]
if missing:
    raise SystemExit("Missing required paths: " + ", ".join(missing))

plugin = json.loads((root / ".claude-plugin" / "plugin.json").read_text())
marketplace = json.loads((root / ".claude-plugin" / "marketplace.json").read_text())

if plugin.get("name") != "skills-library":
    raise SystemExit("plugin.json name must match the initial marketplace entry")
plugins = marketplace.get("plugins", [])
if len(plugins) != 1 or plugins[0].get("name") != plugin["name"]:
    raise SystemExit("marketplace.json must contain the initial plugin entry")
if plugins[0].get("source") != "./":
    raise SystemExit("initial plugin source must be the repository root")

skills = list((root / "skills").glob("*/SKILL.md"))
if skills:
    raise SystemExit("This starter must not contain Skills yet: " + ", ".join(map(str, skills)))

print("Repository manifests and empty starter layout are valid.")
PY
