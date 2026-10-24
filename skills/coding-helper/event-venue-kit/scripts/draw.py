#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""event-venue-kit :: draw.py -- seeded draw of design directions.  抽牌：先抽方向，再在方向的包络内抽参数。

    draw.py [--tags a,b] [--seed N] [--count 3] [--keep axis=value ...] [--canon] [--steer safer|bolder]
            [--history PATH | --no-history] [--venue data/venue.json] [--out .evk/roll.json] [--json]
    draw.py choose N --reason "..." [--roll .evk/roll.json] [--history PATH | --no-history] [--venue PATH]
    draw.py adjust KEY=VALUE ... --reason "..." [--card N] [--roll .evk/roll.json] [--history PATH | --no-history]
    draw.py decode CODE [--out PATH] [--json]
    draw.py list                                   the direction pool (weights, fits, ground, map)

How a hand is dealt / 抽牌规则
  weight = direction.weight x tag match x history x steer
    tag match : 0.5 + 1.5 x (matched tags / given tags)       (1 when no tags are given)
    history   : x 0.25 for directions chosen in the last 6 chosen rolls (never 0)
    steer     : bolder -> 0.5 + 1.5 x distance_from_canon ; safer -> 0.5 + 1.5 x (1 - distance_from_canon)
  Directions are drawn without replacement. After each card, every direction still in the pool is multiplied by
  0.6 for each of ground / display class / motion bucket / map material it shares with that card, so a hand
  shows three visibly different worlds. Then sample() draws every parameter inside the direction's envelope.
  Steer also widens the envelopes toward the bold end (bolder) or contracts them (safer).
  Everything is a function of the seed: the same --seed, --tags, --keep, --steer and library give the same hand.

--keep (freeze what the brief already decided) / 冻结
  palette=#hex,#hex[,paper[,climb]]   a and b inks (then optional paper and climb)     a=#hex b=#hex paper=#hex climb=#hex night=#hex
  display="Family" label= text= num= cjk= cjk_display=            font family (looked up in the direction, else used as given)
  label_case=none label_track= label_stretch= label_weight= display_weight= display_track= display_leading= ratio=
  language=chamfer radius=6 chamfer=0 divider= entity_header= entity_token= numerals= nav= density= texture=
  projection=plan material=blueprint pitch= yaw= wall_h= light= dim= map_label_case=
  dur= bounce= press=  structure=  dark=neutral-night
  lead=zh                             which language leads a bilingual pair: en (default) | zh  (<html data-evk-lead>)
  projection=rotate                   "the map must turn when you drag it": orbit | exploded (the direction's own, else exploded)
  projection=3d                       the card must use a 3D projection (orbit | oblique | exploded): the direction's own
                                      choice if it has one, else exploded; oblique pans and does not turn.
                                      projection=plan|orbit|... forces that value.
  direction=airmail[,heraldry]        restrict the pool to these directions
  A frozen axis is used as given even when it lies outside the direction's envelope (then it is recorded in the card's
  `adjusted`); the floor rules still apply. Freezing never moves another parameter: every parameter takes its draw first and
  a frozen value only overrides it, so the same seed gives the same card with or without --keep for everything not frozen.

adjust (after choosing) / 选定后微调
  draw.py adjust pitch=30 wall_h=.6 --reason "the brief wants three floors readable" --roll .evk/roll.json
  Edits the card IN PLACE (default: the chosen card, or --card N) with the same KEY=VALUE vocabulary as --keep, without
  dealing again: the card's seed is kept, so only what you name (and what depends on it: colour roles, tokens, fingerprint,
  similarity, preset code) changes. Each change is appended to the card's `adjusted` as {key, from, to, reason}; if the card
  is already in the history file, its code there is updated. Then run install.py again (see its --update).

Hue families / 色相家族
  Every non-canonical direction has 2-4 hue families for its accent (b), and often for the paper or the structure ink: the
  colours a real event of that mechanism would own (library-catalog: stamp ink violet | red | green). The card draws one family
  per role and the table prints it ("family" column); `--keep b=#hex` / `palette=` overrides it. varsity stays one family.

floor-tuned and adjusted / 两个计数
  floor-tuned  colour roles the generator walked on its own to meet a contrast floor (params.floor_tuned; automatic, routine)
  adjusted     what a person asked for: a frozen value outside its envelope, or a `draw.py adjust` (params.adjusted)

Preset code / 预设码   EVK1-XXXX-XXXX-...   (Crockford base32 of: direction index, card seed, steer, canon flag, library hash,
  --keep overrides, checksum).  `draw.py decode CODE` rebuilds exactly the same card.

Exit codes: 0 ok, 2 usage / input error.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import secrets
import sys
import tempfile
import time
import unicodedata
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit  # noqa: E402

DEFAULT_HISTORY = Path.home() / ".event-venue-kit" / "history.json"
DEFAULT_OUT = ".evk/roll.json"
HISTORY_WINDOW = 6
HISTORY_FACTOR = 0.25
SPREAD_AXES = ("ground", "display_class", "motion_bucket", "map.material")
SPREAD_FACTOR = 0.6   # per axis a remaining direction shares with a card already in the hand
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
STEER_CODE = {None: 0, "safer": 1, "bolder": 2}
STEER_NAME = {v: k for k, v in STEER_CODE.items()}


# --------------------------------------------------------------------------------------------------
# preset codes
# --------------------------------------------------------------------------------------------------

def _b32_encode(data):
    bits = "".join("{:08b}".format(b) for b in data)
    bits += "0" * (-len(bits) % 5)
    return "".join(CROCKFORD[int(bits[i:i + 5], 2)] for i in range(0, len(bits), 5))


def _b32_decode(text):
    t = text.upper().replace("O", "0").replace("I", "1").replace("L", "1")
    bits = ""
    for ch in t:
        if ch not in CROCKFORD:
            raise ValueError("bad character %r in preset code" % ch)
        bits += "{:05b}".format(CROCKFORD.index(ch))
    n = len(bits) // 8
    return bytes(int(bits[i * 8:(i + 1) * 8], 2) for i in range(n))


def _keep_to_string(keep):
    items = []
    for k in sorted(keep):
        if k == "direction":
            continue
        v = keep[k]
        items.append("%s=%s" % (k, ",".join(v) if isinstance(v, list) else v))
    return "\n".join(items)


def _checksum(data):
    s = 7
    for b in data:
        s = (s * 31 + b) & 0xFF
    return s


def encode_code(dir_index, card_seed, steer, canon, keep, lib_hash):
    """EVK1-<crockford base32>.  See module docstring for the layout."""
    flags = STEER_CODE[steer] | (4 if canon else 0)
    ks = _keep_to_string(keep or {})
    if ks:
        flags |= 8
    flags |= (lib_hash & 0xF) << 4
    body = bytearray([dir_index & 0xFF]) + int(card_seed & 0xFFFFFFFF).to_bytes(4, "big") + bytes([flags])
    if ks:
        co = zlib.compressobj(9, zlib.DEFLATED, -15)
        raw = co.compress(ks.encode("utf-8")) + co.flush()
        n = len(raw)
        body += bytes([n]) if n < 128 else bytes([0x80 | (n & 0x7F), n >> 7])
        body += raw
    body.append(_checksum(bytes(body)))
    text = _b32_encode(bytes(body))
    return "EVK1-" + "-".join(text[i:i + 4] for i in range(0, len(text), 4))


def decode_code(code):
    """-> dict(dir_index, card_seed, steer, canon, keep(dict), lib_hash). Raises ValueError for malformed codes."""
    t = code.strip().upper().replace(" ", "")
    if not t.startswith("EVK1"):
        raise ValueError("preset codes start with EVK1-")
    data = _b32_decode(t[4:].replace("-", ""))
    if len(data) < 7:
        raise ValueError("preset code too short")
    # drop trailing padding bytes created by base32 rounding: the checksum is the last byte of the real payload
    flags = data[5]
    need = 6
    keep = {}
    if flags & 8:
        n = data[6]
        off = 7
        if n & 0x80:
            n = (n & 0x7F) | (data[7] << 7)
            off = 8
        raw = data[off:off + n]
        need = off + n
        try:
            do = zlib.decompressobj(-15)
            ks = (do.decompress(raw) + do.flush()).decode("utf-8")
        except Exception as e:  # noqa
            raise ValueError("preset code is damaged (%s)" % e)
        keep = kit.parse_keep([ln for ln in ks.split("\n") if ln])
    if len(data) < need + 1:
        raise ValueError("preset code too short")
    if _checksum(data[:need]) != data[need]:
        raise ValueError("preset code checksum mismatch: typo?")
    return {"dir_index": data[0], "card_seed": int.from_bytes(data[1:5], "big"), "steer": STEER_NAME.get(flags & 3),
            "canon": bool(flags & 4), "keep": keep, "lib_hash": (flags >> 4) & 0xF}


# --------------------------------------------------------------------------------------------------
# history
# --------------------------------------------------------------------------------------------------

def load_history(path):
    """Chosen picks, oldest first. Missing or unreadable file -> []"""
    if not path:
        return []
    p = Path(path).expanduser()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return list(data.get("picks", []))
    except (ValueError, OSError) as e:
        print("draw.py: history %s unreadable (%s); ignoring it" % (p, e), file=sys.stderr)
        return []


def recent_directions(picks, n=HISTORY_WINDOW):
    return {p.get("direction") for p in picks[-n:]}


def append_history(path, entry):
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    picks = load_history(p)
    picks.append(entry)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": 1, "picks": picks}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(str(tmp), str(p))


# --------------------------------------------------------------------------------------------------
# the draw
# --------------------------------------------------------------------------------------------------

_TYPICAL = {}


def typical_fp(d):
    key = d["id"]
    if key not in _TYPICAL:
        _TYPICAL[key] = kit.typical_fingerprint(d)
    return _TYPICAL[key]


def direction_weights(lib, tags, recent, steer, canon_fp, pool=None):
    """[(direction, weight, {parts})] for the pool (default all directions)."""
    out = []
    tagset = [t for t in tags if t]
    for d in (pool if pool is not None else lib["directions"]):
        parts = {"base": float(d.get("weight", 1.0))}
        if tagset:
            fits = set(d.get("fits") or [])
            frac = sum(1 for t in tagset if t in fits) / float(len(tagset))
            parts["tags"] = 0.5 + 1.5 * frac
        else:
            parts["tags"] = 1.0
        parts["history"] = HISTORY_FACTOR if d["id"] in recent else 1.0
        if steer:
            dist = 1.0 - kit.similarity(typical_fp(d), canon_fp)
            parts["steer"] = (0.5 + 1.5 * dist) if steer == "bolder" else (0.5 + 1.5 * (1.0 - dist))
        else:
            parts["steer"] = 1.0
        w = parts["base"] * parts["tags"] * parts["history"] * parts["steer"]
        out.append((d, max(w, 1e-6), parts))
    return out


def hand_spread(a, b):
    """Weight factor for direction a once direction b is already in the hand."""
    fa, fb = typical_fp(a), typical_fp(b)
    shared = sum(1 for ax in SPREAD_AXES if fa.get(ax) is not None and fa.get(ax) == fb.get(ax))
    return SPREAD_FACTOR ** shared


def weighted_sample_without_replacement(rng, items, k, spread=None):
    """items: [(obj, weight)]. Returns up to k objects; consumes exactly k random numbers.
    spread(remaining_obj, picked_obj) -> factor applied to the rest of the pool after each pick."""
    pool = list(items)
    picks = []
    for _ in range(min(k, len(pool))):
        total = sum(w for _, w in pool)
        r = rng.random() * total
        acc = 0.0
        idx = len(pool) - 1
        for i, (_, w) in enumerate(pool):
            acc += w
            if r < acc:
                idx = i
                break
        picked = pool.pop(idx)[0]
        picks.append(picked)
        if spread:
            pool = [(o, w * spread(o, picked)) for o, w in pool]
    return picks


def make_card(lib, direction, card_seed, keep, steer, canon, canon_fp, index=None, weight=None):
    dirs = lib["directions"]
    di = [d["id"] for d in dirs].index(direction["id"])
    keep_for_sample = {k: v for k, v in (keep or {}).items() if k != "direction"}
    params = kit.sample(direction, random.Random(card_seed), keep_for_sample, steer)
    fp = kit.fingerprint(params)
    card = {
        "index": index,
        "code": encode_code(di, card_seed, steer, canon, keep_for_sample, kit.library_hash(lib)),
        "direction": direction["id"],
        "name": direction.get("name"),
        "card_seed": card_seed,
        "weight": None if weight is None else round(weight, 4),
        "keep": keep_for_sample,
        "params": params,
        "fingerprint": fp,
        "similarity_to_canon": round(kit.similarity(fp, canon_fp), 4),
    }
    return card


def draw_cards(lib, seed, count=3, tags=(), keep=None, steer=None, canon=False, recent=(), canon_fp=None):
    """The deterministic core: returns a list of cards."""
    keep = dict(keep or {})
    if canon_fp is None:
        canon_fp, _ = kit.canonical_fingerprint(lib)
    rng = random.Random(seed)
    dirs = lib["directions"]
    if canon:
        picks = [(kit.canonical_direction(lib), 1.0)] * count
    else:
        pool = dirs
        if keep.get("direction"):
            want = set(keep["direction"])
            pool = [d for d in dirs if d["id"] in want]
            unknown = want - {d["id"] for d in dirs}
            if unknown:
                raise ValueError("--keep direction=: unknown %s (have: %s)" % (", ".join(sorted(unknown)), ", ".join(d["id"] for d in dirs)))
        ws = direction_weights(lib, list(tags), set(recent), steer, canon_fp, pool)
        wmap = {d["id"]: w for d, w, _ in ws}
        chosen = weighted_sample_without_replacement(rng, [(d, w) for d, w, _ in ws], count, spread=hand_spread)
        picks = [(d, wmap[d["id"]]) for d in chosen]
    seeds = [rng.getrandbits(32) for _ in picks]
    return [make_card(lib, d, s, keep, steer, canon, canon_fp, i + 1, w) for i, ((d, w), s) in enumerate(zip(picks, seeds))]


def build_roll(lib, seed, count, tags, keep, steer, canon, history_path, use_history, rerolls=None, venue=None):
    canon_fp, canon_src = kit.canonical_fingerprint(lib)
    picks = load_history(history_path) if use_history else []
    recent = recent_directions(picks)
    cards = draw_cards(lib, seed, count, tags, keep, steer, canon, recent, canon_fp)
    return {
        "kit": kit.KIT_NAME, "kit_version": kit.KIT_VERSION, "seed": seed, "tags": list(tags), "keep": keep or {},
        "steer": steer, "canon": bool(canon), "count": count,
        "library": {"path": lib.get("_path"), "version": lib.get("version", 1), "hash": kit.library_hash(lib),
                    "directions": len(lib["directions"])},
        "canon_fingerprint": canon_fp, "canon_fingerprint_source": canon_src,
        "history_path": str(history_path) if (use_history and history_path) else None,
        "use_history": bool(use_history), "venue": str(Path(venue).expanduser().resolve()) if venue else None,
        "recent": sorted(recent),
        "cards": cards, "chosen": None, "reason": None, "history_written": False, "rerolls": rerolls or [],
    }


def card_from_code(lib, code):
    """Rebuild a card from a preset code. Returns (card, warnings)."""
    info = decode_code(code)
    warns = []
    if info["lib_hash"] != kit.library_hash(lib):
        warns.append("the library changed since this code was made (hash %d vs %d): the card may differ" % (info["lib_hash"], kit.library_hash(lib)))
    dirs = lib["directions"]
    if info["dir_index"] >= len(dirs):
        raise ValueError("direction index %d is not in this library (%d directions)" % (info["dir_index"], len(dirs)))
    canon_fp, _ = kit.canonical_fingerprint(lib)
    card = make_card(lib, dirs[info["dir_index"]], info["card_seed"], info["keep"], info["steer"], info["canon"], canon_fp, 1)
    return card, warns, info


# --------------------------------------------------------------------------------------------------
# presentation
# --------------------------------------------------------------------------------------------------

def _w(s):
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def _pad(s, n):
    return s + " " * max(0, n - _w(s))


def _sw(hexv, color):
    if not color:
        return hexv
    r, g, b = kit.hex_to_rgb(hexv)
    return "\x1b[48;2;%d;%d;%dm  \x1b[0m %s" % (r, g, b, hexv)


def short_families(params):
    """The accent families a card drew, short: '邮政红' or '松绿墙+珊瑚点' (the first word of each leader's name)."""
    fams = (params.get("palette") or {}).get("families") or {}
    out = [(f.get("name") or "#%d" % (f["index"] + 1)).split(" ")[0] for r, f in fams.items()]
    return "+".join(out) or "-"


def abs_path(p):
    return str(Path(p).expanduser().resolve())


def history_flag(roll):
    """The --history / --no-history the user passed when the roll was dealt (nothing when the default file is used), so a
    hint never sends a later command to the default ~/.event-venue-kit when the user chose another file."""
    if roll.get("use_history") is False:
        return " --no-history"
    hp = roll.get("history_path")
    if hp and abs_path(hp) != abs_path(DEFAULT_HISTORY):
        return " --history %s" % abs_path(hp)
    return ""


def project_dir_of(roll_path):
    """The project a roll belongs to: .evk/roll.json lives in <project>/.evk/."""
    rp = Path(abs_path(roll_path))
    return str(rp.parent.parent) if rp.parent.name == ".evk" else "<project-dir>"


def next_hints(roll, roll_path, chosen=False):
    """Copy-pasteable next commands: absolute paths (they work from any directory), the venue, the history the user passed."""
    rp = abs_path(roll_path or DEFAULT_OUT)
    sd = str(kit.SCRIPTS_DIR)
    venue = roll.get("venue")
    v = venue if venue else "<your venue.json>"
    proj = project_dir_of(rp)
    if chosen:
        return ["next: python3 %s/install.py %s %s --starter --venue %s" % (sd, rp, proj, v)]
    spec_out = str(Path(rp).parent / "specimens")
    return ["next: python3 %s/specimen.py %s --all --venue %s --out %s   (open every page; add --offline if you may not download fonts; no browser tab? add --png: PNGs via a local headless Chrome)" % (sd, rp, v, spec_out),
            "      python3 %s/draw.py choose N --reason \"names one physical thing from the inventory\" --roll %s%s" % (sd, rp, history_flag(roll))]


def format_roll(roll, color=False, detail=True, roll_path=None):
    lines = []
    head = "EVK roll  seed %s  tags: %s  count %s" % (roll["seed"], ",".join(roll["tags"]) or "-", len(roll["cards"]))
    if roll.get("steer"):
        head += "  steer: %s" % roll["steer"]
    if roll.get("canon"):
        head += "  CANON"
    if roll.get("keep"):
        head += "  keep: %s" % " ".join("%s=%s" % (k, ",".join(v) if isinstance(v, list) else v) for k, v in roll["keep"].items())
    lines.append(head)
    if roll.get("recent"):
        lines.append("history: down-weighted (x%s) %s" % (HISTORY_FACTOR, ", ".join(roll["recent"])))
    cols = ["#", "direction", "ground", "paper", "a", "b", "family", "display", "shape", "map", "motion", "sim", "code"]
    rows = []
    for c in roll["cards"]:
        p = c["params"]
        lt = p["palette"]["light"]
        rows.append([str(c.get("index") or ""), "%s %s" % (c["direction"], (c.get("name") or {}).get("cn", "")),
                     p["palette"]["ground"], lt["paper"], lt["a"], lt["b"], short_families(p),
                     "%s" % p["type"]["fonts"]["display"]["name"], "%s" % p["shape"]["language"],
                     "%s/%s" % (p["map"]["projection"], p["map"]["material"]),
                     kit.motion_bucket(p["motion"]["dur"], p["motion"]["bounce"]), "%.2f" % c["similarity_to_canon"], c["code"]])
    widths = [max(_w(cols[i]), *(_w(r[i]) for r in rows)) if rows else _w(cols[i]) for i in range(len(cols))]
    lines.append("  ".join(_pad(cols[i], widths[i]) for i in range(len(cols))))
    for r in rows:
        cells = []
        for i, v in enumerate(r):
            cell = _pad(v, widths[i])
            if color and cols[i] in ("paper", "a", "b"):
                cell = _sw(v, True) + " " * max(0, widths[i] - 9)
            cells.append(cell)
        lines.append("  ".join(cells))
    legend = False
    if detail:
        for c in roll["cards"]:
            lines.append("")
            lines.append("#%s  %s  %s   %s" % (c.get("index"), c["direction"], (c.get("name") or {}).get("en", ""), c["code"]))
            p = c["params"]
            lines.append("    mechanism: %s -- %s" % (p.get("mechanism"), p.get("idea")))
            for ln in kit.card_summary_lines(p):
                lines.append("    " + ln)
            ft, ad, bad = kit.adjust_counts(p)
            counts = []
            if ft:
                counts.append("floor-tuned: %d" % ft)
            if ad:
                counts.append("adjusted: %d" % ad)
            if bad:
                counts.append("UNRESOLVED: %d" % bad)
            legend = legend or bool(counts)
            lines.append("    similarity to canon %.2f (%s)%s" % (
                c["similarity_to_canon"], ",".join(kit.axis_matches(c["fingerprint"], roll["canon_fingerprint"])) or "no shared axis",
                ("   " + "  ".join(counts)) if counts else ""))
    if legend:
        lines.append("")
        lines.append("floor-tuned = colour roles the generator walked on its own to meet a contrast floor (automatic); "
                     "adjusted = values you froze outside the envelope or changed with `draw.py adjust`.")
    lines.append("")
    if roll.get("chosen"):
        lines.append("chosen: #%s -- %s" % (roll["chosen"], roll.get("reason")))
        lines.extend(next_hints(roll, roll_path, chosen=True))
    else:
        lines.extend(next_hints(roll, roll_path))
    return "\n".join(lines)


def write_roll(roll, path):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(roll, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(str(tmp), str(p))


def read_roll(path):
    """Read a roll.json. Cards made before FIX-SPEC A1-A3 lack `lead`, --climb-text and --m-select-fill: they are filled in
    here (kit.upgrade_params), so every script can rely on them."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError("roll file not found: %s (run draw.py first)" % p)
    roll = json.loads(p.read_text(encoding="utf-8"))
    for c in roll.get("cards") or []:
        if isinstance(c.get("params"), dict):
            c["params"] = kit.upgrade_params(c["params"])
    return roll


def pick_chosen_card(roll):
    """The chosen card of a roll (None if nothing chosen). `chosen` may be a 1-based index, a code, or a dict."""
    ch = roll.get("chosen")
    if ch in (None, "", False):
        return None
    cards = roll.get("cards") or []
    if isinstance(ch, dict):
        ch = ch.get("index") or ch.get("code")
    if isinstance(ch, int) or (isinstance(ch, str) and ch.isdigit()):
        i = int(ch)
        if 1 <= i <= len(cards):
            return cards[i - 1]
        return None
    for c in cards:
        if c.get("code") == ch:
            return c
    return None


# --------------------------------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------------------------------

def _load_lib(args):
    if getattr(args, "fixture", False):
        return kit.load_directions(fixture=True)
    return kit.load_directions(getattr(args, "library", None))


def cmd_draw(args):
    try:
        lib = _load_lib(args)
        keep = kit.parse_keep(args.keep)
    except (FileNotFoundError, ValueError, KeyError) as e:
        print("draw.py: %s" % e, file=sys.stderr)
        return 2
    tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
    known = {t for d in lib["directions"] for t in d.get("fits", [])}
    unknown = [t for t in tags if t not in known]
    if unknown and known:
        print("draw.py: note: tag(s) %s match no direction's `fits` (typo? known tags: %s)" % (", ".join(unknown), ", ".join(sorted(known))), file=sys.stderr)
    seed = args.seed if args.seed is not None else secrets.randbits(31)
    use_hist = not args.no_history
    hist_path = Path(args.history).expanduser() if args.history else DEFAULT_HISTORY
    rerolls = []
    out = Path(args.out)
    if args.reroll:
        if out.exists():
            try:
                prev = json.loads(out.read_text(encoding="utf-8"))
                rerolls = list(prev.get("rerolls", []))
                rerolls.append({"seed": prev.get("seed"), "codes": [c.get("code") for c in prev.get("cards", [])], "reason": args.reroll})
            except ValueError:
                pass
        if len(rerolls) > 2 and not args.force:
            print("draw.py: this would be re-roll #%d. The protocol allows at most two (references/randomness.md); "
                  "use --steer to move the whole pool, or pass --force and say why in --reroll." % len(rerolls), file=sys.stderr)
            return 2
    try:
        roll = build_roll(lib, seed, args.count, tags, keep, args.steer, args.canon, hist_path, use_hist, rerolls, getattr(args, "venue", None))
    except (ValueError, KeyError) as e:
        print("draw.py: %s" % e, file=sys.stderr)
        return 2
    wrote = args.out and args.out != "-"
    if wrote:
        try:
            write_roll(roll, args.out)
        except OSError as e:
            print("draw.py: cannot write %s: %s" % (args.out, e), file=sys.stderr)
            return 2
    if args.json:
        print(json.dumps(roll, ensure_ascii=False, indent=1))
        if wrote:
            print("roll written to %s" % args.out, file=sys.stderr)
    else:
        print(format_roll(roll, color=sys.stdout.isatty() and not os.environ.get("NO_COLOR"), roll_path=args.out if wrote else None))
        if wrote:
            print("roll written to %s" % abs_path(args.out))
    return 0


def cmd_choose(args):
    try:
        roll = read_roll(args.roll)
    except (FileNotFoundError, ValueError) as e:
        print("draw.py: %s" % e, file=sys.stderr)
        return 2
    cards = roll.get("cards", [])
    sel = None
    if args.n.isdigit():
        i = int(args.n)
        if 1 <= i <= len(cards):
            sel = i
    else:
        for i, c in enumerate(cards, 1):
            if c["code"].upper() == args.n.upper() or c["direction"] == args.n:
                sel = i
    if not sel:
        print("draw.py: no card %r in %s (cards: %s)" % (args.n, args.roll, ", ".join("%d=%s" % (i, c["direction"]) for i, c in enumerate(cards, 1))), file=sys.stderr)
        return 2
    reason = (args.reason or "").strip()
    if len(reason) < 4:
        print("draw.py: --reason is required: say which physical thing from the event inventory this direction answers "
              "(see references/randomness.md step 4)", file=sys.stderr)
        return 2
    card = cards[sel - 1]
    roll["chosen"] = sel
    roll["chosen_code"] = card["code"]
    roll["reason"] = reason
    if getattr(args, "venue", None):
        roll["venue"] = abs_path(args.venue)
    use_hist = not args.no_history
    hist_path = Path(args.history).expanduser() if args.history else (Path(roll["history_path"]).expanduser() if roll.get("history_path") else DEFAULT_HISTORY)
    if use_hist and not roll.get("history_written"):
        append_history(hist_path, {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "direction": card["direction"], "code": card["code"],
                                   "seed": roll.get("seed"), "tags": roll.get("tags", []), "reason": reason})
        roll["history_written"] = True
        roll["history_path"] = str(hist_path)
    write_roll(roll, args.roll)
    print("chosen #%d  %s  %s\nreason: %s\nhistory: %s" % (sel, card["direction"], card["code"], reason,
                                                            ("written to %s" % hist_path) if roll["history_written"] else "not written"))
    for ln in next_hints(roll, args.roll, chosen=True):
        print(ln)
    return 0


def card_keep(roll, card):
    """The --keep set this card was made with: stored on the card, else read back from its preset code, else the roll's."""
    if isinstance(card.get("keep"), dict):
        return dict(card["keep"])
    try:
        return dict(decode_code(card["code"])["keep"])
    except (ValueError, KeyError, TypeError):
        return {k: v for k, v in (roll.get("keep") or {}).items() if k != "direction"}


def update_history_code(path, old_code, new_code, changes):
    """Point the history entry of a card at its adjusted code (and note the changes). True when an entry was found."""
    p = Path(path).expanduser()
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return False
    hit = False
    for e in data.get("picks", []):
        if e.get("code") == old_code:
            e["code"] = new_code
            e.setdefault("adjusted", []).extend({"key": c["key"], "from": c["from"], "to": c["to"]} for c in changes)
            hit = True
    if hit:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        os.replace(str(tmp), str(p))
    return hit


def adjust_card(lib, roll, card_index, items, reason, today=None):
    """Edit one card of a roll in place, without dealing again. items: ['pitch=30', 'wall_h=.6', ...] (the --keep vocabulary).
    The card seed stays, so only the named axes and what depends on them move (kit.sample draws before it overrides).
    Re-derives colour roles and tokens (they are computed from params), the fingerprint, the similarity and the preset code;
    appends {key, from, to, reason} to params["adjusted"]. Returns (new_card, changes). Raises ValueError on bad input."""
    old = roll["cards"][card_index - 1]
    new_kv = kit.parse_keep(items)
    if "direction" in new_kv:
        raise ValueError("a card's direction cannot be adjusted: that is a different card (re-roll before choosing, or choose another)")
    if not new_kv:
        raise ValueError("adjust needs at least one KEY=VALUE (the --keep vocabulary)")
    merged = card_keep(roll, old)
    merged.pop("direction", None)
    if "palette" in new_kv:                     # a new palette= supersedes the old a / b / paper / climb it spells out
        for i, key in enumerate(("a", "b", "paper", "climb")):
            if i < len(new_kv["palette"]):
                merged.pop(key, None)
    merged.update(new_kv)
    direction = kit.direction_by_id(lib, old["direction"])
    canon_fp = roll.get("canon_fingerprint") or kit.canonical_fingerprint(lib)[0]
    card = make_card(lib, direction, old["card_seed"], merged, roll.get("steer"), bool(roll.get("canon")), canon_fp,
                     old.get("index"), old.get("weight"))
    changes = []
    for key in new_kv:
        frm, to = kit.param_get(old["params"], key), kit.param_get(card["params"], key)
        if frm != to:
            changes.append({"key": key, "from": frm, "to": to, "reason": reason, "date": today or time.strftime("%Y-%m-%d")})
    carried = [e for e in old["params"].get("adjusted", []) if isinstance(e, dict) and not kit.is_keep_record(e)]
    card["params"]["adjusted"] = list(card["params"].get("adjusted", [])) + carried + changes     # records only; floor_tuned stays as sample() wrote it
    roll["cards"][card_index - 1] = card
    return card, changes


def cmd_adjust(args):
    try:
        roll = read_roll(args.roll)
        lib = _load_lib(args)
    except (FileNotFoundError, ValueError, KeyError) as e:
        print("draw.py: %s" % e, file=sys.stderr)
        return 2
    reason = (args.reason or "").strip()
    if len(reason) < 4:
        print("draw.py: --reason is required: say why (the content or the brief), it is recorded in the card's `adjusted` "
              "and in DESIGN.md", file=sys.stderr)
        return 2
    cards = roll.get("cards") or []
    if args.card:
        if not 1 <= args.card <= len(cards):
            print("draw.py: no card %d in %s (cards: %s)" % (args.card, args.roll, ", ".join("%d=%s" % (i, c["direction"]) for i, c in enumerate(cards, 1))), file=sys.stderr)
            return 2
        idx = args.card
    else:
        ch = pick_chosen_card(roll)
        if ch is None:
            print("draw.py: no card is chosen in %s: pass --card N, or choose one first" % args.roll, file=sys.stderr)
            return 2
        idx = cards.index(ch) + 1
    old = cards[idx - 1]
    was_chosen = pick_chosen_card(roll) is old
    try:
        card, changes = adjust_card(lib, roll, idx, args.items, reason)
    except (ValueError, KeyError) as e:
        print("draw.py: %s" % e, file=sys.stderr)
        return 2
    if was_chosen:
        roll["chosen_code"] = card["code"]
        if isinstance(roll.get("chosen"), str) and not roll["chosen"].isdigit():
            roll["chosen"] = card["code"]
    hist_note = "not in a history file"
    if roll.get("history_written") and roll.get("history_path") and not args.no_history:
        hp = Path(args.history).expanduser() if args.history else Path(roll["history_path"]).expanduser()
        if changes and update_history_code(hp, old["code"], card["code"], changes):
            hist_note = "history entry in %s updated" % hp
    write_roll(roll, args.roll)
    p = card["params"]
    print("card %d  %s   %s -> %s" % (idx, card["direction"], old["code"], card["code"]))
    if not changes:
        print("nothing changed: the card already has those values")
    for c in changes:
        print("  %-14s %s -> %s" % (c["key"], c["from"], c["to"]))
    sim_old, sim_new = old.get("similarity_to_canon"), card["similarity_to_canon"]
    print("fingerprint and similarity recomputed: %s -> %.2f   (%s)" % ("%.2f" % sim_old if sim_old is not None else "?", sim_new, hist_note))
    bad = kit.unresolved(p)
    print("floor: %s" % ("ok" if not bad else "UNRESOLVED %s (the card needs a different value)" % "; ".join(bad)))
    print("recorded in `adjusted`: %d entr%s    next: python3 %s/install.py %s %s --update   (writes the new tokens; "
          "copy the rows into DESIGN.md > Deviations)" % (len(changes), "y" if len(changes) == 1 else "ies", kit.SCRIPTS_DIR, abs_path(args.roll),
                                                         project_dir_of(args.roll)))
    return 1 if bad else 0


def cmd_decode(args):
    try:
        lib = _load_lib(args)
        card, warns, info = card_from_code(lib, args.code)
    except (FileNotFoundError, ValueError, KeyError) as e:
        print("draw.py: %s" % e, file=sys.stderr)
        return 2
    for w in warns:
        print("warning: " + w, file=sys.stderr)
    canon_fp, src = kit.canonical_fingerprint(lib)
    roll = {"kit": kit.KIT_NAME, "kit_version": kit.KIT_VERSION, "seed": info["card_seed"], "tags": [], "keep": info["keep"],
            "steer": info["steer"], "canon": info["canon"], "count": 1,
            "library": {"path": lib.get("_path"), "version": lib.get("version", 1), "hash": kit.library_hash(lib),
                        "directions": len(lib["directions"])},
            "canon_fingerprint": canon_fp, "canon_fingerprint_source": src, "history_path": None, "recent": [],
            "cards": [card], "chosen": None, "reason": None, "history_written": False, "rerolls": [], "decoded_from": args.code}
    if args.out:
        write_roll(roll, args.out)
    if args.json:
        print(json.dumps(roll, ensure_ascii=False, indent=1))
    else:
        print(format_roll(roll, color=sys.stdout.isatty() and not os.environ.get("NO_COLOR"), roll_path=args.out))
        if args.out:
            print("roll written to %s" % abs_path(args.out))
    return 0


def cmd_list(args):
    try:
        lib = _load_lib(args)
    except (FileNotFoundError, ValueError) as e:
        print("draw.py: %s" % e, file=sys.stderr)
        return 2
    canon_fp, _ = kit.canonical_fingerprint(lib)
    print("%-16s %-6s %-7s %-30s %-22s %-22s %-14s %s" % ("id", "weight", "ground", "name", "material", "projection", "hue families", "fits"))
    for d in lib["directions"]:
        t = kit.sample(d, random.Random(0), None, None, mode=True)
        nm = "%s %s" % ((d.get("name") or {}).get("en", ""), (d.get("name") or {}).get("cn", ""))
        fam = " ".join("%s%s" % (r, "x%d" % len(kit.hue_families(d["palette"][r].get("h")))) for r in kit.HUE_ROLES
                       if len(kit.hue_families(d["palette"][r].get("h"))) > 1 and not d["palette"][r].get("follow")) or "one"
        print("%-16s %-6s %-7s %s %-22s %-22s %-14s %s" % (d["id"], d.get("weight", 1.0), t["palette"]["ground"], _pad(nm, 30),
                                                           "/".join(sorted(set(kit._as_list(d.get("map", {}).get("material"))))),
                                                           "/".join(kit._as_list(d.get("map", {}).get("projection"))), fam,
                                                           ",".join(d.get("fits", []))))
    return 0


# --------------------------------------------------------------------------------------------------
# self-test
# --------------------------------------------------------------------------------------------------

class _quiet(object):
    """Silence stdout/stderr of the commands exercised by a selftest."""

    def __enter__(self):
        import io
        self._o, self._e = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = io.StringIO()

    def __exit__(self, *a):
        sys.stdout, sys.stderr = self._o, self._e


def _selftest():
    kit.REFERENCE_FP_PATH = kit.SCRIPTS_DIR / "__no_reference__.json"   # hermetic: no dependence on other builders' files
    fails = []

    def ok(cond, msg):
        if not cond:
            fails.append(msg)
            print("  FAIL", msg)

    lib = kit.load_directions(fixture=True)
    canon_fp, _ = kit.canonical_fingerprint(lib)
    # determinism
    a = draw_cards(lib, 4242, 3, ["letter"], {}, None, False, set(), canon_fp)
    b = draw_cards(lib, 4242, 3, ["letter"], {}, None, False, set(), canon_fp)
    ok(json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True), "same seed -> same hand")
    c = draw_cards(lib, 4243, 3, ["letter"], {}, None, False, set(), canon_fp)
    ok(json.dumps(a, sort_keys=True) != json.dumps(c, sort_keys=True), "other seed -> other hand")
    ok(len({x["direction"] for x in a}) == 3, "no replacement: three different directions")
    # code round trip, with and without keep / steer / canon
    for steer in (None, "bolder", "safer"):
        for keep in ({}, kit.parse_keep(["palette=#0B5FFF,#FF5A1F", "display=Libre Franklin", "label_case=none", "projection=plan"])):
            for canon in (False, True):
                hand = draw_cards(lib, 99, 3, [], keep, steer, canon, set(), canon_fp)
                for card in hand:
                    code = card["code"]
                    back, warns, info = card_from_code(lib, code)
                    same = json.dumps(back["params"], sort_keys=True) == json.dumps(card["params"], sort_keys=True)
                    ok(same and back["code"] == code and not warns, "code round-trips (%s, steer=%s, canon=%s, keep=%d)" % (code, steer, canon, len(keep)))
                    ok(info["steer"] == steer and info["canon"] == canon, "code carries steer and canon")
    try:
        decode_code(a[0]["code"][:-2] + "ZZ")
        ok(False, "damaged code should fail")
    except ValueError:
        pass
    ok(decode_code(a[0]["code"].lower().replace("-", " "))["card_seed"] == a[0]["card_seed"], "decode tolerates case and spaces")
    # keep
    keep = kit.parse_keep(["palette=#0B5FFF,#FF5A1F", 'display="Libre Franklin"', "label_case=none", "projection=plan"])
    hand = draw_cards(lib, 5, 3, [], keep, None, False, set(), canon_fp)
    for card in hand:
        p = card["params"]
        ok(p["type"]["fonts"]["display"]["name"] == "Libre Franklin" and p["type"]["label_case"] == "none" and p["map"]["projection"] == "plan",
           "keep display/label_case/projection applied (%s)" % card["direction"])
        ok(p["palette"]["sampled"]["a"][2] > 250 and p["palette"]["sampled"]["b"][2] < 70, "keep palette applied to a and b")
    # canon
    hand = draw_cards(lib, 8, 3, [], {}, None, True, set(), canon_fp)
    ok(all(x["direction"] == "varsity" for x in hand) and len({x["card_seed"] for x in hand}) == 3, "--canon forces the canonical direction")
    # direction filter
    hand = draw_cards(lib, 8, 2, [], {"direction": ["airmail", "scoreboard"]}, None, False, set(), canon_fp)
    ok({x["direction"] for x in hand} == {"airmail", "scoreboard"}, "keep direction= restricts the pool")
    # history down-weighting and tag weighting (statistics)
    def share(tags, recent, steer=None, n=600):
        cnt = {}
        for s in range(n):
            rng = random.Random(s)
            ws = direction_weights(lib, tags, recent, steer, canon_fp)
            d = weighted_sample_without_replacement(rng, [(x, w) for x, w, _ in ws], 1)[0]
            cnt[d["id"]] = cnt.get(d["id"], 0) + 1
        return {k: v / float(n) for k, v in cnt.items()}
    s0 = share([], set())
    s1 = share([], {"airmail"})
    ok(s1["airmail"] < s0["airmail"] * 0.6 and s1.get("airmail", 0) > 0, "history factor reduces but never zeroes (%.2f -> %.2f)" % (s0["airmail"], s1["airmail"]))
    st = share(["letter"], set())
    ok(st["airmail"] > s0["airmail"], "tag match raises weight")
    ok(s0.get("varsity", 0) < 0.15, "canonical direction is rare (%.2f)" % s0.get("varsity", 0))
    sb = share([], set(), "bolder")
    ss = share([], set(), "safer")
    ok(sb.get("varsity", 0) < ss.get("varsity", 0), "steer safer favours the canonical side, bolder the far side")
    # chroma widening
    def mean_chroma(steer):
        vals = []
        for s in range(60):
            p = kit.sample(lib["directions"][1], random.Random(s), None, steer)
            vals.append(kit.hex_to_oklch(p["palette"]["light"]["b"])[1])
        return sum(vals) / len(vals)
    ok(mean_chroma("bolder") >= mean_chroma(None) - 1e-9 >= mean_chroma("safer") - 2e-9 - 1e-9, "bolder/safer move accent chroma")
    # roll, choose, history
    with tempfile.TemporaryDirectory() as td:
        hp = Path(td) / "h" / "history.json"
        rp = Path(td) / "roll.json"
        roll = build_roll(lib, 31337, 3, ["letter", "travel"], {}, None, False, hp, True)
        write_roll(roll, rp)
        ok(roll["chosen"] is None and roll["history_written"] is False, "fresh roll has no choice")
        class A:  # noqa
            pass
        ns = A()
        ns.n, ns.reason, ns.roll, ns.history, ns.no_history = "2", "the postage-paid reply card on the front desk", str(rp), None, False
        ns.fixture, ns.library = True, None
        with _quiet():
            rc = cmd_choose(ns)
        r2 = read_roll(rp)
        ok(rc == 0 and r2["chosen"] == 2 and r2["history_written"] is True, "choose writes the choice")
        picks = load_history(hp)
        ok(len(picks) == 1 and picks[0]["direction"] == r2["cards"][1]["direction"], "choose appends to history")
        ok(pick_chosen_card(r2)["code"] == r2["cards"][1]["code"], "pick_chosen_card")
        r3 = build_roll(lib, 31338, 3, [], {}, None, False, hp, True)
        ok(r3["recent"] == [picks[0]["direction"]], "next roll sees history")
        ns.n, ns.reason = "9", "x" * 10
        with _quiet():
            ok(cmd_choose(ns) == 2, "choose rejects an unknown card")
        ns.n, ns.reason = "1", ""
        with _quiet():
            ok(cmd_choose(ns) == 2, "choose requires a reason")
    ok("EVK roll" in format_roll(roll) and roll["cards"][0]["code"] in format_roll(roll), "table prints")
    # --- FIX-SPEC-3 B: the next commands carry an absolute roll path, the venue and the history the user passed
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "site"
        rp = proj / ".evk" / "roll.json"
        myhist = Path(td) / "my-history.json"
        vp = Path(td) / "data" / "venue.json"
        rr = build_roll(lib, 12, 3, [], {}, None, False, myhist, True, None, vp)
        txt = format_roll(rr, roll_path=rp)
        hint = txt[txt.index("next:"):]
        ok(str(rp.resolve()) in hint and "specimen.py" in hint and ("--venue %s" % vp.resolve()) in hint, "the specimen hint has the absolute roll path and --venue")
        ok(("--history %s" % myhist.resolve()) in hint and "draw.py choose N" in hint, "the choose hint carries the --history the user passed")
        ok(str(kit.SCRIPTS_DIR) in hint and "--out %s" % (proj.resolve() / ".evk" / "specimens") in hint, "scripts are addressed absolutely, specimens land beside the roll")
        rd = build_roll(lib, 12, 3, [], {}, None, False, DEFAULT_HISTORY, True)
        ok("--history" not in format_roll(rd, roll_path=rp) and "<your venue.json>" in format_roll(rd, roll_path=rp), "the default history is not spelled out; no venue -> a placeholder")
        rn = build_roll(lib, 12, 3, [], {}, None, False, None, False)
        ok("--no-history" in format_roll(rn, roll_path=rp), "--no-history is carried too")
        write_roll(rr, rp)
        ns2 = A()
        ns2.n, ns2.reason, ns2.roll, ns2.history, ns2.no_history, ns2.venue = "1", "the reply-paid card on the desk", str(rp), None, False, None
        ns2.fixture, ns2.library = True, None
        import io
        buf = io.StringIO()
        old_out = sys.stdout
        sys.stdout = buf
        try:
            cmd_choose(ns2)
        finally:
            sys.stdout = old_out
        out_ = buf.getvalue()
        ok("install.py %s %s --starter --venue %s" % (rp.resolve(), proj.resolve(), vp.resolve()) in out_, "choose prints the install command: roll, project (the parent of .evk), --starter --venue")
    # floor-tuned and adjusted are counted apart; the family shows in the table
    cards_ = draw_cards(lib, 3, 3, [], {}, None, False, set(), canon_fp)
    for c in cards_:
        c["params"]["floor_tuned"] = ["light.a: lightness re-fitted", "dark.b: lightness re-fitted"]
        c["params"]["adjusted"] = []
    cards_[1]["params"]["adjusted"] = [{"key": "map.pitch", "from": 84, "to": 30, "reason": "x"}]
    t2 = format_roll(dict(roll, cards=cards_))
    lines2 = [ln for ln in t2.splitlines() if ln.startswith("    similarity to canon")]
    ok(len(lines2) == 3 and all("floor-tuned: 2" in ln for ln in lines2) and "adjusted: 1" in lines2[1] and "adjusted" not in lines2[0] and "adjusted" not in lines2[2],
       "floor-tuned counts what the floor rules moved, adjusted only what a person asked for: %s" % lines2)
    ok(" family " in t2.splitlines()[1], "the table has a family column")
    ok(any(short_families(c["params"]) != "-" for c in cards_), "short_families names the drawn families")
    # lead is frozen like any axis and rides in the preset code
    hand = draw_cards(lib, 12, 3, [], kit.parse_keep(["lead=zh"]), None, False, set(), canon_fp)
    ok(all(c["params"]["lead"] == "zh" and decode_code(c["code"])["keep"].get("lead") == "zh" for c in hand), "lead=zh in params and in the code")
    ok(all(kit.root_attrs_html(c["params"]).count('data-evk-lead="zh"') == 1 for c in hand), "<html> attributes carry the lead")
    # keep=projection=3d: every direction can honour it
    hand = draw_cards(lib, 31, 3, [], kit.parse_keep(["projection=3d"]), None, False, set(), canon_fp)
    ok(all(c["params"]["map"]["projection"] in kit.PROJECTIONS_3D and c["params"]["map"]["pitch"] < 70 for c in hand), "projection=3d gives 3D cards")
    # same seed, same hand, with or without keep: the unfrozen parameters do not move (FIX-SPEC A5)
    base_hand = draw_cards(lib, 31, 3, [], {}, None, False, set(), canon_fp)
    for a_, b_ in zip(base_hand, hand):
        ok(a_["direction"] == b_["direction"] and a_["card_seed"] == b_["card_seed"], "keep does not change which cards are dealt")
        ok(all(a_["params"][k] == b_["params"][k] for k in ("palette", "type", "shape", "motion", "layout", "divider", "numerals")), "…nor their unfrozen parameters (%s)" % a_["direction"])

    # --- adjust: edits the chosen card in place, without dealing again (FIX-SPEC A5)
    class NS(object):
        def __init__(self, **kw):
            self.__dict__.update(kw)
    with tempfile.TemporaryDirectory() as td:
        hp = Path(td) / "h" / "history.json"
        rp = Path(td) / "roll.json"
        roll = build_roll(lib, 777, 3, ["letter"], kit.parse_keep(["lead=zh"]), None, False, hp, True)
        write_roll(roll, rp)
        mk = lambda items, **kw: NS(items=items, reason=kw.get("reason", "the brief wants three floors readable"), card=kw.get("card"),
                                    roll=str(rp), history=None, no_history=False, fixture=True, library=None)
        with _quiet():
            ok(cmd_adjust(mk(["pitch=30"])) == 2, "adjust without a chosen card and without --card -> 2")
            ok(cmd_adjust(mk(["pitch=30"], card=9)) == 2, "adjust --card 9 -> 2")
            ok(cmd_adjust(mk(["pitch=30"], reason="")) == 2, "adjust requires a reason")
            ok(cmd_adjust(mk(["direction=airmail"], card=1)) == 2, "adjust cannot change the direction")
            ok(cmd_adjust(mk(["nonsense=1"], card=1)) == 2, "adjust rejects unknown keys")
        ns = NS(n="2", reason="the reply-paid card on the desk", roll=str(rp), history=None, no_history=False, fixture=True, library=None)
        with _quiet():
            cmd_choose(ns)
        r0 = read_roll(rp)
        c0 = r0["cards"][1]
        with _quiet():
            rc = cmd_adjust(mk(["pitch=30", "wall_h=0.7", "projection=3d"]))
        ok(rc == 0, "adjust ran (rc=%s)" % rc)
        r1 = read_roll(rp)
        c1 = r1["cards"][1]
        p0, p1 = c0["params"], c1["params"]
        ok(p1["map"]["pitch"] == 30 and p1["map"]["wall_h"] == 0.7 and p1["map"]["projection"] in kit.PROJECTIONS_3D, "adjusted values applied")
        ok(r1["cards"][0] == r0["cards"][0] and r1["cards"][2] == r0["cards"][2], "the other cards are untouched")
        ok(c1["card_seed"] == c0["card_seed"] and c1["direction"] == c0["direction"], "the seed and the direction stay: not a re-deal")
        for k in ("palette", "type", "shape", "motion", "layout", "divider", "numerals", "entity_header", "lead"):
            ok(p0[k] == p1[k], "unrelated parameter %s did not move" % k)
        ent = [e for e in p1["adjusted"] if isinstance(e, dict) and not kit.is_keep_record(e)]
        ok(sorted(e["key"] for e in ent) == sorted(k for k, a_, b_ in (("pitch", p0["map"]["pitch"], 30), ("wall_h", p0["map"]["wall_h"], 0.7),
                                                                     ("projection", p0["map"]["projection"], p1["map"]["projection"])) if a_ != b_),
           "`adjusted` gets {key, from, to, reason} for every value that changed: %s" % [e["key"] for e in ent])
        ok(all(set(e) >= {"key", "from", "to", "reason"} and e["reason"] == "the brief wants three floors readable" for e in ent), "…with the reason")
        ok(c1["fingerprint"] == kit.fingerprint(p1) and abs(c1["similarity_to_canon"] - round(kit.similarity(c1["fingerprint"], r1["canon_fingerprint"]), 4)) < 1e-9,
           "fingerprint and similarity are recomputed")
        ok(c1["code"] != c0["code"] and r1["chosen"] == 2 and r1.get("chosen_code") == c1["code"], "new preset code, still the chosen card")
        back, warns, info = card_from_code(lib, c1["code"])
        strip = lambda pp: {k: v for k, v in pp.items() if k != "adjusted"}
        ok(strip(back["params"]) == strip(p1), "the new code rebuilds the adjusted card")
        picks = load_history(hp)
        ok(len(picks) == 1 and picks[0]["code"] == c1["code"], "the history entry follows the adjusted code")
        # a second adjust accumulates, and a colour edit re-derives the roles
        with _quiet():
            rc = cmd_adjust(mk(["b=#0B5FFF", "lead=en"], reason="brand blue from the logo"))
        r2 = read_roll(rp)
        p2 = r2["cards"][1]["params"]
        ok(rc == 0 and p2["palette"]["light"]["b"] != p1["palette"]["light"]["b"] and kit.hex_to_oklch(p2["palette"]["light"]["b"])[2] > 240, "b=#hex re-derives the accent (%s)" % p2["palette"]["light"]["b"])
        ok(p2["palette"]["light"]["b-text"] != p1["palette"]["light"]["b-text"] and not kit.unresolved(p2), "…and its dependent roles, floor intact")
        ok(p2["lead"] == "en" and p2["map"]["pitch"] == 30, "lead changed, the earlier adjustment is still in force")
        keys = [e["key"] for e in p2["adjusted"] if isinstance(e, dict) and not kit.is_keep_record(e)]
        ok(keys[:len(ent)] == [e["key"] for e in ent] and "b" in keys and "lead" in keys, "records accumulate in order: %s" % keys)
        with _quiet():
            ok(cmd_adjust(mk(["b=#0B5FFF"])) == 0, "adjusting to the same value is a no-op")
        ok(len([e for e in read_roll(rp)["cards"][1]["params"]["adjusted"] if isinstance(e, dict) and not kit.is_keep_record(e)]) == len(keys), "…and records nothing")
        with _quiet():
            ok(cmd_adjust(mk(["radius=9"], card=1)) == 0, "adjust --card 1 works on a card that was not chosen")
        ok(read_roll(rp)["chosen"] == 2, "…and the choice stays")
    ok(_w("寄往世界") == 8, "CJK width")
    if fails:
        print("draw.py selftest: %d FAILED" % len(fails))
        return 1
    print("draw.py selftest: ok")
    return 0


def build_parser():
    ap = argparse.ArgumentParser(prog="draw.py", formatter_class=argparse.RawDescriptionHelpFormatter,
                                 description=__doc__.split("How a hand is dealt")[0] + "Run `draw.py --help-long` for the full protocol.",
                                 epilog="subcommands: choose N --reason ... | adjust KEY=VALUE ... --reason ... | decode CODE | list    (see: draw.py choose --help)")
    ap.add_argument("--tags", help="comma-separated inventory tags, e.g. campus,science,competition")
    ap.add_argument("--seed", type=int, help="integer seed; omitted -> random, and recorded in roll.json")
    ap.add_argument("--count", type=int, default=3, help="number of cards (default 3)")
    ap.add_argument("--keep", nargs="*", default=[], metavar="AXIS=VALUE", help="freeze axes, e.g. palette=#0B5FFF,#FF5A1F display=\"Source Serif 4\" projection=plan")
    ap.add_argument("--canon", action="store_true", help="force the canonical (source-site) direction; only when the user asked for it")
    ap.add_argument("--steer", choices=["safer", "bolder"], help="bias the pool and widen/contract envelopes")
    ap.add_argument("--history", metavar="PATH", help="history file (default ~/.event-venue-kit/history.json)")
    ap.add_argument("--no-history", action="store_true", help="ignore history (used by sweeps and tests)")
    ap.add_argument("--venue", metavar="PATH", help="your venue.json: remembered in the roll so the printed next commands (specimen.py, install.py) carry it")
    ap.add_argument("--out", default=DEFAULT_OUT, help="roll file to write (default %s; '-' = do not write)" % DEFAULT_OUT)
    ap.add_argument("--json", action="store_true", help="print the roll as JSON instead of the table")
    ap.add_argument("--reroll", metavar="REASON", help="this is a re-roll: keep the previous roll's seed and codes in roll.json with REASON (max 2)")
    ap.add_argument("--force", action="store_true", help="with --reroll: allow a third re-roll")
    ap.add_argument("--library", metavar="PATH", help="alternative directions.json")
    ap.add_argument("--fixture", action="store_true", help="use the tiny built-in fixture library (tests, demos)")
    ap.add_argument("--selftest", action="store_true", help="run built-in tests")
    ap.add_argument("--help-long", action="store_true", help="print the full protocol and exit")
    return ap


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "choose":
        ap = argparse.ArgumentParser(prog="draw.py choose", description="Mark the chosen card of a roll and write the history. N is the card number (1-based), its code, or its direction id.")
        ap.add_argument("n", help="card number, code or direction id")
        ap.add_argument("--reason", required=False, help="why: name one physical thing from the event inventory")
        ap.add_argument("--roll", default=DEFAULT_OUT)
        ap.add_argument("--history", metavar="PATH")
        ap.add_argument("--no-history", action="store_true")
        ap.add_argument("--venue", metavar="PATH", help="your venue.json (remembered in the roll; shows up in the next command)")
        return cmd_choose(ap.parse_args(argv[1:]))
    if argv and argv[0] == "adjust":
        ap = argparse.ArgumentParser(prog="draw.py adjust", formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description="Edit a card in place (default: the chosen card) without dealing again. KEY=VALUE uses the --keep vocabulary "
                                                 "(pitch=30 wall_h=.6 projection=3d lead=zh b=#C8102E ...). The seed is kept: only what you name, and what "
                                                 "depends on it (colour roles, tokens, fingerprint, similarity, preset code), changes. Each change is appended "
                                                 "to the card's `adjusted` as {key, from, to, reason}.")
        ap.add_argument("items", nargs="+", metavar="KEY=VALUE")
        ap.add_argument("--reason", required=False, help="why (from the content or the brief); recorded")
        ap.add_argument("--card", type=int, help="card number (1-based); default the chosen card")
        ap.add_argument("--roll", default=DEFAULT_OUT)
        ap.add_argument("--history", metavar="PATH")
        ap.add_argument("--no-history", action="store_true", help="leave the history file alone")
        ap.add_argument("--library", metavar="PATH")
        ap.add_argument("--fixture", action="store_true")
        return cmd_adjust(ap.parse_args(argv[1:]))
    if argv and argv[0] == "decode":
        ap = argparse.ArgumentParser(prog="draw.py decode", description="Rebuild the card of a preset code (EVK1-...).")
        ap.add_argument("code")
        ap.add_argument("--out", metavar="PATH", help="also write a one-card roll.json")
        ap.add_argument("--json", action="store_true")
        ap.add_argument("--library", metavar="PATH")
        ap.add_argument("--fixture", action="store_true")
        return cmd_decode(ap.parse_args(argv[1:]))
    if argv and argv[0] == "list":
        ap = argparse.ArgumentParser(prog="draw.py list", description="List the direction pool.")
        ap.add_argument("--library", metavar="PATH")
        ap.add_argument("--fixture", action="store_true")
        return cmd_list(ap.parse_args(argv[1:]))
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.help_long:
        print(__doc__)
        return 0
    if args.selftest:
        return _selftest()
    if args.count < 1 or args.count > 12:
        print("draw.py: --count must be 1-12", file=sys.stderr)
        return 2
    return cmd_draw(args)


if __name__ == "__main__":
    sys.exit(main())
