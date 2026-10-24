/* event-venue-kit · spring.js — springs, rubber band, flick projection, motion tokens
   ----------------------------------------------------------------------------------------------
   EVK.Spring(value, {duration, bounce, epsilon, velocityEpsilon, onUpdate, onRest})
       .to(target, velocity?, {duration, bounce, done}?)  chase a target, keep position AND velocity
       .snap(v?)  hard cut (no animation, velocity 0)     .stop()  freeze here, keep value + velocity
       .step(dt) -> true while still moving (for a caller that owns its own frame loop)
       .isActive()   .config({duration, bounce})  change the resting tune
       props: value velocity target duration bounce stiffness damping zeta
     With onUpdate/onRest the spring drives itself with requestAnimationFrame ("driven"). Without them it
     is passive: you call .step(dt) from your own loop (the venue map does this).
   EVK.rubber(overshoot, dimension, c = 0.55)   resistance past a limit (Apple curve)
   EVK.project(v, rate = 0.998)                 where a flick of v px/s would coast to (px)
   EVK.motion(el?) -> {duration, bounce, press, fade, reduced, leave, snap, camera}   from the tokens
   EVK.reduced()                                live prefers-reduced-motion
   EVK.ease(duration?, bounce?, points = 40)    CSS linear() string that traces the spring's step response
   Everything honours prefers-reduced-motion: .to() snaps (and still fires done / onRest).

   Model (the Apple duration/bounce form; the source site called it response/damping ratio)
     stiffness k = (2π / duration)²,  damping c = 4π (1 - bounce) / duration,  mass 1
     => natural period = duration, damping ratio zeta = 1 - bounce (bounce 0 = critically damped, no
     overshoot; 0.15–0.3 = visible life). Negative bounce (to -0.9) = overdamped, c = 4π / (duration (1 + bounce)).
   Integrator: the closed-form solution of the damped oscillator (under-, critically and over-damped), so it is
     exact and frame-rate independent; dt is clamped to 50 ms so a backgrounded tab never makes a sheet
     teleport. The source site used 4 sub-steps of semi-implicit Euler; both look the same, this one is stable
     at any duration. Rest = |x - target| < epsilon and |v| < velocityEpsilon (defaults 0.4 and 8, i.e. px and
     px/s; for unit-less springs pass the smallest change the eye can see, e.g. 0.0005, velocityEpsilon scales
     as 20 x epsilon), then value is set to exactly the target.

   Tempo (原站取值 / source values; the ratios are the idea, the seconds come from --spring-dur)
     sheet opens 0.35 s . closes 0.30 s . snaps back 0.30 s with bounce 0.2 . camera 0.45–0.55 s . fades 0.4 s
     leave = 0.857 x duration, snap = 0.857 x duration with bounce >= 0.2, camera = 1.3 x duration (推算 from those)
     Ranges worth trying: still and heavy 0.5–0.65 s bounce 0 . app-like 0.2–0.28 s . lively bounce 0.2–0.3.
   ---------------------------------------------------------------------------------------------- */
(function () {
  "use strict";
  var EVK = window.EVK = window.EVK || {};
  var TAU = Math.PI * 2, MAX_DT = 0.05;

  var mql = null;
  try { mql = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)"); } catch (e) { mql = null; }
  /* MediaQueryList.matches is live, so the OS setting is honoured without a reload (the source read it once). */
  EVK.reduced = function () { return !!(mql && mql.matches); };

  function clamp(x, lo, hi) { return x < lo ? lo : x > hi ? hi : x; }
  function seconds(str, fb) {
    var s = String(str == null ? "" : str).trim(), n = parseFloat(s);
    if (!isFinite(n)) return fb;
    return /ms$/i.test(s) ? n / 1000 : n;
  }
  function number(str, fb) { var n = parseFloat(String(str == null ? "" : str)); return isFinite(n) ? n : fb; }

  /* ---- tokens ---- */
  EVK.motion = function (el) {
    var cs = null;
    try { cs = getComputedStyle(el || document.documentElement); } catch (e) { cs = null; }
    function tok(n) { return cs ? cs.getPropertyValue(n) : ""; }
    var d = clamp(seconds(tok("--spring-dur"), 0.4), 0.05, 3);
    var b = clamp(number(tok("--spring-bounce"), 0), -0.9, 0.95);
    return {
      duration: d, bounce: b,
      press: clamp(number(tok("--press-scale"), 0.97), 0.5, 1),
      fade: clamp(seconds(tok("--fade-dur"), 0.2), 0, 3),
      reduced: EVK.reduced(),
      leave: { duration: d * 0.857, bounce: 0 },
      snap: { duration: d * 0.857, bounce: Math.max(b, 0.2) },
      camera: { duration: d * 1.3, bounce: 0 }
    };
  };

  /* ---- the closed-form oscillator: (x, v) relative to the target, advanced by t seconds ---- */
  function advance(x, v, w0, zeta, t) {
    var e, a;
    if (Math.abs(zeta - 1) < 1e-4) {
      e = Math.exp(-w0 * t);
      var k = v + w0 * x;
      return [e * (x + k * t), e * (v - w0 * k * t)];
    }
    if (zeta < 1) {
      a = zeta * w0;
      var wd = w0 * Math.sqrt(1 - zeta * zeta), B = (v + a * x) / wd, c = Math.cos(wd * t), s = Math.sin(wd * t);
      e = Math.exp(-a * t);
      return [e * (x * c + B * s), e * ((-a * x + wd * B) * c + (-a * B - wd * x) * s)];
    }
    var q = Math.sqrt(zeta * zeta - 1), r1 = -w0 * (zeta - q), r2 = -w0 * (zeta + q);
    var c2 = (v - r1 * x) / (r2 - r1), c1 = x - c2, e1 = Math.exp(r1 * t), e2 = Math.exp(r2 * t);
    return [c1 * e1 + c2 * e2, c1 * r1 * e1 + c2 * r2 * e2];
  }

  /* ---- Spring ---- */
  function Spring(value, opts) {
    if (!(this instanceof Spring)) return new Spring(value, opts);
    opts = opts || {};
    this.value = +value || 0;
    this.velocity = 0;
    this.target = this.value;
    var m = (opts.duration > 0 && opts.bounce != null) ? null : EVK.motion();
    this._base = {
      duration: opts.duration > 0 ? opts.duration : m.duration,
      bounce: opts.bounce != null ? opts.bounce : m.bounce
    };
    this.epsilon = opts.epsilon != null ? opts.epsilon : 0.4;
    this.velocityEpsilon = opts.velocityEpsilon != null ? opts.velocityEpsilon : this.epsilon * 20;
    this.onUpdate = opts.onUpdate || null;
    this.onRest = opts.onRest || null;
    this._id = 0; this._last = 0; this._done = null;
    this._tune(this._base);
  }
  Spring.prototype._tune = function (o) {
    o = o || this._base;
    var d = o.duration > 0 ? o.duration : this._base.duration;
    var b = clamp(o.bounce != null ? +o.bounce : this._base.bounce, -0.9, 0.95);
    var w0 = TAU / d;
    this.duration = d; this.bounce = b;
    this.stiffness = w0 * w0;
    this.damping = b >= 0 ? 2 * w0 * (1 - b) : 2 * w0 / (1 + b);   // = 4π(1-b)/d
    this.zeta = this.damping / (2 * w0);
    this._w0 = w0;
  };
  Spring.prototype.config = function (o) {
    if (o && o.duration > 0) this._base.duration = o.duration;
    if (o && o.bounce != null) this._base.bounce = o.bounce;
    this._tune(this._base);
    return this;
  };
  Spring.prototype.isActive = function () {
    return Math.abs(this.value - this.target) >= this.epsilon || Math.abs(this.velocity) >= this.velocityEpsilon;
  };
  Spring.prototype.stop = function () {
    if (this._id) cancelAnimationFrame(this._id);
    this._id = 0; this._done = null;
    return this;
  };
  Spring.prototype.snap = function (v) {
    this.stop();
    this.value = this.target = (v == null ? this.target : +v);
    this.velocity = 0;
    if (this.onUpdate) this.onUpdate(this.value, 0);
    return this;
  };
  /* to(target, velocity?, opts?)  opts: {duration, bounce} for this move only, or a function = done.
     A new .to() keeps value and velocity (that is the point) and drops the previous done callback. */
  Spring.prototype.to = function (target, velocity, o) {
    if (velocity && typeof velocity === "object") { o = velocity; velocity = null; }
    var done = null;
    if (typeof o === "function") { done = o; o = null; }
    else if (o && typeof o.done === "function") done = o.done;
    this._done = done;
    this.target = +target;
    if (velocity != null && isFinite(velocity)) this.velocity = +velocity;
    this._tune(o && (o.duration > 0 || o.bounce != null) ? o : null);
    if (EVK.reduced()) {      // same states, no travel
      var d = this._done;
      this.snap(this.target);
      if (this.onRest) this.onRest(this.value);
      if (d) d();
      return this;
    }
    this._start();
    return this;
  };
  Spring.prototype.step = function (dt) {
    dt = dt > MAX_DT ? MAX_DT : dt < 0 ? 0 : dt;
    var x = this.value - this.target, v = this.velocity;
    if (dt > 0) { var r = advance(x, v, this._w0, this.zeta, dt); x = r[0]; v = r[1]; }
    if (Math.abs(x) < this.epsilon && Math.abs(v) < this.velocityEpsilon) {
      this.value = this.target; this.velocity = 0;
      return false;
    }
    this.value = this.target + x; this.velocity = v;
    return true;
  };
  Spring.prototype._start = function () {
    if (!this.onUpdate && !this.onRest) return;     // passive: the caller steps it
    if (this._id) return;                           // already running: the new target is picked up next frame
    var self = this;
    this._last = performance.now();
    function tick(now) {
      self._id = 0;
      var dt = (now - self._last) / 1000;
      self._last = now;
      var active = self.step(dt);
      if (self.onUpdate) self.onUpdate(self.value, self.velocity);
      if (active) { self._id = requestAnimationFrame(tick); return; }
      var d = self._done; self._done = null;
      if (self.onRest) self.onRest(self.value);
      if (d) d();
    }
    this._id = requestAnimationFrame(tick);
  };
  EVK.Spring = Spring;

  /* ---- limits that resist instead of clamping ---- */
  EVK.rubber = function (over, dim, c) {
    if (c == null) c = 0.55;
    if (!(dim > 0) || !over) return 0;
    var s = over < 0 ? -1 : 1, o = Math.abs(over);
    return s * (o * dim * c) / (dim + c * o);
  };
  /* where a flick of v px/s coasts to: v/1000 * rate / (1 - rate); rate 0.998 = UIScrollView "normal" (0.499 s of travel) */
  EVK.project = function (v, rate) {
    if (rate == null) rate = 0.998;
    return (v / 1000) * rate / (1 - rate);
  };

  /* ---- a spring as a CSS easing ---- */
  EVK.ease = function (duration, bounce, points) {
    var m = (duration > 0 && bounce != null) ? null : EVK.motion();
    var d = duration > 0 ? duration : m.duration, b = bounce != null ? bounce : m.bounce;
    var sp = new Spring(1, { duration: d, bounce: b });
    var w0 = sp._w0, z = sp.zeta, n = points > 4 ? points | 0 : 40;
    function at(t) { return 1 + advance(-1, 0, w0, z, t)[0]; }       // step response 0 -> 1
    var T = d, dt = 1 / 480;                                        // settle time: last moment it is off by > 0.2 %
    for (var t = 0, last = 0; t < d * 6; t += dt) if (Math.abs(at(t) - 1) > 0.002) last = t;
    T = last + dt;
    var out = [];
    for (var i = 0; i <= n; i++) out.push((i === n ? 1 : Math.round(at(T * i / n) * 1000) / 1000).toString());
    out[0] = "0";
    return "linear(" + out.join(", ") + ")";
  };
})();
