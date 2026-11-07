"use strict";
// The developing animation. While the server develops a photograph, the page shows the
// same steps on a small copy of it: the raw being read, a flash of exposure and the
// latent image, the black-and-white negative growing in the first developer, cyan, yellow
// and magenta dye forming under the silver, bleach clearing the silver, and the finished
// slide in its mount on the light box. A black-and-white film ("print" mode) instead clears
// in the fixer and is enlarged onto paper, where the picture comes up in the tray. Phases
// follow the server's stages, but each is shown for a moment even when the server is quicker.

const SLIDE_PHASES = ["scan", "expose", "develop", "dyes", "light"];
const PRINT_PHASES = ["scan", "expose", "develop", "fix", "print"];
const LAB_DWELL = { scan: 900, expose: 1100, develop: 1400, dyes: 2100, light: 1400, fix: 1800, print: 2800 };
const LAB_EDGE = 760;      // working size of the copy, in pixels
const MOUNT = 0.11;        // slide mount border, as a share of the long edge
const SAFELIGHT = "#ee5339";  // the darkroom's light
const MOUNT_CARD = "#e9e1d0";  // slide mount card, printed in red and black
const MOUNT_RED = "#b52d1b";
const MOUNT_INK = "#2a2622";
const PAPER = "#f2f0eb";       // fibre-base printing paper

class Lab {
  constructor(canvas, onPhase) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.onPhase = onPhase || (() => {});
    this.reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.mode = "slide";
    this.phases = SLIDE_PHASES;
    this.reset();
    const tick = (now) => { this.frame(now); requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  }

  reset() {
    this.layers = null;
    this.imageUrl = null;
    this.phase = 0;
    this.target = 0;
    this.since = performance.now();
    this.finishing = null;
    this.active = false;
    this.lastSub = null;
    this.size(1200, 800);
  }

  start(mode = "slide") {
    this.mode = mode;
    this.phases = mode === "print" ? PRINT_PHASES : SLIDE_PHASES;
    this.reset();
    this.active = true;
    this.onPhase(this.phases[0], null);
  }

  size(w, h) {
    const pad = Math.round(Math.max(w, h) * MOUNT);
    this.pad = pad;
    this.w = w;
    this.h = h;
    this.canvas.width = w + 2 * pad;
    this.canvas.height = h + 2 * pad;
  }

  // Server stage 1-6 (6, printing the files, stays on the light box).
  stage(n) {
    this.target = Math.max(this.target, Math.min(n, this.phases.length) - 1);
  }

  setImage(url) {
    if (this.imageUrl === url) return;
    this.imageUrl = url;
    const img = new Image();
    img.onload = () => {
      if (this.imageUrl !== url) return;
      const s = Math.min(1, LAB_EDGE / Math.max(img.naturalWidth, img.naturalHeight));
      const w = Math.round(img.naturalWidth * s);
      const h = Math.round(img.naturalHeight * s);
      this.size(w, h);
      this.layers = Lab.layers(img, w, h);
    };
    img.src = url;
  }

  // Resolves when the light-box phase has been shown; quicker once the result is waiting.
  finish() {
    this.target = this.phases.length - 1;
    if (!this.finishing) {
      this.finishing = new Promise((resolve) => { this.resolveFinish = resolve; });
    }
    return this.finishing;
  }

  stop() {
    this.active = false;
    if (this.resolveFinish) this.resolveFinish();
  }

  // Pre-render the pictures the phases blend between.
  static layers(img, w, h) {
    const source = document.createElement("canvas");
    source.width = w;
    source.height = h;
    const sctx = source.getContext("2d");
    sctx.drawImage(img, 0, 0, w, h);
    const px = sctx.getImageData(0, 0, w, h).data;
    const make = (fn) => {
      const c = document.createElement("canvas");
      c.width = w;
      c.height = h;
      const ctx = c.getContext("2d");
      const out = ctx.createImageData(w, h);
      for (let i = 0; i < px.length; i += 4) {
        const [r, g, b] = fn(px[i], px[i + 1], px[i + 2]);
        out.data[i] = r; out.data[i + 1] = g; out.data[i + 2] = b; out.data[i + 3] = 255;
      }
      ctx.putImageData(out, 0, 0);
      return c;
    };
    const grey = (r, g, b) => 0.2126 * r + 0.7152 * g + 0.0722 * b;
    return {
      full: source,
      positive: make((r, g, b) => { const y = grey(r, g, b); return [y, y, y]; }),
      negative: make((r, g, b) => { const y = 255 - grey(r, g, b) * 0.92; return [y * 0.86, y * 0.84, y * 0.8]; }),
      cyan: make((r) => [r, 255, 255]),
      cyanYellow: make((r, g, b) => [r, 255, b]),
    };
  }

  frame(now) {
    if (!this.active) return;
    const name = this.phases[this.phase];
    const dwell = (this.reduced ? 250 : LAB_DWELL[name]) * (this.finishing ? 0.5 : 1);
    let t = Math.min(1, (now - this.since) / dwell);
    if (t >= 1 && this.phase < this.target) {
      this.phase += 1;
      this.since = now;
      t = 0;
      this.onPhase(this.phases[this.phase], null);
    } else if (t >= 1 && this.finishing && this.phase === this.phases.length - 1) {
      this.stop();
    }
    this.draw(this.phases[this.phase], t, now);
  }

  draw(phase, t, now) {
    const { ctx, w, h, pad } = this;
    const cw = this.canvas.width;
    const ch = this.canvas.height;
    ctx.save();
    ctx.clearRect(0, 0, cw, ch);
    const L = this.layers;
    const ease = (x) => x * x * (3 - 2 * x);

    if (this.mode === "print" && ["develop", "fix", "print"].includes(phase)) {
      this.drawPrint(phase, t, now);
      ctx.restore();
      return;
    }

    if (phase === "light") {
      // The slide in its card mount on the light table; the silver veil clears first (bleach and fix).
      const glow = ease(Math.min(1, t * 1.6));
      ctx.save();
      ctx.globalAlpha = 0.25 + 0.75 * glow;
      ctx.shadowColor = "rgba(0, 0, 0, 0.7)";
      ctx.shadowBlur = pad * 0.5;
      ctx.shadowOffsetY = pad * 0.12;
      ctx.fillStyle = MOUNT_CARD;
      Lab.rounded(ctx, pad * 0.3, pad * 0.3, cw - pad * 0.6, ch - pad * 0.6, pad * 0.35);
      ctx.fill();
      ctx.restore();
      ctx.save();
      ctx.globalAlpha = glow;
      ctx.textBaseline = "middle";
      ctx.font = `700 ${Math.round(pad * 0.19)}px -apple-system, BlinkMacSystemFont, system-ui, sans-serif`;
      ctx.fillStyle = MOUNT_RED;
      ctx.textAlign = "center";
      ctx.fillText("S U N D A Y   6 4", cw / 2, pad * 0.66);
      ctx.fillStyle = MOUNT_INK;
      ctx.textAlign = "left";
      ctx.fillText("D Y E R O O M", pad, ch - pad * 0.66);
      ctx.textAlign = "right";
      ctx.font = `600 ${Math.round(pad * 0.17)}px -apple-system, BlinkMacSystemFont, system-ui, sans-serif`;
      ctx.fillText(new Date().toLocaleString("en", { month: "short" }).toUpperCase() + " " + new Date().getFullYear(), cw - pad, ch - pad * 0.66);
      ctx.restore();
      if (L) ctx.drawImage(L.full, pad, pad, w, h);
      const veil = Math.max(0, 0.42 * (1 - t * 2.4));
      if (veil > 0) { ctx.fillStyle = `rgba(22, 20, 17, ${veil})`; ctx.fillRect(pad, pad, w, h); }
      this.sub(veil > 0 ? "bleach" : "light box");
      ctx.restore();
      return;
    }

    ctx.fillStyle = "#16140f";
    ctx.fillRect(pad, pad, w, h);
    if (phase === "scan") {
      const y = pad + h * ease(t);
      if (L) {
        ctx.drawImage(L.full, 0, 0, w, y - pad, pad, pad, w, y - pad);
        ctx.fillStyle = "rgba(22, 20, 17, 0.35)";
        ctx.fillRect(pad, pad, w, y - pad);
      }
      ctx.fillStyle = SAFELIGHT;
      ctx.fillRect(pad, y - 1, w, 2);
      ctx.strokeStyle = "#2b2823";
      ctx.strokeRect(pad + 0.5, pad + 0.5, w - 1, h - 1);
      if (t >= 1 && !this.reduced) this.since = now;  // keep scanning until the stage moves on
    } else if (phase === "expose") {
      if (L) { ctx.globalAlpha = 0.14 * ease(t); ctx.drawImage(L.positive, pad, pad, w, h); ctx.globalAlpha = 1; }
      const flash = this.reduced ? 0 : Math.max(0, 1 - t / 0.18);
      if (flash > 0) { ctx.fillStyle = `rgba(255, 252, 244, ${flash})`; ctx.fillRect(pad, pad, w, h); }
    } else if (phase === "develop") {
      const rock = this.reduced ? 0 : Math.sin(now / 420) * 0.004;
      ctx.translate(cw / 2, ch / 2);
      ctx.rotate(rock);
      ctx.translate(-cw / 2, -ch / 2);
      if (L) { ctx.globalAlpha = 0.15 + 0.85 * ease(t); ctx.drawImage(L.negative, pad, pad, w, h); }
    } else if (phase === "dyes") {
      // Cyan dye first (red re-exposure), then yellow (blue re-exposure), then magenta.
      const steps = L ? [L.positive, L.cyan, L.cyanYellow, L.full] : [];
      const x = t * 3;
      const k = Math.min(2, Math.floor(x));
      if (L) {
        ctx.drawImage(steps[k], pad, pad, w, h);
        ctx.globalAlpha = ease(x - k);
        ctx.drawImage(steps[k + 1], pad, pad, w, h);
        ctx.globalAlpha = 1;
      }
      ctx.fillStyle = "rgba(22, 20, 17, 0.42)";  // silver still in the film
      ctx.fillRect(pad, pad, w, h);
      this.sub(["cyan", "yellow", "magenta"][k]);
    }
    ctx.restore();
  }

  // Black and white: the negative is milky with undeveloped halide until the fixer clears
  // it; then it is enlarged onto paper and the picture comes up in the tray, under safelight.
  drawPrint(phase, t, now) {
    const { ctx, w, h, pad } = this;
    const cw = this.canvas.width;
    const ch = this.canvas.height;
    const L = this.layers;
    const ease = (x) => x * x * (3 - 2 * x);
    const clamp = (x) => Math.min(1, Math.max(0, x));
    if (phase === "develop" || phase === "fix") {
      ctx.fillStyle = "#16140f";
      ctx.fillRect(pad, pad, w, h);
      if (phase === "develop" && !this.reduced) {
        ctx.translate(cw / 2, ch / 2);
        ctx.rotate(Math.sin(now / 420) * 0.004);
        ctx.translate(-cw / 2, -ch / 2);
      }
      if (L) {
        ctx.globalAlpha = phase === "develop" ? 0.15 + 0.85 * ease(t) : 1;
        ctx.drawImage(L.negative, pad, pad, w, h);
        ctx.globalAlpha = 1;
      }
      let milk = 0.42;
      if (phase === "fix") {
        this.sub(t < 0.2 ? "stop" : t < 0.75 ? "fix" : "wash");
        milk *= 1 - ease(clamp((t - 0.2) / 0.55));
      }
      if (milk > 0.002) {
        ctx.fillStyle = `rgba(226, 220, 204, ${milk})`;
        ctx.fillRect(pad, pad, w, h);
      }
      return;
    }
    const step = t < 0.3 ? "enlarger" : t < 0.85 ? "tray" : "print";
    this.sub(step);
    const edge = pad * 0.45;
    ctx.save();
    ctx.shadowColor = "rgba(0, 0, 0, 0.6)";
    ctx.shadowBlur = pad * 0.4;
    ctx.shadowOffsetY = pad * 0.1;
    ctx.fillStyle = PAPER;
    ctx.fillRect(edge, edge, cw - 2 * edge, ch - 2 * edge);
    ctx.restore();
    if (L) {
      if (step === "enlarger") {  // the negative projected onto the paper
        ctx.globalAlpha = 0.25 * ease(clamp(t / 0.3));
        ctx.drawImage(L.negative, pad, pad, w, h);
      } else {
        ctx.globalAlpha = step === "tray" ? ease(clamp((t - 0.3) / 0.55)) : 1;
        ctx.drawImage(L.positive, pad, pad, w, h);
      }
      ctx.globalAlpha = 1;
    }
    const lights = ease(clamp((t - 0.85) / 0.15));
    if (lights < 1) {
      ctx.fillStyle = `rgba(255, 140, 40, ${0.22 * (1 - lights)})`;
      ctx.fillRect(edge, edge, cw - 2 * edge, ch - 2 * edge);
    }
  }

  sub(name) {
    if (name !== this.lastSub) {
      this.lastSub = name;
      this.onPhase(this.phases[this.phase], name);
    }
  }

  static rounded(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }
}
