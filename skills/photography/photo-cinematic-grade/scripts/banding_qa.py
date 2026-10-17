# Quantization residual QA for caller-supplied encoded-sRGB quantization pairs.
# Reimplemented from plan 3.5, not recovered from the historical prototype.
# Requires the ACTUAL pre-quantization references and post-quantization pixels.
# An 8-bit file cannot reveal its lost, original continuous signal. Passing a
# decoded RGB8 image / 255 as a reference measures only a new encoding stage;
# it does not establish that the source photograph had zero quantization loss.
#
# Engineering definition (not yet photographer-confirmed): use complete,
# non-overlapping square tiles from the top-left. Choose the tile with minimum
# mean squared horizontal/vertical first differences in the BEFORE reference.
# This defines relative smoothness, not a calibrated perceptual banding score.
# Exact ties use raster order. The caller MUST supply patch_size; no invented
# scale, noise threshold, smoothing kernel, luma weight or creative recipe.
# RMS is computed over RGB channel samples in the SAME tile before/after.
# The 0.35-code-value increment warning is specified by plan 3.5. No overall
# pass verdict: grain, residual spatial correlation and other regions still
# require visual review. The tile rule has not been validated on real photos.
from __future__ import annotations

import math

import numpy as np

from image_io import InputError

WARNING_THRESHOLD_LSB = 0.35
WARNING = "quantization_residual_increase_above_0_35_lsb"


def _reference(value, name):
    try:
        array = np.asarray(value)
        if array.dtype.kind != "f":
            raise InputError(name + " must contain floating encoded-sRGB values")
        array = np.asarray(array, dtype=np.float64)
    except (TypeError, ValueError, OverflowError):
        raise InputError(name + " must be a finite floating RGB image") from None
    if (array.ndim != 3 or array.shape[-1] != 3 or
            array.shape[0] == 0 or array.shape[1] == 0):
        raise InputError(name + " must have nonempty H x W x 3 shape")
    if not np.all(np.isfinite(array)) or np.any(array < 0) or np.any(array > 1):
        raise InputError(name + " must be finite encoded sRGB within [0, 1]")
    return array


def _quantized(value, shape, name):
    try:
        array = np.asarray(value)
    except (TypeError, ValueError):
        raise InputError(name + " must be a uint8 RGB image") from None
    if array.dtype != np.dtype("uint8") or array.shape != shape:
        raise InputError(name + " must be uint8 and match the reference shape")
    return array


def _warnings(delta):
    return [WARNING] if delta > WARNING_THRESHOLD_LSB else []


def quantization_banding_qa(before_reference, before_quantized,
                           after_reference, after_quantized, *, patch_size):
    # All four arrays must be aligned at one resolution, after explicit color
    # normalization. Lineage is the caller responsibility; it cannot be inferred
    # from pixels. No images are decoded, resized, graded, quantized or modified.
    before = _reference(before_reference, "before_reference")
    after = _reference(after_reference, "after_reference")
    if after.shape != before.shape:
        raise InputError("before/after references must have the same shape")
    before8 = _quantized(before_quantized, before.shape, "before_quantized")
    after8 = _quantized(after_quantized, before.shape, "after_quantized")
    height, width, _ = before.shape
    # Two samples per axis are mathematically necessary for first differences.
    if type(patch_size) is not int or not 2 <= patch_size <= min(height, width):
        raise InputError("patch_size must be an explicit integer from 2 to the short edge")
    best = None
    tiles = 0
    size = patch_size
    for y in range(0, height - size + 1, size):
        for x in range(0, width - size + 1, size):
            tile = before[y:y + size, x:x + size]
            dx = np.diff(tile, axis=1)
            dy = np.diff(tile, axis=0)
            # Pool all RGB neighbor differences. No brightness/channel weights.
            energy = float((np.sum(dx * dx) + np.sum(dy * dy)) / (dx.size + dy.size))
            if best is None or energy < best[0]:
                best = (energy, x, y)
            tiles += 1
    energy, x, y = best
    area = (slice(y, y + size), slice(x, x + size))

    def rms(reference, quantized):
        # 255 is the uint8 full-scale code, not an adjustable coefficient.
        error_lsb = quantized[area].astype(np.float64) - reference[area] * 255
        return math.sqrt(float(np.mean(error_lsb * error_lsb)))

    before_rms = rms(before, before8)
    after_rms = rms(after, after8)
    delta = after_rms - before_rms
    return {
        "algorithm": "encoded-srgb-quantization-residual-rms-v1",
        "scope": "caller_supplied_pre_and_post_quantization_pairs",
        "units": "8_bit_code_values",
        "reference_provenance": "caller_must_supply_actual_aligned_pre_quantization_values",
        "region": {
            "selection": "minimum_before_reference_neighbor_difference_energy",
            "selection_status": "engineering_definition_not_photographer_validated",
            "patch_size": size,
            "box_xywh": [x, y, size, size],
            "tie_break": "first_in_raster_order",
            "source_smoothness_mean_square_encoded_srgb": energy,
            "tiles_examined": tiles,
            "pixels_examined": tiles * size * size,
            "pixels_excluded_at_right_and_bottom": height * width - tiles * size * size,
            "pixels_measured": size * size,
            "channel_samples_measured": size * size * 3,
        },
        "before_rms_lsb": before_rms,
        "after_rms_lsb": after_rms,
        "increase_lsb": delta,
        "warning_threshold_lsb": WARNING_THRESHOLD_LSB,
        "warnings": _warnings(delta),
        "human_review_required": True,
        "limitations": [
            "does_not_recover_unknown_source_quantization_error",
            "caller_quantization_pair_lineage_not_independently_verified",
            "smoothest_examined_tile_need_not_be_a_truly_smooth_scene_region",
            "unselected_tiles_and_incomplete_edge_tiles_are_not_assessed",
            "rms_does_not_measure_error_spatial_correlation_or_perceptual_banding",
            "dither_and_grain_can_raise_residual_without_worsening_visible_banding",
            "not_source_icc_loss_or_whole_photo_visual_acceptance",
        ],
    }
