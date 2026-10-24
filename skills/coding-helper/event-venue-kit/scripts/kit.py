#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""event-venue-kit :: kit.py -- shared module (colour maths, directions, roll -> tokens.css).
共用模块：色彩运算、方向库加载、抽样、令牌 CSS 生成、指纹。Python 3.9+，只用标准库。

    import kit
    lib   = kit.load_directions()                       # library/directions.json
    p     = kit.sample(lib["directions"][0], random.Random(7))
    css   = kit.tokens_css(p)                           # :root{...} + dark block twice
    print(kit.tones("#8C1515"))                         # entity roles (see TONES SPEC)

Rules worth knowing before you edit sample() / derive_scheme()
    * every parameter takes its draw FIRST and a frozen (--keep) value only overrides it: `keep` never moves another value, and
      `draw.py adjust` can therefore re-derive a card from its seed (kit.sample consumes the RNG identically with or without keep).
    * colour roles are derived, never typed: --climb-text (>= 4.5:1 on paper and paper-2, same hue as --climb) is the TEXT twin
      of --climb; --m-select is the selection EDGE (>= 3:1 on --m-slab), --m-select-fill the tint (no floor); --m-cap (the ink
      line of the map) is walked to >= 7:1 on --m-slab and --m-wall to >= 3:1, in light and dark (FIX-SPEC-3 A3).
    * HEADINGS (FIX-SPEC-5 #1). --a-text is the colour of h1-h4, entity names and links, so it is never dimmer than the body text:
      its contrast on --paper is walked (OKLCH lightness, hue and chroma kept) to >= contrast(--text) - HEADING_SLACK (0.5), in
      light and dark; if the walk leaves less than HEADING_MIN_CHROMA of colour (an ink-accent direction on a dark ground) the
      heading IS --text. --focus keeps drawing from the plain "--a as text" colour. check_scheme() reports it as "heading/body".
    * HUE FAMILIES (FIX-SPEC-3 A2). In directions.json the OKLCH `h` of a palette role is one range [lo, hi] or a list of ranges
      [[lo, hi], ...]: the families a real event of that mechanism could own (stamp ink violet | red | green). sample() ALWAYS
      spends one draw per role on the family, even when the role has one family, then samples the hue inside it; so keep/adjust
      stay RNG-stable. A role may `"follow"` an earlier role (same number of families, e.g. night follows a, climb follows b):
      it takes that role's family index (its own draw is still spent). `"names"` names the families for the card summary.
      The canonical direction stays single-family. params["palette"]["families"] records what was drawn.
    * PROPS (FIX-SPEC-4 item 9). A direction's decorative motif that comes from its category (herbarium leaf label, festival-riso
      halftone, heraldry shield, airmail chevrons, departures barcode ...) is switchable: the recipe reads it from a `--prop-*`
      custom property and directions.json lists it: props: [{"name": "leaf", "var": "--prop-leaf", "off": "none", "what": "叶形标签"}]
      (`off` is the value that switches it off). ON is the recipe's own default, so nothing is declared for it. sample() copies the list
      to params["props"]; tokens_css() writes it as COMMENTED lines in :root (uncomment one line to switch the prop off) or, with
      props_off=True / a set of names, as live declarations (specimen.py --props off). A project keeps a prop only if its inventory
      supports it. validate_library() checks the list (and that the recipe reads every var, and only listed ones).
      PRESERVED BY `install.py --update` (FIX-SPEC-5 #2): every `--prop-*: value;` line that is LIVE (not inside a comment) in the
      installed evk/tokens.css, copied VERBATIM (value and trailing comment) into the regenerated file at that prop's place
      (live_prop_lines() reads them, tokens_css(props_keep=...) writes them); a live line for a var the card has no prop for is
      kept too, after the block. Everything else in tokens.css is regenerated from the card, commented prop lines included.
    * params["adjusted"] holds ONLY what a person asked for: {key, from, to, reason} dicts (a frozen value outside its envelope,
      or a `draw.py adjust`). What the floor rules moved on their own (colour roles walked to meet a contrast floor, UNRESOLVED
      and advisory notes) is params["floor_tuned"] (strings). kit.adjust_text() prints either; kit.floor_notes(params) reads
      both places, so rolls made before the split still work.

CLI
    python3 kit.py --selftest              run the built-in tests (uses an inline fixture library)
    python3 kit.py --validate [PATH]       check a directions.json against BUILD-SPEC section 3, its hue families (2-4 for a non-canonical
                                           accent, followers with matching counts, climb clear of b in every pairing) and the colour-word
                                           rule (idea / specimen_note / richness name a hue only when EVERY family of some role has it)
                                           and the props list (name, var, off, what; the recipe reads every var it lists)
    python3 kit.py --tones-table           print the fixed tones() table (same as tones.py --table)

Contents / 目录
  1. colour maths      sRGB <-> linear <-> OKLab <-> OKLCH (Bjorn Ottosson), gamut map by chroma reduction,
                       WCAG 2 luminance/contrast, mix(), toward(), lighten(), fit_L()
  2. TONES SPEC        tones(hex, paper, ink, night, target) -- the entity-colour algorithm; EVK.tones in JS is its twin
  3. floor             FLOOR_CHECKS / check_scheme(): the section 2.1 contrast rules, shared with lint_floor.py
  4. directions        load_directions(), validate_library(), fixture library for self-tests
  5. sampling          sample(direction, rng, keep, steer) -> params ; fingerprint(params)
  6. output            tokens_css(params), root_attrs(params)
  7. roll helpers      param_get(), adjust_text(), upgrade_params() -- used by draw.py adjust / install / lint for old rolls

---------------------------------------------------------------------------------------------------
TONES SPEC (exact; every step is plain IEEE-754 double maths, so JS reproduces it bit for bit)
---------------------------------------------------------------------------------------------------
Inputs: c = entity colour "#RRGGBB"; paper, ink, night = hex; target = 4.6.
Source-site values (原站取值 / source value, one instance only): paper "#F7F5F0", ink "#14171D",
night "#0D1D36", target 4.6.  Any colour may be replaced; the algorithm may not.

  lum(h):      channels r,g,b = byte/255; ch = c/12.92 if c <= 0.03928 else ((c+0.055)/1.055)**2.4;
               0.2126*R + 0.7152*G + 0.0722*B
  contrast(a,b) = (max(la,lb)+0.05) / (min(la,lb)+0.05)
  mix(a,b,t):  per channel  v = x + (y - x) * t   (x from a, y from b, bytes as floats), then
               hex(v) = clamp(floor(v + 0.5), 0, 255)  <- round HALF UP (JS Math.round), NOT Python round()
  toward(c, target, bg, need):  for i in 0..100: out = mix(c, target, i/100);
               if contrast(out, bg) >= need: return out;   after the loop return target
  lighten(c, bg, need):  if contrast(c, bg) >= need: return c;
               (h,l,s) = rgb_to_hls(c bytes/255); s = min(s, 0.62);
               for i in 0..100: out = hex(hls_to_rgb(h, l + (0.92 - l) * i/100, s) * 255);
                    if contrast(out, bg) >= need: return out;   after the loop return "#FFFFFF"
               rgb_to_hls / hls_to_rgb are exactly Python's colorsys (re-implemented below; port them verbatim).

  text   = toward(c, ink, paper, target)                              -> eText
  dark   = lighten(c, night, target)                                  -> eDk
  fill   = c ; if max(contrast(c, paper), contrast(c, ink)) < target: fill = toward(c, ink, paper, target)   -> e
  on     = paper if contrast(fill, paper) >= contrast(fill, ink) else ink                                     -> eOn
  eSoft   = mix(c, paper, 0.90)    (10 % colour in paper)
  eLine   = mix(c, paper, 0.55)    (45 % colour)
  eSoftDk = mix(c, night, 0.78)    (22 % colour in night)
Output keys (JS and Python): e eText eOn eSoft eLine eDk eSoftDk ; CSS: --e --e-text --e-on --e-soft --e-line --e-dk --e-soft-dk.
All outputs are upper-case "#RRGGBB".
DEFAULT  tones(...) uses method="oklch": the walk written up in assets/engine/tones.js (text and dark shades walk OKLCH
lightness in 0.01 steps keeping hue AND chroma), so build-time (Python) and run-time (EVK.tones) give identical values.
The text shade walks TOWARD THE INK END: darker when the ink is darker than the paper (a light card), lighter when the ink is
lighter than the paper (a dark-ground card, where the walk stops at L = 0.98). Only when that walk fails does eText fall back
to the ink colour, so a dark-paper card keeps the hue of every entity colour.
method="mix" is the source site's algorithm above; it reproduces floor.md F04 (Caltech #FF6C0C -> text #B45111 and so on).
---------------------------------------------------------------------------------------------------
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
import zlib
from functools import lru_cache
from pathlib import Path

KIT_NAME = "event-venue-kit"
KIT_VERSION = "0.1.0"
SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPTS_DIR.parent
LIBRARY_PATH = SKILL_ROOT / "library" / "directions.json"
ASSETS_DIR = SKILL_ROOT / "assets"
REFERENCE_FP_PATH = SKILL_ROOT / "references" / "reference-direction" / "fingerprint.json"

# 原站取值 / source value: used only as the default inputs of tones() / tones.py
SOURCE_PAPER, SOURCE_INK, SOURCE_NIGHT = "#F7F5F0", "#14171D", "#0D1D36"
TONES_TARGET = 4.6


# =================================================================================================
# 1. colour maths
# =================================================================================================

def round_half_up(x):
    """JS Math.round for the numbers we use (>= 0). Python's round() is banker's rounding: do not use it."""
    return int(math.floor(x + 0.5))


def norm_hex(h):
    """'#abc' / 'abcdef' / '#ABCDEF' -> '#ABCDEF'. Raises ValueError on anything else (alpha channels are rejected)."""
    s = str(h).strip().lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", s):
        raise ValueError("not a #RRGGBB colour: %r" % (h,))
    return "#" + s.upper()


def hex_to_rgb(h):
    h = norm_hex(h)
    return (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))


def rgb_to_hex(rgb):
    return "#" + "".join("%02X" % max(0, min(255, round_half_up(c))) for c in rgb)


def srgb_to_linear(c8):
    c = c8 / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(v):
    if v <= 0.0031308:
        return 12.92 * v
    return 1.055 * (v ** (1 / 2.4)) - 0.055


def _cbrt(x):
    return math.copysign(abs(x) ** (1.0 / 3.0), x)


def linear_to_oklab(r, g, b):
    """Linear sRGB (0..1) -> OKLab (L, a, b). Matrices: Bjorn Ottosson, 2020."""
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = _cbrt(l), _cbrt(m), _cbrt(s)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def oklab_to_linear(L, a, b):
    """OKLab -> linear sRGB (unclamped)."""
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


@lru_cache(maxsize=8192)
def hex_to_oklab(h):
    r, g, b = (srgb_to_linear(c) for c in hex_to_rgb(h))
    return linear_to_oklab(r, g, b)


@lru_cache(maxsize=8192)
def hex_to_oklch(h):
    L, a, b = hex_to_oklab(h)
    C = math.hypot(a, b)
    H = math.degrees(math.atan2(b, a)) % 360.0 if C > 1e-7 else 0.0
    return (L, C, H)


def oklch_to_oklab(L, C, H):
    hr = math.radians(H)
    return (L, C * math.cos(hr), C * math.sin(hr))


def _in_gamut(rgb, eps=1e-5):
    return all(-eps <= v <= 1 + eps for v in rgb)


def _lin_to_hex(rgb):
    return rgb_to_hex(tuple(linear_to_srgb(min(1.0, max(0.0, v))) * 255.0 for v in rgb))


def oklch_to_hex(L, C, H):
    """OKLCH -> '#RRGGBB'. Out-of-gamut colours are mapped by reducing chroma at constant L and H (bisection)."""
    if L <= 0.0:
        return "#000000"
    if L >= 1.0:
        return "#FFFFFF"
    C = max(0.0, C)
    hr = math.radians(H)
    ca, sb = math.cos(hr), math.sin(hr)
    rgb = oklab_to_linear(L, C * ca, C * sb)
    if _in_gamut(rgb):
        return _lin_to_hex(rgb)
    lo, hi = 0.0, C
    for _ in range(18):
        mid = (lo + hi) / 2.0
        if _in_gamut(oklab_to_linear(L, mid * ca, mid * sb)):
            lo = mid
        else:
            hi = mid
    return _lin_to_hex(oklab_to_linear(L, lo * ca, lo * sb))


def max_chroma(L, H):
    """Largest sRGB-displayable chroma at (L, H) (bisection, 0.001 precision)."""
    hr = math.radians(H)
    ca, sb = math.cos(hr), math.sin(hr)
    lo, hi = 0.0, 0.4
    for _ in range(12):
        mid = (lo + hi) / 2.0
        if _in_gamut(oklab_to_linear(L, mid * ca, mid * sb)):
            lo = mid
        else:
            hi = mid
    return lo


@lru_cache(maxsize=8192)
def rel_luminance(h):
    """WCAG 2 relative luminance of '#RRGGBB'."""
    def ch(c):
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in hex_to_rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    """WCAG 2 contrast ratio between two '#RRGGBB' colours (1..21)."""
    la, lb = rel_luminance(a), rel_luminance(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def mix(a, b, t):
    """a blended toward b by t (0 -> a, 1 -> b), per sRGB byte. Same formula as the source site's report.py."""
    return rgb_to_hex(tuple(x + (y - x) * t for x, y in zip(hex_to_rgb(a), hex_to_rgb(b))))


def mix_ok(a, b, t):
    """a blended toward b by t in OKLab (no muddy mid-tones); used for map materials, never for tones()."""
    la, aa, ba = hex_to_oklab(norm_hex(a))
    lb, ab, bb = hex_to_oklab(norm_hex(b))
    r = oklab_to_linear(la + (lb - la) * t, aa + (ab - aa) * t, ba + (bb - ba) * t)
    return _lin_to_hex(r)


def toward(c, target, bg, need):
    """Mix c toward target 1 % at a time and stop at the first result with contrast(result, bg) >= need."""
    c, target, bg = norm_hex(c), norm_hex(target), norm_hex(bg)
    for i in range(0, 101):
        out = mix(c, target, i / 100)
        if contrast(out, bg) >= need:
            return out
    return target


def rgb_to_hls(r, g, b):
    """colorsys.rgb_to_hls, re-implemented so the JS twin has a literal spec."""
    maxc, minc = max(r, g, b), min(r, g, b)
    sumc = maxc + minc
    rangec = maxc - minc
    l = sumc / 2.0
    if minc == maxc:
        return 0.0, l, 0.0
    if l <= 0.5:
        s = rangec / sumc
    else:
        s = rangec / (2.0 - maxc - minc)
    rc = (maxc - r) / rangec
    gc = (maxc - g) / rangec
    bc = (maxc - b) / rangec
    if r == maxc:
        h = bc - gc
    elif g == maxc:
        h = 2.0 + rc - bc
    else:
        h = 4.0 + gc - rc
    h = (h / 6.0) % 1.0
    return h, l, s


def _hls_v(m1, m2, hue):
    hue = hue % 1.0
    if hue < 1.0 / 6.0:
        return m1 + (m2 - m1) * hue * 6.0
    if hue < 0.5:
        return m2
    if hue < 2.0 / 3.0:
        return m1 + (m2 - m1) * (2.0 / 3.0 - hue) * 6.0
    return m1


def hls_to_rgb(h, l, s):
    """colorsys.hls_to_rgb."""
    if s == 0.0:
        return l, l, l
    if l <= 0.5:
        m2 = l * (1.0 + s)
    else:
        m2 = l + s - (l * s)
    m1 = 2.0 * l - m2
    return (_hls_v(m1, m2, h + 1.0 / 3.0), _hls_v(m1, m2, h), _hls_v(m1, m2, h - 1.0 / 3.0))


def lighten(c, bg, need):
    """The same hue made lighter (HLS saturation capped at .62) until it reads on a dark background."""
    c, bg = norm_hex(c), norm_hex(bg)
    if contrast(c, bg) >= need:
        return c
    r, g, b = (x / 255.0 for x in hex_to_rgb(c))
    h, l, s = rgb_to_hls(r, g, b)
    s = min(s, 0.62)
    for i in range(0, 101):
        out = rgb_to_hex(tuple(x * 255.0 for x in hls_to_rgb(h, l + (0.92 - l) * i / 100, s)))
        if contrast(out, bg) >= need:
            return out
    return "#FFFFFF"


def hue_distance(h1, h2):
    d = abs((h1 - h2) % 360.0)
    return min(d, 360.0 - d)


def fit_L(lch, bgs, need, direction=None, iters=13):
    """Walk OKLCH lightness (hue and chroma kept, chroma gamut-mapped) to the NEAREST L whose contrast against every
    colour in `bgs` is >= need. direction +1 = lighter, -1 = darker, None = away from the backgrounds.
    Returns '#RRGGBB'. If even the extreme fails, returns the better extreme (the caller's check will flag it)."""
    L0, C, H = lch
    if isinstance(bgs, str):
        bgs = [bgs]
    bgs = [norm_hex(b) for b in bgs]

    def worst(L):
        h = oklch_to_hex(L, C, H)
        return min(contrast(h, b) for b in bgs), h

    w0, h0 = worst(L0)
    if w0 >= need:
        return h0
    if direction is None:
        mean_bg = sum(hex_to_oklab(b)[0] for b in bgs) / len(bgs)
        direction = 1 if L0 >= mean_bg else -1
    ext = 1.0 if direction > 0 else 0.0
    w1, h1 = worst(ext)
    if w1 < need:
        ext2 = 1.0 - ext
        w2, h2 = worst(ext2)
        if w2 < need:
            return h1 if w1 >= w2 else h2
        ext, h1 = ext2, h2
    lo, hi, best = L0, ext, h1
    for _ in range(iters):
        mid = (lo + hi) / 2.0
        w, h = worst(mid)
        if w >= need:
            hi, best = mid, h
        else:
            lo = mid
    return best


def parse_color(s):
    """CSS colour text -> '#RRGGBB'. Accepts #rgb, #rrggbb, #rrggbbaa (alpha dropped), rgb()/rgba(), oklch()."""
    s = str(s).strip()
    if s.startswith("#"):
        t = s[1:]
        if len(t) in (4, 8):
            t = t[:-1] if len(t) == 4 else t[:6]
        return norm_hex(t)
    m = re.fullmatch(r"rgba?\(\s*([\d.]+%?)[\s,]+([\d.]+%?)[\s,]+([\d.]+%?)(?:[\s,/]+[\d.%]+)?\s*\)", s, re.I)
    if m:
        vals = []
        for g in m.groups():
            vals.append(float(g[:-1]) * 2.55 if g.endswith("%") else float(g))
        return rgb_to_hex(vals)
    m = re.fullmatch(r"oklch\(\s*([\d.]+%?)\s+([\d.]+%?)\s+([\d.]+)(?:deg)?(?:\s*/\s*[\d.%]+)?\s*\)", s, re.I)
    if m:
        L = float(m.group(1)[:-1]) / 100 if m.group(1).endswith("%") else float(m.group(1))
        C = float(m.group(2)[:-1]) * 0.004 if m.group(2).endswith("%") else float(m.group(2))
        return oklch_to_hex(L, C, float(m.group(3)))
    raise ValueError("cannot parse colour: %r" % (s,))


# =================================================================================================
# 2. tones (TONES SPEC in the module docstring)
# =================================================================================================

TONES_KEYS = ("e", "eText", "eOn", "eSoft", "eLine", "eDk", "eSoftDk")
TONES_CSS = {"e": "--e", "eText": "--e-text", "eOn": "--e-on", "eSoft": "--e-soft", "eLine": "--e-line",
             "eDk": "--e-dk", "eSoftDk": "--e-soft-dk"}


def tones(hex_color, paper=SOURCE_PAPER, ink=SOURCE_INK, night=SOURCE_NIGHT, target=TONES_TARGET, method="oklch"):
    """Entity colour roles (generalised from the source site's report.py palette()).
    method="oklch" (default, = EVK.tones): see tones_oklch().  method="mix": the source algorithm in the TONES SPEC above."""
    if method == "oklch":
        return tones_oklch(hex_color, paper, ink, night, target)
    c, paper, ink, night = norm_hex(hex_color), norm_hex(paper), norm_hex(ink), norm_hex(night)
    text = toward(c, ink, paper, target)
    dark = lighten(c, night, target)
    fill = c
    if max(contrast(c, paper), contrast(c, ink)) < target:
        fill = toward(c, ink, paper, target)
    on = paper if contrast(fill, paper) >= contrast(fill, ink) else ink
    return {"e": fill, "eText": text, "eOn": on,
            "eSoft": mix(c, paper, 0.9), "eLine": mix(c, paper, 0.55),
            "eDk": dark, "eSoftDk": mix(c, night, 0.78)}


def _from_oklch_spec(L, C, h):
    """OKLCH -> hex exactly as tones.js step 4 specifies (32 bisections, gamut eps 1e-6, clamp, half-up)."""
    hr = math.radians(h)
    ca, sb = math.cos(hr), math.sin(hr)

    def lin(c_):
        return oklab_to_linear(L, c_ * ca, c_ * sb)

    def ing(rgb):
        return all(-1e-6 <= v <= 1 + 1e-6 for v in rgb)

    if not ing(lin(C)):
        lo, hi = 0.0, C
        for _ in range(32):
            mid = (lo + hi) / 2.0
            if ing(lin(mid)):
                lo = mid
            else:
                hi = mid
        C = lo
    rgb = lin(C)
    return rgb_to_hex(tuple(linear_to_srgb(min(1.0, max(0.0, v))) * 255.0 for v in rgb))


def _walk_oklch(c, direction, bg, target, max_l=None):
    """tones.js step 5: walk OKLCH lightness in 0.01 steps (hue and chroma kept) until contrast(out, bg) >= target.
    max_l (optional) caps the lightest L tried (the text walk on a dark ground stops at 0.98: white would lose the hue)."""
    if contrast(c, bg) >= target:
        return c
    L0, C, h = hex_to_oklch(c)
    for i in range(1, 101):
        L = min(1.0, max(0.0, L0 + direction * 0.01 * i))
        if max_l is not None and L > max_l:
            L = max_l
        out = _from_oklch_spec(L, C, h)
        if contrast(out, bg) >= target:
            return out
        if max_l is not None and L >= max_l:
            break
    return None


TEXT_MAX_L = 0.98   # lightest L of the text walk on a dark ground (tones.js step 5/6)


def tones_oklch(hex_color, paper=SOURCE_PAPER, ink=SOURCE_INK, night=SOURCE_NIGHT, target=TONES_TARGET):
    """ALTERNATIVE method (tones.js header, 'walk lightness in OKLCH'): text/dark shades keep hue AND chroma instead of
    mixing toward ink / HLS-lightening. This is the default of tones(), identical to EVK.tones in assets/engine/tones.js.
    The text walk goes toward the ink end (darker for dark ink on light paper, lighter for light ink on a dark ground);
    it falls back to the ink colour only when that walk finds nothing (on a dark ground: nothing up to L = 0.98)."""
    c, paper, ink, night = norm_hex(hex_color), norm_hex(paper), norm_hex(ink), norm_hex(night)
    if rel_luminance(ink) > rel_luminance(paper):
        text = _walk_oklch(c, +1, paper, target, TEXT_MAX_L) or ink
    else:
        text = _walk_oklch(c, -1, paper, target) or ink
    dark = _walk_oklch(c, +1, night, target) or "#FFFFFF"
    fill = c if max(contrast(c, paper), contrast(c, ink)) >= target else text
    on = paper if contrast(fill, paper) >= contrast(fill, ink) else ink
    return {"e": fill, "eText": text, "eOn": on, "eSoft": mix(c, paper, 0.9), "eLine": mix(c, paper, 0.55),
            "eDk": dark, "eSoftDk": mix(c, night, 0.78)}


def tones_css(t, indent=""):
    return ";".join("%s%s:%s" % (indent, TONES_CSS[k], t[k]) for k in TONES_KEYS)


# six inputs chosen to hit every branch: untouched colour; ink-text-on-orange; light blue (text walks far, dark untouched);
# cyan; near-black (dark colour lightened); mid-grey where neither paper nor ink text reaches the target (fill walks).
TONES_TABLE_INPUTS = ("#8C1515", "#FF6C0C", "#7BAFD4", "#09A7C8", "#370404", "#808080")
# Frozen outputs with the source paper/ink/night and target 4.6. Verified against the source report.py palette()
# for all 52 school colours (only the rounding mode differs in theory; none of the 52 hits a .5).
TONES_TABLE_EXPECTED = {
    "#8C1515": {"e": "#8C1515", "eText": "#8C1515", "eOn": "#F7F5F0", "eSoft": "#ECDFDA", "eLine": "#C7908D", "eDk": "#D95F5F", "eSoftDk": "#291B2F"},
    "#FF6C0C": {"e": "#FF6C0C", "eText": "#B45111", "eOn": "#14171D", "eSoft": "#F8E7D9", "eLine": "#FBB789", "eDk": "#FF6C0C", "eSoftDk": "#422E2D"},
    "#7BAFD4": {"e": "#7BAFD4", "eText": "#52728B", "eOn": "#14171D", "eSoft": "#EBEEED", "eLine": "#BFD6E3", "eDk": "#7BAFD4", "eSoftDk": "#253D59"},
    "#09A7C8": {"e": "#09A7C8", "eText": "#0D7991", "eOn": "#14171D", "eSoft": "#DFEDEC", "eLine": "#8CD2DE", "eDk": "#09A7C8", "eSoftDk": "#0C3B56"},
    "#370404": {"e": "#370404", "eText": "#370404", "eOn": "#F7F5F0", "eSoft": "#E4DDD8", "eLine": "#A18986", "eDk": "#DA6060", "eSoftDk": "#16182B"},
    "#808080": {"e": "#6F6F70", "eText": "#6F6F70", "eOn": "#F7F5F0", "eSoft": "#EBE9E5", "eLine": "#C1C0BE", "eDk": "#868686", "eSoftDk": "#263346"},
}


# method="oklch": the table printed in assets/engine/tones.js (E2's header). Rows: (input, opts, expected roles).
TONES_OKLCH_EXPECTED = [
    ("#8C1515", {}, ["#8C1515", "#8C1515", "#F7F5F0", "#ECDFDA", "#C7908D", "#DB6258", "#291B2F"]),
    ("#FF6C0C", {}, ["#FF6C0C", "#BA4B00", "#14171D", "#F8E7D9", "#FBB789", "#FF6C0C", "#422E2D"]),
    ("#7BAFD4", {}, ["#7BAFD4", "#3F7294", "#14171D", "#EBEEED", "#BFD6E3", "#7BAFD4", "#253D59"]),
    ("#370404", {}, ["#370404", "#370404", "#F7F5F0", "#E4DDD8", "#A18986", "#B4766E", "#16182B"]),
    ("#09A7C8", {}, ["#09A7C8", "#007992", "#14171D", "#DFEDEC", "#8CD2DE", "#09A7C8", "#0C3B56"]),
    ("#7F7F7F", {}, ["#6D6D6D", "#6D6D6D", "#F7F5F0", "#EBE9E5", "#C1C0BD", "#888888", "#263346"]),
    ("#2E7D32", {"paper": "#FFFFFF", "ink": "#000000", "night": "#121212", "target": 7},
     ["#0F6519", "#0F6519", "#FFFFFF", "#EAF2EB", "#A1C5A3", "#64B265", "#182A19"]),
    ("#E91E63", {"paper": "#FAF3E8", "ink": "#2B2118", "night": "#1A1410", "target": 4.5},
     ["#D90058", "#D90058", "#FAF3E8", "#F8DEDB", "#F293AC", "#F02969", "#481622"]),
    # dark-ground cards (the paper is darker than the ink): the text shade walks LIGHTER and keeps its hue (the last row asks
    # for more contrast than L = 0.98 can give, so it falls back to the ink colour)
    ("#1F6FB2", {"paper": "#14202E", "ink": "#EEEAE1", "night": "#0B1220", "target": 4.6},
     ["#428ED3", "#428ED3", "#14202E", "#15283B", "#194469", "#3884C9", "#0F2640"]),
    ("#8C1515", {"paper": "#14202E", "ink": "#EEEAE1", "night": "#0B1220", "target": 4.6},
     ["#8C1515", "#DB6258", "#EEEAE1", "#201F2C", "#4A1B23", "#D0594F", "#27131E"]),
    ("#370404", {"paper": "#14202E", "ink": "#EEEAE1", "night": "#0B1220", "target": 4.6},
     ["#370404", "#B77971", "#EEEAE1", "#181D2A", "#24131B", "#AE7068", "#150F1A"]),
    ("#7F7F7F", {"paper": "#14202E", "ink": "#EEEAE1", "night": "#0B1220", "target": 4.6},
     ["#888888", "#888888", "#14202E", "#1F2A36", "#444B52", "#7F7F7F", "#252A35"]),
    ("#1F6FB2", {"paper": "#14202E", "ink": "#EEEAE1", "night": "#0B1220", "target": 16.4},
     ["#EEEAE1", "#EEEAE1", "#14202E", "#15283B", "#194469", "#E7F3FF", "#0F2640"]),
]


def tones_table(paper=SOURCE_PAPER, ink=SOURCE_INK, night=SOURCE_NIGHT, target=TONES_TARGET, inputs=TONES_TABLE_INPUTS,
                method="mix"):
    """Rows for the fixed comparison table (printed by `tones.py --table`; the JS twin prints the same)."""
    rows = []
    for h in inputs:
        t = tones(h, paper, ink, night, target, method)
        rows.append((h,) + tuple(t[k] for k in TONES_KEYS))
    return rows


def format_tones_table(rows=None, method="mix"):
    rows = rows or tones_table(method=method)
    head = ("input",) + TONES_KEYS
    lines = ["# tones(method=%r) with paper=%s ink=%s night=%s target=%s" % (method, SOURCE_PAPER, SOURCE_INK, SOURCE_NIGHT, TONES_TARGET),
             "  ".join("%-8s" % h for h in head)]
    for r in rows:
        lines.append("  ".join("%-8s" % v for v in r))
    return "\n".join(lines)


# =================================================================================================
# 3. floor checks (section 2.1)
# =================================================================================================

COLOR_TOKENS = ["paper", "paper-2", "rule", "text", "sub", "a", "a-text", "on-a", "b", "b-text", "on-b", "climb",
                "climb-text", "focus"]
# m-select = the selection EDGE (stroke), >= 3:1 on m-slab; m-select-fill = the selection tint (m-room mixed 10-16 % toward
# m-select), no contrast floor (FIX-SPEC A2)
MAP_COLOR_TOKENS = ["m-ground", "m-slab", "m-room", "m-block", "m-wall", "m-cap", "m-text", "m-route", "m-route-halo",
                    "m-dash", "m-climb", "m-select", "m-select-fill"]
ALL_COLOR_TOKENS = COLOR_TOKENS + MAP_COLOR_TOKENS
MAP_KEYWORD_TOKENS = ["m-projection", "m-material", "m-token", "m-pitch", "m-yaw", "m-wall-h", "m-light", "m-dim",
                      "m-label-case"]
FONT_TOKENS = ["f-display", "f-label", "f-text", "f-num", "f-cjk", "f-cjk-display"]
TYPE_TOKENS = ["label-case", "label-track", "label-stretch", "label-weight", "display-weight", "display-track",
               "display-leading"] + ["step--1", "step-0", "step-1", "step-2", "step-3", "step-4", "step-5"]
SHAPE_TOKENS = ["radius", "chamfer", "hair", "rule-2", "rule-3", "rule-cap"]
MOTION_TOKENS = ["spring-dur", "spring-bounce", "press-scale", "fade-dur"]
LAYOUT_TOKENS = ["gutter", "gap", "row-pad", "measure"]
REQUIRED_TOKENS = (ALL_COLOR_TOKENS + MAP_KEYWORD_TOKENS + FONT_TOKENS + TYPE_TOKENS + SHAPE_TOKENS + MOTION_TOKENS
                   + LAYOUT_TOKENS)

# (id, foreground token, background token, minimum ratio, rule) -- BUILD-SPEC 2.1 / floor.md F01-F03
FLOOR_CHECKS = [
    ("rule/paper", "rule", "paper", 1.25, "F03"),
    ("text/paper", "text", "paper", 7.0, "F01"),
    ("sub/paper", "sub", "paper", 4.5, "F01"),
    ("sub/paper-2", "sub", "paper-2", 4.5, "F01"),
    ("a-text/paper", "a-text", "paper", 4.5, "F02"),
    ("on-a/a", "on-a", "a", 4.5, "F02"),
    ("b-text/paper", "b-text", "paper", 4.5, "F02"),
    ("on-b/b", "on-b", "b", 4.5, "F02"),
    ("climb/m-slab", "climb", "m-slab", 3.0, "F03"),
    ("climb-text/paper", "climb-text", "paper", 4.5, "F02"),
    ("climb-text/paper-2", "climb-text", "paper-2", 4.5, "F02"),
    ("m-select/m-slab", "m-select", "m-slab", 3.0, "F03"),
    ("m-cap/m-slab", "m-cap", "m-slab", 4.5, "F03"),          # the ink line of the map must be seen at all (< 4.5 fails) ...
    ("focus/paper", "focus", "paper", 3.0, "F03"),
]
# graphics and map legibility: reported as warnings by lint_floor.py (the generator always satisfies them)
EXTRA_CHECKS = [
    ("m-cap/m-slab(7:1)", "m-cap", "m-slab", 7.0, "F03"),      # ... and should carry 7:1 (map-craft 5.7); below that is a warning
    ("m-wall/m-slab", "m-wall", "m-slab", 3.0, "F03"),
    ("m-text/m-ground", "m-text", "m-ground", 4.5, "F03"),
    ("m-route/m-slab", "m-route", "m-slab", 3.0, "F03"),
    ("m-dash/m-route", "m-dash", "m-route", 3.0, "F03"),
    ("a-text/paper-2", "a-text", "paper-2", 4.5, "F02"),
    ("b-text/paper-2", "b-text", "paper-2", 4.5, "F02"),
    ("text/paper-2", "text", "paper-2", 4.5, "F01"),
    ("a/paper", "a", "paper", 3.0, "F03"),
]
HEADING_SLACK = 0.5          # --a-text (h1-h4, entity names, links) may be at most this much LOWER in contrast on --paper than --text (FIX-SPEC-5 #1)
HEADING_WARN_RATIO = 0.8     # lint_floor "heading/body": below this share of the body contrast it warns (hand-edited tokens; the generator never gets there)
HEADING_MIN_CHROMA = 0.03    # OKLCH chroma: a walked heading colour below this is no more coloured than the body text (which carries <= 0.026): --text itself is used
MAP_CAP_MIN = 7.05    # what derive_scheme walks --m-cap to (a little over 7 so the rounded hex still clears it)
MAP_WALL_MIN = 3.05   # ... and --m-wall
CLIMB_HUE_MIN = 50.0
CLIMB_TEXT_HUE_MAX = 10.0   # --climb-text is --climb made deeper/lighter: at most this many degrees of hue apart
CHROMA_NEUTRAL = 0.03  # below this the hue of a colour is meaningless (b achromatic -> hue test n/a)


def check_scheme(tokens, include_extra=True):
    """tokens: {name (no '--'): '#RRGGBB'}. Returns a list of dicts
    {id, fg, bg, ratio, min, ok, rule, level} (level 'floor' | 'warn') + the climb hue test."""
    out = []
    for lst, level in ((FLOOR_CHECKS, "floor"), (EXTRA_CHECKS if include_extra else [], "warn")):
        for cid, fg, bg, need, rule in lst:
            if fg not in tokens or bg not in tokens:
                continue
            ratio = contrast(tokens[fg], tokens[bg])
            out.append({"id": cid, "fg": fg, "bg": bg, "ratio": ratio, "min": need, "ok": ratio + 1e-9 >= need,
                        "rule": rule, "level": level})
    if any(c["id"] == "m-cap/m-slab" and not c["ok"] for c in out):          # one finding, not two: the 7:1 warning adds nothing
        out = [c for c in out if c["id"] != "m-cap/m-slab(7:1)"]
    if all(k in tokens for k in ("a-text", "text", "paper")):
        # "heading >= body" (FIX-SPEC-5 #1): the heading colour is never dimmer than the body text. Fail below 4.5:1 on paper;
        # warn when it carries less than HEADING_WARN_RATIO of the body text's own contrast.
        ch, cb_ = contrast(tokens["a-text"], tokens["paper"]), contrast(tokens["text"], tokens["paper"])
        need = max(4.5, cb_ * HEADING_WARN_RATIO)
        out.append({"id": "heading/body", "fg": "a-text", "bg": "paper", "ratio": ch, "min": need, "ok": ch + 1e-9 >= need,
                    "rule": "F02", "level": "floor" if ch + 1e-9 < 4.5 else "warn", "body": cb_})
    if "climb" in tokens and "b" in tokens:
        lb, cb, hb = hex_to_oklch(tokens["b"])
        lc, cc, hc = hex_to_oklch(tokens["climb"])
        if cb < CHROMA_NEUTRAL or cc < CHROMA_NEUTRAL:
            out.append({"id": "climb-hue/b", "fg": "climb", "bg": "b", "ratio": None, "min": CLIMB_HUE_MIN, "ok": True,
                        "rule": "F03", "level": "floor", "note": "achromatic: hue test n/a"})
        else:
            d = hue_distance(hb, hc)
            out.append({"id": "climb-hue/b", "fg": "climb", "bg": "b", "ratio": d, "min": CLIMB_HUE_MIN,
                        "ok": d + 1e-9 >= CLIMB_HUE_MIN, "rule": "F03", "level": "floor", "unit": "deg"})
    if "climb" in tokens and "climb-text" in tokens:
        # the text twin is the same colour, only deeper/lighter: same hue (chroma is gamut-reduced, so allow a few degrees)
        lc, cc, hc = hex_to_oklch(tokens["climb"])
        lt_, ct_, ht_ = hex_to_oklch(tokens["climb-text"])
        if cc < CHROMA_NEUTRAL or ct_ < CHROMA_NEUTRAL:
            out.append({"id": "climb-text-hue/climb", "fg": "climb-text", "bg": "climb", "ratio": None, "min": CLIMB_TEXT_HUE_MAX,
                        "ok": True, "rule": "F02", "level": "floor", "note": "achromatic: hue test n/a"})
        else:
            d = hue_distance(hc, ht_)
            out.append({"id": "climb-text-hue/climb", "fg": "climb-text", "bg": "climb", "ratio": d, "min": CLIMB_TEXT_HUE_MAX,
                        "ok": d <= CLIMB_TEXT_HUE_MAX + 1e-9, "rule": "F02", "level": "floor", "unit": "deg", "max": True})
    return out


# =================================================================================================
# 4. directions library
# =================================================================================================

AXES_VOCAB = {
    "palette_structure": ["two-inks-paper", "one-ink-spot", "dark-ground", "duotone-overprint", "entity-led-neutral",
                          "tinted-ground"],
    "shape.language": ["chamfer", "square", "soft", "pill", "perforated", "notched", "tab", "arched"],
    "divider": ["stripe-band", "double-rule", "perforation", "dotted-leader", "stitch", "airmail-band",
                "dimension-line", "thick-thin", "none"],
    "entity_header": ["table-tent", "placard", "ticket-stub", "index-card", "envelope", "stamp-tile", "masthead",
                      "title-block", "luggage-tag", "specimen-sheet"],
    "entity_token": ["badge", "pin", "plate", "dot", "flag", "stamp"],
    "numerals": ["lining-tabular", "oldstyle", "outlined", "stencil", "split-flap", "roman"],
    "nav": ["lines-top-left", "side-ticks", "tab-strip", "progress-ring", "chapter-rail"],
    "map.projection": ["orbit", "oblique", "exploded", "plan"],
    "map.material": ["paper", "line", "clay", "blueprint", "riso"],
    "density": ["compact", "airy"],
    "texture": ["none", "grain", "halftone", "paper-fiber"],
}
DARK_MODES = ["brand-ink-ground", "neutral-night", "warm-night"]
LIGHTS = ["left", "right", "top"]
FONT_ROLES = ["display", "label", "text", "num", "cjk", "cjk_display"]

CJK_SANS = "'PingFang SC', 'Hiragino Sans GB', 'Noto Sans SC', 'Microsoft YaHei'"
CJK_SERIF = "'Songti SC', 'Noto Serif SC', 'SimSun'"
CJK_FAMILIES = ["pingfang sc", "hiragino sans gb", "noto sans sc", "microsoft yahei", "songti sc", "noto serif sc",
                "simsun", "stsong", "source han sans", "source han serif", "heiti sc", "kaiti sc", "stheiti", "simhei",
                "noto sans cjk", "noto serif cjk", "wenquanyi"]
GENERIC_FAMILIES = ["serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "ui-serif", "ui-sans-serif",
                    "ui-monospace", "ui-rounded", "emoji", "math", "fangsong"]


def load_directions(path=None, fixture=False):
    """Load library/directions.json (or the inline fixture). Raises FileNotFoundError with a clear message."""
    if fixture:
        lib = json.loads(json.dumps(FIXTURE_LIBRARY))
        lib["_path"] = "<fixture>"
        return lib
    p = Path(path) if path else LIBRARY_PATH
    if not p.exists():
        raise FileNotFoundError("directions library not found: %s  (it is written by the library builder: "
                                "library/directions.json)" % p)
    lib = json.loads(p.read_text(encoding="utf-8"))
    if "directions" not in lib or not lib["directions"]:
        raise ValueError("%s has no 'directions' list" % p)
    lib["_path"] = str(p)
    return lib


def direction_by_id(lib, did):
    for d in lib["directions"]:
        if d["id"] == did:
            return d
    raise KeyError("no direction %r in library (have: %s)" % (did, ", ".join(d["id"] for d in lib["directions"])))


def canonical_direction(lib):
    for d in lib["directions"]:
        if d.get("canonical"):
            return d
    return lib["directions"][0]


def library_hash(lib):
    """4-bit check carried in preset codes: lets `draw.py decode` warn when the library changed since the code was made."""
    s = "|".join(d["id"] for d in lib["directions"]) + "|" + str(lib.get("version", 1))
    return zlib.crc32(s.encode("utf-8")) & 0xF


def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _num_range(v):
    return isinstance(v, (list, tuple)) and len(v) == 2 and all(_is_num(x) for x in v)


def _as_list(v):
    if v is None:
        return []
    return list(v) if isinstance(v, (list, tuple)) else [v]


# --------------------------------------------------------------------------------------------------
# hue families (FIX-SPEC-3 A2)
# --------------------------------------------------------------------------------------------------

HUE_ROLES = ["paper", "a", "b", "climb", "night"]   # the order sample() draws them in: a role may only FOLLOW an earlier one
FAMILY_GAP_MIN = 15.0       # two families of one role: ranges at least this far apart (degrees) ...
FAMILY_CENTRE_MIN = 35.0    # ... and centres at least this far apart, or they are one family drawn twice


def hue_families(h):
    """A palette role's `h` -> list of [lo, hi] ranges (the hue families). Accepts a number, one range [lo, hi], or a list of
    ranges [[lo, hi], ...]. A range with hi < lo wraps through 360. Raises ValueError for anything else."""
    if h is None:
        return []
    if _is_num(h):
        return [[float(h), float(h)]]
    if _num_range(h):
        return [[float(h[0]), float(h[1])]]
    if isinstance(h, (list, tuple)) and h and all(_num_range(x) for x in h):
        return [[float(x[0]), float(x[1])] for x in h]
    raise ValueError("a hue is a number, a range [lo, hi] or a list of ranges [[lo, hi], ...]; got %r" % (h,))


def _arc_points(r):
    lo, hi = float(r[0]), float(r[1])
    if hi < lo:
        hi += 360.0
    n = max(1, int(math.ceil(hi - lo)))
    return [(lo + (hi - lo) * i / n) % 360.0 for i in range(n + 1)]


def arc_gap(r1, r2):
    """Smallest angular distance (degrees) between two hue ranges; 0 when they overlap."""
    return min(hue_distance(x, y) for x in _arc_points(r1) for y in _arc_points(r2))


def arc_centre(r):
    lo, hi = float(r[0]), float(r[1])
    if hi < lo:
        hi += 360.0
    return ((lo + hi) / 2.0) % 360.0


def family_leader(pal, role):
    """The role whose family draw decides `role` (follow chain), e.g. climb -> b -> paper. A role without `follow` leads itself."""
    seen = set()
    while isinstance(pal.get(role), dict) and pal[role].get("follow") and role not in seen:
        seen.add(role)
        role = pal[role]["follow"]
    return role


def family_index_of(spec, hue):
    """Which of a role's hue families a sampled hue (degrees) lies in; None if none does (a frozen colour, or a moved climb hue)."""
    for i, (lo, hi) in enumerate(hue_families((spec or {}).get("h"))):
        if hi < lo:
            hi += 360.0
        for shift in (0.0, 360.0):
            if lo - 0.51 <= hue + shift <= hi + 0.51:
                return i
    return None


def family_names(spec, n):
    """The names of a role's families (`names` in directions.json), padded with None to n entries."""
    names = list((spec or {}).get("names") or [])
    return [names[i] if i < len(names) else None for i in range(n)]


# Colour words in a direction's prose against the hue envelopes of its palette (OKLCH hue degrees). A word is backed when
# some role (paper, a, b, climb, night) has EVERY hue family meeting one of the word's bands: the prose must stay true whichever
# family is drawn (FIX-SPEC-3 A2). Neutral words (白 黑 灰 墨 象牙 金 银) name materials or lightness, not a hue, and are
# skipped. The `watch` list says what NOT to do, so it is skipped too, and so are `names` (they name the families).
COLOUR_WORDS = [   # longest first: a match is removed from the text before the shorter words are looked for
    ("靛青", [(235, 295)]), ("青绿", [(150, 215)]), ("墨绿", [(130, 185)]), ("森林绿", [(130, 185)]), ("草绿", [(115, 175)]),
    ("微绿", [(110, 185)]), ("灰绿", [(110, 185)]), ("红褐", [(10, 70)]), ("赭红", [(10, 60)]), ("粉红", [(330, 360), (0, 45)]),
    ("玫红", [(325, 360), (0, 20)]), ("珊瑚红", [(10, 50)]), ("琥珀", [(55, 105)]), ("柠檬黄", [(85, 125)]),
    ("红", [(345, 360), (0, 45)]), ("橙", [(40, 90)]), ("黄", [(85, 125)]), ("绿", [(110, 185)]), ("青", [(165, 260)]),
    ("蓝", [(225, 285)]), ("紫", [(280, 340)]), ("粉", [(325, 360), (0, 45)]), ("褐", [(10, 75)]),
]


def _hue_meets(rng, bands):
    """The family's CENTRE lies inside one of the word's bands (a family that merely touches the band's edge does not back the
    word: a blue-black ink at 280 degrees is not 'violet')."""
    lo, hi = float(rng[0]), float(rng[1])
    if hi < lo:
        hi += 360.0
    mid = (lo + hi) / 2.0
    for b0, b1 in bands:
        for shift in (-360.0, 0.0, 360.0):
            if b0 + shift + 3.0 <= mid <= b1 + shift - 3.0:
                return True
    return False


def _role_backs(role_spec, bands):
    """True when EVERY hue family of this palette role meets one of the bands, and the role has a visible chroma."""
    if not isinstance(role_spec, dict):
        return False
    try:
        fams = hue_families(role_spec.get("h"))
    except ValueError:
        return False
    c = role_spec.get("c")
    cmax = max(_as_list(c)) if c is not None else 0
    return bool(fams) and cmax >= 0.006 and all(_hue_meets(f, bands) for f in fams)


def colour_claims(direction):
    """Advisory strings for colour words in idea / specimen_note / richness that no palette role backs in EVERY one of its
    hue families (so a text that says "violet" fails when the stamp ink may also be red)."""
    pal = direction.get("palette") or {}
    texts = [("idea", direction.get("idea") or ""), ("specimen_note", direction.get("specimen_note") or "")]
    texts += [("richness", t) for t in (direction.get("richness") or [])]
    out = []
    for field, text in texts:
        rest = text
        for word, bands in COLOUR_WORDS:
            if word not in rest:
                continue
            rest = rest.replace(word, " ")
            # night only backs a word when the dark ground is the brand ink made deep (the other modes override its hue/chroma)
            roles = [r for r in HUE_ROLES if r != "night" or pal.get("dark") == "brand-ink-ground"]
            if not any(_role_backs(pal.get(role), bands) for role in roles):
                out.append("%s names a colour (%s) that no palette role guarantees in every hue family: \"%s\"" % (field, word, text[:28]))
    return out


def check_families(did, pal, canonical, errs, warns):
    """The hue families of one direction's palette (FIX-SPEC-3 A2). Appends to errs / warns."""
    counts = {}
    ranges = {}
    for role in HUE_ROLES:
        spec = pal.get(role)
        if not isinstance(spec, dict):
            continue
        try:
            fams = hue_families(spec.get("h"))
        except ValueError as e:
            errs.append("%s: palette.%s.h: %s" % (did, role, e))
            continue
        counts[role], ranges[role] = len(fams), fams
        if canonical and len(fams) > 1:
            errs.append("%s: the canonical direction stays single-family (palette.%s has %d)" % (did, role, len(fams)))
        if len(fams) > 4:
            warns.append("%s: palette.%s has %d hue families (2-4 is plenty)" % (did, role, len(fams)))
        for i in range(len(fams)):
            for j in range(i + 1, len(fams) if not spec.get("follow") else 0):    # a follower may repeat a hue across families
                gap = arc_gap(fams[i], fams[j])
                cen = hue_distance(arc_centre(fams[i]), arc_centre(fams[j]))
                if gap < FAMILY_GAP_MIN:
                    errs.append("%s: palette.%s families %d and %d are %.0f deg apart (< %d): they would read as one" % (
                        did, role, i, j, gap, FAMILY_GAP_MIN))
                elif cen < FAMILY_CENTRE_MIN:
                    warns.append("%s: palette.%s families %d and %d have centres %.0f deg apart (< %d)" % (
                        did, role, i, j, cen, FAMILY_CENTRE_MIN))
        nm = spec.get("names")
        if nm is not None and (not isinstance(nm, list) or len(nm) != len(fams) or not all(isinstance(x, str) and x for x in nm)):
            errs.append("%s: palette.%s.names must list one name per family (%d)" % (did, role, len(fams)))
        elif len(fams) > 1 and nm is None and not spec.get("follow"):
            warns.append("%s: palette.%s has %d families but no `names` (the card summary cannot say which was drawn)" % (did, role, len(fams)))
    for role, spec in pal.items():
        if role not in HUE_ROLES or not isinstance(spec, dict) or not spec.get("follow"):
            continue
        tgt = spec["follow"]
        if tgt not in HUE_ROLES or HUE_ROLES.index(tgt) >= HUE_ROLES.index(role):
            errs.append("%s: palette.%s follows %r: a role can only follow an earlier one (%s)" % (did, role, tgt, ", ".join(HUE_ROLES)))
        elif counts.get(tgt) != counts.get(role):
            errs.append("%s: palette.%s follows %s but has %s families against %s" % (did, role, tgt, counts.get(role), counts.get(tgt)))
    # a non-canonical direction gives its accent 2-4 families (the point of the feature)
    if not canonical and counts.get("b", 1) < 2:
        errs.append("%s: palette.b needs 2-4 hue families (FIX-SPEC-3 A2); `h` is a list of ranges [[lo, hi], ...]" % did)
    # the climb colour stays >= CLIMB_HUE_MIN from b in EVERY pairing the draw can make (else derive_scheme moves it silently)
    if "b" in ranges and "climb" in ranges:
        follow = (pal.get("climb") or {}).get("follow") == "b" and counts.get("b") == counts.get("climb")
        pairs = [(i, i) for i in range(len(ranges["b"]))] if follow else \
            [(i, j) for i in range(len(ranges["b"])) for j in range(len(ranges["climb"]))]
        for i, j in pairs:
            gap = arc_gap(ranges["b"][i], ranges["climb"][j])
            if gap < CLIMB_HUE_MIN + 3:
                errs.append("%s: climb family %d is %.0f deg from b family %d (< %d): let climb follow b, with a hue that clears it" % (
                    did, j, gap, i, CLIMB_HUE_MIN + 3))


PROP_KEYS = ("name", "var", "off", "what")
PROP_NAME_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
PROP_VAR_RE = re.compile(r"--prop-[a-z0-9]+(-[a-z0-9]+)*")
PROP_USE_RE = re.compile(r"var\(\s*(--prop-[a-z0-9-]+)")


def check_props(did, props, errs, warns):
    """directions[].props (FIX-SPEC-4 item 9): optional list of {name, var, off, what}. `name` kebab-case; `var` a `--prop-*` custom
    property the recipe reads; `off` the CSS value that switches the motif off (a bare value: no ; { } or line break); `what` says
    what the motif is. A name and a var occur once per direction."""
    if props is None:
        return
    if not isinstance(props, list):
        errs.append("%s: props must be a list of {name, var, off, what}" % did)
        return
    names, vars_ = set(), set()
    for i, pr in enumerate(props):
        at = "%s: props[%d]" % (did, i)
        if not isinstance(pr, dict):
            errs.append("%s must be an object {name, var, off, what}" % at)
            continue
        for k in PROP_KEYS:
            v = pr.get(k)
            if not isinstance(v, str) or not v.strip():
                errs.append("%s: %r must be a non-empty string" % (at, k))
        extra = sorted(set(pr) - set(PROP_KEYS))
        if extra:
            warns.append("%s has keys the kit does not read: %s" % (at, ", ".join(extra)))
        name, var, off = pr.get("name"), pr.get("var"), pr.get("off")
        if isinstance(name, str) and name.strip():
            at = "%s: props.%s" % (did, name)
            if not PROP_NAME_RE.fullmatch(name):
                errs.append("%s: name must be kebab-case" % at)
            if name in names:
                errs.append("%s: duplicate prop name" % at)
            names.add(name)
        if isinstance(var, str) and var.strip():
            if not PROP_VAR_RE.fullmatch(var):
                errs.append("%s: var %r must be a custom property named --prop-<kebab-case>" % (at, var))
            elif isinstance(name, str) and var != "--prop-" + name:
                warns.append("%s: var %s does not match the name (--prop-%s)" % (at, var, name))
            if var in vars_:
                errs.append("%s: duplicate var %s" % (at, var))
            vars_.add(var)
        if isinstance(off, str) and off.strip() and re.search(r"[;{}\r\n]", off):
            errs.append("%s: off %r must be one bare CSS value (no ; { } or line break): it is written as `%s: <off>;`" % (at, off, var))


def check_props_in_recipe(did, props, css, errs, warns):
    """The recipe has to READ every var the library lists (else `off` does nothing) and every --prop-* it reads has to be listed
    (else nobody can find the switch). Both are warnings: they point at the recipe or at directions.json, whichever is stale."""
    listed = [pr.get("var") for pr in (props or []) if isinstance(pr, dict) and isinstance(pr.get("var"), str)]
    used = set(PROP_USE_RE.findall(css))
    for v in listed:
        if v not in used:
            warns.append("%s: recipes/%s.css never reads var(%s): switching the prop off would change nothing" % (did, did, v))
    for v in sorted(used - set(listed)):
        warns.append("%s: recipes/%s.css reads var(%s) but directions.json does not list it under props" % (did, did, v))
    bare = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for v in sorted(set(re.findall(r"(--prop-[a-z0-9-]+)\s*:", bare))):
        warns.append("%s: recipes/%s.css declares %s itself: tokens.css loads first, so that declaration would beat the off switch (read it with a var() fallback instead)" % (did, did, v))


def props_of(params):
    """The props of a card, [{name, var, off, what}] (a roll made before FIX-SPEC-4 has none)."""
    return [dict((k, pr.get(k, "")) for k in PROP_KEYS) for pr in (params.get("props") or []) if isinstance(pr, dict) and pr.get("var")]


def validate_library(lib, recipes_dir=None):
    """Return (errors, warnings) -- lists of strings -- for a directions library, against BUILD-SPEC section 3.
    recipes_dir: where the recipes live, for the props cross-check (default: assets/recipes next to the library file; False: skip)."""
    errs, warns = [], []
    if recipes_dir is None and lib.get("_path") and lib["_path"] != "<fixture>":
        cand = Path(lib["_path"]).resolve().parent.parent / "assets" / "recipes"
        recipes_dir = cand if cand.is_dir() else False
    ds = lib.get("directions") or []
    if not (10 <= len(ds) <= 12):
        warns.append("library has %d directions (spec: 10-12)" % len(ds))
    ids = [d.get("id") for d in ds]
    if len(set(ids)) != len(ids):
        errs.append("duplicate direction ids")
    for must in ("varsity", "airmail", "heraldry", "departures"):
        if must not in ids:
            errs.append("missing required direction %r" % must)
    canon = [d.get("id") for d in ds if d.get("canonical")]
    if canon != ["varsity"]:
        errs.append("exactly one canonical direction expected and it must be 'varsity' (found %s)" % canon)
    axes = lib.get("axes") or {}

    def vocab(axis):
        if axis in axes and isinstance(axes[axis], dict) and "values" in axes[axis]:
            return list(axes[axis]["values"].keys()) + AXES_VOCAB.get(axis, [])
        return AXES_VOCAB.get(axis, [])

    def check_enum(d, axis, values):
        allowed = vocab(axis)
        for v in _as_list(values):
            if allowed and v not in allowed:
                errs.append("%s: %s value %r not in vocabulary" % (d.get("id"), axis, v))

    dark_n = nonserif = nonsq = 0
    mats, projs = set(), set()
    bounce_lo, bounce_hi = 9.0, 0.0
    still = lively = False
    for d in ds:
        did = d.get("id", "?")
        for key in ("name", "mechanism", "idea", "fits", "weight", "palette", "type", "shape", "divider", "entity_header",
                    "entity_token", "numerals", "nav", "map", "motion", "density", "texture"):
            if key not in d:
                errs.append("%s: missing key %r" % (did, key))
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", str(did)):
            errs.append("%s: id must be kebab-case" % did)
        pal = d.get("palette", {})
        check_enum(d, "palette_structure", pal.get("structure"))
        for role in ("paper", "a", "b", "climb", "night"):
            r = pal.get(role)
            if not isinstance(r, dict):
                errs.append("%s: palette.%s missing" % (did, role))
                continue
            for k, hard in (("l", (0, 1)), ("c", (0, 0.37))):
                v = r.get(k)
                if not (_num_range(v) or _is_num(v)):
                    errs.append("%s: palette.%s.%s must be [lo,hi] or number" % (did, role, k))
                elif any(not (hard[0] <= x <= hard[1]) for x in _as_list(v)):
                    errs.append("%s: palette.%s.%s out of range %s" % (did, role, k, hard))
            try:        # h: a number, [lo, hi], or [[lo, hi], ...] (hue families)
                if not hue_families(r.get("h")):
                    errs.append("%s: palette.%s.h missing" % (did, role))
                elif any(not (-360 <= x <= 720) for f in hue_families(r.get("h")) for x in f):
                    errs.append("%s: palette.%s.h out of range (-360, 720)" % (did, role))
            except ValueError as e:
                errs.append("%s: palette.%s.h: %s" % (did, role, e))
        check_families(did, pal, bool(d.get("canonical")), errs, warns)
        if pal.get("dark") not in DARK_MODES:
            errs.append("%s: palette.dark must be one of %s" % (did, DARK_MODES))
        pl = (pal.get("paper") or {}).get("l")
        if pal.get("structure") == "dark-ground" or (pl and max(_as_list(pl)) < 0.5):
            dark_n += 1
        ty = d.get("type", {})
        for role in FONT_ROLES:
            lst = ty.get(role)
            if not lst or not isinstance(lst, list):
                if role in ("display", "label", "text"):
                    errs.append("%s: type.%s must be a non-empty list of {name, stack, class, google}" % (did, role))
                continue
            for f in lst:
                if not isinstance(f, dict) or "name" not in f or "stack" not in f:
                    errs.append("%s: type.%s entries need name + stack" % (did, role))
        for k in ("label_case", "label_track", "label_stretch", "label_weight", "display_weight", "display_track",
                  "display_leading", "ratio"):
            if k not in ty:
                errs.append("%s: type.%s missing" % (did, k))
        classes = [f.get("class", "") for f in ty.get("display", []) if isinstance(f, dict)]
        if classes and any(c and not str(c).startswith("serif") for c in classes):
            nonserif += 1
        sh = d.get("shape", {})
        check_enum(d, "shape.language", sh.get("language"))
        langs = _as_list(sh.get("language"))
        radius = sh.get("radius", [0, 0])
        if any(l != "square" for l in langs) or max(_as_list(radius) or [0]) > 0:
            nonsq += 1
        check_enum(d, "divider", d.get("divider"))
        check_enum(d, "entity_header", d.get("entity_header"))
        check_enum(d, "entity_token", d.get("entity_token"))
        check_enum(d, "numerals", d.get("numerals"))
        check_enum(d, "nav", d.get("nav"))
        check_enum(d, "density", d.get("density"))
        check_enum(d, "texture", d.get("texture"))
        mp = d.get("map", {})
        check_enum(d, "map.projection", mp.get("projection"))
        check_enum(d, "map.material", mp.get("material"))
        mats.update(_as_list(mp.get("material")))
        projs.update(_as_list(mp.get("projection")))
        if not any(p_ in PROJECTIONS_3D for p_ in _as_list(mp.get("projection"))):
            errs.append("%s: map.projection lists no 3D projection (%s); `--keep projection=3d` needs one (FIX-SPEC A4)" % (
                did, " | ".join(PROJECTIONS_3D)))
        if not any(p_ in PROJECTIONS_ROTATE for p_ in _as_list(mp.get("projection"))):
            errs.append("%s: map.projection lists no rotating projection (%s); `--keep projection=rotate` needs one (FIX-SPEC-3 A1)" % (
                did, " | ".join(PROJECTIONS_ROTATE)))
        for pk in ("pitch", "yaw", "wall_h"):          # one range, or a dict keyed by projection (+ "default")
            spec = mp.get(pk)
            if isinstance(spec, dict):
                for kk, vv in spec.items():
                    if kk != "default" and kk not in PROJECTIONS:
                        errs.append("%s: map.%s has the key %r, which is not a projection" % (did, pk, kk))
                    if not _num_range(vv) and not _is_num(vv):
                        errs.append("%s: map.%s[%s] must be [lo,hi] or a number" % (did, pk, kk))
        for w in colour_claims(d):
            errs.append("%s: %s" % (did, w))
        check_props(did, d.get("props"), errs, warns)
        if recipes_dir:
            rp = Path(recipes_dir) / ("%s.css" % did)
            if rp.is_file():
                check_props_in_recipe(did, d.get("props"), rp.read_text(encoding="utf-8", errors="replace"), errs, warns)
        mo = d.get("motion", {})
        if _num_range(mo.get("bounce")):
            bounce_lo = min(bounce_lo, mo["bounce"][0])
            bounce_hi = max(bounce_hi, mo["bounce"][1])
            if mo["bounce"][1] <= 0.04 and _num_range(mo.get("dur")) and mo["dur"][1] >= 0.5:
                still = True
            if mo["bounce"][1] >= 0.2:
                lively = True
        if not d.get("canonical") and not (0.2 <= float(d.get("weight", 1.0)) <= 3.0):
            warns.append("%s: weight %s outside 0.2-3" % (did, d.get("weight")))
        for k in ("richness", "watch"):
            if not d.get(k):
                warns.append("%s: no %r list" % (did, k))
        # a sampled card must come out clean: try one mode card
        try:
            sample(d, random.Random(1), None, None, mode=True)
        except Exception as e:  # noqa
            errs.append("%s: sample() failed: %r" % (did, e))
    if dark_n < 3:
        warns.append("only %d directions have a dark/deep ground (spec: >= 3)" % dark_n)
    if nonserif < 3:
        warns.append("only %d directions can show a non-serif display class (spec: >= 3)" % nonserif)
    if nonsq < 3:
        warns.append("only %d directions have radius>0 or a non-square shape language (spec: >= 3)" % nonsq)
    if len(mats) < 4:
        warns.append("only %d map materials used (spec: >= 4)" % len(mats))
    if len(projs) < 3:
        warns.append("only %d map projections used (spec: >= 3)" % len(projs))
    if not still:
        warns.append("no 'still and heavy' motion (dur up to >= 0.5 with bounce <= 0.04)")
    if not lively:
        warns.append("no 'lively' motion (bounce upper bound >= 0.2)")
    return errs, warns


# --------------------------------------------------------------------------------------------------
# inline fixture library (3 directions) -- used by every --selftest so nothing depends on other builders' files
# --------------------------------------------------------------------------------------------------

def _f(name, stack, cls, google=None):
    return {"name": name, "stack": stack, "class": cls, "google": google or name}


FIXTURE_LIBRARY = {
    "version": 1,
    "axes": {},
    "directions": [
        {   # 原站取值 / the source site, as a direction
            "id": "varsity", "name": {"en": "Varsity", "cn": "校队"}, "mechanism": "varsity athletics",
            "idea": "fixture: chalk paper, navy structure, red act, slab display, wide caps labels, chamfer",
            "fits": ["campus", "competition", "university"], "weight": 0.15, "canonical": True,
            "palette": {"structure": "two-inks-paper",
                        "paper": {"l": [0.965, 0.98], "c": [0.004, 0.009], "h": [85, 100]},
                        "a": {"l": [0.28, 0.34], "c": [0.06, 0.09], "h": [255, 265]},
                        "b": {"l": [0.50, 0.55], "c": [0.19, 0.22], "h": [22, 28]},
                        "climb": {"l": [0.55, 0.65], "c": [0.12, 0.16], "h": [84, 96]},
                        "night": {"l": [0.18, 0.22], "c": [0.04, 0.06], "h": [255, 262]}, "dark": "brand-ink-ground"},
            "type": {"display": [_f("Zilla Slab", "'Zilla Slab', Rockwell, 'Roboto Slab', Georgia, serif", "slab")],
                     "label": [_f("Archivo", "Archivo, 'Helvetica Neue', Arial, sans-serif", "sans-wide")],
                     "text": [_f("System UI", "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", "system", "")],
                     "num": [_f("Zilla Slab", "'Zilla Slab', Rockwell, Georgia, serif", "slab")],
                     "cjk": [{"name": "PingFang", "stack": CJK_SANS}],
                     "cjk_display": [{"name": "PingFang", "stack": CJK_SANS}],
                     "label_case": ["uppercase"], "label_track": [0.12, 0.18], "label_stretch": ["125%"],
                     "label_weight": [600, 700], "display_weight": [700, 700], "display_track": [-0.02, -0.01],
                     "display_leading": [0.9, 1.0], "ratio": [1.25, 1.333]},
            "shape": {"language": ["chamfer"], "radius": [0, 0], "chamfer": [8, 8]},
            "divider": ["stripe-band"], "entity_header": ["table-tent"], "entity_token": ["badge"],
            "numerals": ["lining-tabular"], "nav": ["lines-top-left"],
            "map": {"projection": ["orbit"], "material": ["paper"], "pitch": [30, 34], "yaw": [30, 34],
                    "wall_h": [1.0, 1.0], "light": ["left"], "dim": [0.2, 0.28]},
            "motion": {"dur": [0.5, 0.55], "bounce": [0.0, 0.0], "press": [0.97, 0.97]},
            "density": ["airy"], "texture": ["none"],
            "richness": ["fixture"], "watch": ["fixture"], "specimen_note": "fixture"},
        {
            "id": "airmail", "name": {"en": "Par Avion", "cn": "寄往世界"}, "mechanism": "postal system",
            "idea": "fixture: stamps, postmarks, air-mail bands",
            "fits": ["letter", "international", "application", "travel", "exchange"], "weight": 1.0, "canonical": False,
            "palette": {"structure": "two-inks-paper",
                        "paper": {"l": [0.95, 0.98], "c": [0.004, 0.02], "h": [70, 95]},
                        "a": {"l": [0.24, 0.36], "c": [0.08, 0.15], "h": [255, 272]},
                        "b": {"l": [0.48, 0.58], "c": [0.16, 0.22], "h": [[20, 32], [148, 162]], "names": ["postal red", "customs green"]},
                        "climb": {"l": [0.70, 0.80], "c": [0.13, 0.18], "h": [[95, 110], [250, 262]], "follow": "b"},
                        "night": {"l": [0.16, 0.22], "c": [0.03, 0.07], "h": [255, 270]}, "dark": "brand-ink-ground"},
            "type": {"display": [_f("Gloock", "Gloock, 'Big Caslon', 'Hoefler Text', Georgia, serif", "serif-display")],
                     "label": [_f("IBM Plex Mono", "'IBM Plex Mono', Menlo, monospace", "mono")],
                     "text": [_f("Source Serif 4", "'Source Serif 4', Georgia, serif", "serif-text"),
                              _f("System UI", "-apple-system, 'Segoe UI', Roboto, sans-serif", "system", "")],
                     "num": [_f("IBM Plex Mono", "'IBM Plex Mono', Menlo, monospace", "mono")],
                     "cjk": [{"name": "Songti", "stack": CJK_SERIF}, {"name": "PingFang", "stack": CJK_SANS}],
                     "cjk_display": [{"name": "Songti", "stack": CJK_SERIF}],
                     "label_case": ["uppercase", "none"], "label_track": [0.06, 0.14], "label_stretch": ["normal"],
                     "label_weight": [500, 700], "display_weight": [400, 700], "display_track": [-0.02, 0.0],
                     "display_leading": [0.9, 1.05], "ratio": [1.25, 1.414]},
            "shape": {"language": ["perforated", "square"], "radius": [0, 2], "chamfer": [0, 0]},
            "divider": ["airmail-band", "perforation", "double-rule"], "entity_header": ["envelope", "stamp-tile"],
            "entity_token": ["stamp", "badge"], "numerals": ["lining-tabular", "outlined"],
            "nav": ["lines-top-left", "tab-strip"],
            "map": {"projection": ["orbit", "exploded"], "material": ["paper", "line"], "pitch": [35, 55],
                    "yaw": [-35, 35], "wall_h": [0.8, 1.2], "light": ["left", "top"], "dim": [0.18, 0.32]},
            "motion": {"dur": [0.35, 0.5], "bounce": [0.0, 0.12], "press": [0.96, 0.985]},
            "density": ["compact", "airy"], "texture": ["none"],
            "richness": ["fixture"], "watch": ["fixture"], "specimen_note": "fixture"},
        {
            "id": "scoreboard", "name": {"en": "Scoreboard", "cn": "记分牌"}, "mechanism": "arena display",
            "idea": "fixture: dark ground, LED amber, split-flap numerals, blueprint map",
            "fits": ["competition", "sport", "tournament", "campus"], "weight": 1.0, "canonical": False,
            "palette": {"structure": "dark-ground",
                        "paper": {"l": [0.16, 0.21], "c": [0.02, 0.05], "h": [250, 275]},
                        "a": {"l": [0.82, 0.90], "c": [0.12, 0.17], "h": [[85, 100], [190, 205]], "names": ["LED amber", "LED cyan"]},
                        "b": {"l": [0.68, 0.76], "c": [0.15, 0.20], "h": [[140, 160], [20, 35]], "names": ["go green", "stop red"]},
                        "climb": {"l": [0.72, 0.80], "c": [0.12, 0.17], "h": [[330, 350], [190, 205]], "follow": "b"},
                        "night": {"l": [0.11, 0.15], "c": [0.01, 0.03], "h": [[250, 275], [170, 185]], "follow": "a"}, "dark": "neutral-night"},
            "type": {"display": [_f("Oswald", "Oswald, 'Arial Narrow', Impact, sans-serif", "condensed")],
                     "label": [_f("Space Grotesk", "'Space Grotesk', 'Helvetica Neue', sans-serif", "grotesk")],
                     "text": [_f("Inter", "Inter, 'Helvetica Neue', Arial, sans-serif", "sans")],
                     "num": [_f("Oswald", "Oswald, 'Arial Narrow', sans-serif", "condensed")],
                     "cjk": [{"name": "PingFang", "stack": CJK_SANS}],
                     "cjk_display": [{"name": "PingFang", "stack": CJK_SANS}],
                     "label_case": ["uppercase"], "label_track": [0.08, 0.16], "label_stretch": ["normal", "112.5%"],
                     "label_weight": [500, 700], "display_weight": [500, 700], "display_track": [0.0, 0.03],
                     "display_leading": [0.95, 1.05], "ratio": [1.2, 1.333]},
            "shape": {"language": ["notched", "soft"], "radius": [3, 8], "chamfer": [0, 6]},
            "divider": ["dotted-leader", "thick-thin"], "entity_header": ["placard", "title-block"],
            "entity_token": ["plate", "dot"], "numerals": ["split-flap", "lining-tabular"],
            "nav": ["side-ticks", "chapter-rail"],
            "map": {"projection": ["plan", "exploded", "oblique"], "material": ["blueprint", "line", "clay"],
                    "pitch": [60, 85], "yaw": [-20, 20], "wall_h": [0.6, 1.0], "light": ["top", "right"],
                    "dim": [0.15, 0.25]},
            "motion": {"dur": [0.25, 0.4], "bounce": [0.15, 0.3], "press": [0.94, 0.97]},
            "density": ["compact"], "texture": ["grain", "none"],
            "richness": ["fixture"], "watch": ["fixture"], "specimen_note": "fixture"},
    ],
}


# =================================================================================================
# 5. sampling
# =================================================================================================

KEEP_ALIASES = {"shape": "language", "shape_language": "language", "token": "entity_token", "header": "entity_header",
                "label_text": "label", "cjk-display": "cjk_display", "wall": "wall_h", "m_label_case": "map_label_case",
                "case": "label_case", "stretch": "label_stretch", "ground_mode": "dark", "lang": "lead"}
KEEP_KEYS = ["direction", "structure", "palette", "paper", "a", "b", "climb", "night", "dark",
             "display", "label", "text", "num", "cjk", "cjk_display",
             "label_case", "label_track", "label_stretch", "label_weight", "display_weight", "display_track",
             "display_leading", "ratio", "language", "radius", "chamfer", "divider", "entity_header", "entity_token",
             "numerals", "nav", "projection", "material", "pitch", "yaw", "wall_h", "light", "dim", "map_label_case",
             "dur", "bounce", "press", "density", "texture", "lead"]
LEADS = ["en", "zh"]
PROJECTIONS = ["orbit", "oblique", "exploded", "plan"]
PROJECTIONS_3D = ["orbit", "oblique", "exploded"]
PROJECTIONS_ROTATE = ["orbit", "exploded"]    # both turn on drag; oblique has its yaw locked (drag pans), plan is top-down
PITCH_3D = (32, 46)           # the tilt a 3D projection gets when its direction only has a plan-view pitch envelope
_HEX_RE = re.compile(r"^#?[0-9a-fA-F]{3}([0-9a-fA-F]{3})?$")


def parse_keep(items):
    """['palette=#123456,#abcdef', 'display="Libre Franklin"', 'label_case=none'] -> {'palette': [...], 'display': ..}.
    Raises ValueError on unknown keys (message lists the valid ones).
    lead=en|zh              the primary language of bilingual pairs (default en)
    projection=3d           any 3D projection (orbit | oblique | exploded); resolved per direction in sample()
    projection=rotate       a projection that turns when you drag: orbit | exploded (oblique pans, plan is flat)
    projection=<value>      that exact projection, even outside the direction's envelope (recorded in `adjusted`)"""
    keep = {}
    for it in items or []:
        if "=" not in it:
            raise ValueError("--keep expects axis=value, got %r" % it)
        k, v = it.split("=", 1)
        k = k.strip().lower().replace("-", "_")
        k = KEEP_ALIASES.get(k, k)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        if k not in KEEP_KEYS:
            raise ValueError("unknown --keep axis %r. valid: %s" % (k, ", ".join(KEEP_KEYS)))
        if k == "palette":
            hexes = [norm_hex(x) for x in re.split(r"[,\s]+", v) if x]
            if not 1 <= len(hexes) <= 4:
                raise ValueError("palette= takes 1-4 hex colours (a,b[,paper[,climb]])")
            keep[k] = hexes
        elif k in ("paper", "a", "b", "climb", "night"):
            keep[k] = norm_hex(v)
        elif k == "direction":
            keep[k] = [x for x in re.split(r"[,|]", v) if x]
        elif k == "lead":
            v = v.lower()
            v = {"cn": "zh", "chinese": "zh", "zh-cn": "zh", "english": "en"}.get(v, v)
            if v not in LEADS:
                raise ValueError("lead= takes en or zh, got %r" % v)
            keep[k] = v
        elif k == "projection":
            v = v.lower()
            v = {"rotatable": "rotate", "rotation": "rotate", "turn": "rotate", "spin": "rotate"}.get(v, v)
            if v not in PROJECTIONS + ["3d", "rotate"]:
                raise ValueError("projection= takes rotate, 3d, %s; got %r" % (", ".join(PROJECTIONS), v))
            keep[k] = v
        else:
            keep[k] = v
    return keep


def has_keep(keep, name):
    """A frozen axis counts even when its value looks falsy (radius=0, yaw=0, bounce=0)."""
    return name in keep and keep[name] is not None and keep[name] != ""


class Draw(object):
    """Wraps random.Random so that EVERY parameter consumes exactly one random number (stable results whatever --keep
    overrides), and so mode=True yields the 'typical card' of a direction (first enum value, range midpoints).
    The rule for sample(): DRAW first, then let a frozen (--keep) value override the draw. Never skip a draw because a value
    is frozen, or every later parameter of the card would move (FIX-SPEC A5)."""

    def __init__(self, rng, steer=None, mode=False):
        self.rng, self.steer, self.mode = rng, steer, mode
        self.last_u = 0.5

    def u(self):
        v = self.rng.random()
        self.last_u = 0.5 if self.mode else v
        return self.last_u

    def pick(self, seq):
        seq = _as_list(seq)
        v = self.rng.random()
        self.last_u = 0.5 if self.mode else v
        if not seq:
            return None
        return seq[0] if self.mode else seq[min(len(seq) - 1, int(v * len(seq)))]

    def pick_at(self, seq, u):
        """The element of seq that an earlier draw `u` (Draw.last_u) selects. Consumes nothing."""
        seq = _as_list(seq)
        if not seq:
            return None
        return seq[0] if self.mode else seq[min(len(seq) - 1, int(u * len(seq)))]

    def num(self, spec, bold_high=True, hard=None, nd=3, default=0.0, u=None):
        """spec: number | [lo, hi]. Steering widens toward / contracts away from the bold end.
        u: reuse an earlier draw instead of consuming a new one (a second reading of the same parameter)."""
        if u is None:
            u = self.u()
        if spec is None:
            return default
        if _is_num(spec):
            return spec
        lo, hi = float(spec[0]), float(spec[1])
        if lo > hi:
            lo, hi = hi, lo
        w = hi - lo
        s = self.steer
        if s == "bolder":
            if bold_high:
                hi += 0.25 * w
            else:
                lo -= 0.25 * w
            t = 1 - (1 - u) ** 1.5
        elif s == "safer":
            if bold_high:
                hi -= 0.4 * w
            else:
                lo += 0.4 * w
            t = u ** 1.5
        else:
            t = u
        if hard:
            lo, hi = max(lo, hard[0]), min(hi, hard[1])
            if lo > hi:
                lo = hi = max(hard[0], min(hard[1], lo))
        v = (lo + t * (hi - lo)) if (bold_high or s is None) else (hi - t * (hi - lo))
        return round(v, nd)

    def hue(self, spec, default=0.0):
        """One hue from a single range [lo, hi] (or a number): one draw. For a role with hue families call family() first."""
        u = self.u()
        if spec is None:
            return default
        if _is_num(spec):
            return float(spec) % 360.0
        lo, hi = float(spec[0]), float(spec[1])
        if hi < lo:
            hi += 360.0
        return (lo + u * (hi - lo)) % 360.0

    def family(self, n):
        """The index of the hue family a role takes, out of n. ALWAYS one draw, also when n is 1 (or 0), so the RNG runs the
        same whether a role has one family or four, and whether or not a later role follows it (FIX-SPEC-3 A2)."""
        u = self.u()
        if n <= 1 or self.mode:
            return 0
        return min(n - 1, int(u * n))


def spec_for(spec, projection):
    """A map envelope entry (pitch / yaw / wall_h) is one range for every projection, or a dict keyed by projection
    (+ optional "default"), e.g. {"plan": [80, 88], "exploded": [30, 44]}. Returns the range that applies."""
    if isinstance(spec, dict):
        if projection in spec:
            return spec[projection]
        if "default" in spec:
            return spec["default"]
        return next(iter(spec.values())) if spec else None
    return spec


def _sample_lch(dr, spec, default, fam=None, role=None):
    """One colour of a palette role: L, C, the hue FAMILY (one draw), the hue inside it (one draw).
    fam: {role: family index} of the roles drawn so far; this role's index is stored there. A role with `"follow": "<role>"`
    takes the index of that earlier role (same number of families) instead of its own draw."""
    spec = spec or {}
    L = dr.num(spec.get("l", default[0]), False, (0.0, 1.0), 4)
    C = dr.num(spec.get("c", default[1]), True, (0.0, 0.37), 4)
    fams = hue_families(spec.get("h", default[2]))
    idx = dr.family(len(fams))
    lead = spec.get("follow")
    if lead and fam is not None and lead in fam and len(fams) > 1:
        idx = min(fam[lead], len(fams) - 1)
    if fam is not None and role:
        fam[role] = idx
    H = dr.hue(fams[idx] if fams else None, default[2])
    return (L, C, H)


def _split_stack(stack):
    parts, cur, q = [], "", None
    for ch in stack:
        if q:
            cur += ch
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
            cur += ch
        elif ch == ",":
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts


def _unq(s):
    return s.strip().strip("\"'").strip().lower()


def stack_has_cjk(stack):
    return any(_unq(p) in CJK_FAMILIES for p in _split_stack(stack))


def with_cjk(stack, cjk_stack):
    """Latin stack + CJK families before the trailing generic family (so Chinese falls back in the same genre)."""
    parts = _split_stack(stack)
    cj = _split_stack(cjk_stack)
    generics = []
    while parts and _unq(parts[-1]) in GENERIC_FAMILIES:
        generics.insert(0, parts.pop())
    cj_nogen = [p for p in cj if _unq(p) not in GENERIC_FAMILIES]
    cj_gen = [p for p in cj if _unq(p) in GENERIC_FAMILIES]
    have = {_unq(p) for p in parts}
    merged = parts + [p for p in cj_nogen if _unq(p) not in have]
    tail = generics or cj_gen or ["sans-serif"]
    return ", ".join(merged + tail)


def _font_pick(dr, direction_type, role, forced):
    lst = direction_type.get(role) or []
    entry = dr.pick(lst) if lst else None
    if forced:
        match = [f for f in lst if f.get("name", "").lower() == forced.lower()]
        if match:
            entry = match[0]
        else:
            ref = lst[0] if lst else {"stack": "system-ui, sans-serif", "class": "custom"}
            generic = _split_stack(ref["stack"])[-1] if ref.get("stack") else "sans-serif"
            fam = forced if re.fullmatch(r"[A-Za-z0-9\-]+", forced) else "'%s'" % forced
            entry = {"name": forced, "stack": "%s, %s" % (fam if " " not in forced else "'%s'" % forced, generic),
                     "class": ref.get("class", "custom"), "google": forced, "forced": True}
    if entry is None:
        entry = {"name": "system", "stack": "system-ui, sans-serif", "class": "system", "google": ""}
    return dict(entry)


def _fmt(x, nd=4):
    s = ("%." + str(nd) + "f") % x
    s = s.rstrip("0").rstrip(".") if "." in s else s
    return "0" if s in ("-0", "") else s


def type_scale(ratio, base_min, base_max, vmin=360.0, vmax=1200.0):
    """Utopia-style fluid steps -1..5 -> CSS clamp() strings. Ratio at the small end is 0.05 lower (min 1.125)."""
    r_max = ratio
    r_min = max(1.125, round(ratio - 0.05, 3))
    out = {}
    for i in range(-1, 6):
        mn, mx = base_min * (r_min ** i), base_max * (r_max ** i)
        if mx < mn:
            mn, mx = mx, mn
        slope = (mx - mn) / (vmax - vmin)
        inter = mn - slope * vmin
        out[str(i)] = "clamp(%srem, %srem + %svw, %srem)" % (_fmt(mn / 16), _fmt(inter / 16), _fmt(slope * 100), _fmt(mx / 16))
    return out


def _stretch_value(s):
    s = str(s).strip()
    return "normal" if s in ("", "normal", "100%") else s


def _stretch_class(s):
    s = _stretch_value(s)
    if s == "normal":
        return "normal"
    try:
        v = float(s.rstrip("%"))
    except ValueError:
        return "normal"
    return "wide" if v > 100 else ("condensed" if v < 100 else "normal")


def _lum_dark(h):
    return rel_luminance(h) < 0.179


def _push_for_on(fill, P, T, min_vs_ground=None):
    """fill reaches 4.5 neither with P nor with T on top: move its L the shortest way until one of them works
    (optionally keeping contrast(fill, P) >= min_vs_ground, which excludes the candidate that sinks into the ground)."""
    cands = []
    lch = hex_to_oklch(fill)
    for onc in (P, T):
        h = fit_L(lch, [onc], 4.58)
        cands.append((abs(hex_to_oklch(h)[0] - lch[0]), h))
    cands.sort()
    if min_vs_ground is not None:
        good = [c for c in cands if contrast(c[1], P) >= min_vs_ground]
        if good:
            return good[0][1]
    return cands[0][1]


def _map_colors(material, P, P2, T, A, B, is_dark, u):
    """Map materials for one scheme. See BUILD-SPEC 2.2 / assets/engine/venue-map.js.
    ground = what the buildings stand on; slab = floor plate; room = room floor; block = solid blocks (stairs, wc);
    wall = wall faces; cap = wall tops; text = labels; route/select = accent; halo = outline under the route."""
    # light scheme: P2 is the darker one; dark scheme: P2 is the lighter one
    if not _lum_dark(P):
        lo, hi = P2, P
    else:
        lo, hi = P, P2
    m = {}
    if material == "line":
        m.update({"m-ground": P, "m-slab": P, "m-room": P, "m-block": mix_ok(P, T, 0.07), "m-wall": mix_ok(P, T, 0.55),
                  "m-cap": A, "m-text": T})
    elif material == "clay":
        slab = mix_ok(hi, A, 0.05 if is_dark else 0.10)      # on a dark ground the pull toward the light ink stays small: the cap must still reach 7:1
        m.update({"m-ground": mix_ok(lo, T, 0.06), "m-slab": slab, "m-room": mix_ok(slab, T, 0.05),
                  "m-block": mix_ok(slab, T, 0.11), "m-wall": mix_ok(slab, T, 0.22),
                  "m-cap": mix_ok(slab, P if not is_dark else P2, 0.55), "m-text": T})
    elif material == "blueprint":
        La, Ca, Ha = hex_to_oklch(A)
        if La < 0.55 and Ca >= 0.04:
            C0, H0 = Ca, Ha                  # a dark ink: the plan is drawn in the brand ink
        else:
            _, C0, H0 = hex_to_oklch(P)      # a pale/bright accent: take the page ground's hue instead
        C0 = min(max(C0, 0.05), 0.10)
        base = 0.20 if is_dark else 0.27
        step = 0.035 + 0.01 * u[7]
        ground = oklch_to_hex(base, C0, H0)
        light_line = oklch_to_hex(0.90, 0.035, H0)
        m.update({"m-ground": ground, "m-slab": oklch_to_hex(base + step, C0, H0),
                  "m-room": oklch_to_hex(base + 2 * step, C0, H0), "m-block": oklch_to_hex(base + 3.2 * step, C0, H0),
                  "m-wall": oklch_to_hex(0.80, 0.05, H0), "m-cap": light_line, "m-text": light_line})
    elif material == "riso":
        m.update({"m-ground": P, "m-slab": mix_ok(P, A, 0.10), "m-room": mix_ok(P, B, 0.15),
                  "m-block": mix_ok(P, A, 0.24), "m-wall": A, "m-cap": A, "m-text": T})
    else:  # paper (source look family): light slabs on a tinted ground, dark caps
        slab = hi
        m.update({"m-ground": lo, "m-slab": slab, "m-room": mix_ok(slab, A, 0.07), "m-block": mix_ok(slab, T, 0.12),
                  "m-wall": mix_ok(slab, T, 0.38), "m-cap": A, "m-text": T})
    return m


def derive_scheme(ground_lch, a_lch, b_lch, climb_lch, material, u, adj, label, rederive):
    """One colour scheme (all section 2.1 + 2.2 colour tokens) from a ground colour and three inks.
    rederive=True: the inks come from the other scheme and are first moved to read on this ground.
    Every floor rule is enforced by walking OKLCH lightness; anything moved outside its envelope goes to `adj`."""
    gl, gc, gh = ground_lch
    P = oklch_to_hex(gl, gc, gh)
    dark = _lum_dark(P)
    sgn = 1 if dark else -1                      # +1 = "raised" is lighter
    gl, gc, gh = hex_to_oklch(P)

    def p2_of(Lg):
        return oklch_to_hex(Lg + sgn * (0.026 + 0.026 * u[0]), gc * 1.12 + 0.003, gh)

    # the ground must let a body text reach 7:1 on both paper and paper-2
    th = gh if (u[1] < 0.55 or a_lch[1] < 0.02) else a_lch[2]
    ext_text = oklch_to_hex(0.965 if dark else 0.14, 0.01, th)
    moved = 0
    P2 = p2_of(gl)
    while min(contrast(ext_text, P), contrast(ext_text, P2)) < 7.4 and moved < 60:
        gl -= sgn * 0.01
        P = oklch_to_hex(gl, gc, gh)
        P2 = p2_of(gl)
        moved += 1
    if moved:
        adj.append("%s.paper: lightness moved %+.2f so body text can reach 7:1" % (label, -sgn * 0.01 * moved))
        dark = _lum_dark(P)
        sgn = 1 if dark else -1

    tc = 0.010 + 0.016 * u[2]
    tl0 = (0.97 - 0.05 * u[3]) if dark else (0.19 + 0.06 * u[3])
    T = fit_L((tl0, tc, th), [P, P2], 7.1, sgn)
    sl0 = (0.74 - 0.06 * u[4]) if dark else (0.48 + 0.07 * u[4])
    S = fit_L((sl0, tc * 0.9, th), [P, P2], 4.58, sgn)
    R = fit_L((gl + sgn * (0.10 + 0.06 * u[5]), gc * 1.1 + 0.004, gh), [P], 1.3, sgn)

    def ink(lch, tag):
        h = oklch_to_hex(*lch)
        if rederive:
            h2 = fit_L(hex_to_oklch(h), [P], 3.06)
            if h2 != h:
                adj.append("%s.%s: lightness re-fitted to this ground (>= 3:1 vs paper)" % (label, tag))
            h = h2
        if max(contrast(h, P), contrast(h, T)) < 4.58:
            h2 = _push_for_on(h, P, T, 3.06 if rederive else None)
            adj.append("%s.%s: %s -> %s so that a label colour can sit on it at 4.5:1" % (label, tag, h, h2))
            h = h2
        return h

    A = ink(a_lch, "a")
    B = ink(b_lch, "b")
    on_a = P if contrast(A, P) >= contrast(A, T) else T
    on_b = P if contrast(B, P) >= contrast(B, T) else T

    def text_of(h, tag):
        if min(contrast(h, P), contrast(h, P2)) >= 4.58:
            return h
        t = fit_L(hex_to_oklch(h), [P, P2], 4.58, sgn)
        return t

    AT, BT = text_of(A, "a-text"), text_of(B, "b-text")
    AT0 = AT                                     # the plain "A as text" colour: the focus ring below keeps drawing from it

    def heading_of(h):
        """--a-text is the HEADING colour (h1-h4, entity names, links): never dimmer than the body text (FIX-SPEC-5 #1). Its
        contrast on paper is walked (OKLCH lightness, hue and chroma kept) to at least contrast(--text) - HEADING_SLACK.
        If that walk would leave no accent in it (chroma < HEADING_MIN_CHROMA: an ink-accent direction on a dark ground),
        or cannot be reached, the heading is --text itself."""
        need = contrast(T, P) - HEADING_SLACK
        if contrast(h, P) >= need and contrast(h, P2) >= 4.58:
            return h
        cand = fit_L(hex_to_oklch(h), [P], need, sgn)
        if contrast(cand, P) < need or min(contrast(cand, P), contrast(cand, P2)) < 4.58 or hex_to_oklch(cand)[1] < HEADING_MIN_CHROMA:
            return T
        return cand

    AT = heading_of(AT)
    mc = _map_colors(material, P, P2, T, A, B, dark, u)
    slab = mc["m-slab"]
    ground_m = mc["m-ground"]
    # the ink line of the map (--m-cap: wall caps, rings, pins, icon strokes) carries 7:1 on the slab and the wall faces 3:1,
    # in light and dark (FIX-SPEC-3 A3, map-craft 5.7): walk OKLCH lightness away from the slab, hue and chroma kept
    mc["m-cap"] = ink_on(mc["m-cap"], slab, MAP_CAP_MIN)
    mc["m-wall"] = ink_on(mc["m-wall"], slab, MAP_WALL_MIN)
    # map text must read on the map ground
    if contrast(mc["m-text"], ground_m) < 4.58:
        mc["m-text"] = fit_L(hex_to_oklch(mc["m-text"]), [ground_m, slab], 4.58)
    route = fit_L(hex_to_oklch(B), [slab, ground_m], 3.05) if min(contrast(B, slab), contrast(B, ground_m)) < 3.05 else B
    mc["m-route"] = route
    mc["m-select"] = route    # the selection EDGE: the route colour already clears 3:1 on the slab
    # the selection TINT: the room colour pulled 10-16 % toward the edge colour; no contrast floor (it is a wash, not a mark).
    # u[8] is a spare draw of u_light/u_dark, so no other value moves.
    mc["m-select-fill"] = mix_ok(mc["m-room"], route, 0.10 + 0.06 * u[8])
    if contrast(mc["m-text"], mc["m-select-fill"]) < 4.5:       # labels sit on the selected room: take the palest tint
        mc["m-select-fill"] = mix_ok(mc["m-room"], route, 0.10)
    mc["m-route-halo"] = ground_m if material == "blueprint" else (hi_of(P, P2) if not dark else lo_of(P, P2))
    mc["m-dash"] = P if contrast(P, route) >= contrast(T, route) else T
    if contrast(mc["m-dash"], route) < 3.05:
        mc["m-dash"] = fit_L(hex_to_oklch(mc["m-dash"]), [route], 3.05)

    # climb: >= 50 degrees from b, >= 3:1 on the slab
    cl, cc, ch = climb_lch
    lb, cb, hb = hex_to_oklch(B)
    if cc < 0.06:
        adj.append("%s.climb: chroma raised %.3f -> 0.060 (hue test needs a real hue)" % (label, cc))
        cc = 0.06
    if cb >= CHROMA_NEUTRAL:
        d = hue_distance(hb, ch)
        if d < CLIMB_HUE_MIN + 3:
            side = 1 if ((ch - hb) % 360.0) < 180.0 else -1
            newh = (hb + side * (CLIMB_HUE_MIN + 6)) % 360.0
            adj.append("%s.climb: hue %.0f -> %.0f deg (%.0f deg from b was < %d)" % (label, ch, newh, d, CLIMB_HUE_MIN))
            ch = newh
    CL = fit_L((cl, cc, ch), [slab], 3.05, sgn if not dark else 1)
    for _ in range(8):  # quantisation can eat a degree or two: verify on the final hex
        lc2, cc2, hc2 = hex_to_oklch(CL)
        if cb < CHROMA_NEUTRAL or cc2 < CHROMA_NEUTRAL or hue_distance(hb, hc2) >= CLIMB_HUE_MIN + 0.5:
            break
        side = 1 if ((hc2 - hb) % 360.0) < 180.0 else -1
        ch = (ch + side * 4.0) % 360.0
        CL = fit_L((cl, max(cc, 0.07), ch), [slab], 3.05, sgn if not dark else 1)
    mc["m-climb"] = CL
    if contrast(CL, slab) < 3.0:
        adj.append("%s.climb: could not reach 3:1 on the slab" % label)
    # the TEXT twin of climb: same hue (and chroma where the gamut allows), lightness walked to 4.5:1 on paper AND paper-2
    CT = CL if min(contrast(CL, P), contrast(CL, P2)) >= 4.58 else fit_L(hex_to_oklch(CL), [P, P2], 4.58, sgn)

    FO = BT if (u[6] < 0.7 or contrast(AT0, P) < 3.0) else AT0
    out = {"paper": P, "paper-2": P2, "rule": R, "text": T, "sub": S, "a": A, "a-text": AT, "on-a": on_a, "b": B,
           "b-text": BT, "on-b": on_b, "climb": CL, "climb-text": CT, "focus": FO}
    out.update(mc)
    return out


def ink_on(h, bg, need):
    """h unchanged if it already clears `need`:1 on bg, else its OKLCH lightness walked (away from bg; hue and chroma kept) to
    the nearest value that does. If neither end can reach it (a mid-tone ground) the better end comes back: lint then says so."""
    return h if contrast(h, bg) >= need else fit_L(hex_to_oklch(h), [bg], need)


def hi_of(P, P2):
    return P if rel_luminance(P) >= rel_luminance(P2) else P2


def lo_of(P, P2):
    return P if rel_luminance(P) < rel_luminance(P2) else P2


def _night_for(dr, spec, mode, default, a_lch, fam=None):
    L, C, H = _sample_lch(dr, spec, default, fam, "night")
    u = dr.u()
    if mode == "neutral-night":
        C = min(C, 0.012)
    elif mode == "warm-night":
        H = 60.0 + 25.0 * u
        C = max(0.012, min(C, 0.03))
    return (L, C, H)


def keep_record(key, frm, to, why):
    """An explicit entry of params["adjusted"]: {key, from, to, reason}. Entries made by sample() for a value frozen outside
    its envelope carry a reason that starts with KEEP_REASON; draw.py adjust adds its own with the author's reason."""
    return {"key": key, "from": frm, "to": to, "reason": why}


KEEP_REASON = "frozen by --keep"


def is_keep_record(e):
    return isinstance(e, dict) and str(e.get("reason", "")).startswith(KEEP_REASON)


def sample(direction, rng, keep=None, steer=None, mode=False):
    """One card of a direction: every resolved value in `params` (JSON-serialisable). Deterministic in (direction, seed,
    keep, steer). `mode=True` returns the typical card (first enum values, range midpoints) -- used for fingerprints.

    RULE (FIX-SPEC A5): the draws are made in a fixed order and every parameter consumes its random number whether or not
    it is frozen; a frozen value only overrides what was drawn. So `keep` never moves an unrelated parameter, and
    `draw.py adjust` can re-derive a card without re-dealing it."""
    keep = dict(keep or {})
    dr = Draw(rng, steer, mode)
    adj = []        # what a person asked for: {key, from, to, reason} (a frozen value outside its envelope; draw.py adjust adds more)
    tuned = []      # what the generator walked on its own to meet a floor rule, and the UNRESOLVED / advisory notes (strings)
    d = direction
    pal = d.get("palette", {})
    ty = d.get("type", {})
    sh = d.get("shape", {})
    mp = d.get("map", {})
    mo = d.get("motion", {})

    def kept(name, drawn, cast=None):
        """The frozen value of `name` if there is one, else the drawn one."""
        if has_keep(keep, name):
            return cast(keep[name]) if cast else keep[name]
        return drawn

    # ---- palette -------------------------------------------------------------------------------
    structure_pick = dr.pick(_as_list(pal.get("structure")) or ["two-inks-paper"])
    structure = keep.get("structure") or structure_pick
    fam = {}       # role -> index of the hue family drawn (a role may follow an earlier one)
    paper_l = _sample_lch(dr, pal.get("paper"), (0.975, 0.006, 90.0), fam, "paper")
    a_l = _sample_lch(dr, pal.get("a"), (0.30, 0.08, 260.0), fam, "a")
    b_l = _sample_lch(dr, pal.get("b"), (0.52, 0.20, 25.0), fam, "b")
    climb_l = _sample_lch(dr, pal.get("climb"), (0.72, 0.14, 75.0), fam, "climb")
    dark_pick = dr.pick(_as_list(pal.get("dark")) or ["brand-ink-ground"])
    dark_mode = keep.get("dark") or dark_pick
    night_l = _night_for(dr, pal.get("night"), dark_mode, (0.18, 0.04, a_l[2]), a_l, fam)
    kp = keep.get("palette") or []
    for i, key in enumerate(("a", "b", "paper", "climb")):
        if i < len(kp):
            keep.setdefault(key, kp[i])
    ov = {}
    for key in ("a", "b", "paper", "climb", "night"):
        if keep.get(key):
            ov[key] = hex_to_oklch(keep[key])
    if "a" in ov:
        a_l = ov["a"]
    if "b" in ov:
        b_l = ov["b"]
    if "paper" in ov:
        paper_l = ov["paper"]
    if "climb" in ov:
        climb_l = ov["climb"]
    if "night" in ov:
        night_l = ov["night"]

    # ---- the rest of the draws, in a fixed order -------------------------------------------------
    u_light = [dr.u() for _ in range(10)]
    u_dark = [dr.u() for _ in range(10)]

    fonts = {}
    for role in FONT_ROLES:
        fonts[role] = _font_pick(dr, ty, role, keep.get(role))
    label_case = kept("label_case", dr.pick(ty.get("label_case") or ["uppercase"]))
    label_track = kept("label_track", dr.num(ty.get("label_track", 0.1), True, (0.0, 0.3), 3), float)
    label_stretch = kept("label_stretch", dr.pick(ty.get("label_stretch") or ["normal"]))
    label_weight_d = dr.num(ty.get("label_weight", 600), True, (100, 900), 0)
    display_weight_d = dr.num(ty.get("display_weight", 700), True, (100, 900), 0)
    display_track = kept("display_track", dr.num(ty.get("display_track", 0.0), False, (-0.06, 0.1), 3), float)
    display_leading = kept("display_leading", dr.num(ty.get("display_leading", 1.0), False, (0.8, 1.3), 3), float)
    ratio = kept("ratio", dr.num(ty.get("ratio", 1.25), True, (1.125, 1.618), 3), float)
    label_weight = int(float(keep["label_weight"])) if has_keep(keep, "label_weight") else int(round(label_weight_d / 100.0) * 100)
    display_weight = int(float(keep["display_weight"])) if has_keep(keep, "display_weight") else int(round(display_weight_d / 100.0) * 100)

    language = kept("language", dr.pick(sh.get("language") or ["square"]))
    radius = kept("radius", dr.num(sh.get("radius", 0), True, (0, 24), 0), float)
    chamfer = kept("chamfer", dr.num(sh.get("chamfer", 0), True, (0, 16), 0), float)
    rule_cap = dr.num(sh.get("rule_cap", [4, 6]), True, (2, 12), 0)
    divider = kept("divider", dr.pick(d.get("divider") or ["none"]))
    entity_header = kept("entity_header", dr.pick(d.get("entity_header") or ["index-card"]))
    entity_token = kept("entity_token", dr.pick(d.get("entity_token") or ["badge"]))
    numerals = kept("numerals", dr.pick(d.get("numerals") or ["lining-tabular"]))
    nav = kept("nav", dr.pick(d.get("nav") or ["lines-top-left"]))
    density = kept("density", dr.pick(d.get("density") or ["airy"]))
    texture = kept("texture", dr.pick(d.get("texture") or ["none"]))

    # ---- map: projection first (the envelopes of pitch / yaw / wall height may depend on it) -------
    envelope = _as_list(mp.get("projection") or ["orbit"])
    proj_drawn = dr.pick(envelope)
    proj_u = dr.last_u
    projection, outside = proj_drawn, False
    want = keep.get("projection")
    if want in ("3d", "rotate"):
        # 3d: any 3D projection; rotate: one that turns on drag (orbit | exploded). The drawn one if it qualifies, else one of
        # the direction's own that does, else exploded (outside the envelope: recorded)
        ok_set = PROJECTIONS_3D if want == "3d" else PROJECTIONS_ROTATE
        if proj_drawn in ok_set:
            projection = proj_drawn
        else:
            own = [p for p in envelope if p in ok_set]
            projection = dr.pick_at(own, proj_u) if own else "exploded"
            if not own:
                outside = True
    elif want:
        projection = want
        outside = want not in envelope
    if outside:
        adj.append(keep_record("map.projection", "/".join(envelope), projection,
                               "%s: outside this direction's envelope (%s)" % (KEEP_REASON, "/".join(envelope))))
    material = kept("material", dr.pick(mp.get("material") or ["paper"]))
    pitch_u = dr.u()
    pitch_d = dr.num(spec_for(mp.get("pitch", 40), projection), True, (10, 90), 0, u=pitch_u)
    yaw_d = dr.num(spec_for(mp.get("yaw", 0), projection), True, (-90, 90), 0)
    wall_d = dr.num(spec_for(mp.get("wall_h", 1.0), projection), True, (0.3, 2.0), 2)
    if projection != "plan" and not has_keep(keep, "pitch") and pitch_d >= 70:
        # a plan-view pitch (80-88) under a 3D projection would draw a flat top view: take the 3D tilt, same draw
        new = dr.num(list(PITCH_3D), True, (10, 90), 0, u=pitch_u)
        tuned.append("map.pitch: %d -> %d (a %s projection needs a tilted view, not a plan-view pitch)" % (pitch_d, new, projection))
        pitch_d = new
    if outside and projection != "plan" and not has_keep(keep, "wall_h") and wall_d < 0.6:
        tuned.append("map.wall_h: %s -> 0.6 (walls too low to read in a %s view)" % (_fmt(wall_d, 2), projection))
        wall_d = 0.6
    pitch = kept("pitch", pitch_d, float)
    yaw = kept("yaw", yaw_d, float)
    wall_h = kept("wall_h", wall_d, float)
    light = kept("light", dr.pick(mp.get("light") or ["left"]))
    dim = kept("dim", dr.num(mp.get("dim", 0.25), False, (0.05, 0.6), 2), float)
    map_token = dr.pick(mp.get("token") or [entity_token])
    map_label_case_d = dr.pick(mp.get("label_case") or ["upper" if label_case == "uppercase" else "none"])
    map_label_case = kept("map_label_case", map_label_case_d)
    if has_keep(keep, "label_case") and not has_keep(keep, "map_label_case") and not mp.get("label_case"):
        map_label_case = "upper" if label_case == "uppercase" else "none"

    dur = kept("dur", dr.num(mo.get("dur", 0.45), False, (0.15, 0.9), 2), float)
    bounce = kept("bounce", dr.num(mo.get("bounce", 0.0), True, (0.0, 0.35), 2), float)
    press = kept("press", dr.num(mo.get("press", 0.97), False, (0.9, 1.0), 3), float)
    fade = dr.num(mo.get("fade", [0.15, 0.25]), False, (0.08, 0.4), 2)

    lay = d.get("layout", {})
    if density == "compact":
        gutter = dr.num(lay.get("gutter", [14, 18]), True, (8, 48), 0)
        gap = dr.num(lay.get("gap", [10, 14]), True, (4, 48), 0)
        row_pad = dr.num(lay.get("row_pad", [8, 11]), True, (4, 32), 0)
        measure = dr.num(lay.get("measure", [58, 64]), True, (40, 80), 0)
        base_min, base_max = 15.0, 17.0
    else:
        gutter = dr.num(lay.get("gutter", [20, 28]), True, (8, 48), 0)
        gap = dr.num(lay.get("gap", [18, 26]), True, (4, 48), 0)
        row_pad = dr.num(lay.get("row_pad", [13, 18]), True, (4, 32), 0)
        measure = dr.num(lay.get("measure", [64, 72]), True, (40, 80), 0)
        base_min, base_max = 16.0, 18.0
    if projection == "plan" and pitch < 80:
        tuned.append("map.pitch: %d -> 84 (plan projection is near top-down)" % pitch)
        pitch = 84.0
    if projection == "oblique" and abs(yaw) < 1:
        yaw = 22.0

    # the primary language of bilingual pairs: not a draw (a brief decides it), so it can never move another value
    lead = keep.get("lead") if keep.get("lead") in LEADS else "en"

    # ---- schemes ---------------------------------------------------------------------------------
    native_dark = (structure == "dark-ground") or _lum_dark(oklch_to_hex(*paper_l))
    first = derive_scheme(paper_l, a_l, b_l, climb_l, material, u_light, tuned, "light" if not native_dark else "base", False)
    second_adj = []
    # the second scheme is derived from the first scheme's final inks, on the night ground
    second = derive_scheme(night_l, hex_to_oklch(first["a"]), hex_to_oklch(first["b"]), hex_to_oklch(first["climb"]),
                           material, u_dark, second_adj, "dark", True)
    tuned.extend(second_adj)
    # the contrast between the native ground and the night ground must be meaningful only for light-native
    schemes = {"light": first, "dark": second}

    # ---- fonts: add CJK fallbacks to every stack ---------------------------------------------------
    cjk_sans = fonts["cjk"]["stack"] if fonts["cjk"].get("stack") else CJK_SANS
    cd_default = CJK_SERIF if re.search(r"serif|slab|didone|old-style|transitional", str(fonts["display"].get("class", "")), re.I) \
        and not re.search(r"sans", str(fonts["display"].get("class", "")), re.I) else CJK_SANS
    cjk_display = fonts["cjk_display"]["stack"] if fonts["cjk_display"].get("stack") else cd_default
    if fonts["cjk"].get("name") == "system":
        cjk_sans = CJK_SANS
    if fonts["cjk_display"].get("name") == "system":
        cjk_display = cd_default
    full = {
        "display": with_cjk(fonts["display"]["stack"], cjk_display),
        "label": with_cjk(fonts["label"]["stack"], cjk_sans),
        "text": with_cjk(fonts["text"]["stack"], cjk_sans),
        "num": with_cjk(fonts["num"]["stack"], cjk_sans),
        "cjk": with_cjk(cjk_sans, cjk_sans) if not stack_has_cjk(cjk_sans) else cjk_sans,
        "cjk_display": cjk_display if stack_has_cjk(cjk_display) else with_cjk(cjk_display, cd_default),
    }
    fonts_out = {}
    for role in FONT_ROLES:
        f = dict(fonts[role])
        f["full_stack"] = full[role]
        fonts_out[role] = f

    scale = type_scale(ratio, base_min, base_max)
    families = {}
    for role in HUE_ROLES:                 # the families that were drawn (roles that follow another are named by their leader)
        spec = pal.get(role) or {}
        try:
            n = len(hue_families(spec.get("h")))
        except ValueError:
            n = 0
        if n > 1 and not spec.get("follow") and role in fam and role not in ov:
            families[role] = {"index": fam[role], "of": n, "name": family_names(spec, n)[fam[role]]}
    params = {
        "direction": d.get("id"),
        "name": d.get("name"),
        "mechanism": d.get("mechanism"),
        "idea": d.get("idea"),
        "steer": steer,
        "lead": lead,
        "palette": {
            "structure": structure, "dark_mode": dark_mode, "ground": "dark" if native_dark else "light",
            "light": schemes["light"], "dark": schemes["dark"], "families": families,
            "sampled": {"paper": [round(x, 4) for x in paper_l], "a": [round(x, 4) for x in a_l],
                        "b": [round(x, 4) for x in b_l], "climb": [round(x, 4) for x in climb_l],
                        "night": [round(x, 4) for x in night_l]},
        },
        "type": {
            "fonts": fonts_out,
            "label_case": label_case, "label_track": label_track, "label_stretch": _stretch_value(label_stretch),
            "label_weight": int(label_weight), "display_weight": int(display_weight),
            "display_track": display_track, "display_leading": display_leading, "ratio": ratio,
            "base": [base_min, base_max], "scale": scale,
        },
        "shape": {"language": language, "radius": int(radius), "chamfer": int(chamfer), "hair": 1, "rule_2": 2,
                  "rule_3": 3, "rule_cap": int(rule_cap)},
        "divider": divider, "entity_header": entity_header, "entity_token": entity_token, "numerals": numerals,
        "nav": nav, "density": density, "texture": texture,
        "map": {"projection": projection, "material": material, "token": map_token, "pitch": pitch, "yaw": yaw,
                "wall_h": wall_h, "light": light, "dim": dim, "label_case": map_label_case},
        "motion": {"dur": dur, "bounce": bounce, "press": press, "fade": fade},
        "layout": {"gutter": int(gutter), "gap": int(gap), "row_pad": int(row_pad), "measure": int(measure)},
        "richness": d.get("richness", []), "watch": d.get("watch", []), "specimen_note": d.get("specimen_note", ""),
        "props": props_of(d),
        "adjusted": adj,
        "floor_tuned": tuned,
    }
    # a final audit: anything that still fails is listed (lint_floor will fail the card; the library needs fixing)
    for sname in ("light", "dark"):
        for c in check_scheme(schemes[sname], include_extra=True):
            if not c["ok"]:
                detail = ("%.2f<%s" % (c["ratio"], c["min"])) if c["ratio"] is not None else ""
                tuned.append(("UNRESOLVED %s %s %s" if c["level"] == "floor" else "advisory %s %s %s") % (sname, c["id"], detail))
    return params


# ---- fingerprint (BUILD-SPEC 5) -------------------------------------------------------------------

FP_AXES = ["palette_family", "ground", "display_class", "label_style", "shape.language", "divider", "entity_header",
           "entity_token", "numerals", "map.projection", "map.material", "motion_bucket"]


def _bucket(h, c):
    if c < CHROMA_NEUTRAL:
        return "n"
    return str(int(h // 30) * 30)


def motion_bucket(dur, bounce):
    """still: bounce <= 0.04 and dur >= 0.45 ; lively: bounce >= 0.18 ; firm: everything between."""
    if bounce >= 0.18:
        return "lively"
    if bounce <= 0.04 and dur >= 0.45:
        return "still"
    return "firm"


def fingerprint(params):
    """The 12-axis fingerprint of a card (flat dict with the keys of FP_AXES)."""
    pal = params["palette"]
    base = pal["light"]
    la, ca, ha = hex_to_oklch(base["a"])
    lb, cb, hb = hex_to_oklch(base["b"])
    ty = params["type"]
    lab = ty["fonts"]["label"]
    mono = str(lab.get("class", "")) == "mono" or "monospace" in lab.get("stack", "").lower()
    return {
        "palette_family": "%s|a%s|b%s" % (pal["structure"], _bucket(ha, ca), _bucket(hb, cb)),
        "ground": pal["ground"],
        "display_class": str(ty["fonts"]["display"].get("class", "")),
        "label_style": "%s|%s|%s" % (ty["label_case"], _stretch_class(ty["label_stretch"]), "mono" if mono else "prop"),
        "shape.language": params["shape"]["language"],
        "divider": params["divider"],
        "entity_header": params["entity_header"],
        "entity_token": params["entity_token"],
        "numerals": params["numerals"],
        "map.projection": params["map"]["projection"],
        "map.material": params["map"]["material"],
        "motion_bucket": motion_bucket(params["motion"]["dur"], params["motion"]["bounce"]),
    }


def normalize_fingerprint(fp):
    """Accept flat or nested fingerprints and a few spellings; returns a flat dict over FP_AXES (missing -> None)."""
    flat = {}

    def walk(prefix, v):
        if isinstance(v, dict):
            for k, x in v.items():
                walk(prefix + k if not prefix else prefix + "." + k, x)
        else:
            flat[prefix] = v

    if isinstance(fp, dict) and isinstance(fp.get("fingerprint"), dict):
        fp = fp["fingerprint"]
    if isinstance(fp, dict) and isinstance(fp.get("axes"), dict):
        fp = fp["axes"]
    walk("", fp)
    alias = {"shape": "shape.language", "language": "shape.language", "projection": "map.projection",
             "material": "map.material", "map_projection": "map.projection", "map_material": "map.material",
             "shape_language": "shape.language", "display": "display_class", "motion": "motion_bucket"}
    out = {}
    for k, v in flat.items():
        out[alias.get(k, k)] = v
    return {k: (None if out.get(k) is None else str(out.get(k))) for k in FP_AXES}


def similarity(fp_a, fp_b):
    """matching axes / 12"""
    a, b = normalize_fingerprint(fp_a), normalize_fingerprint(fp_b)
    n = sum(1 for k in FP_AXES if a[k] is not None and a[k] == b[k])
    return n / float(len(FP_AXES))


def axis_matches(fp_a, fp_b):
    a, b = normalize_fingerprint(fp_a), normalize_fingerprint(fp_b)
    return [k for k in FP_AXES if a[k] is not None and a[k] == b[k]]


def typical_fingerprint(direction):
    """Fingerprint of the direction's typical card (first enum values, range midpoints)."""
    return fingerprint(sample(direction, random.Random(0), None, None, mode=True))


def canonical_fingerprint(lib=None):
    """Canonical fingerprint: references/reference-direction/fingerprint.json when present and complete, else the typical
    fingerprint of the library's canonical direction, else of the fixture. Returns (fp, source_string)."""
    if REFERENCE_FP_PATH.exists():
        try:
            fp = normalize_fingerprint(json.loads(REFERENCE_FP_PATH.read_text(encoding="utf-8")))
            if sum(1 for v in fp.values() if v is not None) >= 10:
                return fp, str(REFERENCE_FP_PATH)
        except Exception:  # noqa
            pass
    try:
        lib = lib or load_directions()
        return typical_fingerprint(canonical_direction(lib)), "typical card of library canonical direction"
    except FileNotFoundError:
        lib = load_directions(fixture=True)
        return typical_fingerprint(canonical_direction(lib)), "typical card of the FIXTURE canonical direction"


# =================================================================================================
# 6. output: tokens.css
# =================================================================================================

def _px(v):
    return "%spx" % _fmt(float(v))


def build_tokens(params):
    """Returns (light_tokens, dark_tokens): {name without '--': css value}. dark holds colours only."""
    params = upgrade_params(params)
    pal = params["palette"]
    ty = params["type"]
    sh = params["shape"]
    mo = params["motion"]
    lay = params["layout"]
    mp = params["map"]
    L = {}
    for k in ALL_COLOR_TOKENS:
        L[k] = pal["light"][k]
    # map keywords / numbers
    L["m-projection"] = mp["projection"]
    L["m-material"] = mp["material"]
    L["m-token"] = mp["token"]
    L["m-pitch"] = _fmt(mp["pitch"])
    L["m-yaw"] = _fmt(mp["yaw"])
    L["m-wall-h"] = _fmt(mp["wall_h"], 2)
    L["m-light"] = mp["light"]
    L["m-dim"] = _fmt(mp["dim"], 2)
    L["m-label-case"] = mp["label_case"]
    # fonts
    f = ty["fonts"]
    L["f-display"] = f["display"]["full_stack"]
    L["f-label"] = f["label"]["full_stack"]
    L["f-text"] = f["text"]["full_stack"]
    L["f-num"] = f["num"]["full_stack"]
    L["f-cjk"] = f["cjk"]["full_stack"]
    L["f-cjk-display"] = f["cjk_display"]["full_stack"]
    L["label-case"] = ty["label_case"]
    L["label-track"] = "%sem" % _fmt(ty["label_track"], 3)
    L["label-stretch"] = ty["label_stretch"]
    L["label-weight"] = str(ty["label_weight"])
    L["display-weight"] = str(ty["display_weight"])
    L["display-track"] = "%sem" % _fmt(ty["display_track"], 3)
    L["display-leading"] = _fmt(ty["display_leading"], 3)
    for i in range(-1, 6):
        L["step-%d" % i] = ty["scale"][str(i)]
    # shape / rules
    L["radius"] = _px(sh["radius"])
    L["chamfer"] = _px(sh["chamfer"])
    L["hair"] = _px(sh["hair"])
    L["rule-2"] = _px(sh["rule_2"])
    L["rule-3"] = _px(sh["rule_3"])
    L["rule-cap"] = _px(sh["rule_cap"])
    # motion
    L["spring-dur"] = "%ss" % _fmt(mo["dur"], 2)
    L["spring-bounce"] = _fmt(mo["bounce"], 2)
    L["press-scale"] = _fmt(mo["press"], 3)
    L["fade-dur"] = "%ss" % _fmt(mo["fade"], 2)
    # layout
    L["gutter"] = _px(lay["gutter"])
    L["gap"] = _px(lay["gap"])
    L["row-pad"] = _px(lay["row_pad"])
    L["measure"] = "%sch" % _fmt(lay["measure"])
    # default entity colour = the accent b, so pages without per-entity vars still resolve --e-*
    t = tones(pal["light"]["b"], pal["light"]["paper"], pal["light"]["text"], pal["dark"]["paper"])
    for k in TONES_KEYS:
        L[TONES_CSS[k][2:]] = t[k]
    D = {k: pal["dark"][k] for k in ALL_COLOR_TOKENS}
    return L, D


_GROUPS = [
    ("colour roles / 颜色角色", COLOR_TOKENS),
    ("map materials / 地图材质 (read by venue-map.js)", MAP_COLOR_TOKENS),
    ("map keywords / 地图关键字与数值", MAP_KEYWORD_TOKENS),
    ("type / 字体", FONT_TOKENS + ["label-case", "label-track", "label-stretch", "label-weight", "display-weight",
                                   "display-track", "display-leading"]),
    ("type scale / 字号阶梯", ["step--1", "step-0", "step-1", "step-2", "step-3", "step-4", "step-5"]),
    ("shape and rules / 形状与线", SHAPE_TOKENS),
    ("motion / 动效", MOTION_TOKENS),
    ("density / 密度", LAYOUT_TOKENS),
    ("default entity colour / 实体色默认值 (override inline per entity)", [TONES_CSS[k][2:] for k in TONES_KEYS]),
]


def root_attrs(params):
    """The rolled enumerations as <html> data-attributes. Recipes switch on these: the three hooks the recipes document
    (data-evk-divider, data-evk-nav, data-evk-numerals) plus the other axes under the same data-evk-<axis> pattern.
    data-evk-lead="en|zh" says which language leads a bilingual pair (the FIRST child of .evk-k; base.css reads it, and
    VenueMap takes it as its default `lead`). If a recipe is written against another name, this list is the one place to change."""
    return [("data-evk-direction", params["direction"]), ("data-evk-lead", params.get("lead") or "en"),
            ("data-evk-divider", params["divider"]),
            ("data-evk-nav", params["nav"]), ("data-evk-numerals", params["numerals"]),
            ("data-evk-entity-header", params["entity_header"]), ("data-evk-header", params["entity_header"]),
            ("data-evk-entity-token", params["entity_token"]), ("data-evk-token", params["entity_token"]),
            ("data-evk-shape", params["shape"]["language"]), ("data-evk-density", params["density"]),
            ("data-evk-texture", params["texture"]), ("data-evk-ground", params["palette"]["ground"])]


def root_attrs_html(params):
    return " ".join('%s="%s"' % (k, v) for k, v in root_attrs(params))


def live_prop_values(css_text):
    """{var: value} of every live (not commented) `--prop-*` declaration of a stylesheet text; the last one wins, as in CSS."""
    bare = re.sub(r"/\*.*?\*/", "", css_text or "", flags=re.S)
    return {m.group(1): m.group(2).strip() for m in re.finditer(r"(--prop-[a-z0-9-]+)\s*:\s*([^;}]+)", bare)}


def live_props(css_text, params):
    """Names of the props that a tokens.css (or any stylesheet text) has switched OFF with a live `--prop-x: <off value>;` line
    (comments are ignored). Reporting only: install.py --update carries over EVERY live --prop-* line (live_prop_lines)."""
    live = live_prop_values(css_text)
    return {pr["name"] for pr in props_of(params) if live.get(pr["var"]) == pr["off"].strip()}


_PROP_DECL_RE = re.compile(r"(--prop-[a-z0-9-]+)\s*:\s*([^;{}]+);")


def live_prop_lines(css_text):
    """The `--prop-*` declarations a stylesheet text has switched ON (live: not inside a /* comment */), line by line:
    [{"vars": ["--prop-leaf"], "line": "  --prop-leaf: none;  /* no plants here */"}]. `line` is the line exactly as written
    (leading spaces and trailing comment included) when the line holds nothing but those declarations and complete comments;
    a line with other text on it, or one that opens or closes a comment across line ends, is rebuilt as `--prop-x: value;`
    so that the regenerated file stays valid CSS. This is what `install.py --update` carries over (see PRESERVED in the header)."""
    out = []
    in_c = False
    for raw in (css_text or "").splitlines():
        started_open, code, i, n = in_c, [], 0, len(raw)
        while i < n:
            if in_c:
                j = raw.find("*/", i)
                if j < 0:
                    i = n
                else:
                    in_c, i = False, j + 2
            else:
                j = raw.find("/*", i)
                if j < 0:
                    code.append(raw[i:])
                    i = n
                else:
                    code.append(raw[i:j])
                    in_c, i = True, j + 2
        text = "".join(code)
        decls = _PROP_DECL_RE.findall(text)
        if not decls:
            continue
        clean = not _PROP_DECL_RE.sub("", text).strip()      # nothing on the line but the declarations
        line = raw.rstrip() if (clean and not started_open and not in_c) else "  " + " ".join("%s: %s;" % (v, val.strip()) for v, val in decls)
        out.append({"vars": [v for v, _ in decls], "line": line})
    return out


def props_css_lines(params, props_off=False, indent="  ", props_keep=None):
    """The props block of tokens.css (empty for a direction without props). props_off=False: every prop stays ON and its switch is
    a COMMENTED line, `/* --prop-leaf: none; */  /* 叶形标签 (leaf) */`, so turning one off is one edit (remove the comment marks around
    the declaration; the description is a comment of its own, so nothing is left over to break the next line).
    props_off=True: every prop is OFF (live declarations); a collection of names: just those.
    props_keep: live_prop_lines() of the previously installed file (install.py --update): each such line is written VERBATIM in place
    of the generated one for its prop; lines for a var this card has no prop for follow the block."""
    props = props_of(params)
    keep = [dict(k) for k in (props_keep or ())]
    if not props and not keep:
        return []
    names = None if props_off is True else set(props_off or ())
    out = []
    used = set()
    if props:
        out += [indent + "/* props / 装饰母题: this direction's category motifs. ON by default (the recipe draws them); to switch one off,",
                indent + "   remove the comment marks around its declaration (install.py --update keeps such a line as you wrote it). Keep a prop only",
                indent + "   if the project's inventory supports it (DESIGN.md, Components). */"]
    for pr in props:
        mine = [i for i, k in enumerate(keep) if pr["var"] in k["vars"] and i not in used]
        if mine:                                         # the line you switched on (or set to your own value): carried over as it was
            for i in mine:
                out.append(keep[i]["line"])
                used.add(i)
        elif props_off is True or (names and pr["name"] in names):
            out.append("%s%s: %s;  /* OFF: %s */" % (indent, pr["var"], pr["off"], pr["what"]))
        else:
            out.append("%s/* %s: %s; */  /* %s (%s) */" % (indent, pr["var"], pr["off"], pr["what"], pr["name"]))
    rest = [k for i, k in enumerate(keep) if i not in used]
    if rest:
        out.append(indent + "/* kept by install.py --update: --prop-* lines of the previous tokens.css that this card has no prop for */")
        out += [k["line"] for k in rest]
    return out


def tokens_css(params, header=None, props_off=False, props_keep=None):
    """tokens.css text: :root{} (native scheme + everything else) and the other scheme twice
    (@media prefers-color-scheme: dark + [data-theme="dark"]). The direction's props follow the tokens as commented lines
    (props_off, props_keep: see props_css_lines)."""
    L, D = build_tokens(params)
    native_dark = params["palette"]["ground"] == "dark"
    out = []
    out.append("/* %s %s -- tokens.css" % (KIT_NAME, KIT_VERSION))
    out.append("   direction : %s  (%s)" % (params["direction"], (params.get("name") or {}).get("en", "")))
    if header:
        for line in str(header).splitlines():
            out.append("   " + line)
    out.append("   html attrs: %s" % root_attrs_html(params))
    out.append("   Generated by scripts/kit.py: edit the roll and regenerate; do not hand-edit values (the props lines at the end of :root are the one switch: install.py --update keeps the ones you switched on, verbatim). */")
    out.append(":root{")
    out.append("  color-scheme: %s;" % ("dark" if native_dark else "light dark"))
    for title, names in _GROUPS:
        out.append("  /* %s */" % title)
        for n in names:
            out.append("  --%s: %s;" % (n, L[n]))
    out.extend(props_css_lines(params, props_off, props_keep=props_keep))
    out.append("}")
    if not native_dark:
        out.append(':root[data-theme="light"]{color-scheme: light}')
    for sel_open, sel_close in (('@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){', "}}"),
                                (':root[data-theme="dark"]{', "}")):
        out.append(sel_open)
        out.append("  color-scheme: dark;")
        for n in ALL_COLOR_TOKENS:
            out.append("  --%s: %s;" % (n, D[n]))
        out.append(sel_close)
    return "\n".join(out) + "\n"


def family_text(params, sep="; "):
    """The hue families a card drew, as text: 'b = postmark violet (1 of 3)'. Empty for a direction without families."""
    fams = (params.get("palette") or {}).get("families") or {}
    out = []
    for role in HUE_ROLES:
        f = fams.get(role)
        if f:
            out.append("%s = %s (%d of %d)" % (role, f.get("name") or "family %d" % (f["index"] + 1), f["index"] + 1, f["of"]))
    return sep.join(out)


def card_summary_lines(params):
    """Human-readable lines describing a card (used by draw.py, specimen.py and DESIGN.md)."""
    pal, ty, sh, mp, mo = params["palette"], params["type"], params["shape"], params["map"], params["motion"]
    f = ty["fonts"]
    lt = pal["light"]
    fam = family_text(params)
    props = props_of(params)
    return [
        "palette : %s | ground %s | paper %s  a %s  b %s  climb %s | night %s" % (
            pal["structure"], pal["ground"], lt["paper"], lt["a"], lt["b"], lt["climb"], pal["dark"]["paper"]) +
        ((" | hue family: " + fam) if fam else ""),
        "type    : display %s (%s %d) | label %s (%s %s, %sem %d) | text %s | ratio %s" % (
            f["display"]["name"], f["display"].get("class", ""), ty["display_weight"], f["label"]["name"],
            ty["label_case"], ty["label_stretch"], _fmt(ty["label_track"], 3), ty["label_weight"], f["text"]["name"],
            _fmt(ty["ratio"], 3)),
        "shape   : %s r%s ch%s | divider %s | header %s | token %s | numerals %s | nav %s" % (
            sh["language"], sh["radius"], sh["chamfer"], params["divider"], params["entity_header"],
            params["entity_token"], params["numerals"], params["nav"]),
        "map     : %s/%s pitch %s yaw %s wall %s light %s dim %s" % (
            mp["projection"], mp["material"], _fmt(mp["pitch"]), _fmt(mp["yaw"]), _fmt(mp["wall_h"], 2), mp["light"],
            _fmt(mp["dim"], 2)),
        "motion  : %s (dur %ss bounce %s press %s) | density %s | texture %s | lead %s" % (
            motion_bucket(mo["dur"], mo["bounce"]), _fmt(mo["dur"], 2), _fmt(mo["bounce"], 2), _fmt(mo["press"], 3),
            params["density"], params["texture"], params.get("lead") or "en"),
    ] + (["props   : %s  (on; each has a --prop-* switch: specimen.py --props off, tokens.css)" % " | ".join(
        "%s %s" % (pr["name"], pr["what"]) for pr in props)] if props else [])


# =================================================================================================
# 7. roll helpers: reading a parameter back, describing an adjustment, opening an old roll
# =================================================================================================

# adjust / --keep key -> where the resolved value lives in params
_PARAM_PATHS = {
    "structure": ("palette", "structure"), "dark": ("palette", "dark_mode"),
    "label_case": ("type", "label_case"), "label_track": ("type", "label_track"), "label_stretch": ("type", "label_stretch"),
    "label_weight": ("type", "label_weight"), "display_weight": ("type", "display_weight"),
    "display_track": ("type", "display_track"), "display_leading": ("type", "display_leading"), "ratio": ("type", "ratio"),
    "language": ("shape", "language"), "radius": ("shape", "radius"), "chamfer": ("shape", "chamfer"),
    "divider": ("divider",), "entity_header": ("entity_header",), "entity_token": ("entity_token",),
    "numerals": ("numerals",), "nav": ("nav",), "density": ("density",), "texture": ("texture",), "lead": ("lead",),
    "projection": ("map", "projection"), "material": ("map", "material"), "pitch": ("map", "pitch"), "yaw": ("map", "yaw"),
    "wall_h": ("map", "wall_h"), "light": ("map", "light"), "dim": ("map", "dim"), "map_label_case": ("map", "label_case"),
    "dur": ("motion", "dur"), "bounce": ("motion", "bounce"), "press": ("motion", "press"),
}


def param_get(params, key):
    """The resolved value a --keep / adjust key stands for, as a short printable value (None if the key is unknown)."""
    key = KEEP_ALIASES.get(key, key)
    if key in _PARAM_PATHS:
        v = params
        for part in _PARAM_PATHS[key]:
            v = (v or {}).get(part) if isinstance(v, dict) else None
        if v is None and key == "lead":
            return "en"
        return int(v) if isinstance(v, float) and v.is_integer() else v
    if key in ("a", "b", "paper", "climb", "night"):
        return params["palette"]["dark" if key == "night" else "light"].get("paper" if key == "night" else key)
    if key == "palette":
        lt = params["palette"]["light"]
        return ",".join(lt[k] for k in ("a", "b", "paper", "climb"))
    if key in FONT_ROLES:
        return (params["type"]["fonts"].get(key) or {}).get("name")
    return None


def adjust_text(entry):
    """One entry of params["adjusted"] as a line of text. Entries are strings (made by the floor rules in sample()) or
    {key, from, to, reason} dicts (a value frozen outside its envelope, or made by `draw.py adjust`)."""
    if isinstance(entry, dict):
        s = "%s: %s -> %s" % (entry.get("key"), entry.get("from"), entry.get("to"))
        if entry.get("reason"):
            s += "  (%s)" % entry["reason"]
        return s
    return str(entry)


def floor_notes(params):
    """What the generator tuned on its own (colour roles walked to meet a floor rule, UNRESOLVED / advisory notes): the strings
    of params["floor_tuned"], plus any string an older roll still keeps in params["adjusted"]."""
    return list(params.get("floor_tuned") or []) + [a for a in (params.get("adjusted") or []) if isinstance(a, str)]


def user_adjustments(params):
    """What a person asked for: the {key, from, to, reason} records of params["adjusted"] (a value frozen outside its envelope,
    or a `draw.py adjust`)."""
    return [a for a in (params.get("adjusted") or []) if isinstance(a, dict)]


def adjust_counts(params):
    """(floor_tuned, adjusted, unresolved) as numbers, for one-line summaries. floor_tuned leaves out the UNRESOLVED notes."""
    notes = floor_notes(params)
    bad = [n for n in notes if n.startswith("UNRESOLVED")]
    return len(notes) - len(bad), len(user_adjustments(params)), len(bad)


def unresolved(params):
    """The UNRESOLVED floor failures sample() could not fix (empty for a healthy card)."""
    return [a for a in floor_notes(params) if a.startswith("UNRESOLVED")]


def complete_scheme(scheme):
    """A colour scheme dict from before FIX-SPEC A2/A3 gets the two tokens it lacks: --climb-text (climb walked to 4.5:1 on
    paper and paper-2, same hue) and --m-select-fill (the room tinted 12 % toward the selection edge); and from before
    FIX-SPEC-3 A3 its --m-cap / --m-wall are walked to 7:1 / 3:1 on --m-slab. Returns a new dict."""
    out = dict(scheme)
    if "m-slab" in out:
        for key, need in (("m-cap", MAP_CAP_MIN), ("m-wall", MAP_WALL_MIN)):
            if key in out:
                out[key] = ink_on(out[key], out["m-slab"], need)
    if "climb-text" not in out and "climb" in out:
        P, P2, CL = out["paper"], out["paper-2"], out["climb"]
        sgn = 1 if _lum_dark(P) else -1
        out["climb-text"] = CL if min(contrast(CL, P), contrast(CL, P2)) >= 4.58 else fit_L(hex_to_oklch(CL), [P, P2], 4.58, sgn)
    if "m-select-fill" not in out and "m-room" in out and "m-select" in out:
        out["m-select-fill"] = mix_ok(out["m-room"], out["m-select"], 0.12)
    return out


def upgrade_params(params):
    """Params of an older roll made current: the two newer colour tokens, a map ink line and wall that clear their contrast,
    `lead`, the palette `families` record, and the floor_tuned / adjusted split (strings that the floor rules wrote move out of
    `adjusted`). Returns the same object when nothing is missing (so it is free to call everywhere), else a copy."""
    pal = params.get("palette") or {}

    def stale(sc):
        t = pal.get(sc) or {}
        return any(k not in t for k in ("climb-text", "m-select-fill")) or complete_scheme(t) != t

    need = ("lead" not in params) or ("floor_tuned" not in params) or ("families" not in pal) or stale("light") or stale("dark")
    if not need:
        return params
    out = dict(params)
    out.setdefault("lead", "en")
    strings = [a for a in (params.get("adjusted") or []) if isinstance(a, str)]
    out["floor_tuned"] = list(params.get("floor_tuned") or []) + strings
    out["adjusted"] = [a for a in (params.get("adjusted") or []) if not isinstance(a, str)]
    out["palette"] = dict(pal, light=complete_scheme(pal["light"]), dark=complete_scheme(pal["dark"]),
                          families=pal.get("families") or {})
    return out


# =================================================================================================
# self-test
# =================================================================================================

def _selftest():
    fails = []

    def ok(cond, msg):
        if not cond:
            fails.append(msg)
            print("  FAIL", msg)

    # --- colour maths
    ok(abs(contrast("#000000", "#FFFFFF") - 21.0) < 1e-9, "contrast black/white = 21")
    ok(abs(contrast("#FFFFFF", "#FFFFFF") - 1.0) < 1e-9, "contrast same = 1")
    L, C, H = hex_to_oklch("#FFFFFF")
    ok(abs(L - 1.0) < 1e-3 and C < 1e-3, "white -> L=1, C=0 (got %.4f %.4f)" % (L, C))
    L, C, H = hex_to_oklch("#FF0000")
    ok(abs(L - 0.6280) < 2e-3 and abs(C - 0.2577) < 2e-3 and abs(H - 29.23) < 0.3, "red OKLCH ~ (0.628, 0.2577, 29.2): got %.4f %.4f %.2f" % (L, C, H))
    L, C, H = hex_to_oklch("#00FF00")
    ok(abs(L - 0.8664) < 2e-3 and abs(C - 0.2948) < 2e-3 and abs(H - 142.5) < 0.5, "green OKLCH ~ (0.8664, 0.2948, 142.5): got %.4f %.4f %.2f" % (L, C, H))
    worst = 0
    for hx in ("#8C1515", "#13294B", "#F7F5F0", "#09A7C8", "#7BAFD4", "#C8102E", "#0D1D36", "#808080", "#FFB000"):
        L, C, H = hex_to_oklch(hx)
        worst = max(worst, sum(abs(a - b) for a, b in zip(hex_to_rgb(hx), hex_to_rgb(oklch_to_hex(L, C, H)))))
    ok(worst == 0, "hex -> OKLCH -> hex round trip exact (max byte diff %d)" % worst)
    h = oklch_to_hex(0.7, 0.35, 150)   # far out of gamut
    L2, C2, H2 = hex_to_oklch(h)
    ok(abs(L2 - 0.7) < 0.01 and C2 < 0.35 and hue_distance(H2, 150) < 3, "gamut map keeps L/H, reduces C (got %s %.3f %.3f %.1f)" % (h, L2, C2, H2))
    ok(mix("#000000", "#FFFFFF", 0.5) == "#808080", "mix half-up rounding (127.5 -> 128)")
    ok(round_half_up(0.5) == 1 and round_half_up(1.5) == 2 and round_half_up(2.5) == 3, "round_half_up")
    h = fit_L((0.9, 0.05, 250), ["#FFFFFF"], 4.5)
    ok(contrast(h, "#FFFFFF") >= 4.5 and hex_to_oklch(h)[0] < 0.7, "fit_L darkens until 4.5:1 on white (got %s)" % h)
    ok(parse_color("rgb(255, 0, 0)") == "#FF0000" and parse_color("#abc") == "#AABBCC" and parse_color("oklch(1 0 0)") == "#FFFFFF", "parse_color")

    # --- tones table
    for hx, exp in TONES_TABLE_EXPECTED.items():
        got = tones(hx, method="mix")
        ok(got == exp, "tones(%s, method='mix') = %s (expected %s)" % (hx, got, exp))
    for hx, opts, exp in TONES_OKLCH_EXPECTED:
        t = tones(hx, method="oklch", **opts)
        ok([t[k] for k in TONES_KEYS] == exp, "tones(%s, method='oklch') = tones.js table row" % hx)
    t = tones("#808080", method="mix")
    ok(t["e"] != "#808080", "mid-grey triggers the fill walk (neither paper nor ink text reaches 4.6)")
    for hx in TONES_TABLE_INPUTS + ("#D0021B", "#2E453C", "#FFD700", "#00FFFF"):
        t = tones(hx)
        ok(contrast(t["eText"], SOURCE_PAPER) >= 4.6 - 1e-9, "eText reads on paper for %s" % hx)
        ok(contrast(t["eDk"], SOURCE_NIGHT) >= 4.6 - 1e-9, "eDk reads on night for %s" % hx)
        ok(contrast(t["eOn"], t["e"]) >= 4.5, "eOn reads on e for %s" % hx)

    # --- fixture library
    lib = load_directions(fixture=True)
    errs, warns = validate_library(lib)
    errs = [e for e in errs if "missing required direction" not in e and "must be 'varsity'" not in e and "10-12" not in e]
    ok(not errs, "fixture library validates: %s" % errs)
    for d in lib["directions"]:
        p1 = sample(d, random.Random(11))
        p2 = sample(d, random.Random(11))
        ok(json.dumps(p1, sort_keys=True) == json.dumps(p2, sort_keys=True), "%s: same seed -> same card" % d["id"])
        p3 = sample(d, random.Random(12))
        ok(json.dumps(p1, sort_keys=True) != json.dumps(p3, sort_keys=True), "%s: other seed -> other card" % d["id"])
    # floor checks over many cards
    bad = 0
    n = 0
    for d in lib["directions"]:
        for seed in range(60):
            for steer in (None, "bolder", "safer"):
                p = sample(d, random.Random(seed), None, steer)
                n += 1
                for sc in ("light", "dark"):
                    for c in check_scheme(p["palette"][sc]):
                        if not c["ok"]:
                            bad += 1
                            if bad < 6:
                                print("   floor fail", d["id"], seed, steer, sc, c["id"], c["ratio"])
    ok(bad == 0, "every sampled card (%d) satisfies every floor/extra check; %d failures" % (n, bad))
    # keep
    p = sample(lib["directions"][1], random.Random(3), parse_keep(["palette=#0B5FFF,#FF5A1F", "display=Libre Franklin",
                                                                 "label_case=none", "projection=plan", "radius=6"]))
    ok(p["palette"]["light"]["a"] != "" and p["type"]["fonts"]["display"]["name"] == "Libre Franklin", "keep display")
    ok(p["type"]["label_case"] == "none" and p["map"]["projection"] == "plan" and p["shape"]["radius"] == 6, "keep enums/numbers")
    ok(hex_to_oklch(p["palette"]["light"]["b"])[2] > 20 and hex_to_oklch(p["palette"]["light"]["b"])[2] < 70, "keep b hue is orange-ish")
    # tokens.css
    css = tokens_css(p)
    for name in REQUIRED_TOKENS:
        ok(("--%s:" % name) in css, "tokens.css has --%s" % name)
    ok(css.count('@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){') == 1 and css.count(':root[data-theme="dark"]{') == 1,
       "dark block declared twice")
    ok(all(stack_has_cjk(b) for b in re.findall(r"--f-(?:display|label|text|num|cjk|cjk-display): ([^;]+);", css)), "every font stack has a CJK family")
    ok(with_cjk("Inter, Arial, sans-serif", CJK_SANS).endswith("sans-serif") and "PingFang SC" in with_cjk("Inter, Arial, sans-serif", CJK_SANS), "with_cjk keeps generic last")
    # steer shifts chroma
    cs = {}
    for st in (None, "bolder", "safer"):
        v = [hex_to_oklch(sample(lib["directions"][0], random.Random(s), None, st)["palette"]["light"]["b"])[1] for s in range(80)]
        cs[st] = sum(v) / len(v)
    ok(cs["bolder"] >= cs[None] - 1e-9 and cs["safer"] <= cs[None] + 1e-9, "steer bolder/safer moves chroma (%.3f %.3f %.3f)" % (cs["safer"], cs[None], cs["bolder"]))
    # fingerprint
    fp = fingerprint(p)
    ok(set(fp) == set(FP_AXES), "fingerprint has the 12 axes")
    ok(similarity(fp, fp) == 1.0, "similarity(x,x) = 1")
    cf = typical_fingerprint(lib["directions"][0])
    ok(similarity(cf, cf) == 1.0 and len(axis_matches(cf, fp)) / 12.0 == similarity(cf, fp), "similarity bookkeeping")
    ok(motion_bucket(0.5, 0) == "still" and motion_bucket(0.4, 0.1) == "firm" and motion_bucket(0.3, 0.25) == "lively", "motion buckets")
    ok(type_scale(1.25, 16, 18)["0"].startswith("clamp(1rem, ") and type_scale(1.25, 16, 18)["0"].endswith(", 1.125rem)"), "type_scale step 0 runs 16 -> 18 px")
    ok("clamp(" in type_scale(1.25, 16, 18)["3"], "type_scale clamp")

    # --- FIX-SPEC A5: --keep never moves an unrelated parameter (every parameter consumes its draw, then is overridden)
    heavy = parse_keep(["display=Libre Franklin", "label_case=none", "label_track=0.1", "label_stretch=normal", "label_weight=600",
                        "display_weight=500", "display_track=0", "display_leading=1", "ratio=1.25", "language=soft", "radius=0",
                        "chamfer=0", "divider=none", "entity_header=placard", "entity_token=dot", "numerals=oldstyle",
                        "nav=side-ticks", "density=compact", "texture=grain", "projection=3d", "material=line", "pitch=30",
                        "yaw=0", "wall_h=0.7", "light=top", "dim=0.2", "map_label_case=none", "dur=0.4", "bounce=0",
                        "press=0.97", "lead=zh", "structure=dark-ground", "dark=warm-night"])
    for d in lib["directions"]:
        for seed in (3, 41, 977):
            for keep_ in (heavy, parse_keep(["palette=#0B5FFF,#FF5A1F,#FAF7F0,#00A86B", "night=#101820"]), parse_keep(["projection=exploded", "pitch=30"]), {}):
                r1, r2 = random.Random(seed), random.Random(seed)
                sample(d, r1, keep_, None)
                sample(d, r2, None, None)
                ok(r1.getstate() == r2.getstate(), "%s seed %d: sample() consumes the RNG identically with keep %s" % (d["id"], seed, sorted(keep_)[:3]))
        # the strongest form: freezing projection+pitch moves nothing else
        a_ = sample(d, random.Random(8), None, None)
        b_ = sample(d, random.Random(8), parse_keep(["projection=exploded", "pitch=30"]), None)
        for sect in ("palette", "type", "shape", "motion", "layout"):
            ok(a_[sect] == b_[sect], "%s: freezing projection+pitch leaves %s untouched" % (d["id"], sect))
        for k_ in ("material", "yaw", "light", "dim", "token", "label_case"):
            ok(a_["map"][k_] == b_["map"][k_] or k_ == "yaw", "%s: freezing projection+pitch leaves map.%s untouched" % (d["id"], k_))
        ok(a_["divider"] == b_["divider"] and a_["numerals"] == b_["numerals"] and a_["entity_header"] == b_["entity_header"], "%s: nor the enumerations" % d["id"])
    # a frozen axis changes ONLY its own value and what depends on it
    base_ = sample(lib["directions"][1], random.Random(5), None, None)
    kept_ = sample(lib["directions"][1], random.Random(5), parse_keep(["radius=0", "dur=0.5", "divider=none"]), None)
    ok(kept_["shape"]["radius"] == 0 and kept_["motion"]["dur"] == 0.5 and kept_["divider"] == "none", "frozen zero / numbers are applied")
    ok(base_["type"] == kept_["type"] and base_["palette"] == kept_["palette"] and base_["map"] == kept_["map"], "…and nothing else moves")

    # --- FIX-SPEC A4: projection=3d / forced values
    for d in lib["directions"]:
        for seed in range(12):
            p3 = sample(d, random.Random(seed), parse_keep(["projection=3d"]), None)
            ok(p3["map"]["projection"] in PROJECTIONS_3D, "%s seed %d: projection=3d resolves to a 3D projection (%s)" % (d["id"], seed, p3["map"]["projection"]))
            ok(p3["map"]["pitch"] < 70, "%s seed %d: a 3D projection has a tilted pitch (%s)" % (d["id"], seed, p3["map"]["pitch"]))
    mono = {"id": "flat", **{k: v for k, v in lib["directions"][0].items() if k != "id"}}
    mono["map"] = dict(mono["map"], projection=["plan"], pitch=[80, 88], wall_h=[0.3, 0.5])
    pf = sample(mono, random.Random(2), parse_keep(["projection=3d"]), None)
    ok(pf["map"]["projection"] == "exploded" and pf["map"]["pitch"] < 70 and pf["map"]["wall_h"] >= 0.6, "projection=3d on a plan-only direction -> exploded, tilted, taller walls")
    ok(any(isinstance(x, dict) and x["key"] == "map.projection" and x["to"] == "exploded" and is_keep_record(x) for x in pf["adjusted"]), "…and it is recorded in `adjusted` as {key, from, to, reason}")
    pg = sample(lib["directions"][1], random.Random(2), parse_keep(["projection=plan"]), None)
    ok(pg["map"]["projection"] == "plan" and pg["map"]["pitch"] >= 80 and any(isinstance(x, dict) for x in pg["adjusted"]), "projection=plan is forced and recorded when outside the envelope")
    pin = sample(lib["directions"][1], random.Random(2), parse_keep(["projection=orbit"]), None)
    ok(not any(isinstance(x, dict) for x in pin["adjusted"]), "a forced value INSIDE the envelope is not an adjustment")
    try:
        parse_keep(["projection=sideways"])
        ok(False, "projection=sideways should be rejected")
    except ValueError:
        pass
    # a per-projection envelope (pitch / yaw / wall_h as dicts) is read for the projection that was resolved
    dd = json.loads(json.dumps(lib["directions"][2]))
    dd["map"]["projection"] = ["plan", "exploded"]
    dd["map"]["pitch"] = {"plan": [80, 88], "exploded": [30, 40]}
    seen = set()
    for seed in range(40):
        pp = sample(dd, random.Random(seed), None, None)
        seen.add(pp["map"]["projection"])
        ok((pp["map"]["pitch"] >= 80) if pp["map"]["projection"] == "plan" else (30 <= pp["map"]["pitch"] <= 40), "per-projection pitch envelope (%s %s)" % (pp["map"]["projection"], pp["map"]["pitch"]))
    ok(seen == {"plan", "exploded"}, "both projections of the envelope are drawn")

    # --- FIX-SPEC A1: lead
    pz = sample(lib["directions"][1], random.Random(4), parse_keep(["lead=zh"]), None)
    pe = sample(lib["directions"][1], random.Random(4), None, None)
    ok(pz["lead"] == "zh" and pe["lead"] == "en" and ("data-evk-lead", "zh") in root_attrs(pz) and ("data-evk-lead", "en") in root_attrs(pe), "lead -> params and <html data-evk-lead>")
    ok(json.dumps({k: v for k, v in pz.items() if k != "lead"}, sort_keys=True) == json.dumps({k: v for k, v in pe.items() if k != "lead"}, sort_keys=True), "lead moves nothing else")
    ok(parse_keep(["lang=cn"])["lead"] == "zh", "lead aliases")
    try:
        parse_keep(["lead=fr"])
        ok(False, "lead=fr should be rejected")
    except ValueError:
        pass

    # --- FIX-SPEC A2/A3: m-select / m-select-fill / climb-text
    worst_ct, hue_kept = 99.0, True
    for d in lib["directions"]:
        for seed in range(40):
            pp = sample(d, random.Random(seed), None, None)
            for sc in ("light", "dark"):
                t_ = pp["palette"][sc]
                worst_ct = min(worst_ct, contrast(t_["climb-text"], t_["paper"]), contrast(t_["climb-text"], t_["paper-2"]))
                ok(contrast(t_["m-select"], t_["m-slab"]) >= 3.0, "%s %s: m-select (edge) >= 3:1 on the slab" % (d["id"], sc))
                ok("m-select-fill" in t_ and t_["m-select-fill"] != t_["m-select"], "%s %s: m-select-fill exists and is a tint, not the edge" % (d["id"], sc))
                if hex_to_oklch(t_["climb"])[1] >= CHROMA_NEUTRAL and \
                        hue_distance(hex_to_oklch(t_["climb"])[2], hex_to_oklch(t_["climb-text"])[2]) > CLIMB_TEXT_HUE_MAX:
                    hue_kept = False
    ok(worst_ct >= 4.5, "climb-text >= 4.5:1 on paper and paper-2, light and dark (worst %.2f)" % worst_ct)
    ok(hue_kept, "climb-text keeps the hue of climb")
    css_ = tokens_css(pz)
    ok("--climb-text:" in css_ and "--m-select-fill:" in css_ and 'data-evk-lead="zh"' in css_, "tokens.css carries the new tokens and the lead attribute")

    # --- FIX-SPEC B: tones on a dark-ground card keep the hue (EVK.tones twin: assets/engine/tones.js, same table)
    dk_ = {"paper": "#14202E", "ink": "#EEEAE1", "night": "#0B1220"}
    for hx in ("#1F6FB2", "#2E7D32", "#8C1515", "#7F5AF0", "#FF6C0C", "#09A7C8"):
        t_ = tones(hx, **dk_)
        ok(contrast(t_["eText"], dk_["paper"]) >= TONES_TARGET - 1e-9, "dark ground: eText reads on the paper for %s" % hx)
        ok(t_["eText"] != dk_["ink"] and hue_distance(hex_to_oklch(t_["eText"])[2], hex_to_oklch(hx)[2]) < 4, "dark ground: eText keeps the hue of %s (got %s)" % (hx, t_["eText"]))
        ok(contrast(t_["eOn"], t_["e"]) >= 4.5, "dark ground: eOn reads on e for %s" % hx)

    # --- FIX-SPEC-3 A1: --keep projection=rotate (orbit | exploded)
    ok(parse_keep(["projection=rotate"])["projection"] == "rotate" and parse_keep(["projection=Rotatable"])["projection"] == "rotate", "projection=rotate parses (and its alias)")
    for d in lib["directions"]:
        for seed in range(12):
            pr_ = sample(d, random.Random(seed), parse_keep(["projection=rotate"]), None)
            ok(pr_["map"]["projection"] in PROJECTIONS_ROTATE and pr_["map"]["pitch"] < 70, "%s seed %d: projection=rotate turns on drag (%s, pitch %s)" % (d["id"], seed, pr_["map"]["projection"], pr_["map"]["pitch"]))
    obl = json.loads(json.dumps(lib["directions"][1]))
    obl["map"]["projection"] = ["oblique", "plan"]
    pr_ = sample(obl, random.Random(2), parse_keep(["projection=rotate"]), None)
    ok(pr_["map"]["projection"] == "exploded" and any(isinstance(x, dict) and x["key"] == "map.projection" and x["to"] == "exploded" for x in pr_["adjusted"]),
       "rotate on an oblique/plan-only direction -> exploded, recorded in `adjusted`")
    both = json.loads(json.dumps(lib["directions"][1]))
    both["map"]["projection"] = ["oblique", "orbit", "plan"]
    got = {sample(both, random.Random(sd), parse_keep(["projection=rotate"]), None)["map"]["projection"] for sd in range(30)}
    ok(got == {"orbit"}, "rotate keeps the direction's own rotating projection when it has one (%s)" % sorted(got))
    ok(not any(isinstance(x, dict) for x in sample(both, random.Random(3), parse_keep(["projection=rotate"]), None)["adjusted"]), "…inside the envelope: nothing to record")
    noroll = json.loads(json.dumps(lib["directions"][1]))
    noroll["map"]["projection"] = ["oblique", "plan"]
    errs_, _ = validate_library({"directions": [noroll], "axes": {}})
    ok(any("rotating projection" in e for e in errs_), "validate: a direction with no rotating projection is an error")

    # --- FIX-SPEC-3 A2: hue families
    ok(hue_families(30) == [[30.0, 30.0]] and hue_families([20, 30]) == [[20.0, 30.0]] and hue_families([[20, 30], [150, 160]]) == [[20.0, 30.0], [150.0, 160.0]]
       and hue_families(None) == [], "hue_families: a number, a range, a list of ranges")
    try:
        hue_families([[1, 2, 3]])
        ok(False, "hue_families should reject [[1,2,3]]")
    except ValueError:
        pass
    ok(arc_gap([20, 30], [150, 160]) == 120 and arc_gap([350, 10], [5, 20]) == 0 and arc_gap([340, 355], [15, 20]) == 20, "arc_gap (wraps through 360)")
    air = lib["directions"][1]
    seen_b, seen_clb = {}, {}
    for seed in range(80):
        pp = sample(air, random.Random(seed), None, None)
        fm = pp["palette"]["families"]
        i_ = fm["b"]["index"]
        seen_b[i_] = seen_b.get(i_, 0) + 1
        bh = pp["palette"]["sampled"]["b"][2]
        rng_ = hue_families(air["palette"]["b"]["h"])[i_]
        ok(rng_[0] - 1e-6 <= bh <= rng_[1] + 1e-6, "airmail seed %d: b hue %.1f is inside its family %s" % (seed, bh, rng_))
        ch = pp["palette"]["sampled"]["climb"][2]
        crng = hue_families(air["palette"]["climb"]["h"])[i_]
        ok(crng[0] - 1e-6 <= ch <= crng[1] + 1e-6, "airmail seed %d: climb follows the b family (%.1f in %s)" % (seed, ch, crng))
        ok(fm["b"]["of"] == 2 and fm["b"]["name"] in air["palette"]["b"]["names"] and "climb" not in fm, "the card records the b family and its name (a follower is not listed)")
        ok(hue_distance(bh, ch) >= CLIMB_HUE_MIN, "airmail seed %d: climb is >= 50 deg from b without being moved" % seed)
        ok(not [t for t in pp["floor_tuned"] if ".climb: hue" in t], "…and nothing was tuned: %s" % pp["floor_tuned"][:1])
    ok(set(seen_b) == {0, 1}, "both b families are drawn over 80 seeds (%s)" % seen_b)
    sc_ = lib["directions"][2]
    for seed in range(40):                       # night follows a (neutral-night ignores the hue, but the index still follows)
        pp = sample(sc_, random.Random(seed), None, None)
        ok(pp["palette"]["families"]["a"]["of"] == 2 and "night" not in pp["palette"]["families"], "scoreboard: a is a leader with two families, night follows")
    # ONE DRAW PER ROLE, whatever the number of families: the RNG ends in the same state, and a one-family role equals a list of one
    vs = json.loads(json.dumps(lib["directions"][0]))
    states, cards = [], []
    for hb in ([22, 28], [[22, 28]], [[22, 28], [150, 160]], [[22, 28], [150, 160], [300, 310]]):
        v2 = json.loads(json.dumps(vs))
        v2["palette"]["b"]["h"] = hb
        v2["palette"]["b"]["names"] = ["x%d" % i for i in range(len(hue_families(hb)))] if len(hue_families(hb)) > 1 else None
        if v2["palette"]["b"]["names"] is None:
            del v2["palette"]["b"]["names"]
        rg = random.Random(31)
        cards.append(sample(v2, rg, None, None))
        states.append(rg.getstate())
    ok(all(st == states[0] for st in states), "sample() spends one draw per role on the family: the RNG ends in the same state with 1, 1 (as a list), 2 and 3 families")
    ok(cards[0]["palette"]["light"] == cards[1]["palette"]["light"], "a single range and a list of one range give the same card")
    ok(all(c["type"] == cards[0]["type"] and c["map"] == cards[0]["map"] and c["motion"] == cards[0]["motion"] for c in cards), "…and a second family moves nothing but the palette")
    # keep: a frozen b leaves the family draw alone and drops b from the record
    k1 = sample(air, random.Random(9), parse_keep(["b=#0B5FFF"]), None)
    k0 = sample(air, random.Random(9), None, None)
    ok("b" not in k1["palette"]["families"] and "b" in k0["palette"]["families"], "a frozen b is not a drawn family")
    ok(k1["type"] == k0["type"] and k1["map"] == k0["map"] and k1["palette"]["sampled"]["paper"] == k0["palette"]["sampled"]["paper"], "…and moves nothing else")
    # typical card = first family
    ok(typical_fingerprint(air) == typical_fingerprint(air) and sample(air, random.Random(0), None, None, mode=True)["palette"]["families"]["b"]["index"] == 0, "mode=True (typical card) takes the first family")
    # validation of families
    def lib_with(mut):
        dd = json.loads(json.dumps(lib["directions"][1]))
        mut(dd)
        return validate_library({"directions": [dd], "axes": {}})[0]
    ok(not [e for e in lib_with(lambda dd: None) if "palette" in e or "family" in e], "validate: the fixture's families are fine")
    ok(any("needs 2-4 hue families" in e for e in lib_with(lambda dd: dd["palette"]["b"].update(h=[20, 32]))), "validate: a non-canonical b with one family is an error")
    ok(any("canonical direction stays single-family" in e for e in validate_library({"directions": [dict(json.loads(json.dumps(lib["directions"][0])), id="varsity", canonical=True,
                                                                                                 palette=dict(lib["directions"][0]["palette"], a=dict(lib["directions"][0]["palette"]["a"], h=[[255, 265], [150, 160]])))], "axes": {}})[0]),
       "validate: the canonical direction may not have families")
    ok(any("follows" in e and "families" in e for e in lib_with(lambda dd: dd["palette"]["climb"].update(h=[[95, 110], [250, 262], [10, 20]]))), "validate: a follower needs the same number of families")
    ok(any("can only follow an earlier" in e for e in lib_with(lambda dd: dd["palette"]["b"].update(follow="climb"))), "validate: a role can only follow an earlier one")
    ok(any("would read as one" in e for e in lib_with(lambda dd: dd["palette"]["b"].update(h=[[20, 32], [30, 40]]))), "validate: overlapping families are an error")
    ok(any("climb family" in e for e in lib_with(lambda dd: dd["palette"]["climb"].update(h=[[40, 50], [250, 262]]))), "validate: climb must clear b in every pairing")
    ok(any("names must list one name per family" in e for e in lib_with(lambda dd: dd["palette"]["b"].update(names=["only one"]))), "validate: names match the families")
    # props (FIX-SPEC-4 item 9)
    leaf = {"name": "leaf", "var": "--prop-leaf", "off": "none", "what": "叶形标签"}

    def props_with(props):
        return lib_with(lambda dd: dd.__setitem__("props", props))

    def props_warns(props, css):
        dd = json.loads(json.dumps(lib["directions"][1]))
        dd["props"] = props
        w_ = []
        check_props(dd["id"], props, [], w_)
        check_props_in_recipe(dd["id"], props, css, [], w_)
        return w_
    ok(not [e for e in props_with([leaf, {"name": "seal", "var": "--prop-seal", "off": "0", "what": "蜡封"}]) if "props" in e], "validate: a well-formed props list is fine")
    ok(not [e for e in props_with([]) + lib_with(lambda dd: None) if "props" in e], "validate: props is optional (and may be empty)")
    ok(any("props must be a list" in e for e in props_with({"leaf": "none"})), "validate: props must be a list")
    ok(any("'what' must be a non-empty string" in e for e in props_with([{"name": "leaf", "var": "--prop-leaf", "off": "none"}])), "validate: every prop needs what")
    ok(any("'off' must be a non-empty string" in e for e in props_with([dict(leaf, off="")])), "validate: every prop needs an off value")
    ok(any("'var' must be a non-empty string" in e for e in props_with([{"name": "leaf", "off": "none", "what": "x"}])), "validate: every prop needs a var")
    ok(any("must be a custom property named --prop-" in e for e in props_with([dict(leaf, var="--leaf")])), "validate: var is a --prop-* custom property")
    ok(any("name must be kebab-case" in e for e in props_with([dict(leaf, name="Leaf Label")])), "validate: name is kebab-case")
    ok(any("duplicate prop name" in e for e in props_with([leaf, dict(leaf, var="--prop-leaf-2")])), "validate: a prop name occurs once")
    ok(any("duplicate var" in e for e in props_with([leaf, dict(leaf, name="leaf-2")])), "validate: a var occurs once")
    ok(any("one bare CSS value" in e for e in props_with([dict(leaf, off="none; color: red")])), "validate: off is one bare value")
    ok(any("must be an object" in e for e in props_with(["leaf"])), "validate: a prop is an object")
    ok(any("does not match the name" in w for w in props_warns([dict(leaf, var="--prop-foliage")], "")), "validate: a var that is not --prop-<name> is a warning")
    ok(any("never reads var(--prop-leaf)" in w for w in props_warns([leaf], ".evk-tag{color:red}")), "validate: a listed var the recipe never reads is a warning")
    ok(any("reads var(--prop-seal)" in w and "does not list" in w for w in props_warns([leaf], ".a{content:var(--prop-leaf,'x')}.b{background:var( --prop-seal )}")),
       "validate: a --prop-* the recipe reads but the library does not list is a warning")
    ok(not props_warns([leaf], ".a{content:var(--prop-leaf,'x')}"), "validate: a recipe that reads exactly the listed vars is clean")
    ok(any("declares --prop-leaf itself" in w for w in props_warns([leaf], ":root{--prop-leaf:'x'}.a{content:var(--prop-leaf)}")), "validate: a recipe that declares the var itself would beat the switch")
    ok(not any("declares" in w for w in props_warns([leaf], "/* --prop-leaf: none; */.a{content:var(--prop-leaf,'x')}")), "validate: a comment that mentions the var is not a declaration")
    import tempfile
    with tempfile.TemporaryDirectory() as td_:
        dd_ = dict(json.loads(json.dumps(lib["directions"][1])), props=[leaf])
        (Path(td_) / ("%s.css" % dd_["id"])).write_text(".x{background:var(--prop-leaf,url(leaf.svg))}.y{content:var(--prop-orphan)}", encoding="utf-8")
        w_ = validate_library({"directions": [dd_], "axes": {}}, recipes_dir=td_)[1]
        ok(any("--prop-orphan" in w for w in w_) and not any("never reads" in w for w in w_), "validate_library(recipes_dir) cross-checks the recipe file of each direction")
        ok(not any("--prop-" in w for w in validate_library({"directions": [dd_], "axes": {}}, recipes_dir=False)[1]), "validate_library(recipes_dir=False) skips the cross-check")
    pp = sample(dict(lib["directions"][1], props=[leaf]), random.Random(5), None, None)
    ok(pp["props"] == [leaf] and props_of(pp) == [leaf] and props_of({}) == [], "sample() carries the direction's props into params (old rolls have none)")
    ok(sample(lib["directions"][1], random.Random(5), None, None)["props"] == [], "a direction without props has an empty list")
    css_on = tokens_css(pp)
    ok("/* --prop-leaf: none;" in css_on and not re.search(r"^\s*--prop-leaf:", css_on, re.M), "tokens.css: props are COMMENTED lines (on by default)")
    ok(re.search(r"^\s*--prop-leaf: none;", tokens_css(pp, props_off=True), re.M) and re.search(r"^\s*--prop-leaf: none;", tokens_css(pp, props_off={"leaf"}), re.M),
       "tokens.css: props_off=True / a name set writes live declarations")
    ok(not re.search(r"^\s*--prop-leaf:", tokens_css(pp, props_off={"other"}), re.M), "tokens.css: props_off={other} leaves leaf on")
    ok("--prop-" not in tokens_css(sample(lib["directions"][1], random.Random(5), None, None)), "tokens.css: a direction without props writes no props block")
    ok(live_props(css_on, pp) == set() and live_props(tokens_css(pp, props_off=True), pp) == {"leaf"} and live_props(css_on.replace("/* --prop-leaf: none;", "--prop-leaf: none; /*"), pp) == {"leaf"}
       and live_props(tokens_css(pp, props_off=True).replace("none;", "block;"), pp) == set(), "live_props reads back the lines that are switched off")
    ok(any("leaf" in ln and "props" in ln for ln in card_summary_lines(pp)) and not any(ln.startswith("props") for ln in card_summary_lines(sample(lib["directions"][1], random.Random(5), None, None))),
       "card_summary_lines names the props")
    # FIX-SPEC-5 #2: install.py --update carries every LIVE --prop-* line over verbatim; the rest is regenerated
    two = dict(pp, props=[leaf, {"name": "grain", "var": "--prop-grain", "off": "0", "what": "纸纹"}])
    css2 = tokens_css(two)
    ok(live_prop_lines(css2) == [], "live_prop_lines: commented lines are not live")
    ok(re.search(r"^\s*/\* --prop-leaf: none; \*/  /\* 叶形标签 \(leaf\) \*/$", css2, re.M), "tokens.css: a prop line is the declaration in one comment and the description in another")
    mine = css2.replace("/* --prop-leaf: none; */", "--prop-leaf: none;").replace("/* --prop-grain: 0; */", "--prop-grain: .4;")     # the two ways to uncomment
    lines = live_prop_lines(mine)
    ok([x["vars"] for x in lines] == [["--prop-leaf"], ["--prop-grain"]] and lines[0]["line"] == "  --prop-leaf: none;  /* 叶形标签 (leaf) */"
       and lines[1]["line"].startswith("  --prop-grain: .4;"), "live_prop_lines: a line is kept as it was written (value, trailing comment)")
    again = tokens_css(two, props_keep=lines)
    ok(live_prop_lines(again) == lines and "/* --prop-leaf:" not in again and "/* --prop-grain:" not in again and again.count("--prop-leaf") == 1,
       "tokens.css(props_keep): the live lines come back verbatim, in place of the generated ones")
    ok("/* --prop-grain: 0; */" in tokens_css(two, props_keep=lines[:1]) and "--prop-grain: .4" not in tokens_css(two, props_keep=lines[:1]), "…and a prop without a live line stays a commented switch")
    odd = "\n".join(["  /* a note: --prop-leaf: none; (inside a comment) */", "  --prop-leaf: none;  叶形标签 (leaf)", "  --prop-grain: 0.2; /* two", "  lines */", "  --prop-gone: 1;", "  /* x", "  --prop-leaf: block; */"])
    lo = live_prop_lines(odd)
    ok([x["line"] for x in lo] == ["  --prop-leaf: none;", "  --prop-grain: 0.2;", "  --prop-gone: 1;"], "live_prop_lines: text after a declaration or an open comment is dropped, comments are ignored: %s" % [x["line"] for x in lo])
    kept = tokens_css(two, props_keep=lo)
    ok(kept.count("--prop-gone: 1;") == 1 and kept.index("--prop-gone") > kept.index("--prop-grain") and "no prop for" in kept, "a live line of a var this card has no prop for is kept, after the block")
    ok(live_props(mine, two) == {"leaf"}, "live_props still reports which props sit at their OFF value")
    ok("--prop-gone: 1;" in tokens_css(sample(lib["directions"][1], random.Random(5), None, None), props_keep=lo), "…also for a direction without props")
    # the colour-word rule: a text may name a hue only when EVERY family of some role has it
    def claims(text, mut=None):
        dd = json.loads(json.dumps(lib["directions"][1]))
        dd["idea"] = text
        if mut:
            mut(dd)
        return colour_claims(dd)
    ok(not claims("a blue-ish airmail, 蓝灰色的信笺"), "colour words: 蓝 is backed by the paper and a (one family each)")
    ok(claims("红色的邮戳"), "colour words: 红 is NOT backed when b may also be green")
    ok(not claims("红色的邮戳", lambda dd: dd["palette"]["b"].update(h=[[20, 30], [350, 360]])), "…but is when every b family is red")
    ok(claims("紫色的印章"), "colour words: a hue no role has is flagged")
    ok(claims("紫线", lambda dd: dd["palette"].update(a=dict(dd["palette"]["a"], h=[270, 290]))), "colour words: a family that only touches the band's edge does not back it")
    # --- FIX-SPEC-3 A3: --m-cap carries 7:1 and --m-wall 3:1 on --m-slab, light and dark
    worst_cap, worst_wall = 99.0, 99.0
    worst_head = 99.0      # FIX-SPEC-5 #1: contrast(a-text) - (contrast(text) - 0.5) on paper, must stay >= 0
    for d in lib["directions"]:
        for seed in range(40):
            for steer in (None, "bolder", "safer"):
                pp = sample(d, random.Random(seed), None, steer)
                for sc in ("light", "dark"):
                    t_ = pp["palette"][sc]
                    worst_cap = min(worst_cap, contrast(t_["m-cap"], t_["m-slab"]))
                    worst_wall = min(worst_wall, contrast(t_["m-wall"], t_["m-slab"]))
                    worst_head = min(worst_head, contrast(t_["a-text"], t_["paper"]) - (contrast(t_["text"], t_["paper"]) - HEADING_SLACK))
    ok(worst_cap >= 7.0, "m-cap >= 7:1 on m-slab in light and dark for every sampled card (worst %.2f)" % worst_cap)
    ok(worst_wall >= 3.0, "m-wall >= 3:1 on m-slab in light and dark for every sampled card (worst %.2f)" % worst_wall)
    ok(worst_head >= -1e-9, "--a-text (headings) is never dimmer than --text - %.1f on paper, light and dark, for every sampled card (worst margin %+.2f)" % (HEADING_SLACK, worst_head))
    hb = {"paper": "#FFFFFF", "paper-2": "#F0F0F0", "text": "#111111", "a-text": "#767676"}     # a heading at 4.5:1 under a 18.9:1 body
    res = {c["id"]: c for c in check_scheme(hb)}
    ok(not res["heading/body"]["ok"] and res["heading/body"]["level"] == "warn", "check_scheme: heading/body warns when the heading carries < 80 % of the body contrast (but >= 4.5)")
    hb["a-text"] = "#BBBBBB"
    res = {c["id"]: c for c in check_scheme(hb)}
    ok(not res["heading/body"]["ok"] and res["heading/body"]["level"] == "floor", "check_scheme: heading/body fails under 4.5:1")
    hb["a-text"] = "#222222"
    ok({c["id"]: c for c in check_scheme(hb)}["heading/body"]["ok"], "check_scheme: a heading as dark as the body passes")
    weak = {"paper": "#FFFFFF", "paper-2": "#F0F0F0", "m-slab": "#EEEEEE", "m-cap": "#8A8A8A", "m-wall": "#DDDDDD"}
    res = {c["id"]: c for c in check_scheme(weak)}
    ok(not res["m-cap/m-slab"]["ok"] and res["m-cap/m-slab"]["level"] == "floor" and "m-cap/m-slab(7:1)" not in res and not res["m-wall/m-slab"]["ok"] and res["m-wall/m-slab"]["level"] == "warn",
       "check_scheme: a cap under 4.5:1 fails (once: no second 7:1 warning), a wall under 3:1 warns")
    mid = {"paper": "#FFFFFF", "paper-2": "#F0F0F0", "m-slab": "#EEEEEE", "m-cap": "#595959", "m-wall": "#767676"}
    res = {c["id"]: c for c in check_scheme(mid)}
    ok(res["m-cap/m-slab"]["ok"] and not res["m-cap/m-slab(7:1)"]["ok"] and res["m-wall/m-slab"]["ok"], "check_scheme: 4.5 <= cap < 7 passes the floor and warns")
    # --- FIX-SPEC-3 B: floor_tuned (strings the floor rules wrote) and adjusted (what a person asked for) are two lists
    for d in lib["directions"]:
        pp = sample(d, random.Random(4), parse_keep(["projection=plan"]), None)
        ok(all(isinstance(x, str) for x in pp["floor_tuned"]) and all(isinstance(x, dict) for x in pp["adjusted"]), "%s: floor_tuned holds strings, adjusted holds records" % d["id"])
    ok(adjust_counts({"floor_tuned": ["a", "b", "UNRESOLVED x"], "adjusted": [{"key": "k"}]}) == (2, 1, 1) and floor_notes({"adjusted": ["old string", {"key": "k"}]}) == ["old string"]
       and unresolved({"adjusted": ["UNRESOLVED light x"]}) == ["UNRESOLVED light x"], "floor_notes / adjust_counts read both places (older rolls keep strings in adjusted)")

    # --- old rolls stay usable
    old = json.loads(json.dumps(pz))
    for sc in ("light", "dark"):
        old["palette"][sc].pop("climb-text")
        old["palette"][sc].pop("m-select-fill")
    old.pop("lead")
    up = upgrade_params(old)
    ok(up is not old and up["lead"] == "en" and "climb-text" in up["palette"]["light"] and "m-select-fill" in up["palette"]["dark"], "upgrade_params fills what an older roll lacks")
    ok(contrast(up["palette"]["light"]["climb-text"], up["palette"]["light"]["paper"]) >= 4.5, "…and the filled climb-text reads")
    ok(upgrade_params(pz) is pz, "upgrade_params is free for a current card")
    ok("--climb-text:" in tokens_css(old), "tokens_css accepts an older roll")
    older = json.loads(json.dumps(pz))
    older["adjusted"] = ["light.a: lightness re-fitted", {"key": "map.pitch", "from": 84, "to": 30, "reason": "x"}]
    older.pop("floor_tuned")
    older["palette"].pop("families")
    older["palette"]["dark"]["m-cap"] = older["palette"]["dark"]["a"]            # round-2 caps: the brand ink as it was
    older["palette"]["dark"]["m-wall"] = older["palette"]["dark"]["m-slab"]
    up2 = upgrade_params(older)
    ok(up2["floor_tuned"] == ["light.a: lightness re-fitted"] and [x["key"] for x in up2["adjusted"]] == ["map.pitch"] and up2["palette"]["families"] == {},
       "upgrade_params splits floor_tuned from adjusted and adds the families record")
    ok(contrast(up2["palette"]["dark"]["m-cap"], up2["palette"]["dark"]["m-slab"]) >= 7.0 and contrast(up2["palette"]["dark"]["m-wall"], up2["palette"]["dark"]["m-slab"]) >= 3.0,
       "…and walks an older roll's weak m-cap / m-wall to 7:1 / 3:1")
    ok(upgrade_params(up2) is up2, "…once")
    ok(adjust_text({"key": "map.pitch", "from": 84, "to": 30, "reason": "x"}).startswith("map.pitch: 84 -> 30") and adjust_text("plain") == "plain", "adjust_text")
    ok(param_get(pz, "projection") == pz["map"]["projection"] and param_get(pz, "b") == pz["palette"]["light"]["b"] and param_get(pz, "display") == pz["type"]["fonts"]["display"]["name"], "param_get")

    if fails:
        print("kit.py selftest: %d FAILED" % len(fails))
        return 1
    print("kit.py selftest: ok (%d cards floor-checked, %d tones rows)" % (n, len(TONES_TABLE_EXPECTED) + len(TONES_OKLCH_EXPECTED)))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kit.py", description="event-venue-kit shared module / 共用模块. Import it from the other scripts; "
                                 "the CLI only offers self-test and library validation.")
    ap.add_argument("--selftest", action="store_true", help="run built-in tests (inline fixture library)")
    ap.add_argument("--validate", nargs="?", const="", metavar="PATH", help="validate library/directions.json (or PATH) against BUILD-SPEC section 3")
    ap.add_argument("--tones-table", action="store_true", help="print the fixed tones() comparison table")
    ap.add_argument("--method", choices=["mix", "oklch"], default="oklch", help="with --tones-table: algorithm (oklch = EVK.tones; mix = source)")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    if a.tones_table:
        print(format_tones_table(method=a.method))
        return 0
    if a.validate is not None:
        try:
            lib = load_directions(a.validate or None)
        except (FileNotFoundError, ValueError) as e:
            print("kit.py: %s" % e, file=sys.stderr)
            return 2
        errs, warns = validate_library(lib)
        for e in errs:
            print("ERROR  ", e)
        for w in warns:
            print("warning", w)
        fam = []
        for d in lib["directions"]:
            roles = []
            for role in HUE_ROLES:
                spec = (d.get("palette") or {}).get(role) or {}
                try:
                    n = len(hue_families(spec.get("h")))
                except ValueError:
                    n = 0
                if n > 1:
                    roles.append("%s x%d%s" % (role, n, " (follows %s)" % spec["follow"] if spec.get("follow") else ""))
            fam.append("%s: %s" % (d.get("id"), ", ".join(roles) or "one family"))
        print("hue families -- " + " | ".join(fam))
        pr = ["%s: %s" % (d.get("id"), ", ".join("%s=%s" % (x.get("name"), x.get("off")) for x in (d.get("props") or []) if isinstance(x, dict))) for d in lib["directions"] if d.get("props")]
        print("props (name=off value) -- " + (" | ".join(pr) if pr else "none listed"))
        print("%d directions, %d errors, %d warnings" % (len(lib["directions"]), len(errs), len(warns)))
        return 1 if errs else 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
