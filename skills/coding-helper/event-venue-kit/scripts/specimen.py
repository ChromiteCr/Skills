#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""event-venue-kit :: specimen.py -- one self-contained HTML page per rolled card.  每张牌一页样张。

    specimen.py <roll.json> [--card N | --all] --out DIR [--venue PATH [--entity ID]] [--offline] [--strict]
                [--props on|off] [--png [--png-at top,route] [--scheme both|light|dark] [--width 390] [--height 1800] [--chrome PATH]]

The page is built from the card's own tokens (kit.tokens_css) + assets/floor/base.css + assets/recipes/<direction>.css +
assets/engine/*.js, all inlined, so it opens from file:// and can be e-mailed.
It shows the components of BUILD-SPEC 2.4: bar + nav, welcome with stats and buttons, divider, search + floor tabs, the entity
grid, a live map with a route sheet, an entity head with strip and three reading parts (the part navigator is live), and a
footer that lists every parameter of the card (palette in light and dark with contrast numbers, fonts, scale, shape, map,
motion, notes, adjustments, <html> attributes). A theme button cycles auto / light / dark so both schemes can be judged.
With several cards an index.html is written too.

Content / 内容
  default        an imaginary harbour science & craft fair (assets/demo/venue.json), bilingual
  --venue PATH   YOUR venue.json (schema: assets/engine/venue.schema.json). The event / venue name, the entity names and colours,
                 rooms, open areas, floors and the live route all come from it, so the specimen shows the real name lengths, the
                 real booth density and the real building. --entity ID picks the entity of the long-page sample (default: the
                 one with the longest name, the worst case). The sample paragraphs of the reading parts are marked as filler.
Lead language / 主语言: the card's `lead` (--keep lead=zh). Every bilingual pair is written PRIMARY LANGUAGE FIRST (the .cn line
first when lead=zh), <html> carries lang and data-evk-lead, and the map follows it.

Open every page and look; the direction's name alone gives the average impression of that name (references/randomness.md step 3).

Props / 装饰母题: a direction's category motifs (herbarium leaf label, riso halftone, heraldry shield ...) are `--prop-*` custom properties
(library/directions.json `props`). The page shows them ON (the default); `--props off` builds it with all of them off, and a Props
button on the page toggles them live, so you can judge the direction with and without its motif before you keep one.

No browser tab? --png / 没有浏览器标签时: with a local Chrome or Chromium (macOS: /Applications/Google Chrome.app; Linux: google-chrome,
chromium; or --chrome PATH, or $CHROME) every page is also rendered to PNG files at phone width: --width x --height px (default 390 x 1800),
per scheme (light and dark) and per spot of the page. --png-at picks the spots, default `top,route`: top = the page from the top (bar,
welcome, stats, grid); route = the floor-plan section with the map drawn and a route sheet open (route and map are shot at a phone's
height, 844 px, or --height if smaller); also entities, map, reading, params.
Files: card-N-<direction>-<spot>-<scheme>.png next to the HTML. The pages are loaded through a 390 px frame (Chrome's headless window is
never narrower than 500 px), with ?static=1 (no transitions), ?theme= and reduced motion (springs snap to their end state); --virtual-time-budget=4000 lets the map draw. Without a Chrome
the HTML is written as usual, the message says so, and the exit code is still 0. stdlib only (subprocess); one-shot profile, nothing is left running.

Fonts: unless --offline, the page loads the named faces from Google Fonts for PREVIEW only (a project page self-hosts them;
floor F27). Offline, or when a face is missing, the system fallbacks of each stack show.
Missing kit files (base.css, a recipe, an engine script, the demo venue) are reported on stderr and in a banner on the page
instead of stopping the build; --strict makes them an error (exit 1).
Exit code: 0 ok (also when --png finds no Chrome); 1 --strict and something was missing, or a PNG could not be made; 2 usage / input
error (including an unreadable --venue or a --chrome that does not exist).
"""
from __future__ import annotations

import argparse
import html as _html
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit  # noqa: E402
import draw  # noqa: E402
import install  # noqa: E402  (html_open_tag: the one place that writes the <html> attributes)

ENGINE_ORDER = ["tones.js", "search.js", "spring.js", "sheet.js", "part-nav.js", "wayfind.js", "venue-map.js"]
_CJK = re.compile(r"[㐀-鿿豈-﫿　-〿＀-￯]")


def esc(s):
    return _html.escape(str(s), quote=True)


def has_cjk(s):
    return bool(_CJK.search(str(s)))


def tx(v):
    """A schema `text` (a string, or {en, cn} with either side missing) -> (en, cn); a missing side falls back to the other."""
    if isinstance(v, str):
        return v, v
    if isinstance(v, dict):
        en, cn = str(v.get("en") or ""), str(v.get("cn") or "")
        return en or cn, cn or en
    return "", ""


def LS(en, cn, lead):
    """The two languages in reading order: [(text, lang, cls), ...], PRIMARY FIRST. One line when both are the same string."""
    e, c = (en, "en", "en"), (cn, "zh-CN", "cn")
    if en == cn or not cn:
        return [(en, "zh-CN", "cn")] if has_cjk(en) else [(en, "en", "en")]
    if not en:
        return [c]
    return [c, e] if lead == "zh" else [e, c]


def PAIR(en, cn, lead):
    """The bilingual pair as bare spans, primary language first (for buttons, tabs, steps: boxes that are not .evk-k)."""
    return "".join('<span class="%s" lang="%s">%s</span>' % (cls, lang, esc(t)) for t, lang, cls in LS(en, cn, lead))


_CJK_CH = "㐀-鿿豈-﫿"                    # ideographs
_CJK_ANY = _CJK_CH + "　-〿＀-￯"       # + CJK punctuation and full-width forms


def autospace(s):
    """F10 for the sentences this script writes: no space between two CJK characters (or around a full-width mark), exactly one between
    a CJK ideograph and a Latin letter or digit. Idempotent. (A name that comes from the venue file is never passed through it.)"""
    s = re.sub(r"(?<=[%s])[ \t]+(?=[%s])" % (_CJK_ANY, _CJK_ANY), "", str(s))
    s = re.sub(r"(?<=[%s])(?=[A-Za-z0-9])" % _CJK_CH, " ", s)
    return re.sub(r"(?<=[A-Za-z0-9])(?=[%s])" % _CJK_CH, " ", s)


EVENT_KEYS = {"name", "date", "time", "place", "note"}


def event_name(venue, default=None):
    """The event's name as (en, cn). venue.event is a text (a string, or {en, cn}) or an object {name, date, time, place, note}; the name
    is event.name, else the venue's own name, else `default`."""
    ev = venue.get("event")
    name = ev.get("name") if isinstance(ev, dict) and set(ev) & EVENT_KEYS else ev
    if name in (None, "", {}):
        name = venue.get("name") or default
    return tx(name)


def K(en, cn, cls="", tag="span", lead="en"):
    """The bilingual pair, PRIMARY LANGUAGE FIRST (BUILD-SPEC 2.4 as amended by FIX-SPEC A1): English first when lead=en, the
    .cn line first when lead=zh. base.css reads the roles from the position and the typesetting from .en / .cn / lang."""
    return '<%s class="evk-k%s">%s</%s>' % (tag, (" " + cls) if cls else "", PAIR(en, cn, lead), tag)


def lines_html(en, cn, lead, tag1, cls1, cls2, tag2="p"):
    """Two stacked lines (a heading and its translation), primary first, each with its lang."""
    ls = LS(en, cn, lead)
    out = ['<%s class="%s" lang="%s">%s</%s>' % (tag1, cls1, ls[0][1], esc(ls[0][0]), tag1)]
    if len(ls) > 1:
        out.append('<%s class="%s" lang="%s">%s</%s>' % (tag2, cls2, ls[1][1], esc(ls[1][0]), tag2))
    return "".join(out)


def js_text(s):
    return re.sub(r"</(script)", r"<\\/\1", s, flags=re.I)


def json_in_html(obj):
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")


# --------------------------------------------------------------------------------------------------
# assets
# --------------------------------------------------------------------------------------------------

FALLBACK_VENUE = {
    "unit": "m", "name": {"en": "Pier Nine Hall", "cn": "九号码头展馆"},
    "event": {"en": "Harbour Science & Craft Fair", "cn": "港湾科学与手作博览会"},
    "floors": [{"id": "1F", "level": 1, "name": {"en": "First Floor", "cn": "一层"},
                "outline": [[0, 0], [30, 0], [30, 20], [0, 20]], "rooms": [
                    {"id": "HALL", "label": "H1", "name": {"en": "Grand Hall", "cn": "大展厅"}, "poly": [[0, 0], [30, 0], [30, 14], [0, 14]], "doors": [[15, 14, 3]]}]}],
    "entities": [
        {"id": "kelp", "name": {"en": "Kelp & Co. Bioplastics", "cn": "海带生物塑料"}, "short": "Kelp", "color": "#2F8F6B", "room": "HALL", "booth": "01", "tags": ["materials"]},
        {"id": "orbital", "name": {"en": "Orbital Kitchen", "cn": "轨道厨房"}, "short": "Orbital", "color": "#E4572E", "room": "HALL", "booth": "02", "tags": ["food"]},
        {"id": "tideclock", "name": {"en": "Tideclock Works", "cn": "潮汐钟表坊"}, "short": "Tideclock", "color": "#1F6FB2", "room": "HALL", "booth": "03", "tags": ["craft"]},
        {"id": "paperlab", "name": {"en": "Paper Engines Lab", "cn": "纸机械实验室"}, "short": "Paperlab", "color": "#F2B134", "room": "HALL", "booth": "04", "tags": ["paper"]},
        {"id": "loomhouse", "name": {"en": "Loomhouse", "cn": "织机工坊"}, "short": "Loomhouse", "color": "#8E4A9E", "room": "HALL", "booth": "05", "tags": ["textile"]},
        {"id": "ironbird", "name": {"en": "Ironbird Forge", "cn": "铁鸟锻造"}, "short": "Ironbird", "color": "#5B6770", "room": "HALL", "booth": "06", "tags": ["metal"]},
    ],
}


def load_venue(path):
    """Read a project's venue.json. Raises ValueError (with a message for the user) when it cannot be a venue."""
    p = Path(path)
    try:
        v = json.loads(p.read_text(encoding="utf-8"))
    except OSError as e:
        raise ValueError("cannot read --venue %s: %s" % (p, e))
    except ValueError as e:
        raise ValueError("--venue %s is not valid JSON: %s" % (p, e))
    if not isinstance(v, dict) or not isinstance(v.get("floors"), list) or not v["floors"]:
        raise ValueError("--venue %s has no floors (see assets/engine/venue.schema.json)" % p)
    if not isinstance(v.get("entities"), list) or not v["entities"]:
        raise ValueError("--venue %s has no entities: a specimen needs the things people look for" % p)
    for e in v["entities"]:
        if not isinstance(e, dict) or not e.get("id") or e.get("name") is None:
            raise ValueError("--venue %s: every entity needs an id and a name (bad: %r)" % (p, e))
    return v


class Assets(object):
    def __init__(self, direction_id, venue_path=None):
        self.missing = []
        self.project = bool(venue_path)
        self.venue_source = str(venue_path) if venue_path else None
        self.base = self._read(kit.ASSETS_DIR / "floor" / "base.css", "assets/floor/base.css")
        self.recipe = self._read(kit.ASSETS_DIR / "recipes" / ("%s.css" % direction_id), "assets/recipes/%s.css" % direction_id)
        self.engine = []
        for name in ENGINE_ORDER:
            t = self._read(kit.ASSETS_DIR / "engine" / name, "assets/engine/%s" % name)
            if t is not None:
                self.engine.append((name, t))
        self.fallback_venue = False
        if venue_path:
            self.venue = load_venue(venue_path)          # the project's own data: errors stop the build (exit 2)
            return
        v = self._read(kit.ASSETS_DIR / "demo" / "venue.json", "assets/demo/venue.json")
        try:
            self.venue = json.loads(v) if v else None
        except ValueError as e:
            self.missing.append("assets/demo/venue.json (invalid JSON: %s)" % e)
            self.venue = None
        if self.venue is None:
            self.venue = FALLBACK_VENUE
            self.fallback_venue = True

    def _read(self, path, label):
        if path.exists():
            return path.read_text(encoding="utf-8")
        self.missing.append(label)
        return None


# --------------------------------------------------------------------------------------------------
# the venue as the page needs it: places, names, entity colours
# --------------------------------------------------------------------------------------------------

def place_index(venue, lead="en"):
    """room / area id -> {label, floor, name:(en, cn), kind}. Entities sit in a room, in an open area, or at a point.
    An area without a `label` is tagged with its name in the lead language."""
    idx = {}
    for f in venue.get("floors", []):
        for r in f.get("rooms") or []:
            idx[r["id"]] = {"label": str(r.get("label") or r["id"]), "floor": f["id"], "name": tx(r.get("name")), "kind": "room"}
        for a in f.get("areas") or []:
            en, cn = tx(a.get("name"))
            idx[a["id"]] = {"label": str(a.get("label") or (cn if lead == "zh" else en) or a["id"]), "floor": f["id"], "name": (en, cn), "kind": a.get("kind") or "open"}
    return idx


def entity_place(e, idx):
    pl = idx.get(e.get("room"))
    if pl:
        return pl
    return {"label": "", "floor": str(e.get("floor") or ""), "name": ("", ""), "kind": "point"}


def floor_name(venue, fid):
    for f in venue.get("floors", []):
        if f["id"] == fid:
            return tx(f.get("name")) if f.get("name") else (fid, fid)
    return (fid, fid)


def term(venue, key, default):
    t = (venue.get("terms") or {}).get(key)
    en, cn = tx(t) if t else default
    return en, cn


def term_words(venue, key, default_en, default_cn, keep_empty_cn=False):
    """A venue `terms` entry as (en, cn) WITHOUT inventing the other side from the first: a missing or empty side takes the default
    (terms.room.cn is empty by design -- '204 门口' reads better than '展室 204 门口' -- so the stat label falls back to a word,
    while keep_empty_cn=True lets a place text use the bare number)."""
    t = (venue.get("terms") or {}).get(key)
    if isinstance(t, str):
        en, cn = ("", t) if has_cjk(t) else (t, "")
    elif isinstance(t, dict):
        en, cn = str(t.get("en") or "").strip(), str(t.get("cn") or "").strip()
    else:
        en = cn = ""
    return en or default_en, cn if (cn or keep_empty_cn) else default_cn


def cap(s):
    return s[:1].upper() + s[1:] if s else s


def plural(w):
    """Booth -> Booths, Gallery -> Galleries, Box -> Boxes."""
    if re.search(r"[^aeiou]y$", w, re.I):
        return w[:-1] + "ies"
    if re.search(r"(s|x|ch|sh)$", w, re.I):
        return w + "es"
    return w + "s"


def entity_color(e, pal):
    c = e.get("color")
    try:
        return kit.norm_hex(c) if c else pal["light"]["b"]
    except ValueError:
        return pal["light"]["b"]


def entity_style(color, pal):
    t = kit.tones(color, pal["light"]["paper"], pal["light"]["text"], pal["dark"]["paper"])
    return ";".join("%s:%s" % (kit.TONES_CSS[k], t[k]) for k in kit.TONES_KEYS)


def initial(e, lead):
    en, cn = tx(e.get("name"))
    if lead == "zh" and has_cjk(cn):
        return cn.strip()[:1]
    s = (e.get("short") or en or cn or "?").strip()
    return s[:1].upper()


def width_em(s):
    """Rough width of a string in ems: a CJK character is one em, a Latin one about half."""
    return sum(1.0 if has_cjk(c) else 0.5 for c in str(s))


def clip(s, em=14):
    """A name cut to about `em` ems with an ellipsis (a button label is not the place to stress-test the longest name)."""
    s, w = str(s), 0.0
    for i, ch in enumerate(s):
        w += 1.0 if has_cjk(ch) else 0.5
        if w > em:
            return s[:i].rstrip() + "…"
    return s


def name_fit(s):
    """The name-fit ladder of base.css (data-fit): bigger for short names, smaller for long ones."""
    w = width_em(s)
    return 0 if w <= 4 else 2 if w <= 7 else 3 if w <= 12 else 4


def longest_entity(venue):
    best = None
    for e in venue.get("entities", []):
        en, cn = tx(e.get("name"))
        if best is None or len(en) + len(cn) > best[0]:
            best = (len(en) + len(cn), e)
    return best[1]


# --------------------------------------------------------------------------------------------------
# page parts
# --------------------------------------------------------------------------------------------------

def grid_cells(venue, pal, lead, idx):
    """One cell per entity: mark, PRIMARY line, secondary line, tag. The primary language is written first (base.css reads the
    roles from the position)."""
    out = []
    for e in venue.get("entities", []):
        en, cn = tx(e.get("name"))
        pl = entity_place(e, idx)
        tag = esc(pl["label"]) + ("<small>·%s</small>" % esc(e.get("booth", "")) if pl["label"] and e.get("booth") else "")
        if not pl["label"]:
            tag = esc(e.get("booth", "")) or esc(pl["floor"])
        lines = "".join('<span class="%s%s" lang="%s">%s</span>' % ("name " if i == 0 else "", cls, lang, esc(t)) for i, (t, lang, cls) in enumerate(LS(en, cn, lead)))
        out.append(
            '<li data-id="%s"><a class="evk-cell" href="#map" data-id="%s" style="%s">'
            '<span class="evk-mark" aria-hidden="true">%s</span>%s<span class="evk-tag">%s</span></a></li>' % (
                esc(e["id"]), esc(e["id"]), esc(entity_style(entity_color(e, pal), pal)), esc(initial(e, lead)), lines, tag))
    return "\n".join(out)


def floor_tabs(venue, lead):
    b = ['<button type="button" role="tab" aria-selected="true" data-floor="">%s</button>' % PAIR("All", "全部", lead)]
    for f in venue.get("floors", []):
        en, cn = tx(f.get("name")) if f.get("name") else ("", "")
        if lead == "zh" and cn and cn != f["id"]:
            label = '<span lang="zh-CN" class="cn">%s</span><span lang="en">%s</span>' % (esc(cn), esc(f["id"]))
        elif cn and cn != f["id"] and has_cjk(cn):
            label = '<span lang="en">%s</span><span lang="zh-CN" class="cn">%s</span>' % (esc(f["id"]), esc(cn))
        else:
            label = '<span lang="en">%s</span>' % esc(f["id"])
        b.append('<button type="button" role="tab" aria-selected="false" data-floor="%s">%s</button>' % (esc(f["id"]), label))
    return "".join(b)


ENTITY_PAGE = {
    "id": "orbital",
    "tagline": ("Cooking science for people who have never left the ground.", "给没离开过地面的人做的料理科学。"),
    "strip": [("46", "people", "Team", "团队规模"), ("12", "dishes", "On the menu", "展出菜品"), ("3", "rooms", "Experiments", "互动实验"), ("2019", "", "Founded", "成立年份")],
    "parts": [
        (("What it is", "它是什么"), [
            ("Orbital Kitchen is a student-run lab that cooks with the physics of orbit: sphere noodles that hold their shape like drops in microgravity, vacuum-dried fruit, and a rice cooker bolted to a turntable.",
             "轨道厨房是一支学生实验团队，用轨道物理来做饭：像失重水滴一样成球的面条、真空干燥的水果，还有装在转盘上的电饭煲。"),
            ("Every dish comes with the one-sentence physics behind it, printed on the plate.", "每道菜的盘子上都印着一句话的物理原理。")]),
        (("On the floor", "现场"), [
            ("Three stations run all day. Station one is the spinning cooker, station two the vacuum chamber, station three a tasting table where you can ask about anything.",
             "全天有三个展台：旋转电饭煲、真空舱，以及可以随便提问的品尝桌。"),
            ("Quantities are small. Come early for the sphere noodles.", "每份很少，想吃球形面条请早点来。")]),
        (("Find us", "怎么找"), [
            ("Grand Hall, booth 02, left of the main doors. Look for the orange crate stack.", "大展厅 02 号展位，主门左手边，找那堆橙色木箱。"),
            ("Step-free access from the harbour side.", "港口一侧有无台阶通道。")]),
    ],
}


def project_page(venue, e, idx):
    """The long-page sample for a project entity, built from its own data. Names, places and numbers are real; the two
    paragraphs of part 2 are filler and say so (the spec: a specimen shows real names and real density, not invented copy)."""
    en, cn = tx(e.get("name"))
    pl = entity_place(e, idx)
    fid = pl["floor"]
    fen, fcn = floor_name(venue, fid) if fid else ("", "")
    ben, bcn = term_words(venue, "booth", "booth", "展位")
    ren, rcn = term_words(venue, "room", "Room", "房间", keep_empty_cn=True)
    here = sum(1 for x in venue.get("entities", []) if entity_place(x, idx)["label"] == pl["label"] and entity_place(x, idx)["floor"] == fid)
    booth = str(e.get("booth", "") or "")
    place_en = ("%s %s" % (ren, pl["label"]) if pl["kind"] == "room" and pl["label"].isdigit() else (pl["name"][0] or pl["label"] or fen or "the floor")).strip()
    place_cn = autospace(("%s %s" % (rcn or "", pl["label"]) if pl["kind"] == "room" and pl["label"].isdigit() else (pl["name"][1] or pl["label"] or fcn or "本层")).strip())
    strip = []
    if booth:
        strip.append((booth, "", ben.capitalize(), bcn))
    if fid:
        strip.append((fid, "", "Floor", "楼层"))
    if pl["label"]:
        strip.append((pl["label"], "", ren if pl["kind"] == "room" else "Area", (rcn or "房间") if pl["kind"] == "room" else "区域"))
    strip.append((str(here), "", "Here", "同处"))
    tags = [str(t) for t in (e.get("tags") or [])]
    glance_en = "%s is in %s%s%s." % (en, place_en, (", on the %s" % fen.lower()) if fen and fen != fid else (", on %s" % fid if fid else ""), (", %s %s" % (ben, booth)) if booth else "")
    glance_cn = autospace("%s在%s%s%s。" % (cn, fcn if fcn else "", place_cn, ("，%s 号%s" % (booth, bcn)) if booth else ""))
    para = [(glance_en, glance_cn)]
    if tags:
        para.append(("Tagged: %s." % ", ".join(tags), autospace("标签：%s。" % "、".join(tags))))
    parts = [
        (("At a glance", "概览"), para),
        (("Sample text", "示例文字"), [
            ("Filler, to show the reading measure and the line height. The sentences in this part are placeholders for %s's real copy; the names, the place and the numbers around them are the project's own." % en,
             autospace("示例文字，用来看行宽和行高。这一部分的句子是%s真实文案的占位，周围的名字、位置和数字取自项目自己的数据。" % cn)),
            ("A second paragraph shows the space between paragraphs and how the bilingual lines sit under each other.", "第二段用来看段间距，以及双语的两行怎样上下排列。")]),
        (("Find us", "怎么找"), [
            ("%s. Use the route button above for steps from the entrance." % ("%s, %s" % (place_en, fen) if fen else place_en),
             autospace("%s。点上面的路线按钮，看从入口出发的分步路线。" % ("%s，%s" % (fcn, place_cn) if fcn else place_cn)))]),
    ]
    return {"tagline": (e.get("short") and ("%s · %s" % (e.get("short"), place_en)) or place_en, autospace("%s · %s" % (cn, place_cn))),
            "strip": strip, "parts": parts, "place_en": place_en, "place_cn": place_cn, "booth": booth, "floor": fid}


def reading_block(venue, pal, lead, entity=None, project=False):
    idx = place_index(venue, lead)
    ents = venue.get("entities", [])
    if project:
        e = entity or longest_entity(venue)
        page = project_page(venue, e, idx)
    else:
        byid = {x["id"]: x for x in ents}
        e = entity or byid.get(ENTITY_PAGE["id"]) or ents[1 if len(ents) > 1 else 0]
        page = None
    style = entity_style(entity_color(e, pal), pal)
    en, cn = tx(e.get("name"))
    pl = entity_place(e, idx)
    ben, bcn = term_words(venue, "booth", "booth", "展位")
    if project:
        strip_src = page["strip"]
        parts_src = page["parts"]
        tagline = page["tagline"]
        place_en, place_cn, booth = page["place_en"], page["place_cn"], page["booth"]
        eyebrow = K("%s%s" % (place_en, (" · %s %s" % (ben, booth)) if booth else ""), "%s%s" % (place_cn, (" · %s 号%s" % (booth, bcn)) if booth else ""), "evk-eyebrow", "p", lead)
        eyebrow = eyebrow.replace('class="evk-k evk-eyebrow"', 'class="evk-eyebrow evk-k"')
    else:
        strip_src = ENTITY_PAGE["strip"]
        parts_src = ENTITY_PAGE["parts"]
        tagline = ENTITY_PAGE["tagline"]
        label = pl["label"]
        booth = str(e.get("booth", ""))
        eyebrow = K("Exhibitor · %s %s" % (label, "booth " + booth), "展商 · %s %s 号展位" % (label, booth), "evk-eyebrow", "p", lead)
        eyebrow = eyebrow.replace('class="evk-k evk-eyebrow"', 'class="evk-eyebrow evk-k"')
    strip = "".join('<div class="evk-num"><b>%s%s</b><span>%s</span></div>' % (
        esc(v), ("<small>%s</small>" % esc(u)) if u else "", PAIR(a, b, lead)) for v, u, a, b in strip_src)
    parts = []
    for i, ((a, b), paras) in enumerate(parts_src, 1):
        body = "".join(_para(pa, pb, lead) for pa, pb in paras)
        if i == 2:
            if project:
                fold = ("Filler as well: a closed section, to show the fold.", "同样是占位：一个收起的小节，用来看折叠的样子。")
            else:
                fold = ("Contains wheat and soy. The vacuum-dried fruit is dried without sulphites.", "含小麦和大豆。真空干燥水果不使用亚硫酸盐。")
            body += '<details class="evk-fold"><summary>%s</summary>%s</details>' % (
                K("Notes" if project else "Allergen notes", "备注" if project else "过敏原说明", lead=lead), _para(fold[0], fold[1], lead))
        parts.append('<section class="evk-part" data-part id="spx-part-%d"><header class="evk-part-head"><span class="no">%02d</span>%s</header>%s</section>' % (
            i, i, K(a, b, lead=lead), body))
    ls = LS(en, cn, lead)
    primary = ls[0][0]
    head = '<h2 class="evk-entity-name" data-fit="%d" lang="%s">%s</h2>' % (name_fit(primary), ls[0][1], esc(primary))
    second = ('<p class="spx-name-2" lang="%s">%s</p>' % (ls[1][1], esc(ls[1][0]))) if len(ls) > 1 else ""
    tl = LS(tagline[0], tagline[1], lead)
    tagline_html = '<p class="spx-tag" lang="%s">%s%s</p>' % (tl[0][1], esc(tl[0][0]), ('<br><span lang="%s">%s</span>' % (tl[1][1], esc(tl[1][0]))) if len(tl) > 1 else "")
    return (
        '<article data-report id="reading" class="evk-entity" style="%s">'
        '<header class="evk-entity-head">%s%s<div class="evk-entity-rule"></div>%s%s</header>'
        '<div class="evk-strip">%s</div>%s</article>' % (esc(style), eyebrow, head, second, tagline_html, strip, "".join(parts))), e


def _para(a, b, lead):
    ls = LS(a, autospace(b), lead)
    return "".join('<p lang="%s">%s</p>' % (lang, esc(t)) for t, lang, _ in ls)


def swatches(pal):
    def fg(h):
        return "#000000" if kit.contrast(h, "#000000") >= kit.contrast(h, "#FFFFFF") else "#FFFFFF"
    cells = []
    for group, names in (("colour roles", kit.COLOR_TOKENS), ("map materials", kit.MAP_COLOR_TOKENS)):
        cells.append('<h4 class="spx-h4">%s</h4><div class="spx-sw">' % esc(group))
        for n in names:
            lo, dk = pal["light"][n], pal["dark"][n]
            cells.append('<div class="spx-chip"><span style="background:%s;color:%s">%s</span><span style="background:%s;color:%s">%s</span><b>--%s</b></div>' % (
                lo, fg(lo), lo, dk, fg(dk), dk, esc(n)))
        cells.append("</div>")
    return "".join(cells)


def contrast_rows(pal):
    """Every floor and advisory check, light and dark, from kit.check_scheme (so the table can never disagree with lint_floor)."""
    rows, order = {}, []
    for sc in ("light", "dark"):
        for c in kit.check_scheme(pal[sc]):
            if c["id"] not in rows:
                rows[c["id"]] = {}
                order.append(c["id"])
            rows[c["id"]][sc] = c
    out = []
    for cid in order:
        r = rows[cid]
        lt, dk = r.get("light"), r.get("dark")
        c0 = lt or dk

        def show(c):
            if c is None or c["ratio"] is None:
                return "n/a"
            return ("%.0f&deg;" % c["ratio"]) if c.get("unit") == "deg" else "%.2f" % c["ratio"]
        ok = all(c["ok"] for c in (lt, dk) if c)
        sign = "&le;&nbsp;" if c0.get("max") else ""
        out.append("<tr><th scope=\"row\">%s</th><td>%s</td><td>%s</td><td>%s%g</td><td>%s</td><td>%s</td></tr>" % (
            esc(cid), show(lt), show(dk), sign, c0["min"], esc(c0["rule"]), "pass" if ok else ("<b>LOW</b>" if c0["level"] == "floor" else "<b>low</b> (advisory)")))
    return "".join(out)


def scale_rows(ty, sample):
    base_min, base_max = ty["base"]
    ratio = ty["ratio"]
    r_min = max(1.125, round(ratio - 0.05, 3))
    rows = []
    for i in range(5, -2, -1):
        mn, mx = base_min * r_min ** i, base_max * ratio ** i
        rows.append('<div class="spx-step" style="font-size:var(--step-%d)"><small>step %d &middot; %.0f&ndash;%.0f px</small><span>%s</span></div>' % (i, i, min(mn, mx), max(mn, mx), esc(sample)))
    return "".join(rows)


def params_footer(card, roll, idx, total, assets, sample):
    p = card["params"]
    pal, ty, sh, mp, mo = p["palette"], p["type"], p["shape"], p["map"], p["motion"]
    f = ty["fonts"]
    nm = card.get("name") or {}
    fp = card["fingerprint"]
    sim = card["similarity_to_canon"]
    matched = ", ".join(kit.axis_matches(fp, roll.get("canon_fingerprint") or fp)) or "none"
    lead = p.get("lead") or "en"

    def dl(rows):
        return "<dl class=\"spx-dl\">" + "".join("<div><dt>%s</dt><dd>%s</dd></div>" % (esc(a), b) for a, b in rows) + "</dl>"

    card_rows = [
        ("direction", "<b>%s</b> &middot; %s %s" % (esc(card["direction"]), esc(nm.get("en", "")), esc(nm.get("cn", "")))),
        ("mechanism", esc(p.get("mechanism", ""))), ("idea", esc(p.get("idea", ""))),
        ("preset code", "<code>%s</code>" % esc(card["code"])), ("card seed", "%s (roll seed %s)" % (card.get("card_seed"), roll.get("seed"))),
        ("steer / canon", "%s / %s" % (esc(roll.get("steer") or "-"), "yes" if roll.get("canon") else "no")),
        ("lead language", "%s &middot; <small>the first line of every pair; <code>data-evk-lead=\"%s\"</code></small>" % ("Chinese (zh)" if lead == "zh" else "English (en)", lead)),
        ("similarity to source", "%.2f &middot; matching axes: %s" % (sim, esc(matched))),
    ]
    if kit.family_text(p):
        card_rows.insert(3, ("hue family", esc(kit.family_text(p))))
    pr_ = kit.props_of(p)
    if pr_:
        card_rows.append(("props", "<ul class=\"spx-props\">%s</ul><small>decorative motifs of the category, on by default; the Props button above toggles them. Keep one only if the inventory supports it; switch one off with its line at the end of <code>:root</code> in tokens.css.</small>" % "".join(
            "<li><b>%s</b> %s &middot; <code>%s</code> off = <code>%s</code></li>" % (esc(x["name"]), esc(x["what"]), esc(x["var"]), esc(x["off"])) for x in pr_)))
    if assets.project:
        card_rows.append(("content", "your venue &middot; <code>%s</code>" % esc(Path(assets.venue_source).name)))
    if p.get("specimen_note"):
        card_rows.append(("how it should feel", esc(p["specimen_note"])))
    type_rows = []
    for role in kit.FONT_ROLES:
        ft = f[role]
        type_rows.append((role, "%s &middot; <small>%s</small>" % (esc(ft.get("name", "")), esc(ft.get("class", "") or "")) + (" <small>(kept)</small>" if ft.get("forced") else "")))
    type_rows += [("label", esc("%s, stretch %s, track %sem, weight %s" % (ty["label_case"], ty["label_stretch"], kit._fmt(ty["label_track"], 3), ty["label_weight"]))),
                  ("display", esc("weight %s, track %sem, leading %s" % (ty["display_weight"], kit._fmt(ty["display_track"], 3), kit._fmt(ty["display_leading"], 3)))),
                  ("scale", esc("ratio %s, base %s-%s px" % (kit._fmt(ty["ratio"], 3), kit._fmt(ty["base"][0]), kit._fmt(ty["base"][1]))))]
    shape_rows = [("shape", esc("%s, radius %spx, chamfer %spx, rules 1/%s/%s px, cap %spx" % (sh["language"], sh["radius"], sh["chamfer"], sh["rule_2"], sh["rule_3"], sh["rule_cap"]))),
                  ("divider", esc(p["divider"])), ("entity head", esc(p["entity_header"])), ("map token", esc(p["entity_token"])),
                  ("numerals", esc(p["numerals"])), ("navigator", esc(p["nav"])), ("density", esc(p["density"])), ("texture", esc(p["texture"])),
                  ("layout", esc("gutter %s, gap %s, row-pad %s px, measure %sch" % (p["layout"]["gutter"], p["layout"]["gap"], p["layout"]["row_pad"], p["layout"]["measure"])))]
    map_rows = [("map", esc("%s / %s / token %s" % (mp["projection"], mp["material"], mp["token"]))),
                ("camera", esc("pitch %s&deg; yaw %s&deg; wall %s m light %s dim %s label-case %s" % (kit._fmt(mp["pitch"]), kit._fmt(mp["yaw"]), kit._fmt(mp["wall_h"], 2), mp["light"], kit._fmt(mp["dim"], 2), mp["label_case"])).replace("&amp;deg;", "&deg;")),
                ("motion", esc("%s: spring %ss, bounce %s, press x%s, fade %ss" % (kit.motion_bucket(mo["dur"], mo["bounce"]), kit._fmt(mo["dur"], 2), kit._fmt(mo["bounce"], 2), kit._fmt(mo["press"], 3), kit._fmt(mo["fade"], 2))))]
    notes = ""
    if p.get("richness"):
        notes += "<h4 class=\"spx-h4\">richness &middot; what gives it fullness</h4><ul>%s</ul>" % "".join("<li>%s</li>" % esc(x) for x in p["richness"])
    if p.get("watch"):
        notes += "<h4 class=\"spx-h4\">watch &middot; drift to steer away from</h4><ul>%s</ul>" % "".join("<li>%s</li>" % esc(x) for x in p["watch"])
    if kit.floor_notes(p):
        notes += "<h4 class=\"spx-h4\">floor-tuned &middot; colour roles the generator walked to meet a contrast floor (automatic)</h4><ul>%s</ul>" % "".join(
            "<li>%s</li>" % esc(kit.adjust_text(x)) for x in kit.floor_notes(p))
    if kit.user_adjustments(p):
        notes += "<h4 class=\"spx-h4\">adjusted &middot; frozen outside the envelope, or changed with <code>draw.py adjust</code></h4><ul>%s</ul>" % "".join(
            "<li>%s</li>" % esc(kit.adjust_text(x)) for x in kit.user_adjustments(p))
    attrs = install.html_open_tag(p)
    cmds = ('python3 scripts/draw.py choose %d --reason "..." --roll .evk/roll.json\n'
            'python3 scripts/draw.py adjust KEY=VALUE --reason "..." --roll .evk/roll.json   # optional: change a value, keep the card\n'
            'python3 scripts/install.py .evk/roll.json ./site --starter --venue %s' % (idx, (assets.venue_source if assets.project else "data/venue.json")))
    return (
        '<footer class="spx-foot" id="params"><h2 class="spx-h2">%s</h2>'
        '<div class="spx-cols"><section>%s%s</section><section><h4 class="spx-h4">type</h4>%s<h4 class="spx-h4">shape and rules</h4>%s<h4 class="spx-h4">map and motion</h4>%s</section></div>'
        '<h3 class="spx-h3">%s</h3>%s'
        '<h3 class="spx-h3">%s</h3><div class="spx-scroll"><table class="spx-table"><thead><tr><th scope="col">check</th><th scope="col">light</th><th scope="col">dark</th><th scope="col">min</th><th scope="col">rule</th><th scope="col"></th></tr></thead><tbody>%s</tbody></table></div>'
        '<h3 class="spx-h3">%s</h3><div class="spx-type"><p class="d">%s</p><p class="l">Floors 层楼 &middot; Booth 展位 02</p><p class="t">%s</p><p class="n">1F 2F 3F &nbsp; 203&middot;01 &nbsp; 08:30&ndash;17:00</p></div>%s'
        '<div class="spx-cols"><section>%s</section><section><h4 class="spx-h4">&lt;html&gt; attributes (recipes and the engine switch on these)</h4><pre class="spx-pre">%s</pre>'
        '<h4 class="spx-h4">next</h4><pre class="spx-pre">%s</pre></section></div>'
        '<p class="spx-note">Specimen page %d of %d &middot; kit %s &middot; %s &middot; preview loads named fonts from Google Fonts unless built with --offline (project pages self-host, floor F27).</p></footer>' % (
            K("Card parameters", "牌面参数", lead=lead), dl(card_rows), "", dl(type_rows), dl(shape_rows), dl(map_rows),
            esc("Colours: light | dark"), swatches(pal), esc("Contrast, light and dark"), contrast_rows(pal), esc("Type"),
            esc(sample[0]), esc(sample[1]), "<h4 class=\"spx-h4\">scale</h4>" + scale_rows(ty, sample[0]), notes,
            esc(attrs).replace("&quot;", '"'), esc(cmds), idx, total, kit.KIT_VERSION,
            "your venue data" if assets.project else "fictional content"))


SPX_CSS = """
/* specimen furniture: tokens only (swatch fills excepted: they are the data on show) */
[hidden]{display:none!important}
.spx-ribbon{display:flex;flex-wrap:wrap;gap:6px 18px;align-items:baseline;padding:8px max(var(--gutter),env(safe-area-inset-left));background:var(--paper-2);color:var(--sub);border-bottom:var(--hair) solid var(--rule);font-family:var(--f-num);font-size:var(--step--1);line-height:1.4}
.spx-ribbon b{color:var(--text);font-weight:600}
.spx-warn{margin:0;padding:10px max(var(--gutter),env(safe-area-inset-left));background:var(--paper);color:var(--text);border-bottom:var(--rule-3) solid var(--b);font-size:var(--step--1)}
.spx-h1{margin:.25em 0 .1em;font-family:var(--f-display);font-weight:var(--display-weight);font-size:var(--step-5);line-height:var(--display-leading);letter-spacing:var(--display-track);color:var(--a-text);text-wrap:balance}
.spx-h1-2{margin:0 0 .6em;font-family:var(--f-display);font-size:var(--step-2);line-height:1.2;font-weight:var(--display-weight);color:var(--sub);text-wrap:balance}
.spx-lede{max-width:var(--measure);font-size:var(--step-1);line-height:1.5;margin:.4em 0}
.spx-lede-2{max-width:var(--measure);color:var(--sub);margin:.2em 0 1em}
.spx-meta{display:flex;flex-wrap:wrap;gap:var(--gap) calc(var(--gap)*2);margin:var(--gap) 0}
.spx-meta div{min-width:0}.spx-meta dt{margin:0}.spx-meta dd{margin:.2em 0 0}
.spx-actions{display:flex;flex-wrap:wrap;gap:12px;margin-top:calc(var(--gap)*1.5)}
.spx-h2{margin:calc(var(--gap)*3) 0 var(--gap);font-family:var(--f-display);font-weight:var(--display-weight);font-size:var(--step-3);line-height:var(--display-leading);letter-spacing:var(--display-track);color:var(--a-text)}
.spx-h3{margin:calc(var(--gap)*2) 0 .6em;font-family:var(--f-display);font-weight:var(--display-weight);font-size:var(--step-1);color:var(--a-text)}
.spx-h4{margin:1.4em 0 .5em;font-family:var(--f-label);font-size:var(--step--1);font-weight:var(--label-weight);letter-spacing:var(--label-track);text-transform:var(--label-case);color:var(--sub)}
.spx-tools{display:grid;gap:var(--gap);margin:var(--gap) 0}
@media (min-width:700px){.spx-tools{grid-template-columns:minmax(0,1fr) auto;align-items:end}}
.spx-name-2{margin:0;font-family:var(--f-display);font-size:var(--step-2);line-height:1.2;font-weight:var(--display-weight);color:var(--sub);text-wrap:balance}
.spx-tag{margin:.4em 0 0;color:var(--text);max-width:var(--measure)}
.spx-brandmark{width:26px;height:26px;margin-inline-end:8px;flex:none;color:var(--b)}
.spx-step-t{display:block;color:var(--text);font-size:var(--step--1);line-height:1.45;margin-top:2px;font-family:var(--f-text)}
.spx-step-t.is-2{color:var(--sub)}
.evk-steps li>button{display:block;width:100%;min-height:var(--hit);padding:0;text-align:left;background:none;border:0;color:inherit;font:inherit;cursor:pointer}
.evk-steps li>button:focus-visible{outline:var(--focus-w,3px) solid var(--focus);outline-offset:2px}
.spx-sheet-sum{margin:.2em 0 .8em;color:var(--sub)}
.spx-map-note{margin:.6em 0 0;color:var(--sub);font-size:var(--step--1)}
.spx-foot{margin-top:calc(var(--gap)*5);padding-top:var(--gap);border-top:var(--rule-cap) solid var(--a)}
.spx-cols{display:grid;gap:var(--gap) calc(var(--gap)*2)}
@media (min-width:860px){.spx-cols{grid-template-columns:repeat(2,minmax(0,1fr))}}
.spx-dl{margin:0}.spx-dl>div{display:grid;grid-template-columns:minmax(6.5em,9em) minmax(0,1fr);gap:.2em 1em;padding:.45em 0;border-bottom:var(--hair) solid var(--rule)}
.spx-dl dt{color:var(--sub);font-family:var(--f-label);font-size:var(--step--1);text-transform:var(--label-case);letter-spacing:var(--label-track)}
.spx-dl dd{margin:0;min-width:0;overflow-wrap:anywhere}
.spx-sw{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
.spx-chip{display:grid;grid-template-columns:1fr 1fr;border:var(--hair) solid var(--rule);font-family:var(--f-num);font-size:.7rem}
.spx-chip span{display:block;padding:14px 6px 6px;text-align:center}
.spx-chip b{grid-column:1/-1;padding:4px 6px;background:var(--paper-2);color:var(--sub);font-weight:500;overflow-wrap:anywhere}
.spx-scroll{overflow-x:auto}
.spx-table{width:100%;border-collapse:collapse;font-size:var(--step--1);font-family:var(--f-num)}
.spx-table th,.spx-table td{padding:5px 8px;text-align:left;border-bottom:var(--hair) solid var(--rule);white-space:nowrap}
.spx-type p{margin:.2em 0}.spx-type .d{font-family:var(--f-display);font-weight:var(--display-weight);font-size:var(--step-3);line-height:var(--display-leading);letter-spacing:var(--display-track)}
.spx-type .l{font-family:var(--f-label);font-size:var(--step-0);font-weight:var(--label-weight);font-stretch:var(--label-stretch);letter-spacing:var(--label-track);text-transform:var(--label-case)}
.spx-type .t{font-family:var(--f-text);font-size:var(--step-0);max-width:var(--measure)}.spx-type .n{font-family:var(--f-num);font-size:var(--step-1)}
.spx-step{display:flex;flex-direction:column;border-bottom:var(--hair) solid var(--rule);padding:.2em 0;font-family:var(--f-text);overflow:hidden}
.spx-step small{font-family:var(--f-num);font-size:.7rem;color:var(--sub)}
.spx-pre{margin:0;padding:10px 12px;background:var(--paper-2);color:var(--text);font-family:var(--f-num);font-size:.78rem;overflow-x:auto;white-space:pre-wrap;overflow-wrap:anywhere}
.spx-note{margin-top:calc(var(--gap)*2);color:var(--sub);font-size:var(--step--1);max-width:var(--measure)}
.spx-dl small{color:var(--sub)}
.spx-foot ul{margin:.2em 0;padding-left:1.2em;max-width:var(--measure)}
.spx-foot code{font-family:var(--f-num)}
.evk-map.spx-missing{display:grid;place-items:center;text-align:center;padding:var(--gap)}
.spx-props{margin:0 0 .4em;padding:0;list-style:none}.spx-props li{padding:.15em 0}
[data-spx-static] *,[data-spx-static] *::before,[data-spx-static] *::after{transition:none!important;animation:none!important;scroll-behavior:auto!important}
"""

PAGE_JS = r"""
(function () {
  "use strict";
  var doc = document, root = doc.documentElement;
  function $(s, r) { return (r || doc).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || doc).querySelectorAll(s)); }
  var venue = JSON.parse($("#spx-venue").textContent);
  var ents = venue.entities || [], byId = {};
  ents.forEach(function (e) { byId[e.id] = e; });
  /* a schema text is a string or {en, cn} with either side missing: nm() always gives both */
  function nm(v) { return typeof v === "string" ? { en: v, cn: v } : v && typeof v === "object" ? { en: v.en || v.cn || "", cn: v.cn || v.en || "" } : { en: "", cn: "" }; }
  function zh() { return root.getAttribute("data-evk-lead") === "zh"; }          // the lead language: written first, and larger
  var roomFloor = {};                                                              // rooms AND open areas know their floor
  (venue.floors || []).forEach(function (f) {
    (f.rooms || []).forEach(function (r) { roomFloor[r.id] = f.id; });
    (f.areas || []).forEach(function (r) { roomFloor[r.id] = f.id; });
  });
  function entFloor(e) { return roomFloor[e.room] || e.floor || ""; }            // an entity stands in a room, in an area, or at a point on a floor
  var map = null, wf = null, sheet = null, curFloor = "", curId = null, curPlan = null;
  var sh = $("#spx-sheet"), box = $("#spx-map"), hint = $(".evk-map-hint", box), stepsEl = $("#spx-steps");

  /* ---- theme: auto -> light -> dark (the map re-reads its tokens by itself when data-theme changes) ---- */
  var modes = ["auto", "light", "dark"], mi = 0, tbtn = $("#spx-theme");
  function setTheme() {
    var m = modes[mi];
    if (m === "auto") root.removeAttribute("data-theme"); else root.setAttribute("data-theme", m);
    $(".en", tbtn).textContent = "Theme: " + m;
    $(".cn", tbtn).textContent = m === "auto" ? "主题：跟随" : (m === "light" ? "主题：浅色" : "主题：深色");
    tbtn.setAttribute("aria-pressed", m === "auto" ? "false" : "true");
  }
  if (tbtn) tbtn.addEventListener("click", function () { mi = (mi + 1) % 3; setTheme(); });
  var qm = /[?&]theme=(light|dark)/.exec(location.search);     // specimen.html?theme=dark opens in that scheme
  if (qm && tbtn) { mi = modes.indexOf(qm[1]); setTheme(); }

  /* ---- ?static=1: no transitions or animations (a screenshot must not catch the page half-way) ---- */
  if (/[?&]static=1/.test(location.search)) root.setAttribute("data-spx-static", "");

  /* ---- props: the direction's category motifs (--prop-* custom properties). ON = the recipe's own default, so "on" sets the
     property to `initial` (guaranteed-invalid: var() takes its fallback) and "off" sets the listed off value. ?props=off opens it off. ---- */
  var pbtn = $("#spx-props"), pdata = {};
  try { pdata = JSON.parse($("#spx-props-data").textContent) || {}; } catch (err) {}
  var pitems = pdata.props || [], pOff = !!pdata.off;
  function setProps() {
    pitems.forEach(function (x) { root.style.setProperty(x.var, pOff ? x.off : "initial"); });
    if (pbtn) {
      $(".en", pbtn).textContent = "Props: " + (pOff ? "off" : "on");
      $(".cn", pbtn).textContent = pOff ? "母题：关" : "母题：开";
      pbtn.setAttribute("aria-pressed", pOff ? "true" : "false");
    }
  }
  var pq = /[?&]props=(on|off)/.exec(location.search);
  if (pq) pOff = pq[1] === "off";
  if (pitems.length) { setProps(); if (pbtn) pbtn.addEventListener("click", function () { pOff = !pOff; setProps(); }); }

  /* ---- search + floor tabs filter the grid ---- */
  var q = $("#spx-q"), lis = $$(".evk-grid > li"), emptyEl = $("#spx-empty");
  function norm(s) { return (s || "").toLowerCase(); }
  /* EVK.search (assets/engine/search.js) ranks names, short forms, group words and room numbers; without it a plain substring filter */
  var finder = null;
  if (window.EVK && EVK.search) { try { finder = EVK.search.create(ents, { rooms: venue.floors }); } catch (err) { if (window.console) console.warn(err); } }
  function applyFilter() {
    var t = (q.value || "").trim(), shown = 0, hits = null;
    if (t && finder) { hits = {}; finder.query(t).forEach(function (r) { hits[r.entity.id] = true; }); }
    lis.forEach(function (li) {
      var e = byId[li.getAttribute("data-id")];
      if (!e) { li.hidden = true; return; }
      var match;
      if (!t) match = shown < 6;
      else if (hits) match = !!hits[e.id];
      else { var n = nm(e.name); match = norm([n.en, n.cn, e.short, (e.tags || []).join(" "), e.room, e.booth].join(" ")).indexOf(norm(t)) >= 0; }
      var ok = (!curFloor || entFloor(e) === curFloor) && match;
      li.hidden = !ok;
      if (ok) shown++;
    });
    if (emptyEl) emptyEl.hidden = shown > 0;
  }
  if (q) q.addEventListener("input", applyFilter);
  $$("#spx-floors button").forEach(function (b) {
    b.addEventListener("click", function () {
      $$("#spx-floors button").forEach(function (x) { x.setAttribute("aria-selected", x === b ? "true" : "false"); });
      curFloor = b.getAttribute("data-floor") || "";
      if (map) { try { map.setFloor(curFloor || null); } catch (e) {} }
      applyFilter();
    });
  });
  applyFilter();

  /* ---- nav: aria-current follows the click ---- */
  $$(".evk-nav a").forEach(function (a) {
    a.addEventListener("click", function () { $$(".evk-nav a").forEach(function (x) { x.removeAttribute("aria-current"); }); a.setAttribute("aria-current", "page"); });
  });

  /* ---- entity artwork for the map tokens: an initial on the entity colour (a data URI, nothing external) ---- */
  function lumOf(hex) {
    var c = [1, 3, 5].map(function (i) { var v = parseInt(hex.substr(i, 2), 16) / 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  }
  var imgs = {};
  ents.forEach(function (e) {
    var n = nm(e.name), col = /^#[0-9a-fA-F]{6}$/.test(e.color || "") ? e.color : "#777777";
    var ch = (zh() && /[\u3400-\u9fff]/.test(n.cn.charAt(0)) ? n.cn.charAt(0) : (e.short || n.en || "?").charAt(0).toUpperCase()), ink = lumOf(col) > 0.3 ? "#14171D" : "#FFFFFF";
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="' + col + '"/><text x="32" y="45" font-family="Georgia,\'PingFang SC\',\'Noto Sans SC\',serif" font-size="36" font-weight="700" text-anchor="middle" fill="' + ink + '">' + ch + "</text></svg>";
    var im = new Image();
    im.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
    imgs[e.id] = im;
  });

  /* ---- route sheet ---- */
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  /* a bilingual pair, PRIMARY LANGUAGE FIRST (the lead language of <html data-evk-lead>) */
  function lines(en, cn) {
    var E = { t: en, lang: "en", cls: "en" }, C = { t: cn, lang: "zh-CN", cls: "cn" };
    if (!cn || cn === en) return [/[\u3400-\u9fff]/.test(en) ? C : E].map(function (x) { x.t = en; return x; });
    return zh() ? [C, E] : [E, C];
  }
  function pair(en, cn) { return '<span class="evk-k evk-k--stack">' + lines(en, cn).map(function (x) { return '<span class="' + x.cls + '" lang="' + x.lang + '">' + esc(x.t) + "</span>"; }).join("") + "</span>"; }
  function sp(t) { return window.EVK && EVK.spaced ? EVK.spaced(t) : t; }           /* F10: one space between a CJK character and a Latin letter or digit */
  function renderSteps(plan, e, start) {
    var steps = wf.describe(plan, "both") || [];
    var n = nm(e.name), sn = nm(start.name || start.label || "the entrance");
    $("#spx-sheet-t").innerHTML = pair(n.en, n.cn);
    var sum = $("#spx-sheet-sum");
    if (sum) {
      var m = plan && plan.metres ? Math.round(plan.metres) : 0;
      sum.innerHTML = lines("From " + (start.label || sn.en) + (m ? " · about " + m + " m" : ""), sp("从" + sn.cn + "出发" + (m ? "，约 " + m + " 米" : ""))).map(function (x) { return '<span class="' + x.cls + '" lang="' + x.lang + '">' + esc(x.t) + "</span>"; }).join("");
    }
    stepsEl.innerHTML = steps.map(function (s, i) {
      var en = s.en || { head: s.head, text: s.text }, cn = s.cn || { head: s.head, text: s.text };
      var cls = (i === 0 ? "is-current " : "") + (s.kind === "stairs" ? "is-climb is-stairs" : "");
      var tl = lines(en.text, cn.text).map(function (x, k) { return '<span class="spx-step-t is-' + (k + 1) + '" lang="' + x.lang + '">' + esc(x.t) + "</span>"; }).join("");
      return '<li class="' + cls.trim() + '" data-i="' + i + '"><button type="button">' + pair(en.head, cn.head) + tl + "</button></li>";
    }).join("");
    $$("li", stepsEl).forEach(function (li) { $("button", li).addEventListener("click", function () { setStep(+li.getAttribute("data-i")); }); });
  }
  function setStep(i) {
    $$("li", stepsEl).forEach(function (li) { li.classList.toggle("is-current", i !== null && +li.getAttribute("data-i") === i); });
    var ov = $("#spx-overview"); if (ov) ov.setAttribute("aria-pressed", i === null ? "true" : "false");
    stepsEl.classList.toggle("is-all", i === null);
    if (map) { try { map.routeStep(i); } catch (e) {} }
  }
  var ovBtn = $("#spx-overview");
  if (ovBtn) ovBtn.addEventListener("click", function () { setStep(ovBtn.getAttribute("aria-pressed") === "true" ? 0 : null); });
  var closeBtn = $("#spx-close");
  function openSheet(launcher) { if (sheet) sheet.open({ launcher: launcher }); else sh.hidden = false; sh.classList.add("is-running"); }
  function closeSheet() { if (sheet) sheet.close(); else sh.hidden = true; }
  if (closeBtn) closeBtn.addEventListener("click", closeSheet);

  function select(id, fromMap, launcher) {
    var e = byId[id];
    if (!e) return;
    curId = id;
    $$(".evk-cell").forEach(function (c) { if (c.getAttribute("data-id") === id) c.setAttribute("aria-current", "true"); else c.removeAttribute("aria-current"); });
    if (map && !fromMap) { try { map.select(id); } catch (err) {} }
    if (wf && map) {
      try {
        var starts = wf.starts(), start = starts.filter(function (s) { return s.kind === "entrance"; })[0] || starts[0];
        var plan = wf.plan(start.id, id) || wf.plan(start.id, "entity:" + id);
        curPlan = plan;
        if (plan) { map.setRoute(plan); renderSteps(plan, e, start); setStep(0); }
      } catch (err) { if (window.console) console.warn("specimen: route failed", err); }
    }
    openSheet(launcher);
  }
  $$(".evk-cell").forEach(function (c) {
    c.addEventListener("click", function (ev) { ev.preventDefault(); select(c.getAttribute("data-id"), false, c); });
  });
  var routeBtn = $("#spx-route-btn");
  var featured = routeBtn ? routeBtn.getAttribute("data-id") : (ents[0] && ents[0].id);        // the entity of the long-page sample
  if (routeBtn) routeBtn.addEventListener("click", function () { select(curId || featured, false, routeBtn); });
  var findBtn = $("#spx-find-btn");
  if (findBtn) findBtn.addEventListener("click", function () { var s = $("#spx-q"); if (s) { s.scrollIntoView(); s.focus({ preventScroll: true }); } });

  /* ---- reading navigator ---- */
  if (window.EVK && EVK.partNav) { try { EVK.partNav($("[data-report]")); } catch (e) { if (window.console) console.warn(e); } }

  /* ---- sheet + map ---- */
  if (window.EVK && EVK.Sheet && sh) {
    try {
      sheet = new EVK.Sheet(sh, { onClose: function () { if (map) { try { map.setRoute(null); map.select(null); map.setPad({ top: 0, right: 0, bottom: 0, left: 0 }); } catch (e) {} } curId = null; $$(".evk-cell").forEach(function (c) { c.removeAttribute("aria-current"); }); } });
    } catch (e) { if (window.console) console.warn(e); }
  }
  function say(msg) { if (hint) { hint.classList.remove("is-gone"); hint.textContent = msg; } }
  function startMap() {
    var canvas = $("canvas", box);
    if (!(window.EVK && EVK.VenueMap && EVK.wayfind && EVK.venueModel)) {
      box.classList.add("spx-missing");
      say("The map engine is not in this build (venue-map.js / wayfind.js missing). The list above has the same information.");
      return;
    }
    try {
      wf = EVK.wayfind.create(venue);
      map = new EVK.VenueMap(canvas, venue, {                     // no `lead` option: the map follows <html data-evk-lead>
        entities: ents,
        image: function (e) { return imgs[e.id] || null; },
        onSelect: function (id) { if (id) select(id, true); else if (sheet && sheet.isOpen) sheet.close(); },
        onRoom: function () {}
      });
      if (EVK.fitAbove && EVK.fitAbove.watch) { try { EVK.fitAbove.watch(map, [sh], { mapEl: box }); } catch (e) {} }
      if (curFloor) map.setFloor(curFloor);
    } catch (e) {
      box.classList.add("spx-missing");
      say("The map could not start: " + e.message);
      if (window.console) console.error(e);
    }
  }
  var pending = ents.length, started = false;
  function go() {
    if (started) return; started = true; startMap();
    if (location.hash === "#route") {                      /* the floor-plan section in view, a route open (what specimen.py --png shoots) */
      select(curId || featured, false);
      var ms = $("#map"), bar = $(".evk-bar");
      if (ms) window.scrollTo(0, ms.getBoundingClientRect().top + (window.pageYOffset || 0) - (bar ? bar.offsetHeight : 0) - 8);
    }
  }
  ents.forEach(function (e) { var im = imgs[e.id]; if (im.complete) { if (--pending === 0) go(); } else { im.onload = im.onerror = function () { if (--pending === 0) go(); }; } });
  setTimeout(go, 600);
})();
"""

FONT_JS = r"""
(function () {
  var F = %s;
  F.forEach(function (name) {
    var chain = ["wght@400;500;600;700", "wght@400;700", ""], i = 0, l = document.createElement("link");
    function url() { return "https://fonts.googleapis.com/css2?family=" + encodeURIComponent(name).replace(/%%20/g, "+") + (chain[i] ? ":" + chain[i] : "") + "&display=swap"; }
    l.rel = "stylesheet";
    l.onerror = function () { if (++i < chain.length) l.href = url(); };
    l.href = url();
    document.head.appendChild(l);
  });
})();
"""


def google_families(params):
    names = []
    for role in ("display", "label", "text", "num"):
        g = params["type"]["fonts"][role].get("google")
        if g and g.lower() not in ("system", "system ui", "system-ui") and g not in names:
            names.append(g)
    return names


def build_page(card, roll, idx, total, assets, offline, entity_id=None, props="on"):
    p = card["params"]
    card_props = kit.props_of(p)
    pal = p["palette"]
    lead = p.get("lead") or "en"
    venue = assets.venue
    project = assets.project
    pidx = place_index(venue, lead)
    ev_en, ev_cn = event_name(venue, None if project else FALLBACK_VENUE["event"])
    vn_en, vn_cn = tx(venue.get("name") or FALLBACK_VENUE["name"])
    nfl = len(venue.get("floors", []))
    nent = len(venue.get("entities", []))
    # rooms only: a corridor, a lobby or an open area is not a room (a venue with none shows its areas instead, labelled as such)
    nroom = sum(len(f.get("rooms", []) or []) for f in venue.get("floors", []))
    narea = sum(len(f.get("areas", []) or []) for f in venue.get("floors", []))
    areas_only = nroom == 0 and narea > 0
    if areas_only:
        nroom = narea
    tokens = kit.tokens_css(p, header="specimen card %d of %d  code %s  seed %s" % (idx, total, card["code"], card.get("card_seed")),
                            props_off=(props == "off"))
    warn = ""
    if assets.missing:
        warn = '<p class="spx-warn" role="note"><b>Missing kit files:</b> %s. The page is built without them.</p>' % esc(", ".join(assets.missing))
    nm = card.get("name") or {}
    fam_txt = kit.family_text(p, " · ")
    ribbon = ('<div class="spx-ribbon"><span><b>SPECIMEN 样张</b> %d/%d</span><span><b>%s</b> %s %s</span><span>%s</span><span>lead %s</span><span>similarity to source %.2f</span>'
              '%s%s<span><a href="#params">parameters &darr;</a></span></div>') % (
        idx, total, esc(card["direction"]), esc(nm.get("en", "")), esc(nm.get("cn", "")), esc(card["code"]), esc(lead), card["similarity_to_canon"],
        (('<span>hue family: %s</span>' % esc(fam_txt)) if fam_txt else "") + (('<span>props: %s (%s)</span>' % (esc(", ".join(x["name"] for x in card_props)), props)) if card_props else ""),
        ('<span>your venue: %s</span>' % esc(Path(assets.venue_source).name)) if project else "")
    read, feat = reading_block(venue, pal, lead, None if not entity_id else next((e for e in venue.get("entities", []) if e["id"] == entity_id), None), project)
    fen, fcn = tx(feat.get("name"))
    brand = vn_en if project else "Harbour"
    brand_cn = vn_cn if project else "港湾"
    bar = (
        '<header class="evk-bar"><a class="evk-brand" href="#top"><svg class="spx-brandmark" viewBox="0 0 26 26" aria-hidden="true"><circle cx="13" cy="13" r="11" fill="none" stroke="currentColor" stroke-width="2"/><path d="M5 17c3-5 6-5 8 0s5 5 8 0" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>%s</a>'
        '<nav class="evk-nav" aria-label="Sections"><a class="evk-k" href="#map" aria-current="page">%s</a>'
        '<a class="evk-k" href="#entities">%s</a>'
        '<a class="evk-k" href="#reading">%s</a></nav></header>') % (
        K(brand, brand_cn, lead=lead), PAIR("Map", "导览", lead), PAIR("List", "展商", lead), PAIR("Read", "阅读", lead))
    ben, bcn = term_words(venue, "booth", "booth", "展位")
    ren, rcn = term_words(venue, "room", "Room", "房间")
    if project:
        eyebrow = K("Event guide", "活动导览", "evk-eyebrow", "p", lead)
        lede = _lines2("%d %s on %d floor%s." % (nent, plural(ben), nfl, "" if nfl == 1 else "s"), "%d 层楼，%d 个%s。" % (nfl, nent, bcn), lead, "spx-lede", "spx-lede-2")
        meta = '<dl class="spx-meta"><div><dt>%s</dt><dd>%s</dd></div></dl>' % (K("Where", "地点", lead=lead), _dd(vn_en, vn_cn, lead))
        stat_labels = (K("Floors", "层楼", lead=lead), K(cap(plural(ben)), bcn, lead=lead),
                       K("Areas", "区域", lead=lead) if areas_only else K(cap(plural(ren)), rcn, lead=lead))
        find_lbl, plan_lbl = PAIR("Find", "查找", lead), PAIR("Floor plan", "平面图", lead)
        search_label = "Search · 搜索" if lead == "en" else "搜索 · Search"
        placeholder = "Search by name or number · 按名称或编号搜索" if lead == "en" else "按名称或编号搜索 · Search by name or number"
        empty = _empty("No match.", "没有找到匹配项。", "Try a shorter word, or a room number.", "试试更短的词，或者房间号。", lead)
        sample_line = "%s · %s" % (ev_en, vn_en) if lead == "en" else "%s · %s" % (ev_cn, vn_cn)
        sample = (("%s 0123" % (vn_en if lead == "en" else vn_cn)), "%s 0123" % (vn_cn if lead == "en" else vn_en))
        route_lbl = PAIR("Route to %s" % clip(feat.get("short") or fen), "去%s" % clip(fcn, 8), lead)
        map_note = "Your venue. Tap a token or a list entry to get a route; the sheet is non-modal, drag it down to dismiss."
    else:
        eyebrow = K("Open day · Free entry", "开放日 · 免费入场", "evk-eyebrow", "p", lead)
        lede = _lines2("Fourteen makers, three floors, one afternoon. Follow a route to a booth, or wander.", "十四组创客，三层楼，一个下午。跟着路线去找展位，或者随便逛逛。", lead, "spx-lede", "spx-lede-2")
        meta = ('<dl class="spx-meta"><div><dt>%s</dt><dd>%s</dd></div><div><dt>%s</dt><dd>%s</dd></div></dl>') % (
            K("When", "时间", lead=lead), _dd("Sat 14 Nov · 10:00–17:00", "11 月 14 日 周六 · 10:00–17:00", lead), K("Where", "地点", lead=lead), _dd(vn_en, vn_cn, lead))
        stat_labels = (K("Floors", "层楼", lead=lead), K("Exhibitors", "参展方", lead=lead), K("Rooms", "展室", lead=lead))
        find_lbl, plan_lbl = PAIR("Find an exhibitor", "找展商", lead), PAIR("Floor plan", "平面图", lead)
        search_label = "Search exhibitors · 搜索展商" if lead == "en" else "搜索展商 · Search exhibitors"
        placeholder = search_label
        empty = _empty("No exhibitor matches.", "没有找到匹配的展商。", "Try a shorter word, such as “kiln” or “paper”.", "可以试试更短的词，例如“纸”。", lead)
        sample = ("Pier Nine Hall · 九号码头 0123" if lead == "en" else "九号码头 · Pier Nine Hall 0123", "Cooking science for people who have never left the ground. 给没离开过地面的人做的料理科学。")
        route_lbl = PAIR("Route to Orbital Kitchen", "去轨道厨房", lead)
        map_note = "Fictional hall. Tap a token or an exhibitor to get a route; the sheet is non-modal, drag it down to dismiss."
    title_en, title_cn = (ev_en, ev_cn)
    welcome = (
        '<section class="evk-welcome" id="top">%s%s%s%s'
        '<div class="evk-stats"><div class="evk-stat"><b class="n">%02d</b>%s</div><div class="evk-stat"><b class="n">%02d</b>%s</div><div class="evk-stat"><b class="n">%02d</b>%s</div></div>'
        '<div class="spx-actions"><button type="button" class="evk-btn evk-btn--primary" id="spx-find-btn">%s</button>'
        '<a class="evk-btn" href="#map">%s</a>'
        '<button type="button" class="evk-btn evk-btn--quiet" id="spx-theme" aria-pressed="false">%s</button>%s</div></section>') % (
        eyebrow, lines_html(title_en, title_cn, lead, "h1", "spx-h1", "spx-h1-2"), lede, meta,
        nfl, stat_labels[0], nent, stat_labels[1], nroom, stat_labels[2], find_lbl, plan_lbl, PAIR("Theme: auto", "主题：跟随", lead),
        ('<button type="button" class="evk-btn evk-btn--quiet" id="spx-props" aria-pressed="%s" title="%s">%s</button>' % (
            "true" if props == "off" else "false", esc(", ".join("%s %s" % (x["name"], x["what"]) for x in card_props)),
            PAIR("Props: " + ("off" if props == "off" else "on"), "母题：" + ("关" if props == "off" else "开"), lead))) if card_props else "")
    entities = (
        '<section class="evk-section" id="entities" aria-labelledby="h-ent"><h2 class="spx-h2" id="h-ent">%s</h2><hr class="evk-divider">'
        '<div class="spx-tools"><div><label class="evk-vh" for="spx-q">%s</label><input class="evk-search" id="spx-q" type="search" placeholder="%s" autocomplete="off" enterkeyhint="search"></div>'
        '<div class="evk-seg" role="tablist" aria-label="Floor" id="spx-floors">%s</div></div>'
        '<ul class="evk-grid">%s</ul>'
        '%s</section>') % (
        K("Exhibitors" if not project else cap(plural(ben)), "展商" if not project else bcn, lead=lead), esc(search_label), esc(placeholder),
        floor_tabs(venue, lead), grid_cells(venue, pal, lead, pidx), empty)
    mapsec = (
        '<section class="evk-section" id="map" aria-labelledby="h-map"><h2 class="spx-h2" id="h-map">%s</h2>'
        '<div class="spx-actions" style="margin:0 0 var(--gap)"><button type="button" class="evk-btn evk-btn--primary evk-btn--sm" id="spx-route-btn" data-id="%s">%s</button></div>'
        '<div class="evk-map" id="spx-map" role="img" aria-label="Floor plan. Drag to turn, pinch to zoom. The list above has the same information."><canvas></canvas>'
        '<div class="evk-map-hint evk-k">%s</div></div>'
        '<noscript><p class="evk-empty">The map needs JavaScript. The list above has the same information.</p></noscript>'
        '<p class="spx-map-note">%s</p></section>') % (
        K("Floor plan", "平面图", lead=lead), esc(feat["id"]), route_lbl, PAIR("Drag to turn", "拖动旋转", lead), esc(map_note))
    if project:
        sheet_steps = ""      # the route is computed from YOUR venue in the browser (EVK.wayfind): the steps appear when a place is chosen
        sheet_title = K(fen, fcn, "evk-k--stack", lead=lead)
        sheet_sum = PAIR("Choose a place", "选一个地点", lead)
    else:
        sheet_steps = ('<li class="is-current"><button type="button">%s</button></li><li class="is-climb is-stairs"><button type="button">%s</button></li><li><button type="button">%s</button></li>') % (
            K("Walk to the stairs", "走到楼梯，约 12 米", "evk-k--stack", lead=lead), K("Up to 2F", "走楼梯上到 2 层", "evk-k--stack", lead=lead),
            K("Booth 02 · Orbital", "02 号展位，轨道厨房", "evk-k--stack", lead=lead))
        sheet_title = K("Orbital Kitchen", "轨道厨房", "evk-k--stack", lead=lead)
        sheet_sum = PAIR("From the entrance", "从入口出发", lead)
    sheet_html = (
        '<div class="evk-sheet" id="spx-sheet" role="dialog" aria-modal="false" aria-labelledby="spx-sheet-t" hidden><div class="evk-grabber"></div>'
        '<div class="evk-sheet-head"><h3 id="spx-sheet-t" tabindex="-1">%s</h3><button type="button" class="evk-btn evk-btn--quiet evk-btn--sm" id="spx-close">%s</button></div>'
        '<p class="spx-sheet-sum evk-k" id="spx-sheet-sum">%s</p>'
        '<button type="button" class="evk-btn evk-btn--sm" id="spx-overview" aria-pressed="false">%s</button>'
        '<ol class="evk-steps" id="spx-steps" aria-live="polite">%s</ol></div>') % (
        sheet_title, PAIR("Close", "关闭", lead), sheet_sum, PAIR("Overview", "全览", lead), sheet_steps)
    scripts = []
    for name, text in assets.engine:
        scripts.append("<script>/* %s */\n%s\n</script>" % (name, js_text(text)))
    fonts_js = ""
    if not offline:
        fonts_js = "<script>%s</script>" % (FONT_JS % json.dumps(google_families(p)))
    theme_metas = ('<meta name="color-scheme" content="light dark"><meta name="theme-color" content="%s" media="(prefers-color-scheme: light)">'
                   '<meta name="theme-color" content="%s" media="(prefers-color-scheme: dark)">') % (pal["light"]["paper"], pal["dark"]["paper"])
    lang = "zh-CN" if lead == "zh" else "en"
    page = (
        '<!doctype html>\n<html lang="%s" %s data-evk-paper="%s" data-evk-ink="%s" data-evk-night="%s">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n%s\n'
        '<title>EVK specimen %d/%d · %s · %s</title>\n<meta name="description" content="event-venue-kit specimen: %s, %s">\n'
        '<style id="evk-tokens">\n%s</style>\n<style id="evk-base">\n%s\n</style>\n<style id="evk-recipe">\n%s\n</style>\n<style id="spx">%s</style>\n</head>\n<body>\n'
        '<a class="evk-skip" href="#main">Skip to content</a>\n%s\n%s\n%s\n<main id="main">\n%s\n%s\n%s\n%s\n%s\n</main>\n%s\n'
        '<script type="application/json" id="spx-venue">%s</script>\n<script type="application/json" id="spx-props-data">%s</script>\n%s\n<script>%s</script>\n%s\n</body>\n</html>\n') % (
        lang, kit.root_attrs_html(p), pal["light"]["paper"], pal["light"]["text"], pal["dark"]["paper"], theme_metas, idx, total, esc(card["direction"]), esc(card["code"]),
        esc(card["direction"]), esc(card["code"]),
        tokens, assets.base or "/* base.css missing */", assets.recipe or "/* recipe missing */", SPX_CSS,
        warn, ribbon, bar, welcome, entities, mapsec, read, params_footer(card, roll, idx, total, assets, sample), sheet_html,
        json_in_html(venue), json_in_html({"off": props == "off", "props": card_props}), "\n".join(scripts), js_text(PAGE_JS), fonts_js)
    return page


def _lines2(en, cn, lead, c1, c2):
    ls = LS(en, cn, lead)
    out = '<p class="%s" lang="%s">%s</p>' % (c1, ls[0][1], esc(ls[0][0]))
    if len(ls) > 1:
        out += '<p class="%s" lang="%s">%s</p>' % (c2, ls[1][1], esc(ls[1][0]))
    return out


def _dd(en, cn, lead):
    ls = LS(en, cn, lead)
    return "<br>".join('<span lang="%s">%s</span>' % (lang, esc(t)) for t, lang, _ in ls)


def _empty(en, cn, hint_en, hint_cn, lead):
    ls = LS("%s %s" % (en, hint_en), "%s%s" % (cn, hint_cn), lead)
    body = "".join('<span lang="%s">%s</span>' % (lang, esc(t)) for t, lang, _ in ls)
    return '<div class="evk-empty" id="spx-empty" hidden>%s</div>' % body


def build_index(roll, cards, files, out_dir):
    rows = []
    for (i, c), fn in zip(cards, files):
        p = c["params"]
        lt = p["palette"]["light"]
        dk = p["palette"]["dark"]
        sw = "".join('<i style="background:%s"></i>' % lt[k] for k in ("paper", "a", "b", "climb")) + '<i class="gap"></i>' + "".join('<i style="background:%s"></i>' % dk[k] for k in ("paper", "a", "b"))
        nm = c.get("name") or {}
        rows.append('<li><a href="%s"><span class="n">%d</span><b>%s</b> <span>%s %s</span><span class="sw">%s</span><small>%s &middot; %s &middot; %s &middot; sim %.2f</small><code>%s</code></a></li>' % (
            esc(fn), i, esc(c["direction"]), esc(nm.get("en", "")), esc(nm.get("cn", "")), sw, esc(p["type"]["fonts"]["display"]["name"]),
            esc(p["shape"]["language"]), esc("%s/%s" % (p["map"]["projection"], p["map"]["material"])), c["similarity_to_canon"], esc(c["code"])))
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EVK specimens</title>'
            '<style>:root{color-scheme:light dark;--bg:#fff;--fg:#111;--sub:#555;--rule:#ccc}@media (prefers-color-scheme:dark){:root{--bg:#141414;--fg:#eee;--sub:#aaa;--rule:#333}}'
            'body{margin:0;padding:24px 16px;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,"PingFang SC","Noto Sans SC",sans-serif}main{max-width:760px;margin:0 auto}'
            'h1{font-size:1.3rem;margin:0 0 .3em}p{color:var(--sub);margin:.2em 0 1.2em}ul{list-style:none;margin:0;padding:0}li{border-top:1px solid var(--rule)}'
            'a{display:grid;grid-template-columns:2em 1fr;gap:2px 10px;padding:14px 4px;color:inherit;text-decoration:none}a:focus-visible{outline:3px solid currentColor;outline-offset:-3px}'
            '.n{grid-row:1/4;font-size:1.6rem;font-weight:700}.sw{display:flex;gap:2px;margin:4px 0}.sw i{display:block;width:34px;height:18px;border:1px solid var(--rule)}.sw i.gap{width:12px;border:0}'
            'small,code{color:var(--sub);font-size:.8rem}</style></head><body><main><h1>Specimens &middot; seed %s</h1><p>Open every page, in light and dark (the Theme button), before choosing. Then: <code>python3 scripts/draw.py choose N --reason "..."</code></p><ul>%s</ul></main></body></html>') % (
        esc(roll.get("seed")), "".join(rows))


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")

# --------------------------------------------------------------------------------------------------
# --png: render the pages with a local headless Chrome / Chromium (stdlib only)
# --------------------------------------------------------------------------------------------------

PNG_SPOTS = {"top": "", "entities": "#entities", "map": "#map", "route": "#route", "reading": "#reading", "params": "#params"}
PHONE_H = 844          # route and map are shot at a real phone's height (the sheet cap and the map's share of the screen are judged at 812-844 px)
PHONE_SPOTS = ("route", "map")
CHROME_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "microsoft-edge", "brave-browser")


def chrome_candidates():
    """Where a Chrome / Chromium may live on this machine, best guess first (paths that exist or names on PATH)."""
    env = [os.environ.get(k) for k in ("CHROME", "CHROME_BIN")]
    mac = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Chromium.app/Contents/MacOS/Chromium",
           "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge", "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
           os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")]
    win = [os.path.join(os.environ.get(k, ""), "Google", "Chrome", "Application", "chrome.exe") for k in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
    return [x for x in env if x] + mac + win + [w for w in (shutil.which(n) for n in CHROME_NAMES) if w]


def find_chrome(explicit=None):
    """The Chrome executable to use, or None. An explicit PATH counts only if it is a file; otherwise the first candidate that exists."""
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    for c in chrome_candidates():
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def png_harness(page_url, width, height):
    """A page that shows `page_url` in a frame of exactly width x height CSS px. Headless Chrome's window is never narrower than
    500 px, so a 390 px phone is the first 390 px of a 500 px window; the frame keeps the page's own viewport at 390 px (its media
    queries and 100dvh see 390 x height) and the screenshot crops to the frame."""
    return ('<!doctype html><html><head><meta charset="utf-8"><title>evk png harness</title>'
            '<style>html,body{margin:0;padding:0;background:#808080;overflow:hidden}iframe{display:block;border:0;width:%dpx;height:%dpx}</style></head>'
            '<body><iframe src="%s" width="%d" height="%d"></iframe></body></html>' % (width, height, esc(page_url), width, height))


def chrome_cmd(chrome, profile, out_png, url, width, height, scale=1.0, budget=4000):
    cmd = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
           "--disable-extensions", "--disable-background-networking", "--mute-audio", "--force-device-scale-factor=%g" % scale,
           "--force-prefers-reduced-motion",           # springs snap to their end state: a screenshot must not catch the sheet half-way
           "--user-data-dir=%s" % profile, "--window-size=%d,%d" % (width, height), "--virtual-time-budget=%d" % budget,
           "--screenshot=%s" % out_png]
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        cmd.append("--no-sandbox")              # Chrome refuses to start as root otherwise (a container)
    return cmd + [url]


def png_name(html_name, spot, scheme):
    return "%s-%s-%s.png" % (Path(html_name).stem, spot, scheme)


def shoot(chrome, page_path, out_png, spot, scheme, width, height, scale=1.0, timeout=90, props=None):
    """One screenshot of one spot of one page in one scheme. Returns (ok, message). The profile and the harness are temporary."""
    tmp = tempfile.mkdtemp(prefix="evk-png-")
    try:
        q = "?static=1&theme=%s%s" % (scheme, ("&props=%s" % props) if props else "")
        url = Path(page_path).resolve().as_uri() + q + PNG_SPOTS[spot]
        harness = Path(tmp) / "harness.html"
        harness.write_text(png_harness(url, width, height), encoding="utf-8")
        profile = Path(tmp) / "profile"
        out_png = Path(out_png).resolve()
        if out_png.exists():
            out_png.unlink()
        kw = {"start_new_session": True} if os.name == "posix" else {}
        proc = subprocess.Popen(chrome_cmd(chrome, str(profile), str(out_png), harness.resolve().as_uri(), width, height, scale),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, **kw)
        try:
            _, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:                                           # our own child and its helpers only (its own session)
                os.killpg(proc.pid, signal.SIGKILL) if os.name == "posix" else proc.kill()
            except (OSError, ProcessLookupError):
                proc.kill()
            proc.communicate()
            return False, "Chrome did not finish within %d s" % timeout
        if out_png.exists() and out_png.stat().st_size > 0:
            return True, ""
        lines = [l for l in (err or "").splitlines() if l.strip() and "CVDisplayLink" not in l and "allocator" not in l]
        return False, "Chrome exited with %s and wrote no PNG%s" % (proc.returncode, (": " + " | ".join(lines[-3:])) if lines else "")
    except OSError as e:
        return False, "could not run Chrome: %s" % e
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def render_pngs(chrome, files, out_dir, spots, schemes, width, height, scale=1.0, props=None, say=print):
    """PNGs for every page in `files` (HTML names inside out_dir). Returns (written paths, failures [message])."""
    done, bad = [], []
    for fn in files:
        for spot in spots:
            for scheme in schemes:
                target = Path(out_dir) / png_name(fn, spot, scheme)
                h = min(height, PHONE_H) if spot in PHONE_SPOTS else height
                good, why = shoot(chrome, Path(out_dir) / fn, target, spot, scheme, width, h, scale, props=props)
                if good:
                    done.append(target)
                    say("png   %s (%dx%d)" % (target, width, h))
                else:
                    bad.append("%s: %s" % (target.name, why))
    return done, bad



def main(argv=None):
    ap = argparse.ArgumentParser(prog="specimen.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("roll", nargs="?", help="roll.json from draw.py")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--card", type=int, help="only this card (1-based)")
    g.add_argument("--all", action="store_true", help="every card (default when nothing is chosen yet)")
    ap.add_argument("--out", default=".evk/specimens", help="output directory (default .evk/specimens)")
    ap.add_argument("--venue", metavar="PATH", help="your venue.json: the specimen uses its event / venue name, entities, rooms, floors and route instead of the demo")
    ap.add_argument("--entity", metavar="ID", help="with --venue: the entity of the long-page sample (default: the one with the longest name)")
    ap.add_argument("--offline", action="store_true", help="do not load fonts from Google Fonts (system fallbacks only)")
    ap.add_argument("--props", choices=["on", "off"], default="on", help="the direction's decorative props (--prop-*): on (default) or off; the page has a button to toggle them")
    ap.add_argument("--png", action="store_true", help="also render every page to PNG files with a local headless Chrome / Chromium (no browser tab needed)")
    ap.add_argument("--png-at", default="top,route", metavar="SPOTS", help="with --png: comma list of top, route, entities, map, reading, params (default top,route)")
    ap.add_argument("--scheme", choices=["both", "light", "dark"], default="both", help="with --png: which colour scheme(s) (default both)")
    ap.add_argument("--width", type=int, default=390, help="with --png: phone width in CSS px (default 390)")
    ap.add_argument("--height", type=int, default=1800, help="with --png: height of each PNG in CSS px (default 1800)")
    ap.add_argument("--scale", type=float, default=1.0, help="with --png: device pixel ratio (default 1; 2 for sharper text)")
    ap.add_argument("--chrome", metavar="PATH", help="with --png: the Chrome / Chromium executable (default: look for one; $CHROME works too)")
    ap.add_argument("--strict", action="store_true", help="exit 1 if a kit file is missing")
    ap.add_argument("--selftest", action="store_true", help="run built-in tests")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    if not a.roll:
        ap.print_help()
        return 2
    try:
        roll = draw.read_roll(a.roll)
    except (OSError, ValueError) as e:
        print("specimen.py: %s" % e, file=sys.stderr)
        return 2
    cards = roll.get("cards") or []
    if not cards:
        print("specimen.py: %s has no cards" % a.roll, file=sys.stderr)
        return 2
    if a.entity and not a.venue:
        print("specimen.py: --entity needs --venue", file=sys.stderr)
        return 2
    spots = [x.strip() for x in a.png_at.split(",") if x.strip()]
    if a.png:
        if not spots or any(x not in PNG_SPOTS for x in spots):
            print("specimen.py: --png-at takes a comma list of %s" % ", ".join(PNG_SPOTS), file=sys.stderr)
            return 2
        if not (200 <= a.width <= 2000 and 300 <= a.height <= 16000 and 0.5 <= a.scale <= 4):
            print("specimen.py: --width must be 200-2000, --height 300-16000, --scale 0.5-4", file=sys.stderr)
            return 2
        if a.chrome and not os.path.isfile(a.chrome):
            print("specimen.py: --chrome %s is not a file" % a.chrome, file=sys.stderr)
            return 2
    if a.card:
        if not 1 <= a.card <= len(cards):
            print("specimen.py: --card must be 1-%d" % len(cards), file=sys.stderr)
            return 2
        pick = [(a.card, cards[a.card - 1])]
    elif a.all or not roll.get("chosen"):
        pick = list(enumerate(cards, 1))
    else:
        ch = draw.pick_chosen_card(roll)
        pick = [(cards.index(ch) + 1, ch)] if ch else list(enumerate(cards, 1))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    files, missing_any = [], False
    for i, c in pick:
        try:
            assets = Assets(c["direction"], a.venue)
        except ValueError as e:
            print("specimen.py: %s" % e, file=sys.stderr)
            return 2
        if a.entity and not any(e["id"] == a.entity for e in assets.venue.get("entities", [])):
            print("specimen.py: --entity %s is not an entity of %s (ids: %s)" % (a.entity, a.venue, ", ".join(e["id"] for e in assets.venue["entities"][:12])), file=sys.stderr)
            return 2
        if assets.missing:
            missing_any = True
            print("specimen.py: card %d (%s): missing kit files: %s" % (i, c["direction"], ", ".join(assets.missing)), file=sys.stderr)
        page = build_page(c, roll, i, len(cards), assets, a.offline, a.entity, a.props)
        fn = "card-%d-%s.html" % (i, slug(c["direction"]))
        (out / fn).write_text(page, encoding="utf-8")
        files.append(fn)
        print("wrote %s (%d KB)" % (out / fn, len(page) // 1024))
    if len(pick) > 1:
        (out / "index.html").write_text(build_index(roll, pick, files, out), encoding="utf-8")
        print("wrote %s" % (out / "index.html"))
    print("open: file://%s" % (out.resolve() / (files[0] if len(files) == 1 else "index.html")))
    rc = 1 if (a.strict and missing_any) else 0
    if a.png:
        chrome = find_chrome(a.chrome)
        if not chrome:
            print("specimen.py: --png: no Chrome or Chromium found (looked for %s, $CHROME, and %s on PATH); the HTML pages above are written, "
                  "open them in a browser. Pass --chrome PATH to name one." % ("/Applications/Google Chrome.app, Chromium.app", ", ".join(CHROME_NAMES[:4])))
            return rc
        print("png: Chrome %s (headless, one-shot profile); %s x %d px, spots %s, scheme %s%s" % (
            chrome, a.width, a.height, ",".join(spots), a.scheme, "; built with --offline: system fonts only" if a.offline else ""))
        schemes = ["light", "dark"] if a.scheme == "both" else [a.scheme]
        done, bad = render_pngs(chrome, files, out, spots, schemes, a.width, a.height, a.scale)
        for b in bad:
            print("specimen.py: --png: %s" % b, file=sys.stderr)
        print("png: %d written, %d failed%s" % (len(done), len(bad), (" in " + str(out.resolve())) if done else ""))
        if bad:
            rc = 1
    return rc


class _Fake(object):
    pass


def _selftest():
    kit.REFERENCE_FP_PATH = kit.SCRIPTS_DIR / "__no_reference__.json"   # hermetic: no dependence on other builders' files
    import copy
    import random
    import tempfile
    from html.parser import HTMLParser
    fails = []

    def ok(cond, msg):
        if not cond:
            fails.append(msg)
            print("  FAIL", msg)

    lib = kit.load_directions(fixture=True)
    roll = draw.build_roll(lib, 77, 3, [], {}, None, False, None, False)
    roll_zh = draw.build_roll(lib, 77, 3, [], kit.parse_keep(["lead=zh"]), None, False, None, False)
    VOID = {"meta", "link", "br", "hr", "img", "input", "col", "area", "base", "source", "track", "wbr", "path", "circle", "rect"}

    class Check(HTMLParser):
        def __init__(self):
            HTMLParser.__init__(self)
            self.stack, self.errors, self.scripts_src = [], [], 0
            self.pairs = []            # (class, [child class lists]) of every .evk-k

        def handle_starttag(self, tag, attrs):
            if any(k == "src" for k, _ in attrs) and tag == "script":
                self.scripts_src += 1
            if tag not in VOID:
                self.stack.append((tag, dict(attrs).get("class", "")))

        def handle_endtag(self, tag):
            if tag in VOID:
                return
            if not self.stack or self.stack[-1][0] != tag:
                self.errors.append("unexpected </%s> (open: %s)" % (tag, self.stack[-3:]))
                if tag in [t for t, _ in self.stack]:
                    while self.stack and self.stack[-1][0] != tag:
                        self.stack.pop()
                    self.stack.pop()
            else:
                self.stack.pop()

    def lead_order(page):
        """For every bilingual pair (.evk-k with two spans) the class of its FIRST child."""
        firsts = []
        for m in re.finditer(r'<(?:span|p|a) class="evk-k[^"]*">(<span class="(en|cn)"[^>]*>[^<]*</span>)(<span class="(en|cn)")?', page):
            if m.group(3):
                firsts.append(m.group(2))
        return firsts

    # a venue of the awkward kinds: bare-string names, a missing side, an entity in an open area, one at a point, no colour
    tough = {"unit": "m", "name": "Riverside Library", "event": {"cn": "河畔书市"},
             "terms": {"booth": {"en": "stall", "cn": "摊位"}},
             "floors": [{"id": "G", "level": 0, "name": {"en": "Ground", "cn": "底层"}, "outline": [[0, 0], [20, 0], [20, 12], [0, 12]],
                         "rooms": [{"id": "R1", "label": "Reading", "name": "Reading Room", "poly": [[0, 0], [8, 0], [8, 12], [0, 12]], "doors": [[8, 6, 1.2]]}],
                         "areas": [{"id": "ARC", "kind": "corridor", "name": {"en": "Arcade", "cn": "拱廊"}, "poly": [[8, 0], [20, 0], [20, 12], [8, 12]]}]}],
             "entities": [
                 {"id": "a", "name": "Bookbinders", "color": "#8C1515", "room": "R1", "booth": "01"},
                 {"id": "b", "name": {"cn": "旧书摊"}, "color": "#2F8F6B", "room": "ARC", "booth": "02"},
                 {"id": "c", "name": {"en": "A very long name that wraps over several lines in a narrow cell", "cn": "一个很长很长很长的名字用来看换行"},
                  "room": "ARC", "booth": "03"},
                 {"id": "d", "name": {"en": "Kiosk", "cn": "报亭"}, "color": "#1F6FB2", "floor": "G", "at": [10, 3], "booth": "K1"}]}

    with tempfile.TemporaryDirectory() as td:
        old = (kit.ASSETS_DIR,)
        vp = Path(td) / "venue.json"
        vp.write_text(json.dumps(tough, ensure_ascii=False), encoding="utf-8")
        # 1. real assets (if the kit is complete) or whatever exists; 2. an empty assets dir -> graceful
        for label, assets_dir in (("kit assets", kit.ASSETS_DIR), ("no assets", Path(td) / "nowhere")):
            kit.ASSETS_DIR = assets_dir
            for rl, lead in ((roll, "en"), (roll_zh, "zh")):
                for i, c in enumerate(rl["cards"], 1):
                    for venue_path in (None, str(vp)):
                        tag = "%s/%s/%s" % (label, lead, "venue" if venue_path else "demo")
                        a = Assets(c["direction"], venue_path)
                        page = build_page(c, rl, i, 3, a, True)
                        ck = Check()
                        ck.feed(page)
                        ok(not ck.errors, "%s: html balanced (%s)" % (tag, ck.errors[:2]))
                        ok(ck.scripts_src == 0, "%s: no external script" % tag)
                        ok("<style id=\"evk-tokens\">" in page and "--paper:" in page, "%s: tokens inlined" % tag)
                        ok(c["code"] in page and "Contrast, light and dark" in page, "%s: footer lists the card" % tag)
                        ok("http://" not in re.sub(r'xmlns="http://www.w3.org/2000/svg"', "", page) and "https://" not in page, "%s: no network reference when offline" % tag)
                        ok(('<html lang="%s"' % ("zh-CN" if lead == "zh" else "en")) in page and ('data-evk-lead="%s"' % lead) in page, "%s: <html> carries lang and data-evk-lead" % tag)
                        firsts = lead_order(page)
                        ok(firsts and set(firsts) == {"cn" if lead == "zh" else "en"}, "%s: every bilingual pair is written %s first (%s)" % (tag, lead, sorted(set(firsts))))
                        ok(not re.search(r"\bF(2[89]|[3-9]\d)\b", page), "%s: no floor rule that does not exist (F01-F27)" % tag)
                        if label == "no assets":
                            ok("Missing kit files" in page, "no assets: banner shown")
                        if venue_path:
                            ok("Riverside Library" in page and "河畔书市" in page and "Bookbinders" in page and "旧书摊" in page, "%s: the project's names are on the page" % tag)
                            ok("Orbital" not in page and "Harbour" not in page and "港湾" not in page, "%s: nothing of the demo is left" % tag)
                            ok(page.count('class="evk-cell"') == 4, "%s: one grid cell per entity (%d)" % (tag, page.count('class="evk-cell"')))
                            ok("Arcade" in page or "拱廊" in page, "%s: an open area is known to the page" % tag)
                        lint_floor = __import__("lint_floor")
                        css_only = re.search(r'<style id="evk-tokens">\n(.*?)</style>', page, re.S).group(1)
                        rep = lint_floor.lint_tokens_text(css_only)
                        ok(rep.ok, "%s: inlined tokens pass lint" % tag)
        kit.ASSETS_DIR = old[0]
        # the entity picked for the long page: longest name by default, --entity by id
        ph = build_page(roll["cards"][0], roll, 1, 3, Assets("varsity", str(vp)), True)
        ok("A very long name that wraps" in ph.split('id="reading"')[1].split("</h2>")[0], "long page: the longest name is the default sample")
        ph = build_page(roll["cards"][0], roll, 1, 3, Assets("varsity", str(vp)), True, "d")
        ok("Kiosk" in ph.split('id="reading"')[1].split("</h2>")[0], "long page: --entity picks the entity")
        # FIX-SPEC-3 B: terms.room.cn is empty by design; the room count is rooms only; the labels fall back to words
        z2 = {"unit": "m", "name": {"en": "Science Building", "cn": "科技楼"}, "event": {"en": "Science Festival", "cn": "科学节"},
              "terms": {"booth": {"en": "booth", "cn": "展位"}, "room": {"en": "Room", "cn": ""}},
              "floors": [{"id": "1F", "level": 1, "name": {"en": "First", "cn": "一层"}, "outline": [[0, 0], [30, 0], [30, 20], [0, 20]],
                          "lobby": {"at": [2, 2], "name": {"en": "Lobby", "cn": "门厅"}},
                          "rooms": [{"id": "101", "label": "101", "name": {"en": "Lab", "cn": "实验室"}, "poly": [[0, 0], [10, 0], [10, 10], [0, 10]], "doors": [[10, 5, 1]]},
                                    {"id": "102", "label": "102", "name": {"en": "Lab 2", "cn": "实验室二"}, "poly": [[10, 0], [20, 0], [20, 10], [10, 10]], "doors": [[10, 5, 1]]}],
                          "areas": [{"id": "HALL", "kind": "open", "name": {"en": "Hall", "cn": "大厅"}, "poly": [[0, 10], [30, 10], [30, 20], [0, 20]]},
                                    {"id": "W", "kind": "corridor", "name": {"en": "West corridor", "cn": "西走廊"}, "poly": [[20, 0], [30, 0], [30, 10], [20, 10]]}]}],
              "entities": [{"id": "b01", "booth": "01", "name": {"en": "Egg Drop", "cn": "鸡蛋撞地球"}, "color": "#A9BCD0", "room": "HALL"},
                           {"id": "b02", "booth": "02", "name": {"en": "Bridges", "cn": "桥梁"}, "color": "#2F8F6B", "room": "101"},
                           {"id": "b03", "booth": "03", "name": {"en": "Lenses", "cn": "透镜"}, "room": "102"}]}
        zp = Path(td) / "z2.json"
        zp.write_text(json.dumps(z2, ensure_ascii=False), encoding="utf-8")
        for lead_, rl_ in (("en", roll), ("zh", roll_zh)):
            pg = build_page(rl_["cards"][0], rl_, 1, 3, Assets("varsity", str(zp)), True)
            nums = re.findall(r'<div class="evk-stat"><b class="n">(\d+)</b>', pg)
            ok(nums == ["01", "03", "02"], "%s: stats are floors / booths / ROOMS ONLY (two rooms, one open area, one corridor, one lobby): %s" % (lead_, nums))
            stats = pg.split('class="evk-stats"')[1].split("</section>")[0]
            ok("房间" in stats and ">Room<" not in stats and "Rooms" in stats, "%s: the empty terms.room.cn falls back to 房间, never to the English word: %s" % (lead_, re.sub(r"<[^>]+>", "|", stats)[:120]))
            ok("Booths" in stats and "展位" in stats, "%s: booths from terms" % lead_)
        only_areas = json.loads(json.dumps(z2))
        only_areas["floors"][0]["rooms"] = []
        only_areas["entities"] = [e for e in only_areas["entities"] if e["room"] == "HALL"]
        zp.write_text(json.dumps(only_areas, ensure_ascii=False), encoding="utf-8")
        pg = build_page(roll["cards"][0], roll, 1, 3, Assets("varsity", str(zp)), True)
        ok(re.findall(r'<div class="evk-stat"><b class="n">(\d+)</b>', pg) == ["01", "01", "02"] and "Areas" in pg.split('class="evk-stats"')[1].split("</section>")[0],
           "a venue with no rooms counts its open areas and says Areas")
        ok(plural("Booth") == "Booths" and plural("Gallery") == "Galleries" and plural("Box") == "Boxes" and cap("booth") == "Booth", "plural / cap")
        ok(term_words({"terms": {"room": {"en": "Room", "cn": ""}}}, "room", "Room", "房间") == ("Room", "房间")
           and term_words({"terms": {"room": {"en": "Room", "cn": ""}}}, "room", "Room", "房间", True) == ("Room", "")
           and term_words({}, "booth", "booth", "展位") == ("booth", "展位") and term_words({"terms": {"booth": "展位"}}, "booth", "booth", "x") == ("booth", "展位"), "term_words")
        # bad venues stop the build with ValueError (the CLI turns it into exit 2)
        for bad, why in (("{", "invalid JSON"), ('{"floors": []}', "no floors"), ('{"floors": [{"id": "1"}], "entities": []}', "no entities")):
            (Path(td) / "bad.json").write_text(bad, encoding="utf-8")
            try:
                Assets("varsity", str(Path(td) / "bad.json"))
                ok(False, "--venue with %s should be rejected" % why)
            except ValueError:
                pass
        # online build mentions the font loader
        c = roll["cards"][0]
        page = build_page(c, roll, 1, 3, Assets(c["direction"]), False)
        ok("fonts.googleapis.com" in page, "online build has the font loader")
        # CLI
        out = Path(td) / "sp"
        rp = Path(td) / "roll.json"
        draw.write_roll(roll_zh, rp)
        with draw._quiet():
            rc = main([str(rp), "--all", "--out", str(out), "--offline"])
        ok(rc == 0 and (out / "index.html").exists() and len(list(out.glob("card-*.html"))) == 3, "CLI writes 3 pages and an index")
        with draw._quiet():
            rc = main([str(rp), "--all", "--out", str(out), "--offline", "--venue", str(vp)])
        ok(rc == 0 and "Riverside Library" in next(out.glob("card-1-*.html")).read_text(encoding="utf-8"), "CLI --venue builds from the project's venue")
        with draw._quiet():
            ok(main([str(rp), "--card", "9", "--out", str(out)]) == 2, "bad card number -> 2")
            ok(main([str(rp), "--out", str(out), "--venue", str(Path(td) / "nope.json")]) == 2, "unreadable --venue -> 2")
            ok(main([str(rp), "--out", str(out), "--entity", "a"]) == 2, "--entity without --venue -> 2")
            ok(main([str(rp), "--out", str(out), "--venue", str(vp), "--entity", "zzz"]) == 2, "unknown --entity -> 2")
    # --- FIX-SPEC-4 item 2: venue.event is a string, {en, cn}, or {name, date, time, place, note}; CJK sentences carry no space between two CJK characters
    ok(event_name({"event": "Open Day", "name": "Hall"}) == ("Open Day", "Open Day")
       and event_name({"event": {"en": "Fair", "cn": "博览会"}}) == ("Fair", "博览会")
       and event_name({"event": {"name": {"en": "Fair", "cn": "博览会"}, "date": "2026-10-24"}}) == ("Fair", "博览会")
       and event_name({"event": {"name": "Open Day", "time": "10:00"}}) == ("Open Day", "Open Day")
       and event_name({"event": {"date": "2026-10-24"}, "name": {"en": "Hall", "cn": "大厅"}}) == ("Hall", "大厅")
       and event_name({"name": "Hall"}) == ("Hall", "Hall") and event_name({}, {"en": "D", "cn": "默"}) == ("D", "默"), "event_name reads a string, {en, cn} and {name, ...}")
    ok(autospace("二层 东回廊") == "二层东回廊" and autospace("Lab实验室2号") == "Lab 实验室 2 号" and autospace("07 号展位") == "07 号展位"
       and autospace("在 二层 ，东") == "在二层，东" and autospace(autospace("A 甲b")) == autospace("A 甲b"), "autospace: none between two CJK, one at a CJK / Latin edge, idempotent")
    ev_venue = json.loads(json.dumps(tough))
    ev_venue["event"] = {"name": {"en": "Riverside Book Fair", "cn": "河畔书市"}, "date": "2026-10-24", "time": "10:00-17:00"}
    ev_venue["floors"][0]["name"] = {"en": "Second", "cn": "二层"}
    ev_venue["floors"][0]["areas"][0]["name"] = {"en": "East gallery", "cn": "东回廊"}
    ev_venue["entities"][1]["name"] = {"en": "Old Books", "cn": "旧书摊"}
    with tempfile.TemporaryDirectory() as td2:
        evp = Path(td2) / "ev.json"
        evp.write_text(json.dumps(ev_venue, ensure_ascii=False), encoding="utf-8")
        for rl_, lead_ in ((roll, "en"), (roll_zh, "zh")):
            pg = build_page(rl_["cards"][0], rl_, 1, 3, Assets("varsity", str(evp)), True, "b")
            ok("Riverside Book Fair" in pg and "河畔书市" in pg and "<title>EVK specimen" in pg, "%s: event {name, date, time} gives the name" % lead_)
            rd = pg.split('id="reading"')[1].split("</article>")[0]
            ok("在二层东回廊" in rd, "%s: the summary sentence reads 在二层东回廊 (no space between CJK characters)" % lead_)
            ok(not re.search(r"[㐀-鿿][ \t]+[㐀-鿿]", re.sub(r"<[^>]+>", "|", rd)), "%s: no space between two CJK characters in the long page" % lead_)
        vp2 = Path(td2) / "tough.json"
        vp2.write_text(json.dumps(tough, ensure_ascii=False), encoding="utf-8")
        pg = build_page(roll["cards"][0], roll, 1, 3, Assets("varsity", str(vp2)), True)
        ok("Riverside Library" in pg and "河畔书市" in pg, "event {cn} only (no name key): the text form still works")
        # props: a button, the data, the off switch; a card without props has none of it
        cp = json.loads(json.dumps(roll["cards"][0]))
        cp["params"]["props"] = [{"name": "leaf", "var": "--prop-leaf", "off": "none", "what": "叶形标签"}]
        pg_on = build_page(cp, roll, 1, 3, Assets("varsity", str(evp)), True)
        pg_off = build_page(cp, roll, 1, 3, Assets("varsity", str(evp)), True, None, "off")
        ok('id="spx-props"' in pg_on and 'aria-pressed="false"' in pg_on.split('id="spx-props"')[1][:60] and '"off": false' in pg_on and "/* --prop-leaf: none;" in pg_on
           and not re.search(r"^\s*--prop-leaf:", pg_on, re.M), "props on (default): a Props button, the data, the switch as a commented line")
        ok('"off": true' in pg_off and re.search(r"^\s*--prop-leaf: none;", pg_off, re.M) and 'aria-pressed="true"' in pg_off.split('id="spx-props"')[1][:60] and "Props: off" in pg_off,
           "--props off: live declarations, the button says off")
        ok("--prop-leaf" in pg_on.split('id="params"')[1] and "叶形标签" in pg_on.split('id="params"')[1], "the parameter footer lists the props")
        ok('id="spx-props"' not in pg and "spx-props-data" in pg and '"props": []' in pg, "a card without props: no button, an empty props list")
        # --png: no Chrome, a bad spot, a bad --chrome; and the whole pipeline with a stand-in Chrome that writes a 1x1 PNG
        rpz = Path(td2) / "roll.json"
        draw.write_roll(roll, rpz)
        import io
        import contextlib
        outp = Path(td2) / "p"

        def run_cli(argv):
            buf, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
                rc_ = main(argv)
            return rc_, buf.getvalue(), err.getvalue()
        saved_find = find_chrome
        globals()["find_chrome"] = lambda explicit=None: None
        try:
            rc_, so, se = run_cli([str(rpz), "--card", "1", "--out", str(outp), "--offline", "--png"])
        finally:
            globals()["find_chrome"] = saved_find
        ok(rc_ == 0 and "no Chrome or Chromium found" in so and (outp / ("card-1-%s.html" % roll["cards"][0]["direction"])).exists() and not list(outp.glob("*.png")),
           "--png without a Chrome: says so, writes the HTML, exits 0 (%s)" % rc_)
        ok(run_cli([str(rpz), "--out", str(outp), "--png", "--png-at", "nowhere"])[0] == 2, "--png-at with an unknown spot -> 2")
        ok(run_cli([str(rpz), "--out", str(outp), "--png", "--chrome", str(Path(td2) / "no-chrome")])[0] == 2, "--chrome that is not a file -> 2")
        ok(run_cli([str(rpz), "--out", str(outp), "--png", "--width", "50"])[0] == 2, "--width out of range -> 2")
        ok(find_chrome(str(Path(td2) / "no-chrome")) is None and find_chrome(__file__) == __file__, "find_chrome(explicit) takes a file or nothing")
        ok(png_name("card-1-airmail.html", "route", "dark") == "card-1-airmail-route-dark.png" and set(PNG_SPOTS) >= {"top", "route", "map", "reading"}, "png_name / spots")
        hs = png_harness("file:///x/card.html?static=1&theme=dark#route", 390, 1800)
        ok('width:390px;height:1800px' in hs and 'src="file:///x/card.html?static=1&amp;theme=dark#route"' in hs, "the harness frames the page at exactly width x height")
        cc = chrome_cmd("/c/chrome", "/tmp/prof", "/tmp/o.png", "file:///h.html", 390, 1800, 2.0)
        ok(cc[0] == "/c/chrome" and "--headless=new" in cc and "--window-size=390,1800" in cc and "--virtual-time-budget=4000" in cc and "--screenshot=/tmp/o.png" in cc
           and "--force-device-scale-factor=2" in cc and "--force-prefers-reduced-motion" in cc and "--user-data-dir=/tmp/prof" in cc and cc[-1] == "file:///h.html", "chrome_cmd: headless=new, window size, virtual time, screenshot, own profile")
        if os.name == "posix":
            import struct
            import zlib
            fake = Path(td2) / "fake-chrome"
            log = Path(td2) / "fake.log"
            fake.write_text("#!%s\nimport sys, struct, zlib\nargs = sys.argv[1:]\nout = [a for a in args if a.startswith('--screenshot=')][0].split('=', 1)[1]\n"
                            "open(%r, 'a').write(' '.join(args) + '\\n')\n"
                            "def ch(t, d):\n    c = struct.pack('>I', len(d)) + t + d\n    return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)\n"
                            "open(out, 'wb').write(b'\\x89PNG\\r\\n\\x1a\\n' + ch(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) + ch(b'IDAT', zlib.compress(b'\\x00\\xff\\xff\\xff')) + ch(b'IEND', b''))\n" % (sys.executable, str(log)),
                            encoding="utf-8")
            fake.chmod(0o755)
            rc_, so, se = run_cli([str(rpz), "--card", "2", "--out", str(outp), "--offline", "--png", "--chrome", str(fake), "--scheme", "light", "--png-at", "top,route,reading", "--width", "360", "--height", "1200"])
            d2 = roll["cards"][1]["direction"]
            made = sorted(x.name for x in outp.glob("card-2-*.png"))
            ok(rc_ == 0 and made == ["card-2-%s-%s-light.png" % (d2, sp) for sp in ("reading", "route", "top")] and "3 written, 0 failed" in so, "--png with a Chrome: one PNG per spot and scheme (%s, rc %s)" % (made, rc_))
            calls = log.read_text(encoding="utf-8").splitlines()
            ok(len(calls) == 3 and all("--window-size=360,1200" in c or "--window-size=360,844" in c for c in calls) and sum("--window-size=360,844" in c for c in calls) == 1,
               "…route is shot at phone height, the others at --height")
            rc_, so, se = run_cli([str(rpz), "--card", "2", "--out", str(outp), "--offline", "--png", "--chrome", str(fake), "--png-at", "top"])
            ok(rc_ == 0 and sorted(x.name for x in outp.glob("card-2-*-top-*.png")) == ["card-2-%s-top-dark.png" % d2, "card-2-%s-top-light.png" % d2], "--scheme both (default): a light and a dark PNG")
            bad = Path(td2) / "bad-chrome"
            bad.write_text("#!%s\nimport sys\nsys.exit(3)\n" % sys.executable, encoding="utf-8")
            bad.chmod(0o755)
            rc_, so, se = run_cli([str(rpz), "--card", "2", "--out", str(outp), "--offline", "--png", "--chrome", str(bad), "--png-at", "map", "--scheme", "dark"])
            ok(rc_ == 1 and "wrote no PNG" in se and "0 written, 1 failed" in so, "a Chrome that writes nothing: reported on stderr, exit 1 (HTML kept)")

    ok(K("A", "甲", lead="zh").index('class="cn"') < K("A", "甲", lead="zh").index('class="en"') and K("A", "甲").index('class="en"') < K("A", "甲").index('class="cn"'), "K writes the lead language first")
    ok(K("Same", "Same").count("lang=") == 1 and K("同", "同").count("lang=") == 1, "a pair with one string is one line")
    ok(tx("x") == ("x", "x") and tx({"cn": "甲"}) == ("甲", "甲") and tx({"en": "A"}) == ("A", "A") and tx(None) == ("", ""), "tx handles the schema's text forms")
    if fails:
        print("specimen.py selftest: %d FAILED" % len(fails))
        return 1
    print("specimen.py selftest: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
