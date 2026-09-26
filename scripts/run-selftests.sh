#!/usr/bin/env sh
# 跑每个支持 --selftest 的脚本（skills/**/scripts/*.py）。同一份共享副本只跑一次。
#
# 用法：./scripts/run-selftests.sh [skill-name | category | _shared ...]
#   不带参数   全部
#   带参数     只跑路径里含这些名字的脚本
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

python3 - "$repo_root" "$@" <<'PY'
import hashlib
import pathlib
import subprocess
import sys
import time

root = pathlib.Path(sys.argv[1])
wanted = set(sys.argv[2:])

scripts = []
seen = {}
for path in sorted((root / "skills").glob("**/scripts/*.py")):
    if "__pycache__" in path.parts:
        continue
    rel = path.relative_to(root)
    if wanted and not wanted & set(rel.parts):
        continue
    if "--selftest" not in path.read_text(encoding="utf-8", errors="replace"):
        continue
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest in seen:
        continue  # identical shared copy already queued
    seen[digest] = rel
    scripts.append(path)

failed = 0
for path in scripts:
    rel = path.relative_to(root)
    start = time.time()
    try:
        proc = subprocess.run([sys.executable, str(path), "--selftest"], cwd=path.parent,
                              capture_output=True, text=True, timeout=600)
        ok, out = proc.returncode == 0, (proc.stdout + proc.stderr)
    except subprocess.TimeoutExpired:
        ok, out = False, "timed out after 600 s"
    print("%s  %-75s %5.1fs" % ("PASS" if ok else "FAIL", rel, time.time() - start))
    if not ok:
        failed += 1
        for line in out.strip().splitlines()[-15:]:
            print("      " + line)

print("%d/%d self-tests passed" % (len(scripts) - failed, len(scripts)))
raise SystemExit(1 if failed else 0)
PY
