"""Locale normalization for provider-backed card services."""
from hsr_cards.providers.nanoka.locales import Locale
DEFAULT_LOCALE = "en"


def normalize_locale(locale: Locale | str | None) -> str:
    """Return the canonical Nanoka locale string; None/empty values select en and unknown aliases raise ValueError."""
    return Locale.normalize(locale or DEFAULT_LOCALE).value
