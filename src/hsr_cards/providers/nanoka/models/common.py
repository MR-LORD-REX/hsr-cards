"""Shared tolerant models, localization, and provider value conversion."""
from __future__ import annotations
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field
from ..constants import PATH_ALIASES, RARITY_MAP
from ..locales import DEFAULT_LOCALE, Locale


RELIC_SLOT_BY_ID: dict[int, str] = {
    1: "head",
    2: "hands",
    3: "body",
    4: "feet",
    5: "planar_sphere",
    6: "link_rope",
}

class NanokaModel(BaseModel):
    """Tolerant base model: new upstream keys are retained, never rejected."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

class LocalizedText(NanokaModel):
    """Optional English, Chinese, Japanese, and Korean text fields.

    get() resolves supported locale aliases, strips ruby annotations, and permits
    other-language fallback when requested.
    """
    en: str | None = None
    zh: str | None = None
    ja: str | None = None
    ko: str | None = None

    def get(self, locale: Locale | str = DEFAULT_LOCALE, *, fallback: bool = True) -> str | None:
        """Return text for locale, or None if absent and no allowed fallback exists.

        Locale aliases are accepted; fallback=True tries en/zh/ja/ko. Game ruby
        annotations are removed. Invalid locale aliases raise ValueError; no IO occurs.
        """
        return localized_field(
            self, locale, "en", "zh", "ja", "ko", fallback=fallback
        )

class NamedEntry(NanokaModel):
    """A small provider object carrying optional identity, text, and effect parameters."""
    id: int | None = None
    name: str | None = None
    desc: str | None = None
    param: list[float | int] = Field(default_factory=list)
    param_list: list[float | int] = Field(default_factory=list)

class MaterialCost(NanokaModel):
    """A required numeric material item ID and quantity with optional rarity metadata."""
    item_id: int
    item_num: int
    rarity: str | None = None

def localized_field(
    model: NanokaModel,
    locale: Locale | str,
    *keys: str,
    fallback: bool = True,
) -> str | None:
    """Select a model language field, then supplied fallback keys when enabled.

    Return sanitized text or None; locale aliases are accepted and invalid aliases
    raise ValueError. This pure helper removes ruby annotations without IO.
    """
    loc = Locale.normalize(locale)
    value = getattr(model, loc.value, None)
    if value:
        return sanitize_localized_text(value)
    if fallback:
        for key in keys:
            candidate = getattr(model, key, None)
            if candidate:
                return sanitize_localized_text(candidate)
    return None

def sanitize_localized_text(value: str | None) -> str | None:
    """Strip game markup (notably Japanese ruby annotations) for display."""
    if not value:
        return value
    import re

    cleaned = re.sub(r"\{RUBY_B#[^}]*\}", "", value)
    cleaned = re.sub(r"\{RUBY_E#\}", "", cleaned)
    return cleaned.strip()

def parse_rarity(value: str | int | None) -> int | None:
    """Convert a provider rarity label or numeric value to stars, or None if unknown."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text in RARITY_MAP:
        return RARITY_MAP[text]
    digits = "".join(char for char in text if char.isdigit())
    if digits:
        try:
            return int(digits)
        except ValueError:
            return None
    return RARITY_MAP.get(text)

def normalize_path(value: str | None) -> str | None:
    """Convert a provider path codename to its display alias, preserving unknown names."""
    if not value:
        return None
    codename = value.strip().lower()
    return PATH_ALIASES.get(codename, codename)

def normalize_path_codename(value: str | None) -> str | None:
    """Convert a path display alias to its provider codename, preserving unknown names."""
    if not value:
        return None
    needle = value.strip().lower()
    reverse = {path: codename for codename, path in PATH_ALIASES.items()}
    return reverse.get(needle, needle)

def parse_element(value: str | None) -> str | None:
    """Lowercase/trim an element name, or return None for missing text."""
    return value.strip().lower() if value else None

def unix_datetime(value: int | float | None) -> datetime | None:
    """Parse a Unix-seconds timestamp as UTC, or None for absent/out-of-range data."""
    if not value:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None

def parse_datetime(value: str | datetime | None) -> datetime | None:
    """Parse ISO/date text or a datetime into UTC, or None when missing/invalid.

    Naive dates are interpreted as UTC; ISO Z and slash-separated dates are accepted.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return as_utc(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    return as_utc(parsed)

def as_utc(value: datetime | None = None) -> datetime:
    """Return the current UTC time, or normalize a supplied datetime to UTC.

    Naive values are interpreted as UTC rather than the host local timezone.
    """
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

def snake_case(value: str) -> str:
    """Convert provider PascalCase keys into lowercase underscore-separated keys."""
    chars: list[str] = []
    for index, char in enumerate(value):
        if char.isupper() and index and not value[index - 1].isupper():
            chars.append("_")
        chars.append(char.lower())
    return "".join(chars)

def sum_optional(*values: float | None) -> float | None:
    """Sum present values, retaining None when every value is absent."""
    present = [value for value in values if value is not None]
    return sum(present) if present else None

__all__ = ['NanokaModel', 'LocalizedText', 'NamedEntry', 'MaterialCost', 'localized_field', 'sanitize_localized_text', 'parse_rarity', 'normalize_path', 'normalize_path_codename', 'parse_element', 'unix_datetime', 'parse_datetime', 'as_utc', 'snake_case', 'sum_optional', 'RELIC_SLOT_BY_ID']
