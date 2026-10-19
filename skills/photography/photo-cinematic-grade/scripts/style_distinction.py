# Measured style separation for AUDIT-AND-IDEAS.md 3.5.
# Rebuilt implementation, NOT recovered historical 0.4.1 code or results.
# Definition: arithmetic mean of per-pixel Euclidean distances in normalized
# Oklab D65. The plan specifies thresholds, not an aggregation implementation;
# this explicit engineering definition is not a recovered prototype metric.
# All aligned supplied pixels are measured. No sampling, registration, resize,
# color-space guessing, creative parameters or automatic style selection.
from collections.abc import Mapping
from itertools import combinations
import re

import numpy as np

from color_core import linear_srgb_to_oklab, srgb_to_linear
from image_io import InputError

VERSION = "0.19.0"
ORIGINAL_MINIMUM = 0.035  # Plan 3.5: vivid styles versus the original.
PAIR_MINIMUM = 0.025      # Plan 3.5: any two styles, excluding the original.


def _image(value):
    try:
        raw = np.asarray(value)
        if raw.dtype.kind not in "iuf" or raw.ndim != 3 or raw.shape[-1] != 3 or not raw.size:
            raise ValueError
        rgb = raw.astype(np.float64, copy=True)
        if not np.all(np.isfinite(rgb)) or np.any((rgb < 0) | (rgb > 1)):
            raise ValueError
    except (ValueError, TypeError, OverflowError):
        raise InputError("distinction requires nonempty H x W x 3 encoded-sRGB arrays in 0..1") from None
    return rgb


def _criterion(distance, limit, applicable):
    # Inclusive threshold; no epsilon that could silently relax the plan.
    meets = distance >= limit
    return {"mean_delta_e_ok": distance, "minimum": limit,
            "criterion_applicable": applicable, "meets_reference": meets,
            "pass": meets if applicable else None}


def style_distinction_qa(original, styles, *, vivid_styles):
    # styles maps stable IDs to aligned encoded-sRGB float images. Include only
    # actual styles, not the original baseline. The caller explicitly identifies
    # vivid styles; an empty list measures original distances for reference only.
    # The API cannot establish scene alignment, ICC provenance or style identity.
    if not isinstance(styles, Mapping) or not styles:
        raise InputError("distinction requires at least one named style")
    names = list(styles)
    if any(not isinstance(name, str) or re.fullmatch(r"[a-z][a-z0-9_-]*", name) is None for name in names):
        raise InputError("style IDs must be lowercase ASCII identifiers")
    if not isinstance(vivid_styles, (list, tuple)) or any(not isinstance(x, str) for x in vivid_styles):
        raise InputError("vivid_styles must be an explicit list or tuple of style IDs")
    if len(set(vivid_styles)) != len(vivid_styles) or not set(vivid_styles).issubset(names):
        raise InputError("vivid style IDs must be unique and present in styles")
    source = _image(original)
    lab_source = linear_srgb_to_oklab(srgb_to_linear(source))
    labs = {}
    for name in names:
        rgb = _image(styles[name])
        if rgb.shape != source.shape:
            raise InputError("distinction images must have identical aligned dimensions")
        labs[name] = linear_srgb_to_oklab(srgb_to_linear(rgb))

    def distance(left, right):
        difference = left - right
        # Mean of distances, NOT distance of mean colors (which can cancel).
        return float(np.mean(np.sqrt(np.sum(difference * difference, axis=-1))))

    originals, pairs, warnings = [], [], []
    for name in names:
        check = _criterion(distance(lab_source, labs[name]), ORIGINAL_MINIMUM, name in vivid_styles)
        originals.append({"style": name, **check})
        if check["pass"] is False:
            warnings.append("vivid_style_below_original_distinction:" + name)
    for first, second in combinations(names, 2):
        check = _criterion(distance(labs[first], labs[second]), PAIR_MINIMUM, True)
        pairs.append({"styles": [first, second], **check})
        if not check["pass"]:
            warnings.append("styles_below_pairwise_distinction:" + first + ":" + second)
    if len(names) < 2:
        warnings.append("pairwise_distinction_not_evaluated_fewer_than_two_styles")
    return {
        "schema_version": 1, "qa_version": VERSION,
        "algorithm": "mean-pixel-delta-e-ok-v1", "color_space": "Oklab_D65_normalized",
        "pixel_count": int(source.shape[0] * source.shape[1]), "all_supplied_pixels": True,
        "dimensions": [source.shape[1], source.shape[0]],
        "vivid_styles": list(vivid_styles), "original_comparisons": originals,
        "pairwise_comparisons": pairs, "warnings": warnings,
        "limitations": [
            "alignment_and_srgb_provenance_are_caller_supplied",
            "original_threshold_applies_only_to_explicitly_declared_vivid_styles",
            "mean_distance_can_hide_local_skin_or_detail_errors",
            "not_visual_acceptance_or_historical_prototype_reproduction",
        ],
    }
