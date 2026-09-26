#!/usr/bin/env python3
"""Static checks for cross-references, citations, figures, and placeholders.

Paths follow TeX semantics. ``\\input``, ``\\include``, ``\\bibliography``,
``\\addbibresource``, ``\\includegraphics`` and ``\\graphicspath`` are resolved
from the directory of the root file (the directory TeX compiles in), even when
the command sits in a sub-file. A path that only works relative to the
sub-file's own directory is reported as ``subfile-relative-path``, because the
real compile will not find it.

``\\input{name}`` tries ``name.tex`` first and then ``name`` as written, so
dotted names such as ``sections/1.intro`` work the way TeX loads them;
``\\include{name}`` always appends ``.tex``.

Every path component is compared with the real directory listing, so a file
that is only found when case is ignored is reported as ``path-case-mismatch``
on every system, including the default case-insensitive macOS file systems.
Linux and Overleaf would not find such a file.

Usage::

    python3 check_latex.py [--root DIR] [--json] [--strict] main.tex [more.tex ...]
    python3 check_latex.py --selftest

Without ``--root`` the allowed root is the current directory when every root
file lies inside it; otherwise it is the directory that contains the root
files. Nothing outside the allowed root is read.

Exit status: 0 no errors (with ``--strict``: no warnings either); 1 errors (or
warnings under ``--strict``), or a failing ``--selftest``; 2 bad command line.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path


SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
# pdfLaTeX's graphicx also tries the upper-case spellings, so a file saved as
# `plot.PNG` is found for `\includegraphics{plot}` and is not a case error.
FIGURE_EXTENSIONS = (
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".eps",
    ".svg",
    ".PDF",
    ".PNG",
    ".JPG",
    ".JPEG",
    ".EPS",
)
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
INPUT_PATTERN = re.compile(r"\\(?P<command>input|include)\s*\{(?P<name>[^{}]+)\}")
LABEL_PATTERN = re.compile(r"\\label\s*\{([^{}]+)\}")
REFERENCE_PATTERN = re.compile(
    r"\\(?:ref|eqref|autoref|pageref|cref|Cref|nameref)\*?\s*\{([^{}]+)\}"
)
BIBLIOGRAPHY_PATTERN = re.compile(r"\\bibliography\s*\{([^{}]+)\}")
ADD_BIB_PATTERN = re.compile(r"\\addbibresource(?:\s*\[[^\]]*\])?\s*\{([^{}]+)\}")
FIGURE_PATTERN = re.compile(r"\\includegraphics(?:\s*\[[^\]]*\])?\s*\{([^{}]+)\}")
GRAPHICSPATH_PATTERN = re.compile(r"\\graphicspath\s*\{((?:\{[^{}]*\}\s*)+)\}")
# Hand-written numbers instead of \ref / \eqref. The Chinese forms cover
# "图 2", "表 3", "公式 (3)", "公式（4）", "式 (5)", "式（5）" and "方程（2）".
# A bare 式 or 方程 needs brackets, and common words are excluded so that
# 形式（1）, 方式 (2), 代表 1 个, 发表 2 篇 or 地图 3 张 are not reported.
MANUAL_NUMBER_PATTERN = re.compile(
    r"\b(?:Figure|Fig\.|Table|Equation|Eq\.)\s*~?\s*\(?\d+\)?"
    r"|(?:(?<![代发列])表|(?<![试意地企])图|公式)\s*~?\s*[（(]?\s*\d+\s*[)）]?"
    r"|(?:方程|(?<![形方模格样范仪正款制句招新旧中西各])式)\s*~?\s*[（(]\s*\d+\s*[)）]",
    re.IGNORECASE,
)
PLACEHOLDER_PATTERN = re.compile(r"\b(?:TODO|FIXME|XXX)\b|\?\?|【未确认】")


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


@dataclass(frozen=True)
class Located:
    """Result of looking a TeX path up the way the compiler would."""

    status: str  # "found", "case-mismatch", "outside-root" or "missing"
    path: Path | None = None  # the file on disk, spelled as the directory lists it
    written: str = ""  # the spelling that only matched when case is ignored


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


def tex_input_names(command: str, raw_name: str) -> list[str]:
    """File names TeX tries for \\input / \\include, in TeX's order."""
    if command == "include":
        return [raw_name + ".tex"]
    if raw_name.endswith(".tex"):
        return [raw_name]
    return [raw_name + ".tex", raw_name]


def bibliography_names(command: str, raw_name: str) -> list[str]:
    """File names BibTeX / biber would read for one bibliography entry."""
    if raw_name.endswith(".bib"):
        return [raw_name]
    if command == "addbibresource" and Path(raw_name).suffix:
        return [raw_name, raw_name + ".bib"]
    return [raw_name + ".bib"]


def figure_names(raw_name: str, graphics_prefixes: list[str]) -> list[str]:
    """Spellings graphicx tries: the name, then each \\graphicspath prefix."""
    names: list[str] = []
    for prefix in ["", *graphics_prefixes]:
        stem = raw_name if not prefix else prefix.rstrip("/") + "/" + raw_name
        names.append(stem)
        if Path(stem).suffix == "":
            names.extend(stem + extension for extension in FIGURE_EXTENSIONS)
    return names


class Resolver:
    """Looks paths up component by component against real directory listings."""

    def __init__(self, allowed_root: Path) -> None:
        self.root = allowed_root.resolve()
        self._listings: dict[Path, dict[str, str] | None] = {}

    def _listing(self, directory: Path) -> dict[str, str] | None:
        if directory not in self._listings:
            try:
                entries = os.listdir(directory)
            except OSError:
                self._listings[directory] = None
            else:
                self._listings[directory] = {
                    unicodedata.normalize("NFC", entry): entry for entry in entries
                }
        return self._listings[directory]

    def walk(self, base: Path, relative: str) -> tuple[Path | None, bool]:
        """Return (file as spelled on disk, whether the case differed)."""
        written = Path(relative)
        if written.is_absolute():
            current = Path(written.anchor)
            parts = written.parts[1:]
        else:
            current = base
            parts = written.parts
        case_differs = False
        for part in parts:
            if part in ("", "."):
                continue
            if part == "..":
                current = current.parent
                continue
            listing = self._listing(current)
            if listing is None:
                return None, False
            wanted = unicodedata.normalize("NFC", part)
            if wanted in listing:
                current = current / listing[wanted]
                continue
            folded = sorted(
                actual
                for normalized, actual in listing.items()
                if normalized.casefold() == wanted.casefold()
            )
            if not folded:
                return None, False
            current = current / folded[0]
            case_differs = True
        if not current.is_file():
            return None, False
        return current, case_differs

    def locate(self, bases: list[Path], names: list[str]) -> Located:
        """Try every base directory with every name; exact spelling wins."""
        case_match: Located | None = None
        escaped = False
        for base in bases:
            for name in names:
                if not is_within(base / name, self.root):
                    escaped = True
                    continue
                path, case_differs = self.walk(base, name)
                if path is None or not is_within(path, self.root):
                    continue
                if not case_differs:
                    return Located("found", path)
                if case_match is None:
                    case_match = Located("case-mismatch", path, name)
        if case_match is not None:
            return case_match
        return Located("outside-root" if escaped else "missing")


def resolve_reference(
    resolver: Resolver,
    main_directories: list[Path],
    source_directory: Path,
    names: list[str],
) -> tuple[Located, bool]:
    """Resolve from the root file's directory; fall back to the sub-file's
    directory only to report it. Returns (location, only_relative_to_subfile)."""
    located = resolver.locate(main_directories, names)
    if located.status != "missing" or source_directory in main_directories:
        return located, False
    fallback = resolver.locate([source_directory], names)
    if fallback.status in ("found", "case-mismatch"):
        return fallback, True
    return located, False


def default_root(entry_paths: list[Path], cwd: Path) -> Path:
    """cwd when it contains every root file, else the root files' directory."""
    resolved = [path.resolve() for path in entry_paths]
    if all(is_within(path, cwd) for path in resolved):
        return cwd.resolve()
    return Path(os.path.commonpath([str(path.parent) for path in resolved]))


def load_sources(
    entry_paths: list[Path], base: Path, resolver: Resolver
) -> tuple[dict[Path, Source], dict[Path, list[Path]], list[Finding]]:
    allowed_root = resolver.root
    sources: dict[Path, Source] = {}
    mains: dict[Path, list[Path]] = {}
    findings: list[Finding] = []
    visited: set[tuple[Path, Path]] = set()

    def read(path: Path, referring_path: Path | None, referring_line: int) -> Source | None:
        resolved = path.resolve()
        if resolved in sources:
            return sources[resolved]
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
            return None
        if not resolved.is_file():
            add_finding(
                findings,
                "error",
                "missing-tex-input",
                referring_path or path,
                referring_line,
                f"TeX source not found: {display_path(path, base)}",
                base,
            )
            return None
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
            return None
        source = Source(resolved, text, strip_comments(text))
        sources[resolved] = source
        return source

    def visit(path: Path, main_directory: Path, referring_path: Path | None, referring_line: int) -> None:
        source = read(path, referring_path, referring_line)
        if source is None:
            return
        key = (source.path, main_directory)
        if key in visited:
            return
        visited.add(key)
        directories = mains.setdefault(source.path, [])
        if main_directory not in directories:
            directories.append(main_directory)

        for match in INPUT_PATTERN.finditer(source.clean_text):
            command = match.group("command")
            raw_name = match.group("name").strip()
            input_line = line_number(source.clean_text, match.start())
            if "\\" in raw_name or "#" in raw_name:
                add_finding(
                    findings,
                    "warning",
                    "dynamic-tex-input",
                    source.path,
                    input_line,
                    f"Dynamic TeX input could not be checked: {raw_name}",
                    base,
                )
                continue
            names = tex_input_names(command, raw_name)
            located, subfile_only = resolve_reference(
                resolver, [main_directory], source.path.parent, names
            )
            if located.status == "outside-root":
                add_finding(
                    findings,
                    "error",
                    "path-outside-root",
                    source.path,
                    input_line,
                    f"TeX input resolves outside allowed root {allowed_root}: {raw_name}",
                    base,
                )
                continue
            if located.status == "missing":
                hint = ""
                if command == "include" and raw_name.endswith(".tex"):
                    hint = " (\\include always appends .tex; write the name without it)"
                add_finding(
                    findings,
                    "error",
                    "missing-tex-input",
                    source.path,
                    input_line,
                    f"TeX source not found: {display_path(main_directory / names[0], base)}{hint}",
                    base,
                )
                continue
            assert located.path is not None
            report_location_problems(
                findings, located, subfile_only, f"\\{command}", raw_name,
                main_directory, source.path, input_line, base,
            )
            visit(located.path, main_directory, source.path, input_line)

    for entry_path in entry_paths:
        visit(entry_path, entry_path.resolve().parent, None, 1)
    return sources, mains, findings


def report_location_problems(
    findings: list[Finding],
    located: Located,
    subfile_only: bool,
    what: str,
    raw_name: str,
    main_directory: Path,
    source_path: Path,
    line: int,
    base: Path,
) -> None:
    assert located.path is not None
    on_disk = os.path.relpath(located.path, main_directory)
    if subfile_only:
        add_finding(
            findings,
            "error",
            "subfile-relative-path",
            source_path,
            line,
            f"{what}{{{raw_name}}} only resolves relative to the sub-file's directory; "
            f"TeX resolves it from the root file's directory, so the compile will not "
            f"find it. Write it from the root directory: {on_disk}",
            base,
        )
    if located.status == "case-mismatch":
        add_finding(
            findings,
            "error",
            "path-case-mismatch",
            source_path,
            line,
            f"{what}{{{raw_name}}} matches {on_disk} on disk only when case is ignored; "
            f"case-sensitive systems (Linux, Overleaf) will not find it.",
            base,
        )


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
    root = (allowed_root or default_root(entry_paths, base)).resolve()
    resolver = Resolver(root)
    sources, mains, findings = load_sources(entry_paths, base, resolver)
    labels: dict[str, list[tuple[Path, int]]] = {}
    references: list[tuple[str, Path, int]] = []
    citations: list[tuple[str, Path, int]] = []
    bibliography_files: set[Path] = set()
    bibliography_missing = False

    # \graphicspath is global in TeX: set once (usually in the root preamble),
    # it applies to figures in every sub-file.
    graphics_prefixes: list[str] = []
    for source in sources.values():
        for path_match in GRAPHICSPATH_PATTERN.finditer(source.clean_text):
            for raw_directory in re.findall(r"\{([^{}]*)\}", path_match.group(1)):
                if raw_directory.strip() and raw_directory not in graphics_prefixes:
                    graphics_prefixes.append(raw_directory.strip())

    for source in sources.values():
        main_directories = mains.get(source.path, [source.path.parent])

        for match in LABEL_PATTERN.finditer(source.clean_text):
            label = match.group(1).strip()
            labels.setdefault(label, []).append(
                (source.path, line_number(source.clean_text, match.start()))
            )

        for match in REFERENCE_PATTERN.finditer(source.clean_text):
            for key in match.group(1).split(","):
                references.append(
                    (key.strip(), source.path, line_number(source.clean_text, match.start()))
                )

        for key, position in citation_keys(source.clean_text):
            citations.append(
                (key, source.path, line_number(source.clean_text, position))
            )

        bibliography_entries: list[tuple[str, str, int]] = []
        for match in BIBLIOGRAPHY_PATTERN.finditer(source.clean_text):
            for raw_name in match.group(1).split(","):
                if raw_name.strip():
                    bibliography_entries.append(
                        ("bibliography", raw_name.strip(), line_number(source.clean_text, match.start()))
                    )
        for match in ADD_BIB_PATTERN.finditer(source.clean_text):
            bibliography_entries.append(
                ("addbibresource", match.group(1).strip(), line_number(source.clean_text, match.start()))
            )
        for command, raw_name, bib_line in bibliography_entries:
            names = bibliography_names(command, raw_name)
            located, subfile_only = resolve_reference(
                resolver, main_directories, source.path.parent, names
            )
            if located.status == "outside-root":
                add_finding(
                    findings,
                    "error",
                    "path-outside-root",
                    source.path,
                    bib_line,
                    f"Bibliography resolves outside allowed root {root}: {raw_name}",
                    base,
                )
            elif located.status == "missing":
                bibliography_missing = True
                add_finding(
                    findings,
                    "error",
                    "missing-bibliography",
                    source.path,
                    bib_line,
                    "Bibliography file not found: "
                    f"{display_path(main_directories[0] / names[-1], base)}",
                    base,
                )
            else:
                assert located.path is not None
                report_location_problems(
                    findings, located, subfile_only, f"\\{command}", raw_name,
                    main_directories[0], source.path, bib_line, base,
                )
                bibliography_files.add(located.path.resolve())

        for match in FIGURE_PATTERN.finditer(source.clean_text):
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
            located, subfile_only = resolve_reference(
                resolver,
                main_directories,
                source.path.parent,
                figure_names(raw_name, graphics_prefixes),
            )
            if located.status == "outside-root":
                add_finding(
                    findings,
                    "error",
                    "path-outside-root",
                    source.path,
                    figure_line,
                    f"Figure path resolves outside allowed root {root}: {raw_name}",
                    base,
                )
            elif located.status == "missing":
                add_finding(
                    findings,
                    "error",
                    "missing-figure",
                    source.path,
                    figure_line,
                    f"Figure file not found: {raw_name}",
                    base,
                )
            else:
                report_location_problems(
                    findings, located, subfile_only, "\\includegraphics", raw_name,
                    main_directories[0], source.path, figure_line, base,
                )

        for match in MANUAL_NUMBER_PATTERN.finditer(source.clean_text):
            add_finding(
                findings,
                "warning",
                "manual-number-reference",
                source.path,
                line_number(source.clean_text, match.start()),
                f"Possible manual cross-reference: {match.group(0)!r}",
                base,
            )

        for match in PLACEHOLDER_PATTERN.finditer(source.clean_text):
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
    for bib_path in sorted(bibliography_files):
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

    if citations and not (bibliography_files or bibliography_missing):
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
    elif bibliography_files or bibliography_missing:
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


# ---------------------------------------------------------------- selftest

# A 1x1 PNG, so figure fixtures are real image files.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000b4944415478da63f80f040009fb03fd68fa1ccc0000000049454e44ae426082"
)
PREAMBLE = "\\documentclass{article}\n\\usepackage{graphicx}\n"

SELFTEST_CASES: list[dict[str, object]] = [
    {
        "name": "normal paper: labels, citation, graphicspath figure, upper-case extension",
        "files": {
            "main.tex": PREAMBLE + "\\graphicspath{{figures/}}\n\\begin{document}\n"
            "\\section{Model}\\label{sec:model}\nSee Section~\\ref{sec:model} and \\cite{knuth84}.\n"
            "\\includegraphics{demand}\n\\includegraphics{figures/photo}\n"
            "\\bibliographystyle{plain}\n\\bibliography{refs}\n\\end{document}\n",
            "figures/demand.png": TINY_PNG,
            "figures/photo.PNG": TINY_PNG,
            "refs.bib": "@book{knuth84,\n  title = {The TeXbook},\n  year = {1984}\n}\n",
        },
        "expect": {},
    },
    {
        "name": "nested \\input resolves from the root file's directory (scripts-a-11)",
        "files": {
            "main.tex": PREAMBLE + "\\begin{document}\n\\input{sections/results}\n\\end{document}\n",
            "sections/results.tex": "Results.\n\\input{tables/t1}\n",
            "tables/t1.tex": "Table one.\n",
        },
        "expect": {},
    },
    {
        "name": "path that only exists next to the sub-file is an error (scripts-a-11)",
        "files": {
            "main.tex": PREAMBLE + "\\begin{document}\n\\input{sections/results}\n\\end{document}\n",
            "sections/results.tex": "Results.\n\\input{tables/t1}\n",
            "sections/tables/t1.tex": "Table one.\n",
        },
        "expect": {"subfile-relative-path": 1},
    },
    {
        "name": "\\input and \\bibliography inside a sub-file resolve from the root (modeling-3)",
        "files": {
            "main.tex": PREAMBLE + "\\begin{document}\n\\input{sections/intro}\n\\end{document}\n",
            "sections/intro.tex": "\\input{sections/detail}\nSee \\cite{knuth84}.\n"
            "\\bibliographystyle{plain}\n\\bibliography{refs}\n",
            "sections/detail.tex": "Detail.\n",
            "refs.bib": "@book{knuth84,\n  title = {The TeXbook},\n  year = {1984}\n}\n",
        },
        "expect": {},
    },
    {
        "name": "sub-file writes \\input{detail} for sections/detail.tex (modeling-3)",
        "files": {
            "main.tex": PREAMBLE + "\\begin{document}\n\\input{sections/intro}\n\\end{document}\n",
            "sections/intro.tex": "\\input{detail}\n",
            "sections/detail.tex": "Detail.\n",
        },
        "expect": {"subfile-relative-path": 1},
    },
    {
        "name": "figure and \\input differ from the disk only in case (modeling-4)",
        "files": {
            "main.tex": PREAMBLE + "\\begin{document}\n\\input{Sec}\n"
            "\\includegraphics{figs/Result.PNG}\n\\end{document}\n",
            "sec.tex": "Section.\n",
            "figs/result.png": TINY_PNG,
        },
        "expect": {"path-case-mismatch": 2},
    },
    {
        "name": "Chinese manual numbers are reported, ordinary words are not (modeling-x1)",
        "files": {
            "main.tex": PREAMBLE + "\\begin{document}\n由公式 (3) 可知。\n由公式（4）可知。\n"
            "由式 (5) 可得。\n代入式（5）。\n由方程（2）得。\n见图 2。\n如表 3 所示。\n"
            "See Eq. (6).\n两种形式（1）和方式 (2)。\n每个节点代表 1 个站点，发表 2 篇。\n"
            "式中 $x$ 为需求，见式~\\eqref{eq:a}。\n"
            "\\begin{equation}\\label{eq:a}x=1\\end{equation}\n\\end{document}\n",
        },
        "expect": {"manual-number-reference": 8},
    },
    {
        "name": "dotted names: \\input adds .tex like TeX, \\include always does (modeling-x2)",
        "files": {
            "main.tex": PREAMBLE + "\\begin{document}\n\\input{sections/1.intro}\n"
            "\\include{chapters/ch.2}\n\\end{document}\n",
            "sections/1.intro.tex": "Intro.\n",
            "chapters/ch.2.tex": "Chapter two.\n",
        },
        "expect": {},
    },
    {
        "name": "\\graphicspath from the root preamble applies to sub-file figures",
        "files": {
            "main.tex": PREAMBLE + "\\graphicspath{{figures/}}\n\\begin{document}\n"
            "\\input{sections/a}\n\\end{document}\n",
            "sections/a.tex": "\\includegraphics{plot}\n",
            "figures/plot.png": TINY_PNG,
        },
        "expect": {},
    },
    {
        "name": "missing files and paths outside --root are still reported",
        "files": {
            "main.tex": PREAMBLE + "\\begin{document}\n\\input{sections/none}\n\\input{../outside}\n"
            "\\includegraphics{figs/none}\n\\cite{k}\n\\bibliography{none}\n\\end{document}\n",
        },
        "expect": {
            "missing-tex-input": 1,
            "path-outside-root": 1,
            "missing-figure": 1,
            "missing-bibliography": 1,
            "undefined-citation": 1,
        },
    },
]


def _write_project(project: Path, files: dict[str, object]) -> None:
    for relative, content in files.items():
        target = project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(str(content), encoding="utf-8")


def selftest() -> int:
    passed = 0
    total = len(SELFTEST_CASES) + 1
    with tempfile.TemporaryDirectory() as temp_directory:
        temp_root = Path(temp_directory).resolve()
        (temp_root / "outside.tex").write_text("outside\n", encoding="utf-8")
        for number, case in enumerate(SELFTEST_CASES, 1):
            project = temp_root / f"case{number}"
            _write_project(project, case["files"])  # type: ignore[arg-type]
            findings, _ = check_sources([project / "main.tex"], project)
            got = Counter(item.code for item in findings if item.severity != "info")
            expected = Counter(case["expect"])  # type: ignore[arg-type]
            if got == expected:
                passed += 1
                print(f"  pass  {case['name']}")
            else:
                print(f"  FAIL  {case['name']}: expected {dict(expected)}, got {dict(got)}")
                for item in findings:
                    print(f"          {item.severity}: {item.path}:{item.line}: [{item.code}] {item.message}")

        # modeling-1: the command exactly as SKILL.md writes it, run from the
        # skill directory without --root, must read the paper.
        name = "SKILL.md command run from the skill directory reads the paper (modeling-1)"
        paper = temp_root / "paper"
        _write_project(paper, SELFTEST_CASES[0]["files"])  # type: ignore[arg-type]
        skill_directory = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "scripts/check_latex.py", "--json", str(paper / "main.tex")],
            cwd=skill_directory,
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            summary = json.loads(result.stdout)["summary"]
        except (ValueError, KeyError):
            summary = {}
        if result.returncode == 0 and summary.get("sources") == 1 and summary.get("errors") == 0:
            passed += 1
            print(f"  pass  {name}")
        else:
            print(f"  FAIL  {name}: exit {result.returncode}, summary {summary}, stderr {result.stderr.strip()!r}")

    print(f"selftest: {passed}/{total} passed")
    return 0 if passed == total else 1


# ---------------------------------------------------------------- command line


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Statically check LaTeX references, citations, figures, and placeholders.",
        epilog="Exit status: 0 no errors (with --strict: no warnings); 1 errors, warnings "
        "under --strict, or a failing --selftest; 2 bad command line.",
    )
    parser.add_argument("paths", nargs="*", type=Path, help="Root .tex file(s) to check")
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Allowed project root for TeX, bibliography, and figure files "
        "(default: cwd if it contains every root file, else the root files' directory)",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    parser.add_argument(
        "--strict", action="store_true", help="Return nonzero when warnings are present"
    )
    parser.add_argument(
        "--selftest", action="store_true", help="Run the built-in regression cases and exit"
    )
    args = parser.parse_args()
    if not args.selftest and not args.paths:
        parser.error("give at least one root .tex file (or --selftest)")
    return args


def main() -> int:
    args = parse_args()
    if args.selftest:
        return selftest()
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
