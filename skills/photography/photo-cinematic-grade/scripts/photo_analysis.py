# Read-only analysis of normalized RGB8 pixels. No creative parameters.
# Hue sectors follow the conventional six-piece RGB-to-HSV definition:
# https://docs.python.org/3/library/colorsys.html
# https://github.com/python/cpython/blob/v3.13.0/Lib/colorsys.py
# This is a new engineering implementation of AUDIT 3.2, not prototype 0.4.1.
from __future__ import annotations

import hashlib
import math

from PIL import Image

from image_io import InputError, load_image

ANALYSIS_VERSION = "0.20.0"
HUE_SECTORS = ("red_to_yellow", "yellow_to_green", "green_to_cyan",
               "cyan_to_blue", "blue_to_magenta", "magenta_to_red")


def measure_pixels(image):
    # Encoded-sRGB HSV is descriptive, not perceptually uniform color science.
    # Bin edges are the SIX algebraic HSV sectors, not fitted scene thresholds.
    if not isinstance(image, Image.Image) or image.mode != "RGB":
        raise InputError("analysis requires normalized 8-bit RGB")
    total = image.width * image.height
    if total == 0:
        raise InputError("analysis requires a nonempty image")
    raw = image.tobytes()
    counts = [0] * len(HUE_SECTORS)
    achromatic = 0
    saturation_counts = {}
    pixels = iter(raw)
    for r, g, b in zip(pixels, pixels, pixels):
        high, low = max(r, g, b), min(r, g, b)
        delta = high - low
        if delta == 0:
            achromatic += 1
            continue
        # Exact floor(H / 60) avoids rounding at sector boundaries. The six
        # cases and modulo are the RGB-to-HSV hexagon definition. Tied maxima
        # fall on the next sector; gray has undefined hue and is excluded.
        if high == r:
            sector = ((g - b) // delta) % 6
        elif high == g:
            sector = (b - r) // delta + 2
        else:
            sector = (r - g) // delta + 4
        counts[sector] += 1
        key = (delta, high)
        saturation_counts[key] = saturation_counts.get(key, 0) + 1
    chromatic = total - achromatic
    # Aggregate exact integer frequencies, then sum in fixed order. This
    # avoids spatial-order-dependent floating accumulation or pixel sampling.
    mean_saturation = math.fsum(
        count * (delta / high) / total
        for (delta, high), count in sorted(saturation_counts.items()))
    histogram = image.histogram()
    sums = [sum(code * histogram[channel * 256 + code] for code in range(256))
            for channel in range(3)]
    sum_channels = sum(sums)
    return {
        "scope": "all_exif_oriented_icc_normalized_srgb8_pixels",
        "dimensions": list(image.size), "pixel_count": total,
        "pixel_sha256": hashlib.sha256(raw).hexdigest(),
        "hue_families": {
            "method": "encoded_srgb_hsv_six_half_open_sectors_v1",
            "hue_unit": "degrees", "weighting": "equal_pixel_area",
            "achromatic_rule": "R == G == B; hue is undefined",
            "achromatic_pixels": achromatic,
            "achromatic_fraction": achromatic / total,
            "chromatic_pixels": chromatic,
            "minimum_saturation_filter": None,
            "sectors": [
                {"id": name, "hue_range_degrees": [60 * index, 60 * (index + 1)],
                 "range_closure": "left_closed_right_open",
                 "pixels": counts[index], "fraction_of_all_pixels": counts[index] / total,
                 "fraction_of_chromatic_pixels": counts[index] / chromatic if chromatic else None}
                for index, name in enumerate(HUE_SECTORS)
            ],
        },
        "saturation": {
            "method": "HSV_S = (max_RGB - min_RGB) / max_RGB; black is zero",
            "mean_all_pixels": mean_saturation,
        },
        "color_cast_evidence": {
            "method": "global_encoded_rgb_channel_means_and_centered_offsets",
            "channel_order": ["r", "g", "b"], "unit": "8bit_srgb_code_value",
            "mean_rgb": [value / total for value in sums],
            "channel_offsets_from_mean": [(3 * value - sum_channels) / (3 * total) for value in sums],
            "neutral_reference_provided": False,
            "cast_verdict": None, "white_balance_correction": None,
            "reason": "scene colors and illumination cannot be separated from global channel means alone",
        },
        "limitations": [
            "HSV sectors describe encoded RGB; they are not OkLCh hue bands or perceptual color names",
            "all non-gray pixels count equally, including one-code chroma and encoding noise",
            "global channel imbalance is not proof of a color cast; balanced means do not prove neutral lighting",
            "no gray-world assumption, neutral-patch detection, skin detection or automatic correction",
            "measurements follow ICC conversion and 8-bit decoding; source gamut loss is not measured",
        ],
    }


def analyze(source, *, assume_srgb=False):
    # Existing loader hashes and decodes the same immutable in-memory snapshot,
    # applies EXIF/ICC, rejects unsafe formats and allowlists technical metadata.
    loaded = load_image(source, assume_srgb=assume_srgb)
    return {
        "schema": "cinegrade-analysis/1", "analysis_version": ANALYSIS_VERSION,
        "status": "complete", "command": "analyze", "input": loaded.provenance,
        "measurements": measure_pixels(loaded.image),
        "selection": {"automatic_selection": False, "selected_look": None,
                      "ranked_looks": None},
        "pending": ["brightness_key_and_dynamic_range", "clipping_diagnosis",
                    "skin_fraction", "scene_dependent_six_look_recommendations"],
        "warnings": loaded.provenance["warnings"],
        "limitations": [
            "read-only partial analysis; existing candidates and rendering are unchanged",
            "no exposure, white-balance, skin-tone, aesthetic or real-photo acceptance verdict",
            "six planned looks and full floating CLI integration remain pending",
            "historical prototype 0.4.1 was not recovered or reproduced",
            "report contains content hashes and allowlisted technical metadata; share deliberately",
        ],
    }
