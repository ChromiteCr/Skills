#!/usr/bin/env sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

python3 - "$repo_root" <<'PY'
import hashlib
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
CJK = re.compile("[\u4e00-\u9fff]")
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

# ---------------------------------------------------------------- plugin skills paths
# Claude Code 只扫 skills/ 的直接子目录，不往下递归；本库的技能在 skills/<分类>/<技能>/。
# 所以 plugin.json 的 "skills" 必须列出每个含 */SKILL.md 的分类目录，漏一个，那个分类整个不加载。
# 写成 "./skills" 不起作用：它等于默认目录，会被加载器过滤掉。

declared = plugin.get("skills", [])
if isinstance(declared, str):
    declared = [declared]
if not isinstance(declared, list):
    errors.append("plugin.json 'skills' must be a list of './skills/<category>' paths")
    declared = []
declared_norm = set()
for entry_path in declared:
    if not isinstance(entry_path, str) or not entry_path.startswith("./"):
        errors.append("plugin.json skills entry %r must start with './'" % (entry_path,))
        continue
    norm = entry_path.rstrip("/")
    if norm == "./skills":
        errors.append("plugin.json skills entry './skills' is the default folder and is ignored; list the category folders")
        continue
    target = root / norm[2:]
    if not target.is_dir():
        errors.append("plugin.json skills entry %r does not exist" % entry_path)
    elif not list(target.glob("*/SKILL.md")) and not (target / "SKILL.md").exists():
        warnings.append("plugin.json skills entry %r contains no skill" % entry_path)
    declared_norm.add(norm)
for category_dir in sorted({p.parent.parent.name for p in (root / "skills").glob("*/*/SKILL.md")}):
    if "./skills/%s" % category_dir not in declared_norm:
        errors.append(
            "plugin.json 'skills' does not list ./skills/%s, so none of its skills load in Claude Code"
            % category_dir
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
        if raw[0] in " \t" and not raw.lstrip().startswith("- "):
            # 缩进的键在 YAML 里属于上一个键，这个简化解析器会把它当成顶层键，所以直接报错
            errors.append("%s: indented frontmatter key %r (keys must start at column 0)" % (where, raw.strip()))
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
metas = {}

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
        metas[name] = meta

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
        if not CJK.search(description):
            errors.append(
                "%s: description has no Chinese trigger phrase; lead with 2-4 phrases a user would actually say" % rel
            )

    license_key = meta.get("license")
    if license_key not in (None, "", []) and license_key != plugin.get("license"):
        errors.append(
            "%s: frontmatter license %r conflicts with plugin.json license %r; remove the key"
            % (rel, license_key, plugin.get("license"))
        )

# stray files directly under skills/
for child in sorted((root / "skills").iterdir()):
    if child.is_file() and child.name not in {".gitkeep", "README.md"}:
        warnings.append("skills/%s: unexpected loose file" % child.name)

# SKILL.md outside skills/ is never loaded (0.19.0 once left seven skills at the repo root)
for path in sorted(root.rglob("SKILL.md")):
    rel = path.relative_to(root)
    if rel.parts[0] in {"skills", "dist", ".git", ".claude", "node_modules"}:
        continue
    errors.append("%s: SKILL.md outside skills/ is not loaded; move it to skills/<category>/<skill>/" % rel)

# test cases live in tests/cases/<skill>.md only; a second copy inside the skill drifts
for path in sorted((root / "skills").glob("*/*/tests")):
    errors.append(
        "%s: test cases belong in tests/cases/%s.md, not inside the skill directory"
        % (path.relative_to(root), path.parent.name)
    )

# relative references to shared files and sibling skills must resolve
REL_REF = re.compile(r"(?<![A-Za-z0-9_.-])((?:\.\./)+)([A-Za-z0-9_-][A-Za-z0-9_./-]*[A-Za-z0-9_-])")
skill_names = set(seen_names)
category_names = {p.name for p in (root / "skills").iterdir() if p.is_dir()}
for path in sorted((root / "skills").glob("*/*/**/*.md")):
    rel = path.relative_to(root)
    text = path.read_text(encoding="utf-8")
    for m in REL_REF.finditer(text):
        first = m.group(2).split("/")[0]
        if first != "_shared" and first not in skill_names and first not in category_names:
            continue  # example paths in prose, not library references
        base = path.parent
        for _ in range(m.group(1).count("../")):
            base = base.parent
        if not (base / m.group(2)).exists():
            errors.append("%s: reference %s does not exist" % (rel, m.group(0)))

# shared code is copied into every skill that uses it; the copies must stay identical
SHARED_MARK = "scripts/validate.sh checks that all copies have the same sha256"
copies = {}
for path in sorted((root / "skills").glob("*/*/scripts/*")):
    if path.is_file() and path.suffix in {".py", ".sh", ".js"}:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SHARED_MARK in text:
            copies.setdefault(path.name, []).append(path)
for file_name, paths in sorted(copies.items()):
    digests = {}
    for path in paths:
        digests.setdefault(hashlib.sha256(path.read_bytes()).hexdigest()[:12], []).append(
            str(path.relative_to(root))
        )
    if len(digests) > 1:
        detail = "; ".join("%s: %s" % (d, ", ".join(ps)) for d, ps in sorted(digests.items()))
        errors.append("shared copies of %s differ (edit one, then copy it to all): %s" % (file_name, detail))

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
# 正向逐列比对：优先级、状态、版本三列必须与 frontmatter 一致；建成的 skill 不能还写 planned。
INDEX_ROW = re.compile(r"^\|\s*`([a-z0-9-]+)`\s*\|\s*([^|]*?)\s*\|\s*([a-z]+)\s*\|\s*([^|]*?)\s*\|", re.M)
for row in INDEX_ROW.finditer(index_text):
    row_name, row_priority, row_status, row_version = row.groups()
    if row_status != "planned" and row_name not in seen_names:
        errors.append(
            "SKILL_INDEX.md lists %r as %s but skills/**/%s/SKILL.md does not exist"
            % (row_name, row_status, row_name)
        )
    meta = metas.get(row_name)
    if meta is None:
        continue
    if row_status == "planned":
        errors.append("SKILL_INDEX.md still lists %r as planned, but the skill exists" % row_name)
        continue
    for label, got, want in (
        ("priority", row_priority, meta.get("priority")),
        ("status", row_status, meta.get("status")),
        ("version", row_version, meta.get("version")),
    ):
        if got != want:
            errors.append(
                "SKILL_INDEX.md %s for %r is %r but SKILL.md frontmatter says %r" % (label, row_name, got, want)
            )

# README 徽章里的 skill 数
badge = re.search(r"badge/skills-(\d+)-", readme_text)
if badge and int(badge.group(1)) != len(seen_names):
    errors.append("README.md skills badge says %s but the library has %d skills" % (badge.group(1), len(seen_names)))

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

python3 "$repo_root/tests/test_latex_checker.py"
