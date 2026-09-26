#!/usr/bin/env python3
"""Descriptive scan for systematic-error signatures in CSV data.

Uses only the Python standard library. Results are clues for investigation, not
proof of a physical cause.

Fits are computed on the predictor after centering and scaling it
(u = (x - mean) / sd), so a large offset (Unix epoch seconds) or a tiny SI scale
(wavelengths in metres) does not change the fitted curve, the SSE, or the
quadratic SSE reduction. The --time column may hold numbers or ISO 8601
timestamps; timestamps are converted to seconds since the earliest one (no time
zone conversion for timestamps without an offset). Rows whose predictor or
response cannot be read are counted in "dropped_rows" and named in "warnings".

Exit codes: 0 report written; 2 input error (unreadable file, missing column,
or a requested column with no usable rows). --selftest exits 0 when all
regression cases pass and 1 otherwise.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import fmean, pstdev
from typing import Iterable


class InputError(ValueError):
    """Raised when the CSV or the requested columns cannot support a scan."""


def finite_float(value: str | None) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def parse_iso(value: str | None) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    if text[-1] in "Zz":
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def column_values(rows: list[dict[str, str]], name: str, allow_iso: bool) -> tuple[list[float | None], str]:
    """Return one float (or None) per row and a description of how the column was read."""
    raw = [(row.get(name) or "").strip() for row in rows]
    numbers = [finite_float(text) for text in raw]
    if not allow_iso:
        return numbers, "numeric"
    unreadable = [text for text, number in zip(raw, numbers) if text and number is None]
    if not unreadable:
        return numbers, "numeric"
    stamps = [parse_iso(text) if text and number is None else None for text, number in zip(raw, numbers)]
    iso_count = sum(stamp is not None for stamp in stamps)
    if iso_count == 0:
        return numbers, "numeric"
    if any(number is not None for number in numbers):
        raise InputError(f"column '{name}' mixes plain numbers and ISO 8601 timestamps; use one format")
    parsed = [stamp for stamp in stamps if stamp is not None]
    aware = {stamp.tzinfo is not None and stamp.utcoffset() is not None for stamp in parsed}
    if len(aware) > 1:
        raise InputError(f"column '{name}' mixes timestamps with and without a UTC offset")
    origin = min(parsed)
    seconds = [None if stamp is None else (stamp - origin).total_seconds() for stamp in stamps]
    return seconds, f"ISO 8601 timestamps converted to seconds since {origin.isoformat()}"


def correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    mx, my = fmean(xs), fmean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    denominator = math.sqrt(sum(v * v for v in dx) * sum(v * v for v in dy))
    return sum(a * b for a, b in zip(dx, dy)) / denominator if denominator else None


def linear_fit(xs: list[float], ys: list[float]) -> dict[str, float] | None:
    if len(xs) < 2:
        return None
    mx, my = fmean(xs), fmean(ys)
    dx = [x - mx for x in xs]
    sxx = sum(d * d for d in dx)
    if not sxx:
        return None
    slope = sum(d * (y - my) for d, y in zip(dx, ys)) / sxx
    intercept = my - slope * mx
    sse = sum((y - my - slope * d) ** 2 for d, y in zip(dx, ys))
    return {"slope": slope, "intercept": intercept, "sse": sse}


def solve_3x3(matrix: list[list[float]], vector: list[float]) -> list[float] | None:
    scale = max(abs(value) for row in matrix for value in row) or 1.0
    augmented = [row[:] + [value] for row, value in zip(matrix, vector)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda r: abs(augmented[r][column]))
        if abs(augmented[pivot][column]) <= 1e-12 * scale:
            return None
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(3):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [a - factor * b for a, b in zip(augmented[row], augmented[column])]
    return [augmented[i][3] for i in range(3)]


def quadratic_fit(xs: list[float], ys: list[float]) -> tuple[dict[str, float] | None, str | None]:
    """Least-squares y = a0 + a1*x + a2*x^2, solved on the centered and scaled predictor."""
    if len(xs) < 4:
        return None, "quadratic fit needs at least 4 usable rows"
    if len(set(xs)) < 3:
        return None, "quadratic fit needs at least 3 distinct predictor values"
    center, y_center = fmean(xs), fmean(ys)
    scale = math.sqrt(fmean([(x - center) ** 2 for x in xs]))
    us = [(x - center) / scale for x in xs]
    vs = [y - y_center for y in ys]
    sums = [sum(u ** power for u in us) for power in range(5)]
    matrix = [[sums[i + j] for j in range(3)] for i in range(3)]
    vector = [sum((u ** power) * v for u, v in zip(us, vs)) for power in range(3)]
    coefficients = solve_3x3(matrix, vector)
    if coefficients is None:
        return None, "quadratic normal equations are singular even after centering and scaling"
    b0, b1, b2 = coefficients
    sse = sum((v - (b0 + b1 * u + b2 * u * u)) ** 2 for u, v in zip(us, vs))
    quadratic = b2 / scale**2
    linear = b1 / scale - 2.0 * b2 * center / scale**2
    constant = y_center + b0 - b1 * center / scale + b2 * center**2 / scale**2
    return {
        "constant": constant,
        "linear": linear,
        "quadratic": quadratic,
        "sse": sse,
        "x_center": center,
        "x_scale": scale,
    }, None


def scan_pair(
    rows: list[dict[str, str]],
    predictor: str,
    response: str,
    x_values: list[float | None],
    y_values: list[float | None],
    encoding: str,
) -> dict[str, object]:
    xs: list[float] = []
    ys: list[float] = []
    first_bad: str | None = None
    for row, x, y in zip(rows, x_values, y_values):
        if x is not None and y is not None:
            xs.append(x)
            ys.append(y)
        elif first_bad is None:
            column = predictor if x is None else response
            first_bad = f"'{column}' = {(row.get(column) or '')!r}"
    dropped = len(rows) - len(xs)
    if not xs:
        raise InputError(
            f"no usable rows for predictor '{predictor}': no row has both a readable '{predictor}' "
            f"and a numeric '{response}' (first unreadable value: {first_bad}). "
            "Numeric columns need plain numbers; the --time column also accepts ISO 8601 timestamps."
        )
    warnings: list[str] = []
    if dropped:
        warnings.append(f"{dropped} of {len(rows)} rows dropped (first unreadable value: {first_bad})")

    linear = linear_fit(xs, ys)
    if linear is None:
        warnings.append("linear fit unavailable: needs at least 2 rows with distinct predictor values")
    quadratic, quadratic_reason = quadratic_fit(xs, ys)
    if quadratic_reason:
        warnings.append(quadratic_reason)

    reduction: float | None = None
    if linear and quadratic:
        mean_y = fmean(ys)
        total = sum((y - mean_y) ** 2 for y in ys)
        if total == 0:
            warnings.append("response is constant over these rows; SSE reduction not defined")
        elif linear["sse"] <= 1e-12 * total:
            warnings.append("linear fit already leaves no residual; SSE reduction not defined")
        else:
            reduction = (linear["sse"] - quadratic["sse"]) / linear["sse"]
            if -1e-9 < reduction < 0:
                reduction = 0.0
            elif reduction < 0:
                warnings.append("negative SSE reduction is a numerical failure; do not interpret it")

    return {
        "predictor": predictor,
        "response": response,
        "predictor_encoding": encoding,
        "n": len(xs),
        "dropped_rows": dropped,
        "pearson_r": correlation(xs, ys),
        "linear_fit": linear,
        "quadratic_fit": quadratic,
        "quadratic_sse_reduction_fraction": reduction,
        "warnings": warnings,
    }


def segment_drift(y_values: list[float | None]) -> dict[str, object]:
    numeric = [value for value in y_values if value is not None]
    width = max(1, len(numeric) // 5) if numeric else 0
    if len(numeric) < 4:
        return {"n": len(numeric), "segment_width": width, "first_mean": None, "last_mean": None, "difference": None}
    first = fmean(numeric[:width])
    last = fmean(numeric[-width:])
    return {"n": len(numeric), "segment_width": width, "first_mean": first, "last_mean": last, "difference": last - first}


def repeat_scan(rows: list[dict[str, str]], group: str, y_values: list[float | None]) -> dict[str, object]:
    buckets: dict[str, list[float]] = {}
    for row, value in zip(rows, y_values):
        label = (row.get(group) or "").strip()
        if label and value is not None:
            buckets.setdefault(label, []).append(value)
    summaries = {
        label: {"n": len(values), "mean": fmean(values), "population_sd": pstdev(values) if len(values) > 1 else 0.0}
        for label, values in sorted(buckets.items())
    }
    means = [entry["mean"] for entry in summaries.values()]
    return {
        "group_count": len(summaries),
        "between_group_mean_range": max(means) - min(means) if len(means) >= 2 else None,
        "groups": summaries,
    }


def require_columns(fieldnames: Iterable[str] | None, required: Iterable[str]) -> None:
    available = set(fieldnames or [])
    missing = [name for name in required if name not in available]
    if missing:
        raise InputError(f"missing CSV column(s): {', '.join(missing)}")


def build_report(
    rows: list[dict[str, str]],
    fieldnames: Iterable[str] | None,
    source: str,
    response: str,
    time: str | None = None,
    temperature: str | None = None,
    parameters: list[str] | None = None,
    group: str | None = None,
) -> dict[str, object]:
    predictors = [name for name in [time, temperature, *(parameters or [])] if name]
    require_columns(fieldnames, [response, *predictors, *([group] if group else [])])
    if not rows:
        raise InputError("the CSV has a header but no data rows")
    y_values, _ = column_values(rows, response, allow_iso=False)
    if all(value is None for value in y_values):
        raise InputError(f"response column '{response}' has no numeric values")

    pair_scans = []
    for predictor in predictors:
        x_values, encoding = column_values(rows, predictor, allow_iso=(predictor == time))
        pair_scans.append(scan_pair(rows, predictor, response, x_values, y_values, encoding))

    report: dict[str, object] = {
        "source": source,
        "row_count": len(rows),
        "response": response,
        "warning": "Descriptive signatures are not proof of a physical cause.",
        "pair_scans": pair_scans,
        "acquisition_order_drift": segment_drift(y_values),
    }
    if group:
        report["repeat_scan"] = repeat_scan(rows, group, y_values)
    return report


def _report_from_text(text: str, **options: object) -> dict[str, object]:
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    return build_report(rows, reader.fieldnames, "selftest", **options)  # type: ignore[arg-type]


def run_selftest() -> int:
    outcomes: list[tuple[str, bool, str]] = []

    def scans(report: dict[str, object]) -> dict[str, dict[str, object]]:
        return {scan["predictor"]: scan for scan in report["pair_scans"]}  # type: ignore[index,union-attr]

    def check(name: str, func) -> None:  # type: ignore[no-untyped-def]
        try:
            ok, detail = func()
        except Exception as exc:  # noqa: BLE001 - a crash is a failed case
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        outcomes.append((name, ok, detail))

    def expect_input_error(name: str, text: str, message_part: str, **options: object) -> None:
        def run() -> tuple[bool, str]:
            try:
                _report_from_text(text, **options)
            except InputError as exc:
                return message_part in str(exc), str(exc)
            return False, "no input error raised"

        check(name, run)

    smoke = (
        "run_id,elapsed_s,temperature_C,control_value,measured_value\n"
        "A,0,20.0,1,10.0\nA,1,20.2,2,20.3\nA,2,20.4,3,30.8\n"
        "B,3,20.6,1,10.5\nB,4,20.8,2,21.0\nB,5,21.0,3,31.7\n"
    )

    def smoke_case() -> tuple[bool, str]:
        report = _report_from_text(
            smoke,
            response="measured_value",
            time="elapsed_s",
            temperature="temperature_C",
            parameters=["control_value"],
            group="run_id",
        )
        repeat = report["repeat_scan"]
        ok = (
            report["row_count"] == 6
            and len(report["pair_scans"]) == 3  # type: ignore[arg-type]
            and report["acquisition_order_drift"]["difference"] is not None  # type: ignore[index]
            and repeat["group_count"] == 2  # type: ignore[index]
        )
        return ok, json.dumps(report)[:300]

    check("smoke fixture: six rows, three scans, drift, two groups", smoke_case)

    # Audit regression: y exactly quadratic in time; epoch seconds used to give a negative reduction.
    epoch_text = "epoch_s,idx,y\n" + "".join(
        f"{1.7e9 + 60 * i:.1f},{i},{0.5 * i * i - 3 * i + 7}\n" for i in range(20)
    )

    def epoch_case() -> tuple[bool, str]:
        found = scans(_report_from_text(epoch_text, response="y", time="epoch_s", parameters=["idx"]))
        epoch = found["epoch_s"]["quadratic_sse_reduction_fraction"]
        index = found["idx"]["quadratic_sse_reduction_fraction"]
        ok = epoch is not None and index is not None and epoch > 0.999999 and abs(epoch - index) < 1e-9
        return ok, f"epoch={epoch}, idx={index}"

    check("Unix-timestamp predictor gives the same reduction as an index (exact quadratic)", epoch_case)

    # Audit regression: noisy curvature; epoch seconds went negative and SI-small metres returned null.
    rng = random.Random(7)
    noisy_lines = ["t_unix,t_rel,lam_m,y"]
    for i in range(60):
        t = 10 * i
        y = 1 + 2e-4 * t + 3e-7 * t * t + rng.gauss(0, 0.008)
        noisy_lines.append(f"{1758700000 + t},{t},{4e-7 + t * 1e-10:.6e},{y:.6f}")
    noisy_text = "\n".join(noisy_lines) + "\n"

    def noisy_case() -> tuple[bool, str]:
        found = scans(_report_from_text(noisy_text, response="y", time="t_unix", parameters=["t_rel", "lam_m"]))
        values = [found[name]["quadratic_sse_reduction_fraction"] for name in ("t_unix", "t_rel", "lam_m")]
        ok = all(v is not None for v in values) and values[1] > 0.5
        ok = ok and abs(values[0] - values[1]) < 1e-9 and abs(values[2] - values[1]) < 1e-9  # type: ignore[operator]
        quad = found["lam_m"]["quadratic_fit"]
        ok = ok and quad is not None and quad["sse"] <= found["lam_m"]["linear_fit"]["sse"]  # type: ignore[index]
        return ok, f"reductions t_unix/t_rel/lam_m = {values}"

    check("epoch-second and SI-small predictors match elapsed seconds (noisy)", noisy_case)

    # Audit regression: ISO strings used to be dropped entirely with n=0 and exit 0.
    start = datetime(2026, 9, 1, 10, 0, 0)
    iso_text = "ts,y\n" + "".join(
        f"{(start + timedelta(minutes=i)).isoformat()},{0.5 * i * i - 3 * i + 7}\n" for i in range(20)
    )

    def iso_case() -> tuple[bool, str]:
        scan = _report_from_text(iso_text, response="y", time="ts")["pair_scans"][0]  # type: ignore[index]
        reduction = scan["quadratic_sse_reduction_fraction"]
        ok = scan["n"] == 20 and scan["dropped_rows"] == 0 and "ISO 8601" in scan["predictor_encoding"]
        ok = ok and reduction is not None and reduction > 0.999999
        return ok, json.dumps(scan)[:300]

    check("ISO 8601 time column is parsed (n=20)", iso_case)

    zulu_text = "ts,y\n" + "".join(
        f"{(start.replace(tzinfo=timezone.utc) + timedelta(seconds=30 * i)).isoformat().replace('+00:00', 'Z')},{i}\n"
        for i in range(6)
    )

    def zulu_case() -> tuple[bool, str]:
        scan = _report_from_text(zulu_text, response="y", time="ts")["pair_scans"][0]  # type: ignore[index]
        slope = scan["linear_fit"]["slope"]  # type: ignore[index]
        return scan["n"] == 6 and abs(slope - 1 / 30) < 1e-12, f"n={scan['n']}, slope={slope}"

    check("ISO timestamps with a Z suffix are parsed", zulu_case)

    expect_input_error(
        "time column with no readable value exits with a clear error",
        "ts,y\nn/a,1\nn/a,2\nn/a,3\n",
        "no usable rows for predictor 'ts'",
        response="y",
        time="ts",
    )
    expect_input_error("non-numeric response is an input error", "t,y\n1,a\n2,b\n", "has no numeric values", response="y", time="t")
    expect_input_error("missing column is an input error", "t,y\n1,2\n", "missing CSV column(s): temp", response="y", temperature="temp")
    expect_input_error(
        "naive and offset timestamps cannot be mixed",
        "ts,y\n2026-09-01T10:00:00,1\n2026-09-01T10:01:00+00:00,2\n2026-09-01T10:02:00,3\n",
        "with and without a UTC offset",
        response="y",
        time="ts",
    )

    def dropped_case() -> tuple[bool, str]:
        text = "t,y\n0,1.0\n1,\n2,3.1\n3,3.9\n4,5.2\n"
        scan = _report_from_text(text, response="y", time="t")["pair_scans"][0]  # type: ignore[index]
        ok = scan["n"] == 4 and scan["dropped_rows"] == 1 and any("1 of 5 rows dropped" in w for w in scan["warnings"])
        return ok, json.dumps(scan)[:300]

    check("a row with an empty response is counted and warned", dropped_case)

    def exact_linear_case() -> tuple[bool, str]:
        text = "t,y\n" + "".join(f"{1.7e9 + i},{2.0 * i + 1.0}\n" for i in range(10))
        scan = _report_from_text(text, response="y", time="t")["pair_scans"][0]  # type: ignore[index]
        ok = scan["quadratic_sse_reduction_fraction"] is None and any("already leaves no residual" in w for w in scan["warnings"])
        return ok, json.dumps(scan)[:300]

    check("exactly linear data reports no reduction instead of a spurious value", exact_linear_case)

    failed = 0
    for name, ok, detail in outcomes:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  [{detail}]"))
        failed += 0 if ok else 1
    print(f"selftest: {len(outcomes) - failed}/{len(outcomes)} passed")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_file", type=Path, nargs="?")
    parser.add_argument("--response")
    parser.add_argument("--time", help="time or acquisition-order column: numbers, or ISO 8601 timestamps")
    parser.add_argument("--temperature")
    parser.add_argument("--parameter", action="append", default=[])
    parser.add_argument("--group")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--selftest", action="store_true", help="run the built-in regression cases and exit")
    args = parser.parse_args()

    if args.selftest:
        return run_selftest()
    if args.csv_file is None or not args.response:
        parser.error("csv_file and --response are required (or use --selftest)")

    try:
        with args.csv_file.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fieldnames = reader.fieldnames
        report = build_report(
            rows,
            fieldnames,
            str(args.csv_file),
            args.response,
            time=args.time,
            temperature=args.temperature,
            parameters=args.parameter,
            group=args.group,
        )
    except (InputError, OSError, UnicodeDecodeError, csv.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
