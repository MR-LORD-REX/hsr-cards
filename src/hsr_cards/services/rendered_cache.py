"""Read and write rendered non-player cards with stable versioned filenames."""
from __future__ import annotations
from collections.abc import Sequence
from pathlib import Path
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from ..core.locale import DEFAULT_LOCALE, normalize_locale
from ..core.paths import comparison_key, default_rendered_cache_dir, safe_filename


_RENDER_REVISION_KEY = "hsr_cards_render_revision"
_CARD_RENDER_REVISIONS = {"skills": "full-page-film-v1"}


class RenderedCardCache:
    """Cache rendered Nanoka cards that do not depend on a player UID.

    Files are named ``{character}_{card_type}_{version}.png``. A comparison
    card uses both builds joined with ``--`` so either render order remains
    discoverable: ``1511_skills_4.6.51--4.6.54.png``.
    """

    def __init__(
        self,
        root: str | Path | None = None,
        *,
        enabled: bool = True,
    ):
        """Store a render-cache root without creating directories or opening files.

        root defaults to .hsr_cards_rendered under the caller's cwd. enabled=False disables
        load(); callers decide whether to invoke save(), which explicitly writes a file.
        """
        self.root = Path(root or default_rendered_cache_dir()).expanduser().resolve()
        self.enabled = enabled

    def path(
        self,
        character: str | int,
        card_type: str,
        version: str | Sequence[str],
        *,
        locale: str = "en",
    ) -> Path:
        """Return the deterministic PNG path for a card identity/type and build selection.

        A string version names one build; a sequence joins ordered builds with --.
        Names are sanitized and non-English locales add a normalized language suffix.
        This method performs no IO; unsupported locales raise ValueError.
        """
        versions = [version] if isinstance(version, str) else list(version)
        key = comparison_key(versions)
        suffix = "" if normalize_locale(locale) == DEFAULT_LOCALE else f"_{normalize_locale(locale)}"
        return self.root / (
            f"{safe_filename(character)}_{safe_filename(card_type)}_"
            f"{key}{suffix}.png"
        )

    def load(
        self,
        character: str | int,
        card_type: str,
        version: str | Sequence[str],
        *,
        locale: str = "en",
    ) -> Image.Image | None:
        """Read a matching cached PNG into a fully decoded RGBA PIL image.

        Identity/type/version/locale follow path(). Return None when disabled, absent,
        outdated, corrupt or unreadable. Skills PNGs must match the current layout
        revision. Unsupported locale errors propagate. The image has no
        remaining file dependency and the cache owns no provider resource.
        """
        if not self.enabled:
            return None
        path = self.path(character, card_type, version, locale=locale)
        if not path.is_file():
            return None
        try:
            with Image.open(path) as image:
                revision = _CARD_RENDER_REVISIONS.get(card_type)
                if revision is not None and image.info.get(_RENDER_REVISION_KEY) != revision:
                    return None
                image.load()
                return image.convert("RGBA")
        except (OSError, ValueError):
            return None

    def save(
        self,
        image: Image.Image,
        character: str | int,
        card_type: str,
        version: str | Sequence[str],
        *,
        locale: str = "en",
    ) -> Path:
        """Write image as an optimized RGBA PNG and return its cache Path.

        Identity/type/version/locale follow path(). Parent directories are created and
        existing images are replaced. Skills PNGs include their layout revision so
        older layouts refresh automatically. This write runs even when enabled=False;
        callers should skip it to disable IO. File/encoder/locale errors propagate.
        """
        path = self.path(character, card_type, version, locale=locale)
        path.parent.mkdir(parents=True, exist_ok=True)
        metadata = None
        revision = _CARD_RENDER_REVISIONS.get(card_type)
        if revision is not None:
            metadata = PngInfo()
            metadata.add_text(_RENDER_REVISION_KEY, revision)
        image.convert("RGBA").save(path, format="PNG", optimize=True, pnginfo=metadata)
        return path

    def clear(self, version: str | None = None) -> int:
        """Delete cached PNGs matching a build token and return the number removed.

        version=None targets all PNGs in this root; otherwise matching filenames, including
        comparison names, are selected. Missing roots return zero and per-file deletion
        errors are skipped. No provider catalogs or assets are removed.
        """
        if not self.root.is_dir():
            return 0
        removed = 0
        token = f"_{safe_filename(version, limit=24)}" if version else None
        for path in self.root.glob("*.png"):
            if token and token not in path.stem:
                continue
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
        return removed
