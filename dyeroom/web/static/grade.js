"use strict";
// Finishing adjustments, previewed live with WebGL. The arithmetic is the same as
// dyeroom/adjust.py, which makes the downloaded file: Oklab, eight hue bands with smooth
// hand-over, and colour wheels weighted by lightness into shadows, midtones and highlights.

const ADJUST = {
  bands: { red: 29, orange: 60, yellow: 100, green: 143, aqua: 195, blue: 258, purple: 300, magenta: 348 },
  wheels: ["shadows", "midtones", "highlights"],
  hueRange: 30, lightRange: 0.12, wheelRange: 0.05, wheelLight: 0.1,
};

const LMS_FROM_XYZ = [[0.8189330101, 0.3618667424, -0.1288597137],
                      [0.0329845436, 0.9293118715, 0.0361456387],
                      [0.0482003018, 0.2643662691, 0.6338517070]];
const LAB_FROM_LMS = [[0.2104542553, 0.7936177850, -0.0040720468],
                      [1.9779984951, -2.4285922050, 0.4505937099],
                      [0.0259040371, 0.7827717662, -0.8086757660]];
const XYZ_FROM_RGB = {
  p3: [[0.4865709486, 0.2656676932, 0.1982172852], [0.2289745641, 0.6917385218, 0.0792869141],
       [0.0, 0.0451133819, 1.0439443689]],
  srgb: [[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]],
};

function matMul(a, b) {
  return a.map((row) => [0, 1, 2].map((j) => row[0] * b[0][j] + row[1] * b[1][j] + row[2] * b[2][j]));
}

function matInv(m) {
  const [[a, b, c], [d, e, f], [g, h, i]] = m;
  const A = e * i - f * h, B = f * g - d * i, C = d * h - e * g;
  const det = a * A + b * B + c * C;
  return [[A / det, (c * h - b * i) / det, (b * f - c * e) / det],
          [B / det, (a * i - c * g) / det, (c * d - a * f) / det],
          [C / det, (b * g - a * h) / det, (a * e - b * d) / det]];
}

const columnMajor = (m) => new Float32Array([m[0][0], m[1][0], m[2][0], m[0][1], m[1][1], m[2][1], m[0][2], m[1][2], m[2][2]]);

function emptyAdjust() {
  return { bands: {}, wheels: {} };
}

function isIdentity(adjust) {
  const bands = Object.values(adjust.bands).some((v) => v.some((x) => x !== 0));
  const wheels = Object.values(adjust.wheels).some((v) => v[1] !== 0 || v[2] !== 0);
  return !bands && !wheels;
}

const LMS_FROM_LAB = matInv(LAB_FROM_LMS);
const SRGB_FROM_LMS = matInv(matMul(LMS_FROM_XYZ, XYZ_FROM_RGB.srgb));

// Oklab LCh (hue in degrees) to 8-bit sRGB, for the wheels and band labels.
function oklchRgb(l, c, hue) {
  const h = (hue * Math.PI) / 180;
  const lab = [l, c * Math.cos(h), c * Math.sin(h)];
  const lms = LMS_FROM_LAB.map((r) => r[0] * lab[0] + r[1] * lab[1] + r[2] * lab[2]).map((v) => v * v * v);
  return SRGB_FROM_LMS.map((r) => r[0] * lms[0] + r[1] * lms[1] + r[2] * lms[2]).map((v) => {
    const x = Math.min(1, Math.max(0, v));
    return Math.round(255 * (x <= 0.0031308 ? 12.92 * x : 1.055 * Math.pow(x, 1 / 2.4) - 0.055));
  });
}

const oklchCss = (l, c, hue) => `rgb(${oklchRgb(l, c, hue).join(", ")})`;

const VERTEX = `#version 300 es
in vec2 pos;
out vec2 uv;
void main() { uv = vec2(pos.x * 0.5 + 0.5, 0.5 - pos.y * 0.5); gl_Position = vec4(pos, 0.0, 1.0); }`;

const FRAGMENT = `#version 300 es
precision highp float;
uniform sampler2D img;
uniform mat3 toLms, fromLms, toLab, fromLab, outMat;
uniform float centres[8];
uniform vec3 bands[8];
uniform vec2 push[3];
uniform float lift[3];
uniform bool doBands, doWheels, convertOut;
uniform float hueRange, lightRange;
in vec2 uv;
out vec4 color;
vec3 decode(vec3 e) { return mix(e / 12.92, pow((e + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), e)); }
vec3 encode(vec3 l) { return mix(l * 12.92, 1.055 * pow(l, vec3(1.0 / 2.4)) - 0.055, step(vec3(0.0031308), l)); }
float sstep(float a, float b, float x) { float t = clamp((x - a) / (b - a), 0.0, 1.0); return t * t * (3.0 - 2.0 * t); }
vec3 cbrt3(vec3 v) { return sign(v) * pow(abs(v), vec3(1.0 / 3.0)); }
void main() {
  vec3 lab = toLab * cbrt3(toLms * decode(texture(img, uv).rgb));
  float L = lab.x, a = lab.y, b = lab.z;
  if (doBands) {
    float C = length(vec2(a, b));
    float h = mod(degrees(atan(b, a)) + 360.0, 360.0);
    vec3 m = vec3(0.0);
    for (int i = 0; i < 8; i++) {
      int j = (i + 1) % 8;
      float span = mod(centres[j] - centres[i] + 360.0, 360.0);
      float d = mod(h - centres[i] + 360.0, 360.0);
      if (d < span) { float t = sstep(0.0, 1.0, d / span); m = bands[i] * (1.0 - t) + bands[j] * t; }
    }
    float hr = radians(h + m.x * hueRange);
    float c2 = C * max(0.0, 1.0 + m.y);
    L += m.z * lightRange * sstep(0.0, 0.05, C);
    a = c2 * cos(hr);
    b = c2 * sin(hr);
  }
  if (doWheels) {
    float ws = 1.0 - sstep(0.15, 0.55, L);
    float wh = sstep(0.45, 0.85, L);
    float wm = max(0.0, 1.0 - ws - wh);
    a += ws * push[0].x + wm * push[1].x + wh * push[2].x;
    b += ws * push[0].y + wm * push[1].y + wh * push[2].y;
    L += ws * lift[0] + wm * lift[1] + wh * lift[2];
  }
  vec3 lms = fromLab * vec3(L, a, b);
  vec3 lin = clamp(fromLms * (lms * lms * lms), 0.0, 1.0);
  if (convertOut) lin = clamp(outMat * lin, 0.0, 1.0);
  color = vec4(encode(lin), 1.0);
}`;

class Grader {
  constructor(canvas) {
    this.canvas = canvas;
    const gl = canvas.getContext("webgl2", { preserveDrawingBuffer: true, antialias: false, premultipliedAlpha: false });
    if (!gl) throw new Error("WebGL 2 is not available");
    this.gl = gl;
    this.wideCanvas = "drawingBufferColorSpace" in gl;
    const shader = (type, source) => {
      const s = gl.createShader(type);
      gl.shaderSource(s, source);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      return s;
    };
    const program = gl.createProgram();
    gl.attachShader(program, shader(gl.VERTEX_SHADER, VERTEX));
    gl.attachShader(program, shader(gl.FRAGMENT_SHADER, FRAGMENT));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
    gl.useProgram(program);
    this.program = program;
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(program, "pos");
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    this.texture = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, this.texture);
    for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.NEAREST], [gl.TEXTURE_MAG_FILTER, gl.NEAREST],
                          [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) {
      gl.texParameteri(gl.TEXTURE_2D, k, v);
    }
    this.u = (name) => gl.getUniformLocation(program, name);
    gl.uniform1fv(this.u("centres"), new Float32Array(Object.values(ADJUST.bands)));
    gl.uniform1f(this.u("hueRange"), ADJUST.hueRange);
    gl.uniform1f(this.u("lightRange"), ADJUST.lightRange);
    gl.uniformMatrix3fv(this.u("toLab"), false, columnMajor(LAB_FROM_LMS));
    gl.uniformMatrix3fv(this.u("fromLab"), false, columnMajor(matInv(LAB_FROM_LMS)));
  }

  // img: a loaded <img> of the developed slide, encoded in `space` ("p3" or "srgb").
  setImage(img, space) {
    const gl = this.gl;
    this.canvas.width = img.naturalWidth;
    this.canvas.height = img.naturalHeight;
    if (this.wideCanvas) gl.drawingBufferColorSpace = space === "p3" ? "display-p3" : "srgb";
    gl.viewport(0, 0, img.naturalWidth, img.naturalHeight);
    gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);  // the file's own encoded values
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB8, gl.RGB, gl.UNSIGNED_BYTE, img);
    const toLms = matMul(LMS_FROM_XYZ, XYZ_FROM_RGB[space]);
    gl.uniformMatrix3fv(this.u("toLms"), false, columnMajor(toLms));
    gl.uniformMatrix3fv(this.u("fromLms"), false, columnMajor(matInv(toLms)));
    const convert = space === "p3" && !this.wideCanvas;  // show P3 values on an sRGB-only canvas
    gl.uniform1i(this.u("convertOut"), convert ? 1 : 0);
    gl.uniformMatrix3fv(this.u("outMat"), false,
      columnMajor(matMul(matInv(XYZ_FROM_RGB.srgb), XYZ_FROM_RGB.p3)));
  }

  render(adjust) {
    const gl = this.gl;
    const bands = new Float32Array(24);
    Object.keys(ADJUST.bands).forEach((name, i) => {
      (adjust.bands[name] || [0, 0, 0]).forEach((v, k) => { bands[i * 3 + k] = v / 100; });
    });
    const push = new Float32Array(6);
    const lift = new Float32Array(3);
    ADJUST.wheels.forEach((name, i) => {
      const [angle, amount, light] = adjust.wheels[name] || [0, 0, 0];
      const r = (amount / 100) * ADJUST.wheelRange;
      push[i * 2] = r * Math.cos((angle * Math.PI) / 180);
      push[i * 2 + 1] = r * Math.sin((angle * Math.PI) / 180);
      lift[i] = (light / 100) * ADJUST.wheelLight;
    });
    gl.uniform3fv(this.u("bands"), bands);
    gl.uniform2fv(this.u("push"), push);
    gl.uniform1fv(this.u("lift"), lift);
    gl.uniform1i(this.u("doBands"), Object.values(adjust.bands).some((v) => v.some((x) => x !== 0)) ? 1 : 0);
    gl.uniform1i(this.u("doWheels"), Object.values(adjust.wheels).some((v) => v[1] !== 0 || v[2] !== 0) ? 1 : 0);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
}

const WHEEL_FILL = 0.9;  // disc radius as a share of the canvas

// A colour wheel: drag to choose a hue and how strongly it tints; double-click to clear.
class Wheel {
  constructor(canvas, onChange) {
    this.canvas = canvas;
    this.onChange = onChange;
    this.value = [0, 0];  // angle (Oklab hue), amount 0-100
    this.disc = this.paintDisc();
    const set = (e) => {
      const box = canvas.getBoundingClientRect();
      const x = e.clientX - box.left - box.width / 2;
      const y = box.height / 2 - (e.clientY - box.top);
      const radius = (box.width / 2) * WHEEL_FILL;
      const r = Math.min(1, Math.hypot(x, y) / radius);
      this.value = [((Math.atan2(y, x) * 180) / Math.PI + 360) % 360, r < 0.06 ? 0 : Math.round(r * 100)];
      this.draw();
      this.onChange(this.value);
    };
    let dragging = false;
    canvas.addEventListener("pointerdown", (e) => { dragging = true; canvas.setPointerCapture(e.pointerId); set(e); });
    canvas.addEventListener("pointermove", (e) => { if (dragging) set(e); });
    canvas.addEventListener("pointerup", () => { dragging = false; });
    canvas.addEventListener("dblclick", () => { this.value = [0, 0]; this.draw(); this.onChange(this.value); });
  }

  paintDisc() {
    const size = this.canvas.width;
    const disc = new ImageData(size, size);
    const radius = (size / 2) * WHEEL_FILL;
    for (let py = 0; py < size; py++) {
      for (let px = 0; px < size; px++) {
        const x = px + 0.5 - size / 2;
        const y = size / 2 - (py + 0.5);
        const r = Math.hypot(x, y) / radius;
        if (r > 1) continue;
        const rgb = oklchRgb(0.62, 0.11 * r, (Math.atan2(y, x) * 180) / Math.PI);
        const o = (py * size + px) * 4;
        disc.data.set([rgb[0], rgb[1], rgb[2], Math.round(255 * Math.min(1, (1 - r) * radius))], o);
      }
    }
    return disc;
  }

  set(value) {
    this.value = value;
    this.draw();
  }

  draw() {
    const ctx = this.canvas.getContext("2d");
    const size = this.canvas.width;
    ctx.putImageData(this.disc, 0, 0);
    const radius = (size / 2) * WHEEL_FILL;
    const [angle, amount] = this.value;
    const r = (amount / 100) * radius;
    const x = size / 2 + r * Math.cos((angle * Math.PI) / 180);
    const y = size / 2 - r * Math.sin((angle * Math.PI) / 180);
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = "rgba(14, 13, 12, 0.85)";
    ctx.beginPath(); ctx.arc(x, y, 5.5, 0, Math.PI * 2); ctx.stroke();
    ctx.strokeStyle = "#efe8dc";
    ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.stroke();
  }
}
