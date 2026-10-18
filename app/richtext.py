"""Turn the editor's HTML into a simple list of styled blocks for the renderer.

Only the formatting the renderer understands is kept: headings, paragraphs,
lists, alignment, block size, bold, underline, strikethrough, colour, maths
(elements with data-tex), tables and uploaded images. Everything else in the
HTML is ignored, so pasted or hostile markup is harmless.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

from . import mathtex

MATH_CHAR = "￼"  # placeholder character a maths run carries


@dataclass(frozen=True)
class Style:
    bold: bool = False
    underline: bool = False
    strike: bool = False
    color: tuple[int, int, int] | None = None
    math: str | None = None          # LaTeX source when this run is a formula


@dataclass
class Block:
    kind: str = "p"                  # p, h1, h2, h3, li, table, image
    align: str = "left"              # left, center, right, justify
    scale: float = 1.0               # "block text size"
    list_type: str | None = None     # ul / ol for list items
    list_index: int = 0
    depth: int = 0                   # list nesting level
    first: bool = True               # first visual line of the paragraph (gets the list marker)
    para_end: bool = True            # False when a line break continues the same paragraph
    runs: list[tuple[str, Style]] = field(default_factory=list)
    rows: list[list[list["Block"]]] | None = None   # table: rows -> cells -> lines
    image_id: str | None = None      # image: stored editor image
    image_width: float = 0.6         # image: fraction of the text width

    def has_text(self) -> bool:
        return any(t.strip() for t, _ in self.runs)


BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "pre"}
HEADINGS = {"h1": "h1", "h2": "h2", "h3": "h3", "h4": "h3", "h5": "h3", "h6": "h3"}
SKIP_TAGS = {"script", "style", "head", "title", "template", "svg", "math"}
VOID_TAGS = {"br", "img", "hr", "input", "wbr", "col", "meta", "link", "source"}
MAX_BLOCKS = 4000
MAX_TABLE_CELLS = 600
EDITOR_IMAGE = re.compile(r"^/api/editor-images/([0-9a-f]{16}\.(?:jpg|png))$")
_WS = re.compile(r"[ \t\r\n\f]+")


def parse_color(value: str | None) -> tuple[int, int, int] | None:
    if not value:
        return None
    v = value.strip().lower()
    m = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", v)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    m = re.fullmatch(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*[\d.]+)?\s*\)", v)
    if m:
        return tuple(min(255, int(x)) for x in m.groups())  # type: ignore[return-value]
    return None


def _css(attrs: dict) -> dict[str, str]:
    out = {}
    for part in (attrs.get("style") or "").split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip().lower()] = v.strip().lower()
    return out


def _align(css: dict, attrs: dict, parent: str) -> str:
    v = css.get("text-align") or (attrs.get("align") or "").lower()
    return {"start": "left", "end": "right", "left": "left", "right": "right",
            "center": "center", "justify": "justify"}.get(v, parent)


def _number(raw: str | None, lo: float, hi: float) -> float | None:
    try:
        return min(max(float(raw), lo), hi) if raw else None
    except ValueError:
        return None


def _scale(css: dict, attrs: dict, parent: float) -> float:
    v = _number(attrs.get("data-size"), 0.5, 2.5)
    if v is not None:
        return v
    fs = css.get("font-size", "")
    if fs.endswith("%"):
        v = _number(fs[:-1], 50, 250)
        return v / 100 if v else parent
    if fs.endswith("em"):
        return _number(fs[:-2], 0.5, 2.5) or parent
    return parent


def _inline(style: Style, tag: str, css: dict, attrs: dict) -> Style:
    deco = css.get("text-decoration", "") + " " + css.get("text-decoration-line", "")
    weight = css.get("font-weight", "")
    return Style(
        bold=style.bold or tag in ("b", "strong", "th") or weight in ("bold", "bolder", "600", "700", "800", "900"),
        underline=style.underline or tag in ("u", "ins") or "underline" in deco,
        strike=style.strike or tag in ("s", "strike", "del") or "line-through" in deco,
        color=parse_color(css.get("color") or attrs.get("color")) or style.color,
    )


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self.cur: Block | None = None
        self.pending_br = False
        self.inline: list[tuple[str, Style]] = [("", Style())]
        self.ctx: list[dict] = []
        self.lists: list[list] = []
        self.skip = 0
        self.math_skip = 0               # inside a formula's rendered HTML
        self.table: Block | None = None  # table being collected
        self.cell: list[Block] | None = None
        self.table_depth = 0             # nested tables are flattened into text
        self.cells = 0

    # -- helpers --
    def _top(self) -> dict:
        if self.ctx:
            return self.ctx[-1]
        return {"tag": "", "kind": "p", "align": "left", "scale": 1.0, "li": None, "used": False}

    def _new_block(self) -> Block:
        c = self._top()
        b = Block(kind=c["kind"], align=c["align"], scale=c["scale"], first=not c["used"])
        if c["li"]:
            b.list_type, b.list_index, b.depth = c["li"]
        return b

    def _mark_used(self) -> None:
        for c in self.ctx:
            c["used"] = True

    def _emit(self) -> None:
        if self.cur is not None:
            target = self.cell if self.cell is not None else self.blocks
            if len(target) < MAX_BLOCKS:
                target.append(self.cur)
            self._mark_used()
        self.cur = None
        self.pending_br = False

    def _flush_text(self) -> None:
        if self.cur is not None and self.cur.has_text():
            self._emit()
        self.cur = None
        self.pending_br = False

    def _add_run(self, text: str, style: Style) -> None:
        if self.cur is None:
            self.cur = self._new_block()
        if self.pending_br:
            # A single <br> inside a paragraph: new visual line, same paragraph.
            self.cur.para_end = False
            self._emit()
            self.cur = self._new_block()
            self.cur.first = False
        self.cur.runs.append((text, style))

    # -- tables --
    def _table_tag(self, tag: str, start: bool, attrs: dict, css: dict) -> bool:
        """Handle table structure tags. Returns True when the tag was consumed."""
        if tag == "table":
            if start:
                self.table_depth += 1
                if self.table_depth == 1:
                    self._flush_text()
                    self.table = Block(kind="table", rows=[], align=_align(css, attrs, "left"))
            else:
                self.table_depth = max(0, self.table_depth - 1)
                if self.table_depth == 0 and self.table is not None:
                    self._end_cell()
                    if any(any(row) for row in self.table.rows or []):
                        self.blocks.append(self.table)
                    self.table = None
            return True
        if self.table is None or self.table_depth != 1:
            return tag in ("tr", "td", "th", "thead", "tbody", "tfoot", "caption", "colgroup")
        if tag == "tr":
            if start:
                self._end_cell()
                self.table.rows.append([])
            return True
        if tag in ("td", "th"):
            if start:
                self._end_cell()
                if not self.table.rows:
                    self.table.rows.append([])
                if self.cells >= MAX_TABLE_CELLS:
                    self.cell = []  # collected but dropped
                    return True
                self.cells += 1
                self.cell = []
                self.table.rows[-1].append(self.cell)
                self.ctx.append({"tag": tag, "kind": "p", "li": None, "used": False,
                                 "align": _align(css, attrs, "left"), "scale": 1.0})
                self.inline.append((tag, _inline(self.inline[-1][1], tag, css, attrs)))
            else:
                self._end_cell()
            return True
        return tag in ("thead", "tbody", "tfoot", "caption", "colgroup")

    def _end_cell(self) -> None:
        if self.cell is None:
            return
        if self.cur is not None and (self.cur.has_text() or not self.cell):
            self._emit()
        self.cur = None
        self.pending_br = False
        while self.ctx:
            c = self.ctx.pop()
            if self.inline[-1][0] == c["tag"]:
                self.inline.pop()
            if c["tag"] in ("td", "th"):
                break
        self.cell = None

    # -- parser callbacks --
    def handle_starttag(self, tag: str, attrs_list) -> None:
        if tag in SKIP_TAGS:
            self.skip += 1
            return
        if self.skip:
            return
        if self.math_skip:
            if tag not in VOID_TAGS:
                self.math_skip += 1
            return
        attrs = {k: v or "" for k, v in attrs_list}
        css = _css(attrs)
        if attrs.get("data-tex") is not None:
            tex = attrs["data-tex"][:1000]
            if tex.strip():
                base = self.inline[-1][1]
                self._add_run(MATH_CHAR, Style(base.bold, base.underline, base.strike, base.color, tex))
            if tag not in VOID_TAGS:
                self.math_skip = 1
            return
        if self._table_tag(tag, True, attrs, css):
            return
        if tag == "img":
            m = EDITOR_IMAGE.match(attrs.get("src", ""))
            if m and self.cell is None:
                self._flush_text()
                width = _number(attrs.get("data-width"), 0.1, 1.0) or 0.6
                self.blocks.append(Block(kind="image", image_id=m.group(1), image_width=width,
                                         align=self._top()["align"]))
                self._mark_used()
            return
        if tag in ("ul", "ol"):
            self._flush_text()
            self.lists.append([tag, 0])
            return
        if tag in BLOCK_TAGS:
            self._flush_text()
            parent = self._top()
            li = parent["li"]
            if self.cell is not None:
                kind = "p"
                li = None
            elif tag in HEADINGS:
                kind = HEADINGS[tag]
            elif tag == "li":
                kind = "li"
                lst = self.lists[-1] if self.lists else ["ul", 0]
                lst[1] += 1
                li = (lst[0], lst[1], max(0, len(self.lists) - 1))
            else:
                kind = parent["kind"] if parent["kind"] == "li" else "p"
            self.ctx.append({
                "tag": tag, "kind": kind, "li": li if kind == "li" else None,
                "align": _align(css, attrs, parent["align"]),
                "scale": _scale(css, attrs, parent["scale"]),
                "used": False if tag == "li" or not parent["used"] or parent["kind"] != "li" else True,
            })
            self.inline.append((tag, _inline(self.inline[-1][1], "", css, attrs)))
            return
        if tag == "br":
            if self.cur is None:
                self.cur = self._new_block()
            if self.pending_br:
                # Second break in a row: finish this line and start an empty one.
                self.cur.para_end = False
                self._emit()
                self.cur = self._new_block()
                self.cur.first = False
            self.pending_br = True
            return
        if tag in VOID_TAGS:
            return
        self.inline.append((tag, _inline(self.inline[-1][1], tag, css, attrs)))

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if self.math_skip:
            self.math_skip -= 1
            return
        if self._table_tag(tag, False, {}, {}):
            return
        if tag in ("ul", "ol"):
            self._flush_text()
            if self.lists:
                self.lists.pop()
            return
        if tag in BLOCK_TAGS:
            if not any(c["tag"] == tag for c in self.ctx):
                return
            if self.cur is not None:
                self._emit()
            elif not self._top()["used"]:
                # Empty paragraph (<p></p> or <p><br></p>) -> blank line.
                self.cur = self._new_block()
                self._emit()
            while self.ctx:
                c = self.ctx.pop()
                if self.inline[-1][0] == c["tag"]:
                    self.inline.pop()
                if c["tag"] == tag:
                    break
            return
        for i in range(len(self.inline) - 1, 0, -1):
            if self.inline[i][0] == tag:
                del self.inline[i:]
                break

    def handle_data(self, data: str) -> None:
        if self.skip or self.math_skip:
            return
        if self.table is not None and self.cell is None:
            return  # stray text between table cells
        text = _WS.sub(" ", data).replace("\xa0", " ").replace(MATH_CHAR, "")
        if not text:
            return
        if self.cur is None and not text.strip():
            return
        if (self.cur is None or not self.cur.runs or self.pending_br) and not text.strip():
            return
        if self.cur is None or not self.cur.runs or self.pending_br:
            text = text.lstrip()
        style = self.inline[-1][1]
        # Text copied from AI chats often carries maths as \( … \) — turn it into formulas.
        for piece, is_math in mathtex.split_delimited(text) if "\\" in text or "$$" in text else [(text, False)]:
            if is_math:
                self._add_run(MATH_CHAR, Style(style.bold, style.underline, style.strike, style.color, piece[:1000]))
            elif piece:
                self._add_run(piece, style)

    def close(self) -> None:
        super().close()
        if self.table is not None:
            self._end_cell()
            if any(any(row) for row in self.table.rows or []):
                self.blocks.append(self.table)
            self.table = None
        if self.cur is not None and self.cur.has_text():
            self._emit()


def parse(content: str) -> list[Block]:
    """Parse editor HTML (or plain text) into blocks."""
    if "<" not in content:
        return [Block(runs=[(line, Style())] if line.strip() else [])
                for line in content.replace("\r\n", "\n").split("\n")][:MAX_BLOCKS]
    p = _Parser()
    p.feed(content)
    p.close()
    blocks = p.blocks
    while blocks and blocks[-1].kind not in ("table", "image") and not blocks[-1].has_text():
        blocks.pop()
    return blocks
