"""Generate the per-language share preview cards (issue #128).

Writes app/static/og/verbs-{language}.png (1200x630), one per free study language. Run it only when
the design or the language list changes, and commit the PNGs. Pillow is a dev-only dependency:

    uv run --with pillow python tools/make_share_cards.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.languages.config import FREE_STUDY_LANGUAGES  # noqa: E402
from core.share_service import OG_IMAGE_HEIGHT, OG_IMAGE_WIDTH  # noqa: E402

OUT_DIR = REPO_ROOT / "app" / "static" / "og"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BACKGROUND = (45, 106, 79)  # the app's theme-color #2d6a4f
PALE = (216, 243, 220)
WHITE = (255, 255, 255)

# Each language in its own script, the way a learner of it would recognise it.
NATIVE_NAMES = {
    "en": "English",
    "ru": "Русский",
    "he": "עברית",
    "es": "Español",
    "it": "Italiano",
    "fr": "Français",
    "pt": "Português",
}
TAGLINE = "Verb conjugations, examples and audio"


def _visual(text: str, rtl: bool, has_raqm: bool) -> str:
    """Pillow without raqm lays text out left to right, so a Hebrew word must be reversed by hand."""
    return text[::-1] if rtl and not has_raqm else text


def build_card(language: str) -> None:
    from PIL import Image, ImageDraw, ImageFont, features

    has_raqm = features.check("raqm")
    image = Image.new("RGB", (OG_IMAGE_WIDTH, OG_IMAGE_HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    brand_font = ImageFont.truetype(FONT_BOLD, 44)
    name_font = ImageFont.truetype(FONT_BOLD, 150)
    tagline_font = ImageFont.truetype(FONT_REGULAR, 40)

    draw.text((80, 70), "VerbBoard", font=brand_font, fill=PALE)
    name = _visual(NATIVE_NAMES[language], language == "he", has_raqm)
    name_box = draw.textbbox((0, 0), name, font=name_font)
    name_width = name_box[2] - name_box[0]
    draw.text(
        ((OG_IMAGE_WIDTH - name_width) / 2 - name_box[0], 230),
        name,
        font=name_font,
        fill=WHITE,
    )
    tagline_box = draw.textbbox((0, 0), TAGLINE, font=tagline_font)
    draw.text(
        ((OG_IMAGE_WIDTH - (tagline_box[2] - tagline_box[0])) / 2, 470),
        TAGLINE,
        font=tagline_font,
        fill=PALE,
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    image.save(OUT_DIR / f"verbs-{language}.png", optimize=True)


def main() -> int:
    missing = [code for code in FREE_STUDY_LANGUAGES if code not in NATIVE_NAMES]
    if missing:
        print(f"No native name for: {', '.join(missing)}", file=sys.stderr)
        return 2
    for language in FREE_STUDY_LANGUAGES:
        build_card(language)
        print(f"wrote {OUT_DIR / f'verbs-{language}.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
