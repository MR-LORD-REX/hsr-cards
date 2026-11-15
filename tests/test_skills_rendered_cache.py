"""Skills layout changes refresh older PNGs without changing cache paths."""
from PIL import Image
from PIL.PngImagePlugin import PngInfo
import pytest

from hsr_cards.services.rendered_cache import RenderedCardCache


@pytest.mark.parametrize("previous_revision", [None, "older-skills-layout"])
def test_older_skills_cache_is_replaced_and_new_layout_remains_a_cache_hit(tmp_path, previous_revision):
    cache = RenderedCardCache(tmp_path)
    path = cache.path("Blade", "skills", "4.7.51")
    legacy = Image.new("RGBA", (32, 48), (20, 30, 40, 255))
    metadata = PngInfo()
    if previous_revision is not None:
        metadata.add_text("hsr_cards_render_revision", previous_revision)
    legacy.save(path, pnginfo=metadata)

    assert cache.load("Blade", "skills", "4.7.51") is None

    updated = Image.new("RGBA", (32, 48), (70, 80, 90, 255))
    saved = cache.save(updated, "Blade", "skills", "4.7.51")
    assert saved == path == tmp_path / "Blade_skills_4.7.51.png"
    cached = cache.load("Blade", "skills", "4.7.51")
    assert cached is not None
    assert cached.getpixel((0, 0)) == updated.getpixel((0, 0))
    assert cached.info["hsr_cards_render_revision"] == "full-page-film-v1"
    # The fully decoded image no longer depends on its file being open.
    path.unlink()
    assert cached.getpixel((31, 47)) == updated.getpixel((31, 47))


def test_info_cache_remains_usable_without_a_skills_layout_marker(tmp_path):
    cache = RenderedCardCache(tmp_path)
    path = cache.path("Blade", "info", "4.7.51")
    image = Image.new("RGBA", (24, 24), (100, 120, 140, 255))
    image.save(path)

    legacy = cache.load("Blade", "info", "4.7.51")
    assert legacy is not None
    assert legacy.getpixel((0, 0)) == image.getpixel((0, 0))
    assert cache.save(image, "Blade", "info", "4.7.51") == path
    with Image.open(path) as saved:
        assert "hsr_cards_render_revision" not in saved.info
    assert cache.load("Blade", "info", "4.7.51") is not None
