// ─── Configuration ───────────────────────────────────────────────
var NEBULA_POS = [0.85, 1.5];
var FPS = 60;

// ─── Color Helpers ──────────────────────────────────────────────
function srgbToLinear(c) {
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

function parseCSSColor(value) {
  if (!value) return null;
  var tmp = document.createElement("div");
  tmp.style.color = value;
  document.body.appendChild(tmp);
  var computed = getComputedStyle(tmp).color;
  document.body.removeChild(tmp);
  var m = computed.match(/[\d.]+/g);
  if (!m || m.length < 3) return null;
  return [srgbToLinear(+m[0] / 255), srgbToLinear(+m[1] / 255), srgbToLinear(+m[2] / 255)];
}

function getAccentColors() {
  var style = getComputedStyle(document.documentElement);

  // Stop 1: accent-primary token
  var accent = parseCSSColor(
    style.getPropertyValue("--accent-primary").trim()
    || style.getPropertyValue("--accent").trim()
    || style.getPropertyValue("--accent-a11").trim()
    || style.getPropertyValue("--accent-9").trim()
  );

  // Stop 2: read actual background color from CSS
  var bg = parseCSSColor(
    style.getPropertyValue("--background").trim()
    || style.getPropertyValue("--card-background").trim()
    || style.backgroundColor
  );
  if (!bg) bg = isDarkMode() ? [0.0, 0.0, 0.0] : [1.0, 1.0, 1.0];

  return { c1: bg, c2: accent };
}

// ─── Vertex Shader ──────────────────────────────────────────────
var VERT = `#version 300 es
precision mediump float;
in vec2 aPos;
out vec2 vUv;
void main() {
  gl_Position = vec4(aPos, 0, 1);
  vUv = aPos * 0.5 + 0.5;
}`;

// ─── Fragment Shader ──────────────
var FRAG = `#version 300 es
precision highp float;
precision mediump int;

in vec2 vUv;
uniform float uTime;
uniform vec2 uRes;
uniform vec3 uC1;
uniform vec3 uC2;
uniform vec2 uNPos;
uniform float uDarkMode;
out vec4 O;

const float TAU = 6.28318530718;

const mat3 GOLD = mat3(
  -0.571464913, 0.814921382, 0.096597072,
  -0.278044873, -0.303026659, 0.911518454,
  0.772087367, 0.494042493, 0.399753815);

const mat3 GOLD_PHI = mat3(
  -0.924648, -0.449886, 1.249265,
  1.318571, -0.490308, 0.800377,
  0.156297, 1.474868, 0.646816);

const mat3 ROT1 = mat3(
  -0.57, 0.81, 0.10,
  -0.28, -0.30, 0.91,
  0.77, 0.49, 0.40);

const mat3 ROT2 = mat3(
  0.1746, -0.6561, 0.7314,
  0.9452, 0.3072, 0.0211,
  -0.2389, 0.6865, 0.6863);

float interleavedGradientNoise(vec2 st) {
  return fract(52.9829189 * fract(dot(st, vec2(0.06711056, 0.00583715))));
}

vec3 safeCbrt(vec3 v) {
  return sign(v) * pow(abs(v), vec3(1.0 / 3.0));
}

vec3 oklab_mix(vec3 lin1, vec3 lin2, float a) {
  const mat3 kCONEtoLMS = mat3(
    0.4121656120, 0.2118591070, 0.0883097947,
    0.5362752080, 0.6807189584, 0.2818474174,
    0.0514575653, 0.1074065790, 0.6302613616);
  const mat3 kLMStoCONE = mat3(
    4.0767245293, -1.2681437731, -0.0041119885,
    -3.3072168827, 2.6093323231, -0.7034763098,
    0.2307590544, -0.3411344290, 1.7068625689);
  vec3 lms1 = safeCbrt(kCONEtoLMS * lin1);
  vec3 lms2 = safeCbrt(kCONEtoLMS * lin2);
  vec3 lms = mix(lms1, lms2, a);
  lms *= 1.0 + 0.02 * a * (1.0 - a);
  return kLMStoCONE * (lms * lms * lms);
}

vec3 Tonemap_ACES(vec3 x) {
  return (x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14);
}

vec3 pal(float t, vec3 a, vec3 b, vec3 c, vec3 d) {
  return a + b * cos(TAU * (c * t + d));
}

float dot_noise(vec3 p) {
  return dot(cos(GOLD * p), sin(GOLD_PHI * p));
}

float sdCircle(vec2 uv, vec2 scale) {
  return length(uv / scale) - 1.0;
}

float getDistance(vec2 uv, float scale) {
  vec2 finalScale = scale * vec2(1.0 + 0.62 * 0.5, 1.0 - 0.62 * 0.5);
  finalScale *= mix(0.8, 1.2, 0.69);
  return sdCircle(uv, finalScale);
}

float density(vec3 q, float amplitude) {
  float d = 0.0;
  float fd = 0.0;

  q.xy = (q.xy - 0.5) * vec2(1.0 - 0.48 * 0.5, 1.0 + 0.48 * 0.5) + 0.5;
  q.z *= mix(1.0, 0.001, 0.93);

  float n = dot_noise(q * vec3(1.6, 0.8, 1.1)) - 0.2;
  d += amplitude * n;
  fd += max(0.0, d * 0.5 + 0.5) * amplitude;

  q = (ROT1 * (q * vec3(0.8, 1.6, 0.9))) * 2.2 + vec3(1.025, 0.575, 0.425);
  amplitude *= 0.5 + 0.5 * (n * 0.5);
  n = dot_noise(q) - 0.2;
  d += amplitude * n;
  float val = d * 0.5 + 0.5;
  fd += (val * val) * amplitude;

  q = (ROT2 * (q * vec3(1.6, 0.8, 1.1))) * 2.6 + vec3(2.05, 1.15, 0.85);
  amplitude *= 0.5 + 0.5 * abs(n);
  n = dot_noise(q) + 0.2;
  d += amplitude * n;
  val = d * 0.5 + 0.5;
  fd += (val * val) * amplitude;

  return fd;
}

// ── Grain helpers ──
uvec2 pcg2d(uvec2 v) {
  v = v * 1664525u + 1013904223u;
  v.x += v.y * v.y * 1664525u + 1013904223u;
  v.y += v.x * v.x * 1664525u + 1013904223u;
  v ^= v >> 16;
  v.x += v.y * v.y * 1664525u + 1013904223u;
  v.y += v.x * v.x * 1664525u + 1013904223u;
  return v;
}

float randFibo(vec2 p) {
  uvec2 v = pcg2d(floatBitsToUint(p));
  return float(v.x ^ v.y) / 4294967295.0;
}

vec3 grainBlend(vec3 src, vec3 dst) {
  return vec3(
    dst.x <= 0.5 ? 2.0 * src.x * dst.x : 1.0 - 2.0 * (1.0 - dst.x) * (1.0 - src.x),
    dst.y <= 0.5 ? 2.0 * src.y * dst.y : 1.0 - 2.0 * (1.0 - dst.y) * (1.0 - src.y),
    dst.z <= 0.5 ? 2.0 * src.z * dst.z : 1.0 - 2.0 * (1.0 - dst.z) * (1.0 - src.z));
}

vec3 srgb_from_linear(vec3 lin) {
  return pow(max(lin, vec3(0.0)), vec3(1.0 / 2.2));
}

// ── Main ──
void main() {
  vec2 aspect = vec2(uRes.x / uRes.y, 1.0);
  vec2 uv = vUv;
  vec2 pos = uNPos;

  vec2 sdfUv = (uv - pos) * aspect;
  float sdf = getDistance(sdfUv, 2.5);
  float ampSdf = smoothstep(0.1, 0.69 * 1.5, -sdf);

  vec3 col = vec3(0.0);
  float transmittance = 1.0;

  if (ampSdf > 0.0) {
    vec2 uvCentered = (uv - pos) * aspect;
    vec3 ro = vec3(pos, -3.0);
    vec3 rd = normalize(vec3(uvCentered, 1.0));

    const int STEPS = 40;
    float MAX_DIST = 2.86;
    float baseStep = MAX_DIST / float(STEPS);
    float ign = interleavedGradientNoise(uRes * vUv);
    float t = baseStep * ign * 0.999;
    float wrappedTime = uTime * 0.05;

    // Grayscale palette (Unicorn nebula layer originals)
    vec3 colorCenter = oklab_mix(vec3(0.1608), vec3(0.8157), 0.5);
    vec3 colorDelta  = oklab_mix(vec3(0.8157), vec3(0.1608), 0.5);
    float absorptionFactor = baseStep * -6.0;
    float scale = 8.0;
    float ampBase = mix(0.2, 1.2, 0.63) * 2.0;
    float amplitude = ampBase;

    vec3 q_ro = ro * scale + vec3(0.65, 0.0, 2.66) * wrappedTime;
    vec3 q_rd = rd * scale;
    float accumulatedLight = 0.0;
    bool hit = false;
    int emptySteps = 0;

    for (int i = 0; i < STEPS; i++) {
      if (transmittance < 0.01 || t > MAX_DIST) break;
      if (!hit && emptySteps > 20) break;
      if (accumulatedLight > 0.33) break;

      vec3 q = q_ro + q_rd * t;
      float d = density(q, amplitude);
      float depthRatio = t / MAX_DIST;
      float pz = ro.z + rd.z * t;
      d *= smoothstep(-3.0, -2.0, pz) * (1.0 - depthRatio * depthRatio);

      if (d > 0.0001) {
        float d_val = 0.25 / d;
        float atten = smoothstep(0.0, 1.0, d_val);
        vec3 mixed = pal(atten,
          colorCenter, colorDelta,
          vec3(0.5, 1.0, 1.5), vec3(0.5, 0.0, -0.5));
        vec3 light = mixed * atten;
        float absorption = exp(-d * baseStep * 20.0);
        vec3 contribution = light * d * transmittance * absorptionFactor;
        col += contribution;
        accumulatedLight += abs(dot(contribution, vec3(0.299, 0.587, 0.114)));
        transmittance *= absorption;
        emptySteps = 0;
        hit = true;
      } else {
        emptySteps++;
      }

      t += baseStep;
    }
  }

  // Compositing
  col *= ampSdf;
  col = Tonemap_ACES(col);
  float ft = mix(1.0, transmittance, ampSdf);
  ft = smoothstep(0.0, 1.0, ft);

  // Composite onto white background 
  vec3 composite = col + ft;

  // Gradient map: dark areas → accent (uC2), bright areas → background (uC1)
  float lum = dot(composite, vec3(0.299, 0.587, 0.114));
  float gmPos = smoothstep(0.0, 1.0, lum);
  vec3 gmColor = srgb_from_linear(oklab_mix(uC2, uC1, gmPos));

  float nebulaOpacity = max(0.0, 1.0 - ft);

  // Grain 
  if (nebulaOpacity > 0.001) {
    vec2 st = vUv * uRes;
    float delta = fract(uTime / 20.0);
    vec3 grainRGB = vec3(
      randFibo(st + vec2(1, 2) + delta),
      randFibo(st + vec2(2, 3) + delta),
      randFibo(st + vec2(3, 4) + delta));
    gmColor = mix(gmColor, grainBlend(grainRGB, gmColor), 0.17);
  }

  // Composite onto card background
  vec3 cardBg = srgb_from_linear(uC1);
  float opacity = nebulaOpacity * mix(0.5, 1.0, uDarkMode);
  vec3 finalColor = mix(cardBg, gmColor, opacity);
  O = vec4(finalColor, 1.0);
}`;

// ─── WebGL Setup ─────────────────────────────────────────────────
function initWebGL(canvas) {
  var gl = canvas.getContext("webgl2", { alpha: true, premultipliedAlpha: false });
  if (!gl) return null;

  function compile(src, type) {
    var s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
      console.error("Shader error:", gl.getShaderInfoLog(s));
      return null;
    }
    return s;
  }

  var vs = compile(VERT, gl.VERTEX_SHADER);
  var fs = compile(FRAG, gl.FRAGMENT_SHADER);
  if (!vs || !fs) return null;

  var pg = gl.createProgram();
  gl.attachShader(pg, vs);
  gl.attachShader(pg, fs);
  gl.linkProgram(pg);
  if (!gl.getProgramParameter(pg, gl.LINK_STATUS)) {
    console.error("Program error:", gl.getProgramInfoLog(pg));
    return null;
  }

  var buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);

  var aPos = gl.getAttribLocation(pg, "aPos");
  gl.enableVertexAttribArray(aPos);
  gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);

  gl.useProgram(pg);

  var uTime = gl.getUniformLocation(pg, "uTime");
  var uRes = gl.getUniformLocation(pg, "uRes");
  var uC1 = gl.getUniformLocation(pg, "uC1");
  var uC2 = gl.getUniformLocation(pg, "uC2");
  var uNPos = gl.getUniformLocation(pg, "uNPos");
  var uDarkMode = gl.getUniformLocation(pg, "uDarkMode");

  gl.uniform2fv(uNPos, NEBULA_POS);

  gl.enable(gl.BLEND);
  gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

  return { gl: gl, uTime: uTime, uRes: uRes, uDarkMode: uDarkMode, uC1: uC1, uC2: uC2 };
}

// ─── Theme Detection ─────────────────────────────────────────────
function isDarkMode() {
  var html = document.documentElement;
  var theme = html.getAttribute("data-theme");
  if (theme === "dark") return true;
  if (theme === "light") return false;
  if (html.classList.contains("dark")) return true;
  if (html.classList.contains("light")) return false;
  // Fallback: check computed background luminance
  var bg = getComputedStyle(document.body).backgroundColor;
  var m = bg.match(/\d+/g);
  if (m) {
    var lum = (0.299 * +m[0] + 0.587 * +m[1] + 0.114 * +m[2]) / 255;
    return lum < 0.5;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

// ─── Injection ───────────────────────────────────────────────────
(function () {
  var renderer = null;
  var wrapper = null;
  var rafId = null;
  var lastFrame = 0;
  var interval = 1000 / FPS;

  function applyTheme() {
    if (!renderer || !wrapper) return;
    var dark = isDarkMode();
    renderer.gl.uniform1f(renderer.uDarkMode, dark ? 1.0 : 0.0);
    wrapper.style.mixBlendMode = dark ? "screen" : "multiply";

    var colors = getAccentColors();
    renderer.gl.uniform3fv(renderer.uC1, colors.c1);
    renderer.gl.uniform3fv(renderer.uC2, colors.c2);
  }

  function removeScene() {
    var existing = document.querySelector(".background-graphic-wrapper");
    if (existing) {
      existing.remove();
      if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
      renderer = null;
      wrapper = null;
    }
  }

  function injectScene() {
    // Only activate on pages that have the nebula-anchor marker
    var marker = document.querySelector(".nebula-anchor");
    if (!marker) { removeScene(); return; }

    var cw = marker.closest("main") || marker.closest("article") || document.body;
    if (cw.querySelector(".background-graphic-wrapper")) return;

    wrapper = document.createElement("div");
    wrapper.className = "background-graphic-wrapper";

    var canvas = document.createElement("canvas");
    wrapper.appendChild(canvas);
    cw.appendChild(wrapper);

    renderer = initWebGL(canvas);
    if (!renderer) return;

    applyTheme();

    function resize() {
      var r = wrapper.getBoundingClientRect();
      var dpr = Math.min(window.devicePixelRatio, 1.5);
      canvas.width = r.width * dpr;
      canvas.height = r.height * dpr;
      canvas.style.width = r.width + "px";
      canvas.style.height = r.height + "px";
      renderer.gl.viewport(0, 0, canvas.width, canvas.height);
      renderer.gl.uniform2f(renderer.uRes, canvas.width, canvas.height);
    }

    resize();
    window.addEventListener("resize", resize);

    var start = performance.now();
    function frame(now) {
      rafId = requestAnimationFrame(frame);
      if (now - lastFrame < interval) return;
      lastFrame = now;
      renderer.gl.uniform1f(renderer.uTime, (now - start) / 1000);
      renderer.gl.clear(renderer.gl.COLOR_BUFFER_BIT);
      renderer.gl.drawArrays(renderer.gl.TRIANGLE_STRIP, 0, 4);
    }
    rafId = requestAnimationFrame(frame);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", injectScene);
  } else {
    injectScene();
  }

  // Watch for navigation changes
  var observer = new MutationObserver(function () {
    injectScene();
  });
  observer.observe(document.body, { childList: true, subtree: true });

  // Watch for theme changes (class/attribute on <html>)
  var themeObserver = new MutationObserver(applyTheme);
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class", "data-theme"]
  });

  // Also watch prefers-color-scheme media query
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyTheme);
})();


// ─── California corpus search ─────────────────────────────────────
// Search is deliberately just-in-time: fetch and scan only the selected code
// asset, rather than putting 186k records into the page or an AI context.
(function () {
  var root = document.querySelector('[data-corpus-search]');
  if (!root) return;
  var select = root.querySelector('[data-corpus-code]');
  var form = root.querySelector('[data-corpus-form]');
  var input = root.querySelector('[data-corpus-query]');
  var status = root.querySelector('[data-corpus-status]');
  var results = root.querySelector('[data-corpus-results]');
  var manifest;
  var names = {};

  function esc(value) { return String(value || '').toLowerCase(); }
  function terms(value) {
    return (esc(value).match(/[a-z0-9][a-z0-9._-]{1,}/g) || []).filter(function (x) {
      return !/^(the|and|for|that|this|with|from|what|how|does|code|section|california)$/.test(x);
    });
  }
  function score(rec, query, words) {
    var hay = [rec.citation, rec.section, rec.text, rec.path, rec.division, rec.part, rec.title].map(esc).join(' ');
    var value = 0;
    var exact = esc(query);
    if (exact && hay.indexOf(exact) !== -1) value += 24;
    if (rec.citation && esc(rec.citation).indexOf(exact) !== -1) value += 100;
    words.forEach(function (word) {
      var hits = hay.split(word).length - 1;
      if (hits) value += Math.min(18, hits * 3) + (esc(rec.citation).indexOf(word) !== -1 ? 20 : 0);
    });
    if (rec.path && words.some(function (word) { return esc(rec.path).indexOf(word) !== -1; })) value += 6;
    if (rec.history && /history|amend|effective|repeal/.test(esc(query))) value += 5;
    return value;
  }
  function codePage(code) { return '/codes/' + String(code).toLowerCase(); }
  function render(items, query) {
    results.textContent = '';
    if (!items.length) {
      status.textContent = 'No matching sections found. Try a citation, a shorter phrase, or another code.';
      return;
    }
    status.textContent = 'Showing ' + items.length + ' strongest matches for “' + query + '”.';
    items.forEach(function (item) {
      var rec = item.rec;
      var li = document.createElement('li');
      var h = document.createElement('h3');
      var a = document.createElement('a');
      a.href = codePage(rec.code);
      a.textContent = rec.citation || (rec.code + ' § ' + rec.section);
      h.appendChild(a);
      li.appendChild(h);
      var meta = document.createElement('p');
      meta.className = 'corpus-search__meta';
      meta.textContent = [names[rec.code] || rec.code, rec.path].filter(Boolean).join(' · ');
      li.appendChild(meta);
      var text = document.createElement('p');
      text.textContent = String(rec.text || '').slice(0, 720) + (String(rec.text || '').length > 720 ? '…' : '');
      li.appendChild(text);
      if (rec.history) {
        var hist = document.createElement('small');
        hist.textContent = rec.history;
        li.appendChild(hist);
      }
      results.appendChild(li);
    });
  }
  async function scan(code, query, limit) {
    var url = '/assets/corpus/law/' + code + '.jsonl.gz';
    var response = await fetch(url);
    if (!response.ok || !response.body || !window.DecompressionStream) throw new Error('Corpus asset unavailable');
    var stream = response.body.pipeThrough(new DecompressionStream('gzip')).getReader();
    var decoder = new TextDecoder();
    var buffer = '';
    var words = terms(query);
    var best = [];
    function add(line) {
      if (!line.trim()) return;
      var rec;
      try { rec = JSON.parse(line); } catch (_) { return; }
      if (rec.kind !== 'section') return;
      var value = score(rec, query, words);
      if (value <= 0) return;
      best.push({ rec: rec, value: value });
      best.sort(function (a, b) { return b.value - a.value; });
      if (best.length > limit) best.pop();
    }
    while (true) {
      var chunk = await stream.read();
      buffer += decoder.decode(chunk.value || new Uint8Array(), { stream: !chunk.done });
      var lines = buffer.split('\n');
      buffer = lines.pop() || '';
      lines.forEach(add);
      if (chunk.done) break;
    }
    add(buffer);
    return best;
  }
  async function run(query) {
    var codes = select.value ? [select.value] : manifest.datasets.map(function (x) { return x.abbr; });
    var all = [];
    results.textContent = '';
    for (var i = 0; i < codes.length; i++) {
      status.textContent = 'Searching ' + names[codes[i]] + ' (' + (i + 1) + ' of ' + codes.length + ')…';
      var found = await scan(codes[i], query, 12);
      all = all.concat(found).sort(function (a, b) { return b.value - a.value; }).slice(0, 20);
    }
    render(all, query);
  }
  fetch('/assets/corpus/manifest.json').then(function (r) { return r.json(); }).then(function (data) {
    manifest = data;
    data.datasets.forEach(function (item) {
      names[item.abbr] = item.name;
      var option = document.createElement('option');
      option.value = item.abbr;
      option.textContent = item.abbr + ' — ' + item.name;
      select.appendChild(option);
    });
    status.textContent = data.datasets.length + ' code datasets ready; search by citation or text.';
  }).catch(function () { status.textContent = 'The corpus catalog could not be loaded.'; });
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    var query = input.value.trim();
    if (query.length < 2 || !manifest) return;
    run(query).catch(function () { status.textContent = 'Search could not read the compressed corpus asset in this browser.'; });
  });
})();
