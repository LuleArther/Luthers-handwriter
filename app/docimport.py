"""Import .docx and .pdf files as editor HTML.

DOCX keeps headings, bold/underline/strikethrough, colours, alignment, lists
and tables. PDF files only contain positioned text, so paragraphs are rebuilt
from the lines (good for typed documents, not for scans).
"""
from __future__ import annotations

import html
import io
import re
import zipfile
import xml.etree.ElementTree as ET

MAX_IMPORT_BYTES = 20 * 1024 * 1024
MAX_XML_BYTES = 30 * 1024 * 1024     # uncompressed document.xml (zip-bomb guard)
MAX_PAGES = 100
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"


def parse_pages(spec: str | None, total: int) -> list[int]:
    """'1-3, 5' -> [0, 1, 2, 4] (0-based). Empty means all pages."""
    if not spec or not spec.strip():
        return list(range(min(total, MAX_PAGES)))
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)|(\d+)", part)
        if not m:
            raise ValueError(f"Can't read the page range “{part}”. Use something like 1-3, 5.")
        a, b = (int(m.group(1)), int(m.group(2))) if m.group(1) else (int(m.group(3)), int(m.group(3)))
        if a < 1 or b < a:
            raise ValueError(f"“{part}” isn't a valid page range.")
        out.update(range(a - 1, min(b, total)))
    if not out:
        raise ValueError("None of those pages exist in this document.")
    return sorted(out)[:MAX_PAGES]


# ---------------------------------------------------------------- DOCX

def _attr(el, name: str) -> str | None:
    return el.get(W + name) if el is not None else None


def _numbering_formats(z: zipfile.ZipFile) -> dict[str, str]:
    """numId -> 'ol' or 'ul' (from the first list level)."""
    try:
        info = z.getinfo("word/numbering.xml")
    except KeyError:
        return {}
    if info.file_size > MAX_XML_BYTES:
        return {}
    root = ET.fromstring(z.read(info))
    abstract = {}
    for an in root.findall(W + "abstractNum"):
        lvl = an.find(W + "lvl")
        fmt = _attr(lvl.find(W + "numFmt"), "val") if lvl is not None else None
        abstract[_attr(an, "abstractNumId")] = "ul" if fmt in (None, "bullet", "none") else "ol"
    out = {}
    for num in root.findall(W + "num"):
        ref = num.find(W + "abstractNumId")
        out[_attr(num, "numId")] = abstract.get(_attr(ref, "val"), "ul")
    return out


def _runs_html(p) -> str:
    parts = []
    for node in p.iter():
        if node.tag == M + "oMath":
            text = "".join(t.text or "" for t in node.iter(M + "t"))
            if text:
                parts.append(f'<span data-tex="{html.escape(text)}">{html.escape(text)}</span>')
            continue
        if node.tag != W + "r":  # maths runs are m:r, so they're skipped here
            continue
        rpr = node.find(W + "rPr")
        text = []
        for child in node:
            if child.tag == W + "t":
                text.append(html.escape(child.text or ""))
            elif child.tag == W + "tab":
                text.append("&nbsp;&nbsp;&nbsp;&nbsp;")
            elif child.tag in (W + "br", W + "cr"):
                text.append("<br>")
        s = "".join(text)
        if not s:
            continue
        if rpr is not None:
            def on(tag: str) -> bool:
                el = rpr.find(W + tag)
                return el is not None and _attr(el, "val") not in ("0", "false", "none")
            color = _attr(rpr.find(W + "color"), "val")
            if color and re.fullmatch(r"[0-9A-Fa-f]{6}", color) and color.lower() not in ("000000", "auto"):
                s = f'<span style="color: #{color.lower()};">{s}</span>'
            if on("strike") or on("dstrike"):
                s = f"<s>{s}</s>"
            if on("u"):
                s = f"<u>{s}</u>"
            if on("b"):
                s = f"<b>{s}</b>"
        parts.append(s)
    return "".join(parts)


def _paragraph(p, numbering: dict[str, str]) -> tuple[str, str | None, int]:
    """Returns (html, list type or None, list level)."""
    ppr = p.find(W + "pPr")
    style = (_attr(ppr.find(W + "pStyle"), "val") if ppr is not None else "") or ""
    jc = _attr(ppr.find(W + "jc"), "val") if ppr is not None else None
    align = {"center": "center", "right": "right", "end": "right", "both": "justify", "distribute": "justify"}.get(jc or "")
    style_attr = f' style="text-align: {align};"' if align else ""
    body = _runs_html(p) or "<br>"
    numpr = ppr.find(W + "numPr") if ppr is not None else None
    if numpr is not None:
        num_id = _attr(numpr.find(W + "numId"), "val")
        level = int(_attr(numpr.find(W + "ilvl"), "val") or 0)
        if num_id and num_id != "0":
            return body, numbering.get(num_id, "ul"), level
    s = style.lower()
    if s in ("title", "heading1") or s.startswith("heading1"):
        tag = "h1"
    elif s.startswith("heading2") or s == "subtitle":
        tag = "h2"
    elif s.startswith("heading"):
        tag = "h3"
    else:
        tag = "p"
    return f"<{tag}{style_attr}>{body}</{tag}>", None, 0


def _table(tbl, numbering) -> str:
    rows = []
    for tr in tbl.findall(W + "tr"):
        cells = []
        for tc in tr.findall(W + "tc"):
            lines = [_runs_html(p) for p in tc.findall(W + "p")]
            cells.append("<td>" + ("<br>".join(l for l in lines if l) or "<br>") + "</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return "<table>" + "".join(rows) + "</table>"


def docx_to_html(data: bytes) -> str:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        info = z.getinfo("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as e:
        raise ValueError("That isn't a Word .docx file we can read.") from e
    if info.file_size > MAX_XML_BYTES:
        raise ValueError("That document is too large to import.")
    root = ET.fromstring(z.read(info))
    numbering = _numbering_formats(z)
    body = root.find(W + "body")
    out: list[str] = []
    open_lists: list[str] = []

    def close_lists(to: int = 0) -> None:
        while len(open_lists) > to:
            out.append(f"</{open_lists.pop()}>")

    for child in list(body) if body is not None else []:
        if child.tag == W + "p":
            content, list_type, level = _paragraph(child, numbering)
            if list_type:
                while len(open_lists) > level + 1:
                    out.append(f"</{open_lists.pop()}>")
                if len(open_lists) == level + 1 and open_lists[-1] != list_type:
                    out.append(f"</{open_lists.pop()}>")  # bullets followed by numbers: new list
                while len(open_lists) < level + 1:
                    open_lists.append(list_type)
                    out.append(f"<{list_type}>")
                out.append(f"<li>{content}</li>")
            else:
                close_lists()
                out.append(content)
        elif child.tag == W + "tbl":
            close_lists()
            out.append(_table(child, numbering))
    close_lists()
    return "".join(out) or "<p><br></p>"


# ---------------------------------------------------------------- PDF

def pdf_to_html(data: bytes, pages_spec: str | None) -> tuple[str, int]:
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("That PDF is password-protected.")
        total = len(reader.pages)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError("That isn't a PDF we can read.") from e
    out: list[str] = []
    for n in parse_pages(pages_spec, total):
        try:
            text = reader.pages[n].extract_text() or ""
        except Exception:
            text = ""
        lines = [l.rstrip() for l in text.replace("\r", "").split("\n")]
        longest = max((len(l) for l in lines), default=0)
        para: list[str] = []

        def flush() -> None:
            if para:
                out.append("<p>" + html.escape(" ".join(para)) + "</p>")
                para.clear()

        for line in lines:
            stripped = line.strip()
            if not stripped:
                flush()
                continue
            para.append(stripped)
            # A clearly short line ends its paragraph (headings, last lines, list items).
            if len(stripped) < longest * 0.6 or re.match(r"^([•\-–*]|\d+[.)])\s", stripped):
                flush()
        flush()
        out.append("<p><br></p>")
    if not any(chunk != "<p><br></p>" for chunk in out):
        raise ValueError("No text found in those pages. Scanned PDFs (photos of pages) can't be imported yet.")
    return "".join(out), total


def import_file(filename: str, data: bytes, pages_spec: str | None) -> dict:
    if len(data) > MAX_IMPORT_BYTES:
        raise ValueError("File is larger than 20 MB.")
    name = (filename or "").lower()
    if name.endswith(".pdf") or data[:5] == b"%PDF-":
        content, total = pdf_to_html(data, pages_spec)
        return {"html": content, "pages": total, "kind": "pdf"}
    if name.endswith(".docx") or data[:2] == b"PK":
        return {"html": docx_to_html(data), "pages": None, "kind": "docx"}
    raise ValueError("Please choose a .pdf or .docx file. (Old .doc files: open in Word and save as .docx.)")
