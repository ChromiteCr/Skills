#!/usr/bin/env python3
# 3D .cube export and measured readback for the EXISTING integer SDR renderer.
# Rebuilt plan 3.2/3.5 transport, NOT historical 0.4.1 code or the six looks.
# Input/output coordinates: encoded sRGB [0,1], NOT linear light/log.
# CUBE order: red-fastest, table[blue, green, red, output_channel].
# Only a single uniform 3D table; no 1D shaper or extended domain.
# Format reference: Adobe Cube LUT Specification 1.0 (2013), LUT_3D_SIZE and
# DOMAIN_MIN/MAX. Named format reference, not a claimed network fetch.
# Tetrahedra use six permutations of local RGB coordinate order. Barycentric
# weights are coordinate differences, not fitted creative coefficients.
# No random seed, aesthetic parameter, automatic look choice or spatial effect.
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform

import numpy as np
import PIL
from PIL import Image

from color_core import _RGB_TO_LMS, _LMS_ROOT_TO_LAB, srgb_to_linear
from image_io import InputError, load_image

SIZE = 33  # Plan 3.5. API supports up to 65 (plan 3.9 alternate grid).
MAX_SIZE = 65
P99_LIMIT = 0.02  # Strictly below, per plan 3.5, normalized Delta E OK units.
QA_BATCH = 65536  # Memory batching only, no sampling or measurement change.
ALGORITHM = "cube-red-fastest-tetrahedral-v1"


def _rgb(value):
    try:
        raw = np.asarray(value)
        if raw.dtype.kind not in "iuf" or raw.size == 0 or raw.ndim == 0 or raw.shape[-1] != 3:
            raise ValueError
        rgb = raw.astype(np.float64, copy=True)
        if not np.all(np.isfinite(rgb)) or np.any((rgb < 0) | (rgb > 1)):
            raise ValueError
    except (ValueError, TypeError, OverflowError):
        raise InputError("expected nonempty finite encoded-sRGB triples in 0..1") from None
    return rgb


def _size(size):
    if type(size) is not int or not 2 <= size <= MAX_SIZE:
        raise InputError("3D LUT size must be an integer within 2..65")
    return size


def _table(table):
    table = _rgb(table)
    if table.ndim != 4 or len(set(table.shape[:3])) != 1:
        raise InputError("LUT requires shape (size, size, size, 3) in BGR row order")
    _size(table.shape[0])
    return table


def identity_table(size=SIZE):
    size = _size(size)
    axis = np.linspace(0, 1, size, dtype=np.float64)
    blue, green, red = np.meshgrid(axis, axis, axis, indexing="ij")
    return np.stack((red, green, blue), axis=-1)


def encode_cube(table):
    table = _table(table)
    header = ["# encoded sRGB input/output; red varies fastest",
              f"LUT_3D_SIZE {table.shape[0]}", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"]
    # 17 significant decimal digits round-trip a finite binary64 coordinate.
    rows = [" ".join(format(float(v), ".17g") for v in row) for row in table.reshape(-1, 3)]
    return ("\n".join(header + rows) + "\n").encode("ascii")


def decode_cube(blob):
    # Narrow parser: reject unsupported directives, never silently lose shapers.
    if not isinstance(blob, bytes) or len(blob) > 64 * 1024 * 1024:
        raise InputError("cube requires ASCII bytes within the 64 MiB input limit")
    try:
        text = blob.decode("ascii")
    except UnicodeError:
        raise InputError("cube must be ASCII") from None
    size, fields, rows = None, set(), []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        key = parts[0]
        if key in {"LUT_3D_SIZE", "DOMAIN_MIN", "DOMAIN_MAX"}:
            if key in fields or rows:
                raise InputError("duplicate or late cube directive")
            fields.add(key)
            try:
                if key == "LUT_3D_SIZE":
                    if len(parts) != 2 or not parts[1].isascii() or not parts[1].isdigit():
                        raise ValueError
                    size = _size(int(parts[1]))
                else:
                    values = [float(v) for v in parts[1:]]
                    expected = [0.0] * 3 if key == "DOMAIN_MIN" else [1.0] * 3
                    if values != expected:
                        raise ValueError
            except (ValueError, OverflowError):
                raise InputError("unsupported cube size or domain; requires unit RGB domain") from None
            continue
        if size is None or len(parts) != 3 or len(rows) >= size ** 3:
            raise InputError("unknown cube directive or wrong row count")
        try:
            row = [float(v) for v in parts]
        except ValueError:
            raise InputError("cube data rows must contain three numeric values") from None
        if not all(np.isfinite(v) and 0 <= v <= 1 for v in row):
            raise InputError("cube outputs must be finite encoded sRGB in 0..1")
        rows.append(row)
    if size is None or len(rows) != size ** 3:
        raise InputError("cube data row count does not match LUT_3D_SIZE")
    return np.asarray(rows, dtype=np.float64).reshape(size, size, size, 3)


def _interpolate(table, rgb):
    shape = rgb.shape
    flat = rgb.reshape(-1, 3)
    size = table.shape[0]
    position = flat * (size - 1)
    lower = np.minimum(np.floor(position).astype(np.int64), size - 2)
    fraction = position - lower
    order = np.argsort(-fraction, axis=1, kind="stable")
    sorted_fraction = np.take_along_axis(fraction, order, axis=1)
    n = np.arange(len(flat))
    first = lower.copy()
    first[n, order[:, 0]] += 1
    second = first.copy()
    second[n, order[:, 1]] += 1
    last = lower + 1
    weights = (1 - sorted_fraction[:, 0], sorted_fraction[:, 0] - sorted_fraction[:, 1],
               sorted_fraction[:, 1] - sorted_fraction[:, 2], sorted_fraction[:, 2])
    result = np.zeros_like(flat)
    for vertex, weight in zip((lower, first, second, last), weights):
        result += table[vertex[:, 2], vertex[:, 1], vertex[:, 0]] * weight[:, None]
    return result.reshape(shape)


def tetrahedral(table, encoded):
    # All six tetrahedra, no extrapolation/quantization/clipping. Closed domain.
    # Ties share faces continuously; finite inputs copied, never mutated.
    return _interpolate(_table(table), _rgb(encoded))


def legacy_table(recipe, strength, size=SIZE):
    # Sample the REAL renderer, no fitted/replacement recipe. Round grid nodes
    # to nearest uint8 (ties up) before existing integer transform. A 33-cube
    # cannot encode every discrete discontinuity. Zero strength exports the
    # exact mathematical identity, without grid-node quantization.
    from cinegrade import grade_pixels
    grid = identity_table(size)
    pixels = np.floor(grid.reshape(-1, 3) * 255 + 0.5).astype(np.uint8)
    image = Image.frombytes("RGB", (len(pixels), 1), pixels.tobytes())
    graded, _ = grade_pixels(image, recipe, strength)  # also validates strength
    if strength == 0:
        return grid
    return np.asarray(graded, dtype=np.float64).reshape(grid.shape) / 255


def summarize_errors(errors):
    values = np.asarray(errors)
    if (values.dtype.kind not in "iuf" or values.ndim != 1 or not values.size
            or not np.all(np.isfinite(values)) or np.any(values < 0)):
        raise InputError("QA requires a nonempty vector of finite nonnegative pixel errors")
    p99 = float(np.quantile(values, 0.99, method="linear"))
    return {"metric": "euclidean_delta_e_ok", "units": "normalized_Oklab_D65",
            "pixels_evaluated": int(values.size), "p99": p99,
            "p99_method": "numpy_quantile_linear", "max": float(np.max(values)),
            "mean": float(np.mean(values)), "limit": P99_LIMIT,
            "comparison": "strictly_less_than", "pass": p99 < P99_LIMIT}


def _lab_for_qa(encoded):
    # Use the SAME published matrices as color_core, with an explicit per-pixel
    # sum order. BLAS matrix multiplication changed last-bit rounding with batch
    # shape (observed max first-matrix difference 1.11e-16 on synthetic ramps).
    # Do not round measured errors or weaken the strict batch-invariance test.
    def multiply(rgb, matrix):
        return np.stack([((rgb[..., 0] * row[0] + rgb[..., 1] * row[1])
                          + rgb[..., 2] * row[2]) for row in matrix], axis=-1)
    lms = multiply(srgb_to_linear(encoded), _RGB_TO_LMS)
    return multiply(np.cbrt(lms), _LMS_ROOT_TO_LAB)


def roundtrip_qa(table, source, reference):
    # Every aligned RGB8 pixel; floating unquantized LUT output. No sampling,
    # spatial filtering or smooth-region selection. Supplied-source scope only.
    table = _table(table)
    if (not isinstance(source, Image.Image) or not isinstance(reference, Image.Image)
            or source.mode != "RGB" or reference.mode != "RGB"
            or source.size != reference.size or not source.width * source.height):
        raise InputError("LUT QA requires nonempty aligned RGB8 source and reference images")
    before = np.asarray(source).reshape(-1, 3)
    direct = np.asarray(reference).reshape(-1, 3)
    errors = np.empty(len(before), dtype=np.float64)
    for start in range(0, len(before), QA_BATCH):
        stop = min(start + QA_BATCH, len(before))
        via_lut = _interpolate(table, before[start:stop].astype(np.float64) / 255)
        expected = direct[start:stop].astype(np.float64) / 255
        lab_lut = _lab_for_qa(via_lut)
        lab_direct = _lab_for_qa(expected)
        errors[start:stop] = np.linalg.norm(lab_lut - lab_direct, axis=-1)
    return {**summarize_errors(errors), "scope": "all_pixels_of_supplied_normalized_source",
            "reference": "existing_integer_renderer_RGB8_divided_by_255",
            "lut_output_quantized": False, "interpolation": "tetrahedral",
            "visual_acceptance": "not_evaluated"}


def _write_bytes(path, blob):
    with path.open("xb") as stream:
        stream.write(blob)
        stream.flush()
        os.fsync(stream.fileno())


def export_lut(source, output, *, look, strength, assume_srgb=False):
    # Write grade.cube; publish report.json LAST, never replace a path. Actual
    # disk bytes are verified, parsed and tested against full-size source render.
    # Numerical failures persist as qa_failed, I/O failures as partial output
    # without a final report. No source metadata enters the cube.
    from cinegrade import ALGORITHM as GRADE_ALGORITHM, grade_pixels, load_looks
    target = Path(output)
    if target.exists() or target.is_symlink():
        raise InputError("output already exists; choose a new directory")
    if type(strength) is not int or not 0 <= strength <= 100:
        raise InputError("strength must be an integer within 0..100")
    looks = load_looks()
    if not isinstance(look, str) or look not in looks:
        raise InputError("unknown look; use the looks command")
    recipe = looks[look]
    loaded = load_image(source, assume_srgb=assume_srgb)
    reference, _ = grade_pixels(loaded.image, recipe, strength)
    blob = encode_cube(legacy_table(recipe, strength))
    try:
        target.mkdir(mode=0o700, parents=False, exist_ok=False)
    except OSError:
        raise InputError("output must be a new directory under an existing writable parent") from None
    try:
        _write_bytes(target / "grade.cube", blob)
        readback = (target / "grade.cube").read_bytes()
        if readback != blob:
            raise InputError("written cube differs from generated bytes; preserve partial output")
        qa = roundtrip_qa(decode_cube(readback), loaded.image, reference)
        report = {
            "schema_version": 1, "command": "lut", "algorithm": ALGORITHM,
            "status": "complete" if qa["pass"] else "qa_failed", "input": loaded.provenance,
            "grade": {"algorithm": GRADE_ALGORITHM, "look": look,
                      "strength_percent": strength, "recipe": recipe},
            "output": {"file": "grade.cube", "size": SIZE,
                       "cube_sha256": hashlib.sha256(readback).hexdigest(),
                       "readback": "disk_bytes_verified_before_QA",
                       "domain": [0, 1], "input_space": "encoded_sRGB",
                       "output_space": "encoded_sRGB", "row_order": "red_fastest",
                       "source_metadata_copied": False},
            "qa": qa,
            "environment": {"python": platform.python_version(), "numpy": np.__version__,
                            "pillow": PIL.__version__},
            "limitations": [
                "existing three integer SDR recipes only; not the planned six floating looks",
                "historical 0.4.1 prototype not recovered or reproduced",
                "33-cube interpolates nearest-uint8 sampled integer grades; not pixel-exact",
                "QA covers this supplied source only, not all RGB colors or other photos",
                "no spatial effects, ICC transform, EXIF handling or dither stored in cube",
                "apply to normalized encoded sRGB with tetrahedral interpolation, not log/HDR",
                "application interpolation and color management require separate verification",
                "skin, banding and photographic aesthetics not accepted by this LUT test",
                "sidecar contains hashes and technical data; keep private unless needed",
            ],
        }
        receipt = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True,
                              allow_nan=False) + "\n").encode("utf-8")
        pending = target / ".report.pending"
        _write_bytes(pending, receipt)
        os.link(pending, target / "report.json")
        try:
            pending.unlink()
        except OSError:
            pass
    except OSError:
        raise InputError("output write/readback failed; preserve partial directory") from None
    return report
