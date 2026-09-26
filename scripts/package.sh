#!/usr/bin/env sh
# 把每个 skill 打成单独的 zip：dist/<skill>-<version>.zip，顶层目录是 <skill>/。
#
# 为什么需要：不少 SKILL.md 引用自己目录以外的文件：分类下的 _shared（../_shared/…、
# 裸写的 _shared/…、跨分类的 ../../physics/_shared/…），或兄弟 skill 的脚本
# （../lyric-doctor/scripts/…）。只打 skill 自己的目录，这些文件就丢了。
# 本脚本把被引用的文件一起放进 zip 的 <skill>/_shared/ 下（同分类的保持原相对位置，
# 跨分类的多一层分类名），并把 zip 里的引用路径改写成新位置。
# 插件安装不受影响：插件根就是仓库根，这些文件本来就在。
#
# 用法：./scripts/package.sh [--check] [skill-name ...]
#   不带名字   打包全部 skill
#   --check    不写文件，只报告 dist/ 里缺失或过期的 zip（退出码 1 表示有）
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

python3 - "$repo_root" "$@" <<'PY'
import hashlib
import io
import os
import pathlib
import re
import sys
import zipfile

root = pathlib.Path(sys.argv[1])
args = sys.argv[2:]
check_only = "--check" in args
wanted = [a for a in args if not a.startswith("--")]
skills_root = root / "skills"
dist = root / "dist"

TEXT_SUFFIXES = {".md", ".py", ".sh", ".txt", ".json", ".html", ".css", ".js", ".yaml", ".yml", ".csv", ".tex", ".svg"}
SKIP_NAMES = {".DS_Store"}
SKIP_DIRS = {"__pycache__", ".pytest_cache"}
FIXED_TIME = (2026, 1, 1, 0, 0, 0)  # 固定时间戳，同样的源文件得到同样的 zip

# ../x/y（相对当前文件）、skills/<cat>/_shared/x（相对仓库根）、行内裸写的 _shared/x（相对分类目录）
REL_REF = re.compile(r"(?<![A-Za-z0-9_.-])((?:\.\./)+)([A-Za-z0-9_-][A-Za-z0-9_./-]*[A-Za-z0-9_-])")
ROOT_REF = re.compile(r"skills/([a-z0-9-]+)/_shared/([A-Za-z0-9_./-]*[A-Za-z0-9_-])")
BARE_REF = re.compile(r"(?<![A-Za-z0-9_./-])_shared/([A-Za-z0-9_./-]*[A-Za-z0-9_-])")


def frontmatter_version(skill_md):
    lines = skill_md.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip()
    return None


def skill_files(skill_dir):
    for path in sorted(skill_dir.rglob("*")):
        if path.is_dir() or path.name in SKIP_NAMES or path.suffix == ".pyc":
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(skill_dir).parts):
            continue
        yield path


def build(skill_dir):
    """Return {arcname: bytes} for one skill, with referenced _shared files included."""
    name = skill_dir.name
    category = skill_dir.parent.name
    members = {}
    shared = {}  # source path -> arcname
    warnings = []

    def shared_arc(src):
        """skills/<cat>/_shared/x -> _shared/x；skills/<cat>/<other-skill>/x -> _shared/<other-skill>/x；
        别的分类前面再加一层分类名。"""
        parts = src.relative_to(skills_root).parts
        cat, rest = parts[0], list(parts[1:])
        if rest and rest[0] == "_shared":
            rest = rest[1:]
        sub = "/".join(rest if cat == category else [cat] + rest)
        return "%s/_shared/%s" % (name, sub)

    def register(src, where):
        src = pathlib.Path(src)
        if not src.is_file():
            warnings.append("%s: reference to missing file %s" % (where, src))
            return None
        arc = shared_arc(src)
        shared.setdefault(src, arc)
        return shared[src]

    def outside_skill(src):
        try:
            src.relative_to(skill_dir)
            return False
        except ValueError:
            pass
        try:
            src.relative_to(skills_root)
            return True
        except ValueError:
            return False

    def rewrite(text, src_file, arc_file):
        arc_dir = pathlib.PurePosixPath(arc_file).parent

        def rel_to(arc):
            target = pathlib.PurePosixPath(arc)
            ups = len(arc_dir.parts)
            common = 0
            for a, b in zip(arc_dir.parts, target.parts):
                if a != b:
                    break
                common += 1
            return "/".join([".."] * (ups - common) + list(target.parts[common:]))

        def rel_sub(m):
            ups, rest = m.group(1), m.group(2)
            base = src_file.parent
            for _ in range(ups.count("../")):
                base = base.parent
            src = pathlib.Path(os.path.normpath(base / rest))
            # 只处理指向本 skill 以外、skills/ 以内的真实文件；示例路径之类原样保留
            if not src.is_file() or not outside_skill(src):
                return m.group(0)
            arc = register(src, arc_file)
            return rel_to(arc) if arc else m.group(0)

        def root_sub(m):
            src = skills_root / m.group(1) / "_shared" / m.group(2)
            if not src.is_file():
                return m.group(0)
            arc = register(src, arc_file)
            return rel_to(arc) if arc else m.group(0)

        text = REL_REF.sub(rel_sub, text)
        text = ROOT_REF.sub(root_sub, text)
        # 裸写的 _shared/x 指本分类的 _shared；放进 zip 后从 skill 根目录读正好对得上，只需带上文件
        for m in BARE_REF.finditer(text):
            src = skill_dir.parent / "_shared" / m.group(1)
            if src.is_file():
                register(src, arc_file)
        return text

    for path in skill_files(skill_dir):
        arc = "%s/%s" % (name, path.relative_to(skill_dir).as_posix())
        data = path.read_bytes()
        if path.suffix in TEXT_SUFFIXES:
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                members[arc] = data
                continue
            data = rewrite(text, path, arc).encode("utf-8")
        members[arc] = data

    # 被引用的 _shared 文件本身也可能再引用别的 _shared 文件
    done = set()
    while True:
        todo = [s for s in shared if s not in done]
        if not todo:
            break
        for src in todo:
            done.add(src)
            arc = shared[src]
            data = src.read_bytes()
            if src.suffix in TEXT_SUFFIXES:
                data = rewrite(data.decode("utf-8"), src, arc).encode("utf-8")
            members[arc] = data
    return members, warnings


def zip_bytes(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        dirs = set()
        for arc in sorted(members):
            parts = arc.split("/")[:-1]
            for i in range(1, len(parts) + 1):
                d = "/".join(parts[:i]) + "/"
                if d not in dirs:
                    dirs.add(d)
                    zf.writestr(zipfile.ZipInfo(d, FIXED_TIME), b"")
            info = zipfile.ZipInfo(arc, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if arc.endswith((".py", ".sh")) else 0o644) << 16
            zf.writestr(info, members[arc])
    return buf.getvalue()


def digest(members):
    h = hashlib.sha256()
    for arc in sorted(members):
        h.update(arc.encode())
        h.update(hashlib.sha256(members[arc]).digest())
    return h.hexdigest()


def zip_digest(path):
    with zipfile.ZipFile(path) as zf:
        members = {i.filename: zf.read(i) for i in zf.infolist() if not i.filename.endswith("/")}
    return digest(members)


skill_dirs = sorted(p.parent for p in skills_root.glob("*/*/SKILL.md"))
if wanted:
    by_name = {d.name: d for d in skill_dirs}
    unknown = [w for w in wanted if w not in by_name]
    if unknown:
        print("ERROR: unknown skill(s): " + ", ".join(unknown))
        raise SystemExit(2)
    skill_dirs = [by_name[w] for w in wanted]

if not check_only:
    dist.mkdir(exist_ok=True)

problems = 0
for skill_dir in skill_dirs:
    name = skill_dir.name
    version = frontmatter_version(skill_dir / "SKILL.md")
    if not version:
        print("ERROR: %s: no version in frontmatter" % name)
        problems += 1
        continue
    members, warnings = build(skill_dir)
    for w in warnings:
        print("WARN:  " + w)
    target = dist / ("%s-%s.zip" % (name, version))
    shared_count = sum(1 for arc in members if "/_shared/" in arc)
    if check_only:
        if not target.exists():
            print("MISSING  %s" % target.relative_to(root))
            problems += 1
        elif zip_digest(target) != digest(members):
            print("STALE    %s" % target.relative_to(root))
            problems += 1
        continue
    target.write_bytes(zip_bytes(members))
    for old in list(dist.glob("%s.zip" % name)) + list(dist.glob("%s-*.zip" % name)):
        if old != target and re.fullmatch(re.escape(name) + r"(-\d+\.\d+\.\d+)?\.zip", old.name):
            old.unlink()
    print("%-40s %d files%s" % (target.relative_to(root), len(members),
                                "  (+%d shared)" % shared_count if shared_count else ""))

if check_only:
    print("dist/ is up to date." if not problems else "%d zip(s) missing or stale; run ./scripts/package.sh" % problems)
raise SystemExit(1 if problems else 0)
PY
