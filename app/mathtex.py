"""A small LaTeX-style maths parser: just enough for school and university notes.

Supported: x^2, x_{12}, \\frac{a}{b}, \\sqrt{x}, \\overline{x}, \\text{words},
Greek letters and common symbols (\\times, \\Rightarrow, \\leq, \\infty, ...).
Anything unknown is kept as plain text, so a typo never breaks the page.

The result is a tree of nodes:
    ("text", "abc") | ("sup", [nodes]) | ("sub", [nodes])
    ("frac", [num], [den]) | ("sqrt", [nodes]) | ("over", [nodes])
    ("big", "(")  -- a tall bracket from \\left( or \\right)
The browser has a matching JavaScript version (static/app.js: texToHtml).
"""
from __future__ import annotations

SYMBOLS = {
    # Greek
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "varepsilon": "ε", "zeta": "ζ",
    "eta": "η", "theta": "θ", "vartheta": "ϑ", "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν",
    "xi": "ξ", "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ", "upsilon": "υ", "phi": "φ", "varphi": "φ",
    "chi": "χ", "psi": "ψ", "omega": "ω", "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ",
    "Pi": "Π", "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
    # operators & relations
    "times": "×", "div": "÷", "pm": "±", "mp": "∓", "cdot": "·", "ast": "∗", "star": "⋆", "circ": "∘",
    "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥", "neq": "≠", "ne": "≠", "approx": "≈", "equiv": "≡",
    "sim": "∼", "simeq": "≃", "cong": "≅", "propto": "∝", "ll": "≪", "gg": "≫",
    "infty": "∞", "partial": "∂", "nabla": "∇", "sum": "∑", "prod": "∏", "int": "∫", "oint": "∮",
    # arrows
    "rightarrow": "→", "to": "→", "leftarrow": "←", "gets": "←", "Rightarrow": "⇒", "implies": "⇒",
    "Leftarrow": "⇐", "leftrightarrow": "↔", "Leftrightarrow": "⇔", "iff": "⇔", "uparrow": "↑",
    "downarrow": "↓", "mapsto": "↦", "longrightarrow": "⟶", "Longrightarrow": "⟹",
    # logic & sets
    "therefore": "∴", "because": "∵", "in": "∈", "notin": "∉", "ni": "∋", "subset": "⊂", "subseteq": "⊆",
    "supset": "⊃", "supseteq": "⊇", "cup": "∪", "cap": "∩", "emptyset": "∅", "varnothing": "∅",
    "forall": "∀", "exists": "∃", "neg": "¬", "lnot": "¬", "land": "∧", "wedge": "∧", "lor": "∨", "vee": "∨",
    "setminus": "∖",
    # misc
    "angle": "∠", "perp": "⊥", "parallel": "∥", "degree": "°", "deg": "°", "ldots": "…", "dots": "…",
    "cdots": "⋯", "prime": "′", "hbar": "ℏ", "ell": "ℓ", "triangle": "△", "square": "□",
    "langle": "⟨", "rangle": "⟩", "lvert": "|", "rvert": "|", "mid": "|", "vert": "|", "|": "‖",
    # escapes & spacing
    "%": "%", "{": "{", "}": "}", "$": "$", "&": "&", "#": "#", "_": "_", "\\": " ",
    " ": "\u2009", ",": "\u2009", ";": "\u2002", ":": "\u2005", "quad": "\u2003", "qquad": "\u2003\u2003", "!": "",
    # sizing commands that only matter in real TeX
    "big": "", "Big": "", "bigg": "", "Bigg": "", "displaystyle": "", "textstyle": "",
}
BLACKBOARD = {"R": "ℝ", "N": "ℕ", "Z": "ℤ", "Q": "ℚ", "C": "ℂ"}
FUNCTIONS = {"sin", "cos", "tan", "cot", "sec", "csc", "log", "ln", "exp", "lim", "max", "min", "det", "arcsin",
             "arccos", "arctan", "sinh", "cosh", "tanh", "mod", "gcd"}
# Operators that get a little space either side, like typeset maths.
OPERATORS = set("=+×÷<>≤≥≠≈≡⇒⇐⇔→←±∓·∼≃≅∝∈∉⊂⊆⊃⊇∪∩")
MAX_TEX = 1000
MAX_DEPTH = 8


def _tokens(tex: str) -> list[str]:
    out, i = [], 0
    while i < len(tex):
        c = tex[i]
        if c == "\\":
            j = i + 1
            if j < len(tex) and tex[j].isalpha():
                while j < len(tex) and tex[j].isalpha():
                    j += 1
                out.append(tex[i:j])
                i = j
            else:
                out.append(tex[i:j + 1])
                i = j + 1
        else:
            out.append(c)
            i += 1
    return out


class _Parser:
    def __init__(self, tex: str) -> None:
        self.t = _tokens(tex[:MAX_TEX])
        self.i = 0

    def peek(self) -> str | None:
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self) -> str | None:
        tok = self.peek()
        self.i += tok is not None
        return tok

    def group(self, depth: int) -> list:
        """A {braced group} or a single token, as used after ^, _ and \\frac."""
        tok = self.peek()
        if tok == "{":
            self.take()
            nodes = self.seq(depth + 1, stop="}")
            self.take()
            return nodes
        if tok is None:
            return []
        return self.atom(depth + 1)

    def raw_group(self) -> str:
        if self.peek() != "{":
            return self.take() or ""
        self.take()
        depth, buf = 1, []
        while (tok := self.take()) is not None:
            if tok == "{":
                depth += 1
            elif tok == "}":
                depth -= 1
                if depth == 0:
                    break
            buf.append(tok[1:] if tok.startswith("\\") and len(tok) == 2 else tok)
        return "".join(buf)

    def atom(self, depth: int) -> list:
        tok = self.take()
        if tok is None:
            return []
        if depth > MAX_DEPTH:
            return [("text", tok)]
        if tok.startswith("\\") and len(tok) > 1:
            name = tok[1:]
            if name == "frac" or name == "dfrac" or name == "tfrac":
                return [("frac", self.group(depth), self.group(depth))]
            if name == "sqrt":
                if self.peek() == "[":  # \sqrt[n]{x}: index dropped, root kept
                    while self.take() not in (None, "]"):
                        pass
                return [("sqrt", self.group(depth))]
            if name in ("overline", "bar", "vec", "hat"):
                return [("over", self.group(depth))]
            if name in ("text", "mathrm", "textrm", "mathit", "mathbf", "operatorname"):
                return [("text", self.raw_group())]
            if name in ("left", "right"):
                delim = self.take() or ""
                if delim.startswith("\\") and len(delim) == 2:
                    delim = delim[1]
                delim = {"\\langle": "⟨", "\\rangle": "⟩", "\\lvert": "|", "\\rvert": "|", "\\vert": "|"}.get(delim, delim)
                return [] if delim in (".", "") else [("big", delim)]
            if name == "mathbb":
                return [("text", "".join(BLACKBOARD.get(c, c) for c in self.raw_group()))]
            if name in FUNCTIONS:
                return [("text", name + "\u2009")]  # thin space after sin, log, …
            if name in SYMBOLS:
                return [("text", SYMBOLS[name])] if SYMBOLS[name] else []
            return [("text", name)]
        if tok in "{}" or tok.isspace():
            return []  # like TeX: plain spaces in maths are ignored; operators get spacing instead
        return [("text", tok)]

    def seq(self, depth: int, stop: str | None = None) -> list:
        nodes: list = []
        while (tok := self.peek()) is not None and tok != stop:
            if tok in ("^", "_"):
                self.take()
                nodes.append(("sup" if tok == "^" else "sub", self.group(depth)))
            elif tok == "}":
                self.take()  # stray closing brace
            else:
                nodes.extend(self.atom(depth))
        return _merge(nodes)


def _merge(nodes: list) -> list:
    """Join neighbouring text nodes."""
    out: list = []
    for n in nodes:
        if n[0] == "text" and out and out[-1][0] == "text":
            out[-1] = ("text", out[-1][1] + n[1])
        else:
            out.append(n)
    return out


def parse(tex: str) -> list:
    return _Parser(tex or "").seq(0)


def plain(nodes: list) -> str:
    """Rough plain-text version (used for character coverage)."""
    out = []
    for n in nodes:
        if n[0] in ("text", "big"):
            out.append(n[1])
        elif n[0] == "frac":
            out.append(plain(n[1]) + "/" + plain(n[2]))
        else:
            out.append(plain(n[1]))
    return "".join(out)


DELIMITED = __import__("re").compile(r"\\\((.+?)\\\)|\\\[(.+?)\\\]|\$\$(.+?)\$\$", __import__("re").S)


def split_delimited(text: str) -> list[tuple[str, bool]]:
    """Split text containing \\( … \\), \\[ … \\] or $$ … $$ into (piece, is_maths) parts."""
    out: list[tuple[str, bool]] = []
    pos = 0
    for m in DELIMITED.finditer(text):
        if m.start() > pos:
            out.append((text[pos:m.start()], False))
        tex = next(g for g in m.groups() if g is not None).strip()
        if tex:
            out.append((tex, True))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], False))
    return out
