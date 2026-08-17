#!/usr/bin/env python3
"""Static checks for cross-references, citations, figures, and placeholders."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
FIGURE_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".eps", ".svg")
CITATION_COMMANDS = {
    "autocite",
    "autocites",
    "cite",
    "citealp",
    "citealt",
    "citeauthor",
    "citep",
    "citet",
    "cites",
    "citeyear",
    "citeyearpar",
    "footcite",
    "footcites",
    "footfullcite",
    "fullcite",
    "nocite",
    "parencite",
    "parencites",
    "smartcite",
    "smartcites",
    "supercite",
    "supercites",
    "textcite",
    "textcites",
}
PLURAL_CITATION_COMMANDS = {
    command for command in CITATION_COMMANDS if command.endswith("s")
}
CITATION_COMMAND_PATTERN = re.compile(
    r"\\(?P<command>"
    + "|".join(sorted(CITATION_COMMANDS, key=len, reverse=True))
    + r")\*?(?![A-Za-z@])"
)


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    path: str
    line: int
    message: str


@dataclass(frozen=True)
class Source:
    path: Path
    text: str
    clean_text: str


def strip_comments(text: str) -> str:
    cleaned_lines: list[str] = []
    for line in text.splitlines(keepends=True):
        content = line[:-1] if line.endswith("\n") else line
        cut_at = len(content)
        for index, character in enumerate(content):
            if character != "%":
                continue
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and content[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                cut_at = index
                break
        suffix = "\n" if line.endswith("\n") else ""
        cleaned_lines.append(content[:cut_at] + suffix)
    return "".join(cleaned_lines)


def line_number(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def display_path(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path)


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def add_finding(
    findings: list[Finding],
    severity: str,
    code: str,
    path: Path,
    line: int,
    message: str,
    base: Path,
) -> None:
    findings.append(
        Finding(severity, code, display_path(path, base), line, message)
    )


def load_sources(
    entry_paths: list[Path], base: Path, allowed_root: Path
) -> tuple[dict[Path, Source], list[Finding]]:
    sources: dict[Path, Source] = {}
    findings: list[Finding] = []

    def visit(path: Path, referring_path: Path | None = None, referring_line: int = 1) -> None:
        resolved = path.resolve()
        if resolved in sources:
            return
        if not is_within(resolved, allowed_root):
            add_finding(
                findings,
                "error",
                "path-outside-root",
                referring_path or path,
                referring_line,
                f"TeX input resolves outside allowed root {allowed_root}: {path}",
                base,
            )
            return
        if not resolved.is_file():
            location = referring_path or path
            add_finding(
                findings,
                "error",
                "missing-tex-input",
                location,
                referring_line,
                f"TeX source not found: {display_path(path, base)}",
                base,
            )
            return

        try:
            text = resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            add_finding(
                findings,
                "error",
                "unreadable-tex-source",
                resolved,
                1,
                f"Could not read TeX source as UTF-8: {error}",
                base,
            )
            return
        source = Source(resolved, text, strip_comments(text))
        sources[resolved] = source

        input_pattern = re.compile(r"\\(?:input|include)\s*\{([^{}]+)\}")
        for match in input_pattern.finditer(source.clean_text):
            raw_name = match.group(1).strip()
            if "\\" in raw_name or "#" in raw_name:
                add_finding(
                    findings,
                    "warning",
                    "dynamic-tex-input",
                    resolved,
                    line_number(source.clean_text, match.start()),
                    f"Dynamic TeX input could not be checked: {raw_name}",
                    base,
                )
                continue
            child = resolved.parent / raw_name
            if child.suffix == "":
                child = child.with_suffix(".tex")
            visit(child, resolved, line_number(source.clean_text, match.start()))

    for entry_path in entry_paths:
        visit(entry_path)
    return sources, findings


def resolve_with_extensions(
    candidates: list[Path], allowed_root: Path
) -> tuple[Path | None, bool]:
    escaped_root = False
    for candidate in candidates:
        resolved = candidate.resolve()
        if not is_within(resolved, allowed_root):
            escaped_root = True
            continue
        if resolved.is_file():
            return resolved, escaped_root
        if resolved.suffix == "":
            for extension in FIGURE_EXTENSIONS:
                extended = resolved.with_suffix(extension)
                if extended.is_file():
                    return extended, escaped_root
    return None, escaped_root


def citation_keys(text: str) -> list[tuple[str, int]]:
    citations: list[tuple[str, int]] = []
    for command_match in CITATION_COMMAND_PATTERN.finditer(text):
        command = command_match.group("command")
        cursor = command_match.end()
        while True:
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
            while cursor < len(text) and text[cursor] == "[":
                option_end = text.find("]", cursor + 1)
                if option_end < 0:
                    break
                cursor = option_end + 1
                while cursor < len(text) and text[cursor].isspace():
                    cursor += 1
            if cursor >= len(text) or text[cursor] != "{":
                break
            argument_end = text.find("}", cursor + 1)
            if argument_end < 0:
                break
            for key in text[cursor + 1 : argument_end].split(","):
                normalized = key.strip()
                if normalized and normalized != "*":
                    citations.append((normalized, command_match.start()))
            cursor = argument_end + 1
            if command not in PLURAL_CITATION_COMMANDS:
                break
    return citations


def check_sources(
    entry_paths: list[Path], allowed_root: Path | None = None
) -> tuple[list[Finding], dict[str, int]]:
    base = Path.cwd()
    root = (allowed_root or base).resolve()
    sources, findings = load_sources(entry_paths, base, root)
    labels: dict[str, list[tuple[Path, int]]] = {}
    references: list[tuple[str, Path, int]] = []
    citations: list[tuple[str, Path, int]] = []
    bibliography_files: set[Path] = set()
    main_directories = {path.resolve().parent for path in entry_paths}

    label_pattern = re.compile(r"\\label\s*\{([^{}]+)\}")
    reference_pattern = re.compile(
        r"\\(?:ref|eqref|autoref|pageref|cref|Cref|nameref)\*?\s*\{([^{}]+)\}"
    )
    bibliography_pattern = re.compile(r"\\bibliography\s*\{([^{}]+)\}")
    add_bib_pattern = re.compile(r"\\addbibresource(?:\s*\[[^\]]*\])?\s*\{([^{}]+)\}")
    figure_pattern = re.compile(r"\\includegraphics(?:\s*\[[^\]]*\])?\s*\{([^{}]+)\}")
    graphicspath_pattern = re.compile(r"\\graphicspath\s*\{((?:\{[^{}]*\}\s*)+)\}")
    manual_number_pattern = re.compile(
        r"\b(?:Figure|Fig\.|Table|Equation|Eq\.)\s*~?\s*\(?\d+\)?|(?:图|表|公式)\s*\d+",
        re.IGNORECASE,
    )
    placeholder_pattern = re.compile(r"\b(?:TODO|FIXME|XXX)\b|\?\?|【未确认】")

    for source in sources.values():
        for match in label_pattern.finditer(source.clean_text):
            label = match.group(1).strip()
            labels.setdefault(label, []).append(
                (source.path, line_number(source.clean_text, match.start()))
            )

        for match in reference_pattern.finditer(source.clean_text):
            for key in match.group(1).split(","):
                references.append(
                    (key.strip(), source.path, line_number(source.clean_text, match.start()))
                )

        for key, position in citation_keys(source.clean_text):
            citations.append(
                (key, source.path, line_number(source.clean_text, position))
            )

        for match in bibliography_pattern.finditer(source.clean_text):
            for raw_name in match.group(1).split(","):
                bib_path = source.path.parent / raw_name.strip()
                if bib_path.suffix == "":
                    bib_path = bib_path.with_suffix(".bib")
                if not is_within(bib_path, root):
                    add_finding(
                        findings,
                        "error",
                        "path-outside-root",
                        source.path,
                        line_number(source.clean_text, match.start()),
                        f"Bibliography resolves outside allowed root {root}: {raw_name.strip()}",
                        base,
                    )
                else:
                    bibliography_files.add(bib_path.resolve())

        for match in add_bib_pattern.finditer(source.clean_text):
            raw_name = match.group(1).strip()
            bib_path = source.path.parent / raw_name
            if bib_path.suffix == "":
                bib_path = bib_path.with_suffix(".bib")
            if not is_within(bib_path, root):
                add_finding(
                    findings,
                    "error",
                    "path-outside-root",
                    source.path,
                    line_number(source.clean_text, match.start()),
                    f"Bibliography resolves outside allowed root {root}: {raw_name}",
                    base,
                )
            else:
                bibliography_files.add(bib_path.resolve())

        graphics_directories: list[Path] = []
        for path_match in graphicspath_pattern.finditer(source.clean_text):
            for raw_directory in re.findall(r"\{([^{}]*)\}", path_match.group(1)):
                for main_directory in main_directories:
                    graphics_directories.append(main_directory / raw_directory)

        for match in figure_pattern.finditer(source.clean_text):
            raw_name = match.group(1).strip()
            figure_line = line_number(source.clean_text, match.start())
            if "\\" in raw_name or "#" in raw_name:
                add_finding(
                    findings,
                    "warning",
                    "dynamic-figure-path",
                    source.path,
                    figure_line,
                    f"Dynamic figure path could not be checked: {raw_name}",
                    base,
                )
                continue
            candidates = [source.path.parent / raw_name]
            candidates.extend(directory / raw_name for directory in main_directories)
            candidates.extend(directory / raw_name for directory in graphics_directories)
            resolved_figure, escaped_root = resolve_with_extensions(candidates, root)
            if resolved_figure is None and escaped_root:
                add_finding(
                    findings,
                    "error",
                    "path-outside-root",
                    source.path,
                    figure_line,
                    f"Figure path resolves outside allowed root {root}: {raw_name}",
                    base,
                )
            elif resolved_figure is None:
                add_finding(
                    findings,
                    "error",
                    "missing-figure",
                    source.path,
                    figure_line,
                    f"Figure file not found: {raw_name}",
                    base,
                )

        for match in manual_number_pattern.finditer(source.clean_text):
            add_finding(
                findings,
                "warning",
                "manual-number-reference",
                source.path,
                line_number(source.clean_text, match.start()),
                f"Possible manual cross-reference: {match.group(0)!r}",
                base,
            )

        for match in placeholder_pattern.finditer(source.clean_text):
            add_finding(
                findings,
                "warning",
                "unresolved-placeholder",
                source.path,
                line_number(source.clean_text, match.start()),
                f"Unresolved placeholder: {match.group(0)!r}",
                base,
            )

        if re.search(r"\\begin\s*\{eqnarray\*?\}", source.clean_text):
            add_finding(
                findings,
                "warning",
                "legacy-eqnarray",
                source.path,
                1,
                "eqnarray has unreliable spacing; prefer an amsmath alignment environment.",
                base,
            )

        for match in re.finditer(r"\\tag\s*\{\s*\d+\s*\}", source.clean_text):
            add_finding(
                findings,
                "warning",
                "manual-equation-tag",
                source.path,
                line_number(source.clean_text, match.start()),
                "Manual numeric equation tag may break automatic numbering.",
                base,
            )

    for label, locations in labels.items():
        if len(locations) <= 1:
            continue
        for path, label_line in locations:
            add_finding(
                findings,
                "error",
                "duplicate-label",
                path,
                label_line,
                f"Duplicate label: {label}",
                base,
            )

    for key, path, reference_line in references:
        if key and key not in labels:
            add_finding(
                findings,
                "error",
                "undefined-reference",
                path,
                reference_line,
                f"Reference has no matching label: {key}",
                base,
            )

    used_labels = {key for key, _, _ in references}
    for label, locations in labels.items():
        if label in used_labels:
            continue
        path, label_line = locations[0]
        add_finding(
            findings,
            "info",
            "unused-label",
            path,
            label_line,
            f"Label is not referenced in the checked sources: {label}",
            base,
        )

    bibliography_keys: set[str] = set()
    for bib_path in bibliography_files:
        if not bib_path.is_file():
            add_finding(
                findings,
                "error",
                "missing-bibliography",
                bib_path,
                1,
                "Bibliography file not found.",
                base,
            )
            continue
        try:
            bib_text = strip_comments(bib_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as error:
            add_finding(
                findings,
                "error",
                "unreadable-bibliography",
                bib_path,
                1,
                f"Could not read bibliography as UTF-8: {error}",
                base,
            )
            continue
        bibliography_keys.update(
            match.group(1).strip()
            for match in re.finditer(r"@\w+\s*\{\s*([^,\s]+)\s*,", bib_text)
        )

    if citations and not bibliography_files:
        first_key, first_path, first_line = citations[0]
        add_finding(
            findings,
            "warning",
            "bibliography-not-declared",
            first_path,
            first_line,
            f"Citations are present but no bibliography resource was found (first key: {first_key}).",
            base,
        )
    elif bibliography_files:
        for key, path, citation_line in citations:
            if key and key not in bibliography_keys:
                add_finding(
                    findings,
                    "error",
                    "undefined-citation",
                    path,
                    citation_line,
                    f"Citation key not found in loaded bibliography files: {key}",
                    base,
                )

    findings.sort(
        key=lambda item: (SEVERITY_ORDER[item.severity], item.path, item.line, item.code)
    )
    summary = {
        "sources": len(sources),
        "errors": sum(item.severity == "error" for item in findings),
        "warnings": sum(item.severity == "warning" for item in findings),
        "info": sum(item.severity == "info" for item in findings),
    }
    return findings, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Statically check LaTeX references, citations, figures, and placeholders."
    )
    parser.add_argument("paths", nargs="+", type=Path, help="Root .tex file(s) to check")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Allowed project root for TeX, bibliography, and figure files (default: cwd)",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    parser.add_argument(
        "--strict", action="store_true", help="Return nonzero when warnings are present"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    findings, summary = check_sources(args.paths, args.root)
    if args.json:
        print(
            json.dumps(
                {"summary": summary, "findings": [asdict(item) for item in findings]},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for item in findings:
            print(
                f"{item.severity.upper()}: {item.path}:{item.line}: "
                f"[{item.code}] {item.message}"
            )
        print(
            "SUMMARY: {sources} source(s), {errors} error(s), "
            "{warnings} warning(s), {info} info".format(**summary)
        )
    if summary["errors"] or (args.strict and summary["warnings"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())