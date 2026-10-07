#!/usr/bin/env python3
"""Deterministic SDR grading: render, candidate previews and numeric QA.

Pixel math uses integers in encoded sRGB, not scene-linear film simulation.
Contact cards, comparisons and LUT export are not yet shipped.
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

VERSION = '0.2.0'
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


def grade_pixels(image, recipe, strength):
    if image.mode != 'RGB':
        raise InputError('grading core requires normalized 8-bit RGB')
    if not _integer(strength, 0, 100):
        raise InputError('strength must be an integer within 0..100')
    source = image.tobytes()
    if strength == 0:
        return Image.frombytes('RGB', image.size, source), 0
    tone = curve_table(recipe['curve'])
    tables = []
    for shadow, highlight in zip(recipe['shadow_rgb'], recipe['highlight_rgb']):
        tables.append([v + round_div(shadow * (255 - v) + highlight * v, 255) for v in tone])
    red, green, blue = tables
    saturation = recipe['saturation_percent']
    result = bytearray(len(source))
    excursion_count = 0
    for i in range(0, len(source), 3):
        channels = (red[source[i]], green[source[i + 1]], blue[source[i + 2]])
        # Approximate luma weights on encoded values, deliberately not luminance.
        luma = round_div(54 * channels[0] + 183 * channels[1] + 19 * channels[2], 256)
        for c, value in enumerate(channels):
            graded = luma + round_div((value - luma) * saturation, 100)
            excursion_count += graded < 0 or graded > 255
            bounded = min(255, max(0, graded))
            result[i + c] = round_div(source[i + c] * (100 - strength) + bounded * strength, 100)
    return Image.frombytes('RGB', image.size, bytes(result)), excursion_count


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


def render(source, output, *, look='warm-muted', strength=60, assume_srgb=False):
    # Refuse occupied output even when it is an empty directory or dangling link.
    target = Path(output)
    if target.exists() or target.is_symlink():
        raise InputError('output already exists; choose a new directory')
    if not _integer(strength, 0, 100):
        raise InputError('strength must be an integer within 0..100')
    looks = load_looks()
    if look not in looks:
        raise InputError('unknown look; use the looks command')
    loaded = load_image(source, assume_srgb=assume_srgb)
    recipe = looks[look]
    graded, excursions = grade_pixels(loaded.image, recipe, strength)
    png = encode_png(graded)
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
            'pixel_sha256': hashlib.sha256(graded.tobytes()).hexdigest(),
            'source_metadata_copied': False,
        },
        'qa': {
            'before': endpoint_qa(loaded.image), 'after': endpoint_qa(graded),
            'full_strength_pre_clamp_channel_samples': excursions,
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


def candidates(source, output, *, strength=60, max_edge=1024, assume_srgb=False):
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
    for index, name in enumerate(CANDIDATE_LOOKS, 1):
        amount = 0 if name == 'neutral' else strength
        graded, excursions = grade_pixels(preview, looks[name], amount)
        png = encode_png(graded)
        filename = f'{index:02d}-{name}.png'
        images[filename] = png
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
                'full_strength_pre_clamp_channel_samples': excursions,
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
    receipt = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + '\n').encode('utf-8')
    write_new_bundle(output, images, receipt)
    return report


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
    command = sub.add_parser('candidates', help='write three candidate PNGs + report.json into a NEW directory')
    command.add_argument('source', type=Path)
    command.add_argument('--output', required=True, type=Path, help='new run directory; parent must exist')
    command.add_argument('--strength', type=int, default=60, help='style strength 0..100; neutral stays 0 (default: 60)')
    command.add_argument('--max-edge', type=int, default=1024, help='preview long-edge cap 1..2048; never upscale (default: 1024)')
    command.add_argument('--assume-srgb', action='store_true', help='explicitly confirm sRGB for an untagged source')
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
                            strength=args.strength, assume_srgb=args.assume_srgb)
            print(json.dumps({'status': 'complete', 'output': 'render.png',
                              'look': args.look, 'pixel_sha256': report['output']['pixel_sha256'],
                              'warnings': report['input']['warnings'] + report['qa']['warnings']}))
        elif args.command == 'candidates':
            report = candidates(args.source, args.output, strength=args.strength,
                                max_edge=args.max_edge, assume_srgb=args.assume_srgb)
            print(json.dumps({
                'status': 'complete', 'command': 'candidates',
                'outputs': [item['output']['file'] for item in report['candidates']],
                'dimensions': report['preview']['dimensions'], 'automatic_selection': False,
                'warnings': sorted(set(report['input']['warnings'] + [
                    warning for item in report['candidates'] for warning in item['qa']['warnings']])),
            }))
        else:
            parser.print_help()
        return 0
    except InputError as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
