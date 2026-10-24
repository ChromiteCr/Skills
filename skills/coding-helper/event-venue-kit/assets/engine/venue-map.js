/* event-venue-kit · assets/engine/venue-map.js
   ---------------------------------------------------------------------------
   EVK.VenueMap: a venue drawn on a canvas as a turntable model, from the
   authored venue (venue.schema.json). Hand-written 2D canvas, painter's
   algorithm, no library, no build. Load wayfind.js first (EVK.venueModel).

     var map = new EVK.VenueMap(canvas, venue, {
       entities,                  // optional: replaces venue.entities
       image: function (entity) { return HTMLImageElement | null },   // token artwork
       lead: "en" | "zh",         // which language leads in labels, tooltips, aria: the primary line is first and larger,
                                  // the other follows smaller. Default: <html data-evk-lead> (and it follows that attribute
                                  // when it changes); else "en". `lang` is the old name and still works when nothing else says.
       onSelect: function (entityId | null) {},   // a person tapped a token (null: tapped away)
       onRoom: function (roomId) {},              // a person tapped a room
       onFloor: function (floorId) {},            // … or bare floor
       floor: "2F", select: "kelp",   // start on one floor / with an exhibitor chosen
       intro: true, tuning: {…}   // see TUNE below
     });
     read-only state: map.mode ("all" | floorId | "route"), map.room, map.sel, map.route
     map.setFloor("2F" | null)   map.select(id | null)
     map.focusRoom(roomId | areaId | null)   // frame a room or an open area; null lets it go and returns to the view that was
                                              // showing before the focus (all floors, or that floor): ux-contracts RF-5
     map.setRoute(plan | null)   map.routeStep(i | null) map.setStops([ids] | null)
     map.setPad({top, right, bottom, left})   // px of the canvas something covers (a sheet, a card): the model glides
                                                // into the free part, a side card refits it, a tall sheet shrinks it only if needed
     map.lock(true)   map.reset()
     map.setLead("en" | "zh" | null)   // pin the lead (null: follow <html data-evk-lead> again)   map.setLang = the same
     read-only: map.lead
     map.refresh()   // re-read tokens now (also happens by itself, see below)   map.resize()   map.destroy()

   The look is read from CSS custom properties on the canvas (getComputedStyle),
   once at construction, whenever prefers-color-scheme flips, and whenever the
   class / style / data-theme of the canvas, its parent or <html> changes:
     colours   --m-ground  the canvas ground (blueprint and riso paint it; paper leaves the canvas clear, so make the
                           slab the same colour as the page and the building floats with no card edge)
               --m-slab    floor plate top        --m-room   a hollow room's floor     --m-block  solid masses
               --m-wall    wall faces             --m-cap    wall caps = the ink line (spend the contrast here)
               --m-text    plates, names          --m-route  route line, start, entrance arrow
               --m-route-halo  text halos and the under-stroke of the route (also the paper of icon plates)
               --m-dash    the marching dashes    --m-climb  stairs and lifts in a route
               --m-select       the chosen room's EDGE (a stroke: keep it >= 3:1 against --m-slab)
               --m-select-fill  the chosen room's tint (default: --m-room mixed 12 % toward --m-select)
     keywords  --m-projection  orbit | oblique | exploded | plan
               --m-material    paper | line | clay | blueprint | riso
               --m-token       badge | pin | plate | dot | flag | stamp
                               (the map's token style IS the card's `entity_token` parameter: install.py writes it into tokens.css,
                               and the page's cards and the map must agree. To change it, adjust key `entity_token=…` with
                               draw.py, never edit --m-token by hand. The characters on a badge, pin, flag or stamp are the
                               entity's monogram, unique in the venue: see `mono` in venue.schema.json and EVK.monograms)
               --m-light       left | right | top        --m-label-case  upper | none
     numbers   --m-pitch (deg)  --m-yaw (deg)  --m-wall-h (m)  --m-dim (0–1)
     optional  --m-wall-t (m)  --m-pin-h (m)  --m-persp (camera distance ÷ scene radius, 3–40)
               --radius --chamfer (px; shape of the map's plates and icons)
               --spring-dur (s) --spring-bounce (0–0.35)   --f-label --f-cjk --f-num (font stacks)
   Missing tokens fall back to a neutral paper look, so the engine runs bare.

   Venue data it draws beyond rooms and blocks (see venue.schema.json): floors[].areas[] (open zones without walls: a
   dashed floor patch and a name, tappable like a room, booths stand in them; `holes` cut rings out of the patch, both rings are
   outlined, a tap in a hole misses the area: a ring gallery round a void) and blocks of kind "void" (an opening to the
   floor below: the slab is cut away and a rail runs round the edge. Stacked, it is a well you look down into: walls, the floor
   at the bottom and a dot for each booth right under it; with one floor, a plan or side-by-side floors, an X over a tinted box).

   What one finger (or the mouse) dragging does is a constant of the projection, not a guess (VenueMap.DRAG_MODE):
     orbit, exploded   "rotate"  the model turns about the vertical axis, 1:1 (a mouse also tilts it)
     plan              "rotate"  the plan turns in the plane of the paper (the camera is nearly overhead; there is no pan)
     oblique           "pan"     the model is pulled across the table (the yaw is a locked shear; a mouse pulls in y too)
   Pinch always zooms. map.dragMode() answers for the current tokens, VenueMap.dragModeFor("plan") for any projection, and the
   map root carries data-evk-drag="rotate|pan" (kept in step with --m-projection), so a hint can follow it in CSS or in JS:
   "Drag to rotate · 拖动旋转" or "Drag to pan · 拖动平移". The canvas's aria-label follows it too.

   Long buildings (footprint longer than 1.6 : 1) on a portrait canvas: the resting yaw is clamped so the long side stays across
   the screen (see footprintCap); drag, pinch and the keyboard are not clamped, and a landscape canvas is never touched.

   What is craft here, and not look (keep these): springs that start from the
   camera's current position and speed; a finger catches everything in flight;
   1:1 drag with release velocity and exponential decay; rubber-banded limits;
   gesture negotiation with page scroll (touch-action: pan-y); halo text;
   static when idle (no frame loop unless something moves); DPR-correct;
   prefers-reduced-motion in every path; hit areas larger than the visuals.

   Numbers marked "原站取值" are what the CollegeFair site used; they are
   one instance. Override through opts.tuning or the optional tokens above.
   --------------------------------------------------------------------------- */
(function () {
  "use strict";
  var EVK = (window.EVK = window.EVK || {});
  if (!EVK.venueModel) throw new Error("venue-map.js needs wayfind.js loaded first (it provides EVK.venueModel)");

  var DEG = Math.PI / 180, TAU = Math.PI * 2;

  /* ---- tuning: 原站取值 (range that still works) ------------------------------ */
  var TUNE = {
    wallT: 0.22,          // wall cap thickness, m  (0.08 – 0.4)                  token --m-wall-t
    slab: 0.45,           // floor plate thickness, m  (0.1 – 0.9)
    blockRatio: 1.15,     // solid block height ÷ wall height  (1 – 2.2)
    pinH: 2.1,            // height of a token above the floor, m  (1 – 3)         token --m-pin-h
    persp: 7,             // camera distance ÷ scene radius: gentle, like a table model  (3 – 14; 40 ≈ parallel)
    zoomMin: 0.75, zoomMax: 4.5,
    pitchMin: 16, pitchMax: 84,           // deg; plan projection narrows this to 80 – 89
    turn: 0.0078,         // rad per px dragged (0.447°/px)  (0.004 – 0.012)
    tilt: 0.0055,         // rad per px, mouse tilt and two-finger slide
    decel: 0.9955,        // spin kept per millisecond after a flick (iOS-like)  (0.99 – 0.998)
    spinMax: 9,           // rad/s cap on a flick
    tapSlop: 7, tapMs: 600, hitPad: 6,    // px: a tap is a press that barely moves; pick radius = visual + this
    ghost: 0.12,          // the floor you are not looking at, during a route step
    dimStepRatio: 0.38,   // dim × this while a route step is shown (0.26 → 0.1)
    dimStop: 0.72, dimStopStep: 0.4,      // stops of a themed route
    detail: 0.5, detailStep: 0.16,        // room plates / icons / entrance in a route overview / during a step
    pulseMs: 1500, pulseCount: 3, pulseDelay: 500,   // the target's attention cue: finite, after the camera settles
    gapAir: 0.8,          // m of air between stacked floors on screen at rest (orbit: footprints just clear)
    explode: 1.4,         // exploded projection: floor gap × this
    labelMin: 9, labelMax: 12,            // px, label font clamp(0.5 k)
    shaft: 3.2,           // a void seen from above: how deep the well looks, m per m of --m-wall-h (the walls are stylised half-height)  (2 – 5)
    longAspect: 1.6,      // a footprint this much longer than wide (or more) is "long": on a portrait canvas the resting yaw is clamped  (1.4 – 2)
    longShare: 0.8,       // … until one floor's projected footprint is at least this share of the usable canvas width at the fit zoom  (0.7 – 0.88)
    hintMs: 6000,         // the "drag to rotate" hint dies on first touch or after this
    pitchFloor: 4, pitchCeil: 89.5       // deg: the rubber band may stretch the tilt past its limits but never to 0 (a flat or upside-down camera)
  };
  /* camera springs: [response s, epsilon]; damping is 1 − --spring-bounce (default 1 = critically damped) */
  var SPR = { yaw: [0.55, 0.0004], pitch: [0.45, 0.0004], zoom: [0.45, 0.0005], fit: [0.5, 0.0005], at: [0.5, 0.002], inset: [0.45, 0.1], pos: [0.55, 0.003], alpha: [0.4, 0.003] };
  /* pitch offsets from --m-pitch as the question gets more local: overview is low, a room is steep */
  var PITCH_UP = { all: 0, floor: 20, room: 28, routeSide: 16, routeSingle: 22, routeStack: 2 };

  var reduceQ = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
  function reduced() { return !!(reduceQ && reduceQ.matches); }

  /* ---- little maths ------------------------------------------------------------ */
  function clamp(x, lo, hi) { return x < lo ? lo : x > hi ? hi : x; }
  function wrap(a) { return a - TAU * Math.round(a / TAU); }                 // shortest way round
  function band(over, dim) { return (over * dim * 0.55) / (dim + 0.55 * over); }   // UIScrollView rubber band
  function rubber(x, lo, hi, dim) { return x < lo ? lo - band(lo - x, dim) : x > hi ? hi + band(x - hi, dim) : x; }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function rr(r) { return r > 0.2 ? r : 0.2; }                  // canvas arc() / ellipse() throw IndexSizeError on a negative radius: every radius goes through this
  function docLead() { var a = document.documentElement.getAttribute("data-evk-lead"); return a === "zh" || a === "en" ? a : null; }
  function cap1(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }
  function hashStr(s) { var h = 2166136261; for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0) / 4294967295; }

  /* ---- springs: response in seconds (the period), damping ratio (1 = no overshoot) ---- */
  function Spring(x, kind, sys) {
    this.x = x; this.to = x; this.v = 0;
    this.base = SPR[kind][0]; this.eps = SPR[kind][1]; this.kind = kind;
    this.sys = sys;                                  // { scale, damping } from the tokens, shared and live
    this.mult = 1;                                   // the intro slows the yaw for a moment
  }
  Spring.prototype.step = function (dt) {
    if (this.x === this.to && this.v === 0) return false;
    var resp = this.base * this.sys.scale * this.mult;
    var k = Math.pow(TAU / resp, 2), c = 4 * Math.PI * this.sys.damping / resp;
    var n = Math.max(1, Math.ceil(dt / 0.004)), h = dt / n;           // sub-steps of at most 4 ms
    for (var i = 0; i < n; i++) { this.v += (-k * (this.x - this.to) - c * this.v) * h; this.x += this.v * h; }
    if (Math.abs(this.x - this.to) < this.eps && Math.abs(this.v) < this.eps * 8) { this.x = this.to; this.v = 0; return false; }
    return true;
  };
  Spring.prototype.set = function (x) { this.x = this.to = x; this.v = 0; };
  Spring.prototype.hold = function () { this.to = this.x; this.v = 0; };      // a finger caught it
  Spring.prototype.go = function (x, animate) { if (animate && !reduced()) this.to = x; else this.set(x); };

  /* ---- colour: any CSS colour the browser understands -> [r, g, b, a] ---------- */
  var probe = null;
  function parseColor(s, fb) {
    s = (s || "").trim();
    if (!s) return fb;
    var m = /^#([0-9a-f]{3,8})$/i.exec(s);
    if (m) {
      var h = m[1];
      if (h.length === 3 || h.length === 4) h = h.replace(/./g, "$&$&");
      if (h.length === 6 || h.length === 8) return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16), h.length === 8 ? parseInt(h.slice(6), 16) / 255 : 1];
    }
    m = /^rgba?\(\s*([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)$/i.exec(s);
    if (m) {
      var a = m[4] == null ? 1 : /%$/.test(m[4]) ? parseFloat(m[4]) / 100 : parseFloat(m[4]);
      return [+m[1], +m[2], +m[3], a];
    }
    try {                                              // oklch(), color-mix(), hsl(), names…: let the browser resolve it
      if (!probe) { var cv = document.createElement("canvas"); cv.width = cv.height = 1; probe = cv.getContext("2d", { willReadFrequently: true }); }
      probe.clearRect(0, 0, 1, 1);
      probe.fillStyle = "#010203";
      probe.fillStyle = s;
      if (probe.fillStyle === "#010203" && s.replace(/\s/g, "").toLowerCase() !== "#010203") return fb;     // not a colour
      probe.fillRect(0, 0, 1, 1);
      var d = probe.getImageData(0, 0, 1, 1).data;
      var al = d[3] / 255;
      return al ? [Math.round(d[0] / al), Math.round(d[1] / al), Math.round(d[2] / al), al] : [0, 0, 0, 0];
    } catch (e) { return fb; }
  }
  function css(c, f, a) {                              // rgb × brightness f, alpha a (default the colour's own)
    f = f == null ? 1 : f;
    var al = a == null ? (c[3] == null ? 1 : c[3]) : a;
    var r = Math.round(clamp(c[0] * f, 0, 255)), g = Math.round(clamp(c[1] * f, 0, 255)), b = Math.round(clamp(c[2] * f, 0, 255));
    return al >= 0.999 ? "rgb(" + r + "," + g + "," + b + ")" : "rgba(" + r + "," + g + "," + b + "," + (Math.round(al * 1000) / 1000) + ")";
  }
  function mix(a, b, t) { return [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t), 1]; }
  function lum(c) {
    function f(v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
  }
  function opaque(c) { return [c[0], c[1], c[2], 1]; }

  /* ---- tokens ------------------------------------------------------------------- */
  var COLORS = {
    ground: "#EFEDE6", slab: "#E7E3D8", room: "#FFFFFF", block: "#D3CEC2", wall: "#F3F0E8", cap: "#1E2B3A", text: "#1E2B3A",
    route: "#D6402A", "route-halo": "#F6F3EC", dash: "#FFFFFF", climb: "#C77D0A", select: "#B8452C"
  };
  var KEYWORDS = {
    projection: ["orbit", "oblique", "exploded", "plan"], material: ["paper", "line", "clay", "blueprint", "riso"],
    token: ["badge", "pin", "plate", "dot", "flag", "stamp"], light: ["left", "right", "top"], labelCase: ["upper", "none"]
  };
  var SYSFONT = 'system-ui, -apple-system, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Noto Sans SC", "Microsoft YaHei", sans-serif';

  function readTokens(el) {
    var cs = getComputedStyle(el);
    function v(n) { return cs.getPropertyValue(n).trim(); }
    function kw(n, list, fb) { var s = v(n).toLowerCase().replace(/["']/g, ""); return list.indexOf(s) >= 0 ? s : fb; }
    function num(n, fb) { var x = parseFloat(v(n)); return isFinite(x) ? x : fb; }
    var c = {};
    Object.keys(COLORS).forEach(function (k) { c[k] = parseColor(v("--m-" + k), parseColor(COLORS[k])); });
    var sf = v("--m-select-fill");                               // the tint; without the token: the room colour 12 % toward the edge colour
    c["select-fill"] = sf ? parseColor(sf, null) : null;
    if (!c["select-fill"]) c["select-fill"] = mix(c.room, c.select, 0.12);
    var tk = {
      c: c,
      projection: kw("--m-projection", KEYWORDS.projection, "orbit"), material: kw("--m-material", KEYWORDS.material, "paper"),
      token: kw("--m-token", KEYWORDS.token, "badge"), light: kw("--m-light", KEYWORDS.light, "left"),
      labelCase: kw("--m-label-case", KEYWORDS.labelCase, "upper"),
      pitch: clamp(num("--m-pitch", 30), 5, 89), yaw: clamp(num("--m-yaw", 32), -180, 180), wallH: clamp(num("--m-wall-h", 1), 0.2, 4),
      dim: clamp(num("--m-dim", 0.26), 0.04, 1),
      wallT: clamp(num("--m-wall-t", TUNE.wallT), 0.05, 0.8), pinH: clamp(num("--m-pin-h", TUNE.pinH), 0.6, 4), persp: clamp(num("--m-persp", TUNE.persp), 2.5, 60),
      radius: clamp(num("--radius", 0), 0, 999), chamfer: clamp(num("--chamfer", 0), 0, 40),
      dur: clamp(num("--spring-dur", 0.45), 0.15, 1.5), bounce: clamp(num("--spring-bounce", 0), 0, 0.35),
      fLabel: v("--f-label") || SYSFONT, fCjk: v("--f-cjk") || SYSFONT, fNum: v("--f-num") || v("--f-label") || SYSFONT
    };
    tk.sig = JSON.stringify([tk.c, tk.projection, tk.material, tk.token, tk.light, tk.labelCase, tk.pitch, tk.yaw, tk.wallH, tk.dim, tk.wallT, tk.pinH, tk.persp, tk.radius, tk.chamfer, tk.dur, tk.bounce, tk.fLabel, tk.fCjk, tk.fNum]);
    return tk;
  }

  /* ---- materials: how the same scene is painted ------------------------------------
     paper     light slabs, pale walls, an inked cap on every wall (原站 look family)
     line      no fills: hidden-line drawing, ink only, hatched solids
     clay      matte solids, soft ambient shading and contact shadows, no ink
     blueprint dark ground, light lines, a faint drafting grid on every floor
     riso      flat posterised fills multiplied on paper, plates 1–2 px out of register
     A look is {fill, stroke, width} per primitive plus a few switches.
    The chosen room is filled with --m-select-fill and edged with --m-select in every material (blueprint lifts the edge
    if it would not reach 3:1 on its own dark ground). Open areas are a dashed patch (corridor: dashes, open: dots). */
  var SHADE = {          // base − span × s, where s ∈ [−1, 1] is how far a face points away from the light
    paper: { slab: [0.92, 0.20], wall: [0.93, 0.13], block: [0.86, 0.16], top: 1.04 },     // 原站取值
    clay: { slab: [0.74, 0.26], wall: [0.90, 0.30], block: [0.88, 0.30], top: 1.07 }
  };
  function buildLook(tk) {
    var c = tk.c, mat = tk.material, memo = {};
    var paper = c.ground[3] > 0.5 ? opaque(c.ground) : opaque(c.slab);
    var L = {
      mat: mat, ink: c.cap, text: c.text, halo: c["route-halo"], route: c.route, dash: c.dash, climb: c.climb, select: c.select,
      plate: opaque(c.room), ground: null, hidden: paper, op: "source-over", jf: [0, 0], ji: [0, 0],
      shadows: false, grid: false, hatch: false, edge: 0, fills: true
    };
    function S(f, s, w, ink) { return { f: f, s: s, w: w || 1, ink: !!ink }; }
    function cached(name, fn) { return function (s) { var k = name + Math.round(s * 20); return memo[k] || (memo[k] = fn(s)); }; }
    var sf = c["select-fill"];
    function SEL(f, s, w, op) { return { f: f, s: s, w: w || 1.7, ink: false, op: op }; }          // the chosen room: tint inside, edge round it
    function AREA(f, s, w, op) {                                                                    // an open area: a patch with a dashed (corridor) or dotted (open) edge
      var by = {};
      return function (kind) { return by[kind] || (by[kind] = { f: f, s: s, w: w || 0.9, ink: false, op: op, dash: kind === "corridor" ? [6, 4] : [1.5, 4.5] }); };
    }
    var capLight = lum(c.cap) > lum(c.slab);
    if (mat === "paper") {
      var side = capLight ? c.slab : c.cap, sc = SHADE.paper;
      L.slabSide = cached("ss", function (s) { return S(css(side, capLight ? 0.4 : sc.slab[0] - sc.slab[1] * s)); });
      L.slabTop = S(css(c.slab)); L.room = S(css(c.room)); L.roomSel = SEL(css(sf), css(c.select));
      L.area = AREA(css(mix(c.slab, c.room, 0.55)), css(c.cap, 1, 0.5));
      L.well = S(css(c.slab, 0.8));
      L.wallFace = cached("wf", function (s) { return S(css(c.wall, sc.wall[0] - sc.wall[1] * s)); });
      L.wallCap = S(css(c.cap), null, 1, true);
      L.blockFace = cached("bf", function (s) { return S(css(c.block, sc.block[0] - sc.block[1] * s)); });
      L.blockTop = S(css(c.block, sc.top));
    } else if (mat === "clay") {
      var cs = SHADE.clay, cl = mix(c.slab, c.room, 0.35);
      L.shadows = true; L.edge = 0.7;
      L.slabSide = cached("ss", function (s) { return S(css(c.slab, cs.slab[0] - cs.slab[1] * s)); });
      L.slabTop = S(css(c.slab)); L.room = S(css(cl, 1.0)); L.roomSel = SEL(css(mix(cl, sf, 0.9)), css(c.select, 1, 0.9), 1.3);
      L.area = AREA(css(mix(c.slab, c.room, 0.2)), css(c.slab, 0.74), 1);
      L.well = S(css(c.slab, 0.7));
      L.wallFace = cached("wf", function (s) { var col = css(c.wall, cs.wall[0] - cs.wall[1] * s); return S(col, col, 0.7); });
      L.wallCap = S(css(c.wall, cs.top), css(c.wall, cs.top), 0.7);
      L.blockFace = cached("bf", function (s) { var col = css(c.block, cs.block[0] - cs.block[1] * s); return S(col, col, 0.7); });
      L.blockTop = S(css(c.block, cs.top), css(c.block, cs.top), 0.7);
    } else if (mat === "line") {
      var ink = css(c.cap, 1, 0.85), thin = css(c.cap, 1, 0.5), hid = css(L.hidden);
      L.hatch = true; L.fills = false;
      L.slabSide = function () { return S(hid, ink, 0.9); };
      L.slabTop = S(hid, ink, 1.1); L.room = S(hid, thin, 0.7); L.roomSel = SEL(css(mix(L.hidden, sf, 0.9)), css(c.select), 1.4);
      L.area = AREA(hid, thin, 0.8);
      L.well = S(hid, thin, 0.7);
      L.wallFace = function () { return S(hid, ink, 0.8); };
      L.wallCap = S(css(c.cap), null, 1, true);
      L.blockFace = function () { return S(hid, ink, 1); };
      L.blockTop = S(hid, ink, 1);
    } else if (mat === "blueprint") {
      var dark = lum(c.cap) < lum(c.ground) ? c.cap : c.ground, light = dark === c.cap ? c.ground : c.cap;
      if (lum(dark) > 0.12) dark = mix(dark, [8, 14, 30, 1], 0.7);                 // a light theme: deepen the ink into a blueprint ground
      if (lum(light) < 0.55) light = mix(light, [255, 255, 255, 1], 0.78);
      dark = opaque(dark); light = opaque(light);
      L.ground = css(dark); L.hidden = dark; L.ink = light; L.text = light; L.halo = dark; L.plate = mix(dark, light, 0.1); L.grid = true; L.fills = false; L.hatch = true;
      var fg = css(light, 1, 0.85), fg2 = css(light, 1, 0.5);
      L.slabSide = function () { return S(css(dark), fg, 0.9); };
      var edge = c.select, tint = lum(sf) < 0.25 ? mix(dark, sf, 0.85) : mix(dark, edge, 0.26);        // a dark-scheme tint is already right; a light one is re-made for the dark ground
      for (var lift = 0; lift < 8 && (lum(edge) + 0.05) / (lum(dark) + 0.05) < 3; lift++) edge = mix(edge, light, 0.2);   // the edge must stand off the blueprint ground
      L.slabTop = S(css(mix(dark, light, 0.05)), fg, 1); L.room = S(css(mix(dark, light, 0.11)), fg2, 0.7); L.roomSel = SEL(css(tint), css(edge), 1.5);
      L.area = AREA(css(mix(dark, light, 0.06)), fg2, 0.8);
      L.well = S(css(mix(dark, [0, 0, 0, 1], 0.35)), fg2, 0.7);
      L.wallFace = function () { return S(css(mix(dark, light, 0.07)), fg2, 0.7); };
      L.wallCap = S(css(light), null, 1, true);
      L.blockFace = function () { return S(css(mix(dark, light, 0.14)), fg, 0.8); };
      L.blockTop = S(css(mix(dark, light, 0.2)), fg, 0.9);
    } else {                                                                         // riso
      var dk = lum(paper) < 0.3, posterise = function (s) { return s > 0.35 ? 0.8 : s > -0.35 ? 0.9 : 1; };
      /* ink on paper multiplies (a room is paper showing through: knocked out, not white ink);
         light on a dark ground adds up instead (screen) */
      L.ground = css(paper); L.op = dk ? "screen" : "multiply"; L.jf = [1.2, 0.8]; L.ji = [-1, -0.6]; L.hidden = paper;
      var inkTint = dk ? mix(paper, c.cap, 0.4) : mix(paper, c.cap, 0.62);
      L.slabSide = cached("ss", function (s) { return S(css(inkTint, posterise(s))); });
      L.slabTop = S(css(c.slab));
      if (dk) { L.room = S(css(c.room)); L.roomSel = SEL(css(sf), css(c.select), 1.5); L.area = AREA(css(mix(c.room, c.slab, 0.5)), css(c.cap, 1, 0.5)); }
      else {
        L.room = { f: css(paper), s: null, w: 1, ink: false, op: "source-over" };
        L.roomSel = SEL(css(sf), css(c.select), 1.5, "multiply");                             // a second ink laid over the paper
        L.area = AREA(css(paper), css(c.cap, 1, 0.5), 0.9, "source-over");
      }
      L.well = S(css(c.slab, 0.86));
      L.wallFace = cached("wf", function (s) { return S(css(c.wall, posterise(s))); });
      L.wallCap = S(css(c.cap), null, 1, true);
      L.blockFace = cached("bf", function (s) { return S(css(c.block, posterise(s))); });
      L.blockTop = S(css(c.block, 1.03));
    }
    L.roomSelFill = { f: L.roomSel.f, ink: L.roomSel.ink, op: L.roomSel.op };                   // a walled room's tint and its edge are painted apart (the edge sits inside the walls)
    L.roomSelEdge = { s: L.roomSel.s, w: L.roomSel.w, ink: L.roomSel.ink, op: L.roomSel.op };
    /* the rail round a void: a thin ink panel (the posts show as its end lines), and the X drawn over an opening with nothing below it */
    L.rail = { f: css(L.ink, 1, 0.07), s: css(L.ink, 1, 0.75), w: 0.9, ink: true };
    L.cross = css(L.ink, 1, 0.3);
    return L;
  }

  /* ---- geometry ------------------------------------------------------------------ */
  function inside(pts, x, y) {
    var c = false;
    for (var i = 0, j = pts.length - 1; i < pts.length; j = i++) {
      var a = pts[i], b = pts[j];
      if ((a[1] > y) !== (b[1] > y) && x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]) c = !c;
    }
    return c;
  }
  function outward(pts, a, b) {
    var ex = b[0] - a[0], ey = b[1] - a[1], l = Math.hypot(ex, ey) || 1, nx = ey / l, ny = -ex / l;
    if (inside(pts, (a[0] + b[0]) / 2 + nx * 0.02, (a[1] + b[1]) / 2 + ny * 0.02)) { nx = -nx; ny = -ny; }
    return [nx, ny];
  }
  /* the polygon pulled in by d metres (mitred corners); the original if that would fold over. The chosen room's edge is drawn this far
     inside its walls: on the wall line itself the near walls would hide it. */
  function inset(pts, d) {
    var n = pts.length, out = [];
    for (var i = 0; i < n; i++) {
      var a = pts[(i + n - 1) % n], b = pts[i], c = pts[(i + 1) % n];
      var n1 = outward(pts, a, b), n2 = outward(pts, b, c), k = 1 + n1[0] * n2[0] + n1[1] * n2[1];
      if (k < 0.2) return pts;
      out.push([b[0] - (n1[0] + n2[0]) * d / k, b[1] - (n1[1] + n2[1]) * d / k]);
    }
    for (i = 0; i < n; i++) if (!inside(pts, out[i][0], out[i][1])) return pts;
    return out;
  }
  function sides(pts, h) {          // vertical faces of an extruded polygon: [x0, y0, x1, y1, nx, ny, z0, z1]
    var out = [];
    for (var i = 0; i < pts.length; i++) {
      var a = pts[i], b = pts[(i + 1) % pts.length], n = outward(pts, a, b);
      out.push([a[0], a[1], b[0], b[1], n[0], n[1], h[0], h[1]]);
    }
    return out;
  }
  /* a wall segment as a slim box cut into short pieces, so painting far to near stays right;
     both ends are pushed out by half the thickness so corners close (原站: 2.4 m pieces) */
  function wallBoxes(w, T) {
    var x0 = w[0], y0 = w[1], x1 = w[2], y1 = w[3], len = Math.hypot(x1 - x0, y1 - y0);
    if (len < 1e-6) return [];
    var ux = (x1 - x0) / len, uy = (y1 - y0) / len, nx = -uy, ny = ux, h = T / 2;
    x0 -= ux * h; y0 -= uy * h; x1 += ux * h; y1 += uy * h; len += T;
    var n = Math.max(1, Math.ceil(len / 2.4)), out = [];
    for (var i = 0; i < n; i++) {
      var ax = x0 + (x1 - x0) * i / n, ay = y0 + (y1 - y0) * i / n, bx = x0 + (x1 - x0) * (i + 1) / n, by = y0 + (y1 - y0) * (i + 1) / n;
      var p1 = [ax + nx * h, ay + ny * h], p2 = [bx + nx * h, by + ny * h], p3 = [bx - nx * h, by - ny * h], p4 = [ax - nx * h, ay - ny * h];
      var faces = [[p1, p2, nx, ny], [p3, p4, -nx, -ny]];
      if (i === 0) faces.push([p4, p1, -ux, -uy]);
      if (i === n - 1) faces.push([p2, p3, ux, uy]);
      out.push({ faces: faces, top: [p1, p2, p3, p4] });
    }
    return out;
  }
  function ring(g, pts, ox, oy) {          // one closed sub-path (no beginPath: rings can be stacked for holes)
    g.moveTo(pts[0][0] + ox, pts[0][1] + oy);
    for (var i = 1; i < pts.length; i++) g.lineTo(pts[i][0] + ox, pts[i][1] + oy);
    g.closePath();
  }
  function poly(g, pts, ox, oy) {
    g.beginPath();
    ring(g, pts, ox || 0, oy || 0);
  }

  /* ---- little icons on a 48 grid (stairs, lift, toilets) ---------------------------- */
  var GLYPH = {
    stairs: { stroke: "M11 36H19V29H26V22H33V15H38" },
    lift: { stroke: "M14 11H34V37H14Z", fill: "M24 15L29 21H19ZM24 33L29 27H19Z" },
    wc: { fill: "M20.2 13.5A3.2 3.2 0 1 1 13.8 13.5A3.2 3.2 0 1 1 20.2 13.5ZM13.5 19H20.5V28H19V36H15V28H13.5Z" +
                "M34.2 13.5A3.2 3.2 0 1 1 27.8 13.5A3.2 3.2 0 1 1 34.2 13.5ZM31 18.5L36 30H33V36H29V30H26Z M23.2 11H24.8V37H23.2Z" }
  };
  var paths = {};
  function path(d) { return paths[d] || (paths[d] = new Path2D(d)); }
  function framePath(chamfer, radius) {       // the plate behind an icon, in the venue's shape language (chamfer / round / square)
    var key = "F" + chamfer + "/" + radius;
    if (paths[key]) return paths[key];
    var a = 1.25, b = 46.75, p = new Path2D();
    if (chamfer > 0) {
      var c = clamp(chamfer / 8 * 7, 2, 16);
      p.moveTo(a + c, a); p.lineTo(b - c, a); p.lineTo(b, a + c); p.lineTo(b, b - c); p.lineTo(b - c, b); p.lineTo(a + c, b); p.lineTo(a, b - c); p.lineTo(a, a + c); p.closePath();
    } else if (radius > 0) {
      var r = clamp(radius / 8 * 6, 0.01, 22.75);
      p.moveTo(a + r, a); p.arcTo(b, a, b, b, r); p.arcTo(b, b, a, b, r); p.arcTo(a, b, a, a, r); p.arcTo(a, a, b, a, r); p.closePath();
    } else p.rect(a, a, b - a, b - a);
    return (paths[key] = p);
  }
  function plateRect(g, x, y, w, h, chamfer, radius) {       // x, y: top-left; same shape language, in screen px
    g.beginPath();
    if (chamfer > 0) {
      var c = Math.min(chamfer, h * 0.34, w * 0.34);
      g.moveTo(x + c, y); g.lineTo(x + w - c, y); g.lineTo(x + w, y + c); g.lineTo(x + w, y + h - c); g.lineTo(x + w - c, y + h); g.lineTo(x + c, y + h); g.lineTo(x, y + h - c); g.lineTo(x, y + c);
    } else if (radius > 0) {
      var r = Math.max(0, Math.min(radius, h / 2, w / 2));
      g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r);
    } else g.rect(x, y, w, h);
    g.closePath();
  }

  /* ---- entity tokens: what stands for an exhibitor on the map ----------------------
     Each renderer gets one bag and returns its hit circle. All are sized by the caller
     with clamp(metres × k, min, max); selected 1.3×, others dimmed by the caller. */
  /* the characters on a token come from the model (wayfind.js: ent.mono, unique in the venue, `mono` in the schema wins) */
  function monogram(ent) { return ent.mono || (EVK.monograms ? EVK.monograms([ent])[ent.id] : "") || "?"; }
  /* set g.font for the monogram and return it, shrinking the type so a long form (a booth number, 3 or 4 letters) stays inside maxW */
  function monoFit(g, ent, size, maxW, family) {
    var t = monogram(ent);
    g.font = "700 " + Math.round(size) + "px " + family;
    var w = g.measureText(t).width;
    if (w > maxW && w > 0) g.font = "700 " + Math.max(5, Math.round(size * maxW / w)) + "px " + family;
    return t;
  }
  function onColor(hex, L) { return lum(hex) > 0.42 ? [24, 28, 34, 1] : [250, 248, 243, 1]; }

  function disc(g, cx, cy, r, ent, img, L, font) {            // image disc or coloured monogram disc
    if (img) { g.save(); g.beginPath(); g.arc(cx, cy, rr(r), 0, TAU); g.clip(); g.fillStyle = "#fff"; g.fillRect(cx - r, cy - r, r * 2, r * 2); g.drawImage(img, cx - r, cy - r, r * 2, r * 2); g.restore(); return; }
    g.beginPath(); g.arc(cx, cy, rr(r), 0, TAU); g.fillStyle = css(ent.rgb); g.fill();
    if (r >= 7) {
      g.fillStyle = css(onColor(ent.rgb, L)); g.textAlign = "center"; g.textBaseline = "middle";
      g.fillText(monoFit(g, ent, r * 0.92, r * 1.7, font), cx, cy + r * 0.06);
    }
  }
  function foot(g, base, r, sp, L, a) {                       // contact shadow squashed by the pitch so it lies on the floor
    g.beginPath(); g.ellipse(base[0], base[1], rr(Math.max(2, r * 0.42)), rr(Math.max(1, r * 0.42 * sp)), 0, 0, TAU);
    g.fillStyle = css(L.ink, 1, a == null ? 0.18 : a); g.fill();
  }
  function stem(g, base, cx, cy, w, color) { g.beginPath(); g.moveTo(base[0], base[1]); g.lineTo(cx, cy); g.lineWidth = w; g.strokeStyle = color; g.stroke(); }

  var TOKENS = {
    /* badge: an image (or monogram) disc on a hairline pin, ring stroked inside the edge */
    badge: function (b) {
      var g = b.g, L = b.L, r = b.d / 2, cx = b.head[0], cy = b.head[1] - r * 0.15, ring = b.sel ? css(L.route) : css(L.ink);
      foot(g, b.base, r, b.sp, L);
      stem(g, b.base, cx, cy + r - 1, b.sel ? 2 : 1.25, ring);
      if (b.pulseR) pulse(g, cx, cy, r, b);
      g.beginPath(); g.arc(cx, cy + 1, rr(r + 0.5), 0, TAU); g.fillStyle = css(L.ink, 1, 0.22); g.fill();
      disc(g, cx, cy, r, b.ent, b.img, L, b.fNum);
      g.beginPath(); g.arc(cx, cy, rr(r - (b.sel ? 1.25 : 0.6)), 0, TAU); g.lineWidth = b.sel ? 2.5 : 1.2; g.strokeStyle = ring; g.stroke();
      return { x: cx, y: cy, rad: r, top: cy - r, bottom: b.base[1] };
    },
    /* pin: the classic teardrop in the exhibitor's colour, point on the floor */
    pin: function (b) {
      var g = b.g, L = b.L, r = b.d * 0.46, cx = b.head[0], cy = b.head[1] - r * 0.1;
      var ax = b.base[0] - cx, ay = b.base[1] - cy, dist = Math.hypot(ax, ay);
      if (dist < r * 1.7) { var u = dist > 1e-3 ? [ax / dist, ay / dist] : [0, 1]; ax = u[0] * r * 1.7; ay = u[1] * r * 1.7; dist = r * 1.7; }   // steep views: the point stays below the bulb
      var phi = Math.atan2(ay, ax), th = Math.acos(clamp(r / dist, 0, 1)), tipX = cx + ax, tipY = cy + ay;
      foot(g, b.base, r, b.sp, L);
      if (b.pulseR) pulse(g, cx, cy, r, b);
      g.beginPath();
      g.moveTo(tipX, tipY);
      g.lineTo(cx + r * Math.cos(phi - th), cy + r * Math.sin(phi - th));
      g.arc(cx, cy, rr(r), phi - th, phi + th, true);                          // the long way round, over the top
      g.closePath();
      g.fillStyle = css(b.ent.rgb); g.fill();
      g.lineWidth = b.sel ? 2.2 : 1.1; g.strokeStyle = b.sel ? css(L.route) : css(L.ink, 1, 0.85); g.lineJoin = "round"; g.stroke();
      g.beginPath(); g.arc(cx, cy, rr(r * 0.5), 0, TAU); g.fillStyle = css(L.plate); g.fill();
      if (b.img) { g.save(); g.beginPath(); g.arc(cx, cy, rr(r * 0.5), 0, TAU); g.clip(); g.drawImage(b.img, cx - r * 0.5, cy - r * 0.5, r, r); g.restore(); }
      else if (r >= 9) { g.fillStyle = css(L.ink); g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(monoFit(g, b.ent, r * 0.58, r * 1.06, b.fNum), cx, cy + r * 0.04); }
      return { x: cx, y: cy, rad: r, top: cy - r, bottom: b.base[1] };
    },
    /* plate: a number plate on a stem, the exhibitor's colour as a band along its top */
    plate: function (b) {
      var g = b.g, L = b.L, h = b.d * 0.82, w = Math.max(h * 1.55, h + 8), cx = b.head[0], y = b.head[1] - h * 0.9, x = cx - w / 2;
      foot(g, b.base, h * 0.5, b.sp, L);
      stem(g, b.base, cx, y + h, b.sel ? 2 : 1.25, b.sel ? css(L.route) : css(L.ink));
      if (b.pulseR) pulse(g, cx, y + h / 2, Math.max(w, h) / 2, b);
      g.save();
      plateRect(g, x + 1, y + 1.5, w, h, b.chamfer, b.radius); g.fillStyle = css(L.ink, 1, 0.22); g.fill();
      plateRect(g, x, y, w, h, b.chamfer, b.radius); g.fillStyle = css(L.plate); g.fill();
      g.clip();
      g.fillStyle = css(b.ent.rgb); g.fillRect(x, y, w, Math.max(3, h * 0.26));
      g.restore();
      plateRect(g, x, y, w, h, b.chamfer, b.radius); g.lineWidth = b.sel ? 2.5 : 1.2; g.strokeStyle = b.sel ? css(L.route) : css(L.ink); g.stroke();
      g.fillStyle = css(L.text); g.font = "700 " + Math.round(h * 0.46) + "px " + b.fNum; g.textAlign = "center"; g.textBaseline = "middle";
      g.fillText(b.ent.booth || monogram(b.ent), cx, y + h * 0.63);
      return { x: cx, y: y + h / 2, rad: Math.max(w, h) / 2, top: y, bottom: b.base[1] };
    },
    /* dot: lies on the floor, a coloured disc squashed by the pitch (no stem, no billboard) */
    dot: function (b) {
      var g = b.g, L = b.L, r = b.d * 0.5, x = b.base[0], y = b.base[1] - (b.sel ? r * 0.25 : 0), ry = Math.max(r * b.sp, r * 0.28);
      if (b.pulseR) { g.beginPath(); g.ellipse(x, y, rr(r + b.pulseR), rr((r + b.pulseR) * Math.max(b.sp, 0.28)), 0, 0, TAU); g.lineWidth = 2; g.strokeStyle = css(L.route, 1, b.pulseA); g.stroke(); }
      g.beginPath(); g.ellipse(x, y + 1, rr(r + 0.5), rr(ry + 0.5), 0, 0, TAU); g.fillStyle = css(L.ink, 1, 0.2); g.fill();
      g.beginPath(); g.ellipse(x, y, rr(r), rr(ry), 0, 0, TAU); g.fillStyle = css(b.ent.rgb); g.fill();
      g.lineWidth = b.sel ? 2.4 : 1.2; g.strokeStyle = b.sel ? css(L.route) : css(L.plate); g.stroke();
      g.beginPath(); g.ellipse(x, y, rr(r * 0.38), rr(ry * 0.38), 0, 0, TAU); g.fillStyle = css(L.plate, 1, 0.92); g.fill();
      return { x: x, y: y, rad: Math.max(r, 8), top: y - ry, bottom: y + ry };
    },
    /* flag: a pole with a swallow-tailed pennant in the exhibitor's colour */
    flag: function (b) {
      var g = b.g, L = b.L, hh = Math.max(b.base[1] - b.head[1], b.d * 1.1), x = b.base[0], top = b.base[1] - hh, w = b.d * 0.95, h = b.d * 0.62;
      foot(g, b.base, b.d * 0.4, b.sp, L);
      if (b.pulseR) pulse(g, x + w * 0.4, top + h / 2, w * 0.5, b);
      g.beginPath(); g.moveTo(x, b.base[1]); g.lineTo(x, top - 1); g.lineWidth = b.sel ? 2.2 : 1.5; g.strokeStyle = b.sel ? css(L.route) : css(L.ink); g.lineCap = "round"; g.stroke();
      g.beginPath(); g.moveTo(x, top); g.lineTo(x + w, top); g.lineTo(x + w - w * 0.2, top + h / 2); g.lineTo(x + w, top + h); g.lineTo(x, top + h); g.closePath();
      g.fillStyle = css(b.ent.rgb); g.fill(); g.lineJoin = "round"; g.lineWidth = b.sel ? 2 : 1; g.strokeStyle = b.sel ? css(L.route) : css(L.ink, 1, 0.8); g.stroke();
      if (h >= 11) { g.fillStyle = css(onColor(b.ent.rgb, L)); g.textAlign = "left"; g.textBaseline = "middle"; g.fillText(monoFit(g, b.ent, h * 0.52, w * 0.66, b.fNum), x + w * 0.14, top + h / 2 + 0.5); }
      g.beginPath(); g.arc(x, top - 1, 1.8, 0, TAU); g.fillStyle = css(L.ink); g.fill();
      return { x: x + w * 0.4, y: top + h / 2, rad: Math.max(w * 0.55, 10), top: top, bottom: b.base[1] };
    },
    /* stamp: a perforated square, slightly off-true like a stamp stuck on a letter */
    stamp: function (b) {
      var g = b.g, L = b.L, s = b.d * 1.02, cx = b.head[0], cy = b.head[1] - s * 0.5, rot = (hashStr(b.ent.id) - 0.5) * 6 * DEG;
      foot(g, b.base, s * 0.4, b.sp, L, 0.14);
      stem(g, b.base, cx, cy + s * 0.5 - 1, b.sel ? 2 : 1.25, b.sel ? css(L.route) : css(L.ink));
      if (b.pulseR) pulse(g, cx, cy, s * 0.62, b);
      g.save(); g.translate(cx, cy); g.rotate(rot);
      var half = s / 2, hole = Math.max(1.4, s * 0.055), n = Math.max(4, Math.round(s / (hole * 3.3))), step = s / n, p = new Path2D();
      p.rect(-half, -half, s, s);
      for (var i = 0; i <= n; i++) {
        var t = -half + i * step;
        p.moveTo(t + hole, -half); p.arc(t, -half, hole, 0, TAU);
        p.moveTo(t + hole, half); p.arc(t, half, hole, 0, TAU);
        p.moveTo(-half + hole, t); p.arc(-half, t, hole, 0, TAU);
        p.moveTo(half + hole, t); p.arc(half, t, hole, 0, TAU);
      }
      g.save(); g.translate(1, 1.5); g.fillStyle = css(L.ink, 1, 0.22); g.fill(p, "evenodd"); g.restore();
      g.fillStyle = css(L.plate); g.fill(p, "evenodd");
      var inset = hole * 2.1 + s * 0.05, q = s - inset * 2;
      if (b.img) { g.save(); g.beginPath(); g.rect(-q / 2, -q / 2, q, q); g.clip(); g.drawImage(b.img, -q / 2, -q / 2, q, q); g.restore(); }
      else {
        g.fillStyle = css(b.ent.rgb); g.fillRect(-q / 2, -q / 2, q, q);
        if (q >= 12) { g.fillStyle = css(onColor(b.ent.rgb, L)); g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(monoFit(g, b.ent, q * 0.46, q * 0.9, b.fNum), 0, q * 0.03); }
      }
      g.lineWidth = b.sel ? 2.2 : 1; g.strokeStyle = b.sel ? css(L.route) : css(L.ink, 1, 0.6); g.strokeRect(-q / 2, -q / 2, q, q);
      g.restore();
      return { x: cx, y: cy, rad: s * 0.55, top: cy - s / 2, bottom: b.base[1] };
    }
  };
  function pulse(g, cx, cy, r, b) {            // the attention cue: rings that grow and fade, a finite number of times
    g.beginPath(); g.arc(cx, cy, rr(r + 3 + b.pulseR), 0, TAU); g.lineWidth = 2; g.strokeStyle = css(b.L.route, 1, b.pulseA); g.stroke();
  }

  /* ---- images: one redraw hook per async resource -------------------------------------- */
  function imageReady(im) { return im && im.complete && im.naturalWidth > 0 ? im : null; }

  /* ================================================================================== */
  /*  The map                                                                           */
  /* ================================================================================== */
  function VenueMap(canvas, venue, opts) {
    if (!(this instanceof VenueMap)) return new VenueMap(canvas, venue, opts);
    var self = this;
    opts = opts || {};
    this.canvas = canvas; this.g = canvas.getContext("2d"); this.venue = venue; this.opts = opts;
    this.root = canvas.parentElement || canvas;
    this.T = {}; Object.keys(TUNE).forEach(function (k) { self.T[k] = opts.tuning && opts.tuning[k] != null ? opts.tuning[k] : TUNE[k]; });
    /* the lead language: an explicit `lead` wins; otherwise <html data-evk-lead> (and it is followed live); else the old `lang`; else en */
    this.leadAuto = !(opts.lead === "zh" || opts.lead === "en");
    this.lead = this.lang = this.leadAuto ? docLead() || (opts.lang === "zh" ? "zh" : "en") : opts.lead;
    this.roomFrom = null;                                   // the view to return to when a focused room is let go (focusRoom(null))
    this.stacked = true;                                    // floors are laid one above the other (a void shows the floor below only then)
    this.yawMax = Infinity;                                 // |resting yaw| cap for a long building on a portrait canvas (footprintCap); no cap until the canvas has a size
    this.m = EVK.venueModel(venue, opts.entities || null);
    this.W = 0; this.H = 0; this.dpr = 1;
    this.mode = "all"; this.room = null; this.sel = null; this.hoverId = null; this.stops = null; this.route = null;
    this.pulse = 0; this.frame = 0; this.last = 0; this.visible = true; this.locked = false;
    this.fling = 0; this.panFling = null; this.pointers = {}; this.hits = []; this.floorHits = []; this.turned = false; this.dragging = false;
    this.cleanup = [];
    this.sys = { scale: 1, damping: 1 };
    this.tk = readTokens(canvas); this.look = buildLook(this.tk); this.sysFromTokens();

    this.ents = this.m.entities.map(function (e) {
      var rgb = parseColor(e.color, [119, 119, 119, 1]);
      return { id: e.id, name: e.name, short: e.short, mono: e.mono, booth: e.booth, color: e.color, rgb: rgb, room: e.room, floor: e.floor, at: e.at, raw: e.raw, ent: e };
    });
    this.entById = {}; this.ents.forEach(function (e) { self.entById[e.id] = e; });

    var b = this.m.bounds;
    this.cx = (b[0] + b[2]) / 2; this.cy = (b[1] + b[3]) / 2; this.half = Math.hypot(b[2] - b[0], b[3] - b[1]) / 2;
    this.n = this.m.floors.length;

    var S = this.sys;
    this.yaw = new Spring(0, "yaw", S); this.pitch = new Spring(0, "pitch", S); this.zoom = new Spring(1, "zoom", S); this.fitS = new Spring(1, "fit", S);
    this.tx = new Spring(this.cx, "at", S); this.ty = new Spring(this.cy, "at", S); this.tz = new Spring(0, "at", S);
    this.pt = new Spring(0, "inset", S); this.pr = new Spring(0, "inset", S); this.pb = new Spring(0, "inset", S); this.pl = new Spring(0, "inset", S);
    this.gut = new Spring(0, "inset", S);
    this.sx = new Spring(0, "inset", S); this.sy = new Spring(0, "inset", S);       // screen-space centring left over after the perspective fit
    this.springs = [this.pitch, this.zoom, this.fitS, this.tx, this.ty, this.tz, this.pt, this.pr, this.pb, this.pl, this.gut, this.sx, this.sy];
    this.floors = this.m.floors.map(function (f, i) { return self.prepare(f, i); });
    this.links = this.m.links.map(function (l) { return { lo: self.floors[self.m.order[l.lo]], hi: self.floors[self.m.order[l.hi]], a: l.a, b: l.b, kind: l.kind, key: l.key }; });

    this.setupDom();
    this.limits(); this.layoutConstants();
    this.resize();
    this.setMode(opts.floor && this.m.order[opts.floor] != null ? opts.floor : "all", false);
    if (opts.select && this.entById[opts.select]) { this.sel = opts.select; this.pulse = reduced() ? 0 : performance.now() + 900; }     // 原站: 900 ms on first load, 500 ms later
    if (opts.intro !== false && !reduced()) this.intro();
    this.bind();
    this.kick();
  }

  VenueMap.version = "0.1.0";
  VenueMap.validate = function (venue) { return EVK.venueModel(venue, null, {}).warnings.slice(); };
  var P_ = VenueMap.prototype;

  P_.sysFromTokens = function () {
    var tk = this.tk;
    this.sys.scale = tk.dur / 0.45;                         // 0.45 s ≈ the middle of the source's 0.4–0.55 s band
    this.sys.damping = 1 - tk.bounce;                       // Apple's convention: bounce 0 = critically damped
  };

  P_.prepare = function (f, i) {
    var self = this;
    var fl = {
      id: f.id, level: f.level, rank: i, name: f.name, short: f.short, outline: f.outline, bbox: f.bbox, rooms: f.rooms, areas: f.areas, blocks: [], voids: [], walls: [], f: f,
      slabSides: sides(f.outline, [-this.T.slab, 0]),
      z: new Spring(0, "pos", this.sys), ox: new Spring(0, "pos", this.sys), oy: new Spring(0, "pos", this.sys), alpha: new Spring(1, "alpha", this.sys),
      entrance: f.entrance
    };
    fl.blocks = f.blocks.filter(function (bl) { return bl.kind !== "void"; }).map(function (bl) { return { b: bl, kind: bl.kind, poly: bl.poly, sides: sides(bl.poly, [0, 1]), c: bl.c, size: bl.size, label: bl.label, id: bl.id, bbox: bl.bbox }; });
    /* a void: no mass. Its rim (the slab's cut edge, seen on the far side), and its rail cut into posts-and-panel pieces of at most 1.6 m */
    fl.voids = f.voids.map(function (v) {
      var rim = sides(v.poly, [-self.T.slab, 0]), segs = [];
      rim.forEach(function (s) {
        var len = Math.hypot(s[2] - s[0], s[3] - s[1]), n = Math.max(1, Math.ceil(len / 1.6));
        for (var k = 0; k < n; k++) segs.push({ a: [s[0] + (s[2] - s[0]) * k / n, s[1] + (s[3] - s[1]) * k / n], b: [s[0] + (s[2] - s[0]) * (k + 1) / n, s[1] + (s[3] - s[1]) * (k + 1) / n], n: [s[4], s[5]] });
      });
      return { b: v, poly: v.poly, rim: rim, segs: segs, c: v.c, size: v.size, label: v.label, id: v.id, bbox: v.bbox };
    });
    this.buildWalls(fl);
    return fl;
  };
  P_.buildWalls = function (fl) {
    var T = this.tk.wallT, out = [];
    fl.f.walls.forEach(function (w) { out = out.concat(wallBoxes(w, T)); });
    fl.walls = out; fl.wallT = T;
  };

  /* DOM touches: the canvas is a page citizen. Only attributes that are missing get set. */
  P_.setupDom = function () {
    var c = this.canvas, root = this.root;
    if (!c.hasAttribute("tabindex")) c.setAttribute("tabindex", "0");
    if (!c.hasAttribute("role")) c.setAttribute("role", "img");
    this.labelled = !c.hasAttribute("aria-label");
    this.aria();
    var ta = getComputedStyle(c).touchAction;
    if (!ta || ta === "auto") c.style.touchAction = "pan-y";
    c.style.userSelect = "none"; c.style.webkitUserSelect = "none"; c.style.webkitTapHighlightColor = "transparent";
    if (!c.style.cursor) { c.style.cursor = "grab"; this.cur = "grab"; }
    if (root !== c && getComputedStyle(root).position === "static") root.style.position = "relative";
    root.classList.add("is-live");
    this.syncDrag();
    this.hint = root.querySelector(".evk-map-hint"); this.resetBtn = root.querySelector(".evk-map-reset"); this.tip = root.querySelector(".evk-map-tip");
    if (this.hint) { /* the hint is page markup: it only needs to know when to go */ }
  };
  /* what one finger dragging does: "rotate" | "pan" (see the header); the map root says it too, for a hint that follows it */
  P_.dragMode = function () { return VenueMap.dragModeFor(this.tk.projection); };
  P_.syncDrag = function () { var d = this.dragMode(); if (this.root.getAttribute("data-evk-drag") !== d) { this.root.setAttribute("data-evk-drag", d); return true; } return false; };
  P_.aria = function () {
    if (!this.labelled) return;
    var m = this.m, zh = this.lead === "zh", nm = zh ? m.name.cn : m.name.en, pan = this.dragMode() === "pan";
    this.canvas.setAttribute("aria-label", zh
      ? "立体楼层导览：" + nm + "，" + m.floors.length + " 层，" + m.entities.length + " 个展位。可以拖动" + (pan ? "平移" : "旋转") + "、双指缩放，方向键也可以操作；方括号键切换展位。页面下方的列表列出全部展位。"
      : "3D floor guide of " + nm + ": " + m.floors.length + " floors, " + m.entities.length + " exhibitors. Drag to " + (pan ? "pan" : "turn") + ", pinch to zoom, or use the arrow keys; [ and ] step through exhibitors. The list below the map has the same information.");
  };

  /* ---- tokens, live ----------------------------------------------------------------- */
  /* follow <html data-evk-lead> unless the lead was pinned by the option or setLead() */
  P_.syncLead = function () {
    if (!this.leadAuto) return false;
    var l = docLead() || (this.opts.lang === "zh" ? "zh" : "en");
    if (l === this.lead) return false;
    this.lead = this.lang = l; this.aria(); this.setTip(null); this.kick();
    return true;
  };
  P_.refresh = function () {
    this.syncLead();
    var tk = readTokens(this.canvas);
    if (this.tk && tk.sig === this.tk.sig) return false;
    var old = this.tk, geometry = tk.wallT !== old.wallT;
    this.tk = tk; this.look = buildLook(tk); this.sysFromTokens();
    if (geometry) this.floors.forEach(this.buildWalls, this);
    this.limits(); this.layoutConstants();
    if (this.syncDrag()) this.aria();
    var layoutChanged = tk.projection !== old.projection || tk.wallH !== old.wallH || tk.pitch !== old.pitch || tk.yaw !== old.yaw || tk.persp !== old.persp || tk.pinH !== old.pinH;
    if (layoutChanged) {
      var keep = this.route ? this.route.active : null, rt = this.route && this.route.plan;
      if (tk.projection !== old.projection || tk.pitch !== old.pitch || tk.yaw !== old.yaw) this.turned = false;      // a new resting angle wins; a taller wall does not undo the person's turn
      if (this.mode === "route" && rt) { this.setRoute(rt, true); this.routeStep(keep, true); }
      else this.setMode(this.mode, true, true);
    }
    this.syncReset(); this.kick();
    return true;
  };
  P_.limits = function () {
    var plan = this.tk.projection === "plan";
    this.pmin = (plan ? 80 : this.T.pitchMin) * DEG; this.pmax = (plan ? 89 : this.T.pitchMax) * DEG;
  };
  /* the tilt while a finger drags: rubber-banded past its limits, but the stretch can never reach a flat (0) or upside-down camera,
     which is what made the band's negative pitch throw "negative radius" from every ellipse until it was pulled back */
  P_.pitchBand = function (x) { return clamp(rubber(x, this.pmin, this.pmax, 0.5), this.T.pitchFloor * DEG, this.T.pitchCeil * DEG); };
  P_.font = function (kind, weight, size) {
    var tk = this.tk, stack = kind === "cjk" ? tk.fCjk : kind === "num" ? tk.fNum : tk.fLabel;
    return weight + " " + size + "px " + stack;
  };
  P_.wallH = function () { return this.tk.wallH; };
  P_.blockH = function () { return this.tk.wallH * this.T.blockRatio; };

  /* ---- the camera: a general projection, so oblique can share every drawing routine ---- */
  /* ex, ey: screen-right and screen-up as vectors in (x, y, z); v: toward the viewer (depth, bigger = nearer) */
  P_.basis = function (yaw, pitch) {
    pitch = clamp(pitch, this.T.pitchFloor * DEG, this.T.pitchCeil * DEG);        // belt and braces: no code path may reach a flat or inverted camera
    var cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
    if (this.tk.projection === "oblique") {
      var shx = clamp(-Math.tan(yaw) * cp * 0.55, -1, 1), vx = -shx, vy = cp / sp, vz = 1, vl = Math.hypot(vx, vy, vz);
      var pl = Math.hypot(vx, vy) || 1;
      return { ex: [1, 0, shx], ey: [0, -sp, cp], v: [vx / vl, vy / vl, vz / vl], vp: [vx / pl, vy / pl], xp: [1, 0], par: true, sp: sp };
    }
    return { ex: [cy, -sy, 0], ey: [-sy * sp, -cy * sp, cp], v: [sy * cp, cy * cp, sp], vp: [sy, cy], xp: [cy, -sy], par: false, sp: sp };
  };
  P_.camera = function () {
    var b = this.basis(this.yaw.x, this.pitch.x), insetL = this.pl.x + this.gut.x, insetR = this.pr.x;
    this.cam = {
      ex0: b.ex[0], ex1: b.ex[1], ex2: b.ex[2], ey0: b.ey[0], ey1: b.ey[1], ey2: b.ey[2], v0: b.v[0], v1: b.v[1], v2: b.v[2],
      vp: b.vp, xp: b.xp, par: b.par, sp: b.sp, s: this.fitS.x * this.zoom.x, L: this.L,
      ox: (this.W + insetL - insetR) / 2 + this.sx.x, oy: this.H / 2 + (this.pt.x - this.pb.x) / 2 + this.sy.x,        // band → pan (a sheet below), column → refit (fitTo)
      tx: this.tx.x, ty: this.ty.x, tz: this.tz.x
    };
  };
  /* plan (x, y) at height z -> [screen x, screen y, depth (bigger = nearer), px per metre there] */
  P_.P = function (x, y, z) {
    var c = this.cam, dx = x - c.tx, dy = y - c.ty, dz = z - c.tz;
    var x1 = dx * c.ex0 + dy * c.ex1 + dz * c.ex2, Y = dx * c.ey0 + dy * c.ey1 + dz * c.ey2, D = dx * c.v0 + dy * c.v1 + dz * c.v2;
    var k = c.par ? c.s : c.L / (c.L - D) * c.s;
    return [c.ox + x1 * k, c.oy - Y * k, D, k];
  };
  /* how much of a vertical face with outward normal (nx, ny) faces the viewer, and which way it leans from the light */
  P_.facing = function (nx, ny) {
    var c = this.cam;
    return [nx * c.vp[0] + ny * c.vp[1], nx * c.xp[0] + ny * c.xp[1]];       // [toward viewer, toward screen right]
  };
  P_.lightS = function (face) {                              // −1 lit … +1 shaded, for the chosen --m-light
    var l = this.tk.light;
    if (l === "right") return -face[1];
    if (l === "top") return clamp(0.55 - 1.1 * face[0], -1, 1);
    return face[1];                                         // left (原站): light fixed in view space, upper left
  };

  P_.layoutConstants = function () {
    var tk = this.tk;
    this.yawMax = this.footprintCap();                       // before the gap: the gap is worked out at the yaw the map will rest at
    this.computeGap();
    var stackH = (this.n - 1) * this.gap + tk.wallH;
    this.stackR = Math.hypot(this.half, stackH / 2);
    this.L = this.stackR * tk.persp;
      };
  /* the height between stacked floors that keeps their footprints from covering each other on screen
     at the resting view: gap × cos(pitch) ≈ footprint depth × sin(pitch) + wall height (+ a little air) */
  P_.gapFor = function (floors, yaw, pitch, air) {
    var b = this.basis(yaw, pitch), lo = Infinity, hi = -Infinity;
    floors.forEach(function (f) { f.outline.forEach(function (p) { var d = p[0] * b.ey[0] + p[1] * b.ey[1]; lo = Math.min(lo, d); hi = Math.max(hi, d); }); });
    return ((hi - lo) + air) / Math.max(b.ey[2], 0.2) + this.tk.wallH + this.T.slab;
  };
  P_.gapAt = function (yaw) {                                // the floor-to-floor height at a resting yaw
    var pitch = this.pitchFor("all"), gap = this.gapFor(this.floors, yaw, pitch, this.T.gapAir * (this.tk.projection === "oblique" ? 3 : 1));
    if (this.tk.projection === "exploded") gap *= this.T.explode;
    return Math.max(gap, this.tk.wallH * 6);
  };
  P_.computeGap = function () { this.gap = this.gapAt(this.yawFor("all", false)); };
  /* ---- long buildings on a portrait canvas ------------------------------------------------------------------
     A footprint 50 x 20 m turned 30° runs away from the viewer: on a 375 px phone every stacked floor ends up a hand wide.
     The rule: when the footprint (all floors' bounds) is longer than T.longAspect : 1 along x, the canvas is taller than wide and
     the projection turns the plan (orbit, exploded, plan; an oblique yaw is a shear and keeps the long side across anyway), the
     resting yaw is clamped to the largest |yaw| (never above the token's) at which ONE floor's projected footprint is still
     T.longShare (80 %) of the usable canvas width (width less the floor-label gutter) at the fit zoom of the whole stack; if even yaw 0
     cannot reach it, the best yaw found wins. Worked out for the all-floors stack, then applied to every resting view (one floor,
     a route). It is recomputed whenever the canvas size, the tokens or the orientation change (resize()), in whole degrees so a
     dragged window does not re-lay the map out at every pixel. Only the resting pose is clamped: the person can still turn the map. */
  P_.footprintCap = function () {
    var tk = this.tk, T = this.T, b = this.m.bounds, w = b[2] - b[0], d = b[3] - b[1], W = this.W, H = this.H;
    if (!(W > 0 && H > W) || tk.projection === "oblique" || this.n < 1 || w < T.longAspect * Math.max(d, 0.01)) return Infinity;
    var raw = Math.abs(tk.yaw) * DEG * (tk.projection === "plan" ? 0.5 : 1), self = this;
    if (raw < 1 * DEG) return Infinity;
    var pitch = this.pitchFor("all"), n = this.n, usable = Math.max(W - (n > 1 && tk.projection !== "plan" ? this.labelSize()[1] + 14 : 0), 1);
    function share(yaw) {
      var gap = self.gapAt(yaw), stackH = (n - 1) * gap + tk.wallH, L = Math.hypot(self.half, stackH / 2) * tk.persp, items = [], one = 0;
      var flat = tk.projection === "plan";
      self.floors.forEach(function (f, i) { items.push({ pts: f.outline, zs: flat ? [-T.slab, tk.pinH] : [i * gap - T.slab, i * gap + tk.pinH] }); });
      var bb = bboxOfItems(items), view = { yaw: yaw, pitch: pitch, tx: (bb[0] + bb[2]) / 2, ty: (bb[1] + bb[3]) / 2, tz: (bb[4] + bb[5]) / 2, L: L };
      var all = self.projBox(items, view);
      var s = Math.min(usable * 0.9 / Math.max(all[1] - all[0], 0.02), H * 0.9 / Math.max(all[3] - all[2], 0.02));
      self.floors.forEach(function (f, i) {
        var bx = self.projBox([{ pts: f.outline, zs: [flat ? 0 : i * gap] }], view);
        one = Math.max(one, bx[1] - bx[0]);
      });
      return one * s / usable;
    }
    var best = raw, bs = -1, y;
    for (var deg = Math.floor(raw / DEG); deg >= 0; deg--) {
      y = deg * DEG;
      var sh = share(y);
      if (sh >= T.longShare) return y >= raw - 1e-6 ? Infinity : y;
      if (sh > bs) { bs = sh; best = y; }
    }
    return best;
  };
  P_.pitchFor = function (kind) {
    var tk = this.tk;
    if (tk.projection === "plan") return (kind === "room" ? 87 : 84) * DEG;
    return clamp((tk.pitch + (PITCH_UP[kind] || 0)) * DEG, this.pmin || this.T.pitchMin * DEG, this.pmax || this.T.pitchMax * DEG);
  };
  P_.yawFor = function (kind, tall) {
    var tk = this.tk, y = tk.yaw * DEG, cap = this.yawMax;
    if (tk.projection === "oblique") return y;                              // locked
    if (tk.projection === "plan") y *= 0.5;
    if (kind === "routeSide") y *= 0.56;                                    // 原站: 18° of 32°
    else if (kind !== "all" && tall) y *= 0.44;                             // 原站: one floor on a tall screen, 14° of 32°
    return cap < Math.abs(y) ? (y < 0 ? -cap : cap) : y;                    // a long building on a portrait canvas keeps its long side across (footprintCap)
  };

  /* ---- where each floor stands in a mode (z, ox, oy, alpha), and the camera for it ------ */
  P_.rankOf = function (fid) { return this.m.order[fid]; };
  P_.floorById = function (fid) { var i = this.m.order[fid]; return i == null ? null : this.floors[i]; };
  P_.extent = function (f, dir) {                           // length of a floor's outline along a plan direction
    var lo = Infinity, hi = -Infinity;
    f.outline.forEach(function (p) { var d = p[0] * dir[0] + p[1] * dir[1]; lo = Math.min(lo, d); hi = Math.max(hi, d); });
    return hi - lo;
  };
  /* tiles: floors laid out flat as a grid in screen axes, in reading order (first floor top-left). "row" and "col" force the
     shape; "auto" takes whichever grid lets the plans be drawn largest on this canvas. */
  P_.tiles = function (list, how, yaw, air) {
    var xp = [Math.cos(yaw), -Math.sin(yaw)], up = [-Math.sin(yaw), -Math.cos(yaw)], self = this, fw = 0, fh = 0, n = list.length;
    list.forEach(function (f) { fw = Math.max(fw, self.extent(f, xp)); fh = Math.max(fh, self.extent(f, up)); });
    var cols = how === "row" ? n : how === "col" ? 1 : 1, best = -1;
    if (how === "auto") {
      for (var c = 1; c <= n; c++) {
        var sc = Math.min((this.W - 90) / (c * (fw + air)), (this.H - 60) / (Math.ceil(n / c) * (fh + air)));
        if (sc > best + 1e-9) { best = sc; cols = c; }
      }
    }
    var rows = Math.ceil(n / cols);
    return list.map(function (f, i) {
      var dx = (i % cols - (cols - 1) / 2) * (fw + air), dy = (Math.floor(i / cols) - (rows - 1) / 2) * (fh + air);     // dy runs down the screen
      return [0, xp[0] * dx - up[0] * dy, xp[1] * dx - up[1] * dy];
    });
  };
  P_.setMode = function (mode, animate, keepFrom) {
    var idx = this.m.order[mode], self = this, plan = this.tk.projection === "plan";
    this.mode = idx == null ? "all" : mode;
    this.route = null;
    if (!keepFrom) this.roomFrom = null;                     // the person went somewhere else: a later focusRoom(null) has nothing to go back to
    this.stacked = !plan && idx == null;
    var sel = idx == null ? null : this.floors[idx];
    var offs = plan ? this.tiles(this.floors, "auto", this.yawFor("all", false), 6) : null;
    this.floors.forEach(function (f, i) {
      var z = 0, a, ox = 0, oy = 0;
      if (!sel) { a = 1; if (offs) { ox = offs[i][1]; oy = offs[i][2]; } else { z = f.rank * self.gap; ox = self.leanX(z); } }
      else if (f === sel) a = 1;
      else {
        a = 0;
        if (offs) { ox = offs[i][1]; oy = offs[i][2]; }
        else { z = (f.rank - sel.rank) * self.gap * 1.2; ox = self.leanX(z); }     // the others slide away along the stack, upper up and lower down (原站: 26 vs 22)
      }
      self.place(f, z, a, ox, oy, animate);
    });
    if (this.room && (!sel || this.roomInfo(this.room).floor !== sel.id)) this.room = null;
    this.glide(animate);
    this.syncReset();
  };
  /* an oblique stack leans (the height axis is drawn at an angle); shift each floor back along x so the storeys stay in one column on screen */
  P_.leanX = function (z, pitch) {
    if (this.tk.projection !== "oblique") return 0;
    return -this.basis(this.yawFor("all", false), pitch == null ? this.pitchFor("all") : pitch).ex[2] * z;
  };
  P_.place = function (f, z, a, ox, oy, animate) {
    f.z.go(z, animate); f.alpha.go(a, animate); f.ox.go(ox, animate); f.oy.go(oy, animate);
  };

  P_.roomInfo = function (rid) {
    var r = this.m.roomById[rid];
    if (!r) return null;
    var f = this.floorById(r.floor), m = 0;
    r.poly.forEach(function (p) { m = Math.max(m, Math.hypot(p[0] - r.c[0], p[1] - r.c[1])); });
    return { room: r, floor: r.floor, f: f, c: r.c, r: m };
  };
  P_.labelSize = function () {            // [height, width] of a floor label ("1F")
    var h = clamp(this.H / 24, 15, 26), g = this.g, w = 0;
    g.font = this.font("num", 700, h);
    this.m.floors.forEach(function (f) { w = Math.max(w, g.measureText(f.id).width); });
    return [h, w];
  };

  /* px per metre that fits the items (points at heights) around the view's look-at point, through the real projection:
     the nearest floor is magnified more than the far one, so the fit measures the projected box, scales to the share of the
     canvas, and keeps the leftover centring offset (sx, sy). The source used an orthographic fit ÷ 1.06; this is exact. */
  P_.projBox = function (items, view) {                  // [x0, x1, y0, y1] in metres on the screen plane, perspective included (view.L overrides the camera distance)
    var b = this.basis(view.yaw, view.pitch), L = view.L || this.L, x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    items.forEach(function (it) {
      it.pts.forEach(function (p) {
        var dx = p[0] - view.tx, dy = p[1] - view.ty;
        it.zs.forEach(function (z) {
          var dz = z - view.tz, X = dx * b.ex[0] + dy * b.ex[1] + dz * b.ex[2], Y = dx * b.ey[0] + dy * b.ey[1] + dz * b.ey[2];
          var k = b.par ? 1 : L / (L - (dx * b.v[0] + dy * b.v[1] + dz * b.v[2]));
          X *= k; Y *= k;
          x0 = Math.min(x0, X); x1 = Math.max(x1, X); y0 = Math.min(y0, Y); y1 = Math.max(y1, Y);
        });
      });
    });
    return [x0, x1, y0, y1];
  };
  P_.fitTo = function (items, view, share) {
    var bx = this.projBox(items, view), x0 = bx[0], x1 = bx[1], y0 = bx[2], y1 = bx[3];
    var w = Math.max(this.W - (view.gut || 0) - this.pl.to - this.pr.to, 1);
    var dy = Math.max(y1 - y0, 0.02), s = Math.min(w * share / Math.max(x1 - x0, 0.02), this.H * share / dy), band = this.H - this.pt.to - this.pb.to;
    if (band < this.H - 1) s = Math.min(s, Math.max(band, 80) * Math.max(share, 0.85) / dy);        // a sheet over the map: pan into the free band, and shrink only if the model does not fit it
    view.sx = -s * (x0 + x1) / 2; view.sy = s * (y0 + y1) / 2;
    return s;
  };
  function bboxOfItems(items) {
    var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity, z0 = Infinity, z1 = -Infinity;
    items.forEach(function (it) {
      it.pts.forEach(function (p) { x0 = Math.min(x0, p[0]); y0 = Math.min(y0, p[1]); x1 = Math.max(x1, p[0]); y1 = Math.max(y1, p[1]); });
      it.zs.forEach(function (z) { z0 = Math.min(z0, z); z1 = Math.max(z1, z); });
    });
    return [x0, y0, x1, y1, z0, z1];
  }
  function shifted(pts, ox, oy) { return pts.map(function (p) { return [p[0] + ox, p[1] + oy]; }); }
  function grown(pts, m) {                // the corners of a shape pushed out by m metres in four diagonals
    var o = [];
    pts.forEach(function (p) { o.push([p[0] - m, p[1] - m], [p[0] + m, p[1] + m], [p[0] - m, p[1] + m], [p[0] + m, p[1] - m]); });
    return o;
  }

  /* the resting camera for the current mode; yaw, when given, is kept (the person turned the map) */
  P_.home = function (yaw) {
    if (this.mode === "route" && this.route) return this.routeView(yaw);
    var self = this, all = this.mode === "all", focus = this.room && this.roomInfo(this.room), tall = !(this.W > this.H * 0.9), tk = this.tk;
    var view = {
      yaw: yaw != null ? yaw : this.yawFor(all ? "all" : "floor", tall), pitch: this.pitchFor(all ? "all" : focus ? "room" : "floor"), zoom: 1, gut: 0
    };
    var items = [], sel = all ? null : this.floorById(this.mode), wallH = tk.wallH;
    if (focus) {
      var f = focus.f;
      items.push({ pts: shifted(focus.room.poly, f.ox.to, f.oy.to), zs: [f.z.to, f.z.to + tk.pinH] });
    } else {
      this.floors.forEach(function (f) {
        if (sel && f !== sel) return;
        items.push({ pts: shifted(f.outline, f.ox.to, f.oy.to), zs: [f.z.to - self.T.slab, f.z.to + tk.pinH] });
      });
    }
    var bb = bboxOfItems(items);
    view.tx = (bb[0] + bb[2]) / 2; view.ty = (bb[1] + bb[3]) / 2; view.tz = (bb[4] + bb[5]) / 2;
    if (!focus && all && this.n > 1 && tk.projection !== "plan") view.gut = this.labelSize()[1] + 14;
    view.fitS = this.fitTo(items, view, focus ? 0.62 : 0.9);
    return view;
  };

  P_.go = function (view, animate, keepYaw) {
    var s = this;
    [[s.pitch, view.pitch], [s.zoom, view.zoom], [s.fitS, view.fitS], [s.tx, view.tx], [s.ty, view.ty], [s.tz, view.tz], [s.gut, view.gut || 0], [s.sx, view.sx || 0], [s.sy, view.sy || 0]].forEach(function (p) { p[0].go(p[1], animate); });
    if (!keepYaw) {
      this.fling = 0; this.panFling = null;
      var y = this.yaw.x + wrap(view.yaw - this.yaw.x);
      this.yaw.go(y, animate);
    }
    this.kick();
  };
  /* move to the current mode's view: a turned map keeps its turn, an untouched one turns too */
  P_.glide = function (animate) {
    var turned = this.turned && animate && this.tk.projection !== "oblique";
    this.go(this.home(turned ? this.yaw.to : null), animate, turned);
  };
  P_.reset = function () {
    this.turned = false; this.fling = 0; this.panFling = null;
    this.go(this.home(), true, false);
    this.syncReset();
  };
  P_.isHome = function () {
    var h = this.home(), plan = this.tk.projection === "oblique";
    var ok = Math.abs(wrap(this.yaw.to - h.yaw)) < 3 * DEG && !this.fling && !this.panFling && Math.abs(this.pitch.to - h.pitch) < 2 * DEG && Math.abs(this.zoom.to - 1) < 0.04;
    if (plan) ok = ok && Math.hypot(this.tx.to - h.tx, this.ty.to - h.ty) < 0.8;
    return ok;
  };
  P_.syncReset = function () { if (this.resetBtn) this.resetBtn.hidden = this.isHome(); };

  /* ---- public: floor, selection, room ----------------------------------------------- */
  P_.setFloor = function (fid) {
    if (fid != null && this.m.order[fid] == null) fid = null;
    if (this.mode === "route") { this.route = null; }
    this.setMode(fid == null ? "all" : fid, true);
    this.kick();
  };
  P_.select = function (id) {
    var e = id != null ? this.entById[id] : null;
    this.sel = e ? e.id : null;
    if (e) {
      if (this.mode !== "all" && this.mode !== "route" && this.mode !== e.floor) this.setMode(e.floor, true);
      this.pulse = reduced() ? 0 : performance.now() + 500;      // after the camera has settled
    } else this.pulse = 0;
    this.kick();
  };
  P_.setStops = function (ids) { this.stops = ids && ids.length ? ids.slice() : null; this.kick(); };
  /* focus a room (or an area); focusRoom(null) lets it go and returns to the view that was showing before the first focus
     (all floors, or that floor), whichever floor the focus itself moved to */
  P_.focusRoom = function (rid) {
    var info = rid && this.roomInfo(rid);
    if (info) {
      if (!this.room) this.roomFrom = this.mode === "route" ? null : this.mode;
      this.room = rid;
      if (this.mode !== info.floor) this.setMode(info.floor, true, true);
      else this.glide(true);
    } else {
      var back = this.room ? this.roomFrom : null;
      this.room = null; this.roomFrom = null;
      if (back && back !== this.mode && (back === "all" || this.m.order[back] != null)) this.setMode(back, true);
      else this.glide(true);
    }
    this.syncReset(); this.kick();
  };
  /* pin the lead ("en" | "zh"); null hands it back to <html data-evk-lead> */
  P_.setLead = function (lead) {
    if (lead === "zh" || lead === "en") { this.leadAuto = false; this.lead = this.lang = lead; this.aria(); this.setTip(null); this.kick(); }
    else { this.leadAuto = true; this.syncLead(); }
  };
  P_.setLang = P_.setLead;
  P_.lock = function (b) { this.locked = !!b; if (b) this.setTip(null); this.kick(); };
  /* keep these insets (px) of the canvas clear: a bottom sheet pans the model up, a side card refits it beside it */
  P_.setPad = function (p) {
    p = p || {};
    var self = this, W = this.W, H = this.H;
    var t = clamp(+p.top || 0, 0, H * 0.7), b = clamp(+p.bottom || 0, 0, H * 0.7), l = clamp(+p.left || 0, 0, W * 0.5), r = clamp(+p.right || 0, 0, W * 0.5);
    var vis = H - t - b; if (vis < 80) { t = 0; b = 0; }                    // a sliver of a band is not worth centring in
    var changed = Math.abs(l - this.pl.to) >= 2 || Math.abs(r - this.pr.to) >= 2;
    this.pt.go(t, true); this.pb.go(b, true); this.pl.go(l, true); this.pr.go(r, true);
    if (changed) { var h = this.home(this.turned ? this.yaw.to : null); this.fitS.go(h.fitS, true); this.sx.go(h.sx, true); this.sy.go(h.sy, true); }
    self.kick();
  };

  /* ---- routes: the floors it crosses, its line, a step at a time ---------------------------
     One floor: that floor. Two or more: stacked on a tall canvas, side by side on a wide one
     (a plan projection always lays floors out flat), the floor you start on first. */
  P_.setRoute = function (plan, animate) {
    animate = animate !== false;
    if (!plan) {
      if (this.mode === "route") this.setMode("all", animate);
      this.route = null; this.kick();
      return;
    }
    var self = this, ids = plan.floors.slice(), used = ids.map(function (id) { return self.floorById(id); }).filter(Boolean);
    var flat = this.tk.projection === "plan";
    var layout = used.length < 2 ? "single" : this.W > this.H * 1.15 ? "side" : "stack";
    this.mode = "route"; this.room = null; this.roomFrom = null; this.sel = plan.to.entity || this.sel;
    this.stacked = layout === "stack" && !flat;
    this.route = { plan: plan, floors: used.map(function (f) { return f.id; }), layout: layout, flat: flat, active: -1, focus: null, t0: performance.now() };
    var ranked = used.slice().sort(function (a, b) { return a.rank - b.rank; });
    var offs = null;
    if (layout === "side" || (layout === "stack" && flat)) offs = this.tiles(used, layout === "side" ? "row" : "col", this.yawFor(layout === "side" ? "routeSide" : "all", false), 7);
    var gap = layout === "stack" && !flat ? this.routeGap(used) : 0;
    this.route.gap = gap;
    this.floors.forEach(function (f) {
      var i = used.indexOf(f);
      if (i < 0) {                                          // not on the way: out of sight, but leaving in a sensible direction
        var below = f.rank < ranked[0].rank, mid = f.rank < ranked[ranked.length - 1].rank;
        self.place(f, below ? -gap || -17 : mid ? (gap || 17) / 2 : (gap || 17) * 2, 0, 0, 0, animate);
      } else if (offs) self.place(f, 0, 1, offs[i][1], offs[i][2], animate);
      else { var zz = ranked.indexOf(f) * gap; self.place(f, zz, 1, self.leanX(zz, self.pitchFor("routeStack")), 0, animate); }
    });
    this.turned = false;
    this.go(this.home(), animate, false);
    this.syncReset();
  };
  P_.routeGap = function (used) {
    var g = this.gapFor(used, this.yawFor("all", false), this.pitchFor("routeStack"), 3);
    if (this.tk.projection === "exploded") g *= 1.2;
    return Math.max(g, this.tk.wallH * 6);
  };
  /* show step i (null / -1: the whole route): that step's line is drawn strong and the camera frames
     it; the stairs step and the overview frame every floor on the way */
  P_.routeStep = function (i, animate) {
    var R = this.route;
    if (!R) return;
    if (i == null) i = -1;
    R.active = i; R.focus = null;
    var st = R.plan.steps[i];
    if (st && st.kind === "walk") { var sg = R.plan.segs[st.seg]; R.focus = { floor: sg.floor, pts: sg.pts }; }
    else if (st && st.kind === "arrive") {
      var info = R.plan.to.room ? this.roomInfo(R.plan.to.room) : null;       // a walled room is framed whole; a booth in an area or on an open floor is framed by itself
      R.focus = info && !info.room.area ? { floor: info.floor, pts: info.room.poly } : { floor: R.plan.to.floor, pts: [R.plan.to.at] };
    }
    var self = this, soft = animate !== false;
    R.floors.forEach(function (id) {                         // the floor in focus stands alone; the other fades back
      var f = self.floorById(id), a = R.focus && R.layout !== "single" && f.id !== R.focus.floor ? self.T.ghost : 1;
      f.alpha.go(a, soft);
    });
    this.turned = false;
    this.go(this.home(), soft, false);
    this.syncReset(); this.kick();
  };
  P_.routeView = function (yaw) {
    var R = this.route, self = this, side = R.layout === "side", single = R.layout === "single", tk = this.tk;
    var view = {
      yaw: yaw != null ? yaw : side ? this.yawFor("routeSide", false) : this.W > this.H * 0.9 ? this.yawFor("all", false) : single ? this.yawFor("floor", true) : this.yawFor("all", false),
      pitch: this.pitchFor(side ? "routeSide" : single ? "routeSingle" : "routeStack"), zoom: 1, gut: 0
    };
    var items = [];
    if (R.focus) {
      var f = this.floorById(R.focus.floor);
      items.push({ pts: grown(shifted(R.focus.pts, f.ox.to, f.oy.to), 3.5), zs: [f.z.to, f.z.to + tk.pinH] });
    } else {
      R.floors.forEach(function (id) {
        var fl = self.floorById(id);
        items.push({ pts: shifted(fl.outline, fl.ox.to, fl.oy.to), zs: [fl.z.to - self.T.slab, fl.z.to + tk.pinH] });
      });
    }
    var bb = bboxOfItems(items);
    view.tx = (bb[0] + bb[2]) / 2; view.ty = (bb[1] + bb[3]) / 2; view.tz = (bb[4] + bb[5]) / 2;
    if (!side && !single && !R.flat && !R.focus) view.gut = this.labelSize()[1] + 14;
    view.fitS = this.fitTo(items, view, R.focus ? 0.82 : 0.9);
    return view;
  };
  /* room plates, icons and the entrance: full without a route, half in its overview, faint during a step */
  P_.detail = function () { return !this.route ? 1 : this.route.active >= 0 ? this.T.detailStep : this.T.detail; };
  P_.usesConnector = function (f, bl) {
    var R = this.route;
    if (!R || !R.plan.hops || !bl.b.key) return false;
    return R.plan.hops.some(function (h) { return h.key === bl.b.key && (h.from === f.id || h.to === f.id); });
  };

  /* ---- the arrival: the model turns in and the floors settle into place, once -------------
     Only the current values move, so the springs still end wherever the view is meant to be. */
  P_.intro = function () {
    var self = this;
    if (this.tk.projection !== "oblique") { this.yaw.x -= 40 * DEG; this.yaw.mult = 2; }       // 原站: 1.1 s instead of 0.55 s for 1.4 s
    this.floors.forEach(function (f, i) { f.z.x -= 6 + 4 * i; f.alpha.x = 0; });
    this.introTimer = setTimeout(function () { self.yaw.mult = 1; }, 1400);
  };

  /* ---- the frame loop: nothing is drawn while nothing moves -------------------------------- */
  P_.kick = function () {
    if (this.frame || this.dead) return;
    var self = this;
    this.frame = requestAnimationFrame(function (t) { self.tick(t); });
  };
  P_.tick = function (now) {
    this.frame = 0;
    if (this.dead) return;
    var dt = this.last ? clamp((now - this.last) / 1000, 0, 0.05) : 1 / 60;
    this.last = now;
    var moving = false, i;
    if (this.fling) {
      this.yaw.x += this.fling * dt; this.yaw.to = this.yaw.x;
      this.fling *= Math.pow(this.T.decel, dt * 1000);
      if (Math.abs(this.fling) < 0.02) { this.fling = 0; this.syncReset(); } else moving = true;
    } else if (this.yaw.step(dt)) moving = true;
    if (this.panFling) {
      var pf = this.panFling, kk = Math.max(this.cam ? this.cam.s : 1, 1e-3);
      this.tx.x -= pf.x * dt / kk; this.tx.to = this.tx.x;
      this.ty.x -= pf.y * dt / (kk * Math.max(this.cam.sp, 0.2)); this.ty.to = this.ty.x;
      var dec = Math.pow(this.T.decel, dt * 1000); pf.x *= dec; pf.y *= dec;
      if (Math.hypot(pf.x, pf.y) < 8) { this.panFling = null; this.syncReset(); } else moving = true;
    }
    for (i = 0; i < this.springs.length; i++) if (this.springs[i].step(dt)) moving = true;
    for (i = 0; i < this.floors.length; i++) {
      var fl = this.floors[i];
      if (fl.z.step(dt)) moving = true;
      if (fl.ox.step(dt)) moving = true;
      if (fl.oy.step(dt)) moving = true;
      if (fl.alpha.step(dt)) moving = true;
    }
    var pulsing = this.pulse && now < this.pulse + this.T.pulseCount * this.T.pulseMs + 200;
    if (this.pulse && !pulsing) this.pulse = 0;
    this.draw(now);
    var flowing = this.route && !reduced();                    // the route's dashes walk toward the destination
    if ((moving || pulsing || flowing) && this.visible) { this.last = now; this.kick(); } else this.last = 0;
  };

  /* ---- drawing -------------------------------------------------------------------------------- */
  /* a polygon in the current material; `holes` (rings of screen points) are cut out of it, fill and edge alike */
  P_.paint = function (q, spec, holes) {
    var g = this.g, L = this.look, off = spec.ink ? L.ji : L.jf, cut = holes && holes.length;
    g.globalCompositeOperation = spec.op || L.op;
    poly(g, q, off[0], off[1]);
    if (cut) holes.forEach(function (h) { ring(g, h, off[0], off[1]); });
    if (spec.f) { g.fillStyle = spec.f; if (cut) g.fill("evenodd"); else g.fill(); }
    if (spec.s) {
      var lw = this.lw;
      g.lineWidth = spec.w * lw; g.strokeStyle = spec.s; g.lineJoin = "round";
      if (spec.dash) { g.setLineDash(spec.dash.map(function (d) { return d * lw; })); g.lineCap = spec.dash[0] < 2 ? "round" : "butt"; }
      g.stroke();
      if (spec.dash) { g.setLineDash([]); g.lineCap = "butt"; }
    }
  };

  P_.draw = function (now) {
    var g = this.g, self = this, L = this.look;
    this.camera();
    g.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    g.globalAlpha = 1; g.globalCompositeOperation = "source-over"; g.setLineDash([]); g.lineCap = "butt"; g.lineJoin = "miter";
    g.clearRect(0, 0, this.W, this.H);
    if (L.ground) { g.fillStyle = L.ground; g.fillRect(0, 0, this.W, this.H); }
    this.hits = []; this.floorHits = [];
    var order = this.floors.slice().sort(function (a, b) { return a.z.x - b.z.x; });
    order.forEach(function (f) {
      var a = clamp(f.alpha.x, 0, 1);
      if (a < 0.01) return;
      g.globalAlpha = a;
      self.drawFloor(f, now);
      self.links.forEach(function (l) { if (l.lo === f) self.drawLink(l); });
    });
    g.globalAlpha = 1;
    if (this.route) this.drawRouteOver(now);
    if ((this.mode === "all" && this.n > 1) || (this.route && this.route.layout !== "single" && !this.route.focus)) this.drawFloorLabels();
  };

  P_.drawFloor = function (f, now) {
    var g = this.g, L = this.look, self = this, z0 = f.z.x, ox = f.ox.x, oy = f.oy.x, tk = this.tk, T = this.T;
    var wallH = tk.wallH, blockH = this.blockH();
    var P = function (p, z) { return self.P(p[0] + ox, p[1] + oy, z0 + z); };
    var kc = this.P(this.cx + ox, this.cy + oy, z0)[3];
    this.lw = clamp(kc / 9, 0.7, 1.6);                                  // line weight follows the scale a little
    var overview = this.mode === "all" || (this.route && !this.route.focus);
    g.globalCompositeOperation = L.op;

    /* slab: the near edges, then the top */
    f.slabSides.forEach(function (s) {
      var face = self.facing(s[4], s[5]);
      if (face[0] <= 0.01) return;
      self.paint([P([s[0], s[1]], s[6]), P([s[2], s[3]], s[6]), P([s[2], s[3]], s[7]), P([s[0], s[1]], s[7])], L.slabSide(self.lightS(face)));
    });
    var top = f.outline.map(function (p) { return P(p, 0); });
    var holes = f.voids.map(function (v) { return v.poly.map(function (p) { return P(p, 0); }); });       // voids: the slab is cut away there
    this.paint(top, L.slabTop, holes);
    var lower = this.floors[f.rank - 1], through = !!lower && this.stacked && lower.alpha.x > 0.3;   // is the floor below on show under the opening?
    f.voids.forEach(function (v, vi) {
      if (through) self.drawShaft(f, v, P, holes[vi], lower);           // a well down to the floor below, seen through the cut
      else {
        v.rim.forEach(function (s) {                                    // the cut edge of the slab, on the far side of the opening
          var face = self.facing(-s[4], -s[5]);
          if (face[0] <= 0.01) return;
          self.paint([P([s[0], s[1]], s[6]), P([s[2], s[3]], s[6]), P([s[2], s[3]], s[7]), P([s[0], s[1]], s[7])], L.slabSide(self.lightS(face)));
        });
        self.drawVoidCross(v, P, holes[vi]);                            // single floor / plan / side by side: nothing below to show, so the architect's X
      }
    });
    if (L.grid) this.drawGrid(f, P, top, holes);
    var hit = null;
    if (f.alpha.x > 0.5) { hit = { floor: f.id, pts: top, holes: holes, rooms: [] }; this.floorHits.push(hit); }

    var edgeIn = tk.wallT / 2 + 0.22;
    f.rooms.forEach(function (r) {
      var q = r.poly.map(function (p) { return P(p, 0.01); });
      if (r.id === self.room) {                                         // the chosen room: its tint, then its edge just inside the walls
        self.paint(q, L.roomSelFill);
        self.paint(inset(r.poly, edgeIn).map(function (p) { return P(p, 0.012); }), L.roomSelEdge);
      } else self.paint(q, L.room);
      if (hit) hit.rooms.push({ id: r.id, pts: q });
    });
    f.areas.forEach(function (a) {                                      // open areas: floor patches, no walls; holes are cut out and both rings are outlined
      var q = a.poly.map(function (p) { return P(p, 0.01); }), qh = (a.holes || []).map(function (h) { return h.map(function (p) { return P(p, 0.01); }); });
      self.paint(q, a.id === self.room ? L.roomSel : L.area(a.kind), qh);
      if (hit) hit.rooms.push({ id: a.id, pts: q, holes: qh });
    });
    var detail = this.detail(), a0 = g.globalAlpha;
    if (f.entrance) { g.globalAlpha = a0 * detail; this.drawArrow(f.entrance, P); g.globalAlpha = a0; }

    if (L.shadows) this.drawShadows(f, P);

    /* solids: the sides far to near, then the tops */
    var faces = [], tops = [];
    f.walls.forEach(function (w) {
      w.faces.forEach(function (fc) {
        var face = self.facing(fc[2], fc[3]);
        if (face[0] <= 0.005) return;
        var q = [P(fc[0], 0), P(fc[1], 0), P(fc[1], wallH), P(fc[0], wallH)];
        faces.push({ q: q, d: (q[0][2] + q[1][2] + q[2][2] + q[3][2]) / 4, spec: L.wallFace(self.lightS(face)) });
      });
      var t = w.top.map(function (p) { return P(p, wallH); });
      tops.push({ q: t, d: (t[0][2] + t[2][2]) / 2, spec: L.wallCap });
    });
    var railH = clamp(wallH * 0.8, 0.45, 1.05);
    f.voids.forEach(function (v) {                                       // a rail panel is seen from both sides, so every piece is drawn
      v.segs.forEach(function (sg) {
        var q = [P(sg.a, 0), P(sg.b, 0), P(sg.b, railH), P(sg.a, railH)];
        faces.push({ q: q, d: (q[0][2] + q[1][2] + q[2][2] + q[3][2]) / 4, spec: L.rail });
      });
    });
    f.blocks.forEach(function (bl) {
      bl.sides.forEach(function (s) {
        var face = self.facing(s[4], s[5]);
        if (face[0] <= 0.005) return;
        var q = [P([s[0], s[1]], 0), P([s[2], s[3]], 0), P([s[2], s[3]], blockH), P([s[0], s[1]], blockH)];
        faces.push({ q: q, d: (q[0][2] + q[1][2] + q[2][2] + q[3][2]) / 4, spec: L.blockFace(self.lightS(face)) });
      });
      var t = bl.poly.map(function (p) { return P(p, blockH); }), d = 0;
      t.forEach(function (p) { d += p[2]; });
      tops.push({ q: t, d: d / t.length, spec: L.blockTop, block: true });
    });
    faces.sort(function (a, b) { return a.d - b.d; });
    faces.forEach(function (fc) { self.paint(fc.q, fc.spec); });
    tops.sort(function (a, b) { return a.d - b.d; });
    tops.forEach(function (t) { self.paint(t.q, t.spec); if (t.block && L.hatch) self.hatch(t.q); });
    g.globalCompositeOperation = "source-over";

    /* things that face the viewer: icons, room plates, labels, tokens. Collected, culled, then drawn far to near. */
    var boards = [], keep = this.route ? [this.route.plan.from.room, this.route.plan.to.room] : [];
    function faded(a, draw) { return a >= 0.999 ? draw : function () { var k = g.globalAlpha; g.globalAlpha = k * a; draw(); g.globalAlpha = k; }; }
    f.blocks.forEach(function (bl) {
      var p = P(bl.c, blockH + 0.05), a = self.usesConnector(f, bl) ? 1 : detail, glyph = GLYPH[bl.kind];
      if (glyph) boards.push({ d: p[2], prio: 5, draw: faded(a, function () { self.drawIcon(bl, glyph, p); }), obs: function () { var px = self.iconPx(bl, p) / 2; return [p[0] - px, p[1] - px, p[0] + px, p[1] + px]; } });
      if (bl.label && p[3] >= 12 && !overview) boards.push({ d: p[2] - 1, prio: 2, label: true, draw: faded(a * 0.85, function () { return self.drawBlockLabel(bl, p); }), measure: function () { return self.measureBlockLabel(bl, p); } });
    });
    f.voids.forEach(function (v) {
      if (!v.label) return;
      var p = P(v.c, 0.05);
      if (p[3] >= 12 && !overview) boards.push({ d: p[2] - 1, prio: 2, label: true, draw: faded(detail * 0.85, function () { return self.drawBlockLabel(v, p); }), measure: function () { return self.measureBlockLabel(v, p); } });
    });
    f.areas.forEach(function (ar) {
      var sel = ar.id === self.room, a = keep.indexOf(ar.id) >= 0 ? 1 : detail, plate = ar.plate ? P(ar.c, 1.7) : null, p = plate || P(ar.labelAt || ar.c, 0.05);
      if (plate) boards.push({ d: plate[2] - 0.5, prio: sel ? 9 : 6, draw: faded(a, function () { self.drawSign(ar, plate); }),
        obs: function () { var q = self.signGeom(ar, plate); return [q.x, q.y, q.x + q.w, q.y + q.h]; } });
      if (p[3] >= 11 && !overview) boards.push({ d: p[2] - 0.6, prio: sel ? 9 : 3, label: true, force: sel, draw: faded(a * 0.9, function () { return self.drawRoomName(ar, p, !plate); }), measure: function () { return self.measureRoomName(ar, p, !plate); } });
    });
    f.rooms.forEach(function (r) {
      if (!r.sign) return;
      var p = P(r.sign, 1.7), a = keep.indexOf(r.id) >= 0 ? 1 : detail, sel = r.id === self.room;
      boards.push({ d: p[2] - 0.5, prio: sel ? 9 : 6, draw: faded(a, function () { self.drawSign(r, p); }),
        obs: function () { var q = self.signGeom(r, p); return [q.x, q.y, q.x + q.w, q.y + q.h]; } });
      if (p[3] >= 11 && !overview) boards.push({ d: p[2] - 0.6, prio: 3, label: true, draw: faded(a * 0.9, function () { return self.drawRoomName(r, p); }), measure: function () { return self.measureRoomName(r, p); } });
    });
    if (!this.route && f.entrance) {
      var m = f.entrance, p = P([m.at[0] + m.dir[0] * 3.2, m.at[1] + m.dir[1] * 3.2], 0.3);
      boards.push({ d: p[2], prio: 7, draw: function () { self.drawLabel(m.name.en, m.name.cn, p, L.route); } });
    }
    this.ents.forEach(function (e) {
      if (e.floor !== f.id) return;
      var base = P(e.at, 0), head = P(e.at, tk.pinH), isSel = e.id === self.sel;
      boards.push({ d: head[2] + (isSel ? 50 : 0), prio: 10, token: true, draw: function () { self.drawToken(e, base, head, now, f); },
        obs: function () { var d = self.badgeSize(head[3], isSel); return [head[0] - d / 2, head[1] - d, head[0] + d / 2, base[1]]; } });
      if (isSel || e.id === self.hoverId || head[3] >= 13) {
        var ta = self.tokenAlpha(e);
        boards.push({ d: head[2] + (isSel ? 50 : 0) + 0.1, prio: isSel ? 9.5 : e.id === self.hoverId ? 9 : 1, label: true, force: isSel || e.id === self.hoverId,
          measure: function () { return self.measureTokenName(e, base, head[3]); },
          draw: faded(ta, function () { self.drawTokenName(e, base, head[3]); }) });
      }
    });
    boards.sort(function (a, b) { return a.d - b.d; });
    this.cull(boards).forEach(function (bd) { bd.draw(); });
  };

  /* label collision culling: signs, icons and tokens are obstacles that always draw; a label is kept when it clears all of
     them and every label of higher priority already kept (chosen and hovered ones are forced) */
  P_.cull = function (boards) {
    var rects = [], keep = {};
    boards.forEach(function (b) { if (b.obs) { var r = b.obs(); if (r) rects.push(r); } });
    var cand = boards.filter(function (b) { return b.label; }).sort(function (a, b) { return b.prio - a.prio; });
    cand.forEach(function (b) {
      var r = b.measure();
      if (!r) return;
      if (!b.force) for (var i = 0; i < rects.length; i++) {
        var o = rects[i];
        if (r[0] < o[2] && r[2] > o[0] && r[1] < o[3] && r[3] > o[1]) return;
      }
      rects.push(r); keep[boards.indexOf(b)] = 1;
    });
    return boards.filter(function (b, i) { return !b.label || keep[i]; });
  };

  /* blueprint: a drafting grid on the floor, 1 m and 5 m */
  P_.drawGrid = function (f, P, top, holes) {
    var g = this.g, k = this.P(this.cx + f.ox.x, this.cy + f.oy.x, f.z.x)[3], L = this.look, b = f.bbox;
    if (k < 4) return;
    g.save(); poly(g, top); (holes || []).forEach(function (h) { ring(g, h, 0, 0); }); g.clip("evenodd");
    g.lineCap = "butt";
    function lines(step, alpha, w) {
      g.beginPath();
      for (var x = Math.ceil(b[0] / step) * step; x <= b[2]; x += step) { var a = P([x, b[1]], 0.003), c = P([x, b[3]], 0.003); g.moveTo(a[0], a[1]); g.lineTo(c[0], c[1]); }
      for (var y = Math.ceil(b[1] / step) * step; y <= b[3]; y += step) { var a2 = P([b[0], y], 0.003), c2 = P([b[2], y], 0.003); g.moveTo(a2[0], a2[1]); g.lineTo(c2[0], c2[1]); }
      g.lineWidth = w; g.strokeStyle = css(L.ink, 1, alpha); g.stroke();
    }
    if (k >= 7) lines(1, 0.07, 0.6);
    lines(5, 0.16, 0.7);
    g.restore();
  };
  /* line / blueprint: solid tops are hatched so "closed" still reads without a fill */
  P_.hatch = function (q) {
    var g = this.g, x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    q.forEach(function (p) { x0 = Math.min(x0, p[0]); y0 = Math.min(y0, p[1]); x1 = Math.max(x1, p[0]); y1 = Math.max(y1, p[1]); });
    if (x1 - x0 < 8 || y1 - y0 < 5) return;
    g.save(); poly(g, q); g.clip();
    g.beginPath();
    var step = 5;
    for (var x = x0 - (y1 - y0); x < x1; x += step) { g.moveTo(x, y1); g.lineTo(x + (y1 - y0), y0); }
    g.lineWidth = 0.7; g.strokeStyle = css(this.look.ink, 1, 0.38); g.stroke();
    g.restore();
  };
  /* clay: a soft contact shadow beside every wall and block, away from the light */
  P_.drawShadows = function (f, P) {
    var g = this.g, L = this.look, k = this.cam.s, c = this.cam, sx = this.tk.light === "right" ? -1 : 1;
    var dir = this.tk.light === "top" ? [0, 0] : [c.xp[0] * 0.45 * sx, c.xp[1] * 0.45 * sx];
    g.save(); g.lineJoin = "round";
    function foot(pts) {
      var q = pts.map(function (p) { return P([p[0] + dir[0], p[1] + dir[1]], 0.004); });
      poly(g, q);
    }
    [[0.9, 0.05], [0.45, 0.06]].forEach(function (s) {
      g.fillStyle = g.strokeStyle = css(L.ink, 1, s[1]); g.lineWidth = s[0] * k * 0.8;
      f.walls.forEach(function (w) { foot(w.top); g.fill(); g.stroke(); });
      f.blocks.forEach(function (bl) { foot(bl.poly); g.fill(); g.stroke(); });
    });
    g.restore();
  };

  /* an opening whose floor below is not on show (single floor, plan, side by side): the architect's X over a box */
  P_.drawVoidCross = function (v, P, ringPts) {
    var g = this.g, n = v.poly.length;
    g.save(); g.globalCompositeOperation = "source-over";
    if (ringPts) { poly(g, ringPts); g.fillStyle = css(this.look.ink, 1, 0.07); g.fill(); }        // a little weight, so the cut reads as a drop and not as bare ground
    if (n < 4) { g.restore(); return; }
    g.lineWidth = 1; g.strokeStyle = this.look.cross; g.setLineDash([5, 4]);
    g.beginPath();
    for (var i = 0; i < Math.floor(n / 2); i++) { var a = P(v.poly[i], 0.02), b = P(v.poly[i + Math.ceil(n / 2)], 0.02); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); }
    g.stroke(); g.restore();
  };

  /* an opening seen with the floor below on show: a well. Everything is clipped to the cut in the slab, so only what the opening
     lets the eye through is painted: the far walls running down (a storey, `shaft` × wall height), the floor at the bottom in a
     darker tone, and a dot in the colour of each booth that stands right under the opening. The floor below is also drawn on its
     own, in its place in the stack; this is the view straight down the shaft. */
  P_.drawShaft = function (f, v, P, ringPts, lower) {
    var g = this.g, L = this.look, self = this, D = clamp(this.T.shaft * this.tk.wallH, 1.2, 5);
    g.save();
    poly(g, ringPts); g.clip();
    this.paint(v.poly.map(function (p) { return P(p, -D); }), L.well);
    if (L.hatch) this.hatch(v.poly.map(function (p) { return P(p, -D); }));
    v.rim.forEach(function (s) {                                          // the far walls: pale wall below the slab's own (inked) edge
      var face = self.facing(-s[4], -s[5]), sl = self.T.slab, sh = self.lightS(face);
      if (face[0] <= 0.005) return;
      self.paint([P([s[0], s[1]], -sl), P([s[2], s[3]], -sl), P([s[2], s[3]], -D), P([s[0], s[1]], -D)], L.wallFace(sh));
      self.paint([P([s[0], s[1]], 0), P([s[2], s[3]], 0), P([s[2], s[3]], -sl), P([s[0], s[1]], -sl)], L.slabSide(sh));
    });
    this.ents.forEach(function (e) {
      if (e.floor !== lower.id || !inside(v.poly, e.at[0], e.at[1])) return;
      var p = P(e.at, -D), r = clamp(0.4 * p[3], 3, 8);
      g.beginPath(); g.ellipse(p[0], p[1], rr(r), rr(r * Math.max(self.cam.sp, 0.3)), 0, 0, TAU);
      g.fillStyle = css(e.rgb, 1, 0.9); g.fill(); g.lineWidth = 1; g.strokeStyle = css(L.halo, 1, 0.8); g.stroke();
    });
    g.restore();
  };

  /* the entrance: a big flat arrow in the accent, poking through the wall gap */
  P_.drawArrow = function (m, P) {
    var g = this.g, dx = m.dir[0], dy = m.dir[1], nx = -dy, ny = dx, Lh = 3.4, Wd = Math.min(1.0, m.width * 0.3), H = Wd * 1.7;
    var ox = m.at[0] - dx * 3.4, oy = m.at[1] - dy * 3.4;           // the tail starts outside the door (原站: L 3.4, W 1.0, H 1.7, head 1.9)
    var pts = [[0, -Wd], [Lh, -Wd], [Lh, -H], [Lh + 1.9, 0], [Lh, H], [Lh, Wd], [0, Wd]].map(function (p) { return P([ox + dx * p[0] + nx * p[1], oy + dy * p[0] + ny * p[1]], 0.02); });
    var L = this.look;
    poly(g, pts, L.jf[0], L.jf[1]);
    if (L.mat === "line" || L.mat === "blueprint") { g.lineWidth = 1.6; g.strokeStyle = css(L.route); g.lineJoin = "round"; g.stroke(); g.fillStyle = css(L.route, 1, 0.22); g.fill(); }
    else { g.fillStyle = css(L.route); g.fill(); }
  };

  /* stairs / lift / toilets: the icon plate in the venue's shape language */
  P_.iconPx = function (bl, p) {
    var px = clamp(Math.min(bl.size * 0.62, 1.7) * p[3], 11, 26);
    return this.mode === "all" ? Math.min(px, 15) : px;
  };
  P_.drawIcon = function (bl, glyph, p) {
    var g = this.g, L = this.look, tk = this.tk, px = this.iconPx(bl, p), s = px / 48;
    g.save(); g.translate(p[0] - px / 2, p[1] - px / 2); g.scale(s, s);
    var frame = framePath(tk.chamfer, tk.radius);
    g.fillStyle = css(L.plate); g.fill(frame);
    g.lineWidth = 2.5; g.strokeStyle = css(L.ink); g.stroke(frame);
    g.lineWidth = 3.4; g.lineJoin = "miter";
    if (glyph.stroke) g.stroke(path(glyph.stroke));
    if (glyph.fill) { g.fillStyle = css(L.ink); g.fill(path(glyph.fill)); }
    g.restore();
  };

  /* text with a halo: stroke first, fill second, round joins (wrong order or miter joins spike on W, M, N) */
  P_.haloText = function (txt, x, y, color, halo, w) {
    var g = this.g;
    g.lineJoin = "round"; g.lineWidth = w || 3.5; g.strokeStyle = halo; g.strokeText(txt, x, y);
    g.fillStyle = color; g.fillText(txt, x, y);
  };
  /* the lines of a label, the lead language first. A single line when the other language is missing or the same text. */
  P_.labelLines = function (en, cn) {
    var lat = this.tk.labelCase === "upper" ? (en || "").toUpperCase() : en || "", zh = cn || "";
    if (!zh || zh === en) return [{ t: lat, cjk: false }];
    if (!en) return [{ t: zh, cjk: true }];
    return this.lead === "zh" ? [{ t: zh, cjk: true }, { t: lat, cjk: false }] : [{ t: lat, cjk: false }, { t: zh, cjk: true }];
  };
  /* a bilingual halo label; (x, y) is the top centre. The primary line (the lead language) is first, larger and bolder; the
     secondary follows at ~0.82 of its size, lighter. Returns its screen rect. */
  P_.drawLabel = function (en, cn, p, color, dry) {
    var g = this.g, L = this.look, size = clamp(0.5 * p[3], this.T.labelMin, this.T.labelMax), small = Math.max(this.T.labelMin - 1, Math.round(size * 0.82));
    var lines = this.labelLines(en, cn), y = p[1] + 4, w = 0, self = this;
    g.textAlign = "center"; g.textBaseline = "top";
    lines.forEach(function (l, i) {
      var sz = i === 0 ? size : small;
      g.font = l.cjk ? self.font("cjk", i === 0 ? 700 : 500, sz) : self.font("label", i === 0 ? 800 : 600, sz);
      w = Math.max(w, g.measureText(l.t).width);
      if (!dry) self.haloText(l.t, p[0], y + (i ? size + 2 : 0), css(color || L.route, 1, i ? 0.82 : 1), css(L.halo));
    });
    return [p[0] - w / 2 - 2, y - 2, p[0] + w / 2 + 2, y + size + (lines.length > 1 ? 2 + small : 0) + 4];
  };
  P_.signGeom = function (r, p) {
    var g = this.g, tk = this.tk, h = clamp(1.5 * p[3], 13, 34);
    if (this.mode === "all") h = Math.min(h, 16);
    g.font = this.font("num", 700, Math.round(h * 0.62));
    var tw = g.measureText(r.label).width, w = Math.max(h * 1.1, tw + h * 0.6);
    return { h: h, w: w, x: p[0] - w / 2, y: p[1] - h, ch: tk.chamfer ? Math.min(tk.chamfer * h / 24, h * 0.3) : 0, rad: tk.radius ? Math.min(tk.radius * h / 24, h / 2) : 0 };
  };
  P_.drawSign = function (r, p) {                                // the room's number, standing at its door
    var g = this.g, L = this.look, q = this.signGeom(r, p), sel = r.id === this.room;
    g.save();
    plateRect(g, q.x + 0.6, q.y + 1.2, q.w, q.h, q.ch, q.rad); g.fillStyle = css(L.ink, 1, 0.16); g.fill();
    plateRect(g, q.x, q.y, q.w, q.h, q.ch, q.rad); g.fillStyle = css(L.plate, 1, 0.97); g.fill();
    g.lineWidth = sel ? 2.2 : 1.1; g.strokeStyle = sel ? css(L.route) : css(L.ink); g.stroke();
    g.fillStyle = sel ? css(L.route) : css(L.text); g.textAlign = "center"; g.textBaseline = "middle";
    g.fillText(r.label, p[0], q.y + q.h * 0.54);
    g.restore();
  };
  /* a room's name hangs 3 px under its plate; an area has no plate unless labelled, so (bare) its name sits on its centre.
     An area's English name is a common noun in the directions ("west corridor"): the map capitalises its first letter. */
  P_.measureRoomName = function (r, p, bare) {
    var q = [p[0], p[1] + (bare ? -8 : 3), p[2], p[3]];
    return this.drawLabel(r.area ? cap1(r.name.en) : r.name.en, r.name.cn, q, null, true);
  };
  P_.drawRoomName = function (r, p, bare) {
    var q = [p[0], p[1] + (bare ? -8 : 3), p[2], p[3]];
    this.drawLabel(r.area ? cap1(r.name.en) : r.name.en, r.name.cn, q, this.look.text);
  };
  P_.measureBlockLabel = function (bl, p) { return this.drawLabel(bl.label.en, bl.label.cn, [p[0], p[1] - 6, p[2], p[3]], null, true); };
  P_.drawBlockLabel = function (bl, p) { this.drawLabel(bl.label.en, bl.label.cn, [p[0], p[1] - 6, p[2], p[3]], this.look.text); };

  P_.badgeSize = function (k, isTarget) {
    var d = clamp(2.1 * k, 16, 46);
    if (this.mode === "all") d = Math.min(d, 22);
    return isTarget ? Math.max(d * 1.3, 26) : d;
  };
  P_.tokenAlpha = function (e) {                               // the focus ladder: chosen 1 > a themed route's stops > the rest
    if (!this.sel || e.id === this.sel) return 1;
    var stop = this.stops ? this.stops.indexOf(e.id) : -1, stepping = this.route && this.route.active >= 0, T = this.T;
    return stop >= 0 ? (stepping ? T.dimStopStep : T.dimStop) : (stepping ? this.tk.dim * T.dimStepRatio : this.tk.dim);
  };
  P_.tokenName = function (e) { return this.lead === "zh" ? e.name.cn : (this.tk.labelCase === "upper" ? e.short.toUpperCase() : e.short); };
  P_.nameFont = function (k) { var size = clamp(0.5 * k, this.T.labelMin, this.T.labelMax); return [this.font(this.lead === "zh" ? "cjk" : "label", 700, size), size]; };
  P_.measureTokenName = function (e, base, k) {
    var g = this.g, f = this.nameFont(k), y = base[1] + (this.tk.token === "dot" ? 7 : 3);
    g.font = f[0];
    var w = g.measureText(this.tokenName(e)).width;
    return [base[0] - w / 2 - 2, y - 1, base[0] + w / 2 + 2, y + f[1] + 2];
  };
  P_.drawTokenName = function (e, base, k) {
    var g = this.g, f = this.nameFont(k), L = this.look;
    g.font = f[0]; g.textAlign = "center"; g.textBaseline = "top";
    this.haloText(this.tokenName(e), base[0], base[1] + (this.tk.token === "dot" ? 7 : 3), css(L.text), css(L.halo));
  };
  P_.drawToken = function (e, base, head, now, floor) {
    var g = this.g, L = this.look, T = this.T, tk = this.tk;
    var isSel = e.id === this.sel, isHover = e.id === this.hoverId && !isSel, stop = this.stops ? this.stops.indexOf(e.id) : -1;
    var a0 = g.globalAlpha;
    g.globalAlpha = a0 * this.tokenAlpha(e);
    var d = this.badgeSize(head[3], isSel) * (isHover ? 1.12 : 1);
    var img = null;
    if (this.opts.image) {
      var im = this.opts.image(e.raw);
      img = imageReady(im);
      if (im && !img && !im.__evk) { im.__evk = 1; var self = this; im.addEventListener("load", function () { self.kick(); }); }
    }
    var b = {
      g: g, L: L, ent: e, img: img, base: base, head: head, d: d, sel: isSel, sp: this.cam.sp, fNum: tk.fNum, chamfer: tk.chamfer, radius: tk.radius,
      pulseR: 0, pulseA: 0
    };
    if (isSel && this.pulse && now > this.pulse) {
      var t = ((now - this.pulse) % T.pulseMs) / T.pulseMs;
      if (now < this.pulse + T.pulseCount * T.pulseMs) { b.pulseR = t * 16; b.pulseA = 0.55 * (1 - t); }
    }
    var hit = TOKENS[tk.token](b);
    if (stop >= 0) {                                             // the stop's number on a themed route
      var tr = Math.max(7.5, d / 2 * 0.42), cx = hit.x + d / 2 * 0.78, cy = hit.y - d / 2 * 0.78;
      g.beginPath(); g.arc(cx, cy, rr(tr), 0, TAU); g.fillStyle = css(isSel ? L.route : L.ink); g.fill();
      g.lineWidth = 1.5; g.strokeStyle = css(L.halo); g.stroke();
      g.fillStyle = css(L.halo); g.font = this.font("num", 800, Math.round(tr * 1.15)); g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(String(stop + 1), cx, cy + 0.5);
    }
    g.globalAlpha = a0;
    if (floor.alpha.x > 0.5) this.hits.push({ id: e.id, room: e.room, x: hit.x, y: hit.y, rad: hit.rad });
  };
  /* a stairwell between two floors of the stack: a faint shaft from the stairs below to the floor above,
     its corners dashed. Exploded: a ghosted centre line and landing marks instead. Drawn after the lower
     floor, so the upper one covers its top. */
  P_.drawLink = function (l) {
    var a = Math.min(l.lo.alpha.x, l.hi.alpha.x);
    if (a < 0.02) return;
    var g = this.g, self = this, L = this.look, inset = 0.35, z0 = l.lo.z.x + this.blockH(), z1 = l.hi.z.x - this.T.slab;
    if (z1 - z0 < 0.5) return;
    function ring(box, z, f) {
      return [[box[0] + inset, box[1] + inset], [box[2] - inset, box[1] + inset], [box[2] - inset, box[3] - inset], [box[0] + inset, box[3] - inset]]
        .map(function (p) { return self.P(p[0] + f.ox.x, p[1] + f.oy.x, z); });
    }
    var bot = ring(l.a, z0, l.lo), top = ring(l.b, z1, l.hi);
    g.save();
    g.globalAlpha = a; g.globalCompositeOperation = "source-over";
    if (this.tk.projection === "exploded") {
      var cb = this.P((l.a[0] + l.a[2]) / 2 + l.lo.ox.x, (l.a[1] + l.a[3]) / 2 + l.lo.oy.x, z0), ct = this.P((l.b[0] + l.b[2]) / 2 + l.hi.ox.x, (l.b[1] + l.b[3]) / 2 + l.hi.oy.x, z1);
      g.setLineDash([2, 5]); g.lineCap = "round"; g.lineWidth = 1.8; g.strokeStyle = css(l.kind === "lift" ? L.climb : L.ink, 1, 0.55);
      g.beginPath(); g.moveTo(cb[0], cb[1]); g.lineTo(ct[0], ct[1]); g.stroke();
      g.setLineDash([]); g.lineWidth = 1; g.strokeStyle = css(L.ink, 1, 0.4); poly(g, top); g.stroke(); poly(g, bot); g.stroke();
      g.restore();
      return;
    }
    var normals = [[0, -1], [1, 0], [0, 1], [-1, 0]];             // north, east, south, west
    g.fillStyle = css(L.ink);
    for (var i = 0; i < 4; i++) {
      if (this.facing(normals[i][0], normals[i][1])[0] <= 0) continue;
      var j = (i + 1) % 4;
      poly(g, [bot[i], bot[j], top[j], top[i]]);
      g.globalAlpha = a * 0.07; g.fill();
    }
    var far = 0;                                                   // the corner behind the shaft, drawn fainter
    for (i = 1; i < 4; i++) if (bot[i][2] < bot[far][2]) far = i;
    g.setLineDash([4, 4]); g.lineWidth = 1.2; g.strokeStyle = css(L.ink);
    for (i = 0; i < 4; i++) {
      g.globalAlpha = a * (i === far ? 0.22 : 0.6);
      g.beginPath(); g.moveTo(bot[i][0], bot[i][1]); g.lineTo(top[i][0], top[i][1]); g.stroke();
    }
    g.restore();
  };

  /* ---- the route, drawn after every floor so a floor above never hides it ------------------- */
  P_.drawRouteOver = function (now) {
    var self = this, R = this.route, g = this.g;
    g.globalCompositeOperation = "source-over";
    R.plan.segs.forEach(function (sg, si) {
      var f = self.floorById(sg.floor);
      if (!f || f.alpha.x < 0.02) return;
      g.globalAlpha = clamp(f.alpha.x, 0, 1);
      self.drawRoute(f, sg, si, now);
    });
    g.globalAlpha = 1;
    (R.plan.hops || []).forEach(function (h) { self.drawConnector(h, now); });
    var boards = [];
    R.floors.forEach(function (id) {
      var f = self.floorById(id);
      if (!f || f.alpha.x < 0.02) return;
      var P = function (p, z) { return self.P(p[0] + f.ox.x, p[1] + f.oy.x, f.z.x + z); }, mine = [];
      self.routeBoards(f, P, mine);
      mine.forEach(function (b) { b.alpha = clamp(f.alpha.x, 0, 1); boards.push(b); });
    });
    boards.sort(function (a, b) { return a.d - b.d; });
    boards.forEach(function (bd) { g.globalAlpha = bd.alpha; bd.draw(); });
    g.globalAlpha = 1;
  };
  /* the walking line on one floor: a halo, the accent line, and light dashes marching along it */
  P_.drawRoute = function (f, sg, si, now) {
    var self = this, R = this.route, g = this.g, L = this.look, st = R.plan.steps[R.active];
    if (sg.pts.length < 2) return;
    var on = !st || st.kind === "stairs" || st.seg === si;
    var q = sg.pts.map(function (p) { return self.P(p[0] + f.ox.x, p[1] + f.oy.x, f.z.x + 0.08); }), k = 0;
    q.forEach(function (p) { k += p[3]; });
    var w = clamp(0.36 * k / q.length, 3, 9);
    g.save(); g.lineJoin = "round"; g.lineCap = "round";
    g.globalAlpha *= on ? 1 : 0.38;
    g.beginPath(); g.moveTo(q[0][0], q[0][1]);
    for (var i = 1; i < q.length; i++) g.lineTo(q[i][0], q[i][1]);
    g.strokeStyle = css(L.halo); g.lineWidth = w + 4; g.stroke();
    g.strokeStyle = css(L.route); g.lineWidth = w; g.stroke();
    if (on) {
      g.setLineDash([w * 0.8, w * 2.4]);
      g.lineDashOffset = reduced() ? 0 : -(now - R.t0) / 28;                 // 原站: about 36 px/s toward the destination
      g.strokeStyle = css(L.dash, 1, 0.92); g.lineWidth = Math.max(1.5, w * 0.42); g.stroke();
    }
    g.restore();
  };
  P_.routeBoards = function (f, P, boards) {
    var R = this.route, plan = R.plan, self = this, L = this.look;
    if (plan.from.floor === f.id && plan.from.kind !== "entity") {
      var at = P(plan.from.at, 0.1);
      boards.push({ d: at[2] + 40, draw: function () { self.drawStart(at); } });
    }
    (plan.hops || []).forEach(function (h) {
      [h.from, h.to].forEach(function (fid, side) {
        if (fid !== f.id) return;
        var pt = side === 0 ? h.a : h.b, ring = P(pt, 0.1);
        boards.push({ d: ring[2] + 35, draw: function () { self.drawLanding(ring); } });
        if (side === 0) {
          var up = self.floorById(h.to).level > f.level, lift = h.kind === "lift", to = self.floorById(h.to), rg = P(h.a, 0.1), rr = clamp(0.5 * rg[3], 6, 12);
          var p = [rg[0], rg[1] + rr * 1.4 * self.cam.sp + 1, rg[2], rg[3]];                  // the label hangs under the landing ring, not through it
          var sh = to.f.short || { en: to.id, cn: to.id };                                       // floors[].short: the same words as the route sentence
          var en = (lift ? (up ? "Lift up to " : "Lift down to ") : up ? "Up to " : "Down to ") + sh.en;
          var cn = (lift ? (up ? "乘电梯上" : "乘电梯下") : up ? "上楼到" : "下楼到") + (/^[A-Za-z0-9]/.test(sh.cn) ? " " : "") + sh.cn;
          boards.push({ d: p[2] + 30, draw: function () { self.drawLabel(en, cn, p, L.climb); } });
        }
      });
    });
  };
  P_.drawLanding = function (p) {
    var g = this.g, L = this.look, r = clamp(0.5 * p[3], 6, 12);
    g.save(); g.beginPath(); g.ellipse(p[0], p[1], rr(r * 1.4), rr(r * 1.4 * this.cam.sp), 0, 0, TAU);
    g.fillStyle = css(L.halo); g.fill(); g.lineWidth = Math.max(2.5, r * 0.35); g.strokeStyle = css(L.climb); g.stroke(); g.restore();
  };
  P_.drawStart = function (p) {
    var g = this.g, L = this.look, r = clamp(0.55 * p[3], 7, 14);
    g.save();
    g.beginPath(); g.ellipse(p[0], p[1], rr(r * 1.7), rr(r * 1.7 * this.cam.sp), 0, 0, TAU); g.fillStyle = css(L.route, 1, 0.16); g.fill();
    g.beginPath(); g.arc(p[0], p[1] - r * 0.2, rr(r * 0.75), 0, TAU); g.fillStyle = css(L.halo); g.fill();
    g.lineWidth = Math.max(2.5, r * 0.4); g.strokeStyle = css(L.route); g.stroke();
    g.restore();
    this.drawLabel("Start", "起点", [p[0], p[1] + r * 0.6, p[2], p[3]], L.route);
  };
  /* between floors: the climb as a dashed line (stacked) or a dashed arc (side by side) in its own colour */
  P_.drawConnector = function (h, now) {
    var R = this.route, fa = this.floorById(h.from), fc = this.floorById(h.to);
    if (!fa || !fc) return;
    var a = Math.min(fa.alpha.x, fc.alpha.x);
    if (a < 0.05) return;
    var pa = this.P(h.a[0] + fa.ox.x, h.a[1] + fa.oy.x, fa.z.x + 0.08), pc = this.P(h.b[0] + fc.ox.x, h.b[1] + fc.oy.x, fc.z.x + 0.08);
    var g = this.g, L = this.look, st = R.plan.steps[R.active], active = R.active < 0 || (st && st.kind === "stairs");
    var mx = (pa[0] + pc[0]) / 2, my = (pa[1] + pc[1]) / 2, d = Math.hypot(pc[0] - pa[0], pc[1] - pa[1]);
    var lift = R.layout !== "stack" || R.flat ? Math.min(d * 0.35, this.H * 0.3) : 0;
    g.save(); g.globalAlpha = clamp(a, 0, 1) * (active ? 1 : 0.45); g.lineCap = "round"; g.setLineDash([6, 6]);
    g.lineDashOffset = reduced() ? 0 : -(now - R.t0) / 40;
    [[css(L.halo), 7], [css(L.climb), 3.5]].forEach(function (s) {
      g.beginPath(); g.moveTo(pa[0], pa[1]); g.quadraticCurveTo(mx, my - lift, pc[0], pc[1]); g.strokeStyle = s[0]; g.lineWidth = s[1]; g.stroke();
    });
    g.restore();
  };

  /* "1F 2F 3F" in the left margin beside each floor's corner (side layouts: above each floor) */
  P_.drawFloorLabels = function () {
    var g = this.g, self = this, L = this.look, lay = this.route ? this.route.layout : null, side = lay === "side" || (this.mode === "all" && this.tk.projection === "plan") || (this.route && this.route.flat);
    var h = this.labelSize()[0];
    g.textBaseline = "middle";
    this.floors.forEach(function (f) {
      if (f.alpha.x < 0.05) return;
      if (self.route && self.route.floors.indexOf(f.id) < 0) return;
      var left = null, topq = null, sx = 0;
      f.outline.forEach(function (p) {
        var q = self.P(p[0] + f.ox.x, p[1] + f.oy.x, f.z.x);
        if (!left || q[0] < left[0]) left = q;
        if (!topq || q[1] < topq[1]) topq = q;
        sx += q[0];
      });
      g.save(); g.globalAlpha = clamp(f.alpha.x, 0, 1);
      g.font = self.font("num", 700, h);
      var tw = g.measureText(f.id).width;
      var x = 8, y = left[1];
      if (side) { x = sx / f.outline.length - tw / 2; y = Math.max(h / 2 + 4, topq[1] - h / 2 - 10); }
      g.textAlign = "left";
      self.haloText(f.id, x, y, css(L.text), css(L.halo), 4);
      g.restore();
    });
  };

  /* ---- picking --------------------------------------------------------------------------------- */
  P_.pick = function (x, y) {
    var pad = this.T.hitPad, i;
    for (i = this.hits.length - 1; i >= 0; i--) {
      var h = this.hits[i];
      if (Math.hypot(x - h.x, y - h.y) <= h.rad + pad) return { entity: h.id, room: h.room };
    }
    for (i = this.floorHits.length - 1; i >= 0; i--) {
      var f = this.floorHits[i];
      if (!inside(f.pts, x, y)) continue;
      if (f.holes && f.holes.some(function (h) { return inside(h, x, y); })) continue;       // an opening: look through it to the floor below
      for (var j = 0; j < f.rooms.length; j++) {
        var rj = f.rooms[j];
        if (inside(rj.pts, x, y) && !(rj.holes && rj.holes.some(function (h) { return inside(h, x, y); }))) return { room: rj.id, floor: f.floor };   // a hole in an area is not the area
      }
      return { floor: f.floor };
    }
    return null;
  };

  /* ---- size -------------------------------------------------------------------------------------- */
  P_.resize = function () {
    var r = this.canvas.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 3);
    var w = Math.max(1, Math.round(r.width)), h = Math.max(1, Math.round(r.height));
    if (w === this.W && h === this.H && dpr === this.dpr) return;
    var cls = w > h * 1.15, flipped = this.cls != null && cls !== this.cls && this.floors && this.floors.length;
    this.cls = cls;
    this.W = w; this.H = h; this.dpr = dpr;
    this.canvas.width = Math.round(w * dpr); this.canvas.height = Math.round(h * dpr);
    if (this.floors && this.floors.length && this.pl && this.applyCap()) { /* the resting yaw changed with the canvas: the floors were laid out again */ }
    if (this.floors && this.floors.length && this.pl) { var hv = this.home(this.turned ? this.yaw.to : null); this.fitS.set(hv.ffitS === undefined ? hv.fitS : hv.fitS); this.sx.set(hv.sx); this.sy.set(hv.sy); }   // keep it framed, without a zoom animation
    if (flipped) this.relayoutSoon();
    this.kick();
  };
  /* the canvas changed shape: does a long building's resting yaw change with it? Then the gap between floors changes too, so lay out again, now. */
  P_.applyCap = function () {
    var cap = this.footprintCap();
    if (cap === this.yawMax) return false;
    this.layoutConstants();                                  // sets yawMax (the same value), the gap and the camera distance
    var plan = this.route && this.route.plan, act = this.route && this.route.active;
    this.turned = false;
    if (plan) { this.setRoute(plan, false); this.routeStep(act, false); }
    else this.setMode(this.mode, false, true);
    return true;
  };
  /* portrait <-> landscape changes how floors are laid out (tiles, a route's side-by-side or stacked): re-lay out once, after the
     browser stops firing resize (the URL bar collapsing and a keyboard are not a flip) */
  P_.relayoutSoon = function () {
    var self = this;
    clearTimeout(this.relayoutTimer);
    this.relayoutTimer = setTimeout(function () {
      if (self.dead) return;
      var plan = self.route && self.route.plan, act = self.route && self.route.active;
      if (plan) { self.setRoute(plan, false); self.routeStep(act, false); }
      else if (self.tk.projection === "plan") self.setMode(self.mode, false, true);
    }, 250);
  };

  /* ---- tooltip ------------------------------------------------------------------------------------- */
  P_.setTip = function (hit) {
    if (this.opts.tooltip === false) return;
    var tip = this.tip;
    if (!hit) { if (tip) tip.hidden = true; return; }
    if (!tip) {
      tip = this.tip = document.createElement("div");
      tip.className = "evk-map-tip";
      tip.setAttribute("role", "tooltip");
      var s = tip.style;
      s.position = "absolute"; s.zIndex = "2"; s.pointerEvents = "none"; s.margin = "0"; s.padding = "6px 10px"; s.transform = "translate(-50%, -100%)";
      s.background = "var(--a, #222)"; s.color = "var(--on-a, #fff)"; s.fontFamily = "var(--f-text, system-ui, sans-serif)"; s.lineHeight = "1.25"; s.whiteSpace = "nowrap";
      s.borderRadius = "var(--radius, 0)"; s.fontSize = "0.9rem"; s.fontWeight = "600";
      this.root.appendChild(tip);
    }
    var e = this.entById[hit.id], zh = this.lead === "zh";
    tip.textContent = "";
    var a = document.createElement("b"), b = document.createElement("span");
    a.textContent = zh ? e.name.cn : e.name.en; b.textContent = zh ? e.name.en : e.name.cn;
    b.style.cssText = "display:block;font-weight:400;font-size:.76em;opacity:.8";
    tip.appendChild(a); if (e.name.cn !== e.name.en) tip.appendChild(b);
    tip.hidden = false;
    var cr = this.canvas.getBoundingClientRect(), rr = this.root.getBoundingClientRect();
    tip.style.left = (hit.x + cr.left - rr.left) + "px"; tip.style.top = (hit.y - hit.rad - 6 + cr.top - rr.top) + "px";
  };
  P_.setCursor = function (c) { if (this.cur !== c) { this.cur = c; this.canvas.style.cursor = c; } };
  P_.hover = function (x, y) {
    var hit = this.locked ? null : this.pick(x, y), id = hit && hit.entity ? hit.entity : null;
    this.setCursor(hit && (hit.entity || hit.room) ? "pointer" : this.dragging ? "grabbing" : "grab");
    if (id !== this.hoverId) { this.hoverId = id; this.kick(); }
    var h = null;
    if (id) for (var i = 0; i < this.hits.length; i++) if (this.hits[i].id === id) h = this.hits[i];
    this.setTip(h);
  };

  /* ---- selection from a tap ---------------------------------------------------------------------------- */
  P_.tapped = function (hit) {
    var o = this.opts;
    if (this.locked) return;
    if (hit && hit.entity) { this.select(hit.entity); if (o.onSelect) o.onSelect(hit.entity, hit.room); }
    else if (hit && hit.room && o.onRoom) o.onRoom(hit.room);
    else if (hit && hit.floor && !hit.room && o.onFloor) o.onFloor(hit.floor);
    else if (!hit && this.sel) { this.select(null); if (o.onSelect) o.onSelect(null); }
  };

  /* ---- input ---------------------------------------------------------------------------------------------- */
  P_.listen = function (target, type, fn, opt) { target.addEventListener(type, fn, opt); this.cleanup.push(function () { target.removeEventListener(type, fn, opt); }); };
  P_.bind = function () {
    var self = this, el = this.canvas, T = this.T;
    if (window.ResizeObserver) { var ro = new ResizeObserver(function () { self.resize(); }); ro.observe(el); this.cleanup.push(function () { ro.disconnect(); }); }
    this.listen(window, "resize", function () { self.resize(); });
    if (window.IntersectionObserver) {
      var io = new IntersectionObserver(function (es) { self.visible = es[es.length - 1].isIntersecting; if (self.visible) self.kick(); });
      io.observe(el); this.cleanup.push(function () { io.disconnect(); });
    }
    var dark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)");
    function again() { self.refresh(); self.kick(); }
    if (dark && dark.addEventListener) { dark.addEventListener("change", again); this.cleanup.push(function () { dark.removeEventListener("change", again); }); }
    if (reduceQ && reduceQ.addEventListener) { var rm = function () { self.kick(); }; reduceQ.addEventListener("change", rm); this.cleanup.push(function () { reduceQ.removeEventListener("change", rm); }); }
    if (window.MutationObserver) {                             // data-theme, data-evk-lead, class or inline-style token changes anywhere above the canvas
      var queued = 0;
      var mo = new MutationObserver(function () {                 // one re-read per frame, however many attributes changed
        if (queued || self.dead) return;
        queued = requestAnimationFrame(function () { queued = 0; self.refresh(); });
      });
      var seen = [];
      for (var n = el; n && seen.indexOf(n) < 0; n = n.parentElement) { seen.push(n); mo.observe(n, { attributes: true, attributeFilter: ["class", "style", "data-theme", "data-evk-lead"] }); }
      this.cleanup.push(function () { mo.disconnect(); });
    }
    if (document.fonts) {                                      // canvas text will not relayout when a webfont arrives
      var kick = function () { self.kick(); };
      try { [this.tk.fLabel, this.tk.fCjk, this.tk.fNum].forEach(function (s) { document.fonts.load("700 12px " + s).then(kick, function () {}); }); } catch (e) { /* a nicety */ }
      if (document.fonts.addEventListener) { document.fonts.addEventListener("loadingdone", kick); this.cleanup.push(function () { document.fonts.removeEventListener("loadingdone", kick); }); }
    }

    function local(e) { var r = el.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }
    function two() {
      var ids = Object.keys(self.pointers);
      if (ids.length < 2) return null;
      var a = self.pointers[ids[0]], b = self.pointers[ids[1]];
      return { d: Math.hypot(a.x - b.x, a.y - b.y), ang: Math.atan2(b.y - a.y, b.x - a.x), mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2 };
    }
    function start() {                                         // (re)anchor the gesture on the fingers now down; a finger catches everything in flight
      self.fling = 0; self.panFling = null;
      [self.yaw, self.pitch, self.zoom, self.tx, self.ty].forEach(function (s) { s.hold(); });
      var ids = Object.keys(self.pointers), p = self.pointers[ids[0]];
      self.g0 = { x: p.x, y: p.y, yaw: self.yaw.x, pitch: self.pitch.x, zoom: self.zoom.x, tx: self.tx.x, ty: self.ty.x, two: two(), hist: [{ x: p.x, y: p.y, t: performance.now() }] };
    }
    function ob() { return self.dragMode() === "pan"; }                // the gesture follows the documented constant, not the projection name

    this.listen(el, "pointerdown", function (e) {
      if (e.pointerType === "mouse" && e.button !== 0) return;
      var p = local(e);
      self.pointers[e.pointerId] = { x: p[0], y: p[1], type: e.pointerType };
      try { el.setPointerCapture(e.pointerId); } catch (err) { /* capture is a nicety, not a requirement */ }
      if (Object.keys(self.pointers).length === 1) self.down = { x: p[0], y: p[1], t: performance.now(), moved: false };
      else if (self.down) self.down.moved = true;
      self.dragging = true; self.root.classList.add("is-dragging");
      self.setCursor("grabbing");
      if (self.hint) self.hint.classList.add("is-gone");
      self.setTip(null);
      start(); self.kick();
    });
    this.listen(el, "pointermove", function (e) {
      var p = local(e);
      if (!self.pointers[e.pointerId]) { if (e.pointerType === "mouse") self.hover(p[0], p[1]); return; }
      self.pointers[e.pointerId].x = p[0]; self.pointers[e.pointerId].y = p[1];
      var g0 = self.g0, t2 = two(), sp = self.cam ? self.cam.sp : 0.5, kk = Math.max(self.cam ? self.cam.s : 1, 1e-3);
      if (self.down && Math.hypot(p[0] - self.down.x, p[1] - self.down.y) > T.tapSlop) self.down.moved = true;
      if (t2 && g0.two) {
        self.zoom.x = rubber(g0.zoom * t2.d / g0.two.d, T.zoomMin, T.zoomMax, 1);
        if (ob()) { self.tx.x = g0.tx - (t2.mx - g0.two.mx) / kk; self.ty.x = g0.ty - (t2.my - g0.two.my) / (kk * Math.max(sp, 0.2)); }
        else { self.yaw.x = g0.yaw + wrap(t2.ang - g0.two.ang); self.pitch.x = self.pitchBand(g0.pitch + (t2.my - g0.two.my) * T.tilt); }
      } else if (!t2) {
        if (ob()) {                                           // oblique: the model is pulled across the table
          self.tx.x = g0.tx - (p[0] - g0.x) / kk;
          if (e.pointerType !== "touch") self.ty.x = g0.ty - (p[1] - g0.y) / (kk * Math.max(sp, 0.2));
        } else {
          self.yaw.x = g0.yaw - (p[0] - g0.x) * T.turn;                            // turntable: 1:1
          if (e.pointerType !== "touch") self.pitch.x = self.pitchBand(g0.pitch + (p[1] - g0.y) * T.tilt);
        }
        g0.hist.push({ x: p[0], y: p[1], t: performance.now() });
        if (g0.hist.length > 6) g0.hist.shift();
      }
      [self.yaw, self.pitch, self.zoom, self.tx, self.ty].forEach(function (s) { s.to = s.x; });
      if (self.down && self.down.moved) self.turned = true;
      self.kick();
    });
    function end(e, cancelled) {
      if (!self.pointers[e.pointerId]) return;
      delete self.pointers[e.pointerId];
      if (Object.keys(self.pointers).length) { start(); return; }
      self.dragging = false; self.root.classList.remove("is-dragging"); self.setCursor("grab");
      var g0 = self.g0, h = g0.hist, now = performance.now();
      while (h.length > 1 && now - h[0].t > 90) h.shift();                           // only the last 90 ms of motion counts
      var span = Math.max(12, h[h.length - 1].t - h[0].t);
      var vx = h.length > 1 ? (h[h.length - 1].x - h[0].x) / span * 1000 : 0, vy = h.length > 1 ? (h[h.length - 1].y - h[0].y) / span * 1000 : 0;
      if (now - h[h.length - 1].t > 80) { vx = 0; vy = 0; }                          // the finger stopped before lifting
      if (!g0.two && !reduced()) {
        if (ob()) { if (Math.hypot(vx, vy) > 60) self.panFling = { x: vx, y: e.pointerType === "touch" ? 0 : vy }; }
        else if (Math.abs(vx) > 60) self.fling = clamp(-vx * T.turn, -T.spinMax, T.spinMax);
      }
      self.pitch.to = clamp(self.pitch.x, self.pmin, self.pmax);
      self.zoom.to = clamp(self.zoom.x, T.zoomMin, T.zoomMax);
      var d = self.down; self.down = null;
      if (!cancelled && d && !d.moved && now - d.t < T.tapMs) { var p = local(e); self.tapped(self.pick(p[0], p[1])); }
      self.syncReset(); self.kick();
    }
    this.listen(el, "pointerup", function (e) { end(e, false); });
    this.listen(el, "pointercancel", function (e) { end(e, true); });
    this.listen(el, "pointerleave", function (e) { if (e.pointerType === "mouse") { self.setTip(null); if (self.hoverId) { self.hoverId = null; self.kick(); } } });

    /* trackpad pinch: ctrl + wheel in Chrome and Firefox, gesture events in Safari */
    this.listen(el, "wheel", function (e) {
      if (!e.ctrlKey) return;
      e.preventDefault();
      self.zoom.x = self.zoom.to = clamp(self.zoom.x * Math.exp(-e.deltaY * 0.01), T.zoomMin, T.zoomMax);
      self.syncReset(); self.kick();
    }, { passive: false });
    var gz = 1, gr = 0;
    this.listen(el, "gesturestart", function (e) { e.preventDefault(); gz = self.zoom.x; gr = self.yaw.x; });
    this.listen(el, "gesturechange", function (e) {
      e.preventDefault();
      if (Object.keys(self.pointers).length) return;
      self.zoom.to = self.zoom.x = clamp(gz * e.scale, T.zoomMin, T.zoomMax);
      if (!ob()) { self.yaw.to = self.yaw.x = gr + e.rotation * DEG; if (Math.abs(e.rotation) > 2) self.turned = true; }
      self.kick();
    });
    this.listen(el, "gestureend", function (e) { e.preventDefault(); self.syncReset(); });

    /* keyboard: the same targets, the same springs */
    this.listen(el, "keydown", function (e) {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      var k = e.key, now = reduced();
      if (k === "[" || k === "]") {                                // step through exhibitors on the floors in view
        e.preventDefault();
        var list = self.ents.filter(function (x) { return self.mode === "all" || self.mode === "route" || x.floor === self.mode; });
        if (!list.length) return;
        var i = list.findIndex(function (x) { return x.id === self.sel; }), nxt = list[(i + (k === "]" ? 1 : -1) + list.length * 2) % list.length];
        self.select(nxt.id); if (self.opts.onSelect && !self.locked) self.opts.onSelect(nxt.id, nxt.room);
        return;
      }
      if (k === "Escape" && self.sel && !self.locked) { self.select(null); if (self.opts.onSelect) self.opts.onSelect(null); return; }
      if (k === "0" || k === "Home") { e.preventDefault(); self.reset(); return; }
      var step = { ArrowLeft: [1, 0, 1], ArrowRight: [-1, 0, 1], ArrowUp: [0, -1, 1], ArrowDown: [0, 1, 1], "+": [0, 0, 1.25], "=": [0, 0, 1.25], "-": [0, 0, 0.8], "_": [0, 0, 0.8] }[k];
      if (!step) return;
      e.preventDefault();
      self.fling = 0; self.panFling = null; self.turned = true;
      if (ob()) {
        var kk = Math.max(self.cam.s, 1e-3), pan = 60 / kk;                       // 60 px of travel per press
        self.tx.to -= step[0] * pan; self.ty.to += step[1] * pan / Math.max(self.cam.sp, 0.2);
      } else {
        self.yaw.to += step[0] * 20 * DEG;
        self.pitch.to = clamp(self.pitch.to + step[1] * 8 * DEG, self.pmin, self.pmax);
      }
      self.zoom.to = clamp(self.zoom.to * step[2], T.zoomMin, T.zoomMax);
      if (now) { [self.yaw, self.pitch, self.zoom, self.tx, self.ty].forEach(function (s) { s.set(s.to); }); }
      self.syncReset(); self.kick();
    });

    if (this.resetBtn) this.listen(this.resetBtn, "click", function () { self.reset(); });
    if (this.hint) { this.hintTimer = setTimeout(function () { self.hint.classList.add("is-gone"); }, T.hintMs); }
  };

  P_.destroy = function () {
    this.dead = true;
    if (this.frame) cancelAnimationFrame(this.frame);
    clearTimeout(this.introTimer); clearTimeout(this.hintTimer); clearTimeout(this.relayoutTimer);
    this.cleanup.forEach(function (f) { try { f(); } catch (e) { /* already gone */ } });
    this.cleanup = [];
    this.root.classList.remove("is-live", "is-dragging");
    if (this.tip && this.tip.parentNode && this.tip.className === "evk-map-tip" && this.tip.style.position === "absolute") this.tip.parentNode.removeChild(this.tip);
  };

  /* one finger / the mouse dragging, per projection (the header says why). Frozen: a hint, a test or a recipe may read it. */
  VenueMap.DRAG_MODE = Object.freeze({ orbit: "rotate", exploded: "rotate", plan: "rotate", oblique: "pan" });
  VenueMap.dragModeFor = function (projection) { return VenueMap.DRAG_MODE[projection] || "rotate"; };

  EVK.VenueMap = VenueMap;
})();
