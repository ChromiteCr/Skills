#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""event-venue-kit :: starter.py -- a working site skeleton from a venue and the chosen card.  从场地数据长出一套能用的页面骨架。

    starter.py <venue.json> <roll.json> <out-dir> [--card N] [--force] [--force-assets] [--no-routes] [--dry-run]
    starter.py --selftest
    from starter import render;  render(venue: dict, card: dict, out_dir: Path, force: bool = False, force_assets: bool = False,
                                        static_routes: bool = True) -> list[Path]

install.py calls render() when you pass `--starter --venue data/venue.json`; this CLI does the same by itself (the chosen card of the roll,
or --card N). It writes, under <out-dir> (the folder install.py filled with evk/):

  index.html         the bar and nav; a welcome with the event name, date, time and place (anything missing is printed as
                     "待定 / TBA", never invented), the stats, a live map preview, a search box + floor control + the entity grid
                     grouped by floor (or by tag, or by room: event.group_by), with an empty state
  map.html           the map; a floor control; a search box; the directions sheet (start select [entrances, lobbies, rooms, open areas]
                     + a target search through EVK.search + Back / Overview / Next + a polite live region); the room / entity sheet;
                     URL state ?s= ?r= ?f= ?to= ?from=; the last start remembered in localStorage (inside try/catch); and a static
                     directory of every room and entity, which is the whole page when JavaScript is off
  e/<id>.html        one page per entity: the head in the card's entity_header form (the recipe draws it from <html data-evk-entity-header>;
                     the DOM keeps the name pair together: eyebrow, primary name, other-language name, then the rule, the code and the line
                     about the entity), a data strip from entity.facts (none if it has none), the reading content from entity.parts and
                     entity.blocks (else one placeholder part marked "示意 / Placeholder"), a "How to get here / 怎么走" part (below), a
                     "Where" part with a small map focused on the entity, a link to map.html?to=<id>, prev / next
  assets/starter.css layout glue for the above: tokens only, no colours, no font names
  assets/starter.js  the behaviour (copy of assets/starter/starter.js); its first block is the dictionary of words (UI), shared with this script
  data/venue.js      window.EVK_VENUE = the venue (a script, so the pages open from file://). Rebuild after editing venue.json.

HOW TO GET HERE  Every entity page has a "How to get here / 怎么走" part with the written route (the same steps as the map's directions
sheet) from the venue's main entrance (the first floor, by level, that has an `entrance`) and, in a closed <details>, from the lobby on the
entity's own floor if it has one. The build asks the engine for them: `node evk/engine/wayfind.js --describe-all venue.json --from entrance:1F`
(the project's copy of the engine, else the kit's) -- when `node` is on PATH. They are an <ol class="evk-r-steps"> whose climb steps are
`li.is-climb` (the climb colour, DR-6). Without Node (or when the call fails: a warning says why) the part holds the map link only and starter.js
writes the same <ol> in the browser from the same engine; --no-routes (static_routes=False) asks for exactly that. Each box is
`<div class="sp-route" data-from="entrance:1F">`; a link "Show on the map" opens map.html?to=<id>&from=<start id> with the route running.

LOCATION CODES  One format everywhere (tags on the cards, the entity head, the sheets, the search list): "<floor short>·<booth>" -- "2F·L02",
"2 层·L02". Booth numbers that repeat on a floor (numbered per room: 01 in every room) cannot make a code alone, so for such a venue the room's
number goes between them ("2F·203·02"), on every page. A `label` of an open area is a display name (the map plate, headings), never a code.

Every page loads evk/tokens.css, evk/base.css, evk/recipe.css, assets/starter.css, then (end of body) data/venue.js and the engine in the
order tones, search, spring, sheet, part-nav, wayfind, venue-map, then assets/starter.js. All static content is rendered here, at build time:
a page is complete and readable with JavaScript off, and the script only adds search, the map, sheets and directions.

The venue is the one in assets/engine/venue.schema.json. Optional extras read here: event {name, date, time, place, note, group_by}, entity.group,
floors[].short {en, cn} (the floor in route sentences, chips, tags and location lines) and floors[].name (headings), terms.tags
{tag: text}, entity.blurb, entity.facts [{n, unit, label}], entity.parts [{title, text, blocks}], entity.blocks, and the x- keys
x-schematic (a banner + noindex) and x-groups (search group words, also the groups of group_by = tag).
Bilingual pairs are written PRIMARY LANGUAGE FIRST, from the card's `lead`.

READING BLOCKS  (entity.blocks, parts[].blocks; reading.md §3, closed vocabulary, rendered as classes evk-r-<type>). Every `text` is a
string or {en, cn}; `type` may be written `t`. A block with a `title` starts a new part of its own at the top level of entity.blocks
(untitled blocks join the part before them: the last of entity.parts, or an "About / 简介" part when there is none) and is a small
heading inside a part; entity.parts come first, then the parts that entity.blocks make.
    {"type":"p","text":text | [text, ...]}                       {"type":"note","text":text}
    {"type":"quote","text":text,"by":text}                      {"type":"list","items":[text],"ordered":false}
    {"type":"facts","items":[{"k":text,"v":text}]}              {"type":"cards","items":[{"title":text,"meta":text,"text":text}]}
    {"type":"steps","items":[text | {"title":text,"text":text}]}
    {"type":"table","caption":text,"head":[text],"rows":[[text]]}   (every row as long as the head)
    {"type":"timeline","items":[{"at":"10:30","text":text,"title":text}]}
    {"type":"numbers","items":[{"n":"46","unit":text,"label":text,"note":text}]}      (the note -- the year, "about", the list's edition -- is printed under the label)
    {"type":"qa","items":[{"q":text,"a":text | [text, ...]}]}   (an answer is a text, an {en, cn} pair, or a list of paragraphs: one <p> each)
    {"type":"fold","title":text,"blocks":[...],"open":false}
A bad block stops the build with the entity and the position ("entity kelp: blocks[2] (timeline) item 1 has no 'at'").

GROUPING  event.group_by = "floor" (default) | "tag" | "room": how the home page's grid is grouped. `tag` groups by x-groups entries that
have `tags` / `ids` / `rooms` / `floors` or else by each entity's first tag; the label is the entry's label / name, terms.tags[tag]
({en, cn}), the entry's words (first Chinese word, first Latin word) or the tag id in title case. A second control (#seg-group, its labels in both
languages, scrolling inside itself) and `?g=<key>` filter by the group; the floor control stays. `room` groups by room or open area.
One entity is in ONE group: `entity.group` (an x-groups `id`, else the slug of its first tag; or a terms.tags key when there is no x-groups) wins;
else the entry that lists its id, then the one that has its FIRST tag, then its room, its floor, and last its other tags. An entity that fits
several groups gets a build warning naming them (set `entity.group`). x-groups `words` only ever find the entities the build put in the group
(data/venue.js lists them as `ids`): a tag that merely equals a group's tag is not a member, and a group without `words` adds nothing to the search.

YOUR COPIES OF assets/starter.js AND assets/starter.css  The words of the pages are read from the PROJECT copy <out-dir>/assets/starter.js
(its /* ui:begin */ ... /* ui:end */ block, over the kit's: a word the project copy lacks falls back to the kit's) when that file
exists, else from the kit. render() rewrites the generated pages (with force) but never overwrites assets/starter.js or
assets/starter.css when they already exist in the project: those are yours. --force-assets (force_assets=True) replaces them with the
kit's copies. So the cycle is: change a word in assets/starter.js, run starter.py with --force, and the static pages carry it.

Never overwrites an existing page without force: all conflicts are listed (StarterConflict, a FileExistsError, .paths) and nothing is written.
Browsers cache stylesheets and scripts: after a rebuild add ?v= to the asset URLs, or hard-refresh.
Exit code: 0 ok; 1 selftest failed; 2 usage / input error / conflicts without --force.
"""
from __future__ import annotations

import argparse
import datetime
import html as _html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit  # noqa: E402

STARTER_DIR = kit.ASSETS_DIR / "starter"
ENGINE_ORDER = ["tones.js", "search.js", "spring.js", "sheet.js", "part-nav.js", "wayfind.js", "venue-map.js"]
_CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
_SP1 = re.compile(r"([\u3400-\u9fff\uf900-\ufaff])([A-Za-z0-9])")
_SP2 = re.compile(r"([A-Za-z0-9])([\u3400-\u9fff\uf900-\ufaff])")
_UI_RE = re.compile(r"/\*\s*ui:begin\s*\*/(.*?)/\*\s*ui:end\s*\*/", re.S)
_WD_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MON_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_WD_CN = "一二三四五六日"


class StarterConflict(FileExistsError):
    """Files the starter would write already exist (and force is off). .paths lists them; nothing was written."""

    def __init__(self, paths):
        self.paths = [Path(p) for p in paths]
        super(StarterConflict, self).__init__("refusing to overwrite %d existing file(s) (nothing written): %s%s" % (
            len(self.paths), ", ".join(str(p) for p in self.paths[:6]), " ..." if len(self.paths) > 6 else ""))


# --------------------------------------------------------------------------------------------------
# text helpers
# --------------------------------------------------------------------------------------------------

def esc(s):
    return _html.escape(str(s), quote=True)


def has_cjk(s):
    return bool(_CJK.search(str(s)))


def spaced(s):
    """One space between CJK and an adjacent Latin letter or digit, both ways (the same rule as EVK.spaced)."""
    return _SP2.sub(r"\1 \2", _SP1.sub(r"\1 \2", str(s)))


def cap(s):
    return s[:1].upper() + s[1:] if s else s


def plural(w):
    if re.search(r"[^aeiou]y$", w, re.I):
        return w[:-1] + "ies"
    if re.search(r"(s|x|ch|sh)$", w, re.I):
        return w + "es"
    return w + "s"


def tx(v):
    """A schema `text` (a string, or {en, cn} with either side missing) -> (en, cn); a missing side falls back to the other."""
    if isinstance(v, str):
        return v, v
    if isinstance(v, dict):
        en, cn = str(v.get("en") or ""), str(v.get("cn") or "")
        return en or cn, cn or en
    return "", ""


def ls(en, cn, lead):
    """The two languages in reading order, PRIMARY FIRST: [(text, class, lang), ...]. One line when they match or one is missing."""
    en, cn = en or "", cn or ""
    if not en or not cn or en == cn:
        t = en or cn
        return [(spaced(t), "cn", "zh-CN")] if has_cjk(t) else [(t, "en", "en")]
    a, b = (spaced(cn), "cn", "zh-CN"), (en, "en", "en")
    return [a, b] if lead == "zh" else [b, a]


def spans(en, cn, lead):
    return "".join('<span class="%s" lang="%s">%s</span>' % (c, l, esc(t)) for t, c, l in ls(en, cn, lead))


def js_json(obj):
    """JSON for a <script> or a .js file: no raw </ or <!--, no U+2028 / U+2029."""
    return (json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
            .replace("</", "<\\/").replace("<!--", "<\\!--").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def _ui_of(path):
    t = Path(path).read_text(encoding="utf-8")
    m = _UI_RE.search(t)
    if not m:
        raise ValueError("%s has no /* ui:begin */ ... /* ui:end */ block" % path)
    try:
        ui = json.loads(m.group(1))
    except ValueError as e:
        raise ValueError("%s: the UI block is not valid JSON (%s)" % (path, e))
    if not isinstance(ui, dict):
        raise ValueError("%s: the UI block is not an object" % path)
    return ui


def project_assets(out_dir):
    """{'starter.css': Path, 'starter.js': Path} of the files already in the project (<out>/assets/): your copies."""
    a = Path(out_dir) / "assets"
    return {n: a / n for n in ("starter.css", "starter.js") if (a / n).is_file()}


def load_ui(out_dir=None):
    """The dictionary of words: the UI block at the top of assets/starter/starter.js, one source for the script and the static pages.
    With out_dir, the project's own copy <out_dir>/assets/starter.js is read when it exists and its words win over the kit's (a word
    it lacks, say one added to the kit after the project was made, is the kit's)."""
    ui = _ui_of(STARTER_DIR / "starter.js")
    if out_dir is not None:
        mine = project_assets(out_dir).get("starter.js")
        if mine:
            ui.update(_ui_of(mine))
    return ui


def slug(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(s)).strip("-.") or "entity"


def width_em(s):
    return sum(1.0 if has_cjk(c) else 0.5 for c in str(s))


def name_fit(s):
    """The name-fit ladder of base.css (data-fit): bigger for short names, smaller for long ones (原站取值 <= 4, 7, 12 em)."""
    w = width_em(s)
    return 0 if w <= 4 else 2 if w <= 7 else 3 if w <= 12 else 4


def fmt_date(s):
    """'2026-10-24' -> ('Sat 24 Oct 2026', '2026 年 10 月 24 日（周六）'); anything else is left as it is."""
    m = re.fullmatch(r"\s*(\d{4})-(\d{2})-(\d{2})\s*", str(s))
    if m:
        try:
            d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
        return ("%s %d %s %d" % (_WD_EN[d.weekday()], d.day, _MON_EN[d.month - 1], d.year),
                "%d 年 %d 月 %d 日（周%s）" % (d.year, d.month, d.day, _WD_CN[d.weekday()]))
    return None


def point_in(poly, x, y):
    c = False
    j = len(poly) - 1
    for i in range(len(poly)):
        a, b = poly[i], poly[j]
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            c = not c
        j = i
    return c


def poly_of(it):
    if it.get("poly"):
        return [(float(p[0]), float(p[1])) for p in it["poly"]]
    r = it.get("rect")
    if r:
        x, y, w, h = (float(n) for n in r)
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    return []


# --------------------------------------------------------------------------------------------------
# the site: the venue, the card, and every page
# --------------------------------------------------------------------------------------------------

BLOCK_TYPES = ("p", "facts", "cards", "steps", "table", "timeline", "numbers", "qa", "quote", "list", "note", "fold")
GROUP_BY = ("floor", "tag", "room")
KIND_OF = {"orbit": "rotate", "exploded": "rotate", "oblique": "pan", "plan": "plan"}     # what the card calls its view (words map_what / map_view): 3D | oblique | plan
KIND_SUFFIX = {"rotate": "", "pan": "_pan", "plan": "_plan"}
# What ONE-FINGER DRAG does per projection (the words map_hint / map_drag): rotate | pan. This is the engine's constant (venue-map.js, VenueMap
# dragMode(), VenueMap.DRAG_MODE): the plan turns in its plane under a finger, only the oblique projection pans. engine_drag_modes() reads the
# engine's own table; starter.js asks the map itself (dragMode()) and corrects the words if the two ever differ.
DRAG_OF = {"orbit": "rotate", "exploded": "rotate", "oblique": "pan", "plan": "rotate"}
DRAG_SUFFIX = {"rotate": "", "pan": "_pan"}
CLIMB_KINDS = ("stairs", "lift")


def engine_drag_modes():
    """{projection: 'rotate' | 'pan'} as assets/engine/venue-map.js declares it (`VenueMap.DRAG_MODE = Object.freeze({orbit: "rotate", …})`), else DRAG_OF."""
    try:
        src = (kit.ASSETS_DIR / "engine" / "venue-map.js").read_text(encoding="utf-8")
        m = re.search(r"\.DRAG_MODES?\s*=\s*(?:Object\.freeze\(\s*)?\{([^}]*)\}", src)
        got = dict(re.findall(r"[\"']?(\w+)[\"']?\s*:\s*[\"'](rotate|pan)[\"']", m.group(1))) if m else {}
        return dict(DRAG_OF, **{k: v for k, v in got.items() if k in DRAG_OF})
    except (OSError, ValueError):
        return dict(DRAG_OF)


class Site(object):
    def __init__(self, venue, card, ui=None, out_dir=None, static_routes=True):
        if not isinstance(venue, dict) or not isinstance(venue.get("floors"), list) or not venue["floors"]:
            raise ValueError("the venue has no floors (see assets/engine/venue.schema.json)")
        if not isinstance(venue.get("entities"), list) or not venue["entities"]:
            raise ValueError("the venue has no entities: the starter needs the things people look for")
        self.v = venue
        self.card = card
        self.p = card["params"]
        self.pal = self.p["palette"]
        self.lead = "zh" if self.p.get("lead") == "zh" else "en"
        self.other = "en" if self.lead == "zh" else "zh"
        self.ui = ui or load_ui(out_dir)
        self.proj = str((self.p.get("map") or {}).get("projection") or "orbit")
        self.kind = KIND_OF.get(self.proj, "rotate")
        self.drag = engine_drag_modes().get(self.proj, "rotate")           # what one finger does on the map in this projection
        self.out_dir = Path(out_dir) if out_dir is not None else None
        self.static_routes = static_routes
        self.warnings = []                                                   # build warnings: printed by render(), listed in render.warnings
        self._routes_cache = None
        t = venue.get("terms") or {}
        self.booth_t = tx(t["booth"]) if t.get("booth") else ("booth", "展位")
        self.room_t = tx(t["room"]) if t.get("room") else ("Room", "")
        self.tag_terms = {str(k): tx(v) for k, v in (t.get("tags") or {}).items()} if isinstance(t.get("tags"), dict) else {}
        self.venue_name = tx(venue.get("name")) if venue.get("name") else ("Venue", "场地")
        self._events()
        self._places()
        self._entities()
        self._xgroups()
        self._groups()

    # ---- words ---------------------------------------------------------------------------------
    def words(self, key, lang, **vars):
        """One string of the dictionary in lang ('en' | 'zh'). {thing} {things} {Thing} {Things} are the venue's term for an entity."""
        if key not in self.ui:
            raise KeyError("starter: no word %r in the UI block of starter.js" % key)
        u = self.ui[key]
        s = u["cn"] if lang == "zh" else u["en"]
        thing = self.booth_t[1] if lang == "zh" else self.booth_t[0]
        things = self.booth_t[1] if lang == "zh" else (thing if any(str(vars.get(k)) == "1" for k in ("n", "k")) else plural(self.booth_t[0]))     # "1 booth", "3 booths"
        base = {"thing": thing, "things": things, "Thing": cap(thing), "Things": cap(things)}
        for k in ("hint", "drag", "what", "view"):              # hint / drag follow what ONE FINGER does (rotate | pan), what / view the card's projection
            w = self.ui.get("map_" + k + (DRAG_SUFFIX[self.drag] if k in ("hint", "drag") else KIND_SUFFIX[self.kind])) or self.ui.get("map_" + k)
            base[k] = (w["cn"] if lang == "zh" else w["en"]) if w else ""
        s = re.sub(r"\{(\w+)\}", lambda m: str(vars[m.group(1)]) if m.group(1) in vars else base.get(m.group(1), m.group(0)), s)
        return spaced(s) if lang == "zh" else s

    def s(self, key, **vars):
        return self.words(key, self.lead, **vars)

    def s2(self, key, **vars):
        return self.words(key, self.other, **vars)

    def pair(self, key, **vars):
        return spans(self.words(key, "en", **vars), self.words(key, "zh", **vars), self.lead)

    def K(self, key, cls="", tag="span", **vars):
        return '<%s class="evk-k%s">%s</%s>' % (tag, (" " + cls) if cls else "", self.pair(key, **vars), tag)

    def spans(self, en, cn):
        return spans(en, cn, self.lead)

    def sp(self, key, **vars):
        """A sentence in the lead language, the other language under it (muted, a block): '<span lang>…</span><span class="sp-2nd" lang>…</span>'."""
        L = ls(self.words(key, "en", **vars), self.words(key, "zh", **vars), self.lead)
        out = '<span lang="%s">%s</span>' % (L[0][2], esc(L[0][0]))
        if len(L) > 1:
            out += '<span class="sp-2nd" lang="%s">%s</span>' % (L[1][2], esc(L[1][0]))
        return out

    def lines(self, en, cn, tag1, cls1, cls2, tag2="div"):
        """A heading and its translation as two stacked elements, primary first, each with its lang."""
        L = ls(en, cn, self.lead)
        out = ['<%s class="%s" lang="%s">%s</%s>' % (tag1, cls1, L[0][2], esc(L[0][0]), tag1)]
        if len(L) > 1:
            out.append('<%s class="%s" lang="%s">%s</%s>' % (tag2, cls2, L[1][2], esc(L[1][0]), tag2))
        return "".join(out)

    def lead_text(self, en, cn):
        return (cn if self.lead == "zh" else en)

    def other_text(self, en, cn):
        return (en if self.lead == "zh" else cn)

    # ---- the event ------------------------------------------------------------------------------
    def _events(self):
        ev = self.v.get("event")
        keys = {"name", "date", "time", "place", "note", "group_by"}
        if isinstance(ev, dict) and set(ev) & keys:
            self.ev_struct = ev
            name = ev.get("name")
        else:
            self.ev_struct = {}
            name = ev
        gb = self.ev_struct.get("group_by")
        self.group_by = str(gb).strip().lower() if gb not in (None, "") else "floor"
        if self.group_by not in GROUP_BY:
            raise ValueError('event.group_by must be "floor", "tag" or "room" (got %r)' % (gb,))
        self.event_name = tx(name) if name else self.venue_name
        self.event_named = bool(name)
        sch = self.v.get("x-schematic")
        self.schematic = bool(sch)
        self.schematic_text = tx(sch) if isinstance(sch, (str, dict)) and sch else None

    def _fact(self, key):
        """date / time / place of the event as (en, cn) or None."""
        v = self.ev_struct.get(key)
        if v in (None, "", {}):
            return None
        if key == "date" and isinstance(v, str):
            d = fmt_date(v)
            if d:
                return d
        return tx(v)

    # ---- floors, rooms, areas, entities --------------------------------------------------------
    def _places(self):
        floors = sorted(self.v["floors"], key=lambda f: f.get("level", 0))
        self.floors = []
        self.floor_by = {}
        self.place_by = {}          # room or area id -> {...}
        for f in floors:
            fid = str(f["id"])
            en, cn = tx(f.get("name")) if f.get("name") else (fid, fid)
            lvl = f.get("level", 0)
            if f.get("short"):                  # the floor as route sentences, chips, tags and location lines say it ("4F" / "4 层")
                s_en, s_cn = tx(f["short"])
            else:                               # what the router says when `short` is not given: the id, and the level + " 层" (the name for level < 1)
                s_en = fid
                s_cn = ("%d 层" % lvl) if isinstance(lvl, (int, float)) and lvl >= 1 else (cn if f.get("name") else fid)
            fl = {"id": fid, "level": lvl, "en": en, "cn": cn, "s_en": s_en, "s_cn": s_cn, "rooms": [], "areas": []}
            self.floors.append(fl)
            self.floor_by[fid] = fl
            for r in f.get("rooms") or []:
                label = str(r.get("label") if r.get("label") is not None else r["id"])
                nen, ncn = tx(r.get("name")) if r.get("name") else (label, label)
                pl = {"id": str(r["id"]), "kind": "room", "area": False, "label": label, "en": nen, "cn": ncn, "floor": fid, "poly": poly_of(r)}
                fl["rooms"].append(pl)
                self.place_by[pl["id"]] = pl
            for a in f.get("areas") or []:
                label = str(a.get("label")) if a.get("label") not in (None, "") else ""
                nen, ncn = tx(a.get("name")) if a.get("name") else (label or str(a["id"]), label or str(a["id"]))
                pl = {"id": str(a["id"]), "kind": a.get("kind") or "open", "area": True, "label": label, "en": nen, "cn": ncn, "floor": fid, "poly": poly_of(a)}
                fl["areas"].append(pl)
                self.place_by[pl["id"]] = pl

    def _where_is(self, fid, pt):
        fl = self.floor_by[fid]
        for pl in fl["rooms"] + fl["areas"]:
            if pl["poly"] and point_in(pl["poly"], pt[0], pt[1]):
                return pl
        return None

    def _entities(self):
        ents, seen_pages, per_room = [], set(), {}
        for i, e in enumerate(self.v["entities"]):
            if not isinstance(e, dict) or e.get("id") in (None, "") or e.get("name") is None:
                raise ValueError("every entity needs an id and a name (bad: %r)" % (e,))
            eid = str(e["id"])
            pl = None
            if e.get("room") not in (None, ""):
                pl = self.place_by.get(str(e["room"]))
                if pl is None:
                    raise ValueError("entity %s: room %s does not exist" % (eid, e["room"]))
                fid = pl["floor"]
            else:
                fid = str(e.get("floor")) if e.get("floor") is not None else ""
                if fid not in self.floor_by or not e.get("at"):
                    raise ValueError("entity %s needs a room (a room or area id), or at + floor" % eid)
                pl = self._where_is(fid, (float(e["at"][0]), float(e["at"][1])))
            en, cn = tx(e["name"])
            try:
                color = kit.norm_hex(e["color"]) if e.get("color") else None
            except ValueError:
                color = None
            base = slug(eid)
            page, n = base, 2
            while page.lower() in seen_pages:
                page = "%s-%d" % (base, n)
                n += 1
            seen_pages.add(page.lower())
            rec = {"i": i, "id": eid, "raw": e, "en": en, "cn": cn, "short": str(e.get("short") or ""), "color": color or self.pal["light"]["b"],
                   "tags": [str(t) for t in (e.get("tags") or [])], "place": pl, "room": pl["id"] if pl else None, "floor": fid,
                   "booth": str(e["booth"]) if e.get("booth") is not None else None, "page": "e/%s.html" % page,
                   "blurb": tx(e["blurb"]) if e.get("blurb") else None, "facts": e.get("facts") or [], "parts": e.get("parts") or [],
                   "blocks": e.get("blocks") or [], "g": ""}
            key = pl["id"] if pl else "~" + fid
            per_room.setdefault(key, []).append(rec)
            ents.append(rec)
        for lst in per_room.values():           # a booth without a number is numbered by its order in the room (what the router does)
            for k, rec in enumerate(lst):
                if rec["booth"] is None:
                    rec["booth"] = "%02d" % (k + 1)
        by_floor = {}
        for rec in ents:
            by_floor.setdefault(rec["floor"], []).append((rec["booth"] or "").lower())
        # booth numbers that repeat on a floor (numbered per room) cannot make a code alone: the room's number goes between (code_parts)
        self.code_room = any(len(v) != len(set(v)) for v in by_floor.values())
        self.ents = ents
        self.ent_by = {x["id"]: x for x in ents}
        ordered = []
        for fl in self.floors:
            ordered += [x for x in ents if x["floor"] == fl["id"]]
        self.ordered = ordered                   # the order of the list: by floor, then as authored (prev / next follow it)

    # ---- groups: how the home page's grid is divided (event.group_by) -----------------------------------
    def _groups(self):
        """self.groups = [{key, chip, en, cn, members}] in display order; every entity gets rec['g'] = its group's key. Empty groups are dropped."""
        gb = self.group_by
        groups = []
        if gb == "floor":
            for fl in self.floors:
                here = [x for x in self.ents if x["floor"] == fl["id"]]
                if here:
                    groups.append({"key": fl["id"], "floor": fl, "members": here})
        elif gb == "room":
            by = {}
            for fl in self.floors:
                for pl in fl["rooms"] + fl["areas"]:
                    here = [x for x in self.ents if x["room"] == pl["id"]]
                    if here:
                        label = pl["label"]
                        groups.append({"key": pl["id"], "chip": label, "place": pl, "members": here})
                free = [x for x in self.ents if x["floor"] == fl["id"] and not x["room"]]
                if free:
                    groups.append({"key": "~" + fl["id"], "chip": self.floor_short(fl["id"], self.lead), "open": fl, "members": free})
        else:
            groups = self._tag_groups()
        seen = set()
        for g in groups:
            k, n = g["key"], 2
            while g["key"] in seen:
                g["key"] = "%s-%d" % (k, n)
                n += 1
            seen.add(g["key"])
            for x in g["members"]:
                x["g"] = g["key"]
        self.groups = groups

    def _tag_label(self, tag):
        if tag in self.tag_terms:
            return self.tag_terms[tag]
        t = re.sub(r"[-_]+", " ", tag).strip()
        return (t.title() if not has_cjk(t) else t, t.title() if not has_cjk(t) else t)

    def warn(self, msg):
        self.warnings.append(msg)

    def _xgroups(self):
        """x-groups entries that name members (`tags` / `ids` / `rooms` / `floors`) -> self.xspecs, with the entities each one holds: [{i, id, key,
        label, words, tags, ids, rooms, floors, members}]. One entity is in ONE group (the grid shows it once; starter.js also gives the search exactly
        these members, so a group's `words` only ever find what the build put in the group). Which group, strongest first:
          1. entity.group, the group's `id` (else its key: the slug of its first tag)       2. the entry lists the entity's id in `ids`
          3. the entity's FIRST tag is one of the entry's `tags`      4. the entity's room is in `rooms`      5. its floor is in `floors`
          6. one of the entity's other tags is in `tags`
        The first step that finds a group decides; when it finds several, the first of them in x-groups order wins. An entity that fits more than
        one group anywhere in 2-6 gets a build warning that names them (give it `group` to settle it); one that fits none goes to Other."""
        specs = []
        for i, g in enumerate(self.v.get("x-groups") or []):
            if not isinstance(g, dict) or not (g.get("tags") or g.get("ids") or g.get("rooms") or g.get("floors")):
                continue
            tags = [str(t) for t in (g.get("tags") or [])]
            words = [w for w in (g.get("words") or []) if isinstance(w, str) and w.strip()]
            if g.get("label") or g.get("name"):
                lab = tx(g.get("label") or g.get("name"))
            elif tags and tags[0] in self.tag_terms:
                lab = self.tag_terms[tags[0]]
            else:
                cn = next((w for w in words if has_cjk(w)), "")
                en = next((w for w in words if not has_cjk(w)), "")
                lab = (cap(en), cn) if (en or cn) else self._tag_label(tags[0] if tags else "group %d" % (i + 1))
                lab = (lab[0] or lab[1], lab[1] or lab[0])
            gid = str(g["id"]) if g.get("id") not in (None, "") else None
            key, n = slug(gid or (tags[0] if tags else "g%d" % (i + 1))).lower(), 2
            while any(sp["key"] == key for sp in specs):
                key = "%s-%d" % (slug(gid or (tags[0] if tags else "g%d" % (i + 1))).lower(), n)
                n += 1
            specs.append({"i": i, "id": gid, "key": key, "label": lab, "tags": set(tags), "words": words,
                          "ids": {str(x) for x in (g.get("ids") or [])}, "rooms": {str(x) for x in (g.get("rooms") or [])},
                          "floors": {str(x) for x in (g.get("floors") or [])}, "members": []})
        self.xspecs = specs
        if not specs:
            return
        for x in self.ents:
            want = x["raw"].get("group")
            sp = None
            if want not in (None, ""):
                w = str(want)
                sp = next((s for s in specs if s["id"] == w or s["key"] == slug(w).lower()), None)
                if sp is None:
                    tagged = [s for s in specs if w in s["tags"]]
                    sp = tagged[0] if len(tagged) == 1 else None
                if sp is None:
                    self.warn("entity %s: group %r is not an x-groups id (%s); it is placed by its tags instead" % (
                        x["id"], w, ", ".join(s["id"] or s["key"] for s in specs)))
                else:
                    sp["members"].append(x)
                    x["xg"] = sp["key"]
                    continue
            first = x["tags"][:1]
            steps = (lambda s: x["id"] in s["ids"], lambda s: bool(first) and first[0] in s["tags"], lambda s: bool(x["room"]) and x["room"] in s["rooms"],
                     lambda s: x["floor"] in s["floors"], lambda s: bool(set(x["tags"][1:]) & s["tags"]))
            hits = [s for s in specs if any(f(s) for f in steps)]
            if hits:
                sp = next(s for f in steps for s in specs if f(s))
                sp["members"].append(x)
                x["xg"] = sp["key"]
                if len(hits) > 1:
                    self.warn("entity %s fits several groups (%s): placed in %s; set entity.group to choose" % (
                        x["id"], ", ".join(h["id"] or h["key"] for h in hits), sp["id"] or sp["key"]))

    def _tag_groups(self):
        """The groups of group_by = tag: the x-groups entries (see _xgroups), else one group per tag -- the entity's `group` if it has one, else its first
        tag that terms.tags knows (if terms.tags is given), else its first tag. An entity that fits none goes to 'Other' at the end."""
        rest = []
        if self.xspecs:
            rest = [x for x in self.ents if not x.get("xg")]
            specs = self.xspecs
        else:
            known = list(self.tag_terms)
            order = []
            by = {}
            alltags = {t for x in self.ents for t in x["tags"]}
            for x in self.ents:
                want = x["raw"].get("group")
                if want not in (None, ""):
                    tag = str(want)
                    if known and tag not in self.tag_terms and tag not in alltags:
                        self.warn("entity %s: group %r is not in terms.tags (nor a tag of any entity)" % (x["id"], tag))
                else:
                    tag = next((t for t in x["tags"] if t in self.tag_terms), x["tags"][0] if x["tags"] else None) if known else (x["tags"][0] if x["tags"] else None)
                if tag is None:
                    rest.append(x)
                    continue
                if tag not in by:
                    by[tag] = []
                    order.append(tag)
                by[tag].append(x)
            order = [t for t in known if t in by] + [t for t in order if t not in self.tag_terms]
            specs = [{"key": slug(t).lower(), "label": self._tag_label(t), "members": by[t]} for t in order]
        groups = [{"key": sp["key"], "en": sp["label"][0], "cn": sp["label"][1], "members": sp["members"]} for sp in specs if sp["members"]]
        if rest:
            groups.append({"key": "other", "en": self.words("grp_other", "en"), "cn": self.words("grp_other", "zh"), "members": rest})
        return groups

    def group_heading(self, g, hid, tag="h3"):
        n = len(g["members"])
        count = '<span class="sp-count">%s</span>' % self.spans(self.words("n_things", "en", n=n), self.words("n_things", "zh", n=n))
        if "floor" in g:
            return self.floor_heading(g["floor"], hid, n, tag)
        chip, names = "", []
        if "place" in g:
            pl = g["place"]
            nen, ncn = (cap(pl["en"]), pl["cn"]) if pl["area"] else (pl["en"], pl["cn"])
            chip = g["chip"]
            names = [] if (nen == chip and ncn == chip) else ls(nen, ncn, self.lead)
        elif "open" in g:
            chip = g["chip"]
            names = ls(self.words("open_floor", "en"), self.words("open_floor", "zh"), self.lead)
        else:
            names = ls(g["en"], g["cn"], self.lead)
        names = [x for x in names if x[0] != chip]
        fid = ('<span class="sp-fid" lang="%s">%s</span>' % ("zh-CN" if has_cjk(chip) else "en", esc(spaced(chip)))) if chip else ""
        nm = ('<span class="evk-k">%s</span>' % "".join('<span class="%s" lang="%s">%s</span>' % (c, l, esc(t)) for t, c, l in names)) if names else ""
        return '<%s id="%s">%s%s%s</%s>' % (tag, hid, fid, nm, count, tag)

    # ---- names of places ------------------------------------------------------------------------
    def floor_name(self, fid, lang):
        """The floor's NAME (headings, aria labels): 'Fourth Floor' / '四层'."""
        fl = self.floor_by.get(fid)
        return (fl["cn"] if lang == "zh" else fl["en"]) if fl else fid

    def floor_short(self, fid, lang):
        """The floor's SHORT form (chips, tags, location lines, and the router's sentences): '4F' / '4 层'."""
        fl = self.floor_by.get(fid)
        return (fl["s_cn"] if lang == "zh" else fl["s_en"]) if fl else fid

    def floor_title(self, fl):
        """A heading for a floor: (chip, [(text, class, lang), ...]). The chip is the short form in the lead language; the name follows, then
        the other language's name (or its short form), and no string is ever printed twice ('1F 1F')."""
        lead = self.lead
        sh = {"en": fl["s_en"], "zh": fl["s_cn"]}
        nm = {"en": fl["en"], "zh": fl["cn"]}
        chip = sh[lead]
        seen = {chip}
        out = []
        for lang, cands in ((lead, [nm[lead]]), (self.other, [nm[self.other], sh[self.other]])):
            for t in cands:
                if t and t not in seen:
                    seen.add(t)
                    out.append((spaced(t),) + (("cn", "zh-CN") if has_cjk(t) else ("en", "en")))
                    break
        return chip, out

    def place_name(self, pl, lang):
        if not pl:
            return ""
        if pl["area"]:
            return pl["cn"] if lang == "zh" else cap(pl["en"])
        if re.fullmatch(r"\d+", pl["label"]):
            return pl["label"] if lang == "zh" else ((self.room_t[0] + " ") if self.room_t[0] else "") + pl["label"]
        return pl["cn"] if lang == "zh" else pl["en"]

    def booth_name(self, rec, lang):
        if not rec["booth"]:
            return ""
        return ("%s 号%s" % (rec["booth"], self.booth_t[1])) if lang == "zh" else "%s %s" % (self.booth_t[0], rec["booth"])

    def where_text(self, rec, lang):
        t = " · ".join(x for x in (self.floor_short(rec["floor"], lang), self.place_name(rec["place"], lang), self.booth_name(rec, lang)) if x)
        return spaced(t) if lang == "zh" else t

    def at_phrase(self, rec, lang):
        """For a sentence: 'in Room 203, booth 02' / 'in the west corridor, booth 07' / 'on the open floor, booth K1'."""
        pl = rec["place"]
        if lang == "zh":
            core = self.place_name(pl, "zh") if pl else "开放区"
            return spaced("%s%s" % (core, ("，" + self.booth_name(rec, "zh")) if rec["booth"] else ""))
        if pl and pl["area"]:
            core = "in the " + re.sub(r"^the\s+", "", pl["en"], flags=re.I)
        elif pl:
            core = "in " + (self.place_name(pl, "en") if re.fullmatch(r"\d+", pl["label"]) else "the " + re.sub(r"^the\s+", "", pl["en"], flags=re.I))
        else:
            core = "on the open floor"
        return core + ((", " + self.booth_name(rec, "en")) if rec["booth"] else "")

    def code_parts(self, rec, lang=None):
        """The location code of an entity: '<floor short>·<booth>' ('2F·L02', '2 层·L02'), as (front, booth) = ('2F', 'L02'). One format on every
        page and in starter.js. When booth numbers repeat on a floor (they are numbered per room: 01 in every room) the room's number goes
        between them ('2F·203·02'), for the whole venue. A label is a display name (the map plate, the headings), so an area's label is never
        part of a code."""
        front = self.floor_short(rec["floor"], lang or self.lead)
        pl = rec["place"]
        if self.code_room and pl and not pl["area"] and pl["label"]:
            front += "·" + pl["label"]
        return spaced(front), rec["booth"] or ""

    def code_text(self, rec, lang=None):
        front, booth = self.code_parts(rec, lang)
        return front + "·" + booth if booth else front

    def tag_html(self, rec, small=True):
        """The code on a tag. small=True: the floor part is the small, quiet one; small=False writes the whole code as plain text (a tag that sits on a fill)."""
        front, booth = self.code_parts(rec)
        if not booth:
            return esc(front)
        return ("<small>%s·</small>%s" % (esc(front), esc(booth))) if small else esc(front + "·" + booth)

    def initial(self, rec):
        if self.lead == "zh" and has_cjk(rec["cn"]):
            return rec["cn"].strip()[:1]
        return (rec["short"] or rec["en"] or rec["cn"] or "?").strip()[:1].upper()

    def style(self, rec):
        t = kit.tones(rec["color"], self.pal["light"]["paper"], self.pal["light"]["text"], self.pal["dark"]["paper"])
        return ";".join("%s:%s" % (kit.TONES_CSS[k], t[k]) for k in kit.TONES_KEYS)

    def name_lines(self, rec):
        return ls(rec["en"], rec["cn"], self.lead)

    def plain_name(self, rec):
        return self.name_lines(rec)[0][0]

    # ---- shared page parts ------------------------------------------------------------------------
    def title(self, page_en, page_cn):
        sep = "｜" if self.lead == "zh" else " | "
        return "%s%s%s" % (self.lead_text(page_en, page_cn), sep, self.lead_text(*self.event_name))

    def page(self, root, name, title, desc, main, current=None, data_attrs="", extra=""):
        p, pal = self.p, self.pal
        lang = "zh-CN" if self.lead == "zh" else "en"
        scripts = ['<script src="%sdata/venue.js"></script>' % root] + ['<script src="%sevk/engine/%s"></script>' % (root, n) for n in ENGINE_ORDER] \
            + ['<script src="%sassets/starter.js"></script>' % root]
        return (
            '<!doctype html>\n<html lang="%s" %s data-evk-paper="%s" data-evk-ink="%s" data-evk-night="%s">\n<head>\n'
            '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n%s'
            '<title>%s</title>\n<meta name="description" content="%s">\n<meta name="color-scheme" content="light dark">\n'
            '<meta name="theme-color" content="%s" media="(prefers-color-scheme: light)">\n<meta name="theme-color" content="%s" media="(prefers-color-scheme: dark)">\n'
            '<link rel="stylesheet" href="%sevk/tokens.css">\n<link rel="stylesheet" href="%sevk/base.css">\n<link rel="stylesheet" href="%sevk/recipe.css">\n'
            '<link rel="stylesheet" href="%sassets/starter.css">\n</head>\n<body data-page="%s" data-root="%s" data-drag="%s"%s>\n'
            '<a class="evk-skip" href="#main">%s</a>\n%s%s\n<main id="main">\n%s</main>\n%s%s\n</body>\n</html>\n') % (
            lang, kit.root_attrs_html(p), pal["light"]["paper"], pal["light"]["text"], pal["dark"]["paper"],
            '<meta name="robots" content="noindex">\n' if self.schematic else "", esc(title), esc(desc), pal["light"]["paper"], pal["dark"]["paper"],
            root, root, root, root, name, root, self.drag, data_attrs, esc(self.s("skip")), self.banner(), self.bar(root, current), main, extra, "\n".join(scripts))

    def banner(self):
        if not self.schematic:
            return ""
        if self.schematic_text:
            L = ls(self.schematic_text[0], self.schematic_text[1], self.lead)
            text = '<span lang="%s">%s</span>' % (L[0][2], esc(L[0][0])) + ('<span class="sp-2nd" lang="%s">%s</span>' % (L[1][2], esc(L[1][0])) if len(L) > 1 else "")
        else:
            text = self.sp("sample_text")
        return '<p class="sp-banner" role="note"><b>%s</b><span>%s</span></p>\n' % (self.pair("sample_tag"), text)

    def bar(self, root, current):
        items = [("index.html", "nav_guide"), ("map.html", "nav_map")]
        nav = "".join('<a href="%s%s"%s><span class="evk-k">%s</span></a>' % (root, href, ' aria-current="page"' if current == key else "", self.pair(key)) for href, key in items)
        brand = esc(self.lead_text(*self.event_name))
        return ('<header class="evk-bar"><a class="evk-brand" href="%sindex.html"><span class="sp-brand">%s</span></a>'
                '<nav class="evk-nav" aria-label="%s">%s</nav></header>') % (root, brand, esc(self.s("nav_label")), nav)

    def foot(self, root, back=False):
        en, cn = self.event_name
        vn = self.venue_name
        line2 = ""
        if self.event_named and vn != self.event_name:
            line2 = '<p><span class="evk-k">%s</span></p>' % self.spans(*vn)
        link = ('<p><a href="%sindex.html#booths"><span class="evk-k">%s</span></a></p>' % (root, self.pair("e_back"))) if back else ""
        return '<footer class="sp-foot"><p><b class="evk-k">%s</b></p>%s%s</footer>\n' % (self.spans(en, cn), line2, link)

    def entity_style_attr(self, rec):
        return ' style="%s"' % esc(self.style(rec))

    # ---- index.html -------------------------------------------------------------------------------
    def facts_dl(self):
        def dd(val, with_second=True):
            if not val:
                return '<span class="evk-k sp-tba">%s</span>' % self.pair("tba")
            L = ls(val[0], val[1], self.lead)
            out = '<span lang="%s">%s</span>' % (L[0][2], esc(L[0][0]))
            if len(L) > 1 and with_second:
                out += '<small class="sp-2nd" lang="%s">%s</small>' % (L[1][2], esc(L[1][0]))
            return out
        place = self._fact("place") or self.venue_name
        cells = [("f_date", dd(self._fact("date"))), ("f_time", dd(self._fact("time"))), ("f_where", dd(place))]
        return '<dl class="sp-facts">%s</dl>' % "".join('<div><dt>%s</dt><dd>%s</dd></div>' % (self.K(k), v) for k, v in cells)

    def stats(self):
        nfl = len(self.floors)
        nroom = sum(len(f["rooms"]) for f in self.floors)
        nent = len(self.ents)
        bt = self.booth_t
        cells = [(nfl, self.pair("st_floors"))]
        if nroom:
            cells.append((nroom, self.pair("st_rooms")))
        cells.append((nent, spans(cap(plural(bt[0])), "个" + bt[1], self.lead)))
        return '<div class="evk-stats">%s</div>' % "".join(
            '<div class="evk-stat"><b class="n">%02d</b><span class="evk-k">%s</span></div>' % (n, lab) for n, lab in cells)

    def placeholder_examples(self, lang):
        """One or two real names (else a room number) in `lang`, for the search box: 'Kelp, Orbital' / '海带生物塑料、潮汐机械'. Names that are long
        are passed over; a tag id is never an example (it is a key, not something people type)."""
        names = []
        for x in self.ents:
            n = x["cn"] if lang == "zh" else (x["short"] if x["short"] and not has_cjk(x["short"]) else x["en"])
            n = (n or "").strip()
            if n and width_em(n) <= 10 and n not in names:
                names.append(n)
        picks = names[:1] + (names[len(names) // 2:][:1] if len(names) > 2 else names[1:2])
        picks = [n for i, n in enumerate(picks) if n not in picks[:i]]
        if len(picks) < 2:
            room = next((pl["label"] for fl in self.floors for pl in fl["rooms"] if re.fullmatch(r"\d+", pl["label"])), None)
            if room:
                picks.append(room)
        out = ("、" if lang == "zh" else ", ").join(picks)
        return spaced(out) if lang == "zh" else out

    def grid_cell(self, rec):
        L = self.name_lines(rec)
        lines = "".join('<span class="%s%s" lang="%s">%s</span>' % ("name " if i == 0 else "", c, l, esc(spaced(t) if c == "cn" else t)) for i, (t, c, l) in enumerate(L))
        return ('<li data-id="%s" data-floor="%s" data-g="%s"><a class="evk-cell" href="%s"%s><span class="evk-mark" aria-hidden="true">%s</span>%s'
                '<span class="evk-tag">%s</span></a></li>') % (esc(rec["id"]), esc(rec["floor"]), esc(rec["g"]), esc(quote(rec["page"], safe="/")), self.entity_style_attr(rec),
                                                              esc(self.initial(rec)), lines, self.tag_html(rec))

    def floor_heading(self, fl, hid, n, tag="h3"):
        """'4F  Fourth Floor 四层  3 booths': the short form as a chip, the name(s) after it, never the same string twice."""
        chip, names = self.floor_title(fl)
        nm = ('<span class="evk-k">%s</span>' % "".join('<span class="%s" lang="%s">%s</span>' % (c, l, esc(t)) for t, c, l in names)) if names else ""
        count = '<span class="sp-count">%s</span>' % self.spans(self.words("n_things", "en", n=n), self.words("n_things", "zh", n=n))
        return '<%s id="%s"><span class="sp-fid" lang="%s">%s</span>%s%s</%s>' % (tag, hid, "zh-CN" if has_cjk(chip) else "en", esc(spaced(chip)), nm, count, tag)

    def K_raw(self, en, cn, cls=""):
        return '<span class="evk-k%s">%s</span>' % ((" " + cls) if cls else "", self.spans(en, cn))

    def hint_pair(self):
        """The hint on the map: what one finger does in this card's projection (rotate | pan), as the engine says it."""
        return self.pair("map_hint" + DRAG_SUFFIX[self.drag])

    def _floor_btn(self, fl, selected=False):
        """A floor button: the SHORT form in the lead language ('4F' / '4 层'); the control scrolls, a button never shrinks below 44 px."""
        t = fl["s_cn"] if self.lead == "zh" else fl["s_en"]
        return '<button type="button" data-v="%s" aria-pressed="%s" lang="%s">%s</button>' % (
            esc(fl["id"]), "true" if selected else "false", "zh-CN" if has_cjk(t) else "en", esc(spaced(t)))

    def _group_btn(self, g):
        """A button of the group control. Its label is the group's name in BOTH languages (primary first, the way the other buttons are written: 'All 全部');
        a floor or room group is the code people know it by ('2F', '203'). The control scrolls inside itself, a button keeps its width."""
        if "floor" in g:
            fl = g["floor"]
            t = fl["s_cn"] if self.lead == "zh" else fl["s_en"]
            return '<span lang="%s">%s</span>' % ("zh-CN" if has_cjk(t) else "en", esc(spaced(t)))
        if "place" in g:
            if g["chip"]:
                return '<span lang="%s">%s</span>' % ("zh-CN" if has_cjk(g["chip"]) else "en", esc(spaced(g["chip"])))
            return self.K_raw(cap(g["place"]["en"]) if g["place"]["area"] else g["place"]["en"], g["place"]["cn"])
        if "open" in g:
            return self.pair("open_floor")
        return self.K_raw(g["en"], g["cn"])

    def index_html(self):
        en, cn = self.event_name
        ev_eyebrow = '<p class="evk-eyebrow evk-k">%s</p>' % self.pair("eyebrow_event")
        h1 = self.lines(en, cn, "h1", "sp-title", "sp-title-2")
        h1 = h1.replace('<h1 class="sp-title"', '<h1 id="t" class="sp-title"', 1)
        note = self._fact("note")
        note_html = ('<p class="sp-note">%s</p>' % self.spans(*note)) if note else ""
        welcome = ('<section class="evk-welcome" aria-labelledby="t">%s%s%s%s%s'
                   '<div class="sp-actions"><a class="evk-btn evk-btn--primary" href="map.html"><span class="evk-k">%s</span></a>'
                   '<a class="evk-btn" href="#booths"><span class="evk-k">%s</span></a></div></section>\n') % (
            ev_eyebrow, h1, self.facts_dl(), note_html, self.stats(), self.pair("open_map"), self.pair("find_cta"))
        nent = len(self.ents)
        cv = self.s("cv_preview")
        preview = (
            '<section class="evk-section sp-preview" id="preview" aria-labelledby="h-map" style="--sp-floors:%d" hidden>\n<h2 id="h-map" class="sp-h2">%s</h2><hr class="evk-divider">\n'
            '<div class="evk-map"><canvas role="img" tabindex="0" aria-label="%s"></canvas><p class="evk-map-hint evk-k">%s</p>'
            '<button class="evk-btn evk-btn--quiet evk-btn--sm evk-map-reset" type="button" hidden><span class="evk-k">%s</span></button></div>\n'
            '<p class="sp-more"><a class="evk-btn evk-btn--quiet" href="map.html"><span class="evk-k">%s</span></a></p>\n</section>\n') % (
            len(self.floors), self.K("h_map"), esc(cv), self.hint_pair(), self.pair("reset"), self.pair("open_map"))
        all_btn = '<button type="button" data-v="" aria-pressed="true"><span class="evk-k">%s</span></button>' % self.pair("all")
        floors_with = [fl for fl in self.floors if any(x["floor"] == fl["id"] for x in self.ents)]
        seg = [all_btn] + [self._floor_btn(fl) for fl in floors_with]
        gseg = []
        if self.group_by != "floor" and len(self.groups) > 1:
            gseg = [all_btn] + ['<button type="button" data-v="%s" aria-pressed="false">%s</button>' % (esc(g["key"]), self._group_btn(g)) for g in self.groups]
        groups = []
        for g in self.groups:
            hid = "g-" + slug(g["key"])
            groups.append('<section class="sp-group" data-g="%s" aria-labelledby="%s">%s<ul class="evk-grid">\n%s\n</ul></section>' % (
                esc(g["key"]), esc(hid), self.group_heading(g, hid), "\n".join(self.grid_cell(x) for x in g["members"])))
        examples = {"en": self.placeholder_examples("en"), "zh": self.placeholder_examples("zh")}
        ph = self.s("search_ph", ex=examples[self.lead])
        things = cap(plural(self.booth_t[0]))
        booths = ('<section class="evk-section" id="booths" aria-labelledby="h-booths" data-group="' + self.group_by + '">\n'
                  '<h2 id="h-booths" class="sp-h2">%s<span class="sp-count" id="shown">%d / %d</span></h2><hr class="evk-divider">\n'
                  '<div class="sp-find" id="find" hidden>\n<div><label class="evk-vh" for="q">%s</label>'
                  '<input id="q" class="evk-search" type="search" autocomplete="off" spellcheck="false" enterkeyhint="search" placeholder="%s"></div>\n'
                  '%s%s</div>\n'
                  '<p class="evk-empty" id="empty" role="status" hidden><span>%s</span><span>%s</span></p>\n'
                  '<p class="evk-vh" id="live" aria-live="polite"></p>\n%s\n</section>\n') % (
            self.K_raw(things, self.booth_t[1]), nent, nent, esc(self.s("search_label")), esc(ph),
            ('<div class="evk-seg" role="group" aria-label="%s" id="seg-floor">%s</div>\n' % (esc(self.s("floor_label")), "".join(seg))) if len(seg) > 2 else "",
            ('<div class="evk-seg" role="group" aria-label="%s" id="seg-group">%s</div>\n' % (esc(self.s("group_label")), "".join(gseg))) if gseg else "",
            self.pair("empty_title"), self.sp("empty_hint"), "\n".join(groups))
        main = welcome + preview + booths + self.foot("")
        desc = self.s("meta_home", event=self.lead_text(*self.event_name), venue=self.lead_text(*self.venue_name), n=nent, k=len(self.floors))
        return self.page("", "home", self.home_title(), desc, main, current="nav_guide")

    def home_title(self):
        ev = self.event_name
        vn = self.venue_name
        a = self.lead_text(*ev)
        if self.event_named and vn != ev:
            return "%s%s%s" % (a, "｜" if self.lead == "zh" else " | ", self.lead_text(*vn))
        return a

    # ---- map.html ---------------------------------------------------------------------------------
    def directory(self):
        out = []
        for fl in self.floors:
            cards = []
            for pl in fl["rooms"] + fl["areas"]:
                here = [x for x in self.ents if x["room"] == pl["id"]]
                if here:
                    cards.append(self.dir_card(pl, here))
            free = [x for x in self.ents if x["floor"] == fl["id"] and not x["room"]]
            if free:
                cards.append(self.dir_card(None, free, fl))
            if not cards:
                continue
            n = sum(1 for x in self.ents if x["floor"] == fl["id"])
            out.append('<section class="sp-floor" aria-labelledby="d-%s">%s<ul class="sp-cards">\n%s\n</ul></section>' % (
                esc(slug(fl["id"])), self.floor_heading(fl, "d-" + slug(fl["id"]), n), "\n".join(cards)))
        return "\n".join(out)

    def dir_card(self, pl, here, fl=None):
        if pl:
            tag = ('<span class="evk-tag">%s</span>' % esc(pl["label"])) if pl["label"] else ""
            nen, ncn = (cap(pl["en"]), pl["cn"]) if pl["area"] else (pl["en"], pl["cn"])
            name = "" if (nen == pl["label"] and ncn == pl["label"]) else self.K_raw(nen, ncn)
            head = '<a class="sp-room-link" href="map.html?r=%s" data-room="%s">%s%s</a>' % (esc(quote(pl["id"], safe="")), esc(pl["id"]), tag, name)
            cid = ' id="room-%s"' % esc(slug(pl["id"]))
        else:
            head = '<span class="sp-room-link"><span class="evk-k">%s</span></span>' % self.pair("open_floor")
            cid = ""
        rows = []
        for x in here:
            L = self.name_lines(x)
            sub = ('<small lang="%s">%s</small>' % (L[1][2], esc(L[1][0]))) if len(L) > 1 else ""
            rows.append('<li><a href="%s" data-sel="%s"%s><span class="no">%s</span><span class="evk-mark" aria-hidden="true">%s</span>'
                        '<span class="t"><span lang="%s">%s</span>%s</span></a></li>' % (
                            esc(quote(x["page"], safe="/")), esc(x["id"]), self.entity_style_attr(x), esc(x["booth"] or ""), esc(self.initial(x)),
                            L[0][2], esc(spaced(L[0][0]) if L[0][1] == "cn" else L[0][0]), sub))
        return '<li class="sp-card"%s><header>%s</header><ol class="sp-rows">%s</ol></li>' % (cid, head, "".join(rows))

    def map_html(self):
        seg = ['<button type="button" data-v="" aria-pressed="true"><span class="evk-k">%s</span></button>' % self.pair("all")]
        seg += [self._floor_btn(fl) for fl in self.floors]
        nent = len(self.ents)
        cv = self.s("cv_map")
        h1 = ('<h1 class="sp-h1">%s</h1>' % "".join(
            ('<span lang="%s">%s</span>' if i == 0 else '<small lang="%s">%s</small>') % (l, esc(t)) for i, (t, c, l) in enumerate(ls("Map", "地图", self.lead))))
        head = '<header class="sp-pagehead">%s<p>%s</p></header>\n' % (h1, self.sp("map_intro"))
        tools = (
            '<div class="sp-tools" id="tools" hidden>\n<div class="sp-search"><label class="evk-vh" for="q">%s</label>'
            '<input id="q" class="evk-search" type="search" autocomplete="off" spellcheck="false" enterkeyhint="search" role="combobox" aria-expanded="false" '
            'aria-controls="found" aria-autocomplete="list" placeholder="%s"><ul id="found" class="sp-results" role="listbox" aria-label="%s" hidden></ul></div>\n'
            '<div class="sp-row"><div class="evk-seg" role="group" aria-label="%s" id="seg-floor">%s</div>'
            '<button class="evk-btn evk-btn--primary" type="button" id="open-route"><span class="evk-k">%s</span></button></div>\n</div>\n') % (
            esc(self.s("search_label")), esc(self.s("search_ph", ex=self.placeholder_examples(self.lead))), esc(self.s("search_label")),
            esc(self.s("floor_label")), "".join(seg), self.pair("btn_directions"))
        mapbox = (
            '<div class="evk-map sp-map" id="map" hidden><canvas role="img" tabindex="0" aria-label="%s"></canvas>%s<p class="evk-map-hint evk-k">%s</p>'
            '<button class="evk-btn evk-btn--quiet evk-btn--sm evk-map-reset" type="button" hidden><span class="evk-k">%s</span></button></div>\n'
            '<noscript><p class="evk-empty"><span>%s</span></p></noscript>\n') % (
            esc(cv), '<p class="sp-stamp" aria-hidden="true">%s</p>' % self.pair("sample_tag") if self.schematic else "", self.hint_pair(), self.pair("reset"),
            self.sp("noscript_map"))
        dir_head = '<h2 id="h-dir" class="sp-h2">%s<span class="sp-count">%d</span></h2><hr class="evk-divider">' % (self.K("dir_title"), nent)
        directory = '<section class="evk-section sp-dir" id="dir" aria-labelledby="h-dir">\n%s\n%s\n</section>\n' % (dir_head, self.directory())
        fine = self.sp("route_fine_s" if self.schematic else "route_fine")
        sheets = (
            '<div class="evk-sheet" id="sheet-place" role="dialog" aria-modal="false" aria-labelledby="place-t" hidden>\n'
            '<div class="evk-grabber"></div>\n<div class="evk-sheet-head"><h2 id="place-t" tabindex="-1"></h2>'
            '<button class="evk-btn evk-btn--quiet evk-btn--sm" id="place-close" type="button"><span class="evk-k">%(close)s</span></button></div>\n'
            '<div class="sp-sheet-body" id="place-body"></div>\n</div>\n\n'
            '<div class="evk-sheet" id="sheet-route" role="dialog" aria-modal="false" aria-labelledby="route-t" hidden>\n'
            '<div class="evk-grabber"></div>\n<div class="evk-sheet-head"><h2 id="route-t" tabindex="-1"><span class="evk-k">%(rtitle)s</span></h2>'
            '<button class="evk-btn evk-btn--quiet evk-btn--sm" id="route-close" type="button"><span class="evk-k">%(close)s</span></button></div>\n'
            '<form class="sp-form" id="route-form" novalidate>\n'
            '<div><label for="from"><span class="evk-k">%(rfrom)s</span></label><select id="from"></select></div>\n'
            '<div><label for="to-q"><span class="evk-k">%(rto)s</span></label>'
            '<input id="to-q" class="evk-search" type="search" autocomplete="off" spellcheck="false" enterkeyhint="go" role="combobox" aria-expanded="false" '
            'aria-controls="to-found" aria-autocomplete="list" placeholder="%(rph)s"><ul id="to-found" class="sp-results sp-results--inline" role="listbox" aria-label="%(rto_plain)s" hidden></ul></div>\n'
            '<label class="sp-check" id="lift-row" hidden><input type="checkbox" id="lift"><span class="evk-k">%(lift)s</span></label>\n'
            '<p class="sp-err" id="route-err" role="status" hidden></p>\n'
            '<button class="evk-btn evk-btn--primary" type="submit"><span class="evk-k">%(go)s</span></button>\n</form>\n'
            '<div id="route-run" hidden>\n<p class="sp-sum" id="sum"></p>\n<ol class="evk-steps" id="steps"></ol>\n'
            '<div class="sp-nav3"><button class="evk-btn evk-btn--quiet" id="prev" type="button"><span class="evk-k">%(back)s</span></button>'
            '<button class="evk-btn evk-btn--quiet" id="all" type="button" aria-pressed="false"><span class="evk-k">%(overview)s</span></button>'
            '<button class="evk-btn evk-btn--primary" id="next" type="button"><span class="evk-k">%(next)s</span></button></div>\n'
            '<button class="sp-linkbtn" id="again" type="button">%(again)s</button>\n<p class="sp-fine">%(fine)s</p>\n</div>\n</div>\n'
            '<p class="evk-vh" id="live" aria-live="polite"></p>\n') % {
            "close": self.pair("close"), "rtitle": self.pair("route_title"), "rfrom": self.pair("route_from"), "rto": self.pair("route_to"),
            "rto_plain": esc(self.s("route_to")), "rph": esc(self.s("route_to_ph")), "lift": self.pair("route_lift"), "go": self.pair("route_go"),
            "back": self.pair("back"), "overview": self.pair("overview"), "next": self.pair("next"),
            "again": "".join('<span class="%s" lang="%s">%s</span>' % (c, l, esc(t)) for t, c, l in
                             ls(self.words("again", "en"), self.words("again", "zh"), self.lead)), "fine": fine}
        main = head + tools + mapbox + directory + self.foot("")
        desc = self.s("meta_map", venue=self.lead_text(*self.venue_name))
        return self.page("", "map", self.title("Map", "地图"), desc, main, current="nav_map", extra=sheets)

    # ---- e/<id>.html ------------------------------------------------------------------------------
    def para(self, v, cls=""):
        """A paragraph in the lead language and, under it, the other (muted)."""
        en, cn = tx(v)
        L = ls(en, cn, self.lead)
        c = (" " + cls) if cls else ""
        out = '<p%s lang="%s">%s</p>' % ((' class="%s"' % cls) if cls else "", L[0][2], esc(L[0][0]))
        if len(L) > 1:
            out += '<p class="%s sp-2nd" lang="%s">%s</p>' % (cls, L[1][2], esc(L[1][0])) if cls else '<p class="sp-2nd" lang="%s">%s</p>' % (L[1][2], esc(L[1][0]))
        return out

    def inl(self, v):
        """A text as two spans (the second muted, on its own line): for a table cell, a list item, a card title."""
        en, cn = tx(v)
        L = ls(en, cn, self.lead)
        out = '<span lang="%s">%s</span>' % (L[0][2], esc(L[0][0]))
        if len(L) > 1:
            out += '<span class="sp-2nd" lang="%s">%s</span>' % (L[1][2], esc(L[1][0]))
        return out

    def line(self, en, cn, cls="sp-where"):
        """Two stacked lines that are data, not prose (a place, a code): divs, so a recipe's prose rules (drop caps, measure) leave them alone."""
        L = ls(en, cn, self.lead)
        out = '<div class="%s" lang="%s">%s</div>' % (cls, L[0][2], esc(L[0][0]))
        if len(L) > 1:
            out += '<div class="%s sp-2nd" lang="%s">%s</div>' % (cls, L[1][2], esc(L[1][0]))
        return out

    def part(self, n, pid, title_en, title_cn, body):
        return ('<section class="evk-part" data-part id="%s" data-title="%s" data-title-cn="%s"><header class="evk-part-head"><span class="no">%02d</span>'
                '<h2 class="evk-k">%s</h2></header>%s</section>') % (pid, esc(title_en), esc(title_cn), n, self.spans(title_en, title_cn), body)

    # ---- "How to get here": written directions on the entity page -------------------------------------
    def route_starts(self, rec):
        """The starts the entity page writes directions from: the main entrance (the first floor by level that has an entrance) and the lobby on the
        entity's own floor, if it has one: [{id, name: (en, cn)}]. A venue with neither has no written directions (the map button stays)."""
        out = []
        fls = sorted((f for f in self.v["floors"] if isinstance(f, dict)), key=lambda f: f.get("level", 0))
        ent = next((f for f in fls if isinstance(f.get("entrance"), dict) and f["entrance"].get("at")), None)
        if ent:
            nm = tx(ent["entrance"]["name"]) if ent["entrance"].get("name") else ("Entrance", "入口")
            out.append({"id": "entrance:%s" % ent["id"], "name": nm})
        lob = next((f for f in fls if str(f["id"]) == rec["floor"] and isinstance(f.get("lobby"), dict) and f["lobby"].get("at")), None)
        if lob:
            nm = tx(lob["lobby"]["name"]) if lob["lobby"].get("name") else ("%s Lobby" % lob["id"], "%s Lobby" % lob["id"])
            out.append({"id": "lobby:%s" % lob["id"], "name": nm})
        return out

    def _routes(self, start):
        """{entity id: [step, ...]} from `node wayfind.js --describe-all` for one start, or {} when it cannot be had (then the page carries the map
        link only and starter.js writes the same steps in the browser). The project's own evk/engine/wayfind.js is tried first, then the kit's."""
        if self._routes_cache is None:
            self._routes_cache = {}
        if start in self._routes_cache:
            return self._routes_cache[start]
        got, why = {}, ""
        node = shutil.which("node") if self.static_routes else None
        if not self.static_routes:
            why = "turned off"
        elif not node:
            why = "node is not on PATH"
        else:
            cands = ([self.out_dir / "evk" / "engine" / "wayfind.js"] if self.out_dir else []) + [kit.ASSETS_DIR / "engine" / "wayfind.js"]
            td = tempfile.mkdtemp(prefix="evk-routes-")
            try:
                vf = Path(td) / "venue.json"
                vf.write_text(json.dumps(self.v, ensure_ascii=False), encoding="utf-8")
                for c in cands:
                    if not c.is_file():
                        continue
                    try:
                        r = subprocess.run([node, str(c), "--describe-all", str(vf), "--from", start, "--lead", self.lead], capture_output=True, text=True, timeout=120)
                    except (OSError, subprocess.TimeoutExpired) as e:
                        why = str(e)
                        continue
                    if r.returncode != 0:
                        why = (r.stderr.strip().splitlines() or ["exit %d" % r.returncode])[0]
                        continue
                    try:
                        data = json.loads(r.stdout)
                    except ValueError:
                        why = "%s has no --describe-all" % c.name
                        continue
                    if isinstance(data, dict) and isinstance(data.get("routes"), dict):
                        got = data["routes"]
                        break
                    why = "unexpected --describe-all output"
            finally:
                shutil.rmtree(td, ignore_errors=True)
        if not got and self.static_routes and not getattr(self, "_route_warned", False):
            self._route_warned = True
            self.warn("written directions (How to get here) are not in the pages (%s): starter.js writes them in the browser" % (why or "no route"))
        self._routes_cache[start] = got
        return got

    def steps_ol(self, steps):
        """<ol class="evk-r-steps"> of describe() steps ({kind, en: {head, text}, cn: {head, text}, climb}); a climb step is .is-climb (the climb
        colour, DR-6); '' when there is nothing to show. starter.js writes the same markup when the build could not."""
        lis = []
        for st in steps if isinstance(steps, list) else []:
            if not isinstance(st, dict):
                continue
            en, cn = st.get("en") or {}, st.get("cn") or {}
            head = {"en": str(en.get("head") or ""), "cn": str(cn.get("head") or "")}
            text = {"en": str(en.get("text") or ""), "cn": str(cn.get("text") or "")}
            if not (text["en"] or text["cn"]):
                continue
            climb = bool(st.get("climb")) or st.get("kind") in CLIMB_KINDS
            lis.append("<li%s>%s%s</li>" % (' class="is-climb"' if climb else "", ('<strong class="t">%s</strong>' % self.inl(head)) if (head["en"] or head["cn"]) else "", self.inl(text)))
        return ('<ol class="evk-r-steps">%s</ol>' % "".join(lis)) if lis else ""

    def route_part(self, rec):
        """The body of the 'How to get here' part, or None when the venue has no entrance and no lobby."""
        starts = self.route_starts(rec)
        if not starts:
            return None
        eid = quote(rec["id"], safe="")
        out = []
        for k, st in enumerate(starts):
            nm_en, nm_cn = re.sub(r"^the\s+", "", st["name"][0], flags=re.I), st["name"][1]
            label = {"en": self.words("e_route_from", "en", name=nm_en), "cn": self.words("e_route_from", "zh", name=nm_cn)}
            box = '<div class="sp-route" data-from="%s">%s</div>' % (esc(st["id"]), self.steps_ol((self._routes(st["id"]) or {}).get(rec["id"]) or []))
            link = '<p class="sp-route-more"><a class="evk-btn evk-btn--quiet" href="../map.html?to=%s&amp;from=%s"><span class="evk-k">%s</span></a></p>' % (
                esc(eid), esc(quote(st["id"], safe="")), self.pair("e_route_map"))
            if k == 0:                                               # the first step says "From the Entrance, ..." itself: no heading over the main box
                out.append(box + link)
            else:
                out.append('<details class="evk-r-fold evk-fold"><summary>%s</summary>%s%s</details>' % (self.inl(label), box, link))
        return "".join(out)

    # ---- reading blocks (reading.md §3: the closed vocabulary, classes evk-r-<type>) --------------------
    def _text_ok(self, v):
        en, cn = tx(v)
        return bool(en or cn)

    def _items(self, b, ctx, key="items"):
        it = b.get(key)
        if not isinstance(it, list) or not it:
            raise ValueError("%s needs a non-empty %r list" % (ctx, key))
        return it

    def _field(self, d, names, ctx, what, required=True):
        """The first of `names` that d has (aliases); a text."""
        for n in names:
            if isinstance(d, dict) and d.get(n) not in (None, "", {}):
                return d[n]
        if required:
            raise ValueError("%s has no %r" % (ctx, names[0]))
        return None

    def block_html(self, b, ctx, depth=0, title=True):
        """One block -> HTML. `ctx` names it for an error ('entity kelp: blocks[2]'); `title` False when the caller made the title a part head."""
        if not isinstance(b, dict):
            raise ValueError('%s: a block is an object like {"type": "p", "text": ...}' % ctx)
        t = str(b.get("type") or b.get("t") or "")
        if t not in BLOCK_TYPES:
            raise ValueError("%s: unknown block type %r (use %s)" % (ctx, t, ", ".join(BLOCK_TYPES)))
        ctx = "%s (%s)" % (ctx, t)
        head = ""
        if title and t != "fold" and b.get("title"):
            head = '<h3 class="evk-r-title">%s</h3>' % self.K_raw(*tx(b["title"]))
        self._lvl = 4 if head else 3                  # the heading level inside a block (cards): one below the block's own title
        body = getattr(self, "_b_" + t)(b, ctx, depth)
        return head + body

    def blocks_html(self, blocks, ctx, depth=0):
        if not isinstance(blocks, list):
            raise ValueError("%s: blocks must be a list" % ctx)
        return "".join(self.block_html(b, "%s blocks[%d]" % (ctx, i), depth) for i, b in enumerate(blocks))

    def _b_p(self, b, ctx, depth):
        texts = b.get("text")
        texts = texts if isinstance(texts, list) else [texts]
        texts = [x for x in texts if self._text_ok(x)]
        if not texts:
            raise ValueError("%s has no 'text'" % ctx)
        return "".join(self.para(x, "evk-r-p") for x in texts)

    def _b_note(self, b, ctx, depth):
        if not self._text_ok(b.get("text")):
            raise ValueError("%s has no 'text'" % ctx)
        return '<aside class="evk-r-note">%s</aside>' % self.para(b["text"])

    def _b_quote(self, b, ctx, depth):
        if not self._text_ok(b.get("text")):
            raise ValueError("%s has no 'text'" % ctx)
        by = ('<cite class="by">%s</cite>' % self.inl(b["by"])) if self._text_ok(b.get("by")) else ""
        return '<blockquote class="evk-r-quote">%s%s</blockquote>' % (self.para(b["text"]), by)

    def _b_list(self, b, ctx, depth):
        items = self._items(b, ctx)
        tag = "ol" if b.get("ordered") else "ul"
        lis = []
        for i, it in enumerate(items):
            if not self._text_ok(it):
                raise ValueError("%s item %d is empty" % (ctx, i + 1))
            lis.append("<li>%s</li>" % self.inl(it))
        return '<%s class="evk-r-list">%s</%s>' % (tag, "".join(lis), tag)

    def _b_facts(self, b, ctx, depth):
        rows = []
        for i, it in enumerate(self._items(b, ctx)):
            k = self._field(it, ("k", "label", "key"), "%s item %d" % (ctx, i + 1), "k")
            v = self._field(it, ("v", "value"), "%s item %d" % (ctx, i + 1), "v")
            rows.append("<div><dt>%s</dt><dd>%s</dd></div>" % (self.inl(k), self.inl(v)))
        return '<dl class="evk-r-facts">%s</dl>' % "".join(rows)

    def _b_cards(self, b, ctx, depth):
        out, longest = [], 0
        h = "h%d" % self._lvl
        for i, it in enumerate(self._items(b, ctx)):
            c = "%s item %d" % (ctx, i + 1)
            ti = self._field(it, ("title", "name"), c, "title")
            meta = ('<p class="meta">%s</p>' % self.inl(it["meta"])) if self._text_ok(it.get("meta")) else ""
            txt = it.get("text")
            txt = [x for x in (txt if isinstance(txt, list) else [txt]) if self._text_ok(x)]
            longest = max([longest] + [len(self.lead_text(*tx(x))) for x in txt])
            out.append("<li><%s class=\"t\">%s</%s>%s%s</li>" % (h, self.inl(ti), h, meta, "".join(self.para(x) for x in txt)))
        size = " is-short" if longest and longest <= 40 else " is-long" if longest > 220 else ""          # 原站取值: by the longest text, not the count
        return '<ul class="evk-r-cards%s">%s</ul>' % (size, "".join(out))

    def _b_steps(self, b, ctx, depth):
        out = []
        for i, it in enumerate(self._items(b, ctx)):
            if isinstance(it, dict) and not (set(it) <= {"en", "cn"}):
                c = "%s item %d" % (ctx, i + 1)
                ti = self._field(it, ("title", "head"), c, "title", required=False)
                tx_ = self._field(it, ("text",), c, "text", required=not ti)
                out.append("<li>%s%s</li>" % (('<strong class="t">%s</strong>' % self.inl(ti)) if ti else "", self.inl(tx_) if tx_ else ""))
            elif self._text_ok(it):
                out.append("<li>%s</li>" % self.inl(it))
            else:
                raise ValueError("%s item %d is empty" % (ctx, i + 1))
        return '<ol class="evk-r-steps">%s</ol>' % "".join(out)

    def _b_table(self, b, ctx, depth):
        head = self._field(b, ("head", "header", "columns"), ctx, "head")
        rows = self._items(b, ctx, "rows")
        if not isinstance(head, list) or not head:
            raise ValueError("%s: 'head' must be a list of column titles" % ctx)
        for i, r in enumerate(rows):
            if not isinstance(r, list) or len(r) != len(head):
                raise ValueError("%s: row %d has %s cells, the head has %d" % (ctx, i + 1, len(r) if isinstance(r, list) else "no", len(head)))
        cap_ = b.get("caption")
        label = self.lead_text(*tx(cap_)) if self._text_ok(cap_) else self.s("blk_table")
        caption = ("<caption>%s</caption>" % self.inl(cap_)) if self._text_ok(cap_) else ""
        th = "".join('<th scope="col">%s</th>' % self.inl(h) for h in head)
        trs = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % self.inl(c) for c in r) for r in rows)
        return '<div class="evk-r-table" role="region" tabindex="0" aria-label="%s"><table>%s<thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (
            esc(label), caption, th, trs)

    def _b_timeline(self, b, ctx, depth):
        out = []
        for i, it in enumerate(self._items(b, ctx)):
            c = "%s item %d" % (ctx, i + 1)
            at = self._field(it, ("at", "t", "when", "time"), c, "at")
            ti = self._field(it, ("title",), c, "title", required=False)
            tx_ = self._field(it, ("text", "what"), c, "text", required=not ti)
            at_s = self.lead_text(*tx(at)).strip()
            stamp = ('<time datetime="%s">%s</time>' % (esc(at_s), esc(at_s))) if re.fullmatch(r"\d{1,2}:\d{2}", at_s) else '<span data-num>%s</span>' % esc(spaced(at_s))
            out.append("<li>%s<div>%s%s</div></li>" % (stamp, ('<strong class="t">%s</strong>' % self.inl(ti)) if ti else "", self.inl(tx_) if tx_ else ""))
        return '<ol class="evk-r-timeline">%s</ol>' % "".join(out)

    def _b_numbers(self, b, ctx, depth):
        out = []
        for i, it in enumerate(self._items(b, ctx)):
            c = "%s item %d" % (ctx, i + 1)
            n = self._field(it, ("n", "value"), c, "n")
            lab = self._field(it, ("label", "text"), c, "label")
            u = it.get("unit")
            unit = ("<small>%s</small>" % esc(self.lead_text(*tx(u)))) if self._text_ok(u) else ""
            nt = it.get("note")                                      # the qualifier (the year, "about", the list and its edition): printed under the label, quieter
            note = ('<span class="note">%s</span>' % self.inl(nt)) if self._text_ok(nt) else ""
            out.append("<li><b>%s%s</b><span>%s</span>%s</li>" % (esc(self.lead_text(*tx(n)) if isinstance(n, (dict, str)) else n), unit, self.spans(*tx(lab)), note))
        return '<ul class="evk-r-numbers">%s</ul>' % "".join(out)

    def _b_qa(self, b, ctx, depth):
        out = []
        for i, it in enumerate(self._items(b, ctx)):
            c = "%s item %d" % (ctx, i + 1)
            q = self._field(it, ("q", "question"), c, "q")
            a = self._field(it, ("a", "answer"), c, "a")
            if isinstance(a, list):                                   # a list of paragraphs: each one a <p> (its other language right under it)
                paras = [x for x in a if self._text_ok(x)]
                if not paras:
                    raise ValueError("%s has no 'a'" % c)
                ans = "".join(self.para(x) for x in paras)
            else:                                                     # a string or an {en, cn} pair: one answer, two lines
                ans = self.inl(a)
            out.append("<div><dt>%s</dt><dd>%s</dd></div>" % (self.inl(q), ans))
        return '<dl class="evk-r-qa">%s</dl>' % "".join(out)

    def _b_fold(self, b, ctx, depth):
        if depth >= 2:
            raise ValueError("%s: folds nest at most two deep" % ctx)
        ti = self._field(b, ("title",), ctx, "title")
        inner = self.blocks_html(self._items(b, ctx, "blocks"), ctx, depth + 1)
        return '<details class="evk-r-fold evk-fold"%s><summary>%s</summary>%s</details>' % (" open" if b.get("open") else "", self.inl(ti), inner)

    def entity_html(self, rec):
        root = "../"
        lead = self.lead
        L = self.name_lines(rec)
        primary = L[0][0]
        eyebrow = '<p class="evk-eyebrow evk-k">%s</p>' % self.spans(self.where_text(rec, "en"), self.where_text(rec, "zh"))
        h1 = '<h1 class="evk-entity-name" data-fit="%d" lang="%s">%s</h1>' % (name_fit(L[0][0]), L[0][2], esc(primary))
        sub = ('<div class="evk-entity-sub" lang="%s">%s</div>' % (L[1][2], esc(L[1][0]))) if len(L) > 1 else ""
        blurb = ""
        if rec["blurb"]:
            bl = ls(rec["blurb"][0], rec["blurb"][1], lead)
            blurb = '<div class="evk-entity-line evk-entity-blurb" lang="%s">%s</div>' % (bl[0][2], esc(bl[0][0]))
            if len(bl) > 1:
                blurb += '<div class="evk-entity-line evk-entity-blurb sp-2nd" lang="%s">%s</div>' % (bl[1][2], esc(bl[1][0]))
        code = '<div class="evk-entity-code"><span class="evk-tag">%s</span></div>' % self.tag_html(rec, small=False)
        # the name pair stays together in every entity_header form: primary name, then the other language's name, and only then the rule, the code and
        # the line about the entity (a recipe that wants the code or the rule elsewhere moves it with `order`, it never needs the pair split in the DOM)
        head = '<header class="evk-entity-head">%s%s%s<div class="evk-entity-rule"></div>%s%s</header>' % (eyebrow, h1, sub, code, blurb)
        eid = quote(rec["id"], safe="")
        actions = ('<div class="sp-actions"><a class="evk-btn evk-btn--primary" href="%smap.html?to=%s"><span class="evk-k">%s</span></a>'
                   '<a class="evk-btn evk-btn--quiet" href="%smap.html?s=%s"><span class="evk-k">%s</span></a></div>') % (
            root, esc(eid), self.pair("btn_go_here"), root, esc(eid), self.pair("e_on_map"))
        strip = ""
        facts = []
        for f in rec["facts"]:
            if not isinstance(f, dict) or f.get("n") in (None, "") or not f.get("label"):
                continue
            u = tx(f.get("unit")) if f.get("unit") else None
            unit = ("<small>%s</small>" % esc(self.lead_text(*u))) if u else ""
            le, lc = tx(f["label"])
            # EP-4: the word first in the DOM (a screen reader says "Team size 46 people"), the figure on top (starter.css: column-reverse)
            facts.append('<div class="evk-num"><span>%s</span><b>%s%s</b></div>' % (self.spans(le, lc), esc(f["n"]), unit))
        if facts:                                                   # one row of up to three (four from 760 px) cells; more wrap onto the next row (starter.css)
            strip = '<div class="evk-strip" style="--cells:%d;--cells-w:%d">%s</div>' % (min(len(facts), 3), min(len(facts), 4), "".join(facts))
        ctx = "entity %s" % rec["id"]
        parts = []                  # [(title_en, title_cn, body)]
        for pi, pt in enumerate(rec["parts"]):
            if not isinstance(pt, dict) or not pt.get("title"):
                continue
            te, tc = tx(pt["title"])
            texts = pt.get("text")
            texts = texts if isinstance(texts, list) else ([texts] if texts else [])
            body = "".join(self.para(t, "evk-r-p") for t in texts)          # a part's paragraphs are `p` blocks: one prose style for both forms
            if pt.get("blocks"):
                body += self.blocks_html(pt["blocks"], "%s: parts[%d]" % (ctx, pi))
            parts.append([te, tc, [body]])
        cur = None
        if rec["blocks"] and not isinstance(rec["blocks"], list):
            raise ValueError("%s: blocks must be a list" % ctx)
        for bi, b in enumerate(rec["blocks"]):
            bctx = "%s: blocks[%d]" % (ctx, bi)
            titled = isinstance(b, dict) and b.get("title") and str(b.get("type") or b.get("t") or "") != "fold"
            html_ = self.block_html(b, bctx, 0, title=False)
            if titled:
                cur = [tx(b["title"])[0], tx(b["title"])[1], []]
                parts.append(cur)
            elif cur is None:                 # untitled blocks continue the part before them (the last of entity.parts), else they make an "About" part
                cur = parts[-1] if parts else [self.words("e_about", "en"), self.words("e_about", "zh"), []]
                if not parts:
                    parts.append(cur)
            cur[2].append(html_)
        parts = [(p[0], p[1], "".join(p[2])) for p in parts]
        sections = []
        n = 0
        for te, tc, body in parts:
            n += 1
            sections.append(self.part(n, "p%d" % n, te, tc, body))
        if not sections and not rec["blurb"]:
            n += 1
            msg = ('<div class="sp-ph"><span class="evk-tag">%s</span></div>' % self.pair("e_ph_flag")) + self.para(
                {"en": self.words("e_ph_text", "en", name=rec["en"]), "cn": self.words("e_ph_text", "zh", name=rec["cn"])})
            sections.append(self.part(n, "about", self.words("e_about", "en"), self.words("e_about", "zh"), msg))
        route = self.route_part(rec)
        if route:
            n += 1
            sections.append(self.part(n, "how", self.words("e_route", "en"), self.words("e_route", "zh"), route))
        n += 1
        cvnear = self.s("cv_near", floor=self.floor_name(rec["floor"], lead), name=self.plain_name(rec), where=self.at_phrase(rec, lead))
        where_body = (self.line(self.where_text(rec, "en"), self.where_text(rec, "zh")) +
                      '<div class="evk-map sp-near" id="near" hidden><canvas role="img" tabindex="0" aria-label="%s"></canvas>'
                      '<button class="evk-btn evk-btn--quiet evk-btn--sm evk-map-reset" type="button" hidden><span class="evk-k">%s</span></button></div>') % (
            esc(cvnear), self.pair("reset"))
        sections.append(self.part(n, "where", self.words("e_where", "en"), self.words("e_where", "zh"), where_body))
        toc = ""
        if len(sections) - (1 if route else 0) >= 3:               # the contents list is for pages with reading to jump around in (the route part is not reading)
            toc = '<nav class="sp-toc" id="toc" aria-label="%s"><ol>%s</ol></nav>' % (esc(self.s("e_toc")), "".join(
                '<li><a class="sp-toc-link" href="#%s">%s</a></li>' % (re.search(r'id="([^"]+)"', p).group(1), re.search(r'<h2 class="evk-k">(.*?)</h2>', p).group(1)) for p in sections))
        article = '<article class="evk-entity" data-report%s>\n%s\n%s\n%s\n%s\n%s\n</article>\n' % (self.entity_style_attr(rec), head, actions, strip, toc + "\n".join(sections), "")
        pos = self.ordered.index(rec)
        prev = self.ordered[pos - 1] if pos > 0 else None
        nxt = self.ordered[pos + 1] if pos + 1 < len(self.ordered) else None

        def pg(r, key, rel):
            if not r:
                return "<span></span>"
            Lr = self.name_lines(r)
            return ('<a class="sp-pager-link" href="%s" rel="%s"%s><span class="evk-k">%s</span><span class="sp-pager-name" lang="%s">%s</span></a>' % (
                esc(quote(r["page"][2:], safe="/")), rel, self.entity_style_attr(r), self.pair(key), Lr[0][2], esc(Lr[0][0])))
        pager = '<nav class="sp-pager" aria-label="%s">%s%s</nav>\n' % (esc(self.s("e_pager")), pg(prev, "e_prev", "prev"), pg(nxt, "e_next", "next"))
        main = article + pager + self.foot(root, back=True)
        desc = self.s("meta_entity", name=self.plain_name(rec), where=self.where_text(rec, lead), event=self.lead_text(*self.event_name))
        title = "%s%s%s" % (self.plain_name(rec), "｜" if lead == "zh" else " | ", self.lead_text(*self.event_name))
        return self.page(root, "entity", title, desc, main, data_attrs=' data-entity="%s"' % esc(rec["id"]))

    # ---- data/venue.js ----------------------------------------------------------------------------
    def venue_js(self):
        v = json.loads(json.dumps(self.v))
        for e in v["entities"]:
            e["x-page"] = self.ent_by[str(e["id"])]["page"]
        if self.xspecs:                 # the search finds a group by its `words` -- in the entities the build put in it, no others (a tag is not a member)
            by_i = {sp["i"]: sp for sp in self.xspecs}
            v["x-groups"] = [dict({k: val for k, val in g.items() if k not in ("tags", "rooms", "floors", "ids")}, ids=[m["id"] for m in by_i[i]["members"]])
                             if i in by_i and isinstance(g, dict) else g for i, g in enumerate(v["x-groups"])]
        return ("/* event-venue-kit starter · data/venue.js -- the venue as a script, so the pages open from file:// (a fetch of venue.json is refused there).\n"
                "   Written by scripts/starter.py from your venue.json: edit venue.json and rebuild, not this file. `x-page` is each entity's page; each x-groups entry\n"
                "   keeps its words and lists, as `ids`, the entities the build put in that group. */\n"
                "window.EVK_VENUE = %s;\n") % js_json(v)

    def files(self, out_dir=None, force_assets=False):
        """{relative path: text or bytes}. With out_dir, the project's own assets/starter.css and assets/starter.js are left out when they
        exist (they are yours) unless force_assets; `self.kept` lists them."""
        out = {"index.html": self.index_html(), "map.html": self.map_html()}
        for rec in self.ordered:
            out[rec["page"]] = self.entity_html(rec)
        out["data/venue.js"] = self.venue_js()
        out["assets/starter.css"] = (STARTER_DIR / "starter.css").read_bytes()
        out["assets/starter.js"] = (STARTER_DIR / "starter.js").read_bytes()
        self.kept = []
        if out_dir is not None and not force_assets:
            for name in project_assets(out_dir):
                rel = "assets/" + name
                self.kept.append(rel)
                del out[rel]
        return out


# --------------------------------------------------------------------------------------------------
# the API install.py uses
# --------------------------------------------------------------------------------------------------

def _venue(venue):
    if isinstance(venue, (str, Path)):
        try:
            return json.loads(Path(venue).read_text(encoding="utf-8"))
        except OSError as e:
            raise ValueError("cannot read the venue %s: %s" % (venue, e))
        except ValueError as e:
            raise ValueError("%s is not valid JSON: %s" % (venue, e))
    return venue


def plan(venue, roll_card, out_dir, force_assets=False, static_routes=True):
    """The paths render() would write (nothing is written). The project's own assets/starter.css and starter.js are not among them
    while they exist (unless force_assets): they are never a conflict."""
    out = Path(out_dir)
    site = Site(_venue(venue), roll_card, out_dir=None if force_assets else out, static_routes=static_routes)
    paths = [out / rel for rel in site.files(out, force_assets)]
    _report(site)
    return paths


def render(venue, roll_card, out_dir, force=False, force_assets=False, static_routes=True):
    """Write the starter pages for `venue` in the style of `roll_card` (one card of roll.json, with params) under out_dir.
    Returns the paths written. Raises ValueError for a venue the pages cannot be built from, StarterConflict (a FileExistsError with
    .paths) when a page exists and force is off -- then nothing has been written.
    The words come from out_dir/assets/starter.js when it exists (else the kit's). assets/starter.js and assets/starter.css that already
    exist in out_dir are YOURS: force never overwrites them, only force_assets does (the kit's copies replace them). Which were kept is
    in `render.kept` after the call. static_routes=False skips the Node call for the written directions (starter.js writes them in the browser).
    Build warnings (an entity that fits several groups, an unknown entity.group, no written directions) are printed to stderr (at most 8) and
    all of them are in `render.warnings` after the call."""
    out = Path(out_dir)
    site = Site(_venue(venue), roll_card, out_dir=None if force_assets else out, static_routes=static_routes)
    files = site.files(out, force_assets)
    render.kept = [out / rel for rel in site.kept]
    _report(site)
    targets = [(out / rel, data) for rel, data in files.items()]
    conflicts = [p for p, _ in targets if p.exists()]
    if conflicts and not force:
        raise StarterConflict(conflicts)
    written = []
    for p, data in targets:
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            p.write_bytes(data)
        else:
            p.write_text(data, encoding="utf-8", newline="\n")
        written.append(p)
    return written


render.kept = []
render.warnings = []


def _report(site, limit=8):
    """Build warnings (several groups for one entity, an unknown entity.group, no written directions) -> render.warnings and stderr."""
    render.warnings = list(site.warnings)
    for w in site.warnings[:limit]:
        print("starter.py: warning: %s" % w, file=sys.stderr)
    if len(site.warnings) > limit:
        print("starter.py: warning: ... and %d more (render.warnings has all of them)" % (len(site.warnings) - limit), file=sys.stderr)


# --------------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(prog="starter.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("venue", nargs="?", help="venue.json (assets/engine/venue.schema.json)")
    ap.add_argument("roll", nargs="?", help="roll.json with a chosen card (or use --card)")
    ap.add_argument("out", nargs="?", help="project folder (install.py has put evk/ there)")
    ap.add_argument("--card", type=int, help="use this card of the roll even if none was chosen")
    ap.add_argument("--force", action="store_true", help="overwrite existing pages (never your assets/starter.js and assets/starter.css)")
    ap.add_argument("--force-assets", action="store_true", help="also replace assets/starter.js and assets/starter.css with the kit's copies (your edits there are lost)")
    ap.add_argument("--no-routes", action="store_true", help="do not run Node for the written directions on the entity pages (starter.js writes them in the browser)")
    ap.add_argument("--dry-run", action="store_true", help="list the files that would be written")
    ap.add_argument("--selftest", action="store_true", help="run built-in tests")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    if not (a.venue and a.roll and a.out):
        ap.print_usage(sys.stderr)
        print("starter.py: needs <venue.json> <roll.json> <out-dir>", file=sys.stderr)
        return 2
    import draw
    try:
        roll = draw.read_roll(a.roll)
        venue = _venue(a.venue)
        cards = roll.get("cards") or []
        if a.card:
            if not 1 <= a.card <= len(cards):
                raise ValueError("--card must be 1-%d" % len(cards))
            card = cards[a.card - 1]
        else:
            card = draw.pick_chosen_card(roll)
            if card is None:
                raise ValueError("no card has been chosen in %s: python3 scripts/draw.py choose N --reason \"...\" --roll %s (or pass --card N)" % (a.roll, a.roll))
        if a.dry_run:
            for p in plan(venue, card, a.out, a.force_assets, not a.no_routes):
                print("would write", p, "(exists)" if p.exists() else "")
            for n in project_assets(a.out) if not a.force_assets else ():
                print("would keep", Path(a.out) / "assets" / n, "(yours; --force-assets replaces it)")
            return 0
        written = render(venue, card, a.out, a.force, a.force_assets, not a.no_routes)
    except StarterConflict as e:
        print("starter.py: %s\n  pass --force to overwrite" % e, file=sys.stderr)
        for p in e.paths:
            print("  " + str(p), file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError) as e:
        print("starter.py: %s" % e, file=sys.stderr)
        return 2
    for p in written:
        print("wrote", p)
    for p in render.kept:
        print("kept", p, "(yours; --force-assets replaces it with the kit's copy)")
    mine = project_assets(a.out).get("starter.js")
    if mine and not a.force_assets:
        print("words: read from %s" % mine)
    print("%d files under %s: open index.html (from a server, or file://)" % (len(written), a.out))
    return 0


# --------------------------------------------------------------------------------------------------
# selftest
# --------------------------------------------------------------------------------------------------

def _selftest():
    import html.parser
    import shutil
    import subprocess
    import tempfile

    fails = []

    def rn(v, c, out, **kw):                       # most pages are built without the Node call (fast); the written directions have a block of their own
        kw.setdefault("static_routes", False)
        return render(v, c, out, **kw)

    def ok(cond, msg):
        if not cond:
            fails.append(msg)
            print("  FAIL", msg)

    class Check(html.parser.HTMLParser):
        VOID = {"meta", "link", "br", "hr", "input", "img", "source", "wbr", "col"}

        def __init__(self):
            super(Check, self).__init__(convert_charrefs=True)
            self.stack, self.ids, self.hrefs, self.errors, self.text, self.scripts = [], [], [], [], [], []
            self.classes = []

        def handle_starttag(self, tag, attrs):
            d = dict(attrs)
            if "id" in d:
                self.ids.append(d["id"])
            if d.get("href"):
                self.hrefs.append(d["href"])
            if d.get("src"):
                self.scripts.append(d["src"])
            self.classes += (d.get("class") or "").split()
            if tag not in self.VOID:
                self.stack.append(tag)

        def handle_endtag(self, tag):
            if tag in self.VOID:
                return
            if not self.stack or self.stack[-1] != tag:
                self.errors.append("</%s> closes <%s>" % (tag, self.stack[-1] if self.stack else None))
                if tag in self.stack:
                    while self.stack and self.stack.pop() != tag:
                        pass
                return
            self.stack.pop()

        def handle_data(self, data):
            self.text.append(data)

    def check_page(rel, text):
        c = Check()
        c.feed(text)
        ok(not c.errors and not c.stack, "%s: balanced tags (%s %s)" % (rel, c.errors[:2], c.stack[:3]))
        dup = sorted({i for i in c.ids if c.ids.count(i) > 1})
        ok(not dup, "%s: duplicate ids %s" % (rel, dup))
        body = "".join(c.text)
        ok(not re.search(r"\bNone\b|\bundefined\b|\bNaN\b", body), "%s: no None/undefined/NaN in the text" % rel)
        ok(not re.search(r"\{\w+\}", text), "%s: an unfilled {placeholder}" % rel)
        return c

    # ---- the dictionary is valid, complete for what the Python side asks for, and the JS parses
    ui = load_ui()
    ok(all(isinstance(v, dict) and v.get("en") and v.get("cn") for v in ui.values()), "every UI word has en and cn")
    ok(all(not has_cjk(v["en"]) for v in ui.values()), "no Chinese in an English UI word")
    js_src = _UI_RE.sub("", (STARTER_DIR / "starter.js").read_text(encoding="utf-8"))
    py_src = Path(__file__).read_text(encoding="utf-8")
    used = set(re.findall(r'\b(?:S|S2|P|SP|words)\(\s*"([a-z_0-9]+)"', js_src)) | set(re.findall(r'(?:\.pair|\.s|\.s2|\.sp|\.K|\.words)\(\s*"([a-z_0-9]+)"', py_src))
    ok(all(k in ui for k in used if not k.endswith("_")), "every word used by starter.js or starter.py is in the UI block: %s" % sorted(k for k in used if k not in ui))
    ok(all(("grp_" + k) in ui for k in ("entrance", "lobby", "room", "area")), "start-group words exist")
    ok(spaced("共5步，约12米") == "共 5 步，约 12 米", "spaced")
    ok(plural("booth") == "booths" and plural("gallery") == "galleries" and plural("box") == "boxes" and plural("day") == "days", "plural")
    ok(fmt_date("2026-10-24") == ("Sat 24 Oct 2026", "2026 年 10 月 24 日（周六）"), "fmt_date: %s" % (fmt_date("2026-10-24"),))
    ok(fmt_date("Oct 24") is None and fmt_date("2026-02-31") is None, "fmt_date leaves other text alone")
    ok(js_json({"a": "</script><!--"}) == '{"a":"<\\/script><\\!--"}', "js_json escapes </ and <!--")
    node = shutil.which("node")
    if node:
        r = subprocess.run([node, "--check", str(STARTER_DIR / "starter.js")], capture_output=True, text=True)
        ok(r.returncode == 0, "node --check starter.js: " + r.stderr[:200])

    # ---- cards: the kit's own library, both leads
    import draw
    try:
        lib = kit.load_directions()
    except Exception as e:  # the library may be mid-edit by another builder
        print("starter.py selftest: directions library not loadable (%s): page checks skipped" % e)
        return 1 if fails else 0
    cards = []
    for lead in ("en", "zh"):
        cs = draw.draw_cards(lib, 20261024 + (lead == "zh"), 3, (), kit.parse_keep(["lead=" + lead]), None, False, set())
        cards.append((lead, cs[0]))
        if lead == "zh":
            cards.append((lead, cs[1]))
    venue = json.loads((kit.ASSETS_DIR / "demo" / "venue.json").read_text(encoding="utf-8"))
    rich = json.loads(json.dumps(venue))
    rich["event"] = {"name": rich["event"], "date": "2026-10-24", "time": "10:00-17:00", "note": {"en": "Free entry.", "cn": "免费入场。"}}
    rich["x-schematic"] = True
    rich["entities"][0]["blurb"] = {"en": "Seaweed plastics.", "cn": "用海带做的塑料。"}
    rich["entities"][0]["facts"] = [{"n": 46, "unit": {"en": "people", "cn": "人"}, "label": {"en": "Team", "cn": "团队规模"}}, {"n": "2019", "label": "Founded"}]
    rich["entities"][0]["parts"] = [{"title": {"en": "What it is", "cn": "它是什么"}, "text": [{"en": "One.", "cn": "一。"}, {"en": "Two.", "cn": "二。"}]},
                                    {"title": "Find us", "text": "Hall."}, {"title": {"en": "Third", "cn": "第三"}, "text": {"en": "x", "cn": "y"}}]
    rich["entities"][1]["id"] = "orbital/kitchen"          # an id that is not a file name
    tmp = Path(tempfile.mkdtemp(prefix="evk-starter-"))
    try:
        for n, (lead, card) in enumerate(cards):
            for label, v in (("demo", venue), ("rich", rich)):
                out = tmp / ("%s-%d" % (label, n))
                written = rn(v, card, out)
                rels = sorted(str(p.relative_to(out)) for p in written)
                ok("index.html" in rels and "map.html" in rels and "data/venue.js" in rels and "assets/starter.css" in rels and "assets/starter.js" in rels, "files written (%s)" % rels[:5])
                ok(len([r for r in rels if r.startswith("e/")]) == len(v["entities"]), "one page per entity")
                ok(all(("orbital/kitchen" not in r) for r in rels), "an id with a slash is not a path")
                # every page parses, links resolve, scripts are in order
                for p in written:
                    rel = str(p.relative_to(out))
                    if not rel.endswith(".html"):
                        continue
                    text = p.read_text(encoding="utf-8")
                    c = check_page("%s-%d:%s" % (label, n, rel), text)
                    ok('data-evk-lead="%s"' % lead in text and ('lang="zh-CN"' if lead == "zh" else 'lang="en"') in text, "%s: lead %s on <html>" % (rel, lead))
                    base = p.parent
                    for h in c.hrefs + c.scripts:
                        if re.match(r"^(https?:|mailto:|#)", h):
                            continue
                        target = base / h.split("#")[0].split("?")[0]
                        ok(target.name == "" or target.exists() or target.parts[-2:] == ("evk", "tokens.css") or "evk" in target.parts, "%s: link %s resolves" % (rel, h))
                    order = [s.rsplit("/", 1)[-1] for s in c.scripts]
                    ok(order == ["venue.js"] + ENGINE_ORDER + ["starter.js"], "%s: script order %s" % (rel, order))
                    ok(text.count("evk/tokens.css") == 1 and text.index("evk/tokens.css") < text.index("evk/base.css") < text.index("evk/recipe.css") < text.index("assets/starter.css"), "%s: css order" % rel)
                # the content that must be there without JavaScript
                idx = (out / "index.html").read_text(encoding="utf-8")
                ok(idx.count('class="evk-cell"') == len(v["entities"]), "index: one cell per entity")
                ok(("待定" in idx and "TBA" in idx) == (label == "demo"), "index: missing date and time say 待定 / TBA (%s)" % label)
                if label == "rich":
                    ok("Sat 24 Oct 2026" in idx and "10:00-17:00" in idx and "Free entry." in idx and "noindex" in idx and "sp-banner" in idx, "index: event facts, note, schematic banner")
                mp = (out / "map.html").read_text(encoding="utf-8")
                ok(mp.count("data-sel=") == len(v["entities"]), "map: the static directory lists every entity")
                ok(all(i in mp for i in ('id="from"', 'id="to-q"', 'id="prev"', 'id="all"', 'id="next"', 'aria-live="polite"', 'id="sheet-place"', 'id="sheet-route"', '<noscript>')), "map: sheets, form, controls, live region, noscript")
                first = sorted((out / "e").glob("*.html"))[0].read_text(encoding="utf-8")
                ok("map.html?to=" in first and "evk-entity-head" in first and "data-report" in first and "data-part" in first and 'id="near"' in first, "entity: head, report, parts, near map, directions link")
                # a bilingual pair is written primary first
                if lead == "zh":
                    ok(re.search(r'class="evk-k"><span class="cn" lang="zh-CN">[^<]*</span><span class="en"', idx) is not None, "zh lead: the Chinese line comes first in a pair")
                else:
                    ok(re.search(r'class="evk-k"><span class="en" lang="en">[^<]*</span><span class="cn"', idx) is not None, "en lead: the English line comes first in a pair")
                vj = (out / "data" / "venue.js").read_text(encoding="utf-8")
                m = re.search(r"window\.EVK_VENUE = (.*);\n$", vj, re.S)
                data = json.loads(m.group(1).replace("<\\/", "</")) if m else {}
                ok(len(data.get("entities", [])) == len(v["entities"]) and all("x-page" in e for e in data.get("entities", [])), "venue.js: the venue, with x-page")
        # rich entity page: facts strip, three parts + contents list, no placeholder
        out = tmp / "rich-0"
        pg = (out / "e" / "kelp.html").read_text(encoding="utf-8")
        ok(pg.count('class="evk-num"') == 2 and "Founded" in pg and pg.count("data-part") == 5 and 'id="how"' in pg and 'id="toc"' in pg and "sp-ph" not in pg,
           "rich entity page: strip, three parts + how to get here + where, toc, no placeholder")
        ok("evk-entity-blurb" in pg and "evk-entity-line" in pg, "rich entity page: blurb")
        pl = (out / "e" / "orbital-kitchen.html").read_text(encoding="utf-8")
        ok("sp-ph" in pl, "placeholder part when there is nothing to show (marked)")
        # names given as plain strings, no floor names, an area without a label: one line per name, no None, nothing broken
        plain = json.loads(json.dumps(venue))
        plain["event"] = "Open Day"
        for e in plain["entities"]:
            e["name"] = e["name"]["en"]
            e.pop("short", None)
        for f in plain["floors"]:
            f.pop("name", None)
        for lead, card in (cards[0], cards[1]):
            out = tmp / ("plain-" + lead)
            rn(plain, card, out)
            for p in sorted(out.rglob("*.html")):
                c = check_page("plain-%s:%s" % (lead, p.relative_to(out)), p.read_text(encoding="utf-8"))
            ix = (out / "index.html").read_text(encoding="utf-8")
            ok("Open Day" in ix and "Kelp &amp; Co. Bioplastics" in ix and "海带" not in ix, "plain-string names: one language, the English one")
        # ---- round 4: floors (short for chips and lines, name for headings, no string twice), hints, examples, F10, singular
        def text_nodes(html_text):
            c = Check()
            c.feed(html_text)
            return c.text

        fl_v = json.loads(json.dumps(venue))
        for f in fl_v["floors"]:
            f["short"] = {"en": f["id"], "cn": "%d 层" % f["level"]}
            f["name"] = {"en": f["id"], "cn": "%s层" % "一二三四五"[f["level"] - 1]}        # the English name IS the short form
        fl_v["event"] = {"name": venue["event"], "group_by": "floor"}
        for lead, card in (cards[0], cards[1]):
            out = tmp / ("floors-" + lead)
            rn(fl_v, card, out)
            ix = (out / "index.html").read_text(encoding="utf-8")
            heads = re.findall(r"<h3 id=\"g-[^>]*>(.*?)</h3>", ix, re.S)
            ok(len(heads) == 3, "floors: three group headings")
            for h in heads:
                parts = [t.strip() for t in text_nodes(h) if t.strip()]
                body = [t for t in parts if not re.search(r"\d+ (booths?|个)|^\d+$", t)]
                ok(len(body) == len(set(body)), "floors: no string twice in a heading (%s)" % body)
            ok(re.search(r'class="sp-fid" lang="[^"]*">(1F|1 层)<', ix) is not None, "floors: the short form (lead language) is the chip")
            ey = re.search(r'evk-eyebrow evk-k">(.*?)</p>', (out / "e" / "kelp.html").read_text(encoding="utf-8"), re.S).group(1)
            ok("1F" in ey and "1 层" in ey and "First Floor" not in ey, "floors: location lines say the short form (%s)" % re.sub("<[^>]+>", "|", ey)[:60])
        # a name without a short: the router's default (the id; the level + " 层")
        dflt = [Site(venue, cards[0][1]).floor_short(f["id"], "zh") for f in venue["floors"]]
        ok(dflt == ["%d 层" % f["level"] for f in sorted(venue["floors"], key=lambda f: f["level"])], "floors: default short is the level + 层 (%s)" % dflt)

        # the hint on the map follows the projection of the card
        import copy
        for proj, en_hint, zh_hint in (("orbit", "Drag to rotate", "拖动旋转"), ("exploded", "Drag to rotate", "拖动旋转"), ("oblique", "Drag to pan", "拖动平移"),
                                       ("plan", "Drag to rotate", "拖动旋转")):                  # a plan turns in its plane under one finger (the engine's drag mode)
            for lead, card in ((cards[0]), (cards[1])):
                c2 = copy.deepcopy(card)
                c2["params"]["map"]["projection"] = proj
                site = Site(venue, c2)
                hp = re.sub("<[^>]+>", "|", site.hint_pair())
                ok((en_hint in hp) and (zh_hint in hp), "map hint %s / %s: %s" % (proj, lead, hp))
                ok(en_hint.split(",")[0].lower() in site.words("cv_near", "en", floor="1F", name="N", where="here").lower(), "cv_near follows %s" % proj)
        # search example: real names in the lead language, never a tag id, F10 spacing
        site_en, site_zh = Site(venue, cards[0][1]), Site(venue, cards[1][1])
        ex_en, ex_zh = site_en.placeholder_examples("en"), site_zh.placeholder_examples("zh")
        tags_all = {t for e in venue["entities"] for t in e.get("tags", [])}
        ok(ex_en and not (set(re.split(r", ", ex_en)) & tags_all) and not has_cjk(ex_en), "example (en): names, no tag id: %s" % ex_en)
        ok(has_cjk(ex_zh) and not (set(ex_zh.split("、")) & tags_all) and not re.search(r"[\u3400-\u9fff]\s+[\u3400-\u9fff]", ex_zh), "example (zh): names, no tag id, no CJK-space-CJK: %s" % ex_zh)
        ph = site_zh.s("search_ph", ex="Kelp、盐风风筝")
        ok("例如 Kelp" in ph and not re.search(r"[\u3400-\u9fff]\s+[\u3400-\u9fff]", ph), "zh placeholder: space before Latin, none between Chinese: %s" % ph)
        ok(site_en.words("n_things", "en", n=1) == "1 booth" and site_en.words("n_things", "en", n=3) == "3 booths", "1 booth, 3 booths")
        # F10 on every zh-lead page: no whitespace between two Chinese characters in any text node
        for n, (lead, card) in enumerate(cards):
            if lead != "zh":
                continue
            for p in sorted((tmp / ("rich-%d" % n)).rglob("*.html")):
                bad = [t for t in text_nodes(p.read_text(encoding="utf-8")) if re.search(r"[\u3400-\u9fff]\s+[\u3400-\u9fff]", t)]
                ok(not bad, "F10: %s has CJK space CJK: %s" % (p.name, bad[:1]))
        # EP-4: the word first in the DOM, the figure second
        ok(re.search(r'<div class="evk-num"><span>.*?</span><b>46<small>', (tmp / "rich-0" / "e" / "kelp.html").read_text(encoding="utf-8"), re.S) is not None, "strip: label first, then the figure and its unit")

        # grouping: tag (x-groups, terms.tags, first tag), room, floor; a bad value stops the build
        gv = json.loads(json.dumps(venue))
        gv["event"] = {"name": venue["event"], "group_by": "tag"}
        gv["terms"]["tags"] = {"materials": {"en": "Materials", "cn": "材料"}}
        gs = Site(gv, cards[1][1])
        ok(gs.group_by == "tag" and len(gs.groups) >= 2 and all(x["g"] for x in gs.ents), "group_by tag: groups and a key on every entity")
        ok(gs.groups[0]["key"] == "materials" and gs.groups[0]["cn"] == "材料", "group_by tag: the label comes from terms.tags, in terms.tags order first")
        out = tmp / "group-tag"
        rn(gv, cards[1][1], out)
        ix = (out / "index.html").read_text(encoding="utf-8")
        ok('id="seg-group"' in ix and 'data-group="tag"' in ix and 'id="seg-floor"' in ix and ix.count('<section class="sp-group"') == len(gs.groups), "group_by tag: both controls, one section per group")
        ok(len(re.findall(r'<li data-id="[^"]*" data-floor="[^"]*" data-g="[^"]*">', ix)) == len(venue["entities"]), "group_by tag: every cell carries data-g")
        gv2 = json.loads(json.dumps(gv))
        gv2["x-groups"] = [{"words": ["craft", "手作"], "tags": ["craft"]}, {"words": ["Space", "太空"], "tags": ["space", "energy"]}]
        g2 = Site(gv2, cards[1][1])
        ok([g["key"] for g in g2.groups][:2] == ["craft", "space"] and g2.groups[0]["cn"] == "手作" and g2.groups[0]["en"] == "Craft" and g2.groups[-1]["key"] == "other",
           "group_by tag: x-groups with tags, bilingual words, the rest in Other (%s)" % [g["key"] for g in g2.groups])
        gv3 = json.loads(json.dumps(venue))
        gv3["event"] = {"name": venue["event"], "group_by": "room"}
        g3 = Site(gv3, cards[0][1])
        ok(g3.group_by == "room" and len(g3.groups) >= 3 and all(x["g"] for x in g3.ents), "group_by room: one group per occupied room or area")
        rn(gv3, cards[0][1], tmp / "group-room")
        gv4 = json.loads(json.dumps(venue))
        gv4["event"] = {"name": venue["event"], "group_by": "colour"}
        try:
            Site(gv4, cards[0][1])
            ok(False, "an unknown group_by should stop the build")
        except ValueError as e:
            ok("group_by" in str(e), "an unknown group_by is an error")

        # reading blocks: all twelve, in a part and at the top level; errors name the place
        bv = json.loads(json.dumps(venue))
        t = {"en": "Text", "cn": "文字"}
        every = [{"type": "p", "text": [t, "Plain"]}, {"type": "note", "text": t}, {"type": "quote", "text": t, "by": t}, {"type": "list", "items": [t, t], "ordered": True},
                 {"type": "facts", "items": [{"k": t, "v": "105"}]}, {"type": "cards", "title": t, "items": [{"title": t, "meta": "11-14", "text": t}, {"title": t, "text": t}]},
                 {"type": "steps", "title": t, "items": [t, {"title": t, "text": t}]},
                 {"type": "table", "title": t, "caption": t, "head": [t, t, t, t], "rows": [[t, t, t, "x"], ["a", "b", "c", "d"]]},
                 {"type": "timeline", "title": t, "items": [{"at": "10:30", "text": t}, {"at": "Late", "title": t, "text": t}]},
                 {"type": "numbers", "items": [{"n": "3", "label": t}, {"n": "20", "unit": t, "label": t}]},
                 {"type": "qa", "title": t, "items": [{"q": t, "a": t}]},
                 {"type": "fold", "title": t, "blocks": [{"type": "p", "text": t}, {"type": "fold", "title": t, "blocks": [{"type": "p", "text": "x"}]}]}]
        bv["entities"][0]["blocks"] = every
        bv["entities"][0]["parts"] = [{"title": t, "text": t, "blocks": [{"type": "note", "text": t}]}]
        out = tmp / "blocks"
        rn(bv, cards[0][1], out)
        pg = (out / "e" / "kelp.html").read_text(encoding="utf-8")
        check_page("blocks:kelp", pg)
        for cls in ("evk-r-p", "evk-r-note", "evk-r-quote", "evk-r-list", "evk-r-facts", "evk-r-cards", "evk-r-steps", "evk-r-table", "evk-r-timeline", "evk-r-numbers", "evk-r-qa", "evk-r-fold"):
            ok(('class="%s' % cls) in pg or (' %s ' % cls) in pg, "blocks: %s is on the page" % cls)
        ok("<ol class=\"evk-r-list\">" in pg and '<time datetime="10:30">10:30</time>' in pg and '<span data-num>Late</span>' in pg and 'is-short' in pg, "blocks: ordered list, a time stamp, free-text time, short cards")
        ok('role="region" tabindex="0" aria-label=' in pg and "<caption>" in pg, "blocks: the table is a labelled, focusable region")
        ok(pg.split('id="how"')[0].count("<details") == 2, "blocks: two folds (one nested)")
        titles = re.findall(r'data-title="([^"]*)"', pg)
        ok(len(titles) == 1 + 5 + 2 and titles[0] == "Text" and titles[-2:] == ["How to get here", "Where"],
           "blocks: the part first, then one part per titled block (cards, steps, table, timeline, qa = 5), then How to get here and Where %s" % titles)
        ok('id="toc"' in pg, "blocks: contents list for 3+ parts")
        for bad, msg in (([{"type": "nope"}], "unknown block type"), ([{"type": "p"}], "no 'text'"), ([{"type": "timeline", "items": [{"text": "x"}]}], "no 'at'"),
                         ([{"type": "table", "head": ["a", "b"], "rows": [["x"]]}], "row 1"), ([{"type": "qa", "items": [{"q": "x"}]}], "no 'a'"), ("x", "must be a list"),
                         ([{"type": "fold", "title": "a", "blocks": [{"type": "fold", "title": "b", "blocks": [{"type": "fold", "title": "c", "blocks": [{"type": "p", "text": "x"}]}]}]}], "two deep")):
            bb = json.loads(json.dumps(venue))
            bb["entities"][0]["blocks"] = bad
            try:
                rn(bb, cards[0][1], tmp / "blocks-bad")
                ok(False, "a bad block should stop the build: %s" % (bad,))
            except ValueError as e:
                ok(msg in str(e) and "entity kelp" in str(e) and not (tmp / "blocks-bad").exists(), "block error names the place: %s" % e)

        # your copies of assets/starter.js and starter.css: the words come from them, force never overwrites them
        mine = tmp / "mine"
        rn(venue, cards[0][1], mine)
        js = mine / "assets" / "starter.js"
        js.write_text(js.read_text(encoding="utf-8").replace('"Open the map"', '"Open the PLAN"'), encoding="utf-8")
        (mine / "assets" / "starter.css").write_text("/* mine */", encoding="utf-8")
        before = js.read_bytes()
        got = rn(venue, cards[0][1], mine, force=True)
        ok("Open the PLAN" in (mine / "index.html").read_text(encoding="utf-8"), "words are read from the project's assets/starter.js")
        ok(js.read_bytes() == before and (mine / "assets" / "starter.css").read_text(encoding="utf-8") == "/* mine */", "force keeps your assets")
        ok(not any(p.name in ("starter.js", "starter.css") for p in got) and len(render.kept) == 2, "the kept assets are reported (render.kept)")
        ok(not any(p.name in ("starter.js", "starter.css") for p in plan(venue, cards[0][1], mine)), "plan() leaves your assets out: no conflict")
        rn(venue, cards[0][1], mine, force=True, force_assets=True)
        ok("Open the PLAN" not in (mine / "index.html").read_text(encoding="utf-8") and js.read_bytes() != before and (mine / "assets" / "starter.css").read_text(encoding="utf-8") != "/* mine */",
           "force_assets replaces them with the kit's (and the words with it)")
        js.write_text('/* ui:begin */ {"tba": {"en": "TBC", "cn": "未定"}} /* ui:end */', encoding="utf-8")      # a project copy that lacks most words: the kit's fill in
        rn(venue, cards[0][1], mine, force=True)
        ok("TBC" in (mine / "index.html").read_text(encoding="utf-8") and "Open the map" in (mine / "index.html").read_text(encoding="utf-8"), "a word the project copy lacks is the kit's")

        # ---- round 5 ----------------------------------------------------------------------------------
        # (5) the name pair stays together in the head DOM, whatever the card: eyebrow, name, other-language name, then rule, code, line
        for n, (lead, card) in enumerate(cards):
            hd = re.search(r'<header class="evk-entity-head">(.*?)</header>', (tmp / ("rich-%d" % n) / "e" / "kelp.html").read_text(encoding="utf-8"), re.S).group(1)
            order = [c.split()[0] for c in re.findall(r'<(?:h1|div|p) class="([^"]*)"', hd)]
            ok(order[:5] == ["evk-eyebrow", "evk-entity-name", "evk-entity-sub", "evk-entity-rule", "evk-entity-code"] and order[5:] == ["evk-entity-line"] * 2,
               "head order (%s): %s" % (lead, order))

        # (6) groups: entity.group wins; else the first tag; several matches warn; a group's words reach only its members
        def gsite(ent_patch=None, xg=None, gb="tag"):
            w = json.loads(json.dumps(venue))
            w["event"] = {"name": venue["event"], "group_by": gb}
            if xg is not None:
                w["x-groups"] = xg
            for eid, patch in (ent_patch or {}).items():
                next(e for e in w["entities"] if e["id"] == eid).update(patch)
            return w, Site(w, cards[1][1])
        xg = [{"id": "making", "words": ["makers", "手作", "bench"], "tags": ["craft"]}, {"id": "sci", "words": ["Lab", "实验"], "tags": ["science", "craft"]},
              {"id": "gallery", "words": ["Gallery"], "rooms": ["GALLERY"]}]
        w6, g6 = gsite(xg=xg)
        by = {x["id"]: x.get("xg") for x in g6.ents}
        ok(by["loomhouse"] == "making" and by["starlight"] == "sci" and by["driftmap"] == "gallery" and by["kelp"] is None, "groups: first tag, ids, rooms, none: %s" % {k: by[k] for k in ("loomhouse", "starlight", "driftmap", "kelp")})
        ok(any("loomhouse" in m and "making" in m and "sci" in m for m in g6.warnings), "groups: an entity that fits several groups is named in a warning (%s)" % g6.warnings[:2])
        ok(g6.groups[-1]["key"] == "other" and "kelp" in [x["id"] for x in g6.groups[-1]["members"]], "groups: the rest goes to Other")
        w6b, g6b = gsite({"loomhouse": {"group": "sci"}, "echo": {"group": "nope"}}, xg=xg)
        ok({x["id"]: x.get("xg") for x in g6b.ents}["loomhouse"] == "sci" and not any("loomhouse" in m for m in g6b.warnings), "groups: entity.group wins and settles the warning")
        ok(any("echo" in m and "nope" in m for m in g6b.warnings) and {x["id"]: x.get("xg") for x in g6b.ents}["echo"] == "making", "groups: an unknown entity.group warns and falls back to the tags")
        js6 = g6b.venue_js()
        sg = json.loads(re.search(r"window\.EVK_VENUE = (.*);\n$", js6, re.S).group(1).replace("<\\/", "</"))["x-groups"]
        ok(all("tags" not in g and "ids" in g for g in sg) and "loomhouse" in sg[1]["ids"] and "loomhouse" not in sg[0]["ids"] and sg[0]["words"][0] == "makers",
           "groups: venue.js gives the search each group's words and exactly its members (a shared tag adds nothing)")
        w6c, g6c = gsite({"kelp": {"group": "science"}})
        ok({x["id"]: x["g"] for x in g6c.ents}["kelp"] == "science" and not g6c.warnings, "groups (no x-groups): entity.group names a terms.tags group")
        out = tmp / "group-x"
        import contextlib
        import io
        with contextlib.redirect_stderr(io.StringIO()) as quiet:             # the warnings of this venue are the point of the test above
            rn(w6, cards[1][1], out)
        ok("fits several groups" in quiet.getvalue() and "render.warnings" in quiet.getvalue() and len(render.warnings) >= 9, "render prints the build warnings (at most 8) and keeps all of them in render.warnings")
        ix = (out / "index.html").read_text(encoding="utf-8")
        btns = re.search(r'id="seg-group">(.*?)</div>', ix, re.S).group(1)
        ok(btns.count("<button") == len(g6.groups) + 1 and all(('<span class="evk-k">' in b) for b in re.findall(r"<button.*?</button>", btns, re.S)[1:3]), "group control: a button per group, labelled in both languages")
        ok('style="--sp-floors:3"' in ix, "home: the preview knows the number of floors")

        # (7) one code format: <floor short>·<booth>; the room's number goes between only when booth numbers repeat on a floor; an area label is not a code
        uq = json.loads(json.dumps(venue))
        for i, e in enumerate(uq["entities"]):
            e["booth"] = "B%02d" % (i + 1)
        for f in uq["floors"]:
            for a in f.get("areas", []):
                a["label"] = "AREA"
        su, sz = Site(uq, cards[0][1]), Site(uq, cards[1][1])
        ok(not su.code_room and su.code_text(su.ent_by["kelp"]) == "1F·B01" and sz.code_text(sz.ent_by["starlight"]) == "2 层·B12" and su.code_text(su.ent_by["lanterns"]) == "1F·B18",
           "codes: floor short + booth ('%s', '%s', area label left out '%s')" % (su.code_text(su.ent_by["kelp"]), sz.code_text(sz.ent_by["starlight"]), su.code_text(su.ent_by["lanterns"])))
        sd = Site(venue, cards[0][1])
        ok(sd.code_room and sd.code_text(sd.ent_by["kelp"]) == "1F·H1·01" and sd.code_text(sd.ent_by["driftmap"]) == "2F·03".replace("03", "01") or sd.code_text(sd.ent_by["driftmap"]) == "2F·01",
           "codes: booth numbers that repeat -> the room's number between (%s, %s)" % (sd.code_text(sd.ent_by["kelp"]), sd.code_text(sd.ent_by["driftmap"])))
        ok('<small>1F·H1·</small>01' in (tmp / "demo-0" / "index.html").read_text(encoding="utf-8") and ">1F·H1·01<" in (tmp / "demo-0" / "e" / "kelp.html").read_text(encoding="utf-8"), "codes: the same on the card and in the entity head")

        # (10) numbers print their note; qa answers: a text, a pair, a list of paragraphs
        nq = json.loads(json.dumps(venue))
        nq["entities"][0]["blocks"] = [{"type": "numbers", "items": [{"n": "31", "label": t, "note": {"en": "2027 edition", "cn": "2027 版"}}, {"n": "9", "label": t}]},
                                       {"type": "qa", "items": [{"q": t, "a": "One"}, {"q": t, "a": t}, {"q": t, "a": [t, "Second paragraph", {"en": "Third", "cn": "第三"}]}]}]
        rn(nq, cards[1][1], tmp / "nq")
        pg = (tmp / "nq" / "e" / "kelp.html").read_text(encoding="utf-8")
        ok(pg.count('<span class="note">') == 1 and "2027 版" in pg and "2027 edition" in pg, "numbers: the note is printed")
        ok(pg.count("<dd>") == 3 and re.search(r"<dd><p[^>]*>[^<]*</p><p[^>]*>[^<]*</p><p[^>]*>Second paragraph</p>", pg) is not None, "qa: a list of paragraphs is one <p> each")
        try:
            nq["entities"][0]["blocks"] = [{"type": "qa", "items": [{"q": t, "a": []}]}]
            rn(nq, cards[1][1], tmp / "nq2")
            ok(False, "an empty qa answer list should stop the build")
        except ValueError as e:
            ok("no 'a'" in str(e), "qa: an empty list of paragraphs is an error: %s" % e)

        # (8) the written directions: markup (with canned steps), no Node -> the map link only, and the real engine when Node and --describe-all are there
        canned = {"kelp": [{"kind": "walk", "en": {"head": "Walk", "text": "Go straight."}, "cn": {"head": "直行", "text": "一直往前走。"}, "climb": False},
                           {"kind": "stairs", "en": {"head": "Up", "text": "Take the stairs up to 2F."}, "cn": {"head": "上楼", "text": "走楼梯上到 2 层。"}, "climb": True}]}
        sr = Site(venue, cards[1][1])
        sr._routes = lambda start: canned
        rp = sr.entity_html(sr.ent_by["kelp"])
        ok('<ol class="evk-r-steps"><li><strong class="t"><span lang="zh-CN">直行</span><span class="sp-2nd" lang="en">Walk</span></strong>' in rp and rp.count('<li class="is-climb">') >= 1,
           "route: steps in the lead language first, a climb step is .is-climb")
        ok('data-from="entrance:1F"' in rp and 'data-from="lobby:1F"' in rp and "map.html?to=kelp&amp;from=entrance%3A1F" in rp and "<details" in rp, "route: entrance box, the entity floor's lobby in a fold, map links with ?from=")
        ok(rp.index('id="how"') < rp.index('id="where"'), "route: the part sits before Where")
        no_lobby = Site(venue, cards[0][1])
        ok([x["id"] for x in no_lobby.route_starts(no_lobby.ent_by["lumen"])] == ["entrance:1F", "lobby:2F"], "route: lobby of the entity's own floor")
        sn = Site(venue, cards[0][1], static_routes=False)
        np_ = sn.entity_html(sn.ent_by["kelp"])
        ok('class="sp-route"' in np_ and "evk-r-steps" not in np_ and "map.html?to=kelp&amp;from=" in np_ and not sn.warnings, "route: without the Node call the part holds the map link, and no warning")
        bare = json.loads(json.dumps(venue))
        for f in bare["floors"]:
            f.pop("entrance", None)
            f.pop("lobby", None)
        sb = Site(bare, cards[0][1])
        ok('id="how"' not in sb.entity_html(sb.ent_by["kelp"]), "route: a venue with no entrance and no lobby has no How to get here part")
        if node:
            real = Site(venue, cards[0][1])
            rr = real.entity_html(real.ent_by["lumen"])
            if '<ol class="evk-r-steps">' in rr:
                ok('<li class="is-climb">' in rr and "<strong class=\"t\">" in rr, "route: engine steps in the page, the stairs step to 2F marked as a climb (%s)" % real.warnings)
            else:
                print("  note: this engine has no --describe-all (or it failed): %s" % real.warnings[:1])

        # conflicts
        out = tmp / "demo-0"
        try:
            rn(venue, cards[0][1], out)
            ok(False, "a second render without force should refuse")
        except StarterConflict as e:
            ok(len(e.paths) >= 5 and isinstance(e, FileExistsError), "conflicts are listed")
        mark = out / "index.html"
        mark.write_text("mine", encoding="utf-8")
        try:
            rn(venue, cards[0][1], out)
        except StarterConflict:
            pass
        ok(mark.read_text(encoding="utf-8") == "mine", "nothing is overwritten without force")
        rn(venue, cards[0][1], out, force=True)
        ok(mark.read_text(encoding="utf-8") != "mine", "force overwrites")
        # bad data stops with a message
        bad = json.loads(json.dumps(venue))
        bad["entities"][0]["room"] = "NOPE"
        try:
            rn(bad, cards[0][1], tmp / "bad")
            ok(False, "an entity in a missing room should stop the build")
        except ValueError as e:
            ok("NOPE" in str(e) and not (tmp / "bad").exists(), "a missing room is an error, nothing written")
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)
    print("starter.py selftest: %s" % ("%d FAILED" % len(fails) if fails else "all checks passed"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
