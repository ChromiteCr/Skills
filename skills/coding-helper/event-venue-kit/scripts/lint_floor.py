#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""event-venue-kit :: lint_floor.py -- the machine-checkable part of the quality floor (references/floor.md, [lint] marks).

    lint_floor.py <tokens.css | roll.json | page.html | project-dir> [--card N] [--strict] [--json] [--quiet]

What it checks / 检查项
  tokens   all required tokens exist in :root (colours, map materials + keywords, fonts, type, shape, motion, density);
           the dark block is declared twice (@media (prefers-color-scheme: dark) :root:not([data-theme="light"]) and
           :root[data-theme="dark"]), identical, and re-declares every colour role
  colour   BUILD-SPEC 2.1 in light AND dark: rule/paper >= 1.25, text/paper >= 7, sub >= 4.5 on paper and paper-2,
           a-text / b-text >= 4.5 on paper, heading >= body (heading/body: --a-text, the colour of h1-h4 and entity names, fails
           under 4.5:1 on paper and warns when it carries less than 80 % of --text's own contrast; the generator keeps it within
           0.5 of --text, or equal to --text), on-a / on-b >= 4.5 on their fills, focus >= 3, climb >= 3 on --m-slab,
           climb hue >= 50 degrees from --b, climb-text >= 4.5 on paper AND paper-2 and within 10 degrees of the climb hue
           (anything that is TEXT uses --climb-text; --climb stays a graphic colour), m-select (the selection EDGE) >= 3 on
           --m-slab, m-cap (the ink line of the map: wall caps, rings, pins, icons) >= 4.5 on --m-slab or it fails.
           --m-select-fill (the selection tint) has no floor.   warnings: m-cap under 7:1 and m-wall under 3:1 on --m-slab
           (map-craft 5.7; the generator walks both there), map text/route legibility, text on paper-2, a vs paper
  fonts    every --f-* stack carries a CJK family (Songti/Noto Serif SC/SimSun or PingFang/Hiragino/Noto Sans SC/YaHei)
  css      (files next to the tokens, the page's own CSS, or assets/floor/base.css + the recipe for a roll)
           prefers-reduced-motion block that switches transitions/animations off, a :focus-visible style,
           no outline:none/0 without a replacement; warnings: :hover outside (hover:hover), color-scheme
  html     <html lang> present (page.html only)
Inputs: tokens.css (checked with base.css / recipe.css beside it if they exist); roll.json (each card -> tokens_css(params),
plus assets/floor/base.css and assets/recipes/<direction>.css if present); page.html (its <style> blocks and local stylesheets);
a directory (evk/tokens.css or tokens.css inside it).
Exit code: 0 = every floor check passed (warnings allowed); 1 = a floor check failed (--strict: warnings fail too); 2 = bad input.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit  # noqa: E402

LEVELS = ("pass", "info", "warn", "fail")


class Report(object):
    def __init__(self, title):
        self.title = title
        self.items = []

    def add(self, level, cid, msg, rule=None, scheme=None):
        self.items.append({"level": level, "id": cid, "msg": msg, "rule": rule, "scheme": scheme})

    @property
    def failed(self):
        return [i for i in self.items if i["level"] == "fail"]

    @property
    def warned(self):
        return [i for i in self.items if i["level"] == "warn"]

    @property
    def ok(self):
        return not self.failed


# --------------------------------------------------------------------------------------------------
# a small CSS reader (rules, nested at-rules, declarations) -- enough for token files and base.css
# --------------------------------------------------------------------------------------------------

_STR_RE = re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'')
_URL_RE = re.compile(r"url\([^)]*\)", re.I)
_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
DECL_AT = ("@font-face", "@page", "@property", "@counter-style", "@viewport")


def _protect(text):
    store = []

    def sub(m):
        store.append(m.group(0))
        return "\x00%d\x00" % (len(store) - 1)

    text = _COMMENT_RE.sub(" ", text)
    text = _STR_RE.sub(sub, text)
    text = _URL_RE.sub(sub, text)
    return text, store


def _restore(s, store):
    return re.sub(r"\x00(\d+)\x00", lambda m: store[int(m.group(1))], s)


def parse_css(text):
    """-> [{'ctx': (at-rule preludes...), 'sel': str, 'decls': [(name, value), ...]}]"""
    text, store = _protect(text)
    n = len(text)
    rules = []

    def parse_decls(body):
        out = []
        for part in body.split(";"):
            if ":" not in part:
                continue
            k, v = part.split(":", 1)
            k = k.strip().lower()
            v = re.sub(r"\s+", " ", _restore(v, store).strip())
            if k:
                out.append((k, v))
        return out

    def block(i, ctx):
        while i < n:
            while i < n and text[i] in " \t\r\n":
                i += 1
            if i >= n:
                break
            if text[i] == "}":
                return i + 1
            ob = text.find("{", i)
            sc = text.find(";", i)
            if ob == -1 and sc == -1:
                break
            if sc != -1 and (ob == -1 or sc < ob):   # statement at-rule (@import ...;)
                i = sc + 1
                continue
            prelude = re.sub(r"\s+", " ", _restore(text[i:ob], store).strip())
            if prelude.startswith("@") and not prelude.lower().startswith(DECL_AT):
                i = block(ob + 1, ctx + (prelude,))
                continue
            depth, j = 1, ob + 1
            while j < n and depth:
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                j += 1
            body = text[ob + 1:j - 1]
            rules.append({"ctx": ctx, "sel": prelude, "decls": parse_decls(body)})
            i = j
        return i

    block(0, ())
    return rules


def _norm_sel(s):
    return re.sub(r"\s+", "", s.replace("'", '"')).lower()


def _in_dark_media(ctx):
    return any("prefers-color-scheme" in c.lower() and "dark" in c.lower() for c in ctx)


def collect_tokens(rules):
    """-> dict(light={}, dark_media={}, dark_attr={}, root_decls_all={})  names without '--'."""
    light, dmedia, dattr, others = {}, {}, {}, {}
    for r in rules:
        sels = [_norm_sel(s) for s in r["sel"].split(",")]
        decls = {k[2:]: v for k, v in r["decls"] if k.startswith("--")}
        if not decls:
            continue
        if _in_dark_media(r["ctx"]):
            if any(s in (':root:not([data-theme="light"])', 'html:not([data-theme="light"])') for s in sels):
                dmedia.update(decls)
            continue
        if r["ctx"]:
            continue
        if any(s in (":root", "html", ":root,html") for s in sels):
            light.update(decls)
        elif any(s in (':root[data-theme="dark"]', 'html[data-theme="dark"]') for s in sels):
            dattr.update(decls)
        else:
            others.update(decls)
    return {"light": light, "dark_media": dmedia, "dark_attr": dattr, "others": others}


def resolve(scope, name, depth=0):
    """Resolve var() chains inside one token scope; returns the final text or None."""
    v = scope.get(name)
    if v is None or depth > 8:
        return None
    m = re.fullmatch(r"var\(\s*--([\w-]+)\s*(?:,\s*(.+))?\)", v.strip())
    if m:
        r = resolve(scope, m.group(1), depth + 1)
        return r if r is not None else (m.group(2) if m.group(2) else None)
    return v


def color_of(scope, name):
    v = resolve(scope, name)
    if v is None:
        return None
    try:
        return kit.parse_color(v.replace("!important", "").strip())
    except ValueError:
        return None


# --------------------------------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------------------------------

def check_tokens(rep, rules):
    t = collect_tokens(rules)
    light = t["light"]
    if not light:
        rep.add("fail", "tokens", "no :root custom properties found (is this the tokens file?)", "BUILD-SPEC 2")
        return None
    missing = [n for n in kit.REQUIRED_TOKENS if n not in light]
    if missing:
        newer = [m for m in missing if m in ("climb-text", "m-select-fill")]
        hint = ("  (--climb-text and --m-select-fill came with the round-2 token contract: regenerate tokens.css from the roll with install.py)"
                if newer else "")
        rep.add("fail", "tokens-present", "missing %d required token(s) in :root: %s%s" % (len(missing), ", ".join("--" + m for m in missing[:12]) + (" ..." if len(missing) > 12 else ""), hint), "BUILD-SPEC 2")
    else:
        rep.add("pass", "tokens-present", "all %d required tokens present in :root" % len(kit.REQUIRED_TOKENS))
    dm, da = t["dark_media"], t["dark_attr"]
    if not dm:
        rep.add("fail", "dark-media", "no @media (prefers-color-scheme: dark){:root:not([data-theme=\"light\"]){...}} block", "F06")
    if not da:
        rep.add("fail", "dark-attr", "no :root[data-theme=\"dark\"]{...} block", "F06")
    if dm and da:
        diff = [k for k in kit.ALL_COLOR_TOKENS if dm.get(k) != da.get(k)]
        if diff:
            rep.add("fail", "dark-twice", "the two dark blocks differ on: %s" % ", ".join("--" + d for d in diff[:8]), "F06")
        else:
            rep.add("pass", "dark-twice", "dark block declared twice and identical on the colour roles")
    dark = dict(light)
    dark.update(dm if dm else da)
    dscope = da if (da and not dm) else dm
    if dm or da:
        miss = [n for n in kit.COLOR_TOKENS if n not in dscope]
        if miss:
            rep.add("fail", "dark-roles", "dark block does not re-declare: %s (same names in light and dark)" % ", ".join("--" + m for m in miss), "F06")
        else:
            rep.add("pass", "dark-roles", "dark block re-declares all colour roles")
        missm = [n for n in kit.MAP_COLOR_TOKENS if n not in dscope]
        if missm:
            rep.add("warn", "dark-map", "dark block keeps the light value for: %s" % ", ".join("--" + m for m in missm[:6]), "BUILD-SPEC 2.2")
    return {"light": light, "dark": dark}


def check_colours(rep, scopes):
    for sname in ("light", "dark"):
        scope = scopes[sname]
        label = sname
        if sname == "light" and color_of(scope, "paper") and kit._lum_dark(color_of(scope, "paper")):
            label = "root*"      # a dark-ground direction: :root itself is the dark ground
        toks = {}
        unparse = []
        for n in kit.ALL_COLOR_TOKENS:
            if n in scope:
                c = color_of(scope, n)
                if c is None:
                    unparse.append(n)
                else:
                    toks[n] = c
        if unparse:
            rep.add("warn", "colour-parse", "cannot read as a plain colour (checks skipped): %s" % ", ".join("--" + u for u in unparse), None, label)
        for c in kit.check_scheme(toks):
            if c.get("unit") == "deg":
                msg = "%s %.0f deg (%s %d)" % (c["id"], c["ratio"], "<=" if c.get("max") else ">=", c["min"])
            elif c["ratio"] is None:
                msg = "%s %s" % (c["id"], c.get("note", ""))
            elif "body" in c:      # heading/body: the heading's contrast against the body text's own
                msg = "%s %.2f:1 vs body %.2f:1 (fail < 4.5, warn < %.2f = 0.8 x body)  a-text %s, text %s on paper %s" % (
                    c["id"], c["ratio"], c["body"], c["body"] * kit.HEADING_WARN_RATIO, toks["a-text"], toks["text"], toks["paper"])
            else:
                msg = "%s %.2f:1 (>= %s)  %s on %s" % (c["id"], c["ratio"], ("%g" % c["min"]), toks[c["fg"]], toks[c["bg"]])
            level = "pass" if c["ok"] else ("fail" if c["level"] == "floor" else "warn")
            rep.add(level, c["id"], msg, c["rule"], label)


def check_fonts(rep, light):
    for n in kit.FONT_TOKENS:
        v = light.get(n)
        if v is None:
            continue
        if kit.stack_has_cjk(v):
            rep.add("pass", "cjk-" + n, "--%s has a CJK family" % n, "F09")
        else:
            rep.add("fail", "cjk-" + n, "--%s has no CJK system family: %s" % (n, v[:80]), "F09")


def check_css(rep, rules, css_text, label):
    """Structural checks over a body of CSS (base.css + recipe, or a page's styles)."""
    low = css_text.lower()
    # reduced motion
    rm = [r for r in rules if any("prefers-reduced-motion" in c.lower() and "reduce" in c.lower() for c in r["ctx"])]
    if not rm:
        rep.add("fail", "reduced-motion", "%s: no @media (prefers-reduced-motion: reduce) block" % label, "F14")
    else:
        names = {k for r in rm for k, _ in r["decls"]}
        if names & {"transition", "transition-duration", "animation", "animation-duration", "animation-name", "scroll-behavior"}:
            rep.add("pass", "reduced-motion", "%s: prefers-reduced-motion block switches transitions/animations off" % label, "F14")
        else:
            rep.add("fail", "reduced-motion", "%s: the reduced-motion block does not touch transition/animation/scroll-behavior" % label, "F14")
    # focus style
    fv = [r for r in rules if ":focus-visible" in r["sel"] and any(k in ("outline", "outline-color", "outline-width", "box-shadow") and not v.startswith("none") and v != "0" for k, v in r["decls"])]
    if fv:
        rep.add("pass", "focus-visible", "%s: :focus-visible style present (%d rule(s))" % (label, len(fv)), "F13")
    else:
        rep.add("fail", "focus-visible", "%s: no :focus-visible rule with an outline or box-shadow" % label, "F13")
    # outline:none without replacement
    bad = []
    for r in rules:
        for k, v in r["decls"]:
            vv = v.replace("!important", "").strip().lower()
            if (k == "outline" and vv in ("none", "0", "0px", "0 none")) or (k == "outline-style" and vv == "none") or (k == "outline-width" and vv in ("0", "0px")):
                sel = r["sel"]
                if ":not(:focus-visible)" in sel.replace(" ", "") or "sr-only" in sel or '[tabindex="-1"]' in sel.replace("'", '"'):
                    continue
                has_repl = any(kk == "box-shadow" and not vk.startswith("none") for kk, vk in r["decls"])
                if not has_repl and fv:
                    base = re.sub(r":focus(-visible|-within)?", "", sel).strip()
                    has_repl = any(base and base in f["sel"] and ":focus-visible" in f["sel"] for f in fv)
                if not has_repl:
                    bad.append(sel[:50])
    if bad:
        rep.add("fail", "outline-none", "%s: outline removed without a replacement on: %s" % (label, "; ".join(bad[:4])), "F13")
    else:
        rep.add("pass", "outline-none", "%s: no outline:none without a replacement" % label, "F13")
    # hover gating (warning)
    ungated = [r for r in rules if ":hover" in r["sel"] and not any("hover: hover" in c.lower().replace("(hover:hover)", "hover: hover") or "hover:hover" in c.lower().replace(" ", "") for c in r["ctx"])]
    if ungated:
        rep.add("warn", "hover-gate", "%s: %d :hover rule(s) outside @media (hover:hover), e.g. %s" % (label, len(ungated), ungated[0]["sel"][:40]), "F12")
    elif ":hover" in low:
        rep.add("pass", "hover-gate", "%s: all :hover rules are inside @media (hover:hover)" % label, "F12")
    if "color-scheme" not in low:
        rep.add("warn", "color-scheme", "%s: no color-scheme declared (form controls and scrollbars will not follow dark mode)" % label, "F06")


def check_html(rep, html_text):
    m = re.search(r"<html[^>]*>", html_text, re.I)
    if not m:
        rep.add("warn", "html-lang", "no <html> tag found", "F09")
        return
    lm = re.search(r'\blang\s*=\s*["\']([^"\']+)["\']', m.group(0), re.I)
    if lm:
        rep.add("pass", "html-lang", '<html lang="%s">' % lm.group(1), "F09")
    else:
        rep.add("fail", "html-lang", "<html> has no lang attribute", "F09")


# --------------------------------------------------------------------------------------------------
# drivers
# --------------------------------------------------------------------------------------------------

def lint_tokens_text(css_text, title="tokens", with_css=None):
    """Lint a tokens.css text. with_css: optional [(label, css_text)] of companion CSS for the structural checks."""
    rep = Report(title)
    rules = parse_css(css_text)
    scopes = check_tokens(rep, rules)
    if scopes:
        check_colours(rep, scopes)
        check_fonts(rep, scopes["light"])
    if with_css:
        # the structural rules hold for the stylesheets together (reduced motion lives in base.css, not in every recipe)
        label = " + ".join(lab for lab, _ in with_css)
        text = "\n".join(t for _, t in with_css) + "\n" + css_text
        check_css(rep, parse_css(text), text, label)
    else:
        rep.add("info", "css-structure", "no base.css / recipe next to the tokens: reduced-motion, focus and outline checks skipped", "F13/F14")
    return rep


def lint_params(params, with_css=None):
    return lint_tokens_text(kit.tokens_css(params), "card " + str(params.get("direction")), with_css)


def _read(p):
    return Path(p).read_text(encoding="utf-8")


def companions_for_direction(did):
    out = []
    base = kit.ASSETS_DIR / "floor" / "base.css"
    rec = kit.ASSETS_DIR / "recipes" / ("%s.css" % did)
    for lab, p in (("assets/floor/base.css", base), ("assets/recipes/%s.css" % did, rec)):
        if p.exists():
            out.append((lab, _read(p)))
    return out


def lint_roll(path, card=None):
    roll = json.loads(_read(path))
    cards = roll.get("cards") or []
    if not cards:
        raise ValueError("%s has no cards" % path)
    if card:
        if not 1 <= card <= len(cards):
            raise ValueError("card %s is not in %s (1-%d)" % (card, path, len(cards)))
        idx = [card]
    else:
        ch = roll.get("chosen")
        idx = [int(ch)] if isinstance(ch, int) and 1 <= ch <= len(cards) else list(range(1, len(cards) + 1))
    reps = []
    for i in idx:
        c = cards[i - 1]
        comp = companions_for_direction(c["direction"])
        rep = lint_params(c["params"], comp or None)
        rep.title = "%s  card %d/%d  %s  %s" % (path, i, len(cards), c["direction"], c.get("code", ""))
        reps.append(rep)
    return reps


def lint_css_file(path):
    p = Path(path)
    comp = []
    for name in ("base.css", "recipe.css"):
        q = p.parent / name
        if q.exists() and q != p:
            comp.append((name, _read(q)))
    rep = lint_tokens_text(_read(p), str(p), comp or None)
    return [rep]


def lint_html(path):
    p = Path(path)
    html = _read(p)
    css_parts = [m.group(1) for m in re.finditer(r"<style[^>]*>(.*?)</style>", html, re.S | re.I)]
    for m in re.finditer(r"<link[^>]+>", html, re.I):
        tag = m.group(0)
        if re.search(r'rel\s*=\s*["\']stylesheet["\']', tag, re.I):
            hm = re.search(r'href\s*=\s*["\']([^"\']+)["\']', tag, re.I)
            if hm and not re.match(r"^(https?:)?//", hm.group(1)):
                q = (p.parent / hm.group(1).split("?")[0]).resolve()
                if q.exists():
                    css_parts.append(_read(q))
    css = "\n".join(css_parts)
    rep = Report(str(p))
    check_html(rep, html)
    if not css.strip():
        rep.add("fail", "css", "no inline <style> and no local stylesheet found", None)
        return [rep]
    rules = parse_css(css)
    scopes = check_tokens(rep, rules)
    if scopes:
        check_colours(rep, scopes)
        check_fonts(rep, scopes["light"])
    check_css(rep, rules, css, "page CSS")
    return [rep]


def lint_path(path, card=None):
    p = Path(path)
    if p.is_dir():
        for cand in (p / "evk" / "tokens.css", p / "tokens.css", p / "roll.json", p / ".evk" / "roll.json"):
            if cand.exists():
                return lint_path(cand, card)
        raise ValueError("no evk/tokens.css, tokens.css or roll.json in %s" % p)
    if not p.exists():
        raise FileNotFoundError("not found: %s" % p)
    ext = p.suffix.lower()
    if ext == ".json":
        return lint_roll(p, card)
    if ext in (".html", ".htm"):
        return lint_html(p)
    if ext == ".css":
        return lint_css_file(p)
    head = _read(p)[:200].lstrip()
    if head.startswith("{"):
        return lint_roll(p, card)
    if head.lower().startswith("<"):
        return lint_html(p)
    return lint_css_file(p)


def format_reports(reps, quiet=False):
    lines = []
    tot_f = tot_w = 0
    for rep in reps:
        lines.append("lint_floor: %s" % rep.title)
        for it in rep.items:
            if quiet and it["level"] in ("pass", "info"):
                continue
            tag = {"pass": "pass", "info": "info", "warn": "WARN", "fail": "FAIL"}[it["level"]]
            lines.append("  [%s] %s%s%s" % (tag, ("%-5s " % it["scheme"]) if it["scheme"] else "", it["msg"], ("   (%s)" % it["rule"]) if it["rule"] and it["level"] in ("fail", "warn") else ""))
        f, w = len(rep.failed), len(rep.warned)
        tot_f += f
        tot_w += w
        lines.append("  => %s  (%d failed, %d warnings, %d passed)" % ("OK" if not f else "FAILED", f, w, sum(1 for i in rep.items if i["level"] == "pass")))
    if len(reps) > 1:
        lines.append("total: %d failed, %d warnings over %d reports" % (tot_f, tot_w, len(reps)))
    return "\n".join(lines)


# --------------------------------------------------------------------------------------------------
# self-test
# --------------------------------------------------------------------------------------------------

def _selftest():
    import random
    fails = []

    def ok(cond, msg):
        if not cond:
            fails.append(msg)
            print("  FAIL", msg)

    lib = kit.load_directions(fixture=True)
    for d in lib["directions"]:
        p = kit.sample(d, random.Random(21))
        rep = lint_params(p)
        ok(rep.ok, "fixture card %s passes lint: %s" % (d["id"], [i["msg"] for i in rep.failed]))
        ok(sum(1 for i in rep.items if i["level"] == "pass" and i["scheme"] == "dark") >= 8, "%s: dark checks ran" % d["id"])
    p = kit.sample(lib["directions"][1], random.Random(2))
    css = kit.tokens_css(p)
    # mutate: kill text contrast in dark only
    pal_dark_text = p["palette"]["dark"]["text"]
    bad_css = css.replace(pal_dark_text, p["palette"]["dark"]["paper-2"])
    rep = lint_tokens_text(bad_css)
    ok(not rep.ok and any(i["id"] == "text/paper" and i["scheme"] == "dark" for i in rep.failed), "low dark text contrast is caught")
    rep = lint_tokens_text(css.replace("--f-text:", "--f-text-old:"))
    ok(not rep.ok, "missing token is caught")
    # remove the data-theme dark block
    cut = css[:css.index(':root[data-theme="dark"]{')]
    rep = lint_tokens_text(cut)
    ok(any(i["id"] == "dark-attr" for i in rep.failed), "missing [data-theme=dark] block is caught")
    # no CJK
    nocjk = re.sub(r"--f-display: [^;]+;", "--f-display: Georgia, serif;", css)
    rep = lint_tokens_text(nocjk)
    ok(any(i["id"] == "cjk-f-display" for i in rep.failed), "missing CJK fallback is caught")
    # heading >= body (FIX-SPEC-5 #1): a heading colour dimmer than the body text warns, one under 4.5:1 fails
    lt0 = p["palette"]["light"]
    rep = lint_tokens_text(css)
    ok(any(i["id"] == "heading/body" and i["level"] == "pass" for i in rep.items), "generated heading colour passes heading/body")
    dim = css.replace("--a-text: " + lt0["a-text"], "--a-text: " + lt0["sub"], 1)
    rep = lint_tokens_text(dim)
    ok(rep.ok and any(i["id"] == "heading/body" and i["level"] == "warn" and i["scheme"] == "light" for i in rep.items),
       "a heading dimmer than 80 %% of the body contrast warns (passes the floor): %s" % [(i["id"], i["level"]) for i in rep.items if i["id"] == "heading/body"])
    faint = css.replace("--a-text: " + lt0["a-text"], "--a-text: " + lt0["paper-2"], 1)
    rep = lint_tokens_text(faint)
    ok(any(i["id"] == "heading/body" and i["level"] == "fail" for i in rep.items), "a heading under 4.5:1 fails heading/body")
    # climb hue
    bad_hue = css.replace("--climb: " + p["palette"]["light"]["climb"], "--climb: " + p["palette"]["light"]["b"], 1)
    rep = lint_tokens_text(bad_hue)
    ok(any(i["id"].startswith("climb") for i in rep.failed), "climb equal to b is caught")
    # climb-text: text twin of climb, >= 4.5 on paper and paper-2; m-select (edge) >= 3 on the slab
    lt_ = p["palette"]["light"]
    bad_ct = css.replace("--climb-text: " + lt_["climb-text"], "--climb-text: " + lt_["paper-2"], 1)
    rep = lint_tokens_text(bad_ct)
    ok(any(i["id"] == "climb-text/paper" for i in rep.failed) and any(i["id"] == "climb-text/paper-2" for i in rep.failed),
       "climb-text without contrast on paper and paper-2 is caught")
    other_hue = lt_["b-text"]    # reads on paper, but it is the accent's hue, not the climb hue
    rep = lint_tokens_text(css.replace("--climb-text: " + lt_["climb-text"], "--climb-text: " + other_hue, 1))
    ok(any(i["id"] == "climb-text-hue/climb" for i in rep.failed), "climb-text in another hue than climb is caught")
    bad_sel = css.replace("--m-select: " + lt_["m-select"], "--m-select: " + lt_["m-slab"], 1)
    rep = lint_tokens_text(bad_sel)
    ok(any(i["id"] == "m-select/m-slab" and i["scheme"] == "light" for i in rep.failed), "m-select edge without 3:1 on the slab is caught")
    # m-cap (the ink line of the map): under 4.5:1 on the slab fails, under 7:1 warns; m-wall under 3:1 warns (FIX-SPEC-3 A3)
    slab_ = lt_["m-slab"]
    rep = lint_tokens_text(css.replace("--m-cap: " + lt_["m-cap"], "--m-cap: " + slab_, 1))
    ok(any(i["id"] == "m-cap/m-slab" and i["scheme"] == "light" for i in rep.failed), "an m-cap that vanishes into the slab fails")
    def toward_slab(h, ratio_lo, ratio_hi):          # h pulled toward the slab until its contrast falls into [lo, hi]
        for k in range(101):
            c_ = kit.mix_ok(h, slab_, k / 100.0)
            if ratio_lo <= kit.contrast(c_, slab_) <= ratio_hi:
                return c_
        raise AssertionError("no colour with contrast %s-%s between %s and %s" % (ratio_lo, ratio_hi, h, slab_))
    five = toward_slab(lt_["m-cap"], 4.8, 6.5)
    rep = lint_tokens_text(css.replace("--m-cap: " + lt_["m-cap"], "--m-cap: " + five, 1))
    ok(rep.ok and any(i["id"] == "m-cap/m-slab(7:1)" and i["scheme"] == "light" for i in rep.warned), "an m-cap between 4.5 and 7 passes the floor with a warning")
    pale = toward_slab(lt_["m-wall"], 1.2, 2.8)
    rep = lint_tokens_text(css.replace("--m-wall: " + lt_["m-wall"], "--m-wall: " + pale, 1))
    ok(rep.ok and any(i["id"] == "m-wall/m-slab" and i["scheme"] == "light" for i in rep.warned), "an m-wall under 3:1 warns")
    dk_cap = css.replace("--m-cap: " + p["palette"]["dark"]["m-cap"], "--m-cap: " + p["palette"]["dark"]["m-slab"])
    ok(any(i["id"] == "m-cap/m-slab" and i["scheme"] == "dark" for i in lint_tokens_text(dk_cap).failed), "…and in the dark block too")
    nofill = css.replace("--m-select-fill:", "--m-select-fill-x:")
    rep = lint_tokens_text(nofill)
    ok(any(i["id"] == "tokens-present" and "m-select-fill" in i["msg"] for i in rep.failed), "missing --m-select-fill is reported")
    # the fill has no floor: a fill identical to the room still passes
    same = css.replace("--m-select-fill: " + lt_["m-select-fill"], "--m-select-fill: " + lt_["m-room"], 1)
    ok(lint_tokens_text(same).ok, "--m-select-fill has no contrast floor")
    # structural
    good = "@media (prefers-reduced-motion: reduce){*{transition:none!important;animation:none!important}} a:focus-visible{outline:3px solid red} button:focus{outline:none}"
    r1 = Report("x")
    check_css(r1, parse_css(good), good, "t")
    ok(any(i["id"] == "outline-none" and i["level"] == "fail" for i in r1.items) and not any(i["id"] in ("reduced-motion", "focus-visible") and i["level"] == "fail" for i in r1.items),
       "button:focus{outline:none} with only a:focus-visible is caught, reduced motion + focus-visible pass")
    r2 = Report("x")
    bad = "a{outline:none} button{transition:all .2s}"
    check_css(r2, parse_css(bad), bad, "t")
    ids = {i["id"] for i in r2.failed}
    ok({"reduced-motion", "focus-visible", "outline-none"} <= ids, "bad CSS fails reduced-motion, focus-visible, outline-none: %s" % ids)
    r3 = Report("x")
    fine = "@media (prefers-reduced-motion: reduce){*{transition:none}} :focus-visible{outline:3px solid #00f} .x:focus{outline:none;box-shadow:inset 0 0 0 3px red} @media (hover:hover){a:hover{color:red}}"
    check_css(r3, parse_css(fine), fine, "t")
    ok(not r3.failed, "good CSS passes: %s" % [i["msg"] for i in r3.failed])
    # parser: nested at-rules, quotes with braces and semicolons
    rules = parse_css('/* c */ :root{--a: "x;y{"; --b: url(data:image/png;base64,AA); } @media (min-width: 5px){ .k{color:red} } @font-face{font-family:X;src:url(a.woff2)}')
    ok(any(r["sel"] == ":root" and dict(r["decls"]).get("--a") == '"x;y{"' for r in rules), "parser keeps quoted ; and {")
    ok(any(r["sel"] == ".k" and r["ctx"] == ("@media (min-width: 5px)",) for r in rules), "parser nests @media")
    # files: tokens.css + roll.json + html round trip
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td) / "tokens.css"
        tp.write_text(css, encoding="utf-8")
        reps = lint_path(tp)
        ok(reps[0].ok, "lint_path tokens.css")
        rp = Path(td) / "roll.json"
        rp.write_text(json.dumps({"cards": [{"direction": "airmail", "code": "X", "params": p}], "chosen": None}))
        reps = lint_path(rp)
        ok(len(reps) == 1 and reps[0].ok, "lint_path roll.json")
        hp = Path(td) / "p.html"
        hp.write_text('<!doctype html><html lang="zh-CN"><head><style>%s a:focus-visible{outline:2px solid red}@media (prefers-reduced-motion: reduce){*{transition:none}}</style></head><body></body></html>' % css, encoding="utf-8")
        reps = lint_path(hp)
        ok(reps[0].ok, "lint_path page.html: %s" % [i["msg"] for i in reps[0].failed])
    ok("lint_floor:" in format_reports([rep]), "format")
    if fails:
        print("lint_floor.py selftest: %d FAILED" % len(fails))
        return 1
    print("lint_floor.py selftest: ok")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="lint_floor.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", help="tokens.css | roll.json | page.html | project directory")
    ap.add_argument("--card", type=int, help="roll.json: only this card (1-based); default the chosen card, else all")
    ap.add_argument("--strict", action="store_true", help="warnings fail too")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--quiet", action="store_true", help="print only failures and warnings")
    ap.add_argument("--selftest", action="store_true", help="run built-in tests")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    if not a.path:
        ap.print_help()
        return 2
    try:
        reps = lint_path(a.path, a.card)
    except (OSError, ValueError, KeyError) as e:
        print("lint_floor.py: %s" % e, file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps([{"title": r.title, "ok": r.ok, "items": r.items} for r in reps], indent=1, ensure_ascii=False))
    else:
        print(format_reports(reps, a.quiet))
    bad = any(r.failed for r in reps) or (a.strict and any(r.warned for r in reps))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
