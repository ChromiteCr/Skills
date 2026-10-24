/* event-venue-kit · sheet.js — a non-modal bottom sheet that can be caught, dragged and flicked away
   ----------------------------------------------------------------------------------------------
   EVK.Sheet(el, {onOpen, onClose, onSettle, launcher, grab, focus, closeOnEscape, dismissAt, snapBounce, edgeGap})
       .open({launcher?, focus?})   .close(velocity?)   .isOpen (getter)   .destroy()
       .spring (EVK.Spring of the slide, px)   .el   .launcher
       onClose(sheet)  fires when closing STARTS (the map zooms out and the highlight clears while the sheet
                       is still leaving: one gesture, not a sequence)
       onSettle("open"|"closed", sheet)  fires when the spring comes to rest (also after a snap-back)
       Events on el (bubble): "evk:open" at open start, "evk:close" at close start. el[data-state] =
       "open" | "closing" while visible; the element gets [hidden] when closed.
   EVK.fitAbove(map, sheetOrEl, {mapEl, top, gap, minBand}) -> pad     keep what matters in the free part of the map
   EVK.fitAbove.watch(map, sheetsOrEls, opts) -> {update(), stop()}   re-run on open/close/scroll/resize AND whenever a sheet's
                       own box changes size (its content grows or shrinks: overview toggle, a longer step, a font loading),
                       one per frame

   Markup (base.css gives the structure)
     <div class="evk-sheet" role="dialog" aria-modal="false" aria-labelledby="t" hidden>
       <div class="evk-grabber"></div>
       <div class="evk-sheet-head"> <h2 id="t" tabindex="-1">…</h2> <button class="evk-btn evk-btn--quiet">Close</button> </div>
       …content…
     </div>
   Drag handle = every [data-grab], .evk-grabber and .evk-sheet-head inside the sheet (or opts.grab). Presses that
   start on button, a, select, input, textarea, summary, label or [data-no-drag] are left alone; the content below
   scrolls normally (the handle has touch-action: none, the rest does not).

   Behaviour (原站取值 / source value in brackets; each is one instance of a principle, tune freely)
     - not modal: no scrim, no focus trap, no aria-modal; the map behind stays live. Escape closes the newest sheet.
     - one transient surface at a time is the page's job; the stack here only decides who Escape belongs to.
     - open: unhide, jump to "just below the screen" in the same task (no frame at rest position), spring to 0
       with the token tempo (0.35 s). Re-opening an open sheet does not replay the entrance; re-opening a closing
       sheet reverses it from where it is, at the speed it has.
     - close: leaves on the axis it came from, quicker than it arrived (0.30 s, no bounce), from the release velocity.
     - drag: 1:1 downward; upward past rest resists with the rubber band (c 0.55, asymptote = sheet height).
     - release: velocity from the samples of the last 100 ms (the release itself is a sample, so a pause before
       lifting lowers it: the sheet returns instead of being flicked away); dismiss when
       position + project(v) > 50 % of the height (dismissAt 0.5; project = v * 0.499 s). Otherwise snap back with
       bounce >= 0.2 (the one deliberate accent, [ζ 0.8]).
     - offscreen distance = height + the sheet's bottom inset + 16 px of shadow clearance [8 + 16 = 24 + height].
     - at rest the sheet has no inline transform and no will-change; geometry is measured from the settled layout.
     - focus: moves into the sheet only when it was opened from the keyboard (launcher is :focus-visible) or
       focus:true; goes to [data-sheet-title] / heading / the sheet itself with preventScroll; on close it returns
       to the launcher when it was inside the sheet. No phone keyboard ever pops up on open.
     - reduced motion: unhide / hide, same states, no travel.
   Alternatives not built in (options, not bans): the whole sheet draggable when its scroller is at the top
   (iOS pattern); peek / half / full detents with nearest-detent-by-projection; fixed distance or velocity
   thresholds; drag-free sheet with a Close button only.
   ---------------------------------------------------------------------------------------------- */
(function () {
  "use strict";
  var EVK = window.EVK = window.EVK || {};
  if (!EVK.Spring) { if (window.console) console.error("EVK.Sheet needs spring.js loaded first"); return; }

  var stack = [], keyBound = false, HIST = 8, WINDOW = 100;
  var NO_DRAG = "button, a, select, input, textarea, summary, label, [data-no-drag]";

  function onKey(e) {
    if (e.key !== "Escape" || e.defaultPrevented || e.isComposing || e.keyCode === 229) return;   // IME: Escape cancels the composition
    var top = stack[stack.length - 1];
    if (top && top.opts.closeOnEscape !== false) { e.preventDefault(); top.close(); }
  }
  function focusVisible(el) { try { return !!(el && el.matches && el.matches(":focus-visible")); } catch (e) { return false; } }
  function remove(list, x) { var i = list.indexOf(x); if (i >= 0) list.splice(i, 1); }
  function fire(el, name, detail) {
    try { el.dispatchEvent(new CustomEvent(name, { bubbles: true, detail: detail })); } catch (e) { /* old engines */ }
  }

  function Sheet(el, opts) {
    if (!(this instanceof Sheet)) return new Sheet(el, opts);
    if (typeof el === "string") el = document.querySelector(el);
    if (!el) throw new Error("EVK.Sheet: element not found");
    if (el.__evkSheet) return el.__evkSheet;
    el.__evkSheet = this;
    var self = this;
    this.el = el;
    this.opts = opts = opts || {};
    this.launcher = opts.launcher || null;
    this._open = !el.hidden;
    this._moved = false;            // we moved focus into the sheet
    this._regions = [];
    this._drag = null;

    if (!el.hasAttribute("role")) el.setAttribute("role", "dialog");
    if (!el.hasAttribute("aria-modal")) el.setAttribute("aria-modal", "false");
    if (!el.hasAttribute("aria-label") && !el.hasAttribute("aria-labelledby")) {
      var t = this._title();
      if (t) { if (!t.id) t.id = "evk-sheet-t" + Math.random().toString(36).slice(2, 7); el.setAttribute("aria-labelledby", t.id); }
    }

    this.spring = new EVK.Spring(0, {
      onUpdate: function (y) {
        el.style.transform = y ? "translateY(" + Math.round(y * 100) / 100 + "px)" : "";
      }
    });

    var regions = [];
    if (opts.grab) regions = typeof opts.grab === "string" ? [].slice.call(el.querySelectorAll(opts.grab)) : [].concat(opts.grab);
    else regions = [].slice.call(el.querySelectorAll("[data-grab], .evk-grabber, .evk-sheet-head"));
    regions.forEach(function (g) {
      g.style.touchAction = "none";
      g.addEventListener("pointerdown", self._down = self._down || function (e) { self._onDown(e, this); });
      g.addEventListener("pointermove", self._mv = self._mv || function (e) { self._onMove(e); });
      g.addEventListener("pointerup", self._up = self._up || function (e) { self._onUp(e, false); });
      g.addEventListener("pointercancel", self._cx = self._cx || function (e) { self._onUp(e, true); });
      self._regions.push(g);
    });
    if (this._open) { stack.push(this); this._bindKey(); }
  }

  Sheet.prototype._title = function () {
    return this.el.querySelector("[data-sheet-title], .evk-sheet-title, h1, h2, h3");
  };
  Sheet.prototype._bindKey = function () {
    if (!keyBound) { document.addEventListener("keydown", onKey); keyBound = true; }
  };
  Sheet.prototype._offscreen = function () {
    var cs = getComputedStyle(this.el), inset = parseFloat(cs.bottom);
    return this.el.offsetHeight + (isFinite(inset) ? Math.max(0, inset) : 0) + (this.opts.edgeGap != null ? this.opts.edgeGap : 16);
  };
  Sheet.prototype._moving = function (on) {
    this.el.style.willChange = on ? "transform" : "";
  };
  Sheet.prototype._settle = function (state) {
    this._moving(false);
    if (this.opts.onSettle) this.opts.onSettle(state, this);
  };
  Sheet.prototype._focusInto = function (target) {
    var t = target && target !== true && target !== "title" && target !== "auto"
      ? (typeof target === "string" ? this.el.querySelector(target) : target) : this._title();
    t = t || this.el;
    if (!t.hasAttribute("tabindex") && !/^(A|BUTTON|INPUT|SELECT|TEXTAREA|SUMMARY)$/.test(t.tagName)) t.setAttribute("tabindex", "-1");
    try { t.focus({ preventScroll: true }); this._moved = true; } catch (e) { /* ignore */ }
  };

  Object.defineProperty(Sheet.prototype, "isOpen", { get: function () { return this._open; } });

  Sheet.prototype.open = function (o) {
    o = o || {};
    var self = this, el = this.el, wasHidden = el.hidden, reopened = !this._open, m = EVK.motion(el);
    if (reopened) {
      this._open = true;
      var ae = document.activeElement;
      this.launcher = o.launcher || ((ae && ae !== document.body && !el.contains(ae)) ? ae : this.launcher);
      remove(stack, this); stack.push(this);
      this._bindKey();
    } else if (o.launcher) this.launcher = o.launcher;
    el.hidden = false;
    el.setAttribute("data-state", "open");
    if (wasHidden) {
      this._moved = false;
      if (!EVK.reduced()) this.spring.snap(this._offscreen());       // off-screen before the first paint
    }
    if (reopened) {                                                   // also when a closing sheet is caught and reversed
      if (this.opts.onOpen) this.opts.onOpen(this);
      fire(el, "evk:open", { sheet: this });
    }
    var f = o.focus != null ? o.focus : (this.opts.focus != null ? this.opts.focus : "auto");
    if (reopened && (f === "auto" ? focusVisible(this.launcher) : (f !== false && f !== "none"))) this._focusInto(f);
    if (EVK.reduced()) { this.spring.snap(0); this._settle("open"); return this; }
    this._moving(true);
    this.spring.to(0, null, { duration: m.duration, bounce: m.bounce, done: function () { if (self._open) self._settle("open"); } });
    return this;
  };

  Sheet.prototype.close = function (velocity) {
    var self = this, el = this.el;
    if (el.hidden || !this._open) return this;
    this._open = false;
    remove(stack, this);
    var hadFocus = el.contains(document.activeElement) || this._moved;
    el.setAttribute("data-state", "closing");
    if (this.opts.onClose) this.opts.onClose(this);                  // cause first: the map reacts at gesture start
    fire(el, "evk:close", { sheet: this });
    function finish() {
      if (self._open) return;                                        // re-opened meanwhile
      el.hidden = true;
      el.removeAttribute("data-state");
      self.spring.snap(0);
      var l = self.launcher;
      if (hadFocus && l && document.contains(l) && (document.activeElement === document.body || el.contains(document.activeElement) || !document.activeElement)) {
        try { l.focus({ preventScroll: true }); } catch (e) { /* ignore */ }
      }
      self._moved = false;
      self._settle("closed");
    }
    if (EVK.reduced()) { finish(); return this; }
    var m = EVK.motion(el);
    this._moving(true);
    this.spring.to(this._offscreen(), velocity == null ? null : velocity, { duration: m.leave.duration, bounce: 0, done: finish });
    return this;
  };

  /* ---- drag ---- */
  Sheet.prototype._onDown = function (e, region) {
    if (this._drag || e.button !== 0 || e.isPrimary === false || !this._open) return;
    if (e.target.closest && e.target.closest(NO_DRAG) && region.contains(e.target.closest(NO_DRAG))) return;
    this.spring.stop();
    this._moving(true);
    this._drag = { id: e.pointerId, y0: e.clientY, x0: this.spring.value, hist: [{ y: e.clientY, t: e.timeStamp }], region: region };
    this.el.classList.add("is-dragging");
    try { region.setPointerCapture(e.pointerId); } catch (err) { /* capture is a nicety, not a requirement */ }
  };
  Sheet.prototype._onMove = function (e) {
    var d = this._drag;
    if (!d || e.pointerId !== d.id) return;
    var y = d.x0 + (e.clientY - d.y0);
    if (y < 0) y = -EVK.rubber(-y, this.el.offsetHeight);            // down is a door, up is a wall
    this.spring.snap(y);
    d.hist.push({ y: e.clientY, t: e.timeStamp });
    if (d.hist.length > HIST) d.hist.shift();
  };
  Sheet.prototype._onUp = function (e, cancelled) {
    var d = this._drag;
    if (!d || e.pointerId !== d.id) return;
    this._drag = null;
    this.el.classList.remove("is-dragging");
    try { d.region.releasePointerCapture(e.pointerId); } catch (err) { /* already released */ }
    var v = 0;
    if (!cancelled) {                                                // the release is a sample: a pause lowers the speed
      d.hist.push({ y: e.clientY, t: e.timeStamp });
      var b = d.hist[d.hist.length - 1], a = null;
      for (var i = 0; i < d.hist.length; i++) if (b.t - d.hist[i].t <= WINDOW) { a = d.hist[i]; break; }
      if (a && b.t > a.t) v = (b.y - a.y) / (b.t - a.t) * 1000;
    }
    var at = this.opts.dismissAt != null ? this.opts.dismissAt : 0.5;
    if (this.spring.value + EVK.project(v) > this.el.offsetHeight * at) { this.close(v); return; }
    var self = this, m = EVK.motion(this.el);
    var sb = this.opts.snapBounce != null ? this.opts.snapBounce : m.snap.bounce;
    this.spring.to(0, v, { duration: m.snap.duration, bounce: sb, done: function () { if (self._open) self._settle("open"); } });
  };

  Sheet.prototype.destroy = function () {
    var self = this;
    this.spring.stop();
    this._regions.forEach(function (g) {
      g.removeEventListener("pointerdown", self._down); g.removeEventListener("pointermove", self._mv);
      g.removeEventListener("pointerup", self._up); g.removeEventListener("pointercancel", self._cx);
    });
    remove(stack, this);
    this.el.style.transform = ""; this.el.style.willChange = "";
    delete this.el.__evkSheet;
  };
  EVK.Sheet = Sheet;

  /* ---- fitAbove: aim the map at the part the sheet does not cover ---- */
  function matrixOf(el) {
    var t = getComputedStyle(el).transform;
    if (!t || t === "none") return { x: 0, y: 0 };
    try { var m = new DOMMatrix(t); return { x: m.m41, y: m.m42 }; } catch (e) { return { x: 0, y: 0 }; }
  }
  function elOf(x) { return x && x.el ? x.el : x; }
  function liveEl(x) {
    var el = elOf(x);
    if (!el || el.hidden || el.getAttribute("data-state") === "closing") return null;
    return el;
  }
  function firstOpen(list) {
    list = [].concat(list || []);
    for (var i = 0; i < list.length; i++) { var el = liveEl(list[i]); if (el) return el; }
    return null;
  }
  function barBottom() {
    var bar = document.querySelector(".evk-bar");
    if (!bar) return 0;
    var r = bar.getBoundingClientRect();
    return Math.max(0, r.bottom);
  }
  /* The settled box (layout, ignoring the slide transform: "where it settles, not where its slide is now") */
  function settled(el) {
    var r = el.getBoundingClientRect(), mx = matrixOf(el);
    return { left: r.left - mx.x, right: r.right - mx.x, top: r.top - mx.y, bottom: r.bottom - mx.y, width: r.width, height: el.offsetHeight };
  }
  function fitAbove(map, target, opts) {
    opts = opts || {};
    var mapEl = opts.mapEl || (map && map.canvas && map.canvas.closest && map.canvas.closest(".evk-map")) || document.querySelector(".evk-map");
    var pad = { top: 0, right: 0, bottom: 0, left: 0 };
    if (!mapEl) return pad;
    var box = mapEl.getBoundingClientRect(), vw = window.innerWidth;
    var gap = opts.gap != null ? opts.gap : 12, minBand = opts.minBand != null ? opts.minBand : 80;
    var barB = opts.top != null ? (typeof opts.top === "function" ? opts.top() : +opts.top) : barBottom();
    pad.top = Math.max(0, Math.min(box.height, barB - box.top));                 // under a sticky bar [64 px in the source]
    var el = firstOpen(target);
    if (el) {
      var s = settled(el);
      if (s.top < box.bottom && s.bottom > box.top && s.left < box.right && s.right > box.left) {
        var band = s.width >= vw * 0.9 || s.width >= box.width * 0.9;            // a band is avoided by moving, a card by refitting
        if (band) pad.bottom = Math.max(0, Math.min(box.height, box.bottom - Math.max(s.top, box.top)));
        else if (s.left + s.width / 2 > box.left + box.width / 2) pad.right = Math.max(0, Math.min(box.width * 0.5, box.right - s.left + gap));
        else pad.left = Math.max(0, Math.min(box.width * 0.5, s.right - box.left + gap));
      }
    }
    if (box.height - pad.top - pad.bottom < minBand) pad.bottom = 0;             // too little left to centre in: do nothing
    if (map && typeof map.setPad === "function") map.setPad(pad);
    return pad;
  }
  fitAbove.watch = function (map, targets, opts) {
    var queued = false, list = [].concat(targets || []), off = [], ro = null;
    function run() { queued = false; fitAbove(map, list, opts); }
    function soon() { if (!queued) { queued = true; requestAnimationFrame(run); } }
    window.addEventListener("scroll", soon, { passive: true });
    window.addEventListener("resize", soon);
    // the sheet's content can change height while it stays open (steps shown or hidden, a longer line, web fonts arriving):
    // window resize does not fire for that, so the sheet itself is observed. The callback only queues a frame; the pad is
    // applied to the map, not to the observed box, so this cannot feed back into the observer.
    if (window.ResizeObserver) ro = new ResizeObserver(soon);
    list.forEach(function (x) {
      var el = elOf(x);
      if (!el || !el.addEventListener) return;
      el.addEventListener("evk:open", soon); el.addEventListener("evk:close", soon);
      if (ro) ro.observe(el);
      off.push(function () { el.removeEventListener("evk:open", soon); el.removeEventListener("evk:close", soon); });
    });
    soon();
    return {
      update: run,
      stop: function () {
        window.removeEventListener("scroll", soon); window.removeEventListener("resize", soon);
        if (ro) ro.disconnect();
        off.forEach(function (f) { f(); });
      }
    };
  };
  EVK.fitAbove = fitAbove;
})();
