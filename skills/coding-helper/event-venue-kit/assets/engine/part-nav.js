/* event-venue-kit · part-nav.js — the reading navigator, plus the small page-chrome behaviours
   ----------------------------------------------------------------------------------------------
   EVK.partNav(root?, opts?) -> {update(), open(), close(), go(i), destroy(), parts, current}
       root = the element that holds the [data-part] sections ([data-report] if omitted)
       Builds (or fills in) one navigator button with one line <i> per part inside .evk-lines, a contents
       panel, and the .evk-progress line under the bar. Without JavaScript the page still has its in-page
       part index; everything this adds is hidden until it works.
       States, as classes you can restyle (the recipe may turn the lines into ticks, tabs, a ring, a rail):
         <i>.is-done   read           <i>.is-on   the part being read       panel a.is-on + aria-current="location"
         .evk-lines.is-many  more than 6 parts      --p 0..1 progress, --i current index (-1 before the first), --n count
         (--p / --i / --n are set on .evk-partnav, on .evk-progress and on the button, so CSS-only rings work)
       opts: parts "[data-part]", bar ".evk-bar", line 0.28, end 0.6, smooth true, mount (element),
             labels {button, buttonIdle, title, top}  with {i} {n} placeholders, defaults follow <html lang>
             (no lang on <html> -> <html data-evk-lead="zh"> decides)
       Lead language: the contents list copies the order of each part head's bilingual pair (primary line first), so a
       Chinese-led page lists Chinese titles in bold with the Latin line under them. Each line gets class .cn / .en and a lang
       attribute from its script, which is what base.css's script layer keys on. data-title / data-title-cn on a part override
       the head text (shown in lead order). To re-read titles after the lead changes: destroy() and call partNav again.
   EVK.chrome(opts?)   once per page, runs by itself on DOMContentLoaded:
       - the empty touchstart that makes iOS Safari apply :active (the press feedback)
       - html.is-scrolled once scrollY > 2 (the bar's hairline appears only when content passes under it)
       - --evk-bar-h on <html>: the measured height of .evk-bar (scroll-margin and sticky offsets read it)
       - --evk-ease on <html>: the token spring as a CSS linear() easing, where supported
       - EVK.seg() on every .evk-seg[role=tablist]
   EVK.seg(el)         roving tabindex + Left/Right/Up/Down/Home/End on a segmented control (role=tablist). Moving
                       focus selects (clicks the tab) so a handler listening for click works for keyboard users too.

   Behaviour (原站取值 / source value in brackets; one instance each)
     - the part being read = the last part whose top has passed a READING LINE at 28 % of the viewport below the bar
       [0.28; range 0.2–0.4: eyes rest in the upper third]. At the very end of the page the last part counts, even if
       it is too short to reach the line.
     - progress = (bar bottom - report top) / (report height - 0.6 viewport), clamped [0.6; it reaches 1 while the
       last screenful (sources, pager) is still ahead]. transform: scaleX, no transition (it follows the hand).
     - one rAF-coalesced, passive scroll/resize handler; current starts at -2 so the first update always applies;
       the DOM is written only when the index changes; aria-label regenerated only then.
     - hash links reveal their target: every enclosing <details> is opened, then the target is shown. Same for
       hashchange and for the hash at load.
     - panel: aria-expanded + aria-controls, focus goes to the current row (preventScroll), Up/Down/Home/End move
       between rows, Escape closes and returns focus to the button, outside click / Tab away / choosing a row close it.
       Choosing a row scrolls (smooth only after load and without reduced motion), moves focus to the part's head, and
       writes the hash with replaceState (history is not polluted).
     - sub-section chips: the .evk-subnav links of the current part get .is-on by the same reading line, and the
       active chip is kept in view inside its own scroller (never scrolls the page).
   ---------------------------------------------------------------------------------------------- */
(function () {
  "use strict";
  var EVK = window.EVK = window.EVK || {};
  var uid = 0;

  function reduced() { return EVK.reduced ? EVK.reduced() : !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches); }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  /* UI strings follow <html lang>; a page with no lang follows its lead language (<html data-evk-lead="zh">) */
  function zh() {
    var de = document.documentElement, l = de.lang || "";
    return l ? /^zh/i.test(l) : de.getAttribute("data-evk-lead") === "zh";
  }
  /* which script a title is written in, so its line gets .cn / .en and lang (the base.css script layer keys on them) */
  function isCJK(t) { return /[\u3400-\u9fff\uf900-\ufaff]/.test(t || ""); }
  function line(tag, text) {
    var n = el(tag, null, text);
    if (isCJK(text)) { n.className = "cn"; n.setAttribute("lang", "zh-CN"); } else { n.className = "en"; n.setAttribute("lang", "en"); }
    return n;
  }
  function fmt(s, i, n) { return s.replace("{i}", i).replace("{n}", n); }
  function byHash(h) {
    if (!h || h.length < 2) return null;
    try { return document.getElementById(decodeURIComponent(h.slice(1))); } catch (e) { return null; }
  }

  /* ---- reveal through collapsed content ---- */
  function openFor(hash, scroll) {
    var t = byHash(hash);
    if (!t) return;
    var opened = false, box = t.closest && t.closest("details");
    while (box) {
      if (!box.open) { box.open = true; opened = true; }
      box = box.parentElement && box.parentElement.closest("details");
    }
    if (opened && scroll) t.scrollIntoView();
  }

  function partNav(root, opts) {
    if (typeof root === "string") root = document.querySelector(root);
    if (!root) root = document.querySelector("[data-report]") || document;
    if (root.__evkPartNav) return root.__evkPartNav;
    opts = opts || {};
    var parts = [].slice.call(root.querySelectorAll(opts.parts || "[data-part]"));
    if (!parts.length) return null;

    var L = zh()
      ? { button: "章节目录，正在读第 {i} 部分，共 {n} 部分", buttonIdle: "章节目录，共 {n} 部分", title: "目录", top: "回到顶部" }
      : { button: "Contents, reading part {i} of {n}", buttonIdle: "Contents, {n} parts", title: "Contents", top: "Back to top" };
    if (opts.labels) for (var k in opts.labels) if (Object.prototype.hasOwnProperty.call(opts.labels, k)) L[k] = opts.labels[k];

    var readLine = opts.line != null ? opts.line : 0.28, endAt = opts.end != null ? opts.end : 0.6;
    var barSel = opts.bar || ".evk-bar", built = [];
    var n = parts.length, id = ++uid;

    parts.forEach(function (p, i) { if (!p.id) p.id = "part-" + (i + 1); });

    /* the host, the button, the panel, the progress line: reuse markup if it is there, build it if not */
    var host = opts.mount || document.querySelector("[data-partnav]");
    if (!host) {
      host = el("div", "evk-partnav"); host.setAttribute("data-partnav", "");
      var bar0 = document.querySelector(barSel);
      if (bar0) bar0.insertBefore(host, bar0.firstChild); else { host.classList.add("is-floating"); document.body.appendChild(host); }
      built.push(host);
    }
    host.classList.add("evk-partnav");
    var btn = host.querySelector(".evk-lines");
    if (!btn) { btn = el("button", "evk-lines"); btn.type = "button"; host.appendChild(btn); }
    btn.textContent = "";
    for (var li = 0; li < n; li++) { var ln = document.createElement("i"); ln.setAttribute("aria-hidden", "true"); btn.appendChild(ln); }
    var lines = [].slice.call(btn.querySelectorAll("i"));
    btn.classList.toggle("is-many", n > 6);
    var panelId = "evk-partnav-" + id;
    var panel = host.querySelector(".evk-partnav-panel");
    if (!panel) { panel = el("nav", "evk-partnav-panel"); host.appendChild(panel); }
    panel.id = panel.id || panelId; panelId = panel.id;
    panel.hidden = true;
    panel.setAttribute("aria-label", L.title);
    btn.setAttribute("aria-controls", panelId);
    btn.setAttribute("aria-expanded", "false");

    panel.textContent = "";
    var title = el("p", "evk-k evk-partnav-title", L.title);
    if (isCJK(L.title)) title.setAttribute("lang", "zh-CN");        // the script layer re-points the label tokens for a Chinese line
    panel.appendChild(title);
    var ol = el("ol");
    var links = parts.map(function (p, i) {
      var head = p.querySelector(".evk-part-head"), kk = head && head.querySelector(".evk-k");
      var no = head && head.querySelector(".no");
      /* the head's bilingual pair is written primary-first (the lead language leads): the panel keeps that order, so the
         contents list reads in the same language hierarchy as the page. data-title / data-title-cn override, in lead order. */
      var kids = kk ? [].slice.call(kk.children).map(function (c) { return (c.textContent || "").trim(); }).filter(Boolean) : [];
      var dEn = p.getAttribute("data-title"), dCn = p.getAttribute("data-title-cn");
      var titles = (dEn || dCn) ? (document.documentElement.getAttribute("data-evk-lead") === "zh" ? [dCn, dEn] : [dEn, dCn]).filter(Boolean)
        : (kids.length ? kids : [((kk && kk.textContent) || ((p.querySelector("h2,h3") || {}).textContent) || "").trim()].filter(Boolean));
      var first = titles[0] || ("Part " + (i + 1)), second = titles.length > 1 ? titles[titles.length - 1] : "";
      var a = el("a"); a.href = "#" + p.id; a.setAttribute("data-i", i);
      a.appendChild(el("span", "no", no ? no.textContent.trim() : (i < 9 ? "0" : "") + (i + 1)));
      var t = el("span", "t"); t.appendChild(line("b", first));
      if (second && second !== first) t.appendChild(line("span", second));
      a.appendChild(t);
      var item = el("li"); item.appendChild(a); ol.appendChild(item);
      return a;
    });
    panel.appendChild(ol);
    var top = el("a", "evk-partnav-top", L.top); top.href = "#"; top.setAttribute("data-top", ""); panel.appendChild(top);
    if (isCJK(L.top)) top.setAttribute("lang", "zh-CN");
    host.hidden = false;

    var prog = document.querySelector(".evk-progress");
    if (!prog) {
      prog = el("div", "evk-progress"); prog.setAttribute("aria-hidden", "true");
      var bar1 = document.querySelector(barSel);
      (bar1 || document.body).appendChild(prog); built.push(prog);
    }
    prog.hidden = false;
    document.documentElement.classList.add("evk-has-parts");      // base.css hides the scroll hairline: one line, not two

    /* the bar sits outside the report: hand it the report's entity colour, so the long line and the progress line wear it */
    (function adoptEntity() {
      var names = ["--e", "--e-text", "--e-on", "--e-soft", "--e-line", "--e-dk", "--e-soft-dk"];
      if (EVK.applyEntities) EVK.applyEntities(document);            // [data-entity-color] may not have run yet (idempotent)
      var src = getComputedStyle(root.nodeType === 1 ? root : document.body);
      if (!src.getPropertyValue("--e").trim() || getComputedStyle(host).getPropertyValue("--e").trim()) return;
      [host, prog].forEach(function (t) {
        names.forEach(function (nm) { var v = src.getPropertyValue(nm).trim(); if (v) t.style.setProperty(nm, v); });
      });
    })();

    function headerBottom() {
      var b = document.querySelector(barSel);
      return b ? Math.max(0, b.getBoundingClientRect().bottom) : 0;
    }

    /* ---- scroll sync ---- */
    var current = -2, lastP = "", subOn = null, subTouched = 0;
    function setVars(p) {
      var s = String(p);
      [host, prog].forEach(function (t) { t.style.setProperty("--p", s); });
    }
    function markSub(i, line) {
      var on = null;
      if (i >= 0) {
        var navLinks = parts[i].querySelectorAll(".evk-subnav a[href^='#']");
        for (var q = 0; q < navLinks.length; q++) {
          var t = byHash(navLinks[q].getAttribute("href"));
          if (t && t.getBoundingClientRect().top <= line) on = navLinks[q];
        }
      }
      if (on === subOn) return;
      if (subOn) { subOn.classList.remove("is-on"); subOn.removeAttribute("aria-current"); }
      if (on) { on.classList.add("is-on"); on.setAttribute("aria-current", "location"); keepInView(on); }
      subOn = on;
    }
    function keepInView(a) {
      var row = a.closest(".evk-subnav");
      if (!row || row.scrollWidth <= row.clientWidth + 1 || Date.now() - subTouched < 1200) return;
      var want = a.offsetLeft - (row.clientWidth - a.offsetWidth) / 2;
      try { row.scrollTo({ left: Math.max(0, want), behavior: reduced() ? "auto" : "smooth" }); } catch (e) { row.scrollLeft = Math.max(0, want); }
    }
    function update() {
      var hb = headerBottom(), vh = window.innerHeight, line = hb + vh * readLine, i = -1;
      for (var q = 0; q < n; q++) { if (parts[q].getBoundingClientRect().top <= line) i = q; else break; }
      var de = document.documentElement;
      if (i >= 0 && i < n - 1 && de.scrollHeight > vh + 4 && window.scrollY + vh >= de.scrollHeight - 2) i = n - 1;   // the end of the page is reading the last part
      markSub(i, line);
      var box = root.getBoundingClientRect ? root.getBoundingClientRect() : document.body.getBoundingClientRect();
      var span = box.height - vh * endAt;
      var p = span > 0 ? Math.min(1, Math.max(0, (hb - box.top) / span)) : 0;
      var ps = p.toFixed(4);
      if (ps !== lastP) { lastP = ps; setVars(ps); }
      if (i === current) return;
      current = i;
      host.style.setProperty("--i", i); host.style.setProperty("--n", n);
      btn.style.setProperty("--n", n);
      lines.forEach(function (ln, q2) { ln.classList.toggle("is-on", q2 === i); ln.classList.toggle("is-done", q2 < i); });
      links.forEach(function (a, q3) {
        if (q3 === i) a.setAttribute("aria-current", "location"); else a.removeAttribute("aria-current");
        a.classList.toggle("is-on", q3 === i);
      });
      btn.setAttribute("aria-label", i >= 0 ? fmt(L.button, i + 1, n) : fmt(L.buttonIdle, 0, n));
      try { root.dispatchEvent && root.dispatchEvent(new CustomEvent("evk:part", { bubbles: true, detail: { index: i, part: parts[i] || null } })); } catch (e) { /* old engines */ }
    }
    var queued = false;
    function onScroll() {
      if (queued) return;
      queued = true;
      requestAnimationFrame(function () { queued = false; update(); });
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    var rowTouch = function (e) { if (e.target.closest && e.target.closest(".evk-subnav")) subTouched = Date.now(); };
    document.addEventListener("pointerdown", rowTouch, { passive: true });
    document.addEventListener("wheel", rowTouch, { passive: true });

    /* ---- panel ---- */
    function setOpen(open, focus) {
      if (open === !panel.hidden) return;
      panel.hidden = !open;
      host.classList.toggle("is-open", open);
      btn.setAttribute("aria-expanded", open ? "true" : "false");
      if (open) {
        var on = panel.querySelector("a.is-on") || links[0];
        if (on) on.focus({ preventScroll: true });
      } else if (focus) btn.focus({ preventScroll: true });
    }
    function go(i, fromPanel) {
      var p = parts[i];
      if (!p) return;
      openFor("#" + p.id, false);
      var smooth = opts.smooth !== false && !reduced() && document.readyState === "complete";   // never animate before load: it fights scroll restoration
      p.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
      var h = p.querySelector(".evk-part-head") || p;
      if (!h.hasAttribute("tabindex")) h.setAttribute("tabindex", "-1");
      try { h.focus({ preventScroll: true }); } catch (e) { /* ignore */ }
      try { history.replaceState(null, "", "#" + p.id); } catch (e2) { /* file:// or sandbox */ }
      if (fromPanel) setOpen(false, false);
    }
    var onBtn = function () { setOpen(panel.hidden, false); };
    var onDoc = function (e) { if (!panel.hidden && !host.contains(e.target)) setOpen(false, false); };
    var onKey = function (e) {
      if (panel.hidden) return;
      if (e.key === "Escape" && !e.defaultPrevented && !e.isComposing) { e.preventDefault(); setOpen(false, true); return; }
      if (host.contains(document.activeElement) && /^(ArrowDown|ArrowUp|Home|End)$/.test(e.key) && document.activeElement !== btn) {
        var at = links.indexOf(document.activeElement), next = at;
        if (e.key === "ArrowDown") next = (at + 1) % links.length;
        else if (e.key === "ArrowUp") next = (at - 1 + links.length) % links.length;
        else if (e.key === "Home") next = 0; else next = links.length - 1;
        if (next >= 0) { e.preventDefault(); links[next].focus({ preventScroll: true }); }
      }
    };
    var onOut = function (e) { if (!panel.hidden && e.relatedTarget && !host.contains(e.relatedTarget)) setOpen(false, false); };
    var onPanel = function (e) {
      var a = e.target.closest && e.target.closest("a");
      if (!a) return;
      if (a.hasAttribute("data-top")) {
        e.preventDefault();
        window.scrollTo({ top: 0, behavior: reduced() || document.readyState !== "complete" ? "auto" : "smooth" });
        setOpen(false, true);
        return;
      }
      var i = links.indexOf(a);
      if (i >= 0) { e.preventDefault(); go(i, true); }
    };
    btn.addEventListener("click", onBtn);
    document.addEventListener("click", onDoc);
    document.addEventListener("keydown", onKey);
    host.addEventListener("focusout", onOut);
    panel.addEventListener("click", onPanel);

    /* ---- hash links reach into collapsed content ---- */
    var onRootClick = function (e) {
      var a = e.target.closest && e.target.closest("a[href^='#']");
      if (a) openFor(a.getAttribute("href"), false);
    };
    var onHash = function () { openFor(location.hash, true); };
    root.addEventListener("click", onRootClick);
    window.addEventListener("hashchange", onHash);
    openFor(location.hash, true);
    update();

    var api = {
      parts: parts, update: update, go: function (i) { go(i, false); },
      open: function () { setOpen(true); }, close: function () { setOpen(false, false); },
      get current() { return current; },
      destroy: function () {
        window.removeEventListener("scroll", onScroll); window.removeEventListener("resize", onScroll);
        window.removeEventListener("hashchange", onHash);
        document.removeEventListener("click", onDoc); document.removeEventListener("keydown", onKey);
        document.removeEventListener("pointerdown", rowTouch); document.removeEventListener("wheel", rowTouch);
        root.removeEventListener("click", onRootClick);
        built.forEach(function (b) { if (b.parentNode) b.parentNode.removeChild(b); });
        if (!built.length) { host.hidden = true; prog.hidden = true; }
        document.documentElement.classList.remove("evk-has-parts");
        delete root.__evkPartNav;
      }
    };
    root.__evkPartNav = api;
    return api;
  }
  EVK.partNav = partNav;

  /* ---- segmented control keyboard (role=tablist) ---- */
  EVK.seg = function (root) {
    if (!root || root.__evkSeg) return;
    root.__evkSeg = true;
    var vertical = root.getAttribute("aria-orientation") === "vertical";
    function tabs() { return [].slice.call(root.querySelectorAll("button, [role='tab']")).filter(function (b) { return !b.disabled; }); }
    function sync() {
      var t = tabs(), sel = t.filter(function (b) { return b.getAttribute("aria-selected") === "true"; })[0] || t[0];
      t.forEach(function (b) {
        if (!b.hasAttribute("role")) b.setAttribute("role", "tab");
        b.tabIndex = b === sel ? 0 : -1;
      });
    }
    sync();
    root.addEventListener("click", function (e) {
      var b = e.target.closest && e.target.closest("button, [role='tab']");
      if (b && root.contains(b)) setTimeout(sync, 0);        // the app flips aria-selected in its own handler first
    });
    root.addEventListener("keydown", function (e) {
      var t = tabs(), at = t.indexOf(document.activeElement);
      if (at < 0) return;
      var prev = vertical ? "ArrowUp" : "ArrowLeft", next = vertical ? "ArrowDown" : "ArrowRight", to = at;
      if (e.key === next || (!vertical && e.key === "ArrowDown")) to = (at + 1) % t.length;
      else if (e.key === prev || (!vertical && e.key === "ArrowUp")) to = (at - 1 + t.length) % t.length;
      else if (e.key === "Home") to = 0;
      else if (e.key === "End") to = t.length - 1;
      else return;
      e.preventDefault();
      t.forEach(function (b, q) { b.tabIndex = q === to ? 0 : -1; });
      t[to].focus();
      t[to].click();
      setTimeout(sync, 0);
    });
  };

  /* ---- page chrome ---- */
  var chromeOn = false;
  EVK.chrome = function (opts) {
    if (chromeOn) return;
    chromeOn = true;
    opts = opts || {};
    var de = document.documentElement;

    /* iOS Safari only applies :active (the pressed look) when a touch listener exists */
    document.addEventListener("touchstart", function () {}, { passive: true });

    /* the bar's hairline appears only once content scrolls beneath it */
    var scrolled = null, thr = opts.threshold != null ? opts.threshold : 2;
    function onScroll() {
      var now = window.scrollY > thr;
      if (now !== scrolled) { scrolled = now; de.classList.toggle("is-scrolled", now); }
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();

    /* the bar's real height, so offsets are read, not guessed (the source repeated 64/70/76/80/84 px by hand) */
    var bar = document.querySelector(opts.bar || ".evk-bar");
    function measure() { if (bar) de.style.setProperty("--evk-bar-h", bar.offsetHeight + "px"); }
    if (bar) {
      measure();
      if (window.ResizeObserver) new ResizeObserver(measure).observe(bar); else window.addEventListener("resize", measure);
    }

    /* the spring as a CSS easing for transitions that are not gestures */
    try {
      if (EVK.ease && window.CSS && CSS.supports && CSS.supports("transition-timing-function", "linear(0, 1)")) {
        var m = EVK.motion();
        de.style.setProperty("--evk-ease", EVK.ease(m.duration, Math.min(m.bounce, 0.2)));
      }
    } catch (e) { /* optional */ }

    [].forEach.call(document.querySelectorAll(".evk-seg[role='tablist']"), EVK.seg);
  };

  function boot() {
    EVK.chrome();
    var r = document.querySelector("[data-report]");
    if (r && r.querySelector("[data-part]")) partNav(r);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
