/* event-venue-kit · tones.js — one entity colour -> seven page-safe roles
   ----------------------------------------------------------------------------------------------
   EVK.tones(hex, {paper, ink, night, target})  ->  {e, eText, eOn, eSoft, eLine, eDk, eSoftDk}
   EVK.applyEntity(el, hex, opts)   sets --e --e-text --e-on --e-soft --e-line --e-dk --e-soft-dk on el
   EVK.applyEntities(root)          applies [data-entity-color="#RRGGBB"] on every match (also auto-run once)
   EVK.color                        {parse, hex, oklch, fromOklch, luminance, contrast, mix, toward}
   EVK.tones.selfTest()             compares this file with the table at the bottom of this comment
   EVK.tones.palette()/refresh()    paper / ink / night read from the page's tokens (see "Defaults")

   Generalised from the source site's tools/report.py palette(): a school colour became a fill, a
   text-safe shade, an on-colour, a soft tint, a line tint, and two dark-mode shades. This version walks
   lightness in OKLCH (hue and chroma kept) instead of mixing toward ink, so an orange stays an orange
   when it is darkened for text. Same output, role by role, as scripts/kit.py tones().

   ALGORITHM (exact; scripts/kit.py must follow it step by step; every number is IEEE double)
   ----------------------------------------------------------------------------------------------
   0. Hex in/out. Input "#RGB" or "#RRGGBB" (case-insensitive, '#' optional). Output "#RRGGBB" upper case.
      Channel rounding is ROUND HALF UP: v8 = floor(v + 0.5) clamped to 0..255.  Python: math.floor(v+0.5);
      never Python's round() (it is banker's rounding and differs at exact .5).
   1. sRGB <-> linear:  lin(c8) = c<=0.04045 ? c/12.92 : ((c+0.055)/1.055)^2.4  with c = c8/255
                        delin(l) = l<=0.0031308 ? 12.92*l : 1.055*l^(1/2.4) - 0.055
   2. WCAG relative luminance  Y = 0.2126 R + 0.7152 G + 0.0722 B  (R,G,B = lin of the 8-bit channels)
      contrast(a,b) = (max(Ya,Yb)+0.05) / (min(Ya,Yb)+0.05)
   3. OKLab (Ottosson 2020, original constants):
        l = 0.4122214708 r + 0.5363325363 g + 0.0514459929 b
        m = 0.2119034982 r + 0.6806995451 g + 0.1073969566 b
        s = 0.0883024619 r + 0.2817188376 g + 0.6299787005 b          (r g b linear)
        l_ = cbrt(l)  m_ = cbrt(m)  s_ = cbrt(s)
        L = 0.2104542553 l_ + 0.7936177850 m_ - 0.0040720468 s_
        a = 1.9779984951 l_ - 2.4285922050 m_ + 0.4505937099 s_
        b = 0.0259040371 l_ + 0.7827717662 m_ - 0.8086757660 s_
      inverse:  l_ = L + 0.3963377774 a + 0.2158037573 b
                m_ = L - 0.1055613458 a - 0.0638541728 b
                s_ = L - 0.0894841775 a - 1.2914855480 b           l = l_^3, m = m_^3, s = s_^3
                r = +4.0767416621 l - 3.3077115913 m + 0.2309699292 s
                g = -1.2684380046 l + 2.6097574011 m - 0.3413193965 s
                b = -0.0041960863 l - 0.7034186147 m + 1.7076147010 s
      OKLCH: C = hypot(a,b), h = atan2(b,a) in degrees (mod 360). Back: a = C cos h, b = C sin h.
      cbrt is the real cube root (sign-preserving).
   4. fromOklch(L,C,h) -> 8-bit hex with gamut mapping by chroma reduction:
        rgb = linear sRGB of (L,C,h); in gamut <=> every channel in [-1e-6, 1+1e-6].
        If not in gamut: lo=0, hi=C; repeat 32 times { mid=(lo+hi)/2; in gamut(L,mid,h) ? lo=mid : hi=mid };
        use C=lo. Then clamp each linear channel to [0,1], delin, *255, round half up.
   5. walk(c, dir, bg, target, maxL): the lightness walk ("toward")
        (L0,C,h) = oklch(c);  if contrast(c,bg) >= target return c unchanged;
        for i = 1..100:  L = clamp(L0 + (dir*0.01)*i, 0, 1);  if maxL given and L > maxL: L = maxL;
                         out = fromOklch(L,C,h);  if contrast(out,bg) >= target return out;
                         if maxL given and L >= maxL: stop
        (dir = -1 darker, +1 lighter; 1% = 0.01 of the OKLCH L scale)
        not found: return null.
   6. Roles (target default 4.6; paper, ink, night are hex):
        eText   = the walk TOWARD THE INK END on paper, or ink if it finds nothing:
                    ink lighter than paper (a dark-ground card):  walk(c, +1, paper, target, 0.98)
                    otherwise (dark ink on light paper):          walk(c, -1, paper, target)
                  "lighter than" = relative luminance (step 2) of ink > that of paper. A dark-ground card therefore keeps the hue
                  of every entity colour; only if even L = 0.98 misses the target does eText become the ink colour.
        eDk     = walk(c, +1, night, target)  or "#FFFFFF"   text-safe on the dark ground, same hue
        e       = c, unless max(contrast(c,paper), contrast(c,ink)) < target, then eText   (fill protection)
        eOn     = paper if contrast(e,paper) >= contrast(e,ink) else ink
        eSoft   = mix(c, paper, 0.9)     (10 % colour)      mix(a,b,t): per channel a+(b-a)*t, round half up
        eLine   = mix(c, paper, 0.55)    (45 % colour)
        eSoftDk = mix(c, night, 0.78)    (22 % colour)
      Note eSoft/eLine/eSoftDk use the ORIGINAL c, also when e was protected (as in report.py).
      Note on a dark ground the fill is eDk and the text on it is the night ground (base.css --e-fill-on):
      eDk is built to reach `target` against night, so night-on-eDk always passes.

   Defaults (paper / ink / night when opts omit them)
   ----------------------------------------------------------------------------------------------
   1. opts, 2. EVK.tones.palette.set({paper,ink,night}) / <html data-evk-paper|ink|night="#hex">,
   3. the page's own tokens: --paper and --text of :root (light), --paper of the dark block (night),
      read from same-origin stylesheets, 4. source values: paper #F7F5F0, ink #14171D, night #0D1D36
      (原站取值 / source value; any palette is fine, only the three hex strings matter).
   The source values are right for the source's own light paper only. A card with another paper (above all a dark
   ground) gets wrong text shades from them, and a stylesheet read from file:// counts as cross-origin in some browsers,
   so step 3 can come back empty. install.py therefore writes data-evk-paper|ink|night on <html>; when a page still
   falls back to the source values, tones() says so ONCE in the console (EVK.tones.palette().from names the origin of
   each of the three: "opts" | "attr" | "css" | "source").

   Options (all optional): chromaCapDark (number): cap OKLCH chroma while lightening for the dark shade,
   e.g. 0.14 for a calmer dark mode; default none (then identical to kit.py).

   Fixed test table (paper #F7F5F0, ink #14171D, night #0D1D36, target 4.6) — kit.py must reproduce it:
   input     e        eText    eOn      eSoft    eLine    eDk      eSoftDk   (opts)
   #8C1515 #8C1515 #8C1515 #F7F5F0 #ECDFDA #C7908D #DB6258 #291B2F
   #FF6C0C #FF6C0C #BA4B00 #14171D #F8E7D9 #FBB789 #FF6C0C #422E2D
   #7BAFD4 #7BAFD4 #3F7294 #14171D #EBEEED #BFD6E3 #7BAFD4 #253D59
   #370404 #370404 #370404 #F7F5F0 #E4DDD8 #A18986 #B4766E #16182B
   #09A7C8 #09A7C8 #007992 #14171D #DFEDEC #8CD2DE #09A7C8 #0C3B56
   #7F7F7F #6D6D6D #6D6D6D #F7F5F0 #EBE9E5 #C1C0BD #888888 #263346
   #2E7D32 #0F6519 #0F6519 #FFFFFF #EAF2EB #A1C5A3 #64B265 #182A19   paper #FFFFFF ink #000000 night #121212 target 7
   #E91E63 #D90058 #D90058 #FAF3E8 #F8DEDB #F293AC #F02969 #481622   paper #FAF3E8 ink #2B2118 night #1A1410 target 4.5
   dark-ground cards (paper darker than ink): the text shade walks lighter and keeps its hue
   #1F6FB2 #428ED3 #428ED3 #14202E #15283B #194469 #3884C9 #0F2640   paper #14202E ink #EEEAE1 night #0B1220 target 4.6
   #8C1515 #8C1515 #DB6258 #EEEAE1 #201F2C #4A1B23 #D0594F #27131E   (same dark opts)
   #370404 #370404 #B77971 #EEEAE1 #181D2A #24131B #AE7068 #150F1A   (same dark opts)
   #7F7F7F #888888 #888888 #14202E #1F2A36 #444B52 #7F7F7F #252A35   (same dark opts)
   #1F6FB2 #EEEAE1 #EEEAE1 #14202E #15283B #194469 #E7F3FF #0F2640   (same dark opts, target 16.4: L = 0.98 is not enough -> ink)
   ---------------------------------------------------------------------------------------------- */
(function () {
  "use strict";
  var EVK = (typeof window !== "undefined" ? window : globalThis).EVK =
    (typeof window !== "undefined" ? window : globalThis).EVK || {};
  var hasDoc = typeof document !== "undefined";

  /* ---- hex / sRGB ---- */
  function parse(s) {
    s = String(s == null ? "" : s).trim().replace(/^#/, "");
    if (/^[0-9a-f]{3}$/i.test(s)) s = s.charAt(0) + s.charAt(0) + s.charAt(1) + s.charAt(1) + s.charAt(2) + s.charAt(2);
    if (!/^[0-9a-f]{6}$/i.test(s)) throw new TypeError("EVK.tones: not a hex colour: " + s);
    return [parseInt(s.slice(0, 2), 16), parseInt(s.slice(2, 4), 16), parseInt(s.slice(4, 6), 16)];
  }
  function r8(v) { v = Math.floor(v + 0.5); return v < 0 ? 0 : v > 255 ? 255 : v; }
  function hex(rgb) {
    var out = "#";
    for (var i = 0; i < 3; i++) { var h = r8(rgb[i]).toString(16).toUpperCase(); out += h.length < 2 ? "0" + h : h; }
    return out;
  }
  function norm(s) { return hex(parse(s)); }
  function lin(c8) { var c = c8 / 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); }
  function delin(l) { return l <= 0.0031308 ? 12.92 * l : 1.055 * Math.pow(l, 1 / 2.4) - 0.055; }
  function luminance(h) {
    var c = parse(h);
    return 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
  }
  function contrast(a, b) {
    var la = luminance(a), lb = luminance(b);
    var hi = la > lb ? la : lb, lo = la > lb ? lb : la;
    return (hi + 0.05) / (lo + 0.05);
  }
  function mix(a, b, t) {
    var x = parse(a), y = parse(b);
    return hex([x[0] + (y[0] - x[0]) * t, x[1] + (y[1] - x[1]) * t, x[2] + (y[2] - x[2]) * t]);
  }

  /* ---- OKLab / OKLCH ---- */
  function cbrt(x) { return x < 0 ? -Math.pow(-x, 1 / 3) : Math.pow(x, 1 / 3); }
  function oklch(h) {
    var c = parse(h), r = lin(c[0]), g = lin(c[1]), b = lin(c[2]);
    var l = cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
    var m = cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
    var s = cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
    var L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s;
    var A = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s;
    var B = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s;
    var hh = Math.atan2(B, A) * 180 / Math.PI;
    if (hh < 0) hh += 360;
    return [L, Math.sqrt(A * A + B * B), hh];
  }
  function linRgb(L, C, h) {
    var a = C * Math.cos(h * Math.PI / 180), b = C * Math.sin(h * Math.PI / 180);
    var l_ = L + 0.3963377774 * a + 0.2158037573 * b;
    var m_ = L - 0.1055613458 * a - 0.0638541728 * b;
    var s_ = L - 0.0894841775 * a - 1.2914855480 * b;
    var l = l_ * l_ * l_, m = m_ * m_ * m_, s = s_ * s_ * s_;
    return [
      4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
      -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
      -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    ];
  }
  function inGamut(v) {
    return v[0] >= -1e-6 && v[0] <= 1 + 1e-6 && v[1] >= -1e-6 && v[1] <= 1 + 1e-6 && v[2] >= -1e-6 && v[2] <= 1 + 1e-6;
  }
  function fromOklch(L, C, h) {
    var v = linRgb(L, C, h);
    if (!inGamut(v)) {
      var lo = 0, hi = C;
      for (var i = 0; i < 32; i++) {
        var mid = (lo + hi) / 2;
        if (inGamut(linRgb(L, mid, h))) lo = mid; else hi = mid;
      }
      v = linRgb(L, lo, h);
    }
    var out = [];
    for (var k = 0; k < 3; k++) {
      var x = v[k] < 0 ? 0 : v[k] > 1 ? 1 : v[k];
      out.push(delin(x) * 255);
    }
    return hex(out);
  }

  /* ---- the lightness walk ---- */
  function toward(c, dir, bg, target, chromaCap, maxL) {
    c = norm(c); bg = norm(bg);
    if (contrast(c, bg) >= target) return c;
    var lch = oklch(c), L0 = lch[0], C = lch[1], h = lch[2];
    if (chromaCap != null && C > chromaCap) C = chromaCap;
    var step = dir * 0.01;
    for (var i = 1; i <= 100; i++) {
      var L = L0 + step * i;
      L = L < 0 ? 0 : L > 1 ? 1 : L;
      if (maxL != null && L > maxL) L = maxL;
      var out = fromOklch(L, C, h);
      if (contrast(out, bg) >= target) return out;
      if (maxL != null && L >= maxL) break;
    }
    return null;
  }

  /* ---- defaults read from the page ---- */
  var FALLBACK = { paper: "#F7F5F0", ink: "#14171D", night: "#0D1D36" };
  var cache = null, manual = null;

  function toHexLoose(v) {
    v = String(v || "").trim();
    if (!v) return null;
    try { return norm(v); } catch (e) { /* not hex */ }
    if (!hasDoc) return null;
    try {   // rgb(), hsl(), oklch(), names: let the canvas resolve opaque colours
      var cx = document.createElement("canvas").getContext("2d");
      cx.fillStyle = "#010203"; cx.fillStyle = v;
      var got = cx.fillStyle;
      if (got === "#010203" && !/^#010203$/i.test(v)) return null;
      return /^#/.test(got) ? norm(got) : null;
    } catch (e2) { return null; }
  }
  function scan() {
    var found = { paper: null, ink: null, night: null };
    if (!hasDoc) return found;
    function walkRules(rules, dark) {
      for (var i = 0; i < rules.length; i++) {
        var r = rules[i];
        if (r.type === 1) {
          var sel = r.selectorText || "", st = r.style;
          var isDark = dark || /data-theme=["']?dark/.test(sel);
          var isLightRoot = !isDark && /^:root$/.test(sel.trim());
          var p = st.getPropertyValue("--paper");
          if (p && isDark) found.night = toHexLoose(p) || found.night;
          else if (p && isLightRoot) found.paper = toHexLoose(p) || found.paper;
          var t = st.getPropertyValue("--text");
          if (t && isLightRoot) found.ink = toHexLoose(t) || found.ink;
        } else if (r.cssRules) {
          walkRules(r.cssRules, dark || (r.type === 4 && /prefers-color-scheme:\s*dark/.test(r.conditionText || (r.media && r.media.mediaText) || "")));
        }
      }
    }
    for (var s = 0; s < document.styleSheets.length; s++) {
      try { walkRules(document.styleSheets[s].cssRules, false); } catch (e) { /* cross-origin sheet */ }
    }
    return found;
  }
  var warned = false;
  function palette() {
    if (!cache) {
      var s = scan(), de = hasDoc ? document.documentElement : null;
      function attr(n) { try { return de && de.getAttribute("data-evk-" + n) ? norm(de.getAttribute("data-evk-" + n)) : null; } catch (e) { return null; } }
      cache = {};
      var from = {}, fell = [];
      ["paper", "ink", "night"].forEach(function (k) {
        var m = manual && manual[k], a = m ? null : attr(k), c = (m || a) ? null : s[k];
        cache[k] = m || a || c || FALLBACK[k];
        from[k] = m ? "opts" : a ? "attr" : c ? "css" : "source";
        if (from[k] === "source") fell.push(k + " " + FALLBACK[k]);
      });
      Object.defineProperty(cache, "from", { value: from, enumerable: false });
      if (hasDoc && fell.length && !warned && typeof console !== "undefined" && console.warn) {
        warned = true;
        console.warn("EVK.tones: could not read " + fell.join(", ") + " from the page; using the source site's values. Entity text shades are wrong on a card " +
          "with another paper (a dark ground above all). Put data-evk-paper / data-evk-ink / data-evk-night on <html> (install.py prints them) or call EVK.tones.palette.set({...}).");
      }
    }
    return cache;
  }
  palette.set = function (o) {
    manual = manual || {};
    ["paper", "ink", "night"].forEach(function (k) { if (o && o[k]) manual[k] = norm(o[k]); });
    cache = null;
    return palette();
  };
  palette.refresh = function () { cache = null; return palette(); };

  /* ---- the roles ---- */
  function tones(c, o) {
    o = o || {};
    var pal = palette();
    var paper = norm(o.paper || pal.paper), ink = norm(o.ink || pal.ink), night = norm(o.night || pal.night);
    var target = o.target != null ? +o.target : 4.6;
    c = norm(c);
    // the text shade walks toward the ink end: darker for dark ink on light paper, lighter (to L 0.98) on a dark ground
    var text = (luminance(ink) > luminance(paper) ? toward(c, +1, paper, target, null, 0.98) : toward(c, -1, paper, target)) || ink;
    var dk = toward(c, +1, night, target, o.chromaCapDark) || "#FFFFFF";
    var fill = c;
    if (Math.max(contrast(c, paper), contrast(c, ink)) < target) fill = text;
    var on = contrast(fill, paper) >= contrast(fill, ink) ? paper : ink;
    return {
      e: fill, eText: text, eOn: on,
      eSoft: mix(c, paper, 0.9), eLine: mix(c, paper, 0.55),
      eDk: dk, eSoftDk: mix(c, night, 0.78)
    };
  }
  tones.palette = palette;
  tones.refresh = palette.refresh;

  var VARS = { e: "--e", eText: "--e-text", eOn: "--e-on", eSoft: "--e-soft", eLine: "--e-line", eDk: "--e-dk", eSoftDk: "--e-soft-dk" };
  function applyEntity(el, c, o) {
    if (!el || !el.style) return null;
    var t;
    try { t = tones(c, o); } catch (err) {
      if (typeof console !== "undefined") console.warn("EVK.applyEntity: " + err.message);
      return null;
    }
    for (var k in VARS) if (Object.prototype.hasOwnProperty.call(VARS, k)) el.style.setProperty(VARS[k], t[k]);
    return t;
  }
  function applyEntities(root, o) {
    if (!hasDoc) return 0;
    var list = (root || document).querySelectorAll("[data-entity-color]"), n = 0;
    for (var i = 0; i < list.length; i++) if (applyEntity(list[i], list[i].getAttribute("data-entity-color"), o)) n++;
    return n;
  }

  /* ---- self test against the fixed table ---- */
  var TABLE = [
    ["#8C1515", ["#8C1515", "#8C1515", "#F7F5F0", "#ECDFDA", "#C7908D", "#DB6258", "#291B2F"]],
    ["#FF6C0C", ["#FF6C0C", "#BA4B00", "#14171D", "#F8E7D9", "#FBB789", "#FF6C0C", "#422E2D"]],
    ["#7BAFD4", ["#7BAFD4", "#3F7294", "#14171D", "#EBEEED", "#BFD6E3", "#7BAFD4", "#253D59"]],
    ["#370404", ["#370404", "#370404", "#F7F5F0", "#E4DDD8", "#A18986", "#B4766E", "#16182B"]],
    ["#09A7C8", ["#09A7C8", "#007992", "#14171D", "#DFEDEC", "#8CD2DE", "#09A7C8", "#0C3B56"]],
    ["#7F7F7F", ["#6D6D6D", "#6D6D6D", "#F7F5F0", "#EBE9E5", "#C1C0BD", "#888888", "#263346"]],
    ["#2E7D32", ["#0F6519", "#0F6519", "#FFFFFF", "#EAF2EB", "#A1C5A3", "#64B265", "#182A19"], {"paper": "#FFFFFF", "ink": "#000000", "night": "#121212", "target": 7}],
    ["#E91E63", ["#D90058", "#D90058", "#FAF3E8", "#F8DEDB", "#F293AC", "#F02969", "#481622"], {"paper": "#FAF3E8", "ink": "#2B2118", "night": "#1A1410", "target": 4.5}],
    ["#1F6FB2", ["#428ED3", "#428ED3", "#14202E", "#15283B", "#194469", "#3884C9", "#0F2640"], {"paper": "#14202E", "ink": "#EEEAE1", "night": "#0B1220", "target": 4.6}],
    ["#8C1515", ["#8C1515", "#DB6258", "#EEEAE1", "#201F2C", "#4A1B23", "#D0594F", "#27131E"], {"paper": "#14202E", "ink": "#EEEAE1", "night": "#0B1220", "target": 4.6}],
    ["#370404", ["#370404", "#B77971", "#EEEAE1", "#181D2A", "#24131B", "#AE7068", "#150F1A"], {"paper": "#14202E", "ink": "#EEEAE1", "night": "#0B1220", "target": 4.6}],
    ["#7F7F7F", ["#888888", "#888888", "#14202E", "#1F2A36", "#444B52", "#7F7F7F", "#252A35"], {"paper": "#14202E", "ink": "#EEEAE1", "night": "#0B1220", "target": 4.6}],
    ["#1F6FB2", ["#EEEAE1", "#EEEAE1", "#14202E", "#15283B", "#194469", "#E7F3FF", "#0F2640"], {"paper": "#14202E", "ink": "#EEEAE1", "night": "#0B1220", "target": 16.4}]
  ];
  tones.table = TABLE;
  tones.selfTest = function () {
    var bad = [];
    TABLE.forEach(function (row) {
      var got = tones(row[0], row[2] || { paper: "#F7F5F0", ink: "#14171D", night: "#0D1D36", target: 4.6 });
      ["e", "eText", "eOn", "eSoft", "eLine", "eDk", "eSoftDk"].forEach(function (k, i) {
        if (got[k] !== row[1][i]) bad.push(row[0] + " " + k + ": got " + got[k] + ", table " + row[1][i]);
      });
    });
    return bad;
  };

  EVK.tones = tones;
  EVK.applyEntity = applyEntity;
  EVK.applyEntities = applyEntities;
  EVK.color = { parse: parse, hex: hex, norm: norm, oklch: oklch, fromOklch: fromOklch, luminance: luminance, contrast: contrast, mix: mix, toward: toward };

  if (hasDoc) {
    var auto = function () { applyEntities(document); };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", auto); else auto();
  }
  if (typeof module !== "undefined" && module.exports) module.exports = EVK;
})();
