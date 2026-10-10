# Rebuilt floating-point color core for the plan, not the historical 0.4.1 prototype.
# Pure numeric API. No I/O, ICC guessing, presets, automatic correction or quantization.
# All channels use normalized float64 coordinates, NOT integer code values 0..255.
# sRGB and Oklab use D65. Linear-light here means display-referred SDR, not scene radiance.
#
# Sources for STANDARD color-science constants (not fitted creative coefficients):
# https://www.w3.org/TR/css-color-4/#color-conversion-code (extended sRGB transfer)
# https://bottosson.github.io/posts/oklab/ (2021-01-25 linear-sRGB matrices)
# Sources are identified for verification; no claim of a network fetch in this run.
# Forward coefficients are published decimal approximations. Inverses are computed
# from those same matrices, avoiding an additional independently rounded inverse.
#
# NEW ENGINEERING CURVE, not recovered prototype code or an approved look recipe:
# S_c(L)=L**c/(L**c+(1-L)**c). Its midpoint slope is exactly c; endpoints are fixed.
# c and strength are REQUIRED caller inputs. No invented default grading coefficients.
# The plan gives some contrast values but not this equation. Visual acceptance and
# full six-look integration remain pending; current CLI render is unchanged.
from functools import wraps
from numbers import Real

import numpy as np

ALGORITHM = "linear-srgb-oklab-core-v1"

_RGB_TO_LMS = np.array([
    [0.4122214708, 0.5363325363, 0.0514459929],
    [0.2119034982, 0.6806995451, 0.1073969566],
    [0.0883024619, 0.2817188376, 0.6299787005],
], dtype=np.float64)
_LMS_ROOT_TO_LAB = np.array([
    [0.2104542553, 0.7936177850, -0.0040720468],
    [1.9779984951, -2.4285922050, 0.4505937099],
    [0.0259040371, 0.7827717662, -0.8086757660],
], dtype=np.float64)
_LAB_TO_LMS_ROOT = np.linalg.inv(_LMS_ROOT_TO_LAB)
_LMS_TO_RGB = np.linalg.inv(_RGB_TO_LMS)
for _matrix in (_RGB_TO_LMS, _LMS_ROOT_TO_LAB, _LAB_TO_LMS_ROOT, _LMS_TO_RGB):
    _matrix.setflags(write=False)


def _real_array(value):
    try:
        raw = np.asarray(value)
        if raw.dtype.kind not in "iuf" or raw.size == 0:
            raise ValueError("expected nonempty real numeric coordinates")
        result = raw.astype(np.float64, copy=True)
    except (TypeError, OverflowError, ValueError):
        raise ValueError("expected nonempty real numeric coordinates") from None
    if not np.all(np.isfinite(result)):
        raise ValueError("coordinates must be finite")
    return result


def _triples(value):
    result = _real_array(value)
    if result.ndim == 0 or result.shape[-1] != 3:
        raise ValueError("coordinates must have a final axis of length three")
    return result


def _scalar(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(name + " must be a finite real scalar")
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise ValueError(name + " must be a finite real scalar") from None
    if not np.isfinite(result):
        raise ValueError(name + " must be a finite real scalar")
    return result


def _contrast(value):
    result = _scalar(value, "contrast")
    if result <= 0:
        raise ValueError("contrast must be positive")
    return result


def _finite_math(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            # Underflow toward zero is expected for very dark values and steep curves.
            # Overflow/invalid operations fail, never silently clip or emit NaN/Inf.
            with np.errstate(over="raise", invalid="raise", divide="raise", under="ignore"):
                result = function(*args, **kwargs)
        except FloatingPointError:
            raise ValueError("color arithmetic exceeds finite float64 range") from None
        if not np.all(np.isfinite(result)):
            raise ValueError("color arithmetic produced non-finite coordinates")
        return result
    return checked


@_finite_math
def srgb_to_linear(encoded):
    # Signed extension retains out-of-gamut coordinates for later mapping/QA.
    values = _real_array(encoded)
    magnitude = np.abs(values)
    result = np.empty_like(values)
    curved = magnitude > 0.04045
    result[~curved] = magnitude[~curved] / 12.92
    result[curved] = ((magnitude[curved] + 0.055) / 1.055) ** 2.4
    return np.copysign(result, values)


@_finite_math
def linear_to_srgb(linear):
    values = _real_array(linear)
    magnitude = np.abs(values)
    # Piecewise computation avoids evaluating the unselected branch on huge values.
    result = np.empty_like(values)
    curved = magnitude > 0.0031308
    result[~curved] = magnitude[~curved] * 12.92
    result[curved] = 1.055 * magnitude[curved] ** (1 / 2.4) - 0.055
    return np.copysign(result, values)


@_finite_math
def linear_srgb_to_oklab(linear):
    rgb = _triples(linear)
    lms = rgb @ _RGB_TO_LMS.T
    # Real cube root, including negative LMS. Fractional power would generate NaN.
    return np.cbrt(lms) @ _LMS_ROOT_TO_LAB.T


@_finite_math
def oklab_to_linear_srgb(oklab):
    lab = _triples(oklab)
    lms_root = lab @ _LAB_TO_LMS_ROOT.T
    return (lms_root ** 3) @ _LMS_TO_RGB.T


@_finite_math
def oklab_to_oklch(oklab):
    lab = _triples(oklab)
    result = np.empty_like(lab)
    result[..., 0] = lab[..., 0]
    chroma = np.hypot(lab[..., 1], lab[..., 2])
    hue = np.mod(np.degrees(np.arctan2(lab[..., 2], lab[..., 1])), 360)
    result[..., 1] = chroma
    # Hue is undefined ONLY at exact zero chroma. Store 0, with no skin/chroma threshold.
    result[..., 2] = np.where(chroma == 0, 0, hue)
    return result


@_finite_math
def oklch_to_oklab(oklch):
    lch = _triples(oklch)
    if np.any(lch[..., 1] < 0):
        raise ValueError("OkLCh chroma must be nonnegative")
    radians = np.radians(np.mod(lch[..., 2], 360))
    result = np.empty_like(lch)
    result[..., 0] = lch[..., 0]
    result[..., 1] = lch[..., 1] * np.cos(radians)
    result[..., 2] = lch[..., 1] * np.sin(radians)
    return result


@_finite_math
def lightness_curve(lightness, *, contrast):
    values = _real_array(lightness)
    c = _contrast(contrast)
    if np.any((values < 0) | (values > 1)):
        raise ValueError("display-referred lightness must be in 0..1")
    if c == 1:
        return values
    result = values.copy()
    interior = (values > 0) & (values < 1)
    x = values[interior]
    # Stable log-odds evaluation of S_c; does not divide two underflowed powers.
    z = c * (np.log(x) - np.log1p(-x))
    t = np.exp(-np.abs(z))
    result[interior] = np.where(z >= 0, 1 / (1 + t), t / (1 + t))
    return result


@_finite_math
def contrast_oklab(oklab, *, contrast, strength):
    # Pure lightness operation. Keeps a/b untouched; does NOT roll off chroma or map gamut.
    # Strength is explicitly 0..1, unlike the legacy CLI integer strength_percent.
    lab = _triples(oklab)
    c = _contrast(contrast)
    s = _scalar(strength, "strength")
    if not 0 <= s <= 1:
        raise ValueError("strength must be in 0..1")
    lightness = lab[..., 0]
    if np.any((lightness < 0) | (lightness > 1)):
        raise ValueError("display-referred lightness must be in 0..1")
    if s == 0 or c == 1:
        return lab
    target = lightness_curve(lightness, contrast=c)
    lab[..., 0] = (1 - s) * lightness + s * target
    return lab


# Rebuilt plan 3.4 highlight stage. NEW engineering curve, not prototype code or a
# user-confirmed preset. start and strength have NO creative defaults.
# f(t)=(1-t)^2*(1+2t) is the unique cubic with f(0)=1, f(1)=0,
# f_prime(0)=f_prime(1)=0. Its coefficients follow those constraints, not a fit.
HIGHLIGHT_ROLLOFF_ALGORITHM = "oklab-highlight-chroma-hermite-v1"


@_finite_math
def highlight_rolloff_oklab(oklab, *, start, strength):
    """Reduce highlight chroma at fixed Oklab L and hue; return a float64 copy.

    Apply to tone-adjusted Oklab. start is the explicitly selected lightness
    onset in [0, 1); strength is in [0, 1]. At/below start nothing changes.
    Above it, t=(L-start)/(1-start), C_out/C_in=(1-strength)+strength*f(t).
    At full strength L=1 is achromatic; partial strength retains chroma there.
    There is no gamut mapping, skin detection, I/O or intermediate quantization.
    A later stage must map/report out-of-gamut RGB. This is not a full look.
    """
    lab = _triples(oklab)
    onset = _scalar(start, "start")
    s = _scalar(strength, "strength")
    if not 0 <= onset < 1:
        raise ValueError("start must be in 0..1, excluding 1")
    if not 0 <= s <= 1:
        raise ValueError("strength must be in 0..1")
    lightness = lab[..., 0]
    if np.any((lightness < 0) | (lightness > 1)):
        raise ValueError("display-referred lightness must be in 0..1")
    if s == 0:
        return lab
    highlights = lightness > onset
    # Compute only selected pixels: even onset next to 1 cannot overflow from
    # subtracting a shadow coordinate and dividing it by a tiny denominator.
    t = (lightness[highlights] - onset) / (1 - onset)
    # Factored complement avoids cancellation of 1 - smoothstep near white.
    residual = (1 - t) ** 2 * (1 + 2 * t)
    factor = (1 - s) + s * residual
    chroma_axes = lab[..., 1:]
    chroma_axes[highlights] *= factor[..., None]
    return lab
