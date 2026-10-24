#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""event-venue-kit :: tones.py -- one entity colour in, seven page-safe roles out.  一个实体色，派生全部角色。

    tones.py "#8C1515" [--paper HEX] [--ink HEX] [--night HEX] [--target 4.6] [--css] [--json]
    tones.py --batch entities.json [--css] [--json]       list of hex | {id: hex} | [{id, color}] | a venue.json
    tones.py "#8C1515" --roll .evk/roll.json [--card N]   use the paper / text / night of a rolled card
    tones.py --table [--method oklch|mix]                 the fixed comparison table (EVK.tones prints the oklch one)

Roles (CSS custom properties set per entity): e=--e (fill)  eText=--e-text (text on paper)  eOn=--e-on (text on the fill)
eSoft=--e-soft  eLine=--e-line  eDk=--e-dk (text AND fill in dark mode)  eSoftDk=--e-soft-dk.
Algorithm: see "TONES SPEC" at the top of kit.py (generalised from the source site's tools/report.py palette()).
--method oklch (default) OKLCH lightness walk keeping hue and chroma -- identical to EVK.tones in assets/engine/tones.js.
   The text shade walks toward the ink end: darker on a light paper, LIGHTER on a dark-ground card (--paper darker than --ink),
   so a dark card keeps the hue of every entity colour; the ink colour is the fallback only if L = 0.98 still misses the target.
--method mix   the source site's maths: text = mix toward ink 1 % at a time; dark = HLS lighten, saturation cap .62
Defaults for paper/ink/night are the source site's values (#F7F5F0, #14171D, #0D1D36 -- 原站取值), good for the source's own light
paper ONLY: the text shades of a card with another paper, above all a dark-ground card, come out wrong from them. So pass the card
(--roll .evk/roll.json: its paper, text and night) or your own --paper/--ink/--night; with the defaults a hint says so on stderr.
Exit code: 0 ok; 1 when a role misses its contrast target (only with --strict); 2 usage / input error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit  # noqa: E402
import draw  # noqa: E402


def role_checks(hex_color, t, paper, ink, night, target):
    """[(label, value, ratio, need, ok)] for one entity -- the F04/F05 checks."""
    rows = [
        ("e-text on paper", t["eText"], kit.contrast(t["eText"], paper), target),
        ("e-on on e (fill)", t["eOn"], kit.contrast(t["eOn"], t["e"]), 4.5),
        ("e-dk on night", t["eDk"], kit.contrast(t["eDk"], night), target),
        ("night on e-dk (dark fill)", night, kit.contrast(night, t["eDk"]), target),
    ]
    return [(lab, val, ratio, need, ratio + 1e-9 >= need) for lab, val, ratio, need in rows]


def format_one(name, c, t, paper, ink, night, target, method):
    lines = ["%s  %s   paper %s  ink %s  night %s  target %s  method %s" % (name, c, paper, ink, night, target, method)]
    names = [("e", "--e"), ("eText", "--e-text"), ("eOn", "--e-on"), ("eSoft", "--e-soft"), ("eLine", "--e-line"),
             ("eDk", "--e-dk"), ("eSoftDk", "--e-soft-dk")]
    for k, css in names:
        lines.append("  %-14s %s" % (css, t[k]))
    lines.append("  checks:")
    for lab, val, ratio, need, ok in role_checks(c, t, paper, ink, night, target):
        lines.append("    %-28s %s  %5.2f:1  (>= %.1f)  %s" % (lab, val, ratio, need, "ok" if ok else "LOW"))
    fill_night = kit.contrast(t["e"], night)
    lines.append("    %-28s %s  %5.2f:1  %s" % ("fill e on night (identity)", t["e"], fill_night,
                                                "ok" if fill_night >= 3 else "< 3:1: add an edge/ring in dark mode (floor F05)"))
    return "\n".join(lines)


def load_batch(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    if isinstance(data, dict) and isinstance(data.get("entities"), list):
        data = data["entities"]
    if isinstance(data, dict):
        out = [(str(k), v) for k, v in data.items()]
    elif isinstance(data, list):
        for i, it in enumerate(data):
            if isinstance(it, str):
                out.append((it, it))
            elif isinstance(it, dict):
                c = it.get("color") or it.get("colour") or it.get("hex")
                if not c:
                    raise ValueError("batch item %d has no color/hex: %r" % (i, it))
                out.append((str(it.get("id") or it.get("name") or c), c))
            else:
                raise ValueError("batch item %d: expected hex or object" % i)
    else:
        raise ValueError("batch file: expected a list or an object")
    return [(n, kit.norm_hex(c)) for n, c in out]


def roll_card(path, card):
    """(card dict, 1-based index, chosen?) of a roll: card N, else the chosen card, else card 1."""
    roll = json.loads(Path(path).read_text(encoding="utf-8"))
    cards = roll.get("cards") or []
    if not cards:
        raise ValueError("%s has no cards" % path)
    if card:
        if not 1 <= card <= len(cards):
            raise ValueError("card %d not in %s" % (card, path))
        return cards[card - 1], card, True
    ch = draw.pick_chosen_card(roll)           # a number, a digit string, a code or a dict: whatever draw.py wrote
    if ch is not None:
        return ch, cards.index(ch) + 1, True
    return cards[0], 1, False


def palette_from_roll(path, card):
    """(paper, ink, night) of a rolled card: its light paper, its text colour, its dark ground. On a dark-ground direction the
    light scheme IS the dark ground, so paper is dark and ink is light -- exactly what the shade walk needs."""
    c, _, _ = roll_card(path, card)
    lt, dk = c["params"]["palette"]["light"], c["params"]["palette"]["dark"]
    return lt["paper"], lt["text"], dk["paper"]


def contrast_possible(c, paper):
    """True when a lighter shade of c (same hue, L up to 0.98) can reach 4.6:1 on this paper -- then ink is not a fair fallback."""
    L, C, h = kit.hex_to_oklch(c)
    return kit.contrast(kit._from_oklch_spec(0.98, C, h), paper) >= 4.6


def _selftest():
    fails = []

    def ok(cond, msg):
        if not cond:
            fails.append(msg)
            print("  FAIL", msg)

    for hx, exp in kit.TONES_TABLE_EXPECTED.items():
        ok(kit.tones(hx, method="mix") == exp, "table row %s" % hx)
    for hx, opts, exp in kit.TONES_OKLCH_EXPECTED:
        ok([kit.tones(hx, method="oklch", **opts)[k] for k in kit.TONES_KEYS] == exp, "oklch row %s" % hx)
    txt = format_one("x", "#8C1515", kit.tones("#8C1515"), kit.SOURCE_PAPER, kit.SOURCE_INK, kit.SOURCE_NIGHT, 4.6, "mix")
    ok("--e-text" in txt and "checks" in txt, "format_one")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "b.json"
        p.write_text(json.dumps([{"id": "a", "color": "#8c1515"}, {"id": "b", "color": "#09a7c8"}]))
        ok(load_batch(p) == [("a", "#8C1515"), ("b", "#09A7C8")], "batch list of objects")
        p.write_text(json.dumps({"entities": [{"id": "z", "color": "#fff"}]}))
        ok(load_batch(p) == [("z", "#FFFFFF")], "batch venue.json shape")
        p.write_text(json.dumps({"k": "#123456"}))
        ok(load_batch(p) == [("k", "#123456")], "batch mapping")
        # roll-derived palette
        import random
        lib = kit.load_directions(fixture=True)
        pr = kit.sample(lib["directions"][1], random.Random(3))
        rp = Path(td) / "roll.json"
        rp.write_text(json.dumps({"cards": [{"params": pr}], "chosen": None}))
        pa, ik, ni = palette_from_roll(rp, 1)
        ok(pa == pr["palette"]["light"]["paper"] and ni == pr["palette"]["dark"]["paper"], "palette_from_roll")
    # custom palette: every entity colour must reach the targets
    bad = 0
    import random as _r
    r = _r.Random(5)
    for _ in range(400):
        c = "#%02X%02X%02X" % (r.randrange(256), r.randrange(256), r.randrange(256))
        for meth in ("mix", "oklch"):
            t = kit.tones(c, method=meth)
            if kit.contrast(t["eText"], kit.SOURCE_PAPER) < 4.6 - 1e-9 and t["eText"] != kit.SOURCE_INK:
                bad += 1
            if kit.contrast(t["eOn"], t["e"]) < 4.5:
                bad += 1
    ok(bad == 0, "400 random colours x 2 methods meet the text/on targets (%d misses)" % bad)
    # a dark-ground card (paper darker than ink): the text shade reads on the paper AND keeps the hue
    dk = ("#14202E", "#EEEAE1", "#0B1220")
    bad = lost = 0
    for _ in range(400):
        c = "#%02X%02X%02X" % (r.randrange(256), r.randrange(256), r.randrange(256))
        t = kit.tones(c, *dk)
        if kit.contrast(t["eText"], dk[0]) < 4.6 - 1e-9 and t["eText"] != dk[1]:
            bad += 1
        if kit.contrast(t["eOn"], t["e"]) < 4.5:
            bad += 1
        lc, cc, hc = kit.hex_to_oklch(c)
        lt_, ct_, ht_ = kit.hex_to_oklch(t["eText"])
        if t["eText"] == dk[1] and cc > 0.06 and contrast_possible(c, dk[0]):
            lost += 1
    ok(bad == 0, "400 random colours on a dark-ground card meet the text/on targets (%d misses)" % bad)
    ok(lost == 0, "…and none collapses to the ink colour when a lighter shade of its hue would read (%d did)" % lost)
    # --- FIX-SPEC-3 B: the card's own paper/text/night with --roll; a hint when the source site's defaults are used
    import contextlib
    import io
    import random as _rr
    lib = kit.load_directions(fixture=True)
    dark_dir = next(d for d in lib["directions"] if d["id"] == "scoreboard")        # a dark-ground direction
    dcard = kit.sample(dark_dir, _rr.Random(5))
    roll = {"cards": [{"direction": "airmail", "params": kit.sample(lib["directions"][1], _rr.Random(5))}, {"direction": "scoreboard", "params": dcard}], "chosen": "2"}
    with tempfile.TemporaryDirectory() as td:
        rp = Path(td) / "roll.json"
        rp.write_text(json.dumps(roll), encoding="utf-8")

        def run_main(*argv):
            o, e = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
                rc = main(list(argv))
            return rc, o.getvalue(), e.getvalue()

        rc, out, err = run_main("#8C1515", "--json")
        wrong = json.loads(out)
        ok(rc == 0 and "hint: using the source site's" in err and "--roll" in err and "paper #F7F5F0" in err, "no palette given: a hint on stderr names the source-site defaults and --roll")
        ok(out.lstrip().startswith("{") and "hint" not in out, "…and stdout stays clean (CSS / JSON)")
        rc, out, err = run_main("#8C1515", "--roll", str(rp), "--json")
        right = json.loads(out)
        ok(rc == 0 and "hint" not in err, "--roll: no hint")
        dpaper = dcard["palette"]["light"]["paper"]
        ok(kit.contrast(right["eText"], dpaper) >= 4.6 - 1e-9 and kit.contrast(wrong["eText"], dpaper) < 4.6,
           "--roll uses the CHOSEN card's paper/text/night (a digit-string `chosen` works): on a dark-ground card the defaults give a text shade that does not read (%.2f), the card's give %.2f" % (
               kit.contrast(wrong["eText"], dpaper), kit.contrast(right["eText"], dpaper)))
        rc, out, err = run_main("#8C1515", "--roll", str(rp), "--card", "1", "--json")
        ok(json.loads(out)["eText"] != right["eText"], "--card N picks another card")
        roll["chosen"] = None
        rp.write_text(json.dumps(roll), encoding="utf-8")
        rc, out, err = run_main("#8C1515", "--roll", str(rp), "--json")
        ok(rc == 0 and "no card is chosen" in err and "using card 1" in err, "no chosen card: says which one it used")
        rc, out, err = run_main("#8C1515", "--paper", "#101820", "--ink", "#EEEEEE", "--night", "#080C10", "--json")
        ok(rc == 0 and "hint" not in err, "all three given: no hint")
        rc, out, err = run_main("#8C1515", "--paper", "#101820", "--json")
        ok("ink #14171D" in err and "night #0D1D36" in err and "paper #" not in err.split("source site's")[1].split("(")[0], "only --paper given: the hint names what is still a default (ink, night)")
    if fails:
        print("tones.py selftest: %d FAILED" % len(fails))
        return 1
    print("tones.py selftest: ok")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tones.py", description=__doc__.split("Roles (CSS")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("color", nargs="?", help="entity colour, #RRGGBB")
    ap.add_argument("--paper", help="paper hex (default: roll's, else %s)" % kit.SOURCE_PAPER)
    ap.add_argument("--ink", help="ink / text hex (default: roll's, else %s)" % kit.SOURCE_INK)
    ap.add_argument("--night", help="dark ground hex (default: roll's, else %s)" % kit.SOURCE_NIGHT)
    ap.add_argument("--target", type=float, default=kit.TONES_TARGET, help="contrast target for text roles (default 4.6)")
    ap.add_argument("--method", choices=["mix", "oklch"], default="oklch", help="oklch = lightness walk, same as EVK.tones (default); mix = the source site's algorithm")
    ap.add_argument("--css", action="store_true", help="print CSS custom property declarations")
    ap.add_argument("--json", action="store_true", help="print JSON")
    ap.add_argument("--batch", metavar="FILE", help="many entities: list of hex | {id: hex} | [{id,color}] | venue.json")
    ap.add_argument("--roll", metavar="roll.json", help="take paper/ink/night from a rolled card (the chosen one, or --card N)")
    ap.add_argument("--card", type=int, help="with --roll: card number (1-based)")
    ap.add_argument("--table", action="store_true", help="print the fixed 6-row comparison table and exit")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any role misses its target")
    ap.add_argument("--selftest", action="store_true", help="run built-in tests")
    a = ap.parse_args(argv)

    if a.selftest:
        return _selftest()
    if a.table:
        print(kit.format_tones_table(method=a.method))
        return 0
    paper, ink, night = kit.SOURCE_PAPER, kit.SOURCE_INK, kit.SOURCE_NIGHT
    source = {"paper": True, "ink": True, "night": True}          # which of the three are still the source site's values
    try:
        if a.roll:
            paper, ink, night = palette_from_roll(a.roll, a.card)
            source = {k: False for k in source}
            c_, n_, chosen_ = roll_card(a.roll, a.card)
            if not chosen_:
                print("tones.py: note: no card is chosen in %s: using card 1 (%s); pass --card N or choose one first" % (a.roll, c_.get("direction")), file=sys.stderr)
        for key, val in (("paper", a.paper), ("ink", a.ink), ("night", a.night)):
            if val:
                source[key] = False
        paper = kit.norm_hex(a.paper) if a.paper else paper
        ink = kit.norm_hex(a.ink) if a.ink else ink
        night = kit.norm_hex(a.night) if a.night else night
        if a.batch:
            items = load_batch(a.batch)
        elif a.color:
            items = [(a.color, kit.norm_hex(a.color))]
        else:
            ap.print_help()
            return 2
    except (ValueError, OSError) as e:
        print("tones.py: %s" % e, file=sys.stderr)
        return 2
    if any(source.values()):
        used = ", ".join("%s %s" % (k, v) for k, v in (("paper", paper), ("ink", ink), ("night", night)) if source[k])
        here = " (found .evk/roll.json here: add --roll .evk/roll.json)" if Path(".evk/roll.json").exists() else ""
        print("tones.py: hint: using the source site's %s (原站取值). A card with another paper -- above all a dark-ground card -- gets "
              "wrong text shades from them; pass the card's own with --roll .evk/roll.json, or --paper/--ink/--night%s" % (used, here), file=sys.stderr)
    results = [(n, c, kit.tones(c, paper, ink, night, a.target, a.method)) for n, c in items]
    low = 0
    for n, c, t in results:
        low += sum(1 for r in role_checks(c, t, paper, ink, night, a.target) if not r[4])
    if a.json:
        print(json.dumps({n: dict(t, input=c) for n, c, t in results} if a.batch else dict(results[0][2], input=results[0][1]),
                         indent=1, ensure_ascii=False))
    elif a.css:
        if a.batch:
            for n, c, t in results:
                print('[data-entity="%s"]{%s}' % (n, kit.tones_css(t)))
        else:
            print(kit.tones_css(results[0][2]))
    elif a.batch:
        print("%-16s %-8s %-8s %-8s %-8s %-8s %-8s %-8s %-8s %s" % ("id", "input", "e", "eText", "eOn", "eSoft", "eLine", "eDk", "eSoftDk", "notes"))
        for n, c, t in results:
            notes = []
            if kit.contrast(t["e"], night) < 3:
                notes.append("dark: fill<3:1 on night (add ring)")
            if t["e"] != c:
                notes.append("fill protected")
            print("%-16s %-8s %-8s %-8s %-8s %-8s %-8s %-8s %-8s %s" % ((n[:16], c) + tuple(t[k] for k in kit.TONES_KEYS) + ("; ".join(notes),)))
    else:
        n, c, t = results[0]
        print(format_one(n, c, t, paper, ink, night, a.target, a.method))
    if a.strict and low:
        print("tones.py: %d role check(s) below target" % low, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
