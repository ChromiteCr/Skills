#!/usr/bin/env python3
"""Validate the basic structure of a generated task brief.

Usage:
    python3 check_brief.py path/to/brief.md
"""

from __future__ import annotations

import re
import sys
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


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 check_brief.py <brief.md>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8")
    missing = [heading for heading in REQUIRED_HEADINGS if heading not in text]
    if missing:
        print("ERROR: missing required headings:")
        for heading in missing:
            print(f"- {heading}")
        return 1

    sections = split_sections(text)

    empty_sections = []
    for heading in REQUIRED_HEADINGS:
        body = sections.get(heading, "").strip()
        body = re.sub(r"^[\-\*]\s*$", "", body, flags=re.MULTILINE).strip()
        if not body:
            empty_sections.append(heading)

    if empty_sections:
        print("ERROR: empty sections:")
        for heading in empty_sections:
            print(f"- {heading}")
        return 1

    acceptance = sections.get("## Acceptance Criteria", "")
    if "-" not in acceptance and "1." not in acceptance:
        print("ERROR: acceptance criteria should contain at least one list item")
        return 1

    open_questions = sections.get("## Open Questions / Assumptions", "")
    if not re.search(r"Unknown|Assumption:|Needs user confirmation", open_questions):
        print(
            "WARN: open questions section does not explicitly label uncertainty "
            "with 'Unknown', 'Assumption:' or 'Needs user confirmation'"
        )

    print("OK: brief structure looks valid")
    return 0


def split_sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"^## .+$", text, flags=re.MULTILINE))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(0)] = text[start:end]
    return sections


if __name__ == "__main__":
    raise SystemExit(main())
