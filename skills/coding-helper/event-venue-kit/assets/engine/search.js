/* event-venue-kit · assets/engine/search.js
   ---------------------------------------------------------------------------
   Find an exhibitor / session / stand by what people actually type: a name in
   either language, a short form, a group word ("藤校", "理工", "craft"), a
   room number ("203" lists that room's entities). No DOM, no deps; a classic
   <script> (window.EVK.search) that also loads under Node.

     var s = EVK.search.create(venue.entities, {
       groups: [{ words: ["手作", "craft", "handmade"], ids: ["loomhouse", "echo"] },    // words that name a set of entities
                { words: ["space"], tags: ["space"] }],                                  // …or every entity with a tag / in a room / on a floor
       rooms:  venue.floors,          // optional: rooms (or areas, or floors with rooms[] / areas[]) so "201" and "Glass" find the room's entities;
                                      // floors also answer to their id, `short` and `name` ("2F", "2 层", "Second Floor")
       tags:   venue.terms.tags,      // optional: the words for the tag ids, {craft: {en: "Craft", cn: "手作"}}: "手作" finds every entity tagged craft
       fields: ["alias", "name.pinyin"]   // optional: more fields to count as names (dotted paths; arrays are flattened)
     });
     s.query("loom")  ->  [{ entity, score, why }, …]   best first; the entity is the object you passed in
     s.best(q)        ->  the first entity or null       (what Enter should take)
     s.query("")      ->  every entity in venue order, score 0, why "all"      (an empty box shows the whole list)
     s.query(q, { limit: 8 })

   Ranking (ported from the CollegeFair site: fair.js normalize, map.js search):
     score 4  the whole query is one of the entity's names            why "name"
     score 3  a name starts with the query                            why "name-prefix"
     score 2  another key starts with it: a group word, a room number,
              a tag, an id, a booth number                            why "group" | "room" | "tag" | "id" | "booth"
     score 1  any name or key contains it                             why "contains"
     0.5      several words, each found somewhere (the words are AND-ed)   why "words"
   Ties keep venue order (the order of the array you passed), so a result list never reshuffles.

   Names an entity answers to: name.en, name.cn (or the plain string), short, the English name without a leading
   "The", the initials of an English name of two or more words ("Tinker Tide Robotics" → ttr), plus `fields`.
   Keys (score 2 / 1): the names, id, tags (and the words for them, `tags`), its room's id / label / names and its floor's id / short / name, the group words it belongs
   to, and the booth as "<room><booth>" (20301 finds booth 01 of room 203; a bare booth number is a key only when
   no two entities share it).

   normalize(): the key every name and every query is reduced to. Full-width → half-width (ＡＢ１ → ab1), compatibility
   forms folded (NFKC), lower case, accents dropped (café → cafe), then every space, punctuation mark and symbol
   removed, so "Moss & Wire", "moss-wire" and "MOSSWIRE" are one key and 3-02, 3·02 and 302 are one key.
   Traditional/simplified Chinese are not unified (add the other form to `fields` if you need both).

   Load order in a page: tones, search, spring, sheet, part-nav, wayfind, venue-map (search needs none of the others).
   node search.js --selftest   runs the checks at the bottom.
   --------------------------------------------------------------------------- */
(function () {
  "use strict";
  var G = typeof window !== "undefined" ? window : globalThis;
  var EVK = G.EVK = G.EVK || {};

  var RE_STRIP;
  try { RE_STRIP = new RegExp("[\\s\\p{P}\\p{S}\\p{Cc}\\p{Cf}]", "gu"); }                     // ES2018 property escapes
  catch (e) { RE_STRIP = /[\s\-_.,'’"“”‘()（）·–—\/\\&+!?:;、，。！？：；《》【】「」\[\]{}<>|~`@#$%^*=]/g; }

  function normalize(s) {
    s = String(s == null ? "" : s);
    s = s.replace(/[！-～]/g, function (c) { return String.fromCharCode(c.charCodeAt(0) - 0xFEE0); }).replace(/　/g, " ");   // full-width → half-width
    try { s = s.normalize("NFKC"); } catch (e) { /* very old engines: the manual fold above is enough for ASCII */ }
    s = s.toLowerCase();
    try { s = s.normalize("NFD").replace(/[̀-ͯ]/g, "").normalize("NFC"); } catch (e2) { /* keep the accents */ }
    return s.replace(RE_STRIP, "");
  }

  function text(v) { return typeof v === "string" ? { en: v, cn: v } : v && typeof v === "object" ? { en: v.en || v.cn || "", cn: v.cn || v.en || "" } : { en: "", cn: "" }; }
  function pick(o, path) {              // "name.en" → o.name.en; arrays are flattened
    var cur = [o];
    String(path).split(".").forEach(function (k) {
      var next = [];
      cur.forEach(function (c) {
        if (c == null) return;
        var v = c[k];
        if (Array.isArray(v)) v.forEach(function (x) { next.push(x); }); else if (v != null) next.push(v);
      });
      cur = next;
    });
    var out = [];
    cur.forEach(function (v) { if (typeof v === "string" || typeof v === "number") out.push(String(v)); else if (v && typeof v === "object") { if (v.en) out.push(v.en); if (v.cn) out.push(v.cn); } });
    return out;
  }
  function uniq(a) { var seen = {}; return a.filter(function (x) { if (!x || seen[x]) return false; seen[x] = 1; return true; }); }

  /* rooms may be a list of rooms/areas, an {id: room} map, or floors that carry rooms[] / areas[]; a floor is also known by its
     short and name ("2F", "2 层", "Second Floor", "二层"), so typing a floor lists what stands on it */
  function compileRooms(rooms) {
    var by = {}, floorKeys = {};
    function fkeys(fid) { return fid != null && floorKeys[fid] ? floorKeys[fid] : [normalize(fid)]; }
    function add(r, floorId) {
      if (!r || r.id == null) return;
      var n = text(r.name);
      by[String(r.id)] = { keys: uniq([normalize(r.id), normalize(r.label), normalize(n.en), normalize(n.cn)].concat(fkeys(r.floor || floorId))), floor: r.floor || floorId };
    }
    function walk(x) {
      if (!x) return;
      if (Array.isArray(x)) { x.forEach(walk); return; }
      if (x.rooms || x.areas) {
        var sh = text(x.short), fn = text(x.name);
        floorKeys[x.id] = uniq([normalize(x.id), normalize(sh.en), normalize(sh.cn), normalize(fn.en), normalize(fn.cn)]);
        (x.rooms || []).forEach(function (r) { add(r, x.id); }); (x.areas || []).forEach(function (r) { add(r, x.id); });
        return;
      }
      if (x.id != null && (x.poly || x.rect || x.label != null || x.name)) { add(x, x.floor); return; }
      Object.keys(x).forEach(function (k) { var r = x[k]; if (r && typeof r === "object") add(r.id != null ? r : { id: k, name: r.name, label: r.label, floor: r.floor }, r.floor); });
    }
    walk(rooms);
    by["\u0000floors"] = floorKeys;                                   // not a room id: the floors' words, for entities that name a floor
    return by;
  }

  /* groups: [{words, ids?, tags?, rooms?, floors?}] | [[words, ids]] | {word: ids} */
  function compileGroups(groups) {
    var out = [];
    function words(w) { return uniq((Array.isArray(w) ? w : [w]).map(normalize)); }
    if (Array.isArray(groups)) {
      groups.forEach(function (g) {
        if (Array.isArray(g)) out.push({ words: words(g[0]), ids: g[1] || [] });
        else if (g) out.push({ words: words(g.words || g.word || []), ids: g.ids || [], tags: g.tags || [], rooms: g.rooms || [], floors: g.floors || [] });
      });
    } else if (groups && typeof groups === "object") {
      Object.keys(groups).forEach(function (k) { out.push({ words: words(k), ids: Array.isArray(groups[k]) ? groups[k] : [] }); });
    }
    return out;
  }

  function initials(en) {
    var w = String(en || "").split(/[^A-Za-z0-9]+/).filter(function (x) { return /^[A-Za-z]/.test(x) && !/^(and|of|the|co|inc|ltd)$/i.test(x); });
    return w.length >= 2 ? w.map(function (x) { return x.charAt(0); }).join("") : "";
  }

  function create(entities, opts) {
    opts = opts || {};
    var list = (entities || []).slice(), rooms = compileRooms(opts.rooms), groups = compileGroups(opts.groups), extra = opts.fields || [], tagWords = opts.tags || {};
    var floorKeys = rooms["\u0000floors"] || {};
    var boothCount = {};
    list.forEach(function (e) { if (e && e.booth != null) boothCount[normalize(e.booth)] = (boothCount[normalize(e.booth)] || 0) + 1; });

    var rows = list.map(function (e, i) {
      var n = text(e.name), names = [], keys = [];     // keys: [{ k, kind }]
      function name(v) { var k = normalize(v); if (k) names.push(k); }
      function key(v, kind) { var k = normalize(v); if (k) keys.push({ k: k, kind: kind }); }
      name(n.en); name(n.cn); name(e.short);
      name(String(n.en).replace(/^the\s+/i, ""));
      name(initials(n.en));
      extra.forEach(function (p) { pick(e, p).forEach(name); });
      names = uniq(names);
      names.forEach(function (k) { keys.push({ k: k, kind: "name" }); });
      key(e.id, "id");
      (e.tags || []).forEach(function (t) {
        key(t, "tag");
        var w = tagWords[t] != null ? text(tagWords[t]) : null;           // the words people read for the tag id
        if (w) { key(w.en, "tag"); key(w.cn, "tag"); }
      });
      var rm = e.room != null ? rooms[String(e.room)] : null, roomKeys = rm ? rm.keys : e.room != null ? [normalize(e.room)] : [];
      roomKeys.forEach(function (k) { if (k) keys.push({ k: k, kind: "room" }); });
      if (e.floor) { key(e.floor, "room"); (floorKeys[e.floor] || []).forEach(function (k) { if (k) keys.push({ k: k, kind: "room" }); }); }
      if (e.booth != null) {
        var b = normalize(e.booth);
        if (b && boothCount[b] === 1) key(e.booth, "booth");
        if (e.room != null) { key(e.room + "" + e.booth, "booth"); if (rm) rm.keys.slice(0, 2).forEach(function (rk) { if (rk) keys.push({ k: rk + b, kind: "booth" }); }); }
      }
      groups.forEach(function (g) {
        var hit = g.ids.indexOf(e.id) >= 0 || (g.tags || []).some(function (t) { return (e.tags || []).indexOf(t) >= 0; }) ||
          (g.rooms || []).some(function (r) { return String(r) === String(e.room); }) || (g.floors || []).some(function (f) { return f === e.floor || (rm && rm.floor === f); });
        if (hit) g.words.forEach(function (w) { if (w) keys.push({ k: w, kind: "group" }); });
      });
      var seen = {}, kk = keys.filter(function (x) { var id = x.kind + "\u0000" + x.k; if (seen[id]) return false; seen[id] = 1; return true; });
      return { entity: e, i: i, names: names, keys: kk, flat: kk.map(function (x) { return x.k; }) };
    });

    function score(row, q) {
      var j, key;
      if (row.names.indexOf(q) >= 0) return { score: 4, why: "name" };
      for (j = 0; j < row.names.length; j++) if (row.names[j].indexOf(q) === 0) return { score: 3, why: "name-prefix" };
      for (j = 0; j < row.keys.length; j++) { key = row.keys[j]; if (key.kind !== "name" && key.k.indexOf(q) === 0) return { score: 2, why: key.kind }; }
      for (j = 0; j < row.flat.length; j++) if (row.flat[j].indexOf(q) >= 0) return { score: 1, why: "contains" };
      return null;
    }

    function query(q, o) {
      var raw = String(q == null ? "" : q), nq = normalize(raw), out = [];
      if (!nq) out = rows.map(function (r) { return { entity: r.entity, score: 0, why: "all", i: r.i }; });
      else {
        var tokens = raw.split(/[\s,，、;；]+/).map(normalize).filter(Boolean);
        rows.forEach(function (r) {
          var s = score(r, nq);
          if (!s && tokens.length > 1 && tokens.every(function (t) { return r.flat.some(function (k) { return k.indexOf(t) >= 0; }); })) s = { score: 0.5, why: "words" };
          if (s) out.push({ entity: r.entity, score: s.score, why: s.why, i: r.i });
        });
        out.sort(function (a, b) { return b.score - a.score || a.i - b.i; });
      }
      if (o && o.limit > 0) out = out.slice(0, o.limit);
      return out.map(function (x) { return { entity: x.entity, score: x.score, why: x.why }; });
    }

    return {
      query: query,
      best: function (q) { var r = query(q, { limit: 1 }); return r.length && r[0].score > 0 ? r[0].entity : null; },
      size: rows.length
    };
  }

  EVK.search = { version: "0.1.0", normalize: normalize, create: create };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = EVK;
    if (typeof require !== "undefined" && require.main === module && process.argv.indexOf("--selftest") >= 0) selftest();
  }

  /* ---- node search.js --selftest ---------------------------------------------- */
  function selftest() {
    var fails = 0, n = 0;
    function ok(c, msg) { n++; if (!c) { fails++; console.log("FAIL  " + msg); } }
    function ids(r) { return r.map(function (x) { return x.entity.id; }).join(","); }
    var N = EVK.search.normalize;
    ok(N("  Ｍoss ＆ Wire·２ ") === "mosswire2", "full-width, punctuation, spaces: " + N("  Ｍoss ＆ Wire·２ "));
    ok(N("Café-Déjà vu") === "cafedejavu", "accents: " + N("Café-Déjà vu"));
    ok(N("清华 · 大学（北京）") === "清华大学北京", "CJK punctuation: " + N("清华 · 大学（北京）"));
    ok(N("3-02") === N("3·02") && N("3 02") === "302", "numbers");
    ok(N("") === "" && N(null) === "" && N(undefined) === "", "empty");
    var ents = [
      { id: "kelp", name: { en: "Kelp & Co. Bioplastics", cn: "海带生物塑料" }, short: "Kelp", room: "HALL", booth: "01", tags: ["materials"] },
      { id: "tinker", name: { en: "Tinker Tide Robotics", cn: "潮玩机器人" }, short: "Tinker", room: "202", booth: "01", tags: ["robotics", "kids"] },
      { id: "kelpies", name: { en: "Kelpies Choir", cn: "海藻合唱团" }, short: "Kelpies", room: "202", booth: "02", tags: ["music"] },
      { id: "echo", name: "Echo Pottery", room: "203", booth: "01", tags: ["clay", "craft"] },
      { id: "loom", name: { en: "The Loom House", cn: "织机屋" }, room: "203", booth: "02", floor: "2F", tags: ["craft"] }
    ];
    var rooms = [{ id: "HALL", label: "H1", name: { en: "Grand Hall", cn: "大展厅" } }, { id: "202", label: "202", name: { en: "Tinkering Room", cn: "拆装室" } },
                 { id: "203", label: "203", name: { en: "Clay Room", cn: "陶室" } }];
    var s = EVK.search.create(ents, { rooms: rooms, groups: [{ words: ["理工", "tech"], ids: ["tinker", "kelp"] }, [["手作", "handmade"], ["echo"]], { words: ["Space"], tags: ["music"] }] });
    var r = s.query("kelp");
    ok(ids(r) === "kelp,kelpies", "exact name first, prefix second: " + ids(r));
    ok(r[0].score === 4 && r[0].why === "name" && r[1].score === 3 && r[1].why === "name-prefix", "score and why");
    ok(ids(s.query("KELP & CO")) === "kelp", "case, spaces, punctuation");
    ok(ids(s.query("海带")) === "kelp", "chinese prefix");
    ok(ids(s.query("ｋｅｌｐ")) === "kelp,kelpies", "full-width query");
    ok(ids(s.query("ttr")) === "tinker", "initials: " + ids(s.query("ttr")));
    ok(ids(s.query("loom")) === "loom", "leading The ignored");
    ok(ids(s.query("理工")) === "kelp,tinker" && s.query("理工")[0].why === "group", "group word in venue order: " + ids(s.query("理工")));
    ok(ids(s.query("handmade")) === "echo", "group as array pair");
    ok(ids(s.query("space")) === "kelpies", "group by tag");
    ok(ids(s.query("202")) === "tinker,kelpies" && s.query("202")[0].why === "room", "room number lists the room: " + ids(s.query("202")));
    ok(ids(s.query("20")) === "tinker,kelpies,echo,loom", "room prefix: " + ids(s.query("20")));
    ok(ids(s.query("Tinkering")) === "tinker,kelpies", "room name");
    ok(ids(s.query("20301")) === "echo" && ids(s.query("203-01")) === "echo", "room + booth: " + ids(s.query("203-01")));
    ok(ids(s.query("2f")) === "loom", "floor key");
    ok(ids(s.query("hall")) === "kelp", "room name of another room");
    ok(ids(s.query("ioplas")) === "kelp" && s.query("ioplas")[0].why === "contains", "contains");
    ok(ids(s.query("kelp bio")) === "kelp" && s.query("kelp bio")[0].why === "words", "several words AND-ed: " + ids(s.query("kelp bio")));
    ok(ids(s.query("craft 203")) === "echo,loom", "words across tag and room: " + ids(s.query("craft 203")));
    ok(s.query("").length === 5 && s.query("")[0].why === "all" && ids(s.query(" · ")) === ids(s.query("")), "empty query lists everything");
    ok(ids(s.query("", { limit: 2 })) === "kelp,tinker", "limit");
    ok(s.query("zzz").length === 0 && s.best("zzz") === null, "no match");
    ok(s.best("tinker") === ents[1] && s.best("") === null, "best() returns the entity itself, null for an empty box");
    var fl = [{ id: "2F", short: { en: "2F", cn: "2 层" }, name: { en: "Second Floor", cn: "二层" }, rooms: [{ id: "203", label: "203", name: { en: "Clay Room", cn: "陶室" } }] },
              { id: "1F", short: { en: "1F", cn: "1 层" }, name: { en: "First Floor", cn: "一层" }, rooms: [{ id: "HALL", label: "H1", name: { en: "Grand Hall", cn: "大展厅" } }] }];
    var sf = EVK.search.create(ents, { rooms: fl });
    ok(ids(sf.query("二层")) === "echo,loom" && ids(sf.query("2 层")) === "echo,loom", "a floor's cn name and short find what stands on it: " + ids(sf.query("二层")));
    ok(ids(sf.query("second floor")) === "echo,loom" && ids(sf.query("一层")) === "kelp", "a floor's en name; another floor");
    ok(ids(EVK.search.create(ents, { rooms: fl.map(function (x) { return { id: x.id, rooms: x.rooms }; }) }).query("二层")) === "", "floors without short / name only answer to their id");
    var st = EVK.search.create(ents, { tags: { craft: { en: "Handmade", cn: "手作" }, materials: "Materials" } });
    ok(ids(st.query("手作")) === "echo,loom" && st.query("手作")[0].why === "tag", "the word for a tag finds its entities: " + ids(st.query("手作")));
    ok(ids(st.query("handmade")) === "echo,loom", "…in the other language too");
    ok(ids(st.query("craft")) === "echo,loom", "the tag id still works");
    var f = EVK.search.create([{ id: "a", name: "甲", alias: ["jia", "first"] }, { id: "b", name: "乙", alias: "yi" }], { fields: ["alias"] });
    ok(ids(f.query("jia")) === "a" && f.query("jia")[0].why === "name", "fields count as names");
    ok(ids(f.query("甲")) === "a" && ids(f.query("乙")) === "b", "string names work for both languages");
    console.log(fails ? fails + " of " + n + " checks FAILED" : "search.js selftest: " + n + " checks passed");
    if (fails) process.exit(1);
  }
})();
