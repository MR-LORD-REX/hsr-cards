"""Rendering remains usable when system fonts are absent or unreadable."""
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import pytest

from hsr_cards.renderer.nanoka import character_info
from hsr_cards.renderer.nanoka.skills import text, typography
from hsr_cards.renderer.prydwen.builds import primitives
from hsr_cards.prydwen.builds.batch import _contact_sheets
from hsr_cards.utils.hsrfonts import fontpath


def clear_fonts():
    clear = getattr(character_info.font, "cache_clear", None)
    if clear is not None:
        clear()
    typography._font_cache.clear()
    clear = getattr(typography, "symbol_font", None)
    if clear is not None:
        clear.cache_clear()
    primitives._font.cache_clear()


@pytest.fixture
def bundled_fonts_only(monkeypatch):
    """Emulate a minimal host using real packaged fonts and no system faces."""
    original = ImageFont.truetype
    attempts = []

    def load(font, *args, **kwargs):
        attempts.append(font)
        if not isinstance(font, BytesIO) and Path(font).parent != fontpath:
            raise OSError("System font unavailable")
        return original(font, *args, **kwargs)

    clear_fonts()
    monkeypatch.setattr(ImageFont, "truetype", load)
    yield attempts
    clear_fonts()


def test_character_regular_font_survives_missing_windows_fonts(bundled_fonts_only):
    face = character_info.font(24)
    assert Path(face.path).parent == fontpath
    assert face.getlength("Cyrene 123") > 0


@pytest.mark.parametrize("options", [
    {"bold": True}, {"display": True},
    {"locale": "zh"}, {"locale": "zh", "bold": True},
    {"locale": "ja"}, {"locale": "ja", "bold": True},
    {"locale": "ko"}, {"locale": "ko", "bold": True},
])
def test_character_weights_and_locales_have_packaged_fallbacks(bundled_fonts_only, options):
    face = character_info.font(24, **options)
    assert Path(face.path).parent == fontpath
    assert face.getlength("Card 123") > 0


@pytest.mark.parametrize("weight", ["regular", "semi", "bold"])
def test_skill_text_and_symbols_use_matching_fallbacks(bundled_fonts_only, weight):
    image = Image.new("RGB", (640, 90))
    draw = ImageDraw.Draw(image)
    value = "Cyrene \u2605 \u221e"
    face = typography.font_w(24, weight, text=value)
    assert face.getlength(value) > 0
    measured = text.measure_text_mixed(draw, value, 24, weight, "en")
    drawn = text.draw_text_runs(draw, value, 0, 0, 24, weight, "white", "en")
    assert drawn == pytest.approx(measured)


@pytest.mark.parametrize("weight", ["regular", "source", "bold", "title", "icon"])
def test_build_fonts_survive_without_system_fonts(bundled_fonts_only, weight):
    assert primitives._font(24, weight).getlength("Card 123") > 0


def test_batch_preview_survives_without_system_fonts(bundled_fonts_only, tmp_path):
    Image.new("RGB", (1920, 1440)).save(tmp_path / "acheron.png")
    names = _contact_sheets(tmp_path, [{
        "image": "acheron.png", "slug": "acheron", "review_status": "draft",
    }])
    assert names == ["contact-sheet-01.jpg"]
    with Image.open(tmp_path / names[0]) as image:
        assert image.size == (1440, 1616)
