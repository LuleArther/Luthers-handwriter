"""Font registry: built-in fonts, user-uploaded fonts, and character coverage."""
from __future__ import annotations

import hashlib
import io
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import ImageFont

BUILTIN_DIR = Path(__file__).parent / "fonts"
DATA_DIR = Path(os.environ.get("HANDWRITER_DATA", Path(__file__).resolve().parent.parent / "data"))
CUSTOM_DIR = DATA_DIR / "custom_fonts"
MAX_FONT_BYTES = 10 * 1024 * 1024
CUSTOM_ID = re.compile(r"^u-[0-9a-f]{16}$")

# (id, display name, candidate file names, is_cursive). Order = order shown in the picker.
# Fonts whose file isn't present are simply skipped.
BUILTIN = [
    ("caveat", "Caveat", ["Caveat[wght].ttf"], False),
    ("kalam", "Kalam", ["Kalam-Regular.ttf"], False),
    ("indie-flower", "Indie Flower", ["IndieFlower-Regular.ttf"], False),
    ("shadows-into-light", "Shadows Into Light", ["ShadowsIntoLight.ttf"], False),
    ("patrick-hand", "Patrick Hand", ["PatrickHand-Regular.ttf"], False),
    ("reenie-beanie", "Reenie Beanie", ["ReenieBeanie.ttf"], False),
    ("homemade-apple", "Homemade Apple", ["HomemadeApple-Regular.ttf"], True),
    ("dancing-script", "Dancing Script", ["DancingScript[wght].ttf"], True),
    ("nothing-you-could-do", "Nothing You Could Do", ["NothingYouCouldDo.ttf", "NothingYouCouldDo-Regular.ttf"], True),
    ("la-belle-aurore", "La Belle Aurore", ["LaBelleAurore.ttf", "LaBelleAurore-Regular.ttf"], True),
    ("cedarville-cursive", "Cedarville Cursive", ["Cedarville-Cursive.ttf"], True),
    ("zeyada", "Zeyada", ["Zeyada.ttf", "Zeyada-Regular.ttf"], True),
    ("calligraffitti", "Calligraffitti", ["Calligraffitti-Regular.ttf"], True),
    ("bad-script", "Bad Script", ["BadScript-Regular.ttf"], True),
    ("marck-script", "Marck Script", ["MarckScript-Regular.ttf"], True),
    ("gochi-hand", "Gochi Hand", ["GochiHand-Regular.ttf"], False),
    ("covered-by-your-grace", "Covered By Your Grace", ["CoveredByYourGrace.ttf"], False),
    ("architects-daughter", "Architects Daughter", ["ArchitectsDaughter-Regular.ttf"], False),
    ("the-girl-next-door", "The Girl Next Door", ["TheGirlNextDoor.ttf", "TheGirlNextDoor-Regular.ttf"], False),
    ("sue-ellen-francisco", "Sue Ellen Francisco", ["SueEllenFrancisco-Regular.ttf", "SueEllenFrancisco.ttf"], False),
    ("waiting-for-the-sunrise", "Waiting for the Sunrise", ["WaitingfortheSunrise.ttf", "WaitingfortheSunrise-Regular.ttf"], False),
    ("annie-use-your-telescope", "Annie Use Your Telescope", ["AnnieUseYourTelescope-Regular.ttf", "AnnieUseYourTelescope.ttf"], False),
    ("just-another-hand", "Just Another Hand", ["JustAnotherHand-Regular.ttf"], False),
    ("schoolbell", "Schoolbell", ["Schoolbell-Regular.ttf"], False),
    ("handlee", "Handlee", ["Handlee-Regular.ttf"], False),
    ("gloria-hallelujah", "Gloria Hallelujah", ["GloriaHallelujah.ttf", "GloriaHallelujah-Regular.ttf"], False),
    ("rock-salt", "Rock Salt", ["RockSalt-Regular.ttf"], False),
    ("permanent-marker", "Permanent Marker", ["PermanentMarker-Regular.ttf"], False),
    ("amatic-sc", "Amatic SC", ["AmaticSC-Regular.ttf"], False),
    ("caveat-brush", "Caveat Brush", ["CaveatBrush-Regular.ttf"], False),
    ("neucha", "Neucha", ["Neucha.ttf", "Neucha-Regular.ttf"], False),
    ("pangolin", "Pangolin", ["Pangolin-Regular.ttf"], False),
    ("shantell-sans", "Shantell Sans", ["ShantellSans[BNCE,INFM,SPAC,wght].ttf"], False),
    ("comic-neue", "Comic Neue", ["ComicNeue-Regular.ttf"], False),
    ("mali", "Mali", ["Mali-Regular.ttf"], False),
    ("sriracha", "Sriracha", ["Sriracha-Regular.ttf"], False),
    ("itim", "Itim", ["Itim-Regular.ttf"], False),
    ("marhey", "Marhey", ["Marhey[wght].ttf"], False),
    ("nanum-pen", "Nanum Pen", ["NanumPenScript-Regular.ttf"], False),
    ("klee-one", "Klee One", ["KleeOne-Regular.ttf"], False),
    ("yomogi", "Yomogi", ["Yomogi-Regular.ttf"], False),
]
# Last-resort font for maths symbols (⇒, ∑, ∫ …) that no handwriting font has. Not selectable.
SYMBOL_FONT = BUILTIN_DIR / "NotoSansMath-Regular.ttf"

# A script counts as supported when the font covers most of these sample ranges.
SCRIPTS = {
    "latin": [(0x41, 0x5A), (0x61, 0x7A)],
    "cyrillic": [(0x410, 0x44F)],
    "greek": [(0x391, 0x3A1), (0x3A3, 0x3A9), (0x3B1, 0x3C9)],
    "arabic": [(0x627, 0x63A), (0x641, 0x64A)],
    "devanagari": [(0x905, 0x939)],
    "korean": [(0xAC00, 0xAC00 + 399)],
    "japanese": [(0x3042, 0x3093)],
    "thai": [(0xE01, 0xE2E)],
}


@dataclass(frozen=True)
class FontInfo:
    id: str
    name: str
    path: str
    cursive: bool = False
    custom: bool = False


@lru_cache(maxsize=1)
def builtin_fonts() -> tuple[FontInfo, ...]:
    out = []
    for fid, name, files, cursive in BUILTIN:
        path = next((BUILTIN_DIR / f for f in files if (BUILTIN_DIR / f).exists()), None)
        if path:
            out.append(FontInfo(fid, name, str(path), cursive))
    return tuple(out)


def default_font() -> FontInfo:
    fonts = builtin_fonts()
    if not fonts:
        raise RuntimeError(f"No fonts found in {BUILTIN_DIR}")
    return fonts[0]


def get_font(font_id: str | None) -> FontInfo | None:
    font_id = str(font_id or "")
    for f in builtin_fonts():
        if f.id == font_id:
            return f
    if CUSTOM_ID.match(font_id):
        for path in CUSTOM_DIR.glob(f"{font_id[2:]}.*"):
            return FontInfo(font_id, _font_name(str(path)), str(path), False, True)
    return None


@lru_cache(maxsize=256)
def _font_name(path: str) -> str:
    try:
        names = TTFont(path, lazy=True)["name"]
        return (names.getDebugName(4) or names.getDebugName(1) or "Custom font")[:40]
    except Exception:
        return "Custom font"


@lru_cache(maxsize=256)
def codepoints(path: str) -> frozenset[int]:
    try:
        return frozenset(TTFont(path, lazy=True).getBestCmap() or {})
    except Exception:
        return frozenset()


@lru_cache(maxsize=256)
def size_factor(path: str) -> float:
    """Scale so every font has the same lowercase height at the same size setting."""
    font = ImageFont.truetype(path, 100)
    sample = "x" if ord("x") in codepoints(path) else None
    if sample is None:
        return 1.0
    _, top, _, _ = font.getbbox(sample, anchor="ls")
    return min(max(46 / max(-top, 1), 0.7), 1.5)


@lru_cache(maxsize=256)
def scripts(path: str) -> tuple[str, ...]:
    cps = codepoints(path)
    found = []
    for name, ranges in SCRIPTS.items():
        total = sum(b - a + 1 for a, b in ranges)
        have = sum(1 for a, b in ranges for cp in range(a, b + 1) if cp in cps)
        if have >= total * 0.8:
            found.append(name)
    return tuple(found)


@lru_cache(maxsize=256)
def ranges(path: str) -> tuple[tuple[int, int], ...]:
    """Supported code points as compact [start, end] ranges (sent to the browser)."""
    out: list[list[int]] = []
    for cp in sorted(codepoints(path)):
        if out and cp == out[-1][1] + 1:
            out[-1][1] = cp
        else:
            out.append([cp, cp])
    return tuple((a, b) for a, b in out)


@lru_cache(maxsize=4096)
def fallback_for(cp: int) -> FontInfo | None:
    """First built-in font (print styles before cursive) that has this character."""
    fonts = sorted(builtin_fonts(), key=lambda f: f.cursive)
    for f in fonts:
        if cp in codepoints(f.path):
            return f
    if SYMBOL_FONT.exists() and cp in codepoints(str(SYMBOL_FONT)):
        return FontInfo("symbols", "Symbols", str(SYMBOL_FONT))
    return None


def describe(f: FontInfo) -> dict:
    return {
        "id": f.id,
        "name": f.name,
        "url": f"/api/fonts/{f.id}/file",
        "cursive": f.cursive,
        "custom": f.custom,
        "scripts": list(scripts(f.path)),
        "size_factor": round(size_factor(f.path), 4),
        "ranges": ranges(f.path),
    }


def save_custom(data: bytes) -> FontInfo:
    """Validate an uploaded font file and store it. Raises ValueError if unusable."""
    if len(data) > MAX_FONT_BYTES:
        raise ValueError("Font file is larger than 10 MB.")
    try:
        tt = TTFont(io.BytesIO(data))
        cmap = tt.getBestCmap() or {}
    except Exception as e:
        raise ValueError("That file isn't a font we can read (use .ttf, .otf or .woff).") from e
    if len(cmap) < 10:
        raise ValueError("That font has almost no characters in it.")
    if tt.flavor:  # woff/woff2 -> plain sfnt so FreeType and browsers both read it
        tt.flavor = None
        buf = io.BytesIO()
        tt.save(buf)
        data = buf.getvalue()
    ext = "otf" if "CFF " in tt or "CFF2" in tt else "ttf"
    digest = hashlib.sha256(data).hexdigest()[:16]
    CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
    path = CUSTOM_DIR / f"{digest}.{ext}"
    if not path.exists():
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        try:
            ImageFont.truetype(str(tmp), 40).getbbox("A")
        except Exception as e:
            tmp.unlink(missing_ok=True)
            raise ValueError("That font can't be drawn.") from e
        tmp.replace(path)
    info = get_font(f"u-{digest}")
    assert info is not None
    return info
