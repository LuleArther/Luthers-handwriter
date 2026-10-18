# Handwriter

Turns typed text into realistic handwritten pages (preview in the browser, download PDF, ZIP or single pages). Free, no accounts..

## How it works
- `app/richtext.py`: turns the editor's HTML into styled blocks (headings, paragraphs, lists,
  alignment, block size, bold/underline/strikethrough/colour). Anything else is ignored.
- `app/renderer.py`: the engine. Lays the blocks out (wrapping, hyphenation, lists, alignment,
  pagination), draws every letter separately with small random rotation/size/slant/position/
  ink-pressure changes, adds word and line wobble, ink unevenness and blur, then blends each ink
  colour onto generated paper (8 styles). "Photo" output places the page on a desk with
  perspective, shadow and lighting. A `seed` makes results repeatable.
- `app/fonts.py`: built-in and uploaded fonts, character coverage, language groups, backup fonts.
- `app/main.py`: FastAPI server. Body for render calls: `{"html": "...", "settings": {...}}`.
  - `POST /api/preview` -> low-res JPEG pages
  - `POST /api/export?format=pdf|zip|image[&page=N]` -> ~200 dpi download
  - `GET /api/fonts`, `GET /api/fonts/{id}/file`, `POST /api/fonts/upload`, `GET /api/paper/{style}.jpg`
- `app/static/`: the web page (no build step, no external libraries).
- `app/fonts/`: Google Fonts handwriting fonts (commercial use allowed, see `LICENSES.md`).
- `data/custom_fonts/`: fonts people upload (kept on the server; mount it as a volume in Docker).

## Run locally (Mac)
```bash
cd ~/"Text to Handwriting/handwriter"
./.venv/bin/uvicorn app.main:app --reload --port 8000
```
Then open http://127.0.0.1:8000

## Deploy on the Oracle VPS (Docker)
From the Mac, copy the project up (excluding the local virtualenv):
```bash
cd ~/"Text to Handwriting"
tar --exclude handwriter/.venv --exclude handwriter/samples --exclude handwriter/data -czf handwriter.tgz handwriter
scp handwriter.tgz ubuntu@YOUR_SERVER_IP:~
```
On the server:
```bash
tar xzf handwriter.tgz && cd handwriter
mkdir -p data && sudo chown 10001 data   # the container's user must own the uploaded-fonts folder
docker compose up -d --build
```
The app listens on port 8000. Open it in the VPS firewall (Oracle security list + `iptables`),
or put it behind a reverse proxy such as Caddy for HTTPS on a domain.

## Adding a font
Drop a `.ttf` into `app/fonts/` and add a line to `FONT_CATALOG` in `app/renderer.py`.
Only use fonts whose licence allows commercial use.

## Licence
The code is released under the [MIT License](LICENSE): anyone may use, change and share it,
as long as the copyright notice stays, and it comes with no warranty.

The handwriting fonts in `app/fonts/` keep their own open licences (SIL Open Font License 1.1
or Apache 2.0) — see [app/fonts/LICENSES.md](app/fonts/LICENSES.md). They may be bundled and
used commercially, but not sold on their own.
