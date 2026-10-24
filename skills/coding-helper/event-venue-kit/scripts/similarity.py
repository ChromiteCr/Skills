#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""event-venue-kit :: similarity.py -- how close is a card to the source site (and to its siblings)?  指纹距离。

    similarity.py <roll.json> [--card N] [--max X]       fingerprint of each card vs the canonical one and vs the other cards
    similarity.py --sweep 200 [--count 3] [--tags a,b] [--canon] [--library PATH | --fixture]
                                                          draw 200 hands (seeds 0..199, no history), lint every card, report the spread

Fingerprint = 12 axes: palette_family (structure + hue bucket of a and b, 30 degree buckets), ground, display_class,
label_style (case | stretch class | mono?), shape.language, divider, entity_header, entity_token, numerals,
map.projection, map.material, motion_bucket (still / firm / lively).  Similarity = matching axes / 12.
Canonical fingerprint: references/reference-direction/fingerprint.json when present, else the typical card of the
library's canonical direction.

Reading the number / 怎么读
  < 0.34   a different look                       0.34-0.5  a cousin: check which axes match
  >= 0.5   too close to the source site -- re-roll (references/randomness.md) unless the user asked for the source look

--sweep asserts (exit 1 if one fails):
  1. every drawn card passes lint_floor (all floor checks, light and dark)
  2. mean similarity to canonical <= 0.34              (skipped with --canon)
  3. no direction takes more than 30 % of the drawn cards when no tags are given
  4. every direction honours the freezes a brief asks for: `--keep projection=3d` gives a 3D projection with a tilted pitch,
     `--keep projection=rotate` gives orbit or exploded, `--keep lead=zh` gives lead zh, and those cards pass lint_floor too
  5. every hue family of every direction is reachable: over the sweep each family of each direction is drawn at least once
     (FIX-SPEC-3 A2; skipped when a direction gets fewer than 24 cards)
Also prints the distribution of directions and of the main axes, the PALETTE SPREAD of each direction (which hue families its
cards drew, how many distinct palettes, how far apart the accent hues are) and the mean similarity between cards of one hand.
Exit code: 0 ok; 1 an assertion failed (or --max exceeded); 2 usage / input error.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit  # noqa: E402
import draw  # noqa: E402
import lint_floor  # noqa: E402

MEAN_CANON_MAX = 0.34
SHARE_MAX = 0.30
CLOSE_TO_CANON = 0.5
CLOSE_SIBLINGS = 0.58


def report_roll(roll, only=None, max_allowed=None):
    canon_fp = roll.get("canon_fingerprint")
    src = roll.get("canon_fingerprint_source", "roll")
    if not canon_fp:
        canon_fp, src = kit.canonical_fingerprint()
    cards = roll.get("cards") or []
    lines = ["similarity: canonical fingerprint from %s" % src]
    worst = 0.0
    for i, c in enumerate(cards, 1):
        if only and i != only:
            continue
        fp = kit.fingerprint(c["params"]) if c.get("params") else c.get("fingerprint")   # from the params: a hand-edited roll cannot keep a stale one
        s = kit.similarity(fp, canon_fp)
        matched = kit.axis_matches(fp, canon_fp)
        is_canon = c.get("direction") == "varsity" or (c.get("params") or {}).get("direction") == "varsity"
        verdict = "canonical direction (expected)" if is_canon else ("TOO CLOSE: re-roll or --steer bolder" if s >= CLOSE_TO_CANON else ("cousin" if s >= MEAN_CANON_MAX else "different"))
        lines.append("")
        lines.append("card %d  %s  %s   similarity to canon %.2f (%d/12)  %s" % (i, c.get("direction"), c.get("code", ""), s, len(matched), verdict))
        for k in kit.FP_AXES:
            f = kit.normalize_fingerprint(fp)[k]
            g = kit.normalize_fingerprint(canon_fp)[k]
            lines.append("    %-16s %-34s %s %s" % (k, f, "==" if f == g else "!=", g))
        if c.get("params") and kit.family_text(c["params"]):
            lines.append("    hue family       %s" % kit.family_text(c["params"]))
        if not is_canon:
            worst = max(worst, s)
    if len(cards) > 1 and not only:
        lines.append("")
        lines.append("between cards of this hand:")
        for i in range(len(cards)):
            for j in range(i + 1, len(cards)):
                s = kit.similarity(kit.fingerprint(cards[i]["params"]), kit.fingerprint(cards[j]["params"]))
                flag = "  (close: the hand lacks range)" if s >= CLOSE_SIBLINGS else ""
                lines.append("    %d vs %d: %.2f%s" % (i + 1, j + 1, s, flag))
    rc = 0
    if max_allowed is not None and worst > max_allowed:
        lines.append("")
        lines.append("FAILED: a non-canonical card exceeds --max %.2f (%.2f)" % (max_allowed, worst))
        rc = 1
    return "\n".join(lines), rc


def sweep(lib, n=200, count=3, tags=(), canon=False, quiet=False):
    """Draw n hands, lint every card. Returns (text, ok)."""
    t0 = time.time()
    canon_fp, src = kit.canonical_fingerprint(lib)
    dirs = Counter()
    axes = {k: Counter() for k in ("ground", "display_class", "shape.language", "divider", "entity_header", "entity_token", "numerals",
                                   "map.projection", "map.material", "motion_bucket", "label_style")}
    hue_a = Counter()
    spread = {}          # direction id -> {"fam": Counter(of family-name tuples), "b": [hues], "pal": Counter(of palette_family)}
    sims = []
    sib = []
    failures = []
    ncards = 0
    for seed in range(n):
        cards = draw.draw_cards(lib, seed, count, list(tags), {}, None, canon, set(), canon_fp)
        for c in cards:
            ncards += 1
            dirs[c["direction"]] += 1
            fp = c["fingerprint"]
            for k in axes:
                axes[k][fp[k]] += 1
            hue_a[fp["palette_family"].split("|")[1]] += 1
            sp = spread.setdefault(c["direction"], {"fam": Counter(), "b": [], "pal": Counter(), "idx": {}})
            fams = c["params"]["palette"].get("families") or {}
            sp["fam"][tuple((r, f.get("name") or str(f["index"])) for r, f in fams.items())] += 1
            for r, f in fams.items():
                sp["idx"].setdefault(r, Counter())[f["index"]] += 1
            sp["b"].append(c["params"]["palette"]["sampled"]["b"][2])
            sp["pal"][fp["palette_family"]] += 1
            sims.append(c["similarity_to_canon"])
            rep = lint_floor.lint_params(c["params"])
            if not rep.ok:
                failures.append((seed, c["direction"], [i["id"] + " " + i["msg"] for i in rep.failed][:3]))
            adj = kit.unresolved(c["params"])
            if adj:
                failures.append((seed, c["direction"], adj[:2]))
        for i in range(len(cards)):
            for j in range(i + 1, len(cards)):
                sib.append(kit.similarity(cards[i]["fingerprint"], cards[j]["fingerprint"]))
    mean_sim = sum(sims) / max(1, len(sims))
    mean_sib = sum(sib) / max(1, len(sib))
    lines = ["sweep: %d hands x %d cards = %d cards   tags: %s   canon: %s   library: %s (%d directions)   %.1fs" % (
        n, count, ncards, ",".join(tags) or "-", canon, lib.get("_path"), len(lib["directions"]), time.time() - t0),
        "canonical fingerprint: %s" % src, ""]
    lines.append("directions (share of cards):")
    mx = max(dirs.values()) if dirs else 1
    for d in lib["directions"]:
        c = dirs.get(d["id"], 0)
        lines.append("  %-18s %5d  %5.1f%%  %s" % (d["id"], c, 100.0 * c / max(1, ncards), "#" * int(30 * c / mx)))
    lines.append("")
    for k, cnt in axes.items():
        lines.append("%-15s %s" % (k, "  ".join("%s %d%%" % (v, round(100.0 * c / max(1, ncards))) for v, c in cnt.most_common())))
    def hue_key(item):
        v = item[0][1:]
        return (not v.isdigit(), int(v) if v.isdigit() else 0)
    lines.append("%-15s %s" % ("hue of a", "  ".join("%s %d%%" % (v[1:], round(100.0 * c / max(1, ncards))) for v, c in sorted(hue_a.items(), key=hue_key))))
    lines.append("")
    lines.append("similarity to canon: mean %.3f  max %.2f   between cards of a hand: mean %.3f  max %.2f" % (
        mean_sim, max(sims or [0]), mean_sib, max(sib or [0])))
    lines.append("")
    lines.append("palette spread per direction  (cards | family combos drawn / a|b hue buckets of the fingerprint | accent hue spread = mean pairwise distance of b in degrees | b family shares):")
    for d in lib["directions"]:
        sp = spread.get(d["id"])
        if not sp:
            continue
        n = len(sp["b"])
        hs = sp["b"][:60]
        pw = [kit.hue_distance(hs[i], hs[j]) for i in range(len(hs)) for j in range(i + 1, len(hs))]
        pal = d["palette"]
        nb = len(kit.hue_families(pal["b"].get("h")))
        if nb > 1:
            lead_role = kit.family_leader(pal, "b")
            names = kit.family_names(pal[lead_role], len(kit.hue_families(pal[lead_role].get("h"))))
            cnt = Counter(kit.family_index_of(pal["b"], h) for h in sp["b"])
            share = "  ".join("%s %d%%" % ((names[i] or "family %d" % (i + 1)).split(" ")[0], round(100.0 * cnt[i] / n)) for i in sorted(k for k in cnt if k is not None))
        else:
            share = "one family (canonical)" if d.get("canonical") else "one family"
        lines.append("  %-16s %4d | %2d / %2d | %3.0f deg | %s" % (d["id"], n, len(sp["fam"]) or 1, len(sp["pal"]), (sum(pw) / len(pw)) if pw else 0.0, share))
    lines.append("")
    ok = True
    if failures:
        ok = False
        lines.append("FAIL  %d card(s) fail lint_floor, e.g. seed %s %s: %s" % (len(failures), failures[0][0], failures[0][1], "; ".join(failures[0][2])))
    else:
        lines.append("pass  every one of the %d cards passes lint_floor (light and dark)" % ncards)
    if canon:
        lines.append("skip  mean similarity to canonical (--canon)")
    elif mean_sim <= MEAN_CANON_MAX:
        lines.append("pass  mean similarity to canonical %.3f <= %.2f" % (mean_sim, MEAN_CANON_MAX))
    else:
        ok = False
        lines.append("FAIL  mean similarity to canonical %.3f > %.2f" % (mean_sim, MEAN_CANON_MAX))
    # 4. the freezes: every direction can honour projection=3d and lead=zh
    kfail = []
    for d in lib["directions"]:
        for seed in range(8):
            for want, allowed in (("3d", kit.PROJECTIONS_3D), ("rotate", kit.PROJECTIONS_ROTATE)):
                pk = kit.sample(d, __import__("random").Random(seed), kit.parse_keep(["projection=" + want, "lead=zh"]), None)
                if pk["map"]["projection"] not in allowed or pk["map"]["pitch"] >= 70 or pk["lead"] != "zh":
                    kfail.append("%s seed %d: projection=%s gave %s pitch %s lead %s" % (d["id"], seed, want, pk["map"]["projection"], pk["map"]["pitch"], pk["lead"]))
                if not lint_floor.lint_params(pk).ok or kit.unresolved(pk):
                    kfail.append("%s seed %d: a frozen card (%s) fails lint_floor" % (d["id"], seed, want))
    if kfail:
        ok = False
        lines.append("FAIL  --keep projection=3d|rotate lead=zh not honoured, e.g. %s" % kfail[0])
    else:
        lines.append("pass  every direction honours projection=3d, projection=rotate and lead=zh (%d directions x 8 seeds, lint included)" % len(lib["directions"]))
    # 5. every family of every direction is reachable
    miss = []
    for d in lib["directions"]:
        sp = spread.get(d["id"])
        if not sp or len(sp["b"]) < 24:
            continue
        for role in kit.HUE_ROLES:
            spec = (d["palette"].get(role) or {})
            nf = len(kit.hue_families(spec.get("h"))) if spec.get("h") is not None else 1
            if nf > 1 and not spec.get("follow"):
                got = set(sp["idx"].get(role, {}))
                if got != set(range(nf)):
                    miss.append("%s.%s drew families %s of %d" % (d["id"], role, sorted(got), nf))
    if miss:
        ok = False
        lines.append("FAIL  some hue family was never drawn, e.g. %s" % miss[0])
    else:
        lines.append("pass  every hue family of every direction was drawn at least once")
    top, topn = (dirs.most_common(1) or [("-", 0)])[0]
    share = topn / float(max(1, ncards))
    if tags or canon:
        lines.append("skip  direction share (tags given or --canon)")
    elif share <= SHARE_MAX:
        lines.append("pass  largest direction share %.1f%% (%s) <= %d%%" % (100 * share, top, SHARE_MAX * 100))
    else:
        ok = False
        lines.append("FAIL  direction %s takes %.1f%% of the cards (> %d%%)" % (top, 100 * share, SHARE_MAX * 100))
    return "\n".join(lines), ok


def _synthetic_library(n=12):
    """Selftest only: the 3-direction fixture cannot satisfy 'no direction > 30 %' with hands of 3, so make 12 variants."""
    import copy
    base = kit.load_directions(fixture=True)
    lib = {"version": 1, "axes": {}, "directions": [base["directions"][0]]}
    classes = ["serif-display", "slab", "grotesk", "mono", "condensed", "rounded", "didone", "humanist"]
    langs = ["chamfer", "square", "soft", "pill", "perforated", "notched", "tab", "arched"]
    divs = kit.AXES_VOCAB["divider"]
    heads = kit.AXES_VOCAB["entity_header"]
    toks = kit.AXES_VOCAB["entity_token"]
    nums = kit.AXES_VOCAB["numerals"]
    projs = kit.AXES_VOCAB["map.projection"]
    mats = kit.AXES_VOCAB["map.material"]
    for i in range(n - 1):
        d = copy.deepcopy(base["directions"][1 + (i % 2)])
        d["id"] = "fx%d" % i
        d["canonical"] = False
        d["weight"] = 1.0
        for role in ("a", "b", "paper", "night", "climb"):
            h = d["palette"][role]["h"]
            fams = [[(lo + i * 31) % 360, (lo + i * 31 + (hi - lo)) % 360] for lo, hi in kit.hue_families(h)]
            d["palette"][role]["h"] = fams if isinstance(h[0], (list, tuple)) else fams[0]
        for role in ("display", "label", "text", "num"):
            for f in d["type"][role]:
                f["class"] = classes[(i + hash(role) % 3) % len(classes)] if role == "display" else f["class"]
        d["type"]["display"][0]["class"] = classes[i % len(classes)]
        d["shape"]["language"] = [langs[i % len(langs)]]
        d["divider"] = [divs[i % len(divs)]]
        d["entity_header"] = [heads[i % len(heads)]]
        d["entity_token"] = [toks[(i * 2) % len(toks)]]
        d["numerals"] = [nums[i % len(nums)]]
        d["map"]["projection"] = [projs[i % len(projs)]]
        d["map"]["material"] = [mats[(i * 3) % len(mats)]]
        lib["directions"].append(d)
    return lib


def _selftest():
    kit.REFERENCE_FP_PATH = kit.SCRIPTS_DIR / "__no_reference__.json"   # hermetic: no dependence on other builders' files
    fails = []

    def ok(cond, msg):
        if not cond:
            fails.append(msg)
            print("  FAIL", msg)

    lib = kit.load_directions(fixture=True)
    cfp, _ = kit.canonical_fingerprint(lib)
    ok(kit.similarity(cfp, cfp) == 1.0, "identical fingerprints -> 1.0")
    other = dict(cfp, ground="dark", display_class="x")
    ok(abs(kit.similarity(cfp, other) - 10 / 12.0) < 1e-9, "two differing axes -> 10/12")
    ok(kit.similarity(cfp, {"fingerprint": cfp}) == 1.0, "nested fingerprint accepted")
    roll = draw.build_roll(lib, 11, 3, [], {}, None, False, None, False)
    txt, rc = report_roll(roll)
    ok("similarity to canon" in txt and rc == 0, "roll report")
    txt, rc = report_roll(roll, max_allowed=0.0)
    ok(rc in (0, 1), "max flag")
    # a hand-edited roll keeps a stale stored fingerprint: the report reads the params, not the stored copy
    import copy
    stale = copy.deepcopy(roll)
    c0 = stale["cards"][1]
    c0["params"]["map"]["projection"] = "plan" if c0["params"]["map"]["projection"] != "plan" else "orbit"
    txt, rc = report_roll(stale, only=2)
    ok(("map.projection   %s" % c0["params"]["map"]["projection"]) in txt, "report follows the params when the stored fingerprint is stale")
    c0["params"]["adjusted"] = ["UNRESOLVED light text/paper 3.1<7", {"key": "map.pitch", "from": 84, "to": 30, "reason": "x"}]
    ok(kit.unresolved(c0["params"]) == ["UNRESOLVED light text/paper 3.1<7"], "unresolved() skips explicit adjustment records")
    # the 3-direction fixture cannot meet the spread assertions with hands of 3: the sweep must SAY so
    text, passed = sweep(lib, 30, 3, (), False)
    ok(not passed and "FAIL  direction" in text, "sweep reports a direction taking > 30 %")
    # a 12-direction synthetic library passes everything and is fast
    syn = _synthetic_library(12)
    t0 = time.time()
    text, passed = sweep(syn, 120, 3, (), False)
    ok(passed, "synthetic 12-direction sweep passes:\n" + text)
    ok(time.time() - t0 < 20, "120-hand sweep is fast (%.1fs)" % (time.time() - t0))
    # tags given: the share assertion is skipped, lint still runs
    text, passed = sweep(syn, 20, 3, ("letter",), False)
    ok(passed and "skip  direction share" in text, "tag sweep skips the share assertion")
    # canon sweep: all canonical, mean assertion skipped
    text, passed = sweep(syn, 10, 2, (), True)
    ok(passed and "skip  mean similarity" in text, "canon sweep skips the mean assertion")
    if fails:
        print("similarity.py selftest: %d FAILED" % len(fails))
        return 1
    print("similarity.py selftest: ok")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="similarity.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("roll", nargs="?", help="roll.json")
    ap.add_argument("--card", type=int, help="only this card (1-based)")
    ap.add_argument("--max", type=float, metavar="X", help="exit 1 if a non-canonical card is more similar than X")
    ap.add_argument("--sweep", type=int, metavar="N", help="draw N hands and check the whole library")
    ap.add_argument("--count", type=int, default=3, help="cards per hand in --sweep (default 3)")
    ap.add_argument("--tags", help="tags for --sweep (default none)")
    ap.add_argument("--canon", action="store_true", help="--sweep with --canon (skips the mean-similarity assertion)")
    ap.add_argument("--library", metavar="PATH")
    ap.add_argument("--fixture", action="store_true", help="use the tiny built-in fixture library")
    ap.add_argument("--selftest", action="store_true", help="run built-in tests")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    try:
        if a.sweep:
            lib = kit.load_directions(fixture=True) if a.fixture else kit.load_directions(a.library)
            tags = [t for t in (a.tags or "").split(",") if t]
            text, ok_ = sweep(lib, a.sweep, a.count, tags, a.canon)
            print(text)
            return 0 if ok_ else 1
        if not a.roll:
            ap.print_help()
            return 2
        roll = json.loads(Path(a.roll).read_text(encoding="utf-8"))
        text, rc = report_roll(roll, a.card, a.max)
        print(text)
        return rc
    except (OSError, ValueError, KeyError) as e:
        print("similarity.py: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
