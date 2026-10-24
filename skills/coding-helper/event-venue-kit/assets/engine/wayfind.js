/* event-venue-kit · assets/engine/wayfind.js
   ---------------------------------------------------------------------------
   Two things live here, both pure geometry / text, no DOM:

   1. EVK.venueModel(venue [, entities])   the authored venue (venue.schema.json)
      turned into the model the map and the router share: walls derived from
      rooms + blocks + doors + entrance (shared edges merged, block sides and
      door gaps subtracted), door signs, booth positions, stairwell/lift links,
      open areas (walkable zones with no walls: a corridor, a concourse, a ring
      gallery round a void: `holes`) and voids (an opening to the floor below),
      `warnings` for every data mistake and `errors` (the ones that hide an
      entity: its room or area id is unknown; they are also in `warnings`).
      venue-map.js needs this file loaded first.

   2. EVK.wayfind.create(venue) -> { starts(), plan(startId, entityId, opts),
      describe(plan, lang) }   walking directions inside the building.
      Each floor becomes a walkable grid (0.25 m cells) that is clear of solid
      blocks and of walls, so rooms are entered only through their doors; rooms
      are closed except the one you start in and the one you go to; a Dijkstra
      search prefers the middle of corridors; the line is pulled straight where
      the line of sight allows. Between floors the route picks, layer by layer,
      whichever stairwell (or lift) gives the shortest total walk, and comes out
      of it where it went in. Every leg comes back as segments per floor, hops
      between floors and a few steps written for people (zh / en / both).
      Open areas are plain floor to the router, but they are named in the words:
      "沿西走廊走到 07 号展位，约 12 米。" / "Follow the west corridor to booth 07,
      about 12 m." (a booth in an area has no door, so those steps never say one).

   Also here: every model entity carries `.mono`, the characters on its map token, unique in the venue (EVK.monograms(list) gives the
   same for a plain list; see "monograms" below), and a Node CLI:
     node wayfind.js --selftest [venue.json]
     node wayfind.js --describe-all <venue.json> --from <startId> [--lead en|zh]   every entity's written route as JSON (see below)

   Everything numeric below is a tuning value. The "source" figures are the
   ones the CollegeFair site used (原站取值); pass { tuning: {...} } to
   create() to change them. Nothing here is specific to a school fair.

   Works as a classic <script> (window.EVK) and under Node (globalThis.EVK,
   module.exports) so the router can be tested without a browser.
   --------------------------------------------------------------------------- */
(function () {
  "use strict";
  var G = typeof window !== "undefined" ? window : globalThis;
  var EVK = G.EVK = G.EVK || {};

  /* ---- tuning (原站取值 / source value → range that still works) ----------- */
  var TUNE = {
    cell: 0.25,          // grid cell, m                          (0.2 – 0.4)
    wallClear: 0.2,      // cells closer than this to a wall are blocked   (0.15 – 0.3)
    landing: 0.7,        // a stair landing: walkable cells this close     (0.5 – 1.2)
    stairLink: 2.5,      // stairs this close on consecutive floors = one stairwell (auto-link only)
    centre: 0.9,         // paths like at least this much room each side   (0.6 – 1.5)
    centreGain: 1.6,     // how much they like it (cost x 1 + gain at zero room)    (0.8 – 3)
    sight: 0.3,          // straightened lines keep this far from walls    (0.2 – 0.5)
    doorW: 1.2,          // default door gap, m                            (0.9 – 2)
    signOffset: 0.9,     // a room's number stands this far outside its first door  (0.5 – 1.5)
    minGap: 0.8,         // closest two booths in a room, m (validation only)
    doorSnap: 0.3,       // a door further than this from its room's boundary is a mistake (warning, door ignored); nearer ones are moved onto the wall   (0.15 – 0.5)
    doorProbe: 0.4,      // validation: the spot this far outside a door must be open floor, not another room, a block or a void
    boothEdge: 0.6,      // booths laid out by the model in an area with holes keep this far from the area's edges and from the holes   (0.4 – 1)
    entranceIn: 1.2,     // "start at the entrance" stands this far inside the opening
    stairPenalty: 4,     // metres of walking a flight of stairs is "worth" in the choice of stairwell
    liftPenalty: 8,      // … and a lift (waiting)
    through: 0,          // 1: rooms are walkable by default (open-plan venue); 0: closed except start/target
    viaMin: 4,           // a leg is described "along the west corridor" when it spends at least this many metres …
    viaShare: 0.4        // … and at least this share of its length inside one open area
  };

  /* ---- small text helpers ---------------------------------------------------- */
  var CJK = "\\u3400-\\u9fff\\uf900-\\ufaff";
  var RE_A = new RegExp("([" + CJK + "])([A-Za-z0-9])", "g"), RE_B = new RegExp("([A-Za-z0-9])([" + CJK + "])", "g");
  /* one space between CJK and an adjacent Latin letter / digit, both ways: 走到 301 门口 */
  EVK.spaced = function (t) { return String(t).replace(RE_A, "$1 $2").replace(RE_B, "$1 $2"); };

  function nm(v, fb) {            // "text" | {en, cn} -> {en, cn}
    if (v == null || v === "") return { en: fb || "", cn: fb || "" };
    if (typeof v === "string") return { en: v, cn: v };
    return { en: v.en || v.cn || fb || "", cn: v.cn || v.en || fb || "" };
  }
  function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }
  var RE_CJK = new RegExp("[" + CJK + "]");
  function hasCJK(s) { return RE_CJK.test(String(s || "")); }
  function stripThe(s) { return String(s || "").replace(/^the\s+/i, ""); }   // the words add their own "the"
  /* the name an English sentence may use for an entity: `short`, else name.en, never a Chinese string ("" when both are) */
  function enName(e) {
    var c = [e.short, e.name && e.name.en];
    for (var i = 0; i < c.length; i++) if (c[i] && !hasCJK(c[i])) return String(c[i]);
    return "";
  }

  /* ---- monograms: the few characters that stand for an entity on a map token -------------------
     Natural form (2 characters): a Latin single word gives its first two letters ("Kelp" -> "Ke"), several words give the initials
     of the first two ("Pixel Reef" -> "PR"), Chinese gives the first two characters. Two entities of one venue may come out the
     same ("Lux Lab" and "Lantern Lab" are both "LL", "Tideclock" and "Tidal" both "Ti"). Then every entity of that family changes
     together, deterministically: to its BOOTH number when the family's booths are all different (and at most 4 characters),
     otherwise to a longer letter form (3, then 4 … characters: "LUL" / "LAL", "Tide" / "Tida"), until no two are alike.
     An entity's own `mono` (authored, any short string, 4 characters or fewer reads best) is used as written and never changes;
     the entities that would clash with it move instead. Same list in, same monograms out. Each model entity carries the result
     as `.mono`; EVK.monograms() gives the same for a plain list. */
  function monoLetters(s, k) {
    s = String(s == null ? "" : s).trim() || "?";
    if (hasCJK(s)) return Array.from(s).slice(0, k).join("");
    var words = s.split(/[^A-Za-z0-9\u00c0-\u024f]+/).filter(Boolean), n = words.length;
    if (!n) return s.slice(0, k);
    if (n === 1) return words[0].slice(0, k).replace(/^./, function (c) { return c.toUpperCase(); });
    var out = "";
    for (var i = 0; i < n && out.length < k; i++) out += i === 0 && n < k ? words[0].slice(0, k - n + 1) : words[i][0];
    return out.slice(0, k).toUpperCase();
  }
  function solveMonos(list) {
    var n = list.length, fixed = [], fam = [], lvl = {}, out = [], i;
    function usableBooth(e) { var b = e.booth == null ? "" : String(e.booth); return b && b.length <= 4 ? b : ""; }
    function shortOf(e) { return e.short || (e.name && e.name.en) || e.id; }
    for (i = 0; i < n; i++) {
      var e = list[i], own = e.raw ? e.raw.mono : e.mono;
      fixed[i] = own == null ? "" : String(own).trim();
      fam[i] = fixed[i] ? null : monoLetters(shortOf(e), 2);
      if (fam[i] != null && lvl[fam[i]] == null) lvl[fam[i]] = 0;
    }
    function val(i) {
      if (fixed[i]) return fixed[i];
      var l = lvl[fam[i]];
      return l === 0 ? fam[i] : l === 1 ? usableBooth(list[i]) : monoLetters(shortOf(list[i]), l + 1);
    }
    var stuck = {};                                                      // families that ran out of forms (identical names and booths): the author can set `mono`
    for (var round = 0; round < 12; round++) {
      var groups = {}, bumped = {}, moved = false;
      for (i = 0; i < n; i++) { out[i] = val(i); (groups[out[i]] = groups[out[i]] || []).push(i); }
      Object.keys(groups).forEach(function (key) {
        if (groups[key].length < 2) return;
        groups[key].forEach(function (i) {
          var f = fam[i];
          if (f == null || bumped[f] || stuck[f]) return;
          var l = lvl[f], seen = {}, distinct = true;
          for (var j = 0; j < n; j++) if (fam[j] === f) { var b = usableBooth(list[j]); if (!b || seen[b]) distinct = false; seen[b] = 1; }
          var next = l === 0 && distinct ? 1 : Math.max(2, l + 1);
          if (next > 7) { stuck[f] = true; return; }
          lvl[f] = next; bumped[f] = moved = true;
        });
      });
      if (!moved) break;
    }
    for (i = 0; i < n; i++) out[i] = val(i) || (fixed[i] ? fixed[i] : monoLetters(shortOf(list[i]), 2));
    return out;
  }
  /* EVK.monograms([entity, …]) -> { id: monogram }: entities as authored ({id, short, name, booth, mono}) or from the model */
  EVK.monograms = function (list) {
    var a = solveMonos(list || []), o = {};
    (list || []).forEach(function (e, i) { o[e.id] = a[i]; });
    return o;
  };

  /* ---- geometry -------------------------------------------------------------- */
  function polyOf(it) {
    if (it.poly) return it.poly.map(function (p) { return [+p[0], +p[1]]; });
    if (it.rect) { var r = it.rect, x = +r[0], y = +r[1], w = +r[2], h = +r[3]; return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]; }
    return [];
  }
  function inside(pts, x, y) {
    var c = false;
    for (var i = 0, j = pts.length - 1; i < pts.length; j = i++) {
      var a = pts[i], b = pts[j];
      if ((a[1] > y) !== (b[1] > y) && x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]) c = !c;
    }
    return c;
  }
  function bboxOf(pts) {
    var b = [Infinity, Infinity, -Infinity, -Infinity];
    pts.forEach(function (p) { b[0] = Math.min(b[0], p[0]); b[1] = Math.min(b[1], p[1]); b[2] = Math.max(b[2], p[0]); b[3] = Math.max(b[3], p[1]); });
    return b;
  }
  function centroidOf(pts) {      // area-weighted; falls back to the mean for degenerate polygons
    var a = 0, cx = 0, cy = 0;
    for (var i = 0; i < pts.length; i++) {
      var p = pts[i], q = pts[(i + 1) % pts.length], cr = p[0] * q[1] - q[0] * p[1];
      a += cr; cx += (p[0] + q[0]) * cr; cy += (p[1] + q[1]) * cr;
    }
    if (Math.abs(a) < 1e-9) {
      var sx = 0, sy = 0; pts.forEach(function (p) { sx += p[0]; sy += p[1]; });
      return [sx / pts.length, sy / pts.length];
    }
    return [cx / (3 * a), cy / (3 * a)];
  }
  /* a point inside the polygon near its middle: the centroid, else the bbox centre, else the inside point of a coarse scan that is nearest to it */
  function centreOf(poly) {
    var c = centroidOf(poly);
    if (inside(poly, c[0], c[1])) return c;
    var bb = bboxOf(poly), mid = [(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2];
    if (inside(poly, mid[0], mid[1])) return mid;
    var best = null, bd = Infinity;
    for (var j = 0; j <= 24; j++) for (var i = 0; i <= 24; i++) {
      var x = bb[0] + (bb[2] - bb[0]) * i / 24, y = bb[1] + (bb[3] - bb[1]) * j / 24, d = Math.hypot(x - mid[0], y - mid[1]);
      if (d < bd && inside(poly, x, y)) { bd = d; best = [x, y]; }
    }
    return best || [poly[0][0] * 0.9 + mid[0] * 0.1, poly[0][1] * 0.9 + mid[1] * 0.1];
  }
  function edgesOf(pts) {
    var out = [];
    for (var i = 0; i < pts.length; i++) out.push([pts[i], pts[(i + 1) % pts.length]]);
    return out;
  }
  function segDist(px, py, ax, ay, bx, by) {
    var dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy || 1;
    var t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / l2));
    return Math.hypot(px - ax - t * dx, py - ay - t * dy);
  }
  function outwardOf(pts, a, b) {   // unit normal of edge a->b pointing out of the polygon (winding-free)
    var ex = b[0] - a[0], ey = b[1] - a[1], l = Math.hypot(ex, ey) || 1;
    var nx = ey / l, ny = -ex / l;
    if (inside(pts, (a[0] + b[0]) / 2 + nx * 0.02, (a[1] + b[1]) / 2 + ny * 0.02)) { nx = -nx; ny = -ny; }
    return [nx, ny];
  }
  function lenOf(pts) {
    var s = 0;
    for (var i = 1; i < pts.length; i++) s += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    return s;
  }
  function round2(v) { return Math.round(v * 100) / 100; }

  /* a room or an area holds a point: inside its outer ring and in none of its holes (only areas have `holes`) */
  function within(it, x, y) {
    if (!inside(it.poly, x, y)) return false;
    var h = it.holes;
    if (h) for (var i = 0; i < h.length; i++) if (inside(h[i], x, y)) return false;
    return true;
  }
  function ringEdges(it) {                 // the edges of the outer ring and of every hole
    var out = edgesOf(it.poly);
    (it.holes || []).forEach(function (h) { out = out.concat(edgesOf(h)); });
    return out;
  }
  function edgeDist(edges, x, y) {         // distance from a point to the nearest of these edges
    var d = Infinity;
    edges.forEach(function (e) { d = Math.min(d, segDist(x, y, e[0][0], e[0][1], e[1][0], e[1][1])); });
    return d;
  }
  /* the middle of an area for its name and plate. Without holes that is centreOf(); with holes the middle may be the hole,
     so the area is cut into bands (north / south of the holes' bounding box, west / east of it) and the centroid of the
     largest band is used: a ring gallery is named on its widest side, never on the void in the middle. */
  function bandCentre(poly, holes) {
    if (!holes || !holes.length) return centreOf(poly);
    var it = { poly: poly, holes: holes }, bb = bboxOf(poly), all = [];
    holes.forEach(function (h) { all = all.concat(h); });
    var hb = bboxOf(all), hx = (hb[0] + hb[2]) / 2, N = 48, bands = { n: [], s: [], w: [], e: [] };
    for (var j = 0; j < N; j++) for (var i = 0; i < N; i++) {
      var x = bb[0] + (bb[2] - bb[0]) * (i + 0.5) / N, y = bb[1] + (bb[3] - bb[1]) * (j + 0.5) / N;
      if (!within(it, x, y)) continue;
      bands[y < hb[1] ? "n" : y > hb[3] ? "s" : x < hx ? "w" : "e"].push([x, y]);
    }
    var best = null;
    ["n", "s", "w", "e"].forEach(function (k) { if (bands[k].length && (!best || bands[k].length > best.length)) best = bands[k]; });
    if (!best) return centreOf(poly);
    var cx = 0, cy = 0;
    best.forEach(function (p) { cx += p[0]; cy += p[1]; });
    cx /= best.length; cy /= best.length;
    if (within(it, cx, cy)) return [round2(cx), round2(cy)];
    var nb = best[0], nd = Infinity;                                   // a bent band: the sample nearest to its mean
    best.forEach(function (p) { var d = Math.hypot(p[0] - cx, p[1] - cy); if (d < nd) { nd = d; nb = p; } });
    return [round2(nb[0]), round2(nb[1])];
  }

  function unionSpans(spans) {
    var out = [];
    spans.slice().sort(function (p, q) { return p[0] - q[0]; }).forEach(function (s) {
      if (out.length && s[0] <= out[out.length - 1][1] + 1e-6) out[out.length - 1][1] = Math.max(out[out.length - 1][1], s[1]);
      else out.push([s[0], s[1]]);
    });
    return out;
  }
  function cutSpans(spans, a, b) {
    var out = [];
    spans.forEach(function (s) {
      if (b <= s[0] || a >= s[1]) { out.push([s[0], s[1]]); return; }
      if (a > s[0]) out.push([s[0], a]);
      if (b < s[1]) out.push([b, s[1]]);
    });
    return out;
  }

  /* the edge of `pts` that the point (x, y) lies on (within tol): { a, b, axis, c, along, t, n } or null */
  function locate(pts, x, y, tol) {
    var best = null, bd = tol;
    edgesOf(pts).forEach(function (e, i) {
      var d = segDist(x, y, e[0][0], e[0][1], e[1][0], e[1][1]);
      if (d <= bd) { bd = d; best = { i: i, a: e[0], b: e[1] }; }
    });
    if (!best) return null;
    best.dist = bd;
    var a = best.a, b = best.b, len = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    best.n = outwardOf(pts, a, b);
    best.t = Math.max(0, Math.min(len, ((x - a[0]) * (b[0] - a[0]) + (y - a[1]) * (b[1] - a[1])) / len));
    best.len = len;
    best.pt = [a[0] + (b[0] - a[0]) * best.t / len, a[1] + (b[1] - a[1]) * best.t / len];
    if (Math.abs(a[0] - b[0]) < 1e-6) { best.axis = "v"; best.c = a[0]; best.along = best.pt[1]; }
    else if (Math.abs(a[1] - b[1]) < 1e-6) { best.axis = "h"; best.c = a[1]; best.along = best.pt[0]; }
    else best.axis = null;
    return best;
  }

  /* ---- walls: the outline and the rooms' sides, merged where they share an edge, less what a
     block already shows, the doors and the entrance. Axis-aligned edges are merged; any other
     edge is kept whole (diagonal venues work, they just are not merged). -------------------- */
  function wallsOf(outline, rooms, blocks, entrance, W, fid) {
    var L = { v: {}, h: {} }, free = [];
    function put(ax, c, s0, s1) {
      var k = String(round2(c));
      (L[ax][k] = L[ax][k] || { c: round2(c), spans: [] }).spans.push([s0, s1]);
    }
    function shape(pts) {
      edgesOf(pts).forEach(function (e) {
        var a = e[0], b = e[1];
        if (Math.abs(a[0] - b[0]) < 1e-6) put("v", a[0], Math.min(a[1], b[1]), Math.max(a[1], b[1]));
        else if (Math.abs(a[1] - b[1]) < 1e-6) put("h", a[1], Math.min(a[0], b[0]), Math.max(a[0], b[0]));
        else free.push({ a: a, b: b, len: Math.hypot(b[0] - a[0], b[1] - a[1]), spans: null });
      });
    }
    shape(outline);
    rooms.forEach(function (r) { shape(r.poly); });
    ["v", "h"].forEach(function (ax) { Object.keys(L[ax]).forEach(function (k) { L[ax][k].spans = unionSpans(L[ax][k].spans); }); });
    free.forEach(function (f) { f.spans = [[0, f.len]]; });
    function cutAt(ax, c, s0, s1) {
      Object.keys(L[ax]).forEach(function (k) {
        if (Math.abs(L[ax][k].c - c) < 0.05) L[ax][k].spans = cutSpans(L[ax][k].spans, s0, s1);
      });
    }
    function cutFree(e, t0, t1) {
      free.forEach(function (f) {
        if (f.a === e.a || (f.a[0] === e.a[0] && f.a[1] === e.a[1] && f.b[0] === e.b[0] && f.b[1] === e.b[1])) f.spans = cutSpans(f.spans, t0, t1);
      });
    }
    blocks.forEach(function (b) {              // a block's own sides are painted by the block (a void has rails, not walls: the wall stays)
      if (b.kind === "void") return;
      edgesOf(b.poly).forEach(function (e) {
        var a = e[0], c = e[1];
        if (Math.abs(a[0] - c[0]) < 1e-6) cutAt("v", a[0], Math.min(a[1], c[1]), Math.max(a[1], c[1]));
        else if (Math.abs(a[1] - c[1]) < 1e-6) cutAt("h", a[1], Math.min(a[0], c[0]), Math.max(a[0], c[0]));
      });
    });
    if (entrance && entrance.edge) {
      var e = entrance.edge, w = entrance.width / 2;
      if (e.axis) cutAt(e.axis, e.c, e.along - w, e.along + w);
      else cutFree(e, e.t - w, e.t + w);
    }
    rooms.forEach(function (r) {
      r.doors.forEach(function (d) {
        if (!d.edge) { W.push("floor " + fid + ", room " + r.id + ": door " + r.id + "@" + JSON.stringify([d.x, d.y]) + " is " + d.far + " m from the room's boundary (a door must lie on the wall, within " + d.snap + " m), so it is ignored"); return; }
        var e = d.edge;
        if (e.axis) cutAt(e.axis, e.c, e.along - d.w / 2, e.along + d.w / 2);
        else cutFree(e, e.t - d.w / 2, e.t + d.w / 2);
      });
    });
    var out = [];
    ["v", "h"].forEach(function (ax) {
      Object.keys(L[ax]).map(function (k) { return L[ax][k]; }).sort(function (p, q) { return p.c - q.c; }).forEach(function (ln) {
        ln.spans.forEach(function (s) {
          if (s[1] - s[0] < 0.15) return;
          out.push(ax === "v" ? [ln.c, round2(s[0]), ln.c, round2(s[1])] : [round2(s[0]), ln.c, round2(s[1]), ln.c]);
        });
      });
    });
    free.forEach(function (f) {
      var ux = (f.b[0] - f.a[0]) / f.len, uy = (f.b[1] - f.a[1]) / f.len;
      f.spans.forEach(function (s) {
        if (s[1] - s[0] < 0.15) return;
        out.push([round2(f.a[0] + ux * s[0]), round2(f.a[1] + uy * s[0]), round2(f.a[0] + ux * s[1]), round2(f.a[1] + uy * s[1])]);
      });
    });
    return out;
  }

  /* booths in a room: explicit `at` keeps its place, then the room's `slots`, else a grid inside the
     room's bounding box (aspect-aware, inset 1 m from the walls; layout.cols fixes the columns) */
  function placeBooths(room, ents) {
    var auto = ents.filter(function (e) { return !e.at; });
    if (!auto.length) return;
    var slots = room.slots;
    if (slots && slots.length >= auto.length) {
      auto.forEach(function (e, i) { e.at = [+slots[i][0], +slots[i][1]]; });
      return;
    }
    if (room.holes && room.holes.length) { spreadBooths(room, ents, auto, 0.6); return; }
    var b = room.bbox, w = b[2] - b[0], h = b[3] - b[1], m = Math.min(1, w / 4, h / 4);
    var x0 = b[0] + m, y0 = b[1] + m, gw = w - 2 * m, gh = h - 2 * m, n = auto.length;
    var cols = (room.layout && room.layout.cols) || Math.max(1, Math.min(n, Math.round(Math.sqrt(n * gw / gh)))), rows = Math.ceil(n / cols);
    auto.forEach(function (e, i) {
      var p = [x0 + (i % cols + 0.5) * gw / cols, y0 + (Math.floor(i / cols) + 0.5) * gh / rows];
      if (!inside(room.poly, p[0], p[1])) p = room.c.slice();      // a grid point outside an oddly shaped room
      e.at = [round2(p[0]), round2(p[1])];
    });
  }

  /* booths in an area with holes (a ring gallery): a grid in the bounding box would land in the hole, so take the spots of the
     area that keep `edge` metres from its edges and holes, pick them as far apart as possible (the booths already placed count),
     then hand them out in order round the holes, clockwise from the top left, so booth 01, 02, 03 … walk round the ring. */
  function spreadBooths(room, ents, auto, edge) {
    var b = room.bbox, edges = ringEdges(room), step = 0.5, cand = [], chosen = [], x, y, d;
    function collect(clear) {
      cand = [];
      for (x = b[0] + step / 2; x < b[2]; x += step) for (y = b[1] + step / 2; y < b[3]; y += step) {
        if (within(room, x, y) && edgeDist(edges, x, y) >= clear) cand.push([x, y]);
      }
    }
    collect(edge);
    if (cand.length < auto.length) collect(edge / 2);
    var clear = cand.filter(function (p) { return !(room.avoid || []).some(function (q) { return Math.hypot(p[0] - q[0], p[1] - q[1]) < 1.2; }); });
    if (clear.length >= auto.length) cand = clear;                      // not in front of a door or a stair landing, when there is room for that
    ents.forEach(function (e) { if (e.at) chosen.push(e.at); });
    var picked = [];
    for (var n = 0; n < auto.length && cand.length; n++) {
      var bi = 0, bs = -Infinity;
      cand.forEach(function (p, i) {
        var s = Infinity;
        chosen.forEach(function (q) { s = Math.min(s, Math.hypot(p[0] - q[0], p[1] - q[1])); });
        if (!chosen.length) s = -Math.hypot(p[0] - room.c[0], p[1] - room.c[1]);       // the first one: nearest the middle of the area
        if (s > bs + 1e-9) { bs = s; bi = i; }
      });
      chosen.push(cand[bi]); picked.push(cand[bi]); cand.splice(bi, 1);
    }
    var all = []; room.holes.forEach(function (h) { all = all.concat(h); });
    var hb = bboxOf(all), hx = (hb[0] + hb[2]) / 2, hy = (hb[1] + hb[3]) / 2;
    picked.sort(function (p, q) {
      var a = (Math.atan2(p[1] - hy, p[0] - hx) + 3 * Math.PI / 4 + 4 * Math.PI) % (2 * Math.PI), c = (Math.atan2(q[1] - hy, q[0] - hx) + 3 * Math.PI / 4 + 4 * Math.PI) % (2 * Math.PI);
      return a - c;
    });
    auto.forEach(function (e, i) { var p = picked[i] || room.c; e.at = [round2(p[0]), round2(p[1])]; });
  }

  /* ---- the model ------------------------------------------------------------- */
  var cache = typeof WeakMap !== "undefined" ? new WeakMap() : null;

  EVK.venueModel = function (venue, entities, tuning) {
    if (!entities && !tuning && cache && cache.has(venue)) return cache.get(venue);
    var m = buildModel(venue, entities || venue.entities || [], tuning);
    if (!entities && !tuning && cache) cache.set(venue, m);
    return m;
  };

  function buildModel(venue, entList, tuning) {
    var T = {};
    Object.keys(TUNE).forEach(function (k) { T[k] = tuning && tuning[k] != null ? tuning[k] : TUNE[k]; });
    var W = [], E = [], terms = {
      booth: venue.terms && venue.terms.booth ? nm(venue.terms.booth) : { en: "booth", cn: "展位" },
      room: venue.terms && venue.terms.room ? nm(venue.terms.room) : { en: "Room", cn: "" }
    };
    function bad(msg) { W.push(msg); E.push(msg); }       // an error is also a warning, so "warnings is empty" stays the one test a build needs
    var floors = (venue.floors || []).slice().sort(function (a, b) { return a.level - b.level; }).map(function (f) {
      var outline = polyOf({ poly: f.outline });
      var rooms = (f.rooms || []).map(function (r) {
        var poly = polyOf(r), c = centreOf(poly);       // a concave room: the bbox centre if it is inside, else a point that is
        var room = {
          id: String(r.id), label: String(r.label != null ? r.label : r.id), name: nm(r.name, String(r.label != null ? r.label : r.id)),
          poly: poly, c: c, bbox: bboxOf(poly), floor: f.id, layout: r.layout || null, slots: r.slots || null,
          through: r.through != null ? !!r.through : !!T.through, doors: [], sign: null
        };
        (r.doors || []).forEach(function (d) {
          var x = +d[0], y = +d[1], w = d[2] != null ? +d[2] : T.doorW, e = locate(poly, x, y, T.doorSnap);
          if (e) { x = round2(e.pt[0]); y = round2(e.pt[1]); }                                  // within doorSnap of a wall: it is on the wall
          room.doors.push({ x: x, y: y, w: w, edge: e, n: e ? e.n : null, far: e ? 0 : round2(edgeDist(edgesOf(poly), x, y)), snap: T.doorSnap });
        });
        var d0 = room.doors.find(function (d) { return d.edge; });
        if (d0) room.sign = [round2(d0.edge.pt[0] + d0.n[0] * T.signOffset), round2(d0.edge.pt[1] + d0.n[1] * T.signOffset)];
        return room;
      });
      /* open areas: walkable zones without walls (a corridor, a concourse). They are rooms in every way a lookup cares about
         (an id, a name, a polygon, a centre, a floor, booths laid on them) except that they have no walls, no doors and no
         plate unless the author gives a label; the router treats their floor as plain open floor. */
      var areas = (f.areas || []).map(function (a, i) {
        var poly = polyOf(a), lab = a.label != null ? String(a.label) : "", id = String(a.id != null ? a.id : "A" + (i + 1));
        /* holes: rings cut out of the area (a void in a ring gallery, a column block in a hall). A hole is a polygon, or the [x, y, w, h] shorthand. */
        var holes = (a.holes || []).map(function (h) { return polyOf(Array.isArray(h) && h.length === 4 && typeof h[0] === "number" ? { rect: h } : { poly: h }); }).filter(function (h) { return h.length >= 3; });
        return {
          id: id, label: lab, plate: lab !== "", name: nm(a.name, lab || id), poly: poly, holes: holes, c: bandCentre(poly, holes), bbox: bboxOf(poly), floor: f.id,
          layout: a.layout || null, slots: a.slots || null, kind: a.kind === "corridor" ? "corridor" : "open", area: true, through: true, doors: [], sign: null
        };
      });
      var blocks = (f.blocks || []).map(function (b, i) {
        var poly = polyOf(b), bb = bboxOf(poly);
        return {
          id: String(b.id != null ? b.id : "B" + (i + 1)), kind: b.kind || "solid", poly: poly, c: [(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2], bbox: bb,
          size: Math.min(bb[2] - bb[0], bb[3] - bb[1]), label: b.label != null ? nm(b.label) : null,
          doors: (b.doors || []).map(function (d) { return [+d[0], +d[1]]; }), links: b.links != null ? String(b.links) : null, floor: f.id, key: null
        };
      });
      /* voids stay in `blocks` (so the router treats them as solid: nobody walks into a drop) and are listed again as `voids`;
         `rails` is their edges, which the router keeps its distance from like a wall */
      var voids = blocks.filter(function (b) { return b.kind === "void"; }), rails = [];
      voids.forEach(function (v) { edgesOf(v.poly).forEach(function (e) { rails.push([e[0][0], e[0][1], e[1][0], e[1][1]]); }); });
      var entrance = null;
      if (f.entrance && f.entrance.at) {
        var at = f.entrance.at, e = locate(outline, +at[0], +at[1], 1.5);
        if (e) {
          entrance = {
            at: e.pt, width: f.entrance.width != null ? +f.entrance.width : 2.4, dir: [-e.n[0], -e.n[1]], edge: e,
            name: f.entrance.name ? nm(f.entrance.name) : { en: "Entrance", cn: "入口" }
          };
        } else W.push("floor " + f.id + ": the entrance " + JSON.stringify(at) + " is not on the outline");
      }
      var lobby = f.lobby && f.lobby.at ? { at: [+f.lobby.at[0], +f.lobby.at[1]], name: nm(f.lobby.name, f.id + " Lobby") } : null;
      if (lobby) {
        if (!inside(outline, lobby.at[0], lobby.at[1])) W.push("floor " + f.id + ": the lobby is outside the outline");
        blocks.forEach(function (b) { if (inside(b.poly, lobby.at[0], lobby.at[1])) W.push("floor " + f.id + ": the lobby is inside block " + b.id); });
      }
      var walls = wallsOf(outline, rooms, blocks, entrance, W, f.id);
      /* names: `name` heads a section ("Fourth Floor / 四层"); `short` is the one used in a sentence, a chip, a tag ("4F" / "4 层").
         Without `short`: the id, and "<level> 层" (the floor's name when its level is below 1). */
      var fname = nm(f.name, f.id), fshort = f.short != null && f.short !== "" ? nm(f.short, f.id) : { en: String(f.id), cn: f.level >= 1 ? f.level + " 层" : fname.cn };
      return {
        id: f.id, level: f.level, name: fname, short: fshort, outline: outline, bbox: bboxOf(outline), rooms: rooms, areas: areas, blocks: blocks,
        voids: voids, rails: rails, walls: walls, entrance: entrance, lobby: lobby
      };
    });
    var floorById = {}, roomById = {}, order = {};
    floors.forEach(function (f, i) {
      floorById[f.id] = f; order[f.id] = i;
      f.rooms.concat(f.areas).forEach(function (r) {            // rooms and areas share one id space: an entity's `room` may name either
        if (roomById[r.id]) W.push("room or area id " + r.id + " is used twice; ids must be unique");
        roomById[r.id] = r;
      });
    });
    floors.forEach(function (f, i) {                            // authoring mistakes around areas and voids
      f.areas.forEach(function (a) {
        f.rooms.forEach(function (r) { if (within(a, r.c[0], r.c[1]) || inside(r.poly, a.c[0], a.c[1])) W.push("floor " + f.id + ": area " + a.id + " overlaps room " + r.id + " (an area is open floor, not a room)"); });
        a.holes.forEach(function (h, hi) {
          if (!h.every(function (p) { return inside(a.poly, p[0], p[1]); })) W.push("floor " + f.id + ": hole " + (hi + 1) + " of area " + a.id + " reaches outside the area's outer ring");
        });
      });
      /* a door must open onto open floor: the spot just outside it may not be another room (a door drawn on the wall two rooms
         share), a block or a void (facing a solid), or outside the building. An open hall (`through`) is a fine thing to open into. */
      f.rooms.forEach(function (r) {
        r.doors.forEach(function (d) {
          if (!d.edge) return;
          var px = d.x + d.n[0] * T.doorProbe, py = d.y + d.n[1] * T.doorProbe, tag = "floor " + f.id + ": door " + r.id + "@" + JSON.stringify([d.x, d.y]) + " opens ", why = null;
          for (var k = 0; k < f.rooms.length && !why; k++) {
            var o = f.rooms[k];
            if (o !== r && !o.through && inside(o.poly, px, py)) why = tag + "into " + o.id + " (a door cannot lead into another room; draw it on a wall that faces open floor)";
          }
          for (k = 0; k < f.blocks.length && !why; k++) {
            if (inside(f.blocks[k].poly, px, py)) why = tag + "onto " + (f.blocks[k].kind === "void" ? "void " : "block ") + f.blocks[k].id + " (nobody can stand there)";
          }
          if (!why && !inside(f.outline, px, py) && !(f.entrance && f.entrance.edge && Math.hypot(d.x - f.entrance.at[0], d.y - f.entrance.at[1]) < f.entrance.width)) why = tag + "outside the building";
          if (why) W.push(why);
        });
      });
      f.voids.forEach(function (v) {
        if (i === 0) W.push("floor " + f.id + ": void " + v.id + " is on the lowest floor and opens onto nothing");
        f.rooms.forEach(function (r) { if (inside(v.poly, r.c[0], r.c[1]) || inside(r.poly, v.c[0], v.c[1])) W.push("floor " + f.id + ": room " + r.id + " overlaps void " + v.id); });
        f.blocks.forEach(function (b) { if (b !== v && b.kind !== "void" && (inside(v.poly, b.c[0], b.c[1]) || inside(b.poly, v.c[0], v.c[1]))) W.push("floor " + f.id + ": block " + b.id + " overlaps void " + v.id); });
      });
    });
    /* the room or area (rooms first) whose polygon holds a point on a floor, else null */
    function whereIs(f, p) {
      var all = f.rooms.concat(f.areas);
      for (var i = 0; i < all.length; i++) if (within(all[i], p[0], p[1])) return all[i];
      return null;
    }

    /* entities: a room or an area (`room`), or a point on a floor (`at` + `floor`: whichever room or area holds it, else none),
       an optional booth label, a position */
    var ents = [], entById = {}, perRoom = {};
    entList.forEach(function (e) {
      var room = e.room != null && e.room !== "" ? roomById[e.room] : null, fl = null;
      if (e.room != null && e.room !== "") {
        if (!room) { bad("entity " + e.id + ": room " + e.room + " does not exist (no room or area has that id)"); return; }
        fl = floorById[room.floor];
        if (e.floor != null && e.floor !== room.floor) W.push("entity " + e.id + ": floor " + e.floor + " is not the floor of " + e.room + " (" + room.floor + ")");
      } else {
        fl = e.floor != null ? floorById[e.floor] : null;
        if (!fl || !e.at) { bad("entity " + e.id + ": needs a room (a room or area id), or at + floor"); return; }
        room = whereIs(fl, [+e.at[0], +e.at[1]]);
      }
      var name = nm(e.name, e.id), ent = {
        id: String(e.id), name: name, short: e.short || name.en, color: e.color || "#777777", room: room ? room.id : null, floor: fl.id, area: !!(room && room.area),
        booth: e.booth != null ? String(e.booth) : null, at: e.at ? [+e.at[0], +e.at[1]] : null, tags: e.tags || [], raw: e
      };
      if (entById[ent.id]) W.push("entity id " + ent.id + " appears twice");
      entById[ent.id] = ent; ents.push(ent);
      var key = room ? room.id : "~" + fl.id;
      (perRoom[key] = perRoom[key] || []).push(ent);
    });
    Object.keys(perRoom).forEach(function (rid) {
      var room = roomById[rid], list = perRoom[rid];
      if (room && room.holes && room.holes.length) {                    // spots to keep clear of: the doors and stair landings on this floor
        var fl0 = floorById[room.floor]; room.avoid = [];
        fl0.rooms.forEach(function (r) { r.doors.forEach(function (d) { room.avoid.push([d.x, d.y]); }); });
        fl0.blocks.forEach(function (b) { b.doors.forEach(function (d) { room.avoid.push(d); }); });
      }
      if (room) placeBooths(room, list);
      list.forEach(function (e, i) {
        if (e.booth == null) e.booth = (i + 1 < 10 ? "0" : "") + (i + 1);
        var f = floorById[e.floor];
        if (room && !within(room, e.at[0], e.at[1])) W.push("entity " + e.id + ": its booth is outside " + (room.area ? "area " : "room ") + room.id + (room.holes && room.holes.length && inside(room.poly, e.at[0], e.at[1]) ? " (it is in a hole of the area)" : ""));
        if (!room && !inside(f.outline, e.at[0], e.at[1])) W.push("entity " + e.id + ": its position is outside the outline of " + f.id);
        f.blocks.forEach(function (b) { if (inside(b.poly, e.at[0], e.at[1])) W.push("entity " + e.id + ": its booth is inside " + (b.kind === "void" ? "void " : "block ") + b.id); });
      });
      for (var i = 0; i < list.length; i++) for (var j = i + 1; j < list.length; j++) {
        if (Math.hypot(list[i].at[0] - list[j].at[0], list[i].at[1] - list[j].at[1]) < T.minGap) W.push("booths " + list[i].id + " and " + list[j].id + " are closer than " + T.minGap + " m");
      }
    });

    /* where an area's name goes on the map: the spot inside it (kept 0.3 m off its edge) farthest from its own booths, near the middle */
    floors.forEach(function (f) {
      f.areas.forEach(function (a) {
        var mine = ents.filter(function (e) { return e.room === a.id; }), b = a.bbox, best = a.c, bs = -Infinity;
        if (mine.length) {
          for (var j = 0; j <= 10; j++) for (var i = 0; i <= 10; i++) {
            var x = b[0] + (b[2] - b[0]) * i / 10, y = b[1] + (b[3] - b[1]) * j / 10, d = Infinity, edge = Infinity;
            if (!within(a, x, y)) continue;
            edge = edgeDist(ringEdges(a), x, y);                          // the outer ring and the holes
            if (edge < 0.3) continue;
            mine.forEach(function (e) { d = Math.min(d, Math.hypot(e.at[0] - x, e.at[1] - y)); });
            var sc = Math.min(d, 6) - 0.03 * Math.hypot(x - a.c[0], y - a.c[1]);
            if (sc > bs) { bs = sc; best = [x, y]; }
          }
        }
        a.labelAt = best;
      });
    });

    /* connectors: stairs and lifts that continue on the next floor. Same `links` value = same
       stairwell; without `links`, stairs of one kind on consecutive levels within stairLink metres. */
    var auto = 0;
    floors.forEach(function (f, i) {
      f.blocks.forEach(function (b) {
        if (b.kind !== "stairs" && b.kind !== "lift") return;
        if (b.links) b.key = b.links;
        else if (!b.key) b.key = b.kind + "~" + (++auto);
        var nxt = floors[i + 1];
        if (!nxt || b.links) return;
        nxt.blocks.forEach(function (o) {
          if (o.kind === b.kind && !o.links && !o.key && Math.hypot(o.c[0] - b.c[0], o.c[1] - b.c[1]) < T.stairLink) o.key = b.key;
        });
      });
    });
    var connectors = {};
    floors.forEach(function (f) {
      f.blocks.forEach(function (b) {
        if (!b.key) return;
        var c = connectors[b.key] = connectors[b.key] || { key: b.key, kind: b.kind, blocks: {}, floors: [] };
        c.blocks[f.id] = b; c.floors.push(f.id);
      });
    });
    var links = [];
    Object.keys(connectors).forEach(function (k) {
      var c = connectors[k], ids = c.floors.sort(function (a, b) { return order[a] - order[b]; });
      if (ids.length < 2) W.push("connector " + k + " exists on one floor only, so it leads nowhere");
      for (var i = 0; i + 1 < ids.length; i++) {
        var a = c.blocks[ids[i]], b = c.blocks[ids[i + 1]];
        links.push({ lo: ids[i], hi: ids[i + 1], a: a.bbox.slice(), b: b.bbox.slice(), kind: c.kind, key: k });
      }
    });
    var monos = solveMonos(ents); ents.forEach(function (e, i) { e.mono = monos[i]; });         // the token's characters, unique in this venue
    var allPts = []; floors.forEach(function (f) { f.outline.forEach(function (p) { allPts.push(p); }); });
    return {
      venue: venue, unit: venue.unit || "m", name: nm(venue.name, "Venue"), event: venue.event ? nm(venue.event) : null, terms: terms, tuning: T,
      bounds: allPts.length ? bboxOf(allPts) : [0, 0, 1, 1], floors: floors, floorById: floorById, roomById: roomById, order: order,
      entities: ents, entityById: entById, connectors: connectors, links: links, warnings: W, errors: E   // roomById holds rooms AND areas (area: true)
    };
  }

  /* ---- a binary heap of [cost, cell] ----------------------------------------- */
  function Heap() { this.a = []; }
  Heap.prototype.push = function (k, v) {
    var a = this.a, i = a.length;
    a.push([k, v]);
    while (i > 0) {
      var p = (i - 1) >> 1;
      if (a[p][0] <= a[i][0]) break;
      var t = a[p]; a[p] = a[i]; a[i] = t; i = p;
    }
  };
  Heap.prototype.pop = function () {
    var a = this.a, top = a[0], last = a.pop();
    if (a.length) {
      a[0] = last;
      var i = 0, n = a.length;
      for (;;) {
        var l = 2 * i + 1, r = l + 1, m = i;
        if (l < n && a[l][0] < a[m][0]) m = l;
        if (r < n && a[r][0] < a[m][0]) m = r;
        if (m === i) break;
        var t = a[m]; a[m] = a[i]; a[i] = t; i = m;
      }
    }
    return top;
  };

  /* ---- one floor's grid -------------------------------------------------------- */
  function Grid(floor, bounds, T) {
    var CELL = T.cell, x0 = bounds[0] - 1, y0 = bounds[1] - 1;
    var nx = Math.ceil((bounds[2] - x0 + 1) / CELL), ny = Math.ceil((bounds[3] - y0 + 1) / CELL);
    this.f = floor; this.T = T; this.CELL = CELL;
    this.x0 = x0; this.y0 = y0; this.nx = nx; this.ny = ny;
    var n = nx * ny, base = new Uint8Array(n), room = new Int16Array(n).fill(-1);
    var blocks = floor.blocks.map(function (b) { return { poly: b.poly, box: b.bbox }; });
    var rooms = floor.rooms.map(function (r) { return { poly: r.poly, box: r.bbox, through: r.through }; });
    for (var j = 0; j < ny; j++) {
      for (var i = 0; i < nx; i++) {
        var x = x0 + (i + 0.5) * CELL, y = y0 + (j + 0.5) * CELL, k = j * nx + i;
        if (!inside(floor.outline, x, y)) continue;
        var solid = false;
        for (var b = 0; b < blocks.length && !solid; b++) {
          var bb = blocks[b].box;
          if (x >= bb[0] && x <= bb[2] && y >= bb[1] && y <= bb[3] && inside(blocks[b].poly, x, y)) solid = true;
        }
        if (solid) continue;
        base[k] = 1;
        for (var r = 0; r < rooms.length; r++) {
          var rb = rooms[r].box;
          if (x >= rb[0] && x <= rb[2] && y >= rb[1] && y <= rb[3] && inside(rooms[r].poly, x, y)) { if (!rooms[r].through) room[k] = r; break; }
        }
      }
    }
    var self = this;
    floor.walls.concat(floor.rails || []).forEach(function (w) {       // a void's rail is kept at a wall's distance
      var m = T.wallClear + CELL;
      var i0 = self.ci(Math.min(w[0], w[2]) - m), i1 = self.ci(Math.max(w[0], w[2]) + m);
      var j0 = self.cj(Math.min(w[1], w[3]) - m), j1 = self.cj(Math.max(w[1], w[3]) + m);
      for (var jj = Math.max(0, j0); jj <= Math.min(ny - 1, j1); jj++) {
        for (var ii = Math.max(0, i0); ii <= Math.min(nx - 1, i1); ii++) {
          if (segDist(x0 + (ii + 0.5) * CELL, y0 + (jj + 0.5) * CELL, w[0], w[1], w[2], w[3]) < T.wallClear) base[jj * nx + ii] = 0;
        }
      }
    });
    this.base = base;
    this.room = room;
    this.clear = this.distance();
    /* landings: for every stairs / lift block, the walkable cells at its door (or all round it) */
    this.landings = {};
    floor.blocks.forEach(function (bl) {
      if (!bl.key) return;
      var cells = [], bx = bl.bbox, near;
      var i0 = Math.max(0, self.ci(bx[0] - 2)), i1 = Math.min(nx - 1, self.ci(bx[2] + 2)), j0 = Math.max(0, self.cj(bx[1] - 2)), j1 = Math.min(ny - 1, self.cj(bx[3] + 2));
      for (var jj = j0; jj <= j1; jj++) {
        for (var ii = i0; ii <= i1; ii++) {
          var kk = jj * nx + ii;
          if (!base[kk] || room[kk] >= 0) continue;
          var x = x0 + (ii + 0.5) * CELL, y = y0 + (jj + 0.5) * CELL;
          if (bl.doors.length) near = bl.doors.some(function (d) { return Math.hypot(d[0] - x, d[1] - y) <= T.landing + 0.5; });
          else near = Math.hypot(Math.max(bx[0] - x, 0, x - bx[2]), Math.max(bx[1] - y, 0, y - bx[3])) <= T.landing;
          if (near) cells.push(kk);
        }
      }
      self.landings[bl.key] = { block: bl, cells: cells };
    });
  }
  Grid.prototype.ci = function (x) { return Math.floor((x - this.x0) / this.CELL); };
  Grid.prototype.cj = function (y) { return Math.floor((y - this.y0) / this.CELL); };
  Grid.prototype.xy = function (k) {
    return [this.x0 + (k % this.nx + 0.5) * this.CELL, this.y0 + (Math.floor(k / this.nx) + 0.5) * this.CELL];
  };
  Grid.prototype.ok = function (k, open) {
    return this.base[k] === 1 && (this.room[k] < 0 || open.indexOf(this.room[k]) >= 0);
  };
  /* metres from each walkable cell to the nearest blocked one (a two-pass chamfer transform) */
  Grid.prototype.distance = function () {
    var nx = this.nx, ny = this.ny, d = new Float32Array(nx * ny), base = this.base, D = Math.SQRT2;
    for (var k = 0; k < d.length; k++) d[k] = base[k] ? 1e9 : 0;
    for (var j = 0; j < ny; j++) for (var i = 0; i < nx; i++) {
      k = j * nx + i;
      if (!d[k]) continue;
      if (i > 0) d[k] = Math.min(d[k], d[k - 1] + 1);
      if (j > 0) {
        d[k] = Math.min(d[k], d[k - nx] + 1);
        if (i > 0) d[k] = Math.min(d[k], d[k - nx - 1] + D);
        if (i < nx - 1) d[k] = Math.min(d[k], d[k - nx + 1] + D);
      }
    }
    for (j = ny - 1; j >= 0; j--) for (i = nx - 1; i >= 0; i--) {
      k = j * nx + i;
      if (!d[k]) continue;
      if (i < nx - 1) d[k] = Math.min(d[k], d[k + 1] + 1);
      if (j < ny - 1) {
        d[k] = Math.min(d[k], d[k + nx] + 1);
        if (i < nx - 1) d[k] = Math.min(d[k], d[k + nx + 1] + D);
        if (i > 0) d[k] = Math.min(d[k], d[k + nx - 1] + D);
      }
    }
    for (k = 0; k < d.length; k++) d[k] *= this.CELL;
    return d;
  };
  Grid.prototype.snap = function (pt, open) {   // the walkable cell nearest to a point
    var i = this.ci(pt[0]), j = this.cj(pt[1]);
    for (var r = 0; r < 40; r++) {
      var best = -1, bd = Infinity;
      for (var jj = j - r; jj <= j + r; jj++) for (var ii = i - r; ii <= i + r; ii++) {
        if (ii < 0 || jj < 0 || ii >= this.nx || jj >= this.ny) continue;
        if (Math.max(Math.abs(ii - i), Math.abs(jj - j)) !== r) continue;
        var k = jj * this.nx + ii;
        if (!this.ok(k, open)) continue;
        var p = this.xy(k), d = Math.hypot(p[0] - pt[0], p[1] - pt[1]);
        if (d < bd) { bd = d; best = k; }
      }
      if (best >= 0) return best;
    }
    return -1;
  };
  /* Dijkstra from source cells [[cell, startCost]]; stops early once every goal cell is settled.
     The cost of a step is its length x (1 + gain x how short of `centre` metres of room the cell has). */
  Grid.prototype.search = function (sources, open, goals) {
    var T = this.T, nx = this.nx, n = nx * this.ny, dist = new Float64Array(n).fill(Infinity), prev = new Int32Array(n).fill(-1);
    var heap = new Heap(), left = goals ? goals.length : -1, goal = goals ? new Uint8Array(n) : null;
    if (goals) goals.forEach(function (k) { goal[k] = 1; });
    sources.forEach(function (s) { if (s[0] >= 0 && s[1] < dist[s[0]]) { dist[s[0]] = s[1]; heap.push(s[1], s[0]); } });
    var steps = [[1, 0, 1], [-1, 0, 1], [0, 1, 1], [0, -1, 1], [1, 1, Math.SQRT2], [1, -1, Math.SQRT2], [-1, 1, Math.SQRT2], [-1, -1, Math.SQRT2]];
    while (heap.a.length) {
      var top = heap.pop(), k = top[1];
      if (top[0] > dist[k]) continue;
      if (goal && goal[k]) { goal[k] = 0; if (--left === 0) break; }
      var i = k % nx, j = (k - i) / nx;
      for (var s = 0; s < 8; s++) {
        var ii = i + steps[s][0], jj = j + steps[s][1];
        if (ii < 0 || jj < 0 || ii >= nx || jj >= this.ny) continue;
        var kk = jj * nx + ii;
        if (!this.ok(kk, open)) continue;
        if (s >= 4 && (!this.ok(j * nx + ii, open) || !this.ok(jj * nx + i, open))) continue;   // no corner cutting
        var c = this.clear[kk], w = 1 + T.centreGain * Math.max(0, (T.centre - c) / T.centre);
        var nd = dist[k] + steps[s][2] * this.CELL * w;
        if (nd < dist[kk]) { dist[kk] = nd; prev[kk] = k; heap.push(nd, kk); }
      }
    }
    return { dist: dist, prev: prev };
  };
  Grid.prototype.trace = function (res, end) {
    var cells = [];
    for (var k = end; k >= 0; k = res.prev[k]) cells.push(k);
    return cells.reverse();
  };
  Grid.prototype.clearAt = function (p) {
    var i = this.ci(p[0]), j = this.cj(p[1]);
    if (i < 0 || j < 0 || i >= this.nx || j >= this.ny) return 0;
    return this.clear[j * this.nx + i];
  };
  /* can you walk straight from a to b keeping `sight` clear of walls and blocks? Within a metre of
     either end (a door, a booth by the wall) only as much room as that end has. */
  Grid.prototype.sees = function (a, b, open) {
    var SIGHT = this.T.sight, d = Math.hypot(b[0] - a[0], b[1] - a[1]), n = Math.max(1, Math.ceil(d / 0.08));
    var ea = Math.min(SIGHT, this.clearAt(a)), eb = Math.min(SIGHT, this.clearAt(b));
    for (var s = 0; s <= n; s++) {
      var x = a[0] + (b[0] - a[0]) * s / n, y = a[1] + (b[1] - a[1]) * s / n;
      var i = this.ci(x), j = this.cj(y);
      if (i < 0 || j < 0 || i >= this.nx || j >= this.ny) return false;
      var k = j * this.nx + i, t = d * s / n;
      // clearance is measured to blocked cells' centres: half a cell more keeps lines off block corners
      var need = t < 1 ? Math.min(SIGHT, ea + t * SIGHT) : d - t < 1 ? Math.min(SIGHT, eb + (d - t) * SIGHT) : SIGHT + this.CELL / 2;
      if (!this.ok(k, open) || this.clear[k] < need - 1e-6) return false;
    }
    return true;
  };
  /* cells -> a short polyline: keep the farthest point still in sight */
  Grid.prototype.straighten = function (cells, open, first, last) {
    var self = this, pts = cells.map(function (k) { return self.xy(k); });
    if (first) pts[0] = first;
    if (last) pts[pts.length - 1] = last;
    if (pts.length < 3) return pts;
    var out = [pts[0]], i = 0;
    while (i < pts.length - 1) {
      var j = pts.length - 1;
      while (j > i + 1 && !self.sees(pts[i], pts[j], open)) j--;
      out.push(pts[j]);
      i = j;
    }
    return out;
  };

  /* ---- left / right ------------------------------------------------------------ */
  /* the turn from heading a to heading b (plan y points south): 0 straight, 1 right, -1 left.
     "Straight" is generous (under about 35 degrees): a turn is a promise about what the person sees. */
  function turn(a, b) {
    var la = Math.hypot(a[0], a[1]), lb = Math.hypot(b[0], b[1]);
    if (la < 1e-6 || lb < 1e-6) return 0;
    var cross = (a[0] * b[1] - a[1] * b[0]) / (la * lb), dot = (a[0] * b[0] + a[1] * b[1]) / (la * lb);
    if (dot > 0.82) return 0;
    return cross > 0 ? 1 : -1;
  }
  function along(pts, d) {          // the point d metres along a polyline
    for (var i = 1; i < pts.length; i++) {
      var l = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
      if (d <= l) { var t = d / (l || 1); return [pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * t, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * t]; }
      d -= l;
    }
    return pts[pts.length - 1];
  }
  function exitAt(pts, poly) {      // how far along the polyline it first leaves a room (-1: never)
    var total = lenOf(pts);
    for (var d = 0; d <= total; d += 0.1) { var p = along(pts, d); if (!inside(poly, p[0], p[1])) return d; }
    return -1;
  }
  function enterAt(pts, poly) {     // how far along it first enters a room (its length if it never does)
    var total = lenOf(pts), was = inside(poly, pts[0][0], pts[0][1]);
    for (var d = 0; d <= total; d += 0.1) {
      var p = along(pts, d), now = inside(poly, p[0], p[1]);
      if (now && !was) return d;
      was = now;
    }
    return total;
  }
  function metres(m) { return Math.max(1, Math.round(m)); }

  /* ---- the router -------------------------------------------------------------- */
  function Router(venue, opts) {
    opts = opts || {};
    this.m = EVK.venueModel(venue, null, opts.tuning || null);
    this.T = this.m.tuning;
    this.grids = {};
  }
  Router.prototype.grid = function (fid) {
    if (!this.grids[fid]) this.grids[fid] = new Grid(this.m.floorById[fid], this.m.bounds, this.T);
    return this.grids[fid];
  };
  Router.prototype.roomIndex = function (fid, rid) {
    var rs = this.m.floorById[fid].rooms;
    for (var i = 0; i < rs.length; i++) if (rs[i].id === rid) return i;
    return -1;
  };
  Router.prototype.level = function (fid) { return this.m.floorById[fid].level; };

  /* where a route can start: lobbies, entrances, rooms, booths. ids: "lobby:1F", "entrance:1F", "room:201", "entity:kelp" */
  Router.prototype.starts = function () {
    var out = [], m = this.m;
    m.floors.forEach(function (f) {
      if (f.entrance) out.push({ id: "entrance:" + f.id, kind: "entrance", floor: f.id, name: f.entrance.name, label: f.entrance.name.en });
    });
    m.floors.forEach(function (f) {
      if (f.lobby) out.push({ id: "lobby:" + f.id, kind: "lobby", floor: f.id, name: f.lobby.name, label: f.lobby.name.en });
    });
    m.floors.forEach(function (f) {
      f.rooms.forEach(function (r) { out.push({ id: "room:" + r.id, kind: "room", floor: f.id, name: r.name, label: r.label, room: r.id }); });
    });
    m.floors.forEach(function (f) {
      f.areas.forEach(function (a) { out.push({ id: "area:" + a.id, kind: "area", floor: f.id, name: a.name, label: a.label || a.name.en, room: a.id }); });
    });
    m.entities.forEach(function (e) {
      out.push({ id: "entity:" + e.id, kind: "entity", floor: e.floor, name: e.name, label: enName(e) || e.short, room: e.room, entity: e.id });
    });
    return out;
  };
  Router.prototype.place = function (id) {
    if (id == null) return null;
    var m = this.m, s = String(id), kind = null, rest = s, ix = s.indexOf(":");
    if (ix > 0 && /^(lobby|entrance|room|area|entity)$/.test(s.slice(0, ix))) { kind = s.slice(0, ix); rest = s.slice(ix + 1); }
    var kinds = kind ? [kind] : ["entity", "room", "area", "lobby", "entrance"];
    for (var i = 0; i < kinds.length; i++) {
      var k = kinds[i];
      if (k === "entity" && m.entityById[rest]) {
        var e = m.entityById[rest];
        return { id: "entity:" + e.id, kind: "entity", floor: e.floor, at: e.at, room: e.room, name: e.name, entity: e, roomRef: e.room ? m.roomById[e.room] : null };
      }
      if ((k === "room" || k === "area") && m.roomById[rest]) {        // "room:<area id>" finds the area too
        var r = m.roomById[rest];
        if (k === "area" && !r.area) continue;
        return { id: (r.area ? "area:" : "room:") + r.id, kind: r.area ? "area" : "room", floor: r.floor, at: r.c, room: r.id, name: r.name, roomRef: r };
      }
      if (k === "lobby" && m.floorById[rest] && m.floorById[rest].lobby) {
        var lf = m.floorById[rest];
        return { id: "lobby:" + lf.id, kind: "lobby", floor: lf.id, at: lf.lobby.at, room: null, name: lf.lobby.name, roomRef: null };
      }
      if (k === "entrance") {
        var ef = m.floorById[rest] && m.floorById[rest].entrance ? m.floorById[rest]
          : rest === "" || rest === "entrance" ? m.floors.filter(function (f) { return f.entrance; })[0] : null;
        if (ef) {
          var en = ef.entrance, T = this.T;
          return { id: "entrance:" + ef.id, kind: "entrance", floor: ef.id, at: [en.at[0] + en.dir[0] * T.entranceIn, en.at[1] + en.dir[1] * T.entranceIn], room: null, name: en.name, roomRef: null };
        }
      }
    }
    return null;
  };

  /* the room whose polygon holds the point (so that a lobby that sits inside a hall opens the hall) */
  Router.prototype.roomAt = function (fid, p) {
    var rs = this.m.floorById[fid].rooms;
    for (var i = 0; i < rs.length; i++) if (inside(rs[i].poly, p[0], p[1])) return i;
    return -1;
  };

  /* the connectors that join floor a and the next floor b, by preference */
  Router.prototype.hopsBetween = function (a, b, via) {
    var cs = this.m.connectors, out = [];
    Object.keys(cs).forEach(function (k) {
      var c = cs[k];
      if (c.blocks[a] && c.blocks[b]) out.push(c);
    });
    var stairs = out.filter(function (c) { return c.kind === "stairs"; }), lifts = out.filter(function (c) { return c.kind === "lift"; });
    if (via === "lift") return lifts;
    if (via === "any") return out;
    return stairs.length ? stairs : lifts;            // "stairs" (default): lifts only when no stairs join these two floors
  };

  /* a stairwell is named by what stands next to it */
  Router.prototype.connectorName = function (fid, conn) {
    var f = this.m.floorById[fid], b = conn.blocks[fid];
    if (b.label) return { cn: b.label.cn, en: stripThe(b.label.en) };      // the author named it: use that (the words add the "the")
    if (conn.kind === "lift") return { cn: "电梯", en: "lift" };
    var best = null, bd = Infinity;
    f.blocks.forEach(function (bl) {
      if (bl.kind !== "lift" && bl.kind !== "wc") return;
      var d = Math.hypot(bl.c[0] - b.c[0], bl.c[1] - b.c[1]);
      if (d < bd) { bd = d; best = bl; }
    });
    if (best && bd < 9) {
      if (best.kind === "lift") return { cn: "电梯旁的楼梯", en: "stairs by the lift" };
      return { cn: "洗手间旁的楼梯", en: "stairs by the toilets" };
    }
    var near = null, nd = 4;                          // else the room whose door it is nearest to
    var dp = b.doors.length ? b.doors[0] : b.c;
    f.rooms.forEach(function (r) {
      r.doors.forEach(function (d) { var dd = Math.hypot(d.x - dp[0], d.y - dp[1]); if (dd < nd) { nd = dd; near = r; } });
    });
    if (near) {
      var rn = roomNames(near, this.m.terms);
      return { cn: rn.cn + "旁的楼梯", en: "stairs by " + rn.en };
    }
    return { cn: "楼梯", en: "stairs" };
  };

  /* ---- planning ---------------------------------------------------------------- */
  /* plan(startId, entityId [, {via: "stairs" | "lift" | "any"}]) -> plan | null
     plan = { from, to, segs: [{floor, pts}], hops: [{from, to, a, b, kind, name, key}], stairs (= hops[0]),
              steps: [{kind: walk | stairs | arrive, floor, seg, …}], metres, floors, via } */
  Router.prototype.plan = function (startId, entityId, opts) {
    opts = opts || {};
    var from = this.place(startId), to = this.place(entityId && entityId.indexOf && entityId.indexOf(":") < 0 ? "entity:" + entityId : entityId);
    if (!from || !to || to.kind !== "entity") return null;
    var m = this.m, T = this.T, via = opts.via || "stairs";
    var A = from.floor, C = to.floor, toRoomIdx = this.roomIndex(C, to.room);
    var fromRoomIdx = from.room ? this.roomIndex(A, from.room) : this.roomAt(A, from.at);
    var legs = [], hops = [];
    if (A === C) {
      var g = this.grid(A);
      var open = [fromRoomIdx, toRoomIdx].filter(function (i, ix, ar) { return i >= 0 && ar.indexOf(i) === ix; });
      var s = g.snap(from.at, open), t = g.snap(to.at, open);
      if (s < 0 || t < 0) return null;
      var res = g.search([[s, 0]], open, [t]);
      if (!isFinite(res.dist[t])) return null;
      legs.push({ floor: A, pts: g.straighten(g.trace(res, t), open, from.at, to.at), inConn: null, outConn: null, open: open });
    } else {
      var chain = m.floors.slice().sort(function (p, q) { return p.level - q.level; }).filter(function (f) {
        return f.level >= Math.min(m.floorById[A].level, m.floorById[C].level) && f.level <= Math.max(m.floorById[A].level, m.floorById[C].level);
      }).map(function (f) { return f.id; });
      if (m.floorById[A].level > m.floorById[C].level) chain.reverse();
      var self = this, n = chain.length - 1, runs = [], sources = null, entryOf = [];
      for (var i = 0; i <= n; i++) {
        var gi = this.grid(chain[i]);
        var openI = i === 0 ? [fromRoomIdx] : i === n ? [toRoomIdx] : [];
        openI = openI.filter(function (v) { return v >= 0; });
        if (i === 0) {
          var s0 = gi.snap(from.at, openI);
          if (s0 < 0) return null;
          sources = [[s0, 0]];
        }
        var goals = i === n ? [gi.snap(to.at, openI)] : null;
        if (i === n && goals[0] < 0) return null;
        var rs = gi.search(sources, openI, goals);
        runs.push({ g: gi, res: rs, open: openI, sources: sources });
        if (i === n) break;
        /* arrivals on the next floor: every landing shared by a connector that joins both floors */
        var nextId = chain[i + 1], arr = {}, cands = this.hopsBetween(chain[i], nextId, via);
        cands.forEach(function (c) {
          var la = gi.landings[c.key], lb = self.grid(nextId).landings[c.key];
          if (!la || !lb) return;
          var inB = {}; lb.cells.forEach(function (k) { inB[k] = 1; });
          var pen = c.kind === "lift" ? T.liftPenalty : T.stairPenalty;
          la.cells.forEach(function (k) {
            if (!inB[k]) return;                                  // the grids share their origin: the same cell on both floors
            var d = rs.dist[k] + pen;
            if (isFinite(d) && (!arr[k] || d < arr[k].d)) arr[k] = { d: d, conn: c };
          });
        });
        var ks = Object.keys(arr);
        if (!ks.length) return null;
        entryOf.push(arr);
        sources = ks.map(function (k) { return [+k, arr[k].d]; });
      }
      /* walk back from the target through the layers */
      var endCell = runs[n].g.snap(to.at, runs[n].open);
      if (!isFinite(runs[n].res.dist[endCell])) return null;
      var exit = endCell, built = new Array(n + 1);
      for (var li = n; li >= 0; li--) {
        var run = runs[li], cells = run.g.trace(run.res, exit), start = cells[0];
        built[li] = { floor: chain[li], cells: cells, run: run, entry: start, exit: exit };
        if (li > 0) built[li].inConn = entryOf[li - 1][start].conn;
        exit = start;                                             // the same cell on the floor below
      }
      for (li = 0; li < n; li++) built[li].outConn = built[li + 1].inConn;
      /* merge a floor you only pass through (arrive and leave by the same stairwell at the same cell) */
      for (li = 1; li < n; li++) {
        var bq = built[li];
        if (bq.inConn && bq.outConn && bq.inConn.key === bq.outConn.key && bq.entry === bq.exit) bq.skip = true;
      }
      built.forEach(function (b, idx) {
        if (b.skip) return;
        var first = idx === 0 ? from.at : null, last = idx === n ? to.at : null;
        var pts = b.run.g.straighten(b.cells, b.run.open, first, last);
        var leg = { floor: b.floor, pts: pts, inConn: b.inConn || null, outConn: b.outConn || null, open: b.run.open };
        legs.push(leg);
      });
      for (i = 0; i + 1 < legs.length; i++) {
        var lg = legs[i], nl = legs[i + 1];
        hops.push({
          from: lg.floor, to: nl.floor, a: lg.pts[lg.pts.length - 1], b: nl.pts[0], kind: lg.outConn.kind, key: lg.outConn.key,
          name: this.connectorName(lg.floor, lg.outConn), nameTo: this.connectorName(nl.floor, lg.outConn)
        });
      }
    }
    return this.assemble(from, to, legs, hops, via);
  };

  /* the open area a leg mostly runs through (null: none). `prefer` is the area the booth stands in: that one is named whatever the path did. */
  Router.prototype.areaVia = function (leg, prefer) {
    if (prefer) return prefer;
    var f = this.m.floorById[leg.floor], areas = f.areas, T = this.T;
    if (!areas.length || leg.pts.length < 2) return null;
    var total = lenOf(leg.pts), inLen = {}, best = null, bl = 0;
    for (var d = 0; d <= total; d += 0.1) {
      var p = along(leg.pts, d);
      for (var i = 0; i < areas.length; i++) if (inside(areas[i].poly, p[0], p[1])) { inLen[areas[i].id] = (inLen[areas[i].id] || 0) + 0.1; break; }
    }
    areas.forEach(function (a) { if ((inLen[a.id] || 0) > bl) { bl = inLen[a.id]; best = a; } });
    return best && bl >= T.viaMin && bl >= T.viaShare * total ? best : null;
  };

  /* steps for people, as data; describe() puts them into words.
     A booth in a walled room ends in a walk "to the room's door" and an arrive step "into the room".
     A booth in an open area (or on its own on a floor) has no door: the walk goes straight to the booth, naming the area,
     and the arrive step only says where the booth is. */
  Router.prototype.assemble = function (from, to, legs, hops, via) {
    var self = this, m = this.m, steps = [];
    var toRoom = to.room ? m.roomById[to.room] : null, fromRoom = from.room ? m.roomById[from.room] : null;
    var toArea = toRoom && toRoom.area ? toRoom : null, toWalled = toRoom && !toRoom.area ? toRoom : null;
    var fromWalled = fromRoom && !fromRoom.area ? fromRoom : null;
    var segs = legs.map(function (l) { return { floor: l.floor, pts: l.pts }; });
    var lastLeg = legs[legs.length - 1], lastLen = lenOf(lastLeg.pts);
    var toDoor = toWalled ? enterAt(lastLeg.pts, toWalled.poly) : lastLen, inRoom = lastLen - toDoor;
    var level = this.level.bind(this);
    if (fromWalled && fromWalled === toWalled) {
      steps.push({ kind: "arrive", floor: to.floor, seg: 0, same: true, room: toWalled, entity: to.entity });
    } else if (from.entity && from.entity === to.entity) {           // starting at the booth you asked for (in an open area, or on an open floor)
      steps.push({ kind: "arrive", floor: to.floor, seg: 0, here: true, room: toRoom, area: toArea, entity: to.entity });
    } else {
      legs.forEach(function (leg, i) {
        var lastOne = i === legs.length - 1, w = { kind: "walk", floor: leg.floor, seg: i, first: i === 0, via: self.areaVia(leg, lastOne ? toArea : null) };
        if (i === 0) {
          w.start = from;
          w.out = fromWalled ? turnOutOfRoom(leg.pts, fromWalled.poly) : null;
        } else {
          var st = leg.inConn.blocks[leg.floor];
          w.afterKind = leg.inConn.kind;
          w.ex = null;
          if (leg.pts.length > 1) {
            var p0 = leg.pts[0], p1 = along(leg.pts, 1.2), p2 = along(leg.pts, 4);
            if (Math.hypot(p0[0] - st.c[0], p0[1] - st.c[1]) > 0.1) w.ex = turn([p1[0] - st.c[0], p1[1] - st.c[1]], [p2[0] - p1[0], p2[1] - p1[1]]);
          }
        }
        if (lastOne) { w.target = toWalled ? { room: toWalled } : { booth: true, entity: to.entity }; w.metres = metres(toDoor); }
        else { w.target = { conn: hops[i].name, kind: hops[i].kind }; w.metres = metres(lenOf(leg.pts)); }
        steps.push(w);
        if (!lastOne) {
          var h = hops[i], up = level(h.to) > level(h.from);
          steps.push({ kind: "stairs", floor: h.to, seg: -1, up: up, via: h.kind, toFloor: m.floorById[h.to], level: level(h.to) });
        }
      });
      steps.push({ kind: "arrive", floor: to.floor, seg: legs.length - 1, room: toRoom, area: toArea, entity: to.entity, inRoom: toWalled && inRoom >= 3 ? metres(inRoom) : null });
    }
    var total = 0; segs.forEach(function (s) { total += lenOf(s.pts); });
    var floors = segs.map(function (s) { return s.floor; }).filter(function (f, i, a) { return a.indexOf(f) === i; });
    return {
      from: { id: from.id, kind: from.kind, floor: from.floor, at: from.at, room: from.room, name: from.name, entity: from.entity ? from.entity.id : null },
      to: { id: to.entity.id, kind: "entity", floor: to.floor, at: to.at, room: to.room, area: !!toArea, name: to.entity.name, entity: to.entity.id, booth: to.entity.booth },
      segs: segs, hops: hops, stairs: hops[0] || null, steps: steps, metres: metres(total), floors: floors, via: via
    };
  };
  function turnOutOfRoom(pts, poly) {    // the turn as you come out of the room you start in
    var d = exitAt(pts, poly);
    if (d < 0) return null;
    var a = along(pts, Math.max(0, d - 0.6)), b = along(pts, d + 0.4), c = along(pts, d + 3.2);
    return turn([b[0] - a[0], b[1] - a[1]], [c[0] - b[0], c[1] - b[1]]);
  }

  /* ---- words ------------------------------------------------------------------- */
  /* a room is spoken by its number when its label is one (203), else by its name (the Grand Hall);
     an open area by its name ("the west corridor": write area names as common nouns, the words add "the") */
  function roomNames(r, terms) {
    if (r.area) return { cn: r.name.cn, en: "the " + stripThe(r.name.en), num: false, area: true };
    var num = /^\d+$/.test(r.label);
    return { cn: num ? r.label : r.name.cn, en: num ? (terms.room.en ? terms.room.en + " " : "") + r.label : "the " + stripThe(r.name.en), num: num };
  }
  /* how a leg that runs through an open area is put: a corridor is followed, an open area is crossed */
  function areaVerb(a) {
    var en = stripThe(a.name.en);
    return a.kind === "corridor" ? { cn: "沿" + a.name.cn, en: "follow the " + en } : { cn: "穿过" + a.name.cn, en: "cross the " + en };
  }
  var TURN_CN = { "-1": "左转", "0": "直走", "1": "右转" };
  var TURN_OUT_EN = { "-1": "turn left out of the door", "0": "go straight out of the door", "1": "turn right out of the door" };
  /* the same, for a route that ends in an open area or on an open floor: no door anywhere in the text */
  var TURN_OUT_EN_ROOM = { "-1": "turn left as you leave the room", "0": "go straight as you leave the room", "1": "turn right as you leave the room" };
  var TURN_AFTER_EN = { "-1": "turn left", "0": "keep straight", "1": "turn right" };

  function boothWords(e, terms) {
    if (!e.booth) return null;
    return { cn: e.booth + " 号" + terms.booth.cn, en: terms.booth.en + " " + e.booth, head: cap(terms.booth.en) + " " + e.booth };
  }
  function startName(from, terms, m) {
    if (from.kind === "entity") {
      var e = from.entity, r = e.room ? m.roomById[e.room] : null, bw = boothWords(e, terms), en = enName(e);
      var cnIn = r ? (r.area ? r.name.cn : r.label) + " · " + e.booth : e.booth;
      var enIn = r ? (r.area ? stripThe(r.name.en) : r.label) + " · " + e.booth : e.booth;
      return { cn: e.name.cn + "（" + cnIn + "）", en: (en || (bw ? bw.en : e.name.en)) + " (" + enIn + ")" };
    }
    if (from.kind === "room") { var rn = roomNames(from.roomRef, terms); return { cn: rn.cn, en: rn.en }; }
    if (from.kind === "area") return { cn: from.name.cn, en: "the " + stripThe(from.name.en) };
    return { cn: from.name.cn, en: "the " + stripThe(from.name.en) };
  }

  function wordsOf(st, plan, m) {
    var terms = m.terms, en, cn, mt = st.metres, noDoor = !!plan.to.area || !plan.to.room;
    if (st.kind === "walk") {
      var tg, tgEn, hCn, hEn;
      if (st.target.room) {
        var rn = roomNames(st.target.room, terms);
        tg = rn.cn + "门口"; tgEn = rn.en; hCn = "走到" + rn.cn; hEn = "Walk to " + rn.en;
      } else if (st.target.booth) {                               // a booth in an open area / on an open floor: the booth itself, no door
        var tb = boothWords(st.target.entity, terms);
        tg = tb.cn; tgEn = tb.en; hCn = "走到" + tb.cn; hEn = "Walk to " + tb.en;
      } else {
        tg = st.target.conn.cn; tgEn = "the " + st.target.conn.en; hCn = "走到" + st.target.conn.cn; hEn = "Walk to the " + st.target.conn.en;
      }
      var vCn = "走到", vEn = "walk to ";
      if (st.via) { var av = areaVerb(st.via); vCn = av.cn + "走到"; vEn = av.en + " to "; }
      var cp = [], ep = [];
      if (st.first) {
        var sn = startName(st.start, terms, m);
        cp.push("从" + sn.cn + "出发");
        ep.push("From " + sn.en);
        if (st.out != null) { cp.push((noDoor ? "出房间后" : "出门后") + TURN_CN[st.out]); ep.push((noDoor ? TURN_OUT_EN_ROOM : TURN_OUT_EN)[st.out]); }
      } else if (st.ex != null) {
        var what = st.afterKind === "lift" ? "电梯" : "楼梯";
        cp.push("出" + what + "后" + TURN_CN[st.ex]);
        ep.push("out of the " + (st.afterKind === "lift" ? "lift" : "stairs") + ", " + TURN_AFTER_EN[st.ex]);
      }
      cp.push(vCn + tg + "，约 " + mt + " 米");
      ep.push(vEn + tgEn + ", about " + mt + " m");
      cn = { head: EVK.spaced(hCn), text: EVK.spaced(cp.join("，") + "。") };
      en = { head: hEn, text: cap(ep.join(", ")) + "." };
    } else if (st.kind === "stairs") {
      var lv = st.toFloor.short.cn, lvEn = st.toFloor.short.en;          // floors[].short: the same words in the sentence, the chip and the tag
      var lift = st.via === "lift";
      cn = {
        head: (lift ? "乘电梯" : "") + (st.up ? "上" : "下") + "到" + lv,
        text: (lift ? "乘电梯" : "走楼梯") + (st.up ? "上" : "下") + "到" + lv + "。"
      };
      en = {
        head: lift ? "Lift " + (st.up ? "up" : "down") + " to " + lvEn : (st.up ? "Up to " : "Down to ") + lvEn,
        text: "Take the " + (lift ? "lift" : "stairs") + " " + (st.up ? "up" : "down") + " to " + lvEn + "."
      };
      cn.head = EVK.spaced(cn.head); cn.text = EVK.spaced(cn.text);
    } else {                                                          // arrive
      var e = st.entity, bw = boothWords(e, terms), enShort = enName(e) || (bw ? "" : e.name.en);   // never a Chinese short name in the English head
      var enHead = bw ? bw.head + (enShort ? " · " + enShort : "") : enShort;
      if (st.here) {
        cn = { head: "就在这里" + (bw ? " · " + bw.cn : ""), text: "你已经在" + e.name.cn + (bw ? "（" + bw.cn + "）" : "") + "。" };
        en = { head: "You are here" + (bw ? " · " + bw.head : ""), text: "You are already at " + e.name.en + (bw ? " (" + bw.en + ")" : "") + "." };
      } else if (st.same) {
        var r2 = roomNames(st.room, terms);
        cn = { head: "就在这个房间" + (bw ? " · " + bw.cn : ""), text: "就在" + r2.cn + "里：" + e.name.cn + (bw ? "在 " + bw.cn : "就在这里") + "。" };
        en = { head: "Same room" + (bw ? " · " + bw.en : ""), text: "It is in " + r2.en + " itself. " + e.name.en + (bw ? " is at " + bw.en : " is here") + "." };
      } else if (st.area) {                                           // standing in an open area: nothing to enter, just where
        var ar = roomNames(st.area, terms);
        cn = { head: bw ? bw.cn + " · " + e.name.cn : e.name.cn, text: e.name.cn + "在" + ar.cn + (bw ? "的 " + bw.cn : "") + "。" };
        en = { head: enHead, text: e.name.en + (bw ? " is at " + bw.en : " is here") + " in " + ar.en + "." };
      } else if (!st.room) {                                          // on an open floor with no area around it
        cn = { head: bw ? bw.cn + " · " + e.name.cn : e.name.cn, text: e.name.cn + (bw ? "在 " + bw.cn : "就在这里") + "。" };
        en = { head: enHead, text: e.name.en + (bw ? " is at " + bw.en : " is here") + "." };
      } else {
        var r3 = roomNames(st.room, terms);
        cn = { head: bw ? bw.cn + " · " + e.name.cn : e.name.cn, text: "进入" + r3.cn + (st.inRoom ? "再走约 " + st.inRoom + " 米" : "") + "，" + e.name.cn + (bw ? "在 " + bw.cn : "就在这里") + "。" };
        en = { head: enHead, text: "Go into " + r3.en + (st.inRoom ? " and walk about " + st.inRoom + " m further" : "") + ". " + e.name.en + (bw ? " is at " + bw.en : " is here") + "." };
      }
      cn.head = EVK.spaced(cn.head); cn.text = EVK.spaced(cn.text);
    }
    return { en: en, cn: cn };
  }

  /* describe(plan, "zh" | "en" | "both") -> [{ kind, floor, seg, metres, head, text, en: {head, text}, cn: {head, text} }]
     "both" pairs the English sign (head) with the Chinese sentence (text): EN is the sign, CN is the sentence. */
  function describe(plan, lang, m) {
    lang = lang || "zh";
    if (!plan || !plan.steps) return [];                                 // no route: nothing to say (callers test the plan first)
    return plan.steps.map(function (st) {
      var w = wordsOf(st, plan, m), o = { kind: st.kind, floor: st.floor, seg: st.seg, metres: st.metres || null, en: w.en, cn: w.cn };
      if (lang === "en") { o.head = w.en.head; o.text = w.en.text; }
      else if (lang === "both") { o.head = w.en.head; o.text = w.cn.text; }
      else { o.head = w.cn.head; o.text = w.cn.text; }
      return o;
    });
  }

  EVK.wayfind = {
    version: "0.1.0",
    tuning: TUNE,
    create: function (venue, opts) {
      var r = new Router(venue, opts);
      return {
        model: r.m,
        starts: function () { return r.starts(); },
        plan: function (startId, entityId, o) { return r.plan(startId, entityId, o); },
        describe: function (plan, lang) { return describe(plan, lang, r.m); },
        warnings: r.m.warnings,
        errors: r.m.errors
      };
    },
    metres: metres
  };

  var USAGE = "usage: node wayfind.js --selftest [venue.json]\n       node wayfind.js --describe-all <venue.json> --from <startId> [--lead en|zh]";
  if (typeof module !== "undefined" && module.exports) {
    module.exports = EVK;
    if (typeof require !== "undefined" && require.main === module) {
      var argv = process.argv;
      if (argv.indexOf("--selftest") >= 0) selftest(argv[argv.indexOf("--selftest") + 1]);
      else if (argv.indexOf("--describe-all") >= 0) describeAll(argv);
      else if (argv.indexOf("--help") >= 0 || argv.indexOf("-h") >= 0) console.log(USAGE);
    }
  }

  /* ---- node wayfind.js --describe-all <venue.json> --from <startId> [--lead en|zh] ----------------------
     The written route from one start to EVERY entity, as JSON on stdout, for pages that print "How to get here" at build time:
       {"from": "entrance:1F", "lead": "en", "routes": {"<entityId>": [{"kind": "walk|stairs|arrive", "<lead>": {"head","text"}, "<other>": {"head","text"}, "climb": false}, …]}}
     `kind` and the sentences are describe()'s; both languages are always there as "en" and "cn" (the lead language's object comes first); `climb` is true for
     the stairs / lift step (give it the climb colour). An entity with no route has [] (and a note on stderr). Start ids are the ones
     starts() lists: "entrance:<floor>", "lobby:<floor>", "room:<id>", "area:<id>", "entity:<id>". An unknown start, a missing or unreadable
     file or a bad --lead exits 2 with a message on stderr; exit 0 otherwise. */
  function describeAll(argv) {
    var fs = require("fs");
    function opt(name) { var i = argv.indexOf(name); return i >= 0 && i + 1 < argv.length && argv[i + 1].slice(0, 2) !== "--" ? argv[i + 1] : null; }
    function die(msg) { process.stderr.write("wayfind.js --describe-all: " + msg + "\n"); process.exitCode = 2; }
    var file = opt("--describe-all"), from = opt("--from"), lead = opt("--lead") || "en";
    if (!file) return die("needs a venue file.\n" + USAGE);
    if (!from) return die("needs --from <startId>, e.g. --from entrance:1F.\n" + USAGE);
    if (lead !== "en" && lead !== "zh") return die("--lead must be en or zh, not " + lead);
    var venue, wf;
    try { venue = JSON.parse(fs.readFileSync(file, "utf8")); } catch (err) { return die("cannot read " + file + ": " + err.message); }
    try { wf = EVK.wayfind.create(venue); } catch (err2) { return die("cannot build the venue model: " + err2.message); }
    var starts = wf.starts();
    if (!starts.some(function (s) { return s.id === from; })) {
      var ids = starts.map(function (s) { return s.id; });
      return die("unknown start " + from + ". Valid starts: " + ids.slice(0, 12).join(", ") + (ids.length > 12 ? ", … (" + ids.length + " in all)" : ""));
    }
    if (wf.errors.length) process.stderr.write("wayfind.js --describe-all: venue errors: " + wf.errors.join(" | ") + "\n");
    var key = lead === "zh" ? "cn" : "en", other = lead === "zh" ? "en" : "cn", routes = {}, missing = [];
    wf.model.entities.forEach(function (e) {
      var plan = wf.plan(from, e.id);
      if (!plan) { routes[e.id] = []; missing.push(e.id); return; }
      routes[e.id] = wf.describe(plan, "both").map(function (st) {
        var o = { kind: st.kind };
        o[key] = { head: st[key].head, text: st[key].text };
        o[other] = { head: st[other].head, text: st[other].text };
        o.climb = st.kind === "stairs";
        return o;
      });
    });
    if (missing.length) process.stderr.write("wayfind.js --describe-all: no route from " + from + " to " + missing.join(", ") + "\n");
    process.stdout.write(JSON.stringify({ from: from, lead: lead, routes: routes }) + "\n");
  }

  /* ---- node wayfind.js --selftest [venue.json] ---------------------------------------------------
     Every start x every entity, in zh / en / both, on the demo venue (or the file named): a route exists,
     every number is finite, no text carries "undefined" / "NaN", nothing is routed over a void, an English head is
     never Chinese, and a booth in an open area or on an open floor is never "at the door". A pair with no route does not
     stop the run: the missing pairs are counted per start and per entity and the first ten are listed (exit 1). Then the
     area wording the spec fixes, ring areas (holes), floor `short` words, English names, and the data mistakes that must
     come back as warnings (or errors), not exceptions. */
  function selftest(file) {
    var fs = require("fs"), path = require("path"), fails = 0, n = 0;
    function ok(c, msg) {
      n++;
      if (c) return;
      fails++;
      if (fails <= 40) console.log("FAIL  " + msg); else if (fails === 41) console.log("FAIL  … further failures are counted but not listed");
    }
    var vfile = file && file[0] !== "-" ? file : path.join(__dirname, "..", "demo", "venue.json"), venue = JSON.parse(fs.readFileSync(vfile, "utf8"));
    function fix(mut) { var v = JSON.parse(JSON.stringify(venue)); mut(v); return EVK.wayfind.create(v); }
    var wf = EVK.wayfind.create(venue), m = wf.model, starts = wf.starts(), routes = 0, longest = 0;
    ok(wf.errors.length === 0, "model errors: " + wf.errors.join(" | "));
    ok(wf.warnings.length === 0, "model warnings: " + wf.warnings.join(" | "));
    ok(wf.describe(null, "en").length === 0, "describe(null) is empty, not an exception");
    var rx = /undefined|NaN|null|\[object/, noRoute = [], byStart = {}, byEnt = {};
    starts.forEach(function (s) {
      m.entities.forEach(function (e) {
        var tag = s.id + " -> " + e.id, p = null;
        try { p = wf.plan(s.id, e.id); } catch (err) { ok(false, "plan threw " + tag + ": " + err.message); }
        if (!p) { noRoute.push([s.id, e.id]); byStart[s.id] = (byStart[s.id] || 0) + 1; byEnt[e.id] = (byEnt[e.id] || 0) + 1; return; }
        routes++; longest = Math.max(longest, p.metres);
        try {
          ok(isFinite(p.metres) && p.metres >= 1 && p.segs.length >= 1 && p.segs.every(function (sg) { return sg.pts.length >= 1 && sg.pts.every(function (q) { return isFinite(q[0]) && isFinite(q[1]); }); }), "numbers " + tag);
          var gap = Math.abs(m.floorById[p.from.floor].level - m.floorById[p.to.floor].level);
          ok(gap === 0 ? p.hops.length === 0 : p.hops.length >= 1 && p.hops.length <= gap, "hops " + p.hops.length + " for " + gap + " floors apart, " + tag);   // a floor passed through by one stairwell is not a hop of its own
          ok(p.segs.every(function (sg) { return !m.floorById[sg.floor].voids.some(function (v) { return sg.pts.some(function (q) { return inside(v.poly, q[0], q[1]); }); }); }), "route over a void " + tag);
          var noDoor = !!p.to.area || !p.to.room;
          ["zh", "en", "both"].forEach(function (lang) {
            var d = wf.describe(p, lang);
            ok(d.length >= 1 && d.every(function (x) { return x.head && x.text && !rx.test(x.head + " " + x.text); }), lang + " text " + tag);
            if (noDoor) ok(d.every(function (x) { return !/门口|door/i.test(x.head + x.text); }), "no door in " + lang + " " + tag);
          });
          wf.describe(p, "en").forEach(function (x) { ok(!/\bthe\s+the\b/i.test(x.text) && !/;\s+[A-Z]/.test(x.text) && !/ {2}/.test(x.text), "English sentence reads: " + x.text + " (" + tag + ")"); });
          wf.describe(p, "zh").forEach(function (x) { ok(!/[㐀-鿿] [㐀-鿿]/.test(x.text + x.head), "no space between two Chinese characters: " + x.text + " (" + tag + ")"); });
          wf.describe(p, "both").forEach(function (x) { if (x.kind === "arrive") ok(!hasCJK(x.head), "English head is English " + tag + ": " + x.head); });
        } catch (err2) { ok(false, "exception on " + tag + ": " + err2.message); }
      });
    });
    if (noRoute.length) {                                           // a summary, never a crash
      n++; fails++;
      var total = starts.length * m.entities.length;
      function top(map) { return Object.keys(map).sort(function (a, b) { return map[b] - map[a] || (a < b ? -1 : 1); }).slice(0, 10).map(function (k) { return k + " x" + map[k]; }).join(", "); }
      console.log("FAIL  no route for " + noRoute.length + " of " + total + " start -> entity pairs");
      console.log("      by start:   " + top(byStart) + (Object.keys(byStart).length > 10 ? ", … (" + Object.keys(byStart).length + " starts)" : ""));
      console.log("      by entity:  " + top(byEnt) + (Object.keys(byEnt).length > 10 ? ", … (" + Object.keys(byEnt).length + " entities)" : ""));
      console.log("      first " + Math.min(10, noRoute.length) + ":   " + noRoute.slice(0, 10).map(function (q) { return q[0] + " -> " + q[1]; }).join("; "));
      var shut = m.entities.filter(function (e) { return (byEnt[e.id] || 0) >= 0.6 * starts.length; }).map(function (e) { return e.id + " (room " + e.room + ")"; });
      var blind = starts.filter(function (s) { return (byStart[s.id] || 0) >= 0.6 * m.entities.length; }).map(function (s) { return s.id; });
      if (shut.length) console.log("      hardly any start reaches: " + shut.slice(0, 10).join(", ") + (shut.length > 10 ? ", …" : "") + "  (a shut-in room? check its doors: a door drawn on a wall two rooms share opens into the other room)");
      if (blind.length) console.log("      these starts reach hardly anything: " + blind.slice(0, 10).join(", ") + (blind.length > 10 ? ", …" : "") + "  (a pocket walled off by blocks or rooms?)");
      if (wf.warnings.length) console.log("      model warnings: " + wf.warnings.slice(0, 5).join(" | "));
    }
    ok(routes === starts.length * m.entities.length, "all " + routes + " of " + starts.length * m.entities.length + " routes planned");
    var lifts = Object.keys(m.connectors).some(function (k) { return m.connectors[k].kind === "lift" && m.connectors[k].floors.length > 1; });
    if (m.entities.length && starts.length) ["lift", "any"].forEach(function (via) {
      if (via === "lift" && !lifts) return;                         // no lift in this venue: nothing to ask for
      var p = wf.plan(starts[0].id, m.entities[m.entities.length - 1].id, { via: via }); ok(!!p, "via " + via);
    });
    if (!m.entities.length) {                                       // the page that uses this venue supplies its entities: only the model could be checked
      /* monograms: unique in the venue, authored ones win and the rest move, the order of the list does not matter */
    var monoList = m.entities.map(function (e) { return e.mono; });
    ok(monoList.every(function (x) { return x && x.length <= 4; }) && new Set(monoList).size === monoList.length, "every entity has its own monogram of 1 to 4 characters: " + monoList.join(" "));
    var mk = [{ id: "a", short: "Lux Lab", booth: "01" }, { id: "b", short: "Lantern Lab", booth: "01" }, { id: "c", short: "Kelp", mono: "KP" }, { id: "d", short: "Kelp" }, { id: "e", short: "Kiln", booth: "03" }, { id: "f", short: "Kite" , booth: "04" }, { id: "g", short: "清华大学" }, { id: "h", short: "清华附中" }];
    var mg = EVK.monograms(mk), mgR = EVK.monograms(mk.slice().reverse());
    ok(mg.a === "LUL" && mg.b === "LAL", "two 'LL' names get 3-letter forms when their booths are the same: " + mg.a + " " + mg.b);
    ok(mg.c === "KP" && mg.d === "Ke", "an authored `mono` is used as written: " + mg.c + " " + mg.d);
    ok(mg.e === "03" && mg.f === "04", "colliding names with different booths use the booth numbers: " + mg.e + " " + mg.f);
    ok(mg.g !== mg.h && Array.from(mg.g).length === 3, "colliding Chinese names get 3 characters: " + mg.g + " " + mg.h);
    ok(Object.keys(mg).every(function (k) { return mg[k] === mgR[k]; }), "monograms do not depend on the order of the list");

    /* node wayfind.js --describe-all: the shared contract with the starter pages */
    var cp = require("child_process"), da = function (args) { return cp.spawnSync(process.execPath, [__filename, "--describe-all", vfile].concat(args), { encoding: "utf8" }); };
    var first = starts[0], r1 = da(["--from", first.id]);
    ok(r1.status === 0, "--describe-all exits 0 for " + first.id + ": " + r1.stderr);
    var dj = null; try { dj = JSON.parse(r1.stdout); } catch (e1) { /* reported below */ }
    ok(dj && dj.from === first.id && m.entities.every(function (e) { var st = dj.routes[e.id]; return st && st.length && st.every(function (x) { return x.kind && x.en && x.en.head && x.en.text && x.cn && x.cn.head && x.cn.text && typeof x.climb === "boolean"; }); }), "--describe-all lists every entity with en and cn sentences");
    ok(dj && m.entities.every(function (e) { var p = wf.plan(first.id, e.id); return !p || dj.routes[e.id].length === p.steps.length && dj.routes[e.id].every(function (x, i) { return x.climb === (p.steps[i].kind === "stairs"); }); }), "--describe-all marks the stairs / lift step as climb");
    var rz = da(["--from", first.id, "--lead", "zh"]), dz = null; try { dz = JSON.parse(rz.stdout); } catch (e2) { /* reported below */ }
    ok(dz && dz.lead === "zh" && Object.keys(dz.routes[m.entities[0].id][0])[1] === "cn", "--lead zh puts the Chinese sentence first");
    var rb = da(["--from", "no-such-start"]);
    ok(rb.status === 2 && /unknown start/.test(rb.stderr) && !rb.stdout, "--describe-all with an unknown start exits 2 with a message");

    console.log(fails ? fails + " of " + n + " checks FAILED" : "wayfind.js selftest: " + n + " checks passed (the venue file lists no entities, so no routes were tried)");
      if (fails) process.exit(1);
      return;
    }

    /* the wording the spec fixes (demo venue only: these ids exist there) */
    if (m.entityById.driftwood && m.entityById.lanterns && m.entityById.tideradio) {
      var t = function (a, b, l) { var q = wf.plan(a, b); if (!q) return ""; var d = wf.describe(q, l); return d[d.length - 2].text; };
      ok(/沿西走廊走到 07 号展位，约 \d+ 米。$/.test(t("entrance:1F", "driftwood", "zh")), "zh corridor wording: " + t("entrance:1F", "driftwood", "zh"));
      ok(/follow the west corridor to booth 07, about \d+ m\.$/i.test(t("entrance:1F", "driftwood", "en")), "en corridor wording: " + t("entrance:1F", "driftwood", "en"));
      ok(/穿过中庭走到 01 号展位/.test(t("entrance:1F", "lanterns", "zh")) && /cross the atrium to booth 01/i.test(t("entrance:1F", "lanterns", "en")), "open area wording");
      ok(/走到 K1 号展位/.test(t("entrance:1F", "tideradio", "zh")) && /walk to booth K1/i.test(t("entrance:1F", "tideradio", "en")), "booth on an open floor");
      ok(m.entityById.tideradio.room === null && m.entityById.tideradio.floor === "1F", "an entity by at + floor has no room");
      ok(m.entityById.lanterns.area === true && m.roomById.ATRIUM.area === true, "areas share the room id space");
      ok(wf.plan("area:WEST", "sunbeam") && wf.plan("room:WEST", "sunbeam"), "an area is a start, as area: and as room:");
      var selfp = wf.plan("entity:inkwell", "inkwell"), self = wf.describe(selfp, "en"); ok(self.length === 1 && /already at/.test(self[0].text), "a route to where you stand: " + self[0].text);
    }

    /* a ring gallery: an area with a hole round a void. The demo has one (GALLERY, 2F); every venue with a holed area is checked
       the same way, and a small ring venue of our own always runs. */
    function ringChecks(model, w, label) {
      var any = false;
      model.floors.forEach(function (f) {
        f.areas.forEach(function (a) {
          if (!a.holes.length) return;
          any = true;
          ok(within(a, a.c[0], a.c[1]), label + ": the middle of " + a.id + " is on the ring, not in the hole " + JSON.stringify(a.c));
          ok(a.labelAt && within(a, a.labelAt[0], a.labelAt[1]), label + ": the name of " + a.id + " is on the ring");
          model.entities.filter(function (e) { return e.room === a.id; }).forEach(function (e) {
            ok(within(a, e.at[0], e.at[1]), label + ": " + e.id + " stands on the ring of " + a.id + " " + JSON.stringify(e.at));
          });
        });
      });
      return any;
    }
    ringChecks(m, wf, "venue");
    if (m.roomById.GALLERY && m.roomById.GALLERY.holes.length && m.entityById.driftmap) {
      var tz = function (l) { var q = wf.plan("entrance:1F", "driftmap"); return q ? wf.describe(q, l)[wf.describe(q, l).length - 2].text : ""; };
      ok(/沿中庭回廊走到 \d+ 号展位，约 \d+ 米。$/.test(tz("zh")), "zh ring gallery wording: " + tz("zh"));
      ok(/follow the atrium gallery to booth \d+, about \d+ m\.$/i.test(tz("en")), "en ring gallery wording: " + tz("en"));
      ok(wf.plan("entity:driftmap", "lanterns") && wf.plan("area:GALLERY", "kelp"), "routes start in the ring gallery");
    }
    var ringV = {
      unit: "m", name: "Ring Hall",
      floors: [{
        id: "G", level: 1, outline: [[0, 0], [20, 0], [20, 14], [0, 14]], entrance: { at: [10, 14] },
        areas: [{ id: "RING", kind: "corridor", name: "ring gallery", poly: [[1, 1], [19, 1], [19, 13], [1, 13]], holes: [[[5, 4], [15, 4], [15, 10], [5, 10]]] }],
        blocks: [{ kind: "solid", id: "CORE", poly: [[5, 4], [15, 4], [15, 10], [5, 10]] }]
      }],
      entities: [1, 2, 3, 4, 5, 6].map(function (i) { return { id: "r" + i, name: "Stand " + i, room: "RING" }; })
    };
    var rw = EVK.wayfind.create(ringV);
    ok(rw.warnings.length === 0, "ring venue is clean: " + rw.warnings.join(" | "));
    ok(ringChecks(rw.model, rw, "ring"), "ring venue has an area with holes");
    ok(rw.model.entities.every(function (e) { return !inside([[5, 4], [15, 4], [15, 10], [5, 10]], e.at[0], e.at[1]); }), "ring booths are not in the hole");
    var rbooths = rw.model.entities.map(function (e) { return e.at; }), spread = Infinity;
    rbooths.forEach(function (p, i) { rbooths.forEach(function (q, j) { if (j > i) spread = Math.min(spread, Math.hypot(p[0] - q[0], p[1] - q[1])); }); });
    ok(spread >= 3, "ring booths are spread out (closest pair " + round2(spread) + " m)");
    var rr = 0; rw.model.entities.forEach(function (e) { rw.starts().forEach(function (s) { if (rw.plan(s.id, e.id)) rr++; }); });
    ok(rr === rw.starts().length * rw.model.entities.length, "ring venue: every route exists (" + rr + ")");
    var hole2 = JSON.parse(JSON.stringify(ringV)); hole2.floors[0].areas[0].holes = [[[0, 0], [30, 0], [30, 5]]];
    ok(/hole 1 of area RING reaches outside/.test(EVK.wayfind.create(hole2).warnings.join(" | ")), "a hole outside its ring is a warning");
    var hole3 = JSON.parse(JSON.stringify(ringV)); hole3.entities[0].at = [10, 7];
    ok(/r1.*outside area RING \(it is in a hole/.test(EVK.wayfind.create(hole3).warnings.join(" | ")), "a booth in the hole is a warning");

    /* a Chinese `short` never reaches the English head */
    var v2 = JSON.parse(JSON.stringify(venue)); v2.entities.forEach(function (e) { e.short = e.name.cn; });
    var w2 = EVK.wayfind.create(v2), p2 = w2.plan(w2.starts()[0].id, v2.entities[0].id);
    if (p2) ok(!hasCJK(w2.describe(p2, "both").pop().head), "English head with a Chinese short name: " + w2.describe(p2, "both").pop().head);

    /* floors[].short: the same words in the route sentence; without it the id and "<level> 层" */
    var f0 = m.floors[0], atF0 = m.entities.filter(function (e) { return e.floor === f0.id; })[0], upTo = null;
    m.entities.forEach(function (e) { if (!upTo && e.floor !== f0.id && m.floorById[e.floor].level > f0.level) upTo = e; });
    if (atF0 && upTo) {
      var q0 = wf.plan("entity:" + atF0.id, upTo.id);
      if (q0 && q0.hops.length) {
        var hopTo = m.floorById[q0.hops[0].to];
        var sEn = wf.describe(q0, "en").filter(function (x) { return x.kind === "stairs"; })[0], sCn = wf.describe(q0, "zh").filter(function (x) { return x.kind === "stairs"; })[0];
        ok(sEn && sEn.text.indexOf(hopTo.short.en) > 0, "route sentence uses floors[].short.en: " + (sEn && sEn.text));
        ok(sCn && sCn.text.indexOf(EVK.spaced(hopTo.short.cn)) > 0, "route sentence uses floors[].short.cn: " + (sCn && sCn.text));
        var wS = fix(function (v) { v.floors.forEach(function (f) { f.short = { en: "Level " + f.level, cn: "零一二三四五六七八九".charAt(f.level) + "层" }; }); });
        var qS = wS.plan("entity:" + atF0.id, upTo.id);
        if (qS) {
          var tEn = wS.describe(qS, "en").filter(function (x) { return x.kind === "stairs"; })[0].text, tCn = wS.describe(qS, "zh").filter(function (x) { return x.kind === "stairs"; })[0].text;
          ok(/ to Level \d\.$/.test(tEn), "short.en in the sentence: " + tEn);
          ok(/到[零一二三四五六七八九]层。$/.test(tCn), "short.cn in the sentence, no stray space: " + tCn);
        }
      }
    }

    /* English names: written as on the sign, "the" added once, a leading "The" stripped, a name never starts a clause after ";" */
    var wT = fix(function (v) {
      v.floors.forEach(function (f) {
        if (f.entrance) f.entrance.name = { en: "The South Entrance", cn: "南入口" };
        (f.rooms || []).forEach(function (r) { if (!/^\d+$/.test(r.label)) r.name = { en: "The " + (r.name && r.name.en || r.id), cn: r.name && r.name.cn || r.id }; });
        (f.areas || []).forEach(function (a) { a.name = { en: "The " + (a.name && a.name.en || a.id), cn: a.name && a.name.cn || a.id }; });
      });
      v.entities.forEach(function (e, i) { if (i % 2 === 0) e.name = { en: "The " + e.name.en, cn: e.name.cn }; });
    });
    var badEn = [];
    wT.starts().forEach(function (s) { wT.model.entities.forEach(function (e) {
      var q = wT.plan(s.id, e.id);
      if (q) wT.describe(q, "en").forEach(function (x) { if (/\bthe\s+the\b/i.test(x.text) || /;\s+[A-Z]/.test(x.text)) badEn.push(x.text); });
    }); });
    ok(badEn.length === 0, "English names with a leading The: " + badEn.slice(0, 2).join(" | "));
    var enSouth = wT.starts().filter(function (s) { return s.kind === "entrance"; })[0], eT = wT.model.entities[0];
    if (enSouth && eT) {
      var qe = wT.plan(enSouth.id, eT.id);
      if (qe) ok(/^From the South Entrance/.test(wT.describe(qe, "en")[0].text), "an entrance name is used as written, with one 'the': " + wT.describe(qe, "en")[0].text);
    }

    /* data mistakes are warnings, not exceptions. The bad fixture is built from the venue under test, so a valid venue never fails
       here: the void goes on the lowest floor, the duplicate entity into whichever room or area exists, the overlapping area onto
       the first room (a venue with no rooms skips that one check) */
    var v3 = JSON.parse(JSON.stringify(venue)), want = [[/ghost.*does not exist/, "a missing room"], [/lost.*needs a room/, "an entity nowhere"], [/appears twice/, "a duplicate id"], [/lowest floor/, "a void on the lowest floor"]];
    var low = v3.floors.slice().sort(function (a, b) { return a.level - b.level; })[0], lb = bboxOf(low.outline.map(function (p) { return [+p[0], +p[1]]; })), lx = (lb[0] + lb[2]) / 2, ly = (lb[1] + lb[3]) / 2;
    var home = null, homeFloor = null;                                  // a room or an area to put the duplicate in, and the first room (for the overlap)
    v3.floors.forEach(function (f) {
      (f.rooms || []).concat(f.areas || []).forEach(function (r) { if (!home) home = r.id; });
      (f.rooms || []).forEach(function (r) { if (!homeFloor) homeFloor = { f: f, r: r }; });
    });
    var dup = home ? { id: "dup", name: "Dup", room: home } : { id: "dup", name: "Dup", floor: low.id, at: [lx, ly] };
    v3.entities.push({ id: "ghost", name: "Ghost", room: "x-no-such-room" }, { id: "lost", name: "Lost" }, dup, JSON.parse(JSON.stringify(dup)));
    low.blocks = (low.blocks || []).concat([{ kind: "void", id: "x-V0", poly: [[lx - 0.5, ly - 0.5], [lx + 0.5, ly - 0.5], [lx + 0.5, ly + 0.5], [lx - 0.5, ly + 0.5]] }]);
    if (homeFloor) {
      var rb = bboxOf(polyOf(homeFloor.r)), rw2 = rb[2] - rb[0], rh = rb[3] - rb[1];
      homeFloor.f.areas = (homeFloor.f.areas || []).concat([{ id: "x-BAD", kind: "open", rect: [rb[0] + rw2 / 3, rb[1] + rh / 3, rw2 / 3, rh / 3] }]);
      want.push([/overlaps room/, "an area on top of a room"]);
    }
    var w3 = EVK.wayfind.create(v3), W = w3.warnings.join(" | ");
    want.forEach(function (w) { ok(w[0].test(W), "warning for " + w[1] + " in: " + W); });
    ok(w3.errors.some(function (x) { return /ghost.*does not exist/.test(x); }) && w3.errors.some(function (x) { return /lost.*needs a room/.test(x); }), "an entity whose room or area is unknown is an error: " + w3.errors.join(" | "));
    ok(w3.errors.every(function (x) { return w3.warnings.indexOf(x) >= 0; }), "every error is also in warnings");
    ok(!w3.errors.some(function (x) { return /appears twice|lowest floor|overlaps/.test(x); }), "a duplicate id, a void and an overlap are warnings, not errors");

    /* doors: one drawn on a wall two rooms share opens into the other room; one too far from its wall is ignored and said so;
       one a little off its wall is moved onto it */
    var shared = null;
    m.floors.forEach(function (f) {
      f.rooms.forEach(function (r) {
        if (shared) return;
        edgesOf(r.poly).forEach(function (e) {
          if (shared) return;
          var mx = (e[0][0] + e[1][0]) / 2, my = (e[0][1] + e[1][1]) / 2, nn = outwardOf(r.poly, e[0], e[1]), px = mx + nn[0] * 0.4, py = my + nn[1] * 0.4;
          f.rooms.forEach(function (o) { if (!shared && o !== r && !o.through && inside(o.poly, px, py) && !r.doors.some(function (d) { return Math.hypot(d.x - mx, d.y - my) < 2; })) shared = { floor: f.id, room: r.id, other: o.id, at: [round2(mx), round2(my)] }; });
        });
      });
    });
    if (shared) {
      var wD = fix(function (v) { v.floors.forEach(function (f) { if (f.id === shared.floor) f.rooms.forEach(function (r) { if (String(r.id) === shared.room) r.doors = (r.doors || []).concat([[shared.at[0], shared.at[1], 1.2]]); }); }); });
      ok(new RegExp("door " + shared.room.replace(/[^\w]/g, "\\$&") + "@\\[[\\d.,-]+\\] opens into " + shared.other.replace(/[^\w]/g, "\\$&")).test(wD.warnings.join(" | ")), "a door on a wall two rooms share: " + wD.warnings.join(" | "));
    }
    var r0 = null, f0r = null;
    m.floors.forEach(function (f) { f.rooms.forEach(function (r) { if (!r0 && r.doors.length && r.doors[0].edge) { r0 = r; f0r = f; } }); });
    if (r0) {
      var d0 = r0.doors[0], off = function (dist) { return fix(function (v) { v.floors.forEach(function (f) { if (f.id === f0r.id) f.rooms.forEach(function (r) { if (String(r.id) === r0.id) r.doors = [[round2(d0.x - d0.n[0] * dist), round2(d0.y - d0.n[1] * dist), d0.w]]; }); }); }); };
      var far = off(-0.9).warnings.join(" | ");                         // 0.9 m outside the wall
      ok(/door \S+@\[[\d.,-]+\] is [\d.]+ m from the room's boundary/.test(far) || /opens /.test(far), "a door 0.9 m off its wall is a warning: " + far);
      var near = off(-0.2).warnings.join(" | ");                        // 0.2 m outside: snapped, no 'from the room's boundary'
      ok(!/m from the room's boundary/.test(near), "a door 0.2 m off its wall is moved onto it: " + near);
      var mid = fix(function (v) { v.floors.forEach(function (f) { if (f.id === f0r.id) f.rooms.forEach(function (r) { if (String(r.id) === r0.id) r.doors = [[round2(r0.c[0]), round2(r0.c[1]), 1.2]]; }); }); }).warnings.join(" | ");
      ok(/door \S+@\[[\d.,-]+\] is [\d.]+ m from the room's boundary/.test(mid), "a door in the middle of its room is a warning: " + mid);
    }
    console.log(fails ? fails + " of " + n + " checks FAILED" : "wayfind.js selftest: " + n + " checks passed (" + routes + " routes, " + starts.length + " starts x " + m.entities.length + " entities, longest " + longest + " m)");
    if (fails) process.exit(1);
  }
})();
