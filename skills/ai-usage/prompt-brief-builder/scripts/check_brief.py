#!/usr/bin/env python3
"""Validate the basic structure of a generated task brief.

Usage:
    python3 check_brief.py path/to/brief.md
    python3 check_brief.py --selftest

The nine `##` headings and the three uncertainty labels are matched literally
and stay in English, as in SKILL.md "Output template"; the text under them can
be in any language.

A section counts as empty when it holds nothing but blank lines, template
placeholders (`...`, `- ...`, `...instruction text...`) and labels with no value
(`- Artifact:`). A label followed by indented sub-items counts as filled.

Exit codes: 0 = structure valid (warnings may remain); 1 = missing or empty
sections, or no acceptance criterion; 2 = the file cannot be read, or bad
arguments.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REQUIRED_HEADINGS = [
    "## Objective",
    "## Deliverable",
    "## Audience",
    "## Available Inputs",
    "## Constraints",
    "## Acceptance Criteria",
    "## Non-Goals",
    "## Open Questions / Assumptions",
    "## Suggested Execution Prompt",
]
UNCERTAINTY_RE = re.compile(r"Unknown|Assumption:|Needs user confirmation")
CHINESE_UNCERTAINTY_RE = re.compile(r"未知|假设[:：]|待(?:用户|使用者)?确认")
HEADING_RE = re.compile(r"^##[ \t]+(\S.*?)\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")
LABEL_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+([^:：]{1,60}?)\s*[:：]\s*(.*)$")


class InputError(Exception):
    """The brief cannot be read (exit code 2)."""


def heading_key(title: str) -> str:
    """'Open Questions/ Assumptions ' -> 'open questions / assumptions'."""
    title = re.sub(r"\s*/\s*", " / ", title.strip())
    return re.sub(r"\s+", " ", title).lower()


REQUIRED_KEYS = {heading_key(h[3:]): h for h in REQUIRED_HEADINGS}


def is_placeholder(text: str) -> bool:
    """True for template filler: '', '...', '…', '<objective>', '...instruction text...'."""
    text = text.strip()
    if not text or re.fullmatch(r"(\.\.\.|…)+", text) or re.fullmatch(r"<[^<>]*>", text):
        return True
    return bool(re.match(r"^(\.\.\.|…)", text) and re.search(r"(\.\.\.|…)$", text))


def split_sections(text: str) -> tuple[dict[str, list[str]], list[str], list[str]]:
    """Map each required heading to its body lines. Also return duplicates and other '##' headings."""
    sections: dict[str, list[str]] = {}
    duplicates: list[str] = []
    others: list[str] = []
    current: list[str] | None = None
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
        m = None if in_fence else HEADING_RE.match(line)
        if m:
            canonical = REQUIRED_KEYS.get(heading_key(m.group(1)))
            if canonical is None:
                others.append(line.strip())
                current = None          # an unknown heading ends the previous section
            elif canonical in sections:
                duplicates.append(canonical)
                current = None
            else:
                current = sections.setdefault(canonical, [])
            continue
        if current is not None:
            current.append(line)
    return sections, duplicates, others


def analyse_body(lines: list[str]) -> tuple[bool, list[str]]:
    """(has_content, empty_labels) for one section body."""
    has_content = False
    empty_labels: list[str] = []
    in_fence = False
    for index, line in enumerate(lines):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not line.strip():
            continue
        if in_fence:
            has_content = True
            continue
        label = LABEL_RE.match(line)
        if label and not label.group(2).strip():
            indent = len(line) - len(line.lstrip())
            children = False
            for nxt in lines[index + 1:]:
                if not nxt.strip():
                    continue
                if len(nxt) - len(nxt.lstrip()) <= indent:
                    break
                child = LIST_ITEM_RE.match(nxt)
                child_text = child.group(1) if child else nxt
                if not is_placeholder(child_text) and not (LABEL_RE.match(nxt) and not LABEL_RE.match(nxt).group(2).strip()):
                    children = True
                    break
            if not children:
                empty_labels.append(label.group(1).strip())
            continue
        item = LIST_ITEM_RE.match(line)
        text = item.group(1) if item else line
        if label and is_placeholder(label.group(2)):
            empty_labels.append(label.group(1).strip())
            continue
        if not is_placeholder(text):
            has_content = True
    return has_content, empty_labels


def check_text(text: str) -> tuple[int, list[str]]:
    """Validate a brief. Returns (exit code, output lines)."""
    out: list[str] = []
    sections, duplicates, others = split_sections(text)
    missing = [h for h in REQUIRED_HEADINGS if h not in sections]
    if missing:
        out.append("ERROR: missing required headings:")
        out.extend(f"- {h}" for h in missing)
        foreign = [h for h in others if re.search(r"[一-鿿]", h)]
        if foreign:
            out.append("HINT: the nine headings stay in English exactly as in SKILL.md 'Output template'; "
                       "write the content under them in any language. Found: " + ", ".join(foreign[:9]))
        return 1, out

    for h in duplicates:
        out.append(f"WARN: {h} appears more than once; only the first one is checked")

    empty: list[str] = []
    partial: list[tuple[str, list[str]]] = []
    for heading in REQUIRED_HEADINGS:
        has_content, empty_labels = analyse_body(sections[heading])
        if not has_content:
            empty.append(heading)
        elif empty_labels:
            partial.append((heading, empty_labels))
    if empty:
        out.append("ERROR: empty sections (only blank lines, placeholders or labels with no value):")
        out.extend(f"- {h}" for h in empty)
        return 1, out

    acceptance = sections["## Acceptance Criteria"]
    items = [LIST_ITEM_RE.match(line) for line in acceptance]
    if not any(m and not is_placeholder(m.group(1)) for m in items):
        out.append("ERROR: acceptance criteria should contain at least one list item")
        return 1, out

    for heading, labels in partial:
        out.append(f"WARN: {heading} has labels with no value: {', '.join(labels)}")

    open_questions = "\n".join(sections["## Open Questions / Assumptions"])
    if not UNCERTAINTY_RE.search(open_questions):
        hint = ""
        found = CHINESE_UNCERTAINTY_RE.search(open_questions)
        if found:
            hint = f" (found '{found.group(0)}'; the labels stay in English like the headings)"
        out.append("WARN: open questions section does not explicitly label uncertainty with 'Unknown', "
                   "'Assumption:' or 'Needs user confirmation'" + hint)

    out.append("OK: brief structure looks valid")
    return 0, out


def read_brief(path: Path) -> str:
    if path.is_dir():
        raise InputError(f"{path} is a directory; pass the brief's .md file")
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise InputError(f"file not found: {path}") from None
    except UnicodeDecodeError:
        raise InputError(f"{path} is not UTF-8 text") from None
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror or exc}") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_brief.py",
        description="Check that a task brief has the nine required headings (in English), that none of them "
                    "is empty or placeholder-only, that there is at least one acceptance criterion, and that "
                    "uncertainty is labelled.",
        epilog="Exit codes: 0 valid (warnings may remain), 1 structural problems, 2 unreadable file or bad arguments.",
    )
    parser.add_argument("brief", nargs="?", help="path to the brief (.md)")
    parser.add_argument("--selftest", action="store_true", help="run the built-in regression cases and exit")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.brief:
        parser.print_usage(sys.stderr)
        print("ERROR: pass the brief file (or --selftest)", file=sys.stderr)
        return 2
    try:
        text = read_brief(Path(args.brief))
    except InputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    code, lines = check_text(text)
    print("\n".join(lines))
    return code


# ----------------------------------------------------------------- selftest

SKILL_TEMPLATE = """# Task Brief

## Objective
- ...

## Deliverable
- Artifact:
- Format:
- Depth / length:

## Audience
- Primary audience:
- Secondary audience:
- What they already know:

## Available Inputs
- ...

## Constraints
- Must include:
- Must avoid:
- Time / deadline:
- Tool / environment limits:

## Acceptance Criteria
- ...

## Non-Goals
- ...

## Open Questions / Assumptions
- ...

## Suggested Execution Prompt
...one portable prompt or instruction block that another agent/human could use directly...
"""

FILLED = """# Task Brief

## Objective
- Write a 150-word introduction of the team's project for the weekly report

## Deliverable
- Artifact: one paragraph of Chinese text
- Format: plain text
- Depth / length: 120-180 characters

## Audience
- Primary audience: colleagues outside the project
- Secondary audience: the department head
- What they already know: that the team builds internal tools

## Available Inputs
- three feature notes supplied by the user

## Constraints
- Must include: project name, the problem it solves, current stage
- Must avoid: internal code names
- Time / deadline: Friday
- Tool / environment limits: none

## Acceptance Criteria
- 120-180 characters
- a reader outside the project can say what problem it solves

## Non-Goals
- no implementation details

## Open Questions / Assumptions
- Assumption: no English version is needed
- Needs user confirmation: call the stage "internal beta" or "pilot"

## Suggested Execution Prompt
Using the brief above, write one paragraph of 120-180 Chinese characters introducing the project.
"""


def selftest() -> int:
    results: list[tuple[str, bool, str]] = []

    def expect(name: str, text: str, code: int, *needles: str, absent: tuple[str, ...] = ()) -> None:
        got, lines = check_text(text)
        out = "\n".join(lines)
        ok = got == code and all(n in out for n in needles) and not any(a in out for a in absent)
        results.append((name, ok, f"exit {got}\n{out}"))

    all_nine = tuple(f"- {h}" for h in REQUIRED_HEADINGS)
    expect("SKILL.md output template as-is must fail with all nine sections empty", SKILL_TEMPLATE, 1, *all_nine)
    skill_md = Path(__file__).resolve().parent.parent / "SKILL.md"
    if skill_md.is_file():
        block = re.search(r"```md\n(.*?)```", skill_md.read_text(encoding="utf-8"), re.S)
        expect("the template printed in SKILL.md itself fails", block.group(1) if block else "", 1, *all_nine)
    template_file = Path(__file__).resolve().parent.parent / "templates" / "brief-template.md"
    if template_file.is_file():
        expect("templates/brief-template.md fails, Deliverable/Audience/Constraints included",
               template_file.read_text(encoding="utf-8"), 1, *all_nine)

    labels_only = FILLED
    for filled_block, empty_block in (
        ("- Artifact: one paragraph of Chinese text\n- Format: plain text\n- Depth / length: 120-180 characters",
         "- Artifact:\n- Format:\n- Depth / length:"),
        ("- Primary audience: colleagues outside the project\n- Secondary audience: the department head\n"
         "- What they already know: that the team builds internal tools",
         "- Primary audience:\n- Secondary audience:\n- What they already know:"),
        ("- Must include: project name, the problem it solves, current stage\n- Must avoid: internal code names\n"
         "- Time / deadline: Friday\n- Tool / environment limits: none",
         "- Must include:\n- Must avoid:\n- Time / deadline:\n- Tool / environment limits:"),
    ):
        labels_only = labels_only.replace(filled_block, empty_block)
    expect("sections holding only empty labels are reported as empty", labels_only, 1,
           "- ## Deliverable", "- ## Audience", "- ## Constraints", absent=("- ## Objective",))
    expect("trailing space after a heading does not empty the section",
           FILLED.replace("## Objective\n", "## Objective \n"), 0, "OK:")
    expect("'### Objective' is not '## Objective' (no substring match)",
           FILLED.replace("## Objective\n", "### Objective\n"), 1, "- ## Objective")
    zh = FILLED
    for en, cn in (("## Objective", "## 目标"), ("## Deliverable", "## 产物"), ("## Audience", "## 受众")):
        zh = zh.replace(en, cn)
    expect("Chinese headings: missing headings plus the stay-in-English hint", zh, 1,
           "- ## Objective", "stay in English", "## 目标")
    expect("a fully filled brief passes without warnings", FILLED, 0, "OK:", absent=("WARN",))
    expect("a label with indented sub-items counts as filled",
           FILLED.replace("- Must include: project name, the problem it solves, current stage",
                          "- Must include:\n  - project name\n  - the problem it solves"), 0, "OK:",
           absent=("Must include",))
    expect("acceptance criteria as a paragraph with a hyphen is not a list item",
           FILLED.replace("- 120-180 characters\n- a reader outside the project can say what problem it solves",
                          "Should read well in real-time chat."), 1, "at least one list item")
    expect("Chinese uncertainty label is flagged with a hint",
           FILLED.replace("- Assumption: no English version is needed\n"
                          "- Needs user confirmation: call the stage \"internal beta\" or \"pilot\"",
                          "- 假设：不需要英文版"), 0, "found '假设：'")
    expect("a '##' line inside a fenced block in the prompt is not a heading",
           FILLED.replace("Using the brief above", "```\n## Objective\n```\nUsing the brief above"), 0, "OK:",
           absent=("appears more than once",))
    expect("some labels empty, others filled: warning, still valid",
           FILLED.replace("- Format: plain text", "- Format:"), 0, "WARN: ## Deliverable has labels with no value: Format")

    with tempfile.TemporaryDirectory() as tmp:
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            codes = (main([tmp]), main([os.path.join(tmp, "missing.md")]))
        results.append(("directory / missing file: exit 2 without traceback",
                        codes == (2, 2) and "Traceback" not in sink.getvalue(), f"{codes} {sink.getvalue()}"))
    proc = subprocess.run([sys.executable, os.path.abspath(__file__), "--help"], capture_output=True, text=True)
    results.append(("--help prints usage and exits 0", proc.returncode == 0 and "usage:" in proc.stdout,
                    proc.stdout + proc.stderr))

    failed = [r for r in results if not r[1]]
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else "\n      " + detail.replace("\n", "\n      ")))
    print(f"selftest: {len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
