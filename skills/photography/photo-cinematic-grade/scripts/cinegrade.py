#!/usr/bin/env python3
"""Deterministic SDR grading: render, candidate previews, comparisons and QA.

Pixel math uses integers in encoded sRGB, not scene-linear film simulation.
Comparisons use exact full-size before/after panels. LUT export/readback covers the existing integer looks; cards remain pending.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys

import PIL
from PIL import Image, ImageCms

from image_io import InputError, encode_png, load_image, write_new_bundle, write_new_run

# Preserve the legacy receipt version contract; the optional exporter has its own version.
VERSION = '0.4.0'
PNG16_EXPORT_VERSION = "0.18.0"
ALGORITHM = 'encoded-srgb-integer-v1'
CANDIDATE_LOOKS = ('neutral', 'warm-muted', 'cool-muted')
MAX_PREVIEW_EDGE = 2048
LOOK_LIBRARY = Path(__file__).resolve().parent.parent / 'references' / 'look-library.json'


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def load_looks(path=LOOK_LIBRARY):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise InputError('cannot load look library') from None
    if not isinstance(data, dict) or set(data) != {'schema_version', 'looks'} or data['schema_version'] != 1:
        raise InputError('invalid look library schema')
    looks = data['looks']
    if not isinstance(looks, dict) or not looks:
        raise InputError('look library must not be empty')
    for name, recipe in looks.items():
        if not isinstance(name, str) or not name or not isinstance(recipe, dict):
            raise InputError('invalid look name or recipe')
        if set(recipe) != {'label', 'curve', 'shadow_rgb', 'highlight_rgb', 'saturation_percent'}:
            raise InputError('look recipe has missing or unknown keys')
        if not isinstance(recipe['label'], str) or not recipe['label']:
            raise InputError('look recipe needs a label')
        curve = recipe['curve']
        if not isinstance(curve, list) or len(curve) < 2 or any(
            not isinstance(point, list) or len(point) != 2 or
            not all(_integer(v, 0, 255) for v in point) for point in curve
        ):
            raise InputError('curve requires integer [input, output] points from 0 to 255')
        if curve[0][0] != 0 or curve[-1][0] != 255 or any(
            a[0] >= b[0] or a[1] > b[1] for a, b in zip(curve, curve[1:])
        ):
            raise InputError('curve must cover 0..255 with increasing x and nondecreasing y')
        for key in ('shadow_rgb', 'highlight_rgb'):
            value = recipe[key]
            if not isinstance(value, list) or len(value) != 3 or not all(_integer(v, -16, 16) for v in value):
                raise InputError('split-tone offsets must be three integers within -16..16')
        if not _integer(recipe['saturation_percent'], 0, 120):
            raise InputError('saturation must be an integer within 0..120')
    return looks


def round_div(value, denominator):
    """Nearest integer; exact ties go toward positive infinity, including negatives."""
    return (value + denominator // 2) // denominator


def curve_table(points):
    table = []
    segment = 0
    for x in range(256):
        while x > points[segment + 1][0]:
            segment += 1
        left, right = points[segment:segment + 2]
        table.append(left[1] + round_div((x - left[0]) * (right[1] - left[1]), right[0] - left[0]))
    return table


def _clamp_qa(total, mapped, strength):
    # Plan 3.5: count affected PIXELS once, warn strictly above ten percent.
    # The legacy encoded-sRGB pipeline clamps before strength interpolation.
    # This does not call color_core.gamut_map_linear_srgb or measure ICC loss.
    return {
        "algorithm": "encoded-srgb-channel-clamp-v1",
        "scope": "full_strength_before_strength_mix",
        "applied": strength != 0,
        "pixels_total": total,
        "pixels_mapped": mapped,
        "mapped_fraction": mapped / total,
        "warning_threshold_fraction": 0.1,
        "warnings": ["encoded_srgb_clamped_fraction_above_10_percent"] if 10 * mapped > total else [],
        "limitations": ["excludes_source_icc_conversion", "not_linear_srgb_mapping",
                        "not_final_output_clipping_or_visual_acceptance"],
    }


def grade_pixels(image, recipe, strength):
    # Preserve the existing two-result API and its channel-sample count.
    graded, excursions, _ = grade_pixels_with_qa(image, recipe, strength)
    return graded, excursions


def grade_pixels_with_qa(image, recipe, strength):
    # Return legacy pixels, channel excursions and stage-scoped pixel QA.
    # A mapped pixel has at least one full-strength channel outside 0..255.
    # Counts describe the clamp performed BEFORE the requested strength mix,
    # not changed output pixels or recoverable detail. Zero strength bypasses
    # the transform. No new color transform or recipe is applied.

    if image.mode != 'RGB':
        raise InputError('grading core requires normalized 8-bit RGB')
    if not _integer(strength, 0, 100):
        raise InputError('strength must be an integer within 0..100')
    total = image.width * image.height
    if total == 0:
        raise InputError("grading QA requires a nonempty image")
    source = image.tobytes()
    if strength == 0:
        return Image.frombytes("RGB", image.size, source), 0, _clamp_qa(total, 0, strength)
    tone = curve_table(recipe['curve'])
    tables = []
    for shadow, highlight in zip(recipe['shadow_rgb'], recipe['highlight_rgb']):
        tables.append([v + round_div(shadow * (255 - v) + highlight * v, 255) for v in tone])
    red, green, blue = tables
    saturation = recipe['saturation_percent']
    result = bytearray(len(source))
    excursion_count = 0
    mapped_pixels = 0
    for i in range(0, len(source), 3):
        channels = (red[source[i]], green[source[i + 1]], blue[source[i + 2]])
        # Approximate luma weights on encoded values, deliberately not luminance.
        luma = round_div(54 * channels[0] + 183 * channels[1] + 19 * channels[2], 256)
        pixel_mapped = False
        for c, value in enumerate(channels):
            graded = luma + round_div((value - luma) * saturation, 100)
            outside = graded < 0 or graded > 255
            excursion_count += outside
            pixel_mapped |= outside
            bounded = min(255, max(0, graded))
            result[i + c] = round_div(source[i + c] * (100 - strength) + bounded * strength, 100)
        mapped_pixels += pixel_mapped
    return (Image.frombytes("RGB", image.size, bytes(result)), excursion_count,
            _clamp_qa(total, mapped_pixels, strength))


def endpoint_qa(image):
    total = image.width * image.height
    histogram = image.histogram()
    return {
        'pixel_count': total,
        'channel_endpoints': {
            channel: {'at_0': histogram[offset], 'at_255': histogram[offset + 255]}
            for channel, offset in (('r', 0), ('g', 256), ('b', 512))
        },
        'meaning': 'endpoint counts are signals, not proof of clipping or lost detail',
    }


def render(source, output, *, look='warm-muted', strength=60, assume_srgb=False, bit_depth=8):
    # Refuse occupied output even when it is an empty directory or dangling link.
    target = Path(output)
    if target.exists() or target.is_symlink():
        raise InputError('output already exists; choose a new directory')
    if not _integer(strength, 0, 100):
        raise InputError('strength must be an integer within 0..100')
    if type(bit_depth) is not int or bit_depth not in (8, 16):
        raise InputError("bit-depth must be 8 or 16")
    looks = load_looks()
    if look not in looks:
        raise InputError('unknown look; use the looks command')
    loaded = load_image(source, assume_srgb=assume_srgb)
    recipe = looks[look]
    graded, excursions, gamut_qa = grade_pixels_with_qa(loaded.image, recipe, strength)
    if bit_depth == 16:
        import numpy as np
        from srgb16 import encode_png16
        # Lossless 8->16 code expansion: 65535/255 = 257. This adds no detail.
        samples = np.asarray(graded).astype(np.uint16) * 257
        png = encode_png16(samples)
        pixel_bytes = samples.astype(">u2").tobytes()
    else:
        png = encode_png(graded)
        pixel_bytes = graded.tobytes()
    report = {
        'schema_version': 1,
        'status': 'complete',
        'skill_version': VERSION,
        'algorithm': ALGORITHM,
        'input': loaded.provenance,
        'grade': {'look': look, 'strength_percent': strength, 'recipe': recipe},
        'output': {
            'file': 'render.png', 'format': 'PNG', 'mode': 'RGB',
            'dimensions': list(graded.size), 'color_space': 'sRGB',
            'png_sha256': hashlib.sha256(png).hexdigest(),
            'pixel_sha256': hashlib.sha256(pixel_bytes).hexdigest(),
            'source_metadata_copied': False,
        },
        'qa': {
            'before': endpoint_qa(loaded.image), 'after': endpoint_qa(graded),
            "gamut_mapping": gamut_qa,
            "full_strength_pre_clamp_channel_samples": excursions,
            'channel_sample_count': graded.width * graded.height * 3,
            'human_review_required': ['skin_and_memory_colors', 'highlight_detail', 'shadow_detail', 'banding'],
            'warnings': (['grade_out_of_range_before_clamp'] if excursions else []),
        },
        'environment': {
            'python': platform.python_version(), 'pillow': PIL.__version__,
            'littlecms': ImageCms.core.littlecms_version,
        },
        'limitations': [
            '8-bit encoded-sRGB creative transform, not a film-stock or scene-linear emulation',
            'pixel reproducibility requires the same decode/ICC environment; PNG bytes may differ',
            'ICC conversion may already clip source colors; this QA does not detect source gamut loss',
            'no automatic aesthetic, skin-tone, HDR, or print suitability verdict',
            'metadata privacy is not visual anonymization; review visible identifying details separately',
            'the sidecar contains content hashes and technical values; keep private unless needed',
        ],
    }
    if bit_depth == 16:
        from srgb16 import PROFILE_SHA256
        report["output"].update({
            "export_version": PNG16_EXPORT_VERSION,
            "bit_depth": 16, "sample_encoding": "RGB_uint16_big_endian_row_major",
            "icc_sha256": PROFILE_SHA256,
            "precision": {"source_bits": 8, "grading_bits": 8,
                          "expansion": "uint8_times_257", "adds_detail": False},
        })
        report["qa"]["reference_samples"] = "legacy_RGB8_before_lossless_16bit_expansion"
        report["qa"]["warnings"].append("16bit_container_from_8bit_grade_no_added_precision")
        report["limitations"].append(
            "16-bit file preserves the legacy 8-bit grade exactly; full floating CLI integration is pending")
    receipt = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + '\n').encode('utf-8')
    write_new_run(output, png, receipt)
    return report


def candidate_preview(image, max_edge):
    """Resize normalized RGB once, without upscaling or implicit auto-enhancement."""
    if image.mode != 'RGB':
        raise InputError('candidate preview requires normalized 8-bit RGB')
    if not _integer(max_edge, 1, MAX_PREVIEW_EDGE):
        raise InputError('max-edge must be an integer within 1..2048')
    longest = max(image.size)
    if longest <= max_edge:
        preview = Image.frombytes('RGB', image.size, image.tobytes())
        resampling = 'none'
    else:
        size = tuple(max(1, round_div(d * max_edge, longest)) for d in image.size)
        preview = image.resize(size, resample=Image.Resampling.LANCZOS, reducing_gap=None)
        resampling = 'pillow-lanczos'
    return preview, {
        'max_edge': max_edge, 'dimensions': list(preview.size),
        'resampling': resampling, 'reducing_gap': None,
        'dimension_rounding': 'nearest_integer_ties_up_minimum_1',
        'upscaled': False, 'working_space': 'encoded_sRGB',
        'processing_order': ['exif_orientation', 'normalize_srgb', 'resize', 'grade'],
    }


def candidates(source, output, *, strength=60, max_edge=1024, assume_srgb=False, distinction_qa=False):
    """One input snapshot, three fixed-order previews, one final completion receipt."""
    target = Path(output)
    if target.exists() or target.is_symlink():
        raise InputError('output already exists; choose a new directory')
    if not _integer(strength, 0, 100):
        raise InputError('strength must be an integer within 0..100')
    if not _integer(max_edge, 1, MAX_PREVIEW_EDGE):
        raise InputError('max-edge must be an integer within 1..2048')
    looks = load_looks()
    if any(name not in looks for name in CANDIDATE_LOOKS):
        raise InputError('candidate look library requires neutral, warm-muted and cool-muted')
    loaded = load_image(source, assume_srgb=assume_srgb)
    preview, resize_record = candidate_preview(loaded.image, max_edge)
    images, records = {}, []
    measured_styles = {}
    for index, name in enumerate(CANDIDATE_LOOKS, 1):
        amount = 0 if name == 'neutral' else strength
        graded, excursions, gamut_qa = grade_pixels_with_qa(preview, looks[name], amount)
        png = encode_png(graded)
        filename = f'{index:02d}-{name}.png'
        images[filename] = png
        if distinction_qa and name != "neutral":
            import numpy as np
            measured_styles[name] = np.asarray(graded, dtype=np.float64) / 255
        records.append({
            'grade': {'look': name, 'strength_percent': amount, 'recipe': looks[name]},
            'output': {
                'file': filename, 'format': 'PNG', 'mode': 'RGB',
                'dimensions': list(graded.size), 'color_space': 'sRGB',
                'png_sha256': hashlib.sha256(png).hexdigest(),
                'pixel_sha256': hashlib.sha256(graded.tobytes()).hexdigest(),
                'source_metadata_copied': False,
            },
            'qa': {
                'after': endpoint_qa(graded),
                "gamut_mapping": gamut_qa,
                "full_strength_pre_clamp_channel_samples": excursions,
                'channel_sample_count': graded.width * graded.height * 3,
                'warnings': ['grade_out_of_range_before_clamp'] if excursions else [],
            },
        })
    report = {
        'schema_version': 1, 'status': 'complete', 'command': 'candidates',
        'skill_version': VERSION, 'algorithm': ALGORITHM,
        'input': loaded.provenance, 'preview': resize_record,
        'candidates': records,
        'qa': {
            'scope': 'resized_preview_only', 'before': endpoint_qa(preview),
            'human_review_required': ['skin_and_memory_colors', 'highlight_detail', 'shadow_detail', 'banding'],
        },
        'selection': {'automatic_selection': False, 'selected_look': None},
        'environment': {
            'python': platform.python_version(), 'pillow': PIL.__version__,
            'littlecms': ImageCms.core.littlecms_version,
        },
        'limitations': [
            'candidate previews are for choosing a direction, not full-resolution deliverables',
            'resize precedes grading; a resized full-resolution render can have different pixels',
            'preview QA cannot certify full-resolution detail, banding, skin tones or aesthetics',
            '8-bit encoded-sRGB creative transform, not a film-stock or scene-linear emulation',
            'pixel reproducibility requires the same decode/ICC/resize environment; PNG bytes may differ',
            'ICC conversion may already clip source colors; this QA does not detect source gamut loss',
            'metadata privacy is not visual anonymization; review visible identifying details separately',
            'the sidecar contains content hashes and technical values; keep private unless needed',
        ],
    }
    if distinction_qa:
        from style_distinction import style_distinction_qa
        # Existing muted recipes are not the six planned vivid looks.
        # Original distances are reference-only, not a vivid-style pass.
        report["qa"]["style_distinction"] = style_distinction_qa(
            np.asarray(preview, dtype=np.float64) / 255, measured_styles, vivid_styles=[])
        report["qa"]["style_distinction"]["scope"] = "resized_preview_only"
        report["qa"]["style_distinction"]["limitations"].append(
            "existing_muted_candidates_are_not_the_six_planned_looks")
    receipt = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + '\n').encode('utf-8')
    write_new_bundle(output, images, receipt)
    return report



def compare(source, output, *, look, strength, assume_srgb=False):
    """Full-resolution before/after pair; caller explicitly selects look and strength."""
    target = Path(output)
    if target.exists() or target.is_symlink():
        raise InputError("output already exists; choose a new directory")
    if not _integer(strength, 0, 100):
        raise InputError("strength must be an integer within 0..100")
    looks = load_looks()
    if look not in looks:
        raise InputError("unknown look; use the looks command")
    loaded = load_image(source, assume_srgb=assume_srgb)
    original = loaded.image
    recipe = looks[look]
    graded, excursions, gamut_qa = grade_pixels_with_qa(original, recipe, strength)
    width, height = original.size
    # Exact abutting panels, no resize/crop/text/gutter or extra color transform.
    # The 2x width is a layout consequence, not a new aesthetic coefficient.
    pair = Image.new("RGB", (2 * width, height))
    pair.paste(original, (0, 0))
    pair.paste(graded, (width, 0))
    png = encode_png(pair)
    report = {
        "schema_version": 1, "status": "complete", "command": "compare",
        "skill_version": VERSION, "algorithm": ALGORITHM,
        "input": loaded.provenance,
        "grade": {"look": look, "strength_percent": strength, "recipe": recipe},
        "output": {
            "file": "compare.png", "format": "PNG", "mode": "RGB",
            "dimensions": list(pair.size), "color_space": "sRGB",
            "png_sha256": hashlib.sha256(png).hexdigest(),
            "pixel_sha256": hashlib.sha256(pair.tobytes()).hexdigest(),
            "source_metadata_copied": False,
        },
        "panels": [
            {"role": "before", "box_xywh": [0, 0, width, height],
             "pixel_sha256": hashlib.sha256(original.tobytes()).hexdigest()},
            {"role": "after", "box_xywh": [width, 0, width, height],
             "pixel_sha256": hashlib.sha256(graded.tobytes()).hexdigest()},
        ],
        "layout": {
            "order": "before_left_after_right", "resampling": "none",
            "cropped": False, "text_overlay": False,
            "processing_order": ["exif_orientation", "normalize_srgb", "grade", "pair"],
        },
        "qa": {
            "scope": "full_resolution_panels",
            "gamut_mapping": gamut_qa,
            "before": endpoint_qa(original), "after": endpoint_qa(graded),
            "full_strength_pre_clamp_channel_samples": excursions,
            "channel_sample_count": width * height * 3,
            "human_review_required": ["skin_and_memory_colors", "highlight_detail", "shadow_detail", "banding"],
            "warnings": ["grade_out_of_range_before_clamp"] if excursions else [],
        },
        "environment": {
            "python": platform.python_version(), "pillow": PIL.__version__,
            "littlecms": ImageCms.core.littlecms_version,
        },
        "limitations": [
            "before means EXIF-oriented, ICC-normalized sRGB pixels, not the original file bytes",
            "after matches render pixels only with the same source snapshot, recipe, strength and environment",
            "the pair has two full-size panels; a viewer may scale it down, inspect at 1:1 for detail",
            "8-bit encoded-sRGB creative transform, not a film-stock or scene-linear emulation",
            "pixel reproducibility requires the same decode/ICC environment; PNG bytes may differ",
            "ICC conversion may already clip source colors; this QA does not detect source gamut loss",
            "no automatic aesthetic, skin-tone, HDR, or print suitability verdict",
            "metadata privacy is not visual anonymization; review visible identifying details separately",
            "the sidecar contains content hashes and technical values; keep private unless needed",
        ],
    }
    receipt = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    write_new_bundle(output, {"compare.png": png}, receipt)
    return report


def _qa_warnings(qa):
    # Preserve legacy report warnings; surface additive stage warnings in CLI.
    return qa["warnings"] + qa["gamut_mapping"]["warnings"]


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selftest', action='store_true', help='run synthetic grading/CLI tests')
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('looks', help='print the bundled recipes as JSON')
    command = sub.add_parser('render', help='write render.png + privacy-safe report.json into a NEW directory')
    command.add_argument('source', type=Path)
    command.add_argument('--output', required=True, type=Path, help='new run directory; parent must exist')
    command.add_argument('--look', default='warm-muted')
    command.add_argument('--strength', type=int, default=60, help='integer 0..100 (default: 60)')
    command.add_argument('--assume-srgb', action='store_true', help='explicitly confirm sRGB for an untagged source')
    command.add_argument("--bit-depth", type=int, choices=(8, 16), default=8,
                             help="PNG sample depth; 16 expands the existing 8-bit grade without adding detail")
    command = sub.add_parser('candidates', help='write three candidate PNGs + report.json into a NEW directory')
    command.add_argument('source', type=Path)
    command.add_argument('--output', required=True, type=Path, help='new run directory; parent must exist')
    command.add_argument('--strength', type=int, default=60, help='style strength 0..100; neutral stays 0 (default: 60)')
    command.add_argument('--max-edge', type=int, default=1024, help='preview long-edge cap 1..2048; never upscale (default: 1024)')
    command.add_argument('--assume-srgb', action='store_true', help='explicitly confirm sRGB for an untagged source')

    command.add_argument("--distinction-qa", action="store_true",
                         help="measure preview Oklab style separation; original thresholds are reference-only for muted looks")

    command = sub.add_parser("compare", help="write full-resolution before-left/after-right compare.png + report.json")
    command.add_argument("source", type=Path)
    command.add_argument("--output", required=True, type=Path, help="new run directory; parent must exist")
    command.add_argument("--look", required=True, help="explicitly selected look; no automatic selection")
    command.add_argument("--strength", required=True, type=int, help="explicitly selected integer 0..100")
    command.add_argument("--assume-srgb", action="store_true", help="explicitly confirm sRGB for an untagged source")
    command = sub.add_parser("lut", help="export 33-cube for an existing integer look; QA every supplied source pixel")
    command.add_argument("source", type=Path)
    command.add_argument("--output", required=True, type=Path, help="NEW directory for grade.cube and measured report.json")
    command.add_argument("--look", required=True, help="existing look, explicitly selected; not the six planned looks")
    command.add_argument("--strength", required=True, type=int, help="explicitly selected integer 0..100")
    command.add_argument("--assume-srgb", action="store_true", help="explicitly confirm sRGB for an untagged source")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.selftest:
        if args.command:
            parser.error('--selftest cannot be combined with a command')
        from test_cinegrade import run_tests
        return run_tests('grade')
    try:
        if args.command == 'looks':
            print(json.dumps(load_looks(), ensure_ascii=False, indent=2, sort_keys=True))
        elif args.command == 'render':
            report = render(args.source, args.output, look=args.look,
                            strength=args.strength, assume_srgb=args.assume_srgb, bit_depth=args.bit_depth)
            print(json.dumps({'status': 'complete', 'output': 'render.png',
                              'look': args.look, 'pixel_sha256': report['output']['pixel_sha256'],
                              'warnings': report['input']['warnings'] + _qa_warnings(report["qa"])}))
        elif args.command == 'candidates':
            report = candidates(args.source, args.output, strength=args.strength,
                                max_edge=args.max_edge, assume_srgb=args.assume_srgb, distinction_qa=args.distinction_qa)
            print(json.dumps({
                'status': 'complete', 'command': 'candidates',
                'outputs': [item['output']['file'] for item in report['candidates']],
                'dimensions': report['preview']['dimensions'], 'automatic_selection': False,
                'warnings': sorted(set(report['input']['warnings'] + [
                    warning for item in report["candidates"] for warning in _qa_warnings(item["qa"])]
                    + report["qa"].get("style_distinction", {}).get("warnings", []))),
            }))

        elif args.command == "compare":
            report = compare(args.source, args.output, look=args.look,
                             strength=args.strength, assume_srgb=args.assume_srgb)
            print(json.dumps({
                "status": "complete", "command": "compare", "output": "compare.png",
                "dimensions": report["output"]["dimensions"],
                "look": args.look, "strength_percent": args.strength,
                "pixel_sha256": report["output"]["pixel_sha256"],
                "warnings": report["input"]["warnings"] + _qa_warnings(report["qa"]),
            }))
        elif args.command == "lut":
            from cinegrade_lut import export_lut
            report = export_lut(args.source, args.output, look=args.look,
                                strength=args.strength, assume_srgb=args.assume_srgb)
            print(json.dumps({
                "status": report["status"], "command": "lut", "output": "grade.cube",
                "cube_sha256": report["output"]["cube_sha256"],
                "qa": report["qa"], "warnings": report["input"]["warnings"],
            }, allow_nan=False))
            return 0 if report["qa"]["pass"] else 1
        else:
            parser.print_help()
        return 0
    except InputError as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
