# Rebuilt floating-point color core for the plan, not the historical 0.4.1 prototype.
# Pure numeric API. No I/O, ICC guessing, presets or automatic correction.
# Quantization occurs ONLY in the explicit final quantize_srgb8 API.
# Color transforms use normalized float64 coordinates, NOT code values 0..255.
# The terminal quantizer explicitly returns uint8 code values.
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
from math import remainder
from numbers import Integral, Real

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


# Rebuilt plan 3.4 per-hue adjustment. NEW engineering window, not prototype code
# or a confirmed six-look recipe. ALL creative parameters are required inputs.
# w(t)=(1-t)^2*(1+2t): cubic Hermite from w(0)=1, w(1)=0, w_prime(0)=w_prime(1)=0.
# The coefficients are derived boundary constraints, not fitted photographic data.
HUE_BAND_ALGORITHM = "oklch-circular-hue-band-hermite-v1"


def _scaled_sum_products(*products):
    """Sum nonnegative products (or one signed product), scaling only at the end.

    frexp/ldexp are exact binary exponent operations. This prevents an early
    t*t or strength*weight underflow from erasing a representable final color.
    Callers pass at most six factors per product, so the mantissa products and
    integer exponent sums themselves cannot overflow or underflow.
    """
    terms = []
    absent = np.iinfo(np.int32).min
    for factors in products:
        mantissa, exponent = np.frexp(factors[0])
        for factor in factors[1:]:
            other_mantissa, other_exponent = np.frexp(factor)
            mantissa = mantissa * other_mantissa
            exponent = exponent + other_exponent
        terms.append((mantissa, exponent))
    common = np.where(terms[0][0] != 0, terms[0][1], absent)
    for mantissa, exponent in terms[1:]:
        common = np.maximum(common, np.where(mantissa != 0, exponent, absent))
    common = np.where(common == absent, 0, common)
    total = np.zeros_like(terms[0][0], dtype=np.float64)
    for mantissa, exponent in terms:
        total = total + np.ldexp(mantissa, exponent - common)
    return np.ldexp(total, common)


@_finite_math
def hue_band_adjust_oklch(oklch, *, center, width, hue_shift, chroma_scale, strength):
    """Adjust a circular hue band without changing L or tinting exact neutrals.

    Input (..., 3) is (Oklab L, chroma, hue degrees), L in [0,1], C >= 0.
    center is periodic degrees; width is the support HALF-width in (0,180].
    hue_shift is in [-180,180], chroma_scale >= 0 and strength in [0,1].
    Every parameter is explicit. No guessed color-family or skin thresholds.

    For circular distance d < width, t=d/width and a=strength*w(t):
      C_out = C * ((1-a) + a*chroma_scale)
      h_out = (h + a*hue_shift) modulo 360
    L is copied. Neutral C=0, outside/edge pixels, disabled strength and identity
    adjustments are exact independent copies. Chroma-only adjustments retain
    the input hue representation; rotated hues are normalized to [0,360).
    A resulting C=0 has undefined hue; its numeric hue need not be zero.

    No I/O, gamut mapping, quantization, automatic look or skin detection.
    Sequential calls act on the preceding output hue (order can matter).
    Returned colors can be out of sRGB gamut and need downstream mapping/QA.
    """
    lch = _triples(oklch)
    midpoint = remainder(_scalar(center, "center"), 360)
    half_width = _scalar(width, "width")
    shift = _scalar(hue_shift, "hue_shift")
    gain = _scalar(chroma_scale, "chroma_scale")
    s = _scalar(strength, "strength")
    if not 0 < half_width <= 180:
        raise ValueError("width must be in (0,180] degrees (support half-width)")
    if not -180 <= shift <= 180:
        raise ValueError("hue_shift must be in [-180,180] degrees")
    if gain < 0:
        raise ValueError("chroma_scale must be nonnegative")
    if not 0 <= s <= 1:
        raise ValueError("strength must be in 0..1")
    if np.any((lch[..., 0] < 0) | (lch[..., 0] > 1)):
        raise ValueError("display-referred lightness must be in 0..1")
    if np.any(lch[..., 1] < 0):
        raise ValueError("OkLCh chroma must be nonnegative")
    if s == 0 or (shift == 0 and gain == 1):
        return lch
    # Signed reduction preserves tiny negative angles instead of rounding them
    # to 360. Reduce both operands before subtraction to avoid huge-angle overflow.
    hue = np.fmod(lch[..., 2], 360)
    hue = np.where(hue > 180, hue - 360, hue)
    hue = np.where(hue < -180, hue + 360, hue)
    delta = np.abs(hue - midpoint)
    # Across +/-180, add the two distances to that seam. Subtracting a rounded
    # delta from 360 would erase a representable narrow-window separation.
    across_seam = (180 - np.abs(hue)) + (180 - abs(midpoint))
    distance = np.minimum(delta, across_seam)
    active = (distance < half_width) & (lch[..., 1] > 0)
    # Divide only inside the support, keeping subnormal legal widths safe.
    t = distance[active] / half_width
    near_center = t <= 0.5
    complement = t * t * (3 - 2 * t)
    weight = (1 - t) ** 2 * (1 + 2 * t)
    # Evaluate the smaller weight directly at each endpoint. Both stay bounded,
    # and 1-w retains its quadratic tail even when w rounds to exactly one.
    complement = np.where(near_center, complement, 1 - weight)
    weight = np.where(near_center, 1 - complement, weight)
    # Keep the small endpoint factors separate until combined with C/gain/shift.
    # Even t*t can underflow while C*t*t is a perfectly representable value.
    weight_edge = np.where(near_center, 1, 1 - t)
    weight_curve = np.where(near_center, weight, 1 + 2 * t)
    if gain != 1:
        complement_edge = np.where(near_center, t, 1)
        complement_curve = np.where(near_center, 3 - 2 * t, complement)
        chroma = lch[..., 1][active]
        # C*((1-s)+s*(1-w)+s*w*gain), with no subtractive cancellation or
        # premature exponent loss. A truly unrepresentable final result fails.
        lch[..., 1][active] = _scaled_sum_products(
            (chroma, 1 - s),
            (chroma, s, complement_edge, complement_edge, complement_curve),
            (chroma, s, gain, weight_edge, weight_edge, weight_curve))
    if shift != 0:
        rotation = _scaled_sum_products((s, shift, weight_edge, weight_edge, weight_curve))
        rotated = np.mod(hue[active] + rotation, 360)
        # Remainder of a negative subnormal can round to 360. Canonicalize
        # that circular endpoint to 0; this is not RGB/gamut clipping.
        lch[..., 2][active] = np.where(rotated == 360, 0, rotated)
    return lch


# Rebuilt plan 3.4 split toning. NEW engineering envelope, not the historical
# prototype or a user-confirmed six-look recipe. All creative inputs are required.
# The least-degree nonzero polynomial with zero value AND slope at both ends is
# k*t^2*(1-t)^2. Normalizing its midpoint to 1 fixes k=16, not a fitted coefficient.
SPLIT_TONE_ALGORITHM = "oklab-split-tone-quartic-v1"


@_finite_math
def split_tone_oklab(oklab, *, shadow_hue, shadow_chroma, highlight_hue,
                     highlight_chroma, balance, strength):
    """Add separate shadow/highlight chroma vectors while preserving Oklab L.

    Input (...,3) is (L,a,b), L in [0,1]. Hue inputs are periodic degrees;
    chroma inputs are nonnegative PEAK ADDED Oklab chroma, not target saturation.
    balance is the explicitly selected un-tinted L in (0,1), not an EV or a
    percentage of image pixels. strength is in [0,1]. There are no defaults.

    Each region (0,balance) / (balance,1) uses normalized position t in (0,1)
    and w=16*t^2*(1-t)^2. Add strength*chroma*w*(cos(hue),sin(hue)) to (a,b).
    The tint peaks halfway across each region and tapers smoothly to zero at
    black, balance and white. Those three L values stay EXACTLY unchanged.
    Neutral pixels inside a region can be tinted. This does NOT protect skin
    or saturated warm subjects; subsequent protection and gamut QA are needed.

    Returns an independent float64 array; no I/O, quantization, RGB clipping,
    automatic exposure, guessed recipe, or changes to the legacy CLI renderer.
    """
    lab = _triples(oklab)
    sh = remainder(_scalar(shadow_hue, "shadow_hue"), 360)
    hh = remainder(_scalar(highlight_hue, "highlight_hue"), 360)
    sc = _scalar(shadow_chroma, "shadow_chroma")
    hc = _scalar(highlight_chroma, "highlight_chroma")
    pivot = _scalar(balance, "balance")
    s = _scalar(strength, "strength")
    if sc < 0 or hc < 0:
        raise ValueError("shadow_chroma and highlight_chroma must be nonnegative")
    if not 0 < pivot < 1:
        raise ValueError("balance must be in (0,1) Oklab lightness")
    if not 0 <= s <= 1:
        raise ValueError("strength must be in 0..1")
    lightness = lab[..., 0]
    if np.any((lightness < 0) | (lightness > 1)):
        raise ValueError("display-referred lightness must be in 0..1")
    if s == 0 or (sc == 0 and hc == 0):
        return lab
    for lower, upper, hue, chroma in ((0, pivot, sh, sc), (pivot, 1, hh, hc)):
        if chroma == 0:
            continue
        active = (lightness > lower) & (lightness < upper)
        if not np.any(active):
            continue
        selected = lightness[active]
        # Divide only selected pixels, so even a subnormal legal region is safe.
        # Evaluate both distances directly: 1-t can cancel a near-white tail.
        t = (selected - lower) / (upper - lower)
        u = (upper - selected) / (upper - lower)
        envelope_root = 4 * t * u
        angle = np.radians(hue)
        for axis, direction in ((1, np.cos(angle)), (2, np.sin(angle))):
            # Keep the squared envelope and strength/chroma factors separate.
            # Tiny factors with huge chroma can still yield a finite visible tint.
            delta = _scaled_sum_products((s, chroma, envelope_root,
                                          envelope_root, direction))
            lab[..., axis][active] += delta
    return lab


# Rebuilt plan 3.4 subtractive density. NEW ENGINEERING transform, not recovered
# prototype code, measured optical density or a user-confirmed six-look recipe.
# Define d as the decrease in lightness log-odds per unit OkLCh chroma at strength 1:
# logit(L_out) = logit(L) - d * strength * C. This definition fixes the formula,
# with NO fitted numerical coefficients. d and strength have NO creative defaults.
SUBTRACTIVE_DENSITY_ALGORITHM = "oklch-chroma-log-odds-density-v1"


@_finite_math
def subtractive_density_oklch(oklch, *, density, strength):
    # Input (...,3) is (L,C,h); L in [0,1], C >= 0, h in periodic degrees.
    # density is a signed finite real: positive darkens chromatic pixels,
    # negative brightens them. C and the exact input hue representation stay
    # unchanged. This is a creative lightness operation, not film physics,
    # exposure EV, skin detection or gamut mapping. Return a float64 copy.
    #
    # Black, white, exact neutrals, density=0 and strength=0 are exact identities.
    # Interior pixels use L/(L+(1-L)*exp(d*s*C)), evaluated in log-odds space to
    # retain near-black values and avoid unstable exp of a large positive shift.
    # No I/O, intermediate quantization, RGB clipping or implicit CLI switch.
    lch = _triples(oklch)
    d = _scalar(density, "density")
    s = _scalar(strength, "strength")
    if not 0 <= s <= 1:
        raise ValueError("strength must be in 0..1")
    lightness = lch[..., 0]
    chroma = lch[..., 1]
    if np.any((lightness < 0) | (lightness > 1)):
        raise ValueError("display-referred lightness must be in 0..1")
    if np.any(chroma < 0):
        raise ValueError("OkLCh chroma must be nonnegative")
    if d == 0 or s == 0:
        return lch
    active = (lightness > 0) & (lightness < 1) & (chroma > 0)
    x = lightness[active]
    # Scale the product only after combining binary mantissas/exponents, so
    # tiny s with huge d/C does not lose a representable final shift.
    # Overflow is allowed ONLY for this log-odds shift: |d*s*C| > float64 max
    # necessarily rounds the final sigmoid to 0 or 1. Inf never leaves the API.
    # This analytic endpoint limit is not RGB clipping or a creative threshold.
    with np.errstate(over="ignore"):
        shift = _scaled_sum_products((chroma[active], d, s))
    adjusted = x.copy()
    # For |shift| <= ln(2), exp(-shift) lies in [1/2,2], keeping this
    # denominator >= 1/2. Evaluate the CHANGE with expm1: log/exp round-trip
    # noise must not darken a pixel for an infinitesimal negative density.
    # ln(2) is a numerical conditioning boundary, not a grading parameter.
    small = np.abs(shift) <= np.log(2.0)
    u = np.expm1(-shift[small])
    xs = x[small]
    adjusted[small] = xs + xs * (1 - xs) * u / (1 + xs * u)
    # Large shifts use stable log-odds; infinite shift means an endpoint limit.
    large = ~small
    z = np.log(x[large]) - np.log1p(-x[large]) - shift[large]
    tail = np.exp(-np.abs(z))
    fraction = tail / (1 + tail)
    adjusted[large] = np.where(z >= 0, 1 - fraction, fraction)
    lightness[active] = adjusted
    return lch


# Rebuilt plan 3.4 FINAL output stage, not the historical 0.4.1 prototype.
# TPDF is the difference of two independent U[0,1) draws: zero mean,
# variance amplitude_lsb**2/6, support within +/-amplitude_lsb code steps.
# These follow the distribution, not fitted photographic coefficients.
# amplitude_lsb and seed are REQUIRED, with no unconfirmed look defaults.
SRGB8_QUANTIZE_ALGORITHM = "encoded-srgb8-tpdf-pcg64-half-up-v1"


def quantize_srgb8(encoded, *, amplitude_lsb, seed):
    # Input (...,3) must ALREADY be encoded sRGB in [0,1]. Reject any out-of-gamut
    # input, even one ULP outside: this is not a hidden gamut mapper or an ICC API.
    # amplitude_lsb in [0,1] is peak noise in 8-bit code steps, not normalized
    # RGB, variance or film grain. 0 disables noise. All parameters are explicit.
    # seed is a nonnegative integer. Use a private, explicitly named PCG64;
    # never seed/advance numpy global RNG state or use ambient entropy.
    # C-order draws: all first uniforms, then all second uniforms, per channel.
    # Repeatability is for equal input values/shape, parameters and NumPy version.
    # Split/tiled calls restart the stream and are NOT equivalent to one full call.
    # Noise may push valid edge values out of range; saturate ONLY those excursions,
    # then round to nearest code, ties upward. No uint8 wrap or banker rounding.
    # Nonzero noise can move exact black/white one step inward. Identity paths
    # MUST explicitly use amplitude_lsb=0; no promise of endpoint or mean
    # preservation at the bounds, nor of photographic banding/QA acceptance.
    values = _triples(encoded)
    amplitude = _scalar(amplitude_lsb, "amplitude_lsb")
    if not 0 <= amplitude <= 1:
        raise ValueError("amplitude_lsb must be in 0..1 code steps")
    if isinstance(seed, (bool, np.bool_)) or not isinstance(seed, Integral) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if np.any((values < 0) | (values > 1)):
        raise ValueError("encoded sRGB must be in 0..1; map and report gamut first")
    code = values * 255
    if amplitude != 0:
        rng = np.random.Generator(np.random.PCG64(int(seed)))
        noise = rng.random(values.shape) - rng.random(values.shape)
        code += amplitude * noise
        np.clip(code, 0, 255, out=code)
    # Adding 0.5 before floor can round a value just BELOW a half-step up to an
    # integer. Compare the fractional remainder instead, preserving that boundary.
    lower = np.floor(code)
    return (lower + (code - lower >= 0.5)).astype(np.uint8)


# Rebuilt plan 3.5 gamut mapping AND mapped-pixel accounting. This is a new
# engineering method, not the recovered 0.4.1 prototype or an approved look.
# Linear sRGB D65 luminance fractions are STANDARD colorimetry from W3C CSS Color 4:
# https://www.w3.org/TR/css-color-4/#color-conversion-code (lin_sRGB_to_XYZ, Y row).
# They sum exactly to 1 as rational numbers; no fitted photographic coefficients.
# Mapping travels toward a neutral of equal relative luminance until the first
# sRGB cube intersection. It preserves linear RGB opponent direction, NOT exact
# Oklab hue/L. This tradeoff must be evaluated on real photos before CLI adoption.
GAMUT_MAP_ALGORITHM = "linear-srgb-luminance-ray-cube-v1"
_SRGB_Y = np.array([87098/409605, 175762/245763, 12673/175545], dtype=np.float64)
_SRGB_Y.setflags(write=False)


@_finite_math
def _luminance_ray_intersection(rgb):
    # Called ONLY for out-of-gamut pixels. The in-gamut path is an exact copy.
    # Explicit component order makes full-array and partitioned calls agree.
    y = rgb[:,0]*_SRGB_Y[0] + rgb[:,1]*_SRGB_Y[1] + rgb[:,2]*_SRGB_Y[2]
    if np.any((y < 0) | (y > 1)):
        raise ValueError("relative luminance outside 0..1; explicit tone mapping required")
    low, high = rgb.min(axis=1), rgb.max(axis=1)
    scale = np.ones_like(y)
    below = low < 0
    scale[below] = y[below] / (y[below]-low[below])
    above = high > 1
    scale[above] = np.minimum(scale[above], (1-y[above])/(high[above]-y[above]))
    # Convex combination; products stay bounded even for large finite RGB.
    # In exact arithmetic this is inside the cube. Any float64 endpoint
    # excursions are finalized AND separately counted by the public API.
    return (1-scale[:,None])*y[:,None] + scale[:,None]*rgb


def gamut_map_linear_srgb(linear):
    # Pure numeric API -> (independent float64 RGB array, JSON-serializable QA).
    # Input (...,3): nonempty finite display-referred LINEAR sRGB D65, not code
    # values, Oklab or an ICC-tagged image. No implicit decode/encode or I/O.
    # Every source pixel with ANY channel outside [0,1] is counted once, including
    # one-ULP excursions; this reports this stage, not prior ICC gamut losses.
    # For out-of-gamut RGB, Y must be in [0,1]; otherwise fail the whole call
    # rather than silently change brightness. No strength or aesthetic defaults.
    # This method does not identify skin, guarantee six-look distinctness, or
    # prove banding/skin/LUT acceptance. Legacy CLI rendering stays unchanged.
    # A C-contiguous independent array keeps flattening a view, even for
    # Fortran/axis-transposed images; updates must reach the returned RGB.
    rgb = np.ascontiguousarray(_triples(linear))
    flat = rgb.reshape(-1,3)
    active = np.any((flat < 0) | (flat > 1), axis=1)
    count = int(np.count_nonzero(active))
    corrected, correction = 0, 0.0
    if count:
        target = _luminance_ray_intersection(flat[active])
        bounded = np.clip(target, 0, 1)
        # This saturation is only after analytic chroma compression, never a
        # direct clip of the source. Report float endpoint corrections explicitly.
        corrected = int(np.count_nonzero(target != bounded))
        correction = float(np.max(np.abs(target-bounded)))
        flat[active] = bounded
    total = int(len(flat))
    qa = {
        "algorithm": GAMUT_MAP_ALGORITHM,
        "input_space": "linear-srgb-d65", "output_space": "linear-srgb-d65",
        "pixels_total": total, "pixels_mapped": count,
        "mapped_fraction": count/total, "warning_fraction": 0.1,
        # Plan 3.5: warn ABOVE 10%, not at 10%. Integer comparison avoids
        # fraction-rounding ambiguity. No global success/pass claim is produced.
        "warnings": ["gamut_mapped_fraction_above_10_percent"] if 10*count > total else [],
        "roundoff_samples_corrected": corrected,
        "max_roundoff_correction": correction,
    }
    return rgb, qa


# Rebuilt skin-protection pixel stage for plan 3.3/3.5/3.9, not prototype 0.4.1.
# Limits come directly from plan 3.5, NOT fitted or invented look coefficients.
# Applying the mean hue / chroma-ratio limits per selected pixel is a conservative
# ENGINEERING choice. Visual confirmation, detection and final-output QA are pending.
SKIN_PROTECT_ALGORITHM = "oklch-explicit-skin-limits-v1"
_SKIN_HUE_LIMIT = 6.0
_SKIN_CHROMA_RATIO_LIMIT = 1.15


def protect_skin_oklch(original, graded, skin_mask):
    # Inputs (...,3): aligned, finite (L,C,h), L in [0,1], C>=0, hue degrees.
    # skin_mask is a REQUIRED boolean array of EXACT shape (...), with no
    # broadcasting, probability threshold, generic skin key or face inference.
    # A lone triple requires a scalar boolean. Caller owns mask provenance.
    # Return (independent float64 array, stage-scoped JSON accounting).
    # Preserve graded L everywhere and every unselected pixel exactly.
    # Selected C is min(C_graded, 1.15*C_original); desaturation is not reversed.
    # Selected hue moves at most 6 degrees along the shortest circular arc from
    # original hue. Exactly opposite hues choose the positive arc deterministically.
    # At C_original=0, remove new tint, leave undefined hue representation alone.
    # At C_graded=0, preserve zero chroma and undefined hue; never invent color.
    # No near-neutral cutoff. No I/O, randomness, intermediate quantization,
    # automatic selection, image reshaping or adoption by the legacy CLI.
    # Apply before gamut mapping/encoding; those stages can change hue/chroma,
    # so these counts CANNOT replace final-image skin QA or prove plan acceptance.
    source = np.ascontiguousarray(_triples(original))
    result = np.ascontiguousarray(_triples(graded))
    if source.shape != result.shape:
        raise ValueError("original and graded must have identical coordinate shapes")
    for value in (source, result):
        if np.any((value[..., 0] < 0) | (value[..., 0] > 1)):
            raise ValueError("display-referred lightness must be in 0..1")
        if np.any(value[..., 1] < 0):
            raise ValueError("OkLCh chroma must be nonnegative")
    try:
        selected = np.asarray(skin_mask)
    except (TypeError, ValueError):
        raise ValueError("skin_mask must be boolean with the exact pixel shape") from None
    if selected.dtype.kind != "b" or selected.shape != source.shape[:-1]:
        raise ValueError("skin_mask must be boolean with the exact pixel shape")
    selected = selected.reshape(-1)
    before = source.reshape(-1, 3)
    after = result.reshape(-1, 3)
    c0 = before[:, 1]
    cg = after[:, 1]
    # Overflow of the cap means every finite target C already satisfies it.
    # Inf is confined to this comparison bound, never written into the result.
    # Subnormal caps round normally; no inferred neutral threshold is introduced.
    with np.errstate(over="ignore", under="ignore"):
        cap = c0 * _SKIN_CHROMA_RATIO_LIMIT
    chroma_limited = selected & (cg > cap)
    comparable = selected & (c0 > 0) & (cg > 0)
    # Reduce BEFORE subtracting to prevent overflow for huge finite hue inputs.
    # Signed reductions also retain tiny angles near zero without cancellation.
    h0 = np.fmod(before[:, 2], 360)
    hg = np.fmod(after[:, 2], 360)
    h0 = np.where(h0 > 180, h0-360, np.where(h0 < -180, h0+360, h0))
    hg = np.where(hg > 180, hg-360, np.where(hg < -180, hg+360, hg))
    delta = hg-h0
    delta = np.where(delta > 180, delta-360, np.where(delta <= -180, delta+360, delta))
    hue_limited = comparable & (np.abs(delta) > _SKIN_HUE_LIMIT)
    bounded_hue = np.mod(h0[hue_limited] + np.copysign(_SKIN_HUE_LIMIT, delta[hue_limited]), 360)
    after[hue_limited, 2] = np.where(bounded_hue == 360, 0, bounded_hue)
    after[chroma_limited, 1] = cap[chroma_limited]
    count = int(np.count_nonzero(selected))
    qa = {
        "algorithm": SKIN_PROTECT_ALGORITHM,
        "scope": "explicit_mask_before_gamut_and_quantization",
        "skin_detection_performed": False,
        "hue_limit_degrees": _SKIN_HUE_LIMIT,
        "chroma_ratio_limit": _SKIN_CHROMA_RATIO_LIMIT,
        "pixels_total": int(len(after)), "selected_pixels": count,
        "source_achromatic_pixels": int(np.count_nonzero(selected & (c0 == 0))),
        "hue_comparable_pixels": int(np.count_nonzero(comparable)),
        "hue_limited_pixels": int(np.count_nonzero(hue_limited)),
        "chroma_limited_pixels": int(np.count_nonzero(chroma_limited)),
        "changed_pixels": int(np.count_nonzero(hue_limited | chroma_limited)),
        "warnings": [] if count else ["no_skin_pixels_selected"],
    }
    return result, qa


# Rebuilt plan 3.4 LINEAR-LIGHT spatial bloom, not historical prototype 0.4.1.
# ENGINEERING method: luminance bright-pass, normalized sampled Gaussian,
# reflected borders, additive source-colored light. NOT a film/optics simulation
# or an approved six-look recipe. ALL creative parameters are REQUIRED.
# Gaussian exponent 1/2 and normalization follow its mathematical definition;
# luminance uses the already-sourced standard sRGB D65 coefficients above.
BLOOM_ALGORITHM = "linear-srgb-brightpass-gaussian-reflect101-add-v1"


def bloom_linear_srgb(linear, *, threshold, sigma_fraction, truncate, strength):
    # Input: nonempty HxWx3 finite LINEAR sRGB in [0,1], NOT encoded RGB values.
    # No automatic decode, exposure, ICC guesses, image resize or LUT application.
    # threshold in [0,1] is linear relative luminance Y, not Oklab L or a percentile.
    # sigma_fraction in (0,1] scales Gaussian sigma by the current short side.
    # truncate > 0 selects integer support r=max(1,ceil(truncate*sigma_pixels)).
    # Require r <= short side, an ENGINEERING resource bound, not a quality rule.
    # Oversized support is rejected, never silently shortened. All inputs are
    # validated even on identity paths. strength in [0,1] scales ADDED light.
    #
    # Bright-pass E=RGB*(Y-threshold)/Y when Y>threshold, else zero. At threshold
    # zero use E=RGB exactly, retaining even subnormal nonzero RGB contributions.
    # Blur E, never the source itself; add strength*blur(E) to the source.
    # RGB order and source light color are retained; no invented warm tint.
    # Bounded source does NOT imply bounded output. Return >1 values unchanged,
    # count/warn, and require explicit tone handling before mapping/quantization.
    # This stage can invalidate skin QA. It cannot recover clipped source detail.
    #
    # Returns (independent float64 image, stage-only JSON metadata). No file I/O,
    # intermediate quantization, RNG, dependency installation, global OpenCV
    # settings or implicit CLI adoption. Equal environment/input -> same pixels;
    # tiled/resized execution and other OpenCV versions are NOT promised identical.
    rgb = np.ascontiguousarray(_triples(linear))
    if rgb.ndim != 3:
        raise ValueError("bloom requires a nonempty HxWx3 image")
    if np.any((rgb < 0) | (rgb > 1)):
        raise ValueError("bloom input must be linear sRGB in 0..1; handle gamut first")
    threshold = _scalar(threshold, "threshold")
    fraction = _scalar(sigma_fraction, "sigma_fraction")
    support = _scalar(truncate, "truncate")
    s = _scalar(strength, "strength")
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be in 0..1 linear relative luminance")
    if not 0 < fraction <= 1:
        raise ValueError("sigma_fraction must be in (0,1] of the short side")
    if support <= 0:
        raise ValueError("truncate must be positive")
    if not 0 <= s <= 1:
        raise ValueError("strength must be in 0..1")
    short = min(rgb.shape[:2])
    sigma = fraction * short
    # Multiplication overflow is confined to support validation, never an
    # allocation or a pixel operation. Infinite support fails before ceil/int.
    extent = support * sigma
    if not np.isfinite(extent) or extent > short:
        raise ValueError("Gaussian support radius exceeds the image short-side budget")
    radius = max(1, int(np.ceil(extent)))
    with np.errstate(under="ignore"):
        y = rgb[...,0]*_SRGB_Y[0] + rgb[...,1]*_SRGB_Y[1] + rgb[...,2]*_SRGB_Y[2]
    active = (np.any(rgb > 0, axis=-1) if threshold == 0 else y > threshold)
    count = int(np.count_nonzero(active))
    result = rgb.copy()
    performed = bool(s != 0 and count)
    backend = None
    if performed:
        try:
            import cv2
        except ImportError:
            raise ValueError("OpenCV is required for bloom; no dependency was installed") from None
        backend = cv2.__version__
        extracted = np.zeros_like(rgb)
        if threshold == 0:
            extracted[:] = rgb
        else:
            with np.errstate(under="ignore"):
                extracted[active] = rgb[active]*((y[active]-threshold)/y[active])[:,None]
        offsets = np.arange(-radius, radius+1, dtype=np.float64)
        # Tiny legal sigma may overflow squared distance. Its analytic Gaussian
        # tail is then zero; exp(-inf)=0. Center remains exactly 1 before normalization.
        with np.errstate(over="ignore", under="ignore"):
            distance = offsets/sigma
            kernel = np.exp(-0.5*distance*distance)
        kernel /= np.sum(kernel)
        blurred = cv2.sepFilter2D(extracted, cv2.CV_64F, kernel, kernel,
                                  borderType=cv2.BORDER_REFLECT_101)
        with np.errstate(under="ignore"):
            result += s*blurred
        if not np.all(np.isfinite(result)) or np.any(result < rgb):
            raise ValueError("bloom arithmetic produced invalid additive light")
    over = int(np.count_nonzero(np.any(result > 1, axis=-1)))
    warnings = [] if count else ["no_highlights_above_threshold"]
    if over:
        warnings.append("linear_output_above_one_requires_explicit_tone_handling")
    qa = {
        "algorithm": BLOOM_ALGORITHM, "scope": "linear_bloom_before_final_output_qa",
        "input_space": "linear-srgb-d65", "output_space": "linear-srgb-d65",
        "threshold": threshold, "sigma_fraction": fraction, "truncate": support,
        "strength": s, "sigma_pixels": sigma, "kernel_radius_pixels": radius,
        "border": "reflect101", "blend": "additive_source_color",
        "pixels_total": int(rgb.shape[0]*rgb.shape[1]), "highlight_pixels": count,
        "changed_pixels": int(np.count_nonzero(np.any(result != rgb, axis=-1))),
        "pixels_above_one": over, "blur_performed": performed,
        "opencv_version": backend, "warnings": warnings,
    }
    return result, qa


# Rebuilt plan 3.4 spatial colored HALATION, not historical prototype 0.4.1.
# ENGINEERING effect, not a film-emulsion or lens simulation, nor an approved look.
# Bright-pass E=max(Y-threshold,0); halo=max(Gaussian(E)-E,0).
# Removing the local bright-pass suppresses tint in isolated light-source cores;
# only the positive diffused excess is added, with explicit LINEAR RGB tint.
# No guessed tint, threshold, radius or strength. Gaussian 1/2 and normalization
# follow the definition; Y coefficients are the standard sRGB D65 constants above.
HALATION_ALGORITHM = "linear-srgb-brightpass-positive-residual-tint-v1"


def halation_linear_srgb(linear, *, threshold, sigma_fraction, truncate,
                         strength, tint_linear_rgb):
    # Nonempty HxWx3 LINEAR sRGB in [0,1]. No ICC/gamma inference or file I/O.
    # All inputs REQUIRED. threshold: Y in [0,1]; sigma_fraction: (0,1] of the
    # current short side; truncate: positive sigma multiples; strength: [0,1].
    # tint_linear_rgb: exactly three finite channel gains in [0,1], NOT encoded
    # RGB, a hue angle, an observed spectral response or an implicitly normalized
    # color. E.g. red/magenta must be supplied/confirmed by the caller, not guessed.
    # Zero tint/strength or constant bright-pass yields an exact independent copy.
    # Input/parameter validation precedes identity paths, including resource limits.
    # Output can exceed 1. Preserve and report it; explicit downstream tone/gamut
    # handling and FINAL skin/clip QA remain mandatory. No LUT representation for
    # this spatial effect. Legacy CLI, presets and shared I/O remain unchanged.
    rgb = np.ascontiguousarray(_triples(linear))
    if rgb.ndim != 3:
        raise ValueError("halation requires a nonempty HxWx3 image")
    if np.any((rgb < 0) | (rgb > 1)):
        raise ValueError("halation input must be linear sRGB in 0..1; handle gamut first")
    q = _scalar(threshold, "threshold")
    fraction = _scalar(sigma_fraction, "sigma_fraction")
    support = _scalar(truncate, "truncate")
    s = _scalar(strength, "strength")
    tint = _real_array(tint_linear_rgb)
    if tint.shape != (3,) or np.any((tint < 0) | (tint > 1)):
        raise ValueError("tint_linear_rgb must be exactly three channel gains in 0..1")
    if not 0 <= q <= 1:
        raise ValueError("threshold must be in 0..1 linear relative luminance")
    if not 0 < fraction <= 1:
        raise ValueError("sigma_fraction must be in (0,1] of the short side")
    if support <= 0:
        raise ValueError("truncate must be positive")
    if not 0 <= s <= 1:
        raise ValueError("strength must be in 0..1")
    short = min(rgb.shape[:2])
    sigma = fraction*short
    extent = support*sigma
    if not np.isfinite(extent) or extent > short:
        raise ValueError("Gaussian support radius exceeds the image short-side budget")
    radius = max(1, int(np.ceil(extent)))
    with np.errstate(under="ignore"):
        y = rgb[...,0]*_SRGB_Y[0] + rgb[...,1]*_SRGB_Y[1] + rgb[...,2]*_SRGB_Y[2]
        extracted = np.maximum(y-q, 0)
    count = int(np.count_nonzero(extracted > 0))
    uniform = bool(np.all(extracted == extracted.flat[0]))
    performed = bool(s != 0 and np.any(tint > 0) and not uniform)
    result = rgb.copy()
    backend = None
    halo_count = 0
    if performed:
        try:
            import cv2
        except ImportError:
            raise ValueError("OpenCV is required for halation; no dependency was installed") from None
        backend = cv2.__version__
        offsets = np.arange(-radius, radius+1, dtype=np.float64)
        # For tiny legal sigma, overflowed squared distances have analytic zero
        # Gaussian weight. The center stays one, so normalization is well-defined.
        with np.errstate(over="ignore", under="ignore"):
            distance = offsets/sigma
            kernel = np.exp(-0.5*distance*distance)
        kernel /= np.sum(kernel)
        # Center on the minimum before convolution to preserve constant offsets
        # and avoid subtracting a large shared baseline in the residual.
        centered = extracted - np.min(extracted)
        blurred = cv2.sepFilter2D(centered, cv2.CV_64F, kernel, kernel,
                                  borderType=cv2.BORDER_REFLECT_101)
        # Positive-part selection defines the effect; this is NOT clipping RGB.
        halo = np.maximum(blurred-centered, 0)
        halo_count = int(np.count_nonzero(halo > 0))
        with np.errstate(under="ignore"):
            result += (s*halo)[...,None]*tint
        if not np.all(np.isfinite(result)) or np.any(result < rgb):
            raise ValueError("halation arithmetic produced invalid additive light")
    over = int(np.count_nonzero(np.any(result > 1,axis=-1)))
    warnings = [] if count else ["no_highlights_above_threshold"]
    if uniform and count:
        warnings.append("uniform_brightpass_has_no_edge_halo")
    if over:
        warnings.append("linear_output_above_one_requires_explicit_tone_handling")
    qa = {
        "algorithm": HALATION_ALGORITHM,
        "scope": "linear_halation_before_final_output_qa",
        "input_space": "linear-srgb-d65", "output_space": "linear-srgb-d65",
        "threshold": q, "sigma_fraction": fraction, "truncate": support,
        "strength": s, "tint_linear_rgb": tint.tolist(),
        "sigma_pixels": sigma, "kernel_radius_pixels": radius,
        "border": "reflect101", "blend": "additive_positive_residual_tint",
        "pixels_total": int(rgb.shape[0]*rgb.shape[1]), "highlight_pixels": count,
        "halo_pixels": halo_count,
        "changed_pixels": int(np.count_nonzero(np.any(result != rgb,axis=-1))),
        "pixels_above_one": over, "blur_performed": performed,
        "opencv_version": backend, "warnings": warnings,
    }
    return result, qa


# Rebuilt plan 3.4 linear-light GRAIN, not historical prototype 0.4.1.
# ENGINEERING texture: seeded uniform monochrome noise, normalized Gaussian
# correlation, multiplicative linear RGB gain. NOT a physical emulsion model or
# a confirmed photographic recipe. Every creative parameter and seed is REQUIRED.
# 2*U-1 maps U[0,1) to [-1,1); Gaussian 1/2 is mathematical, not fitted data.
GRAIN_ALGORITHM = "linear-srgb-pcg64-uniform-gaussian-multiply-v1"


def grain_linear_srgb(linear, *, amount, sigma_fraction, truncate, strength, seed):
    # Nonempty finite HxWx3 LINEAR sRGB in [0,1], with no implicit gamma/ICC step.
    # amount in [0,1] is the relative gain excursion bound BEFORE smoothing, NOT
    # final RMS, code steps or EV. strength in [0,1] scales that same excursion.
    # sigma_fraction in (0,1] sets sigma=current short side*fraction; truncate>0
    # sets r=max(1,ceil(truncate*sigma)). Require r<=short side before allocation.
    # This support bound controls resources; it is not a photographic criterion.
    # Generate ONE HxW PCG64 uniform field in C order; Gaussian blur only NOISE,
    # not source pixels. Use reflect101 and an L1-normalized separable kernel.
    # result=RGB*(1+strength*amount*blur(2*U-1)), same gain for all channels.
    # Larger sigma lowers realized variance; no sample-mean subtraction, RMS
    # normalization, amplitude fitting, source blur, channel tint or image resize.
    # Black and zero channels remain zero. Linear RGB ratios are preserved up to
    # rounding, NOT absolute Oklab chroma or final skin QA. Finite sample mean is
    # not forced to zero, and reflect borders alter covariance/variance locally.
    # Source in range does NOT imply result<=1. Preserve/report overshoot and
    # require explicit downstream tone handling; never clip away the evidence.
    # Same values/shape/parameters/NumPy/OpenCV environment => same pixel bytes.
    # Tiled or resized calls restart the stream/change sampling; no equivalence.
    # No file I/O, global RNG/backend settings, dependency install or CLI adoption.
    rgb = np.ascontiguousarray(_triples(linear))
    if rgb.ndim != 3:
        raise ValueError("grain requires a nonempty HxWx3 image")
    if np.any((rgb < 0) | (rgb > 1)):
        raise ValueError("grain input must be linear sRGB in 0..1; handle gamut first")
    amount = _scalar(amount, "amount")
    fraction = _scalar(sigma_fraction, "sigma_fraction")
    support = _scalar(truncate, "truncate")
    s = _scalar(strength, "strength")
    if not 0 <= amount <= 1:
        raise ValueError("amount must be in 0..1 relative gain")
    if not 0 < fraction <= 1:
        raise ValueError("sigma_fraction must be in (0,1] of the short side")
    if support <= 0:
        raise ValueError("truncate must be positive")
    if not 0 <= s <= 1:
        raise ValueError("strength must be in 0..1")
    if isinstance(seed, (bool, np.bool_)) or not isinstance(seed, Integral) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    short = min(rgb.shape[:2])
    sigma = fraction*short
    extent = support*sigma
    if not np.isfinite(extent) or extent > short:
        raise ValueError("Gaussian support radius exceeds the image short-side budget")
    radius = max(1, int(np.ceil(extent)))
    result = rgb.copy()
    performed = bool(s != 0 and amount != 0 and np.any(rgb > 0))
    backend = None
    gain_min = gain_max = 1.0
    if performed:
        try:
            import cv2
        except ImportError:
            raise ValueError("OpenCV is required for grain; no dependency was installed") from None
        backend = cv2.__version__
        rng = np.random.Generator(np.random.PCG64(int(seed)))
        noise = 2*rng.random(rgb.shape[:2])-1
        offsets = np.arange(-radius, radius+1, dtype=np.float64)
        # Tiny valid sigma makes analytic Gaussian tails zero; center stays one.
        with np.errstate(over="ignore", under="ignore"):
            distance = offsets/sigma
            kernel = np.exp(-0.5*distance*distance)
        kernel /= np.sum(kernel)
        correlated = cv2.sepFilter2D(noise, cv2.CV_64F, kernel, kernel,
                                     borderType=cv2.BORDER_REFLECT_101)
        with np.errstate(under="ignore"):
            gain = 1+(s*amount)*correlated
            result *= gain[...,None]
        if not np.all(np.isfinite(result)) or np.any(result < 0):
            raise ValueError("grain arithmetic produced invalid linear RGB")
        gain_min, gain_max = float(np.min(gain)), float(np.max(gain))
    over = int(np.count_nonzero(np.any(result > 1, axis=-1)))
    qa = {
        "algorithm": GRAIN_ALGORITHM, "scope": "linear_grain_before_final_output_qa",
        "input_space": "linear-srgb-d65", "output_space": "linear-srgb-d65",
        "amount": amount, "sigma_fraction": fraction, "truncate": support,
        "strength": s, "seed": int(seed), "rng": "PCG64-uniform",
        "sigma_pixels": sigma, "kernel_radius_pixels": radius,
        "border": "reflect101", "blend": "multiplicative_monochrome_gain",
        "gain_min": gain_min, "gain_max": gain_max,
        "pixels_total": int(rgb.shape[0]*rgb.shape[1]),
        "changed_pixels": int(np.count_nonzero(np.any(result != rgb,axis=-1))),
        "brightened_pixels": int(np.count_nonzero(np.any(result > rgb,axis=-1))),
        "darkened_pixels": int(np.count_nonzero(np.any(result < rgb,axis=-1))),
        "pixels_above_one": over, "noise_performed": performed,
        "numpy_version": np.__version__, "opencv_version": backend,
        "warnings": ["linear_output_above_one_requires_explicit_tone_handling"] if over else [],
    }
    return result, qa
