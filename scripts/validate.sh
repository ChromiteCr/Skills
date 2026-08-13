#!/usr/bin/env sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

python3 - "$repo_root" <<'PY'
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
errors = []
warnings = []

SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
STATUSES = {"draft", "beta", "stable", "deprecated"}
PRIORITIES = {"P0", "P1", "P2", "P3"}
REQUIRED_KEYS = [
    "name",
    "description",
    "category",
    "version",
    "status",
    "priority",
    "compatible_agents",
]

# ---------------------------------------------------------------- layout

required_paths = [
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    "README.md",
    "CONTRIBUTING.md",
    "VERSIONING.md",
    "SKILL_INDEX.md",
    "agents",
    "hooks",
    "scripts",
    "skills",
    "templates",
    "templates/skill-template.md",
    "templates/handoff-template.md",
    "templates/edit-plan-template.md",
    "templates/project-brief-template.md",
    "templates/release-note-template.md",
    "tests/cases",
    "tests/fixtures",
]
missing = [p for p in required_paths if not (root / p).exists()]
if missing:
    errors.append("Missing required paths: " + ", ".join(missing))

if (root / ".claude-plugin" / "skills").exists() or (root / ".claude-plugin" / "agents").exists():
    errors.append(".claude-plugin/ must contain manifests only, not component folders")


def fail_now():
    for e in errors:
        print("ERROR: " + e)
    raise SystemExit(1)


if errors:
    fail_now()

# ---------------------------------------------------------------- manifests

plugin = json.loads((root / ".claude-plugin" / "plugin.json").read_text())
marketplace = json.loads((root / ".claude-plugin" / "marketplace.json").read_text())

library_version = plugin.get("version")
if not library_version or not SEMVER.match(str(library_version)):
    errors.append("plugin.json needs a semver 'version' (the Library Version)")

if plugin.get("name") != "skills-library":
    errors.append("plugin.json name must match the marketplace entry ('skills-library')")

entries = marketplace.get("plugins", [])
if len(entries) != 1 or entries[0].get("name") != plugin.get("name"):
    errors.append("marketplace.json must contain exactly the one plugin entry")
else:
    entry = entries[0]
    if entry.get("source") != "./":
        errors.append("plugin source must be the repository root ('./')")
    if entry.get("version") != library_version:
        errors.append(
            "marketplace.json version (%r) must match plugin.json version (%r)"
            % (entry.get("version"), library_version)
        )

# ---------------------------------------------------------------- frontmatter

def parse_frontmatter(text, where):
    """Minimal flat-YAML frontmatter parser: scalars and '- ' lists."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        errors.append("%s: missing '---' YAML frontmatter at the top of the file" % where)
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        errors.append("%s: frontmatter is not closed with '---'" % where)
        return None

    data = {}
    key = None
    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.lstrip().startswith("- "):
            if key is None:
                errors.append("%s: list item outside of any key in frontmatter" % where)
                continue
            data.setdefault(key, [])
            if not isinstance(data[key], list):
                data[key] = []
            data[key].append(raw.lstrip()[2:].strip())
            continue
        if ":" not in raw:
            errors.append("%s: unparsable frontmatter line: %r" % (where, raw))
            continue
        key, _, value = raw.partition(":")
        key = key.strip()
        value = value.strip()
        data[key] = value if value else []
    return data


# ---------------------------------------------------------------- skills

skill_files = sorted((root / "skills").rglob("SKILL.md"))
index_text = (root / "SKILL_INDEX.md").read_text()
readme_text = (root / "README.md").read_text()
seen_names = {}

for path in skill_files:
    rel = path.relative_to(root)
    parts = path.relative_to(root / "skills").parts[:-1]
    if len(parts) == 1:
        category_dir, skill_dir = None, parts[0]
    elif len(parts) == 2:
        category_dir, skill_dir = parts
    else:
        errors.append(
            "%s: skills must live at skills/<category>/<skill-name>/SKILL.md" % rel
        )
        continue

    if not KEBAB.match(skill_dir):
        errors.append("%s: directory name %r must be lowercase kebab-case" % (rel, skill_dir))
    if category_dir and not KEBAB.match(category_dir):
        errors.append("%s: category dir %r must be lowercase kebab-case" % (rel, category_dir))

    meta = parse_frontmatter(path.read_text(), str(rel))
    if meta is None:
        continue

    for k in REQUIRED_KEYS:
        if k not in meta or meta[k] in ("", []):
            errors.append("%s: frontmatter missing required key %r" % (rel, k))

    name = meta.get("name")
    if isinstance(name, str) and name:
        if name != skill_dir:
            errors.append("%s: name %r must equal directory name %r" % (rel, name, skill_dir))
        if name in seen_names:
            errors.append("%s: duplicate skill name %r (also %s)" % (rel, name, seen_names[name]))
        seen_names[name] = str(rel)

        case = root / "tests" / "cases" / ("%s.md" % name)
        if not case.exists():
            errors.append("%s: missing test case tests/cases/%s.md" % (rel, name))
        elif not case.read_text().strip():
            errors.append("tests/cases/%s.md is empty" % name)

        token = "`%s`" % name
        if token not in index_text:
            errors.append("%s: not registered in SKILL_INDEX.md (expected %s)" % (rel, token))
        if token not in readme_text:
            errors.append("%s: not listed in README.md (expected %s)" % (rel, token))

    category = meta.get("category")
    if isinstance(category, str) and category and category_dir:
        if category.split("/")[0] != category_dir:
            errors.append(
                "%s: category %r must start with its directory %r" % (rel, category, category_dir)
            )

    version = meta.get("version")
    if isinstance(version, str) and version and not SEMVER.match(version):
        errors.append("%s: version %r is not semver" % (rel, version))

    status = meta.get("status")
    if isinstance(status, str) and status:
        if status not in STATUSES:
            errors.append("%s: status %r must be one of %s" % (rel, status, sorted(STATUSES)))
        elif isinstance(version, str) and SEMVER.match(version or ""):
            major = int(version.split(".")[0])
            if status == "stable" and major < 1:
                errors.append("%s: status 'stable' requires version >= 1.0.0" % rel)
            if status == "draft" and major >= 1:
                errors.append("%s: version >= 1.0.0 cannot have status 'draft'" % rel)

    priority = meta.get("priority")
    if isinstance(priority, str) and priority and priority not in PRIORITIES:
        errors.append("%s: priority %r must be one of %s" % (rel, priority, sorted(PRIORITIES)))

    agents = meta.get("compatible_agents")
    if agents is not None and not isinstance(agents, list):
        errors.append("%s: compatible_agents must be a YAML list" % rel)

    description = meta.get("description")
    if isinstance(description, str) and description:
        if len(description) < 20:
            warnings.append("%s: description is very short; say when to use the skill" % rel)
        if len(description) > 1024:
            errors.append("%s: description exceeds 1024 characters" % rel)

# stray files directly under skills/
for child in sorted((root / "skills").iterdir()):
    if child.is_file() and child.name not in {".gitkeep", "README.md"}:
        warnings.append("skills/%s: unexpected loose file" % child.name)

# ---------------------------------------------------------------- index

m = re.search(r"Library Version:\s*`([^`]+)`", index_text)
if not m:
    warnings.append("SKILL_INDEX.md has no 'Library Version: `x.y.z`' line")
elif m.group(1) != library_version:
    errors.append(
        "SKILL_INDEX.md Library Version (%s) does not match plugin.json (%s)"
        % (m.group(1), library_version)
    )

# 反向检查：索引里状态不是 planned 的行，必须真有对应的 skill 目录。
# 删掉一个 skill 却忘了删索引行，靠正向检查抓不到。
for row in re.finditer(r"^\|\s*`([a-z0-9-]+)`\s*\|[^|]*\|\s*([a-z]+)\s*\|", index_text, re.M):
    row_name, row_status = row.group(1), row.group(2)
    if row_status != "planned" and row_name not in seen_names:
        errors.append(
            "SKILL_INDEX.md lists %r as %s but skills/**/%s/SKILL.md does not exist"
            % (row_name, row_status, row_name)
        )

# ---------------------------------------------------------------- report

for w in warnings:
    print("WARN:  " + w)
if errors:
    fail_now()

print(
    "OK: layout, manifests and %d skill(s) valid. Library Version %s."
    % (len(skill_files), library_version)
)
PY
