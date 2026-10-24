/* event-venue-kit · assets/starter/starter.js — the behaviour of the starter pages
   ----------------------------------------------------------------------------------------------
   scripts/starter.py writes the markup (complete and readable without this file); this file only enhances it. One file, three
   pages, told apart by <body data-page="home | map | entity">. The data is window.EVK_VENUE (data/venue.js: a script, not a
   fetch, so the pages also work from file://). Every control that needs this file is [hidden] in the markup and shown here
   (ux-contracts ZS-3). Load order: data/venue.js, then the engine (tones, search, spring, sheet, part-nav, wayfind, venue-map),
   then this file.

   home    the grouped list is filtered in place by a search box, a floor control and (when the grid is grouped by tag or by room,
           event.group_by) a group control (SE-4: hide, never reshuffle; an empty group hides with its last item); ?g=<group key>
           opens the page filtered to one group (with group_by floor the key is the floor id); Enter opens the first visible entry;
           a live map preview opens the map page on a tap.
   map     the map, the floor control, a search box, and two non-modal sheets: one for a room or an entity, one for directions
           (start select + target search + Back / Overview / Next + a polite live region). The state is in the URL:
              ?to=<entity>[&from=<start id>][&via=lift]   the directions sheet; with `from` the route starts at once
              ?s=<entity>   an entity selected     ?r=<room or area>   a room opened     ?f=<floor>   one floor only
           one sheet at a time, priority to > s > r (f only chooses the floor underneath); every lookup keyed by a URL value goes through has() (UR-2); route state is mirrored with
           history.replaceState (UR-3); the last start is remembered in localStorage, inside try/catch and checked on read (UR-4).
   entity  a near view: a small map on the entity's floor, the room framed, the entity selected and kept selected; and the "How to get here"
           steps (.sp-route[data-from]): written here from the start named in data-from when the build had no Node to write them.
   all     a location code is "<floor short>·<booth>" everywhere (code()); fitDrag() makes the map hint say what one finger really does
           (VenueMap dragMode(), else the build's body[data-drag]).

   The words this file speaks are in UI below (key → {en, cn}); scripts/starter.py reads the same block for the static markup, so
   change a word there and rebuild. Bilingual pairs are always written PRIMARY LANGUAGE FIRST: the lead is <html data-evk-lead>.
   Keep the hooks (ids, data-* attributes, class names starting sp- and evk-) when you restyle: the CSS is assets/starter.css.
   ---------------------------------------------------------------------------------------------- */
(function () {
  "use strict";

  /* ---- the words: {thing} {things} {Thing} are the venue's term for an entity (terms.booth), in the language being written ---- */
  var UI = /* ui:begin */ {
    "skip":          {"en": "Skip to content", "cn": "跳到正文"},
    "nav_label":     {"en": "Pages", "cn": "页面"},
    "nav_guide":     {"en": "Guide", "cn": "导览"},
    "nav_map":       {"en": "Map", "cn": "地图"},
    "sample_tag":    {"en": "Schematic", "cn": "示意"},
    "sample_text":   {"en": "Sample venue and entries: not the real plan.", "cn": "场地与展位均为示意，不代表实际安排。"},
    "tba":           {"en": "TBA", "cn": "待定"},
    "eyebrow_event": {"en": "Event guide", "cn": "活动导览"},
    "f_date":        {"en": "Date", "cn": "日期"},
    "f_time":        {"en": "Time", "cn": "时间"},
    "f_where":       {"en": "Where", "cn": "地点"},
    "st_floors":     {"en": "Floors", "cn": "层楼"},
    "st_rooms":      {"en": "Rooms", "cn": "个房间"},
    "open_map":      {"en": "Open the map", "cn": "打开地图"},
    "find_cta":      {"en": "Find", "cn": "查找"},
    "h_map":         {"en": "Map", "cn": "地图"},
    "map_hint":      {"en": "Drag to rotate", "cn": "拖动旋转"},
    "map_hint_pan":  {"en": "Drag to pan", "cn": "拖动平移"},
    "map_drag":      {"en": "Drag to rotate, pinch to zoom", "cn": "拖动旋转，双指缩放"},
    "map_drag_pan":  {"en": "Drag to pan, pinch to zoom", "cn": "拖动平移，双指缩放"},
    "map_what":      {"en": "3D floor guide", "cn": "立体楼层导览"},
    "map_what_pan":  {"en": "Oblique floor guide", "cn": "斜视楼层导览"},
    "map_what_plan": {"en": "Floor plan", "cn": "楼层平面图"},
    "map_view":      {"en": "3D view", "cn": "立体图"},
    "map_view_pan":  {"en": "oblique view", "cn": "斜视图"},
    "map_view_plan": {"en": "plan view", "cn": "平面图"},
    "reset":         {"en": "Reset", "cn": "复位"},
    "cv_preview":    {"en": "{what}. {hint}. Tap a marker to open the map with that {thing} selected; the list below has the same information.", "cn": "{what}：{hint}。点一个标记，会在地图页选中该{thing}；下方的列表列出全部{things}。"},
    "cv_map":        {"en": "{what}. {drag}, or use the arrow keys. Tap a room or marker to see its {things}; the directory below lists every {thing}.", "cn": "{what}：{drag}，方向键也可以操作。点房间或标记查看{things}，下方的名录列出每个{thing}。"},
    "cv_near":       {"en": "{floor} {view}: {name} is {where}, marked. {hint}.", "cn": "{floor}{view}：{name}在{where}，已标出。{hint}。"},
    "search_label":  {"en": "Search", "cn": "搜索"},
    "search_ph":     {"en": "Name, category, room, e.g. {ex}…", "cn": "名称、类别、房号，例如{ex}…"},
    "floor_label":   {"en": "Floor", "cn": "楼层"},
    "group_label":   {"en": "Group", "cn": "分组"},
    "grp_other":     {"en": "Other", "cn": "其他"},
    "all":           {"en": "All", "cn": "全部"},
    "empty_title":   {"en": "No match.", "cn": "没有找到匹配项。"},
    "empty_hint":    {"en": "Try a name, a category or a room number, or clear the floor filter.", "cn": "可以试试名称、类别或房号，也可以清掉楼层筛选。"},
    "live_n":        {"en": "{n} results.", "cn": "{n} 个结果。"},
    "live_none":     {"en": "No matches.", "cn": "没有找到匹配的结果。"},
    "n_things":      {"en": "{n} {things}", "cn": "{n} 个{things}"},
    "map_intro":     {"en": "{drag}. Tap a room or a marker, then Directions.", "cn": "{drag}。点房间或标记，再点“路线导航”。"},
    "btn_directions":{"en": "Directions", "cn": "路线导航"},
    "btn_go_here":   {"en": "Directions", "cn": "怎么走"},
    "btn_details":   {"en": "Details", "cn": "详情"},
    "close":         {"en": "Close", "cn": "关闭"},
    "dir_title":     {"en": "Directory", "cn": "名录"},
    "noscript_map":  {"en": "The floor map and directions need JavaScript. The directory below lists where every {thing} is.", "cn": "楼层图和路线导航需要开启 JavaScript；下方的名录列出了每个{thing}的位置。"},
    "open_floor":    {"en": "Open floor", "cn": "本层开放区"},
    "route_title":   {"en": "Directions", "cn": "路线导航"},
    "route_from":    {"en": "I am at", "cn": "我现在在"},
    "route_to":      {"en": "Go to", "cn": "去哪里"},
    "route_to_ph":   {"en": "Name, category, room…", "cn": "名称、类别、房号…"},
    "route_go":      {"en": "Go", "cn": "出发"},
    "route_lift":    {"en": "Lifts only (step-free)", "cn": "只乘电梯（无台阶）"},
    "grp_entrance":  {"en": "Entrances", "cn": "入口"},
    "grp_lobby":     {"en": "Lobbies", "cn": "大堂"},
    "grp_room":      {"en": "Rooms", "cn": "房间"},
    "grp_area":      {"en": "Open areas", "cn": "开放区"},
    "route_err":     {"en": "We couldn't work out this route. Try another starting point, or find the {thing} in the directory below.", "cn": "暂时算不出这条路。换个起点试试，或到下方名录里看{thing}的位置。"},
    "route_err_to":  {"en": "Choose where you are going: type a name, a category or a room, then pick one from the list.", "cn": "请先选好要去的地方：输入名称、类别或房号，再从列表里选一个。"},
    "back":          {"en": "Back", "cn": "上一步"},
    "overview":      {"en": "Overview", "cn": "全览"},
    "next":          {"en": "Next", "cn": "下一步"},
    "again":         {"en": "Change route", "cn": "重新选择"},
    "route_fine":    {"en": "Distances are approximate. On site, follow the signs.", "cn": "距离为约数；现场以指示牌为准。"},
    "route_fine_s":  {"en": "Worked out from the schematic plan; distances are approximate. On site, follow the signs.", "cn": "按示意平面算出，距离为约数；现场以指示牌为准。"},
    "route_sum":     {"en": "To {name}: about {m} m, {n} steps.", "cn": "去{name}，全程约 {m} 米，共 {n} 步。"},
    "say_step":      {"en": "Step {i} of {n}: {text}", "cn": "第 {i} 步，共 {n} 步：{text}"},
    "say_all":       {"en": "{name}, about {m} m in total, {n} steps.", "cn": "{name}，全程约 {m} 米，共 {n} 步。"},
    "say_sel":       {"en": "{name} selected: {where}.", "cn": "已选中{name}：{where}。"},
    "say_floor":     {"en": "Showing {floor} only.", "cn": "只显示{floor}。"},
    "say_room":      {"en": "{name} selected, {k} {things}.", "cn": "已选中{name}，{k} 个{things}。"},
    "same_title":    {"en": "{k} {things} here", "cn": "这里的 {k} 个{things}"},
    "same_current":  {"en": "current", "cn": "当前"},
    "none_here":     {"en": "No {things} here.", "cn": "这里没有{thing}。"},
    "none_hint":     {"en": "Tap another room or a marker.", "cn": "点其他房间或标记看看。"},
    "m_thing":       {"en": "{Thing}", "cn": "{thing}"},
    "m_floor":       {"en": "Floor", "cn": "楼层"},
    "m_room":        {"en": "Room", "cn": "房间"},
    "m_area":        {"en": "Area", "cn": "区域"},
    "e_about":       {"en": "About", "cn": "简介"},
    "e_where":       {"en": "Where", "cn": "在哪"},
    "e_route":       {"en": "How to get here", "cn": "怎么走"},
    "e_route_from":  {"en": "From the {name}", "cn": "从{name}出发"},
    "e_route_map":   {"en": "Show on the map", "cn": "在地图上看路线"},
    "e_ph_flag":     {"en": "Placeholder", "cn": "示意"},
    "e_ph_text":     {"en": "The description of {name} will be added here before the event.", "cn": "{name}的介绍会在活动前补充到这里。"},
    "blk_table":     {"en": "Table", "cn": "表格"},
    "e_on_map":      {"en": "On the map", "cn": "在地图上看"},
    "e_prev":        {"en": "Previous", "cn": "上一个"},
    "e_next":        {"en": "Next", "cn": "下一个"},
    "e_pager":       {"en": "Previous and next {thing}", "cn": "上一个和下一个{thing}"},
    "e_toc":         {"en": "On this page", "cn": "本页内容"},
    "e_back":        {"en": "All {things}", "cn": "全部{things}"},
    "meta_home":     {"en": "Guide to {event} at {venue}: {n} {things} on {k} floors, searchable, with a 3D floor map and step-by-step directions.", "cn": "{event}活动导览：{venue}，{k} 层、{n} 个{things}；可搜索，另有 3D 楼层图和分步路线。"},
    "meta_map":      {"en": "Floor map of {venue}: drag to rotate, tap a room or a {thing}, and get step-by-step directions.", "cn": "{venue}的楼层图：拖动旋转，点房间或{thing}，查看分步路线。"},
    "meta_entity":   {"en": "{name}: {where}. {event}.", "cn": "{name}：{where}。{event}。"}
  } /* ui:end */;

  var V = window.EVK_VENUE, EVK = window.EVK, body = document.body, root = document.documentElement;
  if (!V || !EVK || !EVK.wayfind || !body) return;                  // the static page is complete without this file
  var PAGE = body.getAttribute("data-page"), ROOT = body.getAttribute("data-root") || "";
  var LEAD = root.getAttribute("data-evk-lead") === "zh" ? "zh" : "en";
  var CJK = /[㐀-鿿豈-﫿]/;
  var reduce = !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);

  /* ---------------------------------------------------------------- small helpers */
  function $(id) { return document.getElementById(id); }
  function qa(sel, from) { return [].slice.call((from || document).querySelectorAll(sel)); }
  function has(o, k) { return k != null && Object.prototype.hasOwnProperty.call(o, k); }            // UR-2
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }
  function plural(w) { return /[^aeiou]y$/i.test(w) ? w.slice(0, -1) + "ies" : /(s|x|ch|sh)$/i.test(w) ? w + "es" : w + "s"; }
  function spaced(t) { return EVK.spaced ? EVK.spaced(t) : t; }
  function store(key, val) {                                          // UR-4: storage may be missing, full or blocked
    try { if (val === undefined) return localStorage.getItem(key); localStorage.setItem(key, val); } catch (e) { /* carry on without it */ }
    return null;
  }
  function enc(s) { return encodeURIComponent(s); }

  /* ---------------------------------------------------------------- the model, the words */
  var wf = EVK.wayfind.create(V), model = wf.model;
  var TERMS = model.terms || { booth: { en: "booth", cn: "展位" }, room: { en: "Room", cn: "" } };

  function words(key, vars, l) {                                      // one string in language l ("en" | "zh"; default the lead)
    l = l || LEAD;
    var u = has(UI, key) ? UI[key] : null, s = u ? (l === "zh" ? u.cn : u.en) : key;
    var one = vars && (String(vars.n) === "1" || String(vars.k) === "1");                                    // "1 booth", "3 booths"
    var v = { thing: l === "zh" ? TERMS.booth.cn : TERMS.booth.en, things: l === "zh" ? TERMS.booth.cn : one ? TERMS.booth.en : plural(TERMS.booth.en) };
    v.Thing = cap(v.thing); v.Things = cap(v.things);
    s = s.replace(/\{(\w+)\}/g, function (m, k) { return vars && has(vars, k) ? vars[k] : has(v, k) ? v[k] : m; });
    return l === "zh" ? spaced(s) : s;
  }
  function S(key, vars) { return words(key, vars, LEAD); }
  function S2(key, vars) { return words(key, vars, LEAD === "zh" ? "en" : "zh"); }
  function LS(en, cn) {                                               // [[text, class, lang], …] primary first; one line when they match or one is missing
    en = en || ""; cn = cn || "";
    if (!en || !cn || en === cn) { var t = en || cn; return [CJK.test(t) ? [spaced(t), "cn", "zh-CN"] : [t, "en", "en"]]; }
    var a = [spaced(cn), "cn", "zh-CN"], b = [en, "en", "en"];
    return LEAD === "zh" ? [a, b] : [b, a];
  }
  function spans(en, cn) { return LS(en, cn).map(function (x) { return '<span class="' + x[1] + '" lang="' + x[2] + '">' + esc(x[0]) + "</span>"; }).join(""); }
  function P(key, vars) { return spans(words(key, vars, "en"), words(key, vars, "zh")); }
  function SP(key, vars) {                                            // a sentence in the lead language, the other under it (muted, a block)
    var a = LEAD === "zh" ? "zh" : "en", b = a === "zh" ? "en" : "zh";
    return '<span lang="' + lang(a) + '">' + esc(words(key, vars, a)) + '</span><span class="sp-2nd" lang="' + lang(b) + '">' + esc(words(key, vars, b)) + "</span>";
  }
  function lang(l) { return l === "zh" ? "zh-CN" : "en"; }

  /* ---------------------------------------------------------------- places and names (the model's entities and rooms) */
  function nameOf(e, l) { return (l || LEAD) === "zh" ? e.name.cn : e.name.en; }
  /* floors: `short` ("4F" / "4 层") is the floor in chips, tags, location lines and the router's sentences; `name` ("Fourth Floor" / "四层")
     is for headings. Read from the venue as written (a missing short: the id, and the level + " 层", as the router says it). */
  var FL = {};
  (V.floors || []).forEach(function (f) {
    var id = String(f.id), nm = pairOf(f.name, id), lvl = +f.level;
    FL[id] = { name: nm, short: f.short ? pairOf(f.short, id) : { en: id, cn: lvl >= 1 ? lvl + " 层" : (f.name ? nm.cn : id) } };
  });
  function pairOf(v, dflt) {                                          // a text ("both languages" or {en, cn}, either missing) -> {en, cn}
    if (typeof v === "string") return { en: v, cn: v };
    var en = v && v.en ? String(v.en) : "", cn = v && v.cn ? String(v.cn) : "";
    return { en: en || cn || dflt, cn: cn || en || dflt };
  }
  function floorName(fid, l) { var f = has(FL, fid) ? FL[fid].name : null; return f ? ((l || LEAD) === "zh" ? f.cn : f.en) : fid; }
  function floorShort(fid, l) { var f = has(FL, fid) ? FL[fid].short : null; return f ? ((l || LEAD) === "zh" ? f.cn : f.en) : fid; }
  function roomOf(e) { return e.room && has(model.roomById, e.room) ? model.roomById[e.room] : null; }
  /* a room is spoken by its number when its label is one (Room 203 / 203), else by its name; an area by its name */
  function placeName(r, l) {
    if (!r) return "";
    l = l || LEAD;
    if (r.area) return l === "zh" ? r.name.cn : cap(r.name.en);
    if (/^\d+$/.test(r.label)) return l === "zh" ? r.label : (TERMS.room.en ? TERMS.room.en + " " : "") + r.label;
    return l === "zh" ? r.name.cn : r.name.en;
  }
  function boothName(e, l) { l = l || LEAD; return e.booth ? (l === "zh" ? e.booth + " 号" + TERMS.booth.cn : TERMS.booth.en + " " + e.booth) : ""; }
  function whereText(e, l) {
    var t = [floorShort(e.floor, l), placeName(roomOf(e), l), boothName(e, l)].filter(Boolean).join(" · ");
    return (l || LEAD) === "zh" ? spaced(t) : t;
  }
  /* a location code is '<floor short>·<booth>' ('2F·L02', '2 层·L02'), one format everywhere; when booth numbers repeat on a floor (numbered per room)
     the room's number goes between them ('2F·203·02'), for the whole venue. An area's label is a display name (the map plate, headings), never part of a code. */
  var CODE_ROOM = (function () {
    var seen = {}, dup = false;
    model.entities.forEach(function (e) { var k = e.floor + "\u0000" + String(e.booth || "").toLowerCase(); if (has(seen, k)) dup = true; seen[k] = 1; });
    return dup;
  })();
  function code(e) {
    var r = roomOf(e), front = floorShort(e.floor, LEAD);
    if (CODE_ROOM && r && !r.area && r.label) front += "·" + r.label;
    return { front: spaced(front), booth: e.booth || "" };
  }
  function tagHtml(e) {                                               // the floor part is the quiet one
    var c = code(e);
    return c.booth ? "<small>" + esc(c.front) + "·</small>" + esc(c.booth) : esc(c.front);
  }
  function initial(e) {
    var n = e.name, t = LEAD === "zh" && CJK.test(n.cn) ? n.cn : (e.short || n.en || n.cn || "?");
    return t.trim().charAt(0).toUpperCase();
  }
  function pageOf(e) { return e.raw && e.raw["x-page"] ? ROOT + e.raw["x-page"] : ""; }
  function tone(el, e) { if (EVK.applyEntity && e.color) EVK.applyEntity(el, e.color); }

  /* ---------------------------------------------------------------- what one finger does on the map
     The build wrote it for the card's projection (body[data-drag]: rotate | pan, scripts/starter.py DRAG_OF); the map itself knows (VenueMap
     dragMode()). If the two ever differ the words on the page (the hint, the aria-labels, the intro) follow the map. */
  var DRAG = body.getAttribute("data-drag") === "pan" ? "pan" : "rotate";
  function fitDrag(map) {
    var m = map && typeof map.dragMode === "function" ? map.dragMode() : null;
    if ((m !== "rotate" && m !== "pan") || m === DRAG) return;
    var pairs = [];                                                   // the longer sentence first: "Drag to rotate, pinch to zoom" contains "Drag to rotate"
    ["map_drag", "map_hint"].forEach(function (k) {
      ["en", "zh"].forEach(function (l) {
        var a = words(k + (DRAG === "pan" ? "_pan" : ""), null, l), b = words(k + (m === "pan" ? "_pan" : ""), null, l);
        if (a && b && a !== b) pairs.push([a, b]);
      });
    });
    function swap(t) { pairs.forEach(function (p) { t = t.split(p[0]).join(p[1]); }); return t; }
    var w = document.createTreeWalker(body, NodeFilter.SHOW_TEXT, null), n, nodes = [];
    while ((n = w.nextNode())) if (!/^(SCRIPT|STYLE)$/.test(n.parentNode.nodeName)) nodes.push(n);
    nodes.forEach(function (t) { var v = swap(t.nodeValue); if (v !== t.nodeValue) t.nodeValue = v; });
    qa("[aria-label]").forEach(function (el) { var a = el.getAttribute("aria-label"), v = swap(a); if (v !== a) el.setAttribute("aria-label", v); });
    DRAG = m; body.setAttribute("data-drag", m);
  }

  /* ---------------------------------------------------------------- written directions (the entity page's "How to get here"):
     the same markup as scripts/starter.py steps_ol(), for a build that had no Node to write it */
  function inl(en, cn) {                                              // a text as two spans, the second muted on its own line
    return LS(en, cn).map(function (x, i) { return "<span" + (i ? ' class="sp-2nd"' : "") + ' lang="' + x[2] + '">' + esc(x[0]) + "</span>"; }).join("");
  }
  function stepsHtml(steps) {
    var lis = steps.filter(function (s) { return s.en.text || s.cn.text; }).map(function (s) {
      var head = s.en.head || s.cn.head ? '<strong class="t">' + inl(s.en.head, s.cn.head) + "</strong>" : "";
      return "<li" + (s.kind === "stairs" || s.kind === "lift" ? ' class="is-climb"' : "") + ">" + head + inl(s.en.text, s.cn.text) + "</li>";     // DR-6: a climb step is marked
    });
    return lis.length ? '<ol class="evk-r-steps">' + lis.join("") + "</ol>" : "";
  }

  /* ---------------------------------------------------------------- live region, page chrome */
  var liveT = 0;
  function say(text) {                                                // polite, one sentence, a beat after the change (LV)
    var live = $("live"); if (!live) return;
    clearTimeout(liveT); live.textContent = "";
    liveT = setTimeout(function () { live.textContent = text; }, 40);
  }
  function barH() { var b = document.querySelector(".evk-bar"); return b ? b.getBoundingClientRect().height : 0; }
  function scrollTo(el) {                                             // MS-6: bring the map under the bar, 40 px dead zone, no smooth before load
    if (!el) return;
    var top = el.getBoundingClientRect().top + window.pageYOffset - barH() - 8;
    if (Math.abs(window.pageYOffset - top) < 40) return;
    window.scrollTo({ top: top, behavior: reduce || document.readyState !== "complete" ? "auto" : "smooth" });
  }
  function show(el) { if (el) el.hidden = false; }

  /* ---------------------------------------------------------------- a search box with a result list (page search, directions target) */
  var searchOpts = { rooms: model.floors, groups: has(V, "x-groups") && Array.isArray(V["x-groups"]) ? V["x-groups"] : [] };
  var search = EVK.search ? EVK.search.create(model.entities, searchOpts) : null;

  function combo(input, list, onPick, o) {
    o = o || {};
    var shown = [], active = -1, id = list.id;
    function hide() { list.hidden = true; input.setAttribute("aria-expanded", "false"); input.removeAttribute("aria-activedescendant"); }
    function paint() {
      qa("li", list).forEach(function (li, i) { li.setAttribute("aria-selected", String(i === active)); });
      if (active >= 0) input.setAttribute("aria-activedescendant", id + "-" + active); else input.removeAttribute("aria-activedescendant");
    }
    function render() {
      list.textContent = "";
      var text = input.value;
      if (!search || !text.trim()) { shown = []; active = -1; hide(); return; }
      shown = search.query(text, { limit: o.limit || 8 }).filter(function (r) { return r.score > 0; });
      if (!shown.length) {
        var none = document.createElement("li"); none.className = "none"; none.setAttribute("role", "status");
        none.innerHTML = SP("empty_hint");
        list.appendChild(none);
      }
      shown.forEach(function (r, i) {
        var e = r.entity, li = document.createElement("li"), pair = LS(e.name.en, e.name.cn);
        li.id = id + "-" + i; li.setAttribute("role", "option"); li.setAttribute("aria-selected", String(i === active));
        li.setAttribute("data-entity-color", e.color);
        li.innerHTML = '<span class="evk-mark" aria-hidden="true"></span><span class="nm"><b></b><small></small></span><span class="evk-tag">' + tagHtml(e) + "</span>";
        li.querySelector(".evk-mark").textContent = initial(e);
        var b = li.querySelector("b"), sm = li.querySelector("small");
        b.textContent = spaced(pair[0][0]); b.setAttribute("lang", pair[0][2]);
        if (pair[1]) { sm.textContent = pair[1][0]; sm.setAttribute("lang", pair[1][2]); } else sm.remove();
        li.addEventListener("pointerdown", function (ev) { ev.preventDefault(); });                // keep the focus in the box
        li.addEventListener("click", function () { pick(e); });
        list.appendChild(li);
      });
      if (EVK.applyEntities) EVK.applyEntities(list);
      list.hidden = false; input.setAttribute("aria-expanded", "true"); paint();
    }
    function pick(e) { hide(); active = -1; shown = []; onPick(e); }
    input.addEventListener("input", function () { active = -1; if (o.onInput) o.onInput(); render(); });
    input.addEventListener("keydown", function (ev) {
      if ((ev.key === "ArrowDown" || ev.key === "ArrowUp") && shown.length) {
        ev.preventDefault();
        active = (active + 1 + (ev.key === "ArrowDown" ? 1 : -1) + shown.length + 1) % (shown.length + 1) - 1;      // -1 (the box itself) … last, round and round
        paint();
      } else if (ev.key === "Enter" && !list.hidden && shown.length) {
        ev.preventDefault(); pick((active >= 0 ? shown[active] : shown[0]).entity);                                  // SE-6: Enter takes the first result
      } else if (ev.key === "Escape" && !list.hidden) {
        ev.stopPropagation(); hide();
      }
    });
    input.addEventListener("blur", function () { setTimeout(hide, 150); });
    input.addEventListener("focus", function () { if (input.value.trim()) render(); });
    return { render: render, hide: hide };
  }

  /* ================================================================== home */
  function home() {
    var find = $("find"), q = $("q"), empty = $("empty"), count = $("shown"), seg = $("seg-floor"), gseg = $("seg-group");
    var host = $("booths"), mode = host && host.getAttribute("data-group") || "floor";                     // event.group_by: floor | tag | room
    var items = qa("#booths li[data-id]"), groups = qa("#booths .sp-group"), state = { q: "", floor: "", g: "" }, timer = 0;
    function press(box, v) { if (box) qa("button", box).forEach(function (x) { x.setAttribute("aria-pressed", String((x.getAttribute("data-v") || "") === v)); }); }     // MP-8: an aria-pressed group
    function known(box, v) { return !!box && qa("button", box).some(function (x) { return x.getAttribute("data-v") === v; }); }
    function syncG() {                                                                                    // ?g= mirrors the group (UR-3: replaceState, only our own parameter)
      try {
        var u = new URL(location.href), v = mode === "floor" ? state.floor : state.g;
        if (v) u.searchParams.set("g", v); else u.searchParams.delete("g");
        history.replaceState(null, "", u.pathname + (u.searchParams.toString() ? "?" + u.searchParams.toString() : "") + u.hash);
      } catch (x) { /* the page works without it */ }
    }
    if (find && search && q) {
      show(find);
      var apply = function () {
        var hit = null;
        if (state.q.trim()) { hit = {}; search.query(state.q).forEach(function (r) { if (r.score > 0) hit[r.entity.id] = true; }); }
        var n = 0;
        items.forEach(function (li) {
          var ok = (!hit || has(hit, li.getAttribute("data-id"))) && (!state.floor || li.getAttribute("data-floor") === state.floor) && (!state.g || li.getAttribute("data-g") === state.g);
          li.hidden = !ok; if (ok) n++;
        });
        groups.forEach(function (g) { g.hidden = !g.querySelector("li[data-id]:not([hidden])"); });       // SE-4: an empty group goes with its last item
        if (empty) empty.hidden = n > 0;
        if (count) count.textContent = n + " / " + items.length;
        clearTimeout(timer);                                                                              // LV-6: a pause of ~300 ms, then one sentence
        timer = setTimeout(function () { say(n ? S("live_n", { n: n }) : S("live_none")); }, 320);
      };
      q.addEventListener("input", function () { state.q = q.value; apply(); });
      q.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {                                                                         // SE-6: Enter opens the first visible result
          ev.preventDefault();
          var first = document.querySelector("#booths li[data-id]:not([hidden]) a");
          if (first && q.value.trim()) location.href = first.getAttribute("href");
        } else if (ev.key === "Escape" && q.value) { q.value = ""; state.q = ""; apply(); }
      });
      if (seg) qa("button", seg).forEach(function (b) {
        b.addEventListener("click", function () {
          state.floor = b.getAttribute("data-v") || "";
          press(seg, state.floor);
          if (mode === "floor") syncG();
          apply();
        });
      });
      if (gseg) qa("button", gseg).forEach(function (b) {
        b.addEventListener("click", function () {
          state.g = b.getAttribute("data-v") || "";
          press(gseg, state.g);
          syncG();
          apply();
        });
      });
      var g0 = new URLSearchParams(location.search).get("g");                                             // ?g=<key>: the page opens on one group (a key we do not know is ignored: UR-2)
      if (g0) {
        if (mode === "floor" && known(seg, g0)) { state.floor = g0; press(seg, g0); }
        else if (mode !== "floor" && known(gseg, g0)) { state.g = g0; press(gseg, g0); }
      }
      if (q.value) state.q = q.value;                                                                     // a browser may keep the box's text when you come back
      if (q.value || state.floor || state.g) apply();
    }

    var prev = $("preview");                                                                              // the map preview: a tap goes to the map page
    if (prev && EVK.VenueMap) {
      var canvas = prev.querySelector("canvas"), built = null;
      var go = function (qs) { location.href = ROOT + "map.html" + qs; };
      var build = function () {
        if (built) return;
        built = new EVK.VenueMap(canvas, V, {
          onSelect: function (id) { if (id) go("?s=" + enc(id)); },
          onRoom: function (rid) { go("?r=" + enc(rid)); },
          onFloor: function (fid) { go("?f=" + enc(fid)); }
        });
        fitDrag(built);
      };
      show(prev);
      if ("IntersectionObserver" in window) {
        var io = new IntersectionObserver(function (es) { if (es.some(function (x) { return x.isIntersecting; })) { io.disconnect(); build(); } }, { rootMargin: "300px" });
        io.observe(prev);
      } else build();
    }
  }

  /* ================================================================== entity page: the near view */
  function entityPage() {
    var id = body.getAttribute("data-entity"), e = has(model.entityById, id) ? model.entityById[id] : null, box = $("near");
    if (box && e && EVK.VenueMap) {
      var canvas = box.querySelector("canvas"), map = null;
      var build = function () {
        if (map) return;
        map = new EVK.VenueMap(canvas, V, {
          floor: e.floor, select: id, intro: false,
          onSelect: function () { map.select(id); },                  // the near view always points at this entity
          onRoom: function () {}, onFloor: function () {}
        });
        if (e.room) map.focusRoom(e.room);
        fitDrag(map);
      };
      show(box);
      if ("IntersectionObserver" in window) {
        var io = new IntersectionObserver(function (es) { if (es.some(function (x) { return x.isIntersecting; })) { io.disconnect(); build(); } }, { rootMargin: "300px" });
        io.observe(box);
      } else build();
    }
    qa(".sp-route[data-from]").forEach(function (rb) {                // "How to get here": the build writes the steps when Node was there; if not, write them now
      if (!e || rb.querySelector(".evk-r-steps")) return;
      var steps = null;
      try { var plan = wf.plan(rb.getAttribute("data-from"), id); steps = plan ? wf.describe(plan, "both") : null; } catch (x) { steps = null; }
      if (steps && steps.length) rb.innerHTML = stepsHtml(steps);
    });
    var toc = $("toc");                                               // the in-page contents list is the no-JS fallback of the reading navigator
    if (toc && EVK.partNav) toc.hidden = true;
  }

  /* ================================================================== map page */
  function mapPage() {
    if (!EVK.VenueMap || !EVK.Sheet) return;                          // the directory stays in the page (MP-2)
    var mapEl = $("map"), canvas = mapEl.querySelector("canvas");
    show(mapEl);                                                      // [hidden] in the markup (no empty box without JavaScript); shown before the map measures it
    var placeEl = $("sheet-place"), routeEl = $("sheet-route"), tools = $("tools");
    var state = { floor: null, sel: null, room: null, plan: null, step: -1, via: "stairs" };
    var floorBtns = qa("#seg-floor > button");
    var hasLift = Object.keys(model.connectors || {}).some(function (k) { var c = model.connectors[k]; return c.kind === "lift" && c.floors && c.floors.length > 1; });

    var map = new EVK.VenueMap(canvas, V, {
      onSelect: function (id) { if (state.plan) return; if (id) showBooth(id); else placeSheet.close(); },
      onRoom: function (rid) { if (state.plan) return; if (state.room === rid && !state.sel) placeSheet.close(); else showRoom(rid); },
      onFloor: function (fid) { if (state.plan) return; setFloor(fid); }
    });
    fitDrag(map);

    /* ---- the URL (UR-3): replaceState, hash kept, only our own parameters touched ---- */
    function syncUrl(p) {
      try {
        var u = new URL(location.href);
        ["s", "r", "f", "to", "from", "via"].forEach(function (k) { if (has(p, k)) { if (p[k]) u.searchParams.set(k, p[k]); else u.searchParams.delete(k); } });
        history.replaceState(null, "", u.pathname + (u.searchParams.toString() ? "?" + u.searchParams.toString() : "") + u.hash);
      } catch (x) { /* a sandboxed or old browser: the page works without it */ }
    }

    /* ---- floors (MP-8: an aria-pressed group; while a route runs none is pressed; pressing one ends the route) ---- */
    function paintFloor(v) { floorBtns.forEach(function (b) { b.setAttribute("aria-pressed", String(v !== undefined && b.getAttribute("data-v") === (v || ""))); }); }
    function setFloor(fid) {
      if (state.plan) clearRoute();
      if (placeSheet.isOpen) placeSheet.close();
      state.floor = fid && has(model.floorById, fid) ? fid : null;
      map.setFloor(state.floor); paintFloor(state.floor);
      syncUrl({ f: state.floor, s: null, r: null });
      if (state.floor) say(S("say_floor", { floor: floorShort(state.floor) }));
    }
    floorBtns.forEach(function (b) { b.addEventListener("click", function () { setFloor(b.getAttribute("data-v") || null); }); });

    /* ---- the place sheet: one entity, or one room; content swaps in place (SH-10, RF-4) ---- */
    var placeSheet = new EVK.Sheet(placeEl, {
      onClose: function () {                                          // the side effects of closing start with the gesture (SH-7)
        state.sel = null; state.room = null;
        map.select(null); map.focusRoom(null);
        syncUrl({ s: null, r: null });
      }
    });
    $("place-close").addEventListener("click", function () { placeSheet.close(); });

    function listHtml(list, cur) {
      return '<ol class="sp-list">' + list.map(function (e) {
        var pr = LS(e.name.en, e.name.cn);
        return '<li><button type="button" data-sel="' + esc(e.id) + '"' + (e.id === cur ? ' aria-current="true"' : "") + ' data-entity-color="' + esc(e.color) + '">' +
          '<span class="no">' + esc(e.booth || "") + '</span><span class="evk-mark" aria-hidden="true">' + esc(initial(e)) + '</span><span class="t" lang="' + pr[0][2] + '"' + (e.id === cur ? ' data-current="' + esc(S("same_current")) + '"' : "") + ">" + esc(spaced(pr[0][0])) + "</span></button></li>";
      }).join("") + "</ol>";
    }
    function bindList(host) {
      qa("button[data-sel]", host).forEach(function (b) { b.addEventListener("click", function () { showBooth(b.getAttribute("data-sel")); }); });
      if (EVK.applyEntities) EVK.applyEntities(host);
    }
    function boothsIn(rid) { return model.entities.filter(function (e) { return e.room === rid; }); }
    function fill(titleHtml, bodyHtml, color) {
      $("place-t").innerHTML = titleHtml;
      var b = $("place-body");
      if (color) b.setAttribute("data-entity-color", color); else { b.removeAttribute("data-entity-color"); b.removeAttribute("style"); }
      b.innerHTML = bodyHtml;
      if (color && EVK.applyEntity) EVK.applyEntity(b, color);
      return b;
    }

    function showBooth(id, o) {
      if (!has(model.entityById, id)) return;
      var e = model.entityById[id], r = roomOf(e), pn = LS(e.name.en, e.name.cn);
      o = o || {};
      if (routeSheet.isOpen) routeSheet.close(); else if (state.plan) clearRoute();
      state.sel = id; state.room = e.room;
      if (e.room) map.focusRoom(e.room); else { map.focusRoom(null); state.floor = e.floor; map.setFloor(e.floor); paintFloor(e.floor); }
      map.select(id);
      var others = e.room ? boothsIn(e.room) : [], page = pageOf(e);
      var kick = '<span class="sp-kick"><span class="evk-tag">' + tagHtml(e) + "</span><span>" + esc(whereText(e)) + "</span></span>";
      var head = kick + '<span class="sp-pname" lang="' + pn[0][2] + '">' + esc(spaced(pn[0][0])) + "</span>";
      var meta = '<div><dt>' + P("m_thing") + "</dt><dd>" + esc(e.booth || "—") + "</dd></div><div><dt>" + P("m_floor") + "</dt><dd>" + esc(floorShort(e.floor, LEAD)) + "</dd></div>" +
        (r ? "<div><dt>" + P(r.area ? "m_area" : "m_room") + "</dt><dd>" + esc(r.area ? placeName(r) : r.label) + "</dd></div>" : "");
      var b = fill(head,
        (pn[1] ? '<p class="sp-pname-2" lang="' + pn[1][2] + '">' + esc(pn[1][0]) + "</p>" : "") +
        '<div class="evk-entity-rule" aria-hidden="true"></div>' +
        '<dl class="sp-meta">' + meta + "</dl>" +
        '<div class="sp-actions"><button class="evk-btn evk-btn--primary" type="button" id="go"><span class="evk-k">' + P("btn_go_here") + "</span></button>" +
        (page ? '<a class="evk-btn evk-btn--quiet" href="' + esc(page) + '"><span class="evk-k">' + P("btn_details") + "</span></a>" : "") + "</div>" +
        (others.length > 1 ? '<section class="sp-same"><h3>' + esc(S("same_title", { k: others.length })) + "</h3>" + listHtml(others, id) + "</section>" : ""),
        e.color);
      bindList(b);
      $("go").addEventListener("click", function (ev) { openRoute(id, ev.currentTarget); });
      placeSheet.open({ launcher: o.launcher });
      say(S("say_sel", { name: nameOf(e), where: whereText(e) }));
      syncUrl({ s: id, r: null, to: null, from: null, via: null });
    }

    function showRoom(rid) {
      if (!has(model.roomById, rid)) return;
      var r = model.roomById[rid], list = boothsIn(rid), nm = LS(r.name.en, r.name.cn);
      if (routeSheet.isOpen) routeSheet.close(); else if (state.plan) clearRoute();
      state.sel = null; state.room = rid;
      map.select(null); map.focusRoom(rid);
      var lab = r.label || "";
      var head = '<span class="sp-kick">' + (lab ? '<span class="evk-tag">' + esc(lab) + "</span>" : "") + "<span>" + esc(floorShort(r.floor)) + '</span></span><span class="sp-pname" lang="' + nm[0][2] + '">' + esc(spaced(r.area ? placeName(r) : nm[0][0])) + "</span>";
      var b = fill(head,
        (nm[1] ? '<p class="sp-pname-2" lang="' + nm[1][2] + '">' + esc(r.area ? placeName(r, LEAD === "zh" ? "en" : "zh") : nm[1][0]) + "</p>" : "") +
        (list.length ? '<section class="sp-same"><h3>' + esc(S("same_title", { k: list.length })) + "</h3>" + listHtml(list, null) + "</section>"
                     : '<p class="evk-empty"><span>' + esc(S("none_here")) + "</span><span>" + esc(S("none_hint")) + "</span></p>"),
        null);
      bindList(b);
      placeSheet.open();
      say(S("say_room", { name: placeName(r), k: list.length }));
      syncUrl({ r: rid, s: null, to: null, from: null, via: null });
    }

    /* ---- the directions sheet ---- */
    var routeSheet = new EVK.Sheet(routeEl, { onClose: function () { clearRoute(); } });
    var from = $("from"), toQ = $("to-q"), toFound = $("to-found"), runEl = $("route-run"), form = $("route-form"), err = $("route-err"), lift = $("lift");
    var toId = null;
    $("route-close").addEventListener("click", function () { routeSheet.close(); });
    if (hasLift) { var lr = $("lift-row"); show(lr); }

    var startKey = "evk-from:" + location.pathname.replace(/[^/]*$/, "");
    (function fillFrom() {
      var groups = {};
      wf.starts().forEach(function (s) {
        if (s.kind === "entity") return;                              // a start is an entrance, a lobby, a room or an open area (DR-2: lobbies first)
        if (!groups[s.kind]) { groups[s.kind] = document.createElement("optgroup"); groups[s.kind].label = S("grp_" + s.kind); from.appendChild(groups[s.kind]); }
        var o = document.createElement("option"), n = LS(s.name.en, s.name.cn).map(function (x) { return x[0]; }).join(" · ");
        o.value = s.id;
        var fs = floorShort(s.floor, LEAD);                                                  // an entrance or lobby gets its floor after the name, unless the name already says it ("1F Lobby")
        o.textContent = s.kind === "room" ? s.label + " · " + n : n + (s.kind === "area" || s.kind === "room" || n.indexOf(fs) >= 0 ? "" : " (" + fs + ")");
        groups[s.kind].appendChild(o);
      });
      var saved = store(startKey), ids = qa("option", from).map(function (o) { return o.value; });
      from.value = saved && ids.indexOf(saved) >= 0 ? saved : (ids[0] || "");        // UR-4: only a stable fact, and only if it still exists; else the first entrance (or lobby)
    })();

    /* the target: a search box (EVK.search) whose pick sets toId; typing again forgets it */
    var target = combo(toQ, toFound, function (e) { toId = e.id; toQ.value = nameOf(e); err.hidden = true; }, { limit: 6, onInput: function () { toId = null; } });
    function setTarget(e) { toId = e ? e.id : null; toQ.value = e ? nameOf(e) : ""; }

    function openRoute(id, launcher) {
      if (placeSheet.isOpen) placeSheet.close();
      if (state.plan) clearRoute();
      if (id && has(model.entityById, id)) setTarget(model.entityById[id]);
      err.hidden = true; form.hidden = false; runEl.hidden = true; routeEl.classList.remove("is-running");
      routeSheet.open({ launcher: launcher });
    }
    $("open-route").addEventListener("click", function (ev) { openRoute(state.sel, ev.currentTarget); });
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var id = toId;
      if (!id && search && toQ.value.trim()) { var b = search.best(toQ.value); if (b) { id = b.id; setTarget(b); } }          // typed a full name and pressed Go
      if (!id) { err.innerHTML = SP("route_err_to"); err.hidden = false; toQ.focus(); return; }
      startRoute(from.value, id);
    });

    function startRoute(fromId, id) {
      var plan = null;
      state.via = lift && lift.checked ? "lift" : "stairs";
      try { plan = wf.plan(fromId, id, { via: state.via }); } catch (x) { plan = null; }
      if (!plan || !plan.steps || !plan.steps.length) { err.innerHTML = SP("route_err"); err.hidden = false; return; }        // DR-4: never silent
      err.hidden = true;
      store(startKey, fromId);
      state.plan = plan; state.step = 0; state.sel = id;
      map.select(null); map.focusRoom(null);
      map.lock(true); map.setRoute(plan, true); map.routeStep(0, true);                                       // DR-5: the route opens on step 1
      paintFloor(undefined);
      form.hidden = true; runEl.hidden = false; routeEl.classList.add("is-running");
      if (!routeSheet.isOpen) routeSheet.open();
      $("all").setAttribute("aria-pressed", "false");
      renderSteps(); announce();
      syncUrl({ to: id, from: fromId, via: state.via === "lift" ? "lift" : null, s: null, r: null });
      scrollTo(mapEl);
    }
    function clearRoute() {
      if (!state.plan) return;
      state.plan = null; state.step = -1; state.sel = null;
      map.setRoute(null); map.lock(false); map.select(null); map.setFloor(state.floor); paintFloor(state.floor);
      routeEl.classList.remove("is-running"); runEl.hidden = true; form.hidden = false;
      $("steps").textContent = "";
      syncUrl({ to: null, from: null, via: null });
    }
    $("again").addEventListener("click", function () {                // DR-11: back to the form, keeping the start and the target
      var keepFrom = from.value, keepTo = toId && has(model.entityById, toId) ? model.entityById[toId] : null;
      clearRoute(); from.value = keepFrom; setTarget(keepTo);
      $("route-t").focus({ preventScroll: true });
    });

    function renderSteps() {
      if (!state.plan) return;
      var steps = wf.describe(state.plan, "both"), ol = $("steps"), l = LEAD === "zh" ? "cn" : "en", o = LEAD === "zh" ? "en" : "cn";
      ol.className = "evk-steps" + (state.step < 0 ? " is-all" : "");
      var hadFocus = ol.contains(document.activeElement);
      ol.textContent = "";
      steps.forEach(function (s, i) {
        var li = document.createElement("li"), b = document.createElement("button");
        b.type = "button";
        b.innerHTML = '<span class="h"></span><span class="t"></span><span class="t2"></span>';
        var h = b.querySelector(".h"), t = b.querySelector(".t"), t2 = b.querySelector(".t2");
        h.textContent = s[l].head; h.setAttribute("lang", lang(LEAD));
        t.textContent = s[l].text; t.setAttribute("lang", lang(LEAD));
        t2.textContent = s[o].text; t2.setAttribute("lang", lang(LEAD === "zh" ? "en" : "zh"));
        b.addEventListener("click", function () { setStep(i === state.step ? -1 : i); });
        if (i === state.step) { li.className = "is-current"; b.setAttribute("aria-current", "step"); }     // DR-6: exactly one current step
        if (s.kind === "stairs" || s.kind === "lift") li.classList.add("is-climb");                      // DR-6: climbing is marked by colour AND by its words
        li.appendChild(b); ol.appendChild(li);
      });
      var e = model.entityById[state.sel];
      $("sum").textContent = S("route_sum", { name: nameOf(e), m: state.plan.metres, n: steps.length });
      $("prev").disabled = state.step <= 0; $("next").disabled = state.step >= steps.length - 1 && state.step >= 0;
      if (hadFocus) { var cur = ol.querySelector('[aria-current="step"]') || ol.querySelector("button"); if (cur) cur.focus({ preventScroll: true }); }   // DR-12: the list was rebuilt
    }
    function announce() {
      if (!state.plan) return;
      var steps = wf.describe(state.plan, "both"), e = model.entityById[state.sel], l = LEAD === "zh" ? "cn" : "en";
      say(state.step < 0 ? S("say_all", { name: nameOf(e), m: state.plan.metres, n: steps.length })
                         : S("say_step", { i: state.step + 1, n: steps.length, text: steps[state.step][l].text }));
    }
    function setStep(i) {
      state.step = i; map.routeStep(i < 0 ? null : i, true);
      $("all").setAttribute("aria-pressed", String(i < 0));
      renderSteps(); announce();
    }
    $("prev").addEventListener("click", function () { if (state.step > 0) setStep(state.step - 1); });
    $("next").addEventListener("click", function () { if (state.plan && state.step < state.plan.steps.length - 1) setStep(state.step + 1); });
    $("all").addEventListener("click", function () { setStep(state.step < 0 ? 0 : -1); });                  // DR-5: a one-tap, reversible overview

    /* ---- the page search: pick a result and its sheet opens ---- */
    var q = $("q");
    if (q && search) combo(q, $("found"), function (e) { q.value = ""; q.blur(); showBooth(e.id); scrollTo(mapEl); }, { limit: 8 });

    /* ---- the directory links select on the map without leaving the page; with a modifier key they open as links ---- */
    qa("#dir a[data-sel]").forEach(function (a) {
      a.addEventListener("click", function (ev) {
        if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
        ev.preventDefault(); showBooth(a.getAttribute("data-sel"), { launcher: a }); scrollTo(mapEl);
      });
    });
    qa("#dir a[data-room]").forEach(function (a) {
      a.addEventListener("click", function (ev) {
        if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
        ev.preventDefault(); showRoom(a.getAttribute("data-room")); scrollTo(mapEl);
      });
    });

    EVK.fitAbove.watch(map, [routeSheet, placeSheet]);                // MS-8: the directions sheet wins when both would cover the model
    if (EVK.applyEntities) EVK.applyEntities(document);
    show(tools);

    /* ---- the URL on load: f first (the floor underneath), then one of to(+from) > s > r ---- */
    var Q = new URLSearchParams(location.search);
    var pTo = Q.get("to"), pFrom = Q.get("from"), pS = Q.get("s"), pR = Q.get("r"), pF = Q.get("f");
    var startIds = {}; wf.starts().forEach(function (s) { startIds[s.id] = true; });
    if (pF && has(model.floorById, pF)) setFloor(pF);                                                       // the floor underneath: a route that ends comes back to it
    if (pTo && has(model.entityById, pTo)) {
      if (Q.get("via") === "lift" && lift && hasLift) lift.checked = true;
      if (pFrom && has(startIds, pFrom) && qa("option", from).some(function (o) { return o.value === pFrom; })) { from.value = pFrom; setTarget(model.entityById[pTo]); startRoute(pFrom, pTo); }
      else { openRoute(pTo); scrollTo(mapEl); }
    } else if (pS && has(model.entityById, pS)) { showBooth(pS); scrollTo(mapEl); }
    else if (pR && has(model.roomById, pR)) { showRoom(pR); scrollTo(mapEl); }
  }

  /* ================================================================== go */
  function run() {
    if (PAGE === "home") home();
    else if (PAGE === "map") mapPage();
    else if (PAGE === "entity") entityPage();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run); else run();
})();
