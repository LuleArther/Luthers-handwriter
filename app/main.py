"""Handwriter web server: serves the page and renders handwriting on request."""
from __future__ import annotations

import base64
import io
import threading
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import docimport
from . import fonts as fontreg
from . import images as editor_images
from . import renderer

PREVIEW_SCALE = 3.0  # px per mm -> A4 preview is 630x891
EXPORT_SCALE = 8.0   # px per mm -> ~203 dpi, A4 is 1680x2376
MAX_CHARS = 300_000  # HTML characters (formatting included; images are stored separately)

# Rendering is CPU heavy; cap how many run at once so a small VPS stays responsive.
render_slots = threading.BoundedSemaphore(2)

app = FastAPI(title="Handwriter", docs_url=None, redoc_url=None)


@app.middleware("http")
async def always_fresh_page(request, call_next):
    """Make browsers re-check the page, script and styles every time, so updates show up
    immediately instead of mixing an old cached script with a new page."""
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


class RenderRequest(BaseModel):
    html: str = Field(default="", max_length=MAX_CHARS)
    settings: dict = Field(default_factory=dict)
    shapes: dict = Field(default_factory=dict)  # {page index: [{type, x1, y1, x2, y2, color}]}


def _render(req: RenderRequest, scale: float, only_page: int | None = None):
    if not render_slots.acquire(timeout=30):
        raise HTTPException(503, "Server is busy, please try again in a moment.")
    try:
        settings = renderer.Settings.from_dict(req.settings)
        shapes = renderer.parse_shapes(req.shapes)
        return renderer.render_document(req.html, settings, scale, only_page, shapes)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    finally:
        render_slots.release()


def _download(data: bytes, media: str, name: str) -> Response:
    return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})


def _paper_info(pid: str, spec: dict) -> dict:
    """Paper colours as hex so the editor can mimic the paper with CSS."""
    def hx(c):
        return "#%02x%02x%02x" % c if c else None
    kind = "rules" if "rules" in spec else "grid" if "grid" in spec else "dots" if "dots" in spec else "blank"
    return {
        "id": pid, "name": spec["name"], "kind": kind, "color": hx(spec["color"]),
        "line": hx(spec.get("rules") or spec.get("grid") or spec.get("dots")),
        "margin": spec.get("margin", 0), "margin_color": hx(spec.get("margin_color", (225, 120, 125))),
    }


@app.get("/api/options")
def options():
    return {
        "presets": [*renderer.PRESETS, "custom"],
        "preset_values": renderer.PRESETS,
        "papers": [_paper_info(k, v) for k, v in renderer.PAPERS.items()],
        "paper_sizes": {k: list(v) for k, v in renderer.PAGE_SIZES_MM.items()},
        "max_chars": MAX_CHARS,
        "max_pages": renderer.MAX_PAGES,
        "max_font_mb": fontreg.MAX_FONT_BYTES // (1024 * 1024),
        "max_image_mb": editor_images.MAX_UPLOAD_BYTES // (1024 * 1024),
        "max_import_mb": docimport.MAX_IMPORT_BYTES // (1024 * 1024),
        "shapes": list(renderer.SHAPES),
    }


@app.get("/api/fonts")
def list_fonts(custom: str = ""):
    fonts = [fontreg.describe(f) for f in fontreg.builtin_fonts()]
    for fid in custom.split(",")[:50]:
        f = fontreg.get_font(fid.strip()) if fontreg.CUSTOM_ID.match(fid.strip()) else None
        if f:
            fonts.append(fontreg.describe(f))
    return {"fonts": fonts}


@app.get("/api/fonts/{font_id}/file")
def font_file(font_id: str):
    f = fontreg.get_font(font_id)
    if not f:
        raise HTTPException(404, "Font not found")
    media = "font/otf" if f.path.endswith(".otf") else "font/ttf"
    return FileResponse(f.path, media_type=media, headers={"Cache-Control": "public, max-age=604800"})


@app.post("/api/fonts/upload")
async def upload_font(file: UploadFile = File(...)):
    data = await file.read(fontreg.MAX_FONT_BYTES + 1)
    try:
        f = fontreg.save_custom(data)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"font": fontreg.describe(f)}


@app.post("/api/editor-images")
async def upload_editor_image(file: UploadFile = File(...)):
    data = await file.read(editor_images.MAX_UPLOAD_BYTES + 1)
    try:
        image_id = editor_images.save(data)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"url": f"/api/editor-images/{image_id}"}


@app.get("/api/editor-images/{image_id}")
def editor_image(image_id: str):
    path = editor_images.path_for(image_id)
    if not path:
        raise HTTPException(404, "Image not found")
    media = "image/png" if image_id.endswith(".png") else "image/jpeg"
    return FileResponse(path, media_type=media, headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.post("/api/import")
async def import_document(file: UploadFile = File(...), pages: str = Form("")):
    data = await file.read(docimport.MAX_IMPORT_BYTES + 1)
    if not render_slots.acquire(timeout=30):
        raise HTTPException(503, "Server is busy, please try again in a moment.")
    try:
        return docimport.import_file(file.filename or "", data, pages[:200])
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    finally:
        render_slots.release()


@app.get("/api/paper/{style}.jpg")
def paper_thumb(style: str):
    if style not in renderer.PAPERS:
        raise HTTPException(404, "Unknown paper")
    return Response(renderer.paper_thumbnail(style), media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.post("/api/preview")
def preview(req: RenderRequest):
    pages, info = _render(req, PREVIEW_SCALE)
    images = []
    for page in pages:
        buf = io.BytesIO()
        page.save(buf, "JPEG", quality=82)
        images.append("data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode())
    return {"images": images, **info}


@app.post("/api/export")
def export(req: RenderRequest,
           format: str = Query("pdf", pattern="^(pdf|zip|image)$"),
           page: int | None = Query(None, ge=1, le=renderer.MAX_PAGES)):
    if format == "image":
        pages, _ = _render(req, EXPORT_SCALE, (page or 1) - 1)
        return _download(renderer.page_to_jpeg(pages[0]), "image/jpeg", f"handwriting-page-{page or 1}.jpg")
    pages, _ = _render(req, EXPORT_SCALE)
    if format == "pdf":
        return _download(renderer.pages_to_pdf(pages, EXPORT_SCALE), "application/pdf", "handwriting.pdf")
    return _download(renderer.pages_to_zip(pages), "application/zip", "handwriting-pages.zip")


@app.get("/healthz")
def healthz():
    return {"ok": True, "fonts": len(fontreg.builtin_fonts())}


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
