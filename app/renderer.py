"""Handwriting page renderer.

Text (parsed into styled blocks) is laid out line by line, then every
character is drawn on its own with small random changes (rotation, size,
slant, baseline, spacing, ink pressure) so no two copies of a letter look
identical. Words and lines get their own wobble on top. Maths formulas,
tables (hand-drawn grid) and images are laid out on the same ruled lines.
Each ink colour is a separate layer that gets ink unevenness and blur, and the
layers are blended onto generated paper. Shapes the user placed on the
preview are drawn as pen strokes. "Photo" output then places the page on a
desk with perspective, shadow and lighting.

All randomness comes from a seed, so the same input gives the same pages.
"""
from __future__ import annotations

import io
import math
import random
import zipfile
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import fonts as fontreg
from . import images as editor_images
from . import mathtex
from .richtext import Block, Style, parse, parse_color

try:
    import pyphen
except ImportError:  # hyphenation simply turns off
    pyphen = None

PAGE_SIZES_MM = {"a4": (210.0, 297.0), "a5": (148.0, 210.0), "letter": (215.9, 279.4), "legal": (215.9, 355.6)}

PAPERS = {
    "blank": {"name": "Blank", "color": (252, 250, 244)},
    "lined": {"name": "Ruled + margin", "color": (252, 250, 244), "rules": (150, 182, 222), "margin": 1},
    "lined-plain": {"name": "Ruled", "color": (252, 250, 244), "rules": (150, 182, 222)},
    "legal": {"name": "Legal pad", "color": (252, 243, 176), "rules": (128, 165, 212), "margin": 2,
              "margin_color": (214, 92, 98)},
    "grid": {"name": "Squared", "color": (252, 252, 250), "grid": (186, 202, 224)},
    "dots": {"name": "Dot grid", "color": (252, 252, 250), "dots": (170, 170, 182)},
    "vintage": {"name": "Vintage", "color": (238, 226, 198), "rules": (168, 158, 186), "margin": 1,
                "margin_color": (196, 128, 118), "texture": 1.6},
    "kraft": {"name": "Kraft", "color": (212, 186, 146), "rules": (150, 124, 92), "texture": 2.2},
}

# Amounts are 0..1 and are scaled to real distances inside _render_page.
PRESETS = {
    "off": dict(glyph_variation=0.0, word_placement=0.0, line_starts=0.0, line_wobble=0.0, ink_variation=0.0),
    "subtle": dict(glyph_variation=0.2, word_placement=0.15, line_starts=0.15, line_wobble=0.15, ink_variation=0.15),
    "natural": dict(glyph_variation=0.4, word_placement=0.4, line_starts=0.3, line_wobble=0.3, ink_variation=0.35),
    "realistic": dict(glyph_variation=0.55, word_placement=0.55, line_starts=0.4, line_wobble=0.4, ink_variation=0.55),
    "messy": dict(glyph_variation=0.9, word_placement=0.85, line_starts=0.7, line_wobble=0.7, ink_variation=0.75),
}

SHAPES = ("circle", "box", "underline", "arrow", "check", "cross", "star", "scribble", "highlight")
HIGHLIGHT = (255, 226, 77)
HEADING_SCALE = {"h1": 1.6, "h2": 1.35, "h3": 1.15}
MATH_SPACES = {" ": 0.3, "\u2009": 0.17, "\u2002": 0.5, "\u2005": 0.25, "\u2003": 1.0}  # width as a fraction of font size
LIST_INDENT_MM = 7.0
CELL_PAD_MM = 1.6
BASE_PX_PER_MM = 4.0   # font sizes and spacing in settings are pixels at this resolution
MAX_PAGES = 30
MAX_SHAPES_PER_PAGE = 100


def _num(d: dict, key: str, default: float, lo: float, hi: float) -> float:
    try:
        v = float(d.get(key, default))
    except (TypeError, ValueError):
        return default
    if not math.isfinite(v):
        return default
    return min(max(v, lo), hi)


@dataclass
class Settings:
    font: str = "caveat"
    font_size: float = 26.0          # px at 4 px/mm
    line_height: float = 1.4         # multiple of font size; also the ruled-line gap
    letter_spacing: float = 0.0      # px at 4 px/mm, added after each letter
    word_spacing: float = 0.0        # px at 4 px/mm, added to each space
    paragraph_spacing: float = 0.0   # px at 4 px/mm after each paragraph (whole lines on ruled paper)
    hyphenation: bool = False
    ink_color: tuple = (31, 58, 138)
    paper_size: str = "a4"
    orientation: str = "portrait"
    paper_style: str = "lined"
    mirror_even: bool = False
    paper_texture: bool = True
    shading: bool = True
    output: str = "print"            # print | photo
    margin_top: float = 22.0         # mm
    margin_bottom: float = 15.0
    margin_left: float = 25.0
    margin_right: float = 12.0
    preset: str = "natural"
    glyph_variation: float = 0.4
    word_placement: float = 0.4
    line_starts: float = 0.3
    line_wobble: float = 0.3
    ink_variation: float = 0.35
    slant: float = 0.0               # degrees, positive leans right
    blur: float = 0.15               # 0..1
    seed: int = 1

    @classmethod
    def from_dict(cls, d: dict | None) -> "Settings":
        d = d or {}
        s = cls()
        s.font = (fontreg.get_font(d.get("font")) or fontreg.default_font()).id
        s.font_size = _num(d, "font_size", s.font_size, 10, 90)
        s.line_height = _num(d, "line_height", s.line_height, 1.0, 3.0)
        s.letter_spacing = _num(d, "letter_spacing", s.letter_spacing, 0, 20)
        s.word_spacing = _num(d, "word_spacing", s.word_spacing, 0, 60)
        s.paragraph_spacing = _num(d, "paragraph_spacing", s.paragraph_spacing, 0, 200)
        s.hyphenation = bool(d.get("hyphenation", s.hyphenation))
        s.ink_color = parse_color(str(d.get("ink_color") or "")) or s.ink_color
        s.paper_size = d.get("paper_size") if d.get("paper_size") in PAGE_SIZES_MM else s.paper_size
        s.orientation = "landscape" if d.get("orientation") == "landscape" else "portrait"
        s.paper_style = d.get("paper_style") if d.get("paper_style") in PAPERS else s.paper_style
        s.mirror_even = bool(d.get("mirror_even", s.mirror_even))
        s.paper_texture = bool(d.get("paper_texture", s.paper_texture))
        s.shading = bool(d.get("shading", s.shading))
        s.output = "photo" if d.get("output") == "photo" else "print"
        for side, default in (("top", 22), ("bottom", 15), ("left", 25), ("right", 12)):
            setattr(s, f"margin_{side}", _num(d, f"margin_{side}", default, 0, 80))
        preset = str(d.get("preset", s.preset))
        if preset in PRESETS:
            s.preset = preset
            for k, v in PRESETS[preset].items():
                setattr(s, k, v)
        else:
            s.preset = "custom"
            for k in PRESETS["off"]:
                setattr(s, k, _num(d, k, getattr(s, k), 0, 1))
        s.slant = _num(d, "slant", s.slant, -20, 20)
        s.blur = _num(d, "blur", s.blur, 0, 1)
        s.seed = int(_num(d, "seed", s.seed, 0, 2**31 - 1))
        return s

    def page_mm(self) -> tuple[float, float]:
        w, h = PAGE_SIZES_MM[self.paper_size]
        return (h, w) if self.orientation == "landscape" else (w, h)

    def ruled(self) -> bool:
        """Paper with printed lines/grid: vertical spacing snaps to whole lines."""
        return self.paper_style != "blank"


def parse_shapes(raw) -> dict[int, list[dict]]:
    """Validate shapes sent by the browser: {page: [{type, x1, y1, x2, y2, color}]}, coords 0..1."""
    out: dict[int, list[dict]] = {}
    if not isinstance(raw, dict):
        return out
    for key, items in list(raw.items())[:MAX_PAGES]:
        try:
            page = int(key)
        except (TypeError, ValueError):
            continue
        if not 0 <= page < MAX_PAGES or not isinstance(items, list):
            continue
        clean = []
        for it in items[:MAX_SHAPES_PER_PAGE]:
            if not isinstance(it, dict) or it.get("type") not in SHAPES:
                continue
            c = {"type": it["type"], "color": parse_color(str(it.get("color") or ""))}
            for k in ("x1", "y1", "x2", "y2"):
                c[k] = _num(it, k, 0.5, -0.1, 1.1)
            clean.append(c)
        if clean:
            out[page] = clean
    return out


# ---------------------------------------------------------------- glyphs

@lru_cache(maxsize=128)
def _load_font(path: str, px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, px)


@lru_cache(maxsize=16384)
def _advance(path: str, px: int, ch: str) -> float:
    return _load_font(path, px).getlength(ch)


@lru_cache(maxsize=8192)
def _glyph_tile(path: str, px: int, ch: str, bold: bool) -> tuple[Image.Image, int, int]:
    """Character drawn as an 8-bit mask, plus where its baseline origin sits."""
    font = _load_font(path, px)
    left, top, right, bottom = font.getbbox(ch, anchor="ls")
    pad = px // 2 + 2  # room for rotation/slant without clipping
    w, h = int(right - left) + 2 * pad, int(bottom - top) + 2 * pad
    ox, oy = pad - int(left), pad - int(top)
    tile = Image.new("L", (max(w, 1), max(h, 1)), 0)
    ImageDraw.Draw(tile).text((ox, oy), ch, font=font, fill=255, anchor="ls")
    if bold:
        # Thicken the stroke by spreading it a pixel or two; blend so it stays pen-like.
        r = max(1, round(px * 0.02))
        tile = Image.blend(tile, tile.filter(ImageFilter.MaxFilter(2 * r + 1)), 0.6)
    return tile, ox, oy


def _transform_tile(tile: Image.Image, ox: int, oy: int, rot_deg: float, scale: float, slant_deg: float) -> Image.Image:
    """Rotate, scale and slant a glyph tile around its baseline origin."""
    if abs(rot_deg) < 0.05 and abs(scale - 1) < 0.005 and abs(slant_deg) < 0.05:
        return tile
    t = math.radians(rot_deg)
    k = math.tan(math.radians(slant_deg))
    rot = np.array([[math.cos(t), -math.sin(t)], [math.sin(t), math.cos(t)]])
    shear = np.array([[1.0, -k], [0.0, 1.0]])
    inv = np.linalg.inv(rot @ shear @ (np.eye(2) * scale))  # Pillow wants output->input
    a, b, d, e = inv[0, 0], inv[0, 1], inv[1, 0], inv[1, 1]
    c = ox - a * ox - b * oy
    f = oy - d * ox - e * oy
    return tile.transform(tile.size, Image.AFFINE, (a, b, c, d, e, f), resample=Image.BICUBIC)


# ---------------------------------------------------------------- layout

@dataclass
class Glyph:
    ch: str
    style: Style
    path: str
    px: int
    adv: float


@dataclass
class Box:
    """A maths formula: glyphs placed relative to the box origin (dy: + is down) plus bars."""
    adv: float
    style: Style
    glyphs: list[tuple[Glyph, float, float]] = field(default_factory=list)
    bars: list[tuple[float, float, float]] = field(default_factory=list)
    tall: bool = False   # has a stacked fraction: its line takes two ruled lines


@dataclass
class TableRow:
    col_x: list[float]               # left edge of each column, relative to the text left
    widths: list[float]
    cells: list["Line | None"]
    top: bool                        # first visual line of this table row
    bottom: bool                     # last visual line of this table row


@dataclass
class Line:
    kind: str = "text"               # text | table | image | spacer
    slots: float = 1.0               # how many ruled lines it takes
    words: list[list] = field(default_factory=list)   # each word: list of Glyph | Box
    spaces: list[Style | None] = field(default_factory=list)  # between words; None = forced break
    block: Block | None = None
    indent: float = 0.0
    prefix: str | None = None
    last_in_block: bool = True
    space_px: float = 0.0
    base_px: float = 0.0
    table: TableRow | None = None
    image: Image.Image | None = None
    image_dx: float = 0.0


@lru_cache(maxsize=1)
def _hyphenator():
    return pyphen.Pyphen(lang="en_US") if pyphen else None


class _Layout:
    def __init__(self, s: Settings, ppm: float) -> None:
        self.s, self.ppm = s, ppm
        self.k = ppm / BASE_PX_PER_MM
        self.primary = fontreg.get_font(s.font) or fontreg.default_font()
        self.cps = fontreg.codepoints(self.primary.path)
        self.letter_px = s.letter_spacing * self.k
        self.hyph = _hyphenator() if s.hyphenation else None
        self.missing: set[str] = set()
        self.line_h = s.font_size * s.line_height * self.k
        pw_mm, ph_mm = s.page_mm()
        self.usable_h = (ph_mm - s.margin_top - s.margin_bottom) * ppm

    # -- items --
    def glyph(self, ch: str, st: Style, base_px: float, track: bool = True, spacing: bool = True) -> Glyph:
        path = self.primary.path
        if ord(ch) not in self.cps:
            if track:
                self.missing.add(ch)
            fb = fontreg.fallback_for(ord(ch))
            if fb:
                path = fb.path
            else:
                ch = " "  # no font has it: leave a gap instead of drawing a box
        px = max(6, round(base_px * fontreg.size_factor(path)))
        return Glyph(ch, st, path, px, _advance(path, px, ch) + (self.letter_px if spacing else 0))

    def math_box(self, tex: str, st: Style, base_px: float) -> Box:
        plain_style = Style(st.bold, False, False, st.color)
        box = Box(0.0, st)

        def lay(nodes, scale: float, dy: float, x: float, glyphs: list, bars: list, depth: int = 0) -> float:
            size = base_px * scale
            for node in nodes:
                kind = node[0]
                if kind == "text":
                    for ch in node[1]:
                        if ch in MATH_SPACES:
                            x += size * MATH_SPACES[ch]
                            continue
                        op = ch in mathtex.OPERATORS
                        if op:
                            x += size * 0.16
                        g = self.glyph(ch, plain_style, size, track=False, spacing=False)
                        glyphs.append((g, x, dy))
                        x += g.adv + (size * 0.16 if op else 0)
                elif kind == "big":
                    # \left( … \right): a taller bracket, dropped a little to centre on the formula
                    g = self.glyph(node[1], plain_style, size * 1.5, track=False, spacing=False)
                    glyphs.append((g, x, dy + size * 0.16))
                    x += g.adv
                elif kind in ("sup", "sub") and depth < 6:
                    off = -size * 0.42 if kind == "sup" else size * 0.2
                    x = lay(node[1], scale * 0.65, dy + off, x, glyphs, bars, depth + 1)
                elif kind == "frac" and depth < 6:
                    box.tall = True
                    parts = []
                    for sub_nodes in (node[1], node[2]):
                        g2, b2 = [], []
                        w = lay(sub_nodes, scale * 0.7, 0.0, 0.0, g2, b2, depth + 1)
                        parts.append((w, g2, b2))
                    width = max(parts[0][0], parts[1][0]) + size * 0.2
                    for (w, g2, b2), off in zip(parts, (-size * 0.48, size * 0.3)):
                        dx = x + (width - w) / 2
                        glyphs.extend((g, dx + gx, dy + off + gy) for g, gx, gy in g2)
                        bars.extend((dx + a, dx + b, dy + off + by) for a, b, by in b2)
                    bars.append((x, x + width, dy - size * 0.33))
                    x += width + size * 0.08
                elif kind in ("sqrt", "over") and depth < 6:
                    if kind == "sqrt":
                        g = self.glyph("√", plain_style, size, track=False, spacing=False)
                        glyphs.append((g, x, dy))
                        x += g.adv * 0.92
                    start = x
                    x = lay(node[1], scale, dy, x, glyphs, bars, depth + 1)
                    bars.append((start, x, dy - size * 0.82))
            return x

        box.adv = lay(mathtex.parse(tex), 1.0, 0.0, 0.0, box.glyphs, box.bars) + base_px * 0.05
        return box

    def words(self, block: Block, base_px: float) -> tuple[list[list], list[Style | None]]:
        words: list[list] = []
        spaces: list[Style | None] = []
        cur: list = []
        gap: Style | None = None
        for text, st in block.runs:
            if st.math:
                if not cur and words:
                    spaces.append(gap)
                cur.append(self.math_box(st.math, st, base_px))
                continue
            for ch in text:
                if ch == " ":
                    if cur:
                        words.append(cur)
                        cur = []
                        gap = st
                    continue
                if not cur and words:
                    spaces.append(gap)
                cur.append(self.glyph(ch, st, base_px))
        if cur:
            words.append(cur)
        return words, spaces

    def space_px(self, base_px: float) -> float:
        px = max(6, round(base_px * fontreg.size_factor(self.primary.path)))
        return max(_advance(self.primary.path, px, " "), px * 0.3) + self.s.word_spacing * self.k

    # -- wrapping --
    def wrap(self, block: Block, avail: float, indent: float = 0.0, prefix: str | None = None) -> list[Line]:
        base_px = self.s.font_size * self.k * HEADING_SCALE.get(block.kind, 1.0) * block.scale
        words, spaces = self.words(block, base_px)
        space_px = self.space_px(base_px)
        lines: list[Line] = []

        def new_line() -> Line:
            return Line(block=block, indent=indent, space_px=space_px, base_px=base_px,
                        prefix=prefix if not lines else None)

        line, width, i = new_line(), 0.0, 0
        while i < len(words):
            w = words[i]
            ww = sum(it.adv for it in w)
            sp = space_px if line.words else 0.0
            if width + sp + ww <= avail:
                if line.words:
                    line.spaces.append(spaces[i - 1])
                line.words.append(w)
                width += sp + ww
                i += 1
                continue
            cut = None
            if not line.words and ww > avail:
                # Word longer than a whole line: break it wherever it overflows.
                n, acc = 0, 0.0
                while n < len(w) - 1 and acc + w[n].adv <= avail:
                    acc += w[n].adv
                    n += 1
                cut = (w[:max(1, n)], w[max(1, n):])
            elif self.hyph and len(w) >= 5 and all(isinstance(it, Glyph) for it in w):
                room = avail - width - sp
                for pos in reversed(self.hyph.positions("".join(g.ch for g in w))):
                    if pos < 2 or len(w) - pos < 2:
                        continue
                    head = w[:pos] + [self.glyph("-", w[pos - 1].style, base_px)]
                    if sum(g.adv for g in head) <= room:
                        cut = (head, w[pos:])
                        break
            if cut:
                words[i:i + 1] = [cut[0], cut[1]]
                spaces.insert(i, None)
                continue
            line.last_in_block = False
            lines.append(line)
            line, width = new_line(), 0.0
        lines.append(line)
        for ln in lines:
            if any(isinstance(it, Box) and it.tall for w in ln.words for it in w):
                ln.slots = 2.0  # fraction: numerator on one ruled line, denominator on the next
        return lines

    # -- blocks --
    def table(self, block: Block, avail: float) -> list[Line]:
        rows = [r for r in (block.rows or []) if r] or [[[]]]
        ncols = max(len(r) for r in rows)
        pad = CELL_PAD_MM * self.ppm

        def natural(cell: list[Block]) -> float:
            best = 0.0
            for b in cell:
                base_px = self.s.font_size * self.k * b.scale
                words, _ = self.words(b, base_px)
                best = max(best, sum(it.adv for w in words for it in w) + self.space_px(base_px) * max(0, len(words) - 1))
            return best

        nat = [3 * pad] * ncols
        for row in rows:
            for c, cell in enumerate(row):
                nat[c] = max(nat[c], min(natural(cell), avail) + 2 * pad)
        total = sum(nat)
        if total <= avail:
            widths = [n + (avail - total) / ncols for n in nat]  # share spare width evenly, like the editor
        else:
            floor = avail / ncols * 0.5
            raw = [max(floor, n * avail / total) for n in nat]
            widths = [r * avail / sum(raw) for r in raw]
        col_x = [sum(widths[:c]) for c in range(ncols)]

        lines: list[Line] = []
        for row in rows:
            cell_lines: list[list[Line]] = []
            for c in range(ncols):
                cl: list[Line] = []
                for b in (row[c] if c < len(row) else []):
                    cl.extend(self.wrap(b, widths[c] - 2 * pad))
                cell_lines.append(cl)
            height = max(1, max(len(cl) for cl in cell_lines))
            for j in range(height):
                seg = TableRow(col_x, widths, [cl[j] if j < len(cl) else None for cl in cell_lines],
                               top=j == 0, bottom=j == height - 1)
                lines.append(Line(kind="table", block=block, table=seg))
        return lines

    def image(self, block: Block, avail: float) -> list[Line]:
        img = editor_images.load_rgb_on_white(block.image_id or "")
        if img is None:
            return []
        w = avail * block.image_width
        h = w * img.height / img.width
        max_h = self.usable_h - self.line_h * 1.4
        if h > max_h:
            w, h = w * max_h / h, max_h
        slots = (h + self.line_h * 0.4) / self.line_h
        if self.s.ruled():
            slots = math.ceil(slots)
        dx = {"center": (avail - w) / 2, "right": avail - w}.get(block.align, 0.0)
        resized = img.resize((max(1, round(w)), max(1, round(h))), Image.LANCZOS)
        return [Line(kind="image", block=block, slots=slots, image=resized, image_dx=dx)]

    def spacer(self) -> Line | None:
        extra = self.s.paragraph_spacing * self.k / self.line_h
        if self.s.ruled():
            extra = round(extra)
        return Line(kind="spacer", slots=extra) if extra > 0 else None

    def layout(self, blocks: list[Block], avail_w: float) -> list[Line]:
        lines: list[Line] = []
        for block in blocks:
            if block.kind == "table":
                lines.extend(self.table(block, avail_w))
            elif block.kind == "image":
                lines.extend(self.image(block, avail_w))
            else:
                indent = (block.depth + (1 if block.kind == "li" else 0)) * LIST_INDENT_MM * self.ppm
                prefix = None
                if block.kind == "li" and block.first:
                    prefix = f"{block.list_index}." if block.list_type == "ol" else "•"
                lines.extend(self.wrap(block, avail_w - indent, indent, prefix))
            if block.para_end and block.kind != "li":
                sp = self.spacer()
                if sp:
                    lines.append(sp)
        return lines


# ---------------------------------------------------------------- paper & photo

def _upsampled_noise(rng: np.random.Generator, w: int, h: int, cell_w: int, cell_h: int | None = None) -> np.ndarray:
    """Smooth 0..1 noise: a coarse random grid resized up with bicubic filtering."""
    cell_h = cell_h or cell_w
    small = (rng.random((h // cell_h + 2, w // cell_w + 2)) * 255).astype(np.uint8)
    img = Image.fromarray(small, "L").resize((w, h), Image.BICUBIC)
    return np.asarray(img, dtype=np.float32) / 255.0


def _paper(s: Settings, w: int, h: int, ppm: float, line_h: float, top_px: float, text_left_px: float,
           mirrored: bool, rng: np.random.Generator) -> np.ndarray:
    spec = PAPERS[s.paper_style]
    img = Image.new("RGB", (w, h), spec["color"])
    draw = ImageDraw.Draw(img)
    thin = max(1, round(ppm * 0.2))
    if "rules" in spec:
        y = top_px + line_h
        while y < h - ppm * 5:
            draw.line([(0, y), (w, y)], fill=spec["rules"], width=thin)
            y += line_h
        if spec.get("margin"):
            x = s.margin_left * ppm - 4 * ppm  # mirrored pages flip it to the other side
            if x > 4 * ppm:
                for mx in [x, x - 1.3 * ppm][: spec["margin"]]:
                    mx = w - mx if mirrored else mx
                    draw.line([(mx, 0), (mx, h)], fill=spec.get("margin_color", (225, 120, 125)), width=thin)
    elif "grid" in spec or "dots" in spec:
        # Half the writing-line gap, so every second row is a writing line.
        step = line_h / 2 if 3.5 * ppm <= line_h / 2 <= 7 * ppm else 5 * ppm
        y0 = (top_px + line_h) % step
        x0 = text_left_px % step
        if "grid" in spec:
            for x in np.arange(x0, w, step):
                draw.line([(x, 0), (x, h)], fill=spec["grid"], width=thin)
            for y in np.arange(y0, h, step):
                draw.line([(0, y), (w, y)], fill=spec["grid"], width=thin)
        else:
            r = max(1.0, ppm * 0.3)
            for x in np.arange(x0 or step, w, step):
                for y in np.arange(y0 or step, h, step):
                    draw.ellipse([x - r, y - r, x + r, y + r], fill=spec["dots"])

    arr = np.asarray(img, dtype=np.float32)
    if s.paper_texture:
        amt = spec.get("texture", 1.0)
        grain = rng.normal(0, 3.5 * amt, (h, w)).astype(np.float32)
        blotch = (_upsampled_noise(rng, w, h, max(8, int(ppm * 12))) - 0.5) * 10 * amt
        if amt > 2:  # visible fibres on kraft paper
            blotch += (_upsampled_noise(rng, w, h, max(4, int(ppm * 8)), max(2, int(ppm * 0.6))) - 0.5) * 14
        arr += (grain + blotch)[..., None]
    if s.shading and s.output == "print":
        arr *= _lighting(rng, w, h, 0.04, 0.09, 0.18)[..., None]
    return np.clip(arr, 0, 255)


def _lighting(rng: np.random.Generator, w: int, h: int, lo: float, hi: float, vignette: float) -> np.ndarray:
    """Uneven light from one side plus a soft vignette, like a phone photo."""
    ang = rng.uniform(0, 2 * math.pi)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx, ny = xx / w - 0.5, yy / h - 0.5
    directional = (nx * math.cos(ang) + ny * math.sin(ang)) * rng.uniform(lo, hi)
    return 1 - directional - (nx ** 2 + ny ** 2) * vignette


def _perspective_coeffs(dst: list[tuple[float, float]], src: list[tuple[float, float]]) -> list[float]:
    """Coefficients mapping output (dst) points back to input (src) points."""
    rows = []
    for (x, y), (u, v) in zip(dst, src):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    a = np.array(rows, dtype=np.float64)
    b = np.array([c for pt in src for c in pt], dtype=np.float64)
    return np.linalg.solve(a, b).tolist()


DESKS = [(118, 84, 58), (92, 68, 50), (150, 118, 86), (66, 68, 74), (178, 160, 136)]


def _photo(page: Image.Image, seed: int) -> Image.Image:
    """Place the page on a desk with a slight angle, perspective, shadow and lighting."""
    rng = np.random.default_rng(seed)
    pr = random.Random(seed)
    w, h = page.size
    W, H = int(w * 1.14), int(h * 1.10)

    base = np.array(DESKS[pr.randrange(len(DESKS))], dtype=np.float32)
    grain = _upsampled_noise(rng, W, H, max(4, W // 6), max(2, H // 300))  # long wood-grain streaks
    fine = rng.normal(0, 5, (H, W)).astype(np.float32)
    desk = base[None, None, :] * (0.82 + 0.3 * grain)[..., None] + fine[..., None]

    # Page corners: centred, nudged randomly for a hand-held camera look.
    cx, cy = (W - w) / 2, (H - h) / 2
    j = w * 0.025

    def nudge() -> float:
        return pr.uniform(-j, j)

    dst = [(cx + nudge(), cy + nudge()), (cx + w + nudge(), cy + nudge()),
           (cx + w + nudge(), cy + h + nudge()), (cx + nudge(), cy + h + nudge())]
    coeffs = _perspective_coeffs(dst, [(0, 0), (w, 0), (w, h), (0, h)])
    warped = page.convert("RGBA").transform((W, H), Image.PERSPECTIVE, coeffs, resample=Image.BICUBIC)
    alpha = np.asarray(warped.getchannel("A"), dtype=np.float32) / 255.0

    shadow_img = warped.getchannel("A").filter(ImageFilter.GaussianBlur(w * 0.012))
    sx, sy = int(w * 0.008), int(w * 0.014)
    shadow = np.zeros((H, W), dtype=np.float32)
    s_arr = np.asarray(shadow_img, dtype=np.float32) / 255.0
    shadow[sy:, sx:] = s_arr[: H - sy, : W - sx]
    desk *= (1 - 0.55 * shadow)[..., None]

    paper = np.asarray(warped.convert("RGB"), dtype=np.float32)
    out = desk * (1 - alpha[..., None]) + paper * alpha[..., None]
    out *= _lighting(rng, W, H, 0.08, 0.16, 0.35)[..., None]
    warm = np.array([1.02, 1.0, 0.95] if pr.random() < 0.6 else [0.97, 1.0, 1.03], dtype=np.float32)
    out = out * warm + rng.normal(0, 2.5, (H, W, 1)).astype(np.float32)
    img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")
    return img.filter(ImageFilter.GaussianBlur(0.35))


# ---------------------------------------------------------------- strokes

def _stroke(draw: ImageDraw.ImageDraw, pts: list[tuple[float, float]], width: float, rng: random.Random,
            wobble: float, fill: int = 235) -> None:
    """A pen stroke through the given points with a smooth, slowly drifting hand tremor."""
    out: list[tuple[float, float]] = []
    # Two slow waves with random phase: smooth like a real hand, never spiky.
    p1, p2 = rng.uniform(0, 6.3), rng.uniform(0, 6.3)
    amp = width * 0.35 * wobble
    travelled = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        dist = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(dist / max(width * 4, 1)))
        nx, ny = (-(y1 - y0) / dist, (x1 - x0) / dist) if dist else (0, 0)
        for t in range(n):
            f = t / n
            d = travelled + dist * f
            j = amp * (math.sin(d / (width * 30) + p1) + 0.4 * math.sin(d / (width * 11) + p2))
            out.append((x0 + (x1 - x0) * f + nx * j, y0 + (y1 - y0) * f + ny * j))
        travelled += dist
    out.append(pts[-1])
    draw.line(out, fill=fill, width=max(1, round(width)), joint="curve")


def _hand_line(draw: ImageDraw.ImageDraw, x0: float, x1: float, y: float, width: float, rng: random.Random, wobble: float) -> None:
    drift = rng.gauss(0, 1) * width * 0.8 * wobble
    _stroke(draw, [(x0, y), (x1, y + drift)], width, rng, wobble)


def _draw_shape(draw: ImageDraw.ImageDraw, shape: dict, w: int, h: int, width: float, rng: random.Random) -> None:
    x1, y1, x2, y2 = shape["x1"] * w, shape["y1"] * h, shape["x2"] * w, shape["y2"] * h
    lx, rx, ty, by = min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)
    bw, bh = max(rx - lx, width * 4), max(by - ty, width * 4)
    t = shape["type"]
    jit = lambda s=1.0: rng.gauss(0, 1) * width * s  # noqa: E731
    if t == "circle":
        cx, cy, rx_, ry_ = lx + bw / 2, ty + bh / 2, bw / 2, bh / 2
        a0 = rng.uniform(0, 2 * math.pi)
        turns = 1.08 + rng.uniform(0, 0.08)  # overshoot like a real pen loop
        n = 48
        wob = rng.uniform(0, 2 * math.pi)
        pts = []
        for i in range(n + 1):
            a = a0 + 2 * math.pi * turns * i / n
            grow = 1 + 0.04 * i / n + 0.02 * math.sin(3 * a + wob)
            pts.append((cx + rx_ * grow * math.cos(a), cy + ry_ * grow * math.sin(a)))
        draw.line(pts, fill=235, width=max(1, round(width)), joint="curve")
    elif t == "box":
        corners = [(lx, ty), (lx + bw, ty), (lx + bw, ty + bh), (lx, ty + bh)]
        for i in range(4):
            (ax, ay), (bx, by_) = corners[i], corners[(i + 1) % 4]
            ox, oy = (bx - ax) * 0.04, (by_ - ay) * 0.04  # corners cross slightly
            _stroke(draw, [(ax - ox + jit(), ay - oy + jit()), (bx + ox + jit(), by_ + oy + jit())], width, rng, 1)
    elif t == "underline":
        _hand_line(draw, lx, lx + bw, ty + bh, width, rng, 1)
    elif t == "arrow":
        _stroke(draw, [(x1, y1), (x2 + jit(), y2 + jit())], width, rng, 1)
        ang = math.atan2(y2 - y1, x2 - x1)
        head = max(width * 6, math.hypot(x2 - x1, y2 - y1) * 0.18)
        for side in (-1, 1):
            a = ang + math.pi - side * 0.45
            _stroke(draw, [(x2, y2), (x2 + head * math.cos(a) + jit(), y2 + head * math.sin(a) + jit())], width, rng, 1)
    elif t == "check":
        _stroke(draw, [(lx, ty + bh * 0.55), (lx + bw * 0.35, ty + bh), (lx + bw, ty)], width * 1.1, rng, 1)
    elif t == "cross":
        _stroke(draw, [(lx, ty), (lx + bw, ty + bh)], width, rng, 1)
        _stroke(draw, [(lx + bw, ty), (lx, ty + bh)], width, rng, 1)
    elif t == "star":
        cx, cy, r = lx + bw / 2, ty + bh / 2, min(bw, bh) / 2
        pts = [(cx + r * math.cos(-math.pi / 2 + i * 4 * math.pi / 5) + jit(0.5),
                cy + r * math.sin(-math.pi / 2 + i * 4 * math.pi / 5) + jit(0.5)) for i in range(6)]
        _stroke(draw, pts, width, rng, 1)
    elif t == "scribble":
        n = max(3, int(bw / max(width * 3, 1)))
        pts = [(lx + bw * i / n + jit(), ty + (bh if i % 2 else 0) + jit()) for i in range(n + 1)]
        _stroke(draw, pts, width, rng, 0.6)


# ---------------------------------------------------------------- page rendering

def _render_page(lines: list[Line], first_line: int, s: Settings, ppm: float, page_index: int,
                 shapes: list[dict] | None = None) -> Image.Image:
    k = ppm / BASE_PX_PER_MM
    pw_mm, ph_mm = s.page_mm()
    w, h = round(pw_mm * ppm), round(ph_mm * ppm)
    mirrored = s.mirror_even and page_index % 2 == 1
    ml, mr = (s.margin_right, s.margin_left) if mirrored else (s.margin_left, s.margin_right)
    left_px, top_px = ml * ppm, s.margin_top * ppm
    line_h = s.font_size * s.line_height * k
    avail = (pw_mm - ml - mr) * ppm - s.font_size * k * 0.6
    primary = fontreg.get_font(s.font) or fontreg.default_font()
    cursive = primary.cursive
    pen_w = max(1.0, s.font_size * k * 0.07)

    rng = random.Random(s.seed * 1009 + page_index)
    nrng = np.random.default_rng(s.seed * 7919 + page_index)
    layers: dict[tuple, np.ndarray] = {}
    strokes: dict[tuple, Image.Image] = {}
    pasted: list[tuple[Image.Image, int, int]] = []

    def layer(color: tuple) -> np.ndarray:
        if color not in layers:
            layers[color] = np.zeros((h, w), dtype=np.float32)
        return layers[color]

    def pen(color: tuple) -> ImageDraw.ImageDraw:
        if color not in strokes:
            strokes[color] = Image.new("L", (w, h), 0)
        return ImageDraw.Draw(strokes[color])

    gv, wp, lsv, lw, iv = s.glyph_variation, s.word_placement, s.line_starts, s.line_wobble, s.ink_variation

    def draw_glyph(g: Glyph, x: float, y: float, rot: float, sc: float, sl: float, pressure: float) -> None:
        tile, ox, oy = _glyph_tile(g.path, g.px, g.ch, g.style.bold)
        arr = np.asarray(_transform_tile(tile, ox, oy, rot, sc, sl), dtype=np.float32) / 255.0
        x0, y0 = round(x) - ox, round(y) - oy
        gh, gw = arr.shape
        cx0, cy0 = max(0, -x0), max(0, -y0)
        cx1, cy1 = min(gw, w - x0), min(gh, h - y0)
        if cx1 > cx0 and cy1 > cy0:
            target = layer(g.style.color or s.ink_color)
            region = target[y0 + cy0:y0 + cy1, x0 + cx0:x0 + cx1]
            np.maximum(region, arr[cy0:cy1, cx0:cx1] * pressure, out=region)

    def draw_text_line(line: Line, origin_x: float, width: float, baseline: float, line_rng: random.Random) -> None:
        px = line.base_px
        drift = line_rng.gauss(0, 1) * lw * 0.012  # slope: lines that rise or sink
        natural = sum(it.adv for wd in line.words for it in wd) + line.space_px * max(0, len(line.words) - 1)
        extra = max(0.0, width - line.indent - natural)
        x = origin_x + line.indent
        gap_extra = 0.0
        align = line.block.align if line.block else "left"
        if align == "center":
            x += extra / 2
        elif align == "right":
            x += extra
        else:
            x += line_rng.random() * lsv * px * 0.8
            if align == "justify" and not line.last_in_block and len(line.words) > 1:
                gap_extra = extra / (len(line.words) - 1)
        x_start = x

        if line.prefix:
            mpx = max(6, round(px * fontreg.size_factor(primary.path)))
            mx = origin_x + line.indent - 2 * ppm - sum(_advance(primary.path, mpx, c) for c in line.prefix)
            for c in line.prefix:
                draw_glyph(Glyph(c, Style(), primary.path, mpx, 0), mx, baseline, rng.gauss(0, 1) * gv * 3, 1, s.slant, 1)
                mx += _advance(primary.path, mpx, c)

        spans: list[tuple[float, float, Style]] = []  # for underline/strikethrough
        for wi, word in enumerate(line.words):
            w_dy = rng.gauss(0, 1) * wp * px * 0.05
            w_rot = rng.gauss(0, 1) * wp * 1.2
            w_scale = 1 + rng.gauss(0, 1) * wp * 0.03
            for it in word:
                y_here = baseline + w_dy + drift * (x - x_start)
                if isinstance(it, Box):
                    for g, gx, gy in it.glyphs:
                        draw_glyph(g, x + gx + rng.gauss(0, 1) * gv * px * 0.01, y_here + gy + rng.gauss(0, 1) * gv * px * 0.015,
                                   w_rot + rng.gauss(0, 1) * gv * 2, 1 + rng.gauss(0, 1) * gv * 0.03,
                                   s.slant + rng.gauss(0, 1) * gv * 2, 1 - min(0.5, abs(rng.gauss(0, 1)) * iv * 0.2))
                    color = it.style.color or s.ink_color
                    for a, b, by in it.bars:
                        _hand_line(pen(color), x + a, x + b, y_here + by, pen_w * 0.8, rng, 0.3 + gv)
                    spans.append((x, x + it.adv, it.style))
                    x += it.adv
                    continue
                rot = w_rot + rng.gauss(0, 1) * gv * 3.0
                sc = w_scale * (1 + rng.gauss(0, 1) * gv * 0.05)
                sl = s.slant + rng.gauss(0, 1) * gv * 3.0
                pressure = 1 - min(0.6, abs(rng.gauss(0, 1)) * iv * 0.25)
                gx = x + rng.gauss(0, 1) * gv * px * (0.008 if cursive else 0.02)
                gy = y_here + rng.gauss(0, 1) * gv * px * 0.025
                draw_glyph(it, gx, gy, rot, sc, sl, pressure)
                adv = it.adv * sc
                spans.append((x, x + adv, it.style))
                x += adv
            if wi < len(line.words) - 1:
                gap = line.space_px * (1 + rng.uniform(-0.1, 0.4) * wp) + gap_extra
                gap_style = line.spaces[wi]
                if gap_style is not None:
                    spans.append((x, x + gap, gap_style))
                x += gap

        # Underline / strikethrough as hand-drawn strokes over contiguous spans.
        for attr, dy in (("underline", px * 0.14), ("strike", -px * 0.22)):
            seg = None
            for x0, x1, st in spans + [(0, 0, Style())]:
                if getattr(st, attr):
                    color = st.color or s.ink_color
                    if seg and seg[2] == color and x0 - seg[1] < px * 0.5:
                        seg[1] = x1
                        continue
                    if seg:
                        _hand_line(pen(seg[2]), seg[0], seg[1], seg[3], px * 0.06, rng, 0.4 + gv)
                    seg = [x0, x1, color, baseline + dy + drift * (x0 - x_start)]
                elif seg:
                    _hand_line(pen(seg[2]), seg[0], seg[1], seg[3], px * 0.06, rng, 0.4 + gv)
                    seg = None

    cum = 0.0
    for i, line in enumerate(lines):
        line_rng = random.Random(s.seed * 104729 + first_line + i)  # stable per line
        if line.kind == "image" and line.image is not None:
            y0 = top_px + cum * line_h + line_h * 0.3
            pasted.append((line.image, round(left_px + line.image_dx), round(y0)))
        elif line.kind in ("text", "table"):
            rule_y = top_px + (cum + 1) * line_h
            baseline = rule_y - max(2.0, line_h * 0.08)
            if line.kind == "text" and line.slots >= 2:
                baseline = top_px + (cum + 1.32) * line_h  # centre the formula across its two lines
            baseline += max(-0.12, min(0.12, line_rng.gauss(0, 1) * lw * 0.05)) * line_h
            if line.kind == "text":
                if line.words or line.prefix:
                    draw_text_line(line, left_px, avail, baseline, line_rng)
            else:
                t = line.table
                pad = CELL_PAD_MM * ppm
                for c, cell in enumerate(t.cells):
                    if cell is not None and cell.words:
                        draw_text_line(cell, left_px + t.col_x[c] + pad, t.widths[c] - 2 * pad, rule_y - max(2.0, line_h * 0.12), line_rng)
                color = s.ink_color
                right = left_px + t.col_x[-1] + t.widths[-1]
                y_top, y_bot = rule_y - line_h, rule_y
                last_on_page = i == len(lines) - 1 or lines[i + 1].kind != "table" or lines[i + 1].block is not line.block
                for x in [left_px + cx for cx in t.col_x] + [right]:
                    _stroke(pen(color), [(x + line_rng.gauss(0, 1) * pen_w * 0.4, y_top - (pen_w if t.top else 0)),
                                         (x + line_rng.gauss(0, 1) * pen_w * 0.4, y_bot + (pen_w if t.bottom else 0))], pen_w * 0.8, rng, 0.3 + gv)
                # Row separators come from the row above's bottom edge; only the first row on a page draws a top.
                first_on_page = i == 0 or lines[i - 1].kind != "table" or lines[i - 1].block is not line.block
                if t.top and first_on_page:
                    _hand_line(pen(color), left_px - pen_w, right + pen_w, y_top, pen_w * 0.8, rng, 0.3 + gv)
                if t.bottom or last_on_page:
                    _hand_line(pen(color), left_px - pen_w, right + pen_w, y_bot, pen_w * 0.8, rng, 0.3 + gv)
        cum += line.slots

    highlights: list[np.ndarray] = []
    for shape in shapes or []:
        if shape["type"] == "highlight":
            hl = Image.new("L", (w, h), 0)
            x1, y1, x2, y2 = shape["x1"] * w, shape["y1"] * h, shape["x2"] * w, shape["y2"] * h
            lx, rx, ty, by = min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)
            jitter = lambda: rng.gauss(0, 1) * pen_w * 0.6  # noqa: E731
            ImageDraw.Draw(hl).polygon([(lx + jitter(), ty + jitter()), (rx + jitter(), ty + jitter()),
                                        (rx + jitter(), by + jitter()), (lx + jitter(), by + jitter())], fill=255)
            highlights.append((np.asarray(hl.filter(ImageFilter.GaussianBlur(pen_w * 0.5)), dtype=np.float32) / 255.0 * 0.5,
                               shape["color"] or HIGHLIGHT))
        else:
            _draw_shape(pen(shape["color"] or s.ink_color), shape, w, h, pen_w, rng)

    for color, img in strokes.items():
        np.maximum(layer(color), np.asarray(img, dtype=np.float32) / 255.0, out=layer(color))

    if iv > 0 and layers:
        # Pen runs a little dry in patches, plus fine grain inside strokes.
        patches = _upsampled_noise(nrng, w, h, max(8, int(ppm * 15)))
        dryness = (1 - iv * 0.35 * patches) * (1 - iv * 0.18 * nrng.random((h, w), dtype=np.float32))
        for arr in layers.values():
            arr *= dryness
    if s.blur > 0:
        for color, arr in list(layers.items()):
            mask = Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), "L")
            mask = mask.filter(ImageFilter.GaussianBlur(radius=s.blur * ppm * 0.2))
            layers[color] = np.asarray(mask, dtype=np.float32) / 255.0

    out = _paper(s, w, h, ppm, line_h, top_px, left_px, mirrored, nrng)
    for img, x0, y0 in pasted:
        # Multiply so ruled lines and paper grain show through, like a printed picture.
        x1, y1 = min(w, x0 + img.width), min(h, y0 + img.height)
        if x1 > max(0, x0) and y1 > max(0, y0):
            part = np.asarray(img, dtype=np.float32)[max(0, -y0):y1 - y0, max(0, -x0):x1 - x0] / 255.0
            out[max(0, y0):y1, max(0, x0):x1] *= part
    for a, color in highlights:
        c = np.array(color, dtype=np.float32) / 255.0
        out *= 1 - a[..., None] * (1 - c)
    for color, a in layers.items():
        c = np.array(color, dtype=np.float32) / 255.0
        out *= 1 - a[..., None] * (1 - c)  # multiply blend keeps paper grain under the ink
    page = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")
    if s.output == "photo":
        page = _photo(page, s.seed * 31 + page_index)
    return page


# ---------------------------------------------------------------- public API

def paginate(content: str, s: Settings, ppm: float) -> tuple[list[tuple[int, list[Line]]], dict]:
    k = ppm / BASE_PX_PER_MM
    pw_mm, ph_mm = s.page_mm()
    avail_w = (pw_mm - s.margin_left - s.margin_right) * ppm - s.font_size * k * 0.6
    if avail_w < s.font_size * k * 3:
        raise ValueError("Margins leave no room for text.")
    lay = _Layout(s, ppm)
    lines = lay.layout(parse(content), avail_w)
    while lines and (lines[-1].kind == "spacer" or lines[-1].kind == "text" and not lines[-1].words and not lines[-1].prefix):
        lines.pop()

    capacity = max(1, int(lay.usable_h // lay.line_h) - 1)
    pages: list[tuple[int, list[Line]]] = []
    cur: list[Line] = []
    used, start = 0.0, 0
    for n, line in enumerate(lines):
        if cur and used + line.slots > capacity + 1e-6:
            pages.append((start, cur))
            cur, used = [], 0.0
        if not cur:
            if line.kind == "spacer":
                continue  # don't start a page with paragraph spacing
            start = n
        cur.append(line)
        used += line.slots
    if cur or not pages:
        pages.append((start, cur))
    truncated = len(pages) > MAX_PAGES
    info = {"pages": min(len(pages), MAX_PAGES), "truncated": truncated,
            "lines_per_page": capacity, "missing": sorted(lay.missing)}
    return pages[:MAX_PAGES], info


def render_document(content: str, settings: Settings, scale: float, only_page: int | None = None,
                    shapes: dict[int, list[dict]] | None = None) -> tuple[list[Image.Image], dict]:
    """Render to page images. `scale` is output pixels per millimetre."""
    pages, info = paginate(content, settings, scale)
    shapes = shapes or {}
    if only_page is not None:
        if not 0 <= only_page < len(pages):
            raise ValueError("That page doesn't exist.")
        start, lines = pages[only_page]
        return [_render_page(lines, start, settings, scale, only_page, shapes.get(only_page))], info
    return [_render_page(lines, start, settings, scale, n, shapes.get(n)) for n, (start, lines) in enumerate(pages)], info


@lru_cache(maxsize=32)
def paper_thumbnail(style: str) -> bytes:
    s = Settings.from_dict({"paper_style": style, "shading": False})
    ppm = 0.8
    w, h = round(210 * ppm), round(297 * ppm)
    line_h = s.font_size * s.line_height * ppm / BASE_PX_PER_MM
    arr = _paper(s, w, h, ppm, line_h, s.margin_top * ppm, s.margin_left * ppm, False, np.random.default_rng(3))
    buf = io.BytesIO()
    Image.fromarray(arr.astype(np.uint8), "RGB").save(buf, "JPEG", quality=85)
    return buf.getvalue()


def pages_to_pdf(pages: list[Image.Image], scale: float) -> bytes:
    buf = io.BytesIO()
    pages[0].save(buf, "PDF", save_all=True, append_images=pages[1:], resolution=scale * 25.4, quality=92)
    return buf.getvalue()


def page_to_jpeg(page: Image.Image) -> bytes:
    # JPEG, not PNG: the paper grain makes PNGs ~5x bigger for no visible gain.
    buf = io.BytesIO()
    page.save(buf, "JPEG", quality=92, subsampling=0, dpi=(203, 203))
    return buf.getvalue()


def pages_to_zip(pages: list[Image.Image]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for i, page in enumerate(pages, 1):
            zf.writestr(f"page-{i}.jpg", page_to_jpeg(page))
    return buf.getvalue()
