(() => {
  "use strict";

  // ------------------------------------------------------------------ constants
  const DEFAULTS = {
    font: "caveat", font_size: 26, line_height: 1.4, letter_spacing: 0, word_spacing: 0,
    paragraph_spacing: 0, hyphenation: false, slant: 0,
    ink_color: "#1f3a8a", paper_style: "lined", paper_size: "a4", orientation: "portrait",
    mirror_even: false, paper_texture: true, shading: true, output: "print",
    margin_top: 22, margin_bottom: 15, margin_left: 25, margin_right: 12,
    preset: "natural", glyph_variation: 0.4, word_placement: 0.4, line_starts: 0.3,
    line_wobble: 0.3, ink_variation: 0.35, blur: 0.15, seed: 1,
  };
  const SAMPLE_HTML =
    "<h2>Calculation for number 1(c)</h2>" +
    '<p>Let <span class="math" contenteditable="false" data-tex="X_{it}"></span> = sector given to vehicle ' +
    '<span class="math" contenteditable="false" data-tex="V_i"></span> in shift <span class="math" contenteditable="false" data-tex="T_t"></span></p>' +
    '<p><span class="math" contenteditable="false" data-tex="\\Rightarrow"></span> no. of variables = <span class="math" contenteditable="false" data-tex="4 \\times 2 = 8"></span></p>' +
    "<p><br></p><table><tbody><tr><th>Shift</th><th>S1</th><th>S2</th><th>Idle</th></tr>" +
    "<tr><td>V1</td><td>0</td><td>1</td><td>1</td></tr><tr><td>V2</td><td>1</td><td>0</td><td>1</td></tr></tbody></table>" +
    "<p><br></p><p>Things it can do:</p><ul><li><b>Bold</b>, <u>underlined</u> and <s>crossed out</s> words</li>" +
    "<li>Lists, headings and <span style=\"color: rgb(163, 32, 43);\">coloured ink</span></li></ul>";
  const REALISM = [
    { key: "glyph_variation", label: "Letter shapes" }, { key: "word_placement", label: "Word placement" },
    { key: "line_starts", label: "Line starts" }, { key: "line_wobble", label: "Line wobble" },
    { key: "ink_variation", label: "Ink unevenness" }, { key: "blur", label: "Blur", keepPreset: true },
    { key: "slant", label: "Slant", min: -20, max: 20, step: 1, keepPreset: true, fmt: (v) => `${v}°` },
  ];
  const TYPE_STEPPERS = [
    { key: "font_size", label: "Font Size", min: 10, max: 90, step: 1, unit: "px" },
    { key: "line_height", label: "Line Height", min: 1, max: 3, step: 0.05, unit: "x", digits: 2 },
    { key: "letter_spacing", label: "Letter Spacing", min: 0, max: 20, step: 0.5, unit: "px", digits: 1 },
    { key: "word_spacing", label: "Word Spacing", min: 0, max: 60, step: 1, unit: "px" },
    { key: "paragraph_spacing", label: "Paragraph Spacing", min: 0, max: 200, step: 1, unit: "px" },
  ];
  const MARGIN_STEPPERS = ["top", "bottom", "left", "right"].map((side) => (
    { key: `margin_${side}`, label: side[0].toUpperCase() + side.slice(1), min: 0, max: 80, step: 1, unit: "mm" }
  ));
  // Language filter: a font qualifies when it has every one of these characters.
  const LANGS = [
    ["all", "All languages", ""], ["en", "English", "abcdefghijklmnopqrstuvwxyz"],
    ["lg", "Luganda", "abcdefgijklmnoprstuvwyzŋ"], ["sw", "Swahili", "abcdefghijklmnoprstuvwyz"],
    ["fr", "French", "éèêàâçôûùëïœ"], ["es", "Spanish", "ñáéíóúü¿¡"], ["pt", "Portuguese", "ãõáéíóúâêôç"],
    ["de", "German", "äöüß"], ["it", "Italian", "àèéìòù"], ["nl", "Dutch", "ëïé"], ["pl", "Polish", "ąćęłńóśźż"],
    ["tr", "Turkish", "çğıöşü"], ["vi", "Vietnamese", "ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ"],
    ["ru", "Russian", "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"], ["uk", "Ukrainian", "ґєії"],
    ["el", "Greek", "αβγδεζηθικλμνξοπρστυφχψω"], ["ar", "Arabic", "ابتثجحخدذرزسشصضطظعغفقكلمنهوي"],
    ["hi", "Hindi", "अआइईउऊएऐओऔकखगघचछजझटठडढतथदधनपफबभमयरलवशषसह"], ["th", "Thai", "กขคงจฉชซญดตถทนบปผพฟภมยรลวศษสหอฮ"],
    ["ko", "Korean", "가나다라마바사아자차카타파하"], ["ja", "Japanese", "あいうえおかきくけこさしすせそ"],
  ];
  const SCRIPT_ORDER = ["latin", "cyrillic", "arabic", "greek", "devanagari", "thai", "korean", "japanese"];
  const SHAPE_ICONS = {
    circle: '<ellipse cx="12" cy="12" rx="9" ry="6"/>',
    box: '<rect x="3.5" y="6.5" width="17" height="11" rx="1"/>',
    underline: '<path d="M3 16c4-1 14 1 18-.5"/>',
    arrow: '<path d="M4 18 19 6M19 6h-6M19 6v6"/>',
    check: '<path d="m4 12 5 5L20 6"/>',
    cross: '<path d="M5 5l14 14M19 5 5 19"/>',
    star: '<path d="m12 3 2.6 6 6.4.6-4.9 4.2 1.5 6.3L12 17l-5.6 3.1 1.5-6.3L3 9.6 9.4 9z"/>',
    scribble: '<path d="M3 14l2-4 2 4 2-4 2 4 2-4 2 4 2-4 2 4"/>',
    highlight: '<rect x="3" y="9" width="18" height="6" rx="1" fill="#ffe24d" stroke="none"/><path d="M3 12h18" stroke-opacity=".3"/>',
  };
  // Default size (fraction of the page) when a shape is placed with a click instead of a drag.
  const SHAPE_DEFAULT = { circle: [0.22, 0.05], box: [0.22, 0.05], underline: [0.25, 0], arrow: [0.12, -0.05],
    check: [0.05, 0.035], cross: [0.045, 0.035], star: [0.06, 0.045], scribble: [0.2, 0.02], highlight: [0.3, 0.025] };
  const OUTPUT_HINTS = {
    print: "Clean handwritten pages for printing or PDF.",
    photo: "Looks like a phone photo of the page lying on a desk.",
  };
  const STORE_KEY = "handwriter:v3";

  const $ = (id) => document.getElementById(id);
  const editor = $("editor");
  let options = null;
  let fonts = [];
  let settings = { ...DEFAULTS };
  let favorites = [];
  let customFontIds = [];
  let shapes = {};
  let scriptFilter = "all", langFilter = "all", fontQuery = "";
  let preview = { images: [], page: 0 };
  let inflight = null, renderTimer = null, saveTimer = null;
  let coverageDismissedFor = "", showAllCoverage = false;
  let savedRange = null;
  let activeShape = null;
  let selectedShape = -1;  // index into shapes[preview.page]

  // ------------------------------------------------------------------ storage
  function loadSaved() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORE_KEY) || "null");
      if (saved && typeof saved === "object") {
        settings = { ...DEFAULTS, ...(saved.settings || {}) };
        favorites = Array.isArray(saved.favorites) ? saved.favorites : [];
        customFontIds = Array.isArray(saved.customFonts) ? saved.customFonts : [];
        shapes = saved.shapes && typeof saved.shapes === "object" ? saved.shapes : {};
        return typeof saved.html === "string" ? saved.html : SAMPLE_HTML;
      }
      const old = JSON.parse(localStorage.getItem("handwriter:v2") || "null");  // keep text from the previous version
      if (old && typeof old.html === "string") {
        favorites = old.favorites || [];
        customFontIds = old.customFonts || [];
        return old.html;
      }
    } catch { /* storage unavailable: use defaults */ }
    return SAMPLE_HTML;
  }
  function save() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      try {
        localStorage.setItem(STORE_KEY, JSON.stringify({ html: editor.innerHTML, settings, favorites, customFonts: customFontIds, shapes }));
      } catch { }
    }, 300);
  }

  // ------------------------------------------------------------------ helpers
  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") node.className = v;
      else if (k === "style") node.style.cssText = v;
      else if (k === "html") node.innerHTML = v;
      else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
      else if (v === true) node.setAttribute(k, "");
      else if (v !== false && v != null) node.setAttribute(k, v);
    }
    for (const c of children) if (c != null) node.append(c);
    return node;
  }
  const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
  const esc = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  function setPressed(container, attr, value) {
    for (const b of container.querySelectorAll(`[${attr}]`)) b.setAttribute("aria-pressed", String(b.getAttribute(attr) === String(value)));
  }
  function pageMm() {
    const [w, h] = options.paper_sizes[settings.paper_size] || [210, 297];
    return settings.orientation === "landscape" ? [h, w] : [w, h];
  }
  const fontById = (id) => fonts.find((f) => f.id === id) || fonts[0];
  const isRuled = () => settings.paper_style !== "blank";

  function changed(key, value, delay = 300) {
    settings[key] = value;
    save();
    syncControls();
    styleEditor();
    if (key === "font") checkCoverage();
    if (key === "output") updateShapeUi();
    scheduleRender(delay);
  }

  function editorStatus(msg, isError = false, ms = 4000) {
    const strip = $("editor-status");
    strip.textContent = msg;
    strip.classList.toggle("error", isError);
    strip.hidden = !msg;
    clearTimeout(strip._t);
    if (msg && ms) strip._t = setTimeout(() => { strip.hidden = true; }, ms);
  }

  async function errorMessage(res) {
    try {
      const body = await res.json();
      if (typeof body.detail === "string") return body.detail;
      if (Array.isArray(body.detail)) return body.detail.map((d) => d.msg).join("; ");
    } catch { }
    return `Request failed (${res.status})`;
  }

  // ------------------------------------------------------------------ maths (mirror of app/mathtex.py)
  const TEX_SYMBOLS = {
    alpha: "α", beta: "β", gamma: "γ", delta: "δ", epsilon: "ε", varepsilon: "ε", zeta: "ζ", eta: "η", theta: "θ",
    vartheta: "ϑ", iota: "ι", kappa: "κ", lambda: "λ", mu: "μ", nu: "ν", xi: "ξ", pi: "π", rho: "ρ", sigma: "σ",
    tau: "τ", upsilon: "υ", phi: "φ", varphi: "φ", chi: "χ", psi: "ψ", omega: "ω", Gamma: "Γ", Delta: "Δ",
    Theta: "Θ", Lambda: "Λ", Xi: "Ξ", Pi: "Π", Sigma: "Σ", Phi: "Φ", Psi: "Ψ", Omega: "Ω",
    times: "×", div: "÷", pm: "±", mp: "∓", cdot: "·", ast: "∗", star: "⋆", circ: "∘", leq: "≤", le: "≤",
    geq: "≥", ge: "≥", neq: "≠", ne: "≠", approx: "≈", equiv: "≡", sim: "∼", simeq: "≃", cong: "≅", propto: "∝",
    ll: "≪", gg: "≫", infty: "∞", partial: "∂", nabla: "∇", sum: "∑", prod: "∏", int: "∫", oint: "∮",
    rightarrow: "→", to: "→", leftarrow: "←", gets: "←", Rightarrow: "⇒", implies: "⇒", Leftarrow: "⇐",
    leftrightarrow: "↔", Leftrightarrow: "⇔", iff: "⇔", uparrow: "↑", downarrow: "↓", mapsto: "↦",
    longrightarrow: "⟶", Longrightarrow: "⟹", therefore: "∴", because: "∵", in: "∈", notin: "∉", ni: "∋",
    subset: "⊂", subseteq: "⊆", supset: "⊃", supseteq: "⊇", cup: "∪", cap: "∩", emptyset: "∅", varnothing: "∅",
    forall: "∀", exists: "∃", neg: "¬", lnot: "¬", land: "∧", wedge: "∧", lor: "∨", vee: "∨", setminus: "∖",
    angle: "∠", perp: "⊥", parallel: "∥", degree: "°", deg: "°", ldots: "…", dots: "…", cdots: "⋯", prime: "′",
    hbar: "ℏ", ell: "ℓ", triangle: "△", square: "□", langle: "⟨", rangle: "⟩", lvert: "|", rvert: "|", mid: "|",
    vert: "|", "|": "‖", "%": "%", "{": "{", "}": "}", $: "$", "&": "&", "#": "#", _: "_", "\\": " ",
    " ": "\u2009", ",": "\u2009", ";": "\u2002", ":": "\u2005", quad: "\u2003", qquad: "\u2003\u2003", "!": "",
    big: "", Big: "", bigg: "", Bigg: "", displaystyle: "", textstyle: "",
  };
  const TEX_FUNCS = new Set(["sin", "cos", "tan", "cot", "sec", "csc", "log", "ln", "exp", "lim", "max", "min", "det",
    "arcsin", "arccos", "arctan", "sinh", "cosh", "tanh", "mod", "gcd"]);
  const BLACKBOARD = { R: "ℝ", N: "ℕ", Z: "ℤ", Q: "ℚ", C: "ℂ" };
  // Operators that get a little space either side (must match OPERATORS in app/mathtex.py).
  const TEX_OPS = new Set("=+×÷<>≤≥≠≈≡⇒⇐⇔→←±∓·∼≃≅∝∈∉⊂⊆⊃⊇∪∩");

  function texTokens(tex) {
    const out = [];
    for (let i = 0; i < tex.length;) {
      if (tex[i] === "\\") {
        let j = i + 1;
        if (j < tex.length && /[a-zA-Z]/.test(tex[j])) {
          while (j < tex.length && /[a-zA-Z]/.test(tex[j])) j++;
          out.push(tex.slice(i, j)); i = j;
        } else { out.push(tex.slice(i, j + 1)); i = j + 1; }
      } else { out.push(tex[i]); i++; }
    }
    return out;
  }
  function texParse(tex) {
    const t = texTokens((tex || "").slice(0, 1000));
    let i = 0;
    const peek = () => t[i], take = () => t[i++];
    const rawGroup = () => {
      if (peek() !== "{") return take() || "";
      take();
      let depth = 1, buf = "";
      while (i < t.length) {
        const tok = take();
        if (tok === "{") depth++;
        else if (tok === "}" && --depth === 0) break;
        buf += tok.startsWith("\\") && tok.length === 2 ? tok[1] : tok;
      }
      return buf;
    };
    const group = (d) => {
      if (peek() === "{") { take(); const n = seq(d + 1, "}"); take(); return n; }
      return peek() === undefined ? [] : atom(d + 1);
    };
    const atom = (d) => {
      const tok = take();
      if (tok === undefined) return [];
      if (d > 8) return [["text", tok]];
      if (tok.startsWith("\\") && tok.length > 1) {
        const name = tok.slice(1);
        if (["frac", "dfrac", "tfrac"].includes(name)) return [["frac", group(d), group(d)]];
        if (name === "sqrt") { if (peek() === "[") while (i < t.length && take() !== "]"); return [["sqrt", group(d)]]; }
        if (["overline", "bar", "vec", "hat"].includes(name)) return [["over", group(d)]];
        if (["text", "mathrm", "textrm", "mathit", "mathbf", "operatorname"].includes(name)) return [["text", rawGroup()]];
        if (name === "left" || name === "right") {
          let delim = take() || "";
          if (delim.startsWith("\\") && delim.length === 2) delim = delim[1];
          delim = { "\\langle": "⟨", "\\rangle": "⟩", "\\lvert": "|", "\\rvert": "|", "\\vert": "|" }[delim] || delim;
          return delim === "." || !delim ? [] : [["big", delim]];
        }
        if (name === "mathbb") return [["text", [...rawGroup()].map((c) => BLACKBOARD[c] || c).join("")]];
        if (TEX_FUNCS.has(name)) return [["text", name + "\u2009"]];
        if (name in TEX_SYMBOLS) return TEX_SYMBOLS[name] ? [["text", TEX_SYMBOLS[name]]] : [];
        return [["text", name]];
      }
      if (tok === "{" || tok === "}" || /^\s+$/.test(tok)) return [];  // like TeX: plain spaces are ignored
      return [["text", tok]];
    };
    const seq = (d, stop) => {
      const nodes = [];
      while (peek() !== undefined && peek() !== stop) {
        const tok = peek();
        if (tok === "^" || tok === "_") { take(); nodes.push([tok === "^" ? "sup" : "sub", group(d)]); }
        else if (tok === "}") take();
        else nodes.push(...atom(d));
      }
      return nodes;
    };
    return seq(0);
  }
  function texHtml(nodes) {
    return nodes.map((n) => {
      if (n[0] === "text") return [...n[1]].map((c) => (TEX_OPS.has(c) ? `<span class="op">${esc(c)}</span>` : esc(c))).join("");
      if (n[0] === "big") return `<span class="big">${esc(n[1])}</span>`;
      if (n[0] === "sup") return `<sup>${texHtml(n[1])}</sup>`;
      if (n[0] === "sub") return `<sub>${texHtml(n[1])}</sub>`;
      if (n[0] === "frac") return `<span class="frac"><span>${texHtml(n[1])}</span><span>${texHtml(n[2])}</span></span>`;
      if (n[0] === "sqrt") return `√<span class="sqrt">${texHtml(n[1])}</span>`;
      if (n[0] === "over") return `<span class="over">${texHtml(n[1])}</span>`;
      return "";
    }).join("");
  }
  const renderMathEls = (root) => {
    for (const m of root.querySelectorAll("[data-tex]")) {
      m.classList.add("math");
      m.contentEditable = "false";
      m.innerHTML = texHtml(texParse(m.dataset.tex));
    }
  };

  // ------------------------------------------------------------------ fonts
  const loadedFaces = new Map();
  function loadFace(font) {
    if (!font) return Promise.resolve();
    if (!loadedFaces.has(font.id)) {
      const face = new FontFace(`hw-${font.id}`, `url(${font.url})`);
      loadedFaces.set(font.id, face.load().then((f) => { document.fonts.add(f); return f; }).catch(() => null));
    }
    return loadedFaces.get(font.id);
  }

  function covers(font, cp) {
    const r = font.ranges;
    let lo = 0, hi = r.length - 1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (cp < r[mid][0]) hi = mid - 1;
      else if (cp > r[mid][1]) lo = mid + 1;
      else return true;
    }
    return false;
  }

  async function fetchFonts() {
    const res = await fetch(`/api/fonts?custom=${encodeURIComponent(customFontIds.join(","))}`);
    fonts = (await res.json()).fonts;
    customFontIds = customFontIds.filter((id) => fonts.some((f) => f.id === id));
    if (!fonts.some((f) => f.id === settings.font)) settings.font = fonts[0].id;
  }

  const tileObserver = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      loadFace(fontById(e.target.dataset.font));
      tileObserver.unobserve(e.target);
    }
  }, { rootMargin: "160px" });

  function renderFilters() {
    const scripts = new Set(fonts.flatMap((f) => f.scripts));
    const chips = [["all", "All"], ...SCRIPT_ORDER.filter((s) => scripts.has(s)).map((s) => [s, s])];
    $("script-chips").replaceChildren(...chips.map(([value, label]) => el("button", {
      type: "button", class: "chip", "data-script": value,
      onclick: () => { scriptFilter = value; setPressed($("script-chips"), "data-script", value); renderFontGrid(); },
    }, label)));
    setPressed($("script-chips"), "data-script", scriptFilter);
    const sel = $("lang-filter");
    sel.replaceChildren(...LANGS.map(([code, name]) => el("option", { value: code }, name)));
    sel.value = langFilter;
  }

  function fontMatchesLang(f) {
    if (langFilter === "all") return true;
    const chars = LANGS.find((l) => l[0] === langFilter)?.[2] || "";
    return [...chars].every((c) => covers(f, c.codePointAt(0)));
  }

  const STAR = '<svg viewBox="0 0 24 24"><path d="m12 3.5 2.6 5.6 6.1.7-4.5 4.2 1.2 6L12 17l-5.4 3 1.2-6-4.5-4.2 6.1-.7z"/></svg>';
  function renderFontGrid() {
    const q = fontQuery.trim().toLowerCase();
    const list = fonts.filter((f) => (!q || f.name.toLowerCase().includes(q))
      && (scriptFilter === "all" || f.scripts.includes(scriptFilter)) && fontMatchesLang(f));
    list.sort((a, b) => favorites.includes(b.id) - favorites.includes(a.id));  // favourites first, otherwise catalog order
    const tiles = list.map((f) => {
      const n = fonts.filter((x) => !x.custom).indexOf(f) + 1;
      const fav = favorites.includes(f.id);
      const star = el("button", {
        type: "button", class: `star${fav ? " on" : ""}`, title: fav ? "Remove from favourites" : "Add to favourites",
        "aria-label": fav ? `Remove ${f.name} from favourites` : `Add ${f.name} to favourites`, html: STAR,
        onclick: (e) => { e.stopPropagation(); toggleFavorite(f.id); },
      });
      const remove = f.custom ? el("button", {
        type: "button", class: "remove", title: "Remove this font", "aria-label": `Remove ${f.name}`,
        onclick: (e) => { e.stopPropagation(); removeCustomFont(f.id); },
      }, "×") : null;
      const tile = el("div", {
        class: "font-tile", role: "button", tabindex: "0", "data-font": f.id, title: f.name,
        "aria-label": f.name, "aria-pressed": String(f.id === settings.font),
        onclick: () => changed("font", f.id, 0),
        onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); changed("font", f.id, 0); } },
      },
        el("div", { class: "ft-top" }, el("span", { class: "ft-num" }, f.custom ? f.name : String(n)), el("span", { class: "ft-actions" }, remove, star)),
        el("div", { class: "ft-sample", style: `font-family: "hw-${f.id}", cursive` }, "Aa"),
        f.custom ? el("span", { class: "badge" }, "Yours") : null);
      tileObserver.observe(tile);
      return tile;
    });
    $("font-grid").replaceChildren(...(tiles.length ? tiles : [el("p", { class: "hint", style: "grid-column: 1 / -1" }, "No fonts match.")]));
  }

  function toggleFavorite(id) {
    favorites = favorites.includes(id) ? favorites.filter((x) => x !== id) : [...favorites, id];
    save();
    renderFontGrid();
  }

  function removeCustomFont(id) {
    customFontIds = customFontIds.filter((x) => x !== id);
    fonts = fonts.filter((f) => f.id !== id);
    if (settings.font === id) settings.font = fonts[0].id;
    save();
    renderFontGrid();
    changed("font", settings.font, 0);
  }

  async function uploadFont(file) {
    const text = $("dropzone-text");
    const original = "Drop custom font · max 10 MB";
    if (file.size > options.max_font_mb * 1024 * 1024) { text.textContent = `That file is over ${options.max_font_mb} MB.`; return; }
    text.textContent = `Uploading ${file.name}…`;
    try {
      const body = new FormData();
      body.append("file", file);
      const res = await fetch("/api/fonts/upload", { method: "POST", body });
      if (!res.ok) throw new Error(await errorMessage(res));
      const { font } = await res.json();
      if (!customFontIds.includes(font.id)) customFontIds.push(font.id);
      fonts = [...fonts.filter((f) => f.id !== font.id), font];
      renderFilters();
      renderFontGrid();
      text.textContent = original;
      changed("font", font.id, 0);
    } catch (e) {
      text.textContent = e.message || "Upload failed.";
      setTimeout(() => { text.textContent = original; }, 5000);
    }
  }

  // ------------------------------------------------------------------ settings panel
  function buildStepper(cfg) {
    const input = el("input", { type: "number", min: cfg.min, max: cfg.max, step: cfg.step, id: `st-${cfg.key}`, "aria-label": cfg.label });
    const fmt = (v) => (cfg.digits ? Number(v).toFixed(cfg.digits) : String(v));
    const set = (v) => {
      v = clamp(Math.round(v / cfg.step) * cfg.step, cfg.min, cfg.max);
      changed(cfg.key, Number(v.toFixed(4)));
    };
    const minus = el("button", { type: "button", "aria-label": `Decrease ${cfg.label}`, onclick: () => set(settings[cfg.key] - cfg.step) }, "−");
    const plus = el("button", { type: "button", "aria-label": `Increase ${cfg.label}`, onclick: () => set(settings[cfg.key] + cfg.step) }, "+");
    input.addEventListener("change", () => { const v = parseFloat(input.value); set(Number.isFinite(v) ? v : DEFAULTS[cfg.key]); });
    input._sync = () => {
      input.value = fmt(settings[cfg.key]);
      minus.disabled = settings[cfg.key] <= cfg.min;
      plus.disabled = settings[cfg.key] >= cfg.max;
    };
    return el("div", { class: "stepper" }, el("span", { class: "row-label" }, cfg.label),
      el("div", { class: "stepper-ctl" }, minus, el("span", { class: "val" }, input, el("span", { class: "unit" }, cfg.unit)), plus));
  }

  function buildSettings() {
    for (const [id, key] of [["output-mode", "output"], ["orientation", "orientation"]]) {
      for (const b of $(id).querySelectorAll("button")) b.addEventListener("click", () => changed(key, b.dataset.value, 0));
    }
    $("papers").replaceChildren(...options.papers.map((p) => el("button", {
      type: "button", class: "paper-tile", "data-paper": p.id, title: p.name, onclick: () => changed("paper_style", p.id, 0),
    }, el("img", { src: `/api/paper/${p.id}.jpg`, alt: "", loading: "lazy" }), el("span", {}, p.name))));
    const sizeSel = $("paper_size");
    sizeSel.replaceChildren(...Object.keys(options.paper_sizes).map((k) => el("option", { value: k }, k.toUpperCase())));
    sizeSel.addEventListener("change", () => changed("paper_size", sizeSel.value, 0));
    for (const key of ["mirror_even", "paper_texture", "shading", "hyphenation"]) {
      $(key).addEventListener("change", (e) => changed(key, e.target.checked, 0));
    }
    $("type-steppers").replaceChildren(...TYPE_STEPPERS.map(buildStepper));
    $("margin-steppers").replaceChildren(...MARGIN_STEPPERS.map(buildStepper));

    $("font-search").addEventListener("input", (e) => { fontQuery = e.target.value; renderFontGrid(); });
    $("lang-filter").addEventListener("change", (e) => { langFilter = e.target.value; renderFontGrid(); });
    const dz = $("dropzone");
    $("font-upload").addEventListener("change", (e) => { if (e.target.files[0]) uploadFont(e.target.files[0]); e.target.value = ""; });
    dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("over"); });
    dz.addEventListener("dragleave", () => dz.classList.remove("over"));
    dz.addEventListener("drop", (e) => { e.preventDefault(); dz.classList.remove("over"); if (e.dataTransfer.files[0]) uploadFont(e.dataTransfer.files[0]); });

    $("presets").replaceChildren(...options.presets.filter((p) => p !== "custom").map((name) => el("button", {
      type: "button", class: "chip", "data-preset": name,
      onclick: () => { Object.assign(settings, options.preset_values[name]); changed("preset", name, 0); },
    }, name)));
    $("realism-sliders").replaceChildren(...REALISM.map((cfg) => {
      const { key, label, min = 0, max = 1, step = 0.05 } = cfg;
      const input = el("input", { type: "range", min, max, step, id: `sl-${key}`, "aria-label": label });
      const out = el("output");
      input.addEventListener("input", () => {
        if (!cfg.keepPreset) settings.preset = "custom";
        changed(key, Number(input.value), 350);
      });
      input._sync = () => { input.value = settings[key]; out.textContent = cfg.fmt ? cfg.fmt(settings[key]) : `${Math.round(settings[key] * 100)}%`; };
      return el("label", { class: "slider" }, el("span", { class: "sl-head" }, label, out), input);
    }));
    for (const b of $("inks").querySelectorAll("button")) b.addEventListener("click", () => changed("ink_color", b.dataset.ink, 0));
    $("ink_color").addEventListener("input", (e) => changed("ink_color", e.target.value, 300));
  }

  function syncControls() {
    setPressed($("output-mode"), "data-value", settings.output);
    setPressed($("orientation"), "data-value", settings.orientation);
    setPressed($("papers"), "data-paper", settings.paper_style);
    setPressed($("presets"), "data-preset", settings.preset);
    setPressed($("inks"), "data-ink", settings.ink_color);
    setPressed($("font-grid"), "data-font", settings.font);
    $("output-hint").textContent = OUTPUT_HINTS[settings.output];
    $("paper_size").value = settings.paper_size;
    const [w, h] = pageMm();
    $("format-dims").textContent = `${+w.toFixed(1)} × ${+h.toFixed(1)} mm`;
    for (const key of ["mirror_even", "paper_texture", "shading", "hyphenation"]) $(key).checked = !!settings[key];
    $("ink_color").value = settings.ink_color;
    for (const node of document.querySelectorAll("[id^='st-'], [id^='sl-']")) node._sync?.();
  }

  // ------------------------------------------------------------------ editor look
  // The editor is drawn as the chosen paper, in the chosen font, at the same
  // proportions as the output page, so what you type is what you get.
  let measureCtx = null;
  async function styleEditor() {
    if (!options) return;
    const font = fontById(settings.font);
    const paper = options.papers.find((p) => p.id === settings.paper_style) || options.papers[0];
    const [pw] = pageMm();
    const s = editor.clientWidth / pw;           // screen px per mm
    const k = s / 4;                              // settings are px at 4 px/mm
    const size = settings.font_size * font.size_factor * k;
    const line = settings.font_size * settings.line_height * k;
    const st = editor.style;
    st.setProperty("--ed-font", `"hw-${font.id}", cursive`);
    st.setProperty("--ed-size", `${size}px`);
    st.setProperty("--ed-line", `${line}px`);
    st.setProperty("--ed-pt", `${settings.margin_top * s}px`);
    st.setProperty("--ed-pb", `${Math.max(settings.margin_bottom * s, line * 2)}px`);
    st.setProperty("--ed-pl", `${settings.margin_left * s}px`);
    st.setProperty("--ed-pr", `${settings.margin_right * s}px`);
    st.setProperty("--ed-indent", `${7 * s}px`);
    st.setProperty("--ed-pad", `${1.6 * s}px`);
    st.setProperty("--ed-ink", settings.ink_color);
    st.setProperty("--ed-paper", paper.color);
    st.setProperty("--ed-line-color", paper.line || "transparent");
    st.setProperty("--ed-margin-color", paper.margin_color);
    let gap = settings.paragraph_spacing * k;
    if (isRuled()) gap = Math.round(gap / line) * line;
    st.setProperty("--ed-pgap-px", `${gap}px`);
    st.letterSpacing = `${settings.letter_spacing * k}px`;
    st.wordSpacing = `${settings.word_spacing * k}px`;
    const mx = (settings.margin_left - 4) * s;
    st.setProperty("--ed-mx", paper.margin >= 1 && mx > 4 * s ? `${mx}px` : "-10px");
    st.setProperty("--ed-mx2", paper.margin >= 2 && mx > 4 * s ? `${mx - 1.3 * s}px` : "-10px");
    const step = line / 2 >= 3.5 * s && line / 2 <= 7 * s ? line / 2 : 5 * s;
    st.setProperty("--ed-step", `${step}px`);
    st.setProperty("--ed-gx", `${(settings.margin_left * s) % step}px`);
    st.setProperty("--ed-gy", `${(settings.margin_top * s + line) % step}px`);
    editor.classList.toggle("paper-rules", paper.kind === "rules" || paper.kind === "blank");
    editor.classList.toggle("paper-grid", paper.kind === "grid");
    editor.classList.toggle("paper-dots", paper.kind === "dots");
    if (paper.kind === "blank") st.setProperty("--ed-line-color", "transparent");
    editor.classList.toggle("para-gap", gap > 0);
    $("tb-color").value = settings.ink_color;
    document.querySelector(".tb-color").style.setProperty("--tb-color", settings.ink_color);
    $("math-preview").style.setProperty("--ed-ink", settings.ink_color);
    $("math-preview").style.fontFamily = `"hw-${font.id}", cursive`;

    // Line the text's baseline up with the ruled lines the way the renderer does.
    await loadFace(font);
    measureCtx ||= document.createElement("canvas").getContext("2d");
    measureCtx.font = `${size}px "hw-${font.id}"`;
    const m = measureCtx.measureText("Hg");
    const asc = m.fontBoundingBoxAscent || size * 0.8, desc = m.fontBoundingBoxDescent || size * 0.2;
    const cssBaseline = (line - (asc + desc)) / 2 + asc;
    st.setProperty("--ed-shift", `${line - Math.max(2, line * 0.08) - cssBaseline}px`);
  }

  // ------------------------------------------------------------------ editor behaviour
  function rememberSelection() {
    const sel = getSelection();
    if (sel.rangeCount && editor.contains(sel.anchorNode)) savedRange = sel.getRangeAt(0).cloneRange();
  }
  function restoreSelection() {
    editor.focus();
    if (!savedRange) {
      const r = document.createRange();
      r.selectNodeContents(editor);
      r.collapse(false);
      savedRange = r;
    }
    const sel = getSelection();
    sel.removeAllRanges();
    sel.addRange(savedRange);
  }

  function exec(cmd, value = null) {
    editor.focus();
    document.execCommand("styleWithCSS", false, cmd === "foreColor");
    document.execCommand(cmd, false, value);
    afterEdit();
  }

  function selectedBlocks() {
    const sel = getSelection();
    if (!sel.rangeCount || !editor.contains(sel.anchorNode)) return [];
    const range = sel.getRangeAt(0);
    const blocks = [...editor.querySelectorAll("p, div, h1, h2, h3, li")].filter((b) => range.intersectsNode(b));
    return blocks.filter((b) => !blocks.some((o) => o !== b && b.contains(o)));
  }

  function setBlockSize(v) {
    editor.focus();
    let blocks = selectedBlocks();
    if (!blocks.length) {
      document.execCommand("formatBlock", false, "p");
      blocks = selectedBlocks();
    }
    for (const b of blocks) {
      if (Number(v) === 1) { delete b.dataset.size; b.style.fontSize = ""; }
      else { b.dataset.size = v; b.style.fontSize = `${v * 100}%`; }
      if (!b.getAttribute("style")) b.removeAttribute("style");
    }
    afterEdit();
  }

  const closestIn = (node, selector) => {
    const elx = node?.nodeType === 1 ? node : node?.parentElement;
    const found = elx?.closest(selector);
    return found && editor.contains(found) ? found : null;
  };

  function updateToolbar() {
    const sel = getSelection();
    if (!sel.rangeCount || !editor.contains(sel.anchorNode)) return;
    for (const b of document.querySelectorAll(".tb[data-cmd]")) {
      const cmd = b.dataset.cmd;
      if (cmd === "undo" || cmd === "redo") continue;
      let on = false;
      try { on = document.queryCommandState(cmd); } catch { }
      b.setAttribute("aria-pressed", String(on));
    }
    let block = "p";
    try { block = (document.queryCommandValue("formatBlock") || "p").toLowerCase(); } catch { }
    $("tb-block").value = ["h1", "h2", "h3"].includes(block) ? block : "p";
    $("tb-size").value = selectedBlocks()[0]?.dataset.size || "1";
    $("table-bar").hidden = !closestIn(sel.anchorNode, "td, th");
  }

  function afterEdit() {
    const empty = !editor.textContent.trim() && !editor.querySelector("li, table, img, [data-tex]");
    editor.classList.toggle("is-empty", empty);
    save();
    checkCoverage();
    updateToolbar();
    scheduleRender(800);
  }

  // -- tables
  function buildTablePicker() {
    const grid = $("tp-grid");
    const cells = [];
    for (let r = 1; r <= 8; r++) for (let c = 1; c <= 8; c++) {
      const b = el("button", { type: "button", "aria-label": `${r} by ${c} table` });
      b.addEventListener("mouseenter", () => {
        for (const x of cells) x.b.classList.toggle("on", x.r <= r && x.c <= c);
        $("tp-label").textContent = `${r} × ${c}`;
      });
      b.addEventListener("mousedown", (e) => e.preventDefault());
      b.addEventListener("click", () => { closeTablePicker(); insertTable(r, c); });
      cells.push({ r, c, b });
      grid.append(b);
    }
    $("tb-table").addEventListener("mousedown", (e) => { e.preventDefault(); rememberSelection(); });
    $("tb-table").addEventListener("click", () => {
      const open = $("table-picker").hidden;
      $("table-picker").hidden = !open;
      $("tb-table").setAttribute("aria-expanded", String(open));
    });
    document.addEventListener("click", (e) => { if (!e.target.closest(".tb-pop-wrap")) closeTablePicker(); });
  }
  function closeTablePicker() { $("table-picker").hidden = true; $("tb-table").setAttribute("aria-expanded", "false"); }
  function insertTable(rows, cols) {
    restoreSelection();
    const row = (tag) => `<tr>${`<${tag}><br></${tag}>`.repeat(cols)}</tr>`;
    document.execCommand("insertHTML", false, `<table><tbody>${row("td").repeat(rows)}</tbody></table><p><br></p>`);
    afterEdit();
  }
  function tableAction(action) {
    const cell = closestIn(getSelection().anchorNode, "td, th");
    if (!cell) return;
    const tr = cell.parentElement, table = cell.closest("table");
    const col = [...tr.children].indexOf(cell);
    const rows = [...table.rows];
    const emptyCell = (tag = "td") => el(tag, {}, el("br"));
    if (action === "row-above" || action === "row-below") {
      const nr = el("tr", {}, ...[...tr.children].map(() => emptyCell()));
      tr.parentElement.insertBefore(nr, action === "row-above" ? tr : tr.nextSibling);
    } else if (action === "col-left" || action === "col-right") {
      for (const r of rows) {
        const ref = r.children[col];
        const nc = emptyCell(ref?.tagName === "TH" ? "th" : "td");
        if (!ref) r.append(nc);
        else r.insertBefore(nc, action === "col-left" ? ref : ref.nextSibling);
      }
    } else if (action === "del-row") {
      if (rows.length <= 1) table.remove(); else tr.remove();
    } else if (action === "del-col") {
      if (tr.children.length <= 1) table.remove(); else for (const r of rows) r.children[col]?.remove();
    } else if (action === "delete") {
      table.remove();
    }
    afterEdit();
  }

  // -- images
  async function uploadImage(file) {
    if (file.size > options.max_image_mb * 1024 * 1024) { editorStatus(`That image is over ${options.max_image_mb} MB.`, true); return; }
    editorStatus("Uploading image…", false, 0);
    try {
      const body = new FormData();
      body.append("file", file);
      const res = await fetch("/api/editor-images", { method: "POST", body });
      if (!res.ok) throw new Error(await errorMessage(res));
      const { url } = await res.json();
      restoreSelection();
      document.execCommand("insertHTML", false, `<p><img src="${esc(url)}" data-width="0.5" style="width: 50%;" alt=""></p><p><br></p>`);
      editorStatus("");
      afterEdit();
    } catch (e) {
      editorStatus(e.message || "Image upload failed.", true);
    }
  }
  let selectedImg = null;
  function selectImage(img) {
    selectedImg?.classList.remove("selected");
    selectedImg = img;
    img?.classList.add("selected");
    $("image-bar").hidden = !img;
    if (img) setPressed($("image-bar"), "data-img-width", img.dataset.width || "0.5");
  }
  function imageAction(value) {
    const img = selectedImg;
    if (!img) return;
    if (value === "remove") {
      const p = img.parentElement;
      img.remove();
      if (p !== editor && !p.textContent.trim() && !p.querySelector("img, [data-tex]")) p.remove();
      selectImage(null);
    } else {
      img.dataset.width = value;
      img.style.width = `${value * 100}%`;
      setPressed($("image-bar"), "data-img-width", value);
    }
    afterEdit();
  }

  // -- maths
  let editingMath = null;
  const MATH_KEYS = [["x²", "^{2}"], ["xₙ", "_{n}"], ["a⁄b", "\\frac{}{}"], ["√", "\\sqrt{}"], ["×", "\\times "], ["÷", "\\div "],
    ["±", "\\pm "], ["≠", "\\neq "], ["≤", "\\leq "], ["≥", "\\geq "], ["≈", "\\approx "], ["⇒", "\\Rightarrow "],
    ["→", "\\rightarrow "], ["∞", "\\infty "], ["π", "\\pi "], ["θ", "\\theta "], ["α", "\\alpha "], ["∑", "\\sum "],
    ["∫", "\\int "], ["∴", "\\therefore "], ["°", "^{\\circ}"]];
  function buildMathDialog() {
    const input = $("math-input");
    const update = () => { $("math-preview").innerHTML = texHtml(texParse(input.value)) || '<span class="faint">Preview</span>'; };
    input.addEventListener("input", update);
    $("math-keys").replaceChildren(...MATH_KEYS.map(([label, snippet]) => el("button", {
      type: "button", title: snippet.trim(),
      onclick: () => {
        const { selectionStart: a, selectionEnd: b, value } = input;
        input.value = value.slice(0, a) + snippet + value.slice(b);
        const brace = snippet.indexOf("{}");
        const caret = a + (brace >= 0 ? brace + 1 : snippet.length);
        input.focus();
        input.setSelectionRange(caret, caret);
        update();
      },
    }, label)));
    $("tb-math").addEventListener("mousedown", (e) => { e.preventDefault(); rememberSelection(); });
    $("tb-math").addEventListener("click", () => openMath(null));
    $("math-delete").addEventListener("click", () => {
      editingMath?.remove();
      $("math-dialog").close("deleted");
      afterEdit();
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("math-dialog").close("ok"); }
    });
    $("math-dialog").addEventListener("close", () => {
      const tex = input.value.trim();
      if ($("math-dialog").returnValue !== "ok" || !tex) { editingMath = null; return; }
      if (editingMath) {
        editingMath.dataset.tex = tex;
        editingMath.innerHTML = texHtml(texParse(tex));
      } else {
        restoreSelection();
        const span = el("span", { class: "math", contenteditable: "false", "data-tex": tex, html: texHtml(texParse(tex)) });
        const range = getSelection().getRangeAt(0);
        range.deleteContents();
        const space = document.createTextNode("\u00a0");
        range.insertNode(space);
        range.insertNode(span);
        range.setStartAfter(space);
        range.collapse(true);
        getSelection().removeAllRanges();
        getSelection().addRange(range);
      }
      editingMath = null;
      afterEdit();
    });
  }
  function openMath(existing) {
    editingMath = existing;
    $("math-input").value = existing ? existing.dataset.tex : "";
    $("math-ok").textContent = existing ? "Update" : "Insert";
    $("math-delete").hidden = !existing;
    $("math-input").dispatchEvent(new Event("input"));
    $("math-dialog").showModal();
    $("math-input").focus();
  }

  // -- import
  let importFile = null;
  function buildImport() {
    $("tb-import").addEventListener("mousedown", (e) => { e.preventDefault(); rememberSelection(); });
    $("tb-import").addEventListener("click", () => $("import-upload").click());
    $("import-upload").addEventListener("change", (e) => {
      importFile = e.target.files[0];
      e.target.value = "";
      if (!importFile) return;
      if (importFile.size > options.max_import_mb * 1024 * 1024) { editorStatus(`That file is over ${options.max_import_mb} MB.`, true); return; }
      const isPdf = /\.pdf$/i.test(importFile.name);
      $("import-file-name").textContent = importFile.name;
      $("import-pages-row").hidden = !isPdf;
      $("import-pages").value = "";
      $("import-error").textContent = "";
      $("import-dialog").showModal();
    });
    $("import-go").addEventListener("click", async () => {
      const btn = $("import-go");
      btn.disabled = true;
      btn.textContent = "Importing…";
      $("import-error").textContent = "";
      try {
        const body = new FormData();
        body.append("file", importFile);
        body.append("pages", $("import-pages").value);
        const res = await fetch("/api/import", { method: "POST", body });
        if (!res.ok) throw new Error(await errorMessage(res));
        const data = await res.json();
        const mode = document.querySelector('input[name="import-mode"]:checked').value;
        const tmp = el("div", { html: data.html });
        renderMathEls(tmp);
        if (mode === "replace") editor.innerHTML = tmp.innerHTML;
        else editor.insertAdjacentHTML("beforeend", tmp.innerHTML);
        $("import-dialog").close();
        editorStatus(`Imported ${importFile.name}${data.pages ? ` (${data.pages} page PDF)` : ""}.`);
        afterEdit();
      } catch (e) {
        $("import-error").textContent = e.message || "Import failed.";
      } finally {
        btn.disabled = false;
        btn.textContent = "Import";
      }
    });
  }

  function setupEditor(html) {
    editor.innerHTML = html;
    renderMathEls(editor);
    document.execCommand("defaultParagraphSeparator", false, "p");
    editor.addEventListener("input", afterEdit);
    editor.addEventListener("paste", (e) => {
      // Keep useful structure (maths, bold, headings, lists, tables) but never other sites' fonts/colours.
      e.preventDefault();
      const html = e.clipboardData.getData("text/html");
      const text = e.clipboardData.getData("text/plain");
      const converted = html ? cleanPastedHtml(html) : textToHtml(text);
      if (converted == null || !converted.trim()) document.execCommand("insertText", false, text);
      else {
        document.execCommand("insertHTML", false, converted);
        renderMathEls(editor);
      }
      afterEdit();
    });
    editor.addEventListener("keydown", (e) => {
      if (!(e.metaKey || e.ctrlKey)) return;
      const key = e.key.toLowerCase();
      if (key === "b" || key === "u") { e.preventDefault(); exec(key === "b" ? "bold" : "underline"); }
    });
    editor.addEventListener("click", (e) => {
      const math = e.target.closest(".math");
      if (math && editor.contains(math)) { rememberSelection(); openMath(math); return; }
      selectImage(e.target.tagName === "IMG" ? e.target : null);
    });
    document.addEventListener("selectionchange", () => { updateToolbar(); });
    editor.addEventListener("blur", rememberSelection);

    for (const b of document.querySelectorAll(".tb[data-cmd]")) {
      b.addEventListener("mousedown", (e) => e.preventDefault()); // keep the text selection
      b.addEventListener("click", () => exec(b.dataset.cmd));
    }
    for (const b of $("table-bar").querySelectorAll("button")) {
      b.addEventListener("mousedown", (e) => e.preventDefault());
      b.addEventListener("click", () => tableAction(b.dataset.table));
    }
    for (const b of $("image-bar").querySelectorAll("button")) b.addEventListener("click", () => imageAction(b.dataset.imgWidth));
    $("tb-block").addEventListener("change", (e) => exec("formatBlock", e.target.value));
    $("tb-size").addEventListener("change", (e) => setBlockSize(e.target.value));
    // The colour picker takes focus away from the editor, which can drop the text selection.
    // Remember it before the picker opens and put it back before colouring.
    const colorLabel = document.querySelector(".tb-color");
    colorLabel.addEventListener("pointerdown", rememberSelection);
    const applyColor = (value) => {
      colorLabel.style.setProperty("--tb-color", value);
      if (!savedRange) { editorStatus("Select some words first, then pick a colour."); return; }
      restoreSelection();
      document.execCommand("styleWithCSS", false, true);
      document.execCommand("foreColor", false, value);
      rememberSelection();
      afterEdit();
    };
    $("tb-color").addEventListener("input", (e) => applyColor(e.target.value));
    $("tb-color").addEventListener("change", (e) => applyColor(e.target.value));
    $("tb-image").addEventListener("mousedown", (e) => { e.preventDefault(); rememberSelection(); });
    $("tb-image").addEventListener("click", () => $("image-upload").click());
    $("image-upload").addEventListener("change", (e) => { if (e.target.files[0]) uploadImage(e.target.files[0]); e.target.value = ""; });
    $("tb-clear").addEventListener("click", () => {
      if (!confirm("Clear all text?")) return;
      editor.innerHTML = "<p><br></p>";
      editor.focus();
      afterEdit();
    });
    buildTablePicker();
    buildMathDialog();
    buildImport();
    new ResizeObserver(() => styleEditor()).observe(editor);
    editor.classList.toggle("is-empty", !editor.textContent.trim());
  }

  // ------------------------------------------------------------------ paste conversion
  // AI chats (Gemini, ChatGPT …) copy maths as \( … \), \[ … \] or $$ … $$, or as KaTeX/MathJax HTML.
  const MATH_DELIMS = /\\\(([\s\S]+?)\\\)|\\\[([\s\S]+?)\\\]|\$\$([\s\S]+?)\$\$/g;
  const mathSpan = (tex) => el("span", { class: "math", contenteditable: "false", "data-tex": tex.trim(), html: texHtml(texParse(tex.trim())) });
  function appendText(dst, text) {
    let pos = 0;
    for (const m of text.matchAll(MATH_DELIMS)) {
      if (m.index > pos) dst.append(text.slice(pos, m.index));
      const tex = (m[1] ?? m[2] ?? m[3] ?? "").replace(/\s+/g, " ");
      if (tex.trim()) dst.append(mathSpan(tex));
      pos = m.index + m[0].length;
    }
    if (pos < text.length) dst.append(text.slice(pos));
  }
  function centreLoneFormulas(root) {
    // A paragraph that is just one formula is a displayed equation: centre it like the AI chat did.
    for (const p of root.querySelectorAll("p")) {
      const kids = [...p.childNodes].filter((n) => !(n.nodeType === 3 && !n.textContent.trim()) && n.nodeName !== "BR");
      if (kids.length === 1 && kids[0].classList?.contains("math") && !p.style.textAlign) p.style.textAlign = "center";
    }
  }
  const BLOCK_MAP = { P: "p", DIV: "p", H1: "h1", H2: "h2", H3: "h3", H4: "h3", H5: "h3", H6: "h3", LI: "li", UL: "ul",
    OL: "ol", TABLE: "table", THEAD: "tbody", TBODY: "tbody", TFOOT: "tbody", TR: "tr", TD: "td", TH: "th", BLOCKQUOTE: "p", PRE: "p" };
  const INLINE_MAP = { B: "b", STRONG: "b", U: "u", INS: "u", S: "s", DEL: "s", STRIKE: "s", BR: "br" };
  const PASTE_SKIP = new Set(["SCRIPT", "STYLE", "TEMPLATE", "SVG", "IMG", "PICTURE", "VIDEO", "AUDIO", "BUTTON", "INPUT", "SELECT",
    "TEXTAREA", "NOSCRIPT", "IFRAME", "OBJECT", "HEAD", "TITLE", "META", "LINK", "CANVAS"]);
  function texFromElement(node) {
    if (node.dataset?.math) return node.dataset.math;
    if (node.dataset?.tex) return node.dataset.tex;
    const ann = node.querySelector?.('annotation[encoding="application/x-tex"]');
    return ann ? ann.textContent : null;
  }
  function isMathElement(node) {
    const c = node.classList;
    return node.tagName.toUpperCase() === "MATH" || ["katex", "katex-display", "MathJax", "math-inline", "math-block"].some((k) => c?.contains(k))
      || node.hasAttribute?.("data-math") || node.hasAttribute?.("data-tex");
  }
  const isDisplayMath = (node) => node.classList?.contains("katex-display") || node.classList?.contains("math-block")
    || node.getAttribute?.("display") === "block" || !!node.closest?.(".katex-display, .math-block");
  function walkPasted(src, dst) {
    for (const node of src.childNodes) {
      if (node.nodeType === 3) { appendText(dst, node.textContent.replace(/[ \t\r\n]+/g, " ")); continue; }
      if (node.nodeType !== 1) continue;
      const tag = node.tagName.toUpperCase();
      if (PASTE_SKIP.has(tag)) continue;
      if (isMathElement(node)) {
        const tex = texFromElement(node);
        if (tex) {
          const span = mathSpan(tex);
          dst.append(isDisplayMath(node) ? el("p", { style: "text-align: center;" }, span) : span);
          continue;
        }
      }
      let mapped = BLOCK_MAP[tag] || INLINE_MAP[tag];
      if (tag === "DIV" && node.querySelector("p, div, h1, h2, h3, h4, h5, h6, ul, ol, li, table, blockquote, pre")) mapped = null;
      if (!mapped && /^(bold|[6-9]00)$/.test(node.style?.fontWeight || "")) mapped = "b";  // Google Docs style bold
      if (mapped === "br") { dst.append(el("br")); continue; }
      if (!mapped) { walkPasted(node, dst); continue; }
      const out = document.createElement(mapped);
      const align = node.style?.textAlign || node.getAttribute("align");
      if (BLOCK_MAP[tag] && ["center", "right", "justify"].includes(align)) out.style.textAlign = align;
      walkPasted(node, out);
      dst.append(out);
    }
  }
  function cleanPastedHtml(html) {
    const doc = new DOMParser().parseFromString(html, "text/html");  // inert: nothing in it runs or loads
    const out = el("div");
    walkPasted(doc.body, out);
    centreLoneFormulas(out);
    return out.innerHTML;
  }
  function inlineMarkdown(dst, text) {
    for (const part of text.split(/(\*\*[^*]+\*\*|__[^_]+__)/)) {
      if (/^(\*\*|__).+(\*\*|__)$/.test(part)) { const b = el("b"); appendText(b, part.slice(2, -2)); dst.append(b); }
      else if (part) appendText(dst, part);
    }
  }
  function textToHtml(text) {
    const hasMath = /\\\(|\\\[|\$\$/.test(text);
    const hasMarkdown = /(^|\n)\s*(#{1,6}\s|[-*•]\s|\d+[.)]\s)|\*\*[^*]+\*\*/.test(text);
    if (!hasMath && !hasMarkdown) return null;
    text = text.replace(/\r\n?/g, "\n").replace(MATH_DELIMS, (m) => m.replace(/\s*\n\s*/g, " "));
    const out = el("div");
    let list = null, blank = false;
    for (const raw of text.split("\n")) {
      const line = raw.trim();
      if (!line) {
        list = null;
        if (!blank && out.childNodes.length) out.append(el("p", {}, el("br")));
        blank = true;
        continue;
      }
      blank = false;
      let m;
      if ((m = line.match(/^(#{1,6})\s+(.*)$/))) {
        list = null;
        const h = el(m[1].length === 1 ? "h1" : m[1].length === 2 ? "h2" : "h3");
        inlineMarkdown(h, m[2]);
        out.append(h);
      } else if ((m = line.match(/^([-*•]|\d+[.)])\s+(.*)$/))) {
        const tag = /^\d/.test(m[1]) ? "ol" : "ul";
        if (!list || list.tagName.toLowerCase() !== tag) { list = el(tag); out.append(list); }
        const li = el("li");
        inlineMarkdown(li, m[2]);
        list.append(li);
      } else {
        list = null;
        const para = el("p");
        inlineMarkdown(para, line);
        out.append(para);
      }
    }
    centreLoneFormulas(out);
    return out.innerHTML;
  }

  // ------------------------------------------------------------------ character coverage
  function editorText() {
    const clone = editor.cloneNode(true);
    for (const m of clone.querySelectorAll("[data-tex]")) m.remove();  // maths symbols use the symbol font
    return clone.textContent;
  }
  function checkCoverage() {
    if (!fonts.length) return;
    const chars = [...new Set(editorText().replace(/\s/g, ""))];
    const font = fontById(settings.font);
    const missing = chars.filter((c) => !covers(font, c.codePointAt(0)));
    const box = $("coverage");
    const key = `${font.id}|${missing.join("")}`;
    if (!missing.length || coverageDismissedFor === key) { box.hidden = true; return; }
    box.hidden = false;
    const pct = Math.round((missing.length / chars.length) * 100);
    $("coverage-title").textContent = `Some characters aren't in this font (${pct}%)`;
    $("coverage-missing").textContent = missing.slice(0, 30).join(" ") + (missing.length > 30 ? " …" : "");
    const ranked = fonts.filter((f) => f.id !== font.id)
      .map((f) => ({ f, score: chars.filter((c) => covers(f, c.codePointAt(0))).length / chars.length }))
      .filter((x) => x.score > 0)
      .sort((a, b) => b.score - a.score);
    const shown = showAllCoverage ? ranked : ranked.slice(0, 6);
    $("coverage-all").textContent = ranked.length > 6 ? (showAllCoverage ? "Show fewer" : `Show all (${ranked.length})`) : "";
    $("coverage-fonts").replaceChildren(...shown.map(({ f, score }) => el("button", {
      type: "button", class: "chip", onclick: () => changed("font", f.id, 0),
    }, f.name, el("small", {}, `${Math.round(score * 100)}%`))));
    box.dataset.key = key;
  }

  // ------------------------------------------------------------------ shapes
  function buildShapes() {
    const labels = { circle: "Circle", box: "Box", underline: "Underline", arrow: "Arrow", check: "Tick", cross: "Cross",
      star: "Star", scribble: "Scribble", highlight: "Highlight" };
    $("shape-picker").replaceChildren(...options.shapes.map((t) => el("button", {
      type: "button", class: "shape-btn", "data-shape": t, title: labels[t],
      html: `<svg viewBox="0 0 24 24">${SHAPE_ICONS[t] || ""}</svg><span>${labels[t] || t}</span>`,
      onclick: () => { activeShape = activeShape === t ? null : t; updateShapeUi(); },
    })));
    const color = $("shape-color");
    color.value = settings.ink_color;
    const syncColor = () => document.querySelector(".shape-color").style.setProperty("--shape-color", color.value);
    color.addEventListener("input", syncColor);
    syncColor();
    $("shape-undo").addEventListener("click", () => {
      const list = shapes[preview.page];
      if (list?.length) { list.pop(); if (!list.length) delete shapes[preview.page]; shapesChanged(); }
    });
    $("shape-clear").addEventListener("click", () => { delete shapes[preview.page]; selectedShape = -1; shapesChanged(); });
    document.addEventListener("keydown", (e) => {
      if (selectedShape < 0 || !["Delete", "Backspace"].includes(e.key) || e.target.closest?.("input, textarea, [contenteditable='true']")) return;
      e.preventDefault();
      deleteShape(selectedShape);
    });

    const frame = $("preview-frame");
    const draft = $("shape-draft");
    let start = null;
    const point = (e) => {
      const r = $("preview-img").getBoundingClientRect();
      return { x: clamp((e.clientX - r.left) / r.width, 0, 1), y: clamp((e.clientY - r.top) / r.height, 0, 1), r };
    };
    frame.addEventListener("pointerdown", (e) => {
      if (!canPlaceShapes() || e.target.closest(".zoom-btn, .shape-hit") || e.button !== 0) return;
      e.preventDefault();
      try { frame.setPointerCapture(e.pointerId); } catch { /* not all pointers can be captured */ }
      start = point(e);
    });
    frame.addEventListener("pointermove", (e) => {
      if (!start) return;
      const p = point(e);
      const fr = frame.getBoundingClientRect();
      Object.assign(draft.style, {
        left: `${Math.min(start.x, p.x) * p.r.width + p.r.left - fr.left}px`, top: `${Math.min(start.y, p.y) * p.r.height + p.r.top - fr.top}px`,
        width: `${Math.abs(p.x - start.x) * p.r.width}px`, height: `${Math.abs(p.y - start.y) * p.r.height}px`,
      });
      draft.hidden = false;
    });
    frame.addEventListener("pointerup", (e) => {
      if (!start) return;
      const p = point(e);
      draft.hidden = true;
      let { x: x1, y: y1 } = start, { x: x2, y: y2 } = p;
      start = null;
      if (Math.hypot((x2 - x1) * 210, (y2 - y1) * 297) < 3) {  // a click, not a drag: use a default size
        const [dw, dh] = SHAPE_DEFAULT[activeShape];
        if (activeShape === "arrow") { x2 = x1 + dw; y2 = y1 + dh; }
        else { x1 -= dw / 2; x2 = x1 + dw; y1 -= dh / 2; y2 = y1 + dh; }
      }
      (shapes[preview.page] ||= []).push({
        type: activeShape, x1, y1, x2, y2, color: activeShape === "highlight" ? null : $("shape-color").value,
      });
      selectedShape = -1;
      shapesChanged();
      flashShapeHint(`${activeShape[0].toUpperCase() + activeShape.slice(1)} added ✓ — click it later to select or delete it.`);
    });
    updateShapeUi();
  }
  const canPlaceShapes = () => !!activeShape && settings.output === "print" && preview.images.length > 0;
  function shapesChanged() {
    save();
    updateShapeUi();
    scheduleRender(0);
  }
  function deleteShape(index) {
    const list = shapes[preview.page];
    if (!list || !list[index]) return;
    list.splice(index, 1);
    if (!list.length) delete shapes[preview.page];
    selectedShape = -1;
    shapesChanged();
  }
  let hintTimer = null;
  function flashShapeHint(msg) {
    $("shape-hint").textContent = msg;
    $("shape-hint").classList.add("ok");
    clearTimeout(hintTimer);
    hintTimer = setTimeout(() => { $("shape-hint").classList.remove("ok"); updateShapeUi(); }, 3500);
  }
  function renderShapeLayer() {
    const layer = $("shape-layer");
    const list = settings.output === "print" ? shapes[preview.page] || [] : [];
    if (selectedShape >= list.length) selectedShape = -1;
    layer.replaceChildren(...list.map((sh, i) => {
      const lx = Math.min(sh.x1, sh.x2), ty = Math.min(sh.y1, sh.y2);
      const hit = el("button", {
        type: "button", class: `shape-hit${i === selectedShape ? " selected" : ""}`, "aria-label": `${sh.type} shape — click to select`,
        style: `left:${lx * 100}%;top:${ty * 100}%;width:${Math.abs(sh.x2 - sh.x1) * 100}%;height:${Math.abs(sh.y2 - sh.y1) * 100}%`,
        onclick: (e) => { e.stopPropagation(); selectedShape = i === selectedShape ? -1 : i; renderShapeLayer(); },
      }, el("span", { class: "del", role: "button", "aria-label": "Delete shape", onclick: (e) => { e.stopPropagation(); deleteShape(i); } }, "×"));
      return hit;
    }));
  }
  function updateShapeUi() {
    if (!options) return;
    setPressed($("shape-picker"), "data-shape", activeShape);
    $("preview-frame").classList.toggle("placing", canPlaceShapes());
    const n = (shapes[preview.page] || []).length;
    renderShapeLayer();
    $("shape-count").textContent = n ? `${n} on this page` : "";
    $("shape-undo").disabled = !n;
    $("shape-clear").disabled = !n;
    if ($("shape-hint").classList.contains("ok")) return;
    $("shape-hint").textContent = settings.output === "photo"
      ? "Switch Output to Print to place shapes — they still show up in Photo output."
      : activeShape ? "Click or drag on the preview to place it. Click the shape again to stop."
        : "Pick a shape, then click or drag on the preview. Shapes are drawn in pen like the text.";
  }

  // ------------------------------------------------------------------ preview & downloads
  function setStatus(msg, isError = false) {
    $("status").textContent = msg;
    $("status").classList.toggle("error", isError);
  }

  const payload = () => JSON.stringify({ html: editor.innerHTML, settings, shapes });

  function scheduleRender(delay) {
    clearTimeout(renderTimer);
    renderTimer = setTimeout(render, delay);
  }

  async function render() {
    inflight?.abort();
    const ctrl = new AbortController();
    inflight = ctrl;
    $("preview-busy").classList.add("on");
    setStatus("Writing…");
    const started = performance.now();
    try {
      const res = await fetch("/api/preview", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: payload(), signal: ctrl.signal,
      });
      if (!res.ok) throw new Error(await errorMessage(res));
      const data = await res.json();
      preview.images = data.images;
      preview.page = Math.min(preview.page, data.images.length - 1);
      showPage();
      const secs = ((performance.now() - started) / 1000).toFixed(1);
      setStatus(`${data.pages} page${data.pages === 1 ? "" : "s"} · ready in ${secs}s` +
        (data.truncated ? ` · cut off at ${options.max_pages} pages` : ""));
    } catch (e) {
      if (e.name !== "AbortError") setStatus(e.message || "Something went wrong.", true);
    } finally {
      if (inflight === ctrl) { $("preview-busy").classList.remove("on"); inflight = null; }
    }
  }

  function showPage() {
    const n = preview.images.length;
    const i = preview.page;
    const [w, h] = pageMm();
    $("preview-frame").style.aspectRatio = settings.output === "photo" ? `${w * 1.14} / ${h * 1.1}` : `${w} / ${h}`;
    $("preview-img").src = preview.images[i] || "";
    $("preview-img").alt = `Preview of page ${i + 1}`;
    $("dl-page").textContent = `Download page ${i + 1}`;

    const pager = $("pager");
    const go = (p) => { preview.page = p; showPage(); };
    const btn = (label, p, attrs = {}) => el("button", { type: "button", onclick: () => go(p), ...attrs }, label);
    const items = [btn("‹", i - 1, { disabled: i === 0, "aria-label": "Previous page" })];
    const pages = new Set([0, n - 1, i - 1, i, i + 1].filter((p) => p >= 0 && p < n));
    let last = -1;
    for (const p of [...pages].sort((a, b) => a - b)) {
      if (p - last > 1) items.push(el("span", { class: "gap" }, "…"));
      items.push(btn(String(p + 1), p, p === i ? { "aria-current": "page" } : {}));
      last = p;
    }
    items.push(btn("›", i + 1, { disabled: i >= n - 1, "aria-label": "Next page" }));
    pager.replaceChildren(...items);
    pager.hidden = n <= 1;
    updateShapeUi();
  }

  async function download(format, button, page) {
    const label = button.innerHTML;
    button.disabled = true;
    button.textContent = "Preparing…";
    try {
      const qs = new URLSearchParams({ format });
      if (page) qs.set("page", page);
      const res = await fetch(`/api/export?${qs}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: payload(),
      });
      if (!res.ok) throw new Error(await errorMessage(res));
      const blob = await res.blob();
      const name = (res.headers.get("content-disposition") || "").match(/filename="([^"]+)"/)?.[1] || `handwriting.${format}`;
      const url = URL.createObjectURL(blob);
      const a = el("a", { href: url, download: name });
      document.body.append(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } catch (e) {
      setStatus(e.message || "Download failed.", true);
    } finally {
      button.disabled = false;
      button.innerHTML = label;
      if (page) $("dl-page").textContent = `Download page ${preview.page + 1}`;
    }
  }

  // ------------------------------------------------------------------ init
  async function init() {
    const html = loadSaved();
    try {
      options = await (await fetch("/api/options")).json();
      await fetchFonts();
    } catch {
      setStatus("Can't reach the server.", true);
      return;
    }
    buildSettings();
    renderFilters();
    renderFontGrid();
    setupEditor(html);
    buildShapes();
    syncControls();
    styleEditor();
    checkCoverage();

    $("coverage-close").addEventListener("click", () => { coverageDismissedFor = $("coverage").dataset.key; $("coverage").hidden = true; });
    $("coverage-all").addEventListener("click", () => { showAllCoverage = !showAllCoverage; checkCoverage(); });
    $("dl-pdf").addEventListener("click", (e) => download("pdf", e.currentTarget));
    $("dl-zip").addEventListener("click", (e) => download("zip", e.currentTarget));
    $("dl-page").addEventListener("click", (e) => download("image", e.currentTarget, preview.page + 1));
    $("shuffle").addEventListener("click", () => changed("seed", Math.floor(Math.random() * 2 ** 31), 0));
    $("zoom-btn").addEventListener("click", () => {
      if (!preview.images.length) return;
      $("zoom-img").src = preview.images[preview.page];
      $("zoom").showModal();
    });
    $("zoom").addEventListener("click", (e) => { if (e.target === $("zoom")) $("zoom").close(); });
    render();
  }

  init();
})();
